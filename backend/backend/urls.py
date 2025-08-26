from django.contrib import admin
from django.urls import path, include
from api.views import CreateUserView, StreamListCreate, StreamEnd, GiftListCreate
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/user/register/", CreateUserView.as_view(), name="register"),
    path("api/token/", TokenObtainPairView.as_view(), name="get_token"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("api/streams/", StreamListCreate.as_view(), name="streams"),
    path("api/streams/end/<int:pk>/", StreamEnd.as_view(), name="stream_end"),
    path("api/gifts/", GiftListCreate.as_view(), name="gift_list_create"),
    path("api-auth/", include("rest_framework.urls")),
    path("api/", include("api.urls")),
]