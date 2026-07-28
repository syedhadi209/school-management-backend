from django.contrib.auth import get_user_model
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from schools.models import School

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
    class Meta:
        model = UserRole
        fields = "__all__"


class TeacherProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherProfile
        fields = "__all__"


class ParentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentProfile
        fields = "__all__"
