# Generated migration for offer letter fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0065_delete_offerletterrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='addemployee',
            name='offer_letter_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='addemployee',
            name='offer_letter_pdf',
            field=models.FileField(blank=True, null=True, upload_to='offer_letters/'),
        ),
        migrations.AddField(
            model_name='addemployee',
            name='offer_letter_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='addemployee',
            name='offer_letter_ctc',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
    ]
