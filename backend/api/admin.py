from django.contrib import admin
from django.urls import path, reverse
from django.utils.html import format_html
from django.http import HttpResponseRedirect, JsonResponse
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.utils import timezone
from .models import Short, Comment, Wallet, Transaction, AuditLog, View
from .comment_analysis_service import CommentAnalysisService
import logging

logger = logging.getLogger(__name__)

# Register your models here.

@admin.register(Short)
class ShortAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'author', 'duration', 'created_at', 'get_engagement_stats_display',
        'get_comment_score_display', 'get_audio_quality_display', 'get_video_quality_display',
        'get_moderation_status_display', 'get_moderation_input_field',
        'get_main_reward_display', 'get_ai_bonus_display', 'get_moderation_display', 'get_final_reward_display'
    ]
    list_filter = ('created_at', 'author', 'audio_quality_score', 'comment_analysis_score', 'video_analysis_status', 'video_quality_score', 'reward_calculated_at')
    search_fields = ('title', 'author__username', 'transcript', 'video_analysis_summary')
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'get_engagement_stats_display',
        'get_comment_score_display', 'get_audio_quality_display', 'get_video_quality_display',
        'get_moderation_status_display', 'get_moderation_input_field',
        'get_main_reward_display', 'get_ai_bonus_display', 'get_moderation_display', 'get_final_reward_display'
    ]
    fieldsets = (
        ('Basic Info', {
            'fields': ('title', 'author', 'video', 'duration')
        }),
        ('Engagement Stats', {
            'fields': ('view_count', 'like_count', 'comment_count', 'average_watch_percentage', 'get_engagement_stats_display'),
            'description': 'Cached engagement metrics for performance optimization.'
        }),
        ('Comment Analysis', {
            'fields': ('comment_analysis_score',),
            'description': 'AI-powered sentiment analysis of comments.'
        }),
        ('Reward System', {
            'fields': ('main_reward_score', 'ai_bonus_percentage', 'ai_bonus_reward', 'moderation_adjustment', 'final_reward_score', 'reward_calculated_at'),
            'description': 'Reward calculation based on engagement metrics, AI analysis, and moderation adjustments.'
        }),
        ('Moderation System', {
            'fields': ('is_flagged_for_moderation', 'moderation_status', 'moderated_by', 'moderated_at', 'moderation_reason'),
            'description': 'Moderation system for content review and adjustment. Content with comment score < -0.50 is automatically flagged.',
            'classes': ('collapse',)
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
    actions = ['analyze_comments_for_selected', 'analyze_videos_for_selected', 'update_cached_counts_for_selected']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analyze-comments/<uuid:short_id>/', self.admin_site.admin_view(self.analyze_comments_view), name='analyze-comments'),
            path('analyze-video/<uuid:short_id>/', self.admin_site.admin_view(self.analyze_video_view), name='analyze-video'),
            path('moderate-short/<uuid:short_id>/', self.admin_site.admin_view(self.moderate_short_view), name='moderate-short'),
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

    @method_decorator(csrf_protect)
    def moderate_short_view(self, request, short_id):
        """Handle moderation adjustment for flagged content with enhanced auto-calculation"""
        try:
            short = get_object_or_404(Short, id=short_id)
            
            if request.method == 'POST':
                # Get the adjustment percentage from the form
                adjustment_str = request.POST.get('adjustment', '0')
                reason = request.POST.get('reason', 'Admin adjustment via interface').strip()
                
                try:
                    adjustment = float(adjustment_str)
                except ValueError:
                    messages.error(request, "Invalid adjustment value. Please enter a number.")
                    return HttpResponseRedirect(reverse('admin:api_short_changelist'))
                
                # Validate adjustment range (-20% to +20%)
                if not (-20 <= adjustment <= 20):
                    messages.error(request, "Adjustment must be between -20% and +20%")
                    return HttpResponseRedirect(reverse('admin:api_short_changelist'))
                
                # Store previous values for comparison
                old_final_reward = float(short.final_reward_score or 0)
                
                # Apply moderation
                short.moderation_adjustment = adjustment
                short.moderation_status = 'moderated' if adjustment != 0 else 'cleared'
                short.moderated_by = request.user
                short.moderation_reason = reason
                
                # Clear flag if it was set
                if short.is_flagged_for_moderation:
                    short.is_flagged_for_moderation = False
                
                short.moderated_at = timezone.now()
                
                # Automatically recalculate final reward with new adjustment
                short.calculate_final_reward_score()
                
                # Save all changes
                short.save()
                
                # Provide detailed feedback
                new_final_reward = float(short.final_reward_score or 0)
                reward_change = float(new_final_reward - old_final_reward)
                
                if adjustment > 0:
                    action_text = f"increased by {adjustment:.1f}%"
                    change_color = "green"
                elif adjustment < 0:
                    action_text = f"decreased by {abs(adjustment):.1f}%"
                    change_color = "red"
                else:
                    action_text = "set to neutral (0%)"
                    change_color = "gray"
                
                # Create a simple success message without complex formatting
                message_text = (
                    f'Moderation applied successfully! Reward {action_text} '
                    f'(change: {reward_change:+.2f} pts). '
                    f'New final reward: {new_final_reward:.2f} points'
                )
                
                messages.success(request, message_text)
                
            return HttpResponseRedirect(reverse('admin:api_short_changelist'))
            
        except Exception as e:
            logger.error(f"Error in moderation view for short {short_id}: {str(e)}")
            messages.error(request, f"Error during moderation: {str(e)}")
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

    def get_engagement_stats_display(self, obj):
        """Display engagement statistics in a compact format"""
        watch_percentage = obj.average_watch_percentage if obj.average_watch_percentage is not None else 0.0
        return format_html(
            '<div style="font-size: 11px; line-height: 1.2;">'
            '👁️ <strong>{}</strong> views<br/>'
            '❤️ <strong>{}</strong> likes<br/>'
            '💬 <strong>{}</strong> comments<br/>'
            '⏱️ <strong>{}</strong>% avg watch'
            '</div>',
            obj.view_count,
            obj.like_count,
            obj.comment_count,
            round(watch_percentage, 1)
        )
    get_engagement_stats_display.short_description = "Engagement"
    get_engagement_stats_display.allow_tags = True

    def get_video_analysis_status_display(self, obj):
        status_icons = {
            'pending': '⏳ Pending',
            'processing': '🔄 Processing',
            'completed': '✅ Completed',
            'failed': '❌ Failed'
        }
        return status_icons.get(obj.video_analysis_status, obj.video_analysis_status)
    get_video_analysis_status_display.short_description = "Video Status"

    # Reward System Display Methods
    def get_main_reward_display(self, obj):
        if obj.main_reward_score is None:
            return "Not calculated"
        return f"{obj.main_reward_score:.1f} pts"
    get_main_reward_display.short_description = "Main Reward"

    def get_ai_bonus_display(self, obj):
        if obj.ai_bonus_percentage is None or obj.ai_bonus_reward is None:
            return "Not calculated"
        return f"{obj.ai_bonus_percentage:.1f}% ({obj.ai_bonus_reward:.1f} pts)"
    get_ai_bonus_display.short_description = "AI Bonus"

    def get_moderation_display(self, obj):
        if obj.moderation_adjustment is None:
            return "0%"
        color = "green" if obj.moderation_adjustment > 0 else "red" if obj.moderation_adjustment < 0 else "gray"
        return format_html(
            '<span style="color: {};">{}</span>',
            color, f"{obj.moderation_adjustment:+.1f}%"
        )
    get_moderation_display.short_description = "Moderation"

    def get_final_reward_display(self, obj):
        if obj.final_reward_score is None:
            return "Not calculated"
        return format_html(
            '<strong style="color: #2196F3; background: #E3F2FD; padding: 2px 6px; border-radius: 3px;">{} pts</strong>',
            f"{obj.final_reward_score:.1f}"
        )
    get_final_reward_display.short_description = "Final Reward"

    def get_moderation_status_display(self, obj):
        """Display moderation status with color coding"""
        status_colors = {
            'none': 'gray',
            'flagged': 'red',
            'under_review': 'orange',
            'moderated': 'purple',
            'cleared': 'green'
        }
        color = status_colors.get(obj.moderation_status, 'gray')
        
        if obj.is_flagged_for_moderation:
            flag_icon = "🚩"
        else:
            flag_icon = ""
            
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, flag_icon, obj.get_moderation_status_display()
        )
    get_moderation_status_display.short_description = "Mod Status"

    def get_moderation_input_field(self, obj):
        """Display interactive moderation input field for flagged content"""
        if obj.is_flagged_for_moderation or obj.moderation_status in ['flagged', 'under_review'] or obj.moderation_status == 'moderated':
            current_value = obj.moderation_adjustment or 0
            return format_html(
                '''
                <div style="display: flex; align-items: center; gap: 5px;">
                    <input type="number" 
                           id="mod_input_{}" 
                           value="{}" 
                           min="-20" 
                           max="20" 
                           step="0.1" 
                           style="width: 60px; padding: 2px;"
                           onchange="applyModeration('{}', this.value)"
                    />
                    <span style="font-size: 11px;">%</span>
                    <button onclick="applyModeration('{}', document.getElementById('mod_input_{}').value)" 
                            style="background: #4CAF50; color: white; border: none; padding: 2px 6px; border-radius: 3px; cursor: pointer; font-size: 11px;">
                        Apply
                    </button>
                </div>
                <script>
                function applyModeration(shortId, adjustment) {{
                    const value = parseFloat(adjustment);
                    if (isNaN(value) || value < -20 || value > 20) {{
                        alert('Please enter a value between -20 and 20');
                        return;
                    }}
                    
                    const form = document.createElement('form');
                    form.method = 'POST';
                    form.action = '/admin/api/short/moderate-short/' + shortId + '/';
                    
                    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
                    form.innerHTML = `
                        <input type="hidden" name="csrfmiddlewaretoken" value="${{csrfToken}}">
                        <input type="hidden" name="adjustment" value="${{value}}">
                        <input type="hidden" name="reason" value="Admin adjustment via interface">
                    `;
                    
                    document.body.appendChild(form);
                    form.submit();
                }}
                </script>
                ''',
                obj.id, current_value, obj.id, obj.id, obj.id
            )
        elif obj.moderation_status == 'cleared':
            return format_html('<span style="color: green; font-size: 12px;">✅ Cleared</span>')
        else:
            return format_html('<span style="color: gray; font-size: 12px;">No action needed</span>')
    get_moderation_input_field.short_description = "Moderate"

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

    def calculate_rewards_action(self, obj):
        """Generate a button to calculate rewards for this short"""
        # Create a simple JavaScript onclick handler for now
        if obj.reward_calculated_at:
            return format_html(
                '<button onclick="alert(\'Feature coming soon!\');" class="button">🔢 Recalculate</button>'
            )
        else:
            return format_html(
                '<button onclick="alert(\'Feature coming soon!\');" class="button">💰 Calculate</button>'
            )
    calculate_rewards_action.short_description = "Rewards"

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

    def update_cached_counts_for_selected(self, request, queryset):
        """Admin action to update cached like_count, comment_count, and average_watch_percentage"""
        try:
            updated_count = 0
            total_count = queryset.count()
            
            for short in queryset:
                try:
                    short.update_cached_counts()
                    updated_count += 1
                except Exception as e:
                    logger.error(f"Error updating cached counts for short {short.id}: {e}")
                    continue
            
            if updated_count == total_count:
                self.message_user(
                    request,
                    f"Successfully updated cached counts for {updated_count} shorts.",
                    messages.SUCCESS
                )
            else:
                self.message_user(
                    request,
                    f"Updated {updated_count} out of {total_count} shorts. Check logs for errors.",
                    messages.WARNING
                )
                
        except Exception as e:
            self.message_user(
                request,
                f"Error updating cached counts: {str(e)}",
                messages.ERROR
            )

    update_cached_counts_for_selected.short_description = "Update cached engagement counts"

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
    list_display = ('user', 'short', 'get_content_preview', 'get_sentiment_score_display', 'get_sentiment_label_display', 'analyzed_at', 'created_at')
    list_filter = ('created_at', 'sentiment_label', 'analyzed_at', 'is_active')
    search_fields = ('content', 'user__username', 'short__title', 'sentiment_label')
    readonly_fields = ('created_at', 'updated_at', 'analyzed_at', 'sentiment_score', 'sentiment_label')
    actions = ['analyze_comments_for_selected']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analyze-comment/<int:comment_id>/', self.admin_site.admin_view(self.analyze_comment_view), name='analyze-comment'),
            path('reanalyze-comment/<int:comment_id>/', self.admin_site.admin_view(self.reanalyze_comment_view), name='reanalyze-comment'),
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

    # def analyze_comment_action(self, obj):
    #     """Generate a button to analyze this comment"""
    #     if obj.sentiment_score is not None:
    #         # Already analyzed, offer re-analysis
    #         url = reverse('admin:reanalyze-comment', args=[obj.id])
    #         button_text = "🔄 Re-analyze"
    #     else:
    #         # Not analyzed yet
    #         url = reverse('admin:analyze-comment', args=[obj.id])
    #         button_text = "📊 Analyze"

    #     return format_html(
    #         '<a class="button" href="{}" onclick="return confirm(\'{}?\');">{}</a>',
    #         url, f"Analyze comment by {obj.user.username}", button_text
    #     )
    # analyze_comment_action.short_description = "Actions"

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
