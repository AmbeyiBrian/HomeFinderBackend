from django.db import models, transaction
from properties.models import Reservation
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class MpesaTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('C2B', 'Customer to Business'),
        ('B2C', 'Business to Customer')
    ]
    
    TRANSACTION_STATUS = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled')
    ]
    
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='mpesa_transactions')
    transaction_type = models.CharField(max_length=3, choices=TRANSACTION_TYPES)
    transaction_reference = models.CharField(max_length=100, unique=True)
    merchant_request_id = models.CharField(max_length=100, blank=True, null=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15)
    mpesa_receipt_number = models.CharField(max_length=50, blank=True, null=True)
    transaction_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=TRANSACTION_STATUS, default='PENDING')
    result_code = models.CharField(max_length=5, blank=True, null=True)
    result_description = models.TextField(blank=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['transaction_reference']),
            models.Index(fields=['checkout_request_id']),
            models.Index(fields=['mpesa_receipt_number']),
            models.Index(fields=['status']),
        ]
        
    def __str__(self):
        return f"{self.transaction_reference} - {self.amount} - {self.status}"
    
    @property
    def is_expired(self):
        """Check if a pending transaction has expired (older than 15 minutes)"""
        if self.status == 'PENDING':
            expiration_time = timezone.now() - timedelta(minutes=15)
            return self.transaction_date < expiration_time
        return False
    
    def save(self, *args, **kwargs):
        # Get old instance if this is an existing record
        old_status = None
        if self.pk:
            try:
                old_instance = MpesaTransaction.objects.get(pk=self.pk)
                old_status = old_instance.status
                # Never allow changing status from COMPLETED
                if old_instance.status == 'COMPLETED':
                    self.status = 'COMPLETED'
                    logger.info(f"Prevented status change for completed transaction {self.transaction_reference}")
                    return super().save(*args, **kwargs)
            except MpesaTransaction.DoesNotExist:
                pass

        # Initialize transaction_date for new instances
        if not self.pk and not self.transaction_date:
            self.transaction_date = timezone.now()
            
        # Use atomic transaction to ensure consistency
        with transaction.atomic():
            # For new transactions or non-completed ones, handle status transitions
            if not self.pk or self.status != 'COMPLETED':
                if self.status == 'PENDING' and self.is_expired:
                    logger.info(f"Transaction {self.transaction_reference} has expired")
                    self.status = 'FAILED'
                    self.result_description = 'Transaction expired'
                elif (self.status == 'PENDING' and 
                      self.mpesa_receipt_number and 
                      self.result_code == '0'):  # Only complete if we have receipt AND success code
                    logger.info(f"Transaction {self.transaction_reference} completed with receipt {self.mpesa_receipt_number}")
                    self.status = 'COMPLETED'
            
            # Save the instance
            super().save(*args, **kwargs)
            
            # Only update reservation if status changed to COMPLETED or FAILED
            if old_status != self.status:
                logger.info(f"Transaction status changed from {old_status} to {self.status}")
                
                if self.status == 'COMPLETED' and self.reservation:
                    # Update reservation atomically
                    Reservation.objects.filter(id=self.reservation.id).update(
                        payment_status='paid',
                        status='confirmed'
                    )
                    logger.info(f"Updated reservation {self.reservation.id} status to paid and confirmed")
                    
                    # Update property status atomically if it exists
                    if self.reservation.property:
                        self.reservation.property.__class__.objects.filter(
                            id=self.reservation.property.id
                        ).update(status='reserved')
                        logger.info(f"Updated property {self.reservation.property.id} status to reserved")
                        
                elif self.status in ['FAILED', 'CANCELLED'] and self.reservation:
                    # Update reservation atomically
                    Reservation.objects.filter(id=self.reservation.id).update(
                        payment_status='unpaid',
                        status='failed'
                    )
                    logger.info(f"Updated reservation {self.reservation.id} status to unpaid and failed")
                    
                    # Reset property status atomically if needed
                    if self.reservation.property:
                        self.reservation.property.__class__.objects.filter(
                            id=self.reservation.property.id
                        ).update(status='available')
                        logger.info(f"Reset property {self.reservation.property.id} status to available")