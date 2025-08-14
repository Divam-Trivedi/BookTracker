from django.db import models
from django.contrib.auth.models import User

class Book(models.Model):
    google_books_id = models.CharField(max_length=200, unique=True)
    title = models.CharField(max_length=200)
    authors = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    cover_url = models.URLField(blank=True)
    categories = models.CharField(max_length=200, blank=True)
    thumbnail = models.URLField(blank=True)

    def __str__(self):
        return self.title

class UserLibrary(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    STATUS_CHOICES = [
        ('unread', 'Unread'),
        ('read', 'Read'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='unread')

    def __str__(self):
        return f"{self.user.username} - {self.book.title} ({self.status})"

class UserBook(models.Model):
    STATUS_CHOICES = [
        ('unread', 'Unread'),
        ('reading', 'Reading'),
        ('read', 'Read'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='unread')

    def __str__(self):
        return f"{self.book.title} - {self.status}"