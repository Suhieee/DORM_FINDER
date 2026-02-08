from decimal import Decimal
from .models import RoommatePost, RoommateMatch
import logging

logger = logging.getLogger(__name__)

class RoommateMatchingService:
    @staticmethod
    def calculate_compatibility(post1: RoommatePost, post2: RoommatePost) -> tuple:
        """
        Calculate compatibility score between two roommate posts.
        Returns a tuple of (score, factors_dict) where factors_dict contains the breakdown.
        """
        score = Decimal('0')
        total_weight = Decimal('0')
        factors = {}
        
        # Budget compatibility (30% weight)
        weight = Decimal('30')
        total_weight += weight
        budget_score = Decimal('0')
        budget_match = False
        budget_diff = 0
        
        if (post1.preferred_budget_min <= post2.preferred_budget_max and 
            post1.preferred_budget_max >= post2.preferred_budget_min):
            budget_match = True
            budget_overlap = min(post1.preferred_budget_max, post2.preferred_budget_max) - \
                           max(post1.preferred_budget_min, post2.preferred_budget_min)
            budget_range = max(post1.preferred_budget_max, post2.preferred_budget_max) - \
                         min(post1.preferred_budget_min, post2.preferred_budget_min)
            if budget_range > 0:
                budget_score = weight * (Decimal(str(budget_overlap)) / Decimal(str(budget_range)))
                score += budget_score
                budget_diff = abs(float(post1.preferred_budget) - float(post2.preferred_budget))
        
        factors['budget_score'] = float(budget_score / weight * 100)
        factors['budget_match'] = budget_match
        factors['budget_diff'] = round(budget_diff, 2)
        
        # Location match (25% weight)
        weight = Decimal('25')
        total_weight += weight
        location_score = Decimal('0')
        location_match = post1.preferred_location.lower() == post2.preferred_location.lower()
        
        if location_match:
            location_score = weight
            score += location_score
        
        factors['location_score'] = float(location_score / weight * 100)
        factors['location_match'] = location_match
        
        # Amenities match (20% weight)
        weight = Decimal('20')
        total_weight += weight
        amenities_score = Decimal('0')
        post1_amenities = set(post1.amenities.all())
        post2_amenities = set(post2.amenities.all())
        common_amenities_count = 0
        
        if post1_amenities and post2_amenities:  # Only if both have amenities
            common_amenities = post1_amenities.intersection(post2_amenities)
            all_amenities = post1_amenities.union(post2_amenities)
            common_amenities_count = len(common_amenities)
            if all_amenities:
                amenities_score = weight * Decimal(str(len(common_amenities))) / Decimal(str(len(all_amenities)))
                score += amenities_score
        
        factors['amenities_score'] = float(amenities_score / weight * 100) if weight > 0 else 0
        factors['common_amenities_count'] = common_amenities_count
        
        # Mood/Personality compatibility (15% weight)
        weight = Decimal('15')
        total_weight += weight
        mood_score = Decimal('0')
        mood_match = False
        mood_partial_match = False
        
        if post1.mood == post2.mood:
            mood_score = weight
            score += mood_score
            mood_match = True
        elif (post1.mood in ['quiet', 'studious'] and post2.mood in ['quiet', 'studious']) or \
             (post1.mood in ['friendly', 'adventurous'] and post2.mood in ['friendly', 'adventurous']):
            mood_score = weight * Decimal('0.5')
            score += mood_score
            mood_partial_match = True
        
        factors['mood_score'] = float(mood_score / weight * 100)
        factors['mood_match'] = mood_match
        factors['mood_partial_match'] = mood_partial_match
        
        # Age difference (10% weight)
        weight = Decimal('10')
        total_weight += weight
        age_score = Decimal('0')
        age_diff = abs(post1.age - post2.age)
        
        if age_diff <= 2:
            age_score = weight
            score += age_score
        elif age_diff <= 5:
            age_score = weight * Decimal('0.5')
            score += age_score
        
        factors['age_score'] = float(age_score / weight * 100)
        factors['age_diff'] = age_diff
        
        # Calculate final percentage
        final_score = (score / total_weight * Decimal('100')).quantize(Decimal('0.01'))
        final_score = min(final_score, Decimal('100.00'))

        # Log the compatibility breakdown
        logger.info(f"\nCompatibility Score Breakdown between {post1.name} and {post2.name}:")
        logger.info(f"Budget Score: {factors['budget_score']:.2f}% (weight: 30)")
        logger.info(f"Location Score: {factors['location_score']:.2f}% (weight: 25)")
        logger.info(f"Amenities Score: {factors['amenities_score']:.2f}% (weight: 20)")
        logger.info(f"Mood Score: {factors['mood_score']:.2f}% (weight: 15)")
        logger.info(f"Age Score: {factors['age_score']:.2f}% (weight: 10)")
        logger.info(f"Final Score: {final_score}%\n")
        
        return final_score, factors

    @staticmethod
    def find_matches(post: RoommatePost, min_score: Decimal = Decimal('70.00')) -> list:
        """
        Find all potential matches for a roommate post with compatibility score >= min_score.
        Returns a list of (RoommatePost, score) tuples sorted by score descending.
        """
        matches = []
        # Exclude user's own post and already matched posts
        potential_matches = RoommatePost.objects.exclude(
            user=post.user
        ).exclude(
            received_matches__initiator=post
        ).exclude(
            initiated_matches__target=post
        )
        
        for potential_match in potential_matches:
            score, factors = RoommateMatchingService.calculate_compatibility(post, potential_match)
            if score >= min_score:
                matches.append((potential_match, score))
        
        return sorted(matches, key=lambda x: x[1], reverse=True)

    @staticmethod
    def create_match(initiator: RoommatePost, target: RoommatePost):
        """Create a new roommate match with detailed compatibility factors."""
        score, factors = RoommateMatchingService.calculate_compatibility(initiator, target)
        return RoommateMatch.objects.create(
            initiator=initiator,
            target=target,
            compatibility_score=score,
            compatibility_factors=factors
        )
    
    @staticmethod
    def generate_icebreaker(match: 'RoommateMatch', for_user: 'CustomUser') -> str:
        """Generate a personalized icebreaker based on compatibility factors and profile data."""
        factors = match.compatibility_factors
        initiator = match.initiator
        target = match.target
        partner = target if for_user == initiator.user else initiator
        
        icebreakers = []
        
        # Budget-based icebreaker
        if factors.get('budget_match') and factors.get('budget_score', 0) >= 80:
            icebreakers.append(
                f"Hey! I noticed we have similar budget ranges around ₱{int(partner.preferred_budget):,}/month. "
                f"Have you found any good places in {partner.preferred_location} yet?"
            )
        
        # Location-based icebreaker
        if factors.get('location_match'):
            icebreakers.append(
                f"Hi! I see you're also looking in {partner.preferred_location}. "
                f"What made you choose that area?"
            )
        
        # Mood/personality-based icebreaker
        if factors.get('mood_match'):
            mood_text = {
                'quiet': 'appreciate a peaceful living environment',
                'friendly': 'value a warm, social atmosphere',
                'adventurous': 'love exploring and trying new things',
                'studious': 'prioritize a focused study environment'
            }.get(partner.mood, 'have similar personalities')
            icebreakers.append(
                f"Hey! I noticed we both {mood_text}. "
                f"What's your ideal daily routine like?"
            )
        
        # Hobbies-based icebreaker
        if partner.hobbies:
            icebreakers.append(
                f"Hi! I saw in your profile you enjoy {partner.hobbies[:50]}... "
                f"Would love to hear more about your interests and lifestyle!"
            )
        
        # Amenities-based icebreaker
        if factors.get('common_amenities_count', 0) >= 2:
            icebreakers.append(
                f"Hey! We seem to have similar preferences for amenities. "
                f"What's the most important feature you're looking for in a place?"
            )
        
        # Default icebreaker with compatibility score
        if not icebreakers:
            icebreakers.append(
                f"Hey! I saw we have a {match.compatibility_score}% compatibility match. "
                f"What's your ideal roommate schedule and living style like?"
            )
        
        # Return a random icebreaker from the available ones
        import random
        return random.choice(icebreakers) 