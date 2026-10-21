from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('testapp', '0005_review_squashed')]

    operations = [
        migrations.RunSQL('DROP INDEX testapp_review_book_id_0f464ac3'),
    ]
