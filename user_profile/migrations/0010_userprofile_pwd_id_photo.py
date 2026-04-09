from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_profile', '0009_pwd_verification_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='pwd_id_photo',
            field=models.ImageField(blank=True, null=True, upload_to='verification_docs/pwd/id_photo/'),
        ),
    ]
