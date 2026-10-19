#!/usr/bin/env python3
"""自动化求职投递脚本 — 一键投递高分职位"""
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from jobhunting.db import recent_jobs, mark_applied
from jobhunting.draft import load_profile
from jobhunting.llm import cover_letter, is_llm_enabled
from jobhunting.resume import resume_summary
from jobhunting.notify import notify_text
from jobhunting.config import load as load_config

def main():
    config = load_config()
    nc = config.notify
    
    print("\n🚀 自动化求职投递启动")
    print("="*60)
    
    # 加载画像 + 简历
    profile = load_profile()
    resume_txt = ""
    try:
        resume_txt = resume_summary("en")
    except FileNotFoundError:
        print("⚠️  未找到简历 PDF")
    
    llm_ok = is_llm_enabled()
    if not llm_ok:
        print("❌ LLM 未启用，无法生成 Cover Letter")
        return
    
    # 获取最高分职位（前 5 个）
    jobs = recent_jobs(limit=50)
    top_jobs = [j for j in jobs if j.score >= 40][:5]
    
    if not top_jobs:
        print("❌ 没有 ≥40 分的职位")
        return
    
    print(f"\n📋 找到 {len(top_jobs)} 个值得投递的职位：")
    for i, job in enumerate(top_jobs, 1):
        status = "✅ 已投" if getattr(job, "applied", False) else "⭕ 待投"
        print(f"   [{i}] [{job.score:.0f}分] {job.title} @ {job.company} {status}")
    
    print("\n" + "="*60)
    print("📤 开始投递...\n")
    
    applied_count = 0
    for job in top_jobs:
        # 跳过已投的
        if getattr(job, "applied", False):
            print(f"⏭️  跳过（已投）: {job.title}")
            continue
        
        print(f"\n🎯 投递: {job.title} @ {job.company}")
        print(f"   链接: {job.url}")
        print(f"   薪资: {job.salary or '未提及'}")
        
        try:
            # Step 1: 打开申请页
            print(f"   🌐 打开申请页...", end="", flush=True)
            webbrowser.open(job.url)
            print(" ✅")
            
            # Step 2: 生成 Cover Letter
            print(f"   ✍️  生成定制 Cover Letter...", end="", flush=True)
            name = profile.get("name", "Candidate")
            headline = profile.get("headline", "")
            years = profile.get("years_experience", 0)
            tz = profile.get("timezone_flexibility", "")
            skills = "\n".join(f"- {s}" for s in profile.get("skills", []))
            highlights = profile.get("highlights") or []
            hl = ""
            if highlights:
                h = highlights[0]
                hl = f"\nMost relevant project: {h.get('title')}\n  {h.get('what', '')}\n  Impact: {h.get('impact', '')}"
            
            prompt = (
                f"Write a cover letter for the following position. Be specific, no generic phrases.\n\n"
                f"Position: {job.title}\nCompany: {job.company}\n"
                f"Location: {job.location or 'Remote'}\nSalary: {job.salary or 'Not specified'}\n\n"
                f"Description (key parts):\n{job.description[:2000] if job.description else 'See posting'}\n\n"
                f"Candidate:\nName: {name}\nHeadline: {headline}\n"
                f"Experience: {years} years\nTimezone: {tz}\nSkills:\n{skills}{hl}\n\n"
                "Requirements:\n"
                "- 250-350 words\n"
                "- No template phrases, no buzzword lists\n"
                "- Lead with the strongest match\n"
                "- Address timezone proactively\n"
                "- End with a specific call to action"
            )
            letter = cover_letter(prompt)
            print(" ✅")
            
            # Step 3: 保存到 drafts/
            drafts_dir = Path(__file__).parent / "drafts"
            drafts_dir.mkdir(exist_ok=True)
            safe_id = job.id.replace(":", "_")
            letter_path = drafts_dir / f"{safe_id}_cover_letter.txt"
            letter_path.write_text(letter)
            
            # Step 4: 标记已投递
            print(f"   📌 标记投递...", end="", flush=True)
            mark_applied(job.id)
            print(" ✅")
            
            applied_count += 1
            
            # Step 5: 推送飞书
            if nc.enabled and nc.feishu_app_id:
                notify_text(
                    title=f"✅ 已投递: {job.title}",
                    body=f"公司: {job.company}\n薪资: {job.salary or '未提及'}\n链接: {job.url}\n\n📄 Cover Letter 已生成 → {letter_path.name}",
                    feishu_app_id=nc.feishu_app_id,
                    feishu_app_secret=nc.feishu_app_secret,
                    feishu_chat_id=nc.feishu_chat_id,
                )
            
        except Exception as e:
            print(f" ❌ 失败: {e}")
    
    # 总结
    print("\n" + "="*60)
    print(f"✅ 本次投递 {applied_count} 个职位")
    if applied_count > 0:
        print(f"📁 Cover Letter 已保存到: drafts/")
        print(f"💬 飞书推送已发送")
        print(f"\n📱 收到回复后运行:")
        print(f"   python main.py replied <job_id>")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
