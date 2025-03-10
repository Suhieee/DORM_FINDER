from django.db import models
from accounts.models import CustomUser

class Amenity(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Dorm(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    landlord = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'user_type': 'landlord'})
    name = models.CharField(max_length=255)
    address = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    permit = models.FileField(upload_to='dorm_permits/', null=True, blank=True)
    available = models.BooleanField(default=True)
    approval_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(null=True, blank=True)
    amenities = models.ManyToManyField(Amenity, blank=True, related_name='dorms')

    def __str__(self):
        return f"{self.name} - {self.landlord.username} ({self.landlord.contact_number})"


class DormImage(models.Model):
    dorm = models.ForeignKey(Dorm, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to='dorm_images/')

    def __str__(self):
        return f"Image for {self.dorm.name}"
    


