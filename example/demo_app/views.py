from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView

from demo_app.models import Author, Book
from djgent import drf_tool


def home(request):
    return render(
        request,
        "demo_app/home.html",
        {
            "featured_books": Book.objects.select_related("author")[:4],
            "authors": Author.objects.all()[:4],
        },
    )


@drf_tool(
    name="featured_books_api",
    description="List featured demo books through a DRF view.",
    method="GET",
    path="/api/books/featured/",
)
class FeaturedBooksAPIView(APIView):
    def get(self, request):
        raw_limit = request.query_params.get("limit", 5)
        try:
            limit = max(1, min(int(raw_limit), 20))
        except (TypeError, ValueError):
            limit = 5

        books = Book.objects.select_related("author").filter(is_featured=True)[
            :limit
        ]
        return Response(
            [
                {
                    "id": book.id,
                    "title": book.title,
                    "author": book.author.name,
                    "published_year": book.published_year,
                }
                for book in books
            ]
        )
