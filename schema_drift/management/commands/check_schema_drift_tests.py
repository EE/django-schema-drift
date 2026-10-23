import io

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_compares_with_the_migrations_the_database_has_applied(empty_schema):
    """The models have the tables 0005 creates, which a database stopped at 0004 rightly lacks."""
    call_command('migrate', 'testapp', '0004', verbosity=0)

    call_command('check_schema_drift', stdout=io.StringIO())
