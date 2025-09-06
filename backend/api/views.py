from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from django.db.models import F
from decimal import Decimal
from .signals import analysis_completed
from datetime import datetime
from django.utils import timezone
from pathlib import Path
from django.conf import settings
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
from .reward_service import monthly_revenue_service
from .models import Note, Short, Like, Comment, View, Wallet, Transaction, AuditLog
from .gemini_video_service import gemini_video_service
from .gemini_audio_service import gemini_audio_service
import logging
import os
import time

logger = logging.getLogger(__name__)


class ShortsListView(generics.ListAPIView):
    from .serializers import ShortListSerializer
    serializer_class = ShortListSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        # Use a lean queryset; avoid eager-loading comments for list view
        return (
            Short.objects
            .filter(is_active=True)
            .select_related('author')
            .prefetch_related('likes')
            .only(
                'id','title','description','video','thumbnail','author','created_at',
                'view_count','like_count','comment_count','duration','is_active'
            )
        )


class ShortCreateView(generics.CreateAPIView):
    serializer_class = ShortCreateSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)
    
    def perform_create(self, serializer):
        short = serializer.save(author=self.request.user)
        
        # Process both audio and video analysis asynchronously
        self.process_video_audio_async(short)
        self.process_video_analysis_async(short)
    
    def process_video_audio_async(self, short):
        """Start audio analysis in a background thread to avoid blocking the response"""
        def analyze_audio_in_background():
            try:
                self.process_video_audio(short)
            except Exception as e:
                logger.error(f"Background audio analysis failed for {short.id}: {e}")
        
        # Start audio analysis in background thread
        audio_thread = threading.Thread(target=analyze_audio_in_background)
        audio_thread.daemon = True
        audio_thread.start()
        logger.info(f"Started background audio analysis for {short.id}")
    
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
        """Process the uploaded video to generate transcript and quality score using Gemini"""
        try:
            if not gemini_audio_service.is_available():
                logger.warning(f"Gemini audio service not available for video {short.id}")
                return
            
            # Get the video file path
            video_path = short.video.path
            
            # Process the video using Gemini for audio analysis
            result = gemini_audio_service.analyze_video_audio(video_path)
            
            if result:
                # Always save the results - the service provides default scores on errors
                short.transcript = result.get('transcript', '')
                short.audio_quality_score = result.get('audio_quality_score', 0.0)
                short.transcript_language = result.get('language', 'en')
                short.audio_processed_at = timezone.now()
                short.save(update_fields=['transcript', 'audio_quality_score', 'transcript_language', 'audio_processed_at'])
                
                # Trigger signal for automatic reward calculation
                
                analysis_completed.send(sender=Short, short_id=short.id, analysis_type='audio')
                
                # Trigger auto reward calculation after audio analysis completion
                short.auto_calculate_rewards_if_ready()
                
                if result.get('success', True):
                    logger.info(f"Successfully processed audio for video {short.id}: quality_score={short.audio_quality_score}")
                else:
                    logger.warning(f"Audio processed with fallback scores for video {short.id}: quality_score={short.audio_quality_score}, error={result.get('error', 'Unknown error')}")
            else:
                logger.error(f"Failed to process audio for video {short.id}: No result returned")
        
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
                
                # Trigger auto reward calculation after video analysis completion
                short.auto_calculate_rewards_if_ready()
                
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
    Process all MP4 videos in the media directory and analyze their audio quality using Gemini
    """
    try:
        logger.info("Starting batch audio processing for all videos using Gemini")
        
        if not gemini_audio_service.is_available():
            return Response(
                {'error': 'Gemini audio processing service not available'}, 
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Find all video files in the media directory
        media_videos_path = Path(settings.MEDIA_ROOT) / 'videos'
        video_files = list(media_videos_path.glob("*.mp4"))
        
        results = []
        for video_file in video_files:
            try:
                result = gemini_audio_service.analyze_video_audio(str(video_file))
                if result and 'error' not in result:
                    results.append({
                        'filename': video_file.name,
                        'transcript': result.get('transcript', ''),
                        'audio_quality_score': result.get('audio_quality_score', 0.0),
                        'language': result.get('language', 'en')
                    })
                else:
                    results.append({
                        'filename': video_file.name,
                        'error': result.get('error', 'Unknown error')
                    })
            except Exception as e:
                results.append({
                    'filename': video_file.name,
                    'error': str(e)
                })
        
        # Calculate summary statistics
        total_videos = len(results)
        successful_processes = len([r for r in results if 'error' not in r])
        average_quality = sum([r.get('audio_quality_score', 0) for r in results if 'error' not in r]) / successful_processes if successful_processes > 0 else 0
        
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
    Process a single video for audio quality analysis using Gemini
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
        
        if not gemini_audio_service.is_available():
            return Response({
                'success': False,
                'error': 'Gemini audio processing service not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Construct full path to video file
        media_videos_path = Path(settings.MEDIA_ROOT) / 'videos'
        video_path = media_videos_path / video_filename
        
        if not video_path.exists():
            return Response({
                'success': False,
                'error': f'Video file {video_filename} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        result = gemini_audio_service.analyze_video_audio(str(video_path))
        
        if 'error' in result:
            return Response({
                'success': False,
                'error': result['error']
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        response_data = {
            'success': True,
            'message': f'Successfully processed {video_filename}',
            'result': {
                'filename': video_filename,
                'transcript': result.get('transcript', ''),
                'audio_quality_score': result.get('audio_quality_score', 0.0),
                'language': result.get('language', 'en')
            }
        }
        
        logger.info(f"Single video processing completed: {video_filename} - Quality: {result.get('audio_quality_score', 0):.1f}")
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
    Get a summary report of all processed audio files using Gemini
    """
    try:
        # This processes all videos to get current status using Gemini
        
        if not gemini_audio_service.is_available():
            return Response(
                {'error': 'Gemini audio processing service not available'}, 
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Find all video files and process them
        media_videos_path = Path(settings.MEDIA_ROOT) / 'videos'
        video_files = list(media_videos_path.glob("*.mp4"))
        
        results = []
        for video_file in video_files:
            try:
                result = gemini_audio_service.analyze_video_audio(str(video_file))
                if result and 'error' not in result:
                    results.append({
                        'filename': video_file.name,
                        'audio_quality_score': result.get('audio_quality_score', 0.0)
                    })
            except Exception as e:
                results.append({
                    'filename': video_file.name,
                    'error': str(e)
                })
        
        # Generate report
        valid_results = [r for r in results if 'error' not in r]
        report = {
            'total_videos': len(results),
            'quality_distribution': {
                'excellent': len([r for r in valid_results if r['audio_quality_score'] >= 80]),
                'good': len([r for r in valid_results if 60 <= r['audio_quality_score'] < 80]),
                'fair': len([r for r in valid_results if 40 <= r['audio_quality_score'] < 60]),
                'poor': len([r for r in valid_results if r['audio_quality_score'] < 40])
            },
            'average_quality_score': sum([r['audio_quality_score'] for r in valid_results]) / len(valid_results) if valid_results else 0,
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
        media_videos_path = Path(settings.MEDIA_ROOT) / 'videos'
        videos = list(media_videos_path.glob("*.mp4"))
        
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
    Traditional Django view for processing videos using Gemini (without DRF)
    """
    try:
        if request.method == 'POST':
            data = json.loads(request.body)
            video_filename = data.get('video_filename')
            
            if not gemini_audio_service.is_available():
                return JsonResponse({
                    'success': False,
                    'error': 'Gemini audio processing service not available'
                }, status=503)
            
            if video_filename:
                # Process single video
                media_videos_path = Path(settings.MEDIA_ROOT) / 'videos'
                video_path = media_videos_path / video_filename
                
                if not video_path.exists():
                    return JsonResponse({
                        'success': False,
                        'error': f'Video file {video_filename} not found'
                    }, status=404)
                
                result = gemini_audio_service.analyze_video_audio(str(video_path))
                return JsonResponse({
                    'success': 'error' not in result,
                    'result': result
                })
            else:
                # Process all videos
                media_videos_path = Path(settings.MEDIA_ROOT) / 'videos'
                video_files = list(media_videos_path.glob("*.mp4"))
                
                results = []
                for video_file in video_files:
                    try:
                        result = gemini_audio_service.analyze_video_audio(str(video_file))
                        if result and 'error' not in result:
                            results.append({
                                'filename': video_file.name,
                                'transcript': result.get('transcript', ''),
                                'audio_quality_score': result.get('audio_quality_score', 0.0),
                                'language': result.get('language', 'en')
                            })
                        else:
                            results.append({
                                'filename': video_file.name,
                                'error': result.get('error', 'Unknown error')
                            })
                    except Exception as e:
                        results.append({
                            'filename': video_file.name,
                            'error': str(e)
                        })
                
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
    
    # Update the cached like count
    short.like_count = short.like_count_calculated
    short.save(update_fields=['like_count'])
    
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
        
        # Update the cached comment count
        short.comment_count = short.comment_count_calculated
        short.save(update_fields=['comment_count'])
        
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
        
        # Get the updated count and recalculate complete rewards
        short.refresh_from_db()
        
        # Trigger complete reward recalculation if rewards have been calculated before
        if short.reward_calculated_at:
            # Recalculate all reward components
            short.calculate_main_reward_score()
            short.calculate_ai_bonus_percentage()
            short.calculate_final_reward_score()
            short.save()
            logger.info(f"Recalculated complete rewards for Short {short.id} after view increment")
        else:
            # Try auto-calculation if this is the first time
            short.auto_calculate_rewards_if_ready()
        
        print(f"DEBUG: View incremented for short {short_id}. New view count: {short.view_count}")
        
        return Response({
            'status': 'success',
            'view_count': short.view_count,
            'main_reward_score': short.main_reward_score,
            'final_reward_score': short.final_reward_score
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
        if request.user.is_authenticated:
            existing_views = View.objects.filter(
                user=request.user,
                short=short
            ).exclude(session_id=session_id)
        else:
            # For anonymous users, approximate uniqueness by IP
            existing_views = View.objects.filter(
                user__isnull=True,
                short=short,
                ip_address=ip_address
            ).exclude(session_id=session_id)
        
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


@api_view(['POST'])
@permission_classes([IsAdminUser])
def recalculate_short_rewards(request, short_id):
    """Admin endpoint to manually recalculate rewards for a specific short"""
    try:
        short = get_object_or_404(Short, id=short_id, is_active=True)
        
        # Store original values for comparison
        original_main = short.main_reward_score
        original_final = short.final_reward_score
        original_avg_watch = short.average_watch_percentage
        
        # Recalculate all rewards
        short.recalculate_all_rewards()
        
        # Return comparison
        return Response({
            'status': 'success',
            'message': 'Rewards recalculated successfully',
            'short_id': str(short.id),
            'changes': {
                'average_watch_percentage': {
                    'before': round(original_avg_watch or 0, 2),
                    'after': round(short.average_watch_percentage or 0, 2)
                },
                'main_reward_score': {
                    'before': round(original_main or 0, 2),
                    'after': round(short.main_reward_score or 0, 2)
                },
                'final_reward_score': {
                    'before': round(original_final or 0, 2),
                    'after': round(short.final_reward_score or 0, 2)
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error recalculating rewards for short {short_id}: {e}")
        return Response({
            'status': 'error',
            'message': f'Failed to recalculate rewards: {str(e)}'
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_my_account(request):
    """
    Permanently delete the authenticated user's account.
    Body: { "confirm": "DELETE" } or { "confirm": "<username>" }
    """
    try:
        confirm = str(request.data.get('confirm', '')).strip()
        if not confirm or (confirm != 'DELETE' and confirm != request.user.username):
            return Response({
                'success': False,
                'error': 'Confirmation failed. Type DELETE or your username to confirm.'
            }, status=status.HTTP_400_BAD_REQUEST)

        username = request.user.username

        # Optional: create an audit log entry before deletion
        try:
            AuditLog.objects.create(
                action_type='admin_action',
                user=request.user,
                description='User initiated account deletion',
                metadata={'username': username}
            )
        except Exception:
            pass

        # Delete the user (cascades to Wallet, Transactions, Shorts, etc.)
        request.user.delete()

        return Response({
            'success': True,
            'message': f'Account {username} has been deleted.'
        })

    except Exception as e:
        logger.error(f"Error deleting account for {request.user.username}: {e}")
        return Response({
            'success': False,
            'error': 'Failed to delete account'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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


# Reward System API Views
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_short_rewards(request, short_id):
    """
    Calculate and assign rewards for a specific short
    """
    try:
        short = get_object_or_404(Short, id=short_id, is_active=True)
        
        # Check if user owns the short or is admin
        if short.author != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        from .reward_service import ContentCreatorRewardService
        reward_service = ContentCreatorRewardService()
        
        # Calculate rewards for the short
        result = reward_service.calculate_rewards_for_short(short)
        
        if result.get('error'):
            return Response({
                'success': False,
                'error': result['error']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'short_id': str(short_id),
            'rewards': {
                'main_reward_score': result['main_reward_score'],
                'ai_bonus_percentage': result['ai_bonus_percentage'],
                'moderation_adjustment': result['moderation_adjustment'],
                'final_reward_score': result['final_reward_score'],
                'calculated_at': result['calculated_at'].isoformat()
            },
            'breakdown': result.get('breakdown', {})
        })
        
    except Exception as e:
        logger.error(f"Error calculating rewards for short {short_id}: {str(e)}")
        return Response({
            'success': False,
            'error': f'Reward calculation failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_short_payout(request, short_id):
    """
    Process payout for a specific short's accumulated rewards
    """
    try:
        short = get_object_or_404(Short, id=short_id, is_active=True)
        
        # Check if user owns the short or is admin
        if short.author != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        from .reward_service import ContentCreatorRewardService
        reward_service = ContentCreatorRewardService()
        
        # Process payout for the short
        result = reward_service.process_payout_for_short(short)
        
        if result.get('error'):
            return Response({
                'success': False,
                'error': result['error']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'short_id': str(short_id),
            'payout': {
                'amount': str(result['payout_amount']),
                'points_converted': result['points_converted'],
                'transaction_id': str(result['transaction'].id),
                'processed_at': result['processed_at'].isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error processing payout for short {short_id}: {str(e)}")
        return Response({
            'success': False,
            'error': f'Payout processing failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def creator_reward_summary(request):
    """
    Get comprehensive reward summary for the authenticated creator
    """
    try:
        from .reward_service import ContentCreatorRewardService
        reward_service = ContentCreatorRewardService()
        
        # Get summary for the user
        summary = reward_service.get_creator_summary(request.user)
        
        return Response({
            'success': True,
            'creator': request.user.username,
            'summary': {
                'total_shorts': summary['total_shorts'],
                'shorts_with_rewards': summary['shorts_with_rewards'],
                'total_reward_points': summary['total_reward_points'],
                'estimated_payout': str(summary['estimated_payout']),
                'average_main_reward': summary['average_main_reward'],
                'average_ai_bonus': summary['average_ai_bonus'],
                'average_moderation_score': summary['average_moderation_score'],
                'performance_metrics': summary['performance_metrics']
            },
            'recent_rewards': summary['recent_rewards'][:10]  # Latest 10 rewards
        })
        
    except Exception as e:
        logger.error(f"Error getting creator reward summary for {request.user.username}: {str(e)}")
        return Response({
            'success': False,
            'error': f'Failed to get reward summary: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_batch_calculate_rewards(request):
    """
    Admin endpoint to calculate rewards for multiple shorts in batch
    """
    try:
        from .reward_service import ContentCreatorRewardService
        reward_service = ContentCreatorRewardService()
        
        # Get parameters
        creator_id = request.data.get('creator_id')
        recalculate = request.data.get('recalculate', False)
        limit = request.data.get('limit', 50)
        
        # Process rewards
        result = reward_service.batch_calculate_rewards(
            creator_id=creator_id,
            recalculate=recalculate,
            limit=limit
        )
        
        return Response({
            'success': True,
            'batch_result': {
                'processed_shorts': result['processed_shorts'],
                'successful_calculations': result['successful_calculations'],
                'failed_calculations': result['failed_calculations'],
                'total_points_awarded': result['total_points_awarded'],
                'processing_time': result['processing_time']
            },
            'results': result['results']
        })
        
    except Exception as e:
        logger.error(f"Error in admin batch reward calculation: {str(e)}")
        return Response({
            'success': False,
            'error': f'Batch calculation failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_batch_process_payouts(request):
    """
    Admin endpoint to process payouts for multiple creators
    """
    try:
        from .reward_service import ContentCreatorRewardService
        reward_service = ContentCreatorRewardService()
        
        # Get parameters
        creator_ids = request.data.get('creator_ids', [])
        minimum_payout = request.data.get('minimum_payout', 10.0)  # Minimum $10 payout
        
        # Process payouts
        result = reward_service.batch_process_payouts(
            creator_ids=creator_ids,
            minimum_payout=minimum_payout
        )
        
        return Response({
            'success': True,
            'payout_result': {
                'processed_creators': result['processed_creators'],
                'successful_payouts': result['successful_payouts'],
                'failed_payouts': result['failed_payouts'],
                'total_amount_paid': str(result['total_amount_paid']),
                'processing_time': result['processing_time']
            },
            'results': result['results']
        })
        
    except Exception as e:
        logger.error(f"Error in admin batch payout processing: {str(e)}")
        return Response({
            'success': False,
            'error': f'Batch payout processing failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_reward_dashboard(request):
    """
    Admin dashboard with comprehensive reward system statistics
    """
    try:
        from .reward_service import ContentCreatorRewardService
        reward_service = ContentCreatorRewardService()
        
        # Get dashboard data
        dashboard = reward_service.get_admin_dashboard()
        
        return Response({
            'success': True,
            'dashboard': {
                'system_overview': {
                    'total_creators': dashboard['total_creators'],
                    'active_creators': dashboard['active_creators'],
                    'total_shorts_with_rewards': dashboard['total_shorts_with_rewards'],
                    'total_reward_points': dashboard['total_reward_points'],
                    'total_estimated_payouts': str(dashboard['total_estimated_payouts'])
                },
                'recent_activity': {
                    'rewards_calculated_today': dashboard['rewards_calculated_today'],
                    'payouts_processed_today': dashboard['payouts_processed_today'],
                    'total_amount_paid_today': str(dashboard['total_amount_paid_today'])
                },
                'performance_metrics': dashboard['performance_metrics'],
                'top_creators': dashboard['top_creators'][:10],  # Top 10 creators
                'recent_payouts': dashboard['recent_payouts'][:20]  # Latest 20 payouts
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting admin reward dashboard: {str(e)}")
        return Response({
            'success': False,
            'error': f'Dashboard data retrieval failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reward_history(request):
    """
    Get reward calculation history for the authenticated user
    """
    try:
        # Get user's shorts with rewards
        user_shorts = Short.objects.filter(
            author=request.user,
            is_active=True,
            reward_calculated_at__isnull=False
        ).order_by('-reward_calculated_at')
        
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        
        # Simple pagination
        start = (page - 1) * page_size
        end = start + page_size
        paginated_shorts = user_shorts[start:end]
        
        history = []
        for short in paginated_shorts:
            history.append({
                'short_id': str(short.id),
                'title': short.title or 'Untitled',
                'main_reward_score': short.main_reward_score,
                'ai_bonus_percentage': short.ai_bonus_percentage,
                'moderation_adjustment': short.moderation_adjustment,
                'final_reward_score': short.final_reward_score,
                'calculated_at': short.reward_calculated_at.isoformat(),
                'engagement_metrics': {
                    'views': short.view_count,
                    'likes': short.like_count,
                    'comments': short.comment_count
                }
            })
        
        return Response({
            'success': True,
            'history': history,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': user_shorts.count(),
                'has_next': end < user_shorts.count()
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting reward history for {request.user.username}: {str(e)}")
        return Response({
            'success': False,
            'error': f'Failed to get reward history: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reward_analytics(request):
    """
    Get reward analytics and insights for the authenticated user
    """
    try:
        from .reward_service import ContentCreatorRewardService
        reward_service = ContentCreatorRewardService()
        
        # Get analytics for the user
        analytics = reward_service.get_creator_analytics(request.user)
        
        return Response({
            'success': True,
            'analytics': {
                'performance_trends': analytics['performance_trends'],
                'reward_distribution': analytics['reward_distribution'],
                'top_performing_content': analytics['top_performing_content'],
                'improvement_suggestions': analytics['improvement_suggestions'],
                'monthly_progression': analytics['monthly_progression']
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting reward analytics for {request.user.username}: {str(e)}")
        return Response({
            'success': False,
            'error': f'Failed to get reward analytics: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Monthly Revenue Sharing API Endpoints

@api_view(['GET'])
@permission_classes([IsAdminUser])
def monthly_creator_points(request):
    """
    Get creator points for a specific month.
    Query params: year, month
    """
    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
        
        creator_points = monthly_revenue_service.get_monthly_creator_points(year, month)
        
        return Response({
            'success': True,
            'year': year,
            'month': month,
            'creators_count': len(creator_points),
            'total_points': sum(data['total_points'] for data in creator_points.values()),
            'creator_points': {
                str(creator_id): data for creator_id, data in creator_points.items()
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def calculate_monthly_revenue_share(request):
    """
    Calculate monthly revenue share distribution.
    Body: {"year": 2024, "month": 12, "platform_revenue": "10000.00"}
    """
    try:
        year = request.data.get('year', timezone.now().year)
        month = request.data.get('month', timezone.now().month)
        platform_revenue = Decimal(str(request.data.get('platform_revenue', 0)))
        
        if platform_revenue <= 0:
            return Response({
                'success': False,
                'error': 'Platform revenue must be greater than 0'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        calculation = monthly_revenue_service.calculate_monthly_revenue_share(
            year, month, platform_revenue
        )
        
        return Response(calculation)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def process_monthly_payouts(request):
    """
    Process monthly revenue share payouts to creators.
    Body: {"year": 2024, "month": 12, "platform_revenue": "10000.00", "dry_run": false}
    """
    try:
        year = request.data.get('year', timezone.now().year)
        month = request.data.get('month', timezone.now().month)
        platform_revenue = Decimal(str(request.data.get('platform_revenue', 0)))
        dry_run = request.data.get('dry_run', True)  # Default to dry run for safety
        
        if platform_revenue <= 0:
            return Response({
                'success': False,
                'error': 'Platform revenue must be greater than 0'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = monthly_revenue_service.process_monthly_payouts(
            year, month, platform_revenue, dry_run
        )
        
        return Response(result)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_monthly_earnings(request):
    """
    Get current user's monthly points and estimated earnings.
    Query params: year, month
    """
    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
        
        # Get all creator points for the month
        all_creator_points = monthly_revenue_service.get_monthly_creator_points(year, month)
        
        # Find current user's data
        user_data = all_creator_points.get(request.user.id, {
            'user': request.user,
            'username': request.user.username,
            'total_points': 0,
            'shorts_count': 0,
            'shorts': []
        })
        
        # Calculate user's percentage of total points
        total_points = sum(data['total_points'] for data in all_creator_points.values())
        user_percentage = (user_data['total_points'] / total_points * 100) if total_points > 0 else 0
        
        return Response({
            'success': True,
            'year': year,
            'month': month,
            'user_points': user_data['total_points'],
            'shorts_count': user_data['shorts_count'],
            'total_points_all_creators': total_points,
            'user_percentage': round(user_percentage, 4),
            'shorts': user_data['shorts'],
            'estimated_earnings_formula': f"({user_data['total_points']} / {total_points}) × 50% × Platform Revenue"
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def calculate_points_for_shorts(request):
    """
    Calculate points for shorts that don't have calculated scores yet.
    Uses the point calculation from Short model: (views * 1) + (likes * 5) + (comments * 10) + AI bonuses
    Body: {"year": 2024, "month": 12} (optional - if not provided, calculates for all)
    """
    try:
        year = request.data.get('year')
        month = request.data.get('month')
        
        result = monthly_revenue_service.calculate_points_for_uncalculated_shorts(year, month)
        
        return Response(result)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def withdraw_wallet_balance(request):
    """
    Withdraw entire wallet balance for the current user.
    Sets wallet balance to 0 and creates withdrawal transaction.
    """
    try:
        result = monthly_revenue_service.withdraw_wallet_balance(request.user.id)
        
        if result['success']:
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_payout_history(request):
    """
    Get current user's monthly payout history.
    Query params: limit (default 12)
    """
    try:
        limit = int(request.GET.get('limit', 12))
        
        result = monthly_revenue_service.get_user_monthly_payouts(request.user.id, limit)
        
        return Response(result)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# TEST ENDPOINTS FOR MONTHLY REVENUE SHARING
@api_view(['POST'])
@permission_classes([IsAdminUser])
def test_monthly_revenue_share(request):
    """
    TEST ENDPOINT: Test monthly revenue sharing system.
    Body: {
        "platform_revenue": 10000,
        "year": 2025, 
        "month": 8,
        "dry_run": true
    }
    """
    try:
        platform_revenue = Decimal(str(request.data.get('platform_revenue', 10000)))
        year = request.data.get('year')
        month = request.data.get('month')
        dry_run = request.data.get('dry_run', True)
        
        result = monthly_revenue_service.test_monthly_revenue_share(
            platform_revenue=platform_revenue,
            target_year=year,
            target_month=month,
            dry_run=dry_run
        )
        
        return Response(result)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def test_5min_payout(request):
    """
    TEST ENDPOINT: Trigger 5-minute payout distribution.
    Body: {"platform_revenue": 1000, "dry_run": true}
    """
    try:
        platform_revenue = Decimal(str(request.data.get('platform_revenue', 1000)))
        dry_run = request.data.get('dry_run', True)
        minutes = int(request.data.get('minutes', 5))

        result = monthly_revenue_service.test_5minute_payout(
            platform_revenue=platform_revenue,
            dry_run=dry_run,
            minutes=minutes
        )

        return Response(result)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def test_3min_payout(request):
    """
    TEST ENDPOINT: Trigger 3-minute payout distribution.
    Body: {"platform_revenue": 1000, "dry_run": true}
    """
    try:
        platform_revenue = Decimal(str(request.data.get('platform_revenue', 1000)))
        dry_run = request.data.get('dry_run', True)

        result = monthly_revenue_service.test_3minute_payout(
            platform_revenue=platform_revenue,
            dry_run=dry_run
        )

        return Response(result)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_test_shorts(request):
    """
    TEST ENDPOINT: Create test shorts for a specific month to test revenue sharing.
    Body: {
        "year": 2025,
        "month": 7,
        "num_shorts": 5
    }
    """
    try:
        year = request.data.get('year', 2025)
        month = request.data.get('month', 7)
        num_shorts = request.data.get('num_shorts', 5)
        
        result = monthly_revenue_service.create_test_shorts_for_month(
            target_year=year,
            target_month=month,
            num_shorts=num_shorts
        )
        
        return Response(result)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
