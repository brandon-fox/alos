"""Strangler-Fig configuration shim delegating to Ring 4 ALOSSettings.

Preserves ``alos.core.config.ALOSConfig`` and all origin/main observability/SLO
fields while centralizing Factor III ``BaseSettings`` and ``.env`` resolution.
"""

from __future__ import annotations

from alos.config.settings import ALOSSettings


class ALOSConfig(ALOSSettings):
    """Backwards-compatible Strangler-Fig alias of ``ALOSSettings``."""


__all__ = ["ALOSConfig", "ALOSSettings"]
