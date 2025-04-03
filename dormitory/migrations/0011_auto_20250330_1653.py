# Generated by Django 3.2 on 2025-03-30 08:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dormitory', '0010_auto_20250314_0105'),
    ]

    operations = [
        migrations.AddField(
            model_name='dorm',
            name='latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name='dorm',
            name='longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
    ]
