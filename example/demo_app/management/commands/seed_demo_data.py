from django.core.management.base import BaseCommand

from demo_app.models import Author, Book


class Command(BaseCommand):
    help = "Seed demo authors and books for djgent testing."

    def handle(self, *args, **options):
        authors = [
            {"name": "Ursula K. Le Guin", "country": "United States"},
            {"name": "Haruki Murakami", "country": "Japan"},
            {"name": "Chinua Achebe", "country": "Nigeria"},
        ]

        books = [
            {
                "title": "A Wizard of Earthsea",
                "genre": "Fantasy",
                "published_year": 1968,
                "author": "Ursula K. Le Guin",
                "is_featured": True,
            },
            {
                "title": "Kafka on the Shore",
                "genre": "Magical Realism",
                "published_year": 2002,
                "author": "Haruki Murakami",
                "is_featured": True,
            },
            {
                "title": "Things Fall Apart",
                "genre": "Historical Fiction",
                "published_year": 1958,
                "author": "Chinua Achebe",
                "is_featured": False,
            },
        ]

        author_map = {}
        for item in authors:
            author, _ = Author.objects.get_or_create(
                name=item["name"],
                defaults={"country": item["country"]},
            )
            author_map[author.name] = author

        for item in books:
            Book.objects.get_or_create(
                title=item["title"],
                defaults={
                    "genre": item["genre"],
                    "published_year": item["published_year"],
                    "author": author_map[item["author"]],
                    "is_featured": item["is_featured"],
                },
            )

        self.stdout.write(self.style.SUCCESS("Seeded demo_app authors and books."))
