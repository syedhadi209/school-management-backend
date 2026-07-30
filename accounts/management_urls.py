from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    ManagerAccountViewSet,
    ParentProfileViewSet,
    TeacherDashboardStatsView,
    TeacherProfileViewSet,
    UserRoleViewSet,
)

router = DefaultRouter()
router.register("roles", UserRoleViewSet, basename="roles")
router.register("managers", ManagerAccountViewSet, basename="managers")
router.register("teachers", TeacherProfileViewSet, basename="teachers")
router.register("parents", ParentProfileViewSet, basename="parents")

urlpatterns = [
    path("teacher-dashboard/", TeacherDashboardStatsView.as_view(), name="teacher-dashboard"),
    *router.urls,
]

