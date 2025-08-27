from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Note, Stream, Gift


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]
        read_only_fields = ["id"]
        

class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ["id", "title", "content", "created_at", "author"]
        extra_kwargs = {"author": {"read_only": True}}


class StreamSerializer(serializers.ModelSerializer):
    host_username = serializers.CharField(source="host.username", read_only=True)
    call_cid = serializers.SerializerMethodField()

    class Meta:
        model = Stream
        fields = [
            "id",
            "title",
            "is_live",
            "theatre_mode",
            "started_at",
            "ended_at",
            "host",
            "host_username",
            "stream_key",
            "viewer_count",
            "call_cid",
        ]
        extra_kwargs = {"host": {"read_only": True}, "stream_key": {"read_only": True}}

    def get_call_cid(self, obj):
        return obj.call_cid


class GiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gift
        fields = ["id", "stream", "sender", "gift_type", "amount", "created_at"]
        extra_kwargs = {"sender": {"read_only": True}}


class StreamTokenSerializer(serializers.Serializer):
    """
    Serializer to represent the response your frontend expects when asking
    for a Stream token.
    Response shape:
      { "apiKey": "<STREAM_API_KEY>", "streamToken": "<SIGNED_TOKEN>", "user": { ... } }
    """
    apiKey = serializers.CharField()
    streamToken = serializers.CharField()
    user = UserSerializer()
