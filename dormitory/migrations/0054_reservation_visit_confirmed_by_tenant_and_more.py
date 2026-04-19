from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dormitory', '0053_roommatepost_mood_other'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservation',
            name='visit_confirmed_by_tenant',
            field=models.BooleanField(default=False, help_text="Whether tenant has accepted the landlord's proposed visit schedule"),
        ),
        migrations.AlterField(
            model_name='reservation',
            name='visit_time_slot',
            field=models.CharField(blank=True, choices=[('morning', 'Morning'), ('afternoon', 'Afternoon'), ('evening', 'Evening'), ('flexible', 'Flexible / To Be Finalized')], max_length=20, null=True),
        ),
    ]
