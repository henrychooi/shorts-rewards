from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from django.db.models import F
from decimal import Decimal
from datetime import datetime
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .serializers import (
    UserSerializer, NoteSerializer, ShortSerializer, ShortCreateSerializer,
    LikeSerializer, CommentSerializer, UserProfileSerializer, WalletSerializer, 
    TransactionSerializer, AuditLogSerializer
)
from .models import Note, Short, Like, Comment, View, Wallet, Transaction, AuditLog
from .audio_service import AudioProcessingService
import logging

logger = logging.getLogger(__name__)

audio_service = AudioProcessingService()


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
@permission_classes([IsAuthenticated])  # Adjust permissions as needed
def process_all_videos_audio(request):
    """
    Process all MP4 videos in the media directory and analyze their audio quality
    """
    try:
        logger.info("Starting batch audio processing for all videos")
        results = audio_service.process_all_videos()
        
        # Calculate summary statistics
        total_videos = len(results)
        successful_processes = len([r for r in results if 'error' not in r])
        average_quality = sum([r['quality_analysis']['quality_score'] for r in results]) / total_videos if total_videos > 0 else 0
        
        response_data = {
            'success': True,
            'message': f'Processed {successful_processes}/{total_videos} videos successfully',
            'summary': {
                'total_videos': total_videos,
                'successful_processes': successful_processes,
                'average_quality_score': round(average_quality, 2)
            },
            'results': results
        }
        
        logger.info(f"Batch processing completed: {successful_processes}/{total_videos} successful")
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error in batch audio processing: {str(e)}")
        return Response({
            'success': False,
            'error': f'Batch processing failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_single_video_audio(request):
    """
    Process a single video file's audio quality
    Expected payload: {"video_filename": "example.mp4"}
    """
    try:
        video_filename = request.data.get('video_filename')
        
        if not video_filename:
            return Response({
                'success': False,
                'error': 'video_filename is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"Processing single video: {video_filename}")
        result = audio_service.process_single_video(video_filename)
        
        if 'error' in result:
            return Response({
                'success': False,
                'error': result['error'],
                'quality_analysis': result['quality_analysis']
            }, status=status.HTTP_404_NOT_FOUND if 'not found' in result['error'].lower() else status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        response_data = {
            'success': True,
            'message': f'Successfully processed {video_filename}',
            'result': result
        }
        
        logger.info(f"Single video processing completed: {video_filename} - Quality: {result['quality_analysis']['quality_score']:.1f}")
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error processing single video: {str(e)}")
        return Response({
            'success': False,
            'error': f'Processing failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_audio_quality_report(request):
    """
    Get a summary report of all processed audio files
    """
    try:
        # This could be enhanced to read from a database where you store results
        # For now, it processes all videos to get current status
        results = audio_service.process_all_videos()
        
        # Generate report
        report = {
            'total_videos': len(results),
            'quality_distribution': {
                'excellent': len([r for r in results if r['quality_analysis']['quality_score'] >= 80]),
                'good': len([r for r in results if 60 <= r['quality_analysis']['quality_score'] < 80]),
                'fair': len([r for r in results if 40 <= r['quality_analysis']['quality_score'] < 60]),
                'poor': len([r for r in results if r['quality_analysis']['quality_score'] < 40])
            },
            'average_quality_score': sum([r['quality_analysis']['quality_score'] for r in results]) / len(results) if results else 0,
            'processing_errors': len([r for r in results if 'error' in r]),
            'detailed_results': results
        }
        
        return Response({
            'success': True,
            'report': report
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error generating audio quality report: {str(e)}")
        return Response({
            'success': False,
            'error': f'Report generation failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def list_videos(request):
    """
    List all available MP4 videos in the media directory
    """
    try:
        videos = list(audio_service.media_videos_path.glob("*.mp4"))
        video_list = [
            {
                'filename': video.name,
                'path': str(video),
                'size_mb': round(video.stat().st_size / (1024 * 1024), 2),
                'modified': video.stat().st_mtime
            }
            for video in videos
        ]
        
        return Response({
            'success': True,
            'videos': video_list,
            'total_count': len(video_list)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error listing videos: {str(e)}")
        return Response({
            'success': False,
            'error': f'Failed to list videos: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Traditional Django view example (if not using DRF)
@csrf_exempt
@require_http_methods(["POST"])
def process_videos_traditional(request):
    """
    Traditional Django view for processing videos (without DRF)
    """
    try:
        if request.method == 'POST':
            data = json.loads(request.body)
            video_filename = data.get('video_filename')
            
            if video_filename:
                # Process single video
                result = audio_service.process_single_video(video_filename)
                return JsonResponse({
                    'success': 'error' not in result,
                    'result': result
                })
            else:
                # Process all videos
                results = audio_service.process_all_videos()
                return JsonResponse({
                    'success': True,
                    'results': results
                })
                
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


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


@api_view(['POST'])
@permission_classes([AllowAny])
def track_watch_progress(request, short_id):
    """Track detailed watch progress including position, duration, and rewatches"""
    try:
        short = get_object_or_404(Short, id=short_id, is_active=True)
        
        # Get data from request
        current_position = float(request.data.get('current_position', 0))
        duration_watched = float(request.data.get('duration_watched', 0))
        session_id = request.data.get('session_id', '')
        is_rewatch = request.data.get('is_rewatch', False)
        
        # Get user's IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        
        # Get or create view record - but check for existing views across all sessions
        # First, check if user has watched this video before (in any session)
        existing_views = View.objects.filter(
            user=request.user if request.user.is_authenticated else None,
            short=short
        ).exclude(session_id=session_id) if request.user.is_authenticated else []
        
        # Get or create view record for current session
        view_record, created = View.objects.get_or_create(
            user=request.user if request.user.is_authenticated else None,
            short=short,
            session_id=session_id,
            defaults={
                'ip_address': ip_address,
                'watch_duration': duration_watched,
                'max_watch_position': current_position,
                'last_position': current_position,
            }
        )
        
        # If this is a new session but user has watched this video before, it's a rewatch
        if created and existing_views.exists():
            view_record.rewatch_count = existing_views.count()  # Count previous sessions as rewatches
        
        # Update watch progress
        if not created:
            view_record.update_watch_progress(current_position, duration_watched)
            
            # Handle in-session rewatch (seeking backwards)
            if is_rewatch:
                view_record.mark_rewatch()
        else:
            view_record.update_watch_progress(current_position, duration_watched)
        
        view_record.save()
        
        # Calculate response data
        response_data = {
            'status': 'success',
            'watch_percentage': round(view_record.watch_percentage, 2),
            'is_complete_view': view_record.is_complete_view,
            'rewatch_count': view_record.rewatch_count,
            'engagement_score': round(view_record.engagement_score, 2),
            'max_watch_position': view_record.max_watch_position,
        }
        
        return Response(response_data)
        
    except Exception as e:
        print(f"ERROR in track_watch_progress: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Failed to track watch progress: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_video_analytics(request, short_id):
    """Get comprehensive analytics for a video"""
    try:
        short = get_object_or_404(Short, id=short_id, is_active=True)
        analytics = short.get_analytics_summary()
        
        return Response({
            'status': 'success',
            'analytics': analytics
        })
        
    except Exception as e:
        print(f"ERROR in get_video_analytics: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Failed to get analytics: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_watch_history(request):
    """Get user's watch history with engagement metrics"""
    try:
        views = View.objects.filter(user=request.user).select_related('short').order_by('-updated_at')
        
        watch_history = []
        for view in views:
            watch_history.append({
                'short_id': str(view.short.id),
                'short_title': view.short.title or 'Untitled',
                'watch_percentage': round(view.watch_percentage, 2),
                'watch_duration': view.watch_duration,
                'video_duration': view.short.duration,
                'is_complete_view': view.is_complete_view,
                'rewatch_count': view.rewatch_count,
                'engagement_score': round(view.engagement_score, 2),
                'last_watched': view.updated_at.isoformat(),
                'first_watched': view.created_at.isoformat(),
            })
        
        return Response({
            'status': 'success',
            'watch_history': watch_history
        })
        
    except Exception as e:
        print(f"ERROR in get_user_watch_history: {str(e)}")
        return Response({
            'status': 'error',
            'message': f'Failed to get watch history: {str(e)}'
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
    """Get transaction history for the authenticated user with blockchain verification"""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    transactions = Transaction.objects.filter(wallet=wallet)[:50]  # Latest 50 transactions
    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_transaction(request, transaction_id):
    """Verify a specific transaction's integrity using cryptographic hash"""
    try:
        transaction = get_object_or_404(Transaction, id=transaction_id, wallet__user=request.user)
        
        verification_result = {
            'transaction_id': str(transaction.id),
            'transaction_hash': transaction.transaction_hash,
            'integrity_verified': transaction.verify_integrity(),
            'chain_valid': transaction.get_chain_validity(),
            'is_confirmed': transaction.is_confirmed,
            'confirmation_count': transaction.confirmation_count,
            'created_at': transaction.created_at,
            'merkle_root': transaction.merkle_root
        }
        
        return Response(verification_result)
    except Exception as e:
        return Response({
            'error': 'Transaction verification failed',
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_log(request):
    """Get audit log for transparency (blockchain-inspired immutable log)"""
    logs = AuditLog.objects.filter(user=request.user)[:100]  # Latest 100 logs
    serializer = AuditLogSerializer(logs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_integrity_report(request):
    """Generate a comprehensive integrity report for the user's wallet"""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    transactions = Transaction.objects.filter(wallet=wallet)
    
    total_transactions = transactions.count()
    verified_transactions = sum(1 for tx in transactions if tx.verify_integrity())
    chain_valid_transactions = sum(1 for tx in transactions if tx.get_chain_validity())
    confirmed_transactions = transactions.filter(is_confirmed=True).count()
    
    integrity_report = {
        'wallet_id': wallet.id,
        'user': request.user.username,
        'total_transactions': total_transactions,
        'verified_transactions': verified_transactions,
        'chain_valid_transactions': chain_valid_transactions,
        'confirmed_transactions': confirmed_transactions,
        'integrity_percentage': (verified_transactions / total_transactions * 100) if total_transactions > 0 else 100,
        'chain_validity_percentage': (chain_valid_transactions / total_transactions * 100) if total_transactions > 0 else 100,
        'current_balance': wallet.balance,
        'total_earnings': wallet.total_earnings,
        'generated_at': datetime.now().isoformat()
    }
    
    return Response(integrity_report)


def create_reward_transaction(user, transaction_type, amount, description, related_short=None):
    """
    Blockchain-inspired secure transaction creation with cryptographic hashing,
    immutable logging, and transparency while using fiat currency
    """
    wallet, created = Wallet.objects.get_or_create(user=user)
    
    # Convert amount to Decimal to avoid type errors
    amount_decimal = Decimal(str(amount))
    
    # Ensure wallet balances are Decimal types
    if not isinstance(wallet.balance, Decimal):
        wallet.balance = Decimal(str(wallet.balance))
    if not isinstance(wallet.total_earnings, Decimal):
        wallet.total_earnings = Decimal(str(wallet.total_earnings))
    
    # Create transaction with blockchain-inspired security
    transaction = Transaction.objects.create(
        wallet=wallet,
        transaction_type=transaction_type,
        amount=amount_decimal,
        description=description,
        related_short=related_short,
        nonce=0  # Could implement proof-of-work concept if needed
    )
    
    # Update wallet balances with proper Decimal arithmetic
    wallet.balance = wallet.balance + amount_decimal
    wallet.total_earnings = wallet.total_earnings + amount_decimal
    wallet.save()
    
    # Create immutable audit log entry
    AuditLog.objects.create(
        action_type='transaction_created',
        user=user,
        description=f"Reward transaction created: {transaction_type}",
        metadata={
            'transaction_id': str(transaction.id),
            'transaction_hash': transaction.transaction_hash,
            'amount': str(amount_decimal),
            'wallet_id': wallet.id,
            'related_short_id': str(related_short.id) if related_short else None
        }
    )
    
    # Confirm transaction (in blockchain, this would be mining/consensus)
    transaction.is_confirmed = True
    transaction.confirmation_count = 1  # Simulate network confirmations
    transaction.save(update_fields=['is_confirmed', 'confirmation_count'])
    
    return transaction


class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]