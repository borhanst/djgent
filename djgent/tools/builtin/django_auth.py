"""Authentication check tool for verifying user login status."""

import json
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.utils.encoding import force_str
from django.utils.functional import Promise

from djgent.tools.base import Tool


class DjangoAuthTool(Tool):
    """
    Check user authentication and authorization status.

    Actions:
    - check_auth: Check if a user is authenticated
    - get_user: Get current user details
    - check_permission: Check if user has a specific permission
    - check_group: Check if user belongs to a specific group
    - list_permissions: List all available permissions
    - list_groups: List all available groups

    Authentication:
    - check_auth, list_permissions, list_groups: Available to anonymous users
    - get_user, check_permission, check_group: Require authenticated user
    
    Note: When used with Django request context (via ToolRuntime), the tool
    automatically uses request.user. Otherwise, provide user_id or session_key.
    """

    name = "django_auth"
    description = """
    Check Django user authentication and authorization. Actions:
    - check_auth: Check authentication status (anonymous OK)
    - get_user: Get current user details (requires authentication)
    - check_permission: Check user permission (requires authentication)
    - check_group: Check user group membership (requires authentication)
    - list_permissions: List all permissions (anonymous OK)
    - list_groups: List all groups (anonymous OK)

    When used with Django request context, automatically uses request.user.
    Anonymous users can check their own auth status and list permissions/groups.
    """
    risk_level = "medium"
    requires_approval = True
    approval_reason = "Authentication tools can reveal account and permission data."

    # Actions that require authentication
    REQUIRE_AUTH_ACTIONS = ["get_user", "check_permission", "check_group"]
    ALLOW_ANONYMOUS_ACTIONS = ["check_auth", "list_permissions", "list_groups"]

    def _run(
        self,
        action: str,
        user_id: Optional[int] = None,
        session_key: Optional[str] = None,
        permission: Optional[str] = None,
        group: Optional[str] = None,
        app_label: Optional[str] = None,
        runtime: Optional[Any] = None,  # ToolRuntime - hidden from LLM
    ) -> str:
        """
        Execute the authentication check action.

        Args:
            action: The action to perform
            user_id: User ID for direct user lookup
            session_key: Session key for session-based lookup
            permission: Permission codename (e.g., "auth.view_user")
            group: Group name to check membership
            app_label: App label filter for permissions list
            runtime: LangChain ToolRuntime (provides Django context) - hidden from LLM

        Returns:
            JSON-formatted string with results
        """
        valid_actions = [
            "check_auth",
            "get_user",
            "check_permission",
            "check_group",
            "list_permissions",
            "list_groups",
        ]

        if action not in valid_actions:
            return self._error_response(
                f"Invalid action '{action}'. Valid actions: {valid_actions}"
            )

        # Check authentication requirement
        if action in self.REQUIRE_AUTH_ACTIONS:
            if not self._check_authenticated(runtime):
                # Also check if user_id was explicitly provided
                if not user_id and not session_key:
                    return self._error_response(
                        "Authentication required. Please log in to access this feature. "
                        "Anonymous users can use: check_auth, list_permissions, list_groups"
                    )

        try:
            if action == "list_permissions":
                return self._list_permissions(app_label=app_label)
            elif action == "list_groups":
                return self._list_groups()
            elif action == "check_auth":
                # check_auth is special - can be called by anonymous users
                # to check their own auth status
                return self._check_auth(
                    user_id=user_id,
                    session_key=session_key,
                    runtime=runtime,
                )
            else:
                # Actions that require user identification
                # Priority: runtime context > user_id > session_key
                if runtime and self._check_authenticated(runtime):
                    # Use user from runtime context
                    user = self._get_user(runtime)
                    if user:
                        user_id = user.id

                if not user_id and not session_key:
                    return self._error_response(
                        "user_id or session_key is required for this action"
                    )

                if action == "get_user":
                    return self._get_user_details(user_id=user_id, session_key=session_key, runtime=runtime)
                elif action == "check_permission":
                    if not permission:
                        return self._error_response(
                            "permission is required for check_permission action"
                        )
                    return self._check_permission(
                        user_id=user_id,
                        session_key=session_key,
                        permission=permission,
                        runtime=runtime,
                    )
                elif action == "check_group":
                    if not group:
                        return self._error_response(
                            "group is required for check_group action"
                        )
                    return self._check_group(
                        user_id=user_id,
                        session_key=session_key,
                        group=group,
                        runtime=runtime,
                    )

        except Exception as e:
            return self._error_response(str(e))

        return self._error_response("Unknown action")

    def _get_user_from_session(self, session_key: str) -> Optional[Any]:
        """Get user from session key."""
        from django.contrib.sessions.models import Session
        from django.utils import timezone

        try:
            session = Session.objects.filter(
                session_key=session_key,
                expire_date__gt=timezone.now()
            ).first()

            if not session:
                return None

            # Get user_id from session data
            session_data = session.get_decoded()
            user_id = session_data.get('_auth_user_id')

            if not user_id:
                return None

            from django.contrib.auth import get_user_model
            User = get_user_model()
            return User.objects.get(pk=user_id)

        except Exception:
            return None

    def _get_user_by_id(self, user_id: int) -> Optional[Any]:
        """Get user by ID."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            return User.objects.get(pk=user_id)
        except Exception:
            return None

    def _check_auth(
        self,
        user_id: Optional[int] = None,
        session_key: Optional[str] = None,
        runtime: Optional[Any] = None,
    ) -> str:
        """Check if user is authenticated."""
        user = None
        is_auth = False

        # Priority: runtime context > user_id > session_key
        if runtime:
            # Check if we have Django context with authenticated user
            django_ctx = self._get_django_context(runtime)
            if django_ctx:
                is_auth = getattr(django_ctx, 'is_authenticated', False)
                user = getattr(django_ctx, 'user', None)
        
        # Fallback to user_id or session_key if no runtime context
        if not user and session_key:
            user = self._get_user_from_session(session_key)
            is_auth = user.is_authenticated if user else False
        elif not user and user_id:
            user = self._get_user_by_id(user_id)
            is_auth = user.is_authenticated if user else False

        if not user or not is_auth:
            response = {
                "action": "check_auth",
                "authenticated": False,
                "message": "Anonymous user - not authenticated",
            }
        else:
            response = {
                "action": "check_auth",
                "authenticated": True,
                "user_id": user.id,
                "username": user.get_username(),
                "is_active": user.is_active,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            }

        return json.dumps(response, indent=2, cls=DjangoAuthJSONEncoder)

    def _get_user_details(
        self,
        user_id: Optional[int] = None,
        session_key: Optional[str] = None,
        runtime: Optional[Any] = None,
    ) -> str:
        """Get user details."""
        user = None

        # Priority: runtime context > user_id > session_key
        if runtime:
            django_ctx = self._get_django_context(runtime)
            if django_ctx and getattr(django_ctx, 'is_authenticated', False):
                user = getattr(django_ctx, 'user', None)
                # Ensure user is not a string
                if isinstance(user, str):
                    user = None

        if not user and session_key:
            user = self._get_user_from_session(session_key)
        elif not user and user_id:
            user = self._get_user_by_id(user_id)

        if not user:
            return self._error_response("User not found or session expired")

        # Get configured user fields from settings
        user_fields = self._get_user_fields_config()

        # Build user data based on configured fields
        user_data = {}
        for field in user_fields:
            if field == "full_name":
                # Special handling for full_name (computed field)
                first = getattr(user, "first_name", "")
                last = getattr(user, "last_name", "")
                user_data["full_name"] = f"{first} {last}".strip() or None
            elif field == "username":
                user_data["username"] = user.get_username()
            elif hasattr(user, field):
                value = getattr(user, field)
                # Handle special types
                if hasattr(value, "isoformat"):  # datetime
                    user_data[field] = value.isoformat()
                elif isinstance(value, (list, dict)):  # JSONField
                    user_data[field] = value
                elif isinstance(value, (bool, int, str, type(None))):
                    user_data[field] = value
                else:
                    user_data[field] = str(value)

        response = {
            "action": "get_user",
            "success": True,
            "user": user_data,
        }

        return json.dumps(response, indent=2, cls=DjangoAuthJSONEncoder)

    def _get_user_fields_config(self) -> list:
        """
        Get configured user fields from Django settings.
        
        Returns:
            List of field names to include in get_user response
        """
        from django.conf import settings
        
        djgent_settings = getattr(settings, "DJGENT", {})
        user_fields = djgent_settings.get("USER_FIELDS", ["first_name", "last_name", "full_name"])
        
        # Ensure we always have at least some fields
        if not user_fields:
            return ["first_name", "last_name", "full_name"]
        
        return user_fields

    def _check_permission(
        self,
        user_id: Optional[int] = None,
        session_key: Optional[str] = None,
        permission: Optional[str] = None,
        runtime: Optional[Any] = None,
    ) -> str:
        """Check if user has a specific permission."""
        user = None

        # Priority: runtime context > user_id > session_key
        if runtime and self._check_authenticated(runtime):
            user = self._get_user(runtime)
        elif session_key:
            user = self._get_user_from_session(session_key)
        elif user_id:
            user = self._get_user_by_id(user_id)

        if not user:
            return self._error_response("User not found or session expired")

        has_perm = user.has_perm(permission) if permission else False

        response = {
            "action": "check_permission",
            "user_id": user.id if user else None,
            "permission": permission,
            "has_permission": has_perm,
        }

        return json.dumps(response, indent=2, cls=DjangoAuthJSONEncoder)

    def _check_group(
        self,
        user_id: Optional[int] = None,
        session_key: Optional[str] = None,
        group: Optional[str] = None,
        runtime: Optional[Any] = None,
    ) -> str:
        """Check if user belongs to a specific group."""
        user = None

        # Priority: runtime context > user_id > session_key
        if runtime and self._check_authenticated(runtime):
            user = self._get_user(runtime)
        elif session_key:
            user = self._get_user_from_session(session_key)
        elif user_id:
            user = self._get_user_by_id(user_id)

        if not user:
            return self._error_response("User not found or session expired")

        in_group = user.groups.filter(name=group).exists() if group else False

        response = {
            "action": "check_group",
            "user_id": user.id if user else None,
            "group": group,
            "in_group": in_group,
        }

        return json.dumps(response, indent=2, cls=DjangoAuthJSONEncoder)

    def _list_permissions(self, app_label: Optional[str] = None) -> str:
        """List all available permissions."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        permissions_qs = Permission.objects.all()

        if app_label:
            permissions_qs = permissions_qs.filter(
                content_type__app_label=app_label
            )

        permissions_list = []
        for perm in permissions_qs.select_related("content_type"):
            permissions_list.append({
                "codename": perm.codename,
                "name": perm.name,
                "app_label": perm.content_type.app_label,
                "model": perm.content_type.model,
            })

        response = {
            "action": "list_permissions",
            "count": len(permissions_list),
            "app_filter": app_label,
            "permissions": permissions_list,
        }

        return json.dumps(response, indent=2, cls=DjangoAuthJSONEncoder)

    def _list_groups(self) -> str:
        """List all available groups."""
        from django.contrib.auth.models import Group

        groups_list = []
        for group in Group.objects.all():
            groups_list.append({
                "id": group.id,
                "name": group.name,
            })

        response = {
            "action": "list_groups",
            "count": len(groups_list),
            "groups": groups_list,
        }

        return json.dumps(response, indent=2, cls=DjangoAuthJSONEncoder)

    def _error_response(self, error: str) -> str:
        """Format an error response."""
        return json.dumps({
            "success": False,
            "error": error,
        }, indent=2, cls=DjangoAuthJSONEncoder)


class DjangoAuthJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for Django auth tool."""

    def default(self, obj):
        if isinstance(obj, Promise):
            return force_str(obj)
        return super().default(obj)
