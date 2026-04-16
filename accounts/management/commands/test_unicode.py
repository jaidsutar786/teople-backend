from django.core.management.base import BaseCommand
from accounts.console_utils import safe_print

class Command(BaseCommand):
    help = 'Test Unicode printing'

    def handle(self, *args, **options):
        safe_print("✅ Testing Unicode characters")
        safe_print("❌ Error emoji test")
        safe_print("📊 Data emoji test")
        safe_print("💰 Money emoji test")
        safe_print("🔄 Refresh emoji test")
        self.stdout.write(self.style.SUCCESS('Unicode test completed successfully'))