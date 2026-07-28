from rest_framework.permissions import IsAuthenticated

from core.permissions import IsSchoolAdmin
from core.viewsets import TenantScopedModelViewSet

from .models import ParentStudentLink, Student
from .serializers import ParentStudentLinkSerializer, StudentSerializer


class StudentViewSet(TenantScopedModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated, IsSchoolAdmin]


class ParentStudentLinkViewSet(TenantScopedModelViewSet):
    queryset = ParentStudentLink.objects.all()
    serializer_class = ParentStudentLinkSerializer
    permission_classes = [IsAuthenticated, IsSchoolAdmin]
