from django.db import models
from .models import AddEmployee


class CompOffUsageNotification(models.Model):
    """
    Har mahine ke 1 tarikh ko employee ko notification bhejte hain:
    - Agar comp off balance hai to poochho: use karna hai ya nahi?
    - 2 din tak response nahi aaya → comp off DISCARD ho jayega
    - 'yes' → salary me add hoga
    - 'no' → next month carry forward
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),      # notification bheji, response nahi aaya
        ('accepted', 'Accepted'),    # employee ne 'haan use karna hai' kaha
        ('declined', 'Declined'),    # employee ne 'nahi' kaha → next month
        ('discarded', 'Discarded'),  # 2 din tak koi reply nahi → discard
    ]

    employee = models.ForeignKey(AddEmployee, on_delete=models.CASCADE, related_name='comp_off_usage_notifications')
    comp_off_hours = models.IntegerField()   # kitne hours available hain
    for_month = models.IntegerField()        # kis month ki salary ke liye (e.g. 2 = Feb)
    for_year = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_read = models.BooleanField(default=False)
    expires_at = models.DateTimeField()      # created_at + 2 days
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'accounts'
        ordering = ['-created_at']
        unique_together = ('employee', 'for_month', 'for_year')

    def __str__(self):
        return f"CompOff Notification - {self.employee.first_name} - {self.for_month}/{self.for_year} - {self.status}"

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at
