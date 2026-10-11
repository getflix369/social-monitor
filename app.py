from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import os
import re
import sqlite3
import time
import urllib.parse
import xml.etree.ElementTree as ET
from duckduckgo_search import DDGS
import google.generativeai as genai
import requests
import streamlit as st

st.set_page_config(
    page_title="المرصد الوطني للعدالة والقضاء بالمغرب",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    html, body, [class*="css"], .stApp {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .stTextInput input, .stTextArea textarea, .stSelectbox div, .stMultiSelect div {
        direction: rtl !important;
        text-align: right !important;
    }
    button[data-baseweb="tab"] {
        font-size: 1.05rem !important;
        font-weight: bold !important;
        direction: rtl !important;
        padding: 10px 18px !important;
    }
    div[data-baseweb="tab-list"] {
        direction: rtl !important;
        justify-content: flex-start !important;
        gap: 8px !important;
    }
    .result-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-right: 6px solid #1e3a8a;
        padding: 18px;
        border-radius: 12px;
        margin-bottom: 16px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.04);
    }
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85em;
        margin-left: 8px;
        color: white;
    }
    .badge-site { background-color: #1e3a8a; }
    .badge-yt { background-color: #dc2626; }
    .badge-fb { background-color: #1877f2; }
    .badge-x { background-color: #000000; }
    .badge-insta { background-color: #e1306c; }
    .badge-tiktok { background-color: #111111; }
    .badge-target { background-color: #059669; }
    .meta-line { color: #64748b; font-size: 0.88em; margin: 8px 0; }
    .desc-box {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 12px;
        border-radius: 8px;
        font-size: 0.95em;
        color: #1e293b;
        line-height: 1.6;
        margin-bottom: 12px;
    }
    .ai-box {
        background-color: #f0fdf4;
        border: 1px solid #bbf7d0;
        padding: 10px 14px;
        border-radius: 8px;
        color: #166534;
        font-size: 0.92em;
        margin-bottom: 10px;
    }
    .action-btn {
        display: inline-block;
        padding: 8px 16px;
        border-radius: 6px;
        background-color: #1e3a8a;
        color: white !important;
        text-decoration: none !important;
        font-weight: bold;
        font-size: 0.9em;
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

ARCHIVE_JSON_FILE = "articles_archive.json"
TARGET_PROFILES_FILE = "monitored_profiles.json"
CONFIG_FILE = "credentials.json"


# 1. نظام حفظ واسترجاع الإعدادات الدائم
def load_config():
  cfg = {
      "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
      "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
      "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
      "auto_refresh": False,
      "time_range": "آخر 7 أيام (هذا الأسبوع)",
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
        cfg.update(json.load(f))
    except Exception:
      pass
  return cfg


def save_config(cfg_dict):
  try:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
      json.dump(cfg_dict, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


current_cfg = load_config()


# 2. إدارة قائمة القنوات والصفحات المستهدفة
def load_target_profiles():
  default_targets = [
      {
          "name": "المجلس الأعلى للسلطة القضائية (CSPJ)",
          "platform": "YouTube",
          "query": "site:youtube.com/@CSPJ_Maroc OR site:youtube.com 'المجلس الأعلى للسلطة القضائية'",
          "enabled": True,
      },
      {
          "name": "المجلس الأعلى للسلطة القضائية (فيسبوك)",
          "platform": "Facebook",
          "query": "site:facebook.com/cspj.ma OR site:facebook.com 'المجلس الأعلى للسلطة القضائية'",
          "enabled": True,
      },
      {
          "name": "وزارة العدل المغربية",
          "platform": "Facebook",
          "query": "site:facebook.com/justice.gov.ma OR site:facebook.com 'وزارة العدل المغربية'",
          "enabled": True,
      },
      {
          "name": "رئاسة النيابة العامة بالمغرب",
          "platform": "Facebook",
          "query": "site:facebook.com/pmp.ma OR site:facebook.com 'رئاسة النيابة العامة بالمغرب'",
          "enabled": True,
      },
      {
          "name": "محكمة النقض المغربية",
          "platform": "X (Twitter)",
          "query": "(site:x.com OR site:twitter.com) 'محكمة النقض بالمغرب'",
          "enabled": True,
      },
      {
          "name": "نادي قضاة المغرب",
          "platform": "Facebook",
          "query": "site:facebook.com 'نادي قضاة المغرب'",
          "enabled": True,
      },
  ]
  if os.path.exists(TARGET_PROFILES_FILE):
    try:
      with open(TARGET_PROFILES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      pass
  return default_targets


def save_target_profiles(profiles_list):
  try:
    with open(TARGET_PROFILES_FILE, "w", encoding="utf-8") as f:
      json.dump(profiles_list, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


# 3. تهيئة قاعدة البيانات المحلية
def init_db():
  conn = sqlite3.connect("morocco_justice_hub.db")
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
  try:
    c.execute(
        "ALTER TABLE items ADD COLUMN is_target_profile INTEGER DEFAULT 0"
    )
  except Exception:
    pass
  conn.commit()

  if os.path.exists(ARCHIVE_JSON_FILE):
    try:
      with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
        archived = json.load(f)
        for it in archived:
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


init_db()


def export_db_to_archive_json():
  try:
    conn = sqlite3.connect("morocco_justice_hub.db")
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
    with open(ARCHIVE_JSON_FILE, "w", encoding="utf-8") as f:
      json.dump(items_list, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


# الشريط الجانبي
with st.sidebar:
  st.header("⚙️ إعدادات المنظومة")

  gemini_api_key = st.text_input(
      "مفتاح Gemini API:",
      value=current_cfg.get("gemini_api_key", ""),
      type="password",
  )
  telegram_token = st.text_input(
      "رمز بوت تيليجرام (Token):",
      value=current_cfg.get("telegram_bot_token", ""),
      type="password",
  )
  telegram_chat_id = st.text_input(
      "معرّف تيليجرام (Chat ID):",
      value=current_cfg.get("telegram_chat_id", ""),
  )

  if st.button("💾 حفظ المفاتيح والإعدادات"):
    current_cfg["gemini_api_key"] = gemini_api_key
    current_cfg["telegram_bot_token"] = telegram_token
    current_cfg["telegram_chat_id"] = telegram_chat_id
    save_config(current_cfg)
    st.toast("✅ تم حفظ الإعدادات بنجاح.")

  model_choice = st.selectbox(
      "نموذج الذكاء الاصطناعي:",
      options=[
          "gemini-3.5-flash-lite",
          "gemini-1.5-flash",
          "gemini-2.0-flash",
      ],
      index=0,
  )

  if gemini_api_key:
    st.markdown(
        f'<div class="status-pill status-pill-ok">🟢 المفتاح نشط ومحفوظ'
        f" ({model_choice})</div>",
        unsafe_allow_html=True,
    )
  else:
    st.markdown(
        '<div class="status-pill status-pill-err">🔴 المفتاح غير مسجل</div>',
        unsafe_allow_html=True,
    )

  st.divider()
  st.header("⏱️ الجدولة والرصد الدوري")
  auto_refresh_enabled = st.checkbox(
      "🔄 تفعيل الرصد التلقائي كل 15 دقيقة (دائم)",
      value=current_cfg.get("auto_refresh", False),
      help=(
          "عند تفعيل هذا الخيار، سيحفظ التطبيق الحالة تلقائياً ويعيد الرصد كل"
          " ربع ساعة"
      ),
  )
  if auto_refresh_enabled != current_cfg.get("auto_refresh", False):
    current_cfg["auto_refresh"] = auto_refresh_enabled
    save_config(current_cfg)

  time_range = st.selectbox(
      "النطاق الزمني للنشر:",
      options=[
          "آخر 24 ساعة (اليوم فقط)",
          "آخر 7 أيام (هذا الأسبوع)",
          "آخر 30 يوماً (هذا الشهر)",
          "جميع الأوقات",
      ],
      index=1,
  )

  fetch_limit = st.slider(
      "الحد الأقصى لكل منصة:", min_value=10, max_value=80, value=25, step=5
  )
  send_telegram = st.checkbox("إرسال تنبيه إلى Telegram فورياً", value=True)

  st.divider()
  st.header("💾 الأرشيف الاحتياطي")
  if os.path.exists(ARCHIVE_JSON_FILE):
    with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
      st.download_button(
          "📥 تنزيل الأرشيف كاملاً (JSON)",
          f.read(),
          file_name="morocco_justice_backup.json",
          mime="application/json",
      )

st.title("⚖️ المرصد الوطني للعدالة والقضاء بالمغرب")
st.write(
    "رصد شامل للمواقع والمنصات، مع نظام **التتبع المباشر للقنوات والصفحات"
    " الحصرية** وتلخيص محتواها كاملاً."
)

col1, col2 = st.columns(2)
with col1:
  target_domain = st.text_input(
      "🎯 نطاق التقييم والفلترة:",
      value="شؤون القضاء والعدالة والمحاكم والنيابة العامة بالمملكة المغربية حصراً",
  )
with col2:
  keywords_input = st.text_input(
      "🔑 استعلام البحث الرئيسي (اكتب كلمتك هنا):",
      value="المجلس الأعلى للسلطة القضائية",
      help="الكلمة المفتاحية المعتمدة للبحث في كافة المصادر",
  )

col_btn1, col_btn2 = st.columns([1, 1])
with col_btn1:
  start_general_btn = st.button(
      "🚀 بدء رصد الكلمة المفتاحية عبر كل المنصات", type="primary"
  )
with col_btn2:
  start_targets_btn = st.button(
      "🎯 رصد وتحديث القنوات والصفحات المستهدفة الآن"
  )


# دالة معاملات الوقت
def get_time_params(time_mode):
  if time_mode == "آخر 24 ساعة (اليوم فقط)":
    return 30, "when:1d", "d"
  elif time_mode == "آخر 7 أيام (هذا الأسبوع)":
    return 180, "when:7d", "w"
  elif time_mode == "آخر 30 يوماً (هذا الشهر)":
    return 750, "when:30d", "m"
  return 999999, "", None


# 1. محرك رصد القنوات والصفحات الحصرية المستهدفة بملخص شامل
def fetch_targeted_profiles_content(profiles, time_mode):
  results = []
  seen = set()
  max_h, time_op, ddg_time = get_time_params(time_mode)
  now = datetime.now(timezone.utc)
  headers = {"User-Agent": "Mozilla/5.0"}

  for prof in profiles:
    if not prof.get("enabled", True):
      continue
    name = prof.get("name", "صفحة مستهدفة")
    plat = prof.get("platform", "عام")
    query = f"{prof.get('query')} {time_op}".strip()

    try:
      enc = urllib.parse.quote(query)
      url = (
          f"https://news.google.com/rss/search?q={enc}&hl=ar&gl=MA&ceid=MA:ar"
      )
      resp = requests.get(url, headers=headers, timeout=8)
      root = ET.fromstring(resp.content)
      for item in root.findall(".//item")[:4]:
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

        ts = 0.0
        disp_date = pdate
        is_valid = True
        if pdate:
          try:
            dt = parsedate_to_datetime(pdate)
            ts = dt.timestamp()
            disp_date = dt.strftime("%Y-%m-%d %H:%M")
            if (now - dt).total_seconds() / 3600.0 > max_h:
              is_valid = False
          except Exception:
            pass
        if not is_valid:
          continue

        clean_d = re.sub(r"<[^>]+>", "", desc)
        results.append({
            "platform": plat,
            "source": f"⭐ {name}",
            "title": title,
            "link": link,
            "date": disp_date,
            "timestamp": ts,
            "snippet": clean_d or f"منشور حصري صادر عن {name}",
            "is_target": 1,
        })
        seen.add(link)
    except Exception:
      pass

  return results


# 2. محركات الرصد العامة للكلمة المفتاحية
def fetch_moroccan_sites(user_kw, time_mode, max_count=35):
  results = []
  seen = set()
  max_h, time_op, _ = get_time_params(time_mode)
  now = datetime.now(timezone.utc)
  headers = {"User-Agent": "Mozilla/5.0"}

  queries = [
      f'"{user_kw}" (المغرب OR مغربية) {time_op}'.strip(),
      (
          f'"{user_kw}" (site:.ma OR site:hespress.com OR site:akhbarona.com OR'
          " site:kech24.com OR site:agadir24.info OR site:madar21.com OR"
          " site:alayam24.com OR site:assabah.ma OR site:thevoice.ma OR"
          " site:nadorcity.com OR site:goud.ma OR site:al3omk.com OR"
          f" site:alyaoum24.com OR site:rue20.com) {time_op}".strip()
      ),
  ]

  for q in queries:
    if len(results) >= max_count:
      break
    try:
      enc = urllib.parse.quote(q)
      url = (
          f"https://news.google.com/rss/search?q={enc}&hl=ar&gl=MA&ceid=MA:ar"
      )
      resp = requests.get(url, headers=headers, timeout=8)
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

        ts = 0.0
        disp_date = pdate
        is_valid = True
        if pdate:
          try:
            dt = parsedate_to_datetime(pdate)
            ts = dt.timestamp()
            disp_date = dt.strftime("%Y-%m-%d %H:%M")
            if (now - dt).total_seconds() / 3600.0 > max_h:
              is_valid = False
          except Exception:
            pass
        if not is_valid:
          continue

        clean_d = re.sub(r"<[^>]+>", "", desc)
        results.append({
            "platform": "مواقع وصحف",
            "source": src,
            "title": title,
            "link": link,
            "date": disp_date,
            "timestamp": ts,
            "snippet": clean_d,
            "is_target": 0,
        })
        seen.add(link)
        if len(results) >= max_count:
          break
    except Exception:
      pass

  return results


def fetch_youtube_posts(user_kw, time_mode, max_count=15):
  results = []
  seen = set()
  max_h, time_op, _ = get_time_params(time_mode)
  now = datetime.now(timezone.utc)
  headers = {"User-Agent": "Mozilla/5.0"}

  query = f'site:youtube.com "{user_kw}" {time_op}'.strip()
  try:
    enc = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={enc}&hl=ar&gl=MA&ceid=MA:ar"
    resp = requests.get(url, headers=headers, timeout=8)
    root = ET.fromstring(resp.content)
    for item in root.findall(".//item"):
      link = item.find("link").text if item.find("link") is not None else ""
      if not link or link in seen or "youtube.com" not in link:
        continue
      title = item.find("title").text if item.find("title") is not None else ""
      pdate = (
          item.find("pubDate").text if item.find("pubDate") is not None else ""
      )
      desc = (
          item.find("description").text
          if item.find("description") is not None
          else ""
      )

      ts = 0.0
      disp_date = pdate
      is_valid = True
      if pdate:
        try:
          dt = parsedate_to_datetime(pdate)
          ts = dt.timestamp()
          disp_date = dt.strftime("%Y-%m-%d %H:%M")
          if (now - dt).total_seconds() / 3600.0 > max_h:
            is_valid = False
        except Exception:
          pass
      if not is_valid:
        continue

      results.append({
          "platform": "YouTube",
          "source": "YouTube",
          "title": title.replace(" - YouTube", ""),
          "link": link,
          "date": disp_date,
          "timestamp": ts,
          "snippet": (
              re.sub(r"<[^>]+>", "", desc)
              or f"فيديو يوتيوب حول موضوع: {user_kw}"
          ),
          "is_target": 0,
      })
      seen.add(link)
      if len(results) >= max_count:
        break
  except Exception:
    pass

  return results


def fetch_social_network_posts(user_kw, platform_name, time_mode, max_count=15):
  results = []
  seen = set()
  max_h, time_op, _ = get_time_params(time_mode)
  now = datetime.now(timezone.utc)
  headers = {"User-Agent": "Mozilla/5.0"}

  domain_map = {
      "Facebook": "site:facebook.com",
      "X (Twitter)": "(site:x.com OR site:twitter.com)",
      "TikTok": "site:tiktok.com",
      "Instagram": "site:instagram.com",
      "LinkedIn": "site:linkedin.com",
  }
  target_site = domain_map.get(platform_name, "")
  q = f'{target_site} "{user_kw}" {time_op}'.strip()

  try:
    enc = urllib.parse.quote(q)
    url = f"https://news.google.com/rss/search?q={enc}&hl=ar&gl=MA&ceid=MA:ar"
    resp = requests.get(url, headers=headers, timeout=8)
    root = ET.fromstring(resp.content)
    for item in root.findall(".//item"):
      link = item.find("link").text if item.find("link") is not None else ""
      if not link or link in seen:
        continue
      title = item.find("title").text if item.find("title") is not None else ""
      desc = (
          item.find("description").text
          if item.find("description") is not None
          else ""
      )
      pdate = (
          item.find("pubDate").text if item.find("pubDate") is not None else ""
      )

      ts = 0.0
      disp_date = pdate
      is_valid = True
      if pdate:
        try:
          dt = parsedate_to_datetime(pdate)
          ts = dt.timestamp()
          disp_date = dt.strftime("%Y-%m-%d %H:%M")
          if (now - dt).total_seconds() / 3600.0 > max_h:
            is_valid = False
        except Exception:
          pass
      if not is_valid:
        continue

      results.append({
          "platform": platform_name,
          "source": f"منشور {platform_name}",
          "title": title,
          "link": link,
          "date": disp_date,
          "timestamp": ts,
          "snippet": (
              re.sub(r"<[^>]+>", "", desc)
              or f"منشور على {platform_name} حول {user_kw}"
          ),
          "is_target": 0,
      })
      seen.add(link)
      if len(results) >= max_count:
        break
  except Exception:
    pass

  return results


# 3. التحليل الذكي وتوليد الملخص الوافي بواسطة Gemini
def generate_ai_executive_summary(
    title, snippet, user_kw, domain, key, model_name
):
  try:
    genai.configure(api_key=key)
    m = genai.GenerativeModel(model_name)
    prompt = f"""
أنت مستشار قضائي وإعلامي ومحلل محتوى مغربي.
الموضوع الأساسي المطلوب: {user_kw}
المجال القانوني: {domain}

المادة المرصودة:
العنوان: {title}
المحتوى/المقتطف: {snippet}

المطلوب بدقة:
1. هل هذا الخبر أو المنشور يخص المغرب ويتناول الموضوع المطلوب ({user_kw}) أو الشأن القضائي/القانوني المرتبط به؟ إذا كان خبراً خارج السياق أجب بـ NO فقط.
2. إذا كان مطابقاً، أجب بالصيغة التالية تماماً:
YES: [اكتب ملخصاً إخبارياً تنفيذياً وافياً في 2 إلى 3 جمل مركزة، يوضح بدقة ما ورد في المنشور/الفيديو، مع إبراز القرارات أو الوقائع القانونية والموقف الصادر].
"""
    res = m.generate_content(prompt)
    txt = res.text.strip()
    if txt.startswith("YES"):
      return True, txt.replace("YES:", "").replace("YES", "").strip()
    return False, ""
  except Exception:
    return True, f"مادة إخبارية مطابقة للكلمة المفتاحية: {user_kw}"


# دالة إرسال التنبيه المفصل إلى Telegram
def send_rich_telegram_alert(token, chat_id, item):
  tag = "⭐ [رصد حصري من صفحة متابعة]" if item.get("is_target") else "⚖️ [رصد جديد]"
  msg = (
      f"{tag}\n\n"
      f"🌐 *المنصة:* {item['platform']}\n"
      f"🏛️ *المصدر / الحساب:* `{item['source']}`\n"
      f"📅 *تاريخ النشر:* {item['date']}\n"
      f"📌 *العنوان:* {item['title']}\n\n"
      f"📝 *مقتطف المضمون:*\n_{item['snippet'][:250]}..._\n\n"
      f"💡 *الملخص والتحليل الذكي (Gemini):*\n{item['ai_analysis']}\n\n"
      f"🔗 *رابط المشاهدة / القراءة كاملاً:*\n{item['link']}"
  )
  try:
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
        timeout=8,
    )
  except Exception:
    pass


# دورة المعالجة والحفظ في قاعدة البيانات
def process_and_save_items(items_list, user_kw):
  conn = sqlite3.connect("morocco_justice_hub.db")
  c = conn.cursor()
  new_count = 0

  for it in items_list:
    c.execute("SELECT link FROM items WHERE link = ?", (it["link"],))
    if c.fetchone():
      continue

    is_valid, summary = generate_ai_executive_summary(
        it["title"],
        it["snippet"],
        user_kw,
        target_domain,
        gemini_api_key,
        model_choice,
    )
    if is_valid:
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

      if send_telegram and telegram_token and telegram_chat_id:
        send_rich_telegram_alert(telegram_token, telegram_chat_id, it)

  conn.close()
  export_db_to_archive_json()
  return new_count


# تشغيل الرصد العام للكلمة المفتاحية
if start_general_btn:
  clean_kw = keywords_input.strip()
  if not clean_kw:
    st.warning("⚠️ يرجى إدخال الكلمة المفتاحية أولاً.")
  elif not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API في الشريط الجانبي.")
  else:
    with st.spinner(f"جارٍ الرصد الشامل للكلمة: '{clean_kw}' عبر كل المنصات..."):
      raw_all = []
      raw_all.extend(
          fetch_moroccan_sites(clean_kw, time_range, max_count=fetch_limit)
      )
      raw_all.extend(fetch_youtube_posts(clean_kw, time_range, max_count=15))
      raw_all.extend(
          fetch_social_network_posts(
              clean_kw, "Facebook", time_range, max_count=10
          )
      )
      raw_all.extend(
          fetch_social_network_posts(
              clean_kw, "X (Twitter)", time_range, max_count=10
          )
      )
      raw_all.extend(
          fetch_social_network_posts(
              clean_kw, "TikTok", time_range, max_count=10
          )
      )
      raw_all.extend(
          fetch_social_network_posts(
              clean_kw, "Instagram", time_range, max_count=10
          )
      )
      raw_all.extend(
          fetch_social_network_posts(
              clean_kw, "LinkedIn", time_range, max_count=10
          )
      )

      added = process_and_save_items(raw_all, clean_kw)
      st.success(
          f"✅ اكتمل الرصد! تم فحص {len(raw_all)} مادة، وإضافة {added} خبراً"
          f" ومنشوراً جديداً يطابق الكلمة '{clean_kw}'."
      )

# تشغيل رصد القنوات والصفحات المستهدفة
if start_targets_btn:
  if not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API أولاً.")
  else:
    with st.spinner(
        "جارٍ الفحص اللحظي للقنوات والصفحات المستهدفة واستخراج الملخصات..."
    ):
      targets = load_target_profiles()
      target_items = fetch_targeted_profiles_content(targets, time_range)
      added_t = process_and_save_items(
          target_items, keywords_input.strip() or "القضاء والعدالة بالمغرب"
      )
      st.success(
          f"🎯 اكتمل فحص الصفحات المستهدفة! تم رصد {len(target_items)} مادة"
          f" وتلخيصها، وإضافة {added_t} منشوراً حصرياً جديداً."
      )

# واجهة العرض والتبويبات المتقدمة
conn = sqlite3.connect("morocco_justice_hub.db")
c = conn.cursor()
c.execute(
    "SELECT platform, source, title, link, date_published, snippet,"
    " ai_analysis, is_target_profile, fetched_at FROM items ORDER BY"
    " pub_timestamp DESC, fetched_at DESC LIMIT 300"
)
all_records = c.fetchall()
conn.close()

target_records = [r for r in all_records if r[7] == 1]
news_items = [r for r in all_records if r[0] == "مواقع وصحف" and r[7] == 0]
yt_items = [r for r in all_records if r[0] == "YouTube" and r[7] == 0]
fb_items = [r for r in all_records if r[0] == "Facebook" and r[7] == 0]
x_items = [r for r in all_records if r[0] == "X (Twitter)" and r[7] == 0]
other_social = [
    r
    for r in all_records
    if r[0] in ["LinkedIn", "TikTok", "Instagram"] and r[7] == 0
]

tab_targets, tab_news, tab_fb, tab_x, tab_yt, tab_other, tab_manage = st.tabs([
    f"⭐ قنوات وصفحات تحت المجهر ({len(target_records)})",
    f"📰 الصحف والمواقع ({len(news_items)})",
    f"🟦 فيسبوك ({len(fb_items)})",
    f"⬛ منصة إكس ({len(x_items)})",
    f"📺 يوتيوب ({len(yt_items)})",
    f"🟪 لينكد إن وتيك توك ({len(other_social)})",
    "⚙️ إدارة الصفحات المستهدفة",
])


def render_cards(items_list, badge_class, btn_text):
  if items_list:
    for idx, row in enumerate(items_list, 1):
      plat, src, title, link, d_pub, snip, ai_note, is_t, f_at = row
      card_border = (
          "border-right: 6px solid #059669;"
          if is_t
          else "border-right: 6px solid #1e3a8a;"
      )
      st.markdown(
          f"""
            <div class="result-card" style="{card_border}">
                <h4>#{idx} <span class="badge {badge_class}">{plat}</span> {title}</h4>
                <div class="meta-line">
                    🏛️ <b>الجهة / الناشر:</b> {src} &nbsp;|&nbsp; 
                    📅 <b>تاريخ النشر:</b> <span style="font-weight: bold; color:#1e3a8a;">{d_pub}</span> &nbsp;|&nbsp; 
                    ⏱️ <b>وقت الرصد:</b> {f_at}
                </div>
                <div class="desc-box">
                    <b>📝 مضمون المنشور:</b><br>{snip}
                </div>
                <div class="ai-box">
                    <b>💡 ملخص وتقييم الذكاء الاصطناعي (Gemini):</b><br>{ai_note}
                </div>
                <p><a href="{link}" target="_blank" class="action-btn">🔗 {btn_text} ➔</a></p>
            </div>
            """,
          unsafe_allow_html=True,
      )
  else:
    st.info("لا توجد مواد مسجلة في هذا القسم حالياً.")


# 1. تبويب القنوات والصفحات المتابعة حصرياً
with tab_targets:
  st.subheader(
      "⭐ منشورات وفيديوهات القنوات والصفحات المتابعة حصرياً (ملخصة بالكامل)"
  )
  render_cards(
      target_records,
      "badge-target",
      "مشاهدة الفيديو أو فتح المنشور من الصفحة الرسمية",
  )

# 2. تبويب الصحف
with tab_news:
  st.subheader("📰 مقالات وتقارير الصحف والمواقع المغربية")
  render_cards(news_items, "badge-site", "قراءة التقرير بالكامل من المصدر")

# 3. تبويب فيسبوك
with tab_fb:
  st.subheader("🟦 منشورات وتفاعلات فيسبوك (Facebook)")
  render_cards(fb_items, "badge-fb", "فتح المنشور كاملاً على فيسبوك")

# 4. تبويب إكس
with tab_x:
  st.subheader("⬛ تغريدات منصة X (Twitter)")
  render_cards(x_items, "badge-x", "فتح التغريدة على منصة X")

# 5. تبويب يوتيوب
with tab_yt:
  st.subheader("📺 الفيديوهات والتغطيات المرئية الحديثة (YouTube)")
  render_cards(yt_items, "badge-yt", "مشاهدة الفيديو كاملاً على YouTube")

# 6. لينكد إن وتيك توك وإنستغرام
with tab_other:
  st.subheader("🟪 منشورات ومقاطع LinkedIn و TikTok و Instagram")
  render_cards(other_social, "badge-insta", "فتح الرابط على المنصة الأصلية")

# 7. إدارة الصفحات المستهدفة
with tab_manage:
  st.subheader("⚙️ إدارة قائمة القنوات والصفحات المتابعة تلقائياً")
  st.write(
      "يمكنك إضافة أي قناة أو صفحة رسمية لمتابعة كل ما تنشره وتلخيصه فوراً:"
  )

  profiles_data = load_target_profiles()

  # جدول عرض الحسابات المتابعة حالياً
  for i, p in enumerate(profiles_data):
    cp1, cp2, cp3 = st.columns([2, 2, 1])
    with cp1:
      st.markdown(f"**{p['name']}** ({p['platform']})")
    with cp2:
      st.caption(f"`{p['query']}`")
    with cp3:
      p["enabled"] = st.checkbox("مفعّل", value=p.get("enabled", True), key=f"p_{i}")

  if st.button("💾 حفظ تعديلات الحسابات المتابعة"):
    save_target_profiles(profiles_data)
    st.toast("✅ تم تحديث قائمة الحسابات.")

  st.divider()
  st.write("➕ **إضافة صفحة أو قناة جديدة للرصد التلقائي:**")
  with st.form("add_target_form"):
    new_name = st.text_input(
        "اسم الصفحة أو القناة:", placeholder="مثال: نقابة المحامين بالرباط"
    )
    new_plat = st.selectbox(
        "المنصة:",
        options=[
            "YouTube",
            "Facebook",
            "X (Twitter)",
            "LinkedIn",
            "TikTok",
            "موقع/مدونة",
        ],
    )
    new_query = st.text_input(
        "استعلام الرصد أو الرابط:",
        placeholder=(
            "مثال: site:facebook.com/page_id أو site:youtube.com/@channel"
        ),
    )
    submitted = st.form_submit_button("إضافة إلى قائمة المتابعة الحصرية")
    if submitted and new_name and new_query:
      profiles_data.append({
          "name": new_name.strip(),
          "platform": new_plat,
          "query": new_query.strip(),
          "enabled": True,
      })
      save_target_profiles(profiles_data)
      st.success(f"✅ تمت إضافة '{new_name}' بنجاح إلى قائمة الرصد الحصري!")
      st.rerun()

# الرصد التلقائي كل 15 دقيقة (يستمر ولا ينطفئ)
if auto_refresh_enabled:
  time.sleep(900)
  st.rerun()
