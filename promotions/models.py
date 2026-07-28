from django.db import models


class PromotionHistory(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="promotion_history")
    student = models.ForeignKey("students.Student", on_delete=models.CASCADE, related_name="promotion_history")
    from_section = models.ForeignKey(
        "academics.Section", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    to_section = models.ForeignKey(
        "academics.Section", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    result_status = models.CharField(max_length=30, default="eligible")
    override_reason = models.TextField(blank=True)
    decided_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)
    decided_at = models.DateTimeField(auto_now_add=True)
