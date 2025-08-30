from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import calendar
from datetime import datetime

from api.models import (
    MonthlyPayout, PlatformRevenue, Transaction, Wallet, Short
)


class Command(BaseCommand):
    help = 'Process monthly payouts for creators based on their content performance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            required=True,
            help='Year for the payout period (e.g., 2025)'
        )
        parser.add_argument(
            '--month',
            type=int,
            required=True,
            help='Month for the payout period (1-12)'
        )
        parser.add_argument(
            '--revenue',
            type=float,
            required=True,
            help='Total platform revenue for the month (e.g., 10000.00)'
        )
        parser.add_argument(
            '--creator-share',
            type=float,
            default=50.0,
            help='Percentage of revenue to share with creators (default: 50.0)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually creating payouts'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force processing even if payouts already exist for this period'
        )

    def handle(self, *args, **options):
        year = options['year']
        month = options['month']
        total_revenue = Decimal(str(options['revenue']))
        creator_share_percentage = Decimal(str(options['creator_share']))
        dry_run = options['dry_run']
        force = options['force']

        # Validate inputs
        if month < 1 or month > 12:
            raise CommandError('Month must be between 1 and 12')
        
        if creator_share_percentage < 0 or creator_share_percentage > 100:
            raise CommandError('Creator share percentage must be between 0 and 100')

        # Check if payouts already exist
        existing_payouts = MonthlyPayout.objects.filter(
            payout_year=year,
            payout_month=month
        ).count()

        if existing_payouts > 0 and not force:
            raise CommandError(
                f'Monthly payouts already exist for {year}-{month:02d}. '
                'Use --force to recreate them.'
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Processing monthly payouts for {year}-{month:02d}'
            )
        )
        self.stdout.write(f'Total Platform Revenue: ${total_revenue}')
        self.stdout.write(f'Creator Share: {creator_share_percentage}%')

        # Calculate creator pool
        creator_pool = total_revenue * (creator_share_percentage / Decimal('100'))
        platform_keeps = total_revenue - creator_pool

        self.stdout.write(f'Creator Pool: ${creator_pool}')
        self.stdout.write(f'Platform Keeps: ${platform_keeps}')
        self.stdout.write('=' * 50)

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        try:
            with transaction.atomic():
                # Create or update platform revenue record
                platform_revenue, created = PlatformRevenue.objects.get_or_create(
                    year=year,
                    month=month,
                    defaults={
                        'total_revenue': total_revenue,
                        'creator_share_percentage': creator_share_percentage,
                        'creator_pool': creator_pool,
                        'platform_keeps': platform_keeps,
                        'is_finalized': True,
                    }
                )

                if not created and not force:
                    if not dry_run:
                        # Update existing record
                        platform_revenue.total_revenue = total_revenue
                        platform_revenue.creator_share_percentage = creator_share_percentage
                        platform_revenue.creator_pool = creator_pool
                        platform_revenue.platform_keeps = platform_keeps
                        platform_revenue.is_finalized = True
                        platform_revenue.save()

                # Get date range for the month
                start_date = datetime(year, month, 1)
                if month == 12:
                    end_date = datetime(year + 1, 1, 1)
                else:
                    end_date = datetime(year, month + 1, 1)

                # Get creators who have content in this period
                creators_with_content = User.objects.filter(
                    shorts__created_at__gte=start_date,
                    shorts__created_at__lt=end_date,
                    shorts__is_active=True
                ).distinct()

                self.stdout.write(f'Found {creators_with_content.count()} creators with content in this period')

                # Calculate total platform points for the period
                total_platform_points = Decimal('0')
                creator_stats = {}

                for creator in creators_with_content:
                    # Get creator's shorts for the period
                    creator_shorts = Short.objects.filter(
                        author=creator,
                        created_at__gte=start_date,
                        created_at__lt=end_date,
                        is_active=True
                    )

                    # Calculate points for this creator
                    creator_points = Decimal('0')
                    shorts_count = 0

                    for short in creator_shorts:
                        # Points calculation based on engagement
                        view_points = Decimal(str(short.view_count)) * Decimal('1.0')  # 1 point per view
                        like_points = Decimal(str(short.like_count)) * Decimal('5.0')  # 5 points per like
                        comment_points = Decimal(str(short.comment_count)) * Decimal('10.0')  # 10 points per comment
                        
                        # Quality bonuses
                        quality_bonus = Decimal('0')
                        if short.audio_quality_score:
                            quality_bonus += Decimal(str(short.audio_quality_score)) * Decimal('0.1')
                        if short.video_quality_score:
                            quality_bonus += Decimal(str(short.video_quality_score)) * Decimal('0.1')

                        short_points = view_points + like_points + comment_points + quality_bonus
                        creator_points += short_points
                        shorts_count += 1

                    creator_stats[creator.id] = {
                        'user': creator,
                        'points': creator_points,
                        'shorts_count': shorts_count
                    }
                    total_platform_points += creator_points

                self.stdout.write(f'Total platform points: {total_platform_points}')

                if total_platform_points == 0:
                    self.stdout.write(self.style.WARNING('No points to distribute - no payouts will be created'))
                    return

                # Delete existing payouts if force is used
                if force and existing_payouts > 0:
                    if not dry_run:
                        MonthlyPayout.objects.filter(
                            payout_year=year,
                            payout_month=month
                        ).delete()
                    self.stdout.write(f'Deleted {existing_payouts} existing payouts')

                # Create monthly payouts
                payouts_created = 0
                total_paid_out = Decimal('0')

                for creator_id, stats in creator_stats.items():
                    creator = stats['user']
                    creator_points = stats['points']
                    shorts_count = stats['shorts_count']

                    if creator_points <= 0:
                        continue

                    # Calculate creator's share of the pool
                    creator_share = (creator_points / total_platform_points) * creator_pool
                    
                    if creator_share < Decimal('0.01'):  # Minimum payout threshold
                        self.stdout.write(f'Skipping {creator.username} - payout too small: ${creator_share}')
                        continue

                    self.stdout.write(
                        f'{creator.username}: {creator_points} points, '
                        f'{shorts_count} shorts, ${creator_share:.4f}'
                    )

                    if not dry_run:
                        # Ensure user has a wallet
                        wallet, _ = Wallet.objects.get_or_create(user=creator)

                        # Create monthly payout record
                        monthly_payout = MonthlyPayout.objects.create(
                            user=creator,
                            payout_year=year,
                            payout_month=month,
                            total_points=creator_points,
                            total_platform_points=total_platform_points,
                            platform_revenue=total_revenue,
                            creator_share_percentage=creator_share_percentage,
                            earned_amount=creator_share,
                            status='completed',
                            paid_at=timezone.now(),
                            shorts_count=shorts_count,
                            calculation_details={
                                'points_breakdown': f'{creator_points} total points',
                                'platform_points': f'{total_platform_points} platform total',
                                'share_percentage': f'{(creator_points / total_platform_points * 100):.4f}%',
                                'calculation_date': timezone.now().isoformat()
                            }
                        )

                        # Create transaction for the payout
                        payout_transaction = Transaction.objects.create(
                            wallet=wallet,
                            transaction_type='monthly_revenue_share',
                            amount=creator_share,
                            description=f'Monthly revenue share for {year}-{month:02d}',
                            is_confirmed=True
                        )

                        # Link transaction to payout
                        monthly_payout.payout_transaction = payout_transaction
                        monthly_payout.save()

                    payouts_created += 1
                    total_paid_out += creator_share

                # Update platform revenue status
                if not dry_run:
                    platform_revenue.payouts_processed = True
                    platform_revenue.processed_at = timezone.now()
                    platform_revenue.save()

                self.stdout.write('=' * 50)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'{"Would create" if dry_run else "Created"} {payouts_created} monthly payouts'
                    )
                )
                self.stdout.write(f'Total paid out: ${total_paid_out:.4f}')

                if dry_run:
                    # Rollback the transaction in dry run mode
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.WARNING('Dry run completed - no changes saved'))

        except Exception as e:
            raise CommandError(f'Error processing payouts: {str(e)}')
