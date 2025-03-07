from datetime import timedelta
from django.utils import timezone
from celery import shared_task
from .models import Reservation

@shared_task
def cleanup_abandoned_reservations():
    """
    Cleanup reservations that were initialized but never completed payment.
    Runs automatically every 15 minutes.
    """
    # Find reservations that are over 30 minutes old, still initialized, and unpaid
    timeout = timezone.now() - timedelta(minutes=30)
    abandoned_reservations = Reservation.objects.filter(
        status='initialized',
        payment_status='unpaid',
        created_at__lt=timeout
    )
    
    # Mark them as expired
    count = abandoned_reservations.update(status='expired')
    return f"Cleaned up {count} abandoned reservations"