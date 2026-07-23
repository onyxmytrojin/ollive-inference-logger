import logging

from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import metrics
from .clickhouse_client import get_client
from .kafka_producer import publish_inference_log
from .serializers import InferenceLogSerializer

logger = logging.getLogger(__name__)

_MESSAGE_INFERENCE_COLUMNS = [
    "provider",
    "model",
    "status",
    "error_message",
    "latency_ms",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "request_started_at",
    "request_completed_at",
    "metadata",
]


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


class MessageInferenceView(APIView):
    """Backs the frontend's per-message "inspect" panel: the actual
    latency/tokens/model/status recorded for the inference call that produced
    a given assistant message."""

    def get(self, request, message_id):
        # message_id is a uuid.UUID (validated by the <uuid:...> URL
        # converter before this view runs), so interpolating it is safe.
        query = f"""
            SELECT {", ".join(_MESSAGE_INFERENCE_COLUMNS)}
            FROM inference_logs
            WHERE message_id = '{message_id}'
            ORDER BY created_at DESC
            LIMIT 1
        """
        rows = get_client().query(query).result_rows
        if not rows:
            return Response({"error": "not_found"}, status=http_status.HTTP_404_NOT_FOUND)
        return Response(dict(zip(_MESSAGE_INFERENCE_COLUMNS, rows[0])))


class MetricsSummaryView(APIView):
    def get(self, request):
        window = request.query_params.get("window", metrics.DEFAULT_WINDOW)
        if window not in metrics.WINDOW_SECONDS:
            return Response(
                {"error": "invalid_window", "allowed": list(metrics.WINDOW_SECONDS)},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        return Response(metrics.get_summary(window))


class MetricsTimeseriesView(APIView):
    def get(self, request):
        window = request.query_params.get("window", metrics.DEFAULT_WINDOW)
        if window not in metrics.WINDOW_SECONDS:
            return Response(
                {"error": "invalid_window", "allowed": list(metrics.WINDOW_SECONDS)},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        return Response(metrics.get_timeseries(window))
