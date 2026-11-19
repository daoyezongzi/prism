# S3 答辩稿架构图（重绘版）

## 一、文件与对应页

| 原稿页 | 图名 | SVG（可编辑） | PNG（2x，透明底） |
| --- | --- | --- | --- |
| S8 | 功能架构：统一投资者档案驱动六模块 | `svg/fig-s08-function-architecture.svg` | `png/fig-s08-function-architecture.png` |
| S14 | 系统整体分层架构 | `svg/fig-s14-system-layers.svg` | `png/fig-s14-system-layers.png` |
| S15 | SkillHub 底座与自研控制链 | `svg/fig-s15-skillhub-control-chain.svg` | `png/fig-s15-skillhub-control-chain.png` |
| S16 | 画像风险预算与组合穿透 | `svg/fig-s16-risk-budget-penetration.svg` | `png/fig-s16-risk-budget-penetration.png` |
| S17 | 来源等价类证据防火墙 | `svg/fig-s17-evidence-firewall.svg` | `png/fig-s17-evidence-firewall.png` |
| S18 | 有界 DAG 调度与离散序贯再平衡 | `svg/fig-s18-dag-rebalance.svg` | `png/fig-s18-dag-rebalance.png` |
| S19 | 独立双闸门与会话防漂移 | `svg/fig-s19-gates-session-drift.svg` | `png/fig-s19-gates-session-drift.png` |

## 二、嵌入 PowerPoint

1. 推荐插入 PNG：字体已栅格化，换机放映不走样；透明底可直接置于原稿米色面板上。
2. 需要改字时插入 SVG，右键「转换为形状」即可逐项编辑；样式均为内联属性，转换不丢失。SVG 依赖本机「微软雅黑」。
3. 每张图对应替换原页标题下方的整块内容区；S8 图同时替代左侧思维导图与右侧六张卡片。

## 三、数据口径

图中阈值、状态码与数值均与代码或测试报告一致：集中度上限见 `app/risk/contracts.py`；双闸门取最严结果见 `app/gates/pipeline.py`；会话状态见 `app/service/session_truth.py`；9 项 Skill 见 `app/providers/skillhub.py`；调仓费用 743.15 元与复算差额 0.00 元见 `docs/submission/system-test-report.md`。

## 四、重新生成

```bash
python docs/submission/s3-figures/build_figures.py
node docs/submission/s3-figures/render_png.mjs
```
