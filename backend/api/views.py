from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import generics
from .serializers import UserSerializer, NoteSerializer, StreamSerializer, GiftSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
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
    permission_classes = [IsAuthenticated]

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


class GiftCreate(generics.CreateAPIView):
    serializer_class = GiftSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)