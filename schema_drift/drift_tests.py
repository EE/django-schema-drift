import pytest
from django.db import OperationalError, connection, connections

from schema_drift import drift
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
    """The final schema is right, but a database stopped after 0002 or 0005 is not.

    0005 has only built-in operations.
    """
    assert list(find_migration_drift()) == [
        'testapp.0002_book_isbn_too_short -> testapp.0003_book_isbn_repair '
        '+ column testapp_book.isbn character varying(10) NOT NULL',
        'testapp.0002_book_isbn_too_short -> testapp.0003_book_isbn_repair '
        '- column testapp_book.isbn character varying(20) NOT NULL',
        'testapp.0005_review_squashed -> testapp.0006_review_drop_leftover_index '
        '+ index testapp_review USING btree (book_id)',
    ]


@pytest.mark.django_db(transaction=True)
def test_gives_up_on_a_locked_table_instead_of_queueing(monkeypatch):
    monkeypatch.setattr(drift, 'LOCK_TIMEOUT', '100ms')
    other = connections.create_connection('default')
    with other.cursor() as cursor:
        # Releases the lock if the check waits for it after all, so the test fails instead of hanging.
        cursor.execute("SET idle_in_transaction_session_timeout = '10s'")
        cursor.execute('BEGIN; LOCK testapp_book')

        with pytest.raises(OperationalError, match='lock timeout'):
            find_drift()
    other.close()


@pytest.mark.django_db
def test_refuses_to_replay_migrations_on_a_database_with_tables():
    with pytest.raises(RuntimeError, match='needs an empty one'):
        list(find_migration_drift())
