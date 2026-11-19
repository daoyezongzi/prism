"""Blue-white figures for the S2 solution document.

Rules: Chinese only, no variable names or status codes, one navy focal
element per figure, no subtitle or footnote lines.
Run:  python docs/submission/s2-blue-figures/build_figures.py
"""

from __future__ import annotations

import math

from svg_kit import BLUE, BLUE_MID, BLUE_PALE, BLUE_SOFT, INK, LINE, MUTED, NAVY, OUT, RED, RED_SOFT, WHITE, Svg

LIGHT = "#CFE0F7"


def chain(s: Svg, items, x, y, w, h, gap, focus=None, tsize=24, ssize=19):
    """Horizontal row of cards joined by arrows; returns left x of each card."""
    xs = []
    for i, it in enumerate(items):
        t, sub = (it, None) if isinstance(it, str) else it
        xi = x + i * (w + gap)
        s.card(xi, y, w, h, t, sub, focus=(i == focus), tsize=tsize, ssize=ssize)
        if i:
            s.arrow([(xi - gap + 4, y + h / 2), (xi - 4, y + h / 2)])
        xs.append(xi)
    return xs


def zone(s: Svg, x, y, w, h, title, fill=BLUE_PALE):
    s.rect(x, y, w, h, fill, LINE, 1.5, 14)
    s.text(x + 22, y + 40, title, 24, 700, NAVY)


def note_box(s: Svg, x, y, w, h, text, focus=False, size=22):
    s.rect(x, y, w, h, NAVY if focus else BLUE_SOFT, None, 0, 12)
    s.text(x + w / 2, y + h / 2 + size * 0.36, text, size, 700, WHITE if focus else NAVY, "middle")


# ------------------------------------------------------------------ 1-1
def fig_1_1():
    s = Svg(1200, 540)
    s.rect(20, 20, 1160, 100, NAVY, None, 0, 14)
    s.text(52, 88, "82.05%", 52, 700, WHITE)
    s.text(300, 82, "的受访者曾因看不懂、拿不准而推迟或放弃投资", 26, 700, WHITE)
    s.text(40, 170, "三个困扰", 24, 700, NAVY)
    s.text(700, 170, "我们的回应", 24, 700, NAVY)
    rows = [("信息太多，不知道看什么", 58.97, "重点筛选", "只看与自己持仓相关的要点"),
            ("来源分散，要来回切换平台", 53.85, "统一查询", "行情、财报、公告一处查齐"),
            ("难以判断信息是否可靠", 48.72, "依据展示", "每个结论都附来源和时间")]
    for i, (q, v, a, d) in enumerate(rows):
        y = 196 + i * 112
        s.text(40, y + 26, q, 22, 400, INK)
        s.rect(40, y + 42, 560, 34, BLUE_PALE, None, 0, 6)
        s.rect(40, y + 42, 560 * v / 100, 34, BLUE, None, 0, 6)
        s.text(40 + 560 * v / 100 + 12, y + 68, f"{v:.2f}%", 22, 700, NAVY)
        s.arrow([(612, y + 59), (694, y + 59)], BLUE_MID, 2)
        s.rect(700, y + 8, 460, 88, WHITE, LINE, 1.5, 12)
        s.rect(700, y + 8, 8, 88, BLUE, None, 0, 4)
        s.text(728, y + 46, a, 24, 700, NAVY)
        s.text(728, y + 80, d, 20, 400, MUTED)
    s.save("fig-1-1-investor-needs.svg")


# ------------------------------------------------------------------ 1-2
def fig_1_2():
    s = Svg(1200, 470)
    stages = [("说清需求", ["确认个人画像", "提出投资问题"]),
              ("查数分析", ["查询行情财报", "研究与计算"]),
              ("把关交付", ["依据与合规审查", "给出结论与提示"])]
    for i, (title, cards) in enumerate(stages):
        x = 20 + i * 400
        zone(s, x, 20, 360, 330, title)
        for j, c in enumerate(cards):
            s.card(x + 30, 80 + j * 130, 300, 96, c, focus=(i == 2 and j == 0))
            if j == 0:
                s.arrow([(x + 180, 176), (x + 180, 210)])
        if i < 2:
            s.arrow([(x + 362, 185), (x + 398, 185)])
    # loop back
    s.line([(980, 350), (980, 420), (200, 420)], BLUE_MID, 2, "8 6")
    s.arrow([(200, 420), (200, 352)], BLUE_MID, 2, "8 6")
    s.text(590, 410, "资料不全时退回补充", 22, 700, BLUE, "middle")
    s.save("fig-1-2-service-flow.svg")


