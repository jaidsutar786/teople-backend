import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'login_backend.settings')
django.setup()

from accounting.models import Expense, SalaryExpense

# Delete old salary expense entries
print("🗑️ Deleting old entries...")

# Delete Expense entries linked to salary
deleted_expense = Expense.objects.filter(category='salary', employee_id=1).delete()
print(f"✅ Deleted Expense entries: {deleted_expense}")

# Delete SalaryExpense entries
deleted_salary = SalaryExpense.objects.filter(employee_id=1, month=3, year=2026).delete()
print(f"✅ Deleted SalaryExpense entries: {deleted_salary}")

print("✅ Database cleaned! Now generate salary again.")
