import io

import pytest
from django.core.management import CommandError, call_command
from django.db import connection


@pytest.mark.django_db
def test_printed_windows_are_a_baseline_that_passes(empty_schema, settings, tmp_path):
    out = io.StringIO()
    with pytest.raises(CommandError):
        call_command('check_migration_drift', stdout=out)

    with connection.cursor() as cursor:
        cursor.execute('DROP SCHEMA replay CASCADE; CREATE SCHEMA replay')
    baseline = tmp_path / 'baseline.txt'
    baseline.write_text('# accepted\n' + out.getvalue())
    settings.SCHEMA_DRIFT_BASELINE = baseline
    call_command('check_migration_drift', stdout=io.StringIO())
