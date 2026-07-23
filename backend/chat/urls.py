from django.urls import path

from .views import (
    ChatView,
    ConversationCancelView,
    ConversationDetailView,
    ConversationListView,
)

urlpatterns = [
    path("chat/", ChatView.as_view()),
    path("conversations/", ConversationListView.as_view()),
    path("conversations/<uuid:conversation_id>/", ConversationDetailView.as_view()),
    path("conversations/<uuid:conversation_id>/cancel/", ConversationCancelView.as_view()),
]
