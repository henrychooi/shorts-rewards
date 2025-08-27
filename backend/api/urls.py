from django.urls import path
from . import views

urlpatterns = [
    path("notes/", views.NoteListCreate.as_view(), name="note-list"),
    path("notes/delete/<int:pk>/", views.NoteDelete.as_view(), name="delete-note"),
    path("streams/", views.StreamListCreate.as_view(), name="stream-list"),
    path("streams/<int:pk>/start/", views.StreamStart.as_view(), name="stream-start"),
    path("streams/<int:stream_id>/end/", views.end_stream, name="stream-end"),
    path("streams/<int:stream_id>/offer/", views.stream_offer, name="stream-offer"),
    path("streams/<int:stream_id>/answer/", views.stream_answer, name="stream-answer"),
    path("gifts/", views.GiftListCreate.as_view(), name="gift-list"),
    path("stream/token/", views.create_stream_token, name="stream-token"),  
]
