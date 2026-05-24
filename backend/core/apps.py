"""Core app config."""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Create UserProfile automatically when a new User is created
        from django.db.models.signals import post_save
        from django.contrib.auth.models import User
        from .signals import create_user_profile
        post_save.connect(create_user_profile, sender=User)
