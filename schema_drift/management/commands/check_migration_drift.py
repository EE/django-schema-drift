from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from schema_drift.drift import find_migration_drift


class Command(BaseCommand):
    help = (
        'Apply every migration to an empty database and print the drift windows '
        'that SCHEMA_DRIFT_BASELINE does not list, in its format. '
        'Migrations run for real, RunPython included.'
    )

    def handle(self, *args: Any, **options: Any) -> None:
        path = getattr(settings, 'SCHEMA_DRIFT_BASELINE', None)
        baseline = {
            line for line in (Path(path).read_text().splitlines() if path else [])
            if line and not line.startswith('#')
        }
        observed = set()
        for line in find_migration_drift():
            observed.add(line)
            if line not in baseline:
                self.stdout.write(line)
        for line in sorted(baseline - observed):
            self.stderr.write(f'no longer observed: {line}')
        if observed != baseline:
            raise CommandError('Migrations open drift windows the baseline does not list.')
