from django.contrib.auth import get_user_model
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

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

    def get_full_name(self, obj: TeacherProfile) -> str:
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    class Meta:
        model = TeacherProfile
        fields = (
            "id",
            "user",
            "school",
            "employee_id",
            "joining_date",
            "qualification",
            "full_name",
            "email",
            "first_name",
            "last_name",
            "password",
        )
        read_only_fields = ("school", "employee_id", "user")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["email"] = instance.user.email
        return data

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
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        school = request.user.active_school
        if school is None:
            raise serializers.ValidationError({"detail": "No active school selected."})

        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name", "")
        password = validated_data.pop("password")
        email = validated_data.pop("email")
        validated_data.pop("school", None)
        validated_data.pop("user", None)

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            active_school=school,
        )
        UserRole.objects.get_or_create(user=user, school=school, role=RoleChoices.TEACHER)
        return TeacherProfile.objects.create(user=user, school=school, **validated_data)

    def update(self, instance, validated_data):
        # Account credentials are not edited from this form yet.
        validated_data.pop("password", None)
        validated_data.pop("email", None)
        first_name = validated_data.pop("first_name", None)
        last_name = validated_data.pop("last_name", None)

        if first_name is not None or last_name is not None:
            if first_name is not None:
                instance.user.first_name = first_name
            if last_name is not None:
                instance.user.last_name = last_name
            instance.user.save(update_fields=["first_name", "last_name"])

        return super().update(instance, validated_data)


class ParentProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    email = serializers.CharField(source="user.email", read_only=True, default="")

    def get_full_name(self, obj: ParentProfile) -> str:
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    class Meta:
        model = ParentProfile
        fields = "__all__"
        read_only_fields = ("school",)
