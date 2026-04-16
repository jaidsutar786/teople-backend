# Copy this code and paste at the VERY END of manage/accounts/views.py

# ==================== LEAVE MANAGEMENT VIEWS ====================
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def company_leaves(request):
    from .models import CompanyLeave
    if request.method == 'GET':
        month = request.GET.get('month')
        year = request.GET.get('year')
        leaves = CompanyLeave.objects.filter(month=month, year=year)
        data = [{'id': l.id, 'date': str(l.date), 'reason': l.reason, 'month': l.month, 'year': l.year} for l in leaves]
        return Response(data)
    elif request.method == 'POST':
        CompanyLeave.objects.create(**request.data)
        return Response({'message': 'Added'}, status=201)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_company_leave(request, date):
    from .models import CompanyLeave
    CompanyLeave.objects.filter(date=date).delete()
    return Response(status=204)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def saturday_overrides(request):
    from .models import SaturdayOverride
    if request.method == 'GET':
        month = request.GET.get('month')
        year = request.GET.get('year')
        overrides = SaturdayOverride.objects.filter(month=month, year=year)
        return Response({str(o.date): o.status for o in overrides})
    elif request.method == 'POST':
        override, _ = SaturdayOverride.objects.update_or_create(
            date=request.data['date'],
            defaults={'status': request.data['status'], 'month': request.data['month'], 'year': request.data['year']}
        )
        return Response({'date': str(override.date), 'status': override.status})
