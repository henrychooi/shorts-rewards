# api/utils/risk_scoring.py
from .services.fraud_detection import calculate_risk_score

def get_user_risk_level(user_activity):
    """
    Return risk level string based on score.
    """
    score = calculate_risk_score(user_activity)
    if score >= 75:
        return "high"
    elif score >= 50:
        return "medium"
    else:
        return "low"