from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings
from datetime import timedelta, datetime
import uuid
from decimal import Decimal
import pytz
from django.utils import timezone
import random


# ========== Custom User Manager ==========
class MyUserManager(BaseUserManager):
    def create_user(
        self, email, username, password=None, role="employee", **extra_fields
    ):
        if not email:
            raise ValueError("Email required")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, role=role, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        return self.create_user(
            email=email,
            username=username,
            password=password,
            role="admin",
            **extra_fields,
        )


# ========== Custom User Model ==========
class MyUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("employee", "Employee"),
    )

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=50)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="employee")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = MyUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email


# ========== Employee Model ==========
class AddEmployee(models.Model):
    user = models.OneToOneField(
        MyUser, on_delete=models.CASCADE, related_name="employee_profile"
    )
 
    DEPARTMENT_CHOICES = [
        ("engineering", "Engineering"),
        ("design", "Design"),
        ("marketing", "Marketing"),
        ("hr", "Human Resources"),
        ("finance", "Finance"),
    ]

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]

    employee_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    phone = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=50, choices=DEPARTMENT_CHOICES)
    position = models.CharField(max_length=100)
    address = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    
    # ✅ NEW: Joining date field
    joining_date = models.DateField(blank=True, null=True, help_text="Employee joining date")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Offer Letter Fields
    offer_letter_sent = models.BooleanField(default=False)
    offer_letter_pdf = models.FileField(upload_to='offer_letters/', blank=True, null=True)
    offer_letter_date = models.DateField(blank=True, null=True)
    offer_letter_ctc = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    
    # Relieving Letter Fields
    relieving_letter_sent = models.BooleanField(default=False)
    relieving_letter_pdf = models.FileField(upload_to='relieving_letters/', blank=True, null=True)
    relieving_letter_date = models.DateField(blank=True, null=True)
    last_working_day = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_joining_date_display(self):
        """Get formatted joining date"""
        if self.joining_date:
            return self.joining_date.strftime('%d-%B-%Y')
        return self.created_at.strftime('%d-%B-%Y')  # Fallback to created_at
    
    def get_full_name(self):
        """WorkSession serializer के लिए required"""
        return f"{self.first_name} {self.last_name}"
    
    def save(self, *args, **kwargs):
        """Auto-generate employee_id if not provided"""
        if not self.employee_id:
            # Find the highest existing employee number
            existing_employees = AddEmployee.objects.filter(
                employee_id__isnull=False,
                employee_id__startswith='EMP'
            ).exclude(pk=self.pk if self.pk else None)
            
            max_number = 0
            for emp in existing_employees:
                try:
                    number = int(emp.employee_id.replace('EMP', ''))
                    max_number = max(max_number, number)
                except (ValueError, AttributeError):
                    continue
            
            # Generate next number
            new_number = max_number + 1
            self.employee_id = f"EMP{new_number:03d}"
            
        super().save(*args, **kwargs)


