from django.db import migrations, models


class Migration(migrations.Migration):
    """Adds the column shorter than its state says, which 0003 repairs."""

    dependencies = [('testapp', '0001_initial')]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[migrations.AddField('book', 'isbn', models.CharField(max_length=20))],
            database_operations=[
                migrations.RunSQL('ALTER TABLE testapp_book ADD COLUMN isbn varchar(10) NOT NULL'),
            ],
        ),
    ]
