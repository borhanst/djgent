import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent

load_dotenv(BASE_DIR / ".env")
load_dotenv(REPO_ROOT / ".env")

SECRET_KEY = "django-insecure-djgent-test-project-key"
DEBUG = True
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "djgent",
    "djgent.chat",
    "demo_app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "test_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "test_project.wsgi.application"
ASGI_APPLICATION = "test_project.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DJGENT = {
    "DEFAULT_LLM": os.environ.get("DJGENT_DEFAULT_LLM", "ollama:llama3.2"),
    "API_KEYS": {
        # "OPENAI": os.environ.get("OPENAI_API_KEY", ""),
        # "ANTHROPIC": os.environ.get("ANTHROPIC_API_KEY", ""),
        # "GOOGLE": os.environ.get("GOOGLE_API_KEY", ""),
        # "GROQ": os.environ.get("GROQ_API_KEY", ""),
        "OPENROUTER": os.environ.get("OPENROUTER_API_KEY", ""),
    },
    "BUILTIN_TOOLS": ["calculator", "datetime"],
    "AUTO_DISCOVER_TOOLS": True,
    "MEMORY_ENABLED": True,
    "CHAT_UI": {
        "BUBBLE_ENABLED": True,
        "BUBBLE_TITLE": "Ask Djgent",
        "TITLE": "Djgent Chat",
        "TOOLS": ["calculator", "datetime"],
        "SYSTEM_PROMPT": (
            "You are the Djgent demo assistant. Use book_query for questions "
            "about demo books, authors, genres, or publication years."
        ),
    },
    "MODEL_QUERY_TOOL": {
        "ENABLED": False,
        "ALLOWED_MODELS": [
            "demo_app.Book",
            "demo_app.Author",
        ],
        "EXCLUDED_MODELS": [],
        "DEFAULT_LIMIT": 10,
        "MAX_RESULTS": 100,
        "EXCLUDE_FIELDS": [],
        "ALLOWED_FIELDS": {},
    },
    "PUBLIC_MODELS": {
        "demo_app.Book": ["id", "title", "genre", "published_year", "author"],
        "demo_app.Author": ["id", "name", "country"],
    },
    "AUDIT": {
        "ENABLED": True,
        "LOG_LEVEL": "INFO",

    }
}
