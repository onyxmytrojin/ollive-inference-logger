import logging

from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework.views import APIView

from .kafka_producer import publish_inference_log
from .serializers import InferenceLogSerializer

logger = logging.getLogger(__name__)


class IngestLogView(APIView):
    """
    Ingestion endpoint: the SDK POSTs raw inference metadata here. This view's
    only job is to validate/parse the payload and publish it onto the
    `inference-logs` Kafka topic — actual persistence happens asynchronously
    in the consumer (see management/commands/consume_inference_logs.py), so a
    slow/unavailable ClickHouse can never block the chat request path or the
    SDK's fire-and-forget call.
    """

    def post(self, request):
        serializer = InferenceLogSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "invalid_payload", "details": serializer.errors},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            publish_inference_log(serializer.validated_data)
        except Exception:
            logger.exception("failed to publish inference log to Kafka")
            return Response(
                {"error": "internal_error"}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(status=http_status.HTTP_202_ACCEPTED)
