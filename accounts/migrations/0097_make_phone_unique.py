# Generated manually to make phone field unique

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0096_add_joining_date_to_employee'),
    ]

    operations = [
        migrations.AlterField(
            model_name='addemployee',
            name='phone',
            field=models.CharField(max_length=20, unique=True),
        ),
    ]