"""Compare the database schema with the schema the models would create.

`makemigrations --check` proves the models agree with migration state;
this proves the database does too,
which a `SeparateDatabaseAndState` with mismatched halves, a stray `RunSQL` or a hand fix breaks.
The schema editor builds every model in a scratch schema,
both schemas are flattened into comparable lines,
and the scratch schema is rolled back with the transaction.

Index and constraint names are compared only where `Meta` gives them, since migrations drop those by name;
Django finds the rest by their columns, so their names drift harmlessly.
Accepted differences go to `settings.SCHEMA_DRIFT_IGNORE`, spelled as `check_schema_drift` prints them.
"""
import contextlib
import re
import sys
from collections import Counter
from collections.abc import Iterator

from django.apps import apps as installed_apps
from django.apps.registry import Apps
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import DatabaseError, connection, transaction
from django.db.backends.utils import CursorWrapper
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.db.migrations.state import ProjectState


REFERENCE_SCHEMA = 'schema_drift_reference'
# The snapshot locks every table it reads, and a foreign key to an unmanaged model locks its live table.
# Waiting for a lock would queue the application's queries behind the check.
LOCK_TIMEOUT = '2s'


def find_drift(apps: Apps = installed_apps) -> tuple[set[str], set[str]]:
    """Return the schema lines only the models in `apps` have, and those only the database has."""
    models = [model for model in apps.get_models() if model._meta.can_migrate(connection)]
    names = [named.name for model in models for named in [*model._meta.indexes, *model._meta.constraints]]
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'")
        cursor.execute('SELECT current_schema()')
        [(live_schema,)] = cursor.fetchall()
        live = _snapshot(cursor, live_schema, names)

        cursor.execute(f'CREATE SCHEMA {REFERENCE_SCHEMA}')
        # Snapshots render a schema's own objects unqualified only while it leads the search path;
        # the rest of the path stays for the extension types and operator classes it holds.
        cursor.execute(
            f"SELECT set_config('search_path', '{REFERENCE_SCHEMA}, ' || current_setting('search_path'), true)",
        )
        # Collected and run as one batch, which is faster than a round trip per statement.
        with connection.schema_editor(collect_sql=True, atomic=False) as editor:
            editor.create_model(MigrationRecorder.Migration)
            for model in models:
                editor.create_model(model)
            # A foreign key needs the key it references, which can be a deferred `unique_together`
            # of a model created after it.
            editor.deferred_sql.sort(key=lambda sql: 'FOREIGN KEY' in str(sql))
        cursor.execute('\n'.join(editor.collected_sql))
        reference = _snapshot(cursor, REFERENCE_SCHEMA, names)

        transaction.set_rollback(True)

    ignored = set(getattr(settings, 'SCHEMA_DRIFT_IGNORE', ()))
    return reference - live - ignored, live - reference - ignored


def find_migration_drift() -> Iterator[str]:
    """Apply every migration to an empty database, comparing it after each with the migration state.

    Yields `<opener> -> <closer> <side> <line>`:
    a database with `opener` applied and `closer` not differs from its migration state by that line,
    `-` for a line only the state has, `+` for one only the database has.
    `end` as the closer means no migration closes it.
    """
    executor = MigrationExecutor(connection)
    if connection.introspection.table_names():
        raise RuntimeError('find_migration_drift migrates the database, so it needs an empty one.')
    state = ProjectState(real_apps=executor.loader.unmigrated_apps)
    opened: dict[tuple[str, str], str] = {}
    for migration, _ in executor.migration_plan(executor.loader.graph.leaf_nodes(), clean_start=True):
        # Data migrations print progress; stdout is for the drift.
        with contextlib.redirect_stdout(sys.stderr):
            state = executor.apply_migration(state, migration)
        name = f'{migration.app_label}.{migration.name}'
        try:
            only_in_state, only_in_database = find_drift(state.apps)
        except (FieldDoesNotExist, DatabaseError) as error:
            yield f'{name} cannot be built: {str(error).splitlines()[0]}'
            continue
        drift = {('-', line) for line in only_in_state} | {('+', line) for line in only_in_database}
        for side, line in sorted(opened.keys() - drift):
            yield f'{opened.pop((side, line))} -> {name} {side} {line}'
        for key in sorted(drift - opened.keys()):
            opened[key] = name
    for (side, line), opener in sorted(opened.items()):
        yield f'{opener} -> end {side} {line}'


def _snapshot(cursor: CursorWrapper, schema: str, names: list[str]) -> set[str]:
    """Flatten a schema into one line per table, column, constraint and index, as Postgres renders them.

    Only the index and constraint names in `names` are spelled out; a repeated line gets `(copy n)`.
    """
    cursor.execute(
        """
        SELECT 'table ' || c.relname
        FROM pg_class c
        WHERE c.relnamespace = %(schema)s::regnamespace AND c.relkind IN ('r', 'p')

        UNION ALL
        SELECT 'column ' || c.relname || '.' || a.attname || ' ' || format_type(a.atttypid, a.atttypmod)
            || CASE WHEN a.attnotnull THEN ' NOT NULL' ELSE '' END
            || CASE a.attidentity WHEN 'a' THEN ' GENERATED ALWAYS AS IDENTITY'
                                  WHEN 'd' THEN ' GENERATED BY DEFAULT AS IDENTITY' ELSE '' END
            || CASE WHEN a.attgenerated = 's' THEN ' GENERATED ALWAYS AS ' || pg_get_expr(d.adbin, d.adrelid)
                    WHEN d.adbin IS NOT NULL THEN ' DEFAULT ' || pg_get_expr(d.adbin, d.adrelid) ELSE '' END
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE c.relnamespace = %(schema)s::regnamespace AND c.relkind IN ('r', 'p')
            AND a.attnum > 0 AND NOT a.attisdropped

        UNION ALL
        SELECT 'constraint ' || c.relname
            || CASE WHEN con.conname = ANY(%(names)s) THEN '.' || con.conname ELSE '' END
            || ' ' || pg_get_constraintdef(con.oid)
        FROM pg_constraint con
        JOIN pg_class c ON c.oid = con.conrelid
        -- NOT NULL is a column property above; Postgres 18 also lists it as a constraint.
        WHERE c.relnamespace = %(schema)s::regnamespace AND con.contype <> 'n'

        UNION ALL
        SELECT 'index ' || c.relname
            || CASE WHEN ic.relname = ANY(%(names)s) THEN '.' || ic.relname ELSE '' END
            || ' ' || pg_get_indexdef(i.indexrelid)
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_class ic ON ic.oid = i.indexrelid
        WHERE c.relnamespace = %(schema)s::regnamespace
            -- An index backing a primary key, unique or exclusion constraint is that constraint.
            AND NOT EXISTS (
                SELECT 1 FROM pg_constraint con
                WHERE con.conindid = i.indexrelid AND con.conrelid = i.indrelid
                    AND con.contype IN ('p', 'u', 'x')
            )
        """,
        {'schema': schema, 'names': names},
    )
    return {
        f'{line} (copy {n})' if n > 1 else line
        for line, count in Counter(_drop_index_name(line) for (line,) in cursor.fetchall()).items()
        for n in range(1, count + 1)
    }


def _drop_index_name(line: str) -> str:
    """`index t CREATE UNIQUE INDEX n ON s.t USING ...` -> `index t UNIQUE USING ...`."""
    return re.sub(r'^(index \S+ )CREATE (UNIQUE )?INDEX \S+ ON (ONLY )?\S+ ', r'\1\2', line)
