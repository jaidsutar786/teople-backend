from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import AddEmployee, MyUser

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def toggle_employee_status(request, employee_id):
    """Toggle employee active/inactive status"""
    if request.user.role != 'admin':
        return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        employee = AddEmployee.objects.get(id=employee_id)
        user = employee.user
        
        # Toggle is_active status
        user.is_active = request.data.get('is_active', not user.is_active)
        user.save()
        
        return Response({
            'message': f'Employee {"activated" if user.is_active else "deactivated"} successfully',
            'is_active': user.is_active
        })
        
    except AddEmployee.DoesNotExist:
        return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
