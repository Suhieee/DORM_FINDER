from django.db import migrations

def update_roommate_budgets(apps, schema_editor):
    RoommatePost = apps.get_model('dormitory', 'RoommatePost')
    # Update any roommate posts with default budget values
    # Set a reasonable default range (3000-5000 PHP)
    for post in RoommatePost.objects.filter(preferred_budget_min=0):
        post.preferred_budget_min = 3000
        post.preferred_budget_max = 5000
        post.preferred_budget = 4000  # Average
        post.save()

def reverse_roommate_budgets(apps, schema_editor):
    RoommatePost = apps.get_model('dormitory', 'RoommatePost')
    # Revert back to default values if needed
    RoommatePost.objects.filter(preferred_budget_min=3000).update(
        preferred_budget_min=0,
        preferred_budget_max=0,
        preferred_budget=0
    )

class Migration(migrations.Migration):
    dependencies = [
        ('dormitory', '0022_auto_20250529_1622'),
    ]

    operations = [
        migrations.RunPython(update_roommate_budgets, reverse_roommate_budgets),
    ] 