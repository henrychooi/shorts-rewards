from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.models import Short
from api.reward_service import reward_service


class Command(BaseCommand):
    help = 'Calculate and process content creator rewards'

    def add_arguments(self, parser):
        parser.add_argument(
            '--calculate-only',
            action='store_true',
            help='Only calculate rewards without processing payouts',
        )
        parser.add_argument(
            '--process-payouts',
            action='store_true',
            help='Process actual payouts for calculated rewards',
        )
        parser.add_argument(
            '--creator',
            type=str,
            help='Process rewards for specific creator (username)',
        )
        parser.add_argument(
            '--short-id',
            type=str,
            help='Process rewards for specific short (UUID)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of shorts to process (default: 100)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting Content Creator Reward Processing...')
        )

        # Process specific short
        if options['short_id']:
            try:
                short = Short.objects.get(id=options['short_id'])
                self.process_single_short(short, options)
                return
            except Short.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Short with ID {options["short_id"]} not found')
                )
                return

        # Process specific creator
        if options['creator']:
            try:
                user = User.objects.get(username=options['creator'])
                shorts = Short.objects.filter(author=user, is_active=True)
                self.process_shorts_batch(shorts, options)
                return
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User {options["creator"]} not found')
                )
                return

        # Process all shorts
        shorts = Short.objects.filter(is_active=True)
        self.process_shorts_batch(shorts, options)

    def process_single_short(self, short, options):
        """Process rewards for a single short"""
        self.stdout.write(f'Processing short: {short.title or "Untitled"} by {short.author.username}')
        
        if options['calculate_only']:
            breakdown = reward_service.calculate_reward_for_short(short)
            self.display_reward_breakdown(short, breakdown)
        
        elif options['process_payouts']:
            result = reward_service.process_reward_payout(short)
            self.display_payout_result(short, result)
        
        else:
            # Default: calculate and show breakdown
            breakdown = reward_service.calculate_reward_for_short(short)
            self.display_reward_breakdown(short, breakdown)

    def process_shorts_batch(self, shorts_queryset, options):
        """Process rewards for multiple shorts"""
        total_shorts = shorts_queryset.count()
        limit = options['limit']
        
        self.stdout.write(f'Found {total_shorts} shorts to process (limit: {limit})')
        
        if options['calculate_only']:
            result = reward_service.calculate_batch_rewards(shorts_queryset, limit)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Batch calculation completed: {result["processed"]} processed, '
                    f'{result["errors"]} errors'
                )
            )
        
        elif options['process_payouts']:
            processed = 0
            errors = 0
            
            for short in shorts_queryset[:limit]:
                result = reward_service.process_reward_payout(short)
                if result['success']:
                    processed += 1
                    self.stdout.write(f'✓ Paid out ${result["reward_amount"]} to {short.author.username}')
                else:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(f'✗ Failed to pay {short.author.username}: {result["message"]}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f'Batch payout completed: {processed} processed, {errors} errors')
            )
        
        else:
            # Default: show summary for top creators
            self.show_creator_summaries(shorts_queryset)

    def display_reward_breakdown(self, short, breakdown):
        """Display detailed reward breakdown for a short"""
        self.stdout.write(f'\n📊 Reward Breakdown for "{short.title or "Untitled"}"')
        self.stdout.write(f'Author: {short.author.username}')
        self.stdout.write(f'Created: {short.created_at.strftime("%Y-%m-%d %H:%M")}')
        self.stdout.write('─' * 50)
        
        # Main metrics
        components = breakdown['components']
        self.stdout.write(f'Views: {components["views"]}')
        self.stdout.write(f'Likes: {components["likes"]}')
        self.stdout.write(f'Comments: {components["comments"]}')
        
        # Scores
        self.stdout.write(f'Video Quality: {components["video_quality_score"] or "N/A"}')
        self.stdout.write(f'Audio Quality: {components["audio_quality_score"] or "N/A"}')
        self.stdout.write(f'Comment Sentiment: {components["comment_sentiment_score"] or "N/A"}')
        
        self.stdout.write('─' * 50)
        
        # Reward calculation
        self.stdout.write(f'Main Reward: {breakdown["main_reward"]} points')
        self.stdout.write(f'AI Bonus: +{breakdown["ai_bonus_percentage"]}% (+{breakdown["ai_bonus_amount"]:.1f} points)')
        self.stdout.write(f'Moderation: {breakdown["moderation_adjustment_percentage"]:+.1f}% ({breakdown["moderation_adjustment_amount"]:+.1f} points)')
        
        self.stdout.write(self.style.SUCCESS(f'Final Reward: {breakdown["final_reward"]:.1f} points'))
        
        # Currency equivalent
        currency_value = breakdown["final_reward"] * float(reward_service.POINTS_TO_CURRENCY_RATE)
        self.stdout.write(self.style.SUCCESS(f'Currency Value: ${currency_value:.3f}'))
        self.stdout.write('')

    def display_payout_result(self, short, result):
        """Display payout result"""
        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Payout successful for {short.author.username}: '
                    f'{result["reward_points"]:.1f} points = ${result["reward_amount"]}'
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'✗ Payout failed for {short.author.username}: {result["message"]}')
            )

    def show_creator_summaries(self, shorts_queryset):
        """Show summary for top creators"""
        # Get unique creators from the queryset
        creators = User.objects.filter(
            shorts__in=shorts_queryset
        ).distinct()
        
        self.stdout.write('\n🏆 Creator Reward Summaries')
        self.stdout.write('=' * 60)
        
        for creator in creators[:10]:  # Top 10 creators
            summary = reward_service.get_creator_reward_summary(creator)
            
            if 'error' in summary:
                self.stdout.write(f'❌ {creator.username}: Error - {summary["error"]}')
                continue
            
            self.stdout.write(f'\n👤 {creator.username}')
            self.stdout.write(f'   Shorts: {summary["total_shorts"]}')
            self.stdout.write(f'   Total Points: {summary["total_final_reward_points"]:.1f}')
            self.stdout.write(f'   Wallet Balance: ${summary["wallet_balance"]}')
            self.stdout.write(f'   Total Earnings: ${summary["total_earnings"]}')
        
        self.stdout.write('\n' + '=' * 60)
