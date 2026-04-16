from django.db import models
from django.conf import settings
from accounts.models import AddEmployee


# ─────────────────────────────────────────
# CUSTOMER
# ─────────────────────────────────────────
class Customer(models.Model):
    name         = models.CharField(max_length=200)
    email        = models.EmailField(blank=True, null=True)
    phone        = models.CharField(max_length=20, blank=True, null=True)
    company_name = models.CharField(max_length=200, blank=True, null=True)
    address      = models.TextField(blank=True, null=True)
    gst_number   = models.CharField(max_length=20, blank=True, null=True)
    currency     = models.CharField(max_length=10, default='INR')
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


# ─────────────────────────────────────────
# INVOICE
# ─────────────────────────────────────────
class Invoice(models.Model):
    STATUS_CHOICES = [
        ('draft',          'Draft'),
        ('sent',           'Sent'),
        ('partially_paid', 'Partially Paid'),
        ('paid',           'Paid'),
        ('overdue',        'Overdue'),
    ]

    customer             = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices')
    invoice_number       = models.CharField(max_length=50, unique=True)
    invoice_date         = models.DateField()
    due_date             = models.DateField()
    payment_expected_date = models.DateField(blank=True, null=True)
    status               = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    subtotal             = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_total            = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    grand_total          = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance              = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    currency             = models.CharField(max_length=10, default='INR')
    notes                = models.TextField(blank=True, null=True)

    created_by           = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_invoices'
    )
    created_at           = models.DateTimeField(auto_now_add=True)
    updated_at           = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.invoice_number} - {self.customer.name}"

    def recalculate_totals(self):
        """Recalculate subtotal, tax_total, grand_total from items."""
        items = self.items.all()
        self.subtotal   = sum(i.quantity * i.unit_price for i in items)
        self.tax_total  = sum((i.quantity * i.unit_price * i.tax_percent / 100) for i in items)
        self.grand_total = self.subtotal + self.tax_total
        self.balance     = self.grand_total - self.total_paid()
        self.save(update_fields=['subtotal', 'tax_total', 'grand_total', 'balance'])

    def total_paid(self):
        return sum(p.amount_received for p in self.payments.all())

    def update_status(self):
        from django.utils import timezone
        paid = self.total_paid()
        self.balance = self.grand_total - paid
        if self.balance <= 0:
            self.status = 'paid'
        elif paid > 0:
            self.status = 'partially_paid'
        elif self.due_date < timezone.now().date() and self.balance > 0:
            self.status = 'overdue'
        else:
            self.status = 'sent' if self.status not in ('draft',) else self.status
        self.save(update_fields=['balance', 'status'])

    class Meta:
        ordering = ['-invoice_date']


# ─────────────────────────────────────────
# INVOICE ITEM
# ─────────────────────────────────────────
class InvoiceItem(models.Model):
    invoice     = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    item_name   = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    quantity    = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price  = models.DecimalField(max_digits=14, decimal_places=2)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total       = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price * (1 + self.tax_percent / 100)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.item_name} ({self.invoice.invoice_number})"


# ─────────────────────────────────────────
# PAYMENT
# ─────────────────────────────────────────
class Payment(models.Model):
    PAYMENT_MODE_CHOICES = [
        ('cash',   'Cash'),
        ('bank',   'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('upi',    'UPI'),
    ]

    customer         = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='payments')
    invoice          = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    payment_date     = models.DateField()
    amount_received  = models.DecimalField(max_digits=14, decimal_places=2)
    payment_mode     = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    bank_charges     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency         = models.CharField(max_length=10, default='INR')
    exchange_rate    = models.DecimalField(max_digits=10, decimal_places=4, default=1.0)
    notes            = models.TextField(blank=True, null=True)

    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_payments'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Auto-update invoice status after payment
        self.invoice.update_status()

    def __str__(self):
        return f"Payment ₹{self.amount_received} for {self.invoice.invoice_number}"

    class Meta:
        ordering = ['-payment_date']


# ─────────────────────────────────────────
# EXPENSE
# ─────────────────────────────────────────
class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('rent',            'Rent'),
        ('utilities',       'Utilities'),
        ('office_supplies', 'Office Supplies'),
        ('salary',          'Salary'),
        ('marketing',       'Marketing'),
        ('travel',          'Travel'),
        ('other',           'Other'),
    ]

    vendor_name    = models.CharField(max_length=200, blank=True, null=True)
    employee       = models.ForeignKey(
        AddEmployee, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='expenses'
    )
    expense_date   = models.DateField()
    amount         = models.DecimalField(max_digits=14, decimal_places=2)
    category       = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    tax_percent    = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount     = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_amount   = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency       = models.CharField(max_length=10, default='INR')
    exchange_rate  = models.DecimalField(max_digits=10, decimal_places=4, default=1.0)
    receipt        = models.FileField(upload_to='expense_receipts/', blank=True, null=True)
    notes          = models.TextField(blank=True, null=True)
    is_paid        = models.BooleanField(default=True)

    # Link to salary record if category = salary
    salary_record  = models.ForeignKey(
        'SalaryExpense', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='expense_entries'
    )

    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_expenses'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.tax_amount  = self.amount * self.tax_percent / 100
        self.total_amount = self.amount + self.tax_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category} - ₹{self.total_amount} ({self.expense_date})"

    class Meta:
        ordering = ['-expense_date']


# ─────────────────────────────────────────
# SALARY EXPENSE (Accounting Module)
# ─────────────────────────────────────────
class SalaryExpense(models.Model):
    MONTH_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'),
        (4, 'April'),   (5, 'May'),      (6, 'June'),
        (7, 'July'),    (8, 'August'),   (9, 'September'),
        (10, 'October'),(11, 'November'),(12, 'December'),
    ]

    employee      = models.ForeignKey(AddEmployee, on_delete=models.PROTECT, related_name='salary_expenses')
    month         = models.IntegerField(choices=MONTH_CHOICES)
    year          = models.IntegerField()
    basic_salary  = models.DecimalField(max_digits=14, decimal_places=2)
    bonus         = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    deductions    = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    net_salary    = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_date  = models.DateField(blank=True, null=True)
    notes         = models.TextField(blank=True, null=True)

    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_salary_expenses'
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        from decimal import Decimal
        # Only auto-calculate if net_salary is not explicitly provided or is zero
        # This allows frontend to override with actual calculated salary (after deductions)
        if self.net_salary is None or self.net_salary == Decimal('0') or self.net_salary == 0:
            self.net_salary = self.basic_salary + self.bonus - self.deductions
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Auto-create or update Expense entry when salary is saved
        if is_new:
            Expense.objects.create(
                employee=self.employee,
                expense_date=self.payment_date or __import__('datetime').date.today(),
                amount=self.net_salary,
                category='salary',
                currency='INR',
                is_paid=True,  # Always paid in accounting
                notes=f"Salary for {self.get_month_display()} {self.year}",
                salary_record=self,
                created_by=self.created_by,
            )
        else:
            # Update existing linked Expense entries
            self.expense_entries.update(
                amount=self.net_salary,
                is_paid=True,  # Always paid in accounting
                notes=f"Salary for {self.get_month_display()} {self.year}"
            )

    def __str__(self):
        return f"{self.employee.first_name} - {self.get_month_display()} {self.year} - ₹{self.net_salary}"

    class Meta:
        unique_together = ('employee', 'month', 'year')
        ordering = ['-year', '-month']
