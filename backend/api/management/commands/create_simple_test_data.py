from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.models import Short, Like, Comment
from django.utils import timezone
from datetime import datetime
import random


class Command(BaseCommand):
    help = 'Create simple test data for testing revenue sharing'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='Year (default: current year for recent test)')
        parser.add_argument('--month', type=int, help='Month (default: current month for recent test)')
        parser.add_argument('--count', type=int, default=3)
        parser.add_argument('--recent', action='store_true', help='Create videos in last 3 minutes for testing')

    def handle(self, *args, **options):
        year = options.get('year')
        month = options.get('month')
        count = options['count']
        recent = options['recent']
        
        # If recent flag is set, use current time for 5-minute test
        if recent or (not year and not month):
            now = timezone.now()
            year = now.year
            month = now.month
            self.stdout.write(f'🕐 Creating RECENT test data for 5-minute payout test...')
        else:
            self.stdout.write(f'📅 Creating test data for {month:02d}/{year}...')
        
        # Get or create test users (ensure we have exactly 3 creators for testing)
        users = []
        for i in range(1, 4):  # Create 3 users (creator1 to creator3)
            user, created = User.objects.get_or_create(
                username=f'creator{i}',
                defaults={
                    'email': f'creator{i}@test.com',
                    'first_name': f'Creator{i}'
                }
            )
            if created:
                user.set_password('testpass123')
                user.save()
                self.stdout.write(f'👤 Created user: {user.username}')
            users.append(user)
        
        self.stdout.write(f'👥 Using {len(users)} creators: {[u.username for u in users]}')
        
        # Create test shorts with varying video counts per creator
        # Some creators get many videos, some get few - tests averaging system
        video_distribution = [4, 1, 2]  # creator1: 10 videos, creator2: 1 video, creator3: 3 videos
        
        created_shorts = []
        video_id = 1
        
        for creator_index, user in enumerate(users):
            num_videos = video_distribution[creator_index]
            self.stdout.write(f'🎬 Creating {num_videos} videos for {user.username}...')
            
            for video_num in range(num_videos):
                if recent:
                    # Create videos in the last 4 minutes for 5-minute test
                    minutes_ago = 0  # 0-4 minutes ago
                    seconds_ago = 0
                    test_date = timezone.now() - timezone.timedelta(minutes=minutes_ago, seconds=seconds_ago)
                else:
                    # Create for specific month
                    day = random.randint(1, 28)
                    hour = random.randint(9, 17)
                    minute = random.randint(0, 59)
                    test_date = timezone.make_aware(datetime(year, month, day, hour, minute, 0))
                
                # Vary quality across videos - some high quality, some low
                if video_num % 3 == 0:  # Every 3rd video is high quality
                    views = random.randint(300, 500)
                    likes_ratio = 0.10  # High like ratio
                    comments_ratio = 0.06  # High comment ratio
                else:  # Others are lower quality
                    views = random.randint(20, 100)
                    likes_ratio = 0.05
                    comments_ratio = 0.02
                
                short = Short.objects.create(
                    title=f"{user.username} Video {video_num+1} - {test_date.strftime('%H:%M:%S')}" if recent else f"{user.username} Video {video_num+1} - {test_date.strftime('%m-%d %H:%M')}",
                    description=f"Test content for {user.username} - Quality level {['Low', 'Medium', 'High'][video_num % 3]}",
                    author=user,
                    view_count=views,
                    is_active=True
                )
                
                # Update created_at properly
                short.created_at = test_date
                short.save(update_fields=['created_at'])
                
                # Create likes based on quality
                num_likes = int(views * likes_ratio) + random.randint(0, 5)
                for j in range(min(num_likes, len(users) * 3)):  # Prevent too many likes
                    like_user = random.choice(users)
                    Like.objects.get_or_create(user=like_user, short=short)
                
                # Create comments based on quality
                comments = [
                    "Bad video!", "Love this!", "Amazing work!",
                    "Keep it up!", "Awesome content!", "Well done!",
                    "So Bad!", "Cool!", "Interesting!"
                ]
                num_comments = int(views * comments_ratio) + random.randint(0, 2)
                for j in range(min(num_comments, 15)):  # Cap comments
                    comment_user = random.choice(users)
                    Comment.objects.create(
                        user=comment_user,
                        short=short,
                        content=random.choice(comments),
                        is_active=True
                    )
                
                created_shorts.append({
                    'title': short.title,
                    'author': user.username,
                    'views': short.view_count,
                    'likes': short.like_count,
                    'comments': short.comment_count,
                    'created_at': short.created_at,
                    'time_info': f"Created {int((timezone.now() - short.created_at).total_seconds() / 60)}min ago" if recent else short.created_at.strftime('%Y-%m-%d %H:%M:%S')
                })
                
                video_id += 1
        
        self.stdout.write(self.style.SUCCESS(f'✅ Created {len(created_shorts)} test shorts across 3 creators'))
        
        # Group by creator for summary
        creator_stats = {}
        for short_info in created_shorts:
            author = short_info['author']
            if author not in creator_stats:
                creator_stats[author] = {'videos': 0, 'total_views': 0, 'total_likes': 0, 'total_comments': 0}
            creator_stats[author]['videos'] += 1
            creator_stats[author]['total_views'] += short_info['views']
            creator_stats[author]['total_likes'] += short_info['likes']
            creator_stats[author]['total_comments'] += short_info['comments']
        
        self.stdout.write(f'\n📊 Creator Distribution (Perfect for Testing Averaging System):')
        for author, stats in creator_stats.items():
            avg_views = stats['total_views'] / stats['videos']
            avg_likes = stats['total_likes'] / stats['videos']
            avg_comments = stats['total_comments'] / stats['videos']
            estimated_points = (avg_views * 1) + (avg_likes * 5) + (avg_comments * 10)
            
            self.stdout.write(
                f"  👤 {author}: {stats['videos']} videos, "
                f"Avg: {avg_views:.1f} views, {avg_likes:.1f} likes, {avg_comments:.1f} comments "
                f"(~{estimated_points:.1f} avg points)"
            )
        
        if recent:
            self.stdout.write(f'\n🚀 Perfect! Now test the 5-minute payout:')
            self.stdout.write(f'  python manage.py test_5min_payout --revenue 5000')
        else:
            self.stdout.write(f'\n🚀 Now test with specific month:')
            self.stdout.write(f'  python manage.py test_revenue_share --year {year} --month {month} --revenue 5000')
