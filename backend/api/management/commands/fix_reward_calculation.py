from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import Short

class Command(BaseCommand):
    help = 'Fix reward calculations for shorts that have 0 final_reward_score despite having engagement'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find shorts with engagement but no final reward score
        shorts_to_fix = Short.objects.filter(
            view_count__gt=0,
            final_reward_score__isnull=True
        )
        
        # Also include shorts with 0 final reward score despite having engagement
        shorts_with_zero_reward = Short.objects.filter(
            view_count__gt=0,
            final_reward_score=0
        )
        
        all_shorts_to_fix = shorts_to_fix.union(shorts_with_zero_reward)
        
        self.stdout.write(f'Found {all_shorts_to_fix.count()} shorts that need reward calculation fixes')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        fixed_count = 0
        
        for short in all_shorts_to_fix:
            old_score = short.final_reward_score
            
            # Calculate the reward
            if not dry_run:
                try:
                    short.auto_calculate_rewards_if_ready()
                    short.refresh_from_db()
                    fixed_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error calculating rewards for short {short.id}: {e}')
                    )
                    continue
            
            # Show what was calculated
            self.stdout.write(
                f'Short {short.id}: views={short.view_count}, likes={short.like_count}, '
                f'comments={short.comment_count}, '
                f'old_reward={old_score}, new_reward={short.final_reward_score}'
            )
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'Fixed reward calculations for {fixed_count} shorts')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Would fix {all_shorts_to_fix.count()} shorts')
            )
