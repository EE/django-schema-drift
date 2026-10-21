from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=100)


class Book(models.Model):
    author = models.ForeignKey(to=Author, on_delete=models.CASCADE)
    isbn = models.CharField(max_length=20)
