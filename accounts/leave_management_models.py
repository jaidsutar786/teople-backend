from django.db import models

class CompanyLeave(models.Model):
    date = models.DateField(unique=True)
    reason = models.CharField(max_length=255)
    month = models.IntegerField()
    year = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'accounts'
        db_table = 'company_leaves'
        ordering = ['date']
    
    def __str__(self):
        return f"{self.date} - {self.reason}"

class SaturdayOverride(models.Model):
    STATUS_CHOICES = [
        ('working', 'Working'),
        ('off', 'Off'),
    ]
    
    date = models.DateField(unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    month = models.IntegerField()
    year = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = 'accounts'
        db_table = 'saturday_overrides'
        ordering = ['date']
    
    def __str__(self):
        return f"{self.date} - {self.status}"
