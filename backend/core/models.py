"""
Core models: Organization (tenant) and UserProfile.

Multi-tenancy strategy: Shared Database, Shared Schema with an `organization`
FK on every data model. This is simpler than django-tenants for a prototype and
still enforces logical isolation at the ORM/view layer.
"""
import uuid
from django.db import models
from django.contrib.auth.models import User


class Organization(models.Model):
    """
    Represents a client company (tenant). Every data record is scoped to one org.
    In production we'd migrate to per-schema isolation via django-tenants.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """Extends Django User with org membership and role."""

    class Role(models.TextChoices):
        ANALYST = 'ANALYST', 'Analyst'
        ADMIN = 'ADMIN', 'Admin'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='members'
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ANALYST)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.organization.slug}) [{self.role}]"
