import pytest
from django.db import connection

from schema_drift.drift import find_drift, find_migration_drift


@pytest.mark.django_db
def test_migrated_database_matches_the_models():
    assert find_drift() == (set(), set())


@pytest.mark.django_db
def test_reports_a_column_changed_outside_migrations():
    with connection.cursor() as cursor:
        cursor.execute('ALTER TABLE testapp_author ALTER COLUMN name TYPE text')

    assert find_drift() == (
        {'column testapp_author.name character varying(100) NOT NULL'},
        {'column testapp_author.name text NOT NULL'},
    )


@pytest.mark.django_db
def test_reports_drift_a_later_migration_hides(empty_schema):
    """The final schema is right, but a database stopped after 0002 is not."""
    assert list(find_migration_drift()) == [
        'testapp.0002_book_isbn_too_short -> testapp.0003_book_isbn_repair '
        '+ column testapp_book.isbn character varying(10) NOT NULL',
        'testapp.0002_book_isbn_too_short -> testapp.0003_book_isbn_repair '
        '- column testapp_book.isbn character varying(20) NOT NULL',
    ]
