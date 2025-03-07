from rest_framework import serializers
from .models import MpesaTransaction
from properties.serializers import ReservationSerializer
import re

def validate_phone_number(value):
    """Validate Kenyan phone number format"""
    pattern = r'^254[17]\d{8}$'
    if not re.match(pattern, value):
        raise serializers.ValidationError(
            'Phone number must be in format 254XXXXXXXXX (12 digits starting with 254)'
        )
    return value

class MpesaPaymentSerializer(serializers.Serializer):
    """Serializer for initiating M-Pesa payment"""
    reservation_id = serializers.IntegerField()
    phone_number = serializers.CharField(validators=[validate_phone_number])

class MpesaTransactionSerializer(serializers.ModelSerializer):
    """Serializer for M-Pesa transaction details"""
    reservation = ReservationSerializer(read_only=True)
    
    class Meta:
        model = MpesaTransaction
        fields = [
            'id',
            'reservation',
            'transaction_reference',
            'amount',
            'phone_number',
            'mpesa_receipt_number',
            'transaction_date',
            'status',
            'result_code',
            'result_description'
        ]
        read_only_fields = [
            'transaction_reference',
            'mpesa_receipt_number',
            'status',
            'result_code',
            'result_description'
        ]