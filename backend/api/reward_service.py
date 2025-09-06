"""
Content Creator Reward Service

This service implements the revenue sharing reward system for content creators:
1. Monthly Points Accumulation: Creators earn points throughout the month
2. Revenue Sharing: 50% of platform revenue distributed to creators
3. Proportional Distribution: Based on (creator_points / total_points) × 50% revenue
4. Wallet Integration: Direct payments to creator wallets

Point System Based On:
- Main Reward: Views, Likes, Comments (base points)
- AI Bonus: Video and Audio Quality Scores (bonus percentage)  
- Moderation: Comment Sentiment Analysis (adjustment percentage)
"""

import logging
import hashlib
import json
import secrets
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Q
from django.contrib.auth.models import User
from .models import Short, Transaction, Wallet, AuditLog, MonthlyPayout

logger = logging.getLogger(__name__)


class MonthlyRevenueShareService:
    """Service for monthly revenue sharing based on creator points"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.platform_revenue_share = Decimal('0.50')  # 50% to creators
        self._cent = Decimal('0.01')

    def _quantize_money(self, amount: Decimal) -> Decimal:
        """Round to 2 decimals using HALF_UP (money)."""
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        return amount.quantize(self._cent, rounding=ROUND_HALF_UP)
    
    def _generate_digital_signature(self, transaction_data: Dict) -> str:
        """Generate a digital signature for transaction verification"""
        # Create a deterministic signature based on transaction data
        signature_data = json.dumps(transaction_data, sort_keys=True)
        signature_hash = hashlib.sha256(signature_data.encode()).hexdigest()
        
        # Add a random salt for uniqueness
        salt = secrets.token_hex(16)
        final_signature = hashlib.sha256(f"{signature_hash}{salt}".encode()).hexdigest()
        
        return final_signature
    
    def _create_secure_transaction(self, wallet, transaction_type: str, amount: Decimal, 
                                 description: str, related_data: Dict = None) -> Transaction:
        """
        Create a blockchain-secured transaction with proper hashing and chaining
        
        Args:
            wallet: Wallet object
            transaction_type: Type of transaction
            amount: Transaction amount
            description: Transaction description
            related_data: Additional data for signature generation
            
        Returns:
            Transaction object with blockchain security features
        """
        with transaction.atomic():
            # Prepare transaction data for signature
            signature_data = {
                'wallet_id': wallet.id,
                'transaction_type': transaction_type,
                'amount': str(amount),
                'description': description,
                'timestamp': timezone.now().isoformat(),
                'platform_id': 'live_streaming_rewards',
                'related_data': related_data or {}
            }
            
            # Generate digital signature
            digital_signature = self._generate_digital_signature(signature_data)
            
            # Create transaction with blockchain security
            transaction_obj = Transaction.objects.create(
                wallet=wallet,
                transaction_type=transaction_type,
                amount=amount,
                description=description,
                digital_signature=digital_signature
            )
            
            # The transaction hash, previous_hash, and merkle_root are automatically
            # generated in the Transaction model's save() method
            
            self.logger.info(
                f"🔐 Secure transaction created: {transaction_obj.transaction_hash[:12]}... "
                f"for {wallet.user.username} (${amount})"
            )
            
            return transaction_obj
    
    def _confirm_transaction(self, transaction_obj: Transaction) -> bool:
        """
        Confirm a transaction as part of the blockchain security process
        
        Args:
            transaction_obj: Transaction to confirm
            
        Returns:
            True if confirmation successful
        """
        try:
            # Verify transaction integrity
            if not transaction_obj.verify_integrity():
                self.logger.error(f"Transaction integrity check failed: {transaction_obj.id}")
                return False
            
            # Verify chain validity
            if not transaction_obj.get_chain_validity():
                self.logger.error(f"Chain validity check failed: {transaction_obj.id}")
                return False
            
            # Mark as confirmed
            transaction_obj.is_confirmed = True
            transaction_obj.confirmation_count = 1  # In a real blockchain, this would be network confirmations
            transaction_obj.save(update_fields=['is_confirmed', 'confirmation_count'])
            
            self.logger.info(
                f"✅ Transaction confirmed: {transaction_obj.transaction_hash[:12]}... "
                f"Chain valid: {transaction_obj.get_chain_validity()}"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error confirming transaction {transaction_obj.id}: {e}")
            return False
    
    def get_monthly_creator_points(self, year: int, month: int) -> Dict:
        """
        Get all creator points for a specific month with average-based calculation.
        
        New Formula:
        1. Calculate total points for each creator's videos
        2. Divide by number of videos to get average points per video
        3. Use average points to calculate share of payout pool
        
        This ensures creators are rewarded based on average quality per video,
        not just total volume of content.
        
        Returns:
            Dict with creator_id -> averaged_points mapping
        """
        # Get date range for the month
        start_date = datetime(year, month, 1).date()
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date()
        else:
            end_date = datetime(year, month + 1, 1).date()
        
        # Get all active shorts created in this month
        monthly_shorts = Short.objects.filter(
            Q(created_at__date__gte=start_date) & 
            Q(created_at__date__lt=end_date) &
            Q(is_active=True)
        )
        
        creator_data = {}
        for short in monthly_shorts:
            creator_id = short.author.id
            
            # Calculate or get points for this short
            if short.final_reward_score is None:
                # Auto-calculate points using the model's method
                try:
                    points = short.calculate_final_reward_score()
                    short.save(update_fields=['main_reward_score', 'final_reward_score', 'reward_calculated_at'])
                    self.logger.info(f"Auto-calculated points for short {short.id}: {points}")
                except Exception as e:
                    self.logger.error(f"Error calculating points for short {short.id}: {e}")
                    # Fallback to basic calculation
                    points = short.calculate_main_reward_score()
                    short.save(update_fields=['main_reward_score'])
            else:
                points = short.final_reward_score
            
            if creator_id not in creator_data:
                creator_data[creator_id] = {
                    'user': short.author,
                    'username': short.author.username,
                    'total_points': 0,
                    'video_count': 0,
                    'average_points': 0,  # This will be the key metric
                    'shorts': []
                }
            
            creator_data[creator_id]['total_points'] += points
            creator_data[creator_id]['video_count'] += 1
            creator_data[creator_id]['shorts'].append({
                'id': str(short.id),
                'title': short.title,
                'points': points,
                'main_points': short.main_reward_score,
                'ai_bonus': short.ai_bonus_percentage or 0,
                'views': short.view_count,
                'likes': short.like_count,
                'comments': short.comment_count,
                'created_at': short.created_at
            })
        
        # Calculate average points per video for each creator
        creator_points = {}
        for creator_id, data in creator_data.items():
            if data['video_count'] > 0:
                # Calculate average points per video
                average_points = data['total_points'] / data['video_count']
                creator_points[creator_id] = {
                    'user': data['user'],
                    'username': data['username'],
                    'total_points': data['total_points'],
                    'video_count': data['video_count'],
                    'average_points': average_points,  # This is now the primary metric
                    'shorts': data['shorts']
                }
                
                self.logger.info(
                    f"Creator {data['username']}: {data['total_points']} total points "
                    f"÷ {data['video_count']} videos = {average_points:.2f} avg points/video"
                )
        
        return creator_points
    
    def calculate_points_for_uncalculated_shorts(self, year: int = None, month: int = None) -> Dict:
        """
        Calculate points for all shorts that don't have calculated scores yet.
        If year/month provided, only calculate for that month.
        
        Returns:
            Dict with calculation results
        """
        try:
            # Build query for shorts without calculated scores
            query = Q(is_active=True) & Q(final_reward_score__isnull=True)
            
            if year and month:
                start_date = datetime(year, month, 1).date()
                if month == 12:
                    end_date = datetime(year + 1, 1, 1).date()
                else:
                    end_date = datetime(year, month + 1, 1).date()
                query &= Q(created_at__date__gte=start_date) & Q(created_at__date__lt=end_date)
            
            shorts_to_calculate = Short.objects.filter(query)
            
            calculated_count = 0
            error_count = 0
            results = []
            
            for short in shorts_to_calculate:
                try:
                    # Use the model's point calculation method
                    points = short.calculate_final_reward_score()
                    short.save(update_fields=[
                        'main_reward_score', 'ai_bonus_percentage', 'ai_bonus_reward',
                        'final_reward_score', 'reward_calculated_at'
                    ])
                    
                    calculated_count += 1
                    results.append({
                        'short_id': str(short.id),
                        'title': short.title,
                        'author': short.author.username,
                        'points': points,
                        'main_points': short.main_reward_score,
                        'ai_bonus': short.ai_bonus_percentage or 0,
                        'views': short.view_count,
                        'likes': short.like_count,
                        'comments': short.comment_count
                    })
                    
                except Exception as e:
                    error_count += 1
                    self.logger.error(f"Error calculating points for short {short.id}: {e}")
                    results.append({
                        'short_id': str(short.id),
                        'title': short.title,
                        'author': short.author.username,
                        'error': str(e)
                    })
            
            self.logger.info(
                f"Bulk points calculation completed: "
                f"{calculated_count} calculated, {error_count} errors"
            )
            
            return {
                'success': True,
                'calculated_count': calculated_count,
                'error_count': error_count,
                'total_processed': calculated_count + error_count,
                'results': results
            }
            
        except Exception as e:
            self.logger.error(f"Error in bulk points calculation: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def calculate_monthly_revenue_share(self, year: int, month: int, platform_revenue: Decimal) -> Dict:
        """
        Calculate how much each creator should receive from monthly revenue sharing.
        
        Args:
            year: Year for calculation
            month: Month for calculation  
            platform_revenue: Total platform revenue for the month
            
        Returns:
            Dict with calculation details and payout amounts per creator
        """
        try:
            # Get creator points for the month
            creator_points = self.get_monthly_creator_points(year, month)
            
            if not creator_points:
                return {
                    'success': False,
                    'message': 'No creator points found for this month',
                    'year': year,
                    'month': month,
                    'platform_revenue': platform_revenue,
                    'creators_pool': Decimal('0'),
                    'payouts': {}
                }
            
            # Calculate total AVERAGE points across all creators using Decimal for stability
            total_average_points = sum(Decimal(str(data['average_points'])) for data in creator_points.values())
            
            if total_average_points <= 0:
                return {
                    'success': False,
                    'message': 'Total creator average points is zero',
                    'year': year,
                    'month': month,
                    'platform_revenue': platform_revenue,
                    'creators_pool': Decimal('0'),
                    'payouts': {}
                }
            
            # Calculate creator pool (50% of platform revenue)
            creators_pool = platform_revenue * self.platform_revenue_share
            
            # Calculate individual payouts based on AVERAGE points
            payouts = {}
            for creator_id, data in creator_points.items():
                # Use Decimal for percentage calculation; quantize payout to 2 decimals
                avg_points = Decimal(str(data['average_points']))
                creator_avg_pct = (avg_points / total_average_points) if total_average_points > 0 else Decimal('0')
                payout_amount = self._quantize_money(creators_pool * creator_avg_pct)
                
                payouts[creator_id] = {
                    'user': data['user'],
                    'username': data['username'],
                    'total_points': data['total_points'],
                    'video_count': data['video_count'],
                    'average_points': data['average_points'],  # New field
                    'average_points_percentage': float(creator_avg_pct * 100),  # Based on average
                    'payout_amount': payout_amount,
                    'shorts': data['shorts']
                }
                
                self.logger.info(
                    f"Payout calculation for {data['username']}: "
                    f"{data['average_points']:.2f} avg points "
                    f"({float(creator_avg_pct * 100):.1f}% of pool) = ${payout_amount:.2f}"
                )
            
            return {
                'success': True,
                'year': year,
                'month': month,
                'platform_revenue': platform_revenue,
                'creators_pool': creators_pool,
                'platform_keeps': platform_revenue - creators_pool,
                'total_creator_average_points': total_average_points,  # Changed from total_points
                'creators_count': len(creator_points),
                'payouts': payouts
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating monthly revenue share: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'year': year,
                'month': month
            }
    
    def process_monthly_payouts(self, year: int, month: int, platform_revenue: Decimal, 
                               dry_run: bool = True) -> Dict:
        """
        Process actual monthly revenue share payouts to creator wallets.
        
        Args:
            year: Year for payout
            month: Month for payout
            platform_revenue: Total platform revenue for the month
            dry_run: If True, calculate but don't actually create transactions
            
        Returns:
            Dict with payout results
        """
        calculation = self.calculate_monthly_revenue_share(year, month, platform_revenue)
        
        if not calculation['success']:
            return calculation
        
        if dry_run:
            calculation['message'] = 'DRY RUN - No actual transactions created'
            return calculation
        
        # Process actual payouts
        with transaction.atomic():
            try:
                payout_results = []
                total_paid = Decimal('0')
                
                for creator_id, payout_data in calculation['payouts'].items():
                    user = payout_data['user']
                    amount = payout_data['payout_amount']
                    
                    if amount <= 0:
                        continue
                    
                    # Get or create wallet
                    wallet, created = Wallet.objects.get_or_create(user=user)
                    
                    # Create blockchain-secured transaction
                    # Quantize amount to standard currency precision
                    amount = self._quantize_money(amount)
                    transaction_obj = self._create_secure_transaction(
                        wallet=wallet,
                        transaction_type='monthly_revenue_share',
                        amount=amount,
                        description=f'Monthly Revenue Share - {month:02d}/{year} ({payout_data["average_points"]:.2f} avg points)',
                        related_data={
                            'payout_year': year,
                            'payout_month': month,
                            'creator_points': payout_data['average_points'],
                            'platform_revenue': str(platform_revenue),
                            'creators_pool': str(calculation['creators_pool'])
                        }
                    )
                    
                    # Create MonthlyPayout record
                    monthly_payout = MonthlyPayout.objects.create(
                        user=user,
                        payout_year=year,
                        payout_month=month,
                        total_points=payout_data['total_points'],  # Keep for historical record
                        total_platform_points=calculation['total_creator_average_points'],  # Now based on averages
                        platform_revenue=platform_revenue,
                        creator_share_percentage=self.platform_revenue_share,
                        earned_amount=amount,
                        status='completed',
                        paid_at=timezone.now(),
                        payout_transaction=transaction_obj,
                        shorts_count=payout_data.get('video_count', 0),  # Updated field name
                        calculation_details={
                            'points_breakdown': payout_data.get('shorts', []),
                            'average_points': payout_data['average_points'],  # New field
                            'average_points_percentage': payout_data['average_points_percentage'],  # New field
                            'video_count': payout_data.get('video_count', 0),  # New field
                            'creators_pool': str(calculation['creators_pool'])
                        }
                    )
                    
                    # Update wallet
                    wallet.balance = self._quantize_money(wallet.balance + amount)
                    wallet.total_earnings = self._quantize_money(wallet.total_earnings + amount)
                    wallet.save()
                    
                    # 🔐 Confirm transaction in blockchain system
                    confirmation_success = self._confirm_transaction(transaction_obj)
                    if not confirmation_success:
                        self.logger.warning(f"Transaction confirmation failed for {user.username}")
                    
                    # Create audit log
                    AuditLog.objects.create(
                        action_type='monthly_revenue_share',
                        user=user,
                        description=f'Monthly revenue share payout for {month:02d}/{year}',
                        metadata={
                            'transaction_id': str(transaction_obj.id),
                            'transaction_hash': transaction_obj.transaction_hash,
                            'is_confirmed': transaction_obj.is_confirmed,
                            'monthly_payout_id': str(monthly_payout.id),
                            'amount': str(amount),
                            'creator_total_points': payout_data['total_points'],  # Historical
                            'creator_average_points': payout_data['average_points'],  # New metric
                            'average_points_percentage': payout_data['average_points_percentage'],  # New metric
                            'video_count': payout_data.get('video_count', 0),
                            'blockchain_security': {
                                'transaction_hash': transaction_obj.transaction_hash,
                                'previous_hash': transaction_obj.previous_hash,
                                'merkle_root': transaction_obj.merkle_root,
                                'digital_signature': transaction_obj.digital_signature[:20] + '...' if transaction_obj.digital_signature else None
                            }
                        }
                    )
                    
                    payout_results.append({
                        'user_id': creator_id,
                        'username': user.username,
                        'amount': amount,
                        'transaction_id': str(transaction_obj.id),
                        'monthly_payout_id': str(monthly_payout.id),
                        'success': True
                    })
                    
                    total_paid += amount
                
                self.logger.info(
                    f"Processed monthly revenue share for {month:02d}/{year}: "
                    f"${total_paid} paid to {len(payout_results)} creators"
                )
                
                calculation['payout_results'] = payout_results
                calculation['total_paid'] = total_paid
                calculation['message'] = f'Successfully paid ${total_paid} to {len(payout_results)} creators'
                
                return calculation
                
            except Exception as e:
                self.logger.error(f"Error processing monthly payouts: {str(e)}")
                calculation['success'] = False
                calculation['error'] = str(e)
                return calculation
    
    def withdraw_wallet_balance(self, user_id: int) -> Dict:
        """
        Withdraw entire wallet balance for a user.
        Sets wallet balance to 0 and creates withdrawal transaction.
        
        Args:
            user_id: ID of the user to withdraw for
            
        Returns:
            Dict with withdrawal results
        """
        with transaction.atomic():
            try:
                user = User.objects.get(id=user_id)
                wallet = Wallet.objects.get(user=user)
                
                if wallet.balance <= 0:
                    return {
                        'success': False,
                        'message': 'No balance available for withdrawal',
                        'current_balance': wallet.balance
                    }
                
                withdrawal_amount = self._quantize_money(wallet.balance)
                
                # Create blockchain-secured withdrawal transaction
                withdrawal_transaction = self._create_secure_transaction(
                    wallet=wallet,
                    transaction_type='withdrawal',
                    amount=-withdrawal_amount,  # Negative amount for withdrawal
                    description=f'Full wallet withdrawal - ${withdrawal_amount}',
                    related_data={
                        'withdrawal_type': 'full_balance',
                        'previous_balance': str(wallet.balance),
                        'withdrawal_date': timezone.now().isoformat(),
                        'user_id': user.id,
                        'username': user.username
                    }
                )
                
                # Update MonthlyPayout records to withdrawn status
                monthly_payouts = MonthlyPayout.objects.filter(
                    user=user,
                    status='completed'
                ).update(
                    status='withdrawn',
                    withdrawn_at=timezone.now(),
                    withdrawal_transaction=withdrawal_transaction
                )
                
                # Reset wallet balance
                wallet.balance = Decimal('0.00')
                wallet.save()
                
                # 🔐 Confirm withdrawal transaction in blockchain system
                confirmation_success = self._confirm_transaction(withdrawal_transaction)
                if not confirmation_success:
                    self.logger.warning(f"Withdrawal transaction confirmation failed for {user.username}")
                
                # Create audit log
                AuditLog.objects.create(
                    action_type='withdrawal',
                    user=user,
                    description=f'Full wallet withdrawal of ${withdrawal_amount}',
                    metadata={
                        'transaction_id': str(withdrawal_transaction.id),
                        'transaction_hash': withdrawal_transaction.transaction_hash,
                        'is_confirmed': withdrawal_transaction.is_confirmed,
                        'amount': str(withdrawal_amount),
                        'monthly_payouts_updated': monthly_payouts,
                        'blockchain_security': {
                            'transaction_hash': withdrawal_transaction.transaction_hash,
                            'previous_hash': withdrawal_transaction.previous_hash,
                            'merkle_root': withdrawal_transaction.merkle_root,
                            'digital_signature': withdrawal_transaction.digital_signature[:20] + '...' if withdrawal_transaction.digital_signature else None,
                            'chain_valid': withdrawal_transaction.get_chain_validity()
                        }
                    }
                )
                
                self.logger.info(
                    f"User {user.username} withdrew ${withdrawal_amount} "
                    f"(updated {monthly_payouts} monthly payouts)"
                )
                
                return {
                    'success': True,
                    'withdrawal_amount': withdrawal_amount,
                    'transaction_id': str(withdrawal_transaction.id),
                    'monthly_payouts_updated': monthly_payouts,
                    'new_balance': wallet.balance,
                    'message': f'Successfully withdrew ${withdrawal_amount}'
                }
                
            except User.DoesNotExist:
                return {
                    'success': False,
                    'error': 'User not found'
                }
            except Wallet.DoesNotExist:
                return {
                    'success': False,
                    'error': 'Wallet not found for user'
                }
            except Exception as e:
                self.logger.error(f"Error processing withdrawal for user {user_id}: {str(e)}")
                return {
                    'success': False,
                    'error': str(e)
                }
    
    def get_user_monthly_payouts(self, user_id: int, limit: int = 12) -> Dict:
        """
        Get monthly payout history for a user.
        
        Args:
            user_id: ID of the user
            limit: Number of recent payouts to return
            
        Returns:
            Dict with payout history
        """
        try:
            user = User.objects.get(id=user_id)
            
            payouts = MonthlyPayout.objects.filter(
                user=user
            ).order_by('-payout_year', '-payout_month')[:limit]
            
            payout_data = []
            total_earned = Decimal('0')
            total_withdrawn = Decimal('0')
            
            for payout in payouts:
                payout_info = {
                    'id': str(payout.id),
                    'period': payout.payout_period,
                    'year': payout.payout_year,
                    'month': payout.payout_month,
                    'earned_amount': payout.earned_amount,
                    'total_points': payout.total_points,
                    'shorts_count': payout.shorts_count,
                    'status': payout.status,
                    'paid_at': payout.paid_at,
                    'withdrawn_at': payout.withdrawn_at,
                    'is_available_for_withdrawal': payout.is_available_for_withdrawal
                }
                
                payout_data.append(payout_info)
                total_earned += payout.earned_amount
                
                if payout.status == 'withdrawn':
                    total_withdrawn += payout.earned_amount
            
            return {
                'success': True,
                'payouts': payout_data,
                'summary': {
                    'total_earned': total_earned,
                    'total_withdrawn': total_withdrawn,
                    'available_balance': total_earned - total_withdrawn,
                    'payouts_count': len(payout_data)
                }
            }
            
        except User.DoesNotExist:
            return {
                'success': False,
                'error': 'User not found'
            }
        except Exception as e:
            self.logger.error(f"Error getting monthly payouts for user {user_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_5minute_creator_points(self) -> Dict:
        """
        TEST FUNCTION: Get creator points for the last 5 minutes with averaging system.
        Perfect for testing the payout system quickly!
        
        Uses the same averaging logic as monthly payouts:
        - Calculate total points for each creator
        - Divide by number of videos to get average points per video
        - Use average points for payout distribution
        """
        try:
            # Get shorts from the last 5 minutes
            five_minutes_ago = timezone.now() - timedelta(minutes=5)
            
            recent_shorts = Short.objects.filter(
                Q(created_at__gte=five_minutes_ago) &
                Q(is_active=True)
            )
            
            creator_data = {}
            for short in recent_shorts:
                creator_id = short.author.id
                
                # Calculate points using the model's method
                if short.final_reward_score is None:
                    try:
                        points = short.calculate_final_reward_score()
                        short.save(update_fields=['main_reward_score', 'final_reward_score', 'reward_calculated_at'])
                    except Exception as e:
                        points = short.calculate_main_reward_score()
                        short.save(update_fields=['main_reward_score'])
                else:
                    points = short.final_reward_score
                
                if creator_id not in creator_data:
                    creator_data[creator_id] = {
                        'user': short.author,
                        'username': short.author.username,
                        'total_points': 0,
                        'video_count': 0,
                        'average_points': 0,  # This will be the key metric
                        'shorts': []
                    }
                
                creator_data[creator_id]['total_points'] += points
                creator_data[creator_id]['video_count'] += 1
                creator_data[creator_id]['shorts'].append({
                    'id': str(short.id),
                    'title': short.title,
                    'points': points,
                    'views': short.view_count,
                    'likes': short.like_count,
                    'comments': short.comment_count,
                    'created_at': short.created_at
                })
            
            # Calculate average points per video for each creator
            creator_points = {}
            for creator_id, data in creator_data.items():
                if data['video_count'] > 0:
                    # Calculate average points per video
                    average_points = data['total_points'] / data['video_count']
                    creator_points[creator_id] = {
                        'user': data['user'],
                        'username': data['username'],
                        'total_points': data['total_points'],
                        'video_count': data['video_count'],
                        'average_points': average_points,  # Primary metric for payouts
                        'shorts': data['shorts']
                    }
                    
                    self.logger.info(
                        f"5min test - {data['username']}: {data['total_points']} total points "
                        f"÷ {data['video_count']} videos = {average_points:.2f} avg points/video"
                    )
            
            return creator_points
            
        except Exception as e:
            self.logger.error(f"Error getting 3-minute creator points: {str(e)}")
            return {}
    
    def test_5minute_payout(self, platform_revenue: Decimal = Decimal('1000'), 
                           dry_run: bool = True) -> Dict:
        """
        TEST FUNCTION: Process payouts based on last 5 minutes of activity.
        Perfect for quick testing without waiting for a month!
        
        Args:
            platform_revenue: Revenue to distribute (default $1000)
            dry_run: If True, don't create real transactions
        """
        try:
            self.logger.info("Testing 5-minute payout system")
            
            # Get creator points from last 5 minutes
            creator_points = self.get_5minute_creator_points()
            
            if not creator_points:
                return {
                    'success': False,
                    'message': 'No shorts found in the last 5 minutes. Upload a video first!',
                    'suggestion': 'Upload a video and try again',
                    'timeframe': 'Last 5 minutes'
                }
            
            # Calculate total AVERAGE points using Decimal (stability)
            total_average_points = sum(Decimal(str(data['average_points'])) for data in creator_points.values())
            creators_pool = platform_revenue * self.platform_revenue_share
            
            # Calculate payouts based on AVERAGE points
            payouts = {}
            for creator_id, data in creator_points.items():
                # Use Decimal for percentage calculation; quantize to 2 decimals
                avg_points = Decimal(str(data['average_points']))
                avg_points_percentage = (avg_points / total_average_points) if total_average_points > 0 else Decimal('0')
                payout_amount = self._quantize_money(creators_pool * avg_points_percentage)
                
                payouts[creator_id] = {
                    'user': data['user'],
                    'username': data['username'],
                    'total_points': data['total_points'],
                    'video_count': data['video_count'],
                    'average_points': data['average_points'],  # New field
                    'average_points_percentage': float(avg_points_percentage * 100),  # For display
                    'payout_amount': payout_amount,
                    'shorts': data['shorts']
                }
                
                self.logger.info(
                    f"5min test payout - {data['username']}: "
                    f"{data['average_points']:.2f} avg points "
                    f"({avg_points_percentage * 100:.1f}% of pool) = ${payout_amount:.2f}"
                )
            
            result = {
                'success': True,
                'timeframe': 'Last 5 minutes',
                'total_creator_average_points': total_average_points,  # Changed from total_points
                'platform_revenue': platform_revenue,
                'creators_pool': creators_pool,
                'platform_keeps': platform_revenue - creators_pool,
                'payouts': payouts,
                'test_mode': True,
                'dry_run': dry_run
            }
            
            # Process actual payouts if not dry run
            if not dry_run:
                with transaction.atomic():
                    total_paid = Decimal('0')
                    
                    for creator_id, payout_data in payouts.items():
                        user = payout_data['user']
                        amount = payout_data['payout_amount']
                        
                        if amount <= 0:
                            continue
                        
                        # Get or create wallet
                        wallet, created = Wallet.objects.get_or_create(user=user)
                        
                        # Quantize amount and create blockchain-secured test transaction
                        amount = self._quantize_money(amount)
                        transaction_obj = self._create_secure_transaction(
                            wallet=wallet,
                            transaction_type='monthly_revenue_share',
                            amount=amount,
                            description=f'5-Minute Test Payout - {timezone.now().strftime("%H:%M:%S")} ({payout_data["average_points"]:.2f} avg points)',
                            related_data={
                                'test_mode': True,
                                'test_timeframe': '5_minutes',
                                'creator_points': payout_data['average_points'],
                                'video_count': payout_data['video_count'],
                                'platform_revenue': str(platform_revenue)
                            }
                        )
                        
                        # Update wallet
                        wallet.balance = self._quantize_money(wallet.balance + amount)
                        wallet.total_earnings = self._quantize_money(wallet.total_earnings + amount)
                        wallet.save()
                        
                        # 🔐 Confirm test transaction
                        self._confirm_transaction(transaction_obj)
                        
                        total_paid += amount
                
                result['message'] = f'💰 REAL PAYOUT: ${total_paid} distributed to {len(payouts)} creators!'
                result['total_paid'] = total_paid
            else:
                result['message'] = f'🧪 DRY RUN: Would pay ${creators_pool} to {len(payouts)} creators'
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in 3-minute payout test: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


# Global service instance
monthly_revenue_service = MonthlyRevenueShareService()
