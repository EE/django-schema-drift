from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=100)


class Book(models.Model):
    author = models.ForeignKey(to=Author, on_delete=models.CASCADE)
    isbn = models.CharField(max_length=20)

    class Meta:
        indexes = [models.Index(fields=['isbn'], name='book_isbn_idx')]
        constraints = [models.UniqueConstraint(fields=['author', 'isbn'], name='book_author_isbn_uniq')]


class Review(models.Model):
    book = models.OneToOneField(to=Book, on_delete=models.CASCADE)
