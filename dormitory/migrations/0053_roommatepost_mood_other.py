from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dormitory', '0052_dormamenityimage_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='roommatepost',
            name='mood_other',
            field=models.CharField(blank=True, help_text='Custom personality type when mood is set to Others', max_length=80),
        ),
        migrations.AlterField(
            model_name='roommatepost',
            name='mood',
            field=models.CharField(choices=[('quiet', 'Quiet and Reserved'), ('friendly', 'Friendly and Social'), ('adventurous', 'Adventurous and Outgoing'), ('studious', 'Studious and Focused'), ('others', 'Others')], db_index=True, default='friendly', help_text='Choose the personality type that best describes you', max_length=20),
        ),
    ]
