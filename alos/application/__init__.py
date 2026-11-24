"""Ring 2 (Hexagonal Application): Use cases and segregated CQRS port protocols.

Inward-only boundary: modules in ``alos.application`` may import only Python
standard library modules, ``pydantic``, ``alos.domain``, and
``alos.application``. Concrete infrastructure adapters must never be imported.
"""

__all__: list[str] = []
