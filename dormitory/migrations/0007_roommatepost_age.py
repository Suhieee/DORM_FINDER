# Generated by Django 3.2 on 2025-03-13 07:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dormitory', '0006_roommateamenity_roommatepost'),
    ]

    operations = [
        migrations.AddField(
            model_name='roommatepost',
            name='age',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
