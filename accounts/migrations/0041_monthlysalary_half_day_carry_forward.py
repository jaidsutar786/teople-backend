# Generated migration for half_day_carry_forward field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0040_monthlysalary_paid_leaves_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='monthlysalary',
            name='half_day_carry_forward',
            field=models.DecimalField(decimal_places=1, default=0, max_digits=5),
        ),
    ]
