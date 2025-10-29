from django.db import migrations


def normalize_emails_forward(apps, schema_editor):
    User = apps.get_model('accounts', 'CustomUser')
    # Lowercase all emails first
    for user in User.objects.exclude(email__isnull=True).exclude(email=''):
        email_lower = user.email.strip().lower()
        if user.email != email_lower:
            user.email = email_lower
            user.save(update_fields=['email'])

    # Resolve duplicates by deactivating duplicates, keeping the earliest
    from collections import defaultdict
    seen = defaultdict(list)
    for user in User.objects.exclude(email__isnull=True).exclude(email=''):
        seen[user.email].append(user)

    for email, users in seen.items():
        if len(users) <= 1:
            continue
        # Keep the earliest (by date_joined then id) active; deactivate others
        users.sort(key=lambda u: (u.date_joined, u.id))
        keeper = users[0]
        for dup in users[1:]:
            if dup.is_active:
                dup.is_active = False
                dup.save(update_fields=['is_active'])


def normalize_emails_backward(apps, schema_editor):
    # No-op reverse; cannot easily restore previous duplicates
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0012_alter_customuser_options_customuser_unique_email_ci'),
    ]

    operations = [
        migrations.RunPython(normalize_emails_forward, normalize_emails_backward),
    ]


