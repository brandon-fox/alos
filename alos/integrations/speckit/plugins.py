"""Plugin registry and event hook dispatching for SpecKit integration plugins."""

from typing import Any, Callable, Dict, List, Optional


class SpecKitPluginRegistry:
    """Registry for registering and dispatching SpecKit lifecycle and archiving plugin hooks."""

    _instance: Optional["SpecKitPluginRegistry"] = None

    def __init__(self) -> None:
        self._hooks: Dict[str, List[Callable[..., Any]]] = {
            "pre_lifecycle_transition": [],
            "on_lifecycle_transition": [],
            "post_lifecycle_transition": [],
            "pre_archive": [],
            "on_archive": [],
            "post_archive": [],
            "pre_restore": [],
            "post_restore": [],
        }

    @classmethod
    def get_instance(cls) -> "SpecKitPluginRegistry":
        """Get or initialize singleton instance of SpecKitPluginRegistry."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for testing)."""
        cls._instance = None

    def register_hook(self, event_name: str, callback: Callable[..., Any]) -> None:
        """Register a callback function for a given event hook.

        Args:
            event_name: The event hook name.
            callback: Callable hook function.
        """
        if event_name not in self._hooks:
            self._hooks[event_name] = []
        if callback not in self._hooks[event_name]:
            self._hooks[event_name].append(callback)

    def dispatch_event(self, event_name: str, **kwargs: Any) -> List[Any]:
        """Dispatch event to all registered plugin hooks for event_name.

        Args:
            event_name: Name of the event hook to trigger.
            **kwargs: Event parameters passed to callback functions.

        Returns:
            List of results returned by invoked callbacks.
        """
        results: List[Any] = []
        if event_name in self._hooks:
            for callback in self._hooks[event_name]:
                res = callback(**kwargs)
                results.append(res)
        return results

    def list_hooks(self) -> Dict[str, int]:
        """List registered hook counts per event name."""
        return {event: len(callbacks) for event, callbacks in self._hooks.items()}