# ------------------------------------------------------------------ 1-3
def fig_1_3():
    s = Svg(1200, 520)
    s.card(400, 20, 400, 80, "用户提问与个人资料")
    s.arrow([(600, 100), (600, 140)])
    s.card(400, 140, 400, 80, "服务端校验并分派任务")
    s.line([(600, 220), (600, 250), (300, 250), (300, 280)], BLUE, 2.2)
    s.arrow([(300, 250), (300, 284)])
    s.arrow([(600, 250), (900, 250), (900, 284)])
    zone(s, 40, 284, 520, 150, "大模型：负责听懂")
    s.text(62, 370, "理解问题 · 选择工具 · 解释结果", 22, 400, INK)
    s.rect(640, 284, 520, 150, NAVY, None, 0, 14)
    s.text(662, 324, "程序：负责算准", 24, 700, WHITE)
    s.text(662, 370, "查询数据 · 计算金额比例 · 风险审查", 22, 400, LIGHT)
    s.line([(600, 270), (600, 450)], BLUE_MID, 2, "6 6")
    s.text(600, 480, "数值一律由程序计算，模型不改写结果", 22, 700, NAVY, "middle")
    s.save("fig-1-3-tech-route.svg")


# ------------------------------------------------------------------ 2-1
def fig_2_1():
    s = Svg(1200, 470)
    x0, x1 = 230, 1090
    days = 51  # 8.1 - 9.20
    dx = lambda d: x0 + (x1 - x0) * d / days
    phases = [("项目启动", 0, 5), ("方案规划", 5, 15), ("开发实现", 15, 42), ("测试优化", 42, 45), ("总结交付", 45, 51)]
    for tick, d in [("8.1", 0), ("8.16", 15), ("9.1", 31), ("9.12", 42), ("9.20", 51)]:
        s.line([(dx(d), 40), (dx(d), 350)], LINE, 1.2)
        s.text(dx(d), 30, tick, 20, 700, MUTED, "middle")
    for i, (name, a, b) in enumerate(phases):
        y = 60 + i * 58
        s.text(40, y + 30, name, 22, 700, NAVY)
        focus = name == "开发实现"
        s.rect(dx(a), y + 6, max(dx(b) - dx(a), 10), 34, NAVY if focus else BLUE_MID, None, 0, 6)
    outs = [("需求分析", 5), ("产品方案", 15), ("可运行系统", 42), ("测试记录", 45), ("文档与演示", 51)]
    s.line([(x0, 400), (x1, 400)], BLUE, 2)
    for i, (o, d) in enumerate(outs):
        s.add(f'<circle cx="{dx(d):.1f}" cy="400" r="8" fill="{BLUE}"/>')
        s.text(dx(d), 440 if i % 2 == 0 else 380, o, 20, 700, INK, "middle")
    s.text(40, 408, "交付物", 22, 700, NAVY)
    s.save("fig-2-1-schedule.svg")


# ------------------------------------------------------------------ 2-2
def fig_2_2():
    s = Svg(1200, 500)
    lanes = ["用户", "系统", "审查"]
    for i, l in enumerate(lanes):
        y = 20 + i * 150
        s.rect(20, y, 1160, 140, BLUE_PALE if i != 2 else WHITE, LINE, 1.5, 12)
        s.text(60, y + 78, l, 24, 700, NAVY, "middle")
    s.line([(100, 20), (100, 460)], LINE, 1.5)
    s.card(130, 45, 190, 90, "完成测评")
    s.arrow([(320, 90), (370, 90)])
    s.card(370, 45, 190, 90, "提出问题")
    s.arrow([(465, 135), (465, 195)])
    xs = chain(s, ["识别问题", "查询数据", "计算与核对"], 370, 195, 190, 90, 50)
    s.arrow([(xs[2] + 95, 285), (xs[2] + 95, 345)])
    s.card(xs[2], 345, 190, 90, "风险合规审查", focus=True)
    s.arrow([(xs[2] + 190, 390), (1110, 390), (1110, 135)])
    s.card(910, 45, 240, 90, "查看结论与依据")
    s.line([(xs[2], 400), (225, 400), (225, 142)], BLUE_MID, 2, "8 6")
    s.arrow([(225, 160), (225, 137)], BLUE_MID, 2)
    s.text(470, 430, "资料待补充时退回确认", 20, 700, BLUE, "middle")
    s.save("fig-2-2-business-flow.svg")


# ------------------------------------------------------------------ 3-1
def fig_3_1():
    s = Svg(1200, 560)
    def layer(y, h, name, chips, focus=False):
        s.rect(20, y, 1160, h, NAVY if focus else BLUE_PALE, None if focus else LINE, 1.5, 14)
        s.text(44, y + h / 2 + 9, name, 24, 700, WHITE if focus else NAVY)
        cw = (1160 - 230 - 20 - (len(chips) - 1) * 14) / len(chips)
        for i, c in enumerate(chips):
            x = 250 + i * (cw + 14)
            s.rect(x, y + 16, cw, h - 32, WHITE, None if focus else LINE, 1.5, 10)
            s.text(x + cw / 2, y + h / 2 + 8, c, 22, 700, NAVY, "middle")
    layer(20, 96, "浏览器工作台", ["对话", "测评", "持仓", "行情", "研究"])
    s.arrow([(600, 116), (600, 146)])
    layer(146, 96, "服务接口", ["校验身份与参数", "协调任务", "流式返回进度"])
    s.arrow([(600, 242), (600, 272)])
    layer(272, 110, "领域计算", ["画像", "组合", "研究", "风险", "合规"], focus=True)
    s.arrow([(320, 382), (320, 412)])
    s.arrow([(880, 382), (880, 412)])
    s.rect(20, 412, 570, 120, BLUE_PALE, LINE, 1.5, 14)
    s.text(44, 462, "外部能力", 24, 700, NAVY)
    s.text(44, 502, "问财金融数据 · 大模型接口", 22, 400, INK)
    s.rect(610, 412, 570, 120, BLUE_PALE, LINE, 1.5, 14)
    s.text(634, 462, "数据存储", 24, 700, NAVY)
    s.text(634, 502, "SQLite / PostgreSQL · 版本留痕", 22, 400, INK)
    s.save("fig-3-1-architecture.svg")


