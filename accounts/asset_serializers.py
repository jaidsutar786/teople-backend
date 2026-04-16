from rest_framework import serializers
from .asset_models import Asset, AssetAssignment
from .models import AddEmployee

class AssetSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = '__all__'

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}"
        return None


class AssetAssignmentSerializer(serializers.ModelSerializer):
    employee_name  = serializers.SerializerMethodField()
    asset_title    = serializers.CharField(source='asset.title', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.username', read_only=True)

    class Meta:
        model = AssetAssignment
        fields = '__all__'
        read_only_fields = ['assigned_by']

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"