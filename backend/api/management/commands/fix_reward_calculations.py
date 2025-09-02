from django.core.management.base import BaseCommand
from django.utils import timezone
from api.models import Short
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix reward calculations for all shorts where engagement metrics may have changed'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making actual changes',
        )
        parser.add_argument(
            '--short-id',
            type=str,
            help='Fix rewards for a specific short (UUID)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        short_id = options.get('short_id')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        if short_id:
            # Fix specific short
            try:
                short = Short.objects.get(id=short_id, is_active=True)
                self.fix_short_rewards(short, dry_run)
            except Short.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Short with ID {short_id} not found'))
                return
        else:
            # Fix all shorts that have engagement data but may have incorrect rewards
            shorts = Short.objects.filter(is_active=True).select_related('author')
            
            self.stdout.write(f'Found {shorts.count()} shorts to check')
            
            fixed_count = 0
            for short in shorts:
                if self.fix_short_rewards(short, dry_run):
                    fixed_count += 1
            
            if dry_run:
                self.stdout.write(self.style.SUCCESS(f'Would fix {fixed_count} shorts'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Fixed {fixed_count} shorts'))

    def fix_short_rewards(self, short, dry_run=False):
        """Fix reward calculation for a single short"""
        # Store original values for comparison
        original_main_reward = short.main_reward_score
        original_final_reward = short.final_reward_score
        original_avg_watch_pct = short.average_watch_percentage
        
        # Calculate what the values should be
        if not dry_run:
            # Actually update the short
            short.recalculate_all_rewards()
            new_main_reward = short.main_reward_score
            new_final_reward = short.final_reward_score
            new_avg_watch_pct = short.average_watch_percentage
        else:
            # Just calculate without saving
            # Update cached counts
            short.update_cached_counts()
            # Calculate what main reward should be
            views_score = short.view_count * 1
            likes_score = short.like_count * 5
            comments_score = short.comment_count * 10
            watch_percentage_score = short.average_watch_percentage * 0.5
            new_main_reward = views_score + likes_score + comments_score + watch_percentage_score
            
            # For final reward, we'd need to calculate AI bonus and moderation
            # For simplicity in dry run, just show main reward change
            new_final_reward = short.final_reward_score  # Keep original for dry run
            new_avg_watch_pct = short.average_watch_percentage
        
        # Check if changes were made
        main_reward_changed = abs((original_main_reward or 0) - (new_main_reward or 0)) > 0.01
        final_reward_changed = abs((original_final_reward or 0) - (new_final_reward or 0)) > 0.01
        avg_watch_changed = abs((original_avg_watch_pct or 0) - (new_avg_watch_pct or 0)) > 0.01
        
        if main_reward_changed or final_reward_changed or avg_watch_changed:
            self.stdout.write(
                f'{"[DRY RUN] " if dry_run else ""}Short {short.id} (views: {short.view_count}, likes: {short.like_count}, comments: {short.comment_count})'
            )
            
            if avg_watch_changed:
                self.stdout.write(f'  Average watch %: {original_avg_watch_pct:.2f} -> {new_avg_watch_pct:.2f}')
            
            if main_reward_changed:
                self.stdout.write(f'  Main reward: {original_main_reward or 0:.2f} -> {new_main_reward or 0:.2f}')
            
            if final_reward_changed:
                self.stdout.write(f'  Final reward: {original_final_reward or 0:.2f} -> {new_final_reward or 0:.2f}')
            
            return True
        
        return False
