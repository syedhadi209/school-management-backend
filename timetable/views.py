from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response

from academics.models import Section
from core.permissions import (
    IsManager,
    IsTimetableViewer,
    get_active_role,
    is_school_admin_or_manager,
)
from core.viewsets import TenantScopedModelViewSet
from schools.models import AcademicYear
from schools.services import get_or_create_default_academic_year
from students.models import Student

from .models import TimetableEntry
from .serializers import BulkBreakSerializer, TimetableEntrySerializer
from .services import (
    describe_entry,
    overlapping_entries,
    school_local_now,
    section_label,
    teacher_schedule_q,
)


class TimetableEntryViewSet(TenantScopedModelViewSet):
    queryset = TimetableEntry.objects.select_related(
        "section__class_level",
        "subject",
        "teacher__user",
        "academic_year",
    )
    serializer_class = TimetableEntrySerializer
    filterset_fields = [
        "section",
        "teacher",
        "subject",
        "slot_type",
        "day_of_week",
        "academic_year",
        "is_active",
    ]
    ordering_fields = ["day_of_week", "start_time", "end_time", "id"]
    ordering = ["day_of_week", "start_time", "id"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS or self.action in {
            "my_schedule",
            "current",
        }:
            return [IsAuthenticated(), IsTimetableViewer()]
        return [IsAuthenticated(), IsManager()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser or is_school_admin_or_manager(user):
            return self._apply_student_filter(qs)

        role = get_active_role(user)
        school = user.active_school
        if school is None:
            return qs.none()

        if role == "teacher":
            teacher = getattr(user, "teacher_profile", None)
            if teacher is None:
                return qs.none()
            return qs.filter(teacher_schedule_q(teacher, school))

        if role == "parent":
            parent = getattr(user, "parent_profile", None)
            if parent is None:
                return qs.none()
            section_ids = (
                Student.objects.filter(
                    school=school,
                    parent_links__parent=parent,
                    section__isnull=False,
                )
                .values_list("section_id", flat=True)
                .distinct()
            )
            qs = qs.filter(section_id__in=section_ids)
            return self._apply_student_filter(qs)

        return qs.none()

    def _apply_student_filter(self, qs):
        student_id = self.request.query_params.get("student")
        if not student_id:
            return qs
        try:
            student_pk = int(student_id)
        except (TypeError, ValueError):
            return qs.none()
        user = self.request.user
        school = user.active_school
        student_qs = Student.objects.filter(pk=student_pk, section__isnull=False)
        if school is not None and not user.is_superuser:
            student_qs = student_qs.filter(school=school)
        if get_active_role(user) == "parent":
            parent = getattr(user, "parent_profile", None)
            if parent is None:
                return qs.none()
            student_qs = student_qs.filter(parent_links__parent=parent)
        section_id = student_qs.values_list("section_id", flat=True).first()
        if section_id is None:
            return qs.none()
        return qs.filter(section_id=section_id)

    @action(detail=False, methods=["get"], url_path="my-schedule")
    def my_schedule(self, request):
        teacher = getattr(request.user, "teacher_profile", None)
        if teacher is None and not is_school_admin_or_manager(request.user) and not request.user.is_superuser:
            return Response({"detail": "Teacher profile required."}, status=status.HTTP_403_FORBIDDEN)

        qs = self.get_queryset().filter(is_active=True)
        if teacher is not None and not is_school_admin_or_manager(request.user):
            qs = qs.filter(teacher_schedule_q(teacher, request.user.active_school))
        elif teacher is not None:
            qs = qs.filter(teacher=teacher)

        serializer = self.get_serializer(qs, many=True)
        by_day: dict[str, list] = {str(day): [] for day, _ in TimetableEntry.DAY_CHOICES}
        for entry in serializer.data:
            by_day[str(entry["day_of_week"])].append(entry)
        return Response({"days": by_day, "results": serializer.data})

    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request):
        teacher = getattr(request.user, "teacher_profile", None)
        if teacher is None:
            return Response({"detail": "Teacher profile required."}, status=status.HTTP_403_FORBIDDEN)

        school = request.user.active_school
        if school is None:
            return Response({"detail": "Active school required."}, status=status.HTTP_400_BAD_REQUEST)

        local_now, day_of_week, local_time = school_local_now(school)

        base = TimetableEntry.objects.filter(
            school=school,
            day_of_week=day_of_week,
            is_active=True,
        ).filter(teacher_schedule_q(teacher, school)).select_related(
            "section__class_level", "subject", "teacher__user"
        )

        current_entry = (
            base.filter(start_time__lte=local_time, end_time__gt=local_time)
            .order_by("start_time", "id")
            .first()
        )
        # Prefer an active lecture over a break when both somehow match (should not happen).
        if current_entry and current_entry.slot_type == TimetableEntry.SLOT_BREAK:
            lecture = (
                base.filter(
                    slot_type=TimetableEntry.SLOT_LECTURE,
                    teacher=teacher,
                    start_time__lte=local_time,
                    end_time__gt=local_time,
                )
                .order_by("start_time", "id")
                .first()
            )
            if lecture is not None:
                current_entry = lecture

        next_entry = (
            base.filter(teacher=teacher, slot_type=TimetableEntry.SLOT_LECTURE, start_time__gt=local_time)
            .order_by("start_time", "id")
            .first()
        )

        payload = {
            "server_time": local_now.isoformat(),
            "day_of_week": day_of_week,
            "local_time": local_time.strftime("%H:%M:%S"),
            "current": self._serialize_current_slot(
                current_entry, request, include_roster=True, attendance_date=local_now.date()
            ),
            "next": self._serialize_current_slot(
                next_entry, request, include_roster=False, attendance_date=local_now.date()
            ),
        }
        return Response(payload)

    def _serialize_current_slot(
        self,
        entry: TimetableEntry | None,
        request,
        *,
        include_roster: bool,
        attendance_date=None,
    ):
        if entry is None:
            return None
        data = TimetableEntrySerializer(entry, context={"request": request}).data
        data["section_label"] = section_label(entry.section)
        data["attendance_session_id"] = None
        data["attendance_taken"] = False
        if entry.slot_type == TimetableEntry.SLOT_LECTURE and attendance_date is not None:
            from attendance.models import AttendanceSession

            session = (
                AttendanceSession.objects.filter(
                    timetable_entry=entry,
                    date=attendance_date,
                    status=AttendanceSession.STATUS_SUBMITTED,
                )
                .only("id")
                .first()
            )
            if session is not None:
                data["attendance_session_id"] = session.id
                data["attendance_taken"] = True
        if include_roster and entry.slot_type == TimetableEntry.SLOT_LECTURE:
            students = (
                Student.objects.filter(section=entry.section, status="active")
                .order_by("roll_number", "first_name", "last_name")
            )
            data["roster"] = [
                {
                    "id": student.id,
                    "first_name": student.first_name,
                    "last_name": student.last_name,
                    "full_name": f"{student.first_name} {student.last_name}".strip(),
                    "roll_number": student.roll_number,
                    "profile_image": (
                        request.build_absolute_uri(student.profile_image.url)
                        if student.profile_image
                        else None
                    ),
                }
                for student in students
            ]
        else:
            data["roster"] = []
        return data

    @action(detail=False, methods=["post"], url_path="bulk-break")
    def bulk_break(self, request):
        serializer = BulkBreakSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        school = request.user.active_school
        if school is None:
            return Response({"detail": "Active school required."}, status=status.HTTP_400_BAD_REQUEST)

        sections = serializer.resolve_sections(school)
        data = serializer.validated_data
        academic_year_id = data.get("academic_year")
        if academic_year_id:
            academic_year = AcademicYear.objects.filter(school=school, pk=academic_year_id).first()
            if academic_year is None:
                return Response(
                    {"academic_year": ["Academic year must belong to your active school."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            academic_year = get_or_create_default_academic_year(school)

        created = []
        conflicts = []
        for section in sections:
            clashes = overlapping_entries(
                school=school,
                academic_year=academic_year,
                day_of_week=data["day_of_week"],
                start_time=data["start_time"],
                end_time=data["end_time"],
                section=section,
            )
            if clashes:
                conflicts.append(
                    {
                        "section_id": section.id,
                        "section_label": section_label(section),
                        "error": describe_entry(clashes[0]),
                    }
                )
                continue
            entry = TimetableEntry.objects.create(
                school=school,
                academic_year=academic_year,
                section=section,
                slot_type=TimetableEntry.SLOT_BREAK,
                label=data["label"],
                day_of_week=data["day_of_week"],
                start_time=data["start_time"],
                end_time=data["end_time"],
                is_active=True,
            )
            created.append(TimetableEntrySerializer(entry, context={"request": request}).data)

        return Response(
            {
                "created_count": len(created),
                "conflict_count": len(conflicts),
                "created": created,
                "conflicts": conflicts,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST,
        )
