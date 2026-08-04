from datetime import date as date_cls

from django.db.models import Prefetch
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response

from core.permissions import (
    IsAttendanceStaff,
    IsAttendanceViewer,
    get_active_role,
    is_school_admin_or_manager,
)
from core.viewsets import TenantScopedModelViewSet
from students.models import Student
from timetable.models import TimetableEntry
from timetable.services import school_local_now

from .models import AttendanceRecord, AttendanceSession
from .serializers import (
    AttendanceRecordSerializer,
    AttendanceSessionListSerializer,
    AttendanceSessionSerializer,
    AttendanceTakeSerializer,
)
from .services import draft_payload_for_entry, summarize_sessions, take_attendance


class AttendanceSessionViewSet(TenantScopedModelViewSet):
    queryset = AttendanceSession.objects.select_related(
        "section__class_level",
        "teacher__user",
        "subject",
        "timetable_entry",
        "taken_by",
        "academic_year",
    ).prefetch_related(
        Prefetch("records", queryset=AttendanceRecord.objects.select_related("student"))
    )
    filterset_fields = [
        "date",
        "section",
        "teacher",
        "timetable_entry",
        "academic_year",
        "status",
    ]
    ordering_fields = ["date", "start_time", "end_time", "id"]
    ordering = ["-date", "start_time", "id"]
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action in {"take", "for_entry", "summary"} or self.request.method not in SAFE_METHODS:
            return [IsAuthenticated(), IsAttendanceStaff()]
        return [IsAuthenticated(), IsAttendanceStaff()]

    def get_serializer_class(self):
        if self.action == "list":
            return AttendanceSessionListSerializer
        return AttendanceSessionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or is_school_admin_or_manager(user):
            return qs

        role = get_active_role(user)
        if role == "teacher":
            teacher = getattr(user, "teacher_profile", None)
            if teacher is None:
                return qs.none()
            return qs.filter(teacher=teacher)

        return qs.none()

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Use POST /api/v1/attendance-sessions/take/ to submit attendance."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=False, methods=["post"], url_path="take")
    def take(self, request):
        serializer = AttendanceTakeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        session = take_attendance(
            user=request.user,
            school=request.user.active_school,
            timetable_entry_id=data["timetable_entry"],
            attendance_date=data["date"],
            records=data["records"],
            notes=data.get("notes", ""),
        )
        return Response(
            AttendanceSessionSerializer(session, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="for-entry")
    def for_entry(self, request):
        entry_id = request.query_params.get("timetable_entry")
        date_param = request.query_params.get("date")
        if not entry_id:
            return Response({"timetable_entry": ["This query parameter is required."]}, status=400)

        school = request.user.active_school
        if school is None:
            return Response({"detail": "Active school required."}, status=400)

        try:
            entry = TimetableEntry.objects.select_related("section", "teacher", "subject").get(
                pk=int(entry_id), school=school
            )
        except (TimetableEntry.DoesNotExist, TypeError, ValueError):
            return Response({"timetable_entry": ["Timetable entry not found."]}, status=404)

        if entry.slot_type != TimetableEntry.SLOT_LECTURE:
            return Response({"timetable_entry": ["Breaks cannot have attendance."]}, status=400)

        if not is_school_admin_or_manager(request.user):
            teacher = getattr(request.user, "teacher_profile", None)
            if teacher is None or entry.teacher_id != teacher.id:
                return Response({"detail": "You can only view attendance for your own lectures."}, status=403)

        if date_param:
            try:
                attendance_date = date_cls.fromisoformat(date_param)
            except ValueError:
                return Response({"date": ["Invalid date. Use YYYY-MM-DD."]}, status=400)
        else:
            local_now, _, _ = school_local_now(school)
            attendance_date = local_now.date()

        session = (
            AttendanceSession.objects.filter(timetable_entry=entry, date=attendance_date)
            .prefetch_related(Prefetch("records", queryset=AttendanceRecord.objects.select_related("student")))
            .first()
        )
        payload = draft_payload_for_entry(entry=entry, attendance_date=attendance_date, session=session)
        return Response(payload)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        qs = self.filter_queryset(self.get_queryset())
        return Response(summarize_sessions(qs))


class AttendanceRecordViewSet(TenantScopedModelViewSet):
    queryset = AttendanceRecord.objects.select_related(
        "student",
        "session",
        "session__section__class_level",
        "session__teacher__user",
        "session__subject",
    )
    serializer_class = AttendanceRecordSerializer
    filterset_fields = ["student", "session", "status"]
    ordering_fields = ["marked_at", "id", "status"]
    ordering = ["-session__date", "student__roll_number", "id"]
    http_method_names = ["get", "head", "options"]

    def get_permissions(self):
        return [IsAuthenticated(), IsAttendanceViewer()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or is_school_admin_or_manager(user):
            qs = qs
        else:
            role = get_active_role(user)
            school = user.active_school
            if role == "teacher":
                teacher = getattr(user, "teacher_profile", None)
                if teacher is None:
                    return qs.none()
                qs = qs.filter(session__teacher=teacher)
            elif role == "parent":
                parent = getattr(user, "parent_profile", None)
                if parent is None or school is None:
                    return qs.none()
                child_ids = Student.objects.filter(
                    school=school,
                    parent_links__parent=parent,
                ).values_list("id", flat=True)
                qs = qs.filter(student_id__in=child_ids)
            else:
                return qs.none()

        date_exact = self.request.query_params.get("date") or self.request.query_params.get("session__date")
        date_gte = self.request.query_params.get("session__date__gte")
        date_lte = self.request.query_params.get("session__date__lte")
        section = self.request.query_params.get("section") or self.request.query_params.get("session__section")
        if date_exact:
            qs = qs.filter(session__date=date_exact)
        if date_gte:
            qs = qs.filter(session__date__gte=date_gte)
        if date_lte:
            qs = qs.filter(session__date__lte=date_lte)
        if section:
            qs = qs.filter(session__section_id=section)
        return qs
