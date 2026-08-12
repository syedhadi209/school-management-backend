from rest_framework import serializers

from students.models import Student

from .models import Family


class FamilySerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()

    class Meta:
        model = Family
        fields = (
            "id",
            "school",
            "family_code",
            "primary_contact_email",
            "father_name",
            "mother_name",
            "address",
            "created_at",
            "updated_at",
            "member_count",
            "members",
        )
        read_only_fields = ("school", "family_code", "created_at", "updated_at")

    def get_member_count(self, obj: Family) -> int:
        return obj.students.count()

    def get_members(self, obj: Family):
        members = obj.students.select_related("section__class_level").order_by("first_name", "last_name", "id")
        return [
            {
                "id": student.id,
                "name": f"{student.first_name} {student.last_name}".strip(),
                "roll_number": student.roll_number,
                "section": student.section.name if student.section else "",
                "class_level": student.section.class_level.name if student.section else "",
                "status": student.status,
            }
            for student in members
        ]


class FamilyLookupSerializer(serializers.Serializer):
    code = serializers.CharField()

    def validate_code(self, value: str) -> str:
        return value.strip().upper()
