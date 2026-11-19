"""S3 defense deck page 11 figure: model understands, server computes and reviews.

Same layered layout as fig-s14 (layer label column + chips + right-side
responsibility panel). Each layer has its own hue so blocks separate at a
glance on the blue slide template.
Run:  python docs/submission/s3-figures/build_fig_s11.py
      node docs/submission/s3-figures/render_png.mjs
"""

from __future__ import annotations

from build_figures import MONO, Svg

INK = "#1B2533"
MUTED = "#5A6B82"
ARROW = "#6B7A90"
WHITE = "#FFFFFF"

# hue: (accent, soft zone fill, card border)
ORANGE = ("#E07020", "#FDF1E7", "#F3C9A6")
BLUE = ("#2F6FD6", "#EBF2FD", "#BCD2F2")
TEAL = ("#13806A", "#E5F4EF", "#9FD3C4")
AMBER = ("#C98A0B", "#FDF6E2", "#EED79A")
SLATE = ("#4A5568", "#F0F2F5", "#C9CFD8")
PURPLE = ("#6E49B8", "#F3EEFB", "#D2C3EE")
GREEN_S = "#1E8A4C"
RED_S = "#C0362C"

L, R = 230, 1330  # chip column inside layers


def tab(s: Svg, x, y, w, h, name, tech, hue):
    """Solid coloured label block on the left of a zone."""
    acc = hue[0]
    s.rect(x, y, w, h, acc, None, 0, 10)
    s.text(x + 18, y + h / 2 - 4, name, 22, 700, WHITE)
    s.text(x + 18, y + h / 2 + 22, tech, 14, 400, "#EEF2F7")


def layer(s: Svg, y, h, name, tech, chips, hue, *, steps=False):
    acc, soft, line = hue
    s.rect(30, y, R - 30, h, soft, line, 1.5, 14)
    tab(s, 42, y + 12, L - 60, h - 24, name, tech, hue)
    n = len(chips)
    gap = 44 if steps else 14
    cw = (R - L - 20 - (n - 1) * gap) / n
    for i, (t, sub) in enumerate(chips):
        x = L + i * (cw + gap)
        s.box(x, y + 16, cw, h - 32, t, sub, fill=WHITE, stroke=acc if steps else line,
              sw=2 if steps else 1.5, tcolor=acc, scolor=MUTED, tsize=20, ssize=15)
        if steps:
            s.badge(x + 22, y + 38, str(i + 1), fill=acc, r=13, size=15)
            if i < n - 1:
                s.arrow([(x + cw + 6, y + h / 2), (x + cw + gap - 6, y + h / 2)], acc, 2.5)


def down(s: Svg, x, y1, y2, label):
    s.arrow([(x, y1), (x, y2)], ARROW, 2)
    s.text(x + 12, y2 - 12, label, 14, 400, MUTED)


