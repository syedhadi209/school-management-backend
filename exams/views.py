from django.db.models import Prefetch, Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response

from academics.models import TeacherSubjectAssignment
from core.permissions import (
    IsExamStaff,
    IsExamViewer,
    IsManager,
    get_active_role,
    is_school_admin_or_manager,
)
from core.viewsets import TenantScopedModelViewSet
from students.models import ParentStudentLink, Student

from .models import Exam, ExamSchedule, ExamSheet, Mark, MarkSheet
from .serializers import (
    ExamScheduleSerializer,
    ExamSerializer,
    ExamSheetSerializer,
    MarkEnterSerializer,
    MarkRecordSerializer,
    MarkSheetListSerializer,
    MarkSheetSerializer,
)
from .services import draft_sheet, enter_marks, publish_exam, unpublish_exam


class ExamViewSet(TenantScopedModelViewSet):
    queryset = Exam.objects.select_related(
        "section__class_level",
        "subject",
        "academic_year",
        "created_by",
        "published_by",
    ).prefetch_related("mark_sheets")
    serializer_class = ExamSerializer
    filterset_fields = ["exam_type", "status", "section", "subject", "academic_year"]
    search_fields = ["name"]
    ordering_fields = ["starts_on", "name", "id", "created_at"]
    ordering = ["-starts_on", "-id"]

    def get_permissions(self):
        if self.action in {"publish", "unpublish"}:
            return [IsAuthenticated(), IsExamStaff()]
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated(), IsExamViewer()]
        return [IsAuthenticated(), IsExamStaff()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or is_school_admin_or_manager(user):
            return qs

        role = get_active_role(user)
        school = user.active_school
        if school is None:
            return qs.none()

        if role == "teacher":
            teacher = getattr(user, "teacher_profile", None)
            if teacher is None:
                return qs.none()
            pairs = list(
                TeacherSubjectAssignment.objects.filter(
                    teacher=teacher, school=school
                ).values_list("section_id", "subject_id")
            )
            assignment_q = Q(pk__in=[])
            for section_id, subject_id in pairs:
                assignment_q |= Q(section_id=section_id, subject_id=subject_id)
            return qs.filter(
                Q(created_by=user)
                | (Q(exam_type=Exam.TYPE_CLASS_TEST) & assignment_q)
                | Q(exam_type__in=[Exam.TYPE_MIDTERM, Exam.TYPE_FINAL])
                | Q(mark_sheets__teacher=teacher)
            ).distinct()

        if role == "parent":
            return qs.filter(status=Exam.STATUS_PUBLISHED)

        return qs.none()

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        exam = self.get_object()
        exam = publish_exam(user=request.user, exam=exam)
        return Response(ExamSerializer(exam, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        exam = self.get_object()
        exam = unpublish_exam(user=request.user, exam=exam)
        return Response(ExamSerializer(exam, context={"request": request}).data)


class MarkSheetViewSet(TenantScopedModelViewSet):
    queryset = MarkSheet.objects.select_related(
        "exam",
        "section__class_level",
        "subject",
        "teacher__user",
        "submitted_by",
        "academic_year",
    ).prefetch_related(Prefetch("marks", queryset=Mark.objects.select_related("student", "subject", "exam")))
    filterset_fields = ["exam", "section", "subject", "teacher", "status", "academic_year"]
    ordering_fields = ["updated_at", "submitted_at", "id"]
    ordering = ["-updated_at", "-id"]
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action in {"enter", "for_entry"}:
            return [IsAuthenticated(), IsExamStaff()]
        return [IsAuthenticated(), IsExamStaff()]

    def get_serializer_class(self):
        if self.action == "list":
            return MarkSheetListSerializer
        return MarkSheetSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or is_school_admin_or_manager(user):
            return qs
        role = get_active_role(user)
        if role == "teacher":
            teacher = getattr(user, "teacher_profile", None)
            if teacher is None:
                return qs.none()
            pairs = list(
                TeacherSubjectAssignment.objects.filter(teacher=teacher).values_list(
                    "section_id", "subject_id"
                )
            )
            if not pairs:
                return qs.filter(teacher=teacher)
            q = Q(teacher=teacher)
            for section_id, subject_id in pairs:
                q |= Q(section_id=section_id, subject_id=subject_id)
            return qs.filter(q).distinct()
        return qs.none()

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use POST /api/v1/mark-sheets/enter/ to submit marks."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=False, methods=["get"], url_path="for-entry")
    def for_entry(self, request):
        exam_id = request.query_params.get("exam")
        section_id = request.query_params.get("section")
        subject_id = request.query_params.get("subject")
        if not exam_id or not section_id or not subject_id:
            return Response(
                {"detail": "exam, section, and subject query params are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            payload = draft_sheet(
                user=request.user,
                school=request.user.active_school,
                exam_id=int(exam_id),
                section_id=int(section_id),
                subject_id=int(subject_id),
            )
        except (TypeError, ValueError):
            return Response({"detail": "Invalid exam, section, or subject."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)

    @action(detail=False, methods=["post"])
    def enter(self, request):
        serializer = MarkEnterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        sheet = enter_marks(
            user=request.user,
            school=request.user.active_school,
            exam_id=data["exam"],
            section_id=data["section"],
            subject_id=data["subject"],
            records=data["records"],
            max_marks=data.get("max_marks"),
            notes=data.get("notes") or "",
        )
        return Response(
            MarkSheetSerializer(sheet, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class MarkViewSet(TenantScopedModelViewSet):
    queryset = Mark.objects.select_related(
        "student", "subject", "exam", "teacher__user", "sheet"
    )
    serializer_class = MarkRecordSerializer
    filterset_fields = ["exam", "student", "subject", "teacher", "sheet"]
    ordering_fields = ["marked_at", "id", "marks_obtained"]
    ordering = ["-marked_at", "id"]
    http_method_names = ["get", "head", "options"]

    def get_permissions(self):
        return [IsAuthenticated(), IsExamViewer()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or is_school_admin_or_manager(user):
            return qs

        role = get_active_role(user)
        school = user.active_school
        if school is None:
            return qs.none()

        if role == "teacher":
            teacher = getattr(user, "teacher_profile", None)
            if teacher is None:
                return qs.none()
            return qs.filter(
                Q(teacher=teacher)
                | Q(
                    exam__mark_sheets__teacher=teacher,
                    subject_id__in=TeacherSubjectAssignment.objects.filter(teacher=teacher).values(
                        "subject_id"
                    ),
                )
            ).distinct()

        if role == "parent":
            parent = getattr(user, "parent_profile", None)
            if parent is None:
                return qs.none()
            child_ids = ParentStudentLink.objects.filter(
                parent=parent, school=school
            ).values_list("student_id", flat=True)
            return qs.filter(student_id__in=child_ids, exam__status=Exam.STATUS_PUBLISHED)

        return qs.none()


class ExamScheduleViewSet(TenantScopedModelViewSet):
    queryset = ExamSchedule.objects.select_related("exam", "subject", "section")
    serializer_class = ExamScheduleSerializer
    filterset_fields = ["exam", "subject", "section"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated(), IsExamViewer()]
        return [IsAuthenticated(), IsManager()]


class ExamSheetViewSet(TenantScopedModelViewSet):
    queryset = ExamSheet.objects.select_related("exam", "subject", "section")
    serializer_class = ExamSheetSerializer
    filterset_fields = ["exam", "subject", "section"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated(), IsExamViewer()]
        return [IsAuthenticated(), IsManager()]
