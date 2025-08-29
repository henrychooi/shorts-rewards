import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from django.db import transaction
from .models import Comment, Short
from transformers import pipeline

logger = logging.getLogger(__name__)


class CommentAnalysisService:
    """
    Service for analyzing comment sentiment using Hugging Face transformers.
    Uses cardiffnlp/twitter-roberta-base-sentiment model.
    """

    def __init__(self, model_name: str = "cardiffnlp/twitter-roberta-base-sentiment"):
        self.model_name = model_name
        self.pipeline = None
        self._load_pipeline()

    def _load_pipeline(self):
        """Load the sentiment analysis pipeline if not already loaded"""
        if self.pipeline is None:
            try:
                logger.info(f"Loading sentiment analysis pipeline: {self.model_name}")
                self.pipeline = pipeline(
                    "sentiment-analysis",
                    model=self.model_name,
                    return_all_scores=True,
                    device=-1  # Use CPU
                )
                logger.info("Sentiment analysis pipeline loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load sentiment analysis pipeline: {str(e)}")
                raise

    def analyze_comment(self, comment_text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of a single comment.

        Args:
            comment_text: The comment text to analyze

        Returns:
            Dict containing score, label, and raw results
        """
        if not comment_text or not comment_text.strip():
            return {
                'sentiment_score': None,
                'sentiment_label': None,
                'raw_scores': None,
                'error': 'Empty comment text'
            }

        try:
            if self.pipeline is None:
                self._load_pipeline()

            # Perform sentiment analysis
            results = self.pipeline(comment_text.strip())

            if not results:
                return {
                    'sentiment_score': None,
                    'sentiment_label': None,
                    'raw_scores': None,
                    'error': 'No results from model'
                }

            # Extract scores for each sentiment
            scores = results[0] if isinstance(results[0], list) else [results[0]]
            p_neg = next((item['score'] for item in scores if item['label'] == 'LABEL_0'), 0.0)
            p_neu = next((item['score'] for item in scores if item['label'] == 'LABEL_1'), 0.0)
            p_pos = next((item['score'] for item in scores if item['label'] == 'LABEL_2'), 0.0)

            # Convert to -1 to 1 scale
            # Score formula: (positive - negative) normalized to -1 to 1 range
            sentiment_score = self._calculate_sentiment_score(p_pos, p_neu, p_neg)
            sentiment_label = self._get_sentiment_label(sentiment_score)

            return {
                'sentiment_score': sentiment_score,
                'sentiment_label': sentiment_label,
                'raw_scores': {
                    'p_neg': p_neg,
                    'p_neu': p_neu,
                    'p_pos': p_pos
                },
                'error': None
            }

        except Exception as e:
            logger.error(f"Error analyzing comment: {str(e)}")
            return {
                'sentiment_score': None,
                'sentiment_label': None,
                'raw_scores': None,
                'error': str(e)
            }

    def _calculate_sentiment_score(self, p_pos: float, p_neu: float, p_neg: float) -> float:
        """
        Calculate sentiment score on -1 to 1 scale.

        Formula:
        - Positive sentiment contributes positively
        - Negative sentiment contributes negatively
        - Neutral sentiment has no contribution
        - Result ranges from -1 (most negative) to 1 (most positive)
        """
        # Calculate score as weighted difference between positive and negative
        # Score = (positive - negative) where both are normalized
        score = p_pos - p_neg

        # Ensure score is within -1 to 1 range
        return max(-1.0, min(1.0, score))

    def _get_sentiment_label(self, score: float) -> str:
        """Convert numerical score to sentiment label"""
        if score > 0.3:  # Strongly positive (>0.3)
            return 'positive'
        elif score < -0.3:  # Strongly negative (<-0.3)
            return 'negative'
        else:  # Neutral range (-0.3 to 0.3)
            return 'neutral'

    def analyze_comment_instance(self, comment: Comment) -> Dict[str, Any]:
        """
        Analyze a Comment model instance and update it.

        Args:
            comment: Comment instance to analyze

        Returns:
            Analysis results dictionary
        """
        logger.info(f"Analyzing comment {comment.id}")

        analysis_result = self.analyze_comment(comment.content)

        if analysis_result['error']:
            logger.error(f"Failed to analyze comment {comment.id}: {analysis_result['error']}")
            return analysis_result

        # Update the comment with analysis results
        comment.sentiment_score = analysis_result['sentiment_score']
        comment.sentiment_label = analysis_result['sentiment_label']
        comment.analyzed_at = datetime.now()
        comment.save(update_fields=['sentiment_score', 'sentiment_label', 'analyzed_at'])

        logger.info(f"Comment {comment.id} analysis complete - Score: {analysis_result['sentiment_score']}, Label: {analysis_result['sentiment_label']}")

        return analysis_result

    def analyze_comments_for_short(self, short: Short, update_aggregate: bool = True) -> Dict[str, Any]:
        """
        Analyze all comments for a given Short and optionally update aggregate score.

        Args:
            short: Short instance to analyze comments for
            update_aggregate: Whether to update the Short's comment_analysis_score

        Returns:
            Analysis summary
        """
        logger.info(f"Analyzing all comments for short {short.id}")

        comments = short.comments.filter(is_active=True).exclude(sentiment_score__isnull=False)
        analyzed_count = 0
        total_score = 0
        error_count = 0
        results = []

        for comment in comments:
            result = self.analyze_comment_instance(comment)
            results.append(result)

            if result['error']:
                error_count += 1
            else:
                analyzed_count += 1
                if result['sentiment_score'] is not None:
                    total_score += result['sentiment_score']

        # Update aggregate score if requested
        if update_aggregate and analyzed_count > 0:
            aggregate_score = total_score / analyzed_count
            short.comment_analysis_score = aggregate_score
            short.save(update_fields=['comment_analysis_score'])
            logger.info(f"Updated aggregate comment score for short {short.id}: {aggregate_score}")

        return {
            'short_id': str(short.id),
            'comments_analyzed': analyzed_count,
            'errors': error_count,
            'aggregate_score': aggregate_score if update_aggregate and analyzed_count > 0 else None,
            'results': results
        }

    def reanalyze_comment(self, comment: Comment, force: bool = False) -> Dict[str, Any]:
        """
        Re-analyze a comment that was already processed.

        Args:
            comment: Comment instance to re-analyze
            force: If True, re-analyze even if already analyzed

        Returns:
            Analysis results
        """
        if not force and comment.sentiment_score is not None and comment.analyzed_at:
            logger.warning(f"Comment {comment.id} already analyzed, skipping unless force=True")
            return {
                'error': 'Comment already analyzed',
                'sentiment_score': comment.sentiment_score,
                'sentiment_label': comment.sentiment_label
            }

        return self.analyze_comment_instance(comment)

    def get_short_sentiment_summary(self, short: Short) -> Dict[str, Any]:
        """
        Get sentiment summary for all comments on a Short.

        Args:
            short: Short instance

        Returns:
            Sentiment statistics
        """
        comments = short.comments.filter(is_active=True, sentiment_score__isnull=False)

        if not comments:
            return {
                'total_comments': short.comments.filter(is_active=True).count(),
                'analyzed_comments': 0,
                'average_score': None,
                'sentiment_distribution': {},
                'score_range': None
            }

        scores = [comment.sentiment_score for comment in comments if comment.sentiment_score is not None]
        labels = [comment.sentiment_label for comment in comments if comment.sentiment_label]

        if not scores:
            return {
                'total_comments': short.comments.filter(is_active=True).count(),
                'analyzed_comments': 0,
                'average_score': None,
                'sentiment_distribution': {},
                'score_range': None
            }

        # Calculate distribution
        distribution = {}
        for label in ['positive', 'neutral', 'negative']:
            distribution[label] = labels.count(label) if label in labels else 0

        return {
            'total_comments': short.comments.filter(is_active=True).count(),
            'analyzed_comments': len(scores),
            'average_score': sum(scores) / len(scores) if scores else None,
            'sentiment_distribution': distribution,
            'score_range': {
                'min': min(scores),
                'max': max(scores)
            } if scores else None
        }
