from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Count

from core.permissions import IsManager, IsTeacher, get_active_role, is_school_admin_or_manager
from core.viewsets import TenantScopedModelViewSet
from schools.services import get_or_create_default_academic_year

from .models import ClassLevel, ClassSubject, PassingCriteria, Section, Subject, TeacherSubjectAssignment
from .serializers import (
    ClassLevelSerializer,
    ClassSubjectSerializer,
    PassingCriteriaSerializer,
    SectionSerializer,
    SubjectSerializer,
    TeacherSubjectAssignmentSerializer,
)
from .services import get_or_create_default_section


class ClassLevelViewSet(TenantScopedModelViewSet):
    queryset = ClassLevel.objects.select_related("academic_year").annotate(section_count=Count("sections")).all()
    serializer_class = ClassLevelSerializer
    permission_classes = [IsAuthenticated, IsManager]
    search_fields = ["name", "academic_year__name"]
    filterset_fields = ["academic_year", "is_board_class"]
    ordering_fields = ["name", "order", "academic_year__name"]
    ordering = ["order", "name"]

    def perform_create(self, serializer):
        school = self.request.user.active_school
        academic_year = serializer.validated_data.get("academic_year")
        if academic_year is None:
            academic_year = get_or_create_default_academic_year(school)
        with transaction.atomic():
            class_level = serializer.save(school=school, academic_year=academic_year)
            get_or_create_default_section(class_level)


class SectionViewSet(TenantScopedModelViewSet):
    queryset = (
        Section.objects.select_related("class_level", "class_teacher__user")
        .prefetch_related("teachers__user")
        .annotate(student_count=Count("students", distinct=True))
        .all()
    )
    serializer_class = SectionSerializer
    permission_classes = [IsAuthenticated, IsManager]
    search_fields = [
        "name",
        "class_level__name",
        "class_teacher__user__first_name",
        "class_teacher__user__last_name",
        "teachers__user__first_name",
        "teachers__user__last_name",
    ]
    filterset_fields = ["class_level", "shift", "class_teacher", "teachers"]
    ordering_fields = ["name", "capacity", "shift"]
    ordering = ["class_level__name", "name"]


class SubjectViewSet(TenantScopedModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated, IsManager]
    search_fields = ["name"]
    ordering_fields = ["name"]
    ordering = ["name"]


class ClassSubjectViewSet(TenantScopedModelViewSet):
    queryset = ClassSubject.objects.select_related("class_level", "subject").all()
    serializer_class = ClassSubjectSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filterset_fields = ["class_level", "subject"]
    ordering_fields = ["class_level__name", "subject__name"]


class TeacherSubjectAssignmentViewSet(TenantScopedModelViewSet):
    queryset = TeacherSubjectAssignment.objects.select_related(
        "teacher__user", "subject", "section__class_level", "academic_year"
    ).all()
    serializer_class = TeacherSubjectAssignmentSerializer
    search_fields = ["teacher__user__first_name", "teacher__user__last_name", "subject__name", "section__name"]
    filterset_fields = ["teacher", "subject", "section", "academic_year"]

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated(), IsTeacher()]
        return [IsAuthenticated(), IsManager()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or is_school_admin_or_manager(user):
            return qs
        if get_active_role(user) == "teacher":
            teacher = getattr(user, "teacher_profile", None)
            if teacher is None:
                return qs.none()
            return qs.filter(teacher=teacher)
        return qs.none()


class PassingCriteriaViewSet(TenantScopedModelViewSet):
    queryset = PassingCriteria.objects.select_related("class_level", "academic_year").all()
    serializer_class = PassingCriteriaSerializer
    permission_classes = [IsAuthenticated, IsManager]
    filterset_fields = ["class_level", "academic_year"]
