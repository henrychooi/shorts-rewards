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
    list_display = ('title', 'author', 'view_count', 'like_count', 'comment_count', 'get_comment_score_display', 'get_audio_quality_display', 'created_at', 'analyze_comments_action')
    list_filter = ('created_at', 'author', 'audio_quality_score', 'comment_analysis_score')
    search_fields = ('title', 'author__username', 'transcript')
    readonly_fields = ('created_at', 'updated_at', 'like_count', 'comment_count', 'audio_processed_at', 'comment_analysis_score')
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
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['analyze_comments_for_selected']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analyze-comments/<uuid:short_id>/', self.admin_site.admin_view(self.analyze_comments_view), name='analyze-comments'),
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

    def analyze_comments_action(self, obj):
        """Generate a button to analyze comments for this short"""
        url = reverse('admin:analyze-comments', args=[obj.id])
        return format_html(
            '<a class="button" href="{}" onclick="return confirm(\'Analyze all comments for this short?\');">📊 Analyze</a>',
            url
        )
    analyze_comments_action.short_description = "Actions"

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
