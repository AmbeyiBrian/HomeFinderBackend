from django.db import models
from django.core.exceptions import ValidationError
from properties.models import Property
from users.models import CustomUser


class Review(models.Model):
    property = models.ForeignKey(Property, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField()  # A rating field, you can modify it as per your requirements
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('property', 'user')  # Enforce uniqueness at the database level

    def __str__(self):
        return f"Review for {self.property.title} by {self.user.username}"

    def save(self, *args, **kwargs):
        # Perform validation before saving
        if Review.objects.filter(property=self.property, user=self.user).exists():
            raise ValidationError("You have already rated this property.")
        super().save(*args, **kwargs)


class Requests(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('real_estate_agent', 'Real estate agent'),
        ('seller', 'Seller'),
    ]

    REQUEST_STATUS = [
        ('pending', 'Pending'),
    ]

    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=REQUEST_STATUS, default='pending')
    requester = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='account_requests'  # Changed from 'properties' to avoid clash
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('requester', 'account_type')  # Fixed the field reference

    def __str__(self):
        return f"Request from {self.requester.username} for {self.get_account_type_display()}"