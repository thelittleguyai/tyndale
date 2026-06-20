"""SourceRegistry — maps each interface (DL-68) to its adapter(s).

CO-12A ships SINGLE-ADAPTER PASSTHROUGH: each interface has exactly one adapter
and ``resolve()`` returns it. The internal shape (a priority-ranked list) is here
so registering a second adapter later is a ``register_adapter()`` call, not a
rewrite — at which point ``resolve()`` / BenefitsContext gain precedence +
cross-validation (CO-12B). Modeled on the multi-source precedence already shipped
in knowledge/cost_estimation.py.
"""

from __future__ import annotations

from typing import Any

import structlog

log = structlog.get_logger(__name__)


class SourceRegistry:
    def __init__(self) -> None:
        # interface Protocol type -> [(priority, adapter)], highest priority first.
        self._adapters: dict[type, list[tuple[int, Any]]] = {}

    def register_adapter(self, interface: type, adapter: Any, priority: int = 0) -> None:
        """Register ``adapter`` as an implementation of ``interface``.

        ``interface`` is one of the runtime_checkable Protocols in base.py, so we
        can sanity-check the adapter structurally exposes the interface methods."""
        if isinstance(interface, type) and not isinstance(adapter, interface):
            log.warning(
                "sources.adapter_missing_interface_methods",
                interface=getattr(interface, "__name__", str(interface)),
                adapter=type(adapter).__name__,
            )
        self._adapters.setdefault(interface, []).append((priority, adapter))
        self._adapters[interface].sort(key=lambda pa: pa[0], reverse=True)

    def resolve(self, interface: type) -> Any:
        entries = self._adapters.get(interface)
        if not entries:
            raise LookupError(
                f"no adapter registered for {getattr(interface, '__name__', interface)}"
            )
        # SINGLE-ADAPTER PASSTHROUGH (CO-12A): return the highest-priority adapter.
        # TODO(CO-12B): when len(entries) > 1, cross-validate across adapters and
        # merge with precedence (see knowledge/cost_estimation.py) rather than
        # returning only the top one.
        return entries[0][1]

    def adapters_for(self, interface: type) -> list[Any]:
        """All registered adapters for an interface (diagnostics / future n>1)."""
        return [adapter for _, adapter in self._adapters.get(interface, [])]
