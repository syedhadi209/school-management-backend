from rest_framework.permissions import IsAuthenticated

from core.permissions import IsTeacher
from core.viewsets import TenantScopedModelViewSet

from .models import Exam, ExamSchedule, ExamSheet, Mark
from .serializers import ExamScheduleSerializer, ExamSerializer, ExamSheetSerializer, MarkSerializer


class ExamViewSet(TenantScopedModelViewSet):
    queryset = Exam.objects.all()
    serializer_class = ExamSerializer
    permission_classes = [IsAuthenticated, IsTeacher]


class ExamScheduleViewSet(TenantScopedModelViewSet):
    queryset = ExamSchedule.objects.all()
    serializer_class = ExamScheduleSerializer
    permission_classes = [IsAuthenticated, IsTeacher]


class ExamSheetViewSet(TenantScopedModelViewSet):
    queryset = ExamSheet.objects.all()
    serializer_class = ExamSheetSerializer
    permission_classes = [IsAuthenticated, IsTeacher]


class MarkViewSet(TenantScopedModelViewSet):
    queryset = Mark.objects.all()
    serializer_class = MarkSerializer
    permission_classes = [IsAuthenticated, IsTeacher]
