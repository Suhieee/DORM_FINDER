"""
Management command to seed initial chatbot FAQ data
Run: python manage.py seed_chatbot_faq
"""

from django.core.management.base import BaseCommand
from dormitory.models import ChatbotFAQ


class Command(BaseCommand):
    help = 'Seed initial FAQ data for chatbot to reduce API calls'
    
    def handle(self, *args, **kwargs):
        faqs = [
            {
                'question': 'How do I create an account?',
                'answer': 'To create an account, click the "Sign Up" button at the top right. Choose your account type (Tenant or Landlord), fill in your details including email, password, and contact information, then verify your email address.',
                'keywords': 'signup,register,account,create account,new user,join'
            },
            {
                'question': 'How do I search for dorms?',
                'answer': 'Go to "Browse Dorms" in the menu. You can filter by location, price range, accommodation type (whole unit, bed space, room sharing), and amenities. Click on any dorm to view full details, photos, and reviews.',
                'keywords': 'search,find dorms,browse,look for,filter,location,price'
            },
            {
                'question': 'What payment methods are accepted?',
                'answer': 'We accept payments through PayMongo: GCash, PayMaya, and Credit/Debit Cards. All payments are secure and you\'ll receive an email receipt immediately after successful payment.',
                'keywords': 'payment,pay,gcash,paymaya,card,credit card,how to pay'
            },
            {
                'question': 'How do I make a reservation?',
                'answer': '1. Browse available dorms and select one\n2. Click "Reserve Now"\n3. Fill in your check-in/check-out dates\n4. Review the payment breakdown\n5. Choose your payment method\n6. Complete payment via PayMongo\n7. Wait for landlord confirmation',
                'keywords': 'reserve,book,reservation,booking,how to reserve'
            },
            {
                'question': 'Can I cancel my reservation?',
                'answer': 'Yes, you can cancel your reservation from "My Reservations". Refund eligibility depends on the landlord\'s cancellation policy. Check the dorm\'s refund policy before booking. Most dorms offer partial or full refunds if cancelled before the check-in date.',
                'keywords': 'cancel,cancellation,refund,cancel reservation'
            },
            {
                'question': 'How does the roommate finder work?',
                'answer': 'Go to "Roommate Finder" in the menu. Create a profile with your preferences (budget, location, lifestyle). Browse compatible roommates and send messages to connect. You can filter by school, gender, budget, and lifestyle preferences.',
                'keywords': 'roommate,find roommate,roommate finder,roommate match,compatible'
            },
            {
                'question': 'How do I list my dorm as a landlord?',
                'answer': 'Create a Landlord account, then:\n1. Click "Add Dorm"\n2. Fill in details (name, address, price, description)\n3. Upload photos and permit documents\n4. Configure payment settings\n5. Submit for admin verification\n6. Once approved, your dorm will be visible to tenants',
                'keywords': 'list dorm,add property,landlord,post dorm,list property'
            },
            {
                'question': 'What is the verification process?',
                'answer': 'New dorms undergo verification by our admin team to ensure quality and legitimacy. You need to upload valid permits and property documents. Verification usually takes 1-3 business days. You\'ll receive a notification once approved or if additional documents are needed.',
                'keywords': 'verification,verify,approve,approval,documents,permits'
            },
            {
                'question': 'How do I contact a landlord?',
                'answer': 'After making a reservation, you can message the landlord directly through the "Messages" section. You can also schedule a dorm visit to see the property in person before booking.',
                'keywords': 'contact,message,chat,talk to landlord,communicate'
            },
            {
                'question': 'What if I have a problem with my reservation?',
                'answer': 'Contact the landlord first through the messaging system. If the issue isn\'t resolved, you can report it to our admin team from your reservation details page. Admins will review and mediate the situation.',
                'keywords': 'problem,issue,dispute,complaint,help,support'
            },
            {
                'question': 'How do I schedule a dorm visit?',
                'answer': 'From the dorm detail page, click "Schedule Visit". Choose a date and time, add any special notes, and submit. The landlord will confirm or suggest an alternative time. You\'ll receive notifications about your visit status.',
                'keywords': 'visit,tour,viewing,schedule visit,see dorm'
            },
            {
                'question': 'What are the different accommodation types?',
                'answer': 'We offer three types:\n\n• **Whole Unit**: Rent an entire apartment/house\n• **Bed Space**: Rent just a bed in a shared room\n• **Room Sharing**: Rent a private room in a shared property\n\nEach type has different pricing and privacy levels.',
                'keywords': 'accommodation,type,whole unit,bedspace,room sharing,difference'
            },
            {
                'question': 'How are payments processed?',
                'answer': 'Payments go through PayMongo\'s secure checkout. Money is held in the platform\'s account until landlord confirmation. After check-in is confirmed, funds are released to the landlord. This protects both tenants and landlords.',
                'keywords': 'payment process,how payment works,secure payment,escrow'
            },
            {
                'question': 'Can I view my transaction history?',
                'answer': 'Yes! Tenants can view all reservations and payments in "My Reservations". Landlords can see detailed transaction logs in "Transaction Log" showing all payments, refunds, and fees.',
                'keywords': 'transaction,history,payment history,records,receipts'
            },
            {
                'question': 'What if I forget my password?',
                'answer': 'Click "Forgot Password" on the login page. Enter your email address and we\'ll send you a password reset link. Check your spam folder if you don\'t see it within a few minutes.',
                'keywords': 'forgot password,reset password,password recovery,can\'t login'
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for faq_data in faqs:
            faq, created = ChatbotFAQ.objects.get_or_create(
                question=faq_data['question'],
                defaults={
                    'answer': faq_data['answer'],
                    'keywords': faq_data['keywords'],
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {faq.question[:60]}...'))
            else:
                # Update existing
                faq.answer = faq_data['answer']
                faq.keywords = faq_data['keywords']
                faq.save()
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'↻ Updated: {faq.question[:60]}...'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✅ FAQ seeding complete!'))
        self.stdout.write(self.style.SUCCESS(f'Created: {created_count} | Updated: {updated_count}'))
        self.stdout.write(self.style.SUCCESS(f'Total FAQs: {ChatbotFAQ.objects.count()}'))
