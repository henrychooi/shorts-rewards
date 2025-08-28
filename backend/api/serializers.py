from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Note, Short, Like, Comment, View, Wallet, Transaction


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "password"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        print(validated_data)
        user = User.objects.create_user(**validated_data)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    shorts_count = serializers.SerializerMethodField()
    total_likes = serializers.SerializerMethodField()
    total_views = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ["id", "username", "date_joined", "shorts_count", "total_likes", "total_views"]
    
    def get_shorts_count(self, obj):
        return obj.shorts.filter(is_active=True).count()
    
    def get_total_likes(self, obj):
        return sum(short.like_count for short in obj.shorts.filter(is_active=True))
    
    def get_total_views(self, obj):
        return sum(short.view_count for short in obj.shorts.filter(is_active=True))


class CommentSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    reply_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Comment
        fields = ["id", "user", "content", "created_at", "reply_count", "parent"]
        extra_kwargs = {"user": {"read_only": True}}


class ShortSerializer(serializers.ModelSerializer):
    author = UserProfileSerializer(read_only=True)
    like_count = serializers.ReadOnlyField()
    comment_count = serializers.ReadOnlyField()
    is_liked = serializers.SerializerMethodField()
    comments = CommentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Short
        fields = [
            "id", "title", "description", "video", "thumbnail", "author",
            "created_at", "view_count", "duration", "like_count", "comment_count",
            "is_liked", "comments"
        ]
        extra_kwargs = {"author": {"read_only": True}}
    
    def get_is_liked(self, obj):
        user = self.context.get('request').user
        if user.is_authenticated:
            return Like.objects.filter(user=user, short=obj).exists()
        return False


class ShortCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Short
        fields = ["title", "description", "video", "thumbnail", "duration"]
    
    def validate_video(self, value):
        # Validate video file size (max 50MB)
        if value.size > 50 * 1024 * 1024:
            raise serializers.ValidationError("Video file size cannot exceed 50MB.")
        
        # Validate video format
        allowed_formats = ['mp4', 'mov', 'avi', 'webm']
        file_extension = value.name.split('.')[-1].lower()
        if file_extension not in allowed_formats:
            raise serializers.ValidationError(f"Video format must be one of: {', '.join(allowed_formats)}")
        
        return value
    
    def validate_duration(self, value):
        if value and value > 10:
            raise serializers.ValidationError("Video duration cannot exceed 10 seconds.")
        return value


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ["id", "created_at"]
        extra_kwargs = {"user": {"read_only": True}, "short": {"read_only": True}}


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ["id", "title", "content", "created_at", "author"]
        extra_kwargs = {"author": {"read_only": True}}


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["id", "transaction_type", "amount", "description", "related_short", "created_at"]


class WalletSerializer(serializers.ModelSerializer):
    view_earnings = serializers.ReadOnlyField()
    like_earnings = serializers.ReadOnlyField()
    comment_earnings = serializers.ReadOnlyField()
    
    class Meta:
        model = Wallet
        fields = ["balance", "total_earnings", "view_earnings", "like_earnings", "comment_earnings", "created_at"]