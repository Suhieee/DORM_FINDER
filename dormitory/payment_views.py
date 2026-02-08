"""
Payment Gateway Views
Handles payment flow including booking intent, payment callbacks, and webhooks
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from decimal import Decimal
import json
import logging

from .models import Reservation, Dorm, PaymentConfiguration
from .models_transaction import TransactionLog
from .payment_service import mongo_pay_service
from .payment_paymongo import paymongo_service
from accounts.models import Notification

logger = logging.getLogger(__name__)


def notify_user(user, message, related_object_id=None):
    """Create a notification for a user"""
    if not user:
        return
    Notification.objects.create(
        user=user,
        message=message,
        related_object_id=related_object_id
    )


@login_required
@require_http_methods(["GET", "POST"])
def payment_booking_intent(request, reservation_id):
    """
    Create a booking intent and display payment breakdown
    User can choose payment method: gateway or manual upload
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('dorm', 'tenant', 'dorm__payment_config'),
        id=reservation_id,
        tenant=request.user
    )
    
    # Check reservation status
    if reservation.status not in ['pending', 'pending_payment']:
        messages.error(request, "This reservation cannot be paid at this time.")
        return redirect('dormitory:tenant_reservations')
    
    # Get or create payment configuration
    try:
        payment_config = reservation.dorm.payment_config
    except PaymentConfiguration.DoesNotExist:
        # Create default configuration
        payment_config = PaymentConfiguration.objects.create(
            dorm=reservation.dorm,
            deposit_months=2,
            advance_months=1,
            processing_fee_percent=2.5
        )
    
    # Calculate payment breakdown
    payment_breakdown = payment_config.calculate_total_amount()
    partial_payment_amount = payment_config.get_partial_payment_amount()
    
    # Handle payment method selection
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        
        if payment_method == 'gateway':
            # Proceed with payment gateway
            return redirect('dormitory:payment_gateway_checkout', reservation_id=reservation.id)
        
        elif payment_method == 'gcash':
            # Proceed with PayMongo Checkout (supports GCash, PayMaya, Cards)
            return redirect('dormitory:paymongo_checkout', reservation_id=reservation.id)
        
        elif payment_method == 'manual':
            # Allow manual upload
            reservation.payment_method = 'manual'
            reservation.status = 'pending_payment'
            reservation.save()
            messages.info(request, "Please upload your payment proof.")
            return redirect('dormitory:tenant_reservations')
        
        elif payment_method == 'cash':
            # Cash payment arrangement
            reservation.payment_method = 'cash'
            reservation.status = 'pending_payment'
            reservation.save()
            messages.info(request, "Cash payment arranged. Please coordinate with the landlord.")
            return redirect('dormitory:tenant_reservations')
    
    context = {
        'reservation': reservation,
        'payment_config': payment_config,
        'payment_breakdown': payment_breakdown,
        'partial_payment_amount': partial_payment_amount,
        'accepts_gateway': payment_config.accepts_gateway,
        'accepts_manual': payment_config.accepts_manual,
        'accepts_cash': payment_config.accepts_cash,
        'accepts_partial': payment_config.accepts_partial_payment,
    }
    
    return render(request, 'dormitory/payment_booking_intent.html', context)


