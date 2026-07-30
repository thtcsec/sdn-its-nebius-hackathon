"""Reconstruction-error timeline plots."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence


def plot_re_timeline(re_scores: Sequence[float], tau: float, out: Optional[str] = None):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(re_scores, label="RE")
    ax.axhline(tau, color="r", linestyle="--", label=f"tau={tau:.2f}")
    ax.set_xlabel("Window")
    ax.set_ylabel("Reconstruction Error")
    ax.legend()
    fig.tight_layout()
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=150)
    return fig
