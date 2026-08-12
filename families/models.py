from django.db import models


class Family(models.Model):
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="families")
    family_code = models.CharField(max_length=32)
    primary_contact_email = models.EmailField(blank=True)
    father_name = models.CharField(max_length=150, blank=True)
    mother_name = models.CharField(max_length=150, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["school", "family_code"], name="families_unique_code_per_school"),
        ]
        ordering = ["family_code", "id"]

    def __str__(self) -> str:
        return self.family_code
