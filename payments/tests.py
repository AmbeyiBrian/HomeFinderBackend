from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from properties.models import Property, PropertyType, Reservation
from .models import MpesaTransaction
from .mpesa_utils import MpesaGateway
import json

User = get_user_model()

class MpesaPaymentTests(APITestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test property type
        self.property_type = PropertyType.objects.create(name='Apartment')
        
        # Create test property
        self.property = Property.objects.create(
            title='Test Property',
            property_type=self.property_type,
            price=100000,
            city='Nairobi',
            state='Nairobi',
            status='available'
        )
        
        # Create test reservation
        self.reservation = Reservation.objects.create(
            user=self.user,
            property=self.property,
            reservation_price=self.property.price,
            booking_fee=2.00,
            total_amount=2.00,
            status='pending',
            payment_status='unpaid'
        )
        
        # Valid payload for tests
        self.valid_payload = {
            'reservation_id': self.reservation.id,
            'phone_number': '254712345678'
        }

    @patch('payments.mpesa_utils.MpesaGateway.get_access_token')
    @patch('payments.mpesa_utils.MpesaGateway.initiate_stk_push')
    def test_initiate_payment_success(self, mock_stk_push, mock_get_token):
        # Mock successful responses
        mock_get_token.return_value = 'test_token'
        mock_stk_push.return_value = {
            'MerchantRequestID': 'test-merchant-id',
            'CheckoutRequestID': 'test-checkout-id',
            'ResponseCode': '0',
            'ResponseDescription': 'Success',
            'CustomerMessage': 'Success'
        }
        
        url = reverse('initiate-payment')
        response = self.client.post(url, self.valid_payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('transaction_reference', response.data)
        self.assertIn('merchant_request_id', response.data)
        self.assertEqual(response.data['status'], 'pending')
        
        # Verify transaction was created
        transaction = MpesaTransaction.objects.first()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.status, 'PENDING')
        self.assertEqual(transaction.reservation_id, self.reservation.id)

    def test_invalid_phone_number(self):
        invalid_payload = self.valid_payload.copy()
        invalid_payload['phone_number'] = '0712345678'  # Invalid format
        
        url = reverse('initiate-payment')
        response = self.client.post(url, invalid_payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone_number', response.data)

    @patch('payments.mpesa_utils.MpesaGateway.verify_transaction')
    def test_payment_status_check(self, mock_verify):
        # Create a test transaction
        transaction = MpesaTransaction.objects.create(
            reservation=self.reservation,
            transaction_type='C2B',
            transaction_reference='TEST-REF',
            amount=self.reservation.total_amount,
            phone_number='254712345678',
            status='PENDING'
        )
        
        # Mock successful verification
        mock_verify.return_value = {
            'ResultCode': '0',
            'ResultDesc': 'The service request is processed successfully.'
        }
        
        url = reverse('check-payment-status', kwargs={'transaction_ref': transaction.transaction_reference})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['transaction_reference'], 'TEST-REF')

    def test_payment_throttling(self):
        url = reverse('initiate-payment')
        
        # Make requests up to the limit
        for _ in range(10):
            self.client.post(url, self.valid_payload, format='json')
        
        # The next request should be throttled
        response = self.client.post(url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @patch('payments.mpesa_utils.MpesaGateway.get_access_token')
    @patch('payments.mpesa_utils.MpesaGateway.initiate_stk_push')
    def test_duplicate_pending_payment(self, mock_stk_push, mock_get_token):
        # Create a pending transaction
        MpesaTransaction.objects.create(
            reservation=self.reservation,
            transaction_type='C2B',
            transaction_reference='TEST-REF',
            amount=self.reservation.total_amount,
            phone_number='254712345678',
            status='PENDING'
        )
        
        url = reverse('initiate-payment')
        response = self.client.post(url, self.valid_payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        self.assertIn('already in progress', response.data['detail'])