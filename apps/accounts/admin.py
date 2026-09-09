from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class UserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Portal QuIIN", {"fields": ("nome",)}),)
    list_display = ("username", "nome", "email", "is_active", "is_staff")
