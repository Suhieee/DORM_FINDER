"""
Chatbot API Views for Smart Dorm Finder
Handles AJAX requests for chatbot conversations
"""

import json
import uuid
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from dormitory.models import ChatbotConversation, ChatbotMessage
from dormitory.chatbot import gemini_service

logger = logging.getLogger(__name__)


@require_POST
def chatbot_message(request):
    """
    Handle chatbot messages via AJAX
    Supports both authenticated and anonymous users
    """
    try:
        # Parse request body
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        session_id = data.get('session_id', '')
        
        # Validate message
        if not message:
            return JsonResponse({
                'success': False,
                'error': 'Message cannot be empty'
            }, status=400)
        
        if len(message) > 1000:
            return JsonResponse({
                'success': False,
                'error': 'Message too long (max 1000 characters)'
            }, status=400)
        
        # Generate session ID if not provided
        if not session_id:
            session_id = f'session_{uuid.uuid4().hex[:16]}'
        
        # Get or create conversation
        conversation, created = ChatbotConversation.objects.get_or_create(
            session_id=session_id,
            defaults={
                'user': request.user if request.user.is_authenticated else None
            }
        )
        
        # Update user if authenticated and conversation was for guest
        if request.user.is_authenticated and not conversation.user:
            conversation.user = request.user
            conversation.save(update_fields=['user'])
        
        # Save user message
        user_message = ChatbotMessage.objects.create(
            conversation=conversation,
            role='user',
            content=message
        )
        
        logger.info(f"Chatbot message from {request.user.username if request.user.is_authenticated else 'guest'}: {message[:50]}")
        
        # Get conversation history (last 10 messages for context, excluding current message)
        # Get the last 9 messages (5 exchanges) to leave room for current message
        history = list(
            conversation.messages
            .order_by('-timestamp')[:9]  # Get last 9 messages (most recent first)
        )
        history.reverse()  # Reverse to chronological order
        history = [{'role': msg.role, 'content': msg.content} for msg in history]
        
        # Get AI response
        result = gemini_service.send_message(
            user=request.user,
            message=message,
            conversation_history=history  # Pass properly formatted history
        )
        
        # If Gemini fails but we have a fallback, provide helpful message
        if not result['success'] and not result.get('is_cached'):
            # Try to give a helpful response even without AI
            fallback_response = "I'm currently unavailable. However, I can still help! Try asking:\n\n" \
                              "• How do I create an account?\n" \
                              "• What payment methods are accepted?\n" \
                              "• How do I make a reservation?\n" \
                              "• Can I cancel my reservation?\n\n" \
                              "Or contact support for immediate assistance."
            
            # Save fallback response
            ChatbotMessage.objects.create(
                conversation=conversation,
                role='assistant',
                content=fallback_response,
                is_from_cache=False
            )
            
            return JsonResponse({
                'success': True,  # Don't fail the request
                'response': fallback_response,
                'is_cached': False,
                'session_id': session_id
            })
        
        if result['success']:
            # Save assistant response
            assistant_message = ChatbotMessage.objects.create(
                conversation=conversation,
                role='assistant',
                content=result['response'],
                is_from_cache=result.get('is_cached', False)
            )
            
            return JsonResponse({
                'success': True,
                'response': result['response'],
                'is_cached': result.get('is_cached', False),
                'session_id': session_id,
                'message_id': assistant_message.id
            })
        else:
            # Save error message
            ChatbotMessage.objects.create(
                conversation=conversation,
                role='system',
                content=f"Error: {result.get('error', 'Unknown error')}"
            )
            
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Failed to generate response'),
                'response': result.get('response', 'Sorry, I encountered an error.')
            }, status=500)
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    
    except Exception as e:
        logger.exception(f"Error in chatbot_message: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred',
            'response': 'Sorry, something went wrong. Please try again.'
        }, status=500)


@require_POST
def chatbot_reset(request):
    """
    Reset conversation (start fresh)
    """
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id', '')
        
        if not session_id:
            return JsonResponse({
                'success': False,
                'error': 'Session ID required'
            }, status=400)
        
        # Delete conversation and all messages
        deleted_count, _ = ChatbotConversation.objects.filter(
            session_id=session_id
        ).delete()
        
        logger.info(f"Chatbot conversation reset: {session_id}")
        
        return JsonResponse({
            'success': True,
            'message': 'Conversation reset successfully',
            'deleted': deleted_count > 0
        })
    
    except Exception as e:
        logger.exception(f"Error in chatbot_reset: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def chatbot_save_faq(request):
    """
    Admin endpoint to save a question-answer pair to FAQ cache
    Requires authentication
    """
    if not request.user.is_staff and request.user.user_type != 'admin':
        return JsonResponse({
            'success': False,
            'error': 'Admin access required'
        }, status=403)
    
    try:
        data = json.loads(request.body)
        question = data.get('question', '').strip()
        answer = data.get('answer', '').strip()
        keywords = data.get('keywords', '').strip()
        
        if not question or not answer:
            return JsonResponse({
                'success': False,
                'error': 'Question and answer are required'
            }, status=400)
        
        # Save to FAQ cache
        success = gemini_service.save_to_faq_cache(question, answer, keywords)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'FAQ saved successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to save FAQ'
            }, status=500)
    
    except Exception as e:
        logger.exception(f"Error in chatbot_save_faq: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
