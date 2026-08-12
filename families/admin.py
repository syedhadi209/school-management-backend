from django.contrib import admin

from .models import Family


@admin.register(Family)
class FamilyAdmin(admin.ModelAdmin):
    list_display = ("family_code", "school", "primary_contact_email", "created_at")
    search_fields = ("family_code", "primary_contact_email", "father_name", "mother_name")
    list_filter = ("school",)
