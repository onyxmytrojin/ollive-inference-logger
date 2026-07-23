from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"ok": True})


urlpatterns = [
    path("health/", health),
    path("api/", include("chat.urls")),
    path("api/", include("ingestion.urls")),
]