@login_required
def payment_gateway_checkout(request, reservation_id):
    """
    Create payment session with MonGo Pay and redirect to checkout
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('dorm', 'tenant', 'dorm__payment_config'),
        id=reservation_id,
        tenant=request.user
    )
    
    # Check reservation status
    if reservation.status not in ['pending', 'pending_payment']:
        messages.error(request, "This reservation cannot be paid at this time.")
        return redirect('dormitory:tenant_reservations')
    
    # Check if already has a payment intent
    if reservation.payment_intent_id and reservation.payment_status == 'processing':
        messages.warning(request, "A payment is already in progress for this reservation.")
        return redirect('dormitory:tenant_reservations')
    
    # Get payment configuration
    try:
        payment_config = reservation.dorm.payment_config
        payment_breakdown = payment_config.calculate_total_amount()
        total_amount = Decimal(str(payment_breakdown['total']))
    except PaymentConfiguration.DoesNotExist:
        messages.error(request, "Payment configuration not found for this dorm.")
        return redirect('dormitory:tenant_reservations')
    
    # Create payment session with MonGo Pay
    result = mongo_pay_service.create_payment_session(
        reservation=reservation,
        amount=total_amount,
        description=f"Reservation for {reservation.dorm.name}"
    )
    
    if result['success']:
        # Update reservation with payment session info
        reservation.payment_intent_id = result['session_id']
        reservation.payment_method = 'gateway'
        reservation.payment_status = 'processing'
        reservation.payment_amount = total_amount
        reservation.save()
        
        # Log transaction
        TransactionLog.objects.create(
            landlord=reservation.dorm.landlord,
            tenant=request.user,
            amount=total_amount,
            transaction_type='payment_received',
            description=f"Payment gateway checkout initiated for {reservation.dorm.name}",
            status='pending',
            dorm=reservation.dorm,
            reservation=reservation,
            metadata={
                'payment_method': 'mongo_pay',
                'transaction_id': result['session_id']
            }
        )
        
        # Redirect to MonGo Pay checkout
        return redirect(result['checkout_url'])
    else:
        messages.error(request, f"Payment gateway error: {result.get('error')}")
        return redirect('dormitory:payment_booking_intent', reservation_id=reservation.id)


@csrf_exempt
@require_POST
def payment_webhook(request):
    """
    Webhook endpoint for MonGo Pay payment confirmations
    This endpoint receives POST requests from MonGo Pay when payments are completed
    """
    try:
        # Get signature from headers
        signature = request.headers.get('X-Signature', '')
        
        # Verify signature
        if not mongo_pay_service.verify_webhook_signature(request.body, signature):
            logger.warning("Invalid webhook signature received")
            return HttpResponse(status=403)
        
        # Parse webhook data
        webhook_data = json.loads(request.body)
        payment_info = mongo_pay_service.process_webhook_data(webhook_data)
        
        if not payment_info:
            logger.error("Failed to process webhook data")
            return HttpResponse(status=400)
        
        # Extract reservation ID from reference_id
        reference_id = payment_info.get('reference_id', '')
        if reference_id.startswith('RES-'):
            reservation_id = int(reference_id.replace('RES-', ''))
        else:
            logger.error(f"Invalid reference_id format: {reference_id}")
            return HttpResponse(status=400)
        
        # Get reservation
        try:
            reservation = Reservation.objects.select_related('dorm', 'tenant', 'dorm__landlord').get(
                id=reservation_id
            )
        except Reservation.DoesNotExist:
            logger.error(f"Reservation {reservation_id} not found")
            return HttpResponse(status=404)
        
        # Process payment based on status
        with transaction.atomic():
            event_type = payment_info['event_type']
            
            if event_type == 'payment.success':
                # Payment successful
                reservation.payment_status = 'success'
                reservation.payment_verified_at = timezone.now()
                reservation.has_paid_reservation = True
                # Only set to confirmed if not already in a later stage
                if reservation.status not in ['occupied', 'completed']:
                    reservation.status = 'confirmed'
                reservation.payment_amount = payment_info['amount']
                reservation.save()
                
                # Update transaction log
                TransactionLog.objects.filter(
                    reservation=reservation,
                    status='pending'
                ).update(
                    status='success'
                )
                
                # Notify tenant
                notify_user(
                    user=reservation.tenant,
                    message=f"Payment confirmed for {reservation.dorm.name}! Your reservation is now secured.",
                    related_object_id=reservation.id
                )
                
                # Notify landlord
                notify_user(
                    user=reservation.dorm.landlord,
                    message=f"New confirmed reservation for {reservation.dorm.name} from {reservation.tenant.get_full_name() or reservation.tenant.username}. Payment verified.",
                    related_object_id=reservation.id
                )
                
                logger.info(f"Payment successful for reservation {reservation.id}")
                
            elif event_type == 'payment.failed':
                # Payment failed
                reservation.payment_status = 'failed'
                reservation.save()
                
                # Update transaction log
                TransactionLog.objects.filter(
                    reservation=reservation,
                    status='pending'
                ).update(status='failed')
                
                # Notify tenant
                notify_user(
                    user=reservation.tenant,
                    message=f"Payment failed for {reservation.dorm.name}. Please try again or use a different payment method.",
                    related_object_id=reservation.id
                )
                
                logger.warning(f"Payment failed for reservation {reservation.id}")
            
            else:
                logger.info(f"Unhandled webhook event: {event_type}")
        
        # Return 200 OK to acknowledge receipt
        return HttpResponse(status=200)
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook payload")
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return HttpResponse(status=500)


@login_required
def payment_success(request, reservation_id):
    """
    Callback view when payment is successful
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('dorm', 'tenant'),
        id=reservation_id,
        tenant=request.user
    )
    
    context = {
        'reservation': reservation,
        'payment_status': reservation.payment_status,
    }
    
    # Add success message
    if reservation.payment_status == 'success':
        messages.success(request, "Payment successful! Your reservation is confirmed.")
    else:
        messages.info(request, "Payment is being processed. You will be notified once confirmed.")
    
    return render(request, 'dormitory/payment_success.html', context)


