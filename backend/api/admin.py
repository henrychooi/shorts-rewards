from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from django.http import HttpResponseRedirect, JsonResponse
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from .models import Short, Comment, Wallet, Transaction, AuditLog, View
from .comment_analysis_service import CommentAnalysisService
import logging

logger = logging.getLogger(__name__)

# Register your models here.

@admin.register(Short)
class ShortAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'view_count', 'like_count', 'comment_count', 'get_comment_score_display', 'get_audio_quality_display', 'get_video_quality_display', 'get_video_analysis_status_display', 'created_at', 'analyze_comments_action', 'analyze_video_action')
    list_filter = ('created_at', 'author', 'audio_quality_score', 'comment_analysis_score', 'video_analysis_status', 'video_quality_score')
    search_fields = ('title', 'author__username', 'transcript', 'video_analysis_summary')
    readonly_fields = ('created_at', 'updated_at', 'like_count', 'comment_count', 'audio_processed_at', 'comment_analysis_score', 'video_analysis_processed_at', 'video_quality_score', 'video_engagement_prediction', 'video_sentiment_score')
    fieldsets = (
        ('Basic Info', {
            'fields': ('title', 'author', 'video', 'duration')
        }),
        ('Engagement', {
            'fields': ('view_count', 'like_count', 'comment_count', 'comment_analysis_score')
        }),
        ('Audio Analysis', {
            'fields': ('transcript', 'audio_quality_score', 'transcript_language', 'audio_processed_at'),
            'classes': ('collapse',)
        }),
        ('Video Analysis (Gemini AI)', {
            'fields': ('video_analysis_status', 'video_quality_score', 'video_engagement_prediction', 'video_sentiment_score', 'video_content_categories', 'video_analysis_summary', 'video_analysis_processed_at', 'video_analysis_error'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['analyze_comments_for_selected', 'analyze_videos_for_selected']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analyze-comments/<uuid:short_id>/', self.admin_site.admin_view(self.analyze_comments_view), name='analyze-comments'),
            path('analyze-video/<uuid:short_id>/', self.admin_site.admin_view(self.analyze_video_view), name='analyze-video'),
        ]
        return custom_urls + urls

    @method_decorator(csrf_protect)
    def analyze_comments_view(self, request, short_id):
        """Handle sentiment analysis request for a short"""
        try:
            short = get_object_or_404(Short, id=short_id)
            service = CommentAnalysisService()
            result = service.analyze_comments_for_short(short)

            if result.get('comments_analyzed', 0) > 0:
                messages.success(
                    request,
                    f"Analysis complete! Processed {result.get('comments_analyzed', 0)} comments. "
                    f"Aggregate score: {result.get('aggregate_score', 0):.2f}"
                )
            else:
                messages.info(request, "No new comments to analyze.")

            return HttpResponseRedirect(reverse('admin:api_short_changelist'))

        except Exception as e:
            logger.error(f"Error analyzing comments for short {short_id}: {str(e)}")
            messages.error(request, f"Error during analysis: {str(e)}")
            return HttpResponseRedirect(reverse('admin:api_short_changelist'))

    @method_decorator(csrf_protect)
    def analyze_video_view(self, request, short_id):
        """Handle video analysis request for a short using Gemini AI"""
        try:
            from .gemini_video_service import gemini_video_service
            short = get_object_or_404(Short, id=short_id)
            
            if not gemini_video_service.is_available():
                messages.error(request, "Gemini video analysis service is not available. Please check API configuration.")
                return HttpResponseRedirect(reverse('admin:api_short_changelist'))
            
            if short.video_analysis_status == 'processing':
                messages.warning(request, "Video analysis is already in progress for this short.")
                return HttpResponseRedirect(reverse('admin:api_short_changelist'))
            
            # Set status to processing
            short.video_analysis_status = 'processing'
            short.save(update_fields=['video_analysis_status'])
            
            try:
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
                    from django.utils import timezone
                    short.video_analysis_processed_at = timezone.now()
                    short.video_analysis_error = None
                    
                    short.save(update_fields=[
                        'video_quality_score', 'video_analysis_summary', 'video_content_categories',
                        'video_engagement_prediction', 'video_sentiment_score', 'video_analysis_status',
                        'video_analysis_processed_at', 'video_analysis_error'
                    ])
                    
                    messages.success(
                        request,
                        f"Video analysis complete! Quality Score: {short.video_quality_score:.1f}, "
                        f"Engagement Prediction: {short.video_engagement_prediction:.1f}"
                    )
                else:
                    # Analysis failed
                    error_msg = analysis_result.get('error', 'Unknown analysis error')
                    short.video_analysis_status = 'failed'
                    short.video_analysis_error = error_msg
                    short.save(update_fields=['video_analysis_status', 'video_analysis_error'])
                    messages.error(request, f"Video analysis failed: {error_msg}")
                
            except Exception as analysis_error:
                # Update status to failed
                short.video_analysis_status = 'failed'
                short.video_analysis_error = str(analysis_error)
                short.save(update_fields=['video_analysis_status', 'video_analysis_error'])
                messages.error(request, f"Video analysis failed: {str(analysis_error)}")

            return HttpResponseRedirect(reverse('admin:api_short_changelist'))

        except Exception as e:
            logger.error(f"Error in video analysis view for short {short_id}: {str(e)}")
            messages.error(request, f"Error during video analysis: {str(e)}")
            return HttpResponseRedirect(reverse('admin:api_short_changelist'))

    def get_comment_score_display(self, obj):
        if obj.comment_analysis_score is None:
            return "Not analyzed"
        return f"{obj.comment_analysis_score:.2f}"
    get_comment_score_display.short_description = "Comment Score"

    def get_audio_quality_display(self, obj):
        if obj.audio_quality_score is None:
            return "Not processed"
        return f"{obj.audio_quality_score:.2f}"
    get_audio_quality_display.short_description = "Audio Quality"

    def get_video_quality_display(self, obj):
        if obj.video_quality_score is None:
            return "Not analyzed"
        return f"{obj.video_quality_score:.1f}"
    get_video_quality_display.short_description = "Video Quality"

    def get_video_analysis_status_display(self, obj):
        status_icons = {
            'pending': '⏳ Pending',
            'processing': '🔄 Processing',
            'completed': '✅ Completed',
            'failed': '❌ Failed'
        }
        return status_icons.get(obj.video_analysis_status, obj.video_analysis_status)
    get_video_analysis_status_display.short_description = "Video Status"

    def analyze_comments_action(self, obj):
        """Generate a button to analyze comments for this short"""
        url = reverse('admin:analyze-comments', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" onclick="return confirm(\'Analyze all comments for this short?\');">📊 Analyze</a>',
            url
        )
    analyze_comments_action.short_description = "Actions"

    def analyze_video_action(self, obj):
        """Generate a button to analyze video for this short using Gemini AI"""
        url = reverse('admin:analyze-video', args=[obj.id])
        if obj.video_analysis_status == 'processing':
            return format_html('<span style="color: orange;">🔄 Processing...</span>')
        elif obj.video_analysis_status == 'completed':
            return format_html(
                '<a class="button" href="{}" onclick="return confirm(\'Re-analyze this video?\');">🔄 Re-analyze</a>',
                url
            )
        else:
            return format_html(
                '<a class="button" href="{}" onclick="return confirm(\'Analyze this video with Gemini AI?\');">🤖 Analyze Video</a>',
                url
            )
    analyze_video_action.short_description = "Video AI"

    def analyze_comments_for_selected(self, request, queryset):
        """Admin action to analyze comments for selected shorts"""
        try:
            service = CommentAnalysisService()

            total_shorts = 0
            total_comments = 0

            for short in queryset:
                result = service.analyze_comments_for_short(short)
                total_shorts += 1
                total_comments += result.get('comments_analyzed', 0)

            self.message_user(
                request,
                f"Analysis complete! Processed {total_comments} comments across {total_shorts} shorts.",
                messages.SUCCESS
            )
        except Exception as e:
            self.message_user(
                request,
                f"Error during analysis: {str(e)}",
                messages.ERROR
            )

    analyze_comments_for_selected.short_description = "Analyze comments for selected shorts"

    def analyze_videos_for_selected(self, request, queryset):
        """Admin action to analyze videos for selected shorts using Gemini AI"""
        try:
            from .gemini_video_service import gemini_video_service
            
            if not gemini_video_service.is_available():
                self.message_user(
                    request,
                    "Gemini video analysis service is not available. Please check API configuration.",
                    messages.ERROR
                )
                return

            total_shorts = 0
            successful_analyses = 0
            
            # Limit to 5 videos at once to avoid overwhelming the API
            videos_to_process = queryset.filter(
                video_analysis_status__in=['pending', 'failed']
            )[:5]
            
            if not videos_to_process:
                self.message_user(
                    request,
                    "No videos need analysis (all are completed or already processing).",
                    messages.INFO
                )
                return

            for short in videos_to_process:
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
                        from django.utils import timezone
                        short.video_analysis_processed_at = timezone.now()
                        short.video_analysis_error = None
                        
                        short.save(update_fields=[
                            'video_quality_score', 'video_analysis_summary', 'video_content_categories',
                            'video_engagement_prediction', 'video_sentiment_score', 'video_analysis_status',
                            'video_analysis_processed_at', 'video_analysis_error'
                        ])
                        
                        successful_analyses += 1
                    else:
                        # Analysis failed
                        error_msg = analysis_result.get('error', 'Unknown analysis error')
                        short.video_analysis_status = 'failed'
                        short.video_analysis_error = error_msg
                        short.save(update_fields=['video_analysis_status', 'video_analysis_error'])
                    
                    total_shorts += 1
                    
                    # Add delay between requests to respect rate limits
                    import time
                    time.sleep(1)
                    
                except Exception as e:
                    short.video_analysis_status = 'failed'
                    short.video_analysis_error = str(e)
                    short.save(update_fields=['video_analysis_status', 'video_analysis_error'])
                    total_shorts += 1

            self.message_user(
                request,
                f"Video analysis complete! Successfully analyzed {successful_analyses} out of {total_shorts} videos.",
                messages.SUCCESS
            )
        except Exception as e:
            self.message_user(
                request,
                f"Error during video analysis: {str(e)}",
                messages.ERROR
            )

    analyze_videos_for_selected.short_description = "Analyze videos for selected shorts (Gemini AI)"

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'total_earnings', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'wallet', 'transaction_type', 'amount', 'is_confirmed', 'created_at')
    list_filter = ('transaction_type', 'is_confirmed', 'created_at')
    search_fields = ('id', 'wallet__user__username', 'description')
    readonly_fields = ('id', 'transaction_hash', 'previous_hash', 'merkle_root', 'created_at')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action_type', 'user', 'description', 'created_at')
    list_filter = ('action_type', 'created_at')
    search_fields = ('user__username', 'description')
    readonly_fields = ('id', 'log_hash', 'previous_log_hash', 'created_at')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'short', 'get_content_preview', 'get_sentiment_score_display', 'get_sentiment_label_display', 'analyzed_at', 'created_at', 'analyze_comment_action')
    list_filter = ('created_at', 'sentiment_label', 'analyzed_at', 'is_active')
    search_fields = ('content', 'user__username', 'short__title', 'sentiment_label')
    readonly_fields = ('created_at', 'updated_at', 'analyzed_at', 'sentiment_score', 'sentiment_label')
    actions = ['analyze_comments_for_selected']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analyze-comment/<uuid:comment_id>/', self.admin_site.admin_view(self.analyze_comment_view), name='analyze-comment'),
            path('reanalyze-comment/<uuid:comment_id>/', self.admin_site.admin_view(self.reanalyze_comment_view), name='reanalyze-comment'),
        ]
        return custom_urls + urls

    @method_decorator(csrf_protect)
    def analyze_comment_view(self, request, comment_id):
        """Handle sentiment analysis request for a single comment"""
        return self._analyze_comment(request, comment_id, force=False)

    @method_decorator(csrf_protect)
    def reanalyze_comment_view(self, request, comment_id):
        """Handle re-analysis request for a comment"""
        return self._analyze_comment(request, comment_id, force=True)

    def _analyze_comment(self, request, comment_id, force=False):
        """Common method for analyzing comments"""
        try:
            comment = get_object_or_404(Comment, id=comment_id)
            service = CommentAnalysisService()
            result = service.reanalyze_comment(comment, force=force)

            if result.get('error'):
                messages.error(request, f"Analysis failed: {result['error']}")
            else:
                messages.success(
                    request,
                    f"Comment analysis complete! "
                    f"Score: {result.get('sentiment_score', 0):.2f}, "
                    f"Label: {result.get('sentiment_label', 'Unknown')}"
                )

            return HttpResponseRedirect(reverse('admin:api_comment_changelist'))

        except Exception as e:
            logger.error(f"Error analyzing comment {comment_id}: {str(e)}")
            messages.error(request, f"Error during analysis: {str(e)}")
            return HttpResponseRedirect(reverse('admin:api_comment_changelist'))

    def get_content_preview(self, obj):
        """Show a preview of the comment content"""
        if len(obj.content) > 50:
            return obj.content[:50] + '...'
        return obj.content
    get_content_preview.short_description = "Content Preview"

    def get_sentiment_score_display(self, obj):
        """Display sentiment score with proper formatting"""
        if obj.sentiment_score is None:
            return "Not analyzed"
        return f"{obj.sentiment_score:.2f}"
    get_sentiment_score_display.short_description = "Sentiment Score"

    def get_sentiment_label_display(self, obj):
        """Display sentiment label with color coding"""
        if obj.sentiment_label is None:
            return "Not analyzed"

        if obj.sentiment_label == 'positive':
            color = 'green'
        elif obj.sentiment_label == 'negative':
            color = 'red'
        else:  # neutral
            color = 'orange'

        return format_html('<span style="color: {};"><strong>{}</strong></span>',
                          color, obj.sentiment_label.title())
    get_sentiment_label_display.short_description = "Sentiment"

    def analyze_comment_action(self, obj):
        """Generate a button to analyze this comment"""
        if obj.sentiment_score is not None:
            # Already analyzed, offer re-analysis
            url = reverse('admin:reanalyze-comment', args=[obj.id])
            button_text = "🔄 Re-analyze"
        else:
            # Not analyzed yet
            url = reverse('admin:analyze-comment', args=[obj.id])
            button_text = "📊 Analyze"

        return format_html(
            '<a class="button" href="{}" onclick="return confirm(\'{}?\');">{}</a>',
            url, f"Analyze comment by {obj.user.username}", button_text
        )
    analyze_comment_action.short_description = "Actions"

    def analyze_comments_for_selected(self, request, queryset):
        """Admin action to analyze selected comments"""
        try:
            service = CommentAnalysisService()

            analyzed_count = 0
            error_count = 0

            for comment in queryset:
                result = service.reanalyze_comment(comment, force=True)
                if result.get('error'):
                    error_count += 1
                else:
                    analyzed_count += 1

            self.message_user(
                request,
                f"Analysis complete! Processed {analyzed_count} comments, {error_count} errors.",
                messages.SUCCESS
            )
        except Exception as e:
            self.message_user(
                request,
                f"Error during analysis: {str(e)}",
                messages.ERROR
            )

    analyze_comments_for_selected.short_description = "Analyze selected comments"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'short')


@admin.register(View)
class ViewAdmin(admin.ModelAdmin):
    list_display = ('user', 'short', 'watch_percentage', 'is_complete_view', 'rewatch_count', 'engagement_score', 'created_at', 'updated_at')
    list_filter = ('is_complete_view', 'created_at', 'updated_at')
    search_fields = ('user__username', 'short__title', 'session_id')
    readonly_fields = ('created_at', 'updated_at', 'engagement_score')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'short')
