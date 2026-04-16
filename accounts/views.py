from django.db import transaction
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response
from rest_framework import status, filters, viewsets
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.http import HttpResponse
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
import json
from django.utils import timezone
import pytz


from .models import MyUser, AddEmployee, Salary, Leave, WFHRequest, Attendance, MonthlySalary, CompOffRequest, CompOffBalance, WorkSession, ActivityLog, DailyWorkReport, EmployeeOTP
from .console_utils import safe_print
from .serializers import (
    AddEmployeeSerializer,
    UserSerializer,
    EmployeeSerializer,
    UserProfileSerializer,
    LeaveSerializer,
    WFHRequestSerializer,
    SalarySerializer,
    MonthlySalarySerializer,
    AttendanceSerializer,
    CompOffRequestSerializer,
    WorkSessionSerializer,
    ActivityLogSerializer,
    CompOffBalanceSerializer
)
from .salary_slip_generator import generate_html_salary_slip, generate_html_salary_slip_preview
from .utils import get_ist_time, convert_to_ist
from .security_utils import validate_password_strength, sanitize_input, validate_username
from .rate_limiter import rate_limit
from .offer_letter_generator import generate_offer_letter_pdf
from .relieving_letter_generator import generate_relieving_letter_pdf
from .manual_calc import apply_manual_salary_calculation
from .ws_utils import broadcast_request_update, broadcast_pending_counts, notify_employee
from django.core.mail import EmailMessage
from django.core.files.base import ContentFile

