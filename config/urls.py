from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/accounts/", include("accounts.management_urls")),
    path("api/v1/", include("schools.urls")),
    path("api/v1/", include("academics.urls")),
    path("api/v1/", include("students.urls")),
    path("api/v1/", include("exams.urls")),
    path("api/v1/", include("fees.urls")),
    path("api/v1/", include("admissions.urls")),
    path("api/v1/", include("timetable.urls")),
    path("api/v1/", include("promotions.urls")),
    path("api/v1/", include("notifications.urls")),
    path("api/v1/", include("billing.urls")),
    path("api/v1/analytics/", include("analytics.urls")),
]
