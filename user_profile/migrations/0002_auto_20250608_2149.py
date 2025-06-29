# Generated by Django 3.2 on 2025-06-08 13:49

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dormitory', '0029_auto_20250604_1210'),
        ('user_profile', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FavoriteDorm',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('added_date', models.DateTimeField(auto_now_add=True)),
                ('dorm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dormitory.dorm')),
                ('user_profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='user_profile.userprofile')),
            ],
            options={
                'ordering': ['-added_date'],
                'unique_together': {('user_profile', 'dorm')},
            },
        ),
        migrations.AddField(
            model_name='userprofile',
            name='favorite_dorms',
            field=models.ManyToManyField(related_name='favorited_by', through='user_profile.FavoriteDorm', to='dormitory.Dorm'),
        ),
    ]
