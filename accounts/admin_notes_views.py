from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .admin_notes_models import AdminNote
from .admin_notes_serializers import AdminNoteSerializer
from .models import MyUser

class AdminNoteViewSet(viewsets.ModelViewSet):
    queryset = AdminNote.objects.all()
    serializer_class = AdminNoteSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        # Only allow admin users
        if self.request.user.role == 'admin':
            return AdminNote.objects.all()
        return AdminNote.objects.none()
    
    def perform_create(self, serializer):
        if self.request.user.role != 'admin':
            raise PermissionError("Only admin users can create notes")
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['patch'])
    def toggle_complete(self, request, pk=None):
        note = self.get_object()
        note.is_completed = not note.is_completed
        note.save()
        return Response({'status': 'completed' if note.is_completed else 'pending'})
    
    @action(detail=False, methods=['get'])
    def by_priority(self, request):
        priority = request.query_params.get('priority', 'all')
        if priority != 'all':
            notes = self.queryset.filter(priority=priority)
        else:
            notes = self.queryset
        serializer = self.get_serializer(notes, many=True)
        return Response(serializer.data)