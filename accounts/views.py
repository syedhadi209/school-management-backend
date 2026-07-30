from rest_framework import permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.db.models import Q

from academics.models import Section
from core.permissions import IsSchoolAdmin, IsTeacher
from core.viewsets import TenantScopedModelViewSet
from students.models import Student

from .models import ParentProfile, TeacherProfile, UserRole
from .serializers import (
    AppTokenObtainPairSerializer,
    ParentProfileSerializer,
    SchoolOwnerRegisterSerializer,
    TeacherProfileSerializer,
    UserRoleSerializer,
)


class RegisterSchoolOwnerView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SchoolOwnerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "message": "School owner registered successfully",
                "user_id": user.id,
                "email": user.email,
                "school_id": user.active_school_id,
            },
            status=status.HTTP_201_CREATED,
        )


class AppTokenObtainPairView(TokenObtainPairView):
    serializer_class = AppTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        refresh = response.data.get("refresh")
        if refresh:
            response.set_cookie(
                key="refresh_token",
                value=refresh,
                httponly=True,
                samesite="Lax",
                secure=False,
            )
        return response


class CookieTokenRefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.data.copy()
        if not payload.get("refresh"):
            payload["refresh"] = request.COOKIES.get("refresh_token")
        request._full_data = payload
        return super().post(request, *args, **kwargs)


class LogoutView(APIView):
    def post(self, request):
        response = Response({"message": "Logged out"}, status=status.HTTP_200_OK)
        response.delete_cookie("refresh_token")
        return response


class UserRoleViewSet(TenantScopedModelViewSet):
    queryset = UserRole.objects.select_related("user", "school").all()
    serializer_class = UserRoleSerializer
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
    search_fields = ["user__email", "role"]
    filterset_fields = ["role", "user"]


class TeacherProfileViewSet(TenantScopedModelViewSet):
    queryset = TeacherProfile.objects.select_related("user").prefetch_related("subjects_taught").all()
    serializer_class = TeacherProfileSerializer
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__email",
        "qualification",
        "employee_id",
        "phone_number",
        "cnic",
        "designation",
        "subjects_taught__name",
    ]
    filterset_fields = ["joining_date", "subjects_taught", "designation"]
    ordering_fields = ["joining_date", "user__first_name", "monthly_salary", "shift_start_time"]
    ordering = ["user__first_name"]


class TeacherDashboardStatsView(APIView):
    permission_classes = [IsAuthenticated, IsTeacher]

    def get(self, request):
        teacher = getattr(request.user, "teacher_profile", None)
        school = request.user.active_school
        if teacher is None or school is None:
            return Response(
                {
                    "assigned_sections": 0,
                    "students": 0,
                    "subjects": 0,
                    "incharge_sections": 0,
                }
            )

        assigned_sections = Section.objects.filter(school=school).filter(
            Q(teachers=teacher) | Q(class_teacher=teacher)
        ).distinct()
        students = Student.objects.filter(
            school=school,
            section__in=assigned_sections,
        ).distinct()

        return Response(
            {
                "assigned_sections": assigned_sections.count(),
                "students": students.count(),
                "subjects": teacher.subjects_taught.count(),
                "incharge_sections": assigned_sections.filter(class_teacher=teacher).count(),
            }
        )


class ParentProfileViewSet(TenantScopedModelViewSet):
    queryset = ParentProfile.objects.select_related("user").all()
    serializer_class = ParentProfileSerializer
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
    search_fields = ["user__first_name", "user__last_name", "user__email"]
    ordering_fields = ["user__first_name"]
    ordering = ["user__first_name"]
