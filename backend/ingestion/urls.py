from django.urls import path

from .views import (
    IngestLogView,
    MessageInferenceView,
    MetricsSummaryView,
    MetricsTimeseriesView,
)

urlpatterns = [
    path("ingest/", IngestLogView.as_view()),
    path("messages/<uuid:message_id>/inference/", MessageInferenceView.as_view()),
    path("metrics/summary/", MetricsSummaryView.as_view()),
    path("metrics/timeseries/", MetricsTimeseriesView.as_view()),
]
