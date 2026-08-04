from rest_framework import serializers

from timetable.services import section_label

from .models import AttendanceRecord, AttendanceSession
from .services import session_summary


class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    roll_number = serializers.CharField(source="student.roll_number", read_only=True, default="")
    session_date = serializers.DateField(source="session.date", read_only=True)
    section_label = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="session.subject.name", read_only=True, default="")
    start_time = serializers.TimeField(source="session.start_time", read_only=True)
    end_time = serializers.TimeField(source="session.end_time", read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = (
            "id",
            "school",
            "session",
            "student",
            "student_name",
            "roll_number",
            "status",
            "remarks",
            "marked_at",
            "session_date",
            "section_label",
            "subject_name",
            "start_time",
            "end_time",
        )
        read_only_fields = ("school", "session", "marked_at")

    def get_student_name(self, obj: AttendanceRecord) -> str:
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def get_section_label(self, obj: AttendanceRecord) -> str:
        return section_label(obj.session.section)


class AttendanceRecordInputSerializer(serializers.Serializer):
    student = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=AttendanceRecord.STATUS_CHOICES)
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")


class AttendanceTakeSerializer(serializers.Serializer):
    timetable_entry = serializers.IntegerField(min_value=1)
    date = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    records = AttendanceRecordInputSerializer(many=True)


class AttendanceSessionSerializer(serializers.ModelSerializer):
    section_label = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.name", read_only=True, default="")
    taken_by_name = serializers.SerializerMethodField()
    records = AttendanceRecordSerializer(many=True, read_only=True)
    summary = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceSession
        fields = (
            "id",
            "school",
            "academic_year",
            "timetable_entry",
            "section",
            "section_label",
            "teacher",
            "teacher_name",
            "subject",
            "subject_name",
            "date",
            "day_of_week",
            "start_time",
            "end_time",
            "status",
            "taken_by",
            "taken_by_name",
            "taken_at",
            "notes",
            "created_at",
            "updated_at",
            "records",
            "summary",
        )
        read_only_fields = fields

    def get_section_label(self, obj: AttendanceSession) -> str:
        return section_label(obj.section)

    def get_teacher_name(self, obj: AttendanceSession) -> str:
        name = f"{obj.teacher.user.first_name} {obj.teacher.user.last_name}".strip()
        return name or obj.teacher.user.email

    def get_taken_by_name(self, obj: AttendanceSession) -> str:
        if obj.taken_by_id is None:
            return ""
        name = f"{obj.taken_by.first_name} {obj.taken_by.last_name}".strip()
        return name or obj.taken_by.email

    def get_summary(self, obj: AttendanceSession) -> dict:
        return session_summary(obj)


class AttendanceSessionListSerializer(AttendanceSessionSerializer):
    class Meta(AttendanceSessionSerializer.Meta):
        fields = (
            "id",
            "school",
            "academic_year",
            "timetable_entry",
            "section",
            "section_label",
            "teacher",
            "teacher_name",
            "subject",
            "subject_name",
            "date",
            "day_of_week",
            "start_time",
            "end_time",
            "status",
            "taken_by",
            "taken_by_name",
            "taken_at",
            "notes",
            "created_at",
            "updated_at",
            "summary",
        )
