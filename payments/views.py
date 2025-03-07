from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle, AnonRateThrottle
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from properties.models import Reservation
from .models import MpesaTransaction
from .serializers import MpesaPaymentSerializer, MpesaTransactionSerializer
from .mpesa_utils import MpesaGateway
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class PaymentRateThrottle(ScopedRateThrottle):
    scope = 'payment_attempts'

class MpesaCallbackThrottle(AnonRateThrottle):
    rate = '100/min'  # Limit to 100 callbacks per minute

class InitiateMpesaPaymentView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PaymentRateThrottle]
    
    def post(self, request):
        serializer = MpesaPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        reservation_id = serializer.validated_data['reservation_id']
        phone_number = serializer.validated_data['phone_number']
        
        # Get reservation
        try:
            reservation = Reservation.objects.select_for_update().get(
                id=reservation_id,
                user=request.user
            )
        except Reservation.DoesNotExist:
            return Response(
                {"detail": "Reservation not found or does not belong to you."},
                status=status.HTTP_404_NOT_FOUND
            )
            
        # Check if there's already a pending transaction
        existing_pending = MpesaTransaction.objects.filter(
            reservation=reservation,
            status='PENDING',
            transaction_date__gte=timezone.now() - timezone.timedelta(minutes=15)
        ).exists()
        
        if existing_pending:
            return Response(
                {"detail": "A payment for this reservation is already in progress. Please wait or try again later."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate unique transaction reference
        transaction_ref = f"HF-{uuid.uuid4().hex[:8]}"
        
        try:
            with transaction.atomic():
                # Create pending transaction record
                mpesa_transaction = MpesaTransaction.objects.create(
                    reservation=reservation,
                    transaction_type='C2B',
                    transaction_reference=transaction_ref,
                    amount=reservation.total_amount,
                    phone_number=phone_number,
                    status='PENDING'
                )
                
                # Build callback URL
                callback_url = f"{settings.MPESA_CALLBACK_BASE_URL}/api/payments/callback/"
                logger.info(f"Using callback URL: {callback_url}")
                
                # Initialize M-Pesa gateway and initiate payment
                mpesa = MpesaGateway()
                result = mpesa.initiate_stk_push(
                    phone_number=phone_number,
                    amount=float(reservation.total_amount),
                    reference=transaction_ref,
                    callback_url=callback_url
                )
                
                # Update transaction with M-Pesa request IDs
                mpesa_transaction.merchant_request_id = result.get('MerchantRequestID')
                mpesa_transaction.checkout_request_id = result.get('CheckoutRequestID')
                mpesa_transaction.result_description = result.get('CustomerMessage', '')
                mpesa_transaction.save()
                
                return Response({
                    'message': 'Payment initiated. Please complete the payment on your phone.',
                    'transaction_reference': transaction_ref,
                    'merchant_request_id': mpesa_transaction.merchant_request_id,
                    'checkout_request_id': mpesa_transaction.checkout_request_id,
                    'status': 'pending'
                })
                
        except Exception as e:
            logger.error(f"Error initiating payment: {str(e)}")
            logger.exception(e)
            return Response(
                {"detail": "Failed to initiate payment. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@method_decorator(csrf_exempt, name='dispatch')
class MpesaCallbackView(APIView):
    """Handle M-Pesa payment callbacks from Safaricom."""
    permission_classes = []  # No authentication required for callbacks
    throttle_classes = [MpesaCallbackThrottle]

    def validate_callback_data(self, data):
        """Validate M-Pesa callback data structure"""
        required_fields = {
            'Body': {
                'stkCallback': {
                    'MerchantRequestID': str,
                    'CheckoutRequestID': str,
                    'ResultCode': int,
                    'ResultDesc': str
                }
            }
        }

        def validate_structure(template, data):
            if not isinstance(data, dict):
                return False, "Invalid data structure"
            
            for key, value in template.items():
                if key not in data:
                    return False, f"Missing required field: {key}"
                
                if isinstance(value, dict):
                    is_valid, error = validate_structure(value, data[key])
                    if not is_valid:
                        return False, f"In {key}: {error}"
                else:
                    if not isinstance(data[key], value):
                        return False, f"Invalid type for {key}"
            
            return True, None

        is_valid, error = validate_structure(required_fields, data)
        if not is_valid:
            raise ValidationError(error)

        return True

    def post(self, request):
        try:
            # Log the raw callback data
            logger.info("Raw M-Pesa callback data received:")
            logger.info(request.data)
            
            # Validate callback data structure
            try:
                self.validate_callback_data(request.data)
            except ValidationError as e:
                logger.error(f"Invalid callback data: {str(e)}")
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Extract and validate callback data
            body = request.data.get('Body', {})
            if not body:
                logger.error("No Body in callback data")
                return Response(
                    {"error": "Invalid callback data structure"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            stk_callback = body.get('stkCallback')
            if not stk_callback:
                logger.error("No stkCallback in Body")
                return Response(
                    {"error": "Invalid callback data structure"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Extract required fields
            merchant_request_id = stk_callback.get('MerchantRequestID')
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc', '')

            logger.info(f"""
                Processing M-Pesa callback:
                MerchantRequestID: {merchant_request_id}
                CheckoutRequestID: {checkout_request_id}
                ResultCode: {result_code}
                ResultDesc: {result_desc}
            """)

            if not merchant_request_id or not checkout_request_id:
                logger.error("Missing required fields in callback data")
                return Response(
                    {"error": "Missing required fields"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Use transaction.atomic() to ensure data consistency
            with transaction.atomic():
                # Find transaction - try both merchant request ID and checkout request ID
                try:
                    mpesa_txn = MpesaTransaction.objects.select_for_update().get(
                        transaction_reference=merchant_request_id
                    )
                    logger.info(f"Found transaction with merchant_request_id: {merchant_request_id}")
                except MpesaTransaction.DoesNotExist:
                    logger.error(f"Transaction not found for merchant_request_id: {merchant_request_id}")
                    try:
                        mpesa_txn = MpesaTransaction.objects.select_for_update().get(
                            checkout_request_id=checkout_request_id
                        )
                        logger.info(f"Found transaction with checkout_request_id: {checkout_request_id}")
                    except MpesaTransaction.DoesNotExist:
                        logger.error("Transaction not found with either ID")
                        return Response(
                            {"error": "Transaction not found"},
                            status=status.HTTP_404_NOT_FOUND
                        )

                # Never process a completed transaction again
                if mpesa_txn.status == 'COMPLETED':
                    logger.info(f"Transaction {merchant_request_id} already completed")
                    return Response({"status": "already processed"}, status=status.HTTP_200_OK)

                # Update transaction with result
                mpesa_txn.result_code = str(result_code)
                mpesa_txn.result_description = result_desc
                
                if result_code == 0:  # Successful payment
                    try:
                        # Extract and validate payment details
                        callback_metadata = stk_callback.get('CallbackMetadata', {})
                        if not callback_metadata:
                            raise ValueError("No callback metadata found")

                        items = callback_metadata.get('Item', [])
                        if not items:
                            raise ValueError("No items in callback metadata")

                        # Create metadata dictionary
                        metadata_dict = {}
                        for item in items:
                            name = item.get('Name')
                            value = item.get('Value')
                            if name and value is not None:
                                metadata_dict[name] = value

                        logger.info(f"Extracted metadata: {metadata_dict}")

                        # Update transaction details
                        mpesa_txn.mpesa_receipt_number = metadata_dict.get('MpesaReceiptNumber')
                        
                        # Handle transaction date
                        if metadata_dict.get('TransactionDate'):
                            try:
                                date_str = metadata_dict['TransactionDate']
                                if isinstance(date_str, str):
                                    if len(date_str) == 14:  # Format: YYYYMMDDhhmmss
                                        transaction_date = datetime.strptime(date_str, '%Y%m%d%H%M%S')
                                        mpesa_txn.transaction_date = timezone.make_aware(transaction_date)
                                    else:
                                        mpesa_txn.transaction_date = date_str
                            except (ValueError, TypeError) as e:
                                logger.error(f"Error parsing transaction date: {e}")
                        
                        # Set status to COMPLETED - this will trigger the model's save logic
                        mpesa_txn.status = 'COMPLETED'
                        mpesa_txn.save()

                        return Response({"status": "success"}, status=status.HTTP_200_OK)

                    except (ValueError, KeyError) as e:
                        logger.error(f"Error processing successful payment: {str(e)}")
                        logger.exception(e)
                        mpesa_txn.status = 'FAILED'
                        mpesa_txn.result_description = f"Error processing payment: {str(e)}"
                        mpesa_txn.save()
                        return Response(
                            {"error": str(e)},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    # Payment failed
                    mpesa_txn.status = 'FAILED'
                    mpesa_txn.save()
                    return Response({"status": "failed"}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Unexpected error in M-Pesa callback: {str(e)}")
            logger.exception(e)
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CheckPaymentStatusView(APIView):
    """Check payment status and get transaction details"""
    permission_classes = [IsAuthenticated]
    throttle_classes = [PaymentRateThrottle]
    
    def get(self, request, transaction_ref):
        try:
            transaction = MpesaTransaction.objects.select_related('reservation').get(
                transaction_reference=transaction_ref,
                reservation__user=request.user
            )
        except MpesaTransaction.DoesNotExist:
            return Response(
                {"detail": "Transaction not found."},
                status=status.HTTP_404_NOT_FOUND
            )
            
        # If transaction is still pending and old enough, check its status
        if (transaction.status == 'PENDING' and 
            transaction.transaction_date < timezone.now() - timezone.timedelta(seconds=30)):
            try:
                mpesa = MpesaGateway()
                result = mpesa.verify_transaction(transaction.checkout_request_id)
                
                # Update transaction based on verification result
                result_code = str(result.get('ResultCode', ''))
                if result_code == '0':  # Success
                    transaction.status = 'COMPLETED'
                    transaction.result_code = result_code
                    transaction.result_description = 'Success (verified by status check)'
                    transaction.save()
                elif result_code in ['1032', '1037']:  # Cancelled or Timeout
                    transaction.status = 'FAILED'
                    transaction.result_code = result_code
                    transaction.result_description = 'Transaction cancelled by user' if result_code == '1032' else 'Transaction timeout'
                    transaction.save()
            except Exception as e:
                logger.error(f"Error verifying transaction status: {str(e)}")
                # Don't update transaction status on verification error
        
        serializer = MpesaTransactionSerializer(transaction)
        return Response(serializer.data)