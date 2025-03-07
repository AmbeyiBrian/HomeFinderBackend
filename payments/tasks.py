from celery import shared_task
from django.utils import timezone
from datetime import timedelta, datetime
import logging
from .models import MpesaTransaction

logger = logging.getLogger(__name__)

@shared_task
def cleanup_expired_transactions():
    """
    Periodic task to cleanup expired pending transactions.
    Runs every 5 minutes to check for and update expired transactions.
    """
    expiration_time = timezone.now() - timedelta(minutes=15)
    expired_transactions = MpesaTransaction.objects.filter(
        status='PENDING',
        transaction_date__lt=expiration_time
    )
    
    for transaction in expired_transactions:
        transaction.status = 'FAILED'
        transaction.result_description = 'Transaction expired'
        transaction.save()  # This will trigger the save() method which handles reservation updates

    return f"Cleaned up {expired_transactions.count()} expired transactions"

@shared_task
def verify_pending_transactions():
    """
    Check status of pending transactions and update them accordingly.
    This helps handle cases where callbacks weren't received.
    """
    # Get transactions that have been pending for more than 30 seconds but less than 1 hour
    time_threshold = timezone.now() - timedelta(seconds=30)
    old_threshold = timezone.now() - timedelta(hours=1)
    
    pending_transactions = MpesaTransaction.objects.filter(
        status='PENDING',
        transaction_date__lt=time_threshold,
        transaction_date__gt=old_threshold
    )
    
    mpesa = MpesaGateway()
    
    for transaction in pending_transactions:
        try:
            logger.info(f"Checking status for transaction {transaction.checkout_request_id}")
            
            if not transaction.checkout_request_id:
                logger.error(f"No checkout_request_id for transaction {transaction.transaction_reference}")
                continue
                
            result = mpesa.verify_transaction(transaction.checkout_request_id)
            result_code = str(result.get('ResultCode', ''))
            
            if result_code == '0':  # Success
                transaction.status = 'COMPLETED'
                transaction.result_code = result_code
                transaction.result_description = 'Success (verified by status check)'
                transaction.save()
                
                logger.info(f"Successfully verified and completed transaction {transaction.transaction_reference}")
                
            elif result_code in ['1032', '1037']:  # Cancelled or Timeout
                transaction.status = 'FAILED'
                transaction.result_code = result_code
                transaction.result_description = 'Transaction cancelled by user' if result_code == '1032' else 'Transaction timeout'
                transaction.save()
                
                logger.info(f"Transaction {transaction.transaction_reference} marked as failed: {transaction.result_description}")
            
            else:
                logger.warning(f"Unexpected result code {result_code} for transaction {transaction.transaction_reference}")
        
        except Exception as e:
            logger.error(f"Error verifying transaction {transaction.transaction_reference}: {str(e)}")
            logger.exception(e)

@shared_task
def cleanup_old_pending_transactions():
    """Mark very old pending transactions as failed"""
    hour_ago = timezone.now() - timedelta(hours=1)
    
    old_pending = MpesaTransaction.objects.filter(
        status='PENDING',
        transaction_date__lt=hour_ago
    )
    
    for transaction in old_pending:
        transaction.status = 'FAILED'
        transaction.result_description = 'Transaction expired (no callback received)'
        transaction.save()
        
        # Update reservation status
        reservation = transaction.reservation
        reservation.status = 'failed'
        reservation.save()
        
        logger.info(f"Marked old transaction {transaction.transaction_reference} as failed")

@shared_task
def simulate_mpesa_callback(checkout_request_id, reference, amount, phone_number):
    """Simulate M-Pesa callback in development environment"""
    logger.info(f"Simulating M-Pesa callback for checkout request: {checkout_request_id}")
    
    # Use current time in correct format
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Create callback data
    callback_data = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": reference,
                "CheckoutRequestID": checkout_request_id,
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {
                    "Item": [
                        {
                            "Name": "Amount",
                            "Value": amount
                        },
                        {
                            "Name": "MpesaReceiptNumber",
                            "Value": f"DEV{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        },
                        {
                            "Name": "TransactionDate",
                            "Value": current_time
                        },
                        {
                            "Name": "PhoneNumber",
                            "Value": phone_number
                        }
                    ]
                }
            }
        }
    }
    
    from .views import MpesaCallbackView
    
    try:
        class MockRequest:
            def __init__(self, data):
                self.data = data
        
        mock_request = MockRequest(callback_data)
        callback_view = MpesaCallbackView()
        response = callback_view.post(mock_request)
        
        logger.info(f"Mock callback processed with response status: {response.status_code}")
        return response.status_code
        
    except Exception as e:
        logger.error(f"Error processing mock callback: {str(e)}")
        logger.exception(e)
        raise