from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .asset_models import Asset, AssetAssignment
from .asset_serializers import AssetSerializer, AssetAssignmentSerializer
from .models import AddEmployee

class AssetViewSet(viewsets.ModelViewSet):
    queryset = Asset.objects.all()
    serializer_class = AssetSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role == 'admin':
            queryset = Asset.objects.all()
            assigned_to = self.request.query_params.get('assigned_to', None)
            if assigned_to:
                queryset = queryset.filter(assigned_to=assigned_to)
            return queryset
        return Asset.objects.none()
    
    @action(detail=True, methods=['post'])
    def assign_to_employee(self, request, pk=None):
        asset = self.get_object()
        employee_id = request.data.get('employee_id')
        assigned_date = request.data.get('assigned_date')
        condition = request.data.get('condition', 'Good')
        notes = request.data.get('notes', '')
        
        try:
            employee = AddEmployee.objects.get(id=employee_id)
            
            # Update asset
            asset.assigned_to = employee
            asset.assigned_date = assigned_date
            asset.status = 'Assigned'
            asset.save()
            
            # Create assignment record
            AssetAssignment.objects.create(
                asset=asset,
                employee=employee,
                assigned_by=request.user,
                assigned_date=assigned_date,
                condition_on_assignment=condition,
                notes=notes
            )
            
            return Response({'message': 'Asset assigned successfully'})
        except AddEmployee.DoesNotExist:
            return Response({'error': 'Employee not found'}, status=400)
    
    @action(detail=True, methods=['post'])
    def return_asset(self, request, pk=None):
        asset = self.get_object()
        return_date = request.data.get('return_date')
        condition = request.data.get('condition', 'Good')
        notes = request.data.get('notes', '')
        
        # Update asset
        asset.assigned_to = None
        asset.return_date = return_date
        asset.status = 'Available'
        asset.save()
        
        # Update assignment record
        assignment = AssetAssignment.objects.filter(
            asset=asset, is_active=True
        ).first()
        if assignment:
            assignment.return_date = return_date
            assignment.condition_on_return = condition
            assignment.notes = notes
            assignment.is_active = False
            assignment.save()
        
        return Response({'message': 'Asset returned successfully'})

class AssetAssignmentViewSet(viewsets.ModelViewSet):
    queryset = AssetAssignment.objects.all()
    serializer_class = AssetAssignmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role == 'admin':
            return AssetAssignment.objects.all()
        return AssetAssignment.objects.none()
    
    def perform_create(self, serializer):
        serializer.save(assigned_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def by_employee(self, request):
        employee_id = request.query_params.get('employee_id')
        if employee_id:
            assignments = self.queryset.filter(employee_id=employee_id)
            serializer = self.get_serializer(assignments, many=True)
            return Response(serializer.data)
        return Response({'error': 'Employee ID required'}, status=400)