from rest_framework import serializers

from academics.models import ClassLevel, Section, Subject
from accounts.models import TeacherProfile
from schools.services import get_or_create_default_academic_year

from .models import TimetableEntry
from .services import DAY_LABELS, describe_entry, overlapping_entries, section_label


class TimetableEntrySerializer(serializers.ModelSerializer):
    section_label = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.name", read_only=True, default="")
    teacher_name = serializers.SerializerMethodField()
    day_label = serializers.SerializerMethodField()
    class_level_name = serializers.CharField(source="section.class_level.name", read_only=True, default="")
    class_level = serializers.IntegerField(source="section.class_level_id", read_only=True)

    class Meta:
        model = TimetableEntry
        fields = "__all__"
        read_only_fields = ("school",)
        extra_kwargs = {
            "academic_year": {"required": False},
            "subject": {"required": False, "allow_null": True},
            "teacher": {"required": False, "allow_null": True},
            "label": {"required": False, "allow_blank": True},
        }

    def get_section_label(self, obj: TimetableEntry) -> str:
        return section_label(obj.section)

    def get_teacher_name(self, obj: TimetableEntry) -> str:
        if obj.teacher_id is None:
            return ""
        name = f"{obj.teacher.user.first_name} {obj.teacher.user.last_name}".strip()
        return name or obj.teacher.user.email

    def get_day_label(self, obj: TimetableEntry) -> str:
        return DAY_LABELS.get(obj.day_of_week, str(obj.day_of_week))

    def _active_school(self):
        request = self.context.get("request")
        return getattr(getattr(request, "user", None), "active_school", None)

    def validate_section(self, section: Section) -> Section:
        school = self._active_school()
        if school is not None and section.school_id != school.id:
            raise serializers.ValidationError("Section must belong to your active school.")
        return section

    def validate_subject(self, subject: Subject | None) -> Subject | None:
        if subject is None:
            return None
        school = self._active_school()
        if school is not None and subject.school_id != school.id:
            raise serializers.ValidationError("Subject must belong to your active school.")
        return subject

    def validate_teacher(self, teacher: TeacherProfile | None) -> TeacherProfile | None:
        if teacher is None:
            return None
        school = self._active_school()
        if school is not None and teacher.school_id != school.id:
            raise serializers.ValidationError("Teacher must belong to your active school.")
        return teacher

    def validate_academic_year(self, academic_year):
        school = self._active_school()
        if school is not None and academic_year.school_id != school.id:
            raise serializers.ValidationError("Academic year must belong to your active school.")
        return academic_year

    def validate(self, attrs):
        instance = self.instance
        school = self._active_school()
        if school is None and instance is not None:
            school = instance.school

        slot_type = attrs.get("slot_type", getattr(instance, "slot_type", TimetableEntry.SLOT_LECTURE))
        section = attrs.get("section", getattr(instance, "section", None))
        subject = attrs.get("subject", getattr(instance, "subject", None))
        teacher = attrs.get("teacher", getattr(instance, "teacher", None))
        label = attrs.get("label", getattr(instance, "label", "") if instance else "")
        day_of_week = attrs.get("day_of_week", getattr(instance, "day_of_week", None))
        start_time = attrs.get("start_time", getattr(instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(instance, "end_time", None))
        academic_year = attrs.get("academic_year", getattr(instance, "academic_year", None))

        if academic_year is None and school is not None:
            academic_year = get_or_create_default_academic_year(school)
            attrs["academic_year"] = academic_year

        if start_time is not None and end_time is not None and start_time >= end_time:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})

        if slot_type == TimetableEntry.SLOT_LECTURE:
            errors = {}
            if subject is None:
                errors["subject"] = "Subject is required for lectures."
            if teacher is None:
                errors["teacher"] = "Teacher is required for lectures."
            if errors:
                raise serializers.ValidationError(errors)
            attrs["label"] = ""
            if section is not None and teacher is not None:
                if not section.teachers.filter(pk=teacher.pk).exists():
                    raise serializers.ValidationError(
                        {
                            "teacher": (
                                "This teacher is not assigned to the selected section. "
                                "Add them on the Sections page first."
                            )
                        }
                    )
        elif slot_type == TimetableEntry.SLOT_BREAK:
            if not (label or "").strip():
                raise serializers.ValidationError({"label": "Break label is required (e.g. Recess, Lunch)."})
            if subject is not None:
                raise serializers.ValidationError({"subject": "Breaks cannot have a subject."})
            if teacher is not None:
                raise serializers.ValidationError({"teacher": "Breaks cannot have a teacher."})
            attrs["subject"] = None
            attrs["teacher"] = None
            attrs["label"] = label.strip()
            teacher = None

        if (
            school is not None
            and academic_year is not None
            and section is not None
            and day_of_week is not None
            and start_time is not None
            and end_time is not None
        ):
            clashes = overlapping_entries(
                school=school,
                academic_year=academic_year,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                section=section,
                teacher=teacher,
                exclude_id=instance.pk if instance else None,
            )
            if clashes:
                raise serializers.ValidationError({"non_field_errors": [describe_entry(clashes[0])]})

        return attrs


class BulkBreakSerializer(serializers.Serializer):
    day_of_week = serializers.ChoiceField(choices=TimetableEntry.DAY_CHOICES)
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    label = serializers.CharField(max_length=60)
    academic_year = serializers.IntegerField(required=False)
    section_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )
    class_level_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )

    def validate(self, attrs):
        if attrs["start_time"] >= attrs["end_time"]:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})
        section_ids = attrs.get("section_ids") or []
        class_level_ids = attrs.get("class_level_ids") or []
        if not section_ids and not class_level_ids:
            raise serializers.ValidationError(
                {"section_ids": "Provide section_ids and/or class_level_ids."}
            )
        attrs["label"] = attrs["label"].strip()
        if not attrs["label"]:
            raise serializers.ValidationError({"label": "Break label is required."})
        return attrs

    def resolve_sections(self, school):
        from django.db.models import Q

        section_ids = set(self.validated_data.get("section_ids") or [])
        class_level_ids = set(self.validated_data.get("class_level_ids") or [])

        if class_level_ids:
            valid_levels = set(
                ClassLevel.objects.filter(school=school, id__in=class_level_ids).values_list("id", flat=True)
            )
            invalid_levels = class_level_ids - valid_levels
            if invalid_levels:
                raise serializers.ValidationError(
                    {"class_level_ids": f"Unknown class levels for this school: {sorted(invalid_levels)}"}
                )

        if section_ids:
            found = set(
                Section.objects.filter(school=school, id__in=section_ids).values_list("id", flat=True)
            )
            missing = section_ids - found
            if missing:
                raise serializers.ValidationError(
                    {"section_ids": f"Unknown sections for this school: {sorted(missing)}"}
                )

        query = Q()
        if section_ids:
            query |= Q(id__in=section_ids)
        if class_level_ids:
            query |= Q(class_level_id__in=class_level_ids)

        sections = list(
            Section.objects.filter(school=school)
            .filter(query)
            .select_related("class_level")
            .distinct()
            .order_by("class_level__order", "name")
        )
        if not sections:
            raise serializers.ValidationError({"section_ids": "No matching sections found."})
        return sections
