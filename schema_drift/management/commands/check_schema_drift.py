from typing import Any

from django.core.management.base import BaseCommand, CommandError

from schema_drift.drift import find_drift


class Command(BaseCommand):
    help = (
        'Compare the database schema with the one the models would create. '
        '"-" lines are only in the models, "+" lines only in the database.'
    )

    def handle(self, *args: Any, **options: Any) -> None:
        only_in_models, only_in_database = find_drift()
        lines = [(line, '-') for line in only_in_models] + [(line, '+') for line in only_in_database]
        # Sorted by line, so both sides of a changed column or index print next to each other.
        for line, side in sorted(lines):
            self.stdout.write(f'{side} {line}')
        if lines:
            raise CommandError('The database schema has drifted from the models.')
