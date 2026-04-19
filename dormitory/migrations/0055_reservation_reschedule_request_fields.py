from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dormitory', '0054_reservation_visit_confirmed_by_tenant_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservation',
            name='tenant_preferred_visit_window',
            field=models.CharField(blank=True, choices=[('morning', 'Morning'), ('afternoon', 'Afternoon'), ('evening', 'Evening'), ('flexible', 'Flexible / To Be Finalized')], help_text='Tenant preferred generalized visit window when requesting reschedule', max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='reservation',
            name='tenant_reschedule_note',
            field=models.TextField(blank=True, default='', help_text='Tenant note when requesting a visit reschedule'),
        ),
        migrations.AddField(
            model_name='reservation',
            name='visit_reschedule_requested',
            field=models.BooleanField(default=False, help_text='Whether tenant requested a different visit schedule'),
        ),
    ]