@login_required
def payment_failure(request, reservation_id):
    """
    Callback view when payment fails
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('dorm', 'tenant'),
        id=reservation_id,
        tenant=request.user
    )
    
    context = {
        'reservation': reservation,
        'payment_status': reservation.payment_status,
    }
    
    messages.error(request, "Payment failed. Please try again or use a different payment method.")
    
    return render(request, 'dormitory/payment_failure.html', context)


@login_required
@require_POST
def cancel_reservation_with_refund(request, reservation_id):
    """
    Cancel a reservation and process refund if applicable
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('dorm', 'tenant', 'dorm__payment_config', 'dorm__landlord'),
        id=reservation_id,
        tenant=request.user
    )
    
    # Check if cancellation is allowed
    if reservation.status not in ['confirmed', 'pending_payment']:
        messages.error(request, "This reservation cannot be cancelled.")
        return redirect('dormitory:tenant_reservations')
    
    # Get cancellation reason
    cancellation_reason = request.POST.get('cancellation_reason', 'User requested cancellation')
    
    # Calculate refund if payment was made
    refund_amount = Decimal('0')
    if reservation.has_paid_reservation and reservation.payment_status == 'success':
        try:
            payment_config = reservation.dorm.payment_config
            if reservation.move_in_date:
                days_before_movein = (reservation.move_in_date - timezone.now().date()).days
                refund_amount = Decimal(str(payment_config.calculate_refund(days_before_movein)))
            else:
                # No move-in date set, apply default refund policy
                refund_amount = Decimal(str(payment_config.calculate_refund(7)))  # Assume 7+ days
        except PaymentConfiguration.DoesNotExist:
            refund_amount = reservation.payment_amount or Decimal('0')
    
    # Process refund if applicable
    if refund_amount > 0 and reservation.payment_intent_id:
        refund_result = mongo_pay_service.initiate_refund(
            transaction_id=reservation.payment_intent_id,
            amount=refund_amount,
            reason=cancellation_reason
        )
        
        if refund_result['success']:
            reservation.refund_amount = refund_amount
            reservation.refund_reason = cancellation_reason
            reservation.refund_processed_at = timezone.now()
            reservation.payment_status = 'refunded'
            
            # Log refund transaction
            TransactionLog.objects.create(
                landlord=reservation.dorm.landlord,
                tenant=request.user,
                amount=refund_amount,
                transaction_type='reservation_cancelled',
                description=f"Refund processed for cancelled reservation",
                status='success',
                dorm=reservation.dorm,
                reservation=reservation,
                metadata={
                    'payment_method': 'mongo_pay',
                    'refund_id': refund_result['refund_id'],
                    'refund_amount': str(refund_amount)
                }
            )
            
            messages.success(request, f"Reservation cancelled. Refund of ₱{refund_amount:,.2f} will be processed within 5-7 business days.")
        else:
            messages.warning(request, "Reservation cancelled but refund processing failed. Please contact support.")
    else:
        messages.success(request, "Reservation cancelled successfully.")
    
    # Update reservation status
    reservation.status = 'cancelled'
    reservation.cancellation_reason = cancellation_reason
    
    # Release bed/unit
    if reservation.dorm.accommodation_type == 'whole_unit':
        reservation.dorm.available_beds = reservation.dorm.max_occupants
    else:
        if reservation.dorm.available_beds < reservation.dorm.total_beds:
            reservation.dorm.available_beds += 1
    reservation.dorm.save()
    
    reservation.save()
    
    # Notify landlord
    notify_user(
        user=reservation.dorm.landlord,
        message=f"Reservation cancelled by {reservation.tenant.get_full_name() or reservation.tenant.username} for {reservation.dorm.name}. Refund: ₱{refund_amount:,.2f}",
        related_object_id=reservation.id
    )
    
    return redirect('dormitory:tenant_reservations')


