from decimal import Decimal

from django.db.models import Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import TeacherProfile
from academics.models import Section, Subject
from admissions.models import Inquiry
from fees.models import Invoice, Payment
from students.models import Student


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
        teachers_qs = TeacherProfile.objects.all()
        invoices_qs = Invoice.objects.all()
        payments_qs = Payment.objects.all()

        if not request.user.is_superuser:
            students_qs = students_qs.filter(school=school)
            inquiries_qs = inquiries_qs.filter(school=school)
            sections_qs = sections_qs.filter(school=school)
            subjects_qs = subjects_qs.filter(school=school)
            teachers_qs = teachers_qs.filter(school=school)
            invoices_qs = invoices_qs.filter(school=school)
            payments_qs = payments_qs.filter(school=school)

        total_invoice_amount = invoices_qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0")
        total_paid_amount = payments_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        fee_collection_rate = Decimal("0")
        if total_invoice_amount > 0:
            fee_collection_rate = (total_paid_amount / total_invoice_amount) * 100

        recent_activity = []
        for inquiry in inquiries_qs.order_by("-id")[:5]:
            recent_activity.append(
                {
                    "type": "inquiry",
                    "title": f"Inquiry: {inquiry.full_name}",
                    "subtitle": f"Status: {inquiry.status}",
                }
            )

        payload = {
            "stats": {
                "active_students": students_qs.filter(status="active").count(),
                "pending_admissions": inquiries_qs.filter(status__in=["new", "contacted", "visited", "applied"]).count(),
                "total_sections": sections_qs.count(),
                "total_subjects": subjects_qs.count(),
                "total_teachers": teachers_qs.count(),
                "fee_collection_rate": round(float(fee_collection_rate), 2),
            },
            "recent_activity": recent_activity,
        }
        return Response(payload)
