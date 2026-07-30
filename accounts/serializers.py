from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from academics.models import Subject
from core.cnic import validate_cnic
from schools.models import School
from schools.services import get_or_create_default_academic_year

from .models import ParentProfile, RoleChoices, TeacherProfile, UserRole

User = get_user_model()


class SchoolOwnerRegisterSerializer(serializers.Serializer):
    school_name = serializers.CharField(max_length=255)
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    def create(self, validated_data):
        school_name = validated_data["school_name"]
        school = School.objects.create(name=school_name, slug=slugify(school_name))
        get_or_create_default_academic_year(school)
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["full_name"],
            active_school=school,
        )
        UserRole.objects.create(user=user, school=school, role=RoleChoices.SCHOOL_ADMIN)
        return user


class AppTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        active_role = None
        if user.active_school_id:
            membership = user.school_roles.filter(school_id=user.active_school_id).first()
            active_role = membership.role if membership else None
        token["email"] = user.email
        token["active_school_id"] = user.active_school_id
        token["role"] = active_role
        return token


class UserRoleSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default="")

    class Meta:
        model = UserRole
        fields = "__all__"


class TeacherProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(write_only=True, required=False, max_length=150)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True, default="", max_length=150)
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    subjects_taught = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(),
        many=True,
        required=False,
    )
    subject_names = serializers.SerializerMethodField()

    def get_full_name(self, obj: TeacherProfile) -> str:
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    def get_subject_names(self, obj: TeacherProfile) -> list[str]:
        return list(obj.subjects_taught.order_by("name").values_list("name", flat=True))

    class Meta:
        model = TeacherProfile
        fields = (
            "id",
            "user",
            "school",
            "employee_id",
            "designation",
            "shift_start_time",
            "shift_end_time",
            "joining_date",
            "qualification",
            "monthly_salary",
            "address",
            "cnic",
            "phone_number",
            "subjects_taught",
            "subject_names",
            "full_name",
            "email",
            "first_name",
            "last_name",
            "password",
        )
        read_only_fields = ("school", "employee_id", "user", "subject_names")
        extra_kwargs = {
            "monthly_salary": {"required": False, "allow_null": True},
            "address": {"required": False, "allow_blank": True},
            "cnic": {"required": False, "allow_blank": True},
            "phone_number": {"required": False, "allow_blank": True},
            "shift_start_time": {"required": False, "allow_null": True},
            "shift_end_time": {"required": False, "allow_null": True},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["email"] = instance.user.email
        data["subjects_taught"] = list(instance.subjects_taught.values_list("id", flat=True))
        return data

    def validate_cnic(self, value: str) -> str:
        return validate_cnic(value)

    def validate_monthly_salary(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Monthly salary cannot be negative.")
        return value

    def validate_subjects_taught(self, subjects):
        request = self.context.get("request")
        school = getattr(getattr(request, "user", None), "active_school", None)
        if school is None:
            return subjects
        for subject in subjects:
            if subject.school_id != school.id:
                raise serializers.ValidationError(
                    f"{subject.name} does not belong to your active school."
                )
        return subjects

    def validate(self, attrs):
        if self.instance is None:
            missing = []
            if not attrs.get("first_name"):
                missing.append("first_name")
            if not attrs.get("email"):
                missing.append("email")
            if not attrs.get("password"):
                missing.append("password")
            if missing:
                raise serializers.ValidationError(
                    {field: "This field is required." for field in missing}
                )
            email = attrs["email"].strip().lower()
            if User.objects.filter(email__iexact=email).exists():
                raise serializers.ValidationError({"email": "A user with this email already exists."})
            attrs["email"] = email

        cnic = attrs.get("cnic", getattr(self.instance, "cnic", "") if self.instance else "")
        if cnic:
            request = self.context.get("request")
            school = getattr(getattr(request, "user", None), "active_school", None)
            if school is not None:
                duplicate = TeacherProfile.objects.filter(school=school, cnic=cnic)
                if self.instance is not None:
                    duplicate = duplicate.exclude(pk=self.instance.pk)
                if duplicate.exists():
                    raise serializers.ValidationError(
                        {"cnic": "This CNIC is already used by another teacher in this school."}
                    )

        shift_start = attrs.get(
            "shift_start_time",
            getattr(self.instance, "shift_start_time", None) if self.instance else None,
        )
        shift_end = attrs.get(
            "shift_end_time",
            getattr(self.instance, "shift_end_time", None) if self.instance else None,
        )
        if (shift_start is None) != (shift_end is None):
            missing_field = "shift_end_time" if shift_start is not None else "shift_start_time"
            raise serializers.ValidationError(
                {missing_field: "Enter both the shift start and end time."}
            )
        if shift_start is not None and shift_end is not None and shift_end <= shift_start:
            raise serializers.ValidationError(
                {"shift_end_time": "Shift end time must be later than the start time."}
            )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        school = request.user.active_school
        if school is None:
            raise serializers.ValidationError({"detail": "No active school selected."})

        subjects = validated_data.pop("subjects_taught", [])
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name", "")
        password = validated_data.pop("password")
        email = validated_data.pop("email")
        validated_data.pop("school", None)
        validated_data.pop("user", None)

        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                active_school=school,
            )
            UserRole.objects.get_or_create(user=user, school=school, role=RoleChoices.TEACHER)
            profile = TeacherProfile.objects.create(user=user, school=school, **validated_data)
            if subjects:
                profile.subjects_taught.set(subjects)
        return profile

    def update(self, instance, validated_data):
        validated_data.pop("password", None)
        validated_data.pop("email", None)
        subjects = validated_data.pop("subjects_taught", None)
        first_name = validated_data.pop("first_name", None)
        last_name = validated_data.pop("last_name", None)

        if first_name is not None or last_name is not None:
            if first_name is not None:
                instance.user.first_name = first_name
            if last_name is not None:
                instance.user.last_name = last_name
            instance.user.save(update_fields=["first_name", "last_name"])

        profile = super().update(instance, validated_data)
        if subjects is not None:
            profile.subjects_taught.set(subjects)
        return profile


class ParentProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    email = serializers.CharField(source="user.email", read_only=True, default="")

    def get_full_name(self, obj: ParentProfile) -> str:
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    class Meta:
        model = ParentProfile
        fields = "__all__"
        read_only_fields = ("school",)