# ============================================
# PayMongo GCash Payment Views
# ============================================

@login_required
def paymongo_gcash_checkout(request, reservation_id):
    """
    Create PayMongo GCash payment source and redirect to checkout
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('dorm', 'tenant', 'dorm__payment_config'),
        id=reservation_id,
        tenant=request.user
    )
    
    # Check reservation status
    if reservation.status not in ['pending', 'pending_payment']:
        messages.error(request, "This reservation cannot be paid at this time.")
        return redirect('dormitory:tenant_reservations')
    
    # Reset payment status if it was processing (allow retry)
    if reservation.payment_status == 'processing':
        logger.info(f"Resetting payment status for reservation {reservation.id} to allow retry")
        reservation.payment_status = 'pending'
        reservation.payment_intent_id = None
        reservation.save()
    
    # Get payment configuration
    try:
        payment_config = reservation.dorm.payment_config
        payment_breakdown = payment_config.calculate_total_amount()
        total_amount = Decimal(str(payment_breakdown['total']))
    except PaymentConfiguration.DoesNotExist:
        messages.error(request, "Payment configuration not found for this dorm.")
        return redirect('dormitory:tenant_reservations')
    
    # Create GCash payment source with PayMongo
    result = paymongo_service.create_gcash_source(
        reservation=reservation,
        amount=total_amount,
        description=f"Reservation for {reservation.dorm.name}"
    )
    
    if result['success']:
        # Update reservation with payment source info
        reservation.payment_intent_id = result['source_id']
        reservation.payment_method = 'gcash'
        reservation.payment_status = 'processing'
        reservation.payment_amount = total_amount
        reservation.save()
        
        # Log transaction
        TransactionLog.objects.create(
            landlord=reservation.dorm.landlord,
            tenant=request.user,
            amount=total_amount,
            transaction_type='payment_received',
            description=f"GCash payment initiated for {reservation.dorm.name}",
            status='pending',
            dorm=reservation.dorm,
            reservation=reservation,
            metadata={
                'payment_method': 'gcash_paymongo',
                'source_id': result['source_id']
            }
        )
        
        # Show redirect page with checkout URL
        checkout_url = result['checkout_url']
        logger.info(f"Redirecting to GCash checkout for reservation {reservation.id}")
        logger.info(f"Checkout URL: {checkout_url}")
        
        # Use a template to show the redirect page
        return render(request, 'dormitory/gcash_redirect.html', {
            'checkout_url': checkout_url,
            'reservation': reservation,
            'amount': total_amount
        })
    else:
        messages.error(request, f"GCash payment error: {result.get('error', 'Unknown error')}")
        logger.error(f"GCash payment error for reservation {reservation.id}: {result.get('details')}")
        return redirect('dormitory:payment_booking_intent', reservation_id=reservation.id)


@login_required
def paymongo_success(request, reservation_id):
    """
    Handle successful GCash payment callback from PayMongo
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('dorm', 'tenant', 'dorm__payment_config'),
        id=reservation_id,
        tenant=request.user
    )
    
    source_id = reservation.payment_intent_id
    logger.info(f"PayMongo success callback for reservation {reservation.id}, source_id: {source_id}")
    
    if not source_id:
        messages.warning(request, "No payment source found. Please try again.")
        return redirect('dormitory:tenant_reservations')
    
    # Verify the source status
    source_result = paymongo_service.retrieve_source(source_id)
    logger.info(f"Source status: {source_result.get('status')}")
    
    if source_result.get('success'):
        source_status = source_result.get('status')
        
        # Check if source is chargeable or paid (user completed payment)
        if source_status == 'chargeable' or source_status == 'paid':
            # For GCash sources, when status is 'chargeable' or 'paid', payment is complete
            # No need to create a separate payment object
            with transaction.atomic():
                reservation.payment_status = 'paid'
                reservation.has_paid_reservation = True
                reservation.payment_verified_at = timezone.now()
                # Only set to confirmed if not already in a later stage
                if reservation.status not in ['occupied', 'completed']:
                    reservation.status = 'confirmed'
                reservation.payment_date = timezone.now()
                reservation.save()
                
                # Update transaction log
                TransactionLog.objects.filter(
                    reservation=reservation,
                    status='pending'
                ).update(status='success')
            
            # Notify tenant and landlord
            notify_user(
                user=reservation.tenant,
                message=f"Payment successful! Your reservation for {reservation.dorm.name} is confirmed.",
                related_object_id=reservation.id
            )
            notify_user(
                user=reservation.dorm.landlord,
                message=f"Payment received for {reservation.dorm.name} from {reservation.tenant.get_full_name() or reservation.tenant.username}",
                related_object_id=reservation.id
            )
            
            messages.success(request, "✅ Payment successful! Your reservation is confirmed.")
            logger.info(f"GCash payment successful for reservation {reservation.id}")
            return redirect('dormitory:tenant_reservations')
        
        elif source_status == 'pending':
            # User hasn't completed payment yet
            logger.warning(f"Source still pending for reservation {reservation.id}")
            messages.warning(request, "Payment not completed yet. Please complete the payment in your GCash app.")
            return redirect('dormitory:tenant_reservations')
        
        elif source_status == 'cancelled' or source_status == 'expired':
            # Payment was cancelled or expired
            reservation.payment_status = 'failed'
            reservation.save()
            messages.error(request, "Payment was cancelled or expired. Please try again.")
            return redirect('dormitory:payment_booking_intent', reservation_id=reservation.id)
    
    # If we get here, something went wrong
    logger.error(f"Source retrieval failed: {source_result}")
    messages.warning(request, "Payment is being processed. Please wait for confirmation or contact support if this persists.")
    return redirect('dormitory:tenant_reservations')


