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

