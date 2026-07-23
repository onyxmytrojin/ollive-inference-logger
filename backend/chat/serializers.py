from rest_framework import serializers

from .models import Conversation, ConversationGroup, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ["id", "role", "content", "created_at"]


class ConversationGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversationGroup
        fields = ["id", "name", "created_at"]


class ConversationListSerializer(serializers.ModelSerializer):
    group_id = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "title", "status", "group_id", "created_at", "updated_at"]

    def get_group_id(self, obj):
        return obj.group_id


class ConversationDetailSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    group_id = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "title", "status", "group_id", "created_at", "updated_at", "messages"]

    def get_group_id(self, obj):
        return obj.group_id


class ChatRequestSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=False)
    message = serializers.CharField(min_length=1, max_length=8000)


class ConversationRenameSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=1, max_length=200)


class ConversationGroupAssignSerializer(serializers.Serializer):
    group_id = serializers.UUIDField(required=False, allow_null=True)


class GroupCreateSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=1, max_length=100)
