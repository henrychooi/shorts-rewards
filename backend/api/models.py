import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Note(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notes")

    def __str__(self):
        return self.title


class Stream(models.Model):
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name="streams", null=True)
    title = models.CharField(max_length=150)
    is_live = models.BooleanField(default=False)
    theatre_mode = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    stream_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    viewer_count = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.stream_key:
            self.stream_key = uuid.uuid4().hex
        super().save(*args, **kwargs)

    @property
    def call_cid(self):
        """
        Returns the call CID used by Stream SDK for this stream.
        Example: 'livestream:42' if the object has been saved and has an id.
        """
        return f"livestream:{self.id}" if self.id else None

    def __str__(self):
        return f"{self.title} ({'LIVE' if self.is_live else 'ENDED'})"


class Gift(models.Model):
    stream = models.ForeignKey(Stream, on_delete=models.CASCADE, related_name="gifts")
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    gift_type = models.CharField(max_length=50, default="rose")
    amount = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount}x {self.gift_type} to stream {self.stream.id}"
