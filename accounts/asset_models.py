from django.db import models
from django.conf import settings
from .models import AddEmployee

class Asset(models.Model):
    ASSET_TYPES = [
        ('laptop', 'Laptop'),
        ('monitor', 'Monitor'),
        ('keyboard', 'Keyboard'),
        ('mouse', 'Mouse'),
        ('pendrive', 'Pendrive'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('Stock', 'Stock'),
        ('In Use', 'In Use'),
        ('Under Repair', 'Under Repair'),
        ('Retired', 'Retired'),
        ('Assigned', 'Assigned'),
        ('Submitted', 'Submitted'),
        ('Returned', 'Returned'),
    ]

    CONDITION_CHOICES = [
        ('New', 'New'),
        ('Good', 'Good'),
        ('Fair', 'Fair'),
        ('Poor', 'Poor'),
        ('Damaged', 'Damaged'),
    ]

    DOMAIN_CHOICES = [
        ('Yes', 'Yes'),
        ('No', 'No'),
        ('NA', 'NA'),
    ]

    title        = models.CharField(max_length=200)
    asset_type   = models.CharField(max_length=20, choices=ASSET_TYPES)
    description  = models.TextField(blank=True, null=True)
    given_date   = models.DateField(null=True, blank=True)
    status       = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Stock')
    assigned_to  = models.ForeignKey(AddEmployee, on_delete=models.SET_NULL, null=True, blank=True)
    submitted_date = models.DateField(null=True, blank=True)
    submit_notes = models.TextField(blank=True, null=True)

    # Common fields
    serial_number    = models.CharField(max_length=100, blank=True, null=True)
    company_name     = models.CharField(max_length=100, blank=True, null=True)
    model_name       = models.CharField(max_length=100, blank=True, null=True)
    asset_condition  = models.CharField(max_length=50, choices=CONDITION_CHOICES, blank=True, null=True)
    purchase_date    = models.DateField(null=True, blank=True)
    warranty_expiry  = models.DateField(null=True, blank=True)
    in_date          = models.DateField(null=True, blank=True)
    remark           = models.TextField(blank=True, null=True)

    # Laptop specific
    host_name        = models.CharField(max_length=100, blank=True, null=True)
    os               = models.CharField(max_length=50, blank=True, null=True)
    hdd_ssd          = models.CharField(max_length=50, blank=True, null=True)
    ram              = models.CharField(max_length=50, blank=True, null=True)
    antivirus        = models.CharField(max_length=100, blank=True, null=True)
    domain_updated   = models.CharField(max_length=10, choices=DOMAIN_CHOICES, blank=True, null=True)
    generation       = models.CharField(max_length=50, blank=True, null=True)
    storage          = models.CharField(max_length=50, blank=True, null=True)

    # Other type
    custom_field_name  = models.CharField(max_length=100, blank=True, null=True)
    custom_field_value = models.CharField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.serial_number}"


class AssetAssignment(models.Model):
    asset       = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='assignments')
    employee    = models.ForeignKey(AddEmployee, on_delete=models.CASCADE, related_name='asset_assignments')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assigned_date = models.DateField()
    return_date   = models.DateField(null=True, blank=True)
    condition_on_assignment = models.CharField(max_length=200, default='Good')
    condition_on_return     = models.CharField(max_length=200, blank=True, null=True)
    notes     = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-assigned_date']

    def __str__(self):
        return f"{self.asset.title} → {self.employee.first_name} {self.employee.last_name}"