def fig_s11() -> None:
    s = Svg(1600, 790)

    layer(s, 20, 112, "交互入口", "浏览器工作台", [
        ("咨询", "意图识别"), ("问卷与持仓", "确认资料"),
        ("研究工作台", "选定任务"), ("分析结果", "SSE 流式回传")], ORANGE)
    down(s, 680, 132, 168, "HTTP / SSE")

    layer(s, 168, 112, "应用服务", "FastAPI · Pydantic", [
        ("请求校验", "参数 · 账户归属"), ("锁定前提", "画像 · 持仓版本"),
        ("研究编排", "依赖 · 时间预算"), ("合并回执", "状态 · 引用")], BLUE)
    down(s, 680, 280, 316, "领域调用")

    layer(s, 316, 140, "金融领域", "Python · Decimal", [
        ("画像预算", "风险适当性"), ("证据核验", "来源 · 口径"),
        ("组合计算", "穿透 · 调仓"), ("独立审查", "风险 · 合规")], TEAL, steps=True)

    # bottom: adapters + storage
    y4, h4 = 496, 132
    down(s, 420, 456, y4, "数据查询 · 模型推理")
    down(s, 1010, 456, y4, "快照读写")

    acc, soft, line = AMBER
    s.rect(30, y4, 650, h4, soft, line, 1.5, 14)
    s.rect(42, y4 + 12, 160, 34, acc, None, 0, 8)
    s.text(122, y4 + 36, "外部金融适配", 18, 700, WHITE, "middle")
    ext = [("问财 SkillHub", "9 项金融 Skill"), ("iFinD", "数据适配"), ("模型接口", "可切换")]
    ew = (680 - 42 - 12 - 2 * 12) / 3
    for i, (t, sub) in enumerate(ext):
        s.box(42 + i * (ew + 12), y4 + 56, ew, 64, t, sub, fill=WHITE, stroke=line,
              tcolor=acc, scolor=MUTED, tsize=18, ssize=14)

    acc, soft, line = SLATE
    s.rect(710, y4, R - 710, h4, soft, line, 1.5, 14)
    s.rect(722, y4 + 12, 136, 34, acc, None, 0, 8)
    s.text(790, y4 + 36, "版本化存储", 18, 700, WHITE, "middle")
    dbs = [("SQLite / PostgreSQL", "关系库"), ("快照与回执", "画像 · 持仓 · 研究事实")]
    dw = (R - 722 - 12 - 12) / 2
    for i, (t, sub) in enumerate(dbs):
        s.box(722 + i * (dw + 12), y4 + 56, dw, 64, t, sub, fill=WHITE, stroke=line,
              tcolor=acc, scolor=MUTED, tsize=18, ssize=14)

    # provider result strip
    y5, h5 = 668, 102
    acc, soft, line = PURPLE
    s.line([(200, y4 + h4), (200, y5)], AMBER[0], 2, dash="6 5")
    s.rect(30, y5, R - 30, h5, soft, line, 1.5, 14)
    s.rect(42, y5 + 12, L - 60, h5 - 24, acc, None, 0, 10)
    s.text(60, y5 + 44, "ProviderResult", 18, 700, WHITE, font=MONO)
    s.text(60, y5 + 68, "来源 · 时间 · 缺项", 14, 400, "#EEF2F7")
    states = [("成功", "正常采纳，展示来源", GREEN_S), ("部分可用", "只用有效项，列明缺口", AMBER[0]),
              ("空结果", "保留原查询条件", SLATE[0]), ("失败", "展示异常原因与重试提示", RED_S)]
    sw_ = (R - L - 20 - 3 * 14) / 4
    for i, (t, sub, c) in enumerate(states):
        x = L + i * (sw_ + 14)
        s.rect(x, y5 + 16, sw_, h5 - 32, WHITE, line, 1.5, 10)
        s.rect(x, y5 + 16, 6, h5 - 32, c, None, 0, 3)
        s.text(x + 22, y5 + 46, t, 18, 700, c)
        s.text(x + 22, y5 + 72, sub, 14, 400, MUTED)

    # right panel: responsibility split
    x0, pw = 1360, 210
    s.rect(x0, 20, pw, 436, WHITE, "#C9D8EE", 1.5, 12)
    s.text(x0 + 18, 56, "职责隔离", 20, 700, INK)
    a = AMBER
    s.rect(x0 + 14, 74, pw - 28, 170, a[1], a[2], 1.5, 10)
    s.text(x0 + 28, 106, "大模型", 18, 700, a[0])
    for i, t in enumerate(["意图识别 · 工具选择", "结论通俗表达"]):
        s.text(x0 + 28, 138 + i * 26, t, 15, 400, INK)
    s.text(x0 + 28, 222, "不参与金融计算", 15, 700, RED_S)
    t_ = TEAL
    s.rect(x0 + 14, 260, pw - 28, 180, t_[1], t_[2], 1.5, 10)
    s.text(x0 + 28, 292, "领域程序", 18, 700, t_[0])
    for i, t in enumerate(["金额 · 比例 · 手数", "风险与合规裁决", "Decimal 确定性计算"]):
        s.text(x0 + 28, 324 + i * 26, t, 15, 400, INK)

    p = PURPLE
    s.rect(x0, 496, pw, 274, WHITE, "#C9D8EE", 1.5, 12)
    s.text(x0 + 18, 532, "可回溯", 20, 700, INK)
    for i, t in enumerate(["数据带来源与时点", "计算基于锁定版本", "结论附状态与引用"]):
        s.add(f'<circle cx="{x0 + 26}" cy="{567 + i * 40}" r="5" fill="{p[0]}"/>')
        s.text(x0 + 40, 572 + i * 40, t, 15, 400, INK)

    s.save("fig-s11-model-service-split.svg")


if __name__ == "__main__":
    fig_s11()
    print("written: fig-s11-model-service-split.svg")
