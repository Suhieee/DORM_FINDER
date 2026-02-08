"""
MonGo Pay Integration Service
Handles payment gateway operations including:
- Creating payment sessions
- Verifying webhook signatures
- Processing payment callbacks
- Handling refunds
"""

import requests
import hashlib
import hmac
import json
import logging
from decimal import Decimal
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


class MongoPayService:
    """Service class for MonGo Pay payment gateway integration"""
    
    # MonGo Pay API endpoints (TEST mode) - LEGACY/UNUSED
    # Using PayMongo instead for GCash/PayMaya/Cards
    BASE_URL = getattr(settings, 'MONGOPAY_BASE_URL', 'https://api.mongopay.test')
    API_KEY = getattr(settings, 'MONGOPAY_API_KEY', '')
    SECRET_KEY = getattr(settings, 'MONGOPAY_SECRET_KEY', '')
    MERCHANT_ID = getattr(settings, 'MONGOPAY_MERCHANT_ID', '')
    
    def __init__(self):
        # MonGo Pay is optional - using PayMongo as primary payment gateway
        pass
    
    def create_payment_session(self, reservation, amount, description='Dorm Reservation Payment'):
        """
        Create a payment session with MonGo Pay
        
        Args:
            reservation: Reservation object
            amount: Decimal amount to charge
            description: Payment description
            
        Returns:
            dict: Payment session data including checkout_url and session_id
        """
        # Check if credentials are configured
        if not all([self.API_KEY, self.SECRET_KEY, self.MERCHANT_ID]):
            logger.info("MonGo Pay not configured - using PayMongo for payments")
            return {
                'success': False,
                'error': 'Payment gateway is not configured. Please contact the administrator or use manual payment method.',
                'details': 'Missing API credentials'
            }
        
        try:
            # Build callback URLs
            success_url = settings.SITE_URL + reverse('dormitory:payment_success', 
                                                      kwargs={'reservation_id': reservation.id})
            failure_url = settings.SITE_URL + reverse('dormitory:payment_failure', 
                                                      kwargs={'reservation_id': reservation.id})
            webhook_url = settings.SITE_URL + reverse('dormitory:payment_webhook')
            
            # Prepare payment data
            payment_data = {
                'merchant_id': self.MERCHANT_ID,
                'amount': str(amount),
                'currency': 'PHP',  # Philippine Peso
                'description': description,
                'reference_id': f"RES-{reservation.id}",
                'customer': {
                    'name': reservation.tenant.get_full_name() or reservation.tenant.username,
                    'email': reservation.tenant.email,
                    'phone': reservation.tenant.contact_number or '',
                },
                'redirect_urls': {
                    'success': success_url,
                    'failure': failure_url,
                },
                'webhook_url': webhook_url,
                'metadata': {
                    'reservation_id': reservation.id,
                    'dorm_id': reservation.dorm.id,
                    'tenant_id': reservation.tenant.id,
                }
            }
            
            # Generate signature
            signature = self._generate_signature(payment_data)
            
            # Make API request
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': self.API_KEY,
                'X-Signature': signature,
            }
            
            response = requests.post(
                f"{self.BASE_URL}/v1/payments/create",
                json=payment_data,
                headers=headers,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Payment session created for reservation {reservation.id}: {result.get('session_id')}")
            
            return {
                'success': True,
                'session_id': result.get('session_id'),
                'checkout_url': result.get('checkout_url'),
                'expires_at': result.get('expires_at'),
            }
            
        except requests.RequestException as e:
            logger.error(f"MonGo Pay API error: {str(e)}")
            return {
                'success': False,
                'error': 'Payment gateway error. Please try again later.',
                'details': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error creating payment session: {str(e)}")
            return {
                'success': False,
                'error': 'An unexpected error occurred.',
                'details': str(e)
            }
    
    def verify_webhook_signature(self, payload, signature):
        """
        Verify webhook signature from MonGo Pay
        
        Args:
            payload: Raw request body (bytes or string)
            signature: Signature from X-Signature header
            
        Returns:
            bool: True if signature is valid
        """
        try:
            # Convert payload to bytes if needed
            if isinstance(payload, str):
                payload = payload.encode('utf-8')
            
            # Calculate expected signature
            expected_signature = hmac.new(
                self.SECRET_KEY.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures (constant-time comparison to prevent timing attacks)
            return hmac.compare_digest(expected_signature, signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False
    
    def process_webhook_data(self, webhook_data):
        """
        Process webhook data from MonGo Pay
        
        Args:
            webhook_data: dict of webhook payload
            
        Returns:
            dict: Processed payment information
        """
        try:
            event_type = webhook_data.get('event_type')
            payment_data = webhook_data.get('data', {})
            
            return {
                'event_type': event_type,
                'transaction_id': payment_data.get('transaction_id'),
                'reference_id': payment_data.get('reference_id'),
                'amount': Decimal(payment_data.get('amount', '0')),
                'currency': payment_data.get('currency'),
                'status': payment_data.get('status'),
                'paid_at': payment_data.get('paid_at'),
                'metadata': payment_data.get('metadata', {}),
            }
        except Exception as e:
            logger.error(f"Error processing webhook data: {str(e)}")
            return None
    
    def initiate_refund(self, transaction_id, amount, reason=''):
        """
        Initiate a refund through MonGo Pay
        
        Args:
            transaction_id: Original payment transaction ID
            amount: Amount to refund
            reason: Reason for refund
            
        Returns:
            dict: Refund result
        """
        try:
            refund_data = {
                'merchant_id': self.MERCHANT_ID,
                'transaction_id': transaction_id,
                'amount': str(amount),
                'reason': reason,
            }
            
            # Generate signature
            signature = self._generate_signature(refund_data)
            
            # Make API request
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': self.API_KEY,
                'X-Signature': signature,
            }
            
            response = requests.post(
                f"{self.BASE_URL}/v1/refunds/create",
                json=refund_data,
                headers=headers,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Refund initiated for transaction {transaction_id}: {result.get('refund_id')}")
            
            return {
                'success': True,
                'refund_id': result.get('refund_id'),
                'status': result.get('status'),
                'refunded_amount': result.get('amount'),
            }
            
        except requests.RequestException as e:
            logger.error(f"MonGo Pay refund error: {str(e)}")
            return {
                'success': False,
                'error': 'Refund processing error. Please contact support.',
                'details': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error initiating refund: {str(e)}")
            return {
                'success': False,
                'error': 'An unexpected error occurred.',
                'details': str(e)
            }
    
    def get_payment_status(self, transaction_id):
        """
        Get payment status from MonGo Pay
        
        Args:
            transaction_id: Payment transaction ID
            
        Returns:
            dict: Payment status information
        """
        try:
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': self.API_KEY,
            }
            
            response = requests.get(
                f"{self.BASE_URL}/v1/payments/{transaction_id}",
                headers=headers,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            return {
                'success': True,
                'transaction_id': result.get('transaction_id'),
                'status': result.get('status'),
                'amount': result.get('amount'),
                'paid_at': result.get('paid_at'),
            }
            
        except requests.RequestException as e:
            logger.error(f"Error fetching payment status: {str(e)}")
            return {
                'success': False,
                'error': 'Could not fetch payment status.',
                'details': str(e)
            }
    
    def _generate_signature(self, data):
        """
        Generate HMAC signature for API requests
        
        Args:
            data: dict of data to sign
            
        Returns:
            str: HMAC signature
        """
        # Sort keys and create canonical string
        sorted_data = json.dumps(data, sort_keys=True, separators=(',', ':'))
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.SECRET_KEY.encode('utf-8'),
            sorted_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature


# Singleton instance
mongo_pay_service = MongoPayService()
