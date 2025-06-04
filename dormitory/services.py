from decimal import Decimal
from .models import RoommatePost, RoommateMatch

class RoommateMatchingService:
    @staticmethod
    def calculate_compatibility(post1: RoommatePost, post2: RoommatePost) -> Decimal:
        """
        Calculate compatibility score between two roommate posts.
        Returns a percentage score (0-100).
        """
        score = 0
        total_weight = 0
        
        # Budget compatibility (30% weight)
        weight = 30
        total_weight += weight
        if (post1.preferred_budget_min <= post2.preferred_budget_max and 
            post1.preferred_budget_max >= post2.preferred_budget_min):
            budget_overlap = min(post1.preferred_budget_max, post2.preferred_budget_max) - \
                           max(post1.preferred_budget_min, post2.preferred_budget_min)
            budget_range = max(post1.preferred_budget_max, post2.preferred_budget_max) - \
                         min(post1.preferred_budget_min, post2.preferred_budget_min)
            if budget_range > 0:
                score += weight * (budget_overlap / budget_range)
        
        # Location match (25% weight)
        weight = 25
        total_weight += weight
        if post1.preferred_location.lower() == post2.preferred_location.lower():
            score += weight
        
        # Amenities match (20% weight)
        weight = 20
        total_weight += weight
        post1_amenities = set(post1.amenities.all())
        post2_amenities = set(post2.amenities.all())
        if post1_amenities and post2_amenities:  # Only if both have amenities
            common_amenities = post1_amenities.intersection(post2_amenities)
            all_amenities = post1_amenities.union(post2_amenities)
            if all_amenities:
                score += weight * (len(common_amenities) / len(all_amenities))
        
        # Mood/Personality compatibility (15% weight)
        weight = 15
        total_weight += weight
        if post1.mood == post2.mood:
            score += weight
        elif (post1.mood in ['quiet', 'studious'] and post2.mood in ['quiet', 'studious']) or \
             (post1.mood in ['friendly', 'adventurous'] and post2.mood in ['friendly', 'adventurous']):
            score += weight * 0.5
        
        # Age difference (10% weight)
        weight = 10
        total_weight += weight
        age_diff = abs(post1.age - post2.age)
        if age_diff <= 2:
            score += weight
        elif age_diff <= 5:
            score += weight * 0.5
        
        # Calculate final percentage
        final_score = Decimal(score / total_weight * 100).quantize(Decimal('0.01'))
        return min(final_score, Decimal('100.00'))

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