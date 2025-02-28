from django.db import models
from accounts.models import CustomUser

class Dorm(models.Model):
    landlord = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'user_type': 'landlord'})
    name = models.CharField(max_length=255)
    address = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    image = models.ImageField(upload_to='dorm_images/', null=True, blank=True)
    available = models.BooleanField(default=True)

    def __str__(self):
        return self.name
