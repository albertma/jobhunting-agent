"""Web3.career — Web3 专项职位

网站: https://web3.career
HTML 结构分析（2026-10-17）：
  <tr class="job-row-grid table_row">
    <td data-jobid=155529 class=cell-main scope=row>
      <a href="/<slug>/<id>">
        <h2 class="...job-title-truncate"> 岗位名 </h2>
        <h3> 公司名 </h3>
      </a>
    <td class="cell-salary"><p class="text-salary"> $84k - $120k
"""
from __future__ import annotations

import re

import httpx

from .base import JobSource
from ..log import setup_logging

logger = setup_logging()


class Web3CareerSource(JobSource):
    """Web3.career 爬虫"""

    name = "web3career"
    source_type = "scraper"
    BASE_URL = "https://web3.career"

    def fetch(self) -> list[dict[str, str]]:
        keywords = self.config.get("keywords", [])
        all_jobs: dict[str, dict] = {}

        for kw in keywords:
            slug = kw.lower().replace(" ", "-")
            for page in range(1, 4):
                url = f"{self.BASE_URL}/{slug}-jobs?page={page}"
                try:
                    resp = httpx.get(
                        url,
                        timeout=20.0,
                        follow_redirects=True,
                        headers={
                            "User-Agent": (
                                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/119.0 Safari/537.36"
                            ),
                            "Accept-Language": "en-US,en;q=0.9",
                            "Accept": "text/html,application/xhtml+xml",
                        },
                    )
                    resp.raise_for_status()
                    jobs = self._parse(text=resp.text)
                    if not jobs:
                        break
                    for job in jobs:
                        jid = job.get("id", "")
                        if jid and jid not in all_jobs:
                            all_jobs[jid] = job
                except Exception as e:
                    logger.warning(f"[Web3Career] 「{kw}」第{page}页失败: {e}")
                    continue

        return list(all_jobs.values())

    def _parse(self, text: str) -> list[dict[str, str]]:
        """解析列表页 HTML"""
        jobs = []
        row_pat = re.compile(
            r'class="job-row-grid table_row"[^>]*>(.*?)</tr>',
            re.DOTALL,
        )
        for row_m in row_pat.finditer(text):
            row = row_m.group(1)

            jid_m = re.search(r'data-jobid=(\d+)', row)
            if not jid_m:
                continue
            job_id = jid_m.group(1)

            href_m = re.search(r'href="(/[^"]+/\d+)"', row)
            url = (
                f"{self.BASE_URL}{href_m.group(1)}"
                if href_m
                else f"{self.BASE_URL}/job/{job_id}"
            )

            title_m = re.search(
                r'<h2[^>]*class="[^"]*job-title-truncate[^"]*"[^>]*>(.*?)</h2>',
                row, re.DOTALL,
            )
            title = title_m.group(1).strip() if title_m else ""

            co_m = re.search(
                r'class="[^"]*job-company-location[^"]*"[^>]*>.*?'
                r'<h3[^>]*>\s*([^<]+)\s*</h3>',
                row, re.DOTALL,
            )
            company = co_m.group(1).strip() if co_m else ""

            sal_m = re.search(r'\$([\d]+k?\s*[-–]\s*\$?[\d]+k?)', row)
            salary = f"${sal_m.group(1).strip()}" if sal_m else ""

            if title:
                jobs.append({
                    "id": f"w3c-{job_id}",
                    "title": title,
                    "company": company,
                    "url": url,
                    "description": "",
                    "tags": [],
                    "location": "Remote",
                    "salary": salary,
                    "job_type": "full_time",
                    "posted_at": "",
                })
        return jobs
