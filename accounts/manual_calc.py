from decimal import Decimal


def apply_manual_salary_calculation(half_days, leave_days, manual_comp_off, manual_carry_forward, carry_forward_half_days, total_working_days, present_days=0, wfh_days=0):
    """
    Manual salary calculation when user selects specific comp off and carry forward amounts
    """
    
    print(f"✅ MANUAL Calculation: HD={half_days}, Leaves={leave_days}, Manual CO={manual_comp_off}, Manual CF={manual_carry_forward}")
    
    # Initialize
    paid_leave_used = Decimal('0.0')
    unpaid_leave_used = Decimal('0.0')
    comp_off_used = manual_comp_off
    salary_cut_days = Decimal('0.0')
    used_carry_forward = manual_carry_forward
    new_carry_forward = Decimal('0.0')
    
    # Convert to Decimal
    half_days_dec = Decimal(str(half_days))
    leave_days_dec = Decimal(str(leave_days))
    carry_forward_dec = Decimal(str(carry_forward_half_days))
    
    # Calculate total absence
    total_absence_days = leave_days_dec + (half_days_dec * Decimal('0.5'))
    remaining_absence = total_absence_days
    
    # 1.5 PL available per month + carry forward
    monthly_pl = Decimal('1.5')
    available_paid_leaves = monthly_pl + carry_forward_dec
    
    print(f"📝 Initial: Total PL={available_paid_leaves} (Monthly {monthly_pl} + CF {carry_forward_dec}), Need={total_absence_days}")
    
    # Priority 1: Use manual comp off and carry forward first
    manual_adjustments = comp_off_used + used_carry_forward
    remaining_after_manual = max(Decimal('0.0'), total_absence_days - manual_adjustments)
    
    print(f"✅ Manual adjustments: CO={comp_off_used}, CF={used_carry_forward}, Total={manual_adjustments}")
    print(f"📊 Remaining after manual: {remaining_after_manual}")
    
    # Priority 2: Use remaining PL for what's left
    if remaining_after_manual > 0:
        # Calculate how much PL is actually available after using manual CF
        available_pl_after_cf = available_paid_leaves - used_carry_forward
        pl_used = min(available_pl_after_cf, remaining_after_manual)
        paid_leave_used += pl_used
        remaining_absence = remaining_after_manual - pl_used
        print(f"✅ Used {pl_used} PL (from available {available_pl_after_cf}), remaining: {remaining_absence}")
    else:
        remaining_absence = Decimal('0.0')
        print(f"✅ No additional PL needed")
    
    # Priority 3: Salary Cut
    if remaining_absence > 0:
        unpaid_leave_used = remaining_absence
        salary_cut_days = remaining_absence
        print(f"❌ {remaining_absence} days salary cut")
    
    # Calculate new carry forward
    # Total available - used carry forward - used PL = new carry forward
    new_carry_forward = available_paid_leaves - used_carry_forward - paid_leave_used
    new_carry_forward = max(Decimal('0.0'), new_carry_forward)
    
    print(f"🔄 CF Calculation: Total={available_paid_leaves}, Used CF={used_carry_forward}, Used PL={paid_leave_used}, New CF={new_carry_forward}")
    
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
            'manual_comp_off': float(manual_comp_off),
            'manual_carry_forward': float(manual_carry_forward),
        }
    }
    
    print(f"✅ MANUAL Result: {result}")
    return result
