from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import AddEmployee

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_profile_picture(request):
    """Upload profile picture"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        
        if 'profile_picture' not in request.FILES:
            return Response({'error': 'No image provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        employee.profile_picture = request.FILES['profile_picture']
        employee.save()
        
        profile_pic_url = request.build_absolute_uri(employee.profile_picture.url)
        
        return Response({
            'message': 'Profile picture uploaded successfully',
            'profile_picture': profile_pic_url
        })
        
    except AddEmployee.DoesNotExist:
        return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
