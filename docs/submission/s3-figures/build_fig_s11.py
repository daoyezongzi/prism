"""S3 defense deck page 11 figure in the deck's navy/blue palette.

Same layered layout as fig-s14 (layer label column + chips + right-side
responsibility panel), recoloured to match the blue-white slide template.
Run:  python docs/submission/s3-figures/build_fig_s11.py
      node docs/submission/s3-figures/render_png.mjs
"""

from __future__ import annotations

from build_figures import MONO, Svg

NAVY = "#0B2E59"
BLUE = "#1F5FBF"
BLUE_SOFT = "#E8F0FC"
BLUE_PALE = "#F4F8FE"
LINE = "#C9D8EE"
INK = "#1B2533"
MUTED = "#5A6B82"
LIGHT = "#CFE0F7"
WHITE = "#FFFFFF"

L, R = 230, 1330  # chip column inside layers


def layer(s: Svg, y, h, name, tech, chips, *, focus=False):
    s.rect(30, y, R - 30, h, NAVY if focus else BLUE_PALE, None if focus else LINE, 1.5, 14)
    s.text(50, y + h / 2 - 4, name, 22, 700, WHITE if focus else NAVY)
    s.text(50, y + h / 2 + 22, tech, 14, 400, LIGHT if focus else MUTED)
    n = len(chips)
    gap = 44 if focus else 14
    cw = (R - L - 20 - (n - 1) * gap) / n
    for i, (t, sub) in enumerate(chips):
        x = L + i * (cw + gap)
        s.box(x, y + 16, cw, h - 32, t, sub, fill=WHITE, stroke=None if focus else LINE,
              tcolor=NAVY, scolor=MUTED, tsize=20, ssize=15)
        if focus:
            s.badge(x + 22, y + 38, str(i + 1), fill=BLUE, r=13, size=15)
            if i < n - 1:
                s.arrow([(x + cw + 6, y + h / 2), (x + cw + gap - 6, y + h / 2)], LIGHT, 2.5)


