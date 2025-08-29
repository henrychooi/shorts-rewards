from django.contrib.auth.models import User
from rest_framework import serializers
from django.core.validators import FileExtensionValidator
from .models import Note, Short, Like, Comment, View, Wallet, Transaction, AuditLog


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
            "is_liked", "comments", "transcript", "audio_quality_score", 
            "transcript_language", "audio_processed_at"
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
    integrity_verified = serializers.SerializerMethodField()
    chain_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = Transaction
        fields = [
            "id", "transaction_type", "amount", "description", "related_short", 
            "created_at", "transaction_hash", "previous_hash", "merkle_root",
            "is_confirmed", "confirmation_count", "integrity_verified", "chain_valid"
        ]
    
    def get_integrity_verified(self, obj):
        return obj.verify_integrity()
    
    def get_chain_valid(self, obj):
        return obj.get_chain_validity()


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ["id", "action_type", "description", "metadata", "log_hash", 
                 "previous_log_hash", "created_at"]


class WalletSerializer(serializers.ModelSerializer):
    view_earnings = serializers.ReadOnlyField()
    like_earnings = serializers.ReadOnlyField()
    comment_earnings = serializers.ReadOnlyField()
    
    class Meta:
        model = Wallet
        fields = ["balance", "total_earnings", "view_earnings", "like_earnings", "comment_earnings", "created_at"]

class AudioQualityAnalysisSerializer(serializers.Serializer):
    """Serializer for audio quality analysis results"""
    quality_score = serializers.FloatField(min_value=0, max_value=100)
    analysis = serializers.CharField(max_length=500)
    metrics = serializers.DictField(required=False)

class TranscriptionSegmentSerializer(serializers.Serializer):
    """Serializer for individual transcription segments"""
    start = serializers.FloatField()
    end = serializers.FloatField()
    text = serializers.CharField()
    avg_logprob = serializers.FloatField(required=False)
    no_speech_prob = serializers.FloatField(required=False)

class TranscriptionResultSerializer(serializers.Serializer):
    """Serializer for Whisper transcription results"""
    success = serializers.BooleanField()
    text = serializers.CharField(required=False)
    language = serializers.CharField(required=False)
    duration = serializers.FloatField(required=False)
    segments = TranscriptionSegmentSerializer(many=True, required=False)
    error = serializers.CharField(required=False)
    audio_file = serializers.CharField()
    video_file = serializers.CharField(required=False)

class VideoProcessingResultSerializer(serializers.Serializer):
    """Serializer for complete video processing results"""
    video_file = serializers.CharField()
    audio_file = serializers.CharField()
    transcription = TranscriptionResultSerializer()
    quality_analysis = AudioQualityAnalysisSerializer()
    processed_at = serializers.CharField(required=False)
    error = serializers.CharField(required=False)

class BatchProcessingResultSerializer(serializers.Serializer):
    """Serializer for batch processing results"""
    success = serializers.BooleanField()
    message = serializers.CharField()
    summary = serializers.DictField()
    results = VideoProcessingResultSerializer(many=True)

class VideoProcessingRequestSerializer(serializers.Serializer):
    """Serializer for single video processing requests"""
    video_filename = serializers.CharField(
        max_length=255,
        validators=[FileExtensionValidator(allowed_extensions=['mp4', 'avi', 'mov', 'mkv'])]
    )

class VideoListItemSerializer(serializers.Serializer):
    """Serializer for video list items"""
    filename = serializers.CharField()
    path = serializers.CharField()
    size_mb = serializers.FloatField()
    modified = serializers.FloatField()

class VideoListResponseSerializer(serializers.Serializer):
    """Serializer for video list response"""
    success = serializers.BooleanField()
    videos = VideoListItemSerializer(many=True)
    total_count = serializers.IntegerField()

class AudioQualityReportSerializer(serializers.Serializer):
    """Serializer for audio quality reports"""
    total_videos = serializers.IntegerField()
    quality_distribution = serializers.DictField()
    average_quality_score = serializers.FloatField()
    processing_errors = serializers.IntegerField()
    detailed_results = VideoProcessingResultSerializer(many=True)

class QualityReportResponseSerializer(serializers.Serializer):
    """Serializer for quality report response"""
    success = serializers.BooleanField()
    report = AudioQualityReportSerializer()

# Model serializers 
class VideoAudioAnalysis(serializers.ModelSerializer):
    """Model serializer for storing audio analysis results in database"""
    
    class Meta:
        model = None  # Replace with your actual model
        fields = [
            'id', 'video_filename', 'audio_filename', 'quality_score',
            'transcription_text', 'analysis_summary', 'processed_at',
            'word_count', 'duration_seconds', 'average_confidence',
            'silence_ratio', 'speech_rate'
        ]
        read_only_fields = ['id', 'processed_at']

# Custom validation serializers
class LMStudioConfigSerializer(serializers.Serializer):
    """Serializer for LMStudio configuration"""
    base_url = serializers.URLField(default='http://localhost:1234/v1')
    model_name = serializers.CharField(default='whisper-small')
    timeout = serializers.IntegerField(default=300, min_value=30, max_value=1800)
    temperature = serializers.FloatField(default=0.0, min_value=0.0, max_value=1.0)

class AudioProcessingConfigSerializer(serializers.Serializer):
    """Serializer for audio processing configuration"""
    sample_rate = serializers.IntegerField(default=16000, min_value=8000, max_value=48000)
    channels = serializers.IntegerField(default=1, min_value=1, max_value=2)
    format = serializers.ChoiceField(choices=['wav', 'mp3', 'flac'], default='wav')
    quality = serializers.ChoiceField(choices=['high', 'medium', 'low'], default='high')