from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from api.views import (
    CreateUserView, NoteListCreate, NoteDelete,
    ShortsListView, ShortCreateView, ShortDetailView,
    toggle_like, add_comment, get_comments, track_view,
    user_shorts, user_profile, wallet_detail, wallet_transactions,
    verify_transaction, audit_log, wallet_integrity_report,
    track_watch_progress, get_video_analytics, get_user_watch_history, process_all_videos_audio, process_single_video_audio,
    get_audio_quality_report, list_videos, process_videos_traditional,
    # Comment Analysis endpoints (API only)
    analyze_comment, analyze_comments_for_short, batch_analyze_comments,
    get_comment_sentiment_summary, analyze_text_sentiment
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/user/register/", CreateUserView.as_view(), name="register"),
    path("api/token/", TokenObtainPairView.as_view(), name="get_token"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("api-auth/", include("rest_framework.urls")),
    
    # Notes endpoints (legacy)
    path("api/notes/", NoteListCreate.as_view(), name="note-list"),
    path("api/notes/delete/<int:pk>/", NoteDelete.as_view(), name="delete-note"),
    
    # Shorts endpoints
    path("api/shorts/", ShortsListView.as_view(), name="shorts-list"),
    path("api/shorts/create/", ShortCreateView.as_view(), name="shorts-create"),
    path("api/shorts/<uuid:pk>/", ShortDetailView.as_view(), name="shorts-detail"),
    path("api/shorts/<uuid:short_id>/like/", toggle_like, name="toggle-like"),
    path("api/shorts/<uuid:short_id>/comment/", add_comment, name="add-comment"),
    path("api/shorts/<uuid:short_id>/comments/", get_comments, name="get-comments"),
    path("api/shorts/<uuid:short_id>/view/", track_view, name="track-view"),
    path("api/shorts/<uuid:short_id>/watch-progress/", track_watch_progress, name="track-watch-progress"),
    path("api/shorts/<uuid:short_id>/analytics/", get_video_analytics, name="video-analytics"),
    path("api/my-shorts/", user_shorts, name="user-shorts"),
    path("api/profile/<str:username>/", user_profile, name="user-profile"),
    path("api/watch-history/", get_user_watch_history, name="user-watch-history"),
    
    # Wallet endpoints
    path("api/wallet/", wallet_detail, name="wallet-detail"),
    path("api/wallet/transactions/", wallet_transactions, name="wallet-transactions"),
    path("api/wallet/verify/<uuid:transaction_id>/", verify_transaction, name="verify-transaction"),
    path("api/wallet/audit/", audit_log, name="audit-log"),
    path("api/wallet/integrity/", wallet_integrity_report, name="wallet-integrity"),

    # Audio processing endpoints
    path('api/audio/process-all/', process_all_videos_audio, name='process_all_videos_audio'),
    path('api/audio/process-single/', process_single_video_audio, name='process_single_video_audio'),
    path('api/audio/quality-report/', get_audio_quality_report, name='audio_quality_report'),
    path('api/videos/list/', list_videos, name='list_videos'),

    # Comment Analysis endpoints
    path('api/admin/analyze-comment/<uuid:comment_id>/', analyze_comment, name='analyze_comment'),
    path('api/admin/reanalyze-comment/<uuid:comment_id>/', analyze_comment, {'force': True}, name='reanalyze_comment'),
    path('api/admin/analyze-comments/<uuid:short_id>/', analyze_comments_for_short, name='analyze_comments_for_short'),
    path('api/batch-analyze-comments/', batch_analyze_comments, name='batch_analyze_comments'),
    path('api/comment-sentiment-summary/<uuid:short_id>/', get_comment_sentiment_summary, name='comment_sentiment_summary'),
    path('api/analyze-text-sentiment/', analyze_text_sentiment, name='analyze_text_sentiment'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
