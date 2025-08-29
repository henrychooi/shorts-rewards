from django.contrib import admin
from .models import Short, Wallet, Transaction, AuditLog, View

# Register your models here.

@admin.register(Short)
class ShortAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'view_count', 'like_count', 'comment_count', 'get_audio_quality_display', 'created_at')
    list_filter = ('created_at', 'author', 'audio_quality_score')
    search_fields = ('title', 'author__username', 'transcript')
    readonly_fields = ('created_at', 'updated_at', 'like_count', 'comment_count', 'audio_processed_at')
    fieldsets = (
        ('Basic Info', {
            'fields': ('title', 'author', 'video', 'duration')
        }),
        ('Engagement', {
            'fields': ('view_count', 'like_count', 'comment_count')
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
    
    def get_audio_quality_display(self, obj):
        if obj.audio_quality_score is None:
            return "Not processed"
        return f"{obj.audio_quality_score:.2f}"
    get_audio_quality_display.short_description = "Audio Quality"

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

@admin.register(View)
class ViewAdmin(admin.ModelAdmin):
    list_display = ('user', 'short', 'watch_percentage', 'is_complete_view', 'rewatch_count', 'engagement_score', 'created_at', 'updated_at')
    list_filter = ('is_complete_view', 'created_at', 'updated_at')
    search_fields = ('user__username', 'short__title', 'session_id')
    readonly_fields = ('created_at', 'updated_at', 'engagement_score')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'short')
