"""Drawing kit for the blue-white S2 figures.

Inline SVG presentation attributes only (Word/PowerPoint friendly).
Canvas width 1200 px; inserted at 15.5 cm, 24 px text prints at about 9 pt.
Run:  python docs/submission/s2-blue-figures/build_figures.py
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent / "svg"

FONT = "Microsoft YaHei, PingFang SC, Noto Sans SC, sans-serif"
MONO = "Consolas, Menlo, monospace"

NAVY = "#0B2E59"
BLUE = "#1F5FBF"
BLUE_MID = "#6E9BDB"
BLUE_SOFT = "#E8F0FC"
BLUE_PALE = "#F4F8FE"
LINE = "#C9D8EE"
INK = "#1B2533"
MUTED = "#5A6B82"
WHITE = "#FFFFFF"
RED = "#B42318"
RED_SOFT = "#FDECEA"


def _w(s: str, size: float) -> float:
    return sum(size * (1.0 if ord(c) > 0x2E80 else 0.56) for c in s)


class Svg:
    def __init__(self, w: int, h: int) -> None:
        self.w, self.h, self.parts = w, h, []

    def add(self, s: str) -> None:
        self.parts.append(s)

    def rect(self, x, y, w, h, fill=WHITE, stroke=LINE, sw=1.5, rx=10, dash=None):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}"{st}{d}/>')

    def text(self, x, y, s, size=24, weight=400, fill=INK, anchor="start", font=FONT):
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font}" font-size="{size}" '
                 f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>')

    def line(self, pts, color=BLUE_MID, sw=2, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.add(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linejoin="round"{d}/>')

    def arrow(self, pts, color=BLUE, sw=2.2, dash=None, size=8):
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        horiz = abs(x2 - x1) >= abs(y2 - y1)
        sgn = 1 if (x2 > x1 if horiz else y2 > y1) else -1
        end = (x2 - sgn * 1.5 * size, y2) if horiz else (x2, y2 - sgn * 1.5 * size)
        self.line(pts[:-1] + [end], color, sw, dash)
        s = size
        if horiz:
            tri = [(x2, y2), (x2 - sgn * 1.6 * s, y2 - s), (x2 - sgn * 1.6 * s, y2 + s)]
        else:
            tri = [(x2, y2), (x2 - s, y2 - sgn * 1.6 * s), (x2 + s, y2 - sgn * 1.6 * s)]
        self.add('<polygon points="' + " ".join(f"{a:.1f},{b:.1f}" for a, b in tri) + f'" fill="{color}"/>')

    def card(self, x, y, w, h, title, sub=None, *, focus=False, tsize=26, ssize=21, sub2=None, fill=None):
        if focus:
            self.rect(x, y, w, h, NAVY, None, 0, 12)
            tc, sc = WHITE, "#CFE0F7"
        else:
            self.rect(x, y, w, h, fill or WHITE, LINE, 1.5, 12)
            tc, sc = NAVY, MUTED
        lines = [l for l in (sub, sub2) if l]
        total = tsize + sum(ssize + 10 for _ in lines)
        ty = y + (h - total) / 2 + tsize * 0.86
        self.text(x + w / 2, ty, title, tsize, 700, tc, "middle")
        for i, l in enumerate(lines):
            self.text(x + w / 2, ty + (i + 1) * (ssize + 10) + 2, l, ssize, 400, sc, "middle")

    def pill(self, x, y, label, *, kind="blue", size=20, anchor="start", mono=None):
        fg, bg, border = {"blue": (BLUE, BLUE_SOFT, BLUE), "navy": (WHITE, NAVY, NAVY),
                          "red": (RED, RED_SOFT, RED), "gray": (MUTED, WHITE, LINE)}[kind]
        mono = (not any(ord(c) > 0x2E80 for c in label)) if mono is None else mono
        w = _w(label, size) + 28
        h = size + 16
        x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
        self.rect(x0, y, w, h, bg, border, 1.3, h / 2)
        self.text(x0 + w / 2, y + h / 2 + size * 0.36, label, size, 700, fg, "middle", MONO if mono else FONT)
        return w

    def badge(self, cx, cy, label, fill=BLUE, r=16, size=18):
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}"/>')
        self.text(cx, cy + size * 0.36, label, size, 700, WHITE, "middle")

    def save(self, name: str) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / name).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}">\n<rect width="{self.w}" height="{self.h}" fill="{WHITE}"/>\n'
            + "\n".join(self.parts) + "\n</svg>\n", encoding="utf-8")
