# django-schema-drift

`makemigrations --check` proves your models agree with your migrations.
Nothing proves your database agrees with either:
a `SeparateDatabaseAndState` whose halves disagree, a `RunSQL` that does something its state does not say,
or a fix made by hand on a server all pass CI and surface later as a failing query.

This app lets Django build the schema your models describe in a scratch schema,
compares it with the real one table by table, column by column, constraint by constraint and index by index,
and rolls the scratch schema back.
PostgreSQL only.

## Install

Add `'schema_drift'` to `INSTALLED_APPS`.

## Check a database against the models

```bash
./manage.py check_schema_drift
```

prints one line per difference, `-` for what only the models have and `+` for what only the database has,
and exits non-zero if there is any.
It is safe on a production database: everything it creates is rolled back.
Index and constraint names are not compared, since renames leave old names behind harmlessly.

Accept a known difference by listing its line, without the sign, in `SCHEMA_DRIFT_IGNORE`:

```python
SCHEMA_DRIFT_IGNORE = {
    'index myapp_article USING btree (slug varchar_pattern_ops)',
}
```

A test that runs `schema_drift.drift.find_drift()` on your test database,
which is built by migrations, fails CI on any migration that leaves the schema wrong.

## Check every migration

A migration that leaves the schema wrong can be hidden by a later one that puts it right:
the final schema is fine, and a database that stops in between is not.

```bash
./manage.py check_migration_drift
```

applies every migration to an **empty** database (it refuses any other)
and after each compares the database with the migration state at that point.
It prints drift as windows:

```
myapp.0002_add_isbn -> myapp.0003_fix_isbn - column myapp_book.isbn character varying(20) NOT NULL
```

means a database with `0002` applied and `0003` not differs from its migration state by that line.
`end` as the closer means no migration closes the window.

Moving a model between apps takes a migration in each app, so correct history opens windows too,
each closed by the migration that completes the move.
Accept them in a baseline file, one window per line, `#` for comments:

```python
SCHEMA_DRIFT_BASELINE = BASE_DIR / 'schema_drift_baseline.txt'
```

The command prints windows in the baseline's format, so

```bash
./manage.py check_migration_drift >> schema_drift_baseline.txt
```

accepts everything it reports.
Review what you accept: a window whose ends belong to two different moves
means a database between them is broken in a way nothing else will show.

Migrations that do not depend on each other can be applied in more than one order;
the check follows the one Django's own `migrate` picks.

## Development

```bash
poetry install
poetry run pytest
```

needs a PostgreSQL server; `POSTGRES_HOST`, `POSTGRES_USER` and `POSTGRES_PASSWORD` point at it.
