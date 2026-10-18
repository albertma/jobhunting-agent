"""CryptoJobsList.com — Web3 专项职位

网站: https://cryptojobslist.com
使用 cloudscraper 绕过 Cloudflare 防护，从首页 + 分类页抓取职位列表。

URL 结构:
  /jobs/<title>-at-<company>        — 职位详情
  /jobs?search=<keyword>&page=<n>   — 搜索页
  /remote-blockchain-jobs            — 分类页
"""
from __future__ import annotations

import re

import cloudscraper

from .base import JobSource
from ..log import setup_logging

logger = setup_logging()


class CryptoJobsListSource(JobSource):
    """CryptoJobsList.com 爬虫（cloudscraper 模式）"""

    name = "cryptjobslist"
    source_type = "scraper"
    BASE_URL = "https://cryptojobslist.com"

    def fetch(self) -> list[dict[str, str]]:
        all_jobs: dict[str, dict] = {}

        # 分类页：remote blockchain / defi / solidity jobs
        categories = [
            "blockchain",
            "defi",
            "solidity",
            "web3",
            "smart-contract",
        ]
        for cat in categories:
            url = f"{self.BASE_URL}/?search={cat}"
            try:
                jobs = self._fetch_page(url)
                for job in jobs:
                    jid = job.get("id", "")
                    if jid and jid not in all_jobs:
                        all_jobs[jid] = job
            except Exception as e:
                logger.warning(f"[CryptoJobsList] 分类「{cat}」失败: {e}")
                continue

        # 也从首页抓取 featured jobs
        try:
            jobs = self._fetch_page(self.BASE_URL)
            for job in jobs:
                jid = job.get("id", "")
                if jid and jid not in all_jobs:
                    all_jobs[jid] = job
        except Exception as e:
            logger.warning(f"[CryptoJobsList] 首页失败: {e}")

        return list(all_jobs.values())

    def _fetch_page(self, url: str) -> list[dict[str, str]]:
        """抓取单页并解析"""
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        return self._parse(text=resp.text)

    def _parse(self, text: str) -> list[dict[str, str]]:
        """从页面 HTML 提取职位列表"""
        jobs = []

        # 从 JSON-LD @graph 中提取 ItemList
        graph_m = text.find('"@graph"')
        if graph_m >= 0:
            # 找 @type=ItemList
            itemlist_m = re.search(
                r'"@type":"ItemList","name":"[^"]*","description":"[^"]*"(.*?)(?:"@type"|\}\]\}$)',
                text[graph_m:],
                re.DOTALL,
            )
            if itemlist_m:
                # 直接在原始文本中找 itemListElement
                ile_m = re.findall(
                    r'"itemListElement":\[\{"@type":"ListItem","position":\d+,"url":"([^"]+)","name":"([^"]+)"\}',
                    text,
                )
                for url, title in ile_m:
                    job = self._url_to_job(url, title)
                    if job:
                        jobs.append(job)
                if jobs:
                    return jobs

        # Fallback: 从 HTML 中找 /jobs/ 链接
        links = re.findall(r'href="(/jobs/[^"]+)"', text)
        seen = set()
        for lnk in links:
            if lnk in seen:
                continue
            seen.add(lnk)
            job = self._url_to_job(lnk, "")
            if job:
                jobs.append(job)
        return jobs

    def _url_to_job(self, url: str, title: str) -> dict[str, str]:
        """从 URL slug + title 解析职位"""
        slug = url.replace("/jobs/", "").replace(f"{self.BASE_URL}/jobs/", "")

        # 从 slug 提取公司名（末尾 -at-<company>）
        parts = slug.rsplit("-at-", 1)
        if len(parts) == 2:
            slug_title = parts[0]
            company = parts[1].replace("-", " ").strip()
        else:
            slug_title = slug
            company = ""

        # 从 slug 提取地点
        location = "Remote"
        if "remote" in slug.lower():
            location = "Remote"
        elif slug_title.count("-") > 2:
            # 尝试提取地点
            loc_match = re.search(r"-(us|uk|eu|asia|sg|au|ca|in|remote)-?$", slug_title.lower())
            if not loc_match:
                loc_match = re.search(r"(singapore|berlin|london|new-york|hong-kong)-at-", slug.lower())
            if loc_match:
                location = loc_match.group(1).replace("-", " ").title()

        job_title = (
            title.replace("-", " ").strip()
            if title
            else slug_title.replace("-", " ").strip().title()
        )

        return {
            "id": f"cjl-{slug.replace('/', '-')}",
            "title": job_title,
            "company": company.title() if company else "",
            "url": f"{self.BASE_URL}{url}" if url.startswith("/") else url,
            "description": "",
            "tags": [],
            "location": location,
            "salary": "",
            "job_type": "full_time",
            "posted_at": "",
        }
