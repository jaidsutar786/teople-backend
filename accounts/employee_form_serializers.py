from rest_framework import serializers
from .employee_form_models import EmployeePersonalInfo, EmployeeDocument
import re
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

class EmployeeDocumentSerializer(serializers.ModelSerializer):
    # Personal Documents URLs
    aadhar_pdf = serializers.SerializerMethodField()
    pan_pdf = serializers.SerializerMethodField()
    passport_pdf = serializers.SerializerMethodField()
    
    # Educational Documents URLs
    tenth_marksheet = serializers.SerializerMethodField()
    twelfth_marksheet = serializers.SerializerMethodField()
    highest_qualification_doc = serializers.SerializerMethodField()
    additional_certifications = serializers.SerializerMethodField()
    skill_certificates = serializers.SerializerMethodField()
    
    # Employment Documents URLs - Company 1
    company1_offer_letter = serializers.SerializerMethodField()
    company1_experience_letter = serializers.SerializerMethodField()
    company1_salary_slips = serializers.SerializerMethodField()
    
    # Employment Documents URLs - Company 2
    company2_offer_letter = serializers.SerializerMethodField()
    company2_experience_letter = serializers.SerializerMethodField()
    company2_salary_slips = serializers.SerializerMethodField()
    
    # Bank Documents URLs
    bank_document = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployeeDocument
        fields = [
            'id', 'employee', 'aadhar_pdf', 'pan_pdf', 'passport_pdf',
            'tenth_marksheet', 'twelfth_marksheet', 'highest_qualification_doc',
            'additional_certifications', 'skill_certificates',
            'company1_offer_letter', 'company1_experience_letter', 'company1_salary_slips',
            'company2_offer_letter', 'company2_experience_letter', 'company2_salary_slips',
            'bank_document', 'created_at', 'updated_at'
        ]
    
    def _get_file_url(self, obj, field_name):
        file_field = getattr(obj, field_name, None)
        if file_field:
            return self.context['request'].build_absolute_uri(file_field.url) if 'request' in self.context else file_field.url
        return None
    
    def get_aadhar_pdf(self, obj):
        return self._get_file_url(obj, 'aadhar_pdf')
    
    def get_pan_pdf(self, obj):
        return self._get_file_url(obj, 'pan_pdf')
    
    def get_passport_pdf(self, obj):
        return self._get_file_url(obj, 'passport_pdf')
    
    def get_tenth_marksheet(self, obj):
        return self._get_file_url(obj, 'tenth_marksheet')
    
    def get_twelfth_marksheet(self, obj):
        return self._get_file_url(obj, 'twelfth_marksheet')
    
    def get_highest_qualification_doc(self, obj):
        return self._get_file_url(obj, 'highest_qualification_doc')
    
    def get_additional_certifications(self, obj):
        return self._get_file_url(obj, 'additional_certifications')
    
    def get_skill_certificates(self, obj):
        return self._get_file_url(obj, 'skill_certificates')
    
    def get_company1_offer_letter(self, obj):
        return self._get_file_url(obj, 'company1_offer_letter')
    
    def get_company1_experience_letter(self, obj):
        return self._get_file_url(obj, 'company1_experience_letter')
    
    def get_company1_salary_slips(self, obj):
        return self._get_file_url(obj, 'company1_salary_slips')
    
    def get_company2_offer_letter(self, obj):
        return self._get_file_url(obj, 'company2_offer_letter')
    
    def get_company2_experience_letter(self, obj):
        return self._get_file_url(obj, 'company2_experience_letter')
    
    def get_company2_salary_slips(self, obj):
        return self._get_file_url(obj, 'company2_salary_slips')
    
    def get_bank_document(self, obj):
        return self._get_file_url(obj, 'bank_document')


class EmployeePersonalInfoSerializer(serializers.ModelSerializer):
    documents = EmployeeDocumentSerializer(source='employee.documents', many=True, read_only=True)
    
    class Meta:
        model = EmployeePersonalInfo
        fields = '__all__'


