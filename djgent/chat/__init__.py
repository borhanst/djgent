"""Built-in chat UI for Djgent."""

__all__ = ["BaseChatView", "ConfiguredChatView"]


def __getattr__(name):
    if name in __all__:
        from djgent.chat.views import BaseChatView, ConfiguredChatView

        return {
            "BaseChatView": BaseChatView,
            "ConfiguredChatView": ConfiguredChatView,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
