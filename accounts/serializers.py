from rest_framework import serializers
from .models import (
    MyUser, AddEmployee, Leave, WFHRequest, Salary, MonthlySalary, 
    Attendance, CompOffRequest, CompOffBalance, WorkSession, ActivityLog, DailyWorkReport
)
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
import pytz

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = MyUser
        fields = ["id", "username", "email", "role"]

class EmployeeSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    offer_letter_pdf_url = serializers.SerializerMethodField()
    relieving_letter_pdf_url = serializers.SerializerMethodField()
    joining_date_display = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()  # ✅ NEW FIELD

    class Meta:
        model = AddEmployee
        fields = [
            "id", "user_id", "first_name", "last_name", "email",
            "phone", "gender", "department", "position", "address", "joining_date", "joining_date_display", "created_at",
            "updated_at", "role", "profile_picture",  # ✅ ADDED HERE
            "offer_letter_sent", "offer_letter_date",
            "offer_letter_ctc", "offer_letter_pdf_url",
            "relieving_letter_sent", "relieving_letter_date", "last_working_day", "relieving_letter_pdf_url"
        ]

    def get_role(self, obj):
        return obj.user.role

    def get_email(self, obj):
        return obj.user.email
    
    def get_profile_picture(self, obj):
        if obj.profile_picture:
            return obj.profile_picture
        return None
    
    def get_offer_letter_pdf_url(self, obj):
        if obj.offer_letter_pdf:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.offer_letter_pdf.url)
            return obj.offer_letter_pdf.url
        return None

    def get_relieving_letter_pdf_url(self, obj):
        if obj.relieving_letter_pdf:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.relieving_letter_pdf.url)
            return obj.relieving_letter_pdf.url
        return None
    
    def get_joining_date_display(self, obj):
        return obj.get_joining_date_display()

class AddEmployeeSerializer(serializers.ModelSerializer):
    joining_date = serializers.DateField(required=False, allow_null=True)
    
    class Meta:
        model = AddEmployee
        fields = [
            "id",
            "first_name",
            "last_name",
            "phone",
            "gender",
            "department",
            "position",
            "address",
            "joining_date",
        ]
    
    def validate_phone(self, value):
        """Validate phone number"""
        import re
        
        if not value or not value.strip():
            raise serializers.ValidationError("Phone number is required")
        
        value = value.strip()
        
        # Check if it's a valid 10-digit Indian mobile number
        if not re.match(r'^[6-9]\d{9}$', value):
            raise serializers.ValidationError("Please enter a valid 10-digit mobile number starting with 6, 7, 8, or 9")
        
        # Check for duplicate phone number (excluding current instance)
        existing_employee = AddEmployee.objects.filter(phone=value)
        if self.instance:
            existing_employee = existing_employee.exclude(pk=self.instance.pk)
        
        if existing_employee.exists():
            raise serializers.ValidationError("This phone number is already registered with another employee")
        
        return value

