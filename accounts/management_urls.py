from rest_framework.routers import DefaultRouter

from .views import ParentProfileViewSet, TeacherProfileViewSet, UserRoleViewSet

router = DefaultRouter()
router.register("roles", UserRoleViewSet, basename="roles")
router.register("teachers", TeacherProfileViewSet, basename="teachers")
router.register("parents", ParentProfileViewSet, basename="parents")

urlpatterns = router.urls

