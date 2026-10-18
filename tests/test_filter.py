"""评分逻辑单元测试

运行: .venv/bin/python -m pytest tests/ -v
（或无 pytest: .venv/bin/python tests/test_filter.py）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jobhunting.filter import apply_filters, score_jobs
from jobhunting.models import Job

KW_ARGS = dict(
    core_keywords=["ai agent", "llm", "blockchain", "solidity", "defi"],
    secondary_keywords=["python", "docker"],
    core_weight=10.0,
    secondary_weight=5.0,
    salary_bonus=10.0,
    max_score=100.0,
    title_weight=20.0,
    desc_core_cap=3,
    secondary_cap=4,
    talent_penalty=-30.0,
    talent_companies=["lemon.io", "toptal"],
    location_bonus=10.0,
    location_penalty=-50.0,
    location_eligible=["worldwide", "global", "anywhere", "apac", "asia", "singapore", "china"],
    location_restricted=["usa", "u.s.", "united states", "northern america", "europe", "emea"],
)


def mk(title, company="Acme", desc="", salary="", location=""):
    return Job(
        id="t1", source="remotive", title=title, company=company, url="https://x",
        description=desc, salary=salary, location=location,
    )


def test_title_hit_dominates():
    """标题命中核心词应得高分（两个词 60 分）"""
    one = score_jobs([mk("Senior Blockchain Engineer")], **KW_ARGS)[0]
    two = score_jobs([mk("Blockchain Solidity Engineer")], **KW_ARGS)[0]
    assert one.score >= 30            # 20(标题) + 10(描述同词)
    assert two.score >= 60            # 40(标题×2) + 20(描述同词×2)


def test_desc_stuffing_capped():
    """长描述堆一堆核心词，封顶后不该拿高分"""
    desc = " ".join(["ai agent llm blockchain solidity defi"] * 10)
    jobs = score_jobs([mk("Rails Developer", desc=desc)], **KW_ARGS)
    # 封顶 3×10 + 次要封顶… 分数 < 60
    assert jobs[0].score < 60


def test_talent_penalty():
    """人才库公司应被降权"""
    a = score_jobs([mk("LLM Engineer", company="Lemon.io")], **KW_ARGS)[0]
    b = score_jobs([mk("LLM Engineer", company="RealCorp")], **KW_ARGS)[0]
    assert b.score > 0
    assert a.score == max(0.0, b.score - 30.0)
    assert a.score_breakdown["talent_penalty"] == -30.0


def test_empty_title_zero():
    """无标题不参与推荐"""
    jobs = score_jobs([mk("", desc="llm blockchain")], **KW_ARGS)
    assert jobs[0].score == 0.0


def test_salary_bonus():
    a = score_jobs([mk("Blockchain Dev", salary="$100k")], **KW_ARGS)[0]
    b = score_jobs([mk("Blockchain Dev")], **KW_ARGS)[0]
    assert a.score == b.score + 10.0


def test_secondary_capped():
    desc = "python docker aws gcp postgresql redis"
    jobs = score_jobs([mk("Backend Dev", desc=desc)], **KW_ARGS)
    # 次要词命中 2 个都在列表内 → python, docker 各 5 分
    assert jobs[0].score_breakdown["secondary_hits"] >= 2


def test_exclude_keywords():
    jobs = [
        mk("Blockchain Intern"),
        mk("Blockchain Engineer"),
    ]
    out = apply_filters(jobs, ["intern"])
    assert len(out) == 1
    assert out[0].title == "Blockchain Engineer"


def test_id_prefix_not_duplicated():
    """从数据库读回的 id 不应被重复加前缀"""
    j = Job(id="remotive:123", source="remotive", title="t", company="c",
            url="u", description="")
    assert j.id == "remotive:123"


def test_location_restricted_usa():
    """限定美国时区的职位应被重罚（上海无法入职）"""
    a = score_jobs([mk("Blockchain Engineer", location="USA, Canada, USA timezones")], **KW_ARGS)[0]
    b = score_jobs([mk("Blockchain Engineer")], **KW_ARGS)[0]
    assert a.score_breakdown["location"] == "restricted"
    assert a.score == max(0.0, b.score - 50.0)


def test_location_eligible_apac():
    """含 APAC 的职位应加分"""
    a = score_jobs([mk("Blockchain Engineer", location="Europe, USA, Canada, APAC")], **KW_ARGS)[0]
    b = score_jobs([mk("Blockchain Engineer")], **KW_ARGS)[0]
    assert a.score_breakdown["location"] == "eligible"
    assert a.score == b.score + 10.0


def test_location_eligible_wins_over_restricted():
    """同一地点既有 US 又有 APAC 时，APAC 优先（可入职）"""
    j = score_jobs([mk("Dev", location="Northern America, LATAM, Europe, APAC")], **KW_ARGS)[0]
    assert j.score_breakdown["location"] == "eligible"


def test_location_remote_neutral():
    """仅 Remote 无更多信息时中性，不奖不罚"""
    j = score_jobs([mk("Blockchain Engineer", location="Remote")], **KW_ARGS)[0]
    assert j.score_breakdown["location"] == "neutral"
    assert j.score_breakdown["location_adj"] == 0.0


def test_location_onsite_city_penalized():
    """指定城市坐班（如 Redwood City / Kansas）视同不可入职"""
    a = score_jobs([mk("Blockchain Engineer", location="Redwood City")], **KW_ARGS)[0]
    assert a.score_breakdown["location"] == "onsite"
    assert a.score_breakdown["location_adj"] == -50.0


def test_location_remoto_spanish_neutral():
    """西班牙语 Remoto（=远程）应中性"""
    j = score_jobs([mk("Blockchain Engineer", location="Remoto")], **KW_ARGS)[0]
    assert j.score_breakdown["location"] == "neutral"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"✅ {fn.__name__}")
    print(f"\n{len(fns)} 个测试全部通过")
