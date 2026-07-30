"""Bar charts for accuracy / latency tables."""

from __future__ import annotations

from pathlib import Path


def plot_metric_bars(metrics: dict[str, float], title: str = "Metrics", out: str | None = None):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(list(metrics.keys()), list(metrics.values()))
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=150)
    return fig