class Leave(models.Model):
    LEAVE_TYPES = [
        ("sick", "Sick Leave"),
        ("casual", "Casual Leave"), 
        ("paid", "Paid Leave"),
        ("unpaid", "Unpaid Leave"),
    ]

    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leaves",
    )
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    rejection_reason = models.TextField(blank=True, null=True)
    applied_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.leave_type} ({self.status})"

    def save(self, *args, **kwargs):
        """Override save to update attendance when leave status changes"""
        old_status = None
        if self.pk:
            try:
                old_obj = Leave.objects.get(pk=self.pk)
                old_status = old_obj.status
            except Leave.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # If status changed to Approved, update attendance
        if self.status == "Approved" and old_status != "Approved":
            self.update_attendance_for_approved_leave()
        
        # If status changed from Approved to Rejected, remove attendance
        elif old_status == "Approved" and self.status == "Rejected":
            self.remove_leave_from_attendance()

    def update_attendance_for_approved_leave(self):
        """Update attendance records when leave is approved"""
        try:
            employee = AddEmployee.objects.get(user=self.user)
            current_date = self.start_date
            
            while current_date <= self.end_date:
                # Skip weekends
                if current_date.weekday() not in [5, 6]:  # 5=Saturday, 6=Sunday
                    # Create or update attendance record for each date in leave period
                    attendance, created = Attendance.objects.get_or_create(
                        employee=employee,
                        date=current_date,
                        defaults={
                            'status': 'leave',
                            'in_time': None,
                            'out_time': None
                        }
                    )
                    
                    if not created:
                        attendance.status = 'leave'
                        attendance.in_time = None
                        attendance.out_time = None
                        attendance.save()
                
                current_date += timedelta(days=1)
                
        except AddEmployee.DoesNotExist:
            print(f"Employee profile not found for user {self.user}")

    def remove_leave_from_attendance(self):
        """Remove leave marks when leave is rejected"""
        try:
            employee = AddEmployee.objects.get(user=self.user)
            current_date = self.start_date
            
            while current_date <= self.end_date:
                # Remove attendance records for leave dates
                Attendance.objects.filter(
                    employee=employee,
                    date=current_date,
                    status='leave'
                ).delete()
                
                current_date += timedelta(days=1)
                
        except AddEmployee.DoesNotExist:
            print(f"Employee profile not found for user {self.user}")


# Fixed WFHRequest model - Added missing fields
class WFHRequest(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"), 
        ("Rejected", "Rejected"),
        ("Active", "Active"),
        ("Completed", "Completed"),
    ]

    TYPE_CHOICES = [
        ("Full Day", "Full Day"),
        ("Half Day", "Half Day"),
        ("Comp Off", "Comp Off"),
    ]

    user = models.ForeignKey(MyUser, on_delete=models.CASCADE, related_name="wfh_requests")
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    rejection_reason = models.TextField(blank=True, null=True)
    expected_hours = models.DecimalField(max_digits=5, decimal_places=2, default=8.0)
    actual_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.status}"

    def save(self, *args, **kwargs):
        """Override save to update attendance when WFH status changes"""
        old_status = None
        if self.pk:
            try:
                old_obj = WFHRequest.objects.get(pk=self.pk)
                old_status = old_obj.status
            except WFHRequest.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # If status changed to Approved, update attendance
        if self.status == "Approved" and old_status != "Approved":
            self.update_attendance_for_approved_wfh()
        
        # If status changed from Approved to Rejected, remove attendance
        elif old_status == "Approved" and self.status == "Rejected":
            self.remove_wfh_from_attendance()

    def update_attendance_for_approved_wfh(self):
        """Update attendance records when WFH is approved"""
        try:
            employee = AddEmployee.objects.get(user=self.user)
            current_date = self.start_date
            
            while current_date <= self.end_date:
                # Skip weekends
                if current_date.weekday() not in [5, 6]:
                    # Create or update attendance record
                    attendance, created = Attendance.objects.get_or_create(
                        employee=employee,
                        date=current_date,
                        defaults={
                            'status': 'wfh',
                            'in_time': None,
                            'out_time': None
                        }
                    )
                    
                    if not created:
                        attendance.status = 'wfh'
                        attendance.save()
                
                current_date += timedelta(days=1)
                
        except AddEmployee.DoesNotExist:
            print(f"Employee profile not found for user {self.user}")

    def remove_wfh_from_attendance(self):
        """Remove WFH marks when WFH is rejected"""
        try:
            employee = AddEmployee.objects.get(user=self.user)
            current_date = self.start_date
            
            while current_date <= self.end_date:
                # Remove WFH attendance records
                Attendance.objects.filter(
                    employee=employee,
                    date=current_date,
                    status='wfh'
                ).delete()
                
                current_date += timedelta(days=1)
                
        except AddEmployee.DoesNotExist:
            print(f"Employee profile not found for user {self.user}")


