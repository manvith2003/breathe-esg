"""Signal handlers for core app."""
from django.db.models.signals import post_save


def create_user_profile(sender, instance, created, **kwargs):
    """
    We don't auto-create a profile here because we need an Organization assigned.
    Profile is created explicitly during user registration or admin creation.
    """
    pass
