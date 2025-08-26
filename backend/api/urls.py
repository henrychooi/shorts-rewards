from django.urls import path
from . import views

urlpatterns = [
    path("notes/", views.NoteListCreate.as_view(), name = "note-list"),
    path("notes/delete/<int:pk>/", views.NoteDelete.as_view(), name="delete-note"),
    path("streams/", views.StreamListCreate.as_view(), name="stream-list"),
    path("streams/<int:pk>/start/", views.StreamStart.as_view(), name="stream-start"),
    path("streams/<int:pk>/end/", views.StreamEnd.as_view(), name="stream-end"),
    path("gifts/", views.GiftListCreate.as_view(), name="gift-list"),
]