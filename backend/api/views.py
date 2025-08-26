from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from .serializers import UserSerializer, NoteSerializer, StreamSerializer, GiftSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from .models import Note, Stream, Gift
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import json

# RTC connection storage
rtc_connections = {}


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
        # Create the stream with started_at time
        stream = serializer.save(
            host=self.request.user,
            is_live=True,
            started_at=timezone.now(),
            theatre_mode=True  # Enable theatre mode by default
        )
        # Initialize empty RTC connection data
        rtc_connections[str(stream.id)] = {
            'offer': None,
            'viewers': {},
            'host': self.request.user.id
        }
        return stream

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def stream_offer(request, stream_id):
    try:
        stream = Stream.objects.get(id=stream_id)
        stream_id_str = str(stream_id)
        
        if request.method == 'GET':
            # Return the stored offer for viewers
            if stream_id_str not in rtc_connections:
                return Response({'error': 'Stream connection not found'}, status=404)
            return Response({'offer': rtc_connections[stream_id_str]['offer']})
            
        # POST method - streamer setting up the offer
        if stream.host != request.user:
            return Response({'error': 'Only the host can set the offer'}, status=403)
            
        if not stream.is_live:
            return Response({'error': 'Stream is not live'}, status=400)
            
        offer = request.data.get('offer')
        if not offer:
            return Response({'error': 'No offer provided'}, status=400)
            
        rtc_connections[stream_id_str] = {
            'offer': offer,
            'viewers': {},
            'host': request.user.id
        }
        
        return Response({'status': 'success'})
    except Stream.DoesNotExist:
        return Response({'error': 'Stream not found'}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stream_answer(request, stream_id):
    try:
        stream = Stream.objects.get(id=stream_id)
        if not stream.is_live:
            return Response({'error': 'Stream is not live'}, status=400)
            
        answer = request.data.get('answer')
        if not answer:
            return Response({'error': 'No answer provided'}, status=400)
        
        # Validate the answer structure
        if not isinstance(answer, dict) or 'type' not in answer or answer['type'] != 'answer':
            return Response({'error': 'Invalid answer format'}, status=400)
            
        stream_data = rtc_connections.get(str(stream_id))
        if not stream_data:
            return Response({'error': 'Stream connection not found'}, status=404)
            
        # Don't let the host connect as a viewer
        if request.user.id == stream_data.get('host'):
            return Response({'error': 'Host cannot connect as viewer'}, status=400)
            
        viewer_id = str(request.user.id)
        stream_data['viewers'][viewer_id] = answer
        
        return Response({
            'status': 'success',
            'offer': stream_data['offer']
        })
    except Stream.DoesNotExist:
        return Response({'error': 'Stream not found'}, status=404)
    except Exception as e:
        print(f"Error in stream_answer: {e}")
        return Response({'error': 'Internal server error'}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_stream(request, stream_id):
    try:
        stream = Stream.objects.get(id=stream_id, host=request.user)
        stream.is_live = False
        stream.ended_at = timezone.now()
        stream.save()
        
        # Clean up RTC connections
        if str(stream_id) in rtc_connections:
            del rtc_connections[str(stream_id)]
            
        return Response({'status': 'success'})
    except Stream.DoesNotExist:
        return Response({'error': 'Stream not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_stream(request, stream_id):
    try:
        stream = Stream.objects.get(id=stream_id)
        if stream.host != request.user:
            return Response({'error': 'Only the host can end the stream'}, status=403)
            
        stream.is_live = False
        stream.ended_at = timezone.now()
        stream.save()
        
        # Clean up RTC connections
        if str(stream_id) in rtc_connections:
            del rtc_connections[str(stream_id)]
            
        return Response({'status': 'success'})
    except Stream.DoesNotExist:
        return Response({'error': 'Stream not found'}, status=404)
    except Exception as e:
        print(f"Error ending stream: {e}")
        return Response({'error': 'Failed to end stream'}, status=500)


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