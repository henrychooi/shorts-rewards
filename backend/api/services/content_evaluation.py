# api/services/content_evaluation.py

class ContentScore:
    def __init__(self, video_id, creator_id):
        self.video_id = video_id
        self.creator_id = creator_id
        self.engagement_score = 0
        self.quality_score = 0
        self.viral_potential = 0
        self.final_score = 0

    def calculate_final_score(self):
        self.final_score = (
            self.engagement_score * 0.4 +
            self.quality_score * 0.4 +
            self.viral_potential * 0.2
        )
        return self.final_score

    def get_bonus_multiplier(self):
        if self.final_score >= 90:
            return 1.5
        elif self.final_score >= 80:
            return 1.3
        elif self.final_score >= 70:
            return 1.1
        return 1.0


def evaluate_content(video_data):
    """
    Evaluate content quality and return bonus multiplier.
    video_data = {
        'duration': int,
        'tags': list,
        'description_length': int,
        'upload_time': datetime
    }
    """
    score = ContentScore(video_data['video_id'], video_data['creator_id'])

    # Mock engagement prediction
    score.engagement_score = predict_engagement(video_data)

    # Mock quality score (future AI model)
    score.quality_score = 60 + (video_data.get('duration', 0) // 10) * 5  # example heuristic

    # Viral potential (mock)
    score.viral_potential = 40 + len(video_data.get('tags', [])) * 5

    score.calculate_final_score()

    return {
        'content_score': score.final_score,
        'bonus_multiplier': score.get_bonus_multiplier(),
        'details': {
            'engagement': score.engagement_score,
            'quality': score.quality_score,
            'viral': score.viral_potential
        }
    }


def predict_engagement(video_data):
    """
    Mock function - replace with ML model later.
    """
    score = 50  # base

    if video_data.get('duration', 0) > 30 and video_data.get('duration', 0) < 90:
        score += 15
    if video_data.get('tags', []) and len(video_data.get('tags', [])) >= 3:
        score += 10
    if video_data.get('description_length', 0) > 50:
        score += 5
    hour = video_data.get('upload_time').hour if hasattr(video_data.get('upload_time'), 'hour') else 0
    if 12 <= hour <= 20:
        score += 10

    return min(score, 100)