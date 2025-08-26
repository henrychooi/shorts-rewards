from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Note, Stream, Gift


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "password"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        print(validated_data)
        user = User.objects.create_user(**validated_data)
        return user


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ["id", "title", "content", "created_at", "author"]
        extra_kwargs = {"author": {"read_only": True}}


class StreamSerializer(serializers.ModelSerializer):
    host_username = serializers.CharField(source="host.username", read_only=True)
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
        ]
        extra_kwargs = {"host": {"read_only": True}}


class GiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gift
        fields = ["id", "stream", "sender", "gift_type", "amount", "created_at"]
        extra_kwargs = {"sender": {"read_only": True}}