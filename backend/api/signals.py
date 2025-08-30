"""
Django signals for automatic reward calculation and moderation flagging
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from .models import Short, Comment, Like
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Short)
def auto_calculate_rewards_on_analysis_completion(sender, instance, created, **kwargs):
    """
    Automatically calculate rewards when AI analysis scores are updated
    """
    if not created:  # Only for updates, not new creations
        # Check if this is an analysis update by looking at specific fields
        if hasattr(instance, '_analysis_just_completed'):
            logger.info(f"Analysis completed for Short {instance.id}, triggering auto-reward calculation")
            instance.auto_calculate_rewards_if_ready()


@receiver(post_save, sender=Comment)
def update_rewards_on_comment_change(sender, instance, created, **kwargs):
    """
    Recalculate AI bonus and check moderation when comments change
    """
    try:
        short = instance.short
        
        # Update cached comment count first
        short.comment_count = short.comment_count_calculated
        short.save(update_fields=['comment_count'])
        
        # Recalculate comment analysis score for the short
        from .comment_analysis_service import CommentAnalysisService
        comment_service = CommentAnalysisService()
        
        # Analyze the new/updated comment
        if created or instance.sentiment_score is None:
            comment_service.analyze_comment_instance(instance)
        
        # Update aggregate score for the short
        comment_service.update_short_aggregate_score(short)
        
        # Check moderation flag
        short.check_and_update_moderation_flag()
        
        # If rewards were already calculated, recalculate AI bonus
        if short.reward_calculated_at:
            short.calculate_ai_bonus_percentage()
            short.calculate_final_reward_score()
            short.save()
            
        logger.info(f"Updated rewards for Short {short.id} after comment change")
        
    except Exception as e:
        logger.error(f"Error updating rewards after comment change: {e}")


# Custom signal for when analysis is completed
from django.dispatch import Signal

analysis_completed = Signal()

@receiver(analysis_completed)
def on_analysis_completed(sender, short_id, analysis_type, **kwargs):
    """
    Handle when any type of analysis (video, audio, comment) is completed
    """
    try:
        short = Short.objects.get(id=short_id)
        logger.info(f"{analysis_type} analysis completed for Short {short.id}")
        
        # Mark that analysis just completed
        short._analysis_just_completed = True
        
        # Try to auto-calculate rewards
        if short.auto_calculate_rewards_if_ready():
            logger.info(f"Auto-calculated rewards for Short {short.id}")
        else:
            logger.info(f"Not all analysis complete yet for Short {short.id}")
            
    except Short.DoesNotExist:
        logger.error(f"Short {short_id} not found for analysis completion signal")
    except Exception as e:
        logger.error(f"Error handling analysis completion: {e}")


@receiver(post_save, sender=Like)
def update_like_count_on_like_save(sender, instance, created, **kwargs):
    """
    Update cached like_count when a Like is created
    """
    try:
        short = instance.short
        short.like_count = short.like_count_calculated
        short.save(update_fields=['like_count'])
        logger.debug(f"Updated like_count for Short {short.id} after like save")
    except Exception as e:
        logger.error(f"Error updating like_count after like save: {e}")


@receiver(post_delete, sender=Like)
def update_like_count_on_like_delete(sender, instance, **kwargs):
    """
    Update cached like_count when a Like is deleted
    """
    try:
        short = instance.short
        short.like_count = short.like_count_calculated
        short.save(update_fields=['like_count'])
        logger.debug(f"Updated like_count for Short {short.id} after like delete")
    except Exception as e:
        logger.error(f"Error updating like_count after like delete: {e}")


@receiver(post_delete, sender=Comment)
def update_comment_count_on_comment_delete(sender, instance, **kwargs):
    """
    Update cached comment_count when a Comment is deleted
    """
    try:
        short = instance.short
        short.comment_count = short.comment_count_calculated
        short.save(update_fields=['comment_count'])
        logger.debug(f"Updated comment_count for Short {short.id} after comment delete")
    except Exception as e:
        logger.error(f"Error updating comment_count after comment delete: {e}")
