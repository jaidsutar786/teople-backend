# Generated migration for Modern Work Session Update

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0037_alter_worksession_productivity_score'),
    ]

    operations = [
        # Remove old invasive tracking fields
        migrations.RemoveField(
            model_name='worksession',
            name='keyboard_activity',
        ),
        migrations.RemoveField(
            model_name='worksession',
            name='mouse_activity',
        ),
        migrations.RemoveField(
            model_name='worksession',
            name='screenshots_count',
        ),
        migrations.RemoveField(
            model_name='worksession',
            name='focus_time_minutes',
        ),
        migrations.RemoveField(
            model_name='worksession',
            name='break_time_minutes',
        ),
        migrations.RemoveField(
            model_name='worksession',
            name='last_activity',
        ),
        
        # Add modern task-based tracking fields
        migrations.AddField(
            model_name='worksession',
            name='tasks_planned',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='worksession',
            name='tasks_completed',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='worksession',
            name='blockers',
            field=models.TextField(blank=True, null=True),
        ),
        
        # Add self-reported productivity fields
        migrations.AddField(
            model_name='worksession',
            name='energy_level',
            field=models.IntegerField(
                blank=True,
                choices=[(1, 'Very Low'), (2, 'Low'), (3, 'Medium'), (4, 'High'), (5, 'Very High')],
                null=True
            ),
        ),
        migrations.AddField(
            model_name='worksession',
            name='focus_quality',
            field=models.IntegerField(
                blank=True,
                choices=[(1, 'Poor'), (2, 'Fair'), (3, 'Good'), (4, 'Very Good'), (5, 'Excellent')],
                null=True
            ),
        ),
        
        # Add break tracking
        migrations.AddField(
            model_name='worksession',
            name='breaks_taken',
            field=models.JSONField(blank=True, default=list),
        ),
        
        # Add collaboration metrics
        migrations.AddField(
            model_name='worksession',
            name='meetings_attended',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='worksession',
            name='team_interactions',
            field=models.IntegerField(default=0),
        ),
    ]
