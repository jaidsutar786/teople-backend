from rest_framework import serializers
from .leave_management_models import CompanyLeave, SaturdayOverride

class CompanyLeaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyLeave
        fields = ['id', 'date', 'reason', 'month', 'year', 'created_at']

class SaturdayOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaturdayOverride
        fields = ['id', 'date', 'status', 'month', 'year', 'created_at', 'updated_at']
