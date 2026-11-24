"""Ring 1 (Hexagonal Domain): Pure business entities, value objects, and policies.

Inward-only boundary: modules in ``alos.domain`` may import only Python
standard library modules, ``pydantic``, and ``alos.domain`` itself. Zero
filesystem, database, network, or infrastructure dependencies are permitted.
"""

__all__: list[str] = []
