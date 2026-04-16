from django.http import HttpResponse
from django.template.loader import render_to_string
from datetime import datetime
from .models import AddEmployee, MonthlySalary
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO


def generate_html_salary_slip(employee_id, month, year):
    """Generate professional PDF salary slip using ReportLab
    month: 1-indexed (1-12) from frontend
    """
    try:
        employee = AddEmployee.objects.get(id=employee_id)
        # Database stores 1-indexed month now, use as-is
        monthly_salary = MonthlySalary.objects.get(employee=employee, month=month, year=year)
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Simple black text only
        black = colors.black
        border = colors.HexColor('#000000')
        
        # Header - simple text
        p.setFillColor(black)
        p.setFont("Helvetica-Bold", 24)
        p.drawString(50, height-50, "TEOPLE TECHNOLOGIES")
        p.setFont("Helvetica", 9)
        p.drawString(50, height-68, "Innovation • Excellence • Growth")
        
        # Slip title on right
        p.setFont("Helvetica-Bold", 16)
        p.drawRightString(width-50, height-50, "SALARY SLIP")
        p.setFont("Helvetica", 8)
        p.drawRightString(width-50, height-68, f"{datetime(year, month, 1).strftime('%B %Y').upper()}")
        p.drawRightString(width-50, height-85, f"Slip No: {year}/{month:02d}/{employee.id:04d}")
        
        # Line separator
        p.setStrokeColor(black)
        p.setLineWidth(1)
        p.line(40, height-100, width-40, height-100)
        
        y = height - 120
        
        # Employee details box
        p.setStrokeColor(black)
        p.setLineWidth(0.5)
        p.rect(40, y-90, 245, 80, fill=0, stroke=1)
        
        p.setFillColor(black)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(50, y-20, "EMPLOYEE DETAILS")
        
        p.setFont("Helvetica", 8)
        p.drawString(50, y-38, "ID:")
        p.setFont("Helvetica-Bold", 8)
        p.drawString(130, y-38, f"{employee.id}")
        
        p.setFont("Helvetica", 8)
        p.drawString(50, y-52, "Name:")
        p.setFont("Helvetica-Bold", 8)
        p.drawString(130, y-52, f"{employee.first_name} {employee.last_name}")
        
        p.setFont("Helvetica", 8)
        p.drawString(50, y-66, "Department:")
        p.setFont("Helvetica-Bold", 8)
        p.drawString(130, y-66, f"{employee.department.title()}")
        
        p.setFont("Helvetica", 8)
        p.drawString(50, y-80, "Designation:")
        p.setFont("Helvetica-Bold", 8)
        p.drawString(130, y-80, f"{employee.position}")
        
        # Payment details box
        p.setStrokeColor(black)
        p.setLineWidth(0.5)
        p.rect(300, y-90, 255, 80, fill=0, stroke=1)
        
        p.setFillColor(black)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(310, y-20, "PAYMENT DETAILS")
        
        p.setFont("Helvetica", 8)
        p.drawString(310, y-38, "Payment Date:")
        p.setFont("Helvetica-Bold", 8)
        p.drawRightString(545, y-38, f"{datetime.now().strftime('%d-%m-%Y')}")
        
        p.setFont("Helvetica", 8)
        p.drawString(310, y-52, "Method:")
        p.setFont("Helvetica-Bold", 8)
        p.drawRightString(545, y-52, "Bank Transfer")
        
        p.setFont("Helvetica", 8)
        p.drawString(310, y-66, "Working Days:")
        p.setFont("Helvetica-Bold", 8)
        p.drawRightString(545, y-66, f"{monthly_salary.total_days_in_month}")
        
        p.setFont("Helvetica", 8)
        p.drawString(310, y-80, "Per Day Salary:")
        p.setFont("Helvetica-Bold", 8)
        p.drawRightString(545, y-80, f"Rs. {float(monthly_salary.gross_monthly_salary)/monthly_salary.total_days_in_month:,.2f}")
        
        y -= 110
        
        # Salary breakdown
        p.setFillColor(black)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(50, y, "SALARY BREAKDOWN")
        
        y -= 18
        # Table
        p.setStrokeColor(black)
        p.setLineWidth(0.5)
        p.rect(40, y-50, width-80, 50, fill=0, stroke=1)
        
        # Header line
        p.line(40, y-15, width-40, y-15)
        
        p.setFont("Helvetica-Bold", 8)
        p.drawString(50, y-10, "DESCRIPTION")
        p.drawRightString(width-50, y-10, "AMOUNT (Rs.)")
        
        # Gross salary
        p.setFont("Helvetica", 8)
        p.drawString(50, y-28, "Gross Monthly Salary")
        p.setFont("Helvetica-Bold", 8)
        p.drawRightString(width-50, y-28, f"{float(monthly_salary.gross_monthly_salary):,.2f}")
        
        # Professional tax
        p.setFont("Helvetica", 8)
        p.drawString(50, y-42, "Professional Tax")
        p.setFont("Helvetica-Bold", 8)
        p.drawRightString(width-50, y-42, f"- {float(monthly_salary.professional_tax):,.2f}")
        
        y -= 65
        # Net salary box
        p.setStrokeColor(black)
        p.setLineWidth(1)
        p.rect(40, y-35, width-80, 35, fill=0, stroke=1)
        
        p.setFillColor(black)
        p.setFont("Helvetica-Bold", 10)
        p.drawCentredString(width/2, y-12, "NET SALARY PAYABLE")
        p.setFont("Helvetica-Bold", 16)
        p.drawCentredString(width/2, y-27, f"Rs. {float(monthly_salary.final_salary):,.2f}")
        
        # Footer
        p.setStrokeColor(black)
        p.setLineWidth(0.5)
        p.line(40, 80, width-40, 80)
        
        p.setFillColor(black)
        p.setFont("Helvetica", 7)
        p.drawCentredString(width/2, 65, "95, Maske Vasti Rd, Ravet, Pimpri-Chinchwad, Maharashtra 412101")
        p.drawCentredString(width/2, 55, "Phone: +91 9420206555 | Email: admin@teople.co.in")
        p.setFont("Helvetica-Oblique", 6)
        p.drawCentredString(width/2, 40, "This is a computer-generated salary slip. No signature required.")
        
        p.showPage()
        p.save()
        buffer.seek(0)
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Salary_Slip_{employee.first_name}_{year}_{month}.pdf"'
        return response
        
    except AddEmployee.DoesNotExist:
        return HttpResponse("Employee not found", status=404)
    except MonthlySalary.DoesNotExist:
        return HttpResponse("Salary record not found", status=404)
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)


