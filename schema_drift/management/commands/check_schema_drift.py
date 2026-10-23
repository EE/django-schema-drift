from typing import Any

from django.core.management.base import BaseCommand, CommandError

from schema_drift.drift import find_drift


class Command(BaseCommand):
    help = (
        'Compare the database schema with the one the models would create. '
        '"-" lines are only in the models, "+" lines only in the database; '
        'an index or constraint line ends with its name.'
    )

    def handle(self, *args: Any, **options: Any) -> None:
        only_in_models, only_in_database = find_drift()
        lines = [(line, '-', name) for line, name in only_in_models.items()]
        lines += [(line, '+', name) for line, name in only_in_database.items()]
        # Sorted by line, so both sides of a changed column or index print next to each other.
        for line, side, name in sorted(lines):
            self.stdout.write(f'{side} {line}' + (f'  -- {name}' if name else ''))
        if lines:
            raise CommandError('The database schema has drifted from the models.')
