# 求职 Agent 完整计划

**状态**: 🚀 MVP 交付 + 5 职位已投  
**最后更新**: 2026-10-19  
**目标**: 自动化求职 + 每月至少 1 个面试邀请

---

## 📊 当前状态

### ✅ 已完成
- [x] 4 源职位抓取 (Remotive / RemoteOK / Web3.career / CryptoJobsList)
- [x] 智能评分系统 (标题权重 + 位置感知 + 才能市场惩罚)
- [x] LLM 对接 (MiniMax / DeepSeek / OpenAI 兼容)
- [x] 交互式 Agent REPL (`main.py agent`)
- [x] PDF 简历读取 (`/resume` 命令)
- [x] LLM 定制 Cover Letter 生成 (`/draft` / `/apply`)
- [x] 一键自动投递脚本 (`auto_apply.py`)
- [x] 飞书推送集成
- [x] 应用追踪数据库 (SQLite, 已投 / 回复 / 跟进)
- [x] 跟进提醒 (7 天无回复自动提醒)
- [x] 双语简历 (中文 + 英文 PDF)
- [x] GitHub 开源 + 8 个主题标签
- [x] 交互式架构图 (archify)
- [x] 完整 README + 贡献指南

### 🔄 进行中
- [ ] MiniMax 余额补充（当前不足）
- [ ] Pi 扩展完全整合（Feishu 命令已就绪）
- [ ] 数据分析仪表板（投递 → 回复 → 面试转化率）

---

## 📋 即时行动项 (Week 1)

### 🎯 核心投递周期 (3-5 天)
```
Day 1 (已完成):
  ✅ 抓取职位 (21 条新增)
  ✅ 投递 5 个 ≥40 分职位 (Bitpanda / Zscaler / Sentient / Offchain / Coins.ph)
  ✅ 生成 5 个定制 Cover Letter
  ✅ 推送飞书通知

Day 2-3:
  [ ] 监测邮件回复 (应聘系统 / 招聘官直邮)
  [ ] 标记回复状态 (main.py replied <job_id>)

Day 4-5:
  [ ] 抓取新一轮职位 (auto_apply.py)
  [ ] 投递下一批 ≥40 分职位
```

### 🛠️ 配置优化
```
优先级 1 (立即):
  [ ] 充值 MiniMax（$5-10，目前余额为 0）
  [ ] 验证所有 .env 变量（FEISHU_* + LLM_*）
  [ ] 测试飞书推送 (main.py config feishu)

优先级 2 (Day 3):
  [ ] 调整评分规则 (config.yaml)
    - 考虑降低 min_score: 40 → 35 (更多机会)
    - 或提高 title_weight: 20 → 25 (更看重职位名)
  [ ] 更新 web3.career Profile Bio (版本 A)
  [ ] 验证简历链接在 Cover Letter 里是否可用

优先级 3 (Week 2):
  [ ] 测试 Pi 扩展完全集成
  [ ] 建立日志查询工具 (谁回复了？回复率多少？)
```

---

## 📈 中期目标 (Weeks 2-4)

### 数据追踪
```
投递 → 回复 → 面试 转化率分析

需要的指标:
  - 投递总数: currently 5
  - 回复数: 0 (waiting)
  - 回复率: TBD
  - 面试邀请数: 0
  - 面试率: TBD
  - Offer 数: 0

工具:
  [ ] 创建 stats.py 生成周报
  [ ] 在飞书里发送周报 (每周一)
  [ ] 追踪招聘官回复时间
```

### 自动化深化
```
现状:
  - auto_apply.py 手动运行

计划:
  [ ] 集成到 cron (每周一 09:00 + 周三 18:00)
  [ ] 智能筛选: 只投递 "AI Agent" / "Backend" / "Distributed Sys" 职位
  [ ] 智能延迟: 同一公司的职位间隔 3 天 (避免刷屏)
  [ ] 邮件通知: 新回复时发邮件而不是只有飞书
```

### 材料持续优化
```
Version 1 (当前):
  - Cover Letter 基于 LLM (MiniMax)
  - 简历摘要来自 PDF 提取
  - Bio 基于 Profile YAML

Version 2 (Week 2):
  [ ] A/B 测试两个 Cover Letter 版本
    - A: 技术驱动 (强调 FI-Agent)
    - B: 管理驱动 (强调 VeChain Tech Director 角色)
  [ ] 根据公司类型选择不同版本
  [ ] 追踪哪个版本回复率更高
```

---

## 🎯 长期优化 (Weeks 5-8)

### 匹配算法迭代
```
现状评分规则:
  - title_weight: 20 (无上限，可能过高)
  - desc_core_cap: 3 (防止堆词)
  - talent_penalty: -30 (Lemon.io / Toptal 等)
  - location_aware: +10 APAC / -50 US-locked

改进:
  [ ] 收集 20+ 投递反馈 (哪些公司回复了？)
  [ ] 分析: 高回复率职位有什么共同特征?
  [ ] 重新权衡各个评分维度
  [ ] AB 测试: 原始算法 vs 优化算法
```

### 职位源扩展
```
当前 4 源:
  - Remotive API
  - RemoteOK API
  - Web3.career 爬虫
  - CryptoJobsList 爬虫

新增候选 (Week 6):
  [ ] Greenhouse / Lever 职位页面爬虫
  [ ] Hacker News "Who's Hiring" 线程
  [ ] LinkedIn 职位搜索 (如果 TOS 允许)
  [ ] 直接公司 Careers 页面 (Uniswap / OpenAI / Anthropic)
```

