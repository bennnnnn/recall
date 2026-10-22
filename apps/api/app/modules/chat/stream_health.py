"""What one turn's model stream tells model health: a sample for each model it tried."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.gateways.stream_signals import StreamAttempt
from app.services.model_health import HealthSample


@dataclass(frozen=True)
class StreamEnd:
    """How the turn's stream ended, as the pipeline saw it."""

    # The model the turn ended on (the one that answered, or the last one tried).
    model: str
    # A model sent at least one token.
    answered: bool
    # The model call itself failed (no model answered, or one failed partway).
    failed: bool
    # The user stopped the turn.
    stopped: bool
    elapsed_ms: float
    first_token_ms: float | None


def health_samples(attempts: Sequence[StreamAttempt], end: StreamEnd) -> list[HealthSample]:
    """A failed try is its own model's failure, whatever ended the turn; the model
    that answered is a success. A try the provider refused over the request (a
    4xx: too large, a policy) says nothing about the model, nor does a Stop:
    neither leaves a sample.

    A model call that reports no tries (the mock model, a test double) counts as
    one try by the turn's model.
    """
    if not attempts:
        failed = end.failed or (not end.answered and not end.stopped)
        attempts = [StreamAttempt(end.model, failed=failed)]
    samples: list[HealthSample] = []
    for attempt in attempts:
        if attempt.failed:
            if not attempt.model_failed:
                continue
            latency = _first(attempt.elapsed_ms, end.elapsed_ms)
            samples.append(HealthSample(attempt.alias, latency_ms=latency, success=False))
        elif not end.stopped:
            latency = _first(attempt.first_delta_ms, end.first_token_ms, end.elapsed_ms)
            samples.append(HealthSample(attempt.alias, latency_ms=latency, success=True))
    return samples


def _first(*values: float | None) -> float:
    """The first measured value (the last one is always measured)."""
    return next((value for value in values if value is not None), 0.0)
