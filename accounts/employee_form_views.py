from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .models import AddEmployee
from .employee_form_models import EmployeePersonalInfo, EmployeeDocument
from .employee_form_serializers import (
    EmployeePersonalInfoSerializer, 
    EmployeeDocumentSerializer,
    EmployeeFormSubmitSerializer
)
import os
import cloudinary.uploader


def upload_to_cloudinary(file, folder, public_id):
    """Upload file to Cloudinary if configured, else save locally"""
    if os.environ.get('CLOUDINARY_URL'):
        # PDF/raw files ke liye resource_type='raw', images ke liye 'image'
        ext = os.path.splitext(file.name)[1].lower()
        resource_type = 'raw' if ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx'] else 'image'
        result = cloudinary.uploader.upload(
            file,
            folder=folder,
            public_id=public_id,
            overwrite=True,
            resource_type=resource_type,
        )
        return result['secure_url']
    else:
        from django.conf import settings
        upload_dir = os.path.join(settings.MEDIA_ROOT, folder)
        os.makedirs(upload_dir, exist_ok=True)
        ext = os.path.splitext(file.name)[1] or '.pdf'
        file_path = os.path.join(upload_dir, f'{public_id}{ext}')
        with open(file_path, 'wb') as f_out:
            for chunk in file.chunks():
                f_out.write(chunk)
        return f'{settings.MEDIA_URL}{folder}/{public_id}{ext}'

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_employee_form(request):
    """Submit complete employee form with documents"""
    try:
        with transaction.atomic():
            employee = AddEmployee.objects.get(user=request.user)
            
            # Check for duplicate email in the system
            email = request.data.get('personal_email', '').strip().lower()
            if email:
                existing_info = EmployeePersonalInfo.objects.filter(
                    personal_email=email
                ).exclude(employee=employee).first()
                
                if existing_info:
                    return Response({
                        'personal_email': ['This email is already registered with another employee']
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check for duplicate contact number
            contact_num = request.data.get('contact_number', '').strip()
            if contact_num:
                existing_info = EmployeePersonalInfo.objects.filter(
                    contact_number=contact_num
                ).exclude(employee=employee).first()
                
                if existing_info:
                    return Response({
                        'contact_number': ['This contact number is already registered with another employee']
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate form data
            serializer = EmployeeFormSubmitSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # Create or update personal info
            personal_info, created = EmployeePersonalInfo.objects.update_or_create(
                employee=employee,
                defaults=serializer.validated_data
            )
            
            # Handle document uploads
            documents, doc_created = EmployeeDocument.objects.get_or_create(employee=employee)
            emp_id = employee.id
            
            doc_fields = [
                ('aadhar_pdf', 'employee_docs/aadhar'),
                ('pan_pdf', 'employee_docs/pan'),
                ('passport_pdf', 'employee_docs/passport'),
                ('tenth_marksheet', 'employee_docs/education'),
                ('twelfth_marksheet', 'employee_docs/education'),
                ('highest_qualification_doc', 'employee_docs/education'),
                ('additional_certifications', 'employee_docs/certifications'),
                ('skill_certificates', 'employee_docs/skills'),
                ('company1_offer_letter', 'employee_docs/company1'),
                ('company1_experience_letter', 'employee_docs/company1'),
                ('company1_salary_slips', 'employee_docs/company1'),
                ('company2_offer_letter', 'employee_docs/company2'),
                ('company2_experience_letter', 'employee_docs/company2'),
                ('company2_salary_slips', 'employee_docs/company2'),
                ('bank_document', 'employee_docs/bank'),
            ]
            
            for field_name, folder in doc_fields:
                if field_name in request.FILES:
                    url = upload_to_cloudinary(
                        request.FILES[field_name],
                        folder,
                        f'{emp_id}_{field_name}'
                    )
                    setattr(documents, field_name, url)
            
            documents.save()
            
            return Response({
                'message': 'Employee form submitted successfully',
                'personal_info': EmployeePersonalInfoSerializer(personal_info).data,
                'documents': EmployeeDocumentSerializer(documents, context={'request': request}).data
            }, status=status.HTTP_201_CREATED)
            
    except AddEmployee.DoesNotExist:
        return Response({'error': 'Employee profile not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_employee_form_data(request):
    """Get employee form data"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        
        try:
            personal_info = EmployeePersonalInfo.objects.get(employee=employee)
            personal_data = EmployeePersonalInfoSerializer(personal_info).data
        except EmployeePersonalInfo.DoesNotExist:
            personal_data = None
        
        try:
            documents = EmployeeDocument.objects.get(employee=employee)
            documents_data = EmployeeDocumentSerializer(documents, context={'request': request}).data
        except EmployeeDocument.DoesNotExist:
            documents_data = None
        
        profile_pic_url = None
        if employee.profile_picture:
            profile_pic_url = employee.profile_picture
        
        return Response({
            'employee': {
                'id': employee.id,
                'first_name': employee.first_name,
                'last_name': employee.last_name,
                'email': employee.user.email,
                'profile_picture': profile_pic_url
            },
            'personal_info': personal_data,
            'documents': documents_data,
            'revision_requested': personal_data.get('revision_requested', False) if personal_data else False,
            'revision_message': personal_data.get('revision_message', '') if personal_data else '',
            'incomplete_fields': personal_data.get('incomplete_fields', []) if personal_data else []
        })
        
    except AddEmployee.DoesNotExist:
        return Response({'error': 'Employee profile not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_employee_form(request):
    """Update employee form data"""
    try:
        with transaction.atomic():
            employee = AddEmployee.objects.get(user=request.user)
            
            serializer = EmployeeFormSubmitSerializer(data=request.data, partial=True)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            # Update personal info
            personal_info = EmployeePersonalInfo.objects.get(employee=employee)
            for key, value in serializer.validated_data.items():
                setattr(personal_info, key, value)
            personal_info.save()
            
            # Update documents if provided
            if request.FILES:
                documents = EmployeeDocument.objects.get(employee=employee)
                emp_id = employee.id
                for field_name in request.FILES.keys():
                    if hasattr(documents, field_name):
                        url = upload_to_cloudinary(
                            request.FILES[field_name],
                            f'employee_docs/{field_name}',
                            f'{emp_id}_{field_name}'
                        )
                        setattr(documents, field_name, url)
                documents.save()
            
            return Response({
                'message': 'Employee form updated successfully',
                'personal_info': EmployeePersonalInfoSerializer(personal_info).data
            })
            
    except (AddEmployee.DoesNotExist, EmployeePersonalInfo.DoesNotExist):
        return Response({'error': 'Employee data not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_employee_forms(request):
    """Admin: Get all employees"""
    if request.user.role != 'admin':
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        employees = AddEmployee.objects.select_related('user').all()
        data = []
        
        for emp in employees:
            try:
                personal_info = EmployeePersonalInfo.objects.get(employee=emp)
                personal_data = EmployeePersonalInfoSerializer(personal_info).data
            except EmployeePersonalInfo.DoesNotExist:
                personal_data = None
            
            try:
                documents = EmployeeDocument.objects.get(employee=emp)
                documents_data = EmployeeDocumentSerializer(documents, context={'request': request}).data
            except EmployeeDocument.DoesNotExist:
                documents_data = None
            
            profile_pic_url = None
            if emp.profile_picture:
                profile_pic_url = emp.profile_picture
            
            data.append({
                'employee': {
                    'id': emp.id,
                    'employee_id': emp.employee_id,
                    'first_name': emp.first_name,
                    'last_name': emp.last_name,
                    'email': emp.user.email,
                    'department': emp.department,
                    'position': emp.position,
                    'is_active': emp.user.is_active,
                    'profile_picture': profile_pic_url
                },
                'personal_info': personal_data,
                'documents': documents_data
            })
        
        return Response(data)
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_employee_document(request, document_type):
    """Delete a specific employee document"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        documents = EmployeeDocument.objects.get(employee=employee)
        
        if hasattr(documents, document_type):
            file_field = getattr(documents, document_type)
            if file_field:
                file_field.delete()
                setattr(documents, document_type, None)
                documents.save()
                return Response({'message': f'{document_type} deleted successfully'})
            else:
                return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'error': 'Invalid document type'}, status=status.HTTP_400_BAD_REQUEST)
            
    except (AddEmployee.DoesNotExist, EmployeeDocument.DoesNotExist):
        return Response({'error': 'Employee or documents not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_form_revision(request, employee_id):
    """Admin: Request employee to revise form"""
    if request.user.role != 'admin':
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        employee = AddEmployee.objects.get(id=employee_id)
        personal_info, created = EmployeePersonalInfo.objects.get_or_create(employee=employee)
        
        incomplete_fields = request.data.get('incomplete_fields', [])
        message = request.data.get('message', 'Please complete your profile information.')
        
        personal_info.revision_requested = True
        personal_info.revision_message = message
        personal_info.incomplete_fields = incomplete_fields
        personal_info.save()
        
        # Create notification
        from .models import FormRevisionNotification
        FormRevisionNotification.objects.create(
            employee=employee,
            message=message,
            incomplete_fields=incomplete_fields
        )
        
        return Response({
            'message': 'Revision request sent successfully',
            'incomplete_fields': incomplete_fields
        })
        
    except AddEmployee.DoesNotExist:
        return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_revision_request(request):
    """Employee: Clear revision request after updating form"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        personal_info = EmployeePersonalInfo.objects.get(employee=employee)
        
        personal_info.revision_requested = False
        personal_info.revision_message = ''
        personal_info.incomplete_fields = []
        personal_info.save()
        
        # Clear all revision notifications
        from .models import FormRevisionNotification
        FormRevisionNotification.objects.filter(employee=employee).delete()
        
        return Response({'message': 'Revision request cleared'})
        
    except (AddEmployee.DoesNotExist, EmployeePersonalInfo.DoesNotExist):
        return Response({'error': 'Employee data not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