class Salary(models.Model):
    employee = models.OneToOneField(
        AddEmployee, on_delete=models.CASCADE, related_name="salary"
    )
    financial_year = models.CharField(max_length=20)
    gross_annual_salary = models.DecimalField(max_digits=12, decimal_places=2)
    actual_variable_pay = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def monthly_salary(self):
        return self.gross_annual_salary / 12

    @property
    def in_hand_salary(self):
        return self.gross_annual_salary - self.actual_variable_pay

    @property
    def monthly_in_hand(self):
        return self.in_hand_salary / 12

    @property
    def monthly_variable(self):
        return self.actual_variable_pay / 12

    @property
    def variable_pay(self):
        return self.actual_variable_pay

    def __str__(self):
        return f"{self.employee.first_name} {self.employee.last_name} - {self.financial_year}"



class Attendance(models.Model):
    """Model to track daily attendance with leave and WFH information"""
    employee = models.ForeignKey(AddEmployee, on_delete=models.CASCADE, related_name="attendances")
    date = models.DateField()
    in_time = models.TimeField(null=True, blank=True)
    out_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('present', 'Present'),
        ('half_day', 'Half Day'),  # ✅ EXISTING
        ('absent', 'Absent'),
        ('leave', 'Leave'),
        ('wfh', 'Work From Home'),
        ('comp_off', 'Comp Off'),
        ('weekend', 'Weekend'),
        ('holiday', 'Holiday')
    ], default='absent')
    
    # ✅ NEW FIELDS FOR HALF DAY TRACKING
    is_half_day_am = models.BooleanField(default=False)      # ✅ NEW FIELD
    is_half_day_pm = models.BooleanField(default=False)      # ✅ NEW FIELD
    half_day_reason = models.CharField(max_length=100, blank=True, null=True)  # ✅ NEW FIELD
    
    # ✅ ADMIN COVER TRACKING - YE NAYA FIELD HAI
    admin_covered = models.BooleanField(default=False)       # ✅ ADMIN COVER INDICATOR
    admin_covered_by = models.ForeignKey(MyUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='covered_attendances')  # ✅ KAUN ADMIN NE COVER KIYA
    admin_covered_at = models.DateTimeField(null=True, blank=True)  # ✅ KAB COVER KIYA
    admin_cover_reason = models.CharField(max_length=200, blank=True, null=True)  # ✅ COVER KARNE KA REASON
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('employee', 'date')

    def __str__(self):
        return f"{self.employee.first_name} - {self.date} - {self.status}"