class EmployeeFormSubmitSerializer(serializers.Serializer):
    """Serializer for complete employee form submission"""
    # Personal Information
    first_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=100)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.CharField(required=False, allow_blank=True)
    marital_status = serializers.CharField(required=False, allow_blank=True)
    nationality = serializers.CharField(required=False, allow_blank=True)
    parent_name = serializers.CharField(required=False, allow_blank=True)
    contact_number = serializers.CharField(max_length=20)
    alternate_number = serializers.CharField(required=False, allow_blank=True)
    personal_email = serializers.EmailField()
    permanent_address = serializers.CharField(required=False, allow_blank=True)
    current_address = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_name = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_number = serializers.CharField(required=False, allow_blank=True)
    blood_group = serializers.CharField(required=False, allow_blank=True)
    
    def validate_first_name(self, value):
        """Validate first name"""
        if not value or not value.strip():
            raise serializers.ValidationError("First name is required")
        
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("First name must be at least 2 characters long")
        
        if not re.match(r'^[a-zA-Z\s]+$', value):
            raise serializers.ValidationError("First name can only contain letters and spaces")
        
        return value
    
    def validate_last_name(self, value):
        """Validate last name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Last name is required")
        
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Last name must be at least 2 characters long")
        
        if not re.match(r'^[a-zA-Z\s]+$', value):
            raise serializers.ValidationError("Last name can only contain letters and spaces")
        
        return value
    
    def validate_contact_number(self, value):
        """Validate contact number"""
        if not value or not value.strip():
            raise serializers.ValidationError("Contact number is required")
        
        value = value.strip()
        
        # Check if it's a valid 10-digit Indian mobile number
        if not re.match(r'^[6-9]\d{9}$', value):
            raise serializers.ValidationError("Please enter a valid 10-digit mobile number starting with 6, 7, 8, or 9")
        
        return value
    
    def validate_alternate_number(self, value):
        """Validate alternate number"""
        if value and value.strip():
            value = value.strip()
            if not re.match(r'^[6-9]\d{9}$', value):
                raise serializers.ValidationError("Please enter a valid 10-digit mobile number starting with 6, 7, 8, or 9")
        
        return value
    
    def validate_personal_email(self, value):
        """Validate personal email"""
        if not value or not value.strip():
            raise serializers.ValidationError("Personal email is required")
        
        value = value.strip().lower()
        
        try:
            validate_email(value)
        except ValidationError:
            raise serializers.ValidationError("Please enter a valid email address")
        
        return value
    
    def validate_aadhar_number(self, value):
        """Validate Aadhar number"""
        if value and value.strip():
            value = value.strip()
            if not re.match(r'^\d{12}$', value):
                raise serializers.ValidationError("Aadhar number must be exactly 12 digits")
        
        return value
    
    def validate_pan_number(self, value):
        """Validate PAN number"""
        if value and value.strip():
            value = value.strip().upper()
            if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', value):
                raise serializers.ValidationError("Please enter a valid PAN number (e.g., ABCDE1234F)")
        
        return value
    
    def validate_ifsc_code(self, value):
        """Validate IFSC code"""
        if value and value.strip():
            value = value.strip().upper()
            if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', value):
                raise serializers.ValidationError("Please enter a valid IFSC code (e.g., SBIN0001234)")
        
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        # Check if contact number and alternate number are the same
        contact_num = data.get('contact_number', '').strip()
        alternate_num = data.get('alternate_number', '').strip()
        
        if contact_num and alternate_num and contact_num == alternate_num:
            raise serializers.ValidationError({
                'alternate_number': 'Alternate number cannot be the same as contact number'
            })
        
        # Validate emergency contact number if provided
        emergency_num = data.get('emergency_contact_number', '').strip()
        if emergency_num and not re.match(r'^[6-9]\d{9}$', emergency_num):
            raise serializers.ValidationError({
                'emergency_contact_number': 'Please enter a valid 10-digit mobile number'
            })
        
        return data
    
    # Document Details
    aadhar_number = serializers.CharField(required=False, allow_blank=True)
    pan_number = serializers.CharField(required=False, allow_blank=True)
    passport_number = serializers.CharField(required=False, allow_blank=True)
    
    # Educational Qualifications
    tenth_marks = serializers.CharField(required=False, allow_blank=True)
    tenth_year = serializers.CharField(required=False, allow_blank=True)
    twelfth_marks = serializers.CharField(required=False, allow_blank=True)
    twelfth_year = serializers.CharField(required=False, allow_blank=True)
    highest_qualification = serializers.CharField(required=False, allow_blank=True)
    highest_qualification_marks = serializers.CharField(required=False, allow_blank=True)
    highest_qualification_year = serializers.CharField(required=False, allow_blank=True)
    university_name = serializers.CharField(required=False, allow_blank=True)
    
    # Employment Details
    company1_name = serializers.CharField(required=False, allow_blank=True)
    company1_experience = serializers.CharField(required=False, allow_blank=True)
    company1_from_date = serializers.DateField(required=False, allow_null=True)
    company1_to_date = serializers.DateField(required=False, allow_null=True)
    company2_name = serializers.CharField(required=False, allow_blank=True)
    company2_experience = serializers.CharField(required=False, allow_blank=True)
    company2_from_date = serializers.DateField(required=False, allow_null=True)
    company2_to_date = serializers.DateField(required=False, allow_null=True)
    
    # Bank Details
    bank_name = serializers.CharField(required=False, allow_blank=True)
    account_number = serializers.CharField(required=False, allow_blank=True)
    ifsc_code = serializers.CharField(required=False, allow_blank=True)
    account_holder_name = serializers.CharField(required=False, allow_blank=True)
    pan_number_bank = serializers.CharField(required=False, allow_blank=True)
    uan_number = serializers.CharField(required=False, allow_blank=True)
    esic_number = serializers.CharField(required=False, allow_blank=True)
    tax_regime = serializers.CharField(required=False, allow_blank=True)
