from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import generics
from .serializers import UserSerializer, NoteSerializer, StreamSerializer, GiftSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from .models import Note, Stream, Gift
from rest_framework.response import Response
from rest_framework import status


class NoteListCreate(generics.ListCreateAPIView):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Note.objects.filter(author=user)

    def perform_create(self, serializer):
        if serializer.is_valid():
            serializer.save(author=self.request.user)
        else:
            print(serializer.errors)


class NoteDelete(generics.DestroyAPIView):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Note.objects.filter(author=user)


class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]


class StreamListCreate(generics.ListCreateAPIView):
    serializer_class = StreamSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return Stream.objects.filter(is_live=True)

    def perform_create(self, serializer):
        serializer.save(host=self.request.user, is_live=True)


class StreamEnd(generics.UpdateAPIView):
    serializer_class = StreamSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Stream.objects.filter(host=self.request.user, is_live=True)

    def perform_update(self, serializer):
        serializer.save(is_live=False)


class StreamStart(generics.UpdateAPIView):
    """Endpoint to mark a Stream as started and enable theatre mode."""
    serializer_class = StreamSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # only the host can start their stream
        return Stream.objects.filter(host=self.request.user, is_live=False)

    def perform_update(self, serializer):
        from django.utils import timezone

        serializer.save(is_live=True, theatre_mode=True, started_at=timezone.now())


class GiftListCreate(generics.ListCreateAPIView):
    serializer_class = GiftSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Gift.objects.all().order_by("-created_at")
        stream_id = self.request.query_params.get("stream")
        if stream_id:
            qs = qs.filter(stream_id=stream_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)