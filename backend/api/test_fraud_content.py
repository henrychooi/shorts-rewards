# test_fraud_content.py
import sys
import os
from datetime import datetime

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Set the correct Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Now import Django
import django
django.setup()

def test_fraud_detection():
    print("=== Testing Fraud Detection ===")
    
    from api.services.fraud_detection import calculate_risk_score, is_transaction_suspicious
    
    # Test cases
    test_cases = [
        {
            'name': 'Normal User',
            'data': {
                'transaction_count_last_hour': 2,
                'account_age_hours': 100,
                'amount': 50,
                'failed_payments': 0,
                'location_changed': False
            }
        },
        {
            'name': 'Suspicious User',
            'data': {
                'transaction_count_last_hour': 15,
                'account_age_hours': 5,
                'amount': 200,
                'failed_payments': 5,
                'location_changed': True
            }
        }
    ]
    
    for case in test_cases:
        score = calculate_risk_score(case['data'])
        is_suspicious = is_transaction_suspicious(case['data'])
        print(f"{case['name']}: Score={score}, Suspicious={is_suspicious}")

def test_content_evaluation():
    print("\n=== Testing Content Evaluation ===")
    
    from api.services.content_evaluation import evaluate_content
    
    test_video = {
        'video_id': 'vid_123',
        'creator_id': 'creator_456',
        'duration': 45,
        'tags': ['funny', 'trending', 'dance'],
        'description_length': 150,
        'upload_time': datetime.now()
    }
    
    result = evaluate_content(test_video)
    print("Content Evaluation Result:")
    print(f"Final Score: {result['content_score']}")
    print(f"Bonus Multiplier: {result['bonus_multiplier']}")
    print(f"Details: {result['details']}")

def test_engagement_predictor():
    print("\n=== Testing Engagement Predictor ===")
    
    from api.utils.engagement_predictor import predict_engagement, simulate_engagement_data
    
    # Test with specific data
    test_video = {
        'duration': 60,
        'tags': ['comedy', 'trending'],
        'description_length': 120,
        'upload_time': datetime.now()
    }
    
    score = predict_engagement(test_video)
    print(f"Specific Video Score: {score}")
    
    # Test with simulated data
    mock_data = simulate_engagement_data()
    mock_score = predict_engagement(mock_data)
    print(f"Mock Video Score: {mock_score}")

if __name__ == "__main__":
    test_fraud_detection()
    test_content_evaluation()
    test_engagement_predictor()
    print("\n✅ All tests completed!")