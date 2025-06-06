# Generated by Django 3.2 on 2025-05-28 11:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dormitory', '0018_create_reservation_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='reservation',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='reservation',
            name='status',
            field=models.CharField(choices=[('pending_payment', 'Pending Payment'), ('pending', 'Payment Submitted - Pending Approval'), ('confirmed', 'Confirmed'), ('completed', 'Transaction Completed'), ('declined', 'Declined'), ('cancelled', 'Cancelled')], default='pending_payment', max_length=20),
        ),
        migrations.AlterField(
            model_name='reservationmessage',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='reservationmessage',
            name='timestamp',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