### 智能应用策略
```
现状: 只要 ≥40 分就投

改进:
  [ ] 分层投递:
    - Tier 1 (≥80): 立即投 + 写个性化邮件给招聘官
    - Tier 2 (60-79): 投 + 标准 Cover Letter
    - Tier 3 (40-59): 集中投递 (周一集中投 5 个)
  [ ] 跟进成功率追踪
  [ ] 根据公司响应时间优化投递频率
```

---

## 🚨 风险 & 缓解

| 风险 | 概率 | 缓解措施 |
|---|---|---|
| MiniMax API 余额不足 | 🔴 当前 | 充值或切换 OpenAI |
| LLM 生成差质量 Cover Letter | 🟡 中 | 人工审核前 5 个 + A/B 测试 |
| 职位源枯竭 (重复抓取) | 🟡 中 | 扩展新职位源 + 增加抓取频率 |
| 招聘官垃圾邮件黑名单 | 🟢 低 | 限制投递频率 (Day 1: 5 个 → Day 2: 0 个) |
| 简历过时 (20 年经验但只列最近 3 年) | 🟡 中 | 更新简历展示全面背景 |
| 时区冲突 (上海 UTC+8 vs US 公司) | 🟡 中 | 在 Cover Letter 里主动提 "overlap 3-4h" |

---

## 💡 创意方向 (如果时间充足)

### 高优先级
- [ ] **智能面试准备**: 根据 JD 生成常见面试题 + 答题建议 (LLM)
- [ ] **邮件自动跟进**: 7 天无回复自动发一封友好的跟进邮件
- [ ] **招聘官直邮**: 从 LinkedIn 或公司网站提取招聘负责人，直接发 LinkedIn 消息

### 中优先级
- [ ] **多语言支持**: 中英简历切换 + 简体 / 繁体分支
- [ ] **薪资谈判建议**: 根据职位 / 公司 / 地区推荐谈判范围
- [ ] **公司研究工具**: 自动查询公司融资阶段 / 员工数 / 估值 (Crunchbase API)

### 低优先级
- [ ] **团队招聘**: 帮朋友代管账号投递 (多用户支持)
- [ ] **GitHub Trending Jobs**: 自动追踪热门开源项目的招聘信息
- [ ] **Slack 集成**: 在 Slack 里收到投递状态通知

---

## 📅 实施时间表

### Week 1 (Oct 19-25)
```
Mon (Oct 21):
  ✅ 投递 5 个职位 (已完成)
  [ ] 充值 MiniMax ($10)
  [ ] 测试飞书推送

Tue-Thu:
  [ ] 监测邮件 (每日 2x)
  [ ] 调整配置 (如需要)

Fri:
  [ ] 生成周报 (投递数 / 回复数)
  [ ] 新一轮投递 (auto_apply.py)
```

### Week 2 (Oct 26-Nov 1)
```
Mon:
  [ ] 继续投递 (每周一次 auto_apply.py)
  [ ] 面试准备 (如有邀请)

Wed:
  [ ] 优化 Cover Letter 版本 (A/B 测试)
  [ ] 更新 web3.career Profile Bio

Fri:
  [ ] 数据分析 (2 周投递数据)
  [ ] 调整评分规则 (如需要)
```

### Week 3-4 (Nov 2-15)
```
- 继续日常投递 (auto_apply.py)
- 参加面试 (如有)
- 收集反馈 + 优化算法
- 考虑新职位源
```

---

## ✅ 检查清单

### 日常任务 (每天)
```
[ ] 检查邮件 (招聘回复)
[ ] 标记回复状态 (main.py replied)
[ ] 飞书看投递提醒
```

### 周任务 (每周一)
```
[ ] 运行 auto_apply.py (自动投递新职位)
[ ] 查看周报 (回复率 / 面试数)
[ ] 如有面试，准备材料
```

### 月任务 (月末)
```
[ ] 回顾一月数据
[ ] 评估是否需要调整策略
[ ] 更新简历 (如有新项目)
[ ] 重新评估目标薪资
```

---

## 📞 联系 & 支持

### 常见问题

**Q: 怎么知道有人回复我？**
```bash
# 每天检查邮件，或
.venv/bin/python main.py followups  # 查看待跟进列表
```

**Q: 我想降低投递频率（怕被黑名单）**
```python
# 修改 auto_apply.py，改为
top_jobs = [j for j in jobs if j.score >= 40][:3]  # 从 5 改成 3
```

**Q: 我想看所有投递过的公司**
```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'src')
from jobhunting.db import recent_jobs
jobs = [j for j in recent_jobs(1000) if getattr(j,'applied',False)]
for j in jobs:
    print(f'{j.company:20} | {j.title:40} | {j.score:.0f}分')
"
```

**Q: Cover Letter 质量不满意**
```python
# auto_apply.py 里，在生成前可以手动审核：
# letter = cover_letter(prompt)
# print("生成的 Cover Letter:"); print(letter)
# if input("接受？(y/n)") != "y": continue
```

---

## 🎯 成功标志

投届 Agent 达成目标的标志：

- ✅ 投递 10+ 职位 → 收到 2+ 回复
- ✅ 回复率 ≥ 20%
- ✅ 至少 1 个面试邀请
- ✅ 签署 Offer

---

**下一步**: 按照 Week 1 计划执行，周五汇总进度。
