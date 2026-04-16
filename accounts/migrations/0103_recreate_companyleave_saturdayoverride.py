from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0102_delete_companyleave_delete_saturdayoverride'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyLeave',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(unique=True)),
                ('reason', models.CharField(max_length=255)),
                ('month', models.IntegerField()),
                ('year', models.IntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'company_leaves',
                'ordering': ['date'],
            },
        ),
        migrations.CreateModel(
            name='SaturdayOverride',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(unique=True)),
                ('status', models.CharField(choices=[('working', 'Working'), ('off', 'Off')], max_length=10)),
                ('month', models.IntegerField()),
                ('year', models.IntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'saturday_overrides',
                'ordering': ['date'],
            },
        ),
    ]
