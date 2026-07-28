from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from core.permissions import IsSchoolAdmin

from .models import AcademicYear, School
from .serializers import AcademicYearSerializer, SchoolSerializer


class SchoolViewSet(ModelViewSet):
    serializer_class = SchoolSerializer
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
    queryset = School.objects.all()

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return super().get_queryset()
        return super().get_queryset().filter(id=user.active_school_id)


class AcademicYearViewSet(ModelViewSet):
    serializer_class = AcademicYearSerializer
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
    queryset = AcademicYear.objects.all()

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return super().get_queryset()
        return super().get_queryset().filter(school_id=user.active_school_id)
