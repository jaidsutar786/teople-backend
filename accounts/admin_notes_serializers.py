from rest_framework import serializers
from .admin_notes_models import AdminNote

class AdminNoteSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = AdminNote
        fields = ['id', 'title', 'content', 'priority', 'created_by', 'created_by_name', 
                 'created_at', 'updated_at', 'is_completed']
        read_only_fields = ['created_by', 'created_at', 'updated_at']