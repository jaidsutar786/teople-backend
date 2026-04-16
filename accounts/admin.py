from django.contrib import admin
from .models import EmployeeOTP

@admin.register(EmployeeOTP)
class EmployeeOTPAdmin(admin.ModelAdmin):
    list_display = ['email', 'otp', 'created_at', 'expires_at', 'is_verified', 'attempts']
    list_filter = ['is_verified', 'created_at']
    search_fields = ['email', 'otp']
    readonly_fields = ['created_at']
