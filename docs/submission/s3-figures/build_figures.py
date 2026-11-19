"""Generate the S3 defense architecture figures as PowerPoint-friendly SVG.

All styling is written as inline presentation attributes (no <style>, no
markers) so PowerPoint can import the SVG and "Convert to Shape" without loss.
Run:  python docs/submission/s3-figures/build_figures.py
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent / "svg"

FONT = "Microsoft YaHei, PingFang SC, Noto Sans SC, sans-serif"
MONO = "Consolas, Menlo, monospace"

INK = "#2A1E18"
MUTED = "#6B5A50"
BRAND = "#8A2E12"
ORANGE = "#D9631E"
ORANGE_SOFT = "#FCE6D6"
ORANGE_ZONE = "#FFF3EA"
CARD = "#FFFFFF"
LINE = "#E3C7B3"
GRAY_ZONE = "#F5EFEB"
GRAY_LINE = "#D9CCC3"
GREEN = "#2E7D4F"
GREEN_SOFT = "#E4F2E9"
AMBER = "#A86A12"
AMBER_SOFT = "#FBEFD6"
RED = "#B3261E"
RED_SOFT = "#F9E1DE"


class Svg:
    def __init__(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.parts: list[str] = []

    def add(self, s: str) -> None:
        self.parts.append(s)

    def rect(self, x, y, w, h, fill=CARD, stroke=LINE, sw=1.5, rx=10, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{st}{d}/>')

    def text(self, x, y, s, size=20, weight=400, fill=INK, anchor="start", font=FONT, italic=False):
        it = ' font-style="italic"' if italic else ""
        self.add(
            f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{it}>{escape(s)}</text>'
        )

    def line(self, pts, color=MUTED, sw=2, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        p = " ".join(f"{x},{y}" for x, y in pts)
        self.add(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linejoin="round"{d}/>')

    def head(self, x, y, direction, color=MUTED, size=9):
        s = size
        pts = {
            "r": [(x, y), (x - 1.6 * s, y - s), (x - 1.6 * s, y + s)],
            "l": [(x, y), (x + 1.6 * s, y - s), (x + 1.6 * s, y + s)],
            "d": [(x, y), (x - s, y - 1.6 * s), (x + s, y - 1.6 * s)],
            "u": [(x, y), (x - s, y + 1.6 * s), (x + s, y + 1.6 * s)],
        }[direction]
        p = " ".join(f"{a},{b}" for a, b in pts)
        self.add(f'<polygon points="{p}" fill="{color}"/>')

    def arrow(self, pts, color=MUTED, sw=2, dash=None, size=8):
        self.line(pts[:-1] + [self._shorten(pts[-2], pts[-1], 1.4 * size)], color, sw, dash)
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        direction = ("r" if x2 > x1 else "l") if abs(x2 - x1) >= abs(y2 - y1) else ("d" if y2 > y1 else "u")
        self.head(x2, y2, direction, color, size)

    @staticmethod
    def _shorten(a, b, by):
        (x1, y1), (x2, y2) = a, b
        if x1 == x2:
            return (x2, y2 - by if y2 > y1 else y2 + by)
        return (x2 - by if x2 > x1 else x2 + by, y2)

    def box(self, x, y, w, h, title, sub=None, *, fill=CARD, stroke=LINE, sw=1.5, tcolor=INK,
            scolor=MUTED, tsize=22, ssize=16, rx=10, sub2=None):
        self.rect(x, y, w, h, fill, stroke, sw, rx)
        lines = [l for l in (sub, sub2) if l]
        total = tsize + sum(ssize + 8 for _ in lines)
        ty = y + (h - total) / 2 + tsize * 0.86
        self.text(x + w / 2, ty, title, tsize, 700, tcolor, "middle")
        for i, l in enumerate(lines):
            self.text(x + w / 2, ty + (i + 1) * (ssize + 8) + 2, l, ssize, 400, scolor, "middle")

    def tag(self, x, y, label, kind="pass", size=17, anchor="start"):
        fg, bg = {"pass": (GREEN, GREEN_SOFT), "review": (AMBER, AMBER_SOFT),
                  "blocked": (RED, RED_SOFT), "calc": (BRAND, ORANGE_SOFT),
                  "gray": (MUTED, GRAY_ZONE)}[kind]
        cjk = any(ord(c) > 0x2E80 for c in label)
        w = sum(size * (1.0 if ord(c) > 0x2E80 else 0.62) for c in label) + 24
        h = size + 14
        x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
        self.rect(x0, y, w, h, bg, fg, 1.2, h / 2)
        self.text(x0 + w / 2, y + h / 2 + size * 0.36, label, size, 700, fg, "middle",
                  FONT if cjk else MONO)
        return w

    def badge(self, cx, cy, label, fill=ORANGE, r=15, color="#FFFFFF", size=17):
        self.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>')
        self.text(cx, cy + size * 0.36, label, size, 700, color, "middle")

    def save(self, name: str) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        body = "\n".join(self.parts)
        (OUT / name).write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}">\n{body}\n</svg>\n',
            encoding="utf-8",
        )


def zone_label(s: Svg, x, y, title, color=BRAND, sub=None):
    s.text(x, y, title, 20, 700, color)
    if sub:
        s.text(x, y + 24, sub, 14, 400, MUTED)


# ---------------------------------------------------------------- Figure 1
def fig_layers() -> None:
    """S14 系统整体分层架构."""
    s = Svg(1600, 720)
    L, R = 230, 1330  # content column

    def layer(y, h, name, tech, fill=GRAY_ZONE, stroke=GRAY_LINE, ncolor=INK):
        s.rect(30, y, R - 30, h, fill, stroke, 1.5, 14)
        s.text(50, y + 40, name, 22, 700, ncolor)
        s.text(50, y + 66, tech, 14, 400, MUTED)

    # L1 presentation
    layer(20, 128, "表现层", "HTML · CSS · JS")
    s.text(50, 20 + 88, "Hash 路由", 14, 400, MUTED)
    chips = [("咨询工作台", "SSE 流式输出"), ("持仓分析", "诊断与方案试算"), ("市场观察", "Lightweight-Charts"),
             ("研究工作台", "AntV X6 流程编排"), ("风险测评", "19 题 · DIMS 八维")]
    cw = (R - L - 20 - 4 * 14) / 5
    for i, (t, sub) in enumerate(chips):
        s.box(L + i * (cw + 14), 38, cw, 92, t, sub, tsize=20, ssize=15)

    # L2 api
    layer(184, 110, "接口层", "FastAPI · Uvicorn")
    chips = [("契约校验", "Pydantic 2 请求与响应模型"), ("账户隔离", "未登录 401 · 跨账户 403"), ("流式推送", "SSE 分段返回研究进度")]
    cw = (R - L - 20 - 2 * 14) / 3
    for i, (t, sub) in enumerate(chips):
        s.box(L + i * (cw + 14), 200, cw, 78, t, sub, tsize=20, ssize=15)

    # L3 domain (focus)
    s.rect(30, 330, R - 30, 214, ORANGE_ZONE, ORANGE, 1.5, 14)
    s.text(50, 370, "领域服务", 22, 700, BRAND)
    s.text(50, 398, "与计算层", 22, 700, BRAND)
    s.text(50, 426, "Python 3.11–3.12", 14, 400, MUTED)
    s.text(50, 448, "Decimal · SHA-256", 14, 400, MUTED)
    s.rect(L, 346, R - L - 20, 48, ORANGE_SOFT, None, 0, 8)
    s.text(L + 20, 377, "研究编排", 19, 700, BRAND)
    s.text(L + 116, 377, "意图解析 → 有界 DAG 并行调度专业研究节点（行情 · 持仓 · 证据汇总）", 18, 400, INK)
    steps = [("画像约束", "风险预算 · 集中度上限"), ("证据验证", "来源族去重 · 双源升格"),
             ("确定性计算", "整手 · 费用 · 现金逐笔"), ("风险与合规闸门", "按最严结果定状态")]
    gap = 44
    sw_ = (R - L - 20 - 3 * gap) / 4
    for i, (t, sub) in enumerate(steps):
        x = L + i * (sw_ + gap)
        s.box(x, 412, sw_, 112, t, sub, stroke=ORANGE, sw=2, tsize=21, ssize=15)
        s.badge(x + 22, 432, str(i + 1), r=13, size=15)
        if i < 3:
            s.arrow([(x + sw_ + 6, 468), (x + sw_ + gap - 6, 468)], ORANGE, 2.5)

    # L4 storage + external
    y4, h4 = 580, 120
    s.rect(30, y4, 560, h4, GRAY_ZONE, GRAY_LINE, 1.5, 14)
    s.text(50, y4 + 40, "持久化层", 22, 700, INK)
    s.text(50, y4 + 70, "SQLite / PostgreSQL", 17, 700, INK)
    s.text(50, y4 + 96, "快照版本化 · 会话 SHA-256 指纹 · 审计回溯", 15, 400, MUTED)
    s.rect(620, y4, R - 620, h4, GRAY_ZONE, GRAY_LINE, 1.5, 14)
    s.text(640, y4 + 40, "外部能力", 22, 700, INK)
    ext = [("问财 SkillHub", "9 项金融 Skill"), ("大模型接口", "deepseek-v4-flash"), ("向量检索 · OCR", "e5-small · RapidOCR")]
    ew = (R - 760 - 20 - 2 * 12) / 3
    for i, (t, sub) in enumerate(ext):
        s.box(760 + i * (ew + 12), y4 + 16, ew, 88, t, sub, tsize=19, ssize=15)

    # inter-layer arrows
    s.arrow([(680, 148), (680, 184)], MUTED, 2)
    s.text(692, 172, "HTTP / SSE", 14, 400, MUTED)
    s.arrow([(680, 294), (680, 330)], MUTED, 2)
    s.text(692, 318, "领域调用", 14, 400, MUTED)
    s.arrow([(310, 544), (310, 580)], MUTED, 2)
    s.text(322, 568, "快照读写", 14, 400, MUTED)
    s.arrow([(960, 544), (960, 580)], MUTED, 2)
    s.text(972, 568, "数据查询 · 模型推理", 14, 400, MUTED)

    # right annotation
    x0 = 1360
    s.rect(x0, 20, 210, 128, CARD, LINE, 1.5, 12)
    s.text(x0 + 18, 52, "图例", 17, 700, INK)
    s.rect(x0 + 18, 68, 26, 18, ORANGE_ZONE, ORANGE, 2, 4)
    s.text(x0 + 54, 83, "自研核心", 16, 400, INK)
    s.rect(x0 + 18, 102, 26, 18, GRAY_ZONE, GRAY_LINE, 1.5, 4)
    s.text(x0 + 54, 117, "接入与基础设施", 16, 400, INK)

    s.rect(x0, 330, 210, 214, CARD, ORANGE, 2, 12)
    s.text(x0 + 18, 364, "职责隔离", 19, 700, BRAND)
    s.text(x0 + 18, 398, "大模型", 16, 700, INK)
    s.text(x0 + 18, 422, "意图识别 · 槽位解析", 15, 400, MUTED)
    s.text(x0 + 18, 444, "通俗化阐述", 15, 400, MUTED)
    s.line([(x0 + 18, 462), (x0 + 192, 462)], LINE, 1)
    s.text(x0 + 18, 490, "确定性程序", 16, 700, INK)
    s.text(x0 + 18, 514, "敞口穿透 · 调仓测算", 15, 400, MUTED)
    s.text(x0 + 18, 536, "风控与合规裁决", 15, 400, MUTED)
    s.save("fig-s14-system-layers.svg")


# ---------------------------------------------------------------- Figure 2
def fig_skillhub() -> None:
    """S15 分层架构与 SkillHub 底座集成."""
    s = Svg(1600, 720)
    # top zone: self-built
    s.rect(20, 20, 1560, 360, ORANGE_ZONE, ORANGE, 1.5, 16)
    zone_label(s, 44, 58, "自研：控制链", sub="决定数据与结论以何种资格进入建议")
    # bottom zone: reused
    s.rect(20, 430, 1560, 270, GRAY_ZONE, GRAY_LINE, 1.5, 16)
    s.text(44, 468, "复用：问财 SkillHub 金融能力底座", 20, 700, INK)
    s.text(44, 680, "9 项金融 Skill · iFinD 数据适配 · 可切换大模型接口（OpenAI 兼容）", 15, 400, MUTED)

    y, h = 120, 220
    s.box(44, y, 190, h, "用户入口", "问题 · 问卷", sub2="持仓确认", tsize=21)
    s.arrow([(234, y + h / 2), (276, y + h / 2)], MUTED, 2)
    s.box(276, y, 210, h, "研究编排", "意图解析", sub2="有界 DAG 调度", tsize=21)
    steps = [("画像约束", "确认后的画像", "映射为预算上限"), ("证据验证", "口径校验 · 来源族", "去重 · 双源升格"),
             ("确定性计算", "穿透 · HHI", "整手调仓测算"), ("风险与合规闸门", "两道闸门独立", "取最严结果")]
    x = 540
    sw_, gap = 180, 32
    for i, (t, a, b) in enumerate(steps):
        xi = x + i * (sw_ + gap)
        s.box(xi, y, sw_, h, t, a, sub2=b, stroke=ORANGE, sw=2.2, tsize=21)
        s.badge(xi + 24, y + 24, str(i + 1), r=14)
        if i < 3:
            s.arrow([(xi + sw_ + 4, y + h / 2), (xi + sw_ + gap - 4, y + h / 2)], ORANGE, 2.5)
    s.arrow([(486, y + h / 2), (540, y + h / 2)], ORANGE, 2.5)
    # outputs
    ox = x + 4 * sw_ + 3 * gap + 40
    s.arrow([(ox - 40, y + h / 2), (ox - 4, y + h / 2)], ORANGE, 2.5)
    s.text(ox, y + 14, "建议资格", 18, 700, BRAND)
    s.tag(ox, y + 30, "PASS", "pass", 15)
    s.text(ox, y + 78, "进入正式建议", 14, 400, MUTED)
    s.tag(ox, y + 96, "REVIEW_REQUIRED", "review", 14)
    s.text(ox, y + 142, "保留问题并复核", 14, 400, MUTED)
    s.tag(ox, y + 160, "BLOCKED", "blocked", 15)
    s.text(ox, y + 208, "拦截输出", 14, 400, MUTED)

    # skill chips
    data = [("行情", "market-query"), ("财务", "finance-query"), ("行业", "industry-query"),
            ("宏观", "macro-query"), ("基金", "fund-query"), ("可转债", "cb-selector")]
    news = [("公告", "announcement-search"), ("新闻", "news-search"), ("研报", "report-search")]
    cy, ch, cw, g = 540, 96, 140, 10
    s.text(44, cy - 16, "结构化数据查询 · 6 项", 16, 700, INK)
    for i, (t, sid) in enumerate(data):
        s.box(44 + i * (cw + g), cy, cw, ch, t, sid, tsize=20, ssize=13)
    nx = 44 + 6 * (cw + g) + 36
    s.text(nx, cy - 16, "资讯检索 · 3 项", 16, 700, INK)
    for i, (t, sid) in enumerate(news):
        s.box(nx + i * (168 + g), cy, 168, ch, t, sid, tsize=20, ssize=13)

    # cross-zone arrows
    s.arrow([(440, y + h), (440, 494)], MUTED, 2)
    s.text(452, 410, "按节点调用 Skill", 15, 400, MUTED)
    s.arrow([(830, 494), (830, y + h)], ORANGE, 2.5)
    s.text(842, 402, "原始记录 + lineage_id", 15, 700, BRAND)
    s.text(842, 422, "未经核验不得进入决策链", 14, 400, MUTED)
    s.save("fig-s15-skillhub-control-chain.svg")


# ---------------------------------------------------------------- Figure 3
def fig_functions() -> None:
    """S8 功能架构."""
    s = Svg(1600, 720)
    hub = (600, 180, 400, 360)
    s.rect(*hub, ORANGE_ZONE, ORANGE, 2.5, 18)
    hx, hy, hw, hh = hub
    s.text(hx + hw / 2, hy + 48, "统一投资者档案", 26, 700, BRAND, "middle")
    s.line([(hx + 30, hy + 68), (hx + hw - 30, hy + 68)], ORANGE, 1.2)
    rows = [("画像 Profile", "19 题 · DIMS 八维 · C1–C5"), ("已确认持仓", "资产占比 · 行业暴露 · 交易记录"),
            ("长期偏好", "现金预留 · 换手节奏 · 调整习惯"), ("研究记录", "方法版本 · 输入时点 · 结果")]
    for i, (a, b) in enumerate(rows):
        yy = hy + 108 + i * 56
        s.text(hx + 34, yy, a, 19, 700, INK)
        s.text(hx + 34, yy + 24, b, 15, 400, MUTED)
    s.text(hx + hw / 2, hy + hh - 14, "用户确认后生效 · 保留历史版本", 14, 400, BRAND, "middle")

    mods = [("01", "AI 对话工作台", "六类高频投顾场景一站式问答", "读取画像与持仓"),
            ("02", "持仓分析诊断", "持仓 KPI 与画像区间逐项对照", "读取持仓与预算"),
            ("03", "大盘鉴别研判", "指数切换，趋势与风险同屏", "关联持仓暴露"),
            ("04", "交易风格分析", "依据交易行为证据识别风格", "读取交易记录"),
            ("05", "风险测评画像", "19 题问卷生成八维画像", "确认后写入"),
            ("06", "证据溯源合规", "逻辑链可展开，结论可查", "记录来源与版本")]
    cw, chh = 430, 150
    pos = [(60, 40), (60, 285), (60, 530), (1110, 40), (1110, 285), (1110, 530)]
    for (num, t, d, rel), (x, y) in zip(mods, pos):
        focus = num == "05"
        s.rect(x, y, cw, chh, CARD, ORANGE if focus else LINE, 2 if focus else 1.5, 14)
        s.text(x + 26, y + 46, num, 24, 700, ORANGE)
        s.text(x + 72, y + 46, t, 23, 700, INK)
        s.text(x + 26, y + 88, d, 17, 400, MUTED)
        s.tag(x + 26, y + 104, rel, "calc" if focus else "gray", 14)
        cyy = y + chh / 2
        yy = min(max(cyy, hy + 40), hy + hh - 60)
        if x < hx:
            s.arrow([(hx, yy), (530, yy), (530, cyy), (x + cw, cyy)], MUTED, 1.8)
        elif focus:
            s.arrow([(x, cyy), (hx + hw, cyy)], ORANGE, 2.8)
        else:
            s.arrow([(hx + hw, yy), (1060, yy), (1060, cyy), (x, cyy)], MUTED, 1.8)
    s.text(800, 600, "一处更新，其余模块按最新前提重算", 18, 700, BRAND, "middle")
    s.save("fig-s08-function-architecture.svg")


# ---------------------------------------------------------------- Figure 4
def fig_penetration() -> None:
    """S16 画像风险预算与组合穿透."""
    s = Svg(1600, 720)
    # Row 1: profile -> budget
    s.rect(20, 20, 1040, 200, GRAY_ZONE, GRAY_LINE, 1.5, 14)
    zone_label(s, 40, 56, "画像映射为预算上限", INK)
    s.box(40, 80, 170, 110, "问卷作答", "19 题", tsize=20)
    s.arrow([(210, 135), (246, 135)])
    s.box(246, 80, 170, 110, "用户确认", "确认后才生效", tsize=20)
    s.arrow([(416, 135), (452, 135)])
    s.box(452, 80, 170, 110, "风险类型", "按 risk 维度分档", tsize=20)
    s.arrow([(622, 135), (658, 135)])
    # mini budget table
    tx, ty = 658, 80
    cols = ["", "单一资产", "已识别行业", "科技", "未分类"]
    rows = [("保守型", "20%", "30%", "25%", "10%"), ("平衡型", "35%", "45%", "40%", "20%"), ("成长型", "50%", "60%", "60%", "35%")]
    s.rect(tx, ty, 382, 124, CARD, LINE, 1.5, 8)
    widths = [74, 80, 92, 64, 72]
    xs = [tx]
    for w_ in widths[:-1]:
        xs.append(xs[-1] + w_)
    for j, c in enumerate(cols):
        s.text(xs[j] + widths[j] / 2, ty + 24, c, 14, 700, MUTED, "middle")
    for i, r in enumerate(rows):
        yy = ty + 54 + i * 26
        for j, c in enumerate(r):
            s.text(xs[j] + widths[j] / 2, yy, c, 15, 700 if j == 0 else 400, INK, "middle")
    s.line([(tx + 8, ty + 34), (tx + 374, ty + 34)], LINE, 1)

    # Row 2: penetration flow
    s.rect(20, 250, 1040, 450, ORANGE_ZONE, ORANGE, 1.5, 14)
    zone_label(s, 40, 286, "穿透暴露与集中度检查", BRAND)
    s.box(40, 320, 180, 80, "股票", "直接持仓", tsize=20)
    s.box(40, 420, 180, 80, "基金 / ETF", "间接持仓", tsize=20)
    s.box(40, 520, 180, 80, "现金", "单独计量", tsize=20)
    # allocation
    s.rect(270, 400, 250, 120, CARD, ORANGE, 2.2, 12)
    s.text(395, 436, "按底层成分分摊", 20, 700, INK, "middle")
    s.text(395, 470, "Σ 分摊金额 = 原持仓市值", 17, 700, BRAND, "middle")
    s.text(395, 498, "未分类份额单列", 15, 400, MUTED, "middle")
    s.arrow([(220, 460), (270, 460)], ORANGE, 2.5)
    # merge
    s.box(570, 320, 210, 280, "合并暴露", "直接 + 间接", sub2="按行业汇总 w_k", tsize=21)
    s.arrow([(220, 360), (545, 360), (570, 360)])
    s.arrow([(520, 460), (570, 460)], ORANGE, 2.5)
    s.arrow([(220, 560), (570, 560)])
    # checks
    s.rect(830, 320, 210, 280, CARD, LINE, 1.5, 12)
    s.text(935, 356, "逐项检查", 21, 700, INK, "middle")
    s.text(935, 404, "HHI = Σ w_k²", 19, 700, BRAND, "middle", MONO)
    s.line([(850, 424), (1020, 424)], LINE, 1)
    for i, t in enumerate(["单一资产上限", "行业 / 科技上限", "未分类上限"]):
        s.text(935, 458 + i * 30, t, 16, 400, INK, "middle")
    s.tag(935, 548, "超限项清单", "blocked", 15, "middle")
    s.arrow([(780, 460), (830, 460)], ORANGE, 2.5)
    s.text(40, 650, "每笔分摊可回溯到原持仓；合并后的行业暴露与画像预算逐项比对，超限项进入复核。", 16, 400, MUTED)

    # Right: bar chart (focus)
    bx, by, bw, bh = 1100, 20, 480, 680
    s.rect(bx, by, bw, bh, CARD, ORANGE, 2, 14)
    s.text(bx + 30, by + 46, "同一 144.55 万元组合", 22, 700, INK)
    s.text(bx + 30, by + 76, "不同画像下的预算超限项", 18, 400, MUTED)
    base = by + 560
    unit = 120
    data = [("保守型", 3, ORANGE), ("平衡型", 2, "#E8925A"), ("成长型", 1, "#F2BE98")]
    for i, (lab, v, c) in enumerate(data):
        x = bx + 60 + i * 140
        top = base - v * unit
        s.rect(x, top, 92, v * unit, c, None, 0, 6)
        s.text(x + 46, top - 18, f"{v} 项", 30, 700, INK, "middle")
        s.text(x + 46, base + 34, lab, 19, 700, INK, "middle")
    s.line([(bx + 36, base), (bx + bw - 36, base)], MUTED, 1.5)
    s.text(bx + 30, by + bh - 34, "仅统计风险预算项；现金下限与行业 HHI", 14, 400, MUTED)
    s.text(bx + 30, by + bh - 14, "由组合体检分别核验。", 14, 400, MUTED)
    s.save("fig-s16-risk-budget-penetration.svg")


# ---------------------------------------------------------------- Figure 5
def fig_evidence() -> None:
    """S17 来源等价类证据防火墙."""
    s = Svg(1600, 640)
    # candidate
    s.rect(20, 140, 250, 300, CARD, LINE, 1.5, 14, dash="6 5")
    s.text(145, 180, "LLM 候选结论", 19, 700, MUTED, "middle")
    s.text(145, 270, "“该事件构成利好，", 22, 700, INK, "middle")
    s.text(145, 304, "建议加仓。”", 22, 700, INK, "middle")
    s.tag(145, 360, "UNVERIFIED", "gray", 15, "middle")
    s.arrow([(270, 290), (318, 290)], MUTED, 2.5)

    # firewall stages
    s.rect(318, 20, 900, 540, ORANGE_ZONE, ORANGE, 1.5, 16)
    s.text(342, 58, "四级证据防火墙", 22, 700, BRAND)
    s.text(342, 84, "核验通过的事实才获得决策资格", 15, 400, MUTED)
    stages = [("口径校验", ["主体 · 指标", "单位 · 期间"], False),
              ("来源族去重", ["按 lineage_id 合并", "转载 · 镜像 · 聚合"], True),
              ("双源升格", ["≥ 2 个独立来源族", "一致且无异议"], True),
              ("数值接管", ["金额 · 敞口 · HHI", "交确定性规则计算"], False)]
    sw_, gap = 192, 26
    for i, (t, ls, focus) in enumerate(stages):
        x = 342 + i * (sw_ + gap)
        s.rect(x, 110, sw_, 220, CARD, ORANGE if focus else LINE, 2.4 if focus else 1.5, 12)
        s.badge(x + sw_ / 2, 150, f"0{i + 1}", ORANGE if focus else MUTED, 20, size=16)
        s.text(x + sw_ / 2, 210, t, 22, 700, BRAND if focus else INK, "middle")
        for k, l in enumerate(ls):
            s.text(x + sw_ / 2, 248 + k * 26, l, 16, 400, MUTED, "middle")
        if i < 3:
            s.arrow([(x + sw_ + 2, 220), (x + sw_ + gap - 2, 220)], ORANGE, 2.5)
    # worked example under stage 2/3
    ex = 342 + (sw_ + gap)
    s.rect(ex, 360, 2 * sw_ + gap, 176, CARD, LINE, 1.5, 12)
    s.text(ex + 20, 392, "示例", 16, 700, BRAND)
    srcs = [("A 站原文", 0), ("B 站转载", 0), ("C 聚合页", 0), ("交易所公告", 1)]
    for k, (lab, fam) in enumerate(srcs):
        yy = 410 + k * 28
        s.rect(ex + 20, yy, 120, 22, ORANGE_SOFT if fam == 0 else GREEN_SOFT, None, 0, 5)
        s.text(ex + 80, yy + 16, lab, 13, 400, INK, "middle")
    s.line([(ex + 140, 421), (ex + 170, 421), (ex + 170, 477), (ex + 140, 477)], ORANGE, 1.5)
    s.line([(ex + 170, 449), (ex + 196, 449)], ORANGE, 1.5)
    s.text(ex + 204, 454, "来源族 1", 15, 700, BRAND)
    s.line([(ex + 140, 505), (ex + 196, 505)], GREEN, 1.5)
    s.text(ex + 204, 510, "来源族 2", 15, 700, GREEN)
    s.text(ex + 290, 466, "4 条记录", 15, 400, MUTED)
    s.text(ex + 290, 492, "= 2 个独立支持", 16, 700, INK)

    # outcomes
    s.arrow([(1218, 220), (1262, 220)], ORANGE, 2.5)
    ox = 1262
    s.rect(ox, 20, 318, 540, CARD, LINE, 1.5, 16)
    s.text(ox + 24, 58, "决策资格", 22, 700, BRAND)
    s.text(ox + 24, 84, "再经风险与合规闸门审查", 15, 400, MUTED)
    outs = [("PASS", "pass", "可进入正式建议"), ("REVIEW_REQUIRED", "review", "来源冲突：挂起复核"),
            ("BLOCKED", "blocked", "未核验：拦截建议输出")]
    for i, (lab, kind, d) in enumerate(outs):
        yy = 130 + i * 130
        s.tag(ox + 24, yy, lab, kind, 18)
        s.text(ox + 24, yy + 70, d, 17, 400, INK)
        if i < 2:
            s.line([(ox + 24, yy + 100), (ox + 294, yy + 100)], LINE, 1)
    s.text(20, 612, "审计记录保留来源族、核验结果与未决问题，任一结论可回溯至原始记录。", 17, 700, BRAND)
    s.save("fig-s17-evidence-firewall.svg")


# ---------------------------------------------------------------- Figure 6
def fig_dag_rebalance() -> None:
    """S18 有界 DAG 调度与离散序贯再平衡."""
    s = Svg(1600, 720)
    # left: DAG
    s.rect(20, 20, 640, 680, GRAY_ZONE, GRAY_LINE, 1.5, 16)
    zone_label(s, 44, 58, "有界 DAG 调度", INK, sub="先校验环路与拓扑序，再并行执行就绪节点")
    s.box(44, 230, 150, 80, "请求校验", tsize=19)
    s.box(250, 150, 160, 80, "行情查询", tsize=19, stroke=ORANGE, sw=2)
    s.box(250, 310, 160, 80, "持仓分析", tsize=19, stroke=ORANGE, sw=2)
    s.box(470, 230, 160, 80, "证据汇总", tsize=19)
    s.arrow([(194, 270), (222, 270), (222, 190), (250, 190)], MUTED, 2)
    s.arrow([(222, 270), (222, 350), (250, 350)], MUTED, 2)
    s.arrow([(410, 190), (440, 190), (440, 270), (470, 270)], MUTED, 2)
    s.arrow([(410, 350), (440, 350), (440, 270), (470, 270)], MUTED, 2)
    s.text(330, 140, "并行", 15, 700, ORANGE, "middle")
    # timeout formula
    s.rect(44, 420, 592, 110, CARD, ORANGE, 2, 12)
    s.text(64, 454, "有效时限", 17, 700, BRAND)
    s.text(340, 498, "min（请求预算，节点预算，全局剩余）", 22, 700, INK, "middle")
    # cascade cancel
    s.rect(44, 550, 592, 126, CARD, LINE, 1.5, 12)
    s.text(64, 584, "级联取消", 17, 700, RED)
    s.text(64, 616, "前驱失败或取消时，依赖节点同步取消，", 16, 400, INK)
    s.text(64, 642, "并记录原因；不产生半成品结论。", 16, 400, INK)

    # right: rebalance pipeline
    s.rect(690, 20, 890, 680, ORANGE_ZONE, ORANGE, 1.5, 16)
    zone_label(s, 714, 58, "离散序贯再平衡", BRAND, sub="先卖后买 · 现金逐笔结算 · 交易后复核")
    steps = [("目标权重", "连续解"), ("死区过滤", "|Δw| < 0.50% 忽略"), ("卖出 SELL / REDUCE", "整手 · 现金增加"),
             ("买入 BUY", "二分求最大可买手数"), ("交易后复核", "风险预算重检")]
    y0, bh, g = 106, 66, 14
    for i, (t, d) in enumerate(steps):
        y = y0 + i * (bh + g)
        focus = i == 3
        s.rect(714, y, 400, bh, CARD, ORANGE if focus else LINE, 2.4 if focus else 1.5, 10)
        s.badge(744, y + bh / 2, str(i + 1), ORANGE if focus else MUTED, 14, size=15)
        s.text(772, y + 30, t, 19, 700, INK)
        s.text(772, y + 54, d, 15, 400, MUTED)
        if i < 4:
            s.arrow([(914, y + bh), (914, y + bh + g)], ORANGE, 2, size=6)
    s.tag(714, y0 + 5 * (bh + g) + 4, "CALCULATED", "calc", 16)
    s.text(870, y0 + 5 * (bh + g) + 26, "测算完成，可复算", 15, 400, MUTED)
    # binary search card
    s.rect(1140, 106, 416, 226, CARD, ORANGE, 2, 12)
    s.text(1162, 140, "买入约束", 17, 700, BRAND)
    s.text(1162, 178, "金额(n) + 费用(n) ≤ C − ρV", 19, 700, INK)
    s.text(1162, 210, "n 为整手数，ρV 为现金下限", 15, 400, MUTED)
    s.text(1162, 248, "费用随手数非递减 ⇒ 可行域单调", 16, 400, INK)
    s.text(1162, 284, "O(log n) 二分求最大可买手数", 18, 700, BRAND)
    # cash ledger
    s.rect(1140, 350, 416, 326, CARD, LINE, 1.5, 12)
    s.text(1162, 384, "现金恒等式", 17, 700, BRAND)
    s.text(1348, 426, "C′ = C + S − B − F", 22, 700, INK, "middle", MONO)
    s.text(1162, 458, "S 卖出额 · B 买入额 · F 全部费用", 14, 400, MUTED)
    s.line([(1162, 478), (1534, 478)], LINE, 1)
    s.text(1162, 510, "测试案例（144.55 万元组合）", 15, 700, INK)
    s.text(1162, 540, "原总资产", 15, 400, MUTED)
    s.text(1534, 540, "1,445,545.00", 15, 700, INK, "end", MONO)
    s.text(1162, 566, "全部费用", 15, 400, MUTED)
    s.text(1534, 566, "− 743.15", 15, 700, INK, "end", MONO)
    s.text(1162, 592, "调整后总资产", 15, 400, MUTED)
    s.text(1534, 592, "1,444,801.85", 15, 700, INK, "end", MONO)
    s.line([(1162, 608), (1534, 608)], LINE, 1)
    s.text(1162, 640, "独立复算差额", 16, 700, INK)
    s.tag(1534, 620, "0.00 元", "pass", 16, "end")
    s.save("fig-s18-dag-rebalance.svg")


# ---------------------------------------------------------------- Figure 7
def fig_gates_drift() -> None:
    """S19 独立合规闸门与会话防漂移."""
    s = Svg(1600, 720)
    # left: dual gates
    s.rect(20, 20, 760, 680, GRAY_ZONE, GRAY_LINE, 1.5, 16)
    zone_label(s, 44, 58, "独立双闸门", INK, sub="evaluate_decision_gates() 在模型之外运行")
    s.box(44, 270, 150, 120, "建议候选", "研究结果", sub2="+ 配置方案", tsize=20)
    gates = [("风险闸门", ["风险预算与配置结果", "事实 / 证据已核验", "账户与画像一致"], 110),
             ("合规闸门", ["法定风险揭示完整", "无保本 / 承诺收益措辞", "敏感信息拦截"], 410)]
    for t, ls, y in gates:
        s.rect(250, y, 260, 200, CARD, ORANGE, 2.2, 12)
        s.text(380, y + 40, t, 22, 700, BRAND, "middle")
        for k, l in enumerate(ls):
            s.text(272, y + 84 + k * 34, "· " + l, 16, 400, INK)
        s.arrow([(194, 330), (222, 330), (222, y + 100), (250, y + 100)], MUTED, 2)
        s.arrow([(510, y + 100), (535, y + 100), (535, 330), (560, 330)], ORANGE, 2.2)
    s.rect(560, 230, 200, 200, CARD, ORANGE, 2.4, 12)
    s.text(660, 266, "取最严结果", 20, 700, BRAND, "middle")
    s.tag(660, 282, "BLOCKED", "blocked", 15, "middle")
    s.text(660, 330, "≻", 18, 700, MUTED, "middle")
    s.tag(660, 338, "REVIEW_REQUIRED", "review", 14, "middle")
    s.text(660, 386, "≻", 18, 700, MUTED, "middle")
    s.tag(660, 392, "PASS", "pass", 15, "middle")
    s.text(44, 672, "仅当两道闸门均为 PASS 时，建议才具备输出资格。", 16, 700, BRAND)

    # right: session drift state machine
    s.rect(810, 20, 770, 680, ORANGE_ZONE, ORANGE, 1.5, 16)
    zone_label(s, 834, 58, "版本会话锁 session_truth.v1", BRAND, sub="分析前提绑定 revision · SHA-256 指纹 · owner_id")
    s.box(834, 130, 200, 90, "NOT_LOCKED", "尚无确认前提", tsize=19)
    s.arrow([(1034, 175), (1100, 175)], MUTED, 2)
    s.text(1067, 162, "用户确认", 14, 400, MUTED, "middle")
    s.rect(1100, 120, 440, 110, CARD, GREEN, 2.2, 12)
    s.text(1124, 158, "LOCKED · revision 1", 20, 700, GREEN, font=MONO)
    s.text(1124, 190, "持仓 1,000 股 · 指纹 SHA-256", 15, 400, MUTED)
    s.text(1124, 212, "分析按此前提执行", 15, 400, MUTED)
    s.arrow([(1320, 230), (1320, 300)], RED, 2.2)
    s.text(1334, 272, "持仓改为 1,100 股", 15, 700, RED)
    s.rect(1100, 300, 440, 110, CARD, RED, 2.4, 12)
    s.text(1124, 338, "DRIFT_DETECTED", 20, 700, RED, font=MONO)
    s.text(1124, 370, "变化字段：portfolio", 15, 400, MUTED)
    s.text(1124, 392, "旧前提下的结论不再沿用", 15, 400, MUTED)
    s.arrow([(1320, 410), (1320, 480)], GREEN, 2.2)
    s.text(1334, 452, "用户确认使用新资料", 15, 700, GREEN)
    s.rect(1100, 480, 440, 96, CARD, GREEN, 2.2, 12)
    s.text(1124, 518, "LOCKED · revision 2", 20, 700, GREEN, font=MONO)
    s.text(1124, 550, "按最新前提重新分析", 15, 400, MUTED)
    # unverified branch
    s.rect(834, 300, 220, 110, CARD, LINE, 1.5, 12, dash="6 5")
    s.text(944, 338, "UNVERIFIED", 18, 700, AMBER, "middle", MONO)
    s.text(944, 366, "沿用旧版本号校验", 14, 400, MUTED, "middle")
    s.text(944, 388, "不予通过", 14, 400, MUTED, "middle")
    s.arrow([(1100, 355), (1054, 355)], AMBER, 2, dash="6 4")
    s.rect(834, 600, 706, 76, CARD, LINE, 1.5, 12)
    s.text(856, 632, "记忆受控恢复", 16, 700, BRAND)
    s.text(856, 658, "校验账户归属与事实一致性；模型排序结果仅用于检索相关记录。", 15, 400, INK)
    s.save("fig-s19-gates-session-drift.svg")


if __name__ == "__main__":
    for fn in (fig_functions, fig_layers, fig_skillhub, fig_penetration, fig_evidence, fig_dag_rebalance, fig_gates_drift):
        fn()
    print("written:", sorted(p.name for p in OUT.glob("*.svg")))
