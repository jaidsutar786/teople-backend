from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomerViewSet, InvoiceViewSet, PaymentViewSet,
    ExpenseViewSet, SalaryExpenseViewSet, EmployeeListView, DashboardView
)

router = DefaultRouter()
router.register(r'customers',       CustomerViewSet,      basename='customer')
router.register(r'invoices',        InvoiceViewSet,       basename='invoice')
router.register(r'payments',        PaymentViewSet,       basename='payment')
router.register(r'expenses',        ExpenseViewSet,       basename='expense')
router.register(r'salary-expenses', SalaryExpenseViewSet, basename='salary-expense')
router.register(r'employees-list',  EmployeeListView,     basename='employees-list')
router.register(r'dashboard',       DashboardView,        basename='dashboard')

urlpatterns = [
    path('', include(router.urls)),
]
