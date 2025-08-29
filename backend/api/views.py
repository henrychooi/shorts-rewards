from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from django.db.models import F
from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from pathlib import Path
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import JsonResponse
import json
import threading
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .serializers import (
    UserSerializer, NoteSerializer, ShortSerializer, ShortCreateSerializer,
    LikeSerializer, CommentSerializer, UserProfileSerializer, WalletSerializer,
    TransactionSerializer, AuditLogSerializer
)
from .comment_analysis_service import CommentAnalysisService
from .models import Note, Short, Like, Comment, View, Wallet, Transaction, AuditLog
from .audio_service import AudioProcessingService
from .gemini_video_service import gemini_video_service
import logging
import os
import time

logger = logging.getLogger(__name__)

# Initialize audio service at module level for performance
try:
    audio_service = AudioProcessingService()
except Exception as e:
    logger.warning(f"Failed to initialize AudioProcessingService: {e}")
    audio_service = None


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
        short = serializer.save(author=self.request.user)
        
        # Process audio for transcript and quality score
        self.process_video_audio(short)
        
        # Process video for comprehensive analysis using Gemini (run in background)
        self.process_video_analysis_async(short)
    
    def process_video_analysis_async(self, short):
        """Start video analysis in a background thread to avoid blocking the response"""
        def analyze_in_background():
            try:
                self.process_video_analysis(short)
            except Exception as e:
                logger.error(f"Background video analysis failed for {short.id}: {e}")
        
        # Start analysis in background thread
        analysis_thread = threading.Thread(target=analyze_in_background)
        analysis_thread.daemon = True
        analysis_thread.start()
        logger.info(f"Started background video analysis for {short.id}")
    
    def process_video_audio(self, short):
        """Process the uploaded video to generate transcript and quality score"""
        try:
            if not audio_service:
                logger.warning(f"Audio service not available for video {short.id}")
                return
            
            # Get the video file path
            video_path = short.video.path
            
            # Process the single video using the correct method name
            video_filename = Path(video_path).name
            result = audio_service.process_single_video(video_filename)
            
            if result and 'error' not in result:
                # Update the short with transcript and quality data
                transcript_data = result.get('transcript', {})
                quality_data = result.get('quality_analysis', {})
                
                short.transcript = transcript_data.get('text', '')
                short.audio_quality_score = quality_data.get('quality_score', 0.0)
                short.transcript_language = transcript_data.get('language', '')
                short.audio_processed_at = timezone.now()
                short.save(update_fields=['transcript', 'audio_quality_score', 'transcript_language', 'audio_processed_at'])
                
                logger.info(f"Successfully processed audio for video {short.id}: quality_score={short.audio_quality_score}")
            else:
                logger.error(f"Failed to process audio for video {short.id}: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            logger.error(f"Exception while processing audio for video {short.id}: {str(e)}")
    
    def process_video_analysis(self, short):
        """Process the uploaded video using Gemini AI for comprehensive analysis"""
        try:
            if not gemini_video_service.is_available():
                logger.warning(f"Gemini video analysis service not available for video {short.id}")
                short.video_analysis_status = 'failed'
                short.video_analysis_error = 'Gemini service not available'
                short.save(update_fields=['video_analysis_status', 'video_analysis_error'])
                return
            
            # Set status to processing
            short.video_analysis_status = 'processing'
            short.save(update_fields=['video_analysis_status'])
            
            # Get the video file path
            video_path = short.video.path
            logger.info(f"Starting Gemini video analysis for {short.id}: {video_path}")
            
            # Analyze the video using Gemini
            analysis_result = gemini_video_service.analyze_video(video_path)
            
            if analysis_result.get('success', False):
                # Update the short with enhanced analysis data
                short.video_analysis_summary = analysis_result.get('summary', '')
                short.video_analysis_status = 'completed'
                short.video_analysis_processed_at = timezone.now()
                short.video_analysis_error = None
                
                # Enhanced analysis fields - updated for balanced scoring
                short.video_content_engagement = analysis_result.get('content_engagement', 50)
                short.video_demographic_appeal = analysis_result.get('audience_appeal', 50)  # audience_appeal maps to demographic_appeal
                short.video_content_focus = analysis_result.get('quality_score', 50)  # quality includes focus/clarity
                short.video_content_sensitivity = analysis_result.get('content_sensitivity', 5)
                short.video_originality = analysis_result.get('originality', 50)
                short.video_technical_quality = analysis_result.get('quality_score', 50)  # quality_score includes technical
                short.video_viral_potential = analysis_result.get('viral_potential', 50)
                short.video_overall_score = analysis_result.get('overall_score', 50)
                
                # Store detailed summary if available
                detailed_summary = analysis_result.get('detailed_summary', '')
                if detailed_summary:
                    short.video_analysis_summary = detailed_summary
                
                # Legacy support - remove unused fields in new system
                short.video_detailed_breakdown = {}  # Simplified system doesn't use this
                short.video_demographic_analysis = {}  # Simplified system doesn't use this
                
                # Maintain legacy fields for backward compatibility
                short.video_quality_score = analysis_result.get('quality_score', 50)  # Use new quality_score
                short.video_engagement_prediction = analysis_result.get('content_engagement', 50)
                short.video_sentiment_score = analysis_result.get('sentiment_score', 0)  # Not part of new system
                short.video_content_categories = analysis_result.get('content_categories', [])
                
                short.save(update_fields=[
                    'video_analysis_summary', 'video_analysis_status', 'video_analysis_processed_at', 'video_analysis_error',
                    'video_content_engagement', 'video_demographic_appeal', 'video_content_focus', 'video_content_sensitivity',
                    'video_originality', 'video_technical_quality', 'video_viral_potential', 'video_overall_score',
                    'video_detailed_breakdown', 'video_demographic_analysis',
                    'video_quality_score', 'video_engagement_prediction', 'video_sentiment_score', 'video_content_categories'
                ])
                
                logger.info(f"Successfully analyzed video {short.id}: overall={short.video_overall_score:.1f}, engagement={short.video_content_engagement}, demographics={short.video_demographic_appeal}, originality={short.video_originality}")
            else:
                # Analysis failed
                error_msg = analysis_result.get('error', 'Unknown analysis error')
                short.video_analysis_status = 'failed'
                short.video_analysis_error = error_msg
                short.save(update_fields=['video_analysis_status', 'video_analysis_error'])
                logger.error(f"Failed to analyze video {short.id}: {error_msg}")
        
        except Exception as e:
            logger.error(f"Exception while analyzing video {short.id}: {str(e)}")
            short.video_analysis_status = 'failed'
            short.video_analysis_error = str(e)
            short.save(update_fields=['video_analysis_status', 'video_analysis_error'])


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
        
        if not audio_service:
            return Response(
                {'error': 'Audio processing service not available'}, 
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
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
        
        if not audio_service:
            return Response({
                'success': False,
                'error': 'Audio processing service not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
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
        
        if not audio_service:
            return Response(
                {'error': 'Audio processing service not available'}, 
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
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
        if not audio_service:
            return Response(
                {'error': 'Audio processing service not available'}, 
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
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
        
        # Automatically analyze the new comment for sentiment in background
        def analyze_comment_background():
            try:
                from .comment_analysis_service import CommentAnalysisService
                analysis_service = CommentAnalysisService()
                
                # Analyze the individual comment and update short's aggregate score
                result = analysis_service.analyze_single_comment(comment)
                
                if result.get('error'):
                    logger.error(f"Comment analysis failed for comment {comment.id}: {result['error']}")
                else:
                    logger.info(f"Successfully analyzed comment {comment.id} - Score: {result.get('sentiment_score')}")
                
            except Exception as e:
                logger.error(f"Error in automatic comment analysis for short {short_id}: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        # Start comment analysis in background thread
        analysis_thread = threading.Thread(target=analyze_comment_background)
        analysis_thread.daemon = True
        analysis_thread.start()
        
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


# Comment Analysis API Views
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_comment(request, comment_id):
    """
    Analyze sentiment for a single comment.

    API endpoint for comment sentiment analysis that can be called from admin interface
    or external API clients.

    Expected payload (optional): {"force": true} to re-analyze already analyzed comments
    """
    try:
        comment = get_object_or_404(Comment, id=comment_id, is_active=True)
        force = request.data.get('force', False)

        service = CommentAnalysisService()
        result = service.reanalyze_comment(comment, force=force)

        if result.get('error'):
            return Response({
                'success': False,
                'error': result['error']
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': True,
            'comment_id': str(comment.id),
            'sentiment_score': round(result['sentiment_score'], 2),
            'sentiment_label': result['sentiment_label'],
            'analyzed_at': comment.analyzed_at.isoformat() if comment.analyzed_at else None
        })

    except Comment.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Comment not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error analyzing comment {comment_id}: {str(e)}")
        return Response({
            'success': False,
            'error': f'Analysis failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_comments_for_short(request, short_id):
    """
    Analyze all unanalyzed comments for a given short.

    API endpoint for batch comment sentiment analysis.

    Expected payload (optional):
    - {"force": true} to re-analyze already analyzed comments
    - {"update_aggregate": true} to update the Short's aggregate score
    """
    try:
        short = get_object_or_404(Short, id=short_id, is_active=True)
        force = request.data.get('force', False)
        update_aggregate = request.data.get('update_aggregate', True)

        service = CommentAnalysisService()
        result = service.analyze_comments_for_short(short, update_aggregate=update_aggregate)

        response_data = {
            'success': True,
            'short_id': str(short.id),
            'comments_analyzed': result.get('comments_analyzed', 0),
            'errors': result.get('errors', 0),
            'aggregate_score': round(result.get('aggregate_score'), 2) if result.get('aggregate_score') else None,
            'results': result.get('results', [])
        }

        if result.get('errors', 0) > 0:
            response_data['warning'] = f"{result['errors']} comments failed to analyze"

        return Response(response_data)

    except Short.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Short not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error analyzing comments for short {short_id}: {str(e)}")
        return Response({
            'success': False,
            'error': f'Analysis failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_analyze_comments(request):
    """
    Batch analyze comments across multiple shorts.

    API endpoint for large-scale comment sentiment analysis.

    Expected payload:
    - short_ids: List of short IDs to process
    - force: (optional) Re-analyze already processed comments
    - update_aggregates: (optional) Update Short aggregate scores
    """
    try:
        short_ids = request.data.get('short_ids', [])
        force = request.data.get('force', False)
        update_aggregates = request.data.get('update_aggregates', True)

        if not short_ids:
            return Response({
                'success': False,
                'error': 'short_ids is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        service = CommentAnalysisService()
        total_shorts = 0
        total_comments = 0
        total_errors = 0
        results = []

        for short_id in short_ids:
            try:
                short = Short.objects.get(id=short_id, is_active=True)
                result = service.analyze_comments_for_short(short, update_aggregate=update_aggregates)

                total_shorts += 1
                total_comments += result.get('comments_analyzed', 0)
                total_errors += result.get('errors', 0)

                results.append({
                    'short_id': str(short_id),
                    'short_title': short.title or 'Untitled',
                    'comments_analyzed': result.get('comments_analyzed', 0),
                    'errors': result.get('errors', 0),
                    'aggregate_score': result.get('aggregate_score')
                })

            except Short.DoesNotExist:
                results.append({
                    'short_id': str(short_id),
                    'error': 'Short not found'
                })
            except Exception as e:
                logger.error(f"Error processing short {short_id}: {str(e)}")
                results.append({
                    'short_id': str(short_id),
                    'error': str(e)
                })

        response_data = {
            'success': True,
            'summary': {
                'total_shorts_processed': total_shorts,
                'total_comments_analyzed': total_comments,
                'total_errors': total_errors,
                'success_rate': (total_comments / (total_comments + total_errors) * 100) if (total_comments + total_errors) > 0 else 0
            },
            'results': results
        }

        if total_errors > 0:
            response_data['warning'] = f"{total_errors} comments failed to analyze"

        return Response(response_data)

    except Exception as e:
        logger.error(f"Error in batch analysis: {str(e)}")
        return Response({
            'success': False,
            'error': f'Batch analysis failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_comment_sentiment_summary(request, short_id):
    """
    Get sentiment summary for all comments on a short.

    Returns statistics about comment sentiment distribution and averages.
    """
    try:
        short = get_object_or_404(Short, id=short_id, is_active=True)

        service = CommentAnalysisService()
        summary = service.get_short_sentiment_summary(short)

        return Response({
            'success': True,
            'short_id': str(short_id),
            'summary': summary
        })

    except Short.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Short not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error getting sentiment summary for short {short_id}: {str(e)}")
        return Response({
            'success': False,
            'error': f'Failed to get summary: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_text_sentiment(request):
    """
    Analyze sentiment of arbitrary text.

    API endpoint for testing sentiment analysis on any text without saving to database.
    Useful for testing the model or analyzing text from external sources.

    Expected payload: {"text": "Text to analyze"}
    """
    try:
        text = request.data.get('text', '').strip()

        if not text:
            return Response({
                'success': False,
                'error': 'Text is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        service = CommentAnalysisService()
        result = service.analyze_comment(text)

        if result.get('error'):
            return Response({
                'success': False,
                'error': result['error']
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'success': True,
            'sentiment_score': round(result['sentiment_score'], 2),
            'sentiment_label': result['sentiment_label'],
            'raw_scores': result.get('raw_scores', {})
        })

    except Exception as e:
        logger.error(f"Error analyzing text sentiment: {str(e)}")
        return Response({
            'success': False,
            'error': f'Analysis failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_single_video(request):
    """
    Manually trigger Gemini analysis for a single video
    Expected payload: {"short_id": "uuid"}
    """
    try:
        short_id = request.data.get('short_id')
        if not short_id:
            return Response({'error': 'short_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        short = get_object_or_404(Short, id=short_id, author=request.user, is_active=True)
        
        if not gemini_video_service.is_available():
            return Response(
                {'error': 'Gemini video analysis service is not available'}, 
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Check if analysis is already in progress
        if short.video_analysis_status == 'processing':
            return Response(
                {'message': 'Video analysis is already in progress'}, 
                status=status.HTTP_409_CONFLICT
            )
        
        # Set status to processing
        short.video_analysis_status = 'processing'
        short.save(update_fields=['video_analysis_status'])
        
        try:
            # Analyze the video
            video_path = short.video.path
            analysis_result = gemini_video_service.analyze_video(video_path)
            
            if analysis_result.get('success', False):
                # Update the short with enhanced analysis data
                short.video_analysis_summary = analysis_result.get('summary', '')
                short.video_analysis_status = 'completed'
                short.video_analysis_processed_at = timezone.now()
                short.video_analysis_error = None
                
                # Enhanced analysis fields - updated for balanced scoring
                short.video_content_engagement = analysis_result.get('content_engagement', 50)
                short.video_demographic_appeal = analysis_result.get('audience_appeal', 50)  # audience_appeal maps to demographic_appeal
                short.video_content_focus = analysis_result.get('quality_score', 50)  # quality includes focus/clarity
                short.video_content_sensitivity = analysis_result.get('content_sensitivity', 5)
                short.video_originality = analysis_result.get('originality', 50)
                short.video_technical_quality = analysis_result.get('quality_score', 50)  # quality_score includes technical
                short.video_viral_potential = analysis_result.get('viral_potential', 50)
                short.video_overall_score = analysis_result.get('overall_score', 50)
                
                # Store detailed summary if available
                detailed_summary = analysis_result.get('detailed_summary', '')
                if detailed_summary:
                    short.video_analysis_summary = detailed_summary
                
                # Legacy support - remove unused fields in new system
                short.video_detailed_breakdown = {}  # Simplified system doesn't use this
                short.video_demographic_analysis = {}  # Simplified system doesn't use this
                
                # Maintain legacy fields for backward compatibility
                short.video_quality_score = analysis_result.get('quality_score', 50)  # Use new quality_score
                short.video_engagement_prediction = analysis_result.get('content_engagement', 50)
                short.video_sentiment_score = analysis_result.get('sentiment_score', 0)  # Not part of new system
                short.video_content_categories = analysis_result.get('content_categories', [])
                
                short.save(update_fields=[
                    'video_analysis_summary', 'video_analysis_status', 'video_analysis_processed_at', 'video_analysis_error',
                    'video_content_engagement', 'video_demographic_appeal', 'video_content_focus', 'video_content_sensitivity',
                    'video_originality', 'video_technical_quality', 'video_viral_potential', 'video_overall_score',
                    'video_detailed_breakdown', 'video_demographic_analysis',
                    'video_quality_score', 'video_engagement_prediction', 'video_sentiment_score', 'video_content_categories'
                ])
                
                return Response({
                    'success': True,
                    'message': 'Enhanced video analysis completed successfully',
                    'analysis': {
                        'overall_score': short.video_overall_score,
                        'content_engagement': short.video_content_engagement,
                        'demographic_appeal': short.video_demographic_appeal,
                        'originality': short.video_originality,
                        'content_sensitivity': short.video_content_sensitivity,
                        'technical_quality': short.video_technical_quality,
                        'viral_potential': short.video_viral_potential,
                        'detailed_breakdown': short.video_detailed_breakdown,
                        # Legacy fields for compatibility
                        'quality_score': short.video_quality_score,
                        'engagement_prediction': short.video_engagement_prediction,
                        'sentiment_score': short.video_sentiment_score,
                        'content_categories': short.video_content_categories,
                        'summary': short.video_analysis_summary,
                    }
                }, status=status.HTTP_200_OK)
            else:
                # Analysis failed
                error_msg = analysis_result.get('error', 'Unknown analysis error')
                short.video_analysis_status = 'failed'
                short.video_analysis_error = error_msg
                short.save(update_fields=['video_analysis_status', 'video_analysis_error'])
                
                return Response({
                    'success': False,
                    'error': error_msg
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        except Exception as e:
            # Update status to failed
            short.video_analysis_status = 'failed'
            short.video_analysis_error = str(e)
            short.save(update_fields=['video_analysis_status', 'video_analysis_error'])
            
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        logger.error(f"Error in analyze_single_video: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_video_analysis(request, short_id):
    """
    Get analysis results for a specific video
    """
    try:
        short = get_object_or_404(Short, id=short_id, is_active=True)
        
        # Check if user can access this video (author or public)
        if short.author != request.user:
            # For now, allow anyone to see analysis of public videos
            # You can modify this based on your privacy requirements
            pass
        
        if (short.video_analysis_status == 'completed' and 
            short.video_quality_score is not None and 
            short.video_analysis_summary):
            
            return Response({
                'success': True,
                'analysis': {
                    'status': short.video_analysis_status,
                    'quality_score': short.video_quality_score,
                    'engagement_prediction': short.video_engagement_prediction,
                    'sentiment_score': short.video_sentiment_score,
                    'content_categories': short.video_content_categories,
                    'summary': short.video_analysis_summary,
                    'processed_at': short.video_analysis_processed_at,
                }
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'status': short.video_analysis_status,
                'error': short.video_analysis_error,
                'message': 'Video analysis not completed yet'
            }, status=status.HTTP_202_ACCEPTED)
    
    except Exception as e:
        logger.error(f"Error getting video analysis: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_analyze_videos(request):
    """
    Trigger analysis for all user's videos that haven't been analyzed yet
    """
    try:
        if not gemini_video_service.is_available():
            return Response(
                {'error': 'Gemini video analysis service is not available'}, 
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Get all user's videos that need analysis
        videos_to_analyze = Short.objects.filter(
            author=request.user,
            is_active=True,
            video_analysis_status__in=['pending', 'failed']
        )[:10]  # Limit to 10 videos at once to avoid overwhelming the API
        
        if not videos_to_analyze.exists():
            return Response({
                'message': 'No videos need analysis',
                'analyzed_count': 0
            }, status=status.HTTP_200_OK)
        
        results = []
        successful_count = 0
        
        for short in videos_to_analyze:
            try:
                # Set status to processing
                short.video_analysis_status = 'processing'
                short.save(update_fields=['video_analysis_status'])
                
                # Analyze the video
                video_path = short.video.path
                analysis_result = gemini_video_service.analyze_video(video_path)
                
                if analysis_result.get('success', False):
                    # Update the short with analysis data
                    short.video_quality_score = analysis_result.get('quality_score', 0)
                    short.video_analysis_summary = analysis_result.get('summary', '')
                    short.video_content_categories = analysis_result.get('content_categories', [])
                    short.video_engagement_prediction = analysis_result.get('engagement_prediction', 0)
                    short.video_sentiment_score = analysis_result.get('sentiment_score', 0)
                    short.video_analysis_status = 'completed'
                    short.video_analysis_processed_at = timezone.now()
                    short.video_analysis_error = None
                    
                    short.save(update_fields=[
                        'video_quality_score', 'video_analysis_summary', 'video_content_categories',
                        'video_engagement_prediction', 'video_sentiment_score', 'video_analysis_status',
                        'video_analysis_processed_at', 'video_analysis_error'
                    ])
                    
                    successful_count += 1
                    results.append({
                        'short_id': str(short.id),
                        'title': short.title,
                        'success': True,
                        'quality_score': short.video_quality_score,
                    })
                else:
                    # Analysis failed
                    error_msg = analysis_result.get('error', 'Unknown analysis error')
                    short.video_analysis_status = 'failed'
                    short.video_analysis_error = error_msg
                    short.save(update_fields=['video_analysis_status', 'video_analysis_error'])
                    
                    results.append({
                        'short_id': str(short.id),
                        'title': short.title,
                        'success': False,
                        'error': error_msg
                    })
                
                # Add delay between requests to respect rate limits
                import time
                time.sleep(1)
                
            except Exception as e:
                short.video_analysis_status = 'failed'
                short.video_analysis_error = str(e)
                short.save(update_fields=['video_analysis_status', 'video_analysis_error'])
                
                results.append({
                    'short_id': str(short.id),
                    'title': short.title,
                    'success': False,
                    'error': str(e)
                })
        
        return Response({
            'success': True,
            'message': f'Batch analysis completed: {successful_count}/{len(results)} successful',
            'analyzed_count': successful_count,
            'total_processed': len(results),
            'results': results
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error in batch_analyze_videos: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def video_analysis_report(request):
    """
    Get a comprehensive report of all analyzed videos for the user
    """
    try:
        # Get all user's analyzed videos
        analyzed_videos = Short.objects.filter(
            author=request.user,
            is_active=True,
            video_analysis_status='completed',
            video_quality_score__isnull=False,
        )
        
        if not analyzed_videos.exists():
            return Response({
                'message': 'No analyzed videos found',
                'total_videos': 0
            }, status=status.HTTP_200_OK)
        
        # Calculate summary statistics
        total_videos = analyzed_videos.count()
        avg_quality = sum(v.video_quality_score for v in analyzed_videos) / total_videos
        avg_engagement = sum(v.video_engagement_prediction or 0 for v in analyzed_videos) / total_videos
        avg_sentiment = sum(v.video_sentiment_score or 0 for v in analyzed_videos) / total_videos
        
        # Quality distribution
        quality_distribution = {
            'excellent': analyzed_videos.filter(video_quality_score__gte=80).count(),
            'good': analyzed_videos.filter(video_quality_score__gte=60, video_quality_score__lt=80).count(),
            'fair': analyzed_videos.filter(video_quality_score__gte=40, video_quality_score__lt=60).count(),
            'poor': analyzed_videos.filter(video_quality_score__lt=40).count()
        }
        
        # Collect all categories
        all_categories = []
        for video in analyzed_videos:
            if video.video_content_categories:
                all_categories.extend(video.video_content_categories)
        
        # Count category frequency
        category_counts = {}
        for category in all_categories:
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Top categories
        top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return Response({
            'success': True,
            'summary': {
                'total_analyzed_videos': total_videos,
                'average_quality_score': round(avg_quality, 2),
                'average_engagement_prediction': round(avg_engagement, 2),
                'average_sentiment_score': round(avg_sentiment, 3),
                'quality_distribution': quality_distribution,
                'top_content_categories': top_categories
            },
            'videos': [{
                'id': str(video.id),
                'title': video.title,
                'quality_score': video.video_quality_score,
                'engagement_prediction': video.video_engagement_prediction,
                'sentiment_score': video.video_sentiment_score,
                'content_categories': video.video_content_categories,
                'summary': video.video_analysis_summary[:200] + '...' if len(video.video_analysis_summary or '') > 200 else video.video_analysis_summary,
                'processed_at': video.video_analysis_processed_at
            } for video in analyzed_videos.order_by('-video_analysis_processed_at')]
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error generating video analysis report: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    """
    Analyze a single video by Short ID
    """
    try:
        short_id = request.data.get('short_id')
        force_reanalysis = request.data.get('force_reanalysis', False)
        
        if not short_id:
            return Response(
                {"error": "short_id is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the short
        try:
            short = Short.objects.get(id=short_id)
        except Short.DoesNotExist:
            return Response(
                {"error": "Short not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user owns the video or is admin
        if short.author != request.user and not request.user.is_staff:
            return Response(
                {"error": "Permission denied"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if video file exists
        if not short.video_exists():
            return Response(
                {"error": "Video file not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if already analyzed (unless force reanalysis)
        if (short.video_analysis_status == 'completed' and 
            short.video_quality_score is not None and 
            not force_reanalysis):
            return Response({
                "message": "Video already analyzed",
                "analysis": {
                    "video_quality_score": short.video_quality_score,
                    "engagement_score": short.engagement_score,
                    "technical_score": short.technical_score,
                    "grade": short.get_quality_grade(),
                    "summary": short.video_analysis_summary,
                    "processed_at": short.video_processed_at
                }
            })
        
        # Initialize analysis service
        video_service = VideoAnalysisService()
        
        # Create analysis log
        analysis_log = VideoAnalysisLog.objects.create(
            short=short,
            analysis_type='reanalysis' if force_reanalysis else 'manual',
            file_size_mb=os.path.getsize(short.video.path) / (1024 * 1024)
        )
        
        # Update status to processing
        short.video_analysis_status = 'processing'
        short.save(update_fields=['video_analysis_status'])
        
        try:
            # Process the video
            analysis_result = video_service.process_single_video(short.video.path)
            
            if 'error' in analysis_result:
                # Log failure
                analysis_log.mark_completed(
                    success=False,
                    error_message=analysis_result['error'],
                    result=analysis_result
                )
                
                # Update short with error
                short.update_video_analysis(analysis_result)
                
                return Response(
                    {"error": analysis_result['error']},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Success - update the Short model
            short.update_video_analysis(analysis_result)
            
            # Log success
            analysis_log.mark_completed(
                success=True,
                result=analysis_result
            )
            
            return Response({
                "success": True,
                "message": "Video analysis completed successfully",
                "analysis": {
                    "video_quality_score": short.video_quality_score,
                    "content_quality_score": short.content_quality_score,
                    "engagement_score": short.engagement_score,
                    "technical_score": short.technical_score,
                    "viral_potential": short.viral_potential,
                    "mobile_optimization": short.mobile_optimization,
                    "comprehensive_score": short.get_comprehensive_quality_score(),
                    "grade": short.get_quality_grade(),
                    "summary": short.video_analysis_summary,
                    "category": short.content_category,
                    "strengths": short.analysis_strengths,
                    "weaknesses": short.analysis_weaknesses,
                    "recommendations": short.analysis_recommendations,
                    "technical_metrics": short.technical_metrics,
                    "processed_at": short.video_processed_at
                }
            })
            
        except Exception as e:
            error_msg = f"Analysis failed: {str(e)}"
            
            # Log failure
            analysis_log.mark_completed(
                success=False,
                error_message=error_msg
            )
            
            # Update short status
            short.video_analysis_status = 'failed'
            short.video_analysis_error = error_msg
            short.save(update_fields=['video_analysis_status', 'video_analysis_error'])
            
            return Response(
                {"error": error_msg},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    except Exception as e:
        return Response(
            {"error": f"Unexpected error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def batch_analyze_videos(request):
    """
    Admin endpoint to analyze multiple videos in batch
    """
    try:
        reanalyze = request.data.get('reanalyze', False)
        limit = request.data.get('limit', 10)  # Process max 10 at a time to avoid timeouts
        
        # Get videos that need analysis
        if reanalyze:
            shorts_to_process = Short.objects.filter(
                is_active=True
            )[:limit]
        else:
            shorts_to_process = Short.objects.filter(
                is_active=True,
                video_analysis_status__in=['pending', 'failed']
            )[:limit]
        
        if not shorts_to_process.exists():
            return Response({
                "message": "No videos found that need analysis",
                "processed_count": 0
            })
        
        # Initialize analysis service
        video_service = VideoAnalysisService()
        
        results = []
        successful_count = 0
        
        for short in shorts_to_process:
            if not short.video_exists():
                results.append({
                    "short_id": str(short.id),
                    "title": short.title,
                    "status": "error",
                    "error": "Video file not found"
                })
                continue
            
            # Create analysis log
            analysis_log = VideoAnalysisLog.objects.create(
                short=short,
                analysis_type='reanalysis' if reanalyze else 'batch',
                file_size_mb=os.path.getsize(short.video.path) / (1024 * 1024)
            )
            
            try:
                # Update status
                short.video_analysis_status = 'processing'
                short.save(update_fields=['video_analysis_status'])
                
                # Process video
                analysis_result = video_service.process_single_video(short.video.path)
                
                if 'error' in analysis_result:
                    analysis_log.mark_completed(
                        success=False,
                        error_message=analysis_result['error'],
                        result=analysis_result
                    )
                    
                    short.update_video_analysis(analysis_result)
                    
                    results.append({
                        "short_id": str(short.id),
                        "title": short.title,
                        "status": "error",
                        "error": analysis_result['error']
                    })
                else:
                    # Success
                    short.update_video_analysis(analysis_result)
                    analysis_log.mark_completed(success=True, result=analysis_result)
                    
                    successful_count += 1
                    results.append({
                        "short_id": str(short.id),
                        "title": short.title,
                        "status": "success",
                        "quality_score": short.video_quality_score,
                        "engagement_score": short.engagement_score,
                        "grade": short.get_quality_grade()
                    })
                
                # Small delay between videos
                time.sleep(1)
                
            except Exception as e:
                error_msg = f"Processing failed: {str(e)}"
                
                analysis_log.mark_completed(
                    success=False,
                    error_message=error_msg
                )
                
                short.video_analysis_status = 'failed'
                short.video_analysis_error = error_msg
                short.save(update_fields=['video_analysis_status', 'video_analysis_error'])
                
                results.append({
                    "short_id": str(short.id),
                    "title": short.title,
                    "status": "error",
                    "error": error_msg
                })
        
        return Response({
            "success": True,
            "message": f"Batch analysis completed. {successful_count}/{len(results)} videos processed successfully.",
            "processed_count": len(results),
            "successful_count": successful_count,
            "results": results
        })
        
    except Exception as e:
        return Response(
            {"error": f"Batch analysis failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def video_analysis_report(request):
    """
    Generate comprehensive video analysis report
    """
    try:
        # Get filter parameters
        min_quality = request.GET.get('min_quality', 0)
        max_quality = request.GET.get('max_quality', 100)
        category = request.GET.get('category', None)
        
        # Base queryset
        queryset = Short.objects.filter(
            video_analysis_status='completed',
            video_quality_score__isnull=False,
            video_quality_score__gte=min_quality,
            video_quality_score__lte=max_quality
        )
        
        if category:
            queryset = queryset.filter(content_category=category)
        
        analyzed_shorts = queryset.all()
        
        if not analyzed_shorts.exists():
            return Response({
                "message": "No analyzed videos found matching criteria",
                "total_videos": 0
            })
        
        # Calculate statistics
        total_videos = analyzed_shorts.count()
        
        # Score calculations
        quality_scores = [s.video_quality_score for s in analyzed_shorts]
        engagement_scores = [s.engagement_score for s in analyzed_shorts if s.engagement_score]
        technical_scores = [s.technical_score for s in analyzed_shorts if s.technical_score]
        
        avg_quality = sum(quality_scores) / len(quality_scores)
        avg_engagement = sum(engagement_scores) / len(engagement_scores) if engagement_scores else 0
        avg_technical = sum(technical_scores) / len(technical_scores) if technical_scores else 0
        
        # Grade distribution
        grades = {}
        for short in analyzed_shorts:
            grade = short.get_quality_grade()
            grades[grade] = grades.get(grade, 0) + 1
        
        # Quality distribution
        quality_distribution = {
            'excellent': len([s for s in quality_scores if s >= 90]),
            'very_good': len([s for s in quality_scores if 80 <= s < 90]),
            'good': len([s for s in quality_scores if 70 <= s < 80]),
            'fair': len([s for s in quality_scores if 60 <= s < 70]),
            'needs_improvement': len([s for s in quality_scores if s < 60])
        }
        
        # Category distribution
        categories = {}
        for short in analyzed_shorts:
            cat = short.content_category or 'unknown'
            categories[cat] = categories.get(cat, 0) + 1
        
        # Top performers
        top_quality = analyzed_shorts.order_by('-video_quality_score')[:5]
        top_engagement = analyzed_shorts.order_by('-engagement_score')[:5]
        bottom_quality = analyzed_shorts.order_by('video_quality_score')[:5]
        
        # Processing statistics
        total_shorts = Short.objects.filter(is_active=True).count()
        completed_analysis = Short.objects.filter(video_analysis_status='completed').count()
        failed_analysis = Short.objects.filter(video_analysis_status='failed').count()
        pending_analysis = Short.objects.filter(video_analysis_status='pending').count()
        
        return Response({
            "success": True,
            "report": {
                "overview": {
                    "total_videos_analyzed": total_videos,
                    "average_quality_score": round(avg_quality, 2),
                    "average_engagement_score": round(avg_engagement, 2),
                    "average_technical_score": round(avg_technical, 2)
                },
                "distributions": {
                    "grades": grades,
                    "quality_levels": quality_distribution,
                    "content_categories": categories
                },
                "top_performers": {
                    "highest_quality": [
                        {
                            "id": str(s.id),
                            "title": s.title,
                            "quality_score": s.video_quality_score,
                            "grade": s.get_quality_grade()
                        } for s in top_quality
                    ],
                    "highest_engagement": [
                        {
                            "id": str(s.id),
                            "title": s.title,
                            "engagement_score": s.engagement_score or 0,
                            "quality_score": s.video_quality_score
                        } for s in top_engagement
                    ]
                },
                "needs_improvement": [
                    {
                        "id": str(s.id),
                        "title": s.title,
                        "quality_score": s.video_quality_score,
                        "main_issues": s.analysis_weaknesses[:3] if s.analysis_weaknesses else []
                    } for s in bottom_quality
                ],
                "processing_status": {
                    "total_shorts_in_system": total_shorts,
                    "completed_analysis": completed_analysis,
                    "failed_analysis": failed_analysis,
                    "pending_analysis": pending_analysis,
                    "completion_rate": round((completed_analysis / total_shorts) * 100, 2) if total_shorts > 0 else 0
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error generating video analysis report: {str(e)}")
        return Response(
            {"error": f"Report generation failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_video_analysis(request, short_id):
    """
    Get analysis results for a specific video
    """
    try:
        short = Short.objects.get(id=short_id)
        
        # Check permissions
        if short.author != request.user and not request.user.is_staff:
            return Response(
                {"error": "Permission denied"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if short.video_analysis_status != 'completed':
            return Response({
                "status": short.video_analysis_status,
                "message": f"Analysis status: {short.get_video_analysis_status_display()}",
                "error": short.video_analysis_error
            })
        
        return Response({
            "success": True,
            "analysis": {
                "scores": {
                    "overall_quality": short.video_quality_score,
                    "content_quality": short.content_quality_score,
                    "engagement": short.engagement_score,
                    "technical": short.technical_score,
                    "viral_potential": short.viral_potential,
                    "mobile_optimization": short.mobile_optimization,
                    "comprehensive": short.get_comprehensive_quality_score()
                },
                "grade": short.get_quality_grade(),
                "summary": short.video_analysis_summary,
                "category": short.content_category,
                "feedback": {
                    "strengths": short.analysis_strengths,
                    "weaknesses": short.analysis_weaknesses,
                    "recommendations": short.analysis_recommendations
                },
                "technical_details": short.technical_metrics,
                "processed_at": short.video_processed_at,
                "status": short.video_analysis_status
            }
        })
        
    except Short.DoesNotExist:
        return Response(
            {"error": "Short not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"error": f"Error retrieving analysis: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def trigger_automatic_analysis(request):
    """
    Admin endpoint to trigger automatic analysis for newly uploaded videos
    """
    try:
        # Get videos uploaded in the last hour that haven't been analyzed
        from django.utils import timezone
        from datetime import timedelta
        
        recent_videos = Short.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=1),
            video_analysis_status='pending'
        )
        
        processed_count = 0
        for video in recent_videos:
            try:
                # Trigger video analysis
                if gemini_video_service.is_available():
                    video.video_analysis_status = 'processing'
                    video.save(update_fields=['video_analysis_status'])
                    
                    # Analyze the video
                    analysis_result = gemini_video_service.analyze_video(video.video.path)
                    
                    if analysis_result.get('success', False):
                        video.video_quality_score = analysis_result.get('quality_score', 0)
                        video.video_analysis_summary = analysis_result.get('summary', '')
                        video.video_content_categories = analysis_result.get('content_categories', [])
                        video.video_engagement_prediction = analysis_result.get('engagement_prediction', 0)
                        video.video_sentiment_score = analysis_result.get('sentiment_score', 0)
                        video.video_analysis_status = 'completed'
                        video.video_analysis_processed_at = timezone.now()
                        video.video_analysis_error = None
                    else:
                        video.video_analysis_status = 'failed'
                        video.video_analysis_error = analysis_result.get('error', 'Unknown error')
                    
                    video.save()
                    processed_count += 1
                    
            except Exception as e:
                logger.error(f"Error in automatic analysis for video {video.id}: {e}")
                video.video_analysis_status = 'failed'
                video.video_analysis_error = str(e)
                video.save()
        
        return Response({
            'success': True,
            'message': f'Automatic analysis completed for {processed_count} videos',
            'processed_count': processed_count
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error in trigger_automatic_analysis: {e}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)