def generate_html_salary_slip_preview(employee_id, month, year):
    """Generate HTML preview for browser viewing
    month: 1-indexed (1-12) from frontend
    """
    try:
        employee = AddEmployee.objects.get(id=employee_id)
        # Database stores 1-indexed month now, use as-is
        monthly_salary = MonthlySalary.objects.get(employee=employee, month=month, year=year)
        
        context = {
            'employee_id': f'TS{employee.id:04d}',
            'employee_name': f'{employee.first_name} {employee.last_name}',
            'department': employee.department.title(),
            'designation': employee.position,
            'month_year': datetime(year, month, 1).strftime('%B %Y'),
            'payment_date': datetime.now().strftime('%d-%m-%Y'),
            'slip_number': f'{year}/{month:02d}/{employee.id:04d}',
            'gross_salary': f'{float(monthly_salary.gross_monthly_salary):,.2f}',
            'per_day_salary': f'{float(monthly_salary.gross_monthly_salary) / monthly_salary.total_days_in_month:,.2f}',
            'professional_tax': f'{float(monthly_salary.professional_tax):,.2f}',
            'net_salary': f'{float(monthly_salary.final_salary):,.2f}',
            'total_days': monthly_salary.total_days_in_month,
            'present_days': monthly_salary.present_days,
            'half_days': monthly_salary.half_days,
            'leave_days': monthly_salary.leave_days,
            'wfh_days': monthly_salary.wfh_days,
            'comp_off_days': monthly_salary.comp_off_days,
            'paid_weekly_offs': monthly_salary.paid_weekly_offs,
            'paid_leaves': monthly_salary.paid_leaves,
            'comp_off_used': monthly_salary.comp_off_used,
            'effective_days': (monthly_salary.present_days - monthly_salary.half_days) + 
                            monthly_salary.paid_leaves + 
                            monthly_salary.paid_weekly_offs + 
                            monthly_salary.wfh_days + 
                            monthly_salary.comp_off_days + 
                            monthly_salary.comp_off_used,
            'calculated_salary': f'{float(monthly_salary.final_salary) + float(monthly_salary.professional_tax):,.2f}',
        }
        
        html_string = render_to_string('salary_slip.html', context)
        return HttpResponse(html_string)
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)
