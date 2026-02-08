"""
PayMongo Payment Integration Service
Handles GCash and other PayMongo payment methods
Official API Docs: https://developers.paymongo.com/docs
"""

import requests
import base64
import json
import logging
from decimal import Decimal
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


class PayMongoService:
    """Service class for PayMongo payment gateway integration"""
    
    # PayMongo API endpoints
    BASE_URL = "https://api.paymongo.com/v1"
    
    def __init__(self):
        self.secret_key = getattr(settings, 'PAYMONGO_SECRET_KEY', '')
        self.public_key = getattr(settings, 'PAYMONGO_PUBLIC_KEY', '')
        
        if not self.secret_key:
            logger.warning("PayMongo secret key not configured in settings.py")
    
    def _get_auth_header(self):
        """Generate Basic Auth header for PayMongo API"""
        auth_string = f"{self.secret_key}:"
        auth_bytes = auth_string.encode('ascii')
        base64_bytes = base64.b64encode(auth_bytes)
        base64_string = base64_bytes.decode('ascii')
        return f"Basic {base64_string}"
    
    def create_gcash_source(self, reservation, amount, description='Dorm Reservation Payment'):
        """
        Create a GCash payment source
        
        Args:
            reservation: Reservation object
            amount: Decimal amount to charge (will be converted to centavos)
            description: Payment description
            
        Returns:
            dict: Source data including checkout_url and source_id
        """
        if not self.secret_key:
            logger.error("PayMongo credentials not configured")
            return {
                'success': False,
                'error': 'Payment gateway is not configured. Please contact the administrator.',
                'details': 'Missing API credentials'
            }
        
        try:
            # Convert amount to centavos (integer)
            amount_in_centavos = int(amount * 100)
            
           # Build callback URLs (remove trailing slash to avoid double slashes)
            base_url = settings.SITE_URL.rstrip('/')
            success_url = base_url + reverse('dormitory:paymongo_success', kwargs={'reservation_id': reservation.id})
            failure_url = base_url + reverse('dormitory:paymongo_failure', kwargs={'reservation_id': reservation.id})
            
            # Prepare source data
            source_data = {
                "data": {
                    "attributes": {
                        "amount": amount_in_centavos,
                        "redirect": {
                            "success": success_url,
                            "failed": failure_url
                        },
                        "type": "gcash",
                        "currency": "PHP",
                        "billing": {
                            "name": reservation.tenant.get_full_name() or reservation.tenant.username,
                            "email": reservation.tenant.email,
                            "phone": reservation.tenant.contact_number or "09000000000"
                        },
                        "metadata": {
                            "reservation_id": str(reservation.id),
                            "dorm_id": str(reservation.dorm.id),
                            "tenant_id": str(reservation.tenant.id),
                            "description": description
                        }
                    }
                }
            }
            
            # Make API request
            headers = {
                'Content-Type': 'application/json',
                'Authorization': self._get_auth_header(),
            }
            
            logger.info(f"Creating GCash source for reservation {reservation.id}, amount: ₱{amount}")
            
            response = requests.post(
                f"{self.BASE_URL}/sources",
                json=source_data,
                headers=headers,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Log the full response for debugging
            logger.info(f"PayMongo source response: {json.dumps(result, indent=2)}")
            
            # Extract checkout URL
            checkout_url = result['data']['attributes']['redirect']['checkout_url']
            source_id = result['data']['id']
            
            logger.info(f"GCash source created successfully: {source_id}")
            logger.info(f"Checkout URL: {checkout_url}")
            
            return {
                'success': True,
                'source_id': source_id,
                'checkout_url': checkout_url,
                'status': result['data']['attributes']['status'],
                'amount': amount,
                'data': result
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"PayMongo API request failed: {str(e)}")
            error_detail = "Network error"
            
            if hasattr(e.response, 'text'):
                try:
                    error_data = e.response.json()
                    error_detail = error_data.get('errors', [{}])[0].get('detail', str(e))
                except:
                    error_detail = e.response.text[:200]
            
            return {
                'success': False,
                'error': 'Failed to create payment session',
                'details': error_detail
            }
        except Exception as e:
            logger.exception(f"Unexpected error creating GCash source: {str(e)}")
            return {
                'success': False,
                'error': 'An unexpected error occurred',
                'details': str(e)
            }
    
    def create_payment_from_source(self, source_id, amount, description='Dorm Reservation Payment'):
        """
        Create a payment from a chargeable source
        This is called after the user completes the GCash payment
        
        Args:
            source_id: The PayMongo source ID
            amount: Payment amount in PHP (will be converted to centavos)
            description: Payment description
            
        Returns:
            dict: Payment result
        """
        if not self.secret_key:
            return {
                'success': False,
                'error': 'Payment gateway not configured'
            }
        
        try:
            # Convert amount to centavos
            amount_in_centavos = int(Decimal(str(amount)) * 100)
            
            payment_data = {
                "data": {
                    "attributes": {
                        "amount": amount_in_centavos,
                        "source": {
                            "id": source_id,
                            "type": "source"
                        },
                        "currency": "PHP",
                        "description": description
                    }
                }
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': self._get_auth_header(),
            }
            
            logger.info(f"Creating payment from source: {source_id}, amount: ₱{amount}")
            logger.info(f"Payment data: {json.dumps(payment_data, indent=2)}")
            
            response = requests.post(
                f"{self.BASE_URL}/payments",
                json=payment_data,
                headers=headers,
                timeout=30
            )
            
            # Log response for debugging
            logger.info(f"Payment API response status: {response.status_code}")
            
            if not response.ok:
                error_text = response.text
                logger.error(f"Payment API error response: {error_text}")
                try:
                    error_data = response.json()
                    error_detail = error_data.get('errors', [{}])[0].get('detail', error_text)
                except:
                    error_detail = error_text
                return {
                    'success': False,
                    'error': 'Payment creation failed',
                    'details': error_detail
                }
            
            result = response.json()
            
            payment_id = result['data']['id']
            status = result['data']['attributes']['status']
            
            logger.info(f"Payment created: {payment_id}, status: {status}")
            
            return {
                'success': True,
                'payment_id': payment_id,
                'status': status,
                'data': result
            }
            
        except Exception as e:
            logger.exception(f"Error creating payment from source: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def retrieve_source(self, source_id):
        """
        Retrieve a source to check its status
        
        Args:
            source_id: The PayMongo source ID
            
        Returns:
            dict: Source data
        """
        try:
            headers = {
                'Authorization': self._get_auth_header(),
            }
            
            response = requests.get(
                f"{self.BASE_URL}/sources/{source_id}",
                headers=headers,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            return {
                'success': True,
                'status': result['data']['attributes']['status'],
                'data': result
            }
            
        except Exception as e:
            logger.exception(f"Error retrieving source: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def retrieve_payment(self, payment_id):
        """
        Retrieve a payment to check its status
        
        Args:
            payment_id: The PayMongo payment ID
            
        Returns:
            dict: Payment data
        """
        try:
            headers = {
                'Authorization': self._get_auth_header(),
            }
            
            response = requests.get(
                f"{self.BASE_URL}/payments/{payment_id}",
                headers=headers,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            return {
                'success': True,
                'status': result['data']['attributes']['status'],
                'data': result
            }
            
        except Exception as e:
            logger.exception(f"Error retrieving payment: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_webhook_signature(self, request_body, signature):
        """
        Verify PayMongo webhook signature
        
        Args:
            request_body: Raw request body (bytes)
            signature: Signature from X-Signature header
            
        Returns:
            bool: True if signature is valid
        """
        # TODO: Implement webhook signature verification
        # PayMongo uses HMAC SHA256 for webhook signatures
        # For now, we'll validate based on the webhook secret
        return True
    
    def create_checkout_session(self, reservation, payment_breakdown, description='Dorm Reservation'):
        """
        Create a checkout session with itemized breakdown (RECOMMENDED METHOD)
        This provides a hosted checkout page with professional UI
        
        Args:
            reservation: Reservation object
            payment_breakdown: Dict with pricing breakdown
            description: Session description
            
        Returns:
            dict: Checkout session data with checkout_url
        """
        if not self.secret_key:
            return {
                'success': False,
                'error': 'Payment gateway not configured'
            }
        
        try:
            # Build URLs
            base_url = settings.SITE_URL.rstrip('/')
            success_url = base_url + reverse('dormitory:checkout_success', 
                                            kwargs={'reservation_id': reservation.id})
            cancel_url = base_url + reverse('dormitory:payment_booking_intent',
                                           kwargs={'reservation_id': reservation.id})
            
            # Build line items for itemized display
            line_items = []
            
            # Base rent
            line_items.append({
                "name": f"{reservation.dorm.name} - Monthly Rent",
                "quantity": 1,
                "amount": int(Decimal(str(payment_breakdown['base_price'])) * 100),
                "currency": "PHP",
                "description": "Monthly rental fee"
            })
            
            # Deposit
            if payment_breakdown.get('deposit', 0) > 0:
                line_items.append({
                    "name": f"Security Deposit ({payment_breakdown.get('deposit_months', 2)} months)",
                    "quantity": 1,
                    "amount": int(Decimal(str(payment_breakdown['deposit'])) * 100),
                    "currency": "PHP",
                    "description": "Refundable security deposit"
                })
            
            # Advance
            if payment_breakdown.get('advance', 0) > 0:
                line_items.append({
                    "name": f"Advance Payment ({payment_breakdown.get('advance_months', 1)} month)",
                    "quantity": 1,
                    "amount": int(Decimal(str(payment_breakdown['advance'])) * 100),
                    "currency": "PHP",
                    "description": "Advance rental payment"
                })
            
            # Processing fee
            if payment_breakdown.get('processing_fee', 0) > 0:
                line_items.append({
                    "name": f"Processing Fee ({payment_breakdown.get('processing_fee_percent', 2.5)}%)",
                    "quantity": 1,
                    "amount": int(round(Decimal(str(payment_breakdown['processing_fee'])) * 100)),
                    "currency": "PHP",
                    "description": "Payment processing fee"
                })
            
            # Prepare checkout session data
            checkout_data = {
                "data": {
                    "attributes": {
                        "send_email_receipt": True,
                        "show_description": True,
                        "show_line_items": True,
                        "description": description,
                        "line_items": line_items,
                        "payment_method_types": ["gcash", "paymaya", "card"],
                        "success_url": success_url,
                        "cancel_url": cancel_url,
                        "billing": {
                            "name": reservation.tenant.get_full_name() or reservation.tenant.username,
                            "email": reservation.tenant.email,
                            "phone": ("0" + reservation.tenant.contact_number if reservation.tenant.contact_number and not reservation.tenant.contact_number.startswith('0') else reservation.tenant.contact_number) or "09000000000"
                        },
                        "metadata": {
                            "reservation_id": str(reservation.id),
                            "dorm_id": str(reservation.dorm.id),
                            "tenant_id": str(reservation.tenant.id),
                            "dorm_name": reservation.dorm.name
                        }
                    }
                }
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': self._get_auth_header(),
            }
            
            logger.info(f"Creating checkout session for reservation {reservation.id}")
            logger.info(f"Total amount: ₱{payment_breakdown['total']}")
            logger.info(f"Line items: {len(line_items)} items")
            logger.info(f"Checkout data: {json.dumps(checkout_data, indent=2)}")
            
            response = requests.post(
                f"{self.BASE_URL}/checkout_sessions",
                json=checkout_data,
                headers=headers,
                timeout=30
            )
            
            if not response.ok:
                error_text = response.text
                logger.error(f"Checkout session error: {error_text}")
                try:
                    error_data = response.json()
                    error_detail = error_data.get('errors', [{}])[0].get('detail', error_text)
                except:
                    error_detail = error_text
                return {
                    'success': False,
                    'error': 'Failed to create checkout session',
                    'details': error_detail
                }
            
            result = response.json()
            
            session_id = result['data']['id']
            checkout_url = result['data']['attributes']['checkout_url']
            
            logger.info(f"Checkout session created: {session_id}")
            logger.info(f"Checkout URL: {checkout_url}")
            
            return {
                'success': True,
                'session_id': session_id,
                'checkout_url': checkout_url,
                'data': result
            }
            
        except Exception as e:
            logger.exception(f"Error creating checkout session: {str(e)}")
            return {
                'success': False,
                'error': 'An unexpected error occurred',
                'details': str(e)
            }
    
    def retrieve_checkout_session(self, session_id):
        """
        Retrieve checkout session details
        
        Args:
            session_id: The checkout session ID
            
        Returns:
            dict: Session data with payment status
        """
        try:
            headers = {
                'Authorization': self._get_auth_header(),
            }
            
            logger.info(f"Retrieving checkout session: {session_id}")
            
            response = requests.get(
                f"{self.BASE_URL}/checkout_sessions/{session_id}",
                headers=headers,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Checkout session response: {json.dumps(result, indent=2)}")
            
            # Get payment status from the payments array or payment_intent
            # PayMongo Checkout Sessions include a 'payments' array when payment is made
            payments = result['data']['attributes'].get('payments', [])
            
            if payments and len(payments) > 0:
                # Get status from the first (most recent) payment
                payment_status = payments[0]['attributes']['status']
                logger.info(f"Payment found in payments array with status: {payment_status}")
            else:
                # Fallback: check payment_intent if no payments array yet
                payment_intent = result['data']['attributes'].get('payment_intent')
                if payment_intent:
                    payment_status = payment_intent.get('attributes', {}).get('status', 'pending')
                    logger.info(f"Payment status from payment_intent: {payment_status}")
                else:
                    # No payment made yet
                    payment_status = 'awaiting_payment_method'
                    logger.info(f"No payment found, status: {payment_status}")
            
            return {
                'success': True,
                'status': payment_status,
                'data': result
            }
            
        except Exception as e:
            logger.exception(f"Error retrieving checkout session: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Global service instance
paymongo_service = PayMongoService()
