import json
import logging

from django.conf import settings
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, Message
from .serializers import (
    ChatRequestSerializer,
    ConversationDetailSerializer,
    ConversationListSerializer,
    ConversationRenameSerializer,
)
from .services.groq_client import complete_chat, generate_title, stream_chat

logger = logging.getLogger(__name__)

# Short conversational context: only the last N turns are replayed to the
# model, so cost/latency stay bounded no matter how long a conversation runs.
HISTORY_LIMIT = 20


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


def _generate_title_for(conversation, user_text, assistant_text):
    try:
        title = generate_title(
            user_text, assistant_text, settings.GROQ_MODEL, conversation_id=str(conversation.id)
        )
        if title:
            conversation.title = title[:200]
    except Exception:
        logger.warning("title generation failed, keeping fallback title", exc_info=True)


def _stream_assistant_reply(conversation, history, user_message_id, title_from=None):
    """
    Shared SSE generator for both fresh sends and regenerate: streams delta
    events as tokens arrive from Groq, then persists the assistant message and
    emits a final `done` event once the stream is exhausted. Client
    disconnect (e.g. the "stop" button aborting the fetch) surfaces as a
    write failure the next time this generator is iterated, which stops
    further generation — best-effort, not guaranteed instant cancellation.

    `title_from`, when given the triggering user message text, generates a
    real contextual title once the reply is complete (only relevant for a
    conversation's first turn — the extra Groq call happens after all delta
    events are already sent, so it doesn't delay perceived streaming).
    """
    yield _sse(
        {
            "type": "start",
            "conversation_id": str(conversation.id),
            "message_id": str(user_message_id),
        }
    )
    chunks = []
    try:
        for chunk in stream_chat(
            messages=history,
            model=settings.GROQ_MODEL,
            conversation_id=str(conversation.id),
            message_id=str(user_message_id),
        ):
            delta = chunk.get("delta")
            if delta:
                chunks.append(delta)
                yield _sse({"type": "delta", "content": delta})
    except Exception:
        logger.exception("streaming inference failed")
        yield _sse({"type": "error", "error": "inference_failed"})
        return

    output_text = "".join(chunks)
    assistant_message = Message.objects.create(
        conversation=conversation, role=Message.Role.ASSISTANT, content=output_text
    )

    if title_from is not None:
        _generate_title_for(conversation, title_from, output_text)
    conversation.save(update_fields=["updated_at", "title"])

    yield _sse(
        {
            "type": "done",
            "conversation_title": conversation.title,
            "message": {
                "id": str(assistant_message.id),
                "role": assistant_message.role,
                "content": assistant_message.content,
                "created_at": assistant_message.created_at,
            },
        }
    )


class ChatView(APIView):
    """Non-streaming chat endpoint. Kept alongside ChatStreamView as a plain
    request/response fallback (e.g. for clients that can't consume SSE)."""

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message_text = serializer.validated_data["message"]
        conversation_id = serializer.validated_data.get("conversation_id")
        is_new_conversation = conversation_id is None

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

        if is_new_conversation:
            _generate_title_for(conversation, message_text, result["output"])
        conversation.save(update_fields=["updated_at", "title"])

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


class ChatStreamView(APIView):
    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message_text = serializer.validated_data["message"]
        conversation_id = serializer.validated_data.get("conversation_id")
        is_new_conversation = conversation_id is None

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

        response = StreamingHttpResponse(
            _stream_assistant_reply(
                conversation,
                history,
                user_message.id,
                title_from=message_text if is_new_conversation else None,
            ),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


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


class ConversationRenameView(APIView):
    def post(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, id=conversation_id)
        serializer = ConversationRenameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation.title = serializer.validated_data["title"]
        conversation.save(update_fields=["title", "updated_at"])
        return Response(ConversationListSerializer(conversation).data)


class ConversationRegenerateView(APIView):
    """Drops the conversation's last assistant reply (if any) and re-streams
    a fresh completion for the same trailing user message."""

    def post(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, id=conversation_id)
        if conversation.status == Conversation.Status.CANCELLED:
            return Response(
                {"error": "conversation_cancelled"}, status=http_status.HTTP_409_CONFLICT
            )

        messages = list(conversation.messages.order_by("created_at"))
        if not messages:
            return Response({"error": "no_messages_to_regenerate"}, status=http_status.HTTP_400_BAD_REQUEST)

        if messages[-1].role == Message.Role.ASSISTANT:
            messages[-1].delete()
            messages = messages[:-1]

        if not messages or messages[-1].role != Message.Role.USER:
            return Response({"error": "no_messages_to_regenerate"}, status=http_status.HTTP_400_BAD_REQUEST)

        history = [{"role": m.role, "content": m.content} for m in messages[-HISTORY_LIMIT:]]

        response = StreamingHttpResponse(
            _stream_assistant_reply(conversation, history, messages[-1].id),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