@login_required
def paymongo_failure(request, reservation_id):
    """
    Handle failed GCash payment callback from PayMongo
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('dorm', 'tenant'),
        id=reservation_id,
        tenant=request.user
    )
    
    # Update payment status
    reservation.payment_status = 'failed'
    reservation.save()
    
    # Update transaction log
    if reservation.payment_intent_id:
        TransactionLog.objects.filter(
            reservation=reservation,
            status='pending'
        ).update(status='failed')
    
    messages.error(request, "Payment failed or was cancelled. Please try again.")
    logger.warning(f"GCash payment failed for reservation {reservation.id}")
    
    return redirect('dormitory:payment_booking_intent', reservation_id=reservation.id)


@csrf_exempt
@require_POST
def paymongo_webhook(request):
    """
    Webhook endpoint for PayMongo events (source.chargeable, payment.paid, etc.)
    """
    try:
        # Get signature from headers
        signature = request.headers.get('PayMongo-Signature', '')
        
        # Verify signature (if webhook secret is configured)
        # For now, we'll process without verification in test mode
        # In production, implement proper signature verification
        
        # Parse webhook data
        webhook_data = json.loads(request.body)
        event_type = webhook_data.get('data', {}).get('attributes', {}).get('type')
        
        logger.info(f"Received PayMongo webhook: {event_type}")
        
        if event_type == 'source.chargeable':
            # Source is ready to be charged
            source_data = webhook_data.get('data', {}).get('attributes', {}).get('data', {})
            source_id = source_data.get('id')
            metadata = source_data.get('attributes', {}).get('metadata', {})
            reservation_id = metadata.get('reservation_id')
            
            if reservation_id:
                try:
                    reservation = Reservation.objects.get(id=reservation_id)
                    
                    # Create payment from source
                    payment_result = paymongo_service.create_payment_from_source(source_id)
                    
                    if payment_result.get('success'):
                        logger.info(f"Payment created from webhook for reservation {reservation_id}")
                    
                except Reservation.DoesNotExist:
                    logger.error(f"Reservation {reservation_id} not found for webhook")
        
        elif event_type == 'payment.paid':
            # Payment completed successfully
            payment_data = webhook_data.get('data', {}).get('attributes', {}).get('data', {})
            metadata = payment_data.get('attributes', {}).get('metadata', {})
            reservation_id = metadata.get('reservation_id')
            
            if reservation_id:
                try:
                    reservation = Reservation.objects.get(id=reservation_id)
                    
                    with transaction.atomic():
                        reservation.payment_status = 'paid'
                        reservation.has_paid_reservation = True
                        reservation.payment_verified_at = timezone.now()
                        # Only set to confirmed if not already in a later stage
                        if reservation.status not in ['occupied', 'completed']:
                            reservation.status = 'confirmed'
                        reservation.payment_date = timezone.now()
                        reservation.save()
                    
                    logger.info(f"Payment confirmed via webhook for reservation {reservation_id}")
                    
                except Reservation.DoesNotExist:
                    logger.error(f"Reservation {reservation_id} not found for webhook")
        
        elif event_type == 'payment.failed':
            # Payment failed
            payment_data = webhook_data.get('data', {}).get('attributes', {}).get('data', {})
            metadata = payment_data.get('attributes', {}).get('metadata', {})
            reservation_id = metadata.get('reservation_id')
            
            if reservation_id:
                try:
                    reservation = Reservation.objects.get(id=reservation_id)
                    reservation.payment_status = 'failed'
                    reservation.save()
                    
                    logger.warning(f"Payment failed via webhook for reservation {reservation_id}")
                    
                except Reservation.DoesNotExist:
                    logger.error(f"Reservation {reservation_id} not found for webhook")
        
        return HttpResponse(status=200)
        
    except Exception as e:
        logger.exception(f"Error processing PayMongo webhook: {str(e)}")
        return HttpResponse(status=500)


# ============================================
# PayMongo Checkout Sessions Views (RECOMMENDED)
# ============================================

@login_required
def paymongo_checkout(request, reservation_id):
    """
    Create PayMongo Checkout Session with full UI
    This is the RECOMMENDED method - provides professional checkout page
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('dorm', 'tenant', 'dorm__payment_config'),
        id=reservation_id,
        tenant=request.user
    )
    
    # Check reservation status
    if reservation.status not in ['pending', 'pending_payment']:
        messages.error(request, "This reservation cannot be paid at this time.")
        return redirect('dormitory:tenant_reservations')
    
    # Reset payment status if it was processing (allow retry)
    if reservation.payment_status == 'processing':
        logger.info(f"Resetting payment status for reservation {reservation.id} to allow retry")
        reservation.payment_status = 'pending'
        reservation.payment_intent_id = None
        reservation.save()
    
    # Get payment configuration
    try:
        payment_config = reservation.dorm.payment_config
        payment_breakdown = payment_config.calculate_total_amount()
        total_amount = Decimal(str(payment_breakdown['total']))
    except PaymentConfiguration.DoesNotExist:
        messages.error(request, "Payment configuration not found for this dorm.")
        return redirect('dormitory:tenant_reservations')
    
    # Create Checkout Session with PayMongo
    result = paymongo_service.create_checkout_session(
        reservation=reservation,
        payment_breakdown=payment_breakdown,
        description=f"Reservation for {reservation.dorm.name}"
    )
    
    if result['success']:
        # Update reservation with checkout session info
        reservation.payment_intent_id = result['session_id']
        reservation.payment_method = 'paymongo_checkout'
        reservation.payment_status = 'processing'
        reservation.payment_amount = total_amount
        reservation.save()
        
        # Log transaction
        TransactionLog.objects.create(
            landlord=reservation.dorm.landlord,
            tenant=request.user,
            amount=total_amount,
            transaction_type='payment_received',
            description=f"Checkout session initiated for {reservation.dorm.name}",
            status='pending',
            dorm=reservation.dorm,
            reservation=reservation,
            metadata={
                'payment_method': 'paymongo_checkout',
                'session_id': result['session_id']
            }
        )
        
        # Redirect to PayMongo Checkout page
        checkout_url = result['checkout_url']
        logger.info(f"Redirecting to checkout for reservation {reservation.id}")
        logger.info(f"Checkout URL: {checkout_url}")
        return redirect(checkout_url)
    else:
        messages.error(request, f"Payment error: {result.get('error', 'Unknown error')}")
        logger.error(f"Checkout error for reservation {reservation.id}: {result.get('details')}")
        return redirect('dormitory:payment_booking_intent', reservation_id=reservation.id)


