from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from django.db.models import F
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import (
    UserSerializer, NoteSerializer, ShortSerializer, ShortCreateSerializer,
    LikeSerializer, CommentSerializer, UserProfileSerializer
)
from .models import Note, Short, Like, Comment, View


class ShortsListView(generics.ListAPIView):
    serializer_class = ShortSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return Short.objects.filter(is_active=True).select_related('author').prefetch_related('likes', 'comments')


class ShortCreateView(generics.CreateAPIView):
    serializer_class = ShortCreateSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class ShortDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ShortSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.method == 'GET':
            return Short.objects.filter(is_active=True)
        # For update/delete, only allow the author
        return Short.objects.filter(author=self.request.user, is_active=True)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_like(request, short_id):
    short = get_object_or_404(Short, id=short_id, is_active=True)
    like, created = Like.objects.get_or_create(user=request.user, short=short)
    
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
    
    return Response({
        'liked': liked,
        'like_count': short.like_count
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_comment(request, short_id):
    short = get_object_or_404(Short, id=short_id, is_active=True)
    serializer = CommentSerializer(data=request.data)
    
    if serializer.is_valid():
        serializer.save(user=request.user, short=short)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_comments(request, short_id):
    short = get_object_or_404(Short, id=short_id, is_active=True)
    comments = Comment.objects.filter(short=short, is_active=True, parent=None)
    serializer = CommentSerializer(comments, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny])
def track_view(request, short_id):
    try:
        # Check if the short exists and is active
        short = get_object_or_404(Short, id=short_id, is_active=True)
        
        # Increment view_count for this specific short
        Short.objects.filter(id=short_id, is_active=True).update(
            view_count=F('view_count') + 1
        )
        
        # Get the updated count to return
        short.refresh_from_db()
        
        print(f"DEBUG: View incremented for short {short_id}. New view count: {short.view_count}")
        
        return Response({
            'status': 'success',
            'view_count': short.view_count
        })
        
    except Exception as e:
        print(f"ERROR in track_view: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Failed to track view: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_shorts(request):
    shorts = Short.objects.filter(author=request.user, is_active=True)
    serializer = ShortSerializer(shorts, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def user_profile(request, username):
    user = get_object_or_404(User, username=username)
    user_serializer = UserProfileSerializer(user)
    shorts = Short.objects.filter(author=user, is_active=True)[:20]  # Latest 20 shorts
    shorts_serializer = ShortSerializer(shorts, many=True, context={'request': request})
    
    return Response({
        'user': user_serializer.data,
        'shorts': shorts_serializer.data
    })


# Keep existing Note views for backward compatibility
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