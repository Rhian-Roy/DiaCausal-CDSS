"""Pass-through stubs for what is not built yet (the list is in diacausal/registry.py: `stubs()`).

A stub changes nothing and CHECKS nothing; it says so in the trace ("... layer is a STUB: nothing was checked") so a
pass-through is never mistaken for a check that ran. When the real one lands, change one line in the registry.
"""

from __future__ import annotations

from diacausal.orchestrator.context import Context
from diacausal.tracing import stub_notice


def shap_drivers(ctx: Context) -> dict:
    """P25: SHAP drivers of each option's estimate. Today: none."""
    stub_notice("shap drivers", ctx.request_id)
    return {}
