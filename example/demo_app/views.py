from django.shortcuts import render

from demo_app.models import Author, Book


def home(request):
    return render(
        request,
        "demo_app/home.html",
        {
            "featured_books": Book.objects.select_related("author")[:4],
            "authors": Author.objects.all()[:4],
        },
    )
