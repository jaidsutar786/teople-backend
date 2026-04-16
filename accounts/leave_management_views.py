from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .leave_management_models import CompanyLeave, SaturdayOverride
from .leave_management_serializers import CompanyLeaveSerializer, SaturdayOverrideSerializer

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def company_leaves(request):
    if request.method == 'GET':
        month = request.GET.get('month')
        year = request.GET.get('year')
        
        leaves = CompanyLeave.objects.filter(month=month, year=year)
        serializer = CompanyLeaveSerializer(leaves, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = CompanyLeaveSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_company_leave(request, date):
    try:
        leave = CompanyLeave.objects.get(date=date)
        leave.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except CompanyLeave.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def saturday_overrides(request):
    if request.method == 'GET':
        month = request.GET.get('month')
        year = request.GET.get('year')
        
        overrides = SaturdayOverride.objects.filter(month=month, year=year)
        result = {override.date.strftime('%Y-%m-%d'): override.status for override in overrides}
        return Response(result)
    
    elif request.method == 'POST':
        date = request.data.get('date')
        status_value = request.data.get('status')
        month = request.data.get('month')
        year = request.data.get('year')
        
        override, created = SaturdayOverride.objects.update_or_create(
            date=date,
            defaults={
                'status': status_value,
                'month': month,
                'year': year
            }
        )
        
        serializer = SaturdayOverrideSerializer(override)
        return Response(serializer.data)
