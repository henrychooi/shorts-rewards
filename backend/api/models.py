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
    duration = models.FloatField(help_text="Duration in seconds", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # Audio processing fields
    transcript = models.TextField(blank=True, null=True, help_text="Auto-generated transcript")
    audio_quality_score = models.FloatField(blank=True, null=True, help_text="Audio quality score (0-100)")
    transcript_language = models.CharField(max_length=10, blank=True, null=True, help_text="Detected language")
    audio_processed_at = models.DateTimeField(blank=True, null=True, help_text="When audio processing was completed")
    
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
    def like_count(self):
        return self.likes.count()

    @property
    def comment_count(self):
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
        ('withdrawal', 'Withdrawal'),
        ('bonus', 'Bonus'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
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

