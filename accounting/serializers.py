from rest_framework import serializers
from .models import Customer, Invoice, InvoiceItem, Payment, Expense, SalaryExpense
from accounts.models import AddEmployee


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Customer
        fields = '__all__'


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = InvoiceItem
        fields = '__all__'
        read_only_fields = ['total', 'invoice']


class InvoiceSerializer(serializers.ModelSerializer):
    items           = InvoiceItemSerializer(many=True, read_only=True)
    customer_name   = serializers.CharField(source='customer.name', read_only=True)
    total_paid      = serializers.SerializerMethodField()

    class Meta:
        model  = Invoice
        fields = '__all__'
        read_only_fields = ['subtotal', 'tax_total', 'grand_total', 'balance', 'invoice_number']

    def get_total_paid(self, obj):
        return obj.total_paid()


class InvoiceWriteSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True)

    class Meta:
        model  = Invoice
        fields = '__all__'
        read_only_fields = ['subtotal', 'tax_total', 'grand_total', 'balance', 'invoice_number']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        # Auto-generate invoice number
        last = Invoice.objects.order_by('-id').first()
        next_num = (last.id + 1) if last else 1
        validated_data['invoice_number'] = f"INV-{next_num:04d}"
        invoice = Invoice.objects.create(**validated_data)
        for item_data in items_data:
            InvoiceItem.objects.create(invoice=invoice, **item_data)
        invoice.recalculate_totals()
        return invoice

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                InvoiceItem.objects.create(invoice=instance, **item_data)
        instance.recalculate_totals()
        instance.update_status()  # recalculate balance & status after items change
        return instance


class PaymentSerializer(serializers.ModelSerializer):
    customer_name    = serializers.CharField(source='customer.name', read_only=True)
    invoice_number   = serializers.CharField(source='invoice.invoice_number', read_only=True)
    invoice_balance  = serializers.DecimalField(source='invoice.balance', max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model  = Payment
        fields = '__all__'

    def validate(self, data):
        invoice = data.get('invoice')
        amount  = data.get('amount_received', 0)
        if invoice and amount > invoice.balance:
            raise serializers.ValidationError(
                f"Amount ₹{amount} exceeds invoice balance ₹{invoice.balance}"
            )
        return data


class ExpenseSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model  = Expense
        fields = '__all__'
        read_only_fields = ['tax_amount', 'total_amount']

    def get_employee_name(self, obj):
        if obj.employee:
            return f"{obj.employee.first_name} {obj.employee.last_name}"
        return obj.vendor_name or '-'


class SalaryExpenseSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    month_display = serializers.CharField(source='get_month_display', read_only=True)
    basic_salary_auto = serializers.SerializerMethodField()

    class Meta:
        model  = SalaryExpense
        fields = '__all__'
        # Allow frontend to set net_salary

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"

    def get_basic_salary_auto(self, obj):
        """Return basic salary from employee's Salary model"""
        try:
            salary = obj.employee.salary
            return float(salary.gross_annual_salary / 12)
        except Exception:
            return None
    
    def validate_net_salary(self, value):
        """Ensure net_salary is properly converted to Decimal"""
        if value is not None:
            from decimal import Decimal
            return Decimal(str(value))
        return value


class EmployeeBasicSerializer(serializers.ModelSerializer):
    full_name    = serializers.SerializerMethodField()
    basic_salary = serializers.SerializerMethodField()

    class Meta:
        model  = AddEmployee
        fields = ['id', 'employee_id', 'full_name', 'basic_salary', 'position']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_basic_salary(self, obj):
        try:
            return float(obj.salary.gross_annual_salary / 12)
        except Exception:
            return 0


class DashboardSerializer(serializers.Serializer):
    total_invoices_amount  = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_payments_received = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_pending_amount   = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_expenses         = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_salary_expense   = serializers.DecimalField(max_digits=14, decimal_places=2)
    net_profit             = serializers.DecimalField(max_digits=14, decimal_places=2)
