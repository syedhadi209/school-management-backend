from rest_framework.routers import DefaultRouter

from .views import ExamScheduleViewSet, ExamSheetViewSet, ExamViewSet, MarkSheetViewSet, MarkViewSet

router = DefaultRouter()
router.register("exams", ExamViewSet, basename="exams")
router.register("exam-schedules", ExamScheduleViewSet, basename="exam-schedules")
router.register("exam-sheets", ExamSheetViewSet, basename="exam-sheets")
router.register("mark-sheets", MarkSheetViewSet, basename="mark-sheets")
router.register("marks", MarkViewSet, basename="marks")

urlpatterns = router.urls
