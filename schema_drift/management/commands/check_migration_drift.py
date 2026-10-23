import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import connection

from schema_drift.drift import find_migration_drift


class Command(BaseCommand):
    help = (
        'Apply every migration to a scratch database and print the drift windows '
        'that SCHEMA_DRIFT_BASELINE does not list, in its format. '
        'Migrations run for real, RunPython included.'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            '--update-baseline', action='store_true',
            help='Rewrite SCHEMA_DRIFT_BASELINE to list the observed windows, keeping its comments.',
        )

    def handle(self, *args: Any, update_baseline: bool, **options: Any) -> None:
        path = getattr(settings, 'SCHEMA_DRIFT_BASELINE', None)
        if path:
            path = Path(path)
        elif update_baseline:
            raise CommandError('--update-baseline needs SCHEMA_DRIFT_BASELINE.')
        lines = path.read_text().splitlines() if path and path.exists() else []
        baseline = {line for line in lines if line and not line.startswith('#')}
        new, stale = [], set(baseline)
        with scratch_database():
            for line in find_migration_drift():
                if line in baseline:
                    stale.discard(line)
                else:
                    new.append(line)
                    self.stdout.write(line)
        for line in sorted(stale):
            self.stderr.write(f'no longer observed: {line}')

        if update_baseline:
            path.write_text(''.join(f'{line}\n' for line in lines + new if line not in stale))
            return
        problems = []
        if new:
            problems.append('Migrations open drift windows the baseline does not list.')
        if stale:
            problems.append('The baseline lists windows that migrations no longer open.')
        if problems:
            raise CommandError(' '.join(problems))


@contextlib.contextmanager
def scratch_database() -> Iterator[None]:
    """Point the connection at a new database next to the configured one, and drop it afterwards.

    A scratch schema would be lighter, but extensions installed in `public` would be off its search path.
    """
    name = connection.settings_dict['NAME']
    scratch = f'{name}_migration_drift'
    quoted = connection.ops.quote_name(scratch)
    # Django's test database creation connects the same way, to the server's maintenance database.
    with connection._nodb_cursor() as cursor:
        cursor.execute(f'DROP DATABASE IF EXISTS {quoted}')
        cursor.execute(f'CREATE DATABASE {quoted}')
    connection.close()
    connection.settings_dict['NAME'] = scratch
    try:
        yield
    finally:
        connection.close()
        connection.settings_dict['NAME'] = name
        with connection._nodb_cursor() as cursor:
            cursor.execute(f'DROP DATABASE {quoted}')