class CompOffRequest(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Rejected", "Rejected"),
        ("Active", "Active"),
        ("Completed", "Completed"),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="comp_off_requests"
    )
    date = models.DateField()
    hours = models.IntegerField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    rejection_reason = models.TextField(blank=True, null=True)
    actual_hours_worked = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.date} - {self.hours}hrs - {self.status}"

    def save(self, *args, **kwargs):
        """Override save to update comp off balance when status changes"""
        # Get the old status if this is an update
        old_status = None
        if self.pk:
            try:
                old_obj = CompOffRequest.objects.get(pk=self.pk)
                old_status = old_obj.status
            except CompOffRequest.DoesNotExist:
                pass
        
        # Call the "real" save() method
        super().save(*args, **kwargs)
        
        # ✅ FIXED: Only update balance for NEW approved requests
        if self.status == "Approved" and old_status != "Approved":
            self.update_comp_off_balance()
            self.create_attendance_record()
        
        # ✅ FIXED: Only remove balance when changing FROM Approved to Rejected
        elif old_status == "Approved" and self.status == "Rejected":
            self.remove_comp_off_balance()
            self.remove_attendance_record()

    def update_comp_off_balance(self):
        """✅ FIXED: Update comp off balance when request is approved"""
        try:
            employee = AddEmployee.objects.get(user=self.user)
            comp_off_balance, created = CompOffBalance.objects.get_or_create(
                employee=employee,
                defaults={
                    'balance_hours': self.hours,
                    'earned_hours': self.hours,
                    'used_hours': 0
                }
            )
            
            if not created:
                # ✅ FIX: Add to existing balance, don't overwrite
                comp_off_balance.balance_hours += self.hours
                comp_off_balance.earned_hours += self.hours
                comp_off_balance.save()
                
            print(f"✅ Comp Off Balance Updated: {employee.first_name} - +{self.hours} hours")
                
        except AddEmployee.DoesNotExist:
            print(f"❌ Employee profile not found for user {self.user}")

    def remove_comp_off_balance(self):
        """✅ FIXED: Remove comp off from balance when request is rejected"""
        try:
            employee = AddEmployee.objects.get(user=self.user)
            comp_off_balance = CompOffBalance.objects.get(employee=employee)
            
            # ✅ FIX: Only remove if we have enough balance
            if comp_off_balance.balance_hours >= self.hours:
                comp_off_balance.balance_hours -= self.hours
                comp_off_balance.earned_hours -= self.hours
                comp_off_balance.save()
                print(f"✅ Comp Off Balance Removed: {employee.first_name} - -{self.hours} hours")
            else:
                print(f"⚠️ Not enough balance to remove: {comp_off_balance.balance_hours} available, {self.hours} requested")
                
        except (AddEmployee.DoesNotExist, CompOffBalance.DoesNotExist):
            print(f"❌ Employee or balance not found for user {self.user}")

    def remove_comp_off_balance(self):
        """Remove comp off from balance when request is rejected"""
        try:
            employee = AddEmployee.objects.get(user=self.user)
            comp_off_balance = CompOffBalance.objects.get(employee=employee)
            
            # Remove the hours from balance
            comp_off_balance.balance_hours = max(0, comp_off_balance.balance_hours - self.hours)
            comp_off_balance.earned_hours = max(0, comp_off_balance.earned_hours - self.hours)
            comp_off_balance.save()
            
            print(f"✅ Comp Off Balance Removed: {employee.first_name} - -{self.hours} hours")
                
        except (AddEmployee.DoesNotExist, CompOffBalance.DoesNotExist):
            print(f"❌ Employee or balance not found for user {self.user}")

    def create_attendance_record(self):
        """Create attendance record for comp off date"""
        try:
            employee = AddEmployee.objects.get(user=self.user)
            
            # Create or update attendance record
            attendance, created = Attendance.objects.get_or_create(
                employee=employee,
                date=self.date,
                defaults={
                    'status': 'comp_off',
                    'in_time': None,
                    'out_time': None
                }
            )
            
            if not created:
                attendance.status = 'comp_off'
                attendance.in_time = None
                attendance.out_time = None
                attendance.save()
            
            print(f"✅ Attendance record created for comp off: {employee.first_name} - {self.date}")
                
        except AddEmployee.DoesNotExist:
            print(f"❌ Employee profile not found for user {self.user}")

    def remove_attendance_record(self):
        """Remove comp off attendance record"""
        try:
            employee = AddEmployee.objects.get(user=self.user)
            
            # Remove attendance record for comp off date
            Attendance.objects.filter(
                employee=employee,
                date=self.date,
                status='comp_off'
            ).delete()
            
            print(f"✅ Attendance record removed for comp off: {employee.first_name} - {self.date}")
                
        except AddEmployee.DoesNotExist:
            print(f"❌ Employee profile not found for user {self.user}")

class CompOffBalance(models.Model):
    employee = models.OneToOneField(
        AddEmployee, on_delete=models.CASCADE, related_name="comp_off_balance"
    )
    balance_hours = models.IntegerField(default=0)
    earned_hours = models.IntegerField(default=0)
    used_hours = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.first_name} - {self.balance_hours} hours"

    def use_comp_off(self, hours_to_use):
        """Use comp off hours and update balance"""
        if hours_to_use > self.balance_hours:
            raise ValueError("Not enough comp off balance")
        
        self.balance_hours -= hours_to_use
        self.used_hours += hours_to_use
        self.save()


