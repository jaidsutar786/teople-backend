"""
Salary Calculation Logic - EXACT NEW RULES

RULES:
1. Monthly 1.5 days paid leave (cumulative carry forward)
2. Sunday comp off only for unpaid leaves (no extra payment)
3. Company leaves (2nd & 4th Saturday) are paid
4. Paid leave carry forward:
   - January: 1.5 days available
   - If 0.5 used → 1.0 carries to February
   - February: 1.0 + 1.5 = 2.5 available
   - If 3 days leave → 2.5 paid + 0.5 salary cut
5. Comp off carry forward:
   - Comp off used for unpaid leaves only
   - Remaining comp off carries forward
"""
from decimal import Decimal
from .models import MonthlySalary, AddEmployee, CompOffBalance
from datetime import datetime
import calendar


def calculate_monthly_salary_exact_rules(employee_id, month, year, attendance_data, manual_comp_off=None, manual_carry_forward=None):
    """
    Calculate salary with EXACT new rules
    
    Args:
        employee_id: Employee ID
        month: Month (1-12)
        year: Year
        attendance_data: Dict with present_days, half_days, leave_days, etc.
        manual_comp_off: Manual comp off days to use (from frontend)
        manual_carry_forward: Manual carry forward to use (from frontend)
    """
    
    employee = AddEmployee.objects.get(id=employee_id)
    
    # Get previous month's carry forward (ONLY from new_carry_forward field)
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    
    try:
        prev_salary = MonthlySalary.objects.get(
            employee=employee,
            month=prev_month,
            year=prev_year
        )
        # ✅ ONLY use new_carry_forward field
        previous_carry_forward = float(prev_salary.new_carry_forward or 0)
    except MonthlySalary.DoesNotExist:
        previous_carry_forward = 0
    
    # Current month data
    present_days = attendance_data.get('present_days', 0)
    half_days = attendance_data.get('half_days', 0)
    leave_days = attendance_data.get('leave_days', 0)
    wfh_days = attendance_data.get('wfh_days', 0)
    comp_off_days = attendance_data.get('comp_off_days', 0)
    
    # Get comp off balance
    try:
        comp_off_balance = CompOffBalance.objects.get(employee=employee)
        available_comp_off_hours = comp_off_balance.balance_hours
        available_comp_off_days = available_comp_off_hours / 9  # Convert hours to days
    except CompOffBalance.DoesNotExist:
        available_comp_off_hours = 0
        available_comp_off_days = 0
    
    # Calculate total days in month
    total_days_in_month = calendar.monthrange(year, month)[1]
    
    # Paid weekly offs (Sundays + Company leaves)
    paid_weekly_offs = len([d for d in range(1, total_days_in_month + 1) 
                           if calendar.weekday(year, month, d) == 6])
    
    # ✅ EXACT RULES CALCULATION
    monthly_paid_leave = 1.5  # Every month
    total_available_paid = previous_carry_forward + monthly_paid_leave
    
    # Convert half days to equivalent
    half_day_equivalent = half_days * 0.5
    total_leave_needed = leave_days + half_day_equivalent
    
    # Step 1: Use monthly paid leave first
    if total_leave_needed <= total_available_paid:
        # All covered by paid leave
        paid_leave_used = total_leave_needed
        comp_off_used = 0
        carry_forward_used = 0
        salary_cut_days = 0
        new_carry_forward = total_available_paid - total_leave_needed
    else:
        # Need additional coverage
        paid_leave_used = total_available_paid
        remaining_needed = total_leave_needed - total_available_paid
        
        # Step 2: Use comp off (if manual selection provided)
        if manual_comp_off is not None and manual_comp_off > 0:
            comp_off_to_use = min(manual_comp_off, available_comp_off_days, remaining_needed)
        else:
            comp_off_to_use = 0
        
        comp_off_used = comp_off_to_use
        remaining_needed -= comp_off_to_use
        
        # Step 3: Use carry forward (if manual selection provided)
        if manual_carry_forward is not None and manual_carry_forward > 0:
            carry_forward_to_use = min(manual_carry_forward, previous_carry_forward, remaining_needed)
        else:
            carry_forward_to_use = 0
        
        carry_forward_used = carry_forward_to_use
        remaining_needed -= carry_forward_to_use
        
        # Step 4: Remaining = Salary cut
        salary_cut_days = max(0, remaining_needed)
        new_carry_forward = 0
    
    # Calculate effective working days
    effective_days = (
        present_days +
        wfh_days +
        comp_off_days +
        paid_weekly_offs +
        paid_leave_used -
        salary_cut_days
    )
    
    # Gross salary calculation
    gross_monthly_salary = Decimal(employee.salary)
    per_day_salary = gross_monthly_salary / Decimal(total_days_in_month)
    
    # Calculate final salary
    calculated_salary = per_day_salary * Decimal(effective_days)
    professional_tax = Decimal('200.00')
    final_salary = calculated_salary - professional_tax
    
    # Create or update salary record
    salary_record, created = MonthlySalary.objects.update_or_create(
        employee=employee,
        month=month,
        year=year,
        defaults={
            'present_days': present_days,
            'half_days': half_days,
            'leave_days': leave_days,
            'wfh_days': wfh_days,
            'comp_off_days': comp_off_days,
            'total_days_in_month': total_days_in_month,
            'paid_weekly_offs': paid_weekly_offs,
            'total_working_days': int(effective_days),
            'gross_monthly_salary': gross_monthly_salary,
            'professional_tax': professional_tax,
            'final_salary': final_salary,
            
            # ✅ NEW EXACT RULE FIELDS
            'paid_leave_used': Decimal(str(paid_leave_used)),
            'unpaid_leave_used': Decimal(str(leave_days - paid_leave_used if leave_days > paid_leave_used else 0)),
            'comp_off_used': Decimal(str(comp_off_used)),
            'salary_cut_days': Decimal(str(salary_cut_days)),
            
            # Carry forward fields
            'carry_forward_half_days': Decimal(str(previous_carry_forward)),
            'used_carry_forward': Decimal(str(carry_forward_used)),
            'new_carry_forward': Decimal(str(new_carry_forward)),
            
            'salary_calculation_method': 'exact_new_rules'
        }
    )
    
    return {
        'success': True,
        'salary_record': salary_record,
        'paid_leave_used': paid_leave_used,
        'comp_off_used': comp_off_used,
        'carry_forward_used': carry_forward_used,
        'salary_cut_days': salary_cut_days,
        'new_carry_forward': new_carry_forward,
        'effective_days': effective_days,
        'final_salary': float(final_salary),
        'calculation_details': {
            'monthly_paid_leave': monthly_paid_leave,
            'previous_carry_forward': previous_carry_forward,
            'total_available_paid': total_available_paid,
            'total_leave_needed': total_leave_needed,
            'paid_leave_used': paid_leave_used,
            'comp_off_used': comp_off_used,
            'carry_forward_used': carry_forward_used,
            'salary_cut_days': salary_cut_days,
            'new_carry_forward': new_carry_forward
        }
    }
