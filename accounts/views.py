from rest_framework import permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.permissions import IsSchoolAdmin
from core.viewsets import TenantScopedModelViewSet

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
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [IsAuthenticated, IsSchoolAdmin]


class TeacherProfileViewSet(TenantScopedModelViewSet):
    queryset = TeacherProfile.objects.all()
    serializer_class = TeacherProfileSerializer
    permission_classes = [IsAuthenticated, IsSchoolAdmin]


class ParentProfileViewSet(TenantScopedModelViewSet):
    queryset = ParentProfile.objects.all()
    serializer_class = ParentProfileSerializer
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
