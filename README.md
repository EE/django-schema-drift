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
It is safe on a production database: everything it creates is rolled back,
though it needs the privilege to create a schema.
It gives up after waiting 2 s for a lock, rather than hold up the queries queued behind it.
Index and constraint names are compared only where `Meta` gives them, since migrations drop those by name;
Django finds the rest by their columns, so their names drift harmlessly.
Collations, comments, triggers, functions and views are not compared.

Accept a known difference by listing its line, without the sign, in `SCHEMA_DRIFT_IGNORE`:

```python
SCHEMA_DRIFT_IGNORE = {
    'index myapp_article USING btree (slug varchar_pattern_ops)',
}
```

A test that runs `schema_drift.drift.find_drift()` on your test database,
which is built by migrations, fails CI when migrations leave the final schema wrong.

## Check every migration

A migration that leaves the schema wrong can be hidden by a later one that puts it right:
the final schema is fine, and a database that stops in between is not.

```bash
./manage.py check_migration_drift
```

applies every migration to a scratch database it creates beside the configured one and drops afterwards,
so it needs the privilege to create a database,
and after each compares the database with the migration state at that point.
It runs them as `migrate` would, `RunPython` included,
so run it with settings whose caches, storage and mail are not production's.
It prints drift as windows:

```
myapp.0002_add_isbn -> myapp.0003_fix_isbn - column myapp_book.isbn character varying(20) NOT NULL
```

means a database with `0002` applied and `0003` not differs from its migration state by that line.
`end` as the closer means no migration closes the window.

Built-in operations drift too, so every migration is compared:
a migration that creates a foreign key and makes it one-to-one, as a squash can,
keeps the key's index, because Django creates that index only at the end of the migration.

Moving a model between apps takes a migration in each app, so correct history opens windows too,
each closed by the migration that completes the move.
Accept them in a baseline file, one window per line, `#` for comments:

```python
SCHEMA_DRIFT_BASELINE = BASE_DIR / 'schema_drift_baseline.txt'
```

The command fails on windows the baseline does not list, printing them in its format,
and on baseline lines it no longer observes.

```bash
./manage.py check_migration_drift --update-baseline
```

adds the new windows to the baseline and drops the stale lines, keeping comments.
Review what you accept: a window whose ends belong to two different moves
means a database between them is broken in a way nothing else will show.

Migrations that do not depend on each other can be applied in more than one order;
the check follows the one Django's own `migrate` picks.

## What to run when

Your databases come from two histories.
Fresh ones (tests, CI, review apps) run today's migration files;
deployed ones ran the files that existed when each migration was new, and maybe a fix made by hand.
`check_migration_drift` checks the first, `check_schema_drift` run on a deployed database the second.

### In CI and before pushing

The `find_drift()` test costs one schema build;
`check_migration_drift` also catches what a later migration hides, and takes longer on a long history.
Run it locally after writing a `RunSQL` or `SeparateDatabaseAndState`, or moving a model between apps:
these are where the database and the state part.

### When squashing

A squash merges a create with the alters that follow it,
and can build a different schema while `makemigrations --check` stays green,
as the one-to-one example above does.
Check both histories:

- On a database migrated with the old files, check out the squash:
  `migrate` has nothing to apply, and `check_schema_drift` prints nothing.
- On an empty database, `check_migration_drift` passes,
  and `--update-baseline` drops the windows the squash folded away.

### On a deployed database

Run `check_schema_drift` on production and staging, and again before a squash.
It finds what CI cannot: a fix made by hand, an index nobody dropped,
a foreign key a `RunSQL` re-added without `DEFERRABLE INITIALLY DEFERRED`.
Fix each with a migration or list it in `SCHEMA_DRIFT_IGNORE`.
A squash builds what the models say,
so a difference left in production stays one against every fresh database.

Without access to the server, replay its history:
migrate a scratch database at a commit from before any squash, check out today's code, migrate,
and run `check_schema_drift`.
That finds what the history left, though not what was done by hand.

## Development

```bash
poetry install
poetry run pytest
```

needs a PostgreSQL server; `POSTGRES_HOST`, `POSTGRES_USER` and `POSTGRES_PASSWORD` point at it.
