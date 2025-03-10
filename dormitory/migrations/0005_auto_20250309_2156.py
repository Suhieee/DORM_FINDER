# Generated by Django 3.2 on 2025-03-09 13:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dormitory', '0004_auto_20250309_1452'),
    ]

    operations = [
        migrations.CreateModel(
            name='Amenity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
            ],
        ),
        migrations.AddField(
            model_name='dorm',
            name='amenities',
            field=models.ManyToManyField(blank=True, related_name='dorms', to='dormitory.Amenity'),
        ),
    ]
