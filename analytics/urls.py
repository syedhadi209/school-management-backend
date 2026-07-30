from django.urls import path

from .views import SchoolDashboardStatsView

urlpatterns = [
    path("dashboard/", SchoolDashboardStatsView.as_view(), name="school-dashboard-stats"),
]
