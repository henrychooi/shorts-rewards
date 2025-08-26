from django.db import models
from django.contrib.auth.models import User


class Note(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notes")

    def __str__(self):
        return self.title


class Stream(models.Model):
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name="streams")
    title = models.CharField(max_length=150)
    is_live = models.BooleanField(default=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({'LIVE' if self.is_live else 'ENDED'})"


class Gift(models.Model):
    stream = models.ForeignKey(Stream, on_delete=models.CASCADE, related_name="gifts")
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    gift_type = models.CharField(max_length=50, default="rose")
    amount = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount}x {self.gift_type} to {self.stream_id}"
