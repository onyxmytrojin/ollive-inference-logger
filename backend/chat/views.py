from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, Message
from .serializers import (
    ChatRequestSerializer,
    ConversationDetailSerializer,
    ConversationListSerializer,
)
from .services.groq_client import complete_chat

# Short conversational context: only the last N turns are replayed to the
# model, so cost/latency stay bounded no matter how long a conversation runs.
HISTORY_LIMIT = 20


class ChatView(APIView):
    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message_text = serializer.validated_data["message"]
        conversation_id = serializer.validated_data.get("conversation_id")

        if conversation_id:
            conversation = get_object_or_404(Conversation, id=conversation_id)
            if conversation.status == Conversation.Status.CANCELLED:
                return Response(
                    {"error": "conversation_cancelled"}, status=http_status.HTTP_409_CONFLICT
                )
        else:
            conversation = Conversation.objects.create(title=message_text[:60])

        prior_messages = list(conversation.messages.order_by("created_at")[:HISTORY_LIMIT])
        user_message = Message.objects.create(
            conversation=conversation, role=Message.Role.USER, content=message_text
        )

        history = [{"role": m.role, "content": m.content} for m in prior_messages]
        history.append({"role": "user", "content": message_text})

        try:
            result = complete_chat(
                messages=history,
                model=settings.GROQ_MODEL,
                conversation_id=str(conversation.id),
                message_id=str(user_message.id),
            )
        except Exception:
            return Response(
                {"error": "inference_failed", "conversation_id": str(conversation.id)},
                status=http_status.HTTP_502_BAD_GATEWAY,
            )

        assistant_message = Message.objects.create(
            conversation=conversation, role=Message.Role.ASSISTANT, content=result["output"]
        )
        conversation.save(update_fields=["updated_at"])

        return Response(
            {
                "conversation_id": str(conversation.id),
                "message": {
                    "id": str(assistant_message.id),
                    "role": assistant_message.role,
                    "content": assistant_message.content,
                    "created_at": assistant_message.created_at,
                },
            }
        )


class ConversationListView(APIView):
    def get(self, request):
        conversations = Conversation.objects.all()
        return Response(ConversationListSerializer(conversations, many=True).data)


class ConversationDetailView(APIView):
    def get(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, id=conversation_id)
        return Response(ConversationDetailSerializer(conversation).data)


class ConversationCancelView(APIView):
    def post(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, id=conversation_id)
        conversation.status = Conversation.Status.CANCELLED
        conversation.save(update_fields=["status", "updated_at"])
        return Response(ConversationListSerializer(conversation).data)
