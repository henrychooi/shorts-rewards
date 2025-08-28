from django.db import models
from django.contrib.auth.models import User
import uuid
import os


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

    class Meta:
        indexes = [
            models.Index(fields=['short', 'ip_address']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        username = self.user.username if self.user else "Anonymous"
        return f"View by {username} on {self.short.title or 'Untitled'}"


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
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
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

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=4)
    description = models.CharField(max_length=255)
    related_short = models.ForeignKey(Short, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', '-created_at']),
            models.Index(fields=['transaction_type']),
        ]

    def __str__(self):
        return f"{self.wallet.user.username} - {self.transaction_type} - ${self.amount}"

