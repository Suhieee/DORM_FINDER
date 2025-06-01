from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_notification_related_object_id'),
        ('dormitory', '0017_auto_20250528_1854'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReservationMessage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now)),
                ('is_read', models.BooleanField(default=False)),
                ('reservation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='dormitory.reservation')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_reservation_messages', to='accounts.customuser')),
            ],
            options={
                'ordering': ['timestamp'],
                'db_table': 'dormitory_reservation_message',
            },
        ),
    ] 