from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from api.views import (
    CreateUserView, NoteListCreate, NoteDelete,
    ShortsListView, ShortCreateView, ShortDetailView,
    toggle_like, add_comment, get_comments, track_view,
    user_shorts, user_profile
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
    path("api/my-shorts/", user_shorts, name="user-shorts"),
    path("api/profile/<str:username>/", user_profile, name="user-profile"),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)