def fig_s11() -> None:
    s = Svg(1600, 790)

    layer(s, 20, 112, "交互入口", "浏览器工作台", [
        ("咨询", "意图识别"), ("问卷与持仓", "确认资料"),
        ("研究工作台", "选定任务"), ("分析结果", "SSE 流式回传")])
    s.arrow([(680, 132), (680, 168)], BLUE, 2)
    s.text(692, 156, "HTTP / SSE", 14, 400, MUTED)

    layer(s, 168, 112, "应用服务", "FastAPI · Pydantic", [
        ("请求校验", "参数 · 账户归属"), ("锁定前提", "画像 · 持仓版本"),
        ("研究编排", "依赖 · 时间预算"), ("合并回执", "状态 · 引用")])
    s.arrow([(680, 280), (680, 316)], BLUE, 2)
    s.text(692, 304, "领域调用", 14, 400, MUTED)

    layer(s, 316, 140, "金融领域", "Python · Decimal", [
        ("画像预算", "风险适当性"), ("证据核验", "来源 · 口径"),
        ("组合计算", "穿透 · 调仓"), ("独立审查", "风险 · 合规")], focus=True)

    # bottom: adapters + storage
    y4, h4 = 496, 132
    s.arrow([(420, 456), (420, y4)], BLUE, 2)
    s.text(432, 484, "数据查询 · 模型推理", 14, 400, MUTED)
    s.arrow([(1010, 456), (1010, y4)], BLUE, 2)
    s.text(1022, 484, "快照读写", 14, 400, MUTED)

    s.rect(30, y4, 650, h4, BLUE_PALE, LINE, 1.5, 14)
    s.text(50, y4 + 40, "外部金融适配", 22, 700, NAVY)
    ext = [("问财 SkillHub", "9 项金融 Skill"), ("iFinD", "数据适配"), ("模型接口", "可切换")]
    ew = (680 - 50 - 20 - 2 * 12) / 3
    for i, (t, sub) in enumerate(ext):
        s.box(50 + i * (ew + 12), y4 + 56, ew, 62, t, sub, fill=WHITE, stroke=LINE,
              tcolor=NAVY, scolor=MUTED, tsize=18, ssize=14)

    s.rect(710, y4, R - 710, h4, BLUE_PALE, LINE, 1.5, 14)
    s.text(730, y4 + 40, "版本化存储", 22, 700, NAVY)
    s.text(730, y4 + 76, "SQLite / PostgreSQL", 18, 700, INK)
    s.text(730, y4 + 104, "画像与持仓快照 · 研究事实 · 结论回执", 15, 400, MUTED)

    # provider result strip
    y5, h5 = 668, 102
    s.line([(200, y4 + h4), (200, y5)], BLUE, 2, dash="6 5")
    s.rect(30, y5, R - 30, h5, WHITE, BLUE, 1.8, 14)
    s.text(50, y5 + 42, "ProviderResult", 20, 700, BLUE, font=MONO)
    s.text(50, y5 + 70, "统一标注来源 · 时间 · 缺项", 14, 400, MUTED)
    states = [("成功", "正常采纳，展示来源"), ("部分可用", "只用有效项，列明缺口"),
              ("空结果", "保留原查询条件"), ("失败", "展示异常原因与重试提示")]
    sw_ = (R - L - 20 - 3 * 14) / 4
    for i, (t, sub) in enumerate(states):
        x = L + 30 + i * (sw_ + 14)
        s.rect(x, y5 + 16, sw_ - 30, h5 - 32, BLUE_SOFT, None, 0, 10)
        s.text(x + 18, y5 + 46, t, 18, 700, NAVY)
        s.text(x + 18, y5 + 72, sub, 14, 400, MUTED)

    # right panel
    x0, pw = 1360, 210
    s.rect(x0, 20, pw, 112, WHITE, LINE, 1.5, 12)
    s.text(x0 + 18, 52, "图例", 17, 700, NAVY)
    s.rect(x0 + 18, 68, 26, 18, NAVY, None, 0, 4)
    s.text(x0 + 54, 83, "确定性计算核心", 16, 400, INK)
    s.rect(x0 + 18, 100, 26, 18, BLUE_PALE, LINE, 1.5, 4)
    s.text(x0 + 54, 115, "接入与基础设施", 16, 400, INK)

    s.rect(x0, 168, pw, 288, WHITE, NAVY, 2, 12)
    s.text(x0 + 18, 204, "职责隔离", 19, 700, NAVY)
    s.text(x0 + 18, 244, "大模型", 16, 700, INK)
    s.text(x0 + 18, 270, "意图识别 · 工具选择", 15, 400, MUTED)
    s.text(x0 + 18, 294, "结论通俗表达", 15, 400, MUTED)
    s.text(x0 + 18, 318, "不参与金融计算", 15, 700, BLUE)
    s.line([(x0 + 18, 340), (x0 + pw - 18, 340)], LINE, 1)
    s.text(x0 + 18, 372, "领域程序", 16, 700, INK)
    s.text(x0 + 18, 398, "金额 · 比例 · 手数", 15, 400, MUTED)
    s.text(x0 + 18, 422, "风险与合规裁决", 15, 400, MUTED)

    s.rect(x0, 496, pw, 274, WHITE, LINE, 1.5, 12)
    s.text(x0 + 18, 532, "可回溯", 19, 700, NAVY)
    for i, t in enumerate(["每项数据带来源", "与取数时点", "计算基于锁定版本", "结论附状态与引用"]):
        s.text(x0 + 18, 572 + i * 30, t, 15, 400, MUTED)

    s.save("fig-s11-model-service-split.svg")


if __name__ == "__main__":
    fig_s11()
    print("written: fig-s11-model-service-split.svg")
