import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from .models import Comment, Short
from transformers import pipeline
import torch

logger = logging.getLogger(__name__)


class CommentAnalysisService:
    """
    Service for analyzing comment sentiment using Hugging Face transformers.
    Uses cardiffnlp/twitter-roberta-base-sentiment model.
    """

    def __init__(self, model_name: str = "cardiffnlp/twitter-roberta-base-sentiment"):
        self.model_name = model_name
        self.pipeline = None
        self.is_available = False
        try:
            self._load_pipeline()
            self.is_available = True
        except Exception as e:
            logger.error(f"Failed to initialize CommentAnalysisService: {e}")
            logger.warning("Comment analysis will be disabled")
            self.is_available = False

    def _load_pipeline(self):
        """Load the sentiment analysis pipeline if not already loaded"""
        if self.pipeline is None:
            try:
                logger.info(f"Loading sentiment analysis pipeline: {self.model_name}")
                
                # Set environment variable to force CPU usage and avoid meta device issues
                import os
                os.environ['CUDA_VISIBLE_DEVICES'] = ''
                
                logger.info("Forcing CPU device to avoid meta device issues")
                
                # Try the most basic initialization without any device specification
                try:
                    # Method 1: Simplest initialization - let transformers handle device
                    logger.info("Attempting basic initialization...")
                    self.pipeline = pipeline(
                        "sentiment-analysis",
                        model=self.model_name,
                        return_all_scores=True
                    )
                    logger.info("Basic initialization successful")
                    
                except Exception as e1:
                    logger.warning(f"Basic initialization failed: {e1}")
                    
                    try:
                        # Method 2: Force low CPU memory usage
                        logger.info("Attempting low memory initialization...")
                        self.pipeline = pipeline(
                            "sentiment-analysis",
                            model=self.model_name,
                            return_all_scores=True,
                            model_kwargs={
                                "torch_dtype": torch.float32,
                                "low_cpu_mem_usage": True
                            }
                        )
                        logger.info("Low memory initialization successful")
                        
                    except Exception as e2:
                        logger.warning(f"Low memory initialization failed: {e2}")
                        
                        try:
                            # Method 3: Manual model loading with explicit CPU placement
                            logger.info("Attempting manual model loading...")
                            from transformers import AutoTokenizer, AutoModelForSequenceClassification
                            
                            tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                            model = AutoModelForSequenceClassification.from_pretrained(
                                self.model_name,
                                torch_dtype=torch.float32,
                                low_cpu_mem_usage=True
                            )
                            
                            # Ensure model is on CPU
                            model = model.cpu()
                            
                            # Create pipeline manually
                            self.pipeline = pipeline(
                                "sentiment-analysis",
                                model=model,
                                tokenizer=tokenizer,
                                return_all_scores=True,
                                device=-1  # Force CPU
                            )
                            logger.info("Manual model loading successful")
                            
                        except Exception as e3:
                            logger.error(f"All initialization methods failed. Last error: {e3}")
                            raise Exception(f"Could not initialize sentiment analysis pipeline after trying multiple methods. Final error: {e3}")
                
                # Verify the model is working
                if self.pipeline is not None:
                    try:
                        # Test with a simple phrase
                        test_result = self.pipeline("This is a test")
                        logger.info("Pipeline test successful")
                        
                        # Log device information if available
                        if hasattr(self.pipeline, 'model') and hasattr(self.pipeline.model, 'parameters'):
                            try:
                                model_device = next(self.pipeline.model.parameters()).device
                                logger.info(f"Model loaded on device: {model_device}")
                            except Exception:
                                logger.info("Could not determine model device, but pipeline is working")
                                
                    except Exception as test_error:
                        logger.error(f"Pipeline test failed: {test_error}")
                        self.pipeline = None
                        raise Exception(f"Pipeline loaded but failed test: {test_error}")
                
                logger.info("Sentiment analysis pipeline loaded and tested successfully")
                
            except Exception as e:
                logger.error(f"Failed to load sentiment analysis pipeline: {str(e)}")
                self.pipeline = None
                raise

    def analyze_comment(self, comment_text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of a single comment.

        Args:
            comment_text: The comment text to analyze

        Returns:
            Dict containing score, label, and raw results
        """
        if not self.is_available:
            return {
                'sentiment_score': None,
                'sentiment_label': 'neutral',
                'raw_scores': None,
                'error': 'Comment analysis service not available'
            }
            
        if not comment_text or not comment_text.strip():
            return {
                'sentiment_score': None,
                'sentiment_label': None,
                'raw_scores': None,
                'error': 'Empty comment text'
            }

        try:
            if self.pipeline is None:
                if not self.is_available:
                    return {
                        'sentiment_score': None,
                        'sentiment_label': 'neutral',
                        'raw_scores': None,
                        'error': 'Pipeline not available'
                    }
                self._load_pipeline()

            # Additional check for meta device issues
            if hasattr(self.pipeline.model, 'parameters'):
                model_device = next(self.pipeline.model.parameters()).device
                if str(model_device) == 'meta':
                    logger.warning("Meta device detected, reinitializing pipeline")
                    self.pipeline = None
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
            
            # Try fallback sentiment analysis
            logger.info("Attempting fallback sentiment analysis...")
            try:
                fallback_result = self._fallback_sentiment_analysis(comment_text.strip())
                logger.info("Fallback sentiment analysis successful")
                return fallback_result
            except Exception as fallback_error:
                logger.error(f"Fallback sentiment analysis also failed: {fallback_error}")
            
            return {
                'sentiment_score': None,
                'sentiment_label': 'neutral',
                'raw_scores': None,
                'error': str(e)
            }

    def _fallback_sentiment_analysis(self, text: str) -> Dict[str, Any]:
        """
        Simple lexicon-based sentiment analysis as fallback when transformers fail
        """
        # Simple positive/negative word lists
        positive_words = {
            'good', 'great', 'awesome', 'amazing', 'excellent', 'fantastic', 'wonderful',
            'love', 'like', 'best', 'perfect', 'brilliant', 'outstanding', 'superb',
            'nice', 'beautiful', 'incredible', 'marvelous', 'spectacular', 'magnificent',
            'cool', 'fun', 'happy', 'joy', 'pleased', 'delighted', 'impressed', 'wow',
            'yes', 'definitely', 'absolutely', 'totally', '👍', '❤️', '😍', '🔥'
        }
        
        negative_words = {
            'bad', 'terrible', 'awful', 'horrible', 'worst', 'hate', 'dislike',
            'stupid', 'dumb', 'boring', 'waste', 'sucks', 'annoying', 'frustrating',
            'disappointing', 'pathetic', 'ridiculous', 'useless', 'garbage', 'trash',
            'no', 'never', 'not', 'nothing', 'nobody', 'nowhere', '👎', '😠', '😡'
        }
        
        # Convert to lowercase and split into words
        words = text.lower().split()
        
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        total_words = len(words)
        
        if total_words == 0:
            sentiment_score = 0.0
        else:
            # Calculate score based on ratio of positive/negative words
            sentiment_score = (positive_count - negative_count) / max(total_words, 1)
            # Normalize to -1 to 1 range
            sentiment_score = max(-1.0, min(1.0, sentiment_score * 3))  # Amplify by 3 for better sensitivity
        
        sentiment_label = self._get_sentiment_label(sentiment_score)
        
        return {
            'sentiment_score': sentiment_score,
            'sentiment_label': sentiment_label,
            'raw_scores': {
                'positive_words': positive_count,
                'negative_words': negative_count,
                'total_words': total_words
            },
            'error': None,
            'fallback_used': True
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
        from django.utils import timezone
        comment.analyzed_at = timezone.now()
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

    def analyze_single_comment(self, comment: Comment) -> Dict[str, Any]:
        """
        Convenience method to analyze a single comment and update its short's aggregate score.
        
        Args:
            comment: Comment instance to analyze
            
        Returns:
            Analysis results dictionary
        """
        # Analyze the comment
        result = self.analyze_comment_instance(comment)
        
        if not result.get('error'):
            # Update the short's aggregate comment analysis score
            short = comment.short
            self.update_short_aggregate_score(short)
            
        return result

    def update_short_aggregate_score(self, short: Short) -> float:
        """
        Update the aggregate comment analysis score for a short.
        
        Args:
            short: Short instance to update
            
        Returns:
            New aggregate score
        """
        # Get all analyzed comments for this short
        analyzed_comments = short.comments.filter(
            is_active=True, 
            sentiment_score__isnull=False
        )
        
        if analyzed_comments.exists():
            # Calculate average sentiment score
            scores = [c.sentiment_score for c in analyzed_comments if c.sentiment_score is not None]
            if scores:
                aggregate_score = sum(scores) / len(scores)
                short.comment_analysis_score = aggregate_score
                short.save(update_fields=['comment_analysis_score'])
                logger.info(f"Updated aggregate comment score for short {short.id}: {aggregate_score}")
                return aggregate_score
        
        return None
