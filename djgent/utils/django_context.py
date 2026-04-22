"""Django context helper for passing request/user data to LangChain tools."""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class DjangoContext:
    """
    Django request/user context for LangChain tools.

    This dataclass is passed to tools via ToolRuntime.context to provide
    access to Django's request and user objects.

    Attributes:
        user: Django user object (can be AnonymousUser)
        user_id: User ID (None for anonymous users)
        username: Username (None for anonymous users)
        is_authenticated: True if user is authenticated
        is_staff: True if user is a staff member
        is_superuser: True if user is a superuser
        session_key: Session key if available
        request: Full Django request object (optional)
    """

    user: Optional[Any] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    is_authenticated: bool = False
    is_staff: bool = False
    is_superuser: bool = False
    session_key: Optional[str] = None
    request: Optional[Any] = None
    conversation: Optional[Any] = None

    @classmethod
    def from_request(cls, request: Any) -> "DjangoContext":
        """
        Create DjangoContext from a Django HttpRequest object.

        Args:
            request: Django HttpRequest object with user attribute

        Returns:
            DjangoContext instance populated from the request
        """
        user = getattr(request, "user", None)

        return cls(
            user=user,
            user_id=user.id if user and hasattr(user, "id") and user.is_authenticated else None,
            username=user.get_username() if user and hasattr(user, "get_username") else None,
            is_authenticated=user.is_authenticated if user else False,
            is_staff=user.is_staff if user else False,
            is_superuser=user.is_superuser if user else False,
            session_key=(
                request.session.session_key
                if hasattr(request, "session") and request.session
                else None
            ),
            request=request,
        )

    @classmethod
    def from_user(cls, user: Any) -> "DjangoContext":
        """
        Create DjangoContext from a Django User object.

        Args:
            user: Django User or AnonymousUser object

        Returns:
            DjangoContext instance populated from the user
        """
        return cls(
            user=user,
            user_id=user.id if hasattr(user, "id") and user.is_authenticated else None,
            username=user.get_username() if user and hasattr(user, "get_username") else None,
            is_authenticated=user.is_authenticated if user else False,
            is_staff=user.is_staff if user else False,
            is_superuser=user.is_superuser if user else False,
        )

    def to_dict(self) -> dict:
        """
        Convert DjangoContext to a dictionary (safe for logging/serialization).

        Note: Does NOT include the user or request objects to avoid
        serialization issues and leaking sensitive data.

        Returns:
            Dictionary with safe context information
        """
        return {
            "user_id": self.user_id,
            "username": self.username,
            "is_authenticated": self.is_authenticated,
            "is_staff": self.is_staff,
            "is_superuser": self.is_superuser,
            "session_key": self.session_key,
        }

    def __str__(self) -> str:
        """String representation for debugging."""
        if self.is_authenticated:
            return f"DjangoContext(user={self.username}, id={self.user_id})"
        else:
            return "DjangoContext(anonymous)"