# ------------------------------------------------------------------ 3-2
def fig_3_2():
    s = Svg(1200, 520)
    s.text(40, 46, "提示词由五部分组成", 24, 700, NAVY)
    parts = ["系统规则", "已确认的个人资料", "最近 6 条消息", "用户问题", "工具返回结果"]
    for i, p in enumerate(parts):
        y = 70 + i * 74
        s.rect(40, y, 400, 62, BLUE_SOFT if i % 2 == 0 else WHITE, LINE, 1.5, 10)
        s.text(240, y + 39, p, 22, 700, NAVY, "middle")
    s.arrow([(446, 255), (510, 255)])
    s.card(510, 205, 150, 100, "大模型", focus=False, tsize=26)
    s.arrow([(666, 255), (720, 255)])
    # tool loop 2x2
    s.text(730, 46, "工具调用四步", 24, 700, NAVY)
    pos = [(730, 80), (970, 80), (970, 300), (730, 300)]
    names = ["模型提出调用", "服务端校验", "执行查询", "结果回填"]
    for i, ((x, y), n) in enumerate(zip(pos, names)):
        s.card(x, y, 200, 110, n, focus=(i == 1))
    s.arrow([(930, 135), (970, 135)])
    s.arrow([(1070, 190), (1070, 300)])
    s.arrow([(970, 355), (930, 355)])
    s.arrow([(830, 300), (830, 190)])
    s.text(950, 470, "任何一步失败：说明缺口，不补造数据", 22, 700, RED, "middle")
    s.save("fig-3-2-prompt-tools.svg")


# ------------------------------------------------------------------ 3-3
def fig_3_3():
    s = Svg(1200, 480)
    s.rect(20, 20, 1160, 330, WHITE, LINE, 2, 14)
    s.rect(20, 20, 1160, 50, BLUE_SOFT, None, 0, 14)
    for i in range(3):
        s.add(f'<circle cx="{50 + i * 26}" cy="45" r="8" fill="{BLUE_MID}"/>')
    s.text(600, 53, "浏览器工作台", 22, 700, NAVY, "middle")
    blocks = [("页面骨架", "导航与六个页面"), ("状态与路由", "按账户隔离的数据与跳转"), ("研究页面", "查数据 · 找资料 · 算指标")]
    for i, (t, d) in enumerate(blocks):
        s.card(50 + i * 375, 100, 345, 110, t, d, focus=(i == 1))
    libs = [("流程画布", "AntV X6"), ("行情图表", "Lightweight Charts"), ("文本安全渲染", "marked + DOMPurify")]
    for i, (t, d) in enumerate(libs):
        s.card(50 + i * 375, 236, 345, 90, t, d, fill=BLUE_PALE, tsize=22, ssize=18)
    s.arrow([(420, 352), (420, 410)])
    s.arrow([(780, 410), (780, 352)])
    s.text(400, 390, "提交请求", 20, 700, BLUE, "end")
    s.text(800, 390, "流式返回结果", 20, 700, BLUE)
    s.card(300, 410, 600, 56, "后端服务", tsize=22)
    s.save("fig-3-3-frontend.svg")


# ------------------------------------------------------------------ 3-4
def fig_3_4():
    s = Svg(1200, 400)
    xs = chain(s, [("接口层", "校验参数与权限"), ("应用服务", "协调读取与执行")], 40, 60, 260, 110, 60)
    s.rect(700, 30, 460, 170, WHITE, BLUE, 2, 14, dash="10 7")
    s.text(930, 58, "不发起任何网络请求", 20, 700, BLUE, "middle")
    s.card(740, 74, 380, 106, "领域模块", "画像 · 组合 · 预算 · 审查", focus=True)
    s.arrow([(620, 115), (740, 127)])
    s.arrow([(490, 170), (490, 240), (330, 240), (330, 270)])
    s.arrow([(490, 240), (650, 240), (650, 270)])
    s.card(180, 270, 300, 110, "外部适配", "金融数据 · 大模型")
    s.card(500, 270, 300, 110, "存储", "事务与版本")
    note_box(s, 840, 270, 320, 110, "可脱离网络单独测试")
    s.save("fig-3-4-backend.svg")


