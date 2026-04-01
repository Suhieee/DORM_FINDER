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
from django.db.models import Count
from django.core.paginator import Paginator
from django.conf import settings
from decimal import Decimal
from datetime import timedelta
import json
import logging

from .models import Reservation, Dorm, PaymentConfiguration, Message
from .models_transaction import TransactionLog, PaymentEventLog
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


def log_payment_event(
    *,
    request,
    provider,
    event_type,
    status='info',
    reservation=None,
    payment_intent_id='',
    external_event_id='',
    amount=None,
    message='',
    metadata=None,
):
    """Persist and emit structured payment observability events."""
    request_id = getattr(request, 'request_id', '')
    correlation_id = payment_intent_id or (f"reservation:{reservation.id}" if reservation else '')

    PaymentEventLog.log_event(
        provider=provider,
        event_type=event_type,
        status=status,
        request_id=request_id,
        correlation_id=correlation_id,
        external_event_id=external_event_id,
        payment_intent_id=payment_intent_id,
        reservation=reservation,
        dorm=getattr(reservation, 'dorm', None),
        tenant=getattr(reservation, 'tenant', None),
        amount=amount,
        message=message,
        metadata=metadata or {},
    )

    logger.info(
        "payment_event provider=%s event=%s status=%s request_id=%s correlation_id=%s reservation_id=%s",
        provider,
        event_type,
        status,
        request_id or '-',
        correlation_id or '-',
        reservation.id if reservation else '-',
    )


