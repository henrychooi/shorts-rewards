# api/utils/engagement_predictor.py
"""
Mock engagement prediction system.
This will be replaced with ML models in the future.
"""

import random
from datetime import datetime

def predict_engagement(video_data):
    """
    Predict potential engagement score for a video (0-100).
    
    Args:
        video_data (dict): Contains video metadata
            - duration (int): Video length in seconds
            - tags (list): List of tag strings
            - description_length (int): Length of description
            - upload_time (datetime): When video was uploaded
            - likes (int): Current likes (optional)
            - views (int): Current views (optional)
    
    Returns:
        int: Engagement score (0-100)
    """
    score = 50  # Base score
    
    # Duration scoring (optimal is 30-90 seconds)
    duration = video_data.get('duration', 0)
    if 30 <= duration <= 90:
        score += 20
    elif 15 <= duration <= 120:
        score += 10
    else:
        score -= 10
    
    # Tag relevance
    tags = video_data.get('tags', [])
    if len(tags) >= 5:
        score += 15
    elif len(tags) >= 2:
        score += 5
    
    # Description quality
    desc_length = video_data.get('description_length', 0)
    if desc_length > 100:
        score += 10
    elif desc_length > 30:
        score += 5
    
    # Upload timing (prime hours: 12PM-8PM)
    upload_time = video_data.get('upload_time')
    if upload_time and isinstance(upload_time, datetime):
        hour = upload_time.hour
        if 12 <= hour <= 20:
            score += 10
        elif 9 <= hour <= 23:
            score += 5
    
    # Engagement boosters (if available)
    likes = video_data.get('likes', 0)
    views = video_data.get('views', 0)
    if views > 0:
        engagement_rate = (likes / views) * 100
        if engagement_rate > 10:
            score += 15
        elif engagement_rate > 5:
            score += 10
        elif engagement_rate > 1:
            score += 5
    
    # Keep within bounds
    return max(0, min(100, score))


def get_engagement_tier(score):
    """
    Convert engagement score to tier for reporting.
    
    Args:
        score (int): Engagement score (0-100)
    
    Returns:
        str: Tier classification
    """
    if score >= 90:
        return "Excellent"
    elif score >= 75:
        return "Good"
    elif score >= 60:
        return "Average"
    elif score >= 40:
        return "Below Average"
    else:
        return "Poor"


def simulate_engagement_data():
    """
    Generate mock engagement data for testing.
    
    Returns:
        dict: Sample video data for testing
    """
    return {
        'duration': random.randint(15, 120),
        'tags': ['funny', 'trending', 'dance', 'viral'][:random.randint(1, 4)],
        'description_length': random.randint(20, 200),
        'upload_time': datetime.now(),
        'likes': random.randint(0, 1000),
        'views': random.randint(100, 10000)
    }


# Example usage (for testing)
if __name__ == "__main__":
    # Test with sample data
    test_video = {
        'duration': 45,
        'tags': ['comedy', 'trending', 'fun'],
        'description_length': 150,
        'upload_time': datetime.now(),
        'likes': 500,
        'views': 2000
    }
    
    score = predict_engagement(test_video)
    tier = get_engagement_tier(score)
    
    print(f"Engagement Score: {score}")
    print(f"Tier: {tier}")