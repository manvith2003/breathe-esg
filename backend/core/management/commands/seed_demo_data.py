"""
Management command: seed_demo_data

Creates a demo organization, two users (admin + analyst), loads emission factor
fixtures, and uploads all three sample data files to demonstrate the full pipeline.

Usage:
    python manage.py seed_demo_data
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core import serializers
from core.models import Organization, UserProfile


class Command(BaseCommand):
    help = 'Seed demo organization, users, and emission factors'

    def handle(self, *args, **options):
        self.stdout.write('Seeding demo data...')

        # ── Organization ──────────────────────────────────────────────────
        org, created = Organization.objects.get_or_create(
            slug='acme-corp',
            defaults={'name': 'Acme Corporation'}
        )
        if created:
            self.stdout.write(f'  Created organization: {org.name}')
        else:
            self.stdout.write(f'  Organization exists: {org.name}')

        # ── Admin user ────────────────────────────────────────────────────
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@acme-corp.com',
                'first_name': 'Admin',
                'last_name': 'User',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin_user.set_password('breatheesg2024')
            admin_user.save()
            self.stdout.write('  Created admin user (password: breatheesg2024)')
        UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={'organization': org, 'role': UserProfile.Role.ADMIN}
        )

        # ── Analyst user ──────────────────────────────────────────────────
        analyst_user, created = User.objects.get_or_create(
            username='analyst',
            defaults={
                'email': 'analyst@acme-corp.com',
                'first_name': 'Sarah',
                'last_name': 'Chen',
            }
        )
        if created:
            analyst_user.set_password('breatheesg2024')
            analyst_user.save()
            self.stdout.write('  Created analyst user (password: breatheesg2024)')
        UserProfile.objects.get_or_create(
            user=analyst_user,
            defaults={'organization': org, 'role': UserProfile.Role.ANALYST}
        )

        # ── Load emission factor fixtures ─────────────────────────────────
        from django.core.management import call_command
        call_command('loaddata', 'emission_factors', verbosity=0)
        self.stdout.write('  Loaded emission factors (DEFRA 2023)')

        # ── Process sample data files ─────────────────────────────────────
        sample_dir = os.path.join(
            os.path.dirname(__file__), '..', '..', '..', '..', 'sample_data'
        )
        sample_dir = os.path.abspath(sample_dir)

        files = [
            ('sap_fuel_procurement.csv', 'SAP_FUEL'),
            ('utility_electricity.csv', 'UTILITY'),
            ('concur_travel.csv', 'TRAVEL'),
        ]

        from ingestion.models import IngestionBatch
        from ingestion.services import process_batch

        for fname, source_type in files:
            fpath = os.path.join(sample_dir, fname)
            if not os.path.exists(fpath):
                self.stdout.write(self.style.WARNING(f'  Sample file not found: {fpath}'))
                continue

            # Skip if already ingested
            if IngestionBatch.objects.filter(
                organization=org, file_name=fname
            ).exists():
                self.stdout.write(f'  Already ingested: {fname}')
                continue

            batch = IngestionBatch.objects.create(
                organization=org,
                source_type=source_type,
                file_name=fname,
                uploaded_by=admin_user,
            )

            with open(fpath, 'rb') as f:
                content = f.read()

            batch = process_batch(batch, content)
            self.stdout.write(
                f'  Processed {fname}: {batch.row_count} rows, '
                f'{batch.error_count} errors, {batch.warning_count} warnings'
            )

        self.stdout.write(self.style.SUCCESS('\nDemo data seeded successfully!'))
        self.stdout.write('Login credentials:')
        self.stdout.write('  Admin:   admin / breatheesg2024')
        self.stdout.write('  Analyst: analyst / breatheesg2024')
