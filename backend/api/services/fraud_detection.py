# api/services/fraud_detection.py

from django.core.exceptions import ValidationError

def calculate_risk_score(user_activity):
    """
    Calculate risk score based on user behavior.
    Returns 0-100, higher = more risky.
    """
    score = 0

    if user_activity.get('transaction_count_last_hour', 0) > 10:
        score += 30
    if user_activity.get('account_age_hours', 0) < 24 and user_activity.get('amount', 0) > 100:
        score += 25
    if user_activity.get('failed_payments', 0) > 3:
        score += 20
    if user_activity.get('location_changed', False):
        score += 15

    return min(score, 100)


def is_transaction_suspicious(user_activity, threshold=75):
    """
    Check if transaction should be blocked.
    """
    risk_score = calculate_risk_score(user_activity)
    return risk_score >= threshold


def flag_transaction(transaction_id, reason="High Risk"):
    """
    Log suspicious transaction for review.
    """
    print(f"⚠️ Flagged transaction {transaction_id}: {reason}")
    # In production: log to database or alert system