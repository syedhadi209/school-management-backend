from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction


def teacher_profile_image_path(instance: "TeacherProfile", filename: str) -> str:
    from uuid import uuid4

    school_id = instance.school_id or "unknown"
    return f"profile-images/teachers/school-{school_id}/{uuid4().hex}.webp"


def user_profile_image_path(instance: "User", filename: str) -> str:
    from uuid import uuid4

    school_id = instance.active_school_id or "unknown"
    return f"profile-images/users/school-{school_id}/{uuid4().hex}.webp"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, username=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    active_school = models.ForeignKey(
        "schools.School", null=True, blank=True, on_delete=models.SET_NULL, related_name="active_users"
    )
    profile_image = models.ImageField(upload_to=user_profile_image_path, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    def __str__(self) -> str:
        return self.email

    def delete(self, *args, **kwargs):
        image_name = self.profile_image.name
        image_storage = self.profile_image.storage if image_name else None
        response = super().delete(*args, **kwargs)
        if image_name and image_storage is not None:
            transaction.on_commit(lambda: image_storage.delete(image_name))
        return response


class RoleChoices(models.TextChoices):
    SUPER_ADMIN = "super_admin", "Super Admin"
    SCHOOL_ADMIN = "school_admin", "School Admin"
    MANAGER = "manager", "Manager"
    FRONT_DESK = "front_desk", "Front Desk"
    TEACHER = "teacher", "Teacher"
    ACCOUNTANT = "accountant", "Accountant"
    PARENT = "parent", "Parent"
    STUDENT = "student", "Student"


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="school_roles")
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="user_roles")
    role = models.CharField(max_length=30, choices=RoleChoices.choices)

    class Meta:
        unique_together = ("user", "school", "role")


class TeacherProfile(models.Model):
    DESIGNATION_CHOICES = (
        ("subject_teacher", "Subject Teacher"),
        ("accountant", "Accountant"),
        ("principal", "Principal"),
        ("sports_teacher", "Sports Teacher"),
        ("maid", "Maid"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="teacher_profile")
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="teachers")
    employee_id = models.CharField(max_length=30, blank=True)
    designation = models.CharField(
        max_length=30,
        choices=DESIGNATION_CHOICES,
        default="subject_teacher",
    )
    shift_start_time = models.TimeField(null=True, blank=True)
    shift_end_time = models.TimeField(null=True, blank=True)
    joining_date = models.DateField(null=True, blank=True)
    qualification = models.CharField(max_length=255, blank=True)
    monthly_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    address = models.TextField(blank=True)
    cnic = models.CharField(max_length=20, blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    profile_image = models.ImageField(
        upload_to=teacher_profile_image_path,
        blank=True,
    )
    subjects_taught = models.ManyToManyField(
        "academics.Subject",
        blank=True,
        related_name="specialist_teachers",
        help_text="Subject specialties for this teacher. Section assignments are managed separately.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["school", "employee_id"],
                name="unique_teacher_employee_id_per_school",
                condition=~models.Q(employee_id=""),
            ),
            models.UniqueConstraint(
                fields=["school", "cnic"],
                name="unique_teacher_cnic_per_school",
                condition=~models.Q(cnic=""),
            ),
        ]

    def save(self, *args, **kwargs):
        from django.db import transaction

        from core.identifiers import next_readable_id

        if not self.employee_id and self.school_id:
            with transaction.atomic():
                self.employee_id = next_readable_id(
                    TeacherProfile.objects.select_for_update(),
                    field_name="employee_id",
                    prefix="TCH",
                    school_id=self.school_id,
                )
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        image_name = self.profile_image.name
        image_storage = self.profile_image.storage if image_name else None
        response = super().delete(*args, **kwargs)
        if image_name and image_storage is not None:
            transaction.on_commit(lambda: image_storage.delete(image_name))
        return response


class ParentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="parent_profile")
    school = models.ForeignKey("schools.School", on_delete=models.CASCADE, related_name="parents")

