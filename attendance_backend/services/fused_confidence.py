"""
fused_confidence.py — Weighted fusion of similarity + liveness + metadata risk
═══════════════════════════════════════════════════════════════════════════════
Formula
-------
    fused = w1·sim + w2·liveness + w3·(1 − risk_score)

All three component scores must be in [0, 1]:
  • sim         — cosine / dot-product embedding similarity from FAISS
  • liveness    — output from LivenessDetector.check().score
  • risk_score  — device / IP / time-of-day anomaly score (0 = safe, 1 = risky)

A fused score ≥ FUSED_MIN_CONFIDENCE is required to accept an identity claim.

Configuration (environment variables)
--------------------------------------
  FUSED_W_SIMILARITY   float  (default 0.50) — weight for embedding match
  FUSED_W_LIVENESS     float  (default 0.30) — weight for liveness score
  FUSED_W_METADATA     float  (default 0.20) — weight for (1 − risk_score)
  FUSED_MIN_CONFIDENCE float  (default 0.60) — minimum fused score to accept
  FUSED_REQUIRE_LIVENESS_MIN float (default 0.30) — hard floor: even if fused
                                  passes, liveness must clear this minimum to
                                  prevent a very high similarity from masking
                                  a spoofed frame.

Weights are re-normalised to sum to 1.0 at startup so misconfigured values
never silently produce out-of-range scores.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────────────
def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ[key])
    except (KeyError, ValueError):
        return default


@dataclass
class FusedConfidenceConfig:
    """
    Weights and thresholds for the fused confidence function.

    Loaded once from environment variables; pass an instance to
    `FusedConfidenceScorer` to override in tests or per-deployment.
    """

    w_similarity: float = field(
        default_factory=lambda: _env_float("FUSED_W_SIMILARITY", 0.50)
    )
    w_liveness: float = field(
        default_factory=lambda: _env_float("FUSED_W_LIVENESS", 0.30)
    )
    w_metadata: float = field(
        default_factory=lambda: _env_float("FUSED_W_METADATA", 0.20)
    )
    min_confidence: float = field(
        default_factory=lambda: _env_float("FUSED_MIN_CONFIDENCE", 0.60)
    )
    require_liveness_min: float = field(
        default_factory=lambda: _env_float("FUSED_REQUIRE_LIVENESS_MIN", 0.30)
    )

    def __post_init__(self) -> None:
        total = self.w_similarity + self.w_liveness + self.w_metadata
        if abs(total - 1.0) > 1e-6:
            logger.info(
                f"Fused confidence weights sum to {total:.4f}; re-normalising to 1.0."
            )
            self.w_similarity /= total
            self.w_liveness /= total
            self.w_metadata /= total

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"FusedConfidenceConfig("
            f"sim={self.w_similarity:.2f}, live={self.w_liveness:.2f}, "
            f"meta={self.w_metadata:.2f}, min={self.min_confidence:.2f}, "
            f"live_floor={self.require_liveness_min:.2f})"
        )


# ── Result ────────────────────────────────────────────────────────────────────
@dataclass
class FusedConfidenceResult:
    """Returned by `FusedConfidenceScorer.score`."""

    fused: float              # weighted composite score [0, 1]
    accepted: bool            # fused >= min_confidence AND liveness >= floor
    similarity: float         # raw input
    liveness: float           # raw input
    risk_score: float         # raw input
    reject_reason: Optional[str] = None  # set when accepted=False


# ── Scorer ────────────────────────────────────────────────────────────────────
class FusedConfidenceScorer:
    """
    Fused confidence scorer.

    Example
    -------
    >>> scorer = FusedConfidenceScorer()
    >>> result = scorer.score(similarity=0.82, liveness=0.75, risk_score=0.10)
    >>> result.accepted
    True
    >>> result.fused
    0.767  # 0.50*0.82 + 0.30*0.75 + 0.20*(1-0.10)
    """

    def __init__(self, config: Optional[FusedConfidenceConfig] = None) -> None:
        self.config = config or FusedConfidenceConfig()
        logger.debug(f"FusedConfidenceScorer initialised with {self.config!r}")

    # ── Core computation ──────────────────────────────────────────────────────
    def score(
        self,
        *,
        similarity: float,
        liveness: float,
        risk_score: float,
    ) -> FusedConfidenceResult:
        """
        Compute the fused confidence for one recognition attempt.

        Args:
            similarity:  Embedding cosine similarity (0–1, higher = better match).
            liveness:    Liveness score (0–1, higher = more likely real face).
            risk_score:  Metadata anomaly score (0–1, 0 = low risk, 1 = high risk).

        Returns:
            FusedConfidenceResult — check `.accepted` before proceeding.
        """
        cfg = self.config

        # Clamp inputs defensively
        sim = float(max(0.0, min(1.0, similarity)))
        live = float(max(0.0, min(1.0, liveness)))
        risk = float(max(0.0, min(1.0, risk_score)))

        fused = cfg.w_similarity * sim + cfg.w_liveness * live + cfg.w_metadata * (1.0 - risk)

        # Primary gate: fused score
        if fused < cfg.min_confidence:
            reason = (
                f"fused={fused:.3f} < min_confidence={cfg.min_confidence:.3f} "
                f"(sim={sim:.3f}, live={live:.3f}, risk={risk:.3f})"
            )
            logger.debug(f"Identity rejected — {reason}")
            return FusedConfidenceResult(
                fused=fused,
                accepted=False,
                similarity=sim,
                liveness=live,
                risk_score=risk,
                reject_reason=reason,
            )

        # Hard liveness floor — prevents high similarity from overriding a spoof
        if live < cfg.require_liveness_min:
            reason = (
                f"liveness={live:.3f} < floor={cfg.require_liveness_min:.3f} "
                f"(fused={fused:.3f} would have passed)"
            )
            logger.warning(f"Identity rejected on liveness floor — {reason}")
            return FusedConfidenceResult(
                fused=fused,
                accepted=False,
                similarity=sim,
                liveness=live,
                risk_score=risk,
                reject_reason=reason,
            )

        logger.debug(
            f"Identity accepted — fused={fused:.3f} "
            f"(sim={sim:.3f}, live={live:.3f}, risk={risk:.3f})"
        )
        return FusedConfidenceResult(
            fused=fused,
            accepted=True,
            similarity=sim,
            liveness=live,
            risk_score=risk,
        )

    # ── Convenience helpers ───────────────────────────────────────────────────
    def compute_risk_score(
        self,
        *,
        device_known: bool = True,
        ip_anomaly: float = 0.0,
        time_anomaly: float = 0.0,
        attempt_pressure: float = 0.0,
    ) -> float:
        """
        Combine multiple metadata signals into a single risk_score in [0, 1].

        Args:
            device_known:      True if the device fingerprint is recognised.
            ip_anomaly:        Anomaly score from IP/geolocation checks [0, 1].
            time_anomaly:      How far outside normal login hours this attempt is [0, 1].
            attempt_pressure:  Fraction of MAX_FACE_DETECTION_ATTEMPTS already used [0, 1].

        Returns:
            Composite risk_score [0, 1].
        """
        device_risk = 0.0 if device_known else 0.4

        # Equal-weight blend of the four signals
        risk = (
            0.30 * device_risk
            + 0.25 * ip_anomaly
            + 0.20 * time_anomaly
            + 0.25 * attempt_pressure
        )
        return float(min(1.0, risk))

    def attempt_pressure(self, current_count: int, max_attempts: int = 5) -> float:
        """
        Turn the current attempt counter into a pressure signal.

        Grows non-linearly — early attempts are trusted more than later ones.
        """
        if max_attempts <= 0:
            return 1.0
        ratio = current_count / max_attempts
        # Square to make the last attempts disproportionately costly
        return float(min(1.0, ratio ** 2))


# ── Module-level singleton ────────────────────────────────────────────────────
_scorer: Optional[FusedConfidenceScorer] = None


def get_fused_scorer(config: Optional[FusedConfidenceConfig] = None) -> FusedConfidenceScorer:
    """Return a shared `FusedConfidenceScorer` instance (lazy init)."""
    global _scorer
    if _scorer is None:
        _scorer = FusedConfidenceScorer(config)
    return _scorer