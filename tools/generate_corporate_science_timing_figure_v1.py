from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

OUT = Path("technovation_package")
OUT.mkdir(exist_ok=True)

# Conceptual schematic only: relative timing is shown in event time, not a fitted empirical trajectory.
fig, ax = plt.subplots(figsize=(10.5, 4.8))

# Main timeline
ax.axhline(0, linewidth=1.4)

# Positions in relative conceptual time
x_emerge = 0
x_frontier = 3
x_early_end = 5
x_later = 8

ax.scatter([x_emerge, x_frontier, x_early_end, x_later], [0, 0, 0, 0], s=55, zorder=3)

# Early window and analysis windows
ax.axvspan(x_frontier, x_early_end, alpha=0.13)
ax.axvspan(x_frontier - 2.3, x_frontier - 0.3, alpha=0.08)
ax.axvspan(x_frontier + 0.3, x_frontier + 3.3, alpha=0.08)

ax.text(x_emerge, 0.30, "Global topic\nemergence", ha="center", va="bottom", fontsize=10)
ax.text(x_frontier, 0.30, "First linked corporate entry\n(observed frontier)", ha="center", va="bottom", fontsize=10)
ax.text(x_early_end, 0.30, "End of primary\nearly-entry window", ha="center", va="bottom", fontsize=10)
ax.text(x_later, 0.30, "Example later\nlinked entrant", ha="center", va="bottom", fontsize=10)

ax.annotate(
    "Early = entry 0–2 years after observed frontier",
    xy=((x_frontier + x_early_end) / 2, -0.05),
    xytext=((x_frontier + x_early_end) / 2, -0.75),
    ha="center",
    arrowprops={"arrowstyle": "-[,widthB=6.5,lengthB=0.7", "lw": 1.0},
    fontsize=10,
)

ax.text(x_frontier - 1.3, -1.42, "Pre-entry network window\nt−3 to t−1", ha="center", va="center", fontsize=9)
ax.text(x_frontier + 1.8, -1.42, "Primary post-entry outcome window\nt+1 to t+3", ha="center", va="center", fontsize=9)

ax.text(
    4.2,
    1.25,
    "Entry timing is sample-relative: the frontier is the earliest entry among linked firms,\nnot a claim to identify the first corporation worldwide.",
    ha="center",
    va="center",
    fontsize=9.5,
)

ax.set_xlim(-1.2, 9.4)
ax.set_ylim(-1.9, 1.7)
ax.set_yticks([])
ax.set_xticks([x_emerge, x_frontier, x_early_end, x_later])
ax.set_xticklabels(["Emergence", "Frontier / t", "t+2", "Later entry"])
ax.set_xlabel("Conceptual event time within one scientific topic")
ax.set_title("Research design: global emergence and relative corporate scientific entry")
for spine in ["left", "right", "top"]:
    ax.spines[spine].set_visible(False)

fig.tight_layout()
fig.savefig(OUT / "FIGURE_1_RESEARCH_DESIGN_TIMING.png", dpi=300, bbox_inches="tight")
plt.close(fig)
print(OUT / "FIGURE_1_RESEARCH_DESIGN_TIMING.png")
