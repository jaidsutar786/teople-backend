from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        User = get_user_model()
        email = "admin@teople.com"
        password = "Admin@1234"
        username = "admin"
        if not User.objects.filter(email=email).exists():
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(f"Superuser created: {email}")
        else:
            self.stdout.write("Superuser already exists")
