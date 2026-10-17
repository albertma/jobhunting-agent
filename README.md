# JobHunting — Remote 职位搜索机器人

面向 AI Agent / 区块链方向，自动抓取 + 评分 + 飞书推送。

## 功能

- **多源抓取**：Remotive API + CryptoJobsList + Web3.career
- **关键词过滤**：排除 intern/part-time
- **匹配度评分**：核心词（AI Agent / LLM / DeFi / Solidity）权重 ×15，次要词 ×5，标题加成
- **去重**：7 天内重复职位自动跳过
- **飞书推送**：每日汇总到飞书群

## 安装

```bash
cd jobhunting
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入飞书配置（从 FI-Agent/.env 复制）
```

## 飞书配置

从 `FI-Agent/.env` 复制以下三个变量到 `jobhunting/.env`：

```bash
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_CHAT_ID=oc_xxxxxxxxxxxx
```

## 使用

```bash
# 抓取 + 评分（不入库重复）
.venv/bin/python main.py run

# 抓取 + 推送飞书
.venv/bin/python main.py run --push

# 查看最近职位
.venv/bin/python main.py list -n 20

# 标记已投递
.venv/bin/python main.py applied remotive:12345

# 查看配置
.venv/bin/python main.py config
```

## 定时任务（每日 09:00 自动推送）

```bash
# macOS crontab
0 9 * * 1-5 cd /Users/albertma/sourcecode/workspace/python/jobhunting && /Users/albertma/sourcecode/workspace/python/jobhunting/.venv/bin/python main.py run --push >> /Users/albertma/sourcecode/workspace/python/jobhunting/logs/cron.log 2>&1
```

## 数据

- 数据库：`data/jobs.db`（SQLite，自动创建）
- 日志：`logs/`（首次运行后自动创建）

## 配置

编辑 `config.yaml`：
- `sources.*.keywords` — 各来源搜索关键词
- `scoring.core_keywords` — 核心匹配词（命中 +15 分）
- `scoring.min_score` — 入围门槛（默认 40 分）
- `notify.daily_max` — 飞书每天最多推送条数

## 文件结构

```
jobhunting/
├── main.py                  # CLI 入口
├── config.yaml              # 配置文件
├── .env.example             # 飞书配置模板
├── requirements.txt
├── data/jobs.db             # SQLite（自动创建）
├── logs/                    # 日志（自动创建）
├── src/jobhunting/
│   ├── models.py            # Job 数据模型
│   ├── config.py            # 配置加载
│   ├── db.py                # SQLite 持久化
│   ├── filter.py            # 过滤 + 评分
│   ├── pipeline.py          # 主 Pipeline
│   ├── notify.py            # 飞书推送
│   └── sources/
│       ├── base.py           # 基类
│       ├── remotive.py       # Remotive API
│       ├── cryptjobslist.py  # CryptoJobsList
│       └── web3career.py     # Web3.career
```
