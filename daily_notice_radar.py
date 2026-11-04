#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSNU 通知雷达 · 江苏师范大学每日通知监控

抓取：教务处 / 学校信息门户 / 人工智能与计算机学院
筛选：竞赛、考试、报名类通知（关键词可自定义）
去重：已发过的记在 sent_state.json，下次只发新的
投递：QQ 邮箱 SMTP，HTML 邮件
运行：建议每天 09:00 由系统计划任务触发

用法：
    cp config.example.json config.json   # 填自己的邮箱与授权码
    python daily_notice_radar.py

首次运行只建立基线，不推送（避免一上线就是几十条历史通知）。
"""
import json
import os
import re
import ssl
import sys
import hashlib
import smtplib
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.parse import urlparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")
STATE_FILE = os.path.join(BASE, "sent_state.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# 抓取源。key 会出现在邮件小标题里，可以自己加
SOURCES = {
    "jwc": "http://jwc.jsnu.edu.cn/tzgg/",
    "portal": "http://www.jsnu.edu.cn/xxmhwtzgg/list1.htm",
    "ai": "http://ai.jsnu.edu.cn/main.htm",
}
SOURCE_NAMES = {
    "jwc": "🏫 教务处",
    "portal": "📋 学校信息门户",
    "ai": "💻 人工智能与计算机学院",
}

# 命中任意一个即保留
INCLUDE_KW = [
    "竞赛", "比赛", "大赛", "挑战", "考试", "报名", "选拔", "奖学金",
    "四六级", "四级", "六级", "教资", "教师资格", "考研", "考证", "学位",
    "数学建模", "蓝桥", "程序设计", "电子设计", "机器人", "创新创业",
    "大创", "互联网+", "挑战杯", "ACM", "CCF", "天梯赛", "OJ",
    "期末", "补考", "缓考", "重修", "选课", "推免", "保研", "转专业",
    "等级考试", "水平考试", "口语", "听力", "计算机等级", "软考",
]

# 命中任意一个即丢弃
EXCLUDE_KW = [
    "教职工", "教师", "教学创新", "督导", "党委", "党支部", "工会",
    "招标", "采购", "中标", "修缮", "物业", "保洁", "饮食", "宿舍家具",
    "庆祝", "运动会", "迎新", "毕业", "开学", "放假", "值班", "培训",
    "人事", "招聘教师", "职称", "岗位聘任", "述职", "考核等次",
    "国庆", "中秋", "元旦", "春节", "清明", "劳动", "志愿活动",
]


def load_config():
    if not os.path.exists(CONFIG_PATH):
        sys.exit("缺少 config.json，请先复制 config.example.json 并填写。")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def fetch(url, timeout=15):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        raw = r.read()
    for enc in ("utf-8", "gbk", "gb2312"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def extract_list_items(html, base_url):
    p = urlparse(base_url)
    origin = f"{p.scheme}://{p.netloc}"

    def absolutize(href):
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return origin + href
        return base_url.rstrip("/") + "/" + href

    items = []

    # 模式一：<li> 里包一条 <a title="标题" href="..."> + 日期
    for li in re.finditer(r"<li[^>]*>(.*?)</li>", html, re.S):
        block = li.group(1)
        m = re.search(r"""href=['"]([^'"]+)['"][^>]*title=['"]([^'"]+)['"]""", block)
        d = re.search(r"(\d{4}-\d{2}-\d{2})", block)
        if m and d:
            items.append({"title": m.group(2).strip(), "date": d.group(1), "url": absolutize(m.group(1))})

    # 模式二：学校门户的 <a class="column-news-item">
    for block in re.finditer(r'<a[^>]*class="column-news-item[^"]*"[^>]*>(.*?)</a>', html, re.S):
        inner = block.group(1)
        href_m = re.search(r"""href=['"]([^'"]+)['"]""", block.group(0))
        title_m = re.search(r"""title=['"]([^'"]+)['"]""", inner)
        d = re.search(r"(\d{4}-\d{2}-\d{2})", inner)
        if href_m and title_m and d:
            items.append({"title": title_m.group(1).strip(), "date": d.group(1), "url": absolutize(href_m.group(1))})

    seen, uniq = set(), []
    for it in items:
        key = it["title"] + it["date"]
        if key not in seen:
            seen.add(key)
            uniq.append(it)
    return uniq


def fetch_summary(url, max_len=150):
    """抓正文摘要。正文容器名各站不同，按常见 class 依次试。"""
    try:
        html = fetch(url, timeout=10)
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S | re.I)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.S | re.I)

        body_html = None
        for cls in [
            "wp_articlecontent", "v_news_content", "read", "article",
            "xxgk_content", "main-content", "detail-content",
            "content_article", "art_con", "news_content",
        ]:
            m = re.search(rf'class=["\']{cls}["\'][^>]*>(.*?)</div>', html, re.S | re.I)
            if m:
                body_html = m.group(1)
                break
        if not body_html:
            body_html = html

        text = re.sub(r"<[^>]+>", " ", body_html)
        text = re.sub(r"&[a-z]+;", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_len:
            text = text[:max_len] + "…"
        return text
    except Exception:
        return ""


def filter_notifications(items):
    result = []
    for it in items:
        t = it["title"]
        if any(kw in t for kw in EXCLUDE_KW):
            continue
        if any(kw in t for kw in INCLUDE_KW):
            result.append(it)
    return result


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"seen": {}}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _key(item):
    return hashlib.md5((item["title"] + item["date"]).encode()).hexdigest()


def is_new(state, item):
    return _key(item) not in state["seen"]


def mark_seen(state, items):
    for it in items:
        state["seen"][_key(it)] = {"title": it["title"], "date": it["date"]}


def send_email(config, subject, html_body):
    msg = MIMEMultipart()
    msg["From"] = config["sender"]
    msg["To"] = config["receiver"]
    msg["Subject"] = Header(subject, "utf-8")
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    server = smtplib.SMTP_SSL(config["smtp_server"], config["smtp_port"])
    server.login(config["sender"], config["auth_code"])
    server.sendmail(config["sender"], config["receiver"], msg.as_string())
    server.quit()


def build_html(new_by_source, all_by_source=None):
    today = datetime.now().strftime("%Y年%m月%d日")
    parts = [f"<h2 style='color:#1a73e8'>📢 江苏师范大学每日通知推送（{today}）</h2>"]
    total_new = sum(len(v) for v in new_by_source.values())

    if total_new > 0:
        parts.append(f"<p>🆕 今日新增 <b style='color:#d73a49'>{total_new}</b> 条相关通知：</p>")
        for src, items in new_by_source.items():
            if not items:
                continue
            parts.append(f"<h3>{SOURCE_NAMES.get(src, src)}</h3>")
            for it in items:
                summary = fetch_summary(it["url"], 400)
                parts.append(
                    f'''<div style="margin:10px 0;padding:10px;border-left:3px solid #1a73e8;background:#f6f8fa;border-radius:4px">
<b>[{it["date"]}] <a href="{it["url"]}">{it["title"]}</a></b><br>
<span style="color:#333;font-size:13px">{summary or "（点击查看详情）"}</span>
</div>'''
                )
    else:
        parts.append("<p style='color:#28a745'>✅ 今日无新增竞赛/考试/报名通知。</p>")

    if all_by_source:
        parts.append("<hr><h3 style='color:#586069'>📋 当前各栏目最近相关通知：</h3>")
        for src, items in all_by_source.items():
            if not items:
                continue
            parts.append(f"<p><b>{SOURCE_NAMES.get(src, src)}</b></p>")
            for it in items[:5]:
                summary = fetch_summary(it["url"], 300)
                parts.append(
                    f'''<div style="margin:8px 0;padding:8px;border-left:3px solid #ccc;background:#fafbfc;border-radius:4px">
<span style="color:#586069">[{it["date"]}]</span> <a href="{it["url"]}" style="color:#24292e">{it["title"]}</a><br>
<span style="color:#586069;font-size:12px">{summary}</span>
</div>'''
                )

    parts.append("<hr><p style='color:#999;font-size:12px'>本邮件由每日自动监控任务发送 · 筛选竞赛/考试/报名相关通知</p>")
    return "".join(parts)


def main():
    config = load_config()
    state = load_state()
    new_by_source, all_by_source = {}, {}

    for src, url in SOURCES.items():
        try:
            html = fetch(url)
            items = filter_notifications(extract_list_items(html, url))
            new_items = [it for it in items if is_new(state, it)]
            new_by_source[src] = new_items
            all_by_source[src] = items
            print(f"[{src}] 共 {len(items)} 条相关，新增 {len(new_items)} 条", file=sys.stderr)
        except Exception as e:
            print(f"[{src}] 抓取失败: {e}", file=sys.stderr)
            new_by_source[src] = []
            all_by_source[src] = []

    # 首次运行：只建基线，不发正文
    if not state.get("initialized"):
        state["initialized"] = True
        all_items = []
        for src, url in SOURCES.items():
            try:
                all_items.extend(extract_list_items(fetch(url), url))
            except Exception:
                pass
        mark_seen(state, all_items)
        save_state(state)
        send_email(
            config,
            "【通知雷达】已启动（首次基线建立）",
            "<p>每日通知监控已启动。下次开始每天早上 9 点自动推送新通知。</p>",
        )
        return

    total_new = sum(len(v) for v in new_by_source.values())
    if total_new > 0:
        for items in new_by_source.values():
            mark_seen(state, items)
        save_state(state)
        subject = f"【{total_new}条新通知】江苏师范大学通知日报 - {datetime.now().strftime('%m月%d日')}"
    else:
        # 没有新通知也发一封，否则分不清「今天真没通知」和「脚本挂了」
        subject = f"【通知日报】江苏师范大学 - {datetime.now().strftime('%m月%d日')}"

    send_email(config, subject, build_html(new_by_source, all_by_source))
    print(f"已发送邮件：新增 {total_new} 条", file=sys.stderr)


if __name__ == "__main__":
    main()
