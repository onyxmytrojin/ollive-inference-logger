from django.urls import path

from .views import (
    ChatStreamView,
    ChatView,
    ConversationCancelView,
    ConversationDetailView,
    ConversationGroupAssignView,
    ConversationListView,
    ConversationRegenerateView,
    ConversationRenameView,
    GroupDeleteView,
    GroupListCreateView,
)

urlpatterns = [
    path("chat/", ChatView.as_view()),
    path("chat/stream/", ChatStreamView.as_view()),
    path("conversations/", ConversationListView.as_view()),
    path("conversations/<uuid:conversation_id>/", ConversationDetailView.as_view()),
    path("conversations/<uuid:conversation_id>/cancel/", ConversationCancelView.as_view()),
    path("conversations/<uuid:conversation_id>/rename/", ConversationRenameView.as_view()),
    path("conversations/<uuid:conversation_id>/group/", ConversationGroupAssignView.as_view()),
    path(
        "conversations/<uuid:conversation_id>/regenerate/",
        ConversationRegenerateView.as_view(),
    ),
    path("groups/", GroupListCreateView.as_view()),
    path("groups/<uuid:group_id>/", GroupDeleteView.as_view()),
]
