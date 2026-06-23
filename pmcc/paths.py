from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MonthPoint:
    spot_mult: float
    iv_mult: float


@dataclass(frozen=True)
class PlayPath:
    name: str
    label: str
    months: tuple[MonthPoint, ...]


def _months(*pairs: tuple[float, float]) -> tuple[MonthPoint, ...]:
    return tuple(MonthPoint(s, iv) for s, iv in pairs)


# ~13 monthly steps ≈ 390d; LEAPS typically ~364d at entry — sim trims last step at expiry.
CANONICAL_PATHS: tuple[PlayPath, ...] = (
    PlayPath(
        "crash_recover",
        "Crash −25% then slow recovery",
        _months(
            (1.00, 1.00), (0.82, 1.30), (0.75, 1.35), (0.78, 1.28), (0.82, 1.22),
            (0.86, 1.15), (0.90, 1.10), (0.94, 1.05), (0.98, 1.00), (1.02, 0.95),
            (1.06, 0.92), (1.10, 0.90), (1.12, 0.88),
        ),
    ),
    PlayPath(
        "steady_bear",
        "Steady grind down −20%",
        _months(
            (1.00, 1.00), (0.95, 1.08), (0.90, 1.12), (0.86, 1.15), (0.82, 1.18),
            (0.80, 1.20), (0.79, 1.18), (0.78, 1.15), (0.78, 1.12), (0.79, 1.10),
            (0.80, 1.08), (0.81, 1.05), (0.82, 1.02),
        ),
    ),
    PlayPath(
        "flat_chop",
        "Flat chop ±5%",
        _months(
            (1.00, 1.00), (1.03, 0.98), (0.97, 1.02), (1.02, 0.96), (0.98, 1.00),
            (1.04, 0.95), (0.96, 1.03), (1.01, 0.98), (0.99, 1.00), (1.03, 0.97),
            (0.97, 1.01), (1.00, 0.99), (1.01, 0.98),
        ),
    ),
    PlayPath(
        "steady_bull",
        "Steady bull +35%",
        _months(
            (1.00, 1.00), (1.04, 0.98), (1.08, 0.96), (1.12, 0.94), (1.16, 0.92),
            (1.20, 0.90), (1.24, 0.88), (1.28, 0.86), (1.30, 0.85), (1.32, 0.84),
            (1.33, 0.83), (1.34, 0.82), (1.35, 0.82),
        ),
    ),
    PlayPath(
        "rip_plateau",
        "Rip +55% in 4mo then plateau",
        _months(
            (1.00, 1.00), (1.10, 1.05), (1.22, 1.00), (1.38, 0.92), (1.55, 0.85),
            (1.52, 0.86), (1.50, 0.87), (1.48, 0.88), (1.47, 0.88), (1.46, 0.89),
            (1.45, 0.89), (1.44, 0.90), (1.43, 0.90),
        ),
    ),
    PlayPath(
        "v_recovery",
        "V-shape: −22% then rip to +40%",
        _months(
            (1.00, 1.00), (0.90, 1.15), (0.78, 1.32), (0.82, 1.25), (0.92, 1.10),
            (1.05, 0.95), (1.18, 0.88), (1.28, 0.84), (1.35, 0.82), (1.38, 0.80),
            (1.40, 0.80), (1.40, 0.79), (1.40, 0.78),
        ),
    ),
    PlayPath(
        "moonshot",
        "Extreme bull +90%",
        _months(
            (1.00, 1.00), (1.12, 1.02), (1.25, 0.95), (1.40, 0.88), (1.55, 0.82),
            (1.68, 0.78), (1.78, 0.75), (1.85, 0.72), (1.88, 0.70), (1.90, 0.70),
            (1.90, 0.69), (1.90, 0.68), (1.90, 0.68),
        ),
    ),
    PlayPath(
        "gap_whipsaw",
        "Rip+flush twice then flat (monthly steps)",
        _months(
            (1.00, 1.00), (1.02, 1.02), (1.10, 1.08), (1.04, 1.10), (1.03, 1.08),
            (1.02, 1.05), (1.11, 1.02), (1.06, 1.05), (1.05, 1.03), (1.04, 1.02),
            (1.03, 1.01), (1.02, 1.00), (1.02, 0.98),
        ),
    ),
)