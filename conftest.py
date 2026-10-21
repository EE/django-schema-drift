import pytest
from django.db import connection


@pytest.fixture
def empty_schema():
    """Point the connection at an empty schema, for checks that replay every migration."""
    with connection.cursor() as cursor:
        cursor.execute('CREATE SCHEMA replay')
        cursor.execute('SET LOCAL search_path TO replay')
