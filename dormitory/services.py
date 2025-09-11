from decimal import Decimal
from .models import RoommatePost, RoommateMatch
import logging

logger = logging.getLogger(__name__)

class RoommateMatchingService:
    @staticmethod
    def calculate_compatibility(post1: RoommatePost, post2: RoommatePost) -> Decimal:
        """
        Calculate compatibility score between two roommate posts.
        Returns a percentage score (0-100).
        """
        score = Decimal('0')
        total_weight = Decimal('0')
        
        # Budget compatibility (30% weight)
        weight = Decimal('30')
        total_weight += weight
        budget_score = Decimal('0')
        if (post1.preferred_budget_min <= post2.preferred_budget_max and 
            post1.preferred_budget_max >= post2.preferred_budget_min):
            budget_overlap = min(post1.preferred_budget_max, post2.preferred_budget_max) - \
                           max(post1.preferred_budget_min, post2.preferred_budget_min)
            budget_range = max(post1.preferred_budget_max, post2.preferred_budget_max) - \
                         min(post1.preferred_budget_min, post2.preferred_budget_min)
            if budget_range > 0:
                budget_score = weight * (Decimal(str(budget_overlap)) / Decimal(str(budget_range)))
                score += budget_score
        
        # Location match (25% weight)
        weight = Decimal('25')
        total_weight += weight
        location_score = Decimal('0')
        if post1.preferred_location.lower() == post2.preferred_location.lower():
            location_score = weight
            score += location_score
        
        # Amenities match (20% weight)
        weight = Decimal('20')
        total_weight += weight
        amenities_score = Decimal('0')
        post1_amenities = set(post1.amenities.all())
        post2_amenities = set(post2.amenities.all())
        if post1_amenities and post2_amenities:  # Only if both have amenities
            common_amenities = post1_amenities.intersection(post2_amenities)
            all_amenities = post1_amenities.union(post2_amenities)
            if all_amenities:
                amenities_score = weight * Decimal(str(len(common_amenities))) / Decimal(str(len(all_amenities)))
                score += amenities_score
        
        # Mood/Personality compatibility (15% weight)
        weight = Decimal('15')
        total_weight += weight
        mood_score = Decimal('0')
        if post1.mood == post2.mood:
            mood_score = weight
            score += mood_score
        elif (post1.mood in ['quiet', 'studious'] and post2.mood in ['quiet', 'studious']) or \
             (post1.mood in ['friendly', 'adventurous'] and post2.mood in ['friendly', 'adventurous']):
            mood_score = weight * Decimal('0.5')
            score += mood_score
        
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
        
        # Calculate final percentage
        final_score = (score / total_weight * Decimal('100')).quantize(Decimal('0.01'))
        final_score = min(final_score, Decimal('100.00'))

        # Log the compatibility breakdown
        logger.info(f"\nCompatibility Score Breakdown between {post1.name} and {post2.name}:")
        logger.info(f"Budget Score: {budget_score / weight * 100:.2f}% (weight: {weight})")
        logger.info(f"Location Score: {location_score / weight * 100:.2f}% (weight: {weight})")
        logger.info(f"Amenities Score: {amenities_score / weight * 100:.2f}% (weight: {weight})")
        logger.info(f"Mood Score: {mood_score / weight * 100:.2f}% (weight: {weight})")
        logger.info(f"Age Score: {age_score / weight * 100:.2f}% (weight: {weight})")
        logger.info(f"Final Score: {final_score}%\n")
        
        return final_score

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
            score = RoommateMatchingService.calculate_compatibility(post, potential_match)
            if score >= min_score:
                matches.append((potential_match, score))
        
        return sorted(matches, key=lambda x: x[1], reverse=True)

    @staticmethod
    def create_match(initiator: RoommatePost, target: RoommatePost) -> RoommateMatch:
        """Create a new roommate match."""
        score = RoommateMatchingService.calculate_compatibility(initiator, target)
        return RoommateMatch.objects.create(
            initiator=initiator,
            target=target,
            compatibility_score=score
        ) 