from django.contrib import admin

from .models import Fund


@admin.register(Fund)
class FundAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "academic_year", "amount", "tenure", "status", "due_on")
    list_filter = ("status", "tenure", "school")
    search_fields = ("name",)
    filter_horizontal = ("class_levels",)
