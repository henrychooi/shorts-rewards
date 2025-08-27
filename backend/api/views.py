# backend/api/views.py
import json
from datetime import datetime, timedelta

import jwt
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .serializers import UserSerializer, NoteSerializer, StreamSerializer, GiftSerializer, UserListSerializer
from .models import Note, Stream, Gift

# In-memory RTC offer/answer storage for simple signaling fallback.
# key: str(stream_id) -> { 'offer': <sdp/obj> | None, 'viewers': {viewer_id: answer}, 'host': <host_user_id> }
rtc_connections = {}


class NoteListCreate(generics.ListCreateAPIView):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Note.objects.filter(author=user)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


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

class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserListSerializer
    permission_classes = [AllowAny]


class StreamListCreate(generics.ListCreateAPIView):
    serializer_class = StreamSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        # Return only live streams for listing
        return Stream.objects.filter(is_live=True)

    def perform_create(self, serializer):
        stream = serializer.save(
            host=self.request.user,
            is_live=True,
            started_at=timezone.now(),
            theatre_mode=True
        )

        # Initialize simple in-memory signaling container
        rtc_connections[str(stream.id)] = {
            "offer": None,
            "viewers": {},
            "host": self.request.user.id,
        }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def stream_offer(request, stream_id):
    """
    GET -> viewer fetches host's offer (if present)
    POST -> host sets their offer SDP (host only)
    """
    try:
        stream = Stream.objects.get(id=stream_id)
    except Stream.DoesNotExist:
        return Response({"error": "Stream not found"}, status=status.HTTP_404_NOT_FOUND)

    stream_key = str(stream_id)

    if request.method == "GET":
        conn = rtc_connections.get(stream_key)
        if not conn:
            return Response({"error": "Stream connection not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"offer": conn.get("offer")}, status=status.HTTP_200_OK)

    # POST: host is setting the offer
    if stream.host != request.user:
        return Response({"error": "Only the host can set the offer"}, status=status.HTTP_403_FORBIDDEN)

    if not stream.is_live:
        return Response({"error": "Stream is not live"}, status=status.HTTP_400_BAD_REQUEST)

    offer = request.data.get("offer")
    if not offer:
        return Response({"error": "No offer provided"}, status=status.HTTP_400_BAD_REQUEST)

    rtc_connections[stream_key] = {
        "offer": offer,
        "viewers": {},
        "host": request.user.id,
    }

    return Response({"status": "success"}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def stream_answer(request, stream_id):
    """
    Viewer posts their answer to this endpoint. The server stores the viewer's answer
    in rtc_connections[stream_id]['viewers'][viewer_id] so the host can retrieve it.
    Returns the stored offer so the viewer can validate it (or for convenience).
    """
    try:
        stream = Stream.objects.get(id=stream_id)
    except Stream.DoesNotExist:
        return Response({"error": "Stream not found"}, status=status.HTTP_404_NOT_FOUND)

    if not stream.is_live:
        return Response({"error": "Stream is not live"}, status=status.HTTP_400_BAD_REQUEST)

    answer = request.data.get("answer")
    if not answer or not isinstance(answer, dict) or answer.get("type") != "answer":
        return Response({"error": "Invalid answer provided"}, status=status.HTTP_400_BAD_REQUEST)

    conn = rtc_connections.get(str(stream_id))
    if not conn:
        return Response({"error": "Stream connection not found"}, status=status.HTTP_404_NOT_FOUND)

    # Prevent host from posting an answer as a viewer
    if request.user.id == conn.get("host"):
        return Response({"error": "Host cannot connect as viewer"}, status=status.HTTP_400_BAD_REQUEST)

    viewer_id = str(request.user.id)
    conn["viewers"][viewer_id] = answer

    return Response({"status": "success", "offer": conn.get("offer")}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def end_stream(request, stream_id):
    """
    Host ends the stream. Only the stream host may end the stream.
    """
    try:
        stream = Stream.objects.get(id=stream_id)
    except Stream.DoesNotExist:
        return Response({"error": "Stream not found"}, status=status.HTTP_404_NOT_FOUND)

    if stream.host != request.user:
        return Response({"error": "Only the host can end the stream"}, status=status.HTTP_403_FORBIDDEN)

    stream.is_live = False
    stream.ended_at = timezone.now()
    stream.save()

    # Clean up in-memory RTC entries
    rtc_connections.pop(str(stream_id), None)

    return Response({"status": "success"}, status=status.HTTP_200_OK)


class StreamStart(generics.UpdateAPIView):
    """
    Optional: mark a stream as started. Only for logged-in host users.
    """
    serializer_class = StreamSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Stream.objects.filter(host=self.request.user, is_live=False)

    def perform_update(self, serializer):
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


#
# New endpoint: server-side creation of Stream call tokens for GetStream Video SDK
# Frontend calls this endpoint with Authorization: Bearer <JWT access token>
# to receive a call token (signed by your STREAM_API_SECRET) and apiKey + user info.
#
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_stream_token(request):
    """
    Generates a Stream 'call token' for the currently authenticated user.
    Optional POST body: { "stream_id": <int> } to scope token to a single call CID (e.g. livestream:<id>).

    Response:
      {
        "apiKey": "<STREAM_API_KEY>",
        "streamToken": "<SIGNED_JWT>",
        "user": { "id": ..., "username": ... }
      }
    """
    user = request.user
    stream_id = request.data.get("stream_id")

    # Prepare call_cids claim if stream_id was provided and valid
    call_cids = None
    if stream_id is not None:
        try:
            s = Stream.objects.get(id=stream_id)
        except Stream.DoesNotExist:
            return Response({"error": "Stream not found"}, status=status.HTTP_404_NOT_FOUND)

        # Optionally disallow tokens for non-live streams (choose policy)
        if not s.is_live:
            return Response({"error": "Stream is not live"}, status=status.HTTP_400_BAD_REQUEST)

        call_cids = [f"livestream:{stream_id}"]

    now = datetime.utcnow()
    exp = now + timedelta(hours=1)  # token valid for 1 hour by default; tune as needed

    payload = {
        "user_id": str(user.id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    if call_cids:
        payload["call_cids"] = call_cids

    # Optionally include role claim if you require different roles: "role": "user" or "admin"
    # payload["role"] = "user"

    try:
        token = jwt.encode(payload, settings.STREAM_API_SECRET, algorithm="HS256")
        # PyJWT >=2 returns str, older versions may return bytes
        if isinstance(token, bytes):
            token = token.decode("utf-8")
    except Exception as e:
        return Response({"error": "Failed to create stream token", "detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    user_data = UserSerializer(user).data

    return Response({
        "apiKey": settings.STREAM_API_KEY,
        "streamToken": token,
        "user": user_data
    }, status=status.HTTP_200_OK)
