from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('testapp', '0002_book_isbn_too_short')]

    operations = [
        migrations.RunSQL('ALTER TABLE testapp_book ALTER COLUMN isbn TYPE varchar(20)'),
    ]
