from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.utils import timezone
from ..models import Stream
from ..serializers import StreamSerializer

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_stream(request, stream_id):
    try:
        # First try to get the stream without host filter to give proper error messages
        try:
            stream = Stream.objects.get(id=stream_id)
        except Stream.DoesNotExist:
            return Response({'error': 'Stream not found'}, status=status.HTTP_404_NOT_FOUND)
            
        # Check if user is the host
        if stream.host != request.user:
            return Response({
                'error': 'Only the stream host can end the stream',
                'current_user': request.user.username,
                'host': stream.host.username
            }, status=status.HTTP_403_FORBIDDEN)
            
        # Update the stream
        stream.is_live = False
        stream.ended_at = timezone.now()
        stream.save()
            
        return Response({'status': 'success'})
    except Exception as e:
        print(f"Error ending stream: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StreamStart(generics.UpdateAPIView):
    serializer_class = StreamSerializer
    permission_classes = [IsAuthenticated]
    queryset = Stream.objects.all()

    def perform_update(self, serializer):
        stream = self.get_object()
        if stream.host == self.request.user:
            serializer.save(is_live=True, started_at=timezone.now(), ended_at=None)
        else:
            return Response({"error": "You are not the host of this stream"}, status=403)
