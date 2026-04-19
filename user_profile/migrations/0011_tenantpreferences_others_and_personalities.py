from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_profile', '0010_userprofile_pwd_id_photo'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenantpreferences',
            name='other_amenity_required',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='tenantpreferences',
            name='other_amenity_text',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='tenantpreferences',
            name='preferred_roommate_other_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='tenantpreferences',
            name='preferred_roommate_other_text',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='tenantpreferences',
            name='preferred_roommate_personalities',
            field=models.JSONField(blank=True, default=list, help_text='Preferred roommate personality types (multiple selections)'),
        ),
    ]
