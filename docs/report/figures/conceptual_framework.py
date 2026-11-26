"""Draws Figure 2.1, the conceptual framework. Run: python conceptual_framework.py"""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

plt.rcParams["font.family"] = "Times New Roman"
INK, LINE = "#1a1a1a", "#555555"
FILL = {"in": "#eef2f7", "mid": "#f7f3e9", "out": "#eaf4ec", "loop": "#f3f3f3", "theory": "#ffffff"}
TITLE, BODY = 7.2, 6.9

fig, ax = plt.subplots(figsize=(6.3, 4.15), dpi=300)
ax.set_xlim(-1, 101)
ax.set_ylim(6.5, 80.8)
ax.axis("off")


def box(x, y, w, h, title, body=None, fill="mid", size=TITLE):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=0.8",
                                fc=FILL[fill], ec=LINE, lw=0.7))
    if body:
        ax.text(x + w / 2, y + h - 1.6, title, ha="center", va="top", fontsize=size,
                fontweight="bold", color=INK)
        ax.text(x + w / 2, y + h - 5.4, body, ha="center", va="top", fontsize=BODY,
                color=INK, linespacing=1.15)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=size,
                color=INK, linespacing=1.15)


def arrow(a, b, dashed=False):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=6, lw=0.8, color=INK,
                                 linestyle=(0, (3, 2)) if dashed else "-", shrinkA=0, shrinkB=0))


def label(x, text):
    ax.text(x, 70.3, text, ha="center", va="center", fontsize=7, fontweight="bold", color=INK)


# Theory strip
box(0, 73.6, 49, 6.2,
    "Information asymmetry: paper records hold unused information\n"
    "(Akerlof, 1970; Stiglitz & Weiss, 1981)", fill="theory", size=6.8)
box(51, 73.6, 49, 6.2,
    "Behavioural credit use: repayment behaviour carries signal\n"
    "(Gross & Souleles, 2002; Laibson et al., 2007)", fill="theory", size=6.8)

label(9, "INPUT VARIABLES")
label(49.5, "PROCESSING VARIABLES")
label(91, "OUTPUT VARIABLES")

xs, W, H = (21, 41, 61), 17.5, 14.5
TOP, LOW = 52.5, 24

# Inputs
box(0, 52.5, 18, 14.5, "Ledger pages", "balances, repayments,\ninterest, due months,\ncontributions, loans", "in")
box(0, 38.5, 18, 11.5, "Officials' review", "corrected cells and\nmatched spellings", "in")
box(0, 24, 18, 11.5, "Chama rules", "loan terms and what\ncounts as a miss", "in")

# Processing, from the top row to the bottom row
box(xs[0], TOP, W, H, "1 Read and check", "vision model,\nflagged lines,\nhuman review")
box(xs[1], TOP, W, H, "2 Protect and load", "raw layers, names\nbecome codes, free\ntext left behind")
box(xs[2], TOP, W, H, "3 Clean and rebuild", "dbt tests, typed\nvalues, loans rebuilt\nfrom balances")
box(xs[0], LOW, W, H, "4 Build indicators", "behavioural and\nfinancial features,\npoint in time")
box(xs[1], LOW, W, H, "5 Train and validate", "three models, walk\nforward, members\nheld out, MLflow")
box(xs[2], LOW, W, H, "6 Score and explain", "registered model,\nbands by share,\nSHAP reasons")

# Outputs
box(82, 52.5, 18, 14.5, "Early-warning band", "Follow up now\nKeep an eye on\nLess likely to miss", "out")
box(82, 38.5, 18, 11.5, "Reasons", "top three factors\nin plain words", "out")
box(82, 24, 18, 11.5, "Officials decide", "the system suggests;\npeople lend", "out")

# Monitoring and feedback
box(xs[0], 8, 100 - xs[0], 6.5,
    "Monitoring and feedback: Evidently data drift reports, sprint reviews, usability sessions",
    fill="loop", size=7)

# Flow
arrow((18.7, 60), (20.6, 60))
arrow((18.7, 46), (20.6, 54))
arrow((18.7, 30), (20.6, 30))
arrow((xs[0] + W + 0.3, 60), (xs[1] - 0.3, 60))
arrow((xs[1] + W + 0.3, 60), (xs[2] - 0.3, 60))
ax.plot([xs[2] + W / 2, xs[2] + W / 2, xs[0] + W / 2], [52.2, 45.6, 45.6], color=INK, lw=0.8)
arrow((xs[0] + W / 2, 45.6), (xs[0] + W / 2, 38.9))
arrow((xs[0] + W + 0.3, 31), (xs[1] - 0.3, 31))
arrow((xs[1] + W + 0.3, 31), (xs[2] - 0.3, 31))
arrow((78.9, 35), (81.6, 54))
arrow((78.9, 32), (81.6, 42))
arrow((91, 52.2), (91, 50.4))
arrow((91, 38.2), (91, 35.9))

# Feedback, dashed
arrow((91, 23.7), (91, 14.9), dashed=True)
arrow((xs[0] + W / 2, 14.9), (xs[0] + W / 2, 23.7), dashed=True)
arrow((xs[1] + W / 2, 14.9), (xs[1] + W / 2, 23.7), dashed=True)

out = Path(__file__).with_name("figure_2_1_conceptual_framework.png")
fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.04, facecolor="white")
print(out)
