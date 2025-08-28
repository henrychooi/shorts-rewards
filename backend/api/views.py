from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from django.db.models import F
from decimal import Decimal
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import (
    UserSerializer, NoteSerializer, ShortSerializer, ShortCreateSerializer,
    LikeSerializer, CommentSerializer, UserProfileSerializer, WalletSerializer, TransactionSerializer
)
from .models import Note, Short, Like, Comment, View, Wallet, Transaction


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
        # Award like reward to the short's author (only when liked, not unliked)
        like_reward = 0.01  # $0.01 per like
        create_reward_transaction(
            user=short.author,
            transaction_type='like_reward',
            amount=like_reward,
            description=f"Like reward for '{short.title or 'Untitled'}'"[:255],
            related_short=short
        )
    
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
        comment = serializer.save(user=request.user, short=short)
        
        # Award comment reward to the short's author
        comment_reward = 10.005  # $10.005 per comment
        create_reward_transaction(
            user=short.author,
            transaction_type='comment_reward',
            amount=comment_reward,
            description=f"Comment reward for '{short.title or 'Untitled'}'"[:255],
            related_short=short
        )
        
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
        
        # Award view reward to the short's author (small amount per view)
        view_reward = 0.001  # $0.001 per view
        create_reward_transaction(
            user=short.author,
            transaction_type='view_reward',
            amount=view_reward,
            description=f"View reward for '{short.title or 'Untitled'}'"[:255],
            related_short=short
        )
        
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_detail(request):
    """Get wallet information for the authenticated user"""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    serializer = WalletSerializer(wallet)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_transactions(request):
    """Get transaction history for the authenticated user"""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    transactions = Transaction.objects.filter(wallet=wallet)[:50]  # Latest 50 transactions
    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data)


def create_reward_transaction(user, transaction_type, amount, description, related_short=None):
    """Helper function to create reward transactions"""
    wallet, created = Wallet.objects.get_or_create(user=user)
    
    # Convert amount to Decimal to avoid type errors
    amount_decimal = Decimal(str(amount))
    
    # Create transaction
    transaction = Transaction.objects.create(
        wallet=wallet,
        transaction_type=transaction_type,
        amount=amount_decimal,
        description=description,
        related_short=related_short
    )
    
    # Update wallet balances
    wallet.balance += amount_decimal
    wallet.total_earnings += amount_decimal
    wallet.save()
    
    return transaction


class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]