"""AURA-NSE Pro Verdict Generator.

Enforces strict institutional wording rules:
- The word 'edge' may appear ONLY when the 95% bootstrap confidence interval lower bound is strictly > 0.
- When CI lower bound <= 0, verdict explicitly states confidence interval spans zero and edge is not confirmed.
"""

from __future__ import annotations


def generate_verdict_wording(ci_lower: float, ci_upper: float, mean_r: float) -> str:
    """Generate verdict wording strictly bounded by statistical confidence interval."""
    if ci_lower > 0.0:
        return (
            f"Statistically significant edge confirmed (+{mean_r:.2f} R, "
            f"95% week-block bootstrap CI [{ci_lower:.2f}, {ci_upper:.2f}] R > 0)."
        )
    elif mean_r > 0.0:
        return (
            f"Positive sample mean (+{mean_r:.2f} R), but confidence interval spans zero "
            f"(lower bound {ci_lower:.2f} <= 0); edge not statistically confirmed."
        )
    else:
        return (
            f"Zero or negative sample mean ({mean_r:.2f} R, "
            f"95% CI [{ci_lower:.2f}, {ci_upper:.2f}] R); no statistical advantage."
        )
