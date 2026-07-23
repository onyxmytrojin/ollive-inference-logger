from django.urls import path

from .views import IngestLogView

urlpatterns = [
    path("ingest/", IngestLogView.as_view()),
]
