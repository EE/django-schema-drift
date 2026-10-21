from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('testapp', '0003_book_isbn_repair')]

    operations = [
        migrations.AddIndex('book', models.Index(fields=['isbn'], name='book_isbn_idx')),
        migrations.AddConstraint(
            'book', models.UniqueConstraint(fields=['author', 'isbn'], name='book_author_isbn_uniq'),
        ),
    ]
