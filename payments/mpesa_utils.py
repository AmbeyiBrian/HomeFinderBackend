import requests
import base64
from datetime import datetime
import json
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class MpesaGateway:
    def __init__(self):
        self.business_shortcode = settings.MPESA_SHORTCODE
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.passkey = settings.MPESA_PASSKEY
        if settings.DEBUG:
            self.base_url = "https://sandbox.safaricom.co.ke"
        else:
            self.base_url = "https://api.safaricom.co.ke"
            
    def get_access_token(self):
        """Get M-Pesa API access token"""
        try:
            url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
            auth = base64.b64encode(f"{self.consumer_key}:{self.consumer_secret}".encode()).decode()
            headers = {"Authorization": f"Basic {auth}"}
            
            logger.info(f"Requesting access token from: {url}")
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            logger.info("Successfully obtained access token")
            return result.get('access_token')
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting access token: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response content: {e.response.text}")
            raise

    def generate_password(self, timestamp):
        """Generate M-Pesa API password"""
        data = f"{self.business_shortcode}{self.passkey}{timestamp}"
        return base64.b64encode(data.encode()).decode()

    def initiate_stk_push(self, phone_number, amount, reference, callback_url):
        """Initiate STK Push payment"""
        try:
            # Ensure callback URL uses HTTPS
            if not callback_url.startswith('https://'):
                logger.warning(f"Callback URL {callback_url} does not use HTTPS")
                if settings.DEBUG:
                    # In development, we might need to use HTTP
                    logger.info("Running in DEBUG mode, proceeding with HTTP callback URL")
                else:
                    raise ValueError("Callback URL must use HTTPS in production")

            access_token = self.get_access_token()
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self.generate_password(timestamp)
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # In development mode, we'll use a special callback URL that our system recognizes
            if settings.DEBUG:
                logger.info("Running in development mode - using mock callback")
                callback_url = "https://api.safaricom.co.ke/mock-callback"  # This URL won't actually be called
            
            payload = {
                "BusinessShortCode": self.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": phone_number,
                "PartyB": self.business_shortcode,
                "PhoneNumber": phone_number,
                "CallBackURL": callback_url,
                "AccountReference": reference,
                "TransactionDesc": f"Property Reservation Payment {reference}"
            }
            
            logger.info(f"Initiating STK push for reference: {reference}")
            logger.debug(f"STK push payload: {json.dumps(payload, indent=2)}")
            
            url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            response = requests.post(url, json=payload, headers=headers)
            
            try:
                response.raise_for_status()
                result = response.json()
                logger.info(f"STK push initiated successfully: {json.dumps(result, indent=2)}")
                
                # Validate response structure
                if 'CheckoutRequestID' not in result:
                    logger.error(f"Missing CheckoutRequestID in response: {result}")
                    raise ValueError("Invalid response: Missing CheckoutRequestID")
                    
                return result
                
            except requests.exceptions.HTTPError as he:
                logger.error(f"HTTP error in STK push: {str(he)}")
                if hasattr(response, 'text'):
                    logger.error(f"Error response content: {response.text}")
                raise
                
        except Exception as e:
            logger.error(f"Error initiating STK push: {str(e)}")
            logger.exception(e)  # Log full traceback
            raise

    def verify_transaction(self, checkout_request_id):
        """Verify transaction status"""
        try:
            access_token = self.get_access_token()
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            password = self.generate_password(timestamp)
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "BusinessShortCode": self.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }
            
            logger.info(f"Verifying transaction status for checkout request: {checkout_request_id}")
            
            url = f"{self.base_url}/mpesa/stkpushquery/v1/query"
            response = requests.post(url, json=payload, headers=headers)
            
            try:
                response.raise_for_status()
                result = response.json()
                logger.info(f"Transaction verification result: {json.dumps(result, indent=2)}")
                return result
            except requests.exceptions.HTTPError as he:
                logger.error(f"HTTP error in transaction verification: {str(he)}")
                if hasattr(response, 'text'):
                    logger.error(f"Error response content: {response.text}")
                raise
                
        except Exception as e:
            logger.error(f"Error verifying transaction: {str(e)}")
            logger.exception(e)
            raise