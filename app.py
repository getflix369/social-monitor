from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import os
import re
import sqlite3
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from duckduckgo_search import DDGS
import google.generativeai as genai
import requests
import streamlit as st

ARCHIVE_JSON_FILE = "articles_archive.json"
CUSTOM_TARGETS_FILE = "custom_targets.json"
CONFIG_FILE = "credentials.json"
DB_FILE = "morocco_justice_hub.db"

INTERVAL_OPTIONS = {
    "15 دقيقة": 900,
    "ساعة واحدة": 3600,
    "3 ساعات": 10800,
    "6 ساعات": 21600,
    "12 ساعة": 43200,
    "24 ساعة": 86400,
}


def load_custom_targets():
  try:
    if "CUSTOM_TARGETS" in st.secrets:
      return json.loads(st.secrets["CUSTOM_TARGETS"])
  except Exception:
    pass

  if os.path.exists(CUSTOM_TARGETS_FILE):
    try:
      with open(CUSTOM_TARGETS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, list) and len(data) > 0:
          return data
    except Exception:
      pass

  return [
      {
          "url": "https://www.youtube.com/@CSPJ_Maroc",
          "platform": "YouTube",
          "kw": "",
      },
      {
          "url": "https://www.facebook.com/cspj.ma",
          "platform": "Facebook",
          "kw": "",
      },
  ]


