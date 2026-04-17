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
        if os.environ.get('CLOUDINARY_URL') and (os.environ.get('RENDER') or os.environ.get('IS_PRODUCTION')):
            upload_result = cloudinary.uploader.upload(
                file,
                folder='profile_pictures',
                public_id=f'profile_{employee.id}',
                overwrite=True,
                access_mode='public',
                type='upload'
            )
            profile_url = upload_result['secure_url']
        else:
            import os as _os
            from django.conf import settings
            upload_dir = _os.path.join(settings.MEDIA_ROOT, 'profile_pictures')
            _os.makedirs(upload_dir, exist_ok=True)
            file_path = _os.path.join(upload_dir, f'profile_{employee.id}.jpg')
            with open(file_path, 'wb') as f_out:
                for chunk in file.chunks():
                    f_out.write(chunk)
            profile_url = f'http://127.0.0.1:8000{settings.MEDIA_URL}profile_pictures/profile_{employee.id}.jpg'
        
        employee.profile_picture = profile_url
        
        employee.save()
        
        return Response({
            'message': 'Profile picture uploaded successfully',
            'profile_picture': profile_url
        })
        
    except AddEmployee.DoesNotExist:
        return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