class UserProfileSerializer(serializers.ModelSerializer):
    employee_profile = AddEmployeeSerializer(required=False)

    class Meta:
        model = MyUser
        fields = ["id", "email", "username", "role", "employee_profile"]
        read_only_fields = ["email", "role"]

    def update(self, instance, validated_data):
        employee_data = validated_data.pop("employee_profile", None)
        instance.username = validated_data.get("username", instance.username)
        instance.save()

        if employee_data:
            employee_data.pop("email", None)
            profile, created = AddEmployee.objects.get_or_create(user=instance)
            serializer = AddEmployeeSerializer(profile, data=employee_data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()

        return instance

class LeaveSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    employee_id = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    leave_dates = serializers.SerializerMethodField()

    class Meta:
        model = Leave
        fields = [
            'id', 'leave_type', 'start_date', 'end_date',
            'reason', 'status', 'rejection_reason', 'applied_at', 'full_name', 'employee_id', 'user_id', 'leave_dates'
        ]

    def get_full_name(self, obj):
        try:
            profile = AddEmployee.objects.get(user=obj.user)
            return f"{profile.first_name} {profile.last_name}"
        except AddEmployee.DoesNotExist:
            return obj.user.username

    def get_employee_id(self, obj):
        try:
            return AddEmployee.objects.get(user=obj.user).id
        except AddEmployee.DoesNotExist:
            return None

    def get_leave_dates(self, obj):
        dates = []
        current_date = obj.start_date
        while current_date <= obj.end_date:
            dates.append(current_date.strftime("%Y-%m-%d"))
            current_date += timedelta(days=1)
        return dates

class WFHRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_id = serializers.SerializerMethodField()
    
    class Meta:
        model = WFHRequest
        fields = ['id', 'start_date', 'end_date', 'reason', 'type', 'status', 'rejection_reason', 'expected_hours', 'actual_hours', 'employee_name', 'employee_id']
    
    def get_employee_name(self, obj):
        if hasattr(obj.user, 'employee_profile'):
            return f"{obj.user.employee_profile.first_name} {obj.user.employee_profile.last_name}"
        return obj.user.email

    def get_employee_id(self, obj):
        try:
            return obj.user.employee_profile.id
        except Exception:
            return None

class CompOffRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_id = serializers.SerializerMethodField()
    work_sessions = serializers.SerializerMethodField()
    
    class Meta:
        model = CompOffRequest
        fields = ['id', 'date', 'hours', 'reason', 'status', 'rejection_reason', 'employee_name', 'employee_id',
                 'actual_hours_worked', 'work_sessions']
    
    def get_employee_name(self, obj):
        if hasattr(obj.user, 'employee_profile'):
            profile = obj.user.employee_profile
            return f"{profile.first_name} {profile.last_name}"
        return obj.user.email

    def get_employee_id(self, obj):
        try:
            return obj.user.employee_profile.id
        except Exception:
            return None

    def get_work_sessions(self, obj):
        sessions = WorkSession.objects.filter(comp_off_request=obj)
        return WorkSessionSerializer(sessions, many=True).data

class CompOffBalanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    balance_days = serializers.SerializerMethodField()
    
    class Meta:
        model = CompOffBalance
        fields = [
            'id', 'employee', 'employee_name', 'balance_hours', 
            'earned_hours', 'used_hours', 'balance_days', 'updated_at'
        ]
    
    def get_balance_days(self, obj):
        """Convert hours to days (1 day = 9 hours)"""
        return obj.balance_hours // 9

class ActivityLogSerializer(serializers.ModelSerializer):
    timestamp_ist = serializers.SerializerMethodField()
    
    class Meta:
        model = ActivityLog
        fields = ['id', 'activity_type', 'timestamp_ist', 'details', 'note']
    
    def get_timestamp_ist(self, obj):
        if obj.timestamp:
            return obj.timestamp.strftime('%Y-%m-%d %H:%M:%S IST')
        return None

class SalarySerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    emp_code = serializers.SerializerMethodField()
    monthly_salary = serializers.SerializerMethodField()
    in_hand_salary = serializers.SerializerMethodField()
    monthly_in_hand = serializers.SerializerMethodField()
    monthly_variable = serializers.SerializerMethodField()
    variable_pay = serializers.SerializerMethodField()

    class Meta:
        model = Salary
        fields = [
            "id", "employee", "employee_name", "emp_code", "financial_year",
            "gross_annual_salary", "actual_variable_pay", "monthly_salary",
            "in_hand_salary", "monthly_in_hand", "monthly_variable", "variable_pay",
            "created_at",
        ]

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"

    def get_emp_code(self, obj):
        return obj.employee.id

    def get_monthly_salary(self, obj):
        return obj.monthly_salary

    def get_in_hand_salary(self, obj):
        return obj.in_hand_salary

    def get_monthly_in_hand(self, obj):
        return obj.monthly_in_hand

    def get_monthly_variable(self, obj):
        return obj.monthly_variable

    def get_variable_pay(self, obj):
        return obj.variable_pay



# In your serializers.py, update the MonthlySalarySerializer

class MonthlySalarySerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    per_day_salary = serializers.SerializerMethodField()
    
    # ✅ EXACT RULE FIELDS - Make sure these are read from model
    paid_leave_used = serializers.DecimalField(max_digits=5, decimal_places=1, default=0.0, required=False)
    unpaid_leave_used = serializers.DecimalField(max_digits=5, decimal_places=1, default=0.0, required=False)
    comp_off_used = serializers.DecimalField(max_digits=5, decimal_places=1, default=0.0, required=False)
    salary_cut_days = serializers.DecimalField(max_digits=5, decimal_places=1, default=0.0, required=False)
    used_carry_forward = serializers.DecimalField(max_digits=5, decimal_places=1, default=0.0, required=False)
    new_carry_forward = serializers.DecimalField(max_digits=5, decimal_places=1, default=0.0, required=False)
    
    # ✅ CALCULATION DETAILS
    salary_calculation_details = serializers.JSONField(default=dict)
    
    class Meta:
        model = MonthlySalary
        fields = [
            'id', 'employee', 'employee_name', 'month', 'year',
            'present_days', 'half_days', 'leave_days', 'wfh_days', 'comp_off_days',
            'total_days_in_month', 'paid_weekly_offs', 'total_working_days',
            'gross_monthly_salary', 'professional_tax', 'final_salary', 
            'per_day_salary', 'salary_calculation_method',
            
            # ✅ EXACT RULE FIELDS - CRITICAL: new_carry_forward must be in response
            'paid_leave_used', 'unpaid_leave_used', 'comp_off_used', 'salary_cut_days',
            'carry_forward_half_days', 'used_carry_forward', 'new_carry_forward',
            'salary_calculation_details',
            
            # ✅ BACKWARD COMPATIBILITY FIELDS
            'paid_leaves', 'effective_half_days', 'unpaid_leaves',
            'paid_leave_balance', 'current_month_paid_leaves', 'carry_forward_paid_leaves',
            'used_paid_leaves', 'remaining_paid_leaves', 'used_paid_leaves_for_half_days',
            'used_paid_leaves_for_leaves', 'comp_off_carry_forward',
            
            'generated_at'
        ]
        read_only_fields = ['generated_at']
    
    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"
    
    def get_per_day_salary(self, obj):
        # ✅ FIX: Use total_days_in_month (calendar days 30/31) instead of working days (25)
        if obj.total_days_in_month > 0:
            return round(float(obj.gross_monthly_salary) / obj.total_days_in_month, 2)
        return 0
        
from rest_framework import serializers
from .models import (
    MyUser, AddEmployee, Leave, WFHRequest, Salary, MonthlySalary, 
    Attendance, CompOffRequest, CompOffBalance, WorkSession, ActivityLog, DailyWorkReport
)
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
import pytz

class AttendanceSerializer(serializers.ModelSerializer):
    in_time_formatted = serializers.SerializerMethodField()
    out_time_formatted = serializers.SerializerMethodField()
    in_time_12h = serializers.SerializerMethodField()
    out_time_12h = serializers.SerializerMethodField()
    total_hours = serializers.SerializerMethodField()
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    
    class Meta:
        model = Attendance
        fields = [
            'id', 'employee', 'employee_name', 'date', 'in_time', 'out_time',
            'in_time_formatted', 'out_time_formatted', 'in_time_12h', 'out_time_12h',
            'total_hours', 'status', 'is_half_day_am', 'is_half_day_pm', 'half_day_reason'
        ]
    
    def get_in_time_formatted(self, obj):
        if obj.in_time:
            return obj.in_time.strftime('%I:%M %p')
        return None
    
    def get_out_time_formatted(self, obj):
        if obj.out_time:
            return obj.out_time.strftime('%I:%M %p')
        return None
    
    def get_in_time_12h(self, obj):
        if obj.in_time:
            return obj.in_time.strftime('%I:%M %p')
        return None
    
    def get_out_time_12h(self, obj):
        if obj.out_time:
            return obj.out_time.strftime('%I:%M %p')
        return None
    
    def get_total_hours(self, obj):
        """Calculate total working hours"""
        if obj.in_time and obj.out_time:
            in_dt = datetime.combine(obj.date, obj.in_time)
            out_dt = datetime.combine(obj.date, obj.out_time)
            
            time_diff = out_dt - in_dt
            total_seconds = time_diff.total_seconds()
            total_hours = total_seconds / 3600
            
            return round(total_hours, 2)
        return None
        
class WorkSessionSerializer(serializers.ModelSerializer):
    start_time_ist = serializers.SerializerMethodField()
    end_time_ist = serializers.SerializerMethodField()
    current_time_ist = serializers.SerializerMethodField()
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    employee_id = serializers.IntegerField(source='employee.id', read_only=True)
    department = serializers.CharField(source='employee.department', read_only=True)
    
    class Meta:
        model = WorkSession
        fields = [
            'id', 'employee', 'employee_id', 'employee_name', 'department', 'session_type', 'status',
            'start_time_ist', 'end_time_ist', 'current_time_ist', 'total_hours', 
            'start_note', 'end_note', 'work_completed',
            'productivity_score', 'tasks_planned', 'tasks_completed',
            'energy_level', 'focus_quality', 'breaks_taken', 'meetings_attended',
            'team_interactions', 'blockers'
        ]
    
    def get_start_time_ist(self, obj):
        return obj.get_start_time_ist()
    
    def get_end_time_ist(self, obj):
        return obj.get_end_time_ist()
    
    def get_current_time_ist(self, obj):
        return obj.get_current_ist_time()
    
    def get_elapsed_time(self, obj):
        if obj.status == 'active':
            return obj.calculate_elapsed_time_ist()
        return None

class DailyWorkReportSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='session.employee.get_full_name', read_only=True)
    session_type = serializers.CharField(source='session.session_type', read_only=True)
    work_start_time_ist_formatted = serializers.SerializerMethodField()
    work_end_time_ist_formatted = serializers.SerializerMethodField()
    created_at_ist = serializers.SerializerMethodField()
    
    class Meta:
        model = DailyWorkReport
        fields = [
            'id', 'session', 'employee_name', 'session_type', 'date',
            'tasks_completed', 'challenges_faced', 'next_day_plan',
            'work_start_time_ist', 'work_end_time_ist', 'work_start_time_ist_formatted', 'work_end_time_ist_formatted',
            'total_work_hours', 'tasks_accomplished', 'meeting_hours', 'focused_work_hours',
            'created_at_ist'
        ]
    
    def get_work_start_time_ist_formatted(self, obj):
        if obj.work_start_time_ist:
            return obj.work_start_time_ist.strftime('%H:%M:%S IST')
        return None
    
    def get_work_end_time_ist_formatted(self, obj):
        if obj.work_end_time_ist:
            return obj.work_end_time_ist.strftime('%H:%M:%S IST')
        return None
    
    def get_created_at_ist(self, obj):
        if obj.created_at:
            return obj.created_at.strftime('%Y-%m-%d %H:%M:%S IST')
        return None
# Custom JWT Serializer
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from django.contrib.auth import get_user_model

class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except get_user_model().DoesNotExist:
            from rest_framework import serializers
            raise serializers.ValidationError({'detail': 'User no longer exists. Please login again.'})