from django.contrib import admin
from .models import Customer, Invoice, InvoiceItem, Payment, Expense, SalaryExpense


class InvoiceItemInline(admin.TabularInline):
    model  = InvoiceItem
    extra  = 1


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display  = ['name', 'email', 'phone', 'company_name', 'currency', 'is_active']
    search_fields = ['name', 'email', 'company_name']
    list_filter   = ['is_active', 'currency']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display  = ['invoice_number', 'customer', 'invoice_date', 'due_date', 'grand_total', 'balance', 'status']
    list_filter   = ['status', 'currency']
    search_fields = ['invoice_number', 'customer__name']
    inlines       = [InvoiceItemInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display  = ['invoice', 'customer', 'payment_date', 'amount_received', 'payment_mode', 'reference_number']
    list_filter   = ['payment_mode', 'currency']
    search_fields = ['customer__name', 'invoice__invoice_number', 'reference_number']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display  = ['category', 'vendor_name', 'employee', 'expense_date', 'amount', 'total_amount', 'is_paid']
    list_filter   = ['category', 'is_paid', 'currency']
    search_fields = ['vendor_name', 'employee__first_name', 'category']


@admin.register(SalaryExpense)
class SalaryExpenseAdmin(admin.ModelAdmin):
    list_display  = ['employee', 'month', 'year', 'basic_salary', 'bonus', 'deductions', 'net_salary']
    list_filter   = ['year', 'month']
    search_fields = ['employee__first_name', 'employee__last_name']
