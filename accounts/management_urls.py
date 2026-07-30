from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import ParentProfileViewSet, TeacherDashboardStatsView, TeacherProfileViewSet, UserRoleViewSet

router = DefaultRouter()
router.register("roles", UserRoleViewSet, basename="roles")
router.register("teachers", TeacherProfileViewSet, basename="teachers")
router.register("parents", ParentProfileViewSet, basename="parents")

urlpatterns = [
    path("teacher-dashboard/", TeacherDashboardStatsView.as_view(), name="teacher-dashboard"),
    *router.urls,
]