@login_required
def checkout_success(request, reservation_id):
    """
    Handle successful payment callback from PayMongo Checkout
    """
    reservation = get_object_or_404(
        Reservation.objects.select_related('dorm', 'tenant', 'dorm__payment_config'),
        id=reservation_id,
        tenant=request.user
    )
    
    session_id = reservation.payment_intent_id
    logger.info(f"Checkout success callback for reservation {reservation.id}, session_id: {session_id}")
    
    if not session_id:
        messages.warning(request, "No payment session found. Please try again.")
        return redirect('dormitory:tenant_reservations')
    
    # Retrieve the checkout session to verify payment
    session_result = paymongo_service.retrieve_checkout_session(session_id)
    logger.info(f"Session retrieval result: {session_result}")
    
    if session_result.get('success'):
        payment_status = session_result.get('status')
        logger.info(f"Payment status from session: {payment_status}")
        
        # Check if payment is successful
        if payment_status == 'paid':
            # Mark as paid
            with transaction.atomic():
                reservation.payment_status = 'paid'
                reservation.has_paid_reservation = True
                reservation.payment_verified_at = timezone.now()
                # Only set to confirmed if not already in a later stage
                if reservation.status not in ['occupied', 'completed']:
                    reservation.status = 'confirmed'
                reservation.payment_date = timezone.now()
                reservation.save()
                
                # Update transaction log
                TransactionLog.objects.filter(
                    reservation=reservation,
                    status='pending'
                ).update(status='success')
            
            # Notify tenant and landlord
            notify_user(
                user=reservation.tenant,
                message=f"✅ Payment successful! Your reservation for {reservation.dorm.name} is confirmed.",
                related_object_id=reservation.id
            )
            notify_user(
                user=reservation.dorm.landlord,
                message=f"💰 Payment received for {reservation.dorm.name} from {reservation.tenant.get_full_name() or reservation.tenant.username}",
                related_object_id=reservation.id
            )
            
            messages.success(request, "✅ Payment successful! Your reservation is confirmed. Check your email for the receipt.")
            logger.info(f"Checkout payment successful for reservation {reservation.id}")
            return redirect('dormitory:tenant_reservations')
        
        elif payment_status == 'awaiting_payment_method' or payment_status == 'processing':
            # Payment still processing
            logger.info(f"Payment still processing for reservation {reservation.id}, status: {payment_status}")
            messages.info(request, "⏳ Payment is being processed. Please wait for confirmation.")
            return redirect('dormitory:tenant_reservations')
        
        else:
            # Unknown status
            logger.warning(f"Unknown payment status for reservation {reservation.id}: {payment_status}")
            messages.warning(request, f"Payment status: {payment_status}. Please wait for confirmation or contact support.")
            return redirect('dormitory:tenant_reservations')
    
    # If we get here, something went wrong
    logger.error(f"Session retrieval failed for reservation {reservation.id}: {session_result}")
    messages.warning(request, "Payment status unclear. Please wait for confirmation or contact support.")
    return redirect('dormitory:tenant_reservations')

