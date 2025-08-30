from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
import uuid
import os
import hashlib
import json
from datetime import datetime


class Short(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=150, blank=True)
    description = models.TextField(max_length=500, blank=True)
    video = models.FileField(upload_to='videos/')
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shorts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0, help_text="Cached count of likes")
    comment_count = models.PositiveIntegerField(default=0, help_text="Cached count of comments")
    average_watch_percentage = models.FloatField(default=0.0, help_text="Average watch percentage (0-100)")
    duration = models.FloatField(help_text="Duration in seconds", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # Audio processing fields
    transcript = models.TextField(blank=True, null=True, help_text="Auto-generated transcript")
    audio_quality_score = models.FloatField(blank=True, null=True, help_text="Audio quality score (0-100)")
    transcript_language = models.CharField(max_length=10, blank=True, null=True, help_text="Detected language")
    audio_processed_at = models.DateTimeField(blank=True, null=True, help_text="When audio processing was completed")

    # Comment analysis fields
    comment_analysis_score = models.FloatField(null=True, blank=True, help_text="Aggregated comment sentiment score (-1 to 1)")
    
    # Video analysis fields using Gemini API
    video_analysis_status = models.CharField(
        max_length=20, 
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='pending',
        help_text="Status of video analysis using Gemini API"
    )
    # Legacy fields (kept for compatibility)
    video_quality_score = models.FloatField(blank=True, null=True, help_text="Legacy: Technical quality score (0-100) from Gemini analysis")
    video_analysis_summary = models.TextField(blank=True, null=True, help_text="AI-generated summary of video content")
    video_content_categories = models.JSONField(default=list, blank=True, help_text="Content categories identified by AI")
    video_engagement_prediction = models.FloatField(blank=True, null=True, help_text="Legacy: Predicted engagement score (0-100)")
    video_sentiment_score = models.FloatField(blank=True, null=True, help_text="Content sentiment analysis (-1 to 1)")
    video_analysis_processed_at = models.DateTimeField(blank=True, null=True, help_text="When video analysis was completed")
    video_analysis_error = models.TextField(blank=True, null=True, help_text="Error message if analysis failed")
    
    # Enhanced video analysis fields
    video_content_engagement = models.FloatField(blank=True, null=True, help_text="Content engagement score (0-100)")
    video_demographic_appeal = models.FloatField(blank=True, null=True, help_text="Demographic appeal score (0-100)")
    video_content_focus = models.FloatField(blank=True, null=True, help_text="Content focus and clarity score (0-100)")
    video_content_sensitivity = models.FloatField(blank=True, null=True, help_text="Content appropriateness score (0-5)")
    video_originality = models.FloatField(blank=True, null=True, help_text="Originality and creativity score (0-100)")
    video_technical_quality = models.FloatField(blank=True, null=True, help_text="Technical production quality score (0-100)")
    video_viral_potential = models.FloatField(blank=True, null=True, help_text="Viral potential and shareability score (0-100)")
    video_overall_score = models.FloatField(blank=True, null=True, help_text="Weighted overall analysis score (0-100)")
    video_detailed_breakdown = models.JSONField(default=dict, blank=True, help_text="Detailed score breakdown")
    video_demographic_analysis = models.JSONField(default=dict, blank=True, help_text="Demographic-specific analysis data")
    
    # Reward System Fields
    main_reward_score = models.FloatField(blank=True, null=True, help_text="Base reward from views, likes, comments")
    ai_bonus_percentage = models.FloatField(blank=True, null=True, help_text="AI bonus percentage from video/audio quality")
    ai_bonus_reward = models.FloatField(blank=True, null=True, help_text="AI bonus reward amount in points")
    moderation_adjustment = models.FloatField(blank=True, null=True, help_text="Moderation adjustment percentage (-20% to +20%)")
    final_reward_score = models.FloatField(blank=True, null=True, help_text="Final calculated reward score")
    reward_calculated_at = models.DateTimeField(blank=True, null=True, help_text="When reward was last calculated")
    
    # Moderation System Fields
    is_flagged_for_moderation = models.BooleanField(default=False, help_text="Automatically flagged when comment score < -0.50")
    moderation_status = models.CharField(
        max_length=20,
        choices=[
            ('none', 'No Moderation Needed'),
            ('flagged', 'Flagged for Review'),
            ('under_review', 'Under Review'),
            ('moderated', 'Moderated'),
            ('cleared', 'Cleared')
        ],
        default='none',
        help_text="Current moderation status"
    )
    moderated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="moderated_shorts", help_text="Admin who performed moderation")
    moderated_at = models.DateTimeField(blank=True, null=True, help_text="When moderation was performed")
    moderation_reason = models.TextField(blank=True, null=True, help_text="Reason for moderation action")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['author']),
            models.Index(fields=['view_count']),
        ]
    
    def __str__(self):
        return f"{self.title or 'Untitled'} by {self.author.username}"
    
    def video_exists(self):
        """Check if the video file actually exists on filesystem"""
        if self.video:
            try:
                return os.path.exists(self.video.path)
            except ValueError:
                # Handle case where video field has no file
                return False
        return False
    
    def thumbnail_exists(self):
        """Check if the thumbnail file actually exists on filesystem"""
        if self.thumbnail:
            try:
                return os.path.exists(self.thumbnail.path)
            except ValueError:
                return False
        return False
    
    def validate_files(self):
        """Check if both video and thumbnail files exist, clean up if not"""
        files_valid = True
        
        if not self.video_exists():
            files_valid = False
        
        if self.thumbnail and not self.thumbnail_exists():
            # Remove thumbnail reference if file doesn't exist
            self.thumbnail = None
            self.save(update_fields=['thumbnail'])
        
        return files_valid
    
    @classmethod
    def cleanup_orphaned_records(cls):
        """Remove database entries for videos that don't exist"""
        orphaned_count = 0
        
        for short in cls.objects.all():
            if not short.video_exists():
                print(f"Deleting orphaned record: {short.title} (ID: {short.id})")
                short.delete()
                orphaned_count += 1
            else:
                # Check thumbnail separately and clean it up if missing
                if short.thumbnail and not short.thumbnail_exists():
                    print(f"Removing missing thumbnail for: {short.title}")
                    short.thumbnail = None
                    short.save(update_fields=['thumbnail'])
        
        return orphaned_count
    
    @classmethod
    def get_valid_shorts(cls):
        """Get only shorts that have valid video files"""
        valid_shorts = []
        for short in cls.objects.all():
            if short.video_exists():
                valid_shorts.append(short)
        return valid_shorts

    @property
    def like_count_calculated(self):
        """Calculate like count from database (for updating cache)"""
        return self.likes.count()

    @property
    def comment_count_calculated(self):
        """Calculate comment count from database (for updating cache)"""
        return self.comments.count()

    # Enhanced analytics properties
    @property
    def total_views(self):
        """Total number of views (including rewatches)"""
        return self.views.count()

    @property
    def unique_viewers(self):
        """Number of unique viewers"""
        return self.views.values('user', 'ip_address').distinct().count()

    @property
    def average_watch_percentage(self):
        """Average watch percentage across all views"""
        views = self.views.all()
        if not views:
            return 0
        total_percentage = sum(view.watch_percentage for view in views)
        return total_percentage / len(views)

    @property
    def completion_rate(self):
        """Percentage of views that were completed (80%+)"""
        total_views = self.total_views
        if total_views == 0:
            return 0
        completed_views = self.views.filter(is_complete_view=True).count()
        return (completed_views / total_views) * 100

    @property
    def total_rewatches(self):
        """Total number of rewatches across all viewers and sessions"""
        # Count additional sessions beyond the first for each user
        total_sessions = 0
        if self.views.exists():
            # Group by user and count sessions per user
            from django.db.models import Count
            user_session_counts = self.views.values('user').annotate(
                session_count=Count('session_id', distinct=True)
            )
            # Total rewatches = total sessions - unique users (first view per user doesn't count as rewatch)
            total_sessions = sum(item['session_count'] for item in user_session_counts)
            unique_users = len([item for item in user_session_counts if item['user'] is not None])
            return max(0, total_sessions - unique_users)
        return 0

    @property
    def unique_rewatchers(self):
        """Number of users who have watched this video more than once"""
        from django.db.models import Count
        return self.views.values('user').annotate(
            session_count=Count('session_id', distinct=True)
        ).filter(session_count__gt=1, user__isnull=False).count()

    @property
    def average_engagement_score(self):
        """Average engagement score across all views"""
        views = self.views.all()
        if not views:
            return 0
        total_score = sum(view.engagement_score for view in views)
        return total_score / len(views)

    def get_analytics_summary(self):
        """Get comprehensive analytics for this video"""
        return {
            'total_views': self.total_views,
            'unique_viewers': self.unique_viewers,
            'view_count': self.view_count,  # Original field
            'like_count': self.like_count,
            'comment_count': self.comment_count,
            'average_watch_percentage': round(self.average_watch_percentage, 2),
            'completion_rate': round(self.completion_rate, 2),
            'total_rewatches': self.total_rewatches,
            'unique_rewatchers': self.unique_rewatchers,
            'average_engagement_score': round(self.average_engagement_score, 2),
            'duration': self.duration,
        }

    def update_cached_counts(self):
        """Update cached like_count, comment_count, and average_watch_percentage"""
        self.like_count = self.like_count_calculated
        self.comment_count = self.comment_count_calculated
        
        # Calculate average watch percentage from views
        views = self.views.all()
        if views:
            total_watch_percentage = sum(view.watch_percentage for view in views if view.watch_percentage is not None)
            valid_views = [view for view in views if view.watch_percentage is not None]
            self.average_watch_percentage = total_watch_percentage / len(valid_views) if valid_views else 0.0
        else:
            self.average_watch_percentage = 0.0
        
        self.save(update_fields=['like_count', 'comment_count', 'average_watch_percentage'])

    def calculate_main_reward_score(self):
        """
        Calculate main reward based on views, likes, comments, and watch percentage.
        Formula: (views * 1) + (likes * 5) + (comments * 10) + (avg_watch_percentage * 0.5)
        """
        views_score = self.view_count * 1
        likes_score = self.like_count * 5
        comments_score = self.comment_count * 10
        watch_percentage_score = self.average_watch_percentage * 0.5  # New component
        
        main_score = views_score + likes_score + comments_score + watch_percentage_score
        self.main_reward_score = main_score
        return main_score

    def calculate_ai_bonus_percentage(self):
        """
        Calculate AI bonus percentage from video quality, audio quality, and comment sentiment.
        This uses a smooth, continuous formula rather than rigid tiers.
        
        Components:
        1. Video Quality (0-100) -> contributes up to 30% bonus
        2. Audio Quality (0-100) -> contributes up to 15% bonus  
        3. Comment Sentiment (-1 to +1) -> contributes up to 5% bonus
        
        Formula uses smooth curves to avoid rigid boundaries:
        - Video: 30% * (score/100)^1.5 (emphasis on high quality)
        - Audio: 15% * (score/100)^1.2 (slightly less emphasis)
        - Sentiment: 5% * normalized_sentiment_score
        
        Maximum total bonus: 50%
        """
        video_bonus = 0
        audio_bonus = 0
        sentiment_bonus = 0
        
        # Video quality bonus (0-30%)
        if self.video_overall_score:
            # Use power curve to emphasize high quality scores
            normalized_video = max(0, min(100, self.video_overall_score)) / 100
            video_bonus = 30 * (normalized_video ** 1.5)
        
        # Audio quality bonus (0-15%)
        if self.audio_quality_score:
            normalized_audio = max(0, min(100, self.audio_quality_score)) / 100
            audio_bonus = 15 * (normalized_audio ** 1.2)
        
        # Comment sentiment bonus (0-5%)
        # Calculate average sentiment from comments
        comments = self.comments.filter(is_active=True, sentiment_score__isnull=False)
        if comments.exists():
            avg_sentiment = sum(c.sentiment_score for c in comments) / len(comments)
            # Normalize sentiment from [-1, 1] to [0, 1] and apply bonus
            normalized_sentiment = (avg_sentiment + 1) / 2  # Convert [-1,1] to [0,1]
            sentiment_bonus = 5 * normalized_sentiment
        
        total_bonus = video_bonus + audio_bonus + sentiment_bonus
        # Cap at 50% maximum
        total_bonus = min(50, total_bonus)
        
        self.ai_bonus_percentage = round(total_bonus, 2)
        
        # Calculate actual bonus amount
        if self.main_reward_score:
            self.ai_bonus_reward = round(self.main_reward_score * (total_bonus / 100), 2)
        else:
            self.ai_bonus_reward = 0
            
        return total_bonus

    def check_and_update_moderation_flag(self):
        """
        Check if short should be flagged for moderation based on comment sentiment
        Automatically flags when comment score is outside -0.8 to 0.8 range
        """
        if self.comment_analysis_score is not None:
            # Flag if sentiment is too extreme (outside -0.8 to 0.8 range)
            should_be_flagged = (self.comment_analysis_score < -0.8 or self.comment_analysis_score > 0.8)
            
            if should_be_flagged and not self.is_flagged_for_moderation:
                # Flag for moderation
                self.is_flagged_for_moderation = True
                self.moderation_status = 'flagged'
                self.save(update_fields=['is_flagged_for_moderation', 'moderation_status'])
                
            elif not should_be_flagged and self.is_flagged_for_moderation and self.moderation_status == 'flagged':
                # Unflag if comment score is back within acceptable range and hasn't been manually moderated
                self.is_flagged_for_moderation = False
                self.moderation_status = 'cleared'
                self.save(update_fields=['is_flagged_for_moderation', 'moderation_status'])
                
        return self.is_flagged_for_moderation

    def auto_calculate_rewards_if_ready(self):
        """
        Automatically calculate rewards if basic engagement data is available
        Logic: Can always calculate basic rewards from views/likes/comments, 
               AI bonuses are added when analysis scores are available
        """
        has_video_score = self.video_overall_score is not None
        has_audio_score = self.audio_quality_score is not None
        has_comment_score = self.comment_analysis_score is not None
        
        # Can always calculate basic rewards from engagement metrics
        # AI bonuses are added when available
        can_calculate = True  # Always allow calculation with basic engagement data
        
        if can_calculate:
            # Calculate main reward
            self.calculate_main_reward_score()
            
            # Calculate AI bonus
            self.calculate_ai_bonus_percentage()
            
            # Check moderation flag (only if we have comment score)
            if has_comment_score:
                self.check_and_update_moderation_flag()
            
            # Calculate final reward
            self.calculate_final_reward_score()
            
            # Update timestamp
            from django.utils import timezone
            self.reward_calculated_at = timezone.now()
            
            # Save all changes
            self.save()
            
            return True
        return False

    def calculate_automatic_moderation_flag(self):
        """
        Calculate if content should be flagged for moderation based on comment sentiment.
        This is ONLY used for flagging content for admin review, NOT for final reward calculation.
        
        Comment score ranges from -1 to 1.
        Flagging logic:
        - Score between -0.8 and 0.8: No flag needed (acceptable sentiment range)
        - Score < -0.8 or > 0.8: FLAG FOR REVIEW (extreme sentiment)
        """
        if self.comment_analysis_score is None:
            return False  # No comment analysis available, no flag needed
        elif self.comment_analysis_score < -0.8 or self.comment_analysis_score > 0.8:
            return True   # Flag for manual review (extreme sentiment)
        else:
            return False  # No flag needed (acceptable range)

    def calculate_final_reward_score(self):
        """
        Calculate the final reward score using the formula:
        final_reward = main_reward + ai_bonus_reward + moderation_adjustment_amount
        
        NEW LOGIC:
        - Only manual admin moderation affects final rewards
        - Automatic moderation is only used for flagging content for review
        - If no manual moderation has been applied, moderation adjustment = 0%
        """
        from django.utils import timezone
        
        # Calculate all components
        main_score = self.calculate_main_reward_score()
        ai_bonus_pct = self.calculate_ai_bonus_percentage()  # This also sets ai_bonus_reward
        
        # Get the calculated AI bonus amount
        ai_bonus_amount = self.ai_bonus_reward or 0
        
        # Only use manual moderation for final reward calculation
        # If no manual moderation has been applied (not moderated), use 0%
        if self.moderation_status == 'moderated' and self.moderation_adjustment is not None:
            mod_adjustment_pct = self.moderation_adjustment
        else:
            mod_adjustment_pct = 0  # No moderation applied
        
        # Calculate moderation adjustment amount
        mod_adjustment_amount = (main_score * mod_adjustment_pct) / 100 if mod_adjustment_pct else 0
        
        final_score = main_score + ai_bonus_amount + mod_adjustment_amount
        
        # Ensure final score is never negative
        final_score = max(0, final_score)
        
        self.final_reward_score = round(final_score, 2)
        self.reward_calculated_at = timezone.now()
        
        return final_score

    def get_reward_breakdown(self):
        """Get detailed breakdown of reward calculation"""
        main_score = self.main_reward_score or 0
        ai_bonus_pct = self.ai_bonus_percentage or 0
        
        # Only use manual moderation for reward breakdown
        if self.moderation_status == 'moderated' and self.moderation_adjustment is not None:
            mod_adjustment_pct = self.moderation_adjustment
        else:
            mod_adjustment_pct = 0  # No moderation applied
        
        ai_bonus_amount = (main_score * ai_bonus_pct) / 100
        mod_adjustment_amount = (main_score * mod_adjustment_pct) / 100
        
        return {
            'main_reward': main_score,
            'ai_bonus_percentage': ai_bonus_pct,
            'ai_bonus_amount': ai_bonus_amount,
            'moderation_adjustment_percentage': mod_adjustment_pct,
            'moderation_adjustment_amount': mod_adjustment_amount,
            'final_reward': self.final_reward_score or 0,
            'is_manually_moderated': self.moderation_status == 'moderated',
            'is_flagged': self.is_flagged_for_moderation,
            'components': {
                'views': self.view_count,
                'likes': self.like_count,
                'comments': self.comment_count,
                'video_quality_score': self.video_overall_score,
                'audio_quality_score': self.audio_quality_score,
                'comment_sentiment_score': self.comment_analysis_score,
            }
        }