# ------------------------------------------------------------------ 3-5
def fig_3_5():
    s = Svg(1200, 470)
    pages = [("对话工作台", "提问与追问"), ("持仓分析", "资产结构与风险"), ("个人中心", "测评与画像"),
             ("市场观察", "指数与行情"), ("研究工作台", "查数据 · 找资料 · 算指标"), ("技能商店", "能力与启用状态")]
    for i, (t, d) in enumerate(pages):
        x = 20 + (i % 3) * 393
        y = 20 + (i // 3) * 130
        s.card(x, y, 373, 110, t, d)
    s.rect(20, 300, 1160, 150, NAVY, None, 0, 14)
    s.text(44, 344, "所有页面统一五种状态", 24, 700, WHITE)
    states = ["加载中", "成功", "部分可用", "空结果", "失败"]
    for i, st in enumerate(states):
        x = 44 + i * 224
        s.rect(x, 368, 200, 60, WHITE if st != "失败" else RED_SOFT, None, 0, 30)
        s.text(x + 100, 406, st, 22, 700, NAVY if st != "失败" else RED, "middle")
    s.save("fig-3-5-pages-states.svg")


# ------------------------------------------------------------------ 3-6
def fig_3_6():
    s = Svg(1200, 520)
    def ent(x, y, name, w=200):
        s.card(x, y, w, 70, name, tsize=22)
    def link(a, b, label):
        s.arrow([a, b], BLUE, 2)
        s.text((a[0] + b[0]) / 2, a[1] - 12, label, 18, 700, MUTED, "middle")
    groups = [("账户", 20, 20), ("对话", 610, 20), ("研究记录", 20, 270), ("参考资料", 610, 270)]
    for name, x, y in groups:
        s.rect(x, y, 570, 230, BLUE_PALE, LINE, 1.5, 14)
        s.text(x + 22, y + 40, name, 24, 700, NAVY)
    ent(50, 110, "本地账户"); link((250, 145), (350, 145), "用户名"); ent(350, 110, "登录会话")
    ent(640, 110, "对话"); link((840, 145), (940, 145), "对话编号"); ent(940, 110, "消息")
    s.card(50, 335, 200, 110, "研究快照", focus=True, tsize=22)
    s.arrow([(250, 390), (330, 340)], BLUE, 2); s.card(330, 300, 230, 70, "研究事实", tsize=22)
    s.arrow([(250, 440), (330, 440)], BLUE, 2); s.card(330, 405, 230, 70, "原始请求与响应", tsize=21)
    s.text(150, 478, "按用户与快照共同关联", 18, 700, BLUE, "middle")
    ent(630, 380, "资料", 150); s.arrow([(780, 415), (810, 415)], BLUE, 2)
    ent(810, 380, "资料版本", 150); s.arrow([(960, 415), (990, 415)], BLUE, 2)
    ent(990, 380, "检索片段", 170)
    s.save("fig-3-6-database.svg")


# ------------------------------------------------------------------ 3-7
def fig_3_7():
    s = Svg(1200, 420)
    ins = ["已确认问卷", "当前持仓", "数据模式", "规则版本"]
    for i, t in enumerate(ins):
        s.card(20, 20 + i * 98, 240, 80, t, tsize=22)
        s.line([(260, 60 + i * 98), (320, 60 + i * 98), (320, 205)], BLUE, 2)
    s.arrow([(320, 205), (380, 205)])
    s.card(380, 125, 300, 160, "资料指纹", "任一项变化，指纹即变", focus=True, tsize=28)
    s.arrow([(680, 205), (740, 205)])
    s.card(740, 145, 190, 120, "会话前提", "带版本号")
    s.arrow([(930, 205), (980, 205)])
    s.card(980, 145, 200, 120, "决策回执", "记录依据")
    s.save("fig-3-7-premise-lock.svg")


# ------------------------------------------------------------------ 3-8
def fig_3_8():
    s = Svg(1200, 500)
    s.card(20, 190, 200, 100, "查询请求")
    s.arrow([(220, 240), (270, 240)])
    s.card(270, 180, 240, 120, "金融数据接口", "问财等提供方")
    s.arrow([(510, 240), (570, 240)])
    s.card(570, 180, 140, 120, "返回结果", focus=True, tsize=24)
    rows = [("完整返回", "直接进入计算", "blue"), ("部分返回", "标出缺项，只用可用字段", "blue"),
            ("没有数据", "如实显示为空，不补值", "blue"), ("请求失败", "提示原因，可稍后重试", "red")]
    for i, (a, b, k) in enumerate(rows):
        y = 30 + i * 115
        s.line([(710, 240), (750, 240), (750, y + 45), (790, y + 45)], BLUE, 2)
        s.arrow([(770, y + 45), (792, y + 45)])
        red = k == "red"
        s.rect(792, y, 388, 90, RED_SOFT if red else WHITE, RED if red else LINE, 1.5, 12)
        s.text(816, y + 40, a, 24, 700, RED if red else NAVY)
        s.text(816, y + 72, b, 20, 400, MUTED)
    s.save("fig-3-8-provider-states.svg")


# ------------------------------------------------------------------ 3-9
def fig_3_9():
    s = Svg(1200, 600)
    chain(s, ["19 题测评", "八维评分", "取风险分数", "用户确认"], 40, 24, 245, 84, 40, focus=3)
    x0, x1, ly = 80, 1120, 190
    sx = lambda v: x0 + (x1 - x0) * v / 100
    bands = [(0, 33, "保守型", "#DCE7F8", NAVY), (33, 66, "平衡型", "#A9C4EE", NAVY), (66, 100, "成长型", BLUE_MID, WHITE)]
    for a, b, lab, c, tc in bands:
        s.rect(sx(a), ly, sx(b) - sx(a), 44, c, None, 0, 0)
        s.text((sx(a) + sx(b)) / 2, ly + 31, lab, 24, 700, tc, "middle")
    for v in (0, 33, 66, 100):
        s.line([(sx(v), ly - 8), (sx(v), ly + 56)], NAVY, 2)
        s.text(sx(v), ly + 86, str(v), 20, 700, NAVY, "middle")
    cols = ["单一资产", "已识别行业", "科技行业", "未分类资产"]
    vals = [("20%", "30%", "25%", "10%"), ("35%", "45%", "40%", "20%"), ("50%", "60%", "60%", "35%")]
    ty = 310
    s.line([(40, ty), (1160, ty)], LINE, 1.2)
    for j, c in enumerate(cols):
        s.text(40, ty + 42 + j * 40, c, 22, 400, INK)
        for i, (a, b, *_ ) in enumerate(bands):
            s.text((sx(a) + sx(b)) / 2, ty + 42 + j * 40, vals[i][j], 22, 700, NAVY, "middle")
    s.rect(40, 500, 760, 76, BLUE_PALE, LINE, 1.5, 12)
    s.text(64, 546, "实际占比逐项对照上限，超出多少记多少", 22, 700, NAVY)
    s.arrow([(806, 538), (850, 538)])
    s.pill(856, 518, "需复核", kind="red", size=22)
    s.save("fig-3-9-profile-budget.svg")


# ------------------------------------------------------------------ 3-10
def fig_3_10():
    s = Svg(1200, 560)
    srcs = [("直接持股", "按股票计入"), ("基金 / ETF", "按成分比例拆分"), ("无披露基金", "单列为未分类")]
    for i, (a, b) in enumerate(srcs):
        y = 20 + i * 120
        s.card(20, y, 220, 96, a, tsize=22)
        s.arrow([(240, y + 48), (290, y + 48)])
        s.card(290, y, 260, 96, b, tsize=22)
        s.line([(550, y + 48), (590, y + 48), (590, 188)], BLUE, 2)
    s.arrow([(590, 188), (640, 188)])
    s.card(640, 108, 520, 160, "金额守恒校验", "拆分后合计 = 原持仓市值", focus=True, tsize=28, ssize=22)
    s.arrow([(900, 268), (900, 320)])
    s.card(640, 320, 520, 100, "计算占比与集中度", "仅证券 / 含现金两种口径")
    s.arrow([(900, 420), (900, 460)])
    s.card(640, 460, 520, 80, "对照画像上限，标出超限项", tsize=22)
    s.save("fig-3-10-penetration.svg")


# ------------------------------------------------------------------ 3-11
def fig_3_11():
    s = Svg(1200, 560)
    steps = ["确定调整方向", "忽略 0.5% 以内的微小偏差", "先卖出，按整手取整", "再买入，算出最多可买几手", "复核调整后的风险"]
    for i, t in enumerate(steps):
        y = 20 + i * 106
        focus = i == 3
        s.rect(20, y, 580, 86, NAVY if focus else WHITE, None if focus else LINE, 1.5, 12)
        s.badge(64, y + 43, str(i + 1), WHITE if focus else BLUE, 18, 18)
        if focus:
            s.text(64, y + 49, str(i + 1), 18, 700, NAVY, "middle")
        s.text(100, y + 52, t, 24, 700, WHITE if focus else NAVY)
        if i < 4:
            s.arrow([(310, y + 86), (310, y + 106)], BLUE, 2, size=6)
    s.rect(640, 20, 540, 520, BLUE_PALE, LINE, 1.5, 14)
    s.text(664, 66, "现金逐笔核算", 24, 700, NAVY)
    s.text(910, 122, "调整后现金 = 原现金 + 卖出 − 买入 − 费用", 21, 700, INK, "middle")
    s.line([(664, 150), (1156, 150)], LINE, 1.2)
    s.text(664, 196, "实测案例", 22, 700, NAVY)
    rows = [("原总资产", "1,445,545.00 元"), ("交易费用", "743.15 元"), ("调整后总资产", "1,444,801.85 元")]
    for i, (a, b) in enumerate(rows):
        s.text(664, 250 + i * 50, a, 22, 400, MUTED)
        s.text(1156, 250 + i * 50, b, 22, 700, INK, "end")
    s.line([(664, 400), (1156, 400)], LINE, 1.2)
    s.text(664, 470, "独立复算差额", 24, 700, NAVY)
    s.text(1156, 474, "0.00 元", 34, 700, BLUE, "end")
    s.save("fig-3-11-rebalance.svg")


# ------------------------------------------------------------------ 3-12
def fig_3_12():
    s = Svg(1200, 470)
    s.card(20, 150, 170, 80, "检查依赖", tsize=22)
    s.card(250, 60, 170, 80, "行情查询", tsize=22)
    s.card(250, 240, 170, 80, "持仓分析", tsize=22)
    s.card(480, 150, 150, 80, "汇总", tsize=22)
    s.arrow([(190, 190), (220, 190), (220, 100), (250, 100)])
    s.arrow([(220, 190), (220, 280), (250, 280)])
    s.arrow([(420, 100), (450, 100), (450, 190), (480, 190)])
    s.arrow([(420, 280), (450, 280), (450, 190), (480, 190)])
    s.text(335, 200, "并行执行", 20, 700, BLUE, "middle")
    note_box(s, 20, 360, 610, 80, "超时只取消下游，已完成的结果保留", size=22)
    lim = [("400", "排队总量"), ("200", "单人排队"), ("100", "同时运行"), ("8", "大模型并发")]
    for i, (n, t) in enumerate(lim):
        x = 680 + (i % 2) * 250
        y = 20 + (i // 2) * 140
        s.rect(x, y, 230, 120, WHITE, LINE, 1.5, 12)
        s.text(x + 115, y + 64, n, 40, 700, BLUE, "middle")
        s.text(x + 115, y + 100, t, 20, 400, MUTED, "middle")
    s.rect(680, 300, 480, 140, NAVY, None, 0, 12)
    s.text(920, 380, "60 秒", 52, 700, WHITE, "middle")
    s.text(920, 422, "单次研究总时限", 20, 400, LIGHT, "middle")
    s.save("fig-3-12-research-limits.svg")


# ------------------------------------------------------------------ 3-13
def fig_3_13():
    s = Svg(1200, 560)
    s.rect(20, 20, 520, 520, BLUE_PALE, LINE, 1.5, 14)
    s.text(44, 64, "第一步：同源合并", 24, 700, NAVY)
    recs = ["A 网站原文", "B 网站转载", "C 聚合页面", "交易所公告", "公司年报"]
    for i, lab in enumerate(recs):
        y = 92 + i * 66
        s.rect(44, y, 200, 50, WHITE, LINE, 1.5, 10)
        s.text(144, y + 33, lab, 20, 400, INK, "middle")
    s.line([(244, 117), (280, 117), (280, 249), (244, 249)], BLUE, 2)
    s.line([(244, 183), (280, 183)], BLUE, 2)
    s.arrow([(280, 183), (330, 183)])
    s.card(334, 153, 180, 60, "来源 1", tsize=22)
    s.arrow([(244, 315), (330, 315)])
    s.card(334, 288, 180, 54, "来源 2", tsize=22)
    s.arrow([(244, 381), (330, 381)])
    s.card(334, 354, 180, 54, "来源 3", tsize=22)
    note_box(s, 44, 446, 470, 70, "5 条记录 = 3 个独立来源", focus=True, size=24)

    s.text(580, 64, "第二步：按来源数判定", 24, 700, NAVY)
    gx, gy, cw, ch = 690, 110, 160, 130
    s.text(gx + 1.5 * cw, gy, "反对的来源数", 20, 700, MUTED, "middle")
    for j, lab in enumerate(["0", "1", "≥ 2"]):
        s.text(gx + j * cw + cw / 2, gy + 32, lab, 22, 700, NAVY, "middle")
    s.text(580, gy + 32, "支持的来源数", 18, 700, MUTED)
    ok, pend, few, no = ("成立", "navy"), ("待复核", "gray"), ("证据不足", "blue"), ("不成立", "red")
    cells = [[ok, pend, pend], [few, pend, pend], [few, few, no]]
    for i, rl in enumerate(["≥ 2", "1", "0"]):
        y = gy + 48 + i * ch
        s.text(620, y + ch / 2 + 8, rl, 22, 700, NAVY, "middle")
        for j in range(3):
            x = gx + j * cw
            lab, kind = cells[i][j]
            fill = {"navy": NAVY, "red": RED_SOFT}.get(kind, WHITE)
            s.rect(x + 4, y + 4, cw - 8, ch - 8, fill, None if kind == "navy" else (RED if kind == "red" else LINE), 1.5, 10)
            color = {"navy": WHITE, "red": RED, "gray": MUTED}.get(kind, BLUE)
            s.text(x + cw / 2, y + ch / 2 + 9, lab, 24, 700, color, "middle")
    s.save("fig-3-13-evidence.svg")


# ------------------------------------------------------------------ 3-14
def fig_3_14():
    s = Svg(1200, 500)
    s.card(20, 175, 180, 110, "建议草稿")
    gates = [("风险审查", "画像上限 · 持仓 · 证据", 30), ("合规审查", "事实引用 · 风险提示 · 禁用说法", 270)]
    for t, d, y in gates:
        s.arrow([(200, 230), (230, 230), (230, y + 80), (260, y + 80)])
        s.card(260, y, 380, 160, t, d, tsize=26)
        s.line([(640, y + 80), (680, y + 80), (680, 230)], BLUE, 2.2)
    s.arrow([(680, 230), (720, 230)])
    s.rect(720, 110, 220, 240, NAVY, None, 0, 14)
    s.text(830, 156, "取最严结果", 24, 700, WHITE, "middle")
    for i, (lab, c) in enumerate([("拦截", RED_SOFT), ("需复核", WHITE), ("通过", BLUE_SOFT)]):
        y = 180 + i * 54
        s.rect(760, y, 140, 42, c, None, 0, 21)
        s.text(830, y + 29, lab, 22, 700, RED if lab == "拦截" else NAVY, "middle")
    s.arrow([(940, 180), (980, 180)])
    s.card(980, 120, 200, 110, "给出建议", "附决策回执", tsize=24)
    s.arrow([(940, 290), (980, 290)])
    s.card(980, 250, 200, 90, "不输出建议", tsize=22)
    s.text(600, 482, "两道审查都通过，才会给出建议", 22, 700, NAVY, "middle")
    s.save("fig-3-14-dual-review.svg")


# ------------------------------------------------------------------ 3-15
def fig_3_15():
    s = Svg(1200, 470)
    s.card(20, 40, 200, 110, "上传资料", "TXT · MD · PDF")
    s.arrow([(220, 95), (260, 95)])
    s.card(260, 40, 200, 110, "检查文件", "8 MB · 1000 页以内")
    s.arrow([(360, 150), (360, 210)], RED, 2)
    s.rect(260, 210, 200, 70, RED_SOFT, RED, 1.5, 12)
    s.text(360, 253, "加密或无文字：拒收", 18, 700, RED, "middle")
    s.arrow([(460, 95), (500, 95)])
    s.card(500, 40, 200, 110, "切分段落", "每段 1200 字以内")
    s.arrow([(700, 95), (740, 95), (740, 60), (770, 60)])
    s.arrow([(740, 95), (740, 160), (770, 160)])
    s.card(770, 20, 200, 80, "关键词检索", tsize=22)
    s.card(770, 120, 200, 80, "语义检索", tsize=22)
    s.line([(970, 60), (1000, 60), (1000, 110)], BLUE, 2)
    s.line([(970, 160), (1000, 160), (1000, 110)], BLUE, 2)
    s.arrow([(1000, 110), (1000, 240)])
    s.card(860, 240, 300, 100, "合并排序", "两路结果互相补充", focus=True)
    s.arrow([(1010, 340), (1010, 380)])
    s.card(760, 380, 400, 76, "返回引用：页码与版本", tsize=22)
    note_box(s, 20, 330, 640, 90, "命中只代表相关，金融结论仍需另行核验", size=22)
    s.save("fig-3-15-document-search.svg")


# ------------------------------------------------------------------ 3-16
def fig_3_16():
    s = Svg(1200, 440)
    s.rect(20, 20, 1160, 190, NAVY, None, 0, 14)
    s.text(44, 64, "当前事实：参与计算", 24, 700, WHITE)
    xs = chain(s, ["已确认问卷", "当前持仓", "数据模式"], 44, 90, 220, 90, 30, tsize=22)
    for x in xs:
        pass
    s.arrow([(794, 135), (840, 135)], WHITE)
    s.rect(840, 90, 310, 90, WHITE, None, 0, 12)
    s.text(995, 145, "会话前提 → 计算", 24, 700, NAVY, "middle")
    s.rect(20, 240, 1160, 180, BLUE_PALE, LINE, 1.5, 14)
    s.text(44, 284, "历史记录：只帮助理解", 24, 700, NAVY)
    chain(s, ["最近消息", "已保存资料"], 44, 310, 220, 86, 30, tsize=22)
    s.arrow([(524, 353), (580, 353)])
    s.card(580, 310, 330, 86, "用户主动恢复并确认", tsize=22)
    s.line([(910, 353), (995, 353)], BLUE, 2, "8 6")
    s.arrow([(995, 353), (995, 184)], BLUE, 2, "8 6")
    s.text(1010, 290, "才进入", 20, 700, BLUE)
    s.save("fig-3-16-context.svg")


# ------------------------------------------------------------------ 3-17
def fig_3_17():
    s = Svg(1200, 430)
    s.card(20, 60, 190, 100, "未确认", tsize=24)
    s.arrow([(210, 110), (280, 110)])
    s.text(245, 96, "确认", 18, 700, BLUE, "middle")
    s.card(280, 60, 260, 100, "已锁定", "第 1 版 · 持仓 1,000 股")
    s.arrow([(540, 110), (640, 110)], RED)
    s.text(590, 96, "持仓改动", 18, 700, RED, "middle")
    s.rect(640, 50, 260, 120, RED_SOFT, RED, 2.2, 12)
    s.text(770, 104, "资料已变更", 26, 700, RED, "middle")
    s.text(770, 140, "旧结论不再沿用", 20, 400, RED, "middle")
    s.arrow([(900, 110), (960, 110)])
    s.text(930, 96, "确认", 18, 700, BLUE, "middle")
    s.card(960, 60, 220, 100, "已锁定", "第 2 版", focus=True)
    s.arrow([(1070, 160), (1070, 230)])
    s.card(960, 230, 220, 80, "重新分析", tsize=24)
    s.arrow([(770, 170), (770, 240)], MUTED, 2, "6 5")
    s.rect(640, 240, 260, 80, WHITE, LINE, 1.5, 12, dash="6 5")
    s.text(770, 288, "沿用旧版：不予通过", 20, 700, MUTED, "middle")
    note_box(s, 20, 350, 1160, 60, "画像、持仓、数据模式或规则任一变化，都需要重新确认", size=22)
    s.save("fig-3-17-session-drift.svg")


# ------------------------------------------------------------------ 3-18
def fig_3_18():
    s = Svg(1200, 400)
    s.rect(20, 40, 260, 250, BLUE_PALE, LINE, 1.5, 14)
    s.text(44, 80, "用户提交", 24, 700, NAVY)
    for i, t in enumerate(["历史收益", "财务数据", "来源", "截止日期"]):
        s.text(44, 126 + i * 42, "· " + t, 22, 400, INK)
    s.arrow([(280, 165), (330, 165)])
    s.card(330, 110, 240, 110, "数据校验", "类型 · 样本量 · 时间顺序")
    s.arrow([(570, 165), (620, 165)])
    s.card(620, 110, 240, 110, "后台计算", "独立线程 · 限量运行")
    s.arrow([(860, 165), (890, 165), (890, 90), (920, 90)])
    s.arrow([(890, 165), (890, 250), (920, 250)])
    s.card(920, 40, 260, 110, "计算完成", "附方法版本与输入", focus=True)
    s.rect(920, 200, 260, 100, WHITE, LINE, 1.5, 12)
    s.text(1050, 244, "无法计算", 24, 700, NAVY, "middle")
    s.text(1050, 278, "说明缺少什么", 20, 400, MUTED, "middle")
    s.text(600, 370, "算法不依赖大模型，可离线复现", 22, 700, NAVY, "middle")
    s.save("fig-3-18-algorithms.svg")


# ------------------------------------------------------------------ 4-1
def fig_4_1():
    s = Svg(1200, 440)
    data = [("人力研发", 55, NAVY), ("计算资源", 20, BLUE), ("第三方服务", 10, BLUE_MID),
            ("资源采购", 10, "#A9C4EE"), ("储备资金", 5, "#DCE7F8")]
    cx, cy, r0, r1 = 300, 220, 110, 190
    a = -math.pi / 2
    for name, v, c in data:
        b = a + 2 * math.pi * v / 100
        large = 1 if b - a > math.pi else 0
        p = [(cx + r1 * math.cos(a), cy + r1 * math.sin(a)), (cx + r1 * math.cos(b), cy + r1 * math.sin(b)),
             (cx + r0 * math.cos(b), cy + r0 * math.sin(b)), (cx + r0 * math.cos(a), cy + r0 * math.sin(a))]
        d = (f"M{p[0][0]:.1f},{p[0][1]:.1f} A{r1},{r1} 0 {large} 1 {p[1][0]:.1f},{p[1][1]:.1f} "
             f"L{p[2][0]:.1f},{p[2][1]:.1f} A{r0},{r0} 0 {large} 0 {p[3][0]:.1f},{p[3][1]:.1f} Z")
        s.add(f'<path d="{d}" fill="{c}" stroke="{WHITE}" stroke-width="3"/>')
        a = b
    s.text(cx, cy + 6, "55%", 48, 700, NAVY, "middle")
    s.text(cx, cy + 42, "人力研发", 20, 400, MUTED, "middle")
    for i, (name, v, c) in enumerate(data):
        y = 70 + i * 66
        s.rect(620, y, 30, 30, c, LINE if c == "#DCE7F8" else None, 1.2, 6)
        s.text(670, y + 24, name, 24, 700 if i == 0 else 400, INK)
        s.text(1120, y + 24, f"{v}%", 26, 700, NAVY, "end")
        s.line([(620, y + 48), (1120, y + 48)], LINE, 1)
    s.save("fig-4-1-costs.svg")


FIGURES = [fig_1_1, fig_1_2, fig_1_3, fig_2_1, fig_2_2, fig_3_1, fig_3_2, fig_3_3, fig_3_4, fig_3_5,
           fig_3_6, fig_3_7, fig_3_8, fig_3_9, fig_3_10, fig_3_11, fig_3_12, fig_3_13, fig_3_14,
           fig_3_15, fig_3_16, fig_3_17, fig_3_18, fig_4_1]

if __name__ == "__main__":
    for old in OUT.glob("*.svg"):
        old.unlink()
    for fn in FIGURES:
        fn()
    print(len(list(OUT.glob("*.svg"))), "figures written")