class MonthlySalary(models.Model):
    employee = models.ForeignKey(AddEmployee, on_delete=models.CASCADE, related_name='monthly_salaries')
    month = models.IntegerField()
    year = models.IntegerField()
    
    # Attendance data
    present_days = models.IntegerField(default=0)
    half_days = models.IntegerField(default=0)
    leave_days = models.IntegerField(default=0)
    wfh_days = models.IntegerField(default=0)
    comp_off_days = models.IntegerField(default=0)
    
    # Working days calculation
    total_days_in_month = models.IntegerField(default=0)
    paid_weekly_offs = models.IntegerField(default=0)
    total_working_days = models.IntegerField(default=0)
    
    # Salary calculation
    gross_monthly_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    professional_tax = models.DecimalField(max_digits=10, decimal_places=2, default=200)
    final_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # ✅ EXACT RULE FIELDS
    paid_leave_used = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    unpaid_leave_used = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    comp_off_used = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    salary_cut_days = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    
    # Carry forward fields
    carry_forward_half_days = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    used_carry_forward = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    new_carry_forward = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    
    # ✅ BACKWARD COMPATIBILITY FIELDS
    paid_leaves = models.IntegerField(default=0)
    effective_half_days = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    unpaid_leaves = models.IntegerField(default=0)
    paid_leave_balance = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    current_month_paid_leaves = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    carry_forward_paid_leaves = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    used_paid_leaves = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    remaining_paid_leaves = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    used_paid_leaves_for_half_days = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    used_paid_leaves_for_leaves = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    comp_off_carry_forward = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Salary calculation details
    salary_calculation_method = models.CharField(max_length=50, default='exact_new_rules')
    salary_calculation_details = models.JSONField(default=dict, blank=True)
    
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'month', 'year')
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.employee.first_name} - {self.year}/{self.month} - ₹{self.final_salary}"
        
