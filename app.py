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
    .badge-linkedin { background-color: #0a66c2; }
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
    .custom-monitor-box {
        background-color: #f0fdf4;
        border: 1px solid #86efac;
        padding: 18px;
        border-radius: 12px;
        margin-bottom: 20px;
    }
    @media (max-width: 768px) {
        .stApp { padding: 8px !important; }
        .result-card { padding: 14px !important; }
        h1 { font-size: 1.5rem !important; }
        div[data-baseweb="tab-list"] { overflow-x: auto !important; flex-wrap: nowrap !important; }
        button[data-baseweb="tab"] { font-size: 0.9rem !important; padding: 8px 12px !important; white-space: nowrap !important; }
    }
    </style>
""",
    unsafe_allow_html=True,
)

ARCHIVE_JSON_FILE = "articles_archive.json"
TARGET_PROFILES_FILE = "monitored_profiles.json"
CONFIG_FILE = "credentials.json"


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


# دالة حساب الطابع الزمني الرقمي بدقة
def calculate_precise_timestamp(date_str):
  now = datetime.now(timezone.utc)
  if not date_str:
    return now.timestamp()

  # إذا كان بتنسيق RFC القياسي
  try:
    dt = parsedate_to_datetime(date_str)
    return dt.timestamp()
  except Exception:
    pass

  # إذا كان بصيغة نسبية (ساعة، يوم، دقيقة...)
  s = date_str.lower()
  try:
    num_match = re.search(r"(\d+)", s)
    val = int(num_match.group(1)) if num_match else 1
    if any(w in s for w in ["دقيقة", "دقائق", "minute"]):
      return now.timestamp() - (val * 60)
    elif any(w in s for w in ["ساعة", "ساعات", "hour"]):
      return now.timestamp() - (val * 3600)
    elif any(w in s for w in ["يوم", "يومان", "أيام", "أمس", "day"]):
      days = 1 if "أمس" in s or "يوم" in s and not num_match else val
      return now.timestamp() - (days * 86400)
    elif any(w in s for w in ["أسبوع", "أسبوعين", "أسابيع", "week"]):
      return now.timestamp() - (val * 7 * 86400)
  except Exception:
    pass

  return now.timestamp()


# دالة تحليل وتفكيك أي رابط أو اسم لقناة أو صفحة مستهدفة
def parse_target_source(raw_input, selected_platform):
  raw = raw_input.strip()
  # إزالة البروتوكولات
  clean = re.sub(r"^https?://(www\.)?", "", raw)

  platform = selected_platform
  query = ""
  name = raw

  if "facebook.com" in clean:
    platform = "Facebook"
    m = re.search(r"facebook\.com/([^/?#]+)", clean)
    slug = m.group(1) if m else clean
    query = f"site:facebook.com/{slug}"
    name = f"صفحة فيسبوك: {slug}"
  elif "youtube.com" in clean or "youtu.be" in clean:
    platform = "YouTube"
    m = re.search(r"youtube\.com/(@[^/?#]+)", clean)
    slug = m.group(1) if m else clean
    query = f"site:youtube.com/{slug}" if "@" in clean else f'site:youtube.com "{raw}"'
    name = f"قناة يوتيوب: {slug}"
  elif "x.com" in clean or "twitter.com" in clean:
    platform = "X (Twitter)"
    m = re.search(r"(?:x\.com|twitter\.com)/([^/?#]+)", clean)
    slug = m.group(1) if m else clean
    query = f"site:x.com/{slug} OR site:twitter.com/{slug}"
    name = f"حساب X: @{slug}"
  elif "linkedin.com" in clean:
    platform = "LinkedIn"
    m = re.search(r"linkedin\.com/(?:company|in)/([^/?#]+)", clean)
    slug = m.group(1) if m else clean
    query = f"site:linkedin.com/company/{slug} OR site:linkedin.com/in/{slug}"
    name = f"صفحة LinkedIn: {slug}"
  elif "tiktok.com" in clean:
    platform = "TikTok"
    m = re.search(r"tiktok\.com/@([^/?#]+)", clean)
    slug = m.group(1) if m else clean
    query = f"site:tiktok.com/@{slug}"
    name = f"حساب TikTok: @{slug}"
  else:
    # اسم عادي أو نطاق موقع
    if "." in raw and not " " in raw:
      platform = "مواقع وصحف"
      query = f"site:{raw}"
      name = f"موقع: {raw}"
    else:
      domain_map = {
          "Facebook": "site:facebook.com",
          "YouTube": "site:youtube.com",
          "X (Twitter)": "(site:x.com OR site:twitter.com)",
          "LinkedIn": "site:linkedin.com",
          "TikTok": "site:tiktok.com",
          "مواقع وصحف": "site:.ma",
      }
      site_d = domain_map.get(selected_platform, "")
      query = f'{site_d} "{raw}"'
      name = f"{selected_platform}: {raw}"

  return platform, name, query


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
      "🔄 تفعيل الرصد الدوري التلقائي (كل 15 دقيقة)",
      value=current_cfg.get("auto_refresh", False),
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
    "رصد شامل للمواقع والمنصات، مع ميزة **الرصد المخصص لصفحة أو قناة معينة**"
    " وعرض النتائج مرتبة من **الأحدث إلى الأقدم أولاً** عبر كافة المصادر."
)

# ==========================================
# 1. صندوق ميزة الرصد المخصص لصفحة أو قناة معينة
# ==========================================
st.markdown(
    '<div class="custom-monitor-box"><h4>🎯 ميزة الرصد المخصص: تتبع صفحة أو'
    " قناة محددة بالرابط أو الاسم</h4><p style='color:#166534; font-size:0.9em;'"
    ">ضع رابط أي صفحة (Facebook, YouTube, X, LinkedIn, TikTok, أو موقع إخباري)"
    " أو اسمها لجلب ما تنشره وتلخيصه حصراً:</p></div>",
    unsafe_allow_html=True,
)

c_t1, c_t2, c_t3 = st.columns([3, 2, 2])
with c_t1:
  custom_target_input = st.text_input(
      "رابط الصفحة/القناة أو اسمها:",
      value="https://www.facebook.com/cspj.ma",
      placeholder="مثال: https://www.facebook.com/page_name أو @channel",
  )
with c_t2:
  custom_target_platform = st.selectbox(
      "المنصة المستهدفة:",
      options=[
          "كشف تلقائي من الرابط",
          "Facebook",
          "YouTube",
          "X (Twitter)",
          "LinkedIn",
          "TikTok",
          "مواقع وصحف",
      ],
      index=0,
  )
with c_t3:
  custom_target_kw = st.text_input(
      "كلمة مفتاحية للحصر داخل الصفحة (اختياري):",
      value="",
      placeholder="اتركه فارغاً لجلب كل ما تنشره الصفحة",
  )

col_run_t1, col_run_t2 = st.columns([2, 1])
with col_run_t1:
  run_custom_target_btn = st.button(
      "🎯 تشغيل الرصد المخصص لهذه الصفحة/القناة الآن", type="primary"
  )
with col_run_t2:
  save_to_permanent = st.checkbox(
      "💾 حفظ هذه الصفحة في قائمة المتابعة الدائمة", value=False
  )

st.divider()

# ==========================================
# 2. حقول الرصد العام للمرصد
# ==========================================
st.markdown("### 🌐 الرصد العام الشامل للكلمة المفتاحية:")
col_g1, col_g2 = st.columns(2)
with col_g1:
  target_domain = st.text_input(
      "🎯 نطاق التقييم والفلترة:",
      value="شؤون القضاء والعدالة والمحاكم والنيابة العامة بالمملكة المغربية حصراً",
  )
with col_g2:
  keywords_input = st.text_input(
      "🔑 استعلام البحث العام (الكلمة المفتاحية المعتمدة):",
      value="المجلس الأعلى للسلطة القضائية",
  )

start_general_btn = st.button("🚀 بدء الرصد العام للكلمة عبر كافة المنصات")


# دالة معاملات الوقت
def get_time_params(time_mode):
  if time_mode == "آخر 24 ساعة (اليوم فقط)":
    return 30, "when:1d", "d"
  elif time_mode == "آخر 7 أيام (هذا الأسبوع)":
    return 180, "when:7d", "w"
  elif time_mode == "آخر 30 يوماً (هذا الشهر)":
    return 750, "when:30d", "m"
  return 999999, "", None


# تنفيذ الرصد المخصص لصفحة أو قناة معينة
def execute_specific_target_monitor(
    target_raw, platform_choice, sub_kw, time_mode
):
  auto_p, disp_name, query_str = parse_target_source(
      target_raw,
      "Facebook"
      if platform_choice == "كشف تلقائي من الرابط"
      else platform_choice,
  )
  final_platform = (
      auto_p if platform_choice == "كشف تلقائي من الرابط" else platform_choice
  )

  max_h, time_op, _ = get_time_params(time_mode)
  now = datetime.now(timezone.utc)
  headers = {"User-Agent": "Mozilla/5.0"}

  full_q = f"{query_str}"
  if sub_kw.strip():
    full_q += f' "{sub_kw.strip()}"'
  if time_op:
    full_q += f" {time_op}"

  results = []
  seen = set()

  try:
    enc = urllib.parse.quote(full_q.strip())
    url = f"https://news.google.com/rss/search?q={enc}&hl=ar&gl=MA&ceid=MA:ar"
    resp = requests.get(url, headers=headers, timeout=9)
    root = ET.fromstring(resp.content)
    for item in root.findall(".//item")[:15]:
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

      ts = calculate_precise_timestamp(pdate)
      if (now.timestamp() - ts) / 3600.0 > max_h:
        continue

      clean_d = re.sub(r"<[^>]+>", "", desc)
      results.append({
          "platform": final_platform,
          "source": f"⭐ {disp_name}",
          "title": title,
          "link": link,
          "date": pdate or datetime.now().strftime("%Y-%m-%d %H:%M"),
          "timestamp": ts,
          "snippet": clean_d or f"منشور صادر عن {disp_name}",
          "is_target": 1,
      })
      seen.add(link)
  except Exception:
    pass

  return results, disp_name, final_platform, full_q


# محركات الرصد العام
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

        ts = calculate_precise_timestamp(pdate)
        if (now.timestamp() - ts) / 3600.0 > max_h:
          continue

        clean_d = re.sub(r"<[^>]+>", "", desc)
        results.append({
            "platform": "مواقع وصحف",
            "source": src,
            "title": title,
            "link": link,
            "date": pdate,
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

      ts = calculate_precise_timestamp(pdate)
      if (now.timestamp() - ts) / 3600.0 > max_h:
        continue

      results.append({
          "platform": "YouTube",
          "source": "قناة YouTube",
          "title": title.replace(" - YouTube", ""),
          "link": link,
          "date": pdate,
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

      ts = calculate_precise_timestamp(pdate)
      if (now.timestamp() - ts) / 3600.0 > max_h:
        continue

      results.append({
          "platform": platform_name,
          "source": f"منشور {platform_name}",
          "title": title,
          "link": link,
          "date": pdate,
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


# التحليل الذكي وتوليد ملخص تنفيذي
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
1. هل هذا الخبر أو المنشور يخص المغرب ويتناول الموضوع المطلوب ({user_kw}) أو الشأن القضائي/القانوني المرتبط به؟ إذا كان خبراً خارج السياق تماماً أجب بـ NO فقط.
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


def send_rich_telegram_alert(token, chat_id, item):
  tag = "⭐ [رصد حصري من صفحة متابعة]" if item.get("is_target") else "⚖️ [رصد جديد]"
  msg = (
      f"{tag}\n\n"
      f"🌐 *المنصة:* {item['platform']}\n"
      f"🏛️ *المصدر / الحساب:* `{item['source']}`\n"
      f"📅 *تاريخ النشر:* {item['date']}\n"
      f"📌 *العنوان:* {item['title']}\n\n"
      f"📝 *مضمون ومقتطف المنشور:*\n_{item['snippet'][:250]}..._\n\n"
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


# تنفيذ زر الرصد المخصص
if run_custom_target_btn:
  if not custom_target_input.strip():
    st.warning("⚠️ يرجى وضع رابط الصفحة/القناة أو اسمها أولاً.")
  elif not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API في الشريط الجانبي.")
  else:
    with st.spinner(
        "جارٍ تشغيل الرصد المخصص للصفحة المستهدفة واستخراج المنشورات..."
    ):
      c_items, d_name, d_plat, d_query = execute_specific_target_monitor(
          custom_target_input,
          custom_target_platform,
          custom_target_kw,
          time_range,
      )

      if save_to_permanent:
        cur_targets = load_target_profiles()
        if not any(t.get("query") == d_query for t in cur_targets):
          cur_targets.append({
              "name": d_name,
              "platform": d_plat,
              "query": d_query,
              "enabled": True,
          })
          save_target_profiles(cur_targets)
          st.toast(
              f"💾 تمت إضافة '{d_name}' إلى قائمة المراقبة الدائمة بنجاح!"
          )

      added_custom = process_and_save_items(
          c_items, custom_target_kw.strip() or d_name
      )
      st.success(
          f"🎯 اكتمل الرصد المخصص لـ '{d_name}'! تم العثور على {len(c_items)}"
          f" مادة، وإضافة {added_custom} منشوراً جديداً بالملخص والروابط."
      )

# تنفيذ زر الرصد العام
if start_general_btn:
  clean_kw = keywords_input.strip()
  if not clean_kw:
    st.warning("⚠️ يرجى إدخال الكلمة المفتاحية للبحث العام.")
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
          f"✅ اكتمل الرصد! تم فحص {len(raw_all)} مادة، وإضافة {added} مادة"
          f" قضائية جديدة تطابق الكلمة '{clean_kw}'."
      )

# ==========================================
# استرجاع قاعدة البيانات بفرز صارم: الأحدث أولاً عبر كافة المصادر
# ==========================================
conn = sqlite3.connect("morocco_justice_hub.db")
c = conn.cursor()
c.execute(
    "SELECT platform, source, title, link, date_published, pub_timestamp,"
    " snippet, ai_analysis, is_target_profile, fetched_at FROM items ORDER BY"
    " pub_timestamp DESC, fetched_at DESC LIMIT 300"
)
all_records = c.fetchall()
conn.close()

target_records = [r for r in all_records if r[8] == 1]
news_items = [r for r in all_records if r[0] == "مواقع وصحف"]
yt_items = [r for r in all_records if r[0] == "YouTube"]
fb_items = [r for r in all_records if r[0] == "Facebook"]
x_items = [r for r in all_records if r[0] == "X (Twitter)"]
other_social = [
    r for r in all_records if r[0] in ["LinkedIn", "TikTok", "Instagram"]
]


def render_cards(items_list):
  if items_list:
    for idx, row in enumerate(items_list, 1):
      plat, src, title, link, d_pub, _, snip, ai_note, is_t, f_at = row

      badge_map = {
          "Facebook": "badge-fb",
          "X (Twitter)": "badge-x",
          "YouTube": "badge-yt",
          "Instagram": "badge-insta",
          "TikTok": "badge-tiktok",
          "LinkedIn": "badge-linkedin",
          "مواقع وصحف": "badge-site",
      }
      b_class = badge_map.get(plat, "badge-site")
      card_border = (
          "border-right: 6px solid #059669;"
          if is_t
          else "border-right: 6px solid #1e3a8a;"
      )
      is_target_tag = (
          " <span class='badge badge-target'>⭐ رصد مخصص</span>" if is_t else ""
      )

      st.markdown(
          f"""
            <div class="result-card" style="{card_border}">
                <h4>#{idx} <span class="badge {b_class}">{plat}</span>{is_target_tag} {title}</h4>
                <div class="meta-line">
                    🏛️ <b>المصدر / الحساب:</b> {src} &nbsp;|&nbsp; 
                    📅 <b>تاريخ النشر:</b> <span style="font-weight: bold; color:#1e3a8a;">{d_pub}</span> &nbsp;|&nbsp; 
                    ⏱️ <b>وقت الرصد:</b> {f_at}
                </div>
                <div class="desc-box">
                    <b>📝 مضمون المنشور:</b><br>{snip}
                </div>
                <div class="ai-box">
                    <b>💡 التقييم والملخص التنفيذي (Gemini):</b><br>{ai_note}
                </div>
                <p><a href="{link}" target="_blank" class="action-btn">🔗 مشاهدة الفيديو أو فتح المنشور كاملاً ➔</a></p>
            </div>
            """,
          unsafe_allow_html=True,
      )
  else:
    st.info("لا توجد مواد مسجلة في هذا القسم حالياً.")


# واجهة التبويبات المتقدمة
tab_unified, tab_targets, tab_news, tab_fb, tab_x, tab_yt, tab_other, tab_manage = st.tabs([
    f"⭐ الخلاصة الموحدة - الأحدث أولاً ({len(all_records)})",
    f"🎯 الرصد المخصص والصفحات ({len(target_records)})",
    f"📰 الصحف والمواقع ({len(news_items)})",
    f"🟦 فيسبوك ({len(fb_items)})",
    f"⬛ منصة إكس ({len(x_items)})",
    f"📺 يوتيوب ({len(yt_items)})",
    f"🟪 لينكد إن وتيك توك ({len(other_social)})",
    "⚙️ إدارة الصفحات المتابعة",
])

# 1. التبويب الرئيسي: الخلاصة الموحدة الشاملة مفرزة بالأحدث أولاً
with tab_unified:
  st.subheader(
      "🌐 الخلاصة الموحدة الشاملة (مرتبة بالأحدث دقيقة بدقيقة عبر كافة المنصات"
      " والمواقع)"
  )
  st.caption(
      "هذا التبويب يجمع لك كل ما تم رصده في مكان واحد، حيث تظهر أحدث مادة تم"
      " نشرها في أي منصة في قمة الترتيب."
  )
  render_cards(all_records)

# 2. تبويب الرصد المخصص
with tab_targets:
  st.subheader("🎯 منشورات وفيديوهات الصفحات والقنوات المستهدفة حصرياً")
  render_cards(target_records)

# 3. تبويب الصحف
with tab_news:
  st.subheader("📰 مقالات وتقارير الصحف والمواقع المغربية (الأحدث أولاً)")
  render_cards(news_items)

# 4. تبويب فيسبوك
with tab_fb:
  st.subheader("🟦 منشورات وتفاعلات فيسبوك (Facebook)")
  render_cards(fb_items)

# 5. تبويب إكس
with tab_x:
  st.subheader("⬛ تغريدات منصة X (Twitter)")
  render_cards(x_items)

# 6. تبويب يوتيوب
with tab_yt:
  st.subheader("📺 الفيديوهات والتغطيات المرئية الحديثة (YouTube)")
  render_cards(yt_items)

# 7. لينكد إن وتيك توك وإنستغرام
with tab_other:
  st.subheader("🟪 منشورات ومقاطع LinkedIn و TikTok و Instagram")
  render_cards(other_social)

# 8. إدارة الصفحات المستهدفة
with tab_manage:
  st.subheader("⚙️ إدارة قائمة القنوات والصفحات المتابعة تلقائياً")
  profiles_data = load_target_profiles()

  for i, p in enumerate(profiles_data):
    cp1, cp2, cp3 = st.columns([2, 3, 1])
    with cp1:
      st.markdown(f"**{p['name']}** ({p['platform']})")
    with cp2:
      st.caption(f"`{p['query']}`")
    with cp3:
      p["enabled"] = st.checkbox("مفعّل", value=p.get("enabled", True), key=f"pr_{i}")

  if st.button("💾 حفظ تعديلات الحسابات"):
    save_target_profiles(profiles_data)
    st.toast("✅ تم تحديث القائمة بنجاح.")

# التحديث الدوري كل 15 دقيقة
if auto_refresh_enabled:
  time.sleep(900)
  st.rerun()