class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    short = models.ForeignKey(Short, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'short')
        indexes = [
            models.Index(fields=['user', 'short']),
            models.Index(fields=['short']),
        ]

    def __str__(self):
        return f"{self.user.username} liked {self.short.title or 'Untitled'}"


class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    short = models.ForeignKey(Short, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(max_length=1000)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    # Comment analysis fields
    sentiment_score = models.FloatField(null=True, blank=True, help_text="Sentiment score (-1 to 1)")
    sentiment_label = models.CharField(max_length=20, null=True, blank=True, help_text="Sentiment label (positive/negative/neutral)")
    analyzed_at = models.DateTimeField(null=True, blank=True, help_text="When sentiment analysis was performed")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['short', '-created_at']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"Comment by {self.user.username} on {self.short.title or 'Untitled'}"

    @property
    def reply_count(self):
        return self.replies.filter(is_active=True).count()


class View(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    short = models.ForeignKey(Short, on_delete=models.CASCADE, related_name='views')
    ip_address = models.GenericIPAddressField()
    created_at = models.DateTimeField(auto_now_add=True)
    watch_duration = models.FloatField(default=0.0, help_text="Duration watched in seconds")
    
    # Enhanced engagement tracking
    watch_percentage = models.FloatField(default=0.0, help_text="Percentage of video watched (0-100)")
    max_watch_position = models.FloatField(default=0.0, help_text="Furthest position reached in seconds")
    is_complete_view = models.BooleanField(default=False, help_text="True if watched >= 80%")
    rewatch_count = models.PositiveIntegerField(default=0, help_text="Number of times rewatched")
    engagement_score = models.FloatField(default=0.0, help_text="Calculated engagement score")
    
    # Session tracking
    session_id = models.CharField(max_length=64, blank=True, help_text="Unique session identifier")
    last_position = models.FloatField(default=0.0, help_text="Last watched position in seconds")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['short', 'ip_address']),
            models.Index(fields=['created_at']),
            models.Index(fields=['user', 'short']),
            models.Index(fields=['session_id']),
            models.Index(fields=['watch_percentage']),
        ]
        # Unique constraint to prevent duplicate views per user/session
        unique_together = [['user', 'short', 'session_id']]

    def calculate_watch_percentage(self):
        """Calculate watch percentage based on video duration"""
        if self.short.duration and self.short.duration > 0:
            # Method 1: Use max_watch_position (how far they got in a single viewing)
            position_percentage = (self.max_watch_position / self.short.duration) * 100
            
            # Method 2: Use total watch duration (if they rewatched, they definitely completed it)
            duration_percentage = (self.watch_duration / self.short.duration) * 100
            
            # Use the higher of the two - if they watched 10 seconds of a 5-second video,
            # they definitely completed it (100%), even if max position was only 4.67 seconds
            self.watch_percentage = min(max(position_percentage, duration_percentage), 100)
        else:
            self.watch_percentage = 0
        return self.watch_percentage

    def calculate_engagement_score(self):
        """Calculate engagement score based on watch percentage, completion, and rewatches"""
        score = 0
        
        # Base score from watch percentage (0-50 points)
        score += (self.watch_percentage / 100) * 50
        
        # Completion bonus (20 points)
        if self.is_complete_view:
            score += 20
        
        # Rewatch bonus (5 points per rewatch, max 30 points)
        score += min(self.rewatch_count * 5, 30)
        
        self.engagement_score = min(score, 100)
        return self.engagement_score

    def update_watch_progress(self, current_position, duration_watched):
        """Update watch progress and calculate metrics"""
        self.last_position = current_position
        self.max_watch_position = max(self.max_watch_position, current_position)
        self.watch_duration = duration_watched
        
        # Calculate percentage
        self.calculate_watch_percentage()

        # Check if it's a complete view (95% threshold)
        self.is_complete_view = self.watch_percentage >= 95
        
        # Calculate engagement score
        self.calculate_engagement_score()

    def mark_rewatch(self):
        """Mark this as a rewatch"""
        self.rewatch_count += 1
        self.calculate_engagement_score()

    def __str__(self):
        username = self.user.username if self.user else "Anonymous"
        return f"View by {username} on {self.short.title or 'Untitled'} ({self.watch_percentage:.1f}%)"


