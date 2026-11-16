"""Typed workflow failures, recorded on the execution so people know what to do next.

Every message here is safe to store and show: provider details never reach it.
"""

import logging

logger = logging.getLogger(__name__)


class AIUnavailableError(RuntimeError):
    """The AI provider stayed unavailable through every automatic retry."""


class AIInvestigationError(RuntimeError):
    """The AI call failed permanently or returned output that failed validation."""


# code -> (retryable by a person, user-facing explanation)
FAILURE_CODES = {
    "AI_UNAVAILABLE": (True, "The AI service is temporarily unavailable. Retrying later usually works."),
    "AI_FAILED": (True, "The AI investigation did not produce a valid result."),
    "INTERRUPTED": (True, "The run was interrupted before this step finished, for example by a restart."),
    "UNEXPECTED": (True, "An unexpected error stopped this step."),
    # Business-rule failures are deterministic; retrying cannot change the outcome.
    "STEP_FAILED": (False, "This step cannot complete with the current workflow or data."),
}


def describe_failure(exc: Exception) -> tuple[str, str]:
    """Return (code, message) for an exception raised while running a step."""
    if isinstance(exc, AIUnavailableError):
        return "AI_UNAVAILABLE", str(exc)
    if isinstance(exc, AIInvestigationError):
        return "AI_FAILED", str(exc)
    if isinstance(exc, ValueError):
        # Raised deliberately by the engine with safe, specific messages.
        return "STEP_FAILED", str(exc)
    # Unknown errors (database, programming) may contain internals: log the class only.
    logger.error("workflow_step_unexpected_error", extra={"error_type": type(exc).__name__})
    return "UNEXPECTED", FAILURE_CODES["UNEXPECTED"][1]


def failure_context(code: str, message: str, failed_step: str | None) -> dict:
    return {"error": message, "error_code": code, "failed_step": failed_step,
            "retryable": FAILURE_CODES[code][0]}
