from rest_framework.routers import DefaultRouter

from .views import (
    ClassLevelViewSet,
    ClassSubjectViewSet,
    PassingCriteriaViewSet,
    SectionViewSet,
    SubjectViewSet,
    TeacherSubjectAssignmentViewSet,
)

router = DefaultRouter()
router.register("class-levels", ClassLevelViewSet, basename="class-levels")
router.register("sections", SectionViewSet, basename="sections")
router.register("subjects", SubjectViewSet, basename="subjects")
router.register("class-subjects", ClassSubjectViewSet, basename="class-subjects")
router.register("teacher-assignments", TeacherSubjectAssignmentViewSet, basename="teacher-assignments")
router.register("passing-criteria", PassingCriteriaViewSet, basename="passing-criteria")

urlpatterns = router.urls

