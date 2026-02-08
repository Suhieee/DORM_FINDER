"""
Google Gemini AI Chatbot Service for Smart Dorm Finder
Provides intelligent assistance to tenants and landlords
"""

import logging
import time
from typing import Dict, List, Optional
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class GeminiChatbotService:
    """
    Service class for integrating Google Gemini AI chatbot
    with FAQ caching and rate limit handling
    """
    
    def __init__(self):
        """Initialize Gemini client with API key from settings"""
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.client = None
        
        if self.api_key:
            try:
                from google import genai
                from google.genai import types
                self.genai = genai
                self.types = types
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini AI client initialized successfully")
            except ImportError:
                logger.error("google-genai package not installed. Run: pip install google-genai")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {str(e)}")
        else:
            logger.warning("GEMINI_API_KEY not configured in settings")
    
    def is_available(self) -> bool:
        """Check if Gemini service is available"""
        return self.client is not None and bool(self.api_key)
    
    def create_system_instruction(self, user) -> str:
        """
        Generate context-aware system instruction based on user role
        Includes real dorm data from database
        """
        from dormitory.models import Dorm
        
        # Determine user type
        if user and user.is_authenticated:
            user_type = user.user_type
            user_name = user.get_full_name() or user.username
        else:
            user_type = 'guest'
            user_name = 'Guest'
        
        # Get available dorms from database
        try:
            dorms = Dorm.objects.filter(
                approval_status='approved',
                available=True
            ).select_related('landlord')[:20]
            
            if dorms.exists():
                dorm_list = []
                for d in dorms:
                    location = d.address[:50]  # Use address field
                    dorm_list.append(
                        f"  - {d.name}: ₱{d.price:,.2f}/month, {location}, "
                        f"Type: {d.get_accommodation_type_display()}"
                    )
                dorm_info = "\n".join(dorm_list)
            else:
                dorm_info = "  No dorms currently available in the system."
        except Exception as e:
            logger.error(f"Error fetching dorm data: {e}")
            dorm_info = "  Dorm data temporarily unavailable."
        
        # Role-specific instructions
        role_instructions = {
            'tenant': """
You are helping a TENANT who is looking for a place to stay.
Focus on:
- Helping them find suitable dorms based on budget, location, amenities
- Explaining the reservation and payment process
- Answering questions about dorm features, rules, and policies
- Guiding them through the platform features (search, filters, roommate finder)
- Payment methods: GCash, PayMaya, Credit/Debit Cards via PayMongo
""",
            'landlord': """
You are helping a LANDLORD who manages properties on the platform.
Focus on:
- Explaining how to list and manage dorms
- Answering questions about the verification process
- Helping with reservation management and tenant communications
- Explaining payment configurations and transaction logs
- Assisting with room management and pricing strategies
""",
            'admin': """
You are helping an ADMIN who manages the entire platform.
Focus on:
- Platform management features
- User verification and moderation
- System reports and analytics
- Transaction monitoring
- Handling disputes and support requests
""",
            'guest': """
You are helping a VISITOR who is browsing the platform.
Focus on:
- Explaining what Smart Dorm Finder is
- Helping them understand the benefits of creating an account
- Showing available dorms and features
- Guiding them through the registration process
- Answering general questions about the platform
"""
        }
        
        system_instruction = f"""You are a friendly, helpful, and conversational AI assistant for **Smart Dorm Finder**, a platform connecting students with dormitories in Manila, Philippines.

**Your Personality**:
- Conversational and warm, like chatting with a knowledgeable friend
- Use casual, natural language (mix English and Filipino when appropriate)
- Show empathy and understanding of student concerns
- Be enthusiastic about helping them find their perfect home
- Keep responses concise but complete (2-4 sentences unless details needed)
- Use emojis occasionally to be friendly 

**Current User**: {user_name} ({user_type.upper()})
{role_instructions.get(user_type, role_instructions['guest'])}

**Available Dorms** (Live data from our database):
{dorm_info}

**Your Knowledge**:

 **Platform Features**:
- Browse and search dorms by location, price, amenities
- Filter by accommodation type (whole unit, bed space, room sharing)
- View dorm details, photos, reviews, and ratings
- Make reservations with secure payment via PayMongo
- Roommate finder to find compatible roommates
- Direct messaging between tenants and landlords
- Real-time notifications
- Transaction logs and payment tracking

 **Payment & Reservations**:
- Payment methods: GCash, PayMaya, Credit/Debit Cards (via PayMongo)
- Secure checkout with instant email receipts
- Advance payments and deposits handled safely
- Platform holds money until check-in confirmed
- Landlord payouts managed by platform
- Cancellation policies vary by dorm - check before booking

 **How Students Use the Platform**:
1. Browse dorms or use filters (location, price, type)
2. View dorm details, photos, landlord info
3. Schedule a visit to see it in person (optional)
4. Make a reservation request
5. Complete secure payment
6. Get confirmation and landlord contact
7. Move in on check-in date!

📱 **Special Features**:
- Roommate Finder: Create profile, find compatible roommates by school, budget, lifestyle
- Visit Scheduling: Book appointments to tour dorms before committing
- Reviews & Ratings: See what other students say
- Verified Landlords: All properties undergo admin verification
- Instant Notifications: Stay updated on reservations, messages, payments

**How to Respond**:
- Be conversational, not robotic - chat naturally like you're helping a friend
- Ask clarifying questions when needed
- Give specific examples when explaining
- If asked about specific dorms, mention actual ones from the list above
- For location questions, use Manila area knowledge (Malate, Ermita, UST, Taft, etc.)
- If you don't know something specific, admit it honestly and suggest alternatives
- Encourage users to browse the platform or contact support for account-specific issues
- Keep safety in mind - remind about verified listings, secure payments

**Examples of Good Responses**:
- Instead of: \"The platform has a reservation feature.\"
- Say: \"To reserve a dorm, just click 'Reserve Now' on any listing, pick your dates, and checkout! It's super quick - usually takes less than 5 minutes. Payment is secure through PayMongo. 💳\"

- Instead of: \"Search filters are available.\"  
- Say: \"Looking for something specific? Use our filters to narrow down by price, location, or room type. For example, if you need bedspace near UST under ₱5,000, just tick those boxes and boom - perfect matches! 🎯\"

Remember: You're not just answering questions - you're helping students find their home away from home. Be warm, helpful, and make them feel confident about using the platform! 🏠✨"""
        
        return system_instruction
    
    def check_faq_cache(self, question: str) -> Optional[Dict]:
        """
        Check if question matches cached FAQ
        Returns cached answer if found, None otherwise
        """
        from dormitory.models import ChatbotFAQ
        
        # Normalize question
        normalized = question.lower().strip()
        
        # Try exact match first (cached)
        cache_key = f'chatbot_faq_{hash(normalized)}'
        cached_faq = cache.get(cache_key)
        if cached_faq:
            logger.info(f"FAQ cache hit (memory): {question[:50]}")
            return cached_faq
        
        # Try database lookup with keyword matching
        try:
            faqs = ChatbotFAQ.objects.filter(is_active=True)
            
            for faq in faqs:
                # Check similarity
                similarity = SequenceMatcher(None, normalized, faq.question.lower()).ratio()
                
                # Check keyword matches
                keywords = [k.strip().lower() for k in faq.keywords.split(',') if k.strip()]
                keyword_match = any(kw in normalized for kw in keywords)
                
                # If high similarity or keyword match
                if similarity > 0.85 or (similarity > 0.7 and keyword_match):
                    logger.info(f"FAQ match found (similarity: {similarity:.2f}): {faq.question[:50]}")
                    faq.increment_hit()
                    
                    result = {
                        'answer': faq.answer,
                        'is_cached': True,
                        'faq_id': faq.id
                    }
                    
                    # Cache for 1 hour
                    cache.set(cache_key, result, 3600)
                    return result
        
        except Exception as e:
            logger.error(f"Error checking FAQ cache: {e}")
        
        return None
    
    def send_message(
        self,
        user,
        message: str,
        conversation_history: List[Dict] = None,
        max_retries: int = 3
    ) -> Dict:
        """
        Send message to Gemini AI with retry logic and FAQ caching
        
        Args:
            user: Django user object
            message: User's message
            conversation_history: List of previous messages [{'role': 'user', 'content': '...'}]
            max_retries: Maximum retry attempts for rate limits
            
        Returns:
            dict: {'success': bool, 'response': str, 'is_cached': bool, 'error': str}
        """
        
        # Check FAQ cache first
        faq_result = self.check_faq_cache(message)
        if faq_result:
            return {
                'success': True,
                'response': faq_result['answer'],
                'is_cached': True,
                'faq_id': faq_result.get('faq_id')
            }
        
        # Check if service is available
        if not self.is_available():
            return {
                'success': False,
                'response': "I'm currently unavailable. Please contact support for assistance.",
                'error': 'Gemini service not configured'
            }
        
        # Prepare conversation history
        if conversation_history is None:
            conversation_history = []
        
        # Attempt to send message with exponential backoff
        for attempt in range(max_retries):
            try:
                # Create system instruction
                system_instruction = self.create_system_instruction(user)
                
                # Build proper conversation history with role-based turns
                # Gemini expects alternating user/model turns
                contents = []
                
                # Add conversation history (last 10 messages for context)
                for msg in conversation_history[-10:]:
                    role = 'user' if msg['role'] == 'user' else 'model'
                    contents.append({
                        'role': role,
                        'parts': [{'text': msg['content']}]
                    })
                
                # Add current user message
                contents.append({
                    'role': 'user',
                    'parts': [{'text': message}]
                })
                
                # Generate response using chat format
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=self.types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.7,  # Balanced creativity
                        top_p=0.95,
                        max_output_tokens=500,  # Limit response length
                    )
                )
                
                # Extract response text
                response_text = response.text if hasattr(response, 'text') else str(response)
                
                logger.info(f"Gemini response generated successfully (attempt {attempt + 1})")
                
                return {
                    'success': True,
                    'response': response_text,
                    'is_cached': False
                }
            
            except Exception as e:
                error_str = str(e).lower()
                
                # Check for authentication errors (invalid API key)
                if 'api key' in error_str or 'authentication' in error_str or 'permission' in error_str or '401' in error_str or '403' in error_str:
                    logger.error(f"Gemini API authentication error: {str(e)}")
                    return {
                        'success': False,
                        'response': "AI service authentication issue. Please contact the administrator to verify the API key configuration.",
                        'error': 'Authentication failed'
                    }
                
                # Check for rate limit errors
                if 'rate limit' in error_str or 'quota' in error_str or '429' in error_str or 'resource_exhausted' in error_str:
                    if attempt < max_retries - 1:
                        # Exponential backoff: 2s, 4s, 8s
                        wait_time = 2 ** (attempt + 1)
                        logger.warning(f"Rate limit hit, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Rate limit exceeded after {max_retries} attempts: {str(e)}")
                        return {
                            'success': False,
                            'response': "I'm receiving a lot of requests right now. Please try again in a few seconds.",
                            'error': 'Rate limit exceeded'
                        }
                
                # Other errors - log full details
                logger.exception(f"Error generating Gemini response: {str(e)}")
                return {
                    'success': False,
                    'response': "I encountered an error. Please try rephrasing your question or contact support.",
                    'error': str(e)
                }
        
        # Should not reach here
        return {
            'success': False,
            'response': "Unable to process your request. Please try again later.",
            'error': 'Max retries exceeded'
        }
    
    def save_to_faq_cache(self, question: str, answer: str, keywords: str = "") -> bool:
        """
        Save a question-answer pair to FAQ cache
        Useful for common questions identified by usage patterns
        
        Args:
            question: The question text
            answer: The answer text
            keywords: Comma-separated keywords for matching
            
        Returns:
            bool: Success status
        """
        from dormitory.models import ChatbotFAQ
        
        try:
            faq, created = ChatbotFAQ.objects.get_or_create(
                question=question.strip(),
                defaults={
                    'answer': answer.strip(),
                    'keywords': keywords
                }
            )
            
            if not created:
                # Update existing
                faq.answer = answer.strip()
                if keywords:
                    faq.keywords = keywords
                faq.save()
            
            logger.info(f"FAQ {'created' if created else 'updated'}: {question[:50]}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving to FAQ cache: {e}")
            return False


# Global service instance
gemini_service = GeminiChatbotService()
