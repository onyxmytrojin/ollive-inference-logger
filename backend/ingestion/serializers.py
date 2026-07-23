from rest_framework import serializers


class InferenceLogSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField(required=False, allow_null=True)
    message_id = serializers.UUIDField(required=False, allow_null=True)
    provider = serializers.CharField(max_length=100)
    model = serializers.CharField(max_length=200)
    status = serializers.ChoiceField(choices=["success", "error"])
    error_message = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    latency_ms = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    prompt_tokens = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    completion_tokens = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    total_tokens = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    input_preview = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    output_preview = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    request_started_at = serializers.DateTimeField()
    request_completed_at = serializers.DateTimeField()
    metadata = serializers.JSONField(required=False, allow_null=True)
