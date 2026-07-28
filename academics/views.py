from rest_framework.permissions import IsAuthenticated

from core.permissions import IsManager
from core.viewsets import TenantScopedModelViewSet

from .models import ClassLevel, ClassSubject, PassingCriteria, Section, Subject, TeacherSubjectAssignment
from .serializers import (
    ClassLevelSerializer,
    ClassSubjectSerializer,
    PassingCriteriaSerializer,
    SectionSerializer,
    SubjectSerializer,
    TeacherSubjectAssignmentSerializer,
)


class ClassLevelViewSet(TenantScopedModelViewSet):
    queryset = ClassLevel.objects.all()
    serializer_class = ClassLevelSerializer
    permission_classes = [IsAuthenticated, IsManager]


class SectionViewSet(TenantScopedModelViewSet):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    permission_classes = [IsAuthenticated, IsManager]


class SubjectViewSet(TenantScopedModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated, IsManager]


class ClassSubjectViewSet(TenantScopedModelViewSet):
    queryset = ClassSubject.objects.all()
    serializer_class = ClassSubjectSerializer
    permission_classes = [IsAuthenticated, IsManager]


class TeacherSubjectAssignmentViewSet(TenantScopedModelViewSet):
    queryset = TeacherSubjectAssignment.objects.all()
    serializer_class = TeacherSubjectAssignmentSerializer
    permission_classes = [IsAuthenticated, IsManager]


class PassingCriteriaViewSet(TenantScopedModelViewSet):
    queryset = PassingCriteria.objects.all()
    serializer_class = PassingCriteriaSerializer
    permission_classes = [IsAuthenticated, IsManager]
