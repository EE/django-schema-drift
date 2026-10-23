import io

import pytest
from django.core.management import CommandError, call_command
from django.db import connection


@pytest.mark.django_db(transaction=True)
def test_update_baseline_accepts_new_windows_and_drops_stale_ones(settings, tmp_path):
    """Runs beside the migrated test database, replaying into a scratch one it drops afterwards."""
    baseline = tmp_path / 'baseline.txt'
    baseline.write_text('# accepted\nstale.0001 -> stale.0002 + table gone\n')
    settings.SCHEMA_DRIFT_BASELINE = baseline
    quiet = {'stdout': io.StringIO(), 'stderr': io.StringIO()}
    with pytest.raises(CommandError, match='does not list.*no longer open'):
        call_command('check_migration_drift', **quiet)

    call_command('check_migration_drift', update_baseline=True, **quiet)

    assert baseline.read_text().startswith('# accepted\ntestapp.0002_book_isbn_too_short -> ')
    # Fails on a window the baseline lacks or a stale line it kept.
    call_command('check_migration_drift', **quiet)
    with connection.cursor() as cursor:
        cursor.execute("SELECT datname FROM pg_database WHERE datname LIKE '%%_migration_drift'")
        assert cursor.fetchall() == []
