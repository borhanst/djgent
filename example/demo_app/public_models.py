from djgent import register_public_model

from .models import Author, Book


register_public_model(
    Author,
    fields=["id", "name", "country"],
)
register_public_model(
    Book,
    fields=["id", "title", "genre", "published_year", "author"],
)