def save_custom_targets(targets_list):
  try:
    with open(CUSTOM_TARGETS_FILE, "w", encoding="utf-8") as f:
      json.dump(targets_list, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


def load_config():
  cfg = {
      "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
      "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
      "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
      "model_choice": "gemini-3.5-flash-lite",
      "auto_refresh": True,
      "refresh_interval": "15 دقيقة",
      "last_auto_run": 0.0,
      "last_run_time_str": "لم يتم بعد",
      "send_telegram": True,
      "custom_keywords": "",
  }
  try:
    cfg["gemini_api_key"] = st.secrets.get(
        "GEMINI_API_KEY", cfg["gemini_api_key"]
    )
    cfg["telegram_bot_token"] = st.secrets.get(
        "TELEGRAM_BOT_TOKEN", cfg["telegram_bot_token"]
    )
    cfg["telegram_chat_id"] = st.secrets.get(
        "TELEGRAM_CHAT_ID", cfg["telegram_chat_id"]
    )
  except Exception:
    pass

  if os.path.exists(CONFIG_FILE):
    try:
      with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        saved = json.load(f)
        for k, v in saved.items():
          if v or isinstance(v, (bool, int, float)):
            cfg[k] = v
    except Exception:
      pass
  return cfg


def save_config(cfg_dict):
  try:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
      json.dump(cfg_dict, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


def init_db():
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            link TEXT PRIMARY KEY,
            platform TEXT,
            source TEXT,
            title TEXT,
            date_published TEXT,
            pub_timestamp REAL,
            snippet TEXT,
            ai_analysis TEXT,
            is_target_profile INTEGER DEFAULT 0,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
  conn.commit()

  if os.path.exists(ARCHIVE_JSON_FILE):
    try:
      with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
        content = json.load(f)
        articles_data = (
            content.get("articles", []) if isinstance(content, dict) else content
        )
        for it in articles_data:
          c.execute(
              """
                    INSERT OR IGNORE INTO items (link, platform, source, title, date_published, pub_timestamp, snippet, ai_analysis, is_target_profile, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
              (
                  it.get("link"),
                  it.get("platform"),
                  it.get("source"),
                  it.get("title"),
                  it.get("date_published"),
                  it.get("pub_timestamp", 0.0),
                  it.get("snippet"),
                  it.get("ai_analysis"),
                  it.get("is_target_profile", 0),
                  it.get("fetched_at", datetime.now().isoformat()),
              ),
          )
      conn.commit()
    except Exception:
      pass
  conn.close()


def export_db_and_targets():
  try:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT link, platform, source, title, date_published, pub_timestamp,"
        " snippet, ai_analysis, is_target_profile, fetched_at FROM items"
    )
    rows = c.fetchall()
    conn.close()
    items_list = []
    for r in rows:
      items_list.append({
          "link": r[0],
          "platform": r[1],
          "source": r[2],
          "title": r[3],
          "date_published": r[4],
          "pub_timestamp": r[5],
          "snippet": r[6],
          "ai_analysis": r[7],
          "is_target_profile": r[8],
          "fetched_at": r[9],
      })

    export_payload = {
        "articles": items_list,
        "custom_targets": load_custom_targets(),
        "exported_at": datetime.now().isoformat(),
    }

    with open(ARCHIVE_JSON_FILE, "w", encoding="utf-8") as f:
      json.dump(export_payload, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


def calculate_precise_timestamp(date_str):
  now = datetime.now(timezone.utc)
  if not date_str:
    return now.timestamp() - 3600
  try:
    return parsedate_to_datetime(date_str).timestamp()
  except Exception:
    pass

  s = str(date_str).lower()
  try:
    num_match = re.search(r"(\d+)", s)
    val = int(num_match.group(1)) if num_match else 1
    if any(w in s for w in ["دقيقة", "دقائق", "minute"]):
      return now.timestamp() - (val * 60)
    elif any(w in s for w in ["ساعة", "ساعات", "hour"]):
      return now.timestamp() - (val * 3600)
    elif any(w in s for w in ["يوم", "يومان", "أيام", "أمس", "day"]):
      days = 1 if "أمس" in s or ("يوم" in s and not num_match) else val
      return now.timestamp() - (days * 86400)
    elif any(w in s for w in ["أسبوع", "أسبوعين", "أسابيع", "week"]):
      return now.timestamp() - (val * 7 * 86400)
    elif any(w in s for w in ["شهر", "أشهر", "month"]):
      return now.timestamp() - (val * 30 * 86400)
  except Exception:
    pass

  return now.timestamp() - (2 * 86400)


# ==========================================
# محركات الجلب
# ==========================================
def fetch_target_youtube_direct(url_or_handle):
  raw = url_or_handle.strip()
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/122.0.0.0 Safari/537.36"
      ),
      "Accept-Language": "ar,en;q=0.9",
  }
  cookies = {
      "SOCS": "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg",
      "CONSENT": "PENDING+999",
  }

  handle_match = re.search(r"(@[a-zA-Z0-9_\-\.]+)", raw)
  channel_slug = handle_match.group(1) if handle_match else raw
  ch_url = (
      f"https://www.youtube.com/{channel_slug}"
      if not raw.startswith("http")
      else raw
  )

  channel_id = None
  try:
    resp = requests.get(
        ch_url, headers=headers, cookies=cookies, timeout=6, allow_redirects=True
    )
    m = re.search(r'"channelId":"([a-zA-Z0-9_\-]{24})"', resp.text)
    if not m:
      m = re.search(
          r'itemprop="channelId"\s+content="([a-zA-Z0-9_\-]{24})"', resp.text
      )
    if not m:
      m = re.search(r"channel_id=([a-zA-Z0-9_\-]{24})", resp.text)
    if m:
      channel_id = m.group(1)
  except Exception:
    pass

  results = []
  if channel_id:
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
      rss_resp = requests.get(
          rss_url, headers=headers, cookies=cookies, timeout=6
      )
      root = ET.fromstring(rss_resp.content)
      ns = {
          "atom": "http://www.w3.org/2005/Atom",
          "media": "http://search.yahoo.com/mrss/",
          "yt": "http://www.youtube.com/xml/schemas/2015",
      }
      for entry in root.findall("atom:entry", ns)[:10]:
        t_title = entry.find("atom:title", ns).text
        t_link = entry.find("atom:link", ns).attrib.get("href")
        t_date = entry.find("atom:published", ns).text
        desc_el = entry.find(".//media:description", ns)
        t_desc = desc_el.text if desc_el is not None else ""

        results.append({
            "platform": "YouTube",
            "source": f"قناة: {channel_slug}",
            "title": t_title,
            "link": t_link,
            "date": t_date[:10] if t_date else "حديثاً",
            "timestamp": calculate_precise_timestamp(t_date),
            "snippet": t_desc[:300],
            "is_target": 1,
        })
    except Exception:
      pass

  if not results:
    clean_kw = channel_slug.replace("@", "").replace(
        "https://www.youtube.com/", ""
    )
    yt_search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(clean_kw)}&sp=CAI%253D"
    try:
      r = requests.get(
          yt_search_url, headers=headers, cookies=cookies, timeout=6
      )
      v_ids = re.findall(r"/watch\?v=([a-zA-Z0-9_\-]{11})", r.text)
      titles = re.findall(r'"title":\{"runs":\[\{"text":"(.*?)"\}\]', r.text)
      seen_vids = set()
      for idx, vid in enumerate(v_ids[:6]):
        if vid in seen_vids:
          continue
        seen_vids.add(vid)
        vid_title = (
            titles[idx]
            if idx < len(titles)
            else f"فيديو يوتيوب حول {clean_kw}"
        )
        results.append({
            "platform": "YouTube",
            "source": f"قناة: {channel_slug}",
            "title": vid_title,
            "link": f"https://www.youtube.com/watch?v={vid}",
            "date": "حديثاً",
            "timestamp": datetime.now(timezone.utc).timestamp(),
            "snippet": f"فيديو صادر عن قناة {channel_slug}",
            "is_target": 1,
        })
    except Exception:
      pass

  return results


def fetch_target_website_direct(url_or_domain):
  clean = (
      url_or_domain.strip()
      .replace("https://", "")
      .replace("http://", "")
      .rstrip("/")
  )
  clean_dom = clean.split("/")[0]
  base = f"https://{clean_dom}"
  headers = {"User-Agent": "Mozilla/5.0"}
  results = []

  feed_urls = [
      f"{base}/feed/",
      f"{base}/feed",
      f"{base}/rss",
      f"http://{clean_dom}/feed/",
  ]
  for f_url in feed_urls:
    try:
      resp = requests.get(f_url, headers=headers, timeout=5)
      if resp.status_code == 200 and (
          "<rss" in resp.text or "<xml" in resp.text
      ):
        root = ET.fromstring(resp.content)
        for it in root.findall(".//item")[:10]:
          t = it.find("title").text if it.find("title") is not None else ""
          l = it.find("link").text if it.find("link") is not None else ""
          d = (
              it.find("description").text
              if it.find("description") is not None
              else ""
          )
          p = it.find("pubDate").text if it.find("pubDate") is not None else ""
          if t and l:
            results.append({
                "platform": "مواقع وصحف",
                "source": clean_dom,
                "title": t,
                "link": l,
                "date": p,
                "timestamp": calculate_precise_timestamp(p),
                "snippet": re.sub(r"<[^>]+>", "", d)[:300],
                "is_target": 1,
            })
        if results:
          break
    except Exception:
      pass

  return results


def fetch_target_social_direct(url_or_handle, platform_name):
  raw = url_or_handle.strip()
  headers = {"User-Agent": "Mozilla/5.0"}
  results = []

  slug = raw
  if "facebook.com/" in raw:
    m = re.search(r"facebook\.com/([^/?#]+)", raw)
    slug = m.group(1) if m else raw
  elif "x.com/" in raw or "twitter.com/" in raw:
    m = re.search(r"(?:x\.com|twitter\.com)/([^/?#]+)", raw)
    slug = m.group(1) if m else raw

  q_search = (
      f"site:facebook.com/{slug}"
      if platform_name == "Facebook"
      else f"site:x.com/{slug}"
  )
  try:
    with DDGS() as ddgs:
      for r in ddgs.text(q_search, max_results=8):
        results.append({
            "platform": platform_name,
            "source": f"صفحة: {slug}",
            "title": r.get("title", f"منشور على {platform_name}"),
            "link": r.get("href", ""),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now(timezone.utc).timestamp() - 1800,
            "snippet": r.get("body", "")[:300],
            "is_target": 1,
        })
  except Exception:
    pass

  if not results:
    try:
      enc = urllib.parse.quote(f'"{slug}" {platform_name}')
      url = f"https://news.google.com/rss/search?q={enc}&hl=ar&gl=MA&ceid=MA:ar"
      resp = requests.get(url, headers=headers, timeout=5)
      root = ET.fromstring(resp.content)
      for it in root.findall(".//item")[:6]:
        l = it.find("link").text
        t = it.find("title").text
        d = (
            it.find("description").text
            if it.find("description") is not None
            else ""
        )
        p = it.find("pubDate").text if it.find("pubDate") is not None else ""
        results.append({
            "platform": platform_name,
            "source": f"صفحة: {slug}",
            "title": t,
            "link": l,
            "date": p,
            "timestamp": calculate_precise_timestamp(p),
            "snippet": re.sub(r"<[^>]+>", "", d)[:300],
            "is_target": 1,
        })
    except Exception:
      pass

  return results


def execute_multi_target_monitor(targets_list, stop_check_fn=None):
  all_target_items = []
  seen_links = set()

  for t in targets_list:
    if stop_check_fn and stop_check_fn():
      break
    u = t["url"].strip()
    if not u:
      continue
    plat = t["platform"]
    kw_filter = t.get("kw", "").strip().lower()

    if plat == "كشف تلقائي من الرابط":
      if "youtube.com" in u or "youtu.be" in u or u.startswith("@"):
        plat = "YouTube"
      elif "facebook.com" in u:
        plat = "Facebook"
      elif "x.com" in u or "twitter.com" in u:
        plat = "X (Twitter)"
      elif "tiktok.com" in u:
        plat = "TikTok"
      elif "linkedin.com" in u:
        plat = "LinkedIn"
      else:
        plat = "مواقع وصحف"

    if plat == "YouTube":
      items = fetch_target_youtube_direct(u)
    elif plat == "مواقع وصحف":
      items = fetch_target_website_direct(u)
    else:
      items = fetch_target_social_direct(u, plat)

    for item in items:
      if item["link"] in seen_links:
        continue
      if kw_filter:
        full_text = f"{item['title']} {item['snippet']}".lower()
        if kw_filter not in full_text:
          continue
      seen_links.add(item["link"])
      all_target_items.append(item)

  return all_target_items


def fetch_moroccan_sites_quick(
    custom_input, max_count=20, stop_check_fn=None
):
  results = []
  seen = set()
  headers = {"User-Agent": "Mozilla/5.0"}

  queries = [
      '"المجلس الأعلى للسلطة القضائية" when:1d',
      '"القضاء المغربي" OR "محكمة النقض" when:1d',
      '"العدالة بالمغرب" OR "وزارة العدل" when:1d',
  ]
  cleaned = custom_input.strip()
  if cleaned:
    kws = [k.strip() for k in cleaned.split(",") if k.strip()]
    queries = [
        f'"{k}" (قضاء OR محكمة OR عدالة OR المغرب) when:1d' for k in kws
    ]

  for q in queries:
    if (stop_check_fn and stop_check_fn()) or len(results) >= max_count:
      break
    try:
      enc = urllib.parse.quote(q)
      url = (
          f"https://news.google.com/rss/search?q={enc}&hl=ar&gl=MA&ceid=MA:ar"
      )
      resp = requests.get(url, headers=headers, timeout=5)
      root = ET.fromstring(resp.content)
      for item in root.findall(".//item"):
        link = item.find("link").text if item.find("link") is not None else ""
        if not link or link in seen:
          continue
        title = (
            item.find("title").text if item.find("title") is not None else ""
        )
        desc = (
            item.find("description").text
            if item.find("description") is not None
            else ""
        )
        pdate = (
            item.find("pubDate").text
            if item.find("pubDate") is not None
            else ""
        )
        src = (
            item.find("source").text
            if item.find("source") is not None
            else "صحيفة مغربية"
        )

        clean_d = re.sub(r"<[^>]+>", "", desc)
        results.append({
            "platform": "مواقع وصحف",
            "source": src,
            "title": title,
            "link": link,
            "date": pdate,
            "timestamp": calculate_precise_timestamp(pdate),
            "snippet": clean_d,
            "is_target": 0,
        })
        seen.add(link)
        if len(results) >= max_count:
          break
    except Exception:
      pass

  return results


def fetch_youtube_posts_live(custom_input, max_count=12, stop_check_fn=None):
  results = []
  seen = set()
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/122.0.0.0 Safari/537.36"
      ),
      "Accept-Language": "ar,en;q=0.9",
  }
  cookies = {
      "SOCS": "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg",
      "CONSENT": "PENDING+999",
  }

  topic = (
      custom_input.strip()
      if custom_input.strip()
      else "المجلس الأعلى للسلطة القضائية المغرب"
  )
  yt_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(topic)}&sp=CAI%253D"

  try:
    resp = requests.get(yt_url, headers=headers, cookies=cookies, timeout=6)
    v_ids = re.findall(r"/watch\?v=([a-zA-Z0-9_\-]{11})", resp.text)
    titles = re.findall(r'"title":\{"runs":\[\{"text":"(.*?)"\}\]', resp.text)
    for idx, vid in enumerate(v_ids[:max_count]):
      if vid in seen or (stop_check_fn and stop_check_fn()):
        continue
      seen.add(vid)
      v_title = (
          titles[idx] if idx < len(titles) else f"فيديو يوتيوب حول: {topic}"
      )
      results.append({
          "platform": "YouTube",
          "source": "قناة YouTube",
          "title": v_title,
          "link": f"https://www.youtube.com/watch?v={vid}",
          "date": "حديثاً",
          "timestamp": datetime.now(timezone.utc).timestamp() - 1200,
          "snippet": f"فيديو يوتيوب مصور يتناول: {topic}",
          "is_target": 0,
      })
  except Exception:
    pass

  return results


def fetch_facebook_posts_live(custom_input, max_count=10, stop_check_fn=None):
  results = []
  seen = set()
  topic = (
      custom_input.strip()
      if custom_input.strip()
      else "المجلس الأعلى للسلطة القضائية"
  )

  try:
    with DDGS() as ddgs:
      for r in ddgs.text(
          f'site:facebook.com "{topic}"', max_results=max_count, timelimit="w"
      ):
        if stop_check_fn and stop_check_fn():
          break
        link = r.get("href", "")
        if not link or link in seen or "facebook.com" not in link:
          continue
        seen.add(link)
        results.append({
            "platform": "Facebook",
            "source": "صفحة فيسبوك",
            "title": r.get("title", f"منشور فيسبوك حول {topic}"),
            "link": link,
            "date": "هذا الأسبوع",
            "timestamp": datetime.now(timezone.utc).timestamp() - 3600,
            "snippet": r.get("body", ""),
            "is_target": 0,
        })
  except Exception:
    pass

  if not results:
    try:
      enc = urllib.parse.quote(f'"{topic}" فيسبوك when:1d')
      url = f"https://news.google.com/rss/search?q={enc}&hl=ar&gl=MA&ceid=MA:ar"
      resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
      root = ET.fromstring(resp.content)
      for it in root.findall(".//item")[:max_count]:
        l = it.find("link").text
        if l not in seen:
          seen.add(l)
          results.append({
              "platform": "Facebook",
              "source": "تغطية فيسبوك",
              "title": it.find("title").text,
              "link": l,
              "date": it.find("pubDate").text or "حديثاً",
              "timestamp": calculate_precise_timestamp(it.find("pubDate").text),
              "snippet": re.sub(
                  r"<[^>]+>", "", it.find("description").text or ""
              )[:300],
              "is_target": 0,
          })
    except Exception:
      pass

  return results


def fetch_x_posts_live(custom_input, max_count=10, stop_check_fn=None):
  results = []
  seen = set()
  topic = (
      custom_input.strip()
      if custom_input.strip()
      else "المجلس الأعلى للسلطة القضائية"
  )

  nitter_instances = [
      f"https://nitter.poast.org/search/rss?f=tweets&q={urllib.parse.quote(topic)}",
      f"https://nitter.privacydev.net/search/rss?f=tweets&q={urllib.parse.quote(topic)}",
  ]
  for n_url in nitter_instances:
    try:
      r = requests.get(n_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
      if r.status_code == 200 and "<rss" in r.text:
        rt = ET.fromstring(r.content)
        for it in rt.findall(".//item")[:max_count]:
          l = (
              it.find("link")
              .text.replace("nitter.poast.org", "x.com")
              .replace("nitter.privacydev.net", "x.com")
          )
          if l not in seen:
            seen.add(l)
            results.append({
                "platform": "X (Twitter)",
                "source": "تغريدة على X",
                "title": it.find("title").text[:80],
                "link": l,
                "date": it.find("pubDate").text or "حديثاً",
                "timestamp": calculate_precise_timestamp(
                    it.find("pubDate").text
                ),
                "snippet": re.sub(
                    r"<[^>]+>", "", it.find("description").text or ""
                )[:300],
                "is_target": 0,
            })
        if results:
          break
    except Exception:
      pass

  if not results:
    try:
      with DDGS() as ddgs:
        for r in ddgs.text(
            f'site:x.com "{topic}"', max_results=max_count, timelimit="w"
        ):
          if stop_check_fn and stop_check_fn():
            break
          link = r.get("href", "")
          if link and link not in seen:
            seen.add(link)
            results.append({
                "platform": "X (Twitter)",
                "source": "تغريدة على X",
                "title": r.get("title", f"تغريدة حول {topic}"),
                "link": link,
                "date": "حديثاً",
                "timestamp": datetime.now(timezone.utc).timestamp() - 3600,
                "snippet": r.get("body", ""),
                "is_target": 0,
            })
    except Exception:
      pass

  return results


def fetch_other_social_live(custom_input, max_count=8, stop_check_fn=None):
  results = []
  seen = set()
  topic = (
      custom_input.strip()
      if custom_input.strip()
      else "المجلس الأعلى للسلطة القضائية المغرب"
  )
  try:
    with DDGS() as ddgs:
      for r in ddgs.text(
          f'(site:tiktok.com OR site:linkedin.com) "{topic}"',
          max_results=max_count,
      ):
        if stop_check_fn and stop_check_fn():
          break
        link = r.get("href", "")
        if link and link not in seen:
          seen.add(link)
          plat = "TikTok" if "tiktok.com" in link else "LinkedIn"
          results.append({
              "platform": plat,
              "source": f"حساب {plat}",
              "title": r.get("title", f"محتوى على {plat}"),
              "link": link,
              "date": "حديثاً",
              "timestamp": datetime.now(timezone.utc).timestamp() - 3600,
              "snippet": r.get("body", ""),
              "is_target": 0,
          })
  except Exception:
    pass
  return results


def quick_process_and_save(
    items_list,
    cfg,
    is_target_run=False,
    stop_check_fn=None,
    progress_cb=None,
):
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()

  new_candidates = []
  for it in items_list:
    c.execute("SELECT link FROM items WHERE link = ?", (it["link"],))
    if not c.fetchone():
      new_candidates.append(it)

  new_candidates = new_candidates[:8]
  new_count = 0
  api_key = cfg.get("gemini_api_key", "")
  model_name = cfg.get("model_choice", "gemini-3.5-flash-lite")
  tg_token = cfg.get("telegram_bot_token", "")
  tg_chat = cfg.get("telegram_chat_id", "")
  send_tg = cfg.get("send_telegram", True)

  if new_candidates and api_key:
    for i, it in enumerate(new_candidates):
      if stop_check_fn and stop_check_fn():
        break

      summary = ""
      try:
        genai.configure(api_key=api_key)
        m = genai.GenerativeModel(model_name)
        prompt = f"""
أنت مستشار قضائي وإعلامي بالمملكة المغربية.
العنوان: {it['title']}
المحتوى: {it['snippet']}

المطلوب:
اكتب ملخصاً إخبارياً تنفيذياً في جملتين فقط يوضح موضوع الخبر والوقائع القانونية.
"""
        res = m.generate_content(prompt)
        summary = res.text.strip()
      except Exception:
        summary = f"مستجد إخباري منشور عبر {it['source']}"

      if not summary:
        summary = "تم رصد المادة بنجاح."

      it["ai_analysis"] = summary
      c.execute(
          """
                INSERT INTO items (link, platform, source, title, date_published, pub_timestamp, snippet, ai_analysis, is_target_profile)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
          (
              it["link"],
              it["platform"],
              it["source"],
              it["title"],
              it["date"],
              it.get("timestamp", 0.0),
              it["snippet"],
              summary,
              it.get("is_target", 0),
          ),
      )
      conn.commit()
      new_count += 1

      if send_tg and tg_token and tg_chat:
        tag = (
            "⭐ [رصد حصري من صفحة متابعة]"
            if it.get("is_target")
            else "⚖️ [رصد قضائي جديد]"
        )
        msg = (
            f"{tag}\n\n"
            f"🌐 *المنصة:* {it['platform']}\n"
            f"🏛️ *المصدر / الحساب:* `{it['source']}`\n"
            f"📅 *تاريخ النشر:* {it['date']}\n"
            f"📌 *العنوان:* {it['title']}\n\n"
            f"📝 *مضمون ومقتطف المنشور:*\n_{it['snippet'][:250]}..._\n\n"
            f"💡 *الملخص والتحليل الذكي (Gemini):*\n{summary}\n\n"
            f"🔗 *رابط المشاهدة / القراءة كاملاً:*\n{it['link']}"
        )
        try:
          requests.post(
              f"https://api.telegram.org/bot{tg_token}/sendMessage",
              json={
                  "chat_id": tg_chat,
                  "text": msg,
                  "parse_mode": "Markdown",
              },
              timeout=5,
          )
        except Exception:
          pass

      if progress_cb:
        progress_cb(float(i + 1) / float(len(new_candidates)))
      time.sleep(0.3)

  conn.close()
  export_db_and_targets()
  return new_count


def run_headless_background_cycle():
  """دورة الرصد الذاتية التي تعمل في الخلفية تلقائياً دون تدخل المستخدم"""
  cfg = load_config()
  if not cfg.get("gemini_api_key"):
    return 0
  custom_in = cfg.get("custom_keywords", "").strip()
  raw_items = []
  raw_items.extend(fetch_moroccan_sites_quick(custom_in, max_count=20))
  raw_items.extend(fetch_youtube_posts_live(custom_in, max_count=8))
  raw_items.extend(fetch_facebook_posts_live(custom_in, max_count=8))
  raw_items.extend(fetch_x_posts_live(custom_in, max_count=8))
  raw_items.extend(fetch_other_social_live(custom_in, max_count=6))
  targets = load_custom_targets()
  if targets:
    raw_items.extend(execute_multi_target_monitor(targets))

  added = quick_process_and_save(raw_items, cfg, is_target_run=False)
  cfg["last_auto_run"] = time.time()
  cfg["last_run_time_str"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  save_config(cfg)
  return added


# في حال التشغيل عبر GitHub Actions Cron في الخلفية
if os.getenv("CRON_MODE") == "1":
  init_db()
  run_headless_background_cycle()
  raise SystemExit(0)


# ==========================================
# خيط الخلفية الدائم (Background Daemon Thread) للرصد التلقائي المستمر
# ==========================================
@st.cache_resource
def start_background_daemon():
  def daemon_loop():
    while True:
      try:
        cfg = load_config()
        if cfg.get("auto_refresh", False) and cfg.get("gemini_api_key"):
          interval_label = cfg.get("refresh_interval", "15 دقيقة")
          interval_sec = INTERVAL_OPTIONS.get(interval_label, 900)
          last_run = float(cfg.get("last_auto_run", 0.0))
          if (time.time() - last_run) >= interval_sec:
            run_headless_background_cycle()
      except Exception:
        pass
      time.sleep(30)

  t = threading.Thread(target=daemon_loop, daemon=True)
  t.start()
  return t


init_db()
start_background_daemon()
current_cfg = load_config()

st.set_page_config(
    page_title="المرصد الوطني للعدالة والقضاء",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"], .main, .block-container, [data-testid="stMain"] {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif !important;
        background: #090d16 !important;
        background: radial-gradient(circle at 15% 15%, rgba(30, 58, 138, 0.22) 0%, rgba(9, 13, 22, 1) 85%) !important;
        color: #f1f5f9 !important;
    }

    p, span, div, h1, h2, h3, h4, h5, h6, label, [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] * {
        direction: rtl !important;
        text-align: right !important;
        color: #f8fafc !important;
    }

    [data-testid="stSidebar"], [data-testid="stSidebarContent"] {
        direction: rtl !important;
        text-align: right !important;
        background: rgba(13, 17, 28, 0.88) !important;
        backdrop-filter: blur(20px) !important;
        border-left: 1px solid rgba(255, 255, 255, 0.08) !important;
    }

    input, textarea, select, .stTextInput input, .stTextArea textarea, [data-baseweb="input"], [data-baseweb="base-input"] {
        direction: rtl !important;
        text-align: right !important;
        background: rgba(19, 27, 46, 0.75) !important;
        border: 1px solid rgba(255, 255, 255, 0.14) !important;
        color: #f8fafc !important;
        border-radius: 10px !important;
    }

    div[data-baseweb="tab-list"] {
        direction: rtl !important;
        justify-content: flex-start !important;
        flex-direction: row !important;
        gap: 6px !important;
        border-bottom: 2px solid rgba(255, 255, 255, 0.08) !important;
    }
    button[data-baseweb="tab"] {
        direction: rtl !important;
        text-align: center !important;
        font-size: 0.98rem !important;
        font-weight: 700 !important;
        padding: 8px 16px !important;
        border-radius: 8px 8px 0 0 !important;
        background: rgba(19, 27, 46, 0.4) !important;
        color: #94a3b8 !important;
        border: 1px solid transparent !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background: rgba(56, 189, 248, 0.12) !important;
        color: #38bdf8 !important;
        border-bottom: 3px solid #38bdf8 !important;
        text-shadow: 0 0 10px rgba(56, 189, 248, 0.5) !important;
    }

    .stButton > button,
    button[data-testid="baseButton-secondary"],
    button[data-testid="baseButton-primary"],
    .stDownloadButton > button {
        background: rgba(30, 41, 59, 0.85) !important;
        color: #f8fafc !important;
        border: 1px solid rgba(255, 255, 255, 0.16) !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        padding: 10px 18px !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3) !important;
        transition: all 0.2s ease !important;
        backdrop-filter: blur(10px) !important;
        width: 100% !important;
    }

    .stButton > button p, .stButton > button span, .stButton > button div {
        color: inherit !important;
        font-weight: 700 !important;
    }

    .btn-global-all .stButton > button {
        background: linear-gradient(135deg, #1d4ed8 0%, #6d28d9 100%) !important;
        color: #ffffff !important;
        border: 1px solid #60a5fa !important;
        box-shadow: 0 4px 20px rgba(37, 99, 235, 0.45) !important;
        font-size: 1.02rem !important;
    }
    .btn-facebook .stButton > button {
        background: linear-gradient(135deg, #1877f2 0%, #0284c7 100%) !important;
        color: #ffffff !important;
        border: 1px solid #60a5fa !important;
    }
    .btn-x .stButton > button {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
        color: #f8fafc !important;
        border: 1px solid #94a3b8 !important;
    }
    .btn-youtube .stButton > button {
        background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%) !important;
        color: #ffffff !important;
        border: 1px solid #f87171 !important;
    }
    .btn-press .stButton > button {
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
        color: #ffffff !important;
        border: 1px solid #38bdf8 !important;
    }
    .btn-other .stButton > button {
        background: linear-gradient(135deg, #9333ea 0%, #06b6d4 100%) !important;
        color: #ffffff !important;
        border: 1px solid #c084fc !important;
    }
    .btn-custom-target .stButton > button {
        background: linear-gradient(135deg, #059669 0%, #0d9488 100%) !important;
        color: #ffffff !important;
        border: 1px solid #34d399 !important;
    }
    .btn-stop .stButton > button {
        background: rgba(185, 28, 28, 0.45) !important;
        color: #fca5a5 !important;
        border: 1px solid #ef4444 !important;
    }
    .btn-add .stButton > button {
        background: rgba(16, 185, 129, 0.2) !important;
        color: #34d399 !important;
        border: 1px dashed #10b981 !important;
    }
    .btn-save .stButton > button {
        background: rgba(14, 165, 233, 0.22) !important;
        color: #38bdf8 !important;
        border: 1px solid #0ea5e9 !important;
    }
    .btn-del .stButton > button {
        background: rgba(239, 68, 68, 0.2) !important;
        color: #f87171 !important;
        border: 1px solid #ef4444 !important;
        padding: 6px !important;
    }

    .result-card {
        direction: rtl !important;
        text-align: right !important;
        background: rgba(17, 24, 39, 0.72) !important;
        backdrop-filter: blur(16px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 20px;
        border-radius: 14px;
        margin-bottom: 18px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
    }

    .border-facebook { border-right: 6px solid #1877f2 !important; }
    .border-x { border-right: 6px solid #e2e8f0 !important; }
    .border-youtube { border-right: 6px solid #ef4444 !important; }
    .border-instagram { border-right: 6px solid #ec4899 !important; }
    .border-tiktok { border-right: 6px solid #06b6d4 !important; }
    .border-linkedin { border-right: 6px solid #0284c7 !important; }
    .border-news { border-right: 6px solid #3b82f6 !important; }
    .border-target { border-right: 6px solid #10b981 !important; }
    .border-archive { border-right: 6px solid #64748b !important; }

    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.82em;
        margin-left: 8px;
    }
    .badge-facebook { background: rgba(24, 119, 242, 0.18); color: #3b82f6; border: 1px solid rgba(24, 119, 242, 0.4); }
    .badge-x { background: rgba(241, 245, 249, 0.12); color: #f8fafc; border: 1px solid rgba(241, 245, 249, 0.3); }
    .badge-youtube { background: rgba(239, 68, 68, 0.18); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
    .badge-instagram { background: rgba(236, 72, 153, 0.18); color: #f472b6; border: 1px solid rgba(236, 72, 153, 0.4); }
    .badge-tiktok { background: rgba(6, 182, 212, 0.18); color: #22d3ee; border: 1px solid rgba(6, 182, 212, 0.4); }
    .badge-linkedin { background: rgba(2, 132, 199, 0.18); color: #38bdf8; border: 1px solid rgba(2, 132, 199, 0.4); }
    .badge-news { background: rgba(59, 130, 246, 0.18); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); }
    .badge-target { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
    .badge-archive { background: rgba(100, 116, 139, 0.2); color: #94a3b8; border: 1px solid rgba(100, 116, 139, 0.3); }

    .meta-line { color: #94a3b8 !important; font-size: 0.88em; margin: 8px 0; }
    .desc-box {
        background: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.06);
        padding: 12px;
        border-radius: 8px;
        font-size: 0.94em;
        color: #cbd5e1 !important;
        line-height: 1.6;
        margin-bottom: 12px;
    }
    .ai-box {
        background: rgba(6, 78, 59, 0.22) !important;
        border: 1px solid rgba(16, 185, 129, 0.35);
        padding: 12px 14px;
        border-radius: 8px;
        color: #6ee7b7 !important;
        font-size: 0.92em;
        margin-bottom: 12px;
        line-height: 1.6;
    }
    .action-btn {
        display: inline-block;
        padding: 8px 18px;
        border-radius: 8px;
        color: white !important;
        text-decoration: none !important;
        font-weight: 700;
        font-size: 0.88em;
    }

    @keyframes radar-sweep { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    @keyframes radar-blip { 0%, 100% { opacity: 0.2; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.2); } }
    .radar-wrapper {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 20px;
        margin: 14px 0;
        background: rgba(15, 23, 42, 0.7);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 16px;
    }
    .radar-screen {
        position: relative;
        width: 120px;
        height: 120px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(14, 165, 233, 0.08) 0%, rgba(15, 23, 42, 0.9) 70%);
        border: 2px solid rgba(56, 189, 248, 0.45);
        overflow: hidden;
        margin-bottom: 10px;
    }
    .radar-screen::before {
        content: '';
        position: absolute;
        top: 50%; left: 50%;
        width: 60px; height: 60px;
        transform: translate(-50%, -50%);
        border-radius: 50%;
        border: 1px dashed rgba(56, 189, 248, 0.3);
    }
    .radar-sweep-arm {
        position: absolute;
        top: 0; left: 0;
        width: 100%; height: 100%;
        border-radius: 50%;
        background: conic-gradient(from 0deg, rgba(56, 189, 248, 0) 0deg, rgba(56, 189, 248, 0.5) 60deg, transparent 65deg);
        animation: radar-sweep 2s linear infinite;
    }
    .radar-target-dot {
        position: absolute;
        top: 38%; left: 62%;
        width: 7px; height: 7px;
        background: #38bdf8;
        border-radius: 50%;
        box-shadow: 0 0 10px #38bdf8;
        animation: radar-blip 1.5s ease-in-out infinite;
    }
    .done-badge {
        display: inline-block;
        padding: 8px 22px;
        border-radius: 10px;
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid #10b981;
        color: #34d399 !important;
        font-weight: 800;
        font-size: 1.05rem;
        margin: 10px 0;
        text-align: center;
    }
    .status-pill {
        padding: 6px 12px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.88em;
        text-align: center;
        margin-bottom: 15px;
    }
    .status-pill-ok { background-color: #dcfce7; color: #15803d; border: 1px solid #86efac; }
    .status-pill-err { background-color: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; }
    </style>
""",
    unsafe_allow_html=True,
)

# الشريط الجانبي
with st.sidebar:
  st.header("⚙️ الإعدادات")

  gemini_api_key = st.text_input(
      "مفتاح Gemini API:",
      value=current_cfg.get("gemini_api_key", ""),
      type="password",
  )
  telegram_token = st.text_input(
      "رمز بوت تيليجرام:",
      value=current_cfg.get("telegram_bot_token", ""),
      type="password",
  )
  telegram_chat_id = st.text_input(
      "معرّف المحادثة (Chat ID):", value=current_cfg.get("telegram_chat_id", "")
  )

  model_choice = st.selectbox(
      "النموذج:",
      options=[
          "gemini-3.5-flash-lite",
          "gemini-1.5-flash",
          "gemini-2.0-flash",
      ],
      index=0,
  )

  if st.button("💾 حفظ المفاتيح"):
    current_cfg["gemini_api_key"] = gemini_api_key
    current_cfg["telegram_bot_token"] = telegram_token
    current_cfg["telegram_chat_id"] = telegram_chat_id
    current_cfg["model_choice"] = model_choice
    save_config(current_cfg)
    st.toast("✅ تم الحفظ.")

  if gemini_api_key:
    st.markdown(
        f'<div class="status-pill status-pill-ok">🟢 متصل ({model_choice})</div>',
        unsafe_allow_html=True,
    )
  else:
    st.markdown(
        '<div class="status-pill status-pill-err">🔴 غير متصل</div>',
        unsafe_allow_html=True,
    )

  st.divider()
  st.header("⏱️ الرصد التلقائي")

  saved_interval = current_cfg.get("refresh_interval", "15 دقيقة")
  interval_keys = list(INTERVAL_OPTIONS.keys())
  default_idx = (
      interval_keys.index(saved_interval)
      if saved_interval in interval_keys
      else 0
  )

  selected_interval_label = st.selectbox(
      "الفترة الزمنية:",
      options=interval_keys,
      index=default_idx,
  )

  auto_refresh_enabled = st.checkbox(
      f"🔄 رصد تلقائي ({selected_interval_label})",
      value=current_cfg.get("auto_refresh", True),
  )
  send_telegram = st.checkbox(
      "📲 إشعارات Telegram", value=current_cfg.get("send_telegram", True)
  )

  if (
      auto_refresh_enabled != current_cfg.get("auto_refresh")
      or selected_interval_label != saved_interval
      or send_telegram != current_cfg.get("send_telegram")
  ):
    current_cfg["auto_refresh"] = auto_refresh_enabled
    current_cfg["refresh_interval"] = selected_interval_label
    current_cfg["send_telegram"] = send_telegram
    save_config(current_cfg)

  st.caption(f"🕒 آخر فحص: **{current_cfg.get('last_run_time_str', 'لم يتم بعد')}**")

  st.divider()
  st.header("🛡️ الأرشيف")
  export_db_and_targets()
  if os.path.exists(ARCHIVE_JSON_FILE):
    with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
      st.download_button(
          "📥 تنزيل النسخة الاحتياطية",
          f.read(),
          file_name="morocco_justice_full_backup.json",
          mime="application/json",
      )

  uploaded_bk = st.file_uploader("📤 استعادة نسخة:", type=["json"])
  if uploaded_bk is not None:
    try:
      imported_content = json.load(uploaded_bk)
      articles_part = (
          imported_content.get("articles", [])
          if isinstance(imported_content, dict)
          else imported_content
      )
      conn = sqlite3.connect(DB_FILE)
      c = conn.cursor()
      for it in articles_part:
        c.execute(
            """
                INSERT OR IGNORE INTO items (link, platform, source, title, date_published, pub_timestamp, snippet, ai_analysis, is_target_profile, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                it.get("link"),
                it.get("platform"),
                it.get("source"),
                it.get("title"),
                it.get("date_published"),
                it.get("pub_timestamp", 0.0),
                it.get("snippet"),
                it.get("ai_analysis"),
                it.get("is_target_profile", 0),
                it.get("fetched_at", datetime.now().isoformat()),
            ),
        )
      conn.commit()
      conn.close()

      if (
          isinstance(imported_content, dict)
          and "custom_targets" in imported_content
      ):
        save_custom_targets(imported_content["custom_targets"])
        st.session_state.dynamic_targets = imported_content["custom_targets"]

      export_db_and_targets()
      st.success("✅ تمت الاستعادة!")
      st.rerun()
    except Exception as e:
      st.error(f"خطأ: {e}")

# تحديث الصفحة تلقائياً عند تفعيل الرصد الآلي لعرض النتائج الجديدة
if auto_refresh_enabled:
  interval_ms = INTERVAL_OPTIONS.get(selected_interval_label, 900) * 1000
  st.markdown(
      f'<script>setTimeout(function(){{ window.location.reload(); }}, {interval_ms});</script>',
      unsafe_allow_html=True,
  )
  # إذا حل موعد الفحص عند فتح الصفحة، يتم تنفيذه فوراً
  if gemini_api_key and (
      time.time() - float(current_cfg.get("last_auto_run", 0.0))
  ) >= INTERVAL_OPTIONS.get(selected_interval_label, 900):
    with st.spinner("🔄 جارٍ التحديث الدوري التلقائي..."):
      run_headless_background_cycle()
      current_cfg = load_config()

# الواجهة الرئيسية النقية بدون نصوص شرح زائدة
st.title("⚖️ المرصد الوطني للعدالة والقضاء")

if "stop_flags" not in st.session_state:
  st.session_state.stop_flags = {
      "all": False,
      "custom": False,
      "press": False,
      "fb": False,
      "x": False,
      "yt": False,
      "other": False,
  }

# شريط البحث والرصد الشامل المدمج
c_kw, c_all_run, c_all_stop = st.columns([3, 2, 1])
with c_kw:
  keywords_input = st.text_input(
      "تخصيص بكلمات مفتاحية:",
      value=current_cfg.get("custom_keywords", ""),
      placeholder="🔍 تخصيص بكلمات مفتاحية (اختياري)...",
      label_visibility="collapsed",
  )
  if keywords_input != current_cfg.get("custom_keywords", ""):
    current_cfg["custom_keywords"] = keywords_input
    save_config(current_cfg)

with c_all_run:
  st.markdown('<div class="btn-global-all">', unsafe_allow_html=True)
  btn_run_all = st.button("🚀 رصد الشامل (الكل)", key="btn_run_all")
  st.markdown("</div>", unsafe_allow_html=True)

with c_all_stop:
  st.markdown('<div class="btn-stop">', unsafe_allow_html=True)
  if st.button("🛑 إيقاف", key="btn_stop_all"):
    st.session_state.stop_flags["all"] = True
  st.markdown("</div>", unsafe_allow_html=True)

radar_placeholder = st.empty()
progress_placeholder = st.empty()
done_placeholder = st.empty()

# أزرار الرصد الخاص بكل منصة في صف واحد أنيق
c_p1, c_p2, c_p3, c_p4, c_p5 = st.columns(5)
with c_p1:
  st.markdown('<div class="btn-press">', unsafe_allow_html=True)
  btn_run_press = st.button("📰 رصد الصحف", key="btn_run_press")
  st.markdown("</div>", unsafe_allow_html=True)
  st.markdown('<div class="btn-stop">', unsafe_allow_html=True)
  if st.button("🛑 إيقاف الصحف", key="btn_stop_press"):
    st.session_state.stop_flags["press"] = True
  st.markdown("</div>", unsafe_allow_html=True)

with c_p2:
  st.markdown('<div class="btn-facebook">', unsafe_allow_html=True)
  btn_run_fb = st.button("🟦 رصد فيسبوك", key="btn_run_fb")
  st.markdown("</div>", unsafe_allow_html=True)
  st.markdown('<div class="btn-stop">', unsafe_allow_html=True)
  if st.button("🛑 إيقاف فيسبوك", key="btn_stop_fb"):
    st.session_state.stop_flags["fb"] = True
  st.markdown("</div>", unsafe_allow_html=True)

with c_p3:
  st.markdown('<div class="btn-x">', unsafe_allow_html=True)
  btn_run_x = st.button("⬛ رصد إكس", key="btn_run_x")
  st.markdown("</div>", unsafe_allow_html=True)
  st.markdown('<div class="btn-stop">', unsafe_allow_html=True)
  if st.button("🛑 إيقاف إكس", key="btn_stop_x"):
    st.session_state.stop_flags["x"] = True
  st.markdown("</div>", unsafe_allow_html=True)

with c_p4:
  st.markdown('<div class="btn-youtube">', unsafe_allow_html=True)
  btn_run_yt = st.button("🟥 رصد يوتيوب", key="btn_run_yt")
  st.markdown("</div>", unsafe_allow_html=True)
  st.markdown('<div class="btn-stop">', unsafe_allow_html=True)
  if st.button("🛑 إيقاف يوتيوب", key="btn_stop_yt"):
    st.session_state.stop_flags["yt"] = True
  st.markdown("</div>", unsafe_allow_html=True)

with c_p5:
  st.markdown('<div class="btn-other">', unsafe_allow_html=True)
  btn_run_other = st.button("🟪 رصد أخرى", key="btn_run_other")
  st.markdown("</div>", unsafe_allow_html=True)
  st.markdown('<div class="btn-stop">', unsafe_allow_html=True)
  if st.button("🛑 إيقاف أخرى", key="btn_stop_other"):
    st.session_state.stop_flags["other"] = True
  st.markdown("</div>", unsafe_allow_html=True)

# قسم الرصد المخصص للروابط والقنوات
with st.expander("🎯 الروابط والقنوات المخصصة", expanded=False):
  if "dynamic_targets" not in st.session_state:
    st.session_state.dynamic_targets = load_custom_targets()

  c_add_t, c_save_t = st.columns([1, 1])
  with c_add_t:
    st.markdown('<div class="btn-add">', unsafe_allow_html=True)
    if st.button("➕ إضافة رابط"):
      st.session_state.dynamic_targets.append(
          {"url": "", "platform": "كشف تلقائي من الرابط", "kw": ""}
      )
      save_custom_targets(st.session_state.dynamic_targets)
      st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

  with c_save_t:
    st.markdown('<div class="btn-save">', unsafe_allow_html=True)
    if st.button("💾 حفظ الروابط"):
      save_custom_targets(st.session_state.dynamic_targets)
      st.toast("✅ تم الحفظ.")
    st.markdown("</div>", unsafe_allow_html=True)

  targets_to_run = []
  has_changes = False

  for idx, item in enumerate(st.session_state.dynamic_targets):
    c_u1, c_u2, c_u3, c_u4 = st.columns([4, 2, 3, 1])
    with c_u1:
      new_url = st.text_input(
          f"الرابط #{idx+1}",
          value=item.get("url", ""),
          key=f"t_url_{idx}",
          placeholder="https://youtube.com/@channel أو facebook.com/page",
          label_visibility="collapsed",
      )
      if new_url != item.get("url", ""):
        item["url"] = new_url
        has_changes = True

    with c_u2:
      plat_opts = [
          "كشف تلقائي من الرابط",
          "YouTube",
          "Facebook",
          "X (Twitter)",
          "LinkedIn",
          "TikTok",
          "مواقع وصحف",
      ]
      cur_p = item.get("platform", "كشف تلقائي من الرابط")
      p_idx = plat_opts.index(cur_p) if cur_p in plat_opts else 0
      new_plat = st.selectbox(
          f"المنصة #{idx+1}",
          options=plat_opts,
          index=p_idx,
          key=f"t_plat_{idx}",
          label_visibility="collapsed",
      )
      if new_plat != item.get("platform", ""):
        item["platform"] = new_plat
        has_changes = True

    with c_u3:
      new_kw = st.text_input(
          f"كلمة #{idx+1}",
          value=item.get("kw", ""),
          key=f"t_kw_{idx}",
          placeholder="كلمة مفتاحية (اختياري)",
          label_visibility="collapsed",
      )
      if new_kw != item.get("kw", ""):
        item["kw"] = new_kw
        has_changes = True

    with c_u4:
      st.markdown('<div class="btn-del">', unsafe_allow_html=True)
      if st.button("❌", key=f"del_{idx}"):
        st.session_state.dynamic_targets.pop(idx)
        save_custom_targets(st.session_state.dynamic_targets)
        st.rerun()
      st.markdown("</div>", unsafe_allow_html=True)

    if item["url"].strip():
      targets_to_run.append(item)

  if has_changes:
    save_custom_targets(st.session_state.dynamic_targets)

  c_run_tgt, c_stop_tgt = st.columns([3, 1])
  with c_run_tgt:
    st.markdown('<div class="btn-custom-target">', unsafe_allow_html=True)
    run_all_custom_btn = st.button(
        f"🎯 رصد الروابط المخصصة ({len(targets_to_run)})",
        key="btn_run_custom_main",
    )
    st.markdown("</div>", unsafe_allow_html=True)

  with c_stop_tgt:
    st.markdown('<div class="btn-stop">', unsafe_allow_html=True)
    if st.button("🛑 إيقاف المخصص", key="btn_stop_custom"):
      st.session_state.stop_flags["custom"] = True
    st.markdown("</div>", unsafe_allow_html=True)


def show_radar():
  radar_placeholder.markdown(
      """
      <div class="radar-wrapper">
          <div class="radar-screen">
              <div class="radar-sweep-arm"></div>
              <div class="radar-target-dot"></div>
          </div>
      </div>
      """,
      unsafe_allow_html=True,
  )


def show_done(count):
  radar_placeholder.empty()
  done_placeholder.markdown(
      f'<div style="text-align:center;"><div class="done-badge">✨ تـم / DONE (+{count}) ✨</div></div>',
      unsafe_allow_html=True,
  )


# تنفيذ الرصد الشامل
if btn_run_all:
  if not gemini_api_key:
    st.error("⚠️ أدخل مفتاح Gemini API أولاً.")
  else:
    st.session_state.stop_flags["all"] = False
    custom_in = keywords_input.strip()
    stop_fn = lambda: st.session_state.stop_flags.get("all", False)

    show_radar()
    p_bar = progress_placeholder.progress(0.0)
    raw_items = []

    p_bar.progress(0.2)
    raw_items.extend(
        fetch_moroccan_sites_quick(custom_in, max_count=20, stop_check_fn=stop_fn)
    )

    if not stop_fn():
      p_bar.progress(0.4)
      raw_items.extend(
          fetch_youtube_posts_live(custom_in, max_count=10, stop_check_fn=stop_fn)
      )

    if not stop_fn():
      p_bar.progress(0.6)
      raw_items.extend(
          fetch_facebook_posts_live(custom_in, max_count=8, stop_check_fn=stop_fn)
      )

    if not stop_fn():
      p_bar.progress(0.8)
      raw_items.extend(
          fetch_x_posts_live(custom_in, max_count=8, stop_check_fn=stop_fn)
      )
      raw_items.extend(
          fetch_other_social_live(custom_in, max_count=6, stop_check_fn=stop_fn)
      )
      targets = load_custom_targets()
      if targets:
        raw_items.extend(
            execute_multi_target_monitor(targets, stop_check_fn=stop_fn)
        )

    if not stop_fn():
      added_count = quick_process_and_save(
          raw_items,
          current_cfg,
          is_target_run=False,
          stop_check_fn=stop_fn,
          progress_cb=lambda f: p_bar.progress(min(0.85 + (f * 0.15), 1.0)),
      )
      p_bar.progress(1.0)
      current_cfg["last_auto_run"] = time.time()
      current_cfg["last_run_time_str"] = datetime.now().strftime(
          "%Y-%m-%d %H:%M:%S"
      )
      save_config(current_cfg)
      show_done(added_count)
    else:
      radar_placeholder.empty()

# تنفيذ رصد المنصات الفردية
if btn_run_press:
  st.session_state.stop_flags["press"] = False
  stop_fn = lambda: st.session_state.stop_flags.get("press", False)
  show_radar()
  items = fetch_moroccan_sites_quick(
      keywords_input.strip(), max_count=20, stop_check_fn=stop_fn
  )
  added = quick_process_and_save(
      items, current_cfg, is_target_run=False, stop_check_fn=stop_fn
  )
  show_done(added)

if btn_run_fb:
  st.session_state.stop_flags["fb"] = False
  stop_fn = lambda: st.session_state.stop_flags.get("fb", False)
  show_radar()
  items = fetch_facebook_posts_live(
      keywords_input.strip(), max_count=12, stop_check_fn=stop_fn
  )
  added = quick_process_and_save(
      items, current_cfg, is_target_run=False, stop_check_fn=stop_fn
  )
  show_done(added)

if btn_run_x:
  st.session_state.stop_flags["x"] = False
  stop_fn = lambda: st.session_state.stop_flags.get("x", False)
  show_radar()
  items = fetch_x_posts_live(
      keywords_input.strip(), max_count=12, stop_check_fn=stop_fn
  )
  added = quick_process_and_save(
      items, current_cfg, is_target_run=False, stop_check_fn=stop_fn
  )
  show_done(added)

if btn_run_yt:
  st.session_state.stop_flags["yt"] = False
  stop_fn = lambda: st.session_state.stop_flags.get("yt", False)
  show_radar()
  items = fetch_youtube_posts_live(
      keywords_input.strip(), max_count=10, stop_check_fn=stop_fn
  )
  added = quick_process_and_save(
      items, current_cfg, is_target_run=False, stop_check_fn=stop_fn
  )
  show_done(added)

if btn_run_other:
  st.session_state.stop_flags["other"] = False
  stop_fn = lambda: st.session_state.stop_flags.get("other", False)
  show_radar()
  items = fetch_other_social_live(
      keywords_input.strip(), max_count=10, stop_check_fn=stop_fn
  )
  added = quick_process_and_save(
      items, current_cfg, is_target_run=False, stop_check_fn=stop_fn
  )
  show_done(added)

if run_all_custom_btn:
  st.session_state.stop_flags["custom"] = False
  stop_fn = lambda: st.session_state.stop_flags.get("custom", False)
  if targets_to_run and gemini_api_key:
    save_custom_targets(st.session_state.dynamic_targets)
    show_radar()
    t_items = execute_multi_target_monitor(
        targets_to_run, stop_check_fn=stop_fn
    )
    added_t = quick_process_and_save(
        t_items, current_cfg, is_target_run=True, stop_check_fn=stop_fn
    )
    show_done(added_t)

# عرض النتائج
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute(
    "SELECT platform, source, title, link, date_published, pub_timestamp,"
    " snippet, ai_analysis, is_target_profile, fetched_at FROM items ORDER BY"
    " pub_timestamp DESC, fetched_at DESC"
)
all_db_records = c.fetchall()
conn.close()

now_utc_ts = datetime.now(timezone.utc).timestamp()
twenty_four_hours_ago = now_utc_ts - 86400

live_records = [r for r in all_db_records if r[5] >= twenty_four_hours_ago]
archive_records = [r for r in all_db_records if r[5] < twenty_four_hours_ago]

live_news = [r for r in live_records if r[0] == "مواقع وصحف"]
live_yt = [r for r in live_records if r[0] == "YouTube"]
live_fb = [r for r in live_records if r[0] == "Facebook"]
live_x = [r for r in live_records if r[0] == "X (Twitter)"]
live_other = [
    r for r in live_records if r[0] in ["LinkedIn", "TikTok", "Instagram"]
]


def get_platform_design(plat, is_t):
  if is_t:
    return "border-target", "badge-target", "مخصص", "#10b981"
  p = plat.lower()
  if "facebook" in p or "فيسبوك" in p:
    return "border-facebook", "badge-facebook", "فيسبوك", "#1877f2"
  elif "x" in p or "twitter" in p or "تويتر" in p or "إكس" in p:
    return "border-x", "badge-x", "إكس", "#f8fafc"
  elif "youtube" in p or "يوتيوب" in p:
    return "border-youtube", "badge-youtube", "يوتيوب", "#ef4444"
  elif "instagram" in p or "إنستغرام" in p:
    return "border-instagram", "badge-instagram", "إنستغرام", "#ec4899"
  elif "tiktok" in p or "تيك توك" in p:
    return "border-tiktok", "badge-tiktok", "تيك توك", "#06b6d4"
  elif "linkedin" in p or "لينكد" in p:
    return "border-linkedin", "badge-linkedin", "لينكدإن", "#0284c7"
  return "border-news", "badge-news", "صحافة", "#3b82f6"


def render_cards(items_list, is_archive_view=False):
  if items_list:
    for idx, row in enumerate(items_list, 1):
      plat, src, title, link, d_pub, _, snip, ai_note, is_t, f_at = row
      border_cls, badge_cls, p_label, btn_color = get_platform_design(
          plat, is_t
      )
      if is_archive_view:
        border_cls = "border-archive"
        badge_cls = "badge-archive"

      is_target_tag = (
          " <span class='badge badge-target'>⭐ مخصص</span>" if is_t else ""
      )

      st.markdown(
          f"""
            <div class="result-card {border_cls}">
                <h4>#{idx} <span class="badge {badge_cls}">{p_label}</span>{is_target_tag} {title}</h4>
                <div class="meta-line">
                    🏛️ {src} &nbsp;|&nbsp; 📅 <span style="font-weight: bold; color: {btn_color};">{d_pub}</span> &nbsp;|&nbsp; ⏱️ {f_at}
                </div>
                <div class="desc-box">{snip}</div>
                <div class="ai-box">💡 {ai_note}</div>
                <p><a href="{link}" target="_blank" class="action-btn" style="background-color: {btn_color};">🔗 فتح المصدر ➔</a></p>
            </div>
            """,
          unsafe_allow_html=True,
      )
  else:
    st.info("لا توجد بيانات مسجلة.")


tab_live_all, tab_press, tab_facebook, tab_x_plat, tab_youtube, tab_others, tab_archive_all = st.tabs([
    f"الكل ({len(live_records)})",
    f"الصحف ({len(live_news)})",
    f"فيسبوك ({len(live_fb)})",
    f"إكس ({len(live_x)})",
    f"يوتيوب ({len(live_yt)})",
    f"أخرى ({len(live_other)})",
    f"الأرشيف ({len(archive_records)})",
])

with tab_live_all:
  render_cards(live_records)

with tab_press:
  render_cards(live_news)

with tab_facebook:
  render_cards(live_fb)

with tab_x_plat:
  render_cards(live_x)

with tab_youtube:
  render_cards(live_yt)

with tab_others:
  render_cards(live_other)

with tab_archive_all:
  search_archive = st.text_input(
      "بحث في الأرشيف",
      placeholder="🔍 بحث في الأرشيف...",
      label_visibility="collapsed",
  )
  if search_archive.strip():
    q_s = search_archive.strip().lower()
    filtered_archive = [
        r
        for r in archive_records
        if q_s in r[2].lower() or q_s in r[6].lower() or q_s in r[7].lower()
    ]
    render_cards(filtered_archive, is_archive_view=True)
  else:
    render_cards(archive_records, is_archive_view=True)
