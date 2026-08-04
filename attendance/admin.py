from django.contrib import admin

from .models import AttendanceRecord, AttendanceSession


class AttendanceRecordInline(admin.TabularInline):
    model = AttendanceRecord
    extra = 0
    raw_id_fields = ("student",)


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "school", "section", "teacher", "date", "start_time", "end_time", "status")
    list_filter = ("status", "date", "school")
    search_fields = ("section__name", "teacher__user__email", "notes")
    raw_id_fields = ("school", "academic_year", "timetable_entry", "section", "teacher", "subject", "taken_by")
    inlines = [AttendanceRecordInline]


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "school", "session", "student", "status", "marked_at")
    list_filter = ("status", "school")
    search_fields = ("student__first_name", "student__last_name", "student__roll_number")
    raw_id_fields = ("school", "session", "student")