# Keep the old Note model for backward compatibility during migration
class Note(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notes")

    def __str__(self):
        return self.title


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Wallet - ${self.balance}"

    @property
    def view_earnings(self):
        return sum(
            t.amount for t in self.transactions.filter(
                transaction_type='view_reward', 
                amount__gt=0
            )
        )

    @property
    def like_earnings(self):
        return sum(
            t.amount for t in self.transactions.filter(
                transaction_type='like_reward', 
                amount__gt=0
            )
        )

    @property
    def comment_earnings(self):
        return sum(
            t.amount for t in self.transactions.filter(
                transaction_type='comment_reward', 
                amount__gt=0
            )
        )


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('view_reward', 'View Reward'),
        ('like_reward', 'Like Reward'),
        ('comment_reward', 'Comment Reward'),
        ('content_creator_reward', 'Content Creator Reward'),
        ('ai_bonus', 'AI Quality Bonus'),
        ('moderation_adjustment', 'Moderation Adjustment'),
        ('monthly_revenue_share', 'Monthly Revenue Share'),
        ('withdrawal', 'Withdrawal'),
        ('bonus', 'Bonus'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=4)
    description = models.CharField(max_length=255)
    related_short = models.ForeignKey(Short, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Blockchain-inspired security fields
    transaction_hash = models.CharField(max_length=64, unique=True, editable=False, null=True, blank=True)
    previous_hash = models.CharField(max_length=64, blank=True, null=True)
    merkle_root = models.CharField(max_length=64, blank=True, null=True)
    digital_signature = models.TextField(blank=True, null=True)
    nonce = models.BigIntegerField(default=0)
    
    # Immutability fields
    is_confirmed = models.BooleanField(default=False)
    confirmation_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', '-created_at']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['transaction_hash']),
            models.Index(fields=['is_confirmed']),
        ]

    def __str__(self):
        return f"{self.wallet.user.username} - {self.transaction_type} - ${self.amount}"

    def calculate_hash(self):
        """Calculate cryptographic hash for this transaction"""
        transaction_data = {
            'id': str(self.id),
            'wallet_id': self.wallet.id,
            'transaction_type': self.transaction_type,
            'amount': str(self.amount),
            'description': self.description,
            'related_short_id': str(self.related_short.id) if self.related_short else None,
            'previous_hash': self.previous_hash,
            'timestamp': self.created_at.isoformat() if self.created_at else datetime.now().isoformat(),
            'nonce': self.nonce
        }
        
        transaction_string = json.dumps(transaction_data, sort_keys=True)
        return hashlib.sha256(transaction_string.encode()).hexdigest()

    def generate_merkle_root(self):
        """Generate Merkle root for transaction verification"""
        # Simplified Merkle root (in production, you'd include multiple transactions)
        data = f"{self.transaction_hash}{self.wallet.id}{self.amount}"
        return hashlib.sha256(data.encode()).hexdigest()

    def save(self, *args, **kwargs):
        # Generate hash before saving if not already set
        if not self.transaction_hash:
            # Get previous transaction hash for chaining
            previous_tx = Transaction.objects.filter(
                wallet=self.wallet
            ).order_by('-created_at').first()
            
            if previous_tx:
                self.previous_hash = previous_tx.transaction_hash
            
            # Generate the transaction hash
            super().save(*args, **kwargs)  # Save first to get created_at
            
            # Generate a unique hash with retry logic
            max_retries = 10
            for attempt in range(max_retries):
                self.nonce = attempt
                calculated_hash = self.calculate_hash()
                
                # Check if hash already exists
                if not Transaction.objects.filter(transaction_hash=calculated_hash).exists():
                    self.transaction_hash = calculated_hash
                    break
            
            self.merkle_root = self.generate_merkle_root()
            super().save(update_fields=['transaction_hash', 'merkle_root', 'nonce'])
        else:
            super().save(*args, **kwargs)

    def verify_integrity(self):
        """Verify transaction integrity using hash"""
        calculated_hash = self.calculate_hash()
        return calculated_hash == self.transaction_hash

    def get_chain_validity(self):
        """Check if this transaction is properly chained to the previous one"""
        if not self.previous_hash:
            return True  # Genesis transaction
            
        previous_tx = Transaction.objects.filter(
            wallet=self.wallet,
            transaction_hash=self.previous_hash
        ).first()
        
        return previous_tx is not None and previous_tx.verify_integrity()


class AuditLog(models.Model):
    """Immutable audit log for all system actions - blockchain-inspired transparency"""
    
    ACTION_TYPES = [
        ('transaction_created', 'Transaction Created'),
        ('wallet_created', 'Wallet Created'),
        ('withdrawal_request', 'Withdrawal Request'),
        ('admin_action', 'Admin Action'),
        ('security_event', 'Security Event'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audit_logs')
    description = models.TextField()
    metadata = models.JSONField(default=dict)  # Store additional data
    
    # Blockchain-inspired fields
    log_hash = models.CharField(max_length=64, unique=True, editable=False)
    previous_log_hash = models.CharField(max_length=64, blank=True, null=True)
    
    # Immutability
    is_immutable = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action_type']),
            models.Index(fields=['log_hash']),
        ]

    def calculate_hash(self):
        """Calculate hash for audit log entry"""
        log_data = {
            'id': str(self.id),
            'action_type': self.action_type,
            'user_id': self.user.id,
            'description': self.description,
            'metadata': self.metadata,
            'previous_log_hash': self.previous_log_hash,
            'timestamp': self.created_at.isoformat() if self.created_at else datetime.now().isoformat()
        }
        
        log_string = json.dumps(log_data, sort_keys=True)
        return hashlib.sha256(log_string.encode()).hexdigest()

    def save(self, *args, **kwargs):
        if not self.log_hash:
            # Get previous audit log hash for chaining
            previous_log = AuditLog.objects.order_by('-created_at').first()
            if previous_log:
                self.previous_log_hash = previous_log.log_hash
            
            super().save(*args, **kwargs)
            self.log_hash = self.calculate_hash()
            super().save(update_fields=['log_hash'])
        else:
            super().save(*args, **kwargs)

    def __str__(self):
        return f"Audit: {self.action_type} - {self.user.username}"


class MonthlyPayout(models.Model):
    """Track monthly revenue share payouts to creators"""
    
    PAYOUT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'), 
        ('completed', 'Completed'),
        ('withdrawn', 'Withdrawn'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='monthly_payouts')
    payout_year = models.PositiveIntegerField()
    payout_month = models.PositiveIntegerField()
    
    # Points and earnings breakdown
    total_points = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_platform_points = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    platform_revenue = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    creator_share_percentage = models.DecimalField(max_digits=5, decimal_places=4, default=0.50)  # 50%
    earned_amount = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    
    # Payout tracking
    status = models.CharField(max_length=20, choices=PAYOUT_STATUS_CHOICES, default='pending')
    paid_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    
    # Related transaction for audit trail
    payout_transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='monthly_payout')
    withdrawal_transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='withdrawn_payout')
    
    # Metadata
    shorts_count = models.PositiveIntegerField(default=0)
    calculation_details = models.JSONField(default=dict, blank=True, help_text="Detailed breakdown of points calculation")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-payout_year', '-payout_month', '-earned_amount']
        unique_together = ['user', 'payout_year', 'payout_month']
        indexes = [
            models.Index(fields=['user', '-payout_year', '-payout_month']),
            models.Index(fields=['status']),
            models.Index(fields=['payout_year', 'payout_month']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.payout_year}/{self.payout_month:02d} - ${self.earned_amount}"
    
    @property
    def payout_period(self):
        """Human readable payout period"""
        return f"{self.payout_year}-{self.payout_month:02d}"
    
    @property
    def is_available_for_withdrawal(self):
        """Check if payout is available for withdrawal"""
        return self.status == 'completed' and self.earned_amount > 0


class PlatformRevenue(models.Model):
    """Track platform revenue for monthly payouts"""
    
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total platform revenue for the month")
    revenue_sources = models.JSONField(default=dict, blank=True, help_text="Breakdown of revenue sources")
    
    # Revenue distribution
    creator_share_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=50.00, help_text="Percentage going to creators")
    creator_pool = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Amount allocated to creators")
    platform_keeps = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Amount platform keeps")
    
    # Status tracking
    is_finalized = models.BooleanField(default=False, help_text="Revenue finalized for payout processing")
    payouts_processed = models.BooleanField(default=False, help_text="Payouts have been processed")
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_revenues')
    
    # Metadata
    notes = models.TextField(blank=True, help_text="Admin notes about this month's revenue")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-year', '-month']
        unique_together = ['year', 'month']
        indexes = [
            models.Index(fields=['year', 'month']),
            models.Index(fields=['is_finalized']),
            models.Index(fields=['payouts_processed']),
        ]
    
    def __str__(self):
        return f"Platform Revenue {self.year}-{self.month:02d}: ${self.total_revenue}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate distribution amounts
        if self.total_revenue:
            self.creator_pool = self.total_revenue * (self.creator_share_percentage / 100)
            self.platform_keeps = self.total_revenue - self.creator_pool
        super().save(*args, **kwargs)
    
    @property
    def period_display(self):
        """Human readable period"""
        return f"{self.year}-{self.month:02d}"
    
    def get_revenue_breakdown(self):
        """Get detailed revenue breakdown"""
        return {
            'total_revenue': self.total_revenue,
            'creator_share_percentage': self.creator_share_percentage,
            'creator_pool': self.creator_pool,
            'platform_keeps': self.platform_keeps,
            'revenue_sources': self.revenue_sources
        }