@login_required
@require_http_methods(["GET"])
def payment_observability_dashboard(request):
    """Admin HTML dashboard for tracing payment events end-to-end."""
    if getattr(request.user, 'user_type', None) != 'admin':
        return HttpResponse(status=403)

    queryset = PaymentEventLog.objects.select_related('reservation', 'dorm', 'tenant').order_by('-created_at')

    provider = (request.GET.get('provider') or '').strip()
    status = (request.GET.get('status') or '').strip()
    event_type = (request.GET.get('event_type') or '').strip()
    request_id = (request.GET.get('request_id') or '').strip()
    correlation_id = (request.GET.get('correlation_id') or '').strip()
    reservation_id = (request.GET.get('reservation_id') or '').strip()
    payment_intent_id = (request.GET.get('payment_intent_id') or '').strip()
    time_window = (request.GET.get('time_window') or '').strip()

    if provider:
        queryset = queryset.filter(provider=provider)
    if status:
        queryset = queryset.filter(status=status)
    if event_type:
        queryset = queryset.filter(event_type__icontains=event_type)
    if request_id:
        queryset = queryset.filter(request_id__icontains=request_id)
    if correlation_id:
        queryset = queryset.filter(correlation_id__icontains=correlation_id)
    if reservation_id.isdigit():
        queryset = queryset.filter(reservation_id=int(reservation_id))
    if payment_intent_id:
        queryset = queryset.filter(payment_intent_id__icontains=payment_intent_id)

    if time_window in {'1h', '24h', '7d'}:
        now = timezone.now()
        if time_window == '1h':
            queryset = queryset.filter(created_at__gte=now - timedelta(hours=1))
        elif time_window == '24h':
            queryset = queryset.filter(created_at__gte=now - timedelta(hours=24))
        else:
            queryset = queryset.filter(created_at__gte=now - timedelta(days=7))

    total_count = queryset.count()
    failed_count = queryset.filter(status='failed').count()
    success_count = queryset.filter(status='success').count()
    info_count = queryset.filter(status='info').count()
    unique_request_ids = queryset.exclude(request_id='').values('request_id').distinct().count()

    provider_breakdown = list(
        queryset.values('provider').annotate(total=Count('id')).order_by('-total')
    )
    top_event_types = list(
        queryset.values('event_type').annotate(total=Count('id')).order_by('-total')[:8]
    )

    paginator = Paginator(queryset, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'events': page_obj.object_list,
        'page_obj': page_obj,
        'provider_choices': PaymentEventLog.PROVIDER_CHOICES,
        'status_choices': PaymentEventLog.STATUS_CHOICES,
        'filters': {
            'provider': provider,
            'status': status,
            'event_type': event_type,
            'request_id': request_id,
            'correlation_id': correlation_id,
            'reservation_id': reservation_id,
            'payment_intent_id': payment_intent_id,
            'time_window': time_window,
        },
        'summary': {
            'total': total_count,
            'failed': failed_count,
            'success': success_count,
            'info': info_count,
            'unique_request_ids': unique_request_ids,
        },
        'provider_breakdown': provider_breakdown,
        'top_event_types': top_event_types,
    }
    return render(request, 'dormitory/payment_observability.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def payment_booking_intent(request, reservation_id):
    """
    Create a booking intent and display payment breakdown
    User can choose payment method: PayMongo checkout or manual upload
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
    
    selected_payment_method = 'gcash'

    # Handle payment method selection
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        selected_payment_method = payment_method or 'gcash'
        
        if payment_method == 'gcash':
            # Proceed with PayMongo Checkout (supports GCash, PayMaya, Cards)
            return redirect('dormitory:paymongo_checkout', reservation_id=reservation.id)
        
        elif payment_method == 'manual':
            # Manual flow requires proof upload on this page.
            payment_proof = request.FILES.get('payment_proof')
            if not payment_proof:
                messages.error(request, "Please upload a payment proof image for manual payment.")
            else:
                reservation.payment_method = 'manual'
                reservation.status = 'pending_payment'
                reservation.payment_status = 'processing'
                reservation.payment_proof = payment_proof
                reservation.payment_submitted_at = timezone.now()
                reservation.payment_amount = payment_breakdown.get('total', reservation.dorm.price)
                reservation.save()

                Message.objects.create(
                    sender=request.user,
                    receiver=reservation.dorm.landlord,
                    content="Payment proof has been submitted and is awaiting verification.",
                    dorm=reservation.dorm,
                    reservation=reservation
                )

                notify_user(
                    user=reservation.dorm.landlord,
                    message=f"Payment proof submitted for {reservation.dorm.name}. Please verify.",
                    related_object_id=reservation.id
                )

                messages.success(request, "Payment proof uploaded successfully! Waiting for landlord verification.")
                base_url = reverse('dormitory:tenant_reservations')
                return redirect(f"{base_url}?selected_reservation={reservation.id}")

            context = {
                'reservation': reservation,
                'payment_config': payment_config,
                'payment_breakdown': payment_breakdown,
                'partial_payment_amount': partial_payment_amount,
                'accepts_gateway': payment_config.accepts_gateway,
                'accepts_manual': payment_config.accepts_manual,
                'accepts_cash': payment_config.accepts_cash,
                'accepts_partial': payment_config.accepts_partial_payment,
                'selected_payment_method': selected_payment_method,
            }
            return render(request, 'dormitory/payment_booking_intent.html', context)

        # Backward-compatible manual selection without proof upload.
        elif payment_method == 'manual_defer':
            reservation.payment_method = 'manual'
            reservation.status = 'pending_payment'
            reservation.save()
            messages.info(request, "Please upload your payment proof.")
            base_url = reverse('dormitory:tenant_reservations')
            return redirect(f"{base_url}?selected_reservation={reservation.id}")

        messages.error(request, "Please choose a valid payment method.")
        return redirect('dormitory:payment_booking_intent', reservation_id=reservation.id)
    
    context = {
        'reservation': reservation,
        'payment_config': payment_config,
        'payment_breakdown': payment_breakdown,
        'partial_payment_amount': partial_payment_amount,
        'accepts_gateway': payment_config.accepts_gateway,
        'accepts_manual': payment_config.accepts_manual,
        'accepts_cash': payment_config.accepts_cash,
        'accepts_partial': payment_config.accepts_partial_payment,
        'selected_payment_method': selected_payment_method,
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
    log_payment_event(
        request=request,
        provider='mongopay',
        event_type='checkout.initiated',
        reservation=reservation,
        status='info',
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

        log_payment_event(
            request=request,
            provider='mongopay',
            event_type='checkout.session_created',
            status='success',
            reservation=reservation,
            payment_intent_id=result['session_id'],
            amount=total_amount,
            metadata={'checkout_url': result.get('checkout_url', '')},
        )
        
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
        log_payment_event(
            request=request,
            provider='mongopay',
            event_type='checkout.session_failed',
            status='failed',
            reservation=reservation,
            amount=total_amount,
            message=result.get('error', 'unknown_error'),
            metadata={'details': result.get('details', '')},
        )
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
            log_payment_event(
                request=request,
                provider='mongopay',
                event_type='webhook.invalid_signature',
                status='failed',
                message='Webhook signature validation failed',
            )
            logger.warning("Invalid webhook signature received")
            return HttpResponse(status=403)
        
        # Parse webhook data
        webhook_data = json.loads(request.body)
        payment_info = mongo_pay_service.process_webhook_data(webhook_data)

        log_payment_event(
            request=request,
            provider='mongopay',
            event_type='webhook.received',
            status='info',
            external_event_id=webhook_data.get('id', ''),
            metadata={'keys': sorted(list(webhook_data.keys()))},
        )
        
        if not payment_info:
            log_payment_event(
                request=request,
                provider='mongopay',
                event_type='webhook.payload_invalid',
                status='failed',
                message='Failed to process webhook data',
            )
            logger.error("Failed to process webhook data")
            return HttpResponse(status=400)
        
        # Extract reservation ID from reference_id
        reference_id = payment_info.get('reference_id', '')
        if reference_id.startswith('RES-'):
            reservation_id = int(reference_id.replace('RES-', ''))
        else:
            log_payment_event(
                request=request,
                provider='mongopay',
                event_type='webhook.reference_invalid',
                status='failed',
                message=f'Invalid reference_id format: {reference_id}',
            )
            logger.error(f"Invalid reference_id format: {reference_id}")
            return HttpResponse(status=400)
        
        # Get reservation
        try:
            reservation = Reservation.objects.select_related('dorm', 'tenant', 'dorm__landlord').get(
                id=reservation_id
            )
        except Reservation.DoesNotExist:
            log_payment_event(
                request=request,
                provider='mongopay',
                event_type='webhook.reservation_missing',
                status='failed',
                message=f'Reservation {reservation_id} not found',
                metadata={'reservation_id': reservation_id},
            )
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

                log_payment_event(
                    request=request,
                    provider='mongopay',
                    event_type='webhook.payment_success',
                    status='success',
                    reservation=reservation,
                    payment_intent_id=reservation.payment_intent_id or '',
                    amount=payment_info.get('amount'),
                    metadata={'event_type': event_type},
                )
                
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

                log_payment_event(
                    request=request,
                    provider='mongopay',
                    event_type='webhook.payment_failed',
                    status='failed',
                    reservation=reservation,
                    payment_intent_id=reservation.payment_intent_id or '',
                    amount=payment_info.get('amount'),
                    metadata={'event_type': event_type},
                )
                
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
                log_payment_event(
                    request=request,
                    provider='mongopay',
                    event_type='webhook.unhandled_event',
                    status='info',
                    reservation=reservation,
                    payment_intent_id=reservation.payment_intent_id or '',
                    metadata={'event_type': event_type},
                )
                logger.info(f"Unhandled webhook event: {event_type}")
        
        # Return 200 OK to acknowledge receipt
        return HttpResponse(status=200)
        
    except json.JSONDecodeError:
        log_payment_event(
            request=request,
            provider='mongopay',
            event_type='webhook.json_invalid',
            status='failed',
            message='Invalid JSON payload',
        )
        logger.error("Invalid JSON in webhook payload")
        return HttpResponse(status=400)
    except Exception as e:
        log_payment_event(
            request=request,
            provider='mongopay',
            event_type='webhook.error',
            status='failed',
            message=str(e),
        )
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
    if reservation.payment_status in ['success', 'paid']:
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
    previous_status = reservation.status
    
    # Check if cancellation is allowed
    if previous_status not in ['pending', 'pending_payment', 'confirmed']:
        messages.error(request, "This reservation cannot be cancelled.")
        return redirect('dormitory:tenant_reservations')

    # Build cancellation reason from either legacy or modal form fields
    cancellation_reason_select = request.POST.get('cancellation_reason_select', '').strip()
    cancellation_reason_other = request.POST.get('cancellation_reason_other', '').strip()
    cancellation_reason_raw = request.POST.get('cancellation_reason', '').strip()
    if cancellation_reason_select == 'Other':
        cancellation_reason = f"Other: {cancellation_reason_other}" if cancellation_reason_other else 'Other'
    elif cancellation_reason_select:
        cancellation_reason = cancellation_reason_select
    elif cancellation_reason_raw:
        cancellation_reason = cancellation_reason_raw
    else:
        cancellation_reason = 'User requested cancellation'
    
    # Calculate refund if payment was made
    refund_amount = Decimal('0')
    refund_policy_note = ''
    paid_statuses = {'success', 'paid'}
    payment_is_paid = reservation.has_paid_reservation and reservation.payment_status in paid_statuses
    if payment_is_paid:
        monthly_refund_limit = 3
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.month == 12:
            next_month_start = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month_start = month_start.replace(month=month_start.month + 1)

        monthly_refund_count = Reservation.objects.filter(
            tenant=reservation.tenant,
            payment_status='refunded',
            refund_processed_at__gte=month_start,
            refund_processed_at__lt=next_month_start,
        ).exclude(id=reservation.id).count()

        if monthly_refund_count >= monthly_refund_limit:
            refund_policy_note = (
                f"Automatic refund limit reached ({monthly_refund_limit} per month). "
                "Please contact support if you need an exception."
            )
        elif reservation.move_in_date:
            try:
                payment_config = reservation.dorm.payment_config
                days_before_movein = (reservation.move_in_date - timezone.now().date()).days
                refund_amount = Decimal(str(payment_config.calculate_refund(days_before_movein)))
            except PaymentConfiguration.DoesNotExist:
                # Fallback to the same tiered policy if config is missing.
                days_before_movein = (reservation.move_in_date - timezone.now().date()).days
                paid_amount = reservation.payment_amount or Decimal('0')
                if days_before_movein >= 7:
                    refund_amount = paid_amount
                elif days_before_movein >= 3:
                    refund_amount = paid_amount * Decimal('0.5')
                else:
                    refund_amount = Decimal('0')

            if days_before_movein < 3 and refund_amount <= 0:
                refund_policy_note = "Cancellations less than 3 days before move-in are not eligible for refund."
        else:
            refund_policy_note = "No move-in date found, so this cancellation is not eligible for automatic refund."

        # Never refund more than the recorded payment amount
        if reservation.payment_amount:
            refund_amount = min(refund_amount, reservation.payment_amount)
    
    # Process refund if applicable
    if payment_is_paid and refund_amount > 0:
        refund_provider = ''
        refund_result = None

        if not reservation.payment_intent_id:
            messages.warning(request, "Reservation cancelled but no payment reference was found for refund processing.")
        else:
            if reservation.payment_method in ['gcash', 'paymongo_checkout']:
                refund_provider = 'paymongo'
                paymongo_payment_id = reservation.payment_intent_id

                # If we still have a checkout session id, resolve it into the real payment id.
                if paymongo_payment_id.startswith('cs_'):
                    session_result = paymongo_service.retrieve_checkout_session(paymongo_payment_id)
                    if session_result.get('success'):
                        resolved_payment_id = session_result.get('payment_id', '')
                        if resolved_payment_id:
                            paymongo_payment_id = resolved_payment_id
                            reservation.payment_intent_id = resolved_payment_id
                    else:
                        paymongo_payment_id = ''

                if paymongo_payment_id.startswith('pay_'):
                    refund_result = paymongo_service.initiate_refund(
                        payment_id=paymongo_payment_id,
                        amount=refund_amount,
                        reason=cancellation_reason,
                    )
                else:
                    refund_result = {
                        'success': False,
                        'error': 'No refundable PayMongo payment id found. Please process refund manually.',
                    }
            else:
                refund_provider = 'mongopay'
                refund_result = mongo_pay_service.initiate_refund(
                    transaction_id=reservation.payment_intent_id,
                    amount=refund_amount,
                    reason=cancellation_reason
                )

        if refund_result and refund_result.get('success'):
            reservation.refund_amount = refund_amount
            reservation.refund_reason = cancellation_reason
            reservation.refund_processed_at = timezone.now()
            reservation.payment_status = 'refunded'

            log_payment_event(
                request=request,
                provider=refund_provider or ('paymongo' if reservation.payment_method in ['gcash', 'paymongo_checkout'] else 'mongopay'),
                event_type='refund.processed',
                status='success',
                reservation=reservation,
                payment_intent_id=reservation.payment_intent_id or '',
                amount=refund_amount,
                metadata={'refund_id': refund_result.get('refund_id', '')},
            )
            
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
                    'payment_method': reservation.payment_method or 'unknown',
                    'refund_provider': refund_provider or 'unknown',
                    'refund_id': refund_result.get('refund_id', ''),
                    'refund_amount': str(refund_amount)
                }
            )
            
            messages.success(request, f"Reservation cancelled. Refund of ₱{refund_amount:,.2f} will be processed within 5-7 business days.")
        elif refund_result:
            log_payment_event(
                request=request,
                provider=refund_provider or ('paymongo' if reservation.payment_method in ['gcash', 'paymongo_checkout'] else 'mongopay'),
                event_type='refund.failed',
                status='failed',
                reservation=reservation,
                payment_intent_id=reservation.payment_intent_id or '',
                amount=refund_amount,
                message=refund_result.get('error', 'refund_failed'),
                metadata={'details': refund_result.get('details', '')},
            )
            messages.warning(request, "Reservation cancelled but refund processing failed. Please contact support.")
        else:
            messages.warning(request, "Reservation cancelled. Refund could not be processed automatically; please contact support.")
    elif payment_is_paid and refund_amount <= 0:
        log_payment_event(
            request=request,
            provider='paymongo' if reservation.payment_method in ['gcash', 'paymongo_checkout'] else 'mongopay',
            event_type='refund.skipped',
            status='info',
            reservation=reservation,
            payment_intent_id=reservation.payment_intent_id or '',
            amount=Decimal('0'),
            message=refund_policy_note or 'refund_not_eligible_by_policy',
            metadata={'policy_note': refund_policy_note or 'default_non_refundable_policy'},
        )
        if refund_policy_note:
            messages.info(request, f"Reservation cancelled. {refund_policy_note}")
        else:
            messages.info(request, "Reservation cancelled. Based on the dorm refund policy, this cancellation is not eligible for an automatic refund.")
    else:
        messages.success(request, "Reservation cancelled successfully.")
    
    # Update reservation status
    reservation.status = 'cancelled'
    reservation.cancellation_reason = cancellation_reason
    
    # Release bed/unit
    # Only release inventory when a slot was already reserved.
    if previous_status in ['pending_payment', 'confirmed']:
        if reservation.dorm.accommodation_type == 'whole_unit':
            reservation.dorm.available_beds = reservation.dorm.max_occupants
        else:
            if reservation.dorm.available_beds < reservation.dorm.total_beds:
                reservation.dorm.available_beds += 1

        if reservation.room is not None:
            reservation.room.is_available = True
            reservation.room.save()

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

    log_payment_event(
        request=request,
        provider='paymongo',
        event_type='callback.success_received',
        status='info',
        reservation=reservation,
        payment_intent_id=source_id or '',
    )
    
    if not source_id:
        log_payment_event(
            request=request,
            provider='paymongo',
            event_type='callback.missing_source',
            status='failed',
            reservation=reservation,
            message='No source id found on reservation',
        )
        messages.warning(request, "No payment source found. Please try again.")
        return redirect('dormitory:tenant_reservations')
    
    # Verify the source status
    source_result = paymongo_service.retrieve_source(source_id)
    logger.info(f"Source status: {source_result.get('status')}")
    
    if source_result.get('success'):
        source_status = source_result.get('status')
        
        # Check if source is chargeable or paid (user completed payment)
        if source_status == 'chargeable' or source_status == 'paid':
            payment_reference = source_id

            # Convert chargeable source to payment so we have a refundable payment id.
            if source_status == 'chargeable':
                payment_amount = reservation.payment_amount
                if payment_amount is None:
                    source_amount_centavos = source_result.get('data', {}).get('data', {}).get('attributes', {}).get('amount')
                    if source_amount_centavos is not None:
                        payment_amount = Decimal(str(source_amount_centavos)) / Decimal('100')

                if payment_amount is not None:
                    payment_result = paymongo_service.create_payment_from_source(source_id, payment_amount)
                    if payment_result.get('success'):
                        payment_reference = payment_result.get('payment_id', source_id)
                    else:
                        log_payment_event(
                            request=request,
                            provider='paymongo',
                            event_type='callback.source_charge_failed',
                            status='failed',
                            reservation=reservation,
                            payment_intent_id=source_id,
                            amount=payment_amount,
                            message=payment_result.get('error', 'source_charge_failed'),
                            metadata={'details': payment_result.get('details', '')},
                        )
                        messages.warning(request, "Payment is still processing. Please wait for webhook confirmation.")
                        return redirect('dormitory:tenant_reservations')

            with transaction.atomic():
                reservation.payment_status = 'success'
                reservation.has_paid_reservation = True
                reservation.payment_verified_at = timezone.now()
                reservation.payment_intent_id = payment_reference
                # Only set to confirmed if not already in a later stage
                if reservation.status not in ['occupied', 'completed']:
                    reservation.status = 'confirmed'
                reservation.save()

                log_payment_event(
                    request=request,
                    provider='paymongo',
                    event_type='callback.payment_confirmed',
                    status='success',
                    reservation=reservation,
                    payment_intent_id=payment_reference,
                    amount=reservation.payment_amount,
                    metadata={'source_status': source_status},
                )
                
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
            log_payment_event(
                request=request,
                provider='paymongo',
                event_type='callback.payment_pending',
                status='info',
                reservation=reservation,
                payment_intent_id=source_id,
                metadata={'source_status': source_status},
            )
            logger.warning(f"Source still pending for reservation {reservation.id}")
            messages.warning(request, "Payment not completed yet. Please complete the payment in your GCash app.")
            return redirect('dormitory:tenant_reservations')
        
        elif source_status == 'cancelled' or source_status == 'expired':
            # Payment was cancelled or expired
            reservation.payment_status = 'failed'
            reservation.save()
            log_payment_event(
                request=request,
                provider='paymongo',
                event_type='callback.payment_cancelled_or_expired',
                status='failed',
                reservation=reservation,
                payment_intent_id=source_id,
                metadata={'source_status': source_status},
            )
            messages.error(request, "Payment was cancelled or expired. Please try again.")
            return redirect('dormitory:payment_booking_intent', reservation_id=reservation.id)
    
    # If we get here, something went wrong
    log_payment_event(
        request=request,
        provider='paymongo',
        event_type='callback.source_lookup_failed',
        status='failed',
        reservation=reservation,
        payment_intent_id=source_id or '',
        metadata={'source_result_success': source_result.get('success', False)},
    )
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

    log_payment_event(
        request=request,
        provider='paymongo',
        event_type='callback.failure_received',
        status='failed',
        reservation=reservation,
        payment_intent_id=reservation.payment_intent_id or '',
    )
    
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
        
        # Parse webhook data
        webhook_data = json.loads(request.body)
        event_type = webhook_data.get('data', {}).get('attributes', {}).get('type')
        event_id = webhook_data.get('data', {}).get('id', '')

        log_payment_event(
            request=request,
            provider='paymongo',
            event_type='webhook.received',
            status='info',
            external_event_id=event_id,
            metadata={
                'event_type': event_type,
                'signature_present': bool(signature),
            },
        )
        
        logger.info(f"Received PayMongo webhook: {event_type}")
        
        if event_type == 'source.chargeable':
            # Source is ready to be charged
            source_data = webhook_data.get('data', {}).get('attributes', {}).get('data', {})
            source_id = source_data.get('id')
            source_attributes = source_data.get('attributes', {})
            metadata = source_attributes.get('metadata', {})
            reservation_id = metadata.get('reservation_id')
            amount_centavos = source_attributes.get('amount')
            
            if reservation_id:
                try:
                    reservation = Reservation.objects.get(id=reservation_id)

                    if source_id and amount_centavos is not None:
                        payment_amount = Decimal(str(amount_centavos)) / Decimal('100')
                        payment_result = paymongo_service.create_payment_from_source(source_id, payment_amount)

                        if payment_result.get('success'):
                            reservation.payment_intent_id = payment_result.get('payment_id', reservation.payment_intent_id)
                            reservation.save(update_fields=['payment_intent_id'])
                            log_payment_event(
                                request=request,
                                provider='paymongo',
                                event_type='webhook.source_chargeable_payment_created',
                                status='success',
                                reservation=reservation,
                                payment_intent_id=payment_result.get('payment_id', ''),
                                external_event_id=event_id,
                                amount=payment_amount,
                                metadata={'source_id': source_id},
                            )
                            logger.info(f"Payment created from webhook for reservation {reservation_id}")
                        else:
                            log_payment_event(
                                request=request,
                                provider='paymongo',
                                event_type='webhook.source_chargeable_payment_failed',
                                status='failed',
                                reservation=reservation,
                                payment_intent_id=reservation.payment_intent_id or '',
                                external_event_id=event_id,
                                amount=payment_amount,
                                message=payment_result.get('error', 'payment_creation_failed'),
                                metadata={'source_id': source_id, 'details': payment_result.get('details', '')},
                            )
                    else:
                        log_payment_event(
                            request=request,
                            provider='paymongo',
                            event_type='webhook.source_chargeable_missing_fields',
                            status='failed',
                            reservation=reservation,
                            external_event_id=event_id,
                            message='source_id or amount is missing',
                            metadata={'source_id_present': bool(source_id), 'amount_present': amount_centavos is not None},
                        )
                    
                except Reservation.DoesNotExist:
                    log_payment_event(
                        request=request,
                        provider='paymongo',
                        event_type='webhook.reservation_missing',
                        status='failed',
                        external_event_id=event_id,
                        metadata={'reservation_id': reservation_id},
                    )
                    logger.error(f"Reservation {reservation_id} not found for webhook")
        
        elif event_type == 'payment.paid':
            # Payment completed successfully
            payment_data = webhook_data.get('data', {}).get('attributes', {}).get('data', {})
            payment_attributes = payment_data.get('attributes', {})
            metadata = payment_attributes.get('metadata', {})
            reservation_id = metadata.get('reservation_id')
            amount_centavos = payment_attributes.get('amount')
            payment_amount = None
            if amount_centavos is not None:
                payment_amount = Decimal(str(amount_centavos)) / Decimal('100')
            
            if reservation_id:
                try:
                    reservation = Reservation.objects.get(id=reservation_id)
                    
                    with transaction.atomic():
                        reservation.payment_status = 'success'
                        reservation.has_paid_reservation = True
                        reservation.payment_verified_at = timezone.now()
                        reservation.payment_intent_id = payment_data.get('id', reservation.payment_intent_id)
                        # Only set to confirmed if not already in a later stage
                        if reservation.status not in ['occupied', 'completed']:
                            reservation.status = 'confirmed'
                        reservation.save()

                    log_payment_event(
                        request=request,
                        provider='paymongo',
                        event_type='webhook.payment_paid',
                        status='success',
                        reservation=reservation,
                        payment_intent_id=reservation.payment_intent_id or payment_data.get('id', ''),
                        external_event_id=event_id,
                        amount=payment_amount,
                        metadata={'event_type': event_type},
                    )
                    
                    logger.info(f"Payment confirmed via webhook for reservation {reservation_id}")
                    
                except Reservation.DoesNotExist:
                    log_payment_event(
                        request=request,
                        provider='paymongo',
                        event_type='webhook.reservation_missing',
                        status='failed',
                        external_event_id=event_id,
                        metadata={'reservation_id': reservation_id},
                    )
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

                    log_payment_event(
                        request=request,
                        provider='paymongo',
                        event_type='webhook.payment_failed',
                        status='failed',
                        reservation=reservation,
                        payment_intent_id=reservation.payment_intent_id or payment_data.get('id', ''),
                        external_event_id=event_id,
                        metadata={'event_type': event_type},
                    )
                    
                    logger.warning(f"Payment failed via webhook for reservation {reservation_id}")
                    
                except Reservation.DoesNotExist:
                    log_payment_event(
                        request=request,
                        provider='paymongo',
                        event_type='webhook.reservation_missing',
                        status='failed',
                        external_event_id=event_id,
                        metadata={'reservation_id': reservation_id},
                    )
                    logger.error(f"Reservation {reservation_id} not found for webhook")

        else:
            log_payment_event(
                request=request,
                provider='paymongo',
                event_type='webhook.unhandled_event',
                status='info',
                external_event_id=event_id,
                metadata={'event_type': event_type},
            )
        
        return HttpResponse(status=200)

    except json.JSONDecodeError:
        log_payment_event(
            request=request,
            provider='paymongo',
            event_type='webhook.json_invalid',
            status='failed',
            message='Invalid JSON payload',
        )
        logger.error("Invalid JSON in PayMongo webhook payload")
        return HttpResponse(status=400)
        
    except Exception as e:
        log_payment_event(
            request=request,
            provider='paymongo',
            event_type='webhook.error',
            status='failed',
            message=str(e),
        )
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

    log_payment_event(
        request=request,
        provider='paymongo',
        event_type='checkout.initiated',
        status='info',
        reservation=reservation,
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

        log_payment_event(
            request=request,
            provider='paymongo',
            event_type='checkout.session_created',
            status='success',
            reservation=reservation,
            payment_intent_id=result['session_id'],
            amount=total_amount,
            metadata={'checkout_url': result.get('checkout_url', '')},
        )
        
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
        log_payment_event(
            request=request,
            provider='paymongo',
            event_type='checkout.session_failed',
            status='failed',
            reservation=reservation,
            amount=total_amount,
            message=result.get('error', 'unknown_error'),
            metadata={'details': result.get('details', '')},
        )
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

    log_payment_event(
        request=request,
        provider='paymongo',
        event_type='checkout.callback_received',
        status='info',
        reservation=reservation,
        payment_intent_id=session_id or '',
    )
    
    if not session_id:
        log_payment_event(
            request=request,
            provider='paymongo',
            event_type='checkout.callback_missing_session',
            status='failed',
            reservation=reservation,
            message='No payment session found on reservation',
        )
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
                reservation.payment_status = 'success'
                reservation.has_paid_reservation = True
                reservation.payment_verified_at = timezone.now()
                payment_id = session_result.get('payment_id', '')
                if payment_id:
                    reservation.payment_intent_id = payment_id
                # Only set to confirmed if not already in a later stage
                if reservation.status not in ['occupied', 'completed']:
                    reservation.status = 'confirmed'
                reservation.save()

                log_payment_event(
                    request=request,
                    provider='paymongo',
                    event_type='checkout.verified_paid',
                    status='success',
                    reservation=reservation,
                    payment_intent_id=reservation.payment_intent_id or session_id,
                    amount=reservation.payment_amount,
                )
                
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
            log_payment_event(
                request=request,
                provider='paymongo',
                event_type='checkout.still_processing',
                status='info',
                reservation=reservation,
                payment_intent_id=session_id,
                metadata={'payment_status': payment_status},
            )
            logger.info(f"Payment still processing for reservation {reservation.id}, status: {payment_status}")
            messages.info(request, "⏳ Payment is being processed. Please wait for confirmation.")
            return redirect('dormitory:tenant_reservations')
        
        else:
            # Unknown status
            log_payment_event(
                request=request,
                provider='paymongo',
                event_type='checkout.unknown_status',
                status='failed',
                reservation=reservation,
                payment_intent_id=session_id,
                metadata={'payment_status': payment_status},
            )
            logger.warning(f"Unknown payment status for reservation {reservation.id}: {payment_status}")
            messages.warning(request, f"Payment status: {payment_status}. Please wait for confirmation or contact support.")
            return redirect('dormitory:tenant_reservations')
    
    # If we get here, something went wrong
    log_payment_event(
        request=request,
        provider='paymongo',
        event_type='checkout.session_lookup_failed',
        status='failed',
        reservation=reservation,
        payment_intent_id=session_id,
        metadata={'session_result_success': session_result.get('success', False)},
    )
    logger.error(f"Session retrieval failed for reservation {reservation.id}: {session_result}")
    messages.warning(request, "Payment status unclear. Please wait for confirmation or contact support.")
    return redirect('dormitory:tenant_reservations')

