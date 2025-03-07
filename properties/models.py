from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from users.models import CustomUser
import os
from decimal import Decimal

from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

class PropertyType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Property(models.Model):
    SALE_STATUS_CHOICES = [
        ('available', 'Available'),
        ('pending', 'Pending'),
        ('sold', 'Sold')
    ]
    LISTING_TYPE_CHOICES = [
        ('rent', 'Rent'),
        ('sale', 'Sale'),
    ]

    listing_type = models.CharField(max_length=10, choices=LISTING_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    reservation_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    property_type = models.ForeignKey(PropertyType, on_delete=models.SET_NULL, null=True)
    bedrooms = models.IntegerField(validators=[MinValueValidator(0)])
    bathrooms = models.DecimalField(max_digits=10, decimal_places=0, validators=[MinValueValidator(0)])
    square_feet = models.IntegerField(validators=[MinValueValidator(0)])
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    zip_code = models.CharField(max_length=20)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=SALE_STATUS_CHOICES, default='available')
    is_verified=models.BooleanField(default=False)

    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='properties')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['price']),
            models.Index(fields=['city']),
            models.Index(fields=['listing_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Set default reservation price to 10% of property price if not provided
        if not self.reservation_price and self.price:
            self.reservation_price = self.price * Decimal('0.1')
        super().save(*args, **kwargs)

class PropertyImage(models.Model):
    property = models.ForeignKey(
        'Property',
        related_name='images',
        on_delete=models.CASCADE
    )
    image = models.ImageField(
        upload_to='property_images/'
    )
    is_primary = models.BooleanField(default=False)

    def clean(self):
        """
        Validate that only one primary image exists per property
        """
        if self.is_primary:
            qs = PropertyImage.objects.filter(
                property=self.property,
                is_primary=True
            )
            if self.pk:  # Exclude current instance if updating
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError("A primary image already exists for this property")

    def save(self, *args, **kwargs):
        """
        Custom save method with transaction handling and logging
        """
        from django.db import transaction

        try:
            with transaction.atomic():
                # Ensure validation happens before save
                self.full_clean()

                # Call original save method
                super().save(*args, **kwargs)

                # Log successful save
                logger.info(f"Image saved successfully. Path: {self.image.name}")

                # If marked as primary, update other images
                if self.is_primary:
                    PropertyImage.objects.filter(
                        property=self.property
                    ).exclude(pk=self.pk).update(is_primary=False)

        except Exception as e:
            logger.error(f"Error saving image: {str(e)}", exc_info=True)
            raise  # Re-raise exception after logging

    def __str__(self):
        return f"Image for {self.property} (Primary: {self.is_primary})"

class Favorite(models.Model):
    user = models.ForeignKey(CustomUser, related_name='favorites', on_delete=models.CASCADE)
    property = models.ForeignKey(Property, related_name='favorited_by', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'property']  # Prevent duplicate favorites by the same user

    def __str__(self):
        return f'{self.user.username} - {self.property.title}'

class Reservation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed')
    ]
    
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='reservations')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reservations')
    reservation_price = models.DecimalField(max_digits=12, decimal_places=2)
    booking_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, default='unpaid')
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['property']),
            models.Index(fields=['user']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
        
    def __str__(self):
        return f"{self.user.username} - {self.property.title} ({self.status})"
    
    def save(self, *args, **kwargs):
        from decimal import Decimal
        # Calculate booking fee (10% of reservation price)
        if not self.booking_fee:
            self.booking_fee = self.reservation_price * Decimal('0.1')
            
        # Calculate total amount
        if not self.total_amount:
            self.total_amount = self.reservation_price

        if self.payment_status == 'paid' and self.status == 'confirmed':
            # Update property status to sold/unavailable when reservation is confirmed and paid
            self.property.status = 'sold'
            self.property.save()
        elif self.status == 'cancelled':
            # If reservation is cancelled, make property available again
            self.property.status = 'available'
            self.property.save()
            
        super().save(*args, **kwargs)