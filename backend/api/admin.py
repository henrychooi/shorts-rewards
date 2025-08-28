from django.contrib import admin
from .models import Short, Wallet, Transaction, AuditLog

# Register your models here.

@admin.register(Short)
class ShortAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'view_count', 'like_count', 'comment_count', 'created_at')
    list_filter = ('created_at', 'author')
    search_fields = ('title', 'author__username')
    readonly_fields = ('created_at', 'updated_at', 'like_count', 'comment_count')

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
