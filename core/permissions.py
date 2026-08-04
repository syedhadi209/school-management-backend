from rest_framework.permissions import BasePermission


class HasRole(BasePermission):
    required_roles: set[str] = set()

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        school = user.active_school
        if school is None:
            return False
        return user.school_roles.filter(school=school, role__in=self.required_roles).exists()


class IsSuperAdmin(HasRole):
    required_roles = {"super_admin"}


class IsSchoolAdmin(HasRole):
    required_roles = {"school_admin"}


class IsManager(HasRole):
    required_roles = {"manager", "school_admin"}


class IsTeacher(HasRole):
    required_roles = {"teacher", "school_admin", "manager"}


class IsParent(HasRole):
    required_roles = {"parent", "school_admin"}


class IsStudentStaff(HasRole):
    """School admins, managers, and teachers can access student records."""

    required_roles = {"school_admin", "manager", "teacher"}


class IsTimetableViewer(HasRole):
    """School staff, teachers, and parents can view timetable entries for their school."""

    required_roles = {"school_admin", "manager", "teacher", "parent"}


class IsAttendanceStaff(HasRole):
    """School admins, managers, and teachers can manage attendance sessions."""

    required_roles = {"school_admin", "manager", "teacher"}


class IsAttendanceViewer(HasRole):
    """Staff and parents can view attendance records scoped to their role."""

    required_roles = {"school_admin", "manager", "teacher", "parent"}


def get_active_role(user) -> str | None:
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return "super_admin"
    school = user.active_school
    if school is None:
        return None
    membership = user.school_roles.filter(school=school).first()
    return membership.role if membership else None


def is_school_admin_or_manager(user) -> bool:
    if user.is_superuser:
        return True
    role = get_active_role(user)
    return role in {"school_admin", "manager"}


def is_teacher_only(user) -> bool:
    if user.is_superuser:
        return False
    return get_active_role(user) == "teacher"

