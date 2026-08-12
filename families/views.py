from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsManager
from core.viewsets import TenantScopedModelViewSet

from .models import Family
from .serializers import FamilyLookupSerializer, FamilySerializer


class FamilyViewSet(TenantScopedModelViewSet):
    queryset = Family.objects.all()
    serializer_class = FamilySerializer
    permission_classes = [IsAuthenticated, IsManager]
    search_fields = ["family_code", "primary_contact_email", "father_name", "mother_name", "students__first_name", "students__last_name"]
    filterset_fields = ["family_code"]
    ordering_fields = ["family_code", "id", "created_at"]
    ordering = ["family_code", "id"]

    @action(detail=False, methods=["get"], url_path="by-code")
    def by_code(self, request):
        serializer = FamilyLookupSerializer(data={"code": request.query_params.get("code", "")})
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data["code"]
        family = self.get_queryset().filter(family_code=code).first()
        if family is None:
            return Response({"detail": "Family not found."}, status=404)
        return Response(self.get_serializer(family).data)