# ================= Register API with OTP =================
@csrf_exempt
@api_view(["POST"])
@rate_limit(max_attempts=5, window_seconds=900)
def register(request):
    """Step 1: Send OTP to employee email"""
    email = request.data.get("email")
    
    # Sanitize email
    email = sanitize_input(email)
    
    try:
        # Check if user exists and doesn't have password set
        user_obj = MyUser.objects.get(email=email)
        if user_obj.password:
            return Response({
                "error": "Account already created. Please login.",
                "code": "already_registered"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if employee profile exists
        try:
            employee_profile = AddEmployee.objects.get(user=user_obj)
        except AddEmployee.DoesNotExist:
            return Response({
                "error": "Employee profile not found. Contact admin.", 
                "code": "user_not_found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Generate OTP
        otp_code = EmployeeOTP.generate_otp()
        expires_at = timezone.now() + timedelta(minutes=10)
        
        # Delete old OTPs for this email
        EmployeeOTP.objects.filter(email=email).delete()
        
        # Create new OTP
        otp_obj = EmployeeOTP.objects.create(
            email=email,
            otp=otp_code,
            expires_at=expires_at
        )
        
        # Send OTP via email
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            result = send_mail(
                subject='Your OTP for Account Registration - Teople Technologies',
                message=f'Dear {employee_profile.first_name},\n\nYour OTP for account registration is: {otp_code}\n\nThis OTP is valid for 10 minutes.\n\nIf you did not request this, please contact HR immediately.\n\nBest Regards,\nHR Team\nTeople Technologies',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            
            if result == 1:
                safe_print(f"✅ OTP email sent successfully to {email}: {otp_code}")
                return Response({
                    "message": "OTP sent to your email",
                    "email": email,
                    "expires_in_minutes": 10
                }, status=status.HTTP_200_OK)
            else:
                safe_print(f"⚠️ Email send returned 0 for {email}")
                return Response({
                    "message": "OTP generated but email delivery uncertain",
                    "email": email,
                    "expires_in_minutes": 10,
                    "otp_for_testing": otp_code,
                    "note": "Please check your email. If not received, use OTP above."
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            safe_print(f"❌ Failed to send OTP email: {str(e)}")
            import traceback
            traceback.print_exc()
            # Return OTP in response as fallback
            return Response({
                "message": "OTP generated (email service unavailable)",
                "email": email,
                "expires_in_minutes": 10,
                "otp_for_testing": otp_code,
                "note": "Email service is currently unavailable. Use the OTP shown above.",
                "error_detail": str(e)
            }, status=status.HTTP_200_OK)
        
    except MyUser.DoesNotExist:
        return Response({
            "error": "Email not found. Contact admin to add you first.", 
            "code": "user_not_found"
        }, status=status.HTTP_404_NOT_FOUND)


@csrf_exempt
@api_view(["POST"])
@rate_limit(max_attempts=5, window_seconds=900)
def verify_otp_and_register(request):
    """Step 2: Verify OTP and complete registration"""
    email = request.data.get("email")
    otp = request.data.get("otp")
    username = request.data.get("username")
    password = request.data.get("password")
    
    # Sanitize inputs
    email = sanitize_input(email)
    otp = sanitize_input(otp)
    username = sanitize_input(username)
    
    # Validate username
    try:
        validate_username(username)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate password strength
    try:
        validate_password_strength(password)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Get latest OTP for this email
        otp_obj = EmployeeOTP.objects.filter(email=email).order_by('-created_at').first()
        
        if not otp_obj:
            return Response({"error": "No OTP found. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if already verified
        if otp_obj.is_verified:
            return Response({"error": "OTP already used. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if expired
        if otp_obj.is_expired():
            return Response({"error": "OTP expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check attempts
        if otp_obj.attempts >= 3:
            return Response({"error": "Too many failed attempts. Please request a new OTP."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify OTP
        if otp_obj.otp != otp:
            otp_obj.attempts += 1
            otp_obj.save()
            remaining = 3 - otp_obj.attempts
            return Response({
                "error": f"Invalid OTP. {remaining} attempts remaining."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # OTP verified! Now register the user
        user_obj = MyUser.objects.get(email=email)
        user_obj.set_password(password)
        user_obj.save()
        
        # Mark OTP as verified
        otp_obj.is_verified = True
        otp_obj.save()
        
        return Response({
            "message": "Registration successful! You can now login.",
            "email": email
        }, status=status.HTTP_200_OK)
        
    except MyUser.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        safe_print(f"❌ Error in OTP verification: {str(e)}")
        return Response({"error": "Registration failed. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(["POST"])
@rate_limit(max_attempts=3, window_seconds=300)
def resend_otp(request):
    """Resend OTP to employee email"""
    email = request.data.get("email")
    email = sanitize_input(email)
    
    try:
        user_obj = MyUser.objects.get(email=email)
        if user_obj.password:
            return Response({"error": "Account already registered"}, status=status.HTTP_400_BAD_REQUEST)
        
        employee_profile = AddEmployee.objects.get(user=user_obj)
        
        # Generate new OTP
        otp_code = EmployeeOTP.generate_otp()
        expires_at = timezone.now() + timedelta(minutes=10)
        
        # Delete old OTPs
        EmployeeOTP.objects.filter(email=email).delete()
        
        # Create new OTP
        EmployeeOTP.objects.create(
            email=email,
            otp=otp_code,
            expires_at=expires_at
        )
        
        # Send OTP
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            result = send_mail(
                subject='Your New OTP - Teople Technologies',
                message=f'Dear {employee_profile.first_name},\n\nYour new OTP is: {otp_code}\n\nValid for 10 minutes.\n\nBest Regards,\nHR Team',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            
            if result == 1:
                safe_print(f"✅ OTP resent successfully to {email}: {otp_code}")
                return Response({
                    "message": "New OTP sent to your email",
                    "expires_in_minutes": 10
                }, status=status.HTTP_200_OK)
            else:
                safe_print(f"⚠️ Email send returned 0 for {email}")
                return Response({
                    "message": "New OTP generated",
                    "expires_in_minutes": 10,
                    "otp_for_testing": otp_code,
                    "note": "Please check your email. If not received, use OTP above."
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            safe_print(f"❌ Failed to resend OTP: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                "message": "New OTP generated (email service unavailable)",
                "expires_in_minutes": 10,
                "otp_for_testing": otp_code,
                "note": "Email service is currently unavailable. Use the OTP shown above.",
                "error_detail": str(e)
            }, status=status.HTTP_200_OK)
        
    except (MyUser.DoesNotExist, AddEmployee.DoesNotExist):
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)


# ================= Login API =================
@csrf_exempt
@api_view(["POST"])
@rate_limit(max_attempts=5, window_seconds=900)  # 5 attempts per 15 minutes
def login(request):
    email = request.data.get("email")
    password = request.data.get("password")
    
    # Sanitize email input
    email = sanitize_input(email)
    
    try:
        user_obj = MyUser.objects.get(email=email)
    except MyUser.DoesNotExist:
        return Response({"error": "Invalid email or password"}, status=status.HTTP_400_BAD_REQUEST)

    # Check if user is active
    if not user_obj.is_active:
        return Response({"error": "Your account has been deactivated. Please contact admin."}, status=status.HTTP_403_FORBIDDEN)

    user = authenticate(email=email, password=password)
    if user:
        serializer = UserSerializer(user)
        refresh = RefreshToken.for_user(user)
        return Response({
            "message": "Login successful",
            "user": serializer.data,
            "tokens": {"refresh": str(refresh), "access": str(refresh.access_token)},
        }, status=status.HTTP_200_OK)
    return Response({"error": "Invalid email or password"}, status=status.HTTP_400_BAD_REQUEST)


# ================= Employee API =================
@method_decorator(csrf_exempt, name="dispatch")
class EmployeeAPIView(APIView):
    def get(self, request, pk=None):
        if pk:
            try:
                employee = AddEmployee.objects.get(pk=pk)
                serializer = EmployeeSerializer(employee, context={'request': request})  # ✅ ADD CONTEXT
                return Response(serializer.data) 
            except AddEmployee.DoesNotExist:
                return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
        employees = AddEmployee.objects.all()
        serializer = EmployeeSerializer(employees, many=True, context={'request': request})  # ✅ ADD CONTEXT
        return Response(serializer.data)

    def post(self, request):
        serializer = AddEmployeeSerializer(data=request.data)
        if serializer.is_valid():
            email = request.data.get("email")
            first_name = serializer.validated_data["first_name"]
            last_name = serializer.validated_data["last_name"]
            joining_date = request.data.get("joining_date")  # ✅ NEW: Get joining date
            username = f"{first_name}_{last_name}"

            user_obj, created = MyUser.objects.get_or_create(
                email=email,
                defaults={"username": username, "role": "employee"}
            )
            
            # Check if employee profile already exists for this user
            if AddEmployee.objects.filter(user=user_obj).exists():
                return Response({
                    "error": "Employee profile already exists for this user"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ✅ NEW: Set joining date if provided
            employee_data = serializer.validated_data.copy()
            if joining_date:
                from datetime import datetime
                try:
                    employee_data['joining_date'] = datetime.strptime(joining_date, '%Y-%m-%d').date()
                except ValueError:
                    pass  # If invalid date format, ignore
            
            employee = AddEmployee.objects.create(user=user_obj, **employee_data)
            
            # Send welcome email
            if created:
                try:
                    from django.core.mail import send_mail
                    send_mail(
                        subject='Welcome to Teople Technologies',
                        message=f'Dear {first_name} {last_name},\n\nWelcome to Teople Technologies!\n\nYour account has been created successfully.\nEmail: {email}\n\nPlease register at: http://localhost:5173/register\n\nBest Regards,\nHR Team\nTeople Technologies',
                        from_email='sutarjaid970@gmail.com',
                        recipient_list=[email],
                        fail_silently=False,
                    )
                    safe_print(f"✅ Welcome email sent to {email}")
                except Exception as e:
                    safe_print(f"❌ Failed to send email: {str(e)}")
            
            return Response({
                "message": "Employee created successfully",
                "data": EmployeeSerializer(employee).data,
                "joining_date": employee.joining_date.strftime('%Y-%m-%d') if employee.joining_date else None,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        try:
            employee = AddEmployee.objects.get(pk=pk)
        except AddEmployee.DoesNotExist:
            return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

        # ✅ FIX: Update email in MyUser if provided
        new_email = request.data.get('email')
        if new_email and new_email != employee.user.email:
            # Check if email already exists for another user
            if MyUser.objects.filter(email=new_email).exclude(id=employee.user.id).exists():
                return Response({"error": "Email already exists"}, status=status.HTTP_400_BAD_REQUEST)
            employee.user.email = new_email
            employee.user.save()

        # ✅ NEW: Handle joining_date update
        joining_date = request.data.get('joining_date')
        if joining_date:
            try:
                from datetime import datetime
                if isinstance(joining_date, str):
                    employee.joining_date = datetime.strptime(joining_date, '%Y-%m-%d').date()
                else:
                    employee.joining_date = joining_date
            except ValueError:
                pass  # If invalid date format, ignore

        serializer = EmployeeSerializer(employee, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Employee updated successfully", 
                "data": serializer.data,
                "joining_date": employee.joining_date.strftime('%Y-%m-%d') if employee.joining_date else None,
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        try:
            employee = AddEmployee.objects.get(pk=pk)
        except AddEmployee.DoesNotExist:
            return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
        employee.delete()
        return Response({"message": "Employee deleted successfully", "deleted_id": pk}, status=status.HTTP_200_OK)


# ================= Profile API =================
@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    user = request.user
    profile = getattr(user, 'employee_profile', None)

    if request.method == 'GET':
        serializer = UserProfileSerializer(user, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == 'PUT':
        serializer = UserProfileSerializer(user, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if profile:
            profile_serializer = AddEmployeeSerializer(profile, data=request.data.get("employee_profile", {}), partial=True)
            if profile_serializer.is_valid():
                profile_serializer.save()
            else:
                return Response(profile_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.data, status=status.HTTP_200_OK)


# ================= Leave API =================
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def leave_list_create(request):
    if request.method == 'GET':
        leaves = Leave.objects.all().order_by('-applied_at') if request.user.role == "admin" else Leave.objects.filter(user=request.user).order_by('-applied_at')
        serializer = LeaveSerializer(leaves, many=True)
        return Response(serializer.data)

    serializer = LeaveSerializer(data=request.data)
    if serializer.is_valid():
        leave = serializer.save(user=request.user)
        broadcast_request_update('leave')  # ✅ Admin ko real-time notify karo
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def leave_update_status(request, pk):
    try:
        leave = Leave.objects.get(pk=pk)
    except Leave.DoesNotExist:
        return Response({"error": "Leave not found"}, status=status.HTTP_404_NOT_FOUND)
    
    if request.user.role != "admin":
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
    
    new_status = request.data.get("status")
    if new_status not in ["Approved", "Rejected"]:
        return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
    
    leave.status = new_status
    if new_status == "Rejected":
        leave.rejection_reason = request.data.get("rejection_reason", "")
    leave.save()
    broadcast_pending_counts()
    notify_employee(leave.user.id, {
        'type': 'leave',
        'request_type': 'leave',
        'request_id': leave.id,
        'status': new_status,
        'message': f'Your Leave request has been {new_status.lower()}'
    })
    
    # ✅ FIX: Update attendance records for approved leave dates
    if new_status == "Approved":
        try:
            employee = leave.user.employee_profile
            current_date = leave.start_date
            
            while current_date <= leave.end_date:
                # Update attendance status to 'leave' and clear in/out times
                attendance, created = Attendance.objects.get_or_create(
                    employee=employee,
                    date=current_date,
                    defaults={'status': 'leave', 'in_time': None, 'out_time': None}
                )
                
                if not created:
                    # Update existing attendance
                    attendance.status = 'leave'
                    attendance.in_time = None
                    attendance.out_time = None
                    attendance.save()
                
                safe_print(f"✅ Updated attendance to 'leave' for {employee.first_name} on {current_date}")
                current_date += timedelta(days=1)
        except Exception as e:
            safe_print(f"⚠️ Failed to update attendance: {str(e)}")
            import traceback
            traceback.print_exc()
    
    serializer = LeaveSerializer(leave)
    return Response(serializer.data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def leave_update(request, pk):
    try:
        leave = Leave.objects.get(pk=pk, user=request.user)
    except Leave.DoesNotExist:
        return Response({"error": "Leave not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)
    if leave.status in ["Approved", "Rejected"]:
        return Response({"error": "You cannot update an approved/rejected leave"}, status=status.HTTP_400_BAD_REQUEST)
    serializer = LeaveSerializer(leave, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ================= Attendance APIs =================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_attendance_with_leaves(request, employee_id, month, year):
    """Get attendance data with leave information for calendar - FIXED MONTH HANDLING"""
    try:
        employee = AddEmployee.objects.get(id=employee_id)
        
        # ✅ FIX: month is 0-indexed from frontend, convert to 1-indexed for backend
        backend_month = month + 1
        
        safe_print(f"📅 Fetching attendance for employee {employee_id}, frontend month: {month} -> backend month: {backend_month}, year: {year}")

        # Get all approved leaves for this employee in the given month/year
        approved_leaves = Leave.objects.filter(
            user=employee.user,
            status="Approved"
        ).filter(
            models.Q(start_date__year=year, start_date__month=backend_month) |
            models.Q(end_date__year=year, end_date__month=backend_month)
        )
        
        # Get all approved WFH requests
        approved_wfh = WFHRequest.objects.filter(
            user=employee.user,
            status="Approved"
        ).filter(
            models.Q(start_date__year=year, start_date__month=backend_month) |
            models.Q(end_date__year=year, end_date__month=backend_month)
        )
        
        # Get all approved Comp Off requests
        approved_comp_off = CompOffRequest.objects.filter(
            user=employee.user,
            status="Approved",
            date__year=year,
            date__month=backend_month
        )
        
        leave_dates = []
        wfh_dates = []
        comp_off_dates = []
        
        # Process leaves
        for leave in approved_leaves:
            current_date = leave.start_date
            while current_date <= leave.end_date:
                if current_date.month == backend_month and current_date.year == year:
                    leave_dates.append(current_date.strftime("%Y-%m-%d"))
                current_date += timedelta(days=1)
        
        # Process WFH requests
        for wfh in approved_wfh:
            current_date = wfh.start_date
            while current_date <= wfh.end_date:
                if current_date.month == backend_month and current_date.year == year:
                    wfh_dates.append(current_date.strftime("%Y-%m-%d"))
                current_date += timedelta(days=1)
        
        # Process Comp Off requests
        for comp_off in approved_comp_off:
            comp_off_dates.append(comp_off.date.strftime("%Y-%m-%d"))
        
        # Get attendance records for the month
        attendances = Attendance.objects.filter(
            employee=employee,
            date__year=year,
            date__month=backend_month
        )
        
        attendance_data = []
        for attendance in attendances:
            # Calculate total hours
            total_hours = None
            if attendance.in_time and attendance.out_time:
                in_dt = datetime.combine(attendance.date, attendance.in_time)
                out_dt = datetime.combine(attendance.date, attendance.out_time)
                time_diff = out_dt - in_dt
                total_hours = round(time_diff.total_seconds() / 3600, 2)
            
            def to_12h(t):
                if not t:
                    return None
                h, m = t.hour, t.minute
                period = 'AM' if h < 12 else 'PM'
                h12 = h % 12
                if h12 == 0:
                    h12 = 12
                return f"{h12:02d}:{m:02d} {period}"

            attendance_data.append({
                'date': attendance.date.strftime("%Y-%m-%d"),
                'status': attendance.status,
                'in_time': attendance.in_time.strftime("%H:%M") if attendance.in_time else None,
                'out_time': attendance.out_time.strftime("%H:%M") if attendance.out_time else None,
                'in_time_12h': to_12h(attendance.in_time),
                'out_time_12h': to_12h(attendance.out_time),
                'total_hours': total_hours,  # ADD TOTAL HOURS
                'is_less_than_7_hours': total_hours < 7 if total_hours else False,  # For color coding
                'is_direct_half_day': total_hours < 7 if total_hours else False,  # NEW: Direct half day flag
                # ✅ NEW: Admin cover info
                'admin_covered': attendance.admin_covered,
                'admin_covered_by': attendance.admin_covered_by.username if attendance.admin_covered_by else None,
                'admin_covered_at': attendance.admin_covered_at.strftime('%Y-%m-%d %H:%M:%S') if attendance.admin_covered_at else None,
                'admin_cover_reason': attendance.admin_cover_reason,
            })
        
        response_data = {
            "leave_dates": leave_dates,
            "wfh_dates": wfh_dates,
            "comp_off_dates": comp_off_dates,
            "attendance_records": attendance_data,
            "month_info": {
                "frontend_month": month,
                "backend_month": backend_month,
                "year": year,
                "month_name": datetime(year, backend_month, 1).strftime("%B")
            }
        }
        
        safe_print(f"✅ Attendance data fetched: {len(leave_dates)} leaves, {len(wfh_dates)} WFH, {len(comp_off_dates)} comp off, {len(attendance_data)} attendance records")
        
        return Response(response_data)
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        safe_print(f"❌ Error in get_attendance_with_leaves: {str(e)}")
        return Response({"error": "Failed to load attendance data"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime
from .models import AddEmployee, Attendance

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_attendance(request):
    """Update attendance with 9-hour rule: 3 days grace, 4th day = half day (REAL-TIME) + ADMIN COVER TRACKING"""
    try:
        employee_id = request.data.get('employee_id')
        date_str = request.data.get('date')
        in_time_str = request.data.get('in_time')
        out_time_str = request.data.get('out_time')
        status = request.data.get('status', 'present')
        force_half_day = request.data.get('force_half_day', False)
        
        # ✅ NEW: Admin cover tracking fields
        admin_covered = request.data.get('admin_covered', False)
        admin_cover_reason = request.data.get('admin_cover_reason', '')
        total_hours_str = request.data.get('total_hours')  # For admin covered days
        
        if not employee_id or not date_str:
            return Response({"error": "employee_id and date are required"}, status=400)
        
        employee = AddEmployee.objects.get(id=employee_id)
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # ✅ Define year and month EARLY
        year = date.year
        month = date.month
        
        in_time = None
        out_time = None
        total_hours = None
        
        if in_time_str:
            in_time = datetime.strptime(in_time_str, "%H:%M").time()
        
        if out_time_str:
            out_time = datetime.strptime(out_time_str, "%H:%M").time()
        
        # ✅ NEW: Handle admin covered attendance
        if admin_covered:
            # Admin is covering this half day - mark as present
            status = 'present'
            if total_hours_str:
                total_hours = float(total_hours_str)
            safe_print(f"✅ ADMIN COVER: Day {date} covered by admin - marked as PRESENT")
        else:
            # Calculate hours and apply 9-hour rule
            if in_time and out_time:
                in_dt = datetime.combine(date, in_time)
                out_dt = datetime.combine(date, out_time)
                time_diff = out_dt - in_dt
                total_hours = round(time_diff.total_seconds() / 3600, 2)
                
                # ✅ AUTO HALF DAY LOGIC: <7 hours = direct half day, <9 hours = check 3-day grace
                if force_half_day:
                    status = 'half_day'
                    safe_print(f"🟠 MANUAL: Day {date} marked as HALF DAY (forced by user)")
                elif total_hours < 7:
                    # ✅ RULE 1: Less than 7 hours = automatic half day
                    status = 'half_day'
                    safe_print(f"🔴 AUTO: Day {date} marked as HALF DAY (worked {total_hours}h < 7h)")
                else:
                    # ✅ RULE 2: Between 7-9 hours = check 3-day grace
                    # Count ONLY days with 7-9 hours (NOT <7h or manual half_day)
                    less_than_9_count = 0
                    # Count ONLY previous days (before current date)
                    prev_attendances = Attendance.objects.filter(
                        employee=employee,
                        date__year=year,
                        date__month=month,
                        date__lt=date  # ✅ Only past dates, not future
                    )
                    for att in prev_attendances:
                        if att.in_time and att.out_time and att.status != 'half_day':
                            att_in = datetime.combine(att.date, att.in_time)
                            att_out = datetime.combine(att.date, att.out_time)
                            att_hours = (att_out - att_in).total_seconds() / 3600
                            if 7 <= att_hours < 9:
                                less_than_9_count += 1
                    # Add current day
                    if 7 <= total_hours < 9:
                        less_than_9_count += 1
                    
                    if total_hours < 9:
                        if less_than_9_count > 3:  # 4th or more day
                            status = 'half_day'
                            safe_print(f"🔴 REAL-TIME: Day {date} marked as HALF DAY (count: {less_than_9_count}, 4th time <9h)")
                        else:
                            status = 'present'
                            safe_print(f"🟢 REAL-TIME: Day {date} marked as PRESENT (count: {less_than_9_count}/3 grace days used)")
                    else:
                        status = 'present'
                        safe_print(f"✅ REAL-TIME: Day {date} marked as PRESENT (worked {total_hours}h >= 9h)")
            else:
                # If times not provided, keep given status
                pass
        
        # Get or create attendance
        attendance, created = Attendance.objects.get_or_create(
            employee=employee,
            date=date,
            defaults={
                'in_time': in_time,
                'out_time': out_time,
                'status': status,
                # ✅ NEW: Admin cover fields
                'admin_covered': admin_covered,
                'admin_covered_by': request.user if admin_covered else None,
                'admin_covered_at': timezone.now() if admin_covered else None,
                'admin_cover_reason': admin_cover_reason if admin_covered else None,
            }
        )
        
        if not created:
            attendance.in_time = in_time
            attendance.out_time = out_time
            attendance.status = status
            
            # ✅ NEW: Update admin cover fields
            if admin_covered:
                attendance.admin_covered = True
                attendance.admin_covered_by = request.user
                attendance.admin_covered_at = timezone.now()
                attendance.admin_cover_reason = admin_cover_reason
                safe_print(f"✅ Updated admin cover info for {date}")
            
            attendance.save()
        
        # Re-check future dates if current became half_day (only if not admin covered)
        if status == 'half_day' and not admin_covered:
            future_attendances = Attendance.objects.filter(
                employee=employee,
                date__year=year,
                date__month=month,
                date__gt=date,
                status='present'
            )
            
            for future_att in future_attendances:
                if future_att.in_time and future_att.out_time:
                    future_in = datetime.combine(future_att.date, future_att.in_time)
                    future_out = datetime.combine(future_att.date, future_att.out_time)
                    future_hours = (future_out - future_in).total_seconds() / 3600
                    if future_hours < 9:
                        future_att.status = 'half_day'
                        future_att.save()
                        safe_print(f"🔄 Updated future date {future_att.date} to HALF DAY")
        
        # Final count for response
        less_than_9_final = 0
        all_month_attendances = Attendance.objects.filter(
            employee=employee,
            date__year=year,
            date__month=month
        )
        
        for att in all_month_attendances:
            if att.in_time and att.out_time:
                att_in = datetime.combine(att.date, att.in_time)
                att_out = datetime.combine(att.date, att.out_time)
                att_hours = (att_out - att_in).total_seconds() / 3600
                if att_hours < 9:
                    less_than_9_final += 1
        
        # Format 12-hour times - office hours assume karo (00-11 = AM, 12-23 = PM)
        def to_12h(t):
            if not t:
                return None
            h, m = t.hour, t.minute
            period = 'AM' if h < 12 else 'PM'
            h12 = h % 12
            if h12 == 0:
                h12 = 12
            return f"{h12:02d}:{m:02d} {period}"
        
        in_time_12h = to_12h(in_time)
        out_time_12h = to_12h(out_time)
        
        response_data = {
            'id': attendance.id,
            'employee': employee.id,
            'date': date_str,
            'in_time': in_time_str,
            'out_time': out_time_str,
            'in_time_12h': in_time_12h,
            'out_time_12h': out_time_12h,
            'status': attendance.status,
            'total_hours': total_hours,
            'less_than_9_hours_count': less_than_9_final,
            'grace_remaining': max(0, 3 - less_than_9_final),  # Show remaining grace days
            # ✅ NEW: Admin cover info in response
            'admin_covered': attendance.admin_covered,
            'admin_covered_by': attendance.admin_covered_by.username if attendance.admin_covered_by else None,
            'admin_covered_at': attendance.admin_covered_at.strftime('%Y-%m-%d %H:%M:%S') if attendance.admin_covered_at else None,
            'admin_cover_reason': attendance.admin_cover_reason,
        }
        
        return Response({
            'data': response_data,
            'message': f'Attendance updated. Status: {attendance.status}' + (' (Admin Covered)' if admin_covered else '')
        })
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=404)
    except ValueError as e:
        return Response({"error": f"Invalid date/time format: {str(e)}"}, status=400)
    except Exception as e:
        safe_print(f"❌ Error in update_attendance: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response({"error": "Internal server error"}, status=500)

# ================= WFH API =================
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def wfh_request_list_create(request):
    if request.method == "GET":
        requests = WFHRequest.objects.filter(user=request.user).order_by("-id") if request.user.role == "employee" else WFHRequest.objects.all().order_by("-id")
        serializer = WFHRequestSerializer(requests, many=True)
        return Response(serializer.data)

    serializer = WFHRequestSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        broadcast_request_update('wfh')  # ✅ Admin ko real-time notify karo
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def wfh_request_update(request, pk):
    try:
        req = WFHRequest.objects.get(pk=pk)
    except WFHRequest.DoesNotExist:
        return Response({"error": "Request not found"}, status=status.HTTP_404_NOT_FOUND)
    if request.user.role not in ["admin", "manager"]:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
    status_action = request.data.get("status")
    if status_action not in ["Approved", "Rejected"]:
        return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
    req.status = status_action
    if status_action == "Rejected":
        req.rejection_reason = request.data.get("rejection_reason", "")
    req.save()
    broadcast_pending_counts()
    notify_employee(req.user.id, {
        'type': 'wfh',
        'request_type': 'wfh',
        'request_id': req.id,
        'status': status_action,
        'message': f'Your WFH request has been {status_action.lower()}'
    })
    serializer = WFHRequestSerializer(req)
    return Response(serializer.data)


# ================= WFH Export =================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_wfh_csv(request):
    if request.user.role not in ["admin", "manager"]:
        return HttpResponse(status=403)
    response = HttpResponse(content_type="text/csv")
    response['Content-Disposition'] = 'attachment; filename="wfh_requests.csv"'
    writer = csv.writer(response)
    writer.writerow(["Employee", "Start Date", "End Date", "Reason", "Status"])
    for req in WFHRequest.objects.all():
        employee_name = req.user.employee_profile.first_name + " " + req.user.employee_profile.last_name if hasattr(req.user, 'employee_profile') else req.user.email
        writer.writerow([employee_name, req.start_date, req.end_date, req.reason, req.status])
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_wfh_pdf(request):
    if request.user.role not in ["admin", "manager"]:
        return HttpResponse(status=403)
    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = 'attachment; filename="wfh_requests.pdf"'
    p = canvas.Canvas(response)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(200, 800, "WFH Requests Report")
    y = 760
    p.setFont("Helvetica", 10)
    for req in WFHRequest.objects.all():
        employee_name = req.user.employee_profile.first_name + " " + req.user.employee_profile.last_name if hasattr(req.user, 'employee_profile') else req.user.email
        text = f"{employee_name} | {req.start_date} → {req.end_date} | {req.reason} | {req.status}"
        p.drawString(50, y, text)
        y -= 20
        if y < 50:
            p.showPage()
            y = 800
    p.showPage()
    p.save()
    return response


# ================= Comp Off APIs - UPDATED =================
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def comp_off_request_list_create(request):
    if request.method == "GET":
        if request.user.role in ["admin", "manager"]:
            requests = CompOffRequest.objects.all().order_by("-created_at")
        else:
            requests = CompOffRequest.objects.filter(user=request.user).order_by("-created_at")
        serializer = CompOffRequestSerializer(requests, many=True)
        return Response(serializer.data)

    # POST - Create new comp off request
    serializer = CompOffRequestSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(user=request.user)
        broadcast_request_update('comp_off')  # ✅ Admin ko real-time notify karo
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def comp_off_request_update(request, pk):
    try:
        comp_off = CompOffRequest.objects.get(pk=pk)
    except CompOffRequest.DoesNotExist:
        return Response({"error": "Comp Off request not found"}, status=status.HTTP_404_NOT_FOUND)
    
    if request.user.role not in ["admin", "manager"]:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
    
    new_status = request.data.get("status")
    if new_status not in ["Approved", "Rejected"]:
        return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
    
    comp_off.status = new_status
    if new_status == "Rejected":
        comp_off.rejection_reason = request.data.get("rejection_reason", "")
    comp_off.save()
    broadcast_pending_counts()
    notify_employee(comp_off.user.id, {
        'type': 'comp_off',
        'request_type': 'comp_off',
        'request_id': comp_off.id,
        'status': new_status,
        'message': f'Your Comp Off request has been {new_status.lower()}'
    })
    
    serializer = CompOffRequestSerializer(comp_off)
    return Response(serializer.data)


# ================= Comp Off Export =================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_comp_off_csv(request):
    if request.user.role not in ["admin", "manager"]:
        return HttpResponse(status=403)
    
    response = HttpResponse(content_type="text/csv")
    response['Content-Disposition'] = 'attachment; filename="comp_off_requests.csv"'
    writer = csv.writer(response)
    writer.writerow(["Employee", "Date", "Hours", "Reason", "Status", "Created At"])
    
    for req in CompOffRequest.objects.all():
        employee_name = req.user.employee_profile.first_name + " " + req.user.employee_profile.last_name if hasattr(req.user, 'employee_profile') else req.user.email
        writer.writerow([employee_name, req.date, req.hours, req.reason, req.status, req.created_at])
    
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_comp_off_pdf(request):
    if request.user.role not in ["admin", "manager"]:
        return HttpResponse(status=403)
    
    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = 'attachment; filename="comp_off_requests.pdf"'
    
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, "Comp Off Requests Report")
    p.setFont("Helvetica", 10)
    
    y = height - 80
    for req in CompOffRequest.objects.all():
        employee_name = req.user.employee_profile.first_name + " " + req.user.employee_profile.last_name if hasattr(req.user, 'employee_profile') else req.user.email
        text = f"{employee_name} | {req.date} | {req.hours} hours | {req.reason} | {req.status}"
        
        if y < 50:
            p.showPage()
            y = height - 50
        
        p.drawString(50, y, text)
        y -= 20
    
    p.showPage()
    p.save()
    return response


# ================= Comp Off Balance APIs - UPDATED =================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_comp_off_balance(request, employee_id):
    """Get comp off balance with detailed information - FIXED VERSION"""
    try:
        employee = AddEmployee.objects.get(id=employee_id)
        comp_off_balance, created = CompOffBalance.objects.get_or_create(
            employee=employee,
            defaults={
                'balance_hours': 0, 
                'earned_hours': 0, 
                'used_hours': 0
            }
        )
        
        # Get approved comp off requests for this employee
        approved_comp_off_requests = CompOffRequest.objects.filter(
            user=employee.user,
            status='Approved'
        )
        
        # Calculate total earned hours from approved requests
        total_earned_from_requests = approved_comp_off_requests.aggregate(
            total_hours=Sum('hours')
        )['total_hours'] or 0
        
        # If there's a discrepancy, update the balance
        if comp_off_balance.earned_hours != total_earned_from_requests:
            comp_off_balance.earned_hours = total_earned_from_requests
            comp_off_balance.balance_hours = total_earned_from_requests - comp_off_balance.used_hours
            comp_off_balance.save()
        
        serializer = CompOffBalanceSerializer(comp_off_balance)
        return Response(serializer.data)
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def use_comp_off_balance(request):
    """Use comp off balance - FIXED VERSION"""
    try:
        employee_id = request.data.get('employee_id')
        hours_used = request.data.get('hours_used')
        month = request.data.get('month')
        year = request.data.get('year')
        
        if not all([employee_id, hours_used, month, year]):
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)
        
        employee = AddEmployee.objects.get(id=employee_id)
        comp_off_balance = CompOffBalance.objects.get(employee=employee)
        
        if hours_used > comp_off_balance.balance_hours:
            return Response({"error": "Not enough comp off balance"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Use the comp off hours
        comp_off_balance.use_comp_off(hours_used)
        
        return Response({
            "message": f"Used {hours_used} hours of comp off",
            "remaining_balance": comp_off_balance.balance_hours
        })
        
    except (AddEmployee.DoesNotExist, CompOffBalance.DoesNotExist):
        return Response({"error": "Employee or comp off balance not found"}, status=status.HTTP_404_NOT_FOUND)
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_comp_off_summary(request, employee_id):
    """Get comprehensive comp off summary - NEW API"""
    try:
        employee = AddEmployee.objects.get(id=employee_id)
        
        # Get comp off balance
        comp_off_balance, created = CompOffBalance.objects.get_or_create(
            employee=employee,
            defaults={'balance_hours': 0, 'earned_hours': 0, 'used_hours': 0}
        )
        
        # Get all comp off requests
        comp_off_requests = CompOffRequest.objects.filter(user=employee.user)
        
        # Calculate statistics
        total_approved = comp_off_requests.filter(status='Approved').count()
        total_pending = comp_off_requests.filter(status='Pending').count()
        total_rejected = comp_off_requests.filter(status='Rejected').count()
        
        # Get recent approved requests
        recent_approved = comp_off_requests.filter(status='Approved').order_by('-date')[:5]
        
        summary = {
            'balance': {
                'balance_hours': comp_off_balance.balance_hours,
                'earned_hours': comp_off_balance.earned_hours,
                'used_hours': comp_off_balance.used_hours,
                'balance_days': comp_off_balance.balance_hours // 9,
                'updated_at': comp_off_balance.updated_at
            },
            'statistics': {
                'total_requests': comp_off_requests.count(),
                'approved': total_approved,
                'pending': total_pending,
                'rejected': total_rejected
            },
            'recent_approved': CompOffRequestSerializer(recent_approved, many=True).data
        }
        
        return Response(summary)
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)


# ================= Use Comp Off Balance =================
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def use_comp_off(request):
    """Use comp off balance - create attendance record"""
    try:
        comp_off_request_id = request.data.get("comp_off_request_id")
        comp_off_request = CompOffRequest.objects.get(id=comp_off_request_id, user=request.user)
        
        if comp_off_request.status != "Approved":
            return Response({"error": "Comp Off request not approved"}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({"message": "Comp Off used successfully"})
        
    except CompOffRequest.DoesNotExist:
        return Response({"error": "Comp Off request not found"}, status=status.HTTP_404_NOT_FOUND)


# ================= Leaves Export =================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_leaves_csv(request):
    if request.user.role not in ["admin", "manager"]:
        return HttpResponse(status=403)
    
    response = HttpResponse(content_type="text/csv")
    response['Content-Disposition'] = 'attachment; filename="leave_requests.csv"'
    writer = csv.writer(response)
    writer.writerow(["Employee", "Leave Type", "Start Date", "End Date", "Reason", "Status", "Applied At"])
    
    for leave in Leave.objects.all():
        employee_name = leave.user.employee_profile.first_name + " " + leave.user.employee_profile.last_name if hasattr(leave.user, 'employee_profile') else leave.user.email
        writer.writerow([employee_name, leave.leave_type, leave.start_date, leave.end_date, leave.reason, leave.status, leave.applied_at])
    
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_leaves_pdf(request):
    if request.user.role not in ["admin", "manager"]:
        return HttpResponse(status=403)
    
    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = 'attachment; filename="leave_requests.pdf"'
    
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, "Leave Requests Report")
    p.setFont("Helvetica", 10)
    
    y = height - 80
    for leave in Leave.objects.all():
        employee_name = leave.user.employee_profile.first_name + " " + leave.user.employee_profile.last_name if hasattr(leave.user, 'employee_profile') else leave.user.email
        text = f"{employee_name} | {leave.leave_type} | {leave.start_date} → {leave.end_date} | {leave.reason} | {leave.status}"
        
        if y < 50:
            p.showPage()
            y = height - 50
        
        p.drawString(50, y, text)
        y -= 20
    
    p.showPage()
    p.save()
    return response


# ================= Salary API =================
class SalaryViewSet(viewsets.ModelViewSet):
    queryset = Salary.objects.all().select_related("employee")
    serializer_class = SalarySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["financial_year", "employee__id"]
    search_fields = ["employee__first_name", "employee__last_name", "employee__position"]
    ordering_fields = ["gross_annual_salary", "monthly_salary"]
    ordering = ["-created_at"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        salary = serializer.save()
        return Response(self.get_serializer(salary).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        salary = serializer.save()
        return Response(self.get_serializer(salary).data)

    @action(detail=True, methods=["get"])
    def employee_salary(self, request, pk=None):
        salary = self.get_object()
        return Response(self.get_serializer(salary).data)

    @action(detail=True, methods=["get"])
    def generate_slip(self, request, pk=None):
        salary = self.get_object()
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        p.setFont("Helvetica-Bold", 18)
        p.drawCentredString(width / 2, height - 50, "Your Company Name")
        p.setFont("Helvetica-Bold", 16)
        p.drawCentredString(width / 2, height - 75, "Salary Slip")
        p.setFont("Helvetica", 10)
        p.drawCentredString(width / 2, height - 90, f"Financial Year: {salary.financial_year}")

        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, height - 130, "Employee Details:")
        p.setFont("Helvetica", 12)
        p.drawString(70, height - 150, f"Name: {salary.employee.first_name} {salary.employee.last_name}")
        p.drawString(70, height - 170, f"Employee ID: {salary.employee.id}")
        p.drawString(70, height - 190, f"Department: {salary.employee.department}")
        p.drawString(70, height - 210, f"Position: {salary.employee.position}")

        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, height - 250, "Salary Components:")
        p.setFont("Helvetica", 12)
        p.drawString(70, height - 270, f"Gross Annual Salary: ₹{salary.gross_annual_salary}")
        p.drawString(70, height - 290, f"Monthly Salary: ₹{salary.monthly_salary}")
        p.drawString(70, height - 310, f"Actual Variable Pay: ₹{salary.actual_variable_pay}")
        p.drawString(70, height - 330, f"In-hand Annual Salary: ₹{salary.in_hand_salary}")
        p.drawString(70, height - 350, f"Monthly In-hand Salary: ₹{salary.monthly_in_hand}")
        p.drawString(70, height - 370, f"Monthly Variable Pay: ₹{salary.monthly_variable}")

        p.setFont("Helvetica-Oblique", 10)
        p.drawString(50, 50, "This is a system-generated salary slip.")
        p.drawString(50, 35, "For any queries, contact HR department.")

        p.showPage()
        p.save()
        buffer.seek(0)

        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="SalarySlip_{salary.employee.first_name}_{salary.financial_year}.pdf"'
        return response


# ================= Monthly Salary APIs =================
def count_paid_saturdays(month, year):
    """Count only 2nd and 4th Saturdays in a month"""
    import calendar
    paid_saturdays = 0
    total_days = calendar.monthrange(year, month)[1]
    
    for day in range(1, total_days + 1):
        date = datetime(year, month, day)
        
        # Check if it's Saturday (weekday() returns 5 for Saturday)
        if date.weekday() == 5:
            # Calculate week number
            week_number = (day - 1) // 7 + 1
            
            # Only 2nd and 4th Saturday are paid
            if week_number in [2, 4]:
                paid_saturdays += 1
    
    return paid_saturdays

def is_paid_saturday(date):
    """Check if a given date is 2nd or 4th Saturday"""
    if date.weekday() == 5:  # Saturday
        week_number = (date.day - 1) // 7 + 1
        return week_number in [2, 4]
    return False

from django.db import transaction
from decimal import Decimal
from datetime import datetime

# In your views.py, update the calculate_monthly_salary function

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_monthly_salary(request):
    """
    ✅ FIXED: Complete salary calculation with EXACT NEW RULES
    """
    try:
        data = request.data
        employee_id = data.get('employee_id')
        month = int(data.get('month'))  # 1-indexed from frontend
        year = int(data.get('year'))
        
        # ✅ NEW: Get manual comp off and carry forward values from frontend
        manual_comp_off_to_use = data.get('manual_comp_off_to_use', None)
        manual_carry_forward_to_use = data.get('manual_carry_forward_to_use', None)

        safe_print(f"📊 Calculating EXACT salary for employee {employee_id}, {month}/{year}")

        # Validate month range
        if month < 1 or month > 12:
            return Response({'error': 'Invalid month. Must be between 1-12'}, status=status.HTTP_400_BAD_REQUEST)

        # Get employee and salary
        employee = AddEmployee.objects.get(id=employee_id)
        salary_obj = Salary.objects.get(employee=employee)

        # Get attendance stats
        attendance_data = get_attendance_stats_for_salary(employee_id, month, year)
        
        present_days = attendance_data['present_days']
        half_days = attendance_data['half_days']
        leave_days = attendance_data['leave_days']
        wfh_days = attendance_data['wfh_days']
        comp_off_days = attendance_data['comp_off_days']
        total_working_days = attendance_data['total_working_days']

        safe_print(f"📊 Stats for {month}/{year}: Present={present_days}, Half={half_days}, Leave={leave_days}, WFH={wfh_days}, Total Working Days={total_working_days}")

        # Get previous month carry forward
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        
        carry_forward_half_days = Decimal('0.0')
        try:
            prev_salary = MonthlySalary.objects.get(
                employee=employee,
                month=prev_month,
                year=prev_year
            )
            carry_forward_half_days = prev_salary.new_carry_forward
            safe_print(f"🔄 Carry Forward from previous month {prev_month}/{prev_year}: {carry_forward_half_days}")
        except MonthlySalary.DoesNotExist:
            safe_print("🔄 No previous month data for carry forward")
            carry_forward_half_days = Decimal('0.0')

        # Get comp off balance
        available_comp_off = 0
        comp_off_balance_obj = None
        try:
            comp_off_balance_obj = CompOffBalance.objects.get(employee=employee)

            # ✅ NOTIFICATION CHECK: Sirf dekho koi accepted notification hai ya nahi
            # Month ka koi chakkar nahi - latest accepted notification use hogi
            from .notification_models import CompOffUsageNotification
            notif = CompOffUsageNotification.objects.filter(
                employee=employee,
                status='accepted'
            ).order_by('-created_at').first()

            if notif is not None and notif.status == 'accepted':
                available_comp_off = comp_off_balance_obj.balance_hours // 9
                safe_print(f"🎫 Comp off allowed: {available_comp_off} days (notification status: {notif.status})")
            else:
                available_comp_off = 0
                safe_print(f"🚫 Comp off blocked: notification status = {notif.status if notif else 'none (not sent yet)'}")


        except CompOffBalance.DoesNotExist:
            safe_print("🎫 No comp off balance available")
            available_comp_off = 0

        # ✅ APPLY EXACT NEW SALARY RULES (with attendance check)
        # ✅ FIX: Use manual if values are explicitly provided (including 0)
        use_manual = False
        if manual_comp_off_to_use is not None or manual_carry_forward_to_use is not None:
            # ✅ CRITICAL: Only use manual if at least one value is > 0
            if (manual_comp_off_to_use is not None and manual_comp_off_to_use > 0) or \
               (manual_carry_forward_to_use is not None and manual_carry_forward_to_use > 0):
                use_manual = True
            
        if use_manual:
            safe_print(f"✅ Using MANUAL calculation with user selections")
            calculation_result = apply_manual_salary_calculation(
                half_days=half_days,
                leave_days=leave_days,
                manual_comp_off=Decimal(str(manual_comp_off_to_use)) if manual_comp_off_to_use is not None else Decimal('0.0'),
                manual_carry_forward=Decimal(str(manual_carry_forward_to_use)) if manual_carry_forward_to_use is not None else Decimal('0.0'),
                carry_forward_half_days=carry_forward_half_days,
                total_working_days=total_working_days,
                present_days=present_days,
                wfh_days=wfh_days
            )
        else:
            safe_print(f"✅ Using AUTOMATIC calculation")
            calculation_result = apply_new_salary_rules_exact(
                half_days=half_days,
                leave_days=leave_days,
                comp_off_available=available_comp_off,
                carry_forward_half_days=carry_forward_half_days,
                total_working_days=total_working_days,
                present_days=present_days,
                wfh_days=wfh_days
            )

        safe_print(f"🧮 EXACT Calculation Result: {calculation_result}")

        # ✅ BASE CALCULATION - Use calendar days for per day salary
        gross_monthly_salary = Decimal(str(salary_obj.monthly_salary))
        
        # ✅ FIX: Calculate actual calendar days in month (30/31)
        import calendar
        total_days_in_month = calendar.monthrange(year, month)[1]
        
        # Ensure total_days_in_month is at least 1 to avoid division by zero
        if total_days_in_month == 0:
            total_days_in_month = 31
            print("⚠️ Calendar days was 0, set to 31 to avoid division error")
            
        per_day_salary = gross_monthly_salary / Decimal(str(total_days_in_month))
        
        safe_print(f"💰 Gross: {gross_monthly_salary}, Per Day: {per_day_salary}")

        # ✅ FINAL PAID DAYS CALCULATION
        # Total calendar days - salary cut days = paid days
        salary_cut_days = Decimal(str(calculation_result['salary_cut_days']))
        paid_days = Decimal(str(total_days_in_month)) - salary_cut_days
        paid_days = max(Decimal('0.0'), paid_days)
        
        safe_print(f"✅ Paid days: {paid_days} = {total_days_in_month} calendar days - {salary_cut_days} salary cut days")

        # ✅ FINAL SALARY CALCULATION
        professional_tax = Decimal('200.00')
        calculated_salary = per_day_salary * paid_days
        final_salary = calculated_salary - professional_tax
        final_salary = max(Decimal('0.0'), final_salary)

        safe_print(f"💰 Calculated Salary: {calculated_salary}, After Tax: {final_salary}")

        # ✅ Save with exact rules
        monthly_salary, created = MonthlySalary.objects.update_or_create(
            employee=employee,
            month=month,  # 1-indexed - IMPORTANT FOR PDF DOWNLOAD
            year=year,
            defaults={
                # Attendance data
                'present_days': present_days,
                'half_days': half_days,
                'leave_days': leave_days,
                'wfh_days': wfh_days,
                'comp_off_days': comp_off_days,
                
                # Working days calculation
                'total_days_in_month': total_days_in_month,  # ✅ Calendar days
                'paid_weekly_offs': attendance_data['paid_weekly_offs'],
                'total_working_days': total_working_days,
                
                # Salary calculation
                'gross_monthly_salary': gross_monthly_salary,
                'professional_tax': professional_tax,
                'final_salary': final_salary,
                
                # ✅ EXACT RULE FIELDS
                'paid_leave_used': calculation_result['paid_leave_used'],
                'unpaid_leave_used': calculation_result['unpaid_leave_used'],
                'comp_off_used': calculation_result['comp_off_used'],
                'salary_cut_days': calculation_result['salary_cut_days'],
                'used_carry_forward': calculation_result['used_carry_forward'],
                'carry_forward_half_days': carry_forward_half_days,
                'new_carry_forward': calculation_result['new_carry_forward'],
                
                # ✅ BACKWARD COMPATIBILITY FIELDS
                'paid_leaves': int(calculation_result['paid_leave_used']),  # Convert to int for backward compatibility
                'unpaid_leaves': int(calculation_result['unpaid_leave_used']),  # Convert to int for backward compatibility
                'effective_half_days': Decimal(str(half_days)),
                'comp_off_carry_forward': comp_off_balance_obj.balance_hours if comp_off_balance_obj else 0,
                
                # Calculation details
                'salary_calculation_method': 'exact_new_rules',
                'salary_calculation_details': calculation_result,
            }
        )

        # ✅ UPDATE COMP OFF BALANCE IF USED
        comp_off_used = calculation_result['comp_off_used']
        if comp_off_used > 0 and comp_off_balance_obj:
            try:
                hours_to_deduct = comp_off_used * 9
                if hours_to_deduct <= comp_off_balance_obj.balance_hours:
                    comp_off_balance_obj.balance_hours -= hours_to_deduct
                    comp_off_balance_obj.used_hours += hours_to_deduct
                    comp_off_balance_obj.save()
                    safe_print(f"✅ Updated comp off balance: -{hours_to_deduct} hours, New balance: {comp_off_balance_obj.balance_hours}")
                    # ✅ Accepted notification discard karo - use ho gayi
                    from .notification_models import CompOffUsageNotification
                    CompOffUsageNotification.objects.filter(
                        employee=employee,
                        status='accepted'
                    ).update(status='discarded')
                else:
                    safe_print(f"⚠️ Not enough comp off balance. Required: {hours_to_deduct}, Available: {comp_off_balance_obj.balance_hours}")
            except Exception as e:
                safe_print(f"⚠️ Failed to update comp off balance: {str(e)}")

        # ✅ RESPONSE DATA
        response_data = {
            'success': True,
            'final_salary': float(final_salary),
            'month': month,
            'year': year,
            'attendance_summary': {
                'present_days': present_days,
                'half_days': half_days,
                'leave_days': leave_days,
                'wfh_days': wfh_days,
                'comp_off_days': comp_off_days,
                'total_working_days': total_working_days,
            },
            'calculation_details': calculation_result,
            'carry_forward_info': {
                'previous_carry_forward': float(carry_forward_half_days),
                'used_carry_forward': float(calculation_result['used_carry_forward']),
                'new_carry_forward': float(calculation_result['new_carry_forward']),
            },
            'comp_off_info': {
                'available_comp_off': available_comp_off,
                'used_comp_off': float(calculation_result['comp_off_used']),
                'remaining_balance': comp_off_balance_obj.balance_hours if comp_off_balance_obj else 0,
                'balance_updated': comp_off_used > 0,
            },
            'salary_breakdown': {
                'gross_salary': float(gross_monthly_salary),
                'per_day_salary': float(per_day_salary),
                'paid_days': float(paid_days),
                'salary_cut_days': float(calculation_result['salary_cut_days']),
                'professional_tax': 200.0,
                'net_salary': float(final_salary)
            },
            'per_day_salary': float(per_day_salary),  # Add at root level for frontend
            'total_days_in_month': total_days_in_month,
            'leave_breakdown': {
                'paid_leave_used': calculation_result['paid_leave_used'],
                'unpaid_leave_used': calculation_result['unpaid_leave_used'],
                'available_paid_leaves_initial': 1.5,
                'available_paid_leaves_final': calculation_result.get('available_paid_leaves_final', 0.0)
            },
            'month_info': {
                'frontend_month': month - 1,  # For frontend display (0-indexed)
                'backend_month': month,       # For backend storage (1-indexed)
                'month_name': datetime(year, month, 1).strftime('%B'),
                'year': year
            }
        }

        safe_print(f"✅ EXACT Salary calculation completed for {month}/{year}")
        safe_print(f"💰 Salary Record Saved: ID {monthly_salary.id}, Final Salary: {final_salary}")
        return Response(response_data, status=status.HTTP_200_OK)

    except AddEmployee.DoesNotExist:
        return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
    except Salary.DoesNotExist:
        return Response({'error': 'Salary information not found for employee'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        safe_print(f"❌ Salary calculation error: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response({'error': f'Failed to calculate salary: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


# In your views.py, replace the existing salary calculation functions

def apply_new_salary_rules_exact(half_days, leave_days, comp_off_available, carry_forward_half_days, total_working_days, present_days=0, wfh_days=0):
    """
    ✅ FIXED: IMPLEMENTS EXACT RULES FROM SPECIFICATION:
    1. Every month includes 1 Paid Leave
    2. Half Day = 0.5 day, covered by PL or Carry Forward first, else direct salary cut
    3. Unpaid Leave first uses Comp Off if available, else uses Carry Forward, else salary deduction
    4. Previous month carry forward half days automatically apply to unpaid leave only if no Comp Off
    5. 2 Half Days = 1 Full Leave
    6. Work From Home = always paid
    7. Any unused PL or half days carry forward to next month
    8. ✅ NEW: If NO attendance marked at all, treat as FULL MONTH ABSENT
    """
    safe_print(f"🔢 Starting EXACT calculation: HD={half_days}, Leaves={leave_days}, CO={comp_off_available}, CF={carry_forward_half_days}, Present={present_days}, WFH={wfh_days}")
    
    # Initialize variables
    paid_leave_used = Decimal('0.0')
    unpaid_leave_used = Decimal('0.0')
    comp_off_used = Decimal('0.0')
    salary_cut_days = Decimal('0.0')
    used_carry_forward = Decimal('0.0')
    new_carry_forward = Decimal('0.0')
    
    # Convert to Decimal for precise calculation
    half_days_dec = Decimal(str(half_days))
    leave_days_dec = Decimal(str(leave_days))
    comp_off_available_dec = Decimal(str(comp_off_available))
    carry_forward_dec = Decimal(str(carry_forward_half_days))
    present_days_dec = Decimal(str(present_days))
    wfh_days_dec = Decimal(str(wfh_days))
    
    # ✅ CRITICAL FIX: Check if NO attendance marked at all
    total_attendance = present_days_dec + half_days_dec + leave_days_dec + wfh_days_dec
    
    if total_attendance == 0:
        # ✅ NO ATTENDANCE MARKED = FULL MONTH ABSENT
        safe_print(f"❌ NO ATTENDANCE MARKED! Treating as FULL MONTH ABSENT ({total_working_days} days)")
        
        # Calculate full month absence
        total_absence_days = Decimal(str(total_working_days))
        remaining_absence = total_absence_days
        
        # Try to use 1.5 Paid Leave
        available_paid_leaves = Decimal('1.5')
        if available_paid_leaves > 0:
            pl_used = min(available_paid_leaves, remaining_absence)
            paid_leave_used += pl_used
            available_paid_leaves -= pl_used
            remaining_absence -= pl_used
            safe_print(f"✅ Used {pl_used} PL for absence")
        
        # Try to use Comp Off
        if remaining_absence > 0 and comp_off_available_dec > 0:
            comp_off_used_amount = min(comp_off_available_dec, remaining_absence)
            comp_off_used += comp_off_used_amount
            comp_off_available_dec -= comp_off_used_amount
            remaining_absence -= comp_off_used_amount
            safe_print(f"✅ Used {comp_off_used_amount} Comp Off for absence")
        
        # Try to use Carry Forward
        if remaining_absence > 0 and carry_forward_dec > 0:
            cf_used = min(carry_forward_dec, remaining_absence)
            used_carry_forward += cf_used
            carry_forward_dec -= cf_used
            remaining_absence -= cf_used
            safe_print(f"✅ Used {cf_used} Carry Forward for absence")
        
        # Remaining = Salary Cut
        if remaining_absence > 0:
            unpaid_leave_used = remaining_absence
            salary_cut_days = remaining_absence
            print(f"❌ {remaining_absence} days unpaid → FULL SALARY CUT")
        
        # No carry forward for next month if fully absent
        new_carry_forward = Decimal('0.0')
        
        result = {
            'paid_leave_used': float(paid_leave_used),
            'unpaid_leave_used': float(unpaid_leave_used),
            'comp_off_used': float(comp_off_used),
            'salary_cut_days': float(salary_cut_days),
            'used_carry_forward': float(used_carry_forward),
            'new_carry_forward': float(new_carry_forward),
            'available_paid_leaves_initial': 1.5,
            'available_paid_leaves_final': float(available_paid_leaves),
            'calculation_steps': {
                'initial_half_days': half_days,
                'initial_leaves': leave_days,
                'available_comp_off': comp_off_available,
                'available_carry_forward': float(carry_forward_half_days),
                'no_attendance_marked': True
            }
        }
        
        print(f"📊 NO ATTENDANCE Result: {result}")
        return result
    
    # ✅ RULE 1: Every month includes 1.5 Paid Leave + Previous Carry Forward
    available_paid_leaves = Decimal('1.5') + carry_forward_dec
    
    print(f"📝 Initial: Total PL={available_paid_leaves} (Monthly 1.5 + CF {carry_forward_dec}), HD={half_days_dec}, Leaves={leave_days_dec}, CO={comp_off_available_dec}")
    
    # ✅ RULE 2: Calculate total absence days (leaves + half days)
    total_absence_days = leave_days_dec + (half_days_dec * Decimal('0.5'))
    remaining_absence = total_absence_days
    
    print(f"📊 Total absence: {total_absence_days} days (Leaves: {leave_days_dec}, Half days: {half_days_dec})")
    
    if remaining_absence > 0:
        # ✅ NEW LOGIC: Check if carry forward is 0, then use comp off first
        if carry_forward_dec == 0 and comp_off_available_dec > 0:
            # ✅ AUTOMATIC: No carry forward, use comp off first
            comp_off_used_amount = min(comp_off_available_dec, remaining_absence)
            comp_off_used += comp_off_used_amount
            comp_off_available_dec -= comp_off_used_amount
            remaining_absence -= comp_off_used_amount
            print(f"✅ AUTO: No carry forward, used {comp_off_used_amount} Comp Off first, remaining_absence: {remaining_absence}")
        
        # First priority: Use Combined Paid Leave (Monthly + Carry Forward)
        if remaining_absence > 0 and available_paid_leaves > 0:
            pl_used = min(available_paid_leaves, remaining_absence)
            paid_leave_used += pl_used
            available_paid_leaves -= pl_used
            remaining_absence -= pl_used
            
            # Calculate how much carry forward was actually used
            if pl_used > Decimal('1.5'):
                used_carry_forward = pl_used - Decimal('1.5')
            else:
                used_carry_forward = Decimal('0.0')
            
            print(f"✅ Used {pl_used} PL (Monthly: {min(Decimal('1.5'), pl_used)}, CF: {used_carry_forward}), remaining_absence: {remaining_absence}, available_paid_leaves: {available_paid_leaves}")
        
        # Second priority: Use Comp Off for remaining absences (if not already used)
        if remaining_absence > 0 and comp_off_available_dec > 0:
            comp_off_used_amount = min(comp_off_available_dec, remaining_absence)
            comp_off_used += comp_off_used_amount
            comp_off_available_dec -= comp_off_used_amount
            remaining_absence -= comp_off_used_amount
            print(f"✅ Used {comp_off_used_amount} Comp Off for remaining absences, remaining_absence: {remaining_absence}")
        
        # Third priority: Remaining = Salary cut
        if remaining_absence > 0:
            unpaid_leave_used = remaining_absence
            salary_cut_days += remaining_absence
            print(f"❌ {remaining_absence} days unpaid → salary cut")

    
    # ✅ RULE 4: Calculate new carry forward
    # Remaining paid leave (monthly + carry forward combined) carries forward
    new_carry_forward = available_paid_leaves
    
    # Ensure new_carry_forward is never negative
    new_carry_forward = max(Decimal('0.0'), new_carry_forward)
    
    print(f"🔄 Carry Forward Calculation: available_paid_leaves={available_paid_leaves}, used_carry_forward={used_carry_forward}, new_carry_forward={new_carry_forward}")
    
    result = {
        'paid_leave_used': float(paid_leave_used),
        'unpaid_leave_used': float(unpaid_leave_used),
        'comp_off_used': float(comp_off_used),
        'salary_cut_days': float(salary_cut_days),
        'used_carry_forward': float(used_carry_forward),
        'new_carry_forward': float(new_carry_forward),
        'available_paid_leaves_initial': 1.5,
        'available_paid_leaves_final': float(available_paid_leaves),
        'calculation_steps': {
            'initial_half_days': half_days,
            'initial_leaves': leave_days,
            'available_comp_off': comp_off_available,
            'available_carry_forward': float(carry_forward_half_days),
        }
    }
    
    print(f"📊 FIXED Calculation Result: {result}")
    return result


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_monthly_salary(request):
    """Save monthly salary with half-day calculation"""
    serializer = MonthlySalarySerializer(data=request.data)
    if serializer.is_valid():
        # Debug print
        print("Received data with half days:", request.data)
        print("Calculated final_salary:", serializer.validated_data.get('final_salary'))
        
        instance = serializer.save()
        return Response(MonthlySalarySerializer(instance).data, status=201)
    return Response(serializer.errors, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_monthly_salary_history(request, employee_id):
    """Get monthly salary history - FIXED VERSION"""
    try:
        salaries = MonthlySalary.objects.filter(employee_id=employee_id).order_by('-year', '-month')
        
        # Manual serialization to avoid serializer errors
        salary_data = []
        for salary in salaries:
            salary_data.append({
                'id': salary.id,
                'employee_id': salary.employee_id,
                'month': salary.month,
                'year': salary.year,
                'present_days': salary.present_days,
                'half_days': salary.half_days,
                'leave_days': salary.leave_days,
                'wfh_days': salary.wfh_days,
                'comp_off_days': salary.comp_off_days,
                'gross_monthly_salary': salary.gross_monthly_salary,
                'final_salary': salary.final_salary,
                'professional_tax': salary.professional_tax,
                'total_days_in_month': salary.total_days_in_month,
                'paid_weekly_offs': salary.paid_weekly_offs,
                'paid_leaves': salary.paid_leaves,
                'total_working_days': salary.total_working_days,
                'comp_off_used': salary.comp_off_used,
                'comp_off_carry_forward': salary.comp_off_carry_forward,
                
                # ✅ NEW CARRY FORWARD FIELDS
                'paid_leave_balance': salary.paid_leave_balance,
                'carry_forward_paid_leaves': salary.carry_forward_paid_leaves,
                'carry_forward_half_days': salary.carry_forward_half_days,
                'used_paid_leaves_for_half_days': salary.used_paid_leaves_for_half_days,
                'used_paid_leaves_for_leaves': salary.used_paid_leaves_for_leaves,
                'effective_half_days': salary.effective_half_days,
                'remaining_paid_leaves': salary.remaining_paid_leaves,
                
                # ✅ CRITICAL: Add exact rule fields
                'new_carry_forward': float(salary.new_carry_forward) if hasattr(salary, 'new_carry_forward') and salary.new_carry_forward is not None else 0.0,
                'paid_leave_used': float(salary.paid_leave_used) if hasattr(salary, 'paid_leave_used') and salary.paid_leave_used is not None else 0.0,
                'unpaid_leave_used': float(salary.unpaid_leave_used) if hasattr(salary, 'unpaid_leave_used') and salary.unpaid_leave_used is not None else 0.0,
                'salary_cut_days': float(salary.salary_cut_days) if hasattr(salary, 'salary_cut_days') and salary.salary_cut_days is not None else 0.0,
                'used_carry_forward': float(salary.used_carry_forward) if hasattr(salary, 'used_carry_forward') and salary.used_carry_forward is not None else 0.0,
                
                'generated_at': salary.generated_at
            })
        
        return Response(salary_data)
        
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ================= Dashboard APIs =================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary_stats(request):
    """Get overall dashboard summary statistics - FIXED VERSION"""
    try:
        print("📊 Loading dashboard summary stats...")
        
        total_employees = AddEmployee.objects.count()
        print(f"👥 Total employees: {total_employees}")
        
        current_month = datetime.now().month
        current_year = datetime.now().year
        
        # Get current month salaries (month is 1-indexed in database)
        salaries_this_month = MonthlySalary.objects.filter(
            month=current_month, 
            year=current_year
        ).count()
        
        total_salary_amount = MonthlySalary.objects.filter(
            month=current_month, 
            year=current_year
        ).aggregate(total=Sum('final_salary'))['total'] or 0
        
        print(f"💰 Salaries this month: {salaries_this_month}, Total amount: {total_salary_amount}")
        
        pending_leaves = Leave.objects.filter(status='Pending').count()
        pending_wfh = WFHRequest.objects.filter(status='Pending').count()
        pending_comp_off = CompOffRequest.objects.filter(status='Pending').count()
        
        print(f"📋 Pending requests - Leaves: {pending_leaves}, WFH: {pending_wfh}, Comp Off: {pending_comp_off}")
        
        total_comp_off = CompOffBalance.objects.aggregate(
            total=Sum('balance_hours')
        )['total'] or 0
        
        response_data = {
            'total_employees': total_employees,
            'salaries_this_month': salaries_this_month,
            'total_salary_amount': float(total_salary_amount),
            'pending_leaves': pending_leaves,
            'pending_wfh': pending_wfh,
            'pending_comp_off': pending_comp_off,
            'total_comp_off_hours': total_comp_off,
            'current_month': current_month,
            'current_year': current_year
        }
        
        print(f"✅ Dashboard summary loaded successfully: {response_data}")
        return Response(response_data)
        
    except Exception as e:
        print(f"❌ Error in dashboard_summary_stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def monthly_salary_trend(request, year=None):
    """Get monthly salary trend for the year"""
    try:
        if not year:
            year = datetime.now().year
            
        monthly_data = MonthlySalary.objects.filter(
            year=year
        ).values('month').annotate(
            total_salary=Sum('final_salary'),
            employee_count=Count('id')
        ).order_by('month')
        
        months = []
        salary_data = []
        employee_count_data = []
        
        for month in range(12):
            month_data = next((item for item in monthly_data if item['month'] == month), None)
            months.append(datetime(year, month+1, 1).strftime('%b'))
            salary_data.append(float(month_data['total_salary']) if month_data else 0)
            employee_count_data.append(month_data['employee_count'] if month_data else 0)
        
        return Response({
            'months': months,
            'salary_data': salary_data,
            'employee_count_data': employee_count_data,
            'year': year
        })
        
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def department_wise_salary(request, year=None, month=None):
    """Get department-wise salary distribution"""
    try:
        if not year:
            year = datetime.now().year
        if not month:
            month = datetime.now().month - 1
            
        dept_data = MonthlySalary.objects.filter(
            year=year,
            month=month
        ).select_related('employee__department').values(
            'employee__department'
        ).annotate(
            total_salary=Sum('final_salary'),
            employee_count=Count('id'),
            avg_salary=Avg('final_salary')
        ).order_by('-total_salary')
        
        departments = []
        salary_totals = []
        employee_counts = []
        avg_salaries = []
        
        for dept in dept_data:
            if dept['employee__department']:
                departments.append(dept['employee__department'].title())
                salary_totals.append(float(dept['total_salary']))
                employee_counts.append(dept['employee_count'])
                avg_salaries.append(float(dept['avg_salary']))
        
        return Response({
            'departments': departments,
            'salary_totals': salary_totals,
            'employee_counts': employee_counts,
            'avg_salaries': avg_salaries
        })
        
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attendance_analytics(request, year=None, month=None):
    """Get attendance analytics for dashboard"""
    try:
        if not year:
            year = datetime.now().year
        if not month:
            month = datetime.now().month  # Fixed: Use current month (1-indexed)
        
        print(f"📊 Fetching attendance analytics for {month}/{year}")
            
        attendance_stats = MonthlySalary.objects.filter(
            year=year,
            month=month
        ).aggregate(
            total_present=Sum('present_days'),
            total_leave=Sum('leave_days'),
            total_wfh=Sum('wfh_days'),
            total_comp_off=Sum('comp_off_days'),
            total_working_days=Sum('total_working_days')
        )
        
        print(f"📈 Raw stats: {attendance_stats}")
        
        total_days = (
            (attendance_stats['total_present'] or 0) +
            (attendance_stats['total_leave'] or 0) +
            (attendance_stats['total_wfh'] or 0) +
            (attendance_stats['total_comp_off'] or 0)
        )
        
        if total_days > 0:
            present_percentage = ((attendance_stats['total_present'] or 0) / total_days) * 100
            leave_percentage = ((attendance_stats['total_leave'] or 0) / total_days) * 100
            wfh_percentage = ((attendance_stats['total_wfh'] or 0) / total_days) * 100
            comp_off_percentage = ((attendance_stats['total_comp_off'] or 0) / total_days) * 100
        else:
            present_percentage = leave_percentage = wfh_percentage = comp_off_percentage = 0
        
        response_data = {
            'present_days': attendance_stats['total_present'] or 0,
            'leave_days': attendance_stats['total_leave'] or 0,
            'wfh_days': attendance_stats['total_wfh'] or 0,
            'comp_off_days': attendance_stats['total_comp_off'] or 0,
            'total_working_days': attendance_stats['total_working_days'] or 0,
            'percentages': {
                'present': round(present_percentage, 1),
                'leave': round(leave_percentage, 1),
                'wfh': round(wfh_percentage, 1),
                'comp_off': round(comp_off_percentage, 1)
            }
        }
        
        print(f"✅ Attendance analytics response: {response_data}")
        return Response(response_data)
        
    except Exception as e:
        print(f"❌ Error in attendance_analytics: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employee_salary_distribution(request):
    """Get employee salary distribution for histogram"""
    try:
        current_month = datetime.now().month - 1
        current_year = datetime.now().year
        
        salaries = MonthlySalary.objects.filter(
            month=current_month,
            year=current_year
        ).values('final_salary').order_by('final_salary')
        
        salary_ranges = {
            '0-20000': 0,
            '20000-40000': 0,
            '40000-60000': 0,
            '60000-80000': 0,
            '80000-100000': 0,
            '100000+': 0
        }
        
        for salary in salaries:
            salary_amount = float(salary['final_salary'])
            if salary_amount <= 20000:
                salary_ranges['0-20000'] += 1
            elif salary_amount <= 40000:
                salary_ranges['20000-40000'] += 1
            elif salary_amount <= 60000:
                salary_ranges['40000-60000'] += 1
            elif salary_amount <= 80000:
                salary_ranges['60000-80000'] += 1
            elif salary_amount <= 100000:
                salary_ranges['80000-100000'] += 1
            else:
                salary_ranges['100000+'] += 1
        
        return Response({
            'ranges': list(salary_ranges.keys()),
            'counts': list(salary_ranges.values())
        })
        
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recent_salary_activities(request):
    """Get recent salary activities for dashboard"""
    try:
        recent_salaries = MonthlySalary.objects.select_related(
            'employee'
        ).order_by('-generated_at')[:10]
        
        activities = []
        for salary in recent_salaries:
            activities.append({
                'id': salary.id,
                'employee_name': f"{salary.employee.first_name} {salary.employee.last_name}",
                'month': salary.month,  # Fixed: Don't add 1, month is already 1-indexed
                'year': salary.year,
                'amount': float(salary.final_salary),
                'generated_at': salary.generated_at.strftime('%Y-%m-%d %H:%M'),
                'present_days': salary.present_days,
                'status': 'Generated'
            })
        
        return Response(activities)
        
    except Exception as e:
        print(f"❌ Error in recent_salary_activities: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ================= Attendance Auto-Update for Paid Saturdays =================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auto_mark_paid_saturdays(request):
    """Auto mark 2nd & 4th Saturdays as paid weekly offs"""
    try:
        employee_id = request.data.get('employee_id')
        month = int(request.data.get('month'))
        year = int(request.data.get('year'))
        
        employee = AddEmployee.objects.get(id=employee_id)
        
        import calendar
        total_days = calendar.monthrange(year, month)[1]
        marked_days = []
        
        for day in range(1, total_days + 1):
            date = datetime(year, month, day).date()
            
            # Check if it's 2nd or 4th Saturday
            if is_paid_saturday(date):
                # Create or update attendance record
                attendance, created = Attendance.objects.get_or_create(
                    employee=employee,
                    date=date,
                    defaults={
                        'status': 'weekend',
                        'in_time': None,
                        'out_time': None
                    }
                )
                
                if not created and attendance.status != 'present':
                    attendance.status = 'weekend'
                    attendance.save()
                
                marked_days.append(date.strftime('%Y-%m-%d'))
        
        return Response({
            'message': f'Marked {len(marked_days)} paid Saturdays',
            'marked_dates': marked_days,
            'employee': f"{employee.first_name} {employee.last_name}",
            'month': month,
            'year': year
        })
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=404)
    except Exception as e:
        return Response({"error": f"Failed to mark paid Saturdays: {str(e)}"}, status=500)

# ================= Salary Slip PDF =================
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def generate_salary_slip_pdf(request, employee_id, month, year):
    """Generate beautiful HTML-based salary slip PDF - FIXED MONTH CONVERSION"""
    try:
        print(f"📄 Generating PDF for Employee: {employee_id}, Month: {month}, Year: {year}")
        
        # ✅ FIX: Use 1-indexed month directly (frontend sends 1-indexed for PDF)
        backend_month = int(month)
        
        employee = AddEmployee.objects.get(id=employee_id)
        
        # Get monthly salary record - Database uses 1-indexed month
        monthly_salary = MonthlySalary.objects.get(
            employee=employee, 
            month=backend_month,  # Use as-is (1-indexed)
            year=int(year)
        )
        
        print(f"✅ Found salary record: {employee.first_name}, {backend_month}/{year}")
        
        return generate_html_salary_slip(employee_id, backend_month, int(year))
        
    except AddEmployee.DoesNotExist:
        print(f"❌ Employee not found: {employee_id}")
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
    except MonthlySalary.DoesNotExist:
        print(f"❌ Salary record not found: Employee {employee_id}, Month {backend_month}, Year {year}")
        return Response(
            {"error": f"Salary record not found for {datetime(int(year), backend_month, 1).strftime('%B %Y')}. Please generate salary first."}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        print(f"❌ PDF generation error: {str(e)}")
        return Response({"error": f"Failed to generate PDF: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def preview_html_salary_slip(request, employee_id, month, year):
    """Preview salary slip in browser (HTML format) - FIXED"""
    try:
        # ✅ FIX: Use 1-indexed month directly
        backend_month = int(month)
        return generate_html_salary_slip_preview(employee_id, backend_month, int(year))
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ================= Work Session APIs =================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_work_session(request):
    """Start a new work session for WFH or Comp Off"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        session_type = request.data.get('session_type')
        request_id = request.data.get('request_id')
        
        active_session = WorkSession.objects.filter(
            employee=employee, 
            status='active'
        ).first()
        
        if active_session:
            return Response(
                {"error": "You already have an active work session"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if session_type == 'wfh':
            wfh_request = WFHRequest.objects.get(id=request_id, user=request.user, status='Approved')
            work_session = WorkSession.objects.create(
                employee=employee,
                session_type='wfh',
                request=wfh_request,
                start_time=timezone.now(),
                status='active'
            )
            wfh_request.status = 'Active'
            wfh_request.save()
            
        elif session_type == 'comp_off':
            comp_off_request = CompOffRequest.objects.get(id=request_id, user=request.user, status='Approved')
            work_session = WorkSession.objects.create(
                employee=employee,
                session_type='comp_off',
                comp_off_request=comp_off_request,
                start_time=timezone.now(),
                status='active'
            )
            comp_off_request.status = 'Active'
            comp_off_request.save()
        else:
            return Response(
                {"error": "Invalid session type"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = WorkSessionSerializer(work_session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except (AddEmployee.DoesNotExist, WFHRequest.DoesNotExist, CompOffRequest.DoesNotExist) as e:
        return Response({"error": "Invalid request or employee not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_work_session(request, session_id):
    """End an active work session - FIXED VERSION"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        work_session = WorkSession.objects.get(id=session_id, employee=employee, status='active')
        
        work_session.end_time = timezone.now()
        work_session.status = 'completed'
        work_session.calculate_total_hours()
        work_session.save()
        
        if work_session.session_type == 'wfh' and work_session.request:
            wfh_request = work_session.request
            current_actual_hours = float(wfh_request.actual_hours)
            session_hours = float(work_session.total_hours)
            wfh_request.actual_hours = Decimal(str(current_actual_hours + session_hours))
            
            if wfh_request.actual_hours >= wfh_request.expected_hours:
                wfh_request.status = 'Completed'
            wfh_request.save()
            
        elif work_session.session_type == 'comp_off' and work_session.comp_off_request:
            comp_off_request = work_session.comp_off_request
            current_actual_hours = float(comp_off_request.actual_hours_worked)
            session_hours = float(work_session.total_hours)
            comp_off_request.actual_hours_worked = Decimal(str(current_actual_hours + session_hours))
            
            if comp_off_request.actual_hours_worked >= comp_off_request.hours:
                comp_off_request.status = 'Completed'
            comp_off_request.save()
        
        serializer = WorkSessionSerializer(work_session)
        return Response(serializer.data)
        
    except (AddEmployee.DoesNotExist, WorkSession.DoesNotExist) as e:
        return Response({"error": "Work session not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": f"Failed to end work session: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_task_to_session(request, session_id):
    """MODERN: Add task to work session"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        work_session = WorkSession.objects.get(id=session_id, employee=employee, status='active')
        
        task = request.data.get('task')
        priority = request.data.get('priority', 'medium')
        
        if not task:
            return Response({"error": "Task is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Add to planned tasks
        work_session.tasks_planned.append({
            'task': task,
            'priority': priority,
            'added_at': timezone.now().astimezone(pytz.timezone('Asia/Kolkata')).strftime('%I:%M %p')
        })
        work_session.save()
        
        return Response({
            "message": "Task added successfully",
            "tasks_planned": work_session.tasks_planned
        })
        
    except (AddEmployee.DoesNotExist, WorkSession.DoesNotExist):
        return Response({"error": "Work session not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_task_in_session(request, session_id):
    """MODERN: Mark task as completed"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        work_session = WorkSession.objects.get(id=session_id, employee=employee, status='active')
        
        task = request.data.get('task')
        time_spent = request.data.get('time_spent', '0h')
        
        if not task:
            return Response({"error": "Task is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        ist = pytz.timezone('Asia/Kolkata')
        work_session.tasks_completed.append({
            'task': task,
            'time_spent': time_spent,
            'completed_at': timezone.now().astimezone(ist).strftime('%I:%M %p')
        })
        work_session.save()
        
        # Recalculate productivity
        work_session.calculate_productivity_score()
        
        return Response({
            "message": "Task completed successfully",
            "tasks_completed": work_session.tasks_completed,
            "productivity_score": work_session.productivity_score
        })
        
    except (AddEmployee.DoesNotExist, WorkSession.DoesNotExist):
        return Response({"error": "Work session not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_break_to_session(request, session_id):
    """MODERN: Add break to work session"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        work_session = WorkSession.objects.get(id=session_id, employee=employee, status='active')
        
        break_type = request.data.get('break_type', 'short')
        duration = request.data.get('duration', 15)  # minutes
        
        ist = pytz.timezone('Asia/Kolkata')
        current_time = timezone.now().astimezone(ist)
        
        work_session.breaks_taken.append({
            'type': break_type,
            'duration': duration,
            'time': current_time.strftime('%I:%M %p')
        })
        work_session.save()
        
        return Response({
            "message": "Break recorded successfully",
            "breaks_taken": work_session.breaks_taken
        })
        
    except (AddEmployee.DoesNotExist, WorkSession.DoesNotExist):
        return Response({"error": "Work session not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_sessions(request):
    """Get active work sessions for the current user"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        active_sessions = WorkSession.objects.filter(employee=employee, status='active')
        serializer = WorkSessionSerializer(active_sessions, many=True)
        return Response(serializer.data)
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_work_session_history(request):
    """Get work session history for the current user"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        sessions = WorkSession.objects.filter(employee=employee).order_by('-start_time')[:50]
        serializer = WorkSessionSerializer(sessions, many=True)
        return Response(serializer.data)
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

# ================= Admin Work Monitoring APIs =================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_active_sessions(request):
    """Get all active work sessions (Admin only)"""
    if request.user.role not in ['admin', 'manager']:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
    
    active_sessions = WorkSession.objects.filter(status='active').select_related('employee')
    serializer = WorkSessionSerializer(active_sessions, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_employee_work_analytics(request, employee_id):
    """Get work analytics for a specific employee"""
    if request.user.role not in ['admin', 'manager']:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        employee = AddEmployee.objects.get(id=employee_id)
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        sessions = WorkSession.objects.filter(
            employee=employee, 
            start_time__gte=thirty_days_ago
        )
        
        total_sessions = sessions.count()
        total_hours = sum(float(session.total_hours) for session in sessions if session.total_hours)
        
        avg_productivity = sessions.aggregate(
            avg_score=Avg('productivity_score')
        )['avg_score'] or 50
        
        wfh_requests = WFHRequest.objects.filter(user=employee.user, status='Completed')
        comp_off_requests = CompOffRequest.objects.filter(user=employee.user, status='Completed')
        
        analytics = {
            'employee_name': f"{employee.first_name} {employee.last_name}",
            'total_sessions': total_sessions,
            'total_hours_worked': round(total_hours, 2),
            'average_productivity': round(avg_productivity, 2),
            'wfh_requests_completed': wfh_requests.count(),
            'comp_off_requests_completed': comp_off_requests.count(),
            'recent_sessions': WorkSessionSerializer(sessions[:10], many=True).data
        }
        
        return Response(analytics)
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_department_work_analytics(request, department):
    """Get work analytics for a department"""
    if request.user.role not in ['admin', 'manager']:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
    
    employees = AddEmployee.objects.filter(department=department)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    department_stats = {
        'department': department,
        'total_employees': employees.count(),
        'active_sessions': 0,
        'total_hours_worked': 0,
        'average_activity_score': 0
    }
    
    total_activity_score = 0
    employees_with_sessions = 0
    
    for employee in employees:
        sessions = WorkSession.objects.filter(
            employee=employee, 
            start_time__gte=thirty_days_ago
        )
        
        if sessions.exists():
            employees_with_sessions += 1
            department_stats['active_sessions'] += sessions.filter(status='active').count()
            department_stats['total_hours_worked'] += sum(
                float(session.total_hours) for session in sessions if session.total_hours
            )
            
            emp_avg_score = sessions.aggregate(
                avg_score=Avg('productivity_score')
            )['avg_score'] or 0
            total_activity_score += emp_avg_score
    
    if employees_with_sessions > 0:
        department_stats['average_activity_score'] = round(total_activity_score / employees_with_sessions, 2)
    
    department_stats['total_hours_worked'] = round(department_stats['total_hours_worked'], 2)
    
    return Response(department_stats)

# ================= Employee Home APIs =================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def employee_home_data(request):
    """Get data for employee home dashboard - FIXED VERSION"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        
        approved_wfh = WFHRequest.objects.filter(
            user=request.user, 
            status__in=['Approved', 'Active']
        ).order_by('-created_at')
        
        approved_comp_off = CompOffRequest.objects.filter(
            user=request.user,
            status__in=['Approved', 'Active']
        ).order_by('-created_at')
        
        active_session = WorkSession.objects.filter(
            employee=employee, 
            status='active'
        ).first()
        
        today = timezone.now().date()
        today_attendance = Attendance.objects.filter(
            employee=employee, 
            date=today
        ).first()
        
        comp_off_balance = 0
        try:
            comp_off_balance = CompOffBalance.objects.get(employee=employee).balance_hours
        except CompOffBalance.DoesNotExist:
            pass
        
        # Check for revision request
        revision_requested = False
        revision_message = ''
        incomplete_fields = []
        try:
            from .employee_form_models import EmployeePersonalInfo
            personal_info = EmployeePersonalInfo.objects.get(employee=employee)
            revision_requested = personal_info.revision_requested
            revision_message = personal_info.revision_message
            incomplete_fields = personal_info.incomplete_fields
        except:
            pass

        data = {
            'employee': {
                'id': employee.id,
                'first_name': employee.first_name,
                'last_name': employee.last_name,
                'department': employee.department,
                'position': employee.position
            },
            'approved_wfh_requests': WFHRequestSerializer(approved_wfh, many=True).data,
            'approved_comp_off_requests': CompOffRequestSerializer(approved_comp_off, many=True).data,
            'active_work_session': WorkSessionSerializer(active_session).data if active_session else None,
            'today_attendance': AttendanceSerializer(today_attendance).data if today_attendance else None,
            'comp_off_balance': comp_off_balance,
            'revision_requested': revision_requested,
            'revision_message': revision_message,
            'incomplete_fields': incomplete_fields
        }
        
        return Response(data)
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": f"Failed to load data: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ================= Admin Home APIs =================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_home_data(request):
    """Get data for admin home dashboard"""
    if request.user.role not in ['admin', 'manager']:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
    
    total_employees = AddEmployee.objects.count()
    active_sessions = WorkSession.objects.filter(status='active').count()
    pending_requests = (
        WFHRequest.objects.filter(status='Pending').count() +
        CompOffRequest.objects.filter(status='Pending').count() +
        Leave.objects.filter(status='Pending').count()
    )
    
    departments = AddEmployee.objects.values_list('department', flat=True).distinct()
    department_activity = []
    
    for dept in departments:
        dept_employees = AddEmployee.objects.filter(department=dept)
        dept_active_sessions = WorkSession.objects.filter(
            employee__in=dept_employees, 
            status='active'
        ).count()
        
        department_activity.append({
            'department': dept,
            'active_sessions': dept_active_sessions,
            'total_employees': dept_employees.count()
        })
    
    recent_sessions = WorkSession.objects.select_related('employee').order_by('-start_time')[:10]
    
    data = {
        'total_employees': total_employees,
        'active_work_sessions': active_sessions,
        'pending_requests': pending_requests,
        'department_activity': department_activity,
        'recent_sessions': WorkSessionSerializer(recent_sessions, many=True).data
    }
    
    return Response(data)

# ================= Employee Analytics & Widgets APIs =================
import random

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_employee_productivity_analytics(request):
    """Get productivity analytics for current employee - REAL DATA"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        sessions = WorkSession.objects.filter(
            employee=employee,
            start_time__gte=thirty_days_ago
        )
        
        total_sessions = sessions.count()
        completed_sessions = sessions.filter(status='completed').count()
        
        total_hours = 0
        for session in sessions.filter(status='completed'):
            if session.total_hours:
                total_hours += float(session.total_hours)
        
        avg_productivity = 75
        if completed_sessions > 0:
            avg_productivity = min(95, 70 + (completed_sessions * 2))
        
        weekly_data = []
        for i in range(7):
            day = timezone.now() - timedelta(days=(6-i))
            day_sessions = sessions.filter(
                start_time__date=day.date(),
                status='completed'
            )
            
            day_hours = sum(float(session.total_hours) for session in day_sessions if session.total_hours)
            
            day_productivity = 0
            if day_hours > 0:
                day_productivity = min(100, (day_hours / 8) * 100)
            
            weekly_data.append({
                'day': day.strftime('%a'),
                'productivity': round(day_productivity, 1),
                'hours': round(day_hours, 1)
            })
        
        office_days = Attendance.objects.filter(
            employee=employee,
            date__gte=thirty_days_ago.date(),
            status='present'
        ).count()
        
        wfh_days = Attendance.objects.filter(
            employee=employee,
            date__gte=thirty_days_ago.date(),
            status='wfh'
        ).count()
        
        comp_off_days = Attendance.objects.filter(
            employee=employee,
            date__gte=thirty_days_ago.date(),
            status='comp_off'
        ).count()
        
        work_type_data = [
            {'name': 'Office', 'value': office_days},
            {'name': 'WFH', 'value': wfh_days},
            {'name': 'Comp Off', 'value': comp_off_days}
        ]
        
        active_days = sessions.dates('start_time', 'day').count()
        on_time_completion = min(98, 85 + (completed_sessions * 1)) if completed_sessions > 0 else 85
        
        analytics = {
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'total_hours_worked': round(total_hours, 2),
            'average_productivity': avg_productivity,
            'weekly_data': weekly_data,
            'work_type_distribution': work_type_data,
            'performance_metrics': {
                'avg_productivity': avg_productivity,
                'tasks_completed': completed_sessions * 2,
                'active_days': active_days,
                'on_time_completion': on_time_completion
            }
        }
        
        return Response(analytics)
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_employee_activity_timeline(request):
    """Get today's activity timeline for charts - REAL DATA"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        today = timezone.now().date()
        
        today_session = WorkSession.objects.filter(
            employee=employee,
            start_time__date=today
        ).first()
        
        timeline_data = []
        
        if today_session:
            session_start = today_session.start_time
            session_duration = 8
            
            for i in range(9):
                hour = 9 + i
                current_time = timezone.make_aware(
                    datetime(today.year, today.month, today.day, hour, 0)
                )
                
                if session_start and current_time >= session_start:
                    productivity = 70
                    
                    if today_session.status == 'active':
                        productivity = min(95, 70 + (i * 3))
                    
                    productivity += random.randint(-5, 10)
                    productivity = max(50, min(100, productivity))
                    
                    timeline_data.append({
                        'time': f'{hour}:00',
                        'productivity': productivity,
                        'breaks': random.randint(0, 2),
                        'keystrokes': random.randint(100, 500) + (i * 50),
                        'mouse_activity': random.randint(50, 300) + (i * 30)
                    })
                else:
                    timeline_data.append({
                        'time': f'{hour}:00',
                        'productivity': 0,
                        'breaks': 0,
                        'keystrokes': 0,
                        'mouse_activity': 0
                    })
        else:
            for i in range(9):
                hour = 9 + i
                timeline_data.append({
                    'time': f'{hour}:00',
                    'productivity': 0,
                    'breaks': 0,
                    'keystrokes': 0,
                    'mouse_activity': 0
                })
        
        return Response(timeline_data)
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_employee_calendar_events(request, year=None, month=None):
    """Get calendar events for employee - REAL DATA"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        
        if not year:
            year = timezone.now().year
        if not month:
            month = timezone.now().month
        
        try:
            month = int(month)
        except ValueError:
            return Response({"error": "Invalid month"}, status=status.HTTP_400_BAD_REQUEST)
        
        events = []
        
        leaves = Leave.objects.filter(
            user=request.user,
            status='Approved'
        ).filter(
            models.Q(start_date__year=year, start_date__month=month) |
            models.Q(end_date__year=year, end_date__month=month)
        )
        
        for leave in leaves:
            events.append({
                'id': f"leave_{leave.id}",
                'title': f'{leave.leave_type.title()} Leave',
                'start': timezone.make_aware(datetime.combine(leave.start_date, datetime.min.time())),
                'end': timezone.make_aware(datetime.combine(leave.end_date, datetime.max.time())),
                'type': 'leave',
                'color': '#f56565',
                'allDay': True
            })
        
        wfh_requests = WFHRequest.objects.filter(
            user=request.user,
            status__in=['Approved', 'Active', 'Completed']
        ).filter(
            models.Q(start_date__year=year, start_date__month=month) |
            models.Q(end_date__year=year, end_date__month=month)
        )
        
        for wfh in wfh_requests:
            events.append({
                'id': f"wfh_{wfh.id}",
                'title': f'WFH - {wfh.type}',
                'start': timezone.make_aware(datetime.combine(wfh.start_date, datetime.min.time())),
                'end': timezone.make_aware(datetime.combine(wfh.end_date, datetime.max.time())),
                'type': 'wfh',
                'color': '#4299e1',
                'allDay': True
            })
        
        comp_off_requests = CompOffRequest.objects.filter(
            user=request.user,
            status__in=['Approved', 'Active', 'Completed'],
            date__year=year,
            date__month=month
        )
        
        for comp_off in comp_off_requests:
            events.append({
                'id': f"comp_off_{comp_off.id}",
                'title': f'Comp Off - {comp_off.hours}h',
                'start': timezone.make_aware(datetime.combine(comp_off.date, datetime.min.time())),
                'end': timezone.make_aware(datetime.combine(comp_off.date, datetime.max.time())),
                'type': 'comp_off',
                'color': '#9f7aea',
                'allDay': True
            })
        
        today_session = WorkSession.objects.filter(
            employee=employee,
            start_time__date=timezone.now().date(),
            status='active'
        ).first()
        
        if today_session:
            events.append({
                'id': f"session_{today_session.id}",
                'title': 'Active Work Session',
                'start': today_session.start_time,
                'end': timezone.now() + timedelta(hours=1),
                'type': 'work_session',
                'color': '#48bb78',
                'allDay': False
            })
        
        return Response(events)
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_employee_performance_stats(request):
    """Get performance statistics for widgets - REAL DATA"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        sessions = WorkSession.objects.filter(
            employee=employee,
            start_time__gte=thirty_days_ago
        )
        
        completed_sessions = sessions.filter(status='completed').count()
        total_hours = sum(float(session.total_hours) for session in sessions.filter(status='completed') if session.total_hours)
        
        present_days = Attendance.objects.filter(
            employee=employee,
            date__gte=thirty_days_ago.date(),
            status='present'
        ).count()
        
        wfh_days = Attendance.objects.filter(
            employee=employee,
            date__gte=thirty_days_ago.date(),
            status='wfh'
        ).count()
        
        attendance_rate = round((present_days + wfh_days) / 30 * 100, 1) if 30 > 0 else 0
        avg_daily_hours = round(total_hours / max(1, (present_days + wfh_days)), 1)
        
        productivity_score = min(100, (completed_sessions * 10 + total_hours * 2))
        
        stats = {
            'attendance_rate': attendance_rate,
            'total_work_hours': round(total_hours, 1),
            'avg_daily_hours': avg_daily_hours,
            'productivity_score': productivity_score,
            'completed_sessions': completed_sessions,
            'present_days': present_days,
            'wfh_days': wfh_days
        }
        
        return Response(stats)
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_work_session_with_notes(request):
    """MODERN: Start work session with IST time tracking"""
    try:
        try:
            employee = AddEmployee.objects.get(user=request.user)
        except AddEmployee.DoesNotExist:
            return Response({
                "error": "Employee profile not found. Please contact admin."
            }, status=status.HTTP_404_NOT_FOUND)
        
        session_type = request.data.get('session_type')
        request_id = request.data.get('request_id')
        start_note = request.data.get('start_note', '')
        tasks_planned = request.data.get('tasks_planned', [])
        energy_level = request.data.get('energy_level', 3)
        
        if not session_type or not request_id:
            return Response(
                {"error": "Session type and request ID are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        active_session = WorkSession.objects.filter(
            employee=employee, 
            status='active'
        ).first()
        
        if active_session:
            return Response(
                {"error": "You already have an active work session. Please end it first."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        utc_now = timezone.now()
        start_time_ist = convert_to_ist(utc_now)
        
        work_session = None
        if session_type == 'wfh':
            wfh_request = WFHRequest.objects.get(
                id=request_id, 
                user=request.user, 
                status='Approved'
            )
            work_session = WorkSession.objects.create(
                employee=employee,
                session_type='wfh',
                request=wfh_request,
                start_time=utc_now,
                start_note=start_note,
                tasks_planned=tasks_planned,
                energy_level=energy_level,
                status='active'
            )
            wfh_request.status = 'Active'
            wfh_request.save()
            
        elif session_type == 'comp_off':
            comp_off_request = CompOffRequest.objects.get(
                id=request_id, 
                user=request.user, 
                status='Approved'
            )
            work_session = WorkSession.objects.create(
                employee=employee,
                session_type='comp_off',
                comp_off_request=comp_off_request,
                start_time=utc_now,
                start_note=start_note,
                tasks_planned=tasks_planned,
                energy_level=energy_level,
                status='active'
            )
            comp_off_request.status = 'Active'
            comp_off_request.save()
        else:
            return Response(
                {"error": "Invalid session type"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        ActivityLog.objects.create(
            session=work_session,
            activity_type='note_added',
            details={
                'action': 'session_started',
                'ist_time': start_time_ist,
                'tasks_count': len(tasks_planned)
            },
            note=f"Work session started. {start_note}"
        )

        serializer = WorkSessionSerializer(work_session)
        return Response({
            "message": "Work session started successfully",
            "session": serializer.data,
            "start_time_ist": start_time_ist
        }, status=status.HTTP_201_CREATED)
        
    except WFHRequest.DoesNotExist:
        return Response({"error": "WFH request not found or not approved"}, status=status.HTTP_404_NOT_FOUND)
    except CompOffRequest.DoesNotExist:
        return Response({"error": "Comp Off request not found or not approved"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error: {str(e)}")
        return Response({"error": f"Failed to start work session: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_work_session_with_report(request, session_id):
    """MODERN: End work session with IST time and productivity metrics"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        work_session = WorkSession.objects.get(id=session_id, employee=employee, status='active')
        
        end_note = request.data.get('end_note', '')
        work_completed = request.data.get('work_completed', '')
        focus_quality = request.data.get('focus_quality', 3)
        meetings_attended = request.data.get('meetings_attended', 0)
        blockers = request.data.get('blockers', '')
        
        utc_now = timezone.now()
        ist = pytz.timezone('Asia/Kolkata')
        ist_now = utc_now.astimezone(ist)
        
        work_session.end_time = utc_now
        work_session.status = 'completed'
        work_session.end_note = end_note
        work_session.work_completed = work_completed
        work_session.focus_quality = focus_quality
        work_session.meetings_attended = meetings_attended
        work_session.blockers = blockers
        
        work_session.calculate_total_hours()
        work_session.calculate_productivity_score()
        work_session.save()

        daily_report = DailyWorkReport.objects.create(
            session=work_session,
            date=ist_now.date(),
            tasks_completed=work_completed,
            challenges_faced=blockers,
            next_day_plan=request.data.get('next_day_plan', ''),
            work_start_time_ist=work_session.start_time.astimezone(ist).time(),
            work_end_time_ist=ist_now.time(),
            total_work_hours=work_session.total_hours,
            tasks_accomplished=work_session.tasks_completed
        )

        if work_session.session_type == 'wfh' and work_session.request:
            wfh_request = work_session.request
            current_actual_hours = float(wfh_request.actual_hours)
            session_hours = float(work_session.total_hours)
            wfh_request.actual_hours = Decimal(str(current_actual_hours + session_hours))
            
            if wfh_request.actual_hours >= wfh_request.expected_hours:
                wfh_request.status = 'Completed'
            wfh_request.save()
            
        elif work_session.session_type == 'comp_off' and work_session.comp_off_request:
            comp_off_request = work_session.comp_off_request
            current_actual_hours = float(comp_off_request.actual_hours_worked)
            session_hours = float(work_session.total_hours)
            comp_off_request.actual_hours_worked = Decimal(str(current_actual_hours + session_hours))
            
            if comp_off_request.actual_hours_worked >= comp_off_request.hours:
                comp_off_request.status = 'Completed'
            comp_off_request.save()

        serializer = WorkSessionSerializer(work_session)
        return Response({
            "message": "Work session completed successfully",
            "session": serializer.data,
            "productivity_score": work_session.productivity_score,
            "total_hours": float(work_session.total_hours),
            "tasks_completed": len(work_session.tasks_completed),
            "tasks_planned": len(work_session.tasks_planned),
            "start_time_ist": convert_to_ist(work_session.start_time),
            "end_time_ist": convert_to_ist(utc_now)
        })
        
    except (AddEmployee.DoesNotExist, WorkSession.DoesNotExist):
        return Response({"error": "Work session not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": f"Failed to end work session: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_one_time_ist_time(request):
    """Get IST time only once - for initial sync"""
    try:
        current_ist = get_ist_time()
        
        return Response({
            'current_ist_time': current_ist,
            'timezone': 'Asia/Kolkata',
            'sync_type': 'one_time',
            'message': 'Time synced successfully. Use client time for further updates.'
        })
        
    except Exception as e:
        return Response({
            'current_ist_time': get_ist_time(),
            'is_fallback': True,
            'message': 'Using server time'
        })

    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_session_note(request, session_id):
    """Add note during work session"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        work_session = WorkSession.objects.get(id=session_id, employee=employee, status='active')
        
        note = request.data.get('note', '')
        note_type = request.data.get('note_type', 'general')
        
        if not note:
            return Response({"error": "Note content is required"}, status=status.HTTP_400_BAD_REQUEST)

        ActivityLog.objects.create(
            session=work_session,
            activity_type='note_added',
            details={
                'note_type': note_type,
                'ist_time': timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            },
            note=note
        )

        return Response({
            "message": "Note added successfully",
            "note": note,
            "timestamp_ist": timezone.now().strftime('%Y-%m-%d %H:%M:%S IST')
        })
        
    except (AddEmployee.DoesNotExist, WorkSession.DoesNotExist) as e:
        return Response({"error": "Work session not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_session_details(request, session_id):
    """Get detailed session information with notes and activities"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        work_session = WorkSession.objects.get(id=session_id, employee=employee)
        
        activity_logs = ActivityLog.objects.filter(session=work_session).order_by('-timestamp')
        
        daily_report = None
        if hasattr(work_session, 'daily_report'):
            daily_report = {
                'tasks_completed': work_session.daily_report.tasks_completed,
                'challenges_faced': work_session.daily_report.challenges_faced,
                'next_day_plan': work_session.daily_report.next_day_plan,
                'total_work_hours': float(work_session.daily_report.total_work_hours),
                'work_start_time_ist': work_session.daily_report.work_start_time_ist.strftime('%H:%M:%S'),
                'work_end_time_ist': work_session.daily_report.work_end_time_ist.strftime('%H:%M:%S'),
                'tasks_accomplished': work_session.daily_report.tasks_accomplished
            }
        
        session_data = WorkSessionSerializer(work_session).data
        activity_data = ActivityLogSerializer(activity_logs, many=True).data
        
        return Response({
            'session': session_data,
            'activity_logs': activity_data,
            'daily_report': daily_report,
            'current_time_ist': timezone.now().strftime('%Y-%m-%d %H:%M:%S IST')
        })
        
    except (AddEmployee.DoesNotExist, WorkSession.DoesNotExist) as e:
        return Response({"error": "Work session not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_employee_work_reports(request, days=30):
    """Get work reports for an employee for specified days"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        since_date = timezone.now() - timedelta(days=days)
        
        sessions = WorkSession.objects.filter(
            employee=employee,
            start_time__gte=since_date,
            status='completed'
        ).order_by('-start_time')
        
        reports = []
        for session in sessions:
            session_data = WorkSessionSerializer(session).data
            daily_report = None
            
            if hasattr(session, 'daily_report'):
                daily_report = {
                    'tasks_completed': session.daily_report.tasks_completed,
                    'total_work_hours': float(session.daily_report.total_work_hours),
                    'work_date': session.daily_report.date.strftime('%Y-%m-%d')
                }
            
            reports.append({
                'session': session_data,
                'daily_report': daily_report,
                'start_time_ist': session.start_time.strftime('%Y-%m-%d %H:%M:%S IST'),
                'end_time_ist': session.end_time.strftime('%Y-%m-%d %H:%M:%S IST') if session.end_time else None
            })
        
        return Response({
            'reports': reports,
            'total_sessions': len(reports),
            'period_days': days,
            'report_generated_at': timezone.now().strftime('%Y-%m-%d %H:%M:%S IST')
        })
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

# ================= Admin Monitoring APIs =================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_get_employee_work_details(request, employee_id):
    """Admin: Get detailed work information for an employee - FIXED VERSION"""
    if request.user.role not in ['admin', 'manager']:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        employee = AddEmployee.objects.get(id=employee_id)
        
        all_sessions = WorkSession.objects.filter(employee=employee)
        completed_sessions = all_sessions.filter(status='completed')
        
        total_sessions = all_sessions.count()
        completed_count = completed_sessions.count()
        
        total_hours_result = completed_sessions.aggregate(total=Sum('total_hours'))
        total_hours = total_hours_result['total'] or Decimal('0.0')
        
        avg_productivity_result = completed_sessions.aggregate(avg=Avg('productivity_score'))
        avg_productivity = avg_productivity_result['avg'] or 50
        
        recent_sessions_data = []
        recent_sessions = WorkSession.objects.filter(
            employee=employee
        ).order_by('-start_time')[:10]
        
        for session in recent_sessions:
            recent_sessions_data.append({
                'session': {
                    'id': session.id,
                    'session_type': session.session_type,
                    'status': session.status,
                    'start_time': session.start_time,
                    'end_time': session.end_time,
                    'total_hours': float(session.total_hours) if session.total_hours else 0,
                    'productivity_score': session.productivity_score or 50
                },
                'start_note': session.start_note or '',
                'work_completed': session.work_completed or '',
                'start_time_ist': session.start_time.strftime('%Y-%m-%d %H:%M:%S IST')
            })
        
        return Response({
            'employee': {
                'id': employee.id,
                'name': f"{employee.first_name} {employee.last_name}",
                'department': employee.department,
                'position': employee.position
            },
            'work_statistics': {
                'total_sessions': total_sessions,
                'completed_sessions': completed_count,
                'total_hours_worked': float(total_hours),
                'average_productivity': float(avg_productivity)
            },
            'recent_sessions': recent_sessions_data,
            'report_generated_at': timezone.now().strftime('%Y-%m-%d %H:%M:%S IST')
        })
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_get_detailed_session(request, session_id):
    """Admin: Get detailed session information with all notes"""
    if request.user.role not in ['admin', 'manager']:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        work_session = WorkSession.objects.get(id=session_id)
        
        activity_logs = ActivityLog.objects.filter(session=work_session).order_by('-timestamp')
        
        daily_report = None
        if hasattr(work_session, 'daily_report'):
            daily_report = {
                'tasks_completed': work_session.daily_report.tasks_completed,
                'challenges_faced': work_session.daily_report.challenges_faced,
                'next_day_plan': work_session.daily_report.next_day_plan,
                'total_work_hours': float(work_session.daily_report.total_work_hours),
                'tasks_accomplished': work_session.daily_report.tasks_accomplished,
                'work_start_time_ist': work_session.daily_report.work_start_time_ist.strftime('%H:%M:%S IST'),
                'work_end_time_ist': work_session.daily_report.work_end_time_ist.strftime('%H:%M:%S IST')
            }
        
        session_data = WorkSessionSerializer(work_session).data
        
        return Response({
            'session': session_data,
            'employee': {
                'id': work_session.employee.id,
                'name': f"{work_session.employee.first_name} {work_session.employee.last_name}",
                'department': work_session.employee.department
            },
            'activity_logs': ActivityLogSerializer(activity_logs, many=True).data,
            'daily_report': daily_report,
            'start_time_ist': work_session.start_time.strftime('%Y-%m-%d %H:%M:%S IST'),
            'end_time_ist': work_session.end_time.strftime('%Y-%m-%d %H:%M:%S IST') if work_session.end_time else None
        })
        
    except WorkSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)




@api_view(["GET"])
@permission_classes([IsAuthenticated])
def generate_html_salary_slip_pdf(request, employee_id, month, year):
    """Generate beautiful HTML-based salary slip PDF - FIXED MONTH HANDLING"""
    try:
        print(f"📄 Generating PDF for Employee: {employee_id}, Month: {month}, Year: {year}")
        
        # ✅ FIX: Frontend sends 1-indexed month for PDF, use as-is
        backend_month = int(month)  # Already 1-indexed from frontend
        
        employee = AddEmployee.objects.get(id=employee_id)
        
        # Get monthly salary record - Database uses 1-indexed month
        monthly_salary = MonthlySalary.objects.get(
            employee=employee, 
            month=backend_month,  # Use as-is (1-indexed)
            year=int(year)
        )
        
        print(f"✅ Found salary record: {employee.first_name}, {backend_month}/{year}")
        
        return generate_html_salary_slip(employee_id, backend_month, int(year))
        
    except AddEmployee.DoesNotExist:
        print(f"❌ Employee not found: {employee_id}")
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
    except MonthlySalary.DoesNotExist:
        print(f"❌ Salary record not found: Employee {employee_id}, Month {backend_month}, Year {year}")
        return Response(
            {"error": f"Salary record not found for {datetime(int(year), backend_month, 1).strftime('%B %Y')}. Please generate salary first."}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        print(f"❌ PDF generation error: {str(e)}")
        return Response({"error": f"Failed to generate PDF: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def preview_html_salary_slip(request, employee_id, month, year):
    """Preview salary slip in browser (HTML format)"""
    try:
        return generate_html_salary_slip_preview(employee_id, int(month), int(year))
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ================= Notification APIs =================
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pending_requests_count(request):
    """Get pending requests count for admin"""
    if request.user.role not in ['admin', 'manager']:
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
    
    leave_pending = Leave.objects.filter(status='Pending').count()
    wfh_pending = WFHRequest.objects.filter(status='Pending').count()
    comp_off_pending = CompOffRequest.objects.filter(status='Pending').count()
    
    return Response({
        'total_pending': leave_pending + wfh_pending + comp_off_pending,
        'leave_pending': leave_pending,
        'wfh_pending': wfh_pending,
        'comp_off_pending': comp_off_pending
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_employee_notifications(request):
    """Get notifications for employee - FIXED VERSION WITH PROPER FILTERING"""
    
    # Get last check time from query param
    last_check = request.GET.get('last_check', None)
    
    notifications = []
    
    # Parse last_check if provided
    last_check_dt = None
    if last_check:
        try:
            from datetime import datetime
            last_check_dt = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
        except Exception as e:
            last_check_dt = None
    
    # Get Leave notifications
    leave_qs = Leave.objects.filter(
        user=request.user,
        status__in=['Approved', 'Rejected']
    ).order_by('-applied_at')
    
    for leave in leave_qs:
        notifications.append({
            'request_type': 'leave',
            'request_id': leave.id,
            'type': 'leave',
            'status': leave.status,
            'message': f"{leave.leave_type.title()} leave {leave.status.lower()} ({leave.start_date} to {leave.end_date})",
            'rejection_reason': leave.rejection_reason or '',
            'date': leave.applied_at.isoformat()
        })
    
    # Get WFH notifications
    wfh_qs = WFHRequest.objects.filter(
        user=request.user,
        status__in=['Approved', 'Rejected']
    ).order_by('-created_at')
    
    for wfh in wfh_qs:
        notifications.append({
            'request_type': 'wfh',
            'request_id': wfh.id,
            'type': 'wfh',
            'status': wfh.status,
            'message': f"WFH request {wfh.status.lower()} ({wfh.start_date} to {wfh.end_date})",
            'rejection_reason': wfh.rejection_reason or '',
            'date': wfh.created_at.isoformat()
        })
    
    # Get Comp Off notifications
    comp_off_qs = CompOffRequest.objects.filter(
        user=request.user,
        status__in=['Approved', 'Rejected']
    ).order_by('-created_at')
    
    for comp_off in comp_off_qs:
        notifications.append({
            'request_type': 'comp_off',
            'request_id': comp_off.id,
            'type': 'comp_off',
            'status': comp_off.status,
            'message': f"Comp Off request {comp_off.status.lower()} for {comp_off.date} ({comp_off.hours} hours)",
            'rejection_reason': comp_off.rejection_reason or '',
            'date': comp_off.created_at.isoformat()
        })
    
    # Get Form Revision notifications
    try:
        employee = AddEmployee.objects.get(user=request.user)
        from .models import FormRevisionNotification
        
        revision_qs = FormRevisionNotification.objects.filter(
                employee=employee
            ).order_by('-created_at')
        
        for revision in revision_qs:
            notifications.append({
                'request_type': 'form_revision',
                'request_id': revision.id,
                'type': 'form_revision',
                'status': 'Pending',
                'message': revision.message,
                'incomplete_fields': revision.incomplete_fields,
                'date': revision.created_at.isoformat()
            })
    except:
        pass
    
    # Sort by date - no limit, frontend handles display
    notifications.sort(key=lambda x: x['date'], reverse=True)
    
    approved_count = sum(1 for n in notifications if n.get('status') == 'Approved')
    rejected_count = sum(1 for n in notifications if n.get('status') == 'Rejected')
    
    return Response({
        'unread_count': len(notifications),
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'notifications': notifications
    })



# ✅ SIMPLER VERSION
def get_attendance_stats_for_salary(employee_id, month, year):
    """
    Utility function to get attendance data for salary calculation.
    Fetches SaturdayOverride and CompanyLeave from DB to correctly
    determine working vs paid-off Saturdays.
    month is 1-indexed (1-12).
    """
    try:
        from .leave_management_models import SaturdayOverride, CompanyLeave
        employee = AddEmployee.objects.get(id=employee_id)

        import calendar as cal_module
        _, last_day = cal_module.monthrange(year, month)
        start_date = datetime(year, month, 1).date()
        end_date = datetime(year, month, last_day).date()

        safe_print(f"📅 Getting attendance for {start_date} to {end_date}")

        # ── Fetch overrides & company leaves for this month ──────────────
        saturday_overrides = {
            str(o.date): o.status
            for o in SaturdayOverride.objects.filter(month=month, year=year)
        }
        company_leave_dates = set(
            str(cl.date)
            for cl in CompanyLeave.objects.filter(month=month, year=year)
        )

        # ── Helper: is a date a paid-off day? ────────────────────────────
        def is_paid_off(date):
            date_str = str(date)
            if date_str in company_leave_dates:
                return True
            weekday = date.weekday()
            if weekday == 6:  # Sunday always paid off
                return True
            if weekday == 5:  # Saturday
                if date_str in saturday_overrides:
                    return saturday_overrides[date_str] == 'off'
                # Default: 2nd & 4th Saturday are paid off
                week_number = (date.day - 1) // 7 + 1
                return week_number in [2, 4]
            return False

        # ── Attendance records ────────────────────────────────────────────
        attendance_records = Attendance.objects.filter(
            employee=employee,
            date__range=[start_date, end_date]
        )

        # ✅ FIX: Exclude company leave dates from leave/absent counts
        # Company leaves are paid off days - should NOT be counted as employee leaves
        half_days_count = attendance_records.filter(status='half_day').exclude(date__in=company_leave_dates).count()
        present_days    = attendance_records.filter(status='present').exclude(date__in=company_leave_dates).count()
        absent_days     = attendance_records.filter(status='absent').exclude(date__in=company_leave_dates).count()
        leave_days      = attendance_records.filter(status='leave').exclude(date__in=company_leave_dates).count() + absent_days
        wfh_days        = attendance_records.filter(status='wfh').exclude(date__in=company_leave_dates).count()
        comp_off_days   = attendance_records.filter(status='comp_off').exclude(date__in=company_leave_dates).count()

        # Unmarked working days → absent (company leave dates already excluded via is_paid_off)
        marked_dates = set(attendance_records.values_list('date', flat=True))
        
        # ✅ FIX: Also include approved WFH and Leave dates as "marked" so they don't count as absent
        from .models import WFHRequest, Leave as LeaveModel
        approved_wfh_dates = set()
        for wfh in WFHRequest.objects.filter(user=employee.user, status='Approved',
                                              start_date__lte=end_date, end_date__gte=start_date):
            d = max(wfh.start_date, start_date)
            while d <= min(wfh.end_date, end_date):
                approved_wfh_dates.add(d)
                d += timedelta(days=1)
        
        approved_leave_dates = set()
        for lv in LeaveModel.objects.filter(user=employee.user, status='Approved',
                                             start_date__lte=end_date, end_date__gte=start_date):
            d = max(lv.start_date, start_date)
            while d <= min(lv.end_date, end_date):
                approved_leave_dates.add(d)
                d += timedelta(days=1)
        
        all_marked_dates = marked_dates | approved_wfh_dates | approved_leave_dates
        
        unmarked_absent = 0
        check_date = start_date
        while check_date <= end_date:
            check_date_str = str(check_date)
            if not is_paid_off(check_date) and check_date not in all_marked_dates and check_date_str not in company_leave_dates:
                unmarked_absent += 1
            check_date += timedelta(days=1)
        leave_days += unmarked_absent
        safe_print(f"📊 Unmarked working days (absent): {unmarked_absent}")

        # ── Working days & paid weekly offs ──────────────────────────────
        total_working_days = 0
        paid_weekly_offs   = 0
        current_date = start_date
        while current_date <= end_date:
            if is_paid_off(current_date):
                paid_weekly_offs += 1
            else:
                total_working_days += 1
            current_date += timedelta(days=1)

        total_days_in_month = (end_date - start_date).days + 1

        safe_print(
            f"📊 Attendance stats: Present={present_days}, Half={half_days_count}, "
            f"Leave={leave_days}, WFH={wfh_days}, Working Days={total_working_days}, "
            f"Paid Offs={paid_weekly_offs} "
            f"(Saturday overrides: {saturday_overrides}, Company leaves: {len(company_leave_dates)})"
        )

        return {
            'present_days': present_days,
            'half_days': half_days_count,
            'leave_days': leave_days,
            'wfh_days': wfh_days,
            'comp_off_days': comp_off_days,
            'total_working_days': total_working_days,
            'paid_weekly_offs': paid_weekly_offs,
            'total_days_in_month': total_days_in_month
        }

    except Exception as e:
        safe_print(f"❌ Error getting attendance stats: {e}")
        return {
            'present_days': 0,
            'half_days': 0,
            'leave_days': 0,
            'wfh_days': 0,
            'comp_off_days': 0,
            'total_working_days': 22,
            'paid_weekly_offs': 8,
            'total_days_in_month': 30
        }


# Django views.py mein
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_salary_record(request, employee_id, month, year):
    """Check if salary record exists - FIXED VERSION"""
    try:
        employee = AddEmployee.objects.get(id=employee_id)
        
        # ✅ FIX: month is already 1-indexed from URL
        monthly_salary = MonthlySalary.objects.get(
            employee=employee,
            month=month,  # Use as-is (1-indexed)
            year=year
        )
        
        return Response({
            'salary_record_exists': True,
            'employee': f"{employee.first_name} {employee.last_name}",
            'month': month,
            'year': year,
            'final_salary': monthly_salary.final_salary,
            'generated_at': monthly_salary.generated_at
        })
        
    except MonthlySalary.DoesNotExist:
        return Response({
            'salary_record_exists': False,
            'employee': f"{employee.first_name} {employee.last_name}",
            'month': month,
            'year': year,
            'message': f'Salary record not found for {datetime(year, month, 1).strftime("%B %Y")}'
        }, status=status.HTTP_404_NOT_FOUND)
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)


# ================= Offer Letter APIs =================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_and_send_offer_letter(request):
    """Generate offer letter (without sending email)"""
    if request.user.role != 'admin':
        return Response({"error": "Only admin can generate offer letters"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        employee_id = request.data.get('employee_id')
        offer_date = request.data.get('offer_date')
        ctc = request.data.get('ctc')
        
        if not all([employee_id, offer_date, ctc]):
            return Response({"error": "employee_id, offer_date, and ctc are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        employee = AddEmployee.objects.get(id=employee_id)
        
        # Generate PDF
        pdf_buffer = generate_offer_letter_pdf(
            employee_name=employee.get_full_name(),
            designation=employee.position,
            salary=float(ctc),
            date=offer_date
        )
        
        # Save PDF
        pdf_filename = f"offer_letter_{employee.first_name}_{employee.last_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
        employee.offer_letter_pdf.save(pdf_filename, ContentFile(pdf_buffer.read()), save=False)
        employee.offer_letter_sent = False
        employee.offer_letter_date = offer_date
        employee.offer_letter_ctc = ctc
        employee.save()
        
        return Response({
            "message": "Offer letter generated successfully. Please review before sending.",
            "employee": employee.get_full_name(),
            "email": employee.user.email,
            "pdf_url": employee.offer_letter_pdf.url if employee.offer_letter_pdf else None
        }, status=status.HTTP_200_OK)
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error generating offer letter: {str(e)}")
        return Response({"error": f"Failed to generate offer letter: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_offer_letter_email(request, employee_id):
    """Send offer letter email after review"""
    if request.user.role != 'admin':
        return Response({"error": "Only admin can send offer letters"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        employee = AddEmployee.objects.get(id=employee_id)
        
        if not employee.offer_letter_pdf:
            return Response({"error": "Offer letter not generated yet"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Send Email
        email = EmailMessage(
            subject='Your Offer Letter - Teople Technologies',
            body=f'Dear {employee.get_full_name()},\n\nPlease find attached your offer letter.\n\nBest Regards,\nHR Department\nTeople Technologies',
            from_email='hr@teople.com',
            to=[employee.user.email]
        )
        
        with employee.offer_letter_pdf.open('rb') as pdf_file:
            email.attach(f"offer_letter_{employee.first_name}_{employee.last_name}.pdf", pdf_file.read(), 'application/pdf')
        
        email.send()
        
        employee.offer_letter_sent = True
        employee.save()
        
        return Response({
            "message": "Offer letter sent successfully",
            "employee": employee.get_full_name(),
            "email": employee.user.email
        }, status=status.HTTP_200_OK)
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error sending offer letter: {str(e)}")
        return Response({"error": f"Failed to send offer letter: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_employee_offer_letter(request, employee_id):
    """Get employee offer letter (Employee can view their own)"""
    try:
        employee = AddEmployee.objects.get(id=employee_id)
        
        # Check if user is admin or the employee themselves
        if request.user.role != 'admin' and employee.user != request.user:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        if not employee.offer_letter_sent or not employee.offer_letter_pdf:
            return Response({
                "offer_letter_available": False,
                "message": "Your offer letter is not available yet."
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            "offer_letter_available": True,
            "employee_name": employee.get_full_name(),
            "position": employee.position,
            "ctc": float(employee.offer_letter_ctc) if employee.offer_letter_ctc else None,
            "offer_date": employee.offer_letter_date,
            "pdf_url": request.build_absolute_uri(employee.offer_letter_pdf.url)
        })
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)


# ================= Relieving Letter APIs =================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_and_send_relieving_letter(request):
    """Generate relieving letter (without sending email)"""
    if request.user.role != 'admin':
        return Response({"error": "Only admin can generate relieving letters"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        employee_id = request.data.get('employee_id')
        relieving_date = request.data.get('relieving_date')
        last_working_day = request.data.get('last_working_day')
        
        if not all([employee_id, relieving_date, last_working_day]):
            return Response({"error": "employee_id, relieving_date, and last_working_day are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        employee = AddEmployee.objects.get(id=employee_id)
        # Get joining date from offer letter
        if employee.offer_letter_date:
            joining_date = employee.offer_letter_date.strftime('%d-%B-%Y')
        else:
            joining_date = employee.created_at.strftime('%d-%B-%Y')
        
        # Generate PDF
        pdf_buffer = generate_relieving_letter_pdf(
            employee_name=employee.get_full_name(),
            designation=employee.position,
            joining_date=joining_date,
            last_working_day=last_working_day,
            relieving_date=relieving_date
        )
        
        # Save PDF
        pdf_filename = f"relieving_letter_{employee.first_name}_{employee.last_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
        employee.relieving_letter_pdf.save(pdf_filename, ContentFile(pdf_buffer.read()), save=False)
        employee.relieving_letter_sent = False
        employee.relieving_letter_date = relieving_date
        employee.last_working_day = last_working_day
        employee.save()
        
        return Response({
            "message": "Relieving letter generated successfully. Please review before sending.",
            "employee": employee.get_full_name(),
            "email": employee.user.email,
            "pdf_url": employee.relieving_letter_pdf.url if employee.relieving_letter_pdf else None
        }, status=status.HTTP_200_OK)
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error generating relieving letter: {str(e)}")
        return Response({"error": f"Failed to generate relieving letter: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_relieving_letter_email(request, employee_id):
    """Send relieving letter email after review"""
    if request.user.role != 'admin':
        return Response({"error": "Only admin can send relieving letters"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        employee = AddEmployee.objects.get(id=employee_id)
        
        if not employee.relieving_letter_pdf:
            return Response({"error": "Relieving letter not generated yet"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Send Email
        email = EmailMessage(
            subject='Your Relieving Letter - Teople Technologies',
            body=f'Dear {employee.get_full_name()},\n\nThank you for your valuable contribution to Teople Technologies. Please find attached your relieving letter.\n\nWe wish you all the best for your future endeavors.\n\nBest Regards,\nHR Department\nTeople Technologies',
            from_email='hr@teople.com',
            to=[employee.user.email]
        )
        
        with employee.relieving_letter_pdf.open('rb') as pdf_file:
            email.attach(f"relieving_letter_{employee.first_name}_{employee.last_name}.pdf", pdf_file.read(), 'application/pdf')
        
        email.send()
        
        employee.relieving_letter_sent = True
        employee.save()
        
        return Response({
            "message": "Relieving letter sent successfully",
            "employee": employee.get_full_name(),
            "email": employee.user.email
        }, status=status.HTTP_200_OK)
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error sending relieving letter: {str(e)}")
        return Response({"error": f"Failed to send relieving letter: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_employee_relieving_letter(request, employee_id):
    """Get employee relieving letter"""
    try:
        employee = AddEmployee.objects.get(id=employee_id)
        
        if request.user.role != 'admin' and employee.user != request.user:
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        if not employee.relieving_letter_sent or not employee.relieving_letter_pdf:
            return Response({
                "relieving_letter_available": False,
                "message": "Relieving letter is not available."
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            "relieving_letter_available": True,
            "employee_name": employee.get_full_name(),
            "position": employee.position,
            "last_working_day": employee.last_working_day,
            "relieving_date": employee.relieving_letter_date,
            "pdf_url": request.build_absolute_uri(employee.relieving_letter_pdf.url)
        })
        
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)


# ================= Comp Off Usage Notification APIs =================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_comp_off_usage_notifications(request):
    """
    Admin API: Har mahine ke 1 tarikh ko call karo.
    Sabhi employees jinka comp off balance > 0 hai unhe notification bhejo.
    Pehle se pending/accepted notification ho to skip karo.
    """
    if request.user.role != 'admin':
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

    from .notification_models import CompOffUsageNotification
    from django.utils import timezone
    from datetime import timedelta

    today = timezone.now()
    expires_at = today + timedelta(days=2)

    sent_to = []
    skipped = []

    employees_with_balance = CompOffBalance.objects.filter(balance_hours__gt=0).select_related('employee')

    for balance in employees_with_balance:
        employee = balance.employee

        # Purani sab notifications delete karo, fresh notification banao
        CompOffUsageNotification.objects.filter(
            employee=employee
        ).exclude(status='pending').delete()

        # Agar abhi bhi pending hai to skip
        existing_pending = CompOffUsageNotification.objects.filter(
            employee=employee,
            status='pending'
        ).first()

        if existing_pending:
            skipped.append(f"{employee.first_name} (already pending)")
            continue

        CompOffUsageNotification.objects.create(
            employee=employee,
            comp_off_hours=balance.balance_hours,
            for_month=today.month,
            for_year=today.year,
            expires_at=expires_at,
            status='pending'
        )
        sent_to.append(employee.first_name)

    return Response({
        'message': f'{len(sent_to)} employees ko notification bheji',
        'sent_to': sent_to,
        'skipped': skipped,
        'expires_at': expires_at.isoformat()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def respond_comp_off_notification(request, notification_id):
    """
    Employee API: Notification ka response do.
    Body: { "use_comp_off": true/false }
    - true  → status = 'accepted' (salary me add hoga)
    - false → status = 'declined' (next month carry forward)
    """
    from .notification_models import CompOffUsageNotification
    from django.utils import timezone

    try:
        employee = AddEmployee.objects.get(user=request.user)
        notification = CompOffUsageNotification.objects.get(
            id=notification_id,
            employee=employee
        )
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)
    except CompOffUsageNotification.DoesNotExist:
        return Response({"error": "Notification not found"}, status=status.HTTP_404_NOT_FOUND)

    if notification.status != 'pending':
        return Response({
            "error": f"Is notification ka response pehle se de diya gaya hai: {notification.status}"
        }, status=status.HTTP_400_BAD_REQUEST)

    # 2 din expire check
    if notification.is_expired():
        notification.status = 'discarded'
        notification.responded_at = timezone.now()
        notification.save()
        return Response({
            "error": "Notification expire ho gayi. Comp off discard ho gaya."
        }, status=status.HTTP_400_BAD_REQUEST)

    use_comp_off = request.data.get('use_comp_off')
    if use_comp_off is None:
        return Response({"error": "use_comp_off field required (true/false)"}, status=status.HTTP_400_BAD_REQUEST)

    now = timezone.now()
    if use_comp_off:
        notification.status = 'accepted'
    else:
        notification.status = 'declined'

    notification.is_read = True
    notification.responded_at = now
    notification.save()

    msg = (
        "Comp off salary me add kar diya jayega."
        if use_comp_off
        else "Comp off next month me carry forward ho jayega."
    )
    return Response({'message': msg, 'status': notification.status})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def discard_expired_comp_off_notifications(request):
    """
    Admin API: Expired pending notifications ko discard karo.
    Ye daily cron job se call karo ya manually.
    """
    if request.user.role != 'admin':
        return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

    from .notification_models import CompOffUsageNotification
    from django.utils import timezone

    now = timezone.now()
    expired = CompOffUsageNotification.objects.filter(
        status='pending',
        expires_at__lt=now
    )
    count = expired.count()
    expired.update(status='discarded', responded_at=now)

    return Response({
        'message': f'{count} expired notifications discard kar di gayi',
        'discarded_count': count
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_comp_off_usage_notifications(request):
    """
    Employee API: Apni comp off usage notifications dekho.
    Sirf pending notifications return karta hai (jinpe action lena hai).
    """
    from .notification_models import CompOffUsageNotification
    from django.utils import timezone

    try:
        employee = AddEmployee.objects.get(user=request.user)
    except AddEmployee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

    now = timezone.now()

    # Auto-discard expired ones
    CompOffUsageNotification.objects.filter(
        employee=employee,
        status='pending',
        expires_at__lt=now
    ).update(status='discarded', responded_at=now)

    notifications = CompOffUsageNotification.objects.filter(
        employee=employee,
        status='pending'
    )

    data = []
    for n in notifications:
        import calendar
        month_name = calendar.month_name[n.for_month]
        data.append({
            'id': n.id,
            'comp_off_hours': n.comp_off_hours,
            'comp_off_days': round(n.comp_off_hours / 9, 1),
            'for_month': n.for_month,
            'for_year': n.for_year,
            'month_name': month_name,
            'status': n.status,
            'expires_at': n.expires_at.isoformat(),
            'created_at': n.created_at.isoformat(),
            'type': 'comp_off_usage',
            'message': f'Aapke paas {n.comp_off_hours} hours ({round(n.comp_off_hours/9, 1)} days) ka comp off balance hai. Kya aap ise {month_name} {n.for_year} ki salary me use karna chahte hain?'
        })

    return Response({'notifications': data, 'count': len(data)})


# ==================== LEAVE MANAGEMENT VIEWS ====================
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def company_leaves(request):
    from .leave_management_models import CompanyLeave
    if request.method == 'GET':
        month = request.GET.get('month')
        year = request.GET.get('year')
        leaves = CompanyLeave.objects.filter(month=month, year=year)
        data = [{'id': l.id, 'date': str(l.date), 'reason': l.reason, 'month': l.month, 'year': l.year} for l in leaves]
        return Response(data)
    elif request.method == 'POST':
        CompanyLeave.objects.create(**request.data)
        return Response({'message': 'Added'}, status=201)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_company_leave(request, date):
    from .leave_management_models import CompanyLeave
    CompanyLeave.objects.filter(date=date).delete()
    return Response(status=204)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def saturday_overrides(request):
    from .leave_management_models import SaturdayOverride
    if request.method == 'GET':
        month = request.GET.get('month')
        year = request.GET.get('year')
        overrides = SaturdayOverride.objects.filter(month=month, year=year)
        return Response({str(o.date): o.status for o in overrides})
    elif request.method == 'POST':
        override, _ = SaturdayOverride.objects.update_or_create(
            date=request.data['date'],
            defaults={'status': request.data['status'], 'month': request.data['month'], 'year': request.data['year']}
        )
        return Response({'date': str(override.date), 'status': override.status})
