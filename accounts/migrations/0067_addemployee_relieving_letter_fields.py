# Generated migration for relieving letter fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0066_addemployee_offer_letter_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='addemployee',
            name='relieving_letter_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='addemployee',
            name='relieving_letter_pdf',
            field=models.FileField(blank=True, null=True, upload_to='relieving_letters/'),
        ),
        migrations.AddField(
            model_name='addemployee',
            name='relieving_letter_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='addemployee',
            name='last_working_day',
            field=models.DateField(blank=True, null=True),
        ),
    ]
