"""Core app admin registration."""
from django.contrib import admin
from .models import Organization, UserProfile


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization', 'role', 'created_at')
    list_filter = ('organization', 'role')