class WorkSession(models.Model):
    SESSION_TYPES = [
        ('wfh', 'Work From Home'),
        ('comp_off', 'Comp Off'),
        ('regular', 'Regular Office'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
    ]
    
    ENERGY_LEVELS = [
        (1, 'Very Low'),
        (2, 'Low'),
        (3, 'Medium'),
        (4, 'High'),
        (5, 'Very High'),
    ]
    
    FOCUS_QUALITY = [
        (1, 'Poor'),
        (2, 'Fair'),
        (3, 'Good'),
        (4, 'Very Good'),
        (5, 'Excellent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(AddEmployee, on_delete=models.CASCADE, related_name="work_sessions")
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES)
    request = models.ForeignKey('WFHRequest', on_delete=models.CASCADE, null=True, blank=True)
    comp_off_request = models.ForeignKey('CompOffRequest', on_delete=models.CASCADE, null=True, blank=True)
    
    # Work tracking - Store in UTC but display in IST
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    total_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Notes system
    start_note = models.TextField(blank=True, null=True, verbose_name="Start of Work Note")
    end_note = models.TextField(blank=True, null=True, verbose_name="End of Work Note")
    work_completed = models.TextField(blank=True, null=True, verbose_name="Work Completed Summary")
    
    # MODERN: Task-based tracking (REMOVED invasive tracking)
    tasks_planned = models.JSONField(default=list, blank=True)  # [{'task': 'Fix bug', 'priority': 'high'}]
    tasks_completed = models.JSONField(default=list, blank=True)  # [{'task': 'Fix bug', 'time_spent': '2h', 'completed_at': '14:30'}]
    blockers = models.TextField(blank=True, null=True)
    
    # MODERN: Self-reported productivity
    energy_level = models.IntegerField(choices=ENERGY_LEVELS, null=True, blank=True)
    focus_quality = models.IntegerField(choices=FOCUS_QUALITY, null=True, blank=True)
    
    # MODERN: Break tracking (self-reported)
    breaks_taken = models.JSONField(default=list, blank=True)  # [{'start': '10:00', 'end': '10:15', 'type': 'coffee'}]
    
    # MODERN: Collaboration metrics
    meetings_attended = models.IntegerField(default=0)
    team_interactions = models.IntegerField(default=0)
    
    # Performance metrics
    productivity_score = models.IntegerField(default=50)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return f"{self.employee.first_name} - {self.session_type} - {self.start_time.date()}"

    def get_start_time_ist(self):
        """Get start time in IST - Indian Standard Time"""
        if self.start_time:
            try:
                ist = pytz.timezone('Asia/Kolkata')
                if timezone.is_naive(self.start_time):
                    start_time_aware = timezone.make_aware(self.start_time, timezone.utc)
                else:
                    start_time_aware = self.start_time
                start_time_ist = start_time_aware.astimezone(ist)
                return start_time_ist.strftime('%d-%m-%Y %I:%M %p IST')  # Indian format: DD-MM-YYYY
            except Exception as e:
                print(f"Error converting to IST: {e}")
                return self.start_time.strftime('%d-%m-%Y %I:%M %p')
        return None

    def get_end_time_ist(self):
        """Get end time in IST - Indian Standard Time"""
        if self.end_time:
            try:
                ist = pytz.timezone('Asia/Kolkata')
                if timezone.is_naive(self.end_time):
                    end_time_aware = timezone.make_aware(self.end_time, timezone.utc)
                else:
                    end_time_aware = self.end_time
                end_time_ist = end_time_aware.astimezone(ist)
                return end_time_ist.strftime('%d-%m-%Y %I:%M %p IST')  # Indian format
            except Exception as e:
                print(f"Error converting to IST: {e}")
                return self.end_time.strftime('%d-%m-%Y %I:%M %p')
        return None

    def get_current_ist_time(self):
        """Get current time in IST - Indian Standard Time"""
        ist = pytz.timezone('Asia/Kolkata')
        return timezone.now().astimezone(ist).strftime('%d-%m-%Y %I:%M %p IST')

    def calculate_total_hours(self):
        """Calculate total hours worked with IST timezone - FIXED VERSION"""
        if self.start_time and self.end_time:
            try:
                # Convert to IST timezone for calculation
                ist = pytz.timezone('Asia/Kolkata')
                
                # Make times timezone aware if they aren't
                start_time_aware = self.start_time
                if timezone.is_naive(start_time_aware):
                    start_time_aware = timezone.make_aware(start_time_aware, timezone.utc)
                
                end_time_aware = self.end_time
                if timezone.is_naive(end_time_aware):
                    end_time_aware = timezone.make_aware(end_time_aware, timezone.utc)
                
                # Convert to IST for calculation
                start_time_ist = start_time_aware.astimezone(ist)
                end_time_ist = end_time_aware.astimezone(ist)
                
                duration = end_time_ist - start_time_ist
                total_seconds = duration.total_seconds()
                total_hours = total_seconds / 3600
                
                self.total_hours = Decimal(str(round(total_hours, 2)))
                self.save(update_fields=['total_hours'])
                return self.total_hours
            except (TypeError, ValueError) as e:
                print(f"Error calculating total hours: {e}")
                return Decimal('0.0')
        return Decimal('0.0')
    
    
    def calculate_productivity_score(self):
        """MODERN: Calculate productivity based on outcomes, not activity"""
        try:
            score = 0
            
            # Factor 1: Task completion (40 points) - MOST IMPORTANT
            if self.tasks_planned:
                completed_count = len(self.tasks_completed)
                planned_count = len(self.tasks_planned)
                completion_rate = completed_count / planned_count
                score += completion_rate * 40
            else:
                # If no tasks planned, give base score
                score += 20
            
            # Factor 2: Work hours (30 points)
            if self.total_hours:
                hours = float(self.total_hours)
                if hours >= 8:
                    score += 30
                elif hours >= 6:
                    score += 20
                elif hours >= 4:
                    score += 10
            
            # Factor 3: Self-reported quality (20 points)
            if self.energy_level and self.focus_quality:
                quality_score = (self.energy_level + self.focus_quality) * 2
                score += min(20, quality_score)
            
            # Factor 4: Collaboration (10 points)
            collab_score = (self.meetings_attended * 2) + (self.team_interactions * 1)
            score += min(10, collab_score)
            
            # Bonus: Detailed work notes
            if self.work_completed and len(self.work_completed.strip()) > 50:
                score += 5
            
            # Ensure score is between 0 and 100
            final_score = max(0, min(100, int(score)))
            
            self.productivity_score = final_score
            self.save(update_fields=['productivity_score'])
            
            return final_score
            
        except Exception as e:
            print(f"Error calculating productivity score: {e}")
            self.productivity_score = 50
            self.save(update_fields=['productivity_score'])
            return 50
        
    
    
    
    def calculate_elapsed_time_ist(self):
        """Calculate elapsed time for active sessions in IST"""
        if self.status == 'active' and self.start_time:
            try:
                ist = pytz.timezone('Asia/Kolkata')
                current_time_ist = timezone.now().astimezone(ist)
                
                start_time_aware = self.start_time
                if timezone.is_naive(start_time_aware):
                    start_time_aware = timezone.make_aware(start_time_aware, timezone.utc)
                
                start_time_ist = start_time_aware.astimezone(ist)
                duration = current_time_ist - start_time_ist
                
                total_seconds = int(duration.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                
                return f"{hours}h {minutes}m"
            except Exception as e:
                print(f"Error calculating elapsed time: {e}")
                return "0h 0m"
        return "0h 0m"

class ActivityLog(models.Model):
    ACTIVITY_TYPES = [
        ('screenshot', 'Screenshot'),
        ('keyboard', 'Keyboard Activity'),
        ('mouse', 'Mouse Activity'),
        ('application', 'Application Switch'),
        ('break_start', 'Break Started'),
        ('break_end', 'Break Ended'),
        ('focus_start', 'Focus Time Started'),
        ('focus_end', 'Focus Time Ended'),
        ('note_added', 'Note Added'),
    ]
    
    session = models.ForeignKey(WorkSession, on_delete=models.CASCADE, related_name="activity_logs")
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)
    note = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']

class DailyWorkReport(models.Model):
    """Model to store daily work reports with Indian time"""
    session = models.OneToOneField(WorkSession, on_delete=models.CASCADE, related_name="daily_report")
    date = models.DateField()
    
    # Work details
    tasks_completed = models.TextField()
    challenges_faced = models.TextField(blank=True, null=True)
    next_day_plan = models.TextField(blank=True, null=True)
    
    # Time tracking in IST
    work_start_time_ist = models.TimeField()
    work_end_time_ist = models.TimeField()
    total_work_hours = models.DecimalField(max_digits=4, decimal_places=2)
    
    # Productivity metrics
    tasks_accomplished = models.JSONField(default=list)
    meeting_hours = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    focused_work_hours = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.session.employee.first_name} - {self.date}"


class FormRevisionNotification(models.Model):
    """Model to store form revision request notifications"""
    employee = models.ForeignKey(
        AddEmployee, 
        on_delete=models.CASCADE, 
        related_name='revision_notifications'
    )
    message = models.TextField()
    incomplete_fields = models.JSONField(default=list)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Revision notification for {self.employee.first_name} - {self.created_at}"


class EmployeeOTP(models.Model):
    """Model to store OTP for employee first-time registration verification"""
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"OTP for {self.email} - {self.otp}"
    
    def is_expired(self):
        """Check if OTP is expired (10 minutes validity)"""
        return timezone.now() > self.expires_at
    
    @staticmethod
    def generate_otp():
        """Generate 6-digit OTP"""
        return str(random.randint(100000, 999999))


# Import AdminNote model
from .admin_notes_models import AdminNote
# Import Asset models
from .asset_models import Asset, AssetAssignment
# Import Leave Management models
from .leave_management_models import CompanyLeave, SaturdayOverride
# Import Comp Off Usage Notification model
from .notification_models import CompOffUsageNotification