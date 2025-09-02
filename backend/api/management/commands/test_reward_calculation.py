from django.core.management.base import BaseCommand
from api.models import Short
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test reward calculation for a specific short'

    def add_arguments(self, parser):
        parser.add_argument('short_id', type=str, help='Short ID (UUID) to test')

    def handle(self, *args, **options):
        short_id = options['short_id']
        
        try:
            short = Short.objects.get(id=short_id, is_active=True)
            
            self.stdout.write(f'Short: {short.id}')
            self.stdout.write(f'Title: {short.title or "Untitled"}')
            self.stdout.write(f'Author: {short.author.username}')
            self.stdout.write('='*50)
            
            # Current values
            self.stdout.write('CURRENT VALUES:')
            self.stdout.write(f'  View count: {short.view_count}')
            self.stdout.write(f'  Like count: {short.like_count}')
            self.stdout.write(f'  Comment count: {short.comment_count}')
            self.stdout.write(f'  Average watch %: {short.average_watch_percentage:.2f}')
            self.stdout.write(f'  Main reward score: {short.main_reward_score or 0:.2f}')
            self.stdout.write(f'  AI bonus %: {short.ai_bonus_percentage or 0:.2f}')
            self.stdout.write(f'  Final reward score: {short.final_reward_score or 0:.2f}')
            self.stdout.write(f'  Reward calculated at: {short.reward_calculated_at}')
            
            # Calculated values
            self.stdout.write('\nCALCULATED VALUES:')
            
            # Update cached counts first
            old_avg_watch = short.average_watch_percentage
            short.update_cached_counts()
            new_avg_watch = short.average_watch_percentage
            
            if abs(old_avg_watch - new_avg_watch) > 0.01:
                self.stdout.write(f'  Updated average watch %: {old_avg_watch:.2f} -> {new_avg_watch:.2f}')
            
            # Calculate main reward
            views_score = short.view_count * 1
            likes_score = short.like_count * 5
            comments_score = short.comment_count * 10
            watch_percentage_score = short.average_watch_percentage * 0.5
            calculated_main_reward = views_score + likes_score + comments_score + watch_percentage_score
            
            self.stdout.write(f'  Views score (count * 1): {short.view_count} * 1 = {views_score}')
            self.stdout.write(f'  Likes score (count * 5): {short.like_count} * 5 = {likes_score}')
            self.stdout.write(f'  Comments score (count * 10): {short.comment_count} * 10 = {comments_score}')
            self.stdout.write(f'  Watch % score (% * 0.5): {short.average_watch_percentage:.2f} * 0.5 = {watch_percentage_score:.2f}')
            self.stdout.write(f'  Calculated main reward: {calculated_main_reward:.2f}')
            
            # Check if needs update
            if abs((short.main_reward_score or 0) - calculated_main_reward) > 0.01:
                self.stdout.write(self.style.WARNING(f'  MISMATCH! Current: {short.main_reward_score or 0:.2f}, Should be: {calculated_main_reward:.2f}'))
                
                # Ask if user wants to fix it
                response = input('\nDo you want to recalculate and fix this short\'s rewards? (y/n): ')
                if response.lower() == 'y':
                    short.recalculate_all_rewards()
                    self.stdout.write(self.style.SUCCESS(f'Fixed! New main reward: {short.main_reward_score:.2f}, Final reward: {short.final_reward_score:.2f}'))
                else:
                    self.stdout.write('No changes made.')
            else:
                self.stdout.write(self.style.SUCCESS('  Reward calculation is correct!'))
                
        except Short.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Short with ID {short_id} not found'))
