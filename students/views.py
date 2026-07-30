from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from core.permissions import IsStudentStaff, is_school_admin_or_manager, is_teacher_only
from core.viewsets import TenantScopedModelViewSet

from .models import ParentStudentLink, Student
from .serializers import ParentStudentLinkSerializer, StudentSerializer


TEACHER_EDITABLE_FIELDS = {"board_roll_number"}


class StudentViewSet(TenantScopedModelViewSet):
    queryset = Student.objects.select_related("section", "section__class_level").all()
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated, IsStudentStaff]
    search_fields = ["first_name", "last_name", "roll_number", "board_roll_number", "region"]
    filterset_fields = ["status", "section", "gender", "section__class_level__is_board_class"]
    ordering_fields = ["first_name", "admission_date", "roll_number", "board_roll_number"]
    ordering = ["first_name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if is_school_admin_or_manager(user):
            return queryset
        if is_teacher_only(user):
            teacher_profile = getattr(user, "teacher_profile", None)
            if teacher_profile is None:
                return queryset.none()
            return queryset.filter(section__class_teacher=teacher_profile)
        return queryset.none()

    def create(self, request, *args, **kwargs):
        if is_teacher_only(request.user):
            raise PermissionDenied("Teachers cannot create students.")
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if is_teacher_only(request.user):
            raise PermissionDenied("Teachers cannot delete students.")
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if is_teacher_only(request.user):
            disallowed = set(request.data.keys()) - TEACHER_EDITABLE_FIELDS
            if disallowed:
                raise PermissionDenied(
                    "Teachers can only update the board roll number for students in their assigned sections."
                )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if is_teacher_only(request.user):
            disallowed = set(request.data.keys()) - TEACHER_EDITABLE_FIELDS
            if disallowed:
                raise PermissionDenied(
                    "Teachers can only update the board roll number for students in their assigned sections."
                )
        return super().partial_update(request, *args, **kwargs)


class ParentStudentLinkViewSet(TenantScopedModelViewSet):
    queryset = ParentStudentLink.objects.select_related("parent__user", "student").all()
    serializer_class = ParentStudentLinkSerializer
    permission_classes = [IsAuthenticated, IsStudentStaff]
    search_fields = ["parent__user__first_name", "parent__user__last_name", "student__first_name", "student__last_name"]
    filterset_fields = ["parent", "student", "relation"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if is_school_admin_or_manager(user):
            return queryset
        return queryset.none()

    def create(self, request, *args, **kwargs):
        if is_teacher_only(request.user):
            raise PermissionDenied("Teachers cannot manage parent links.")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if is_teacher_only(request.user):
            raise PermissionDenied("Teachers cannot manage parent links.")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if is_teacher_only(request.user):
            raise PermissionDenied("Teachers cannot manage parent links.")
        return super().destroy(request, *args, **kwargs)
