from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import AddEmployee
import cloudinary.uploader
import os

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_profile_picture(request):
    """Upload profile picture"""
    try:
        employee = AddEmployee.objects.get(user=request.user)
        
        if 'profile_picture' not in request.FILES:
            return Response({'error': 'No image provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['profile_picture']
        
        # Upload to Cloudinary if configured, else local
        if os.environ.get('CLOUDINARY_URL'):
            upload_result = cloudinary.uploader.upload(
                file,
                folder='profile_pictures',
                public_id=f'profile_{employee.id}',
                overwrite=True
            )
            profile_url = upload_result['secure_url']
            employee.profile_picture = profile_url
        else:
            employee.profile_picture = file
            profile_url = request.build_absolute_uri(employee.profile_picture.url)
        
        employee.save()
        
        return Response({
            'message': 'Profile picture uploaded successfully',
            'profile_picture': profile_url
        })
        
    except AddEmployee.DoesNotExist:
        return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
