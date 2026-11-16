"""Deterministic stand-in for Gemini, for browser end-to-end tests only.

Enabled with AI_PROVIDER=fake. Refused when APP_ENV=production, so it can
never replace the real model in a deployed system.

Behaviour:
  * Returns a fixed, schema-valid recommendation built from the invoice facts.
  * Invoice totals ending in .13 simulate a provider outage: the first three
    calls for that invoice raise a "503 high demand" error (exhausting the
    automatic retries), and later calls succeed. This lets tests exercise the
    "AI temporarily unavailable" panel and the Retry action end to end.
"""

import os
from collections import Counter

from app.core.security import is_production

_outage_calls: Counter = Counter()
OUTAGE_ATTEMPTS = 3


class FakeProviderUnavailable(Exception):
    code = 503  # Classified as transient by retry_policy.is_transient.


def fake_ai_enabled() -> bool:
    if os.environ.get("AI_PROVIDER", "gemini").strip().lower() != "fake":
        return False
    if is_production():
        raise RuntimeError("AI_PROVIDER=fake is not allowed when APP_ENV=production")
    return True


class FakeInvestigationGraph:
    def invoke(self, state):
        facts = state["invoice_facts"]
        if str(facts.get("invoice_amount", "")).endswith(".13"):
            key = facts.get("invoice_id")
            _outage_calls[key] += 1
            if _outage_calls[key] <= OUTAGE_ATTEMPTS:
                raise FakeProviderUnavailable("Simulated 503: model is experiencing high demand")
        pct = facts.get("validation", {}).get("discrepancy_percentage")
        return {"investigation": {
            "summary": f"Invoice differs from its purchase order by {pct}%." if pct is not None
                       else "Invoice does not match its purchase order.",
            "risk_level": "HIGH",
            "recommended_action": "REQUEST_CORRECTION",
            "reasoning": "Simulated investigation for automated tests. The discrepancy exceeds the 5% policy.",
            "requires_human_approval": True,
        }}


fake_graph = FakeInvestigationGraph()
