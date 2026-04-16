from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Q
from django.utils import timezone
from decimal import Decimal

from .models import Customer, Invoice, InvoiceItem, Payment, Expense, SalaryExpense
from .serializers import (
    CustomerSerializer, InvoiceSerializer, InvoiceWriteSerializer,
    InvoiceItemSerializer, PaymentSerializer, ExpenseSerializer,
    SalaryExpenseSerializer, EmployeeBasicSerializer, DashboardSerializer
)
from accounts.models import AddEmployee


class CustomerViewSet(viewsets.ModelViewSet):
    queryset           = Customer.objects.filter(is_active=True)
    serializer_class   = CustomerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [filters.SearchFilter]
    search_fields      = ['name', 'email', 'company_name', 'phone']


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset           = Invoice.objects.select_related('customer').prefetch_related('items', 'payments')
    permission_classes = [IsAuthenticated]
    filter_backends    = [filters.SearchFilter]
    search_fields      = ['invoice_number', 'customer__name', 'status']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return InvoiceWriteSerializer
        return InvoiceSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        qs     = super().get_queryset()
        status = self.request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    @action(detail=False, methods=['get'])
    def unpaid(self, request):
        """Return only invoices with balance > 0 (for payment dropdown)"""
        invoices = Invoice.objects.filter(
            balance__gt=0
        ).exclude(status='paid').select_related('customer')
        return Response(InvoiceSerializer(invoices, many=True).data)

    @action(detail=True, methods=['post'])
    def mark_overdue(self, request, pk=None):
        invoice = self.get_object()
        invoice.update_status()
        return Response(InvoiceSerializer(invoice).data)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset           = Payment.objects.select_related('customer', 'invoice')
    serializer_class   = PaymentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [filters.SearchFilter]
    search_fields      = ['customer__name', 'invoice__invoice_number', 'reference_number']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        qs         = super().get_queryset()
        invoice_id = self.request.query_params.get('invoice_id')
        customer_id = self.request.query_params.get('customer_id')
        if invoice_id:
            qs = qs.filter(invoice_id=invoice_id)
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        return qs


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset           = Expense.objects.select_related('employee')
    serializer_class   = ExpenseSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [filters.SearchFilter]
    search_fields      = ['category', 'vendor_name', 'employee__first_name']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        qs       = super().get_queryset()
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs


class SalaryExpenseViewSet(viewsets.ModelViewSet):
    queryset           = SalaryExpense.objects.select_related('employee')
    serializer_class   = SalaryExpenseSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def get_queryset(self):
        qs   = super().get_queryset()
        year = self.request.query_params.get('year')
        month = self.request.query_params.get('month')
        employee = self.request.query_params.get('employee')
        if year:
            qs = qs.filter(year=year)
        if month:
            qs = qs.filter(month=month)
        if employee:
            qs = qs.filter(employee_id=employee)
        return qs

    @action(detail=False, methods=['get'])
    def report(self, request):
        """Salary expense report with monthly/yearly totals"""
        year  = request.query_params.get('year', timezone.now().year)
        month = request.query_params.get('month', timezone.now().month)

        monthly = SalaryExpense.objects.filter(year=year, month=month)
        yearly  = SalaryExpense.objects.filter(year=year)

        monthly_total = monthly.aggregate(t=Sum('net_salary'))['t'] or Decimal('0')
        yearly_total  = yearly.aggregate(t=Sum('net_salary'))['t'] or Decimal('0')
        # All salary expenses are considered paid in accounting
        monthly_paid  = monthly_total
        yearly_paid   = yearly_total

        return Response({
            'records':       SalaryExpenseSerializer(monthly, many=True).data,
            'monthly_total': monthly_total,
            'yearly_total':  yearly_total,
            'monthly_paid':  monthly_paid,
            'yearly_paid':   yearly_paid,
        })


class EmployeeListView(viewsets.ReadOnlyModelViewSet):
    """For dropdowns in accounting forms"""
    queryset           = AddEmployee.objects.filter(user__is_active=True)
    serializer_class   = EmployeeBasicSerializer
    permission_classes = [IsAuthenticated]


class DashboardView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        total_invoices  = Invoice.objects.aggregate(t=Sum('grand_total'))['t'] or Decimal('0')
        total_payments  = Payment.objects.aggregate(t=Sum('amount_received'))['t'] or Decimal('0')
        total_pending   = Invoice.objects.filter(
            balance__gt=0
        ).aggregate(t=Sum('balance'))['t'] or Decimal('0')

        # Exclude salary category from expenses to avoid double counting
        total_expenses  = Expense.objects.exclude(category='salary').aggregate(t=Sum('total_amount'))['t'] or Decimal('0')
        total_salary    = SalaryExpense.objects.aggregate(t=Sum('net_salary'))['t'] or Decimal('0')
        net_profit      = total_payments - total_expenses - total_salary

        return Response({
            'total_invoices_amount':   total_invoices,
            'total_payments_received': total_payments,
            'total_pending_amount':    total_pending,
            'total_expenses':          total_expenses,
            'total_salary_expense':    total_salary,
            'net_profit':              net_profit,
        })
