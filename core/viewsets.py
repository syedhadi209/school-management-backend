from rest_framework.viewsets import ModelViewSet


class TenantScopedModelViewSet(ModelViewSet):
    school_field = "school"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return queryset
        school = user.active_school
        if school is None:
            return queryset.none()
        return queryset.filter(**{self.school_field: school})

    def perform_create(self, serializer):
        user = self.request.user
        if "school" in serializer.fields and not serializer.validated_data.get("school"):
            serializer.save(school=user.active_school)
            return
        serializer.save()

