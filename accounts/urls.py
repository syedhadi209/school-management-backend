from django.urls import path
from .views import (
    AppTokenObtainPairView,
    CookieTokenRefreshView,
    LogoutView,
    RegisterSchoolOwnerView,
)

urlpatterns = [
    path("register/", RegisterSchoolOwnerView.as_view(), name="register"),
    path("login/", AppTokenObtainPairView.as_view(), name="login"),
    path("refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
]

