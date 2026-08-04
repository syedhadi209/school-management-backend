from datetime import datetime
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from django.utils.timesince import timesince
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import TeacherProfile
from academics.models import ClassLevel, Section, Subject
from admissions.models import Inquiry
from fees.models import Invoice, Payment
from students.models import Student
from timetable.models import TimetableEntry


def _relative_time(value: datetime | None) -> str:
    if value is None:
        return ""
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    delta = timesince(value, timezone.now()).split(",")[0]
    return f"{delta} ago"


class SchoolDashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = request.user.active_school
        if school is None and not request.user.is_superuser:
            return Response({"detail": "No active school selected."}, status=400)

        students_qs = Student.objects.all()
        inquiries_qs = Inquiry.objects.all()
        sections_qs = Section.objects.all()
        subjects_qs = Subject.objects.all()
        teachers_qs = TeacherProfile.objects.select_related("user").all()
        invoices_qs = Invoice.objects.all()
        payments_qs = Payment.objects.all()
        classes_qs = ClassLevel.objects.all()
        timetable_qs = TimetableEntry.objects.select_related(
            "section__class_level", "subject", "teacher__user"
        ).all()

        if not request.user.is_superuser:
            if school is None:
                return Response({"detail": "No active school selected."}, status=400)
            students_qs = students_qs.filter(school=school)
            inquiries_qs = inquiries_qs.filter(school=school)
            sections_qs = sections_qs.filter(school=school)
            subjects_qs = subjects_qs.filter(school=school)
            teachers_qs = teachers_qs.filter(school=school)
            invoices_qs = invoices_qs.filter(school=school)
            payments_qs = payments_qs.filter(school=school)
            classes_qs = classes_qs.filter(school=school)
            timetable_qs = timetable_qs.filter(school=school)

        total_invoice_amount = invoices_qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0")
        total_paid_amount = payments_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        fee_collection_rate = Decimal("0")
        if total_invoice_amount > 0:
            fee_collection_rate = (total_paid_amount / total_invoice_amount) * 100

        recent_activity: list[dict] = []

        for inquiry in inquiries_qs.order_by("-created_at", "-id")[:8]:
            recent_activity.append(
                {
                    "type": "inquiry",
                    "title": f"Inquiry: {inquiry.full_name}",
                    "subtitle": f"Status: {inquiry.status}",
                    "time": _relative_time(inquiry.created_at),
                    "sort_at": inquiry.created_at,
                }
            )

        for student in students_qs.select_related("section__class_level").order_by("-id")[:5]:
            section_label = ""
            if student.section_id:
                section_label = f"{student.section.class_level.name}-{student.section.name}"
            recent_activity.append(
                {
                    "type": "student",
                    "title": f"Student: {student.first_name} {student.last_name}".strip(),
                    "subtitle": section_label or f"Status: {student.status}",
                    "time": "",
                    "sort_at": None,
                }
            )

        for teacher in teachers_qs.order_by("-id")[:5]:
            name = f"{teacher.user.first_name} {teacher.user.last_name}".strip() or teacher.user.email
            recent_activity.append(
                {
                    "type": "teacher",
                    "title": f"Teacher: {name}",
                    "subtitle": teacher.designation.replace("_", " ").title() if teacher.designation else "Staff",
                    "time": "",
                    "sort_at": None,
                }
            )

        for class_level in classes_qs.order_by("-id")[:3]:
            recent_activity.append(
                {
                    "type": "section",
                    "title": f"Class: {class_level.name}",
                    "subtitle": f"Order {class_level.order}",
                    "time": "",
                    "sort_at": None,
                }
            )

        for entry in timetable_qs.filter(is_active=True).order_by("-id")[:3]:
            label = entry.section.class_level.name + "-" + entry.section.name
            if entry.slot_type == TimetableEntry.SLOT_BREAK:
                title = f"Break: {entry.label or 'Break'}"
                subtitle = f"{label}"
            else:
                subject = entry.subject.name if entry.subject_id else "Lecture"
                title = f"Timetable: {subject}"
                subtitle = label
            recent_activity.append(
                {
                    "type": "timetable",
                    "title": title,
                    "subtitle": subtitle,
                    "time": "",
                    "sort_at": None,
                }
            )

        # Prefer dated inquiry events first, then other school-scoped items.
        dated = [item for item in recent_activity if item.get("sort_at") is not None]
        undated = [item for item in recent_activity if item.get("sort_at") is None]
        dated.sort(key=lambda item: item["sort_at"], reverse=True)
        cleaned = []
        for item in (dated + undated)[:8]:
            item.pop("sort_at", None)
            cleaned.append(item)

        payload = {
            "stats": {
                "active_students": students_qs.filter(status="active").count(),
                "pending_admissions": inquiries_qs.filter(
                    status__in=["new", "contacted", "visited", "applied"]
                ).count(),
                "total_sections": sections_qs.count(),
                "total_subjects": subjects_qs.count(),
                "total_teachers": teachers_qs.count(),
                "fee_collection_rate": round(float(fee_collection_rate), 2),
            },
            "recent_activity": cleaned,
        }
        return Response(payload)
