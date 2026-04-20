"""Pytest configuration and fixtures for djgent tests."""

from __future__ import annotations

import os
import sys
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import django
import pytest
from django.conf import settings

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
EXAMPLE_DIR = os.path.join(ROOT_DIR, "example")
if EXAMPLE_DIR not in sys.path:
    sys.path.insert(0, EXAMPLE_DIR)

# Configure Django settings for testing
if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
            'django.contrib.sessions',
            'django.contrib.staticfiles',
            'djgent',
            'djgent.chat',
            'demo_app',
        ],
        MIDDLEWARE=[
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
        ],
        TEMPLATES=[
            {
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'DIRS': [],
                'APP_DIRS': True,
                'OPTIONS': {
                    'context_processors': [
                        'django.template.context_processors.request',
                    ],
                },
            }
        ],
        STATIC_URL='/static/',
        USE_TZ=True,
        SECRET_KEY='test-secret-key-for-testing-only',
        LOGGING={
            'version': 1,
            'disable_existing_loggers': False,
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                },
            },
            'root': {
                'handlers': ['console'],
                'level': 'INFO',
            },
        },
    )

django.setup()


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create a mock LLM for testing."""
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="Test response")
    llm.bind_tools.return_value = llm
    return llm


@pytest.fixture
def mock_tool() -> MagicMock:
    """Create a mock tool for testing."""
    tool = MagicMock()
    tool.name = "mock_tool"
    tool.description = "A mock tool for testing"
    tool.risk_level = "low"
    tool.requires_approval = False
    tool._run.return_value = "Tool execution result"
    return tool


@pytest.fixture
def sample_messages() -> list:
    """Create sample messages for testing."""
    from langchain_core.messages import HumanMessage, AIMessage
    return [
        HumanMessage(content="Hello"),
        AIMessage(content="Hi there!"),
    ]


@pytest.fixture
def agent_kwargs() -> dict:
    """Create common agent kwargs for testing."""
    return {
        "name": "test_agent",
        "memory": False,
        "system_prompt": "You are a helpful assistant.",
    }


@pytest.fixture
def django_user(db) -> Any:
    """Create a Django user for testing."""
    from django.contrib.auth.models import User
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def mock_django_context() -> dict:
    """Create a mock Django context for tool runtime."""
    from dataclasses import dataclass
    from typing import Optional
    
    @dataclass
    class MockUser:
        id: int = 1
        username: str = "testuser"
        is_authenticated: bool = True
        
    @dataclass  
    class MockDjangoContext:
        user: MockUser
        is_authenticated: bool = True
        request: Optional[Any] = None
        
    return {
        "django": MockDjangoContext(user=MockUser())
    }
