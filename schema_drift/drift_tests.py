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
def test_reports_a_renamed_index_or_constraint_only_if_migrations_name_it():
    """Migrations drop `Meta` indexes and constraints by name, and find the rest by their columns."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'testapp_book'")
        for (name,) in cursor.fetchall():
            cursor.execute(f'ALTER INDEX {name} RENAME TO {name}_by_hand')

    assert find_drift() == (
        {
            'constraint testapp_book.book_author_isbn_uniq UNIQUE (author_id, isbn)',
            'index testapp_book.book_isbn_idx USING btree (isbn)',
        },
        {
            'constraint testapp_book UNIQUE (author_id, isbn)',
            'index testapp_book USING btree (isbn)',
        },
    )


@pytest.mark.django_db
def test_reports_a_duplicate_index():
    with connection.cursor() as cursor:
        cursor.execute('CREATE INDEX ON testapp_book (author_id)')

    assert find_drift() == (set(), {'index testapp_book USING btree (author_id) (copy 2)'})


@pytest.mark.django_db
def test_reports_drift_a_later_migration_hides(empty_schema):
    """The final schema is right, but a database stopped after 0002 is not."""
    assert list(find_migration_drift()) == [
        'testapp.0002_book_isbn_too_short -> testapp.0003_book_isbn_repair '
        '+ column testapp_book.isbn character varying(10) NOT NULL',
        'testapp.0002_book_isbn_too_short -> testapp.0003_book_isbn_repair '
        '- column testapp_book.isbn character varying(20) NOT NULL',
    ]
