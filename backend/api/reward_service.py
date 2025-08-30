"""
Content Creator Reward Service

This service implements the reward system for content creators based on:
1. Main Reward: Views, Likes, Comments (base reward)
2. AI Bonus: Video and Audio Quality Scores (bonus percentage)
3. Moderation: Comment Sentiment Analysis (adjustment percentage)

Final Formula: main_reward + (main_reward * ai_bonus%) + (main_reward * moderation%)
"""

import logging
from decimal import Decimal
from typing import Dict, Optional
from django.utils import timezone
from django.db import transaction
from .models import Short, Transaction, Wallet, AuditLog

logger = logging.getLogger(__name__)


class ContentCreatorRewardService:
    """Service for calculating and distributing content creator rewards"""
    
    # Conversion rate from points to currency (1 point = $0.001)
    POINTS_TO_CURRENCY_RATE = Decimal('0.001')
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_reward_for_short(self, short: Short, save_to_db: bool = True) -> Dict:
        """
        Calculate the complete reward breakdown for a short video.
        
        Args:
            short: The Short instance to calculate rewards for
            save_to_db: Whether to save the calculated values to the database
            
        Returns:
            Dict with detailed reward breakdown
        """
        try:
            # Calculate final reward score
            final_score = short.calculate_final_reward_score()
            
            if save_to_db:
                short.save(update_fields=[
                    'main_reward_score', 'ai_bonus_percentage', 
                    'moderation_adjustment', 'final_reward_score', 'reward_calculated_at'
                ])
                
                self.logger.info(
                    f"Calculated rewards for short {short.id}: "
                    f"Main={short.main_reward_score}, "
                    f"AI Bonus={short.ai_bonus_percentage}%, "
                    f"Moderation={short.moderation_adjustment}%, "
                    f"Final={final_score}"
                )
            
            return short.get_reward_breakdown()
            
        except Exception as e:
            self.logger.error(f"Error calculating rewards for short {short.id}: {str(e)}")
            raise
    
    def process_reward_payout(self, short: Short, force_recalculate: bool = False) -> Dict:
        """
        Process the actual payout of rewards to the content creator.
        
        Args:
            short: The Short instance to process payout for
            force_recalculate: Whether to recalculate rewards even if already calculated
            
        Returns:
            Dict with payout details
        """
        with transaction.atomic():
            try:
                # Check if rewards have been calculated recently
                if not force_recalculate and short.reward_calculated_at:
                    # Use existing calculation if less than 1 hour old
                    time_diff = timezone.now() - short.reward_calculated_at
                    if time_diff.total_seconds() < 3600:  # 1 hour
                        reward_breakdown = short.get_reward_breakdown()
                    else:
                        reward_breakdown = self.calculate_reward_for_short(short)
                else:
                    reward_breakdown = self.calculate_reward_for_short(short)
                
                final_reward_points = reward_breakdown['final_reward']
                
                if final_reward_points <= 0:
                    return {
                        'success': False,
                        'message': 'No reward points to pay out',
                        'reward_breakdown': reward_breakdown
                    }
                
                # Get or create wallet for the creator
                wallet, created = Wallet.objects.get_or_create(user=short.author)
                
                # Convert points to currency
                reward_amount = Decimal(str(final_reward_points)) * self.POINTS_TO_CURRENCY_RATE
                
                # Create main reward transaction
                main_transaction = Transaction.objects.create(
                    wallet=wallet,
                    transaction_type='content_creator_reward',
                    amount=reward_amount,
                    description=f'Content Creator Reward for "{short.title or "Untitled"}"',
                    related_short=short
                )
                
                # Update wallet balance
                wallet.balance += reward_amount
                wallet.total_earnings += reward_amount
                wallet.save()
                
                # Create audit log
                AuditLog.objects.create(
                    action_type='transaction_created',
                    user=short.author,
                    description=f'Content creator reward processed for short {short.id}',
                    metadata={
                        'short_id': str(short.id),
                        'reward_points': final_reward_points,
                        'reward_amount': str(reward_amount),
                        'transaction_id': str(main_transaction.id),
                        'reward_breakdown': reward_breakdown
                    }
                )
                
                self.logger.info(
                    f"Processed payout for short {short.id}: "
                    f"{final_reward_points} points = ${reward_amount}"
                )
                
                return {
                    'success': True,
                    'message': 'Reward payout processed successfully',
                    'reward_points': final_reward_points,
                    'reward_amount': reward_amount,
                    'transaction_id': str(main_transaction.id),
                    'reward_breakdown': reward_breakdown
                }
                
            except Exception as e:
                self.logger.error(f"Error processing payout for short {short.id}: {str(e)}")
                return {
                    'success': False,
                    'message': f'Error processing payout: {str(e)}',
                    'reward_breakdown': {}
                }
    
    def calculate_batch_rewards(self, shorts_queryset=None, limit: int = 100):
        """
        Calculate rewards for multiple shorts in batch.
        
        Args:
            shorts_queryset: QuerySet of shorts to process (default: all active shorts)
            limit: Maximum number of shorts to process in one batch
        """
        if shorts_queryset is None:
            shorts_queryset = Short.objects.filter(is_active=True)
        
        processed_count = 0
        error_count = 0
        
        for short in shorts_queryset[:limit]:
            try:
                self.calculate_reward_for_short(short)
                processed_count += 1
            except Exception as e:
                error_count += 1
                self.logger.error(f"Error processing short {short.id}: {str(e)}")
        
        self.logger.info(
            f"Batch reward calculation completed: "
            f"{processed_count} processed, {error_count} errors"
        )
        
        return {
            'processed': processed_count,
            'errors': error_count,
            'total_attempted': processed_count + error_count
        }
    
    def get_creator_reward_summary(self, user) -> Dict:
        """Get reward summary for a specific creator"""
        try:
            # Get all shorts by this creator
            creator_shorts = Short.objects.filter(author=user, is_active=True)
            
            total_main_rewards = sum(
                short.main_reward_score or 0 
                for short in creator_shorts
            )
            
            total_final_rewards = sum(
                short.final_reward_score or 0 
                for short in creator_shorts
            )
            
            # Get wallet info
            wallet = getattr(user, 'wallet', None)
            
            # Get recent reward transactions
            recent_transactions = []
            if wallet:
                recent_transactions = list(
                    wallet.transactions.filter(
                        transaction_type='content_creator_reward'
                    ).order_by('-created_at')[:10].values(
                        'amount', 'description', 'created_at', 'related_short__title'
                    )
                )
            
            return {
                'creator': user.username,
                'total_shorts': creator_shorts.count(),
                'total_main_reward_points': total_main_rewards,
                'total_final_reward_points': total_final_rewards,
                'wallet_balance': wallet.balance if wallet else Decimal('0.00'),
                'total_earnings': wallet.total_earnings if wallet else Decimal('0.00'),
                'recent_transactions': recent_transactions,
                'shorts_with_rewards': [
                    {
                        'id': str(short.id),
                        'title': short.title,
                        'main_reward': short.main_reward_score,
                        'final_reward': short.final_reward_score,
                        'ai_bonus_pct': short.ai_bonus_percentage,
                        'moderation_pct': short.moderation_adjustment,
                        'calculated_at': short.reward_calculated_at
                    }
                    for short in creator_shorts
                    if short.final_reward_score is not None
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting creator summary for {user.username}: {str(e)}")
            return {
                'creator': user.username,
                'error': str(e)
            }


# Global service instance
reward_service = ContentCreatorRewardService()
