"""Blue-white figures for the S2 solution document.

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


# ------------------------------------------------------------------ 图1-1
def fig_1_1() -> None:
    s = Svg(1200, 560)
    # headline
    s.rect(20, 20, 1160, 104, NAVY, None, 0, 14)
    s.text(52, 88, "82.05%", 54, 700, WHITE)
    s.text(300, 66, "的受访者曾因信息不足、分析困难或无法判断", 24, 400, "#CFE0F7")
    s.text(300, 100, "而推迟甚至放弃投资决策", 24, 700, WHITE)
    s.text(40, 172, "问卷中的三个困扰", 24, 700, NAVY)
    s.text(700, 172, "产品的对应设计", 24, 700, NAVY)
    rows = [("信息太多，不知道该看什么", 58.97, "重点筛选", "结合个人画像，只呈现与持仓相关的要点"),
            ("来源分散，要在多个平台切换", 53.85, "统一查询", "行情、财报、公告在一个入口查齐"),
            ("难以判断信息是否可靠", 48.72, "依据展示", "每个结论附来源与数据时间，可点开核对")]
    bar_x, bar_w = 40, 560
    for i, (q, v, a, d) in enumerate(rows):
        y = 200 + i * 116
        s.text(bar_x, y + 26, q, 22, 400, INK)
        s.rect(bar_x, y + 42, bar_w, 34, BLUE_PALE, None, 0, 6)
        s.rect(bar_x, y + 42, bar_w * v / 100, 34, BLUE, None, 0, 6)
        s.text(bar_x + bar_w * v / 100 + 12, y + 68, f"{v:.2f}%", 22, 700, NAVY)
        s.arrow([(bar_x + bar_w + 12, y + 59), (696, y + 59)], BLUE_MID, 2)
        s.rect(700, y + 6, 460, 92, WHITE, LINE, 1.5, 12)
        s.rect(700, y + 6, 8, 92, BLUE, None, 0, 4)
        s.text(728, y + 44, a, 24, 700, NAVY)
        s.text(728, y + 78, d, 20, 400, MUTED)
    s.save("fig-1-1-investor-needs.svg")


# ------------------------------------------------------------------ 图3-9
def fig_3_9() -> None:
    s = Svg(1200, 670)
    # step strip
    steps = [("19 题测评", "答案完整性校验"), ("八维评分", "各维度 0–100 分"), ("取 risk 维度", "作为风险分数")]
    for i, (t, d) in enumerate(steps):
        x = 40 + i * 300
        s.card(x, 24, 250, 96, t, d, tsize=24, ssize=19)
        if i < 2:
            s.arrow([(x + 254, 72), (x + 296, 72)])
    s.arrow([(940 - 46, 72), (936, 72)])
    s.card(940, 24, 220, 96, "用户确认", "确认后才生效", focus=True, tsize=24, ssize=19)

    # number line
    x0, x1, ly = 80, 1120, 230
    s.text(40, 180, "风险分数决定持仓上限档位", 24, 700, NAVY)
    sx = lambda v: x0 + (x1 - x0) * v / 100
    bands = [(0, 33, "保守型", "#DCE7F8"), (33, 66, "平衡型", "#A9C4EE"), (66, 100, "成长型", BLUE_MID)]
    for a, b, lab, c in bands:
        s.rect(sx(a), ly, sx(b) - sx(a), 40, c, None, 0, 0)
        s.text((sx(a) + sx(b)) / 2, ly + 28, lab, 22, 700, NAVY if c != BLUE_MID else WHITE, "middle")
    for v in (0, 33, 66, 100):
        s.line([(sx(v), ly - 8), (sx(v), ly + 52)], NAVY, 2)
        s.text(sx(v), ly + 80, str(v), 20, 700, NAVY, "middle")
    s.text(sx(33), ly - 16, "≤ 33", 18, 400, MUTED, "middle")
    s.text(sx(66), ly - 16, "≤ 66", 18, 400, MUTED, "middle")

    # budget table aligned to bands
    cols = ["单一资产", "已识别行业", "科技行业合计", "未分类合计"]
    vals = [("20%", "30%", "25%", "10%"), ("35%", "45%", "40%", "20%"), ("50%", "60%", "60%", "35%")]
    ty = 350
    s.text(40, ty + 4, "各档上限", 20, 700, MUTED)
    for j, c in enumerate(cols):
        s.text(40, ty + 50 + j * 40, c, 20, 400, INK)
    for i, (a, b, _, _) in enumerate(bands):
        cx = (sx(a) + sx(b)) / 2
        for j, v in enumerate(vals[i]):
            s.text(cx, ty + 50 + j * 40, v, 22, 700, NAVY, "middle")
    s.line([(40, ty + 16), (1160, ty + 16)], LINE, 1.2)

    # result strip
    ry = 570
    s.rect(40, ry, 700, 76, BLUE_PALE, LINE, 1.5, 12)
    s.text(64, ry + 32, "逐项比较", 20, 700, NAVY)
    s.text(64, ry + 62, "超限幅度 = max(0, 实际占比 − 上限)，单位：百分点", 20, 400, INK)
    s.arrow([(744, ry + 38), (790, ry + 38)])
    s.pill(800, ry + 20, "REVIEW_REQUIRED", kind="red", size=19)
    s.text(1160, ry + 48, "列出超限对象", 20, 400, MUTED, "end")
    s.save("fig-3-9-profile-budget.svg")


# ------------------------------------------------------------------ 图3-13
def fig_3_13() -> None:
    s = Svg(1200, 660)
    # left: grouping example
    s.rect(20, 20, 520, 620, BLUE_PALE, LINE, 1.5, 14)
    s.text(44, 62, "第一步：同源归并", 24, 700, NAVY)
    s.text(44, 94, "按 lineage_id 把转载、镜像合并为一个来源", 19, 400, MUTED)
    recs = [("A 网站原文", 0), ("B 网站转载", 0), ("C 聚合页面", 0), ("交易所公告", 1), ("公司年报", 2)]
    for i, (lab, g) in enumerate(recs):
        y = 130 + i * 70
        s.rect(44, y, 200, 50, WHITE, LINE, 1.5, 10)
        s.text(144, y + 33, lab, 20, 400, INK, "middle")
    # bracket for group 0
    s.line([(244, 155), (280, 155), (280, 295), (244, 295)], BLUE, 2)
    s.line([(244, 225), (280, 225)], BLUE, 2)
    s.arrow([(280, 225), (330, 225)])
    s.card(334, 190, 180, 70, "来源 1", "3 条记录", tsize=22, ssize=17)
    s.arrow([(244, 365), (330, 365)])
    s.card(334, 337, 180, 56, "来源 2", "1 条记录", tsize=20, ssize=15)
    s.arrow([(244, 435), (330, 435)])
    s.card(334, 407, 180, 56, "来源 3", "1 条记录", tsize=20, ssize=15)
    s.rect(44, 530, 470, 86, NAVY, None, 0, 12)
    s.text(279, 568, "5 条记录 = 3 个独立来源", 24, 700, WHITE, "middle")
    s.text(279, 600, "转载再多也只算一票", 18, 400, "#CFE0F7", "middle")

    # right: decision matrix
    s.text(580, 62, "第二步：按独立来源数判定", 24, 700, NAVY)
    s.text(580, 94, "前提：主体、指标、单位、期间与数据质量已核对", 19, 400, MUTED)
    gx, gy, cw, ch = 670, 150, 168, 118
    s.text(gx + 1.5 * cw, gy - 12, "反对的独立来源数", 20, 700, MUTED, "middle")
    for j, lab in enumerate(["0 个", "1 个", "≥ 2 个"]):
        s.text(gx + j * cw + cw / 2, gy + 22, lab, 20, 700, NAVY, "middle")
    s.text(580, gy + 22, "支持数", 20, 700, MUTED)
    sup = ("SUPPORTED", "事实成立", "navy")
    unr = ("UNRESOLVED", "正反并存", "gray")
    ins = ("INSUFFICIENT", "来源不足", "blue")
    con = ("CONTRADICTED", "事实被否定", "red")
    cells = [[sup, unr, unr], [ins, unr, unr], [ins, ins, con]]
    for i, rl in enumerate(["≥ 2 个", "1 个", "0 个"]):
        y = gy + 40 + i * ch
        s.text(580, y + ch / 2 + 8, rl, 20, 700, NAVY)
        for j in range(3):
            x = gx + j * cw
            label, desc, kind = cells[i][j]
            focus = kind == "navy"
            s.rect(x + 4, y + 4, cw - 8, ch - 8, NAVY if focus else WHITE, None if focus else LINE, 1.5, 10)
            color = WHITE if focus else RED if kind == "red" else MUTED if kind == "gray" else BLUE
            s.text(x + cw / 2, y + 54, label, 17, 700, color, "middle", MONO)
            s.text(x + cw / 2, y + 84, desc, 18, 400, "#CFE0F7" if focus else MUTED, "middle")
    s.text(580, 590, "主体、单位、期间或质量存在歧义时，一律记为 UNRESOLVED。", 19, 400, MUTED)
    s.text(580, 626, "只有 SUPPORTED 的事实可以进入建议。", 20, 700, NAVY)
    s.save("fig-3-13-evidence.svg")


FIGURES = [fig_1_1, fig_3_9, fig_3_13]

if __name__ == "__main__":
    for fn in FIGURES:
        fn()
    print("written:", sorted(p.name for p in OUT.glob("*.svg")))
