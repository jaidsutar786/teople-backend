from django.db import models
from .models import AddEmployee

class EmployeeDocument(models.Model):
    """Model to store employee documents"""
    employee = models.ForeignKey(AddEmployee, on_delete=models.CASCADE, related_name='documents')
    
    # Personal Documents
    aadhar_pdf = models.CharField(max_length=500, blank=True, null=True)
    pan_pdf = models.CharField(max_length=500, blank=True, null=True)
    passport_pdf = models.CharField(max_length=500, blank=True, null=True)
    
    # Educational Documents
    tenth_marksheet = models.CharField(max_length=500, blank=True, null=True)
    twelfth_marksheet = models.CharField(max_length=500, blank=True, null=True)
    highest_qualification_doc = models.CharField(max_length=500, blank=True, null=True)
    additional_certifications = models.CharField(max_length=500, blank=True, null=True)
    skill_certificates = models.CharField(max_length=500, blank=True, null=True)
    
    # Employment Documents
    company1_offer_letter = models.CharField(max_length=500, blank=True, null=True)
    company1_experience_letter = models.CharField(max_length=500, blank=True, null=True)
    company1_salary_slips = models.CharField(max_length=500, blank=True, null=True)
    
    company2_offer_letter = models.CharField(max_length=500, blank=True, null=True)
    company2_experience_letter = models.CharField(max_length=500, blank=True, null=True)
    company2_salary_slips = models.CharField(max_length=500, blank=True, null=True)
    
    # Bank Documents
    bank_document = models.CharField(max_length=500, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Documents - {self.employee.first_name} {self.employee.last_name}"


class EmployeePersonalInfo(models.Model):
    """Extended personal information for employee"""
    employee = models.OneToOneField(AddEmployee, on_delete=models.CASCADE, related_name='personal_info')
    
    # Revision tracking
    revision_requested = models.BooleanField(default=False)
    revision_message = models.TextField(blank=True)
    incomplete_fields = models.JSONField(default=list, blank=True)
    
    # Personal Information
    first_name = models.CharField(max_length=100, default='')
    middle_name = models.CharField(max_length=100, blank=True, default='')
    last_name = models.CharField(max_length=100, default='')
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True)
    marital_status = models.CharField(max_length=20, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    parent_name = models.CharField(max_length=200, blank=True)
    contact_number = models.CharField(max_length=20)
    alternate_number = models.CharField(max_length=20, blank=True)
    personal_email = models.EmailField()
    permanent_address = models.TextField(blank=True)
    current_address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_number = models.CharField(max_length=20, blank=True)
    blood_group = models.CharField(max_length=10, blank=True)
    
    # Document Details
    aadhar_number = models.CharField(max_length=20, blank=True)
    pan_number = models.CharField(max_length=20, blank=True)
    passport_number = models.CharField(max_length=20, blank=True)
    
    # Educational Qualifications
    tenth_marks = models.CharField(max_length=20, blank=True)
    tenth_year = models.CharField(max_length=10, blank=True)
    twelfth_marks = models.CharField(max_length=20, blank=True)
    twelfth_year = models.CharField(max_length=10, blank=True)
    highest_qualification = models.CharField(max_length=100, blank=True)
    highest_qualification_marks = models.CharField(max_length=20, blank=True)
    highest_qualification_year = models.CharField(max_length=10, blank=True)
    university_name = models.CharField(max_length=200, blank=True)
    
    # Employment Details
    company1_name = models.CharField(max_length=200, blank=True)
    company1_experience = models.CharField(max_length=50, blank=True)
    company1_from_date = models.DateField(blank=True, null=True)
    company1_to_date = models.DateField(blank=True, null=True)
    
    company2_name = models.CharField(max_length=200, blank=True)
    company2_experience = models.CharField(max_length=50, blank=True)
    company2_from_date = models.DateField(blank=True, null=True)
    company2_to_date = models.DateField(blank=True, null=True)
    
    # Bank Details
    bank_name = models.CharField(max_length=200, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    account_holder_name = models.CharField(max_length=200, blank=True)
    pan_number_bank = models.CharField(max_length=20, blank=True)
    uan_number = models.CharField(max_length=50, blank=True)
    esic_number = models.CharField(max_length=50, blank=True)
    tax_regime = models.CharField(max_length=20, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Personal Info - {self.first_name} {self.last_name}"
