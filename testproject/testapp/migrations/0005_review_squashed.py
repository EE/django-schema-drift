from django.db import migrations, models


class Migration(migrations.Migration):
    """Creates a foreign key and makes it one-to-one, as a squash can, which leaves the key's index behind.

    The index is created only at the end of the migration, so `AlterField` finds none to drop;
    0006 drops it.
    """

    dependencies = [('testapp', '0004_book_named_index_and_constraint')]

    operations = [
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('book', models.ForeignKey(on_delete=models.deletion.CASCADE, to='testapp.book')),
            ],
        ),
        migrations.AlterField(
            'review', 'book', models.OneToOneField(on_delete=models.deletion.CASCADE, to='testapp.book'),
        ),
    ]
