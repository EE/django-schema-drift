from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.loader import MigrationLoader

from schema_drift.drift import find_drift


class Command(BaseCommand):
    help = (
        'Compare the database schema with the one the migrations it has applied would create. '
        '"-" lines are only in the migrations, "+" lines only in the database.'
    )

    def handle(self, *args: Any, **options: Any) -> None:
        loader = MigrationLoader(connection)
        # `django_migrations` also lists migrations since deleted or replaced by a squash, which the graph lacks.
        applied = [key for key in loader.applied_migrations if key in loader.graph.nodes]
        only_in_migrations, only_in_database = find_drift(loader.project_state(applied).apps)
        lines = [(line, '-') for line in only_in_migrations] + [(line, '+') for line in only_in_database]
        # Sorted by line, so both sides of a changed column or index print next to each other.
        for line, side in sorted(lines):
            self.stdout.write(f'{side} {line}')
        if lines:
            raise CommandError('The database schema has drifted from its migrations.')
