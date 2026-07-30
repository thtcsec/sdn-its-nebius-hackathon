"""Simple topology summary figure for docs/notebooks."""

from __future__ import annotations

from pathlib import Path


def plot_topology_summary(out: str | None = None):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    nodes = {"s1": (0.5, 0.7), "s2": (0.2, 0.4), "s3": (0.8, 0.4), "s4": (0.5, 0.15)}
    for name, (x, y) in nodes.items():
        ax.scatter([x], [y], s=400)
        ax.text(x, y, name, ha="center", va="center", color="white", fontsize=9)
    for a, b in [("s1", "s2"), ("s1", "s3"), ("s1", "s4")]:
        ax.plot([nodes[a][0], nodes[b][0]], [nodes[a][1], nodes[b][1]], "k-", alpha=0.4)
    ax.set_axis_off()
    ax.set_title("ITS Edge Topology (s1–s4)")
    fig.tight_layout()
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=150)
    return fig
