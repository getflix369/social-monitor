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
    /* فرض الاتجاه العربي الأصيل */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"], .main, .block-container, [data-testid="stMain"] {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
    }
    p, span, div, h1, h2, h3, h4, h5, h6, label, [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] * {
        direction: rtl !important;
        text-align: right !important;
    }
    [data-testid="stHorizontalBlock"] { direction: rtl !important; flex-direction: row !important; }
    [data-testid="column"] { direction: rtl !important; text-align: right !important; }

    /* تبويبات عصرية وأنيقة ومختصرة */
    div[data-baseweb="tab-list"] {
        direction: rtl !important;
        justify-content: flex-start !important;
        flex-direction: row !important;
        gap: 6px !important;
        border-bottom: 2px solid #e2e8f0 !important;
    }
    button[data-baseweb="tab"] {
        direction: rtl !important;
        text-align: center !important;
        font-size: 0.98rem !important;
        font-weight: 700 !important;
        padding: 8px 16px !important;
        border-radius: 8px 8px 0 0 !important;
        white-space: nowrap !important;
    }

    input, textarea, select, .stTextInput input, .stTextArea textarea, [data-baseweb="input"], [data-baseweb="base-input"] {
        direction: rtl !important;
        text-align: right !important;
    }
    .stSelectbox div, .stMultiSelect div, [data-baseweb="select"] * {
        direction: rtl !important;
        text-align: right !important;
    }
    [data-testid="stSidebar"], [data-testid="stSidebarContent"], [data-testid="stSidebar"] * {
        direction: rtl !important;
        text-align: right !important;
    }

    /* نظام ألوان وبطاقات المنصات العصري */
    .result-card {
        direction: rtl !important;
        text-align: right !important;
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 18px;
        border-radius: 12px;
        margin-bottom: 16px;
        box-shadow: 0 3px 8px rgba(0,0,0,0.03);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .result-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(0,0,0,0.06);
    }

    /* ألوان الإطارات المخصصة لكل منصة */
    .border-facebook { border-right: 6px solid #1877f2 !important; }
    .border-x { border-right: 6px solid #0f1419 !important; }
    .border-youtube { border-right: 6px solid #e02424 !important; }
    .border-instagram { border-right: 6px solid #e1306c !important; }
    .border-tiktok { border-right: 6px solid #111111 !important; }
    .border-linkedin { border-right: 6px solid #0a66c2 !important; }
    .border-news { border-right: 6px solid #1e3a8a !important; }
    .border-target { border-right: 6px solid #059669 !important; }

    /* الشارات العصرية بألوان الباستيل الناعمة */
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.82em;
        margin-left: 8px;
    }
    .badge-facebook { background-color: #e7f3ff; color: #1877f2; border: 1px solid #bedaff; }
    .badge-x { background-color: #f3f4f6; color: #111827; border: 1px solid #d1d5db; }
    .badge-youtube { background-color: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
    .badge-instagram { background-color: #fdf2f8; color: #db2777; border: 1px solid #fbcfe8; }
    .badge-tiktok { background-color: #f1f5f9; color: #0f172a; border: 1px solid #cbd5e1; }
    .badge-linkedin { background-color: #eff6ff; color: #0284c7; border: 1px solid #bae6fd; }
    .badge-news { background-color: #f0f9ff; color: #1e3a8a; border: 1px solid #bae6fd; }
    .badge-target { background-color: #dcfce7; color: #15803d; border: 1px solid #86efac; }

    .meta-line { color: #64748b; font-size: 0.88em; margin: 8px 0; }
    .desc-box {
        direction: rtl !important;
        text-align: right !important;
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 12px;
        border-radius: 8px;
        font-size: 0.94em;
        color: #334155;
        line-height: 1.6;
        margin-bottom: 12px;
    }
    .ai-box {
        direction: rtl !important;
        text-align: right !important;
        background-color: #f0fdf4;
        border: 1px solid #bbf7d0;
        padding: 10px 14px;
        border-radius: 8px;
        color: #166534;
        font-size: 0.92em;
        margin-bottom: 12px;
    }
    .action-btn {
        display: inline-block;
        padding: 8px 18px;
        border-radius: 6px;
        color: white !important;
        text-decoration: none !important;
        font-weight: 700;
        font-size: 0.88em;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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

    @media (max-width: 768px) {
        .stApp { padding: 6px !important; }
        .result-card { padding: 14px !important; }
        h1 { font-size: 1.4rem !important; }
        div[data-baseweb="tab-list"] { overflow-x: auto !important; flex-wrap: nowrap !important; }
        button[data-baseweb="tab"] { font-size: 0.86rem !important; padding: 6px 10px !important; }
    }
    </style>
""",
    unsafe_allow_html=True,
)

ARCHIVE_JSON_FILE = "articles_archive.json"
CUSTOM_TARGETS_FILE = "custom_targets.json"
CONFIG_FILE = "credentials.json"


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
          "url": "https://www.facebook.com/cspj.ma",
          "platform": "Facebook",
          "kw": "",
      },
      {"url": "https://www.youtube.com/@CSPJ_Maroc", "platform": "YouTube", "kw": ""},
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
      "auto_refresh": False,
      "refresh_interval": "15 دقيقة",
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


init_db()


def export_db_and_targets():
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
    return now.timestamp()
  try:
    return parsedate_to_datetime(date_str).timestamp()
  except Exception:
    pass

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


def parse_target_source(raw_input, selected_platform):
  raw = raw_input.strip()
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


INTERVAL_OPTIONS = {
    "15 دقيقة": 900,
    "ساعة واحدة": 3600,
    "3 ساعات": 10800,
    "6 ساعات": 21600,
    "12 ساعة": 43200,
    "24 ساعة (يوم كامل)": 86400,
}

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
      "معرّف تيليجرام (Chat ID):", value=current_cfg.get("telegram_chat_id", "")
  )

  if st.button("💾 حفظ الإعدادات والمفاتيح"):
    current_cfg["gemini_api_key"] = gemini_api_key
    current_cfg["telegram_bot_token"] = telegram_token
    current_cfg["telegram_chat_id"] = telegram_chat_id
    save_config(current_cfg)
    st.toast("✅ تم حفظ الإعدادات.")

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

  saved_interval = current_cfg.get("refresh_interval", "15 دقيقة")
  interval_keys = list(INTERVAL_OPTIONS.keys())
  default_idx = (
      interval_keys.index(saved_interval)
      if saved_interval in interval_keys
      else 0
  )

  selected_interval_label = st.selectbox(
      "دورية الرصد التلقائي:",
      options=interval_keys,
      index=default_idx,
  )

  auto_refresh_enabled = st.checkbox(
      f"🔄 تفعيل الرصد الدوري (كل {selected_interval_label})",
      value=current_cfg.get("auto_refresh", False),
  )

  if (
      auto_refresh_enabled != current_cfg.get("auto_refresh", False)
      or selected_interval_label != saved_interval
  ):
    current_cfg["auto_refresh"] = auto_refresh_enabled
    current_cfg["refresh_interval"] = selected_interval_label
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
  st.header("🛡️ حماية واستعادة البيانات")

  export_db_and_targets()
  if os.path.exists(ARCHIVE_JSON_FILE):
    with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
      st.download_button(
          "📥 تنزيل الأرشيف والروابط المخصصة",
          f.read(),
          file_name="morocco_justice_full_backup.json",
          mime="application/json",
      )

  uploaded_bk = st.file_uploader(
      "📤 استعادة الأرشيف والروابط المخصصة:", type=["json"]
  )
  if uploaded_bk is not None:
    try:
      imported_content = json.load(uploaded_bk)
      articles_part = (
          imported_content.get("articles", [])
          if isinstance(imported_content, dict)
          else imported_content
      )
      conn = sqlite3.connect("morocco_justice_hub.db")
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
      st.success("✅ تمت استعادة كافة الأخبار والروابط المخصصة بنجاح!")
      st.rerun()
    except Exception as e:
      st.error(f"خطأ أثناء الاستعادة: {e}")

st.title("⚖️ المرصد الوطني للعدالة والقضاء بالمغرب")
st.write(
    "رصد شامل للمواقع والمنصات، مصنف بألوان مميزة ومرتب حسب **الأحدث أولاً**."
)

# قسم الرصد المخصص
st.markdown("### 🎯 الرصد المخصص لروابط متعددة")

if "dynamic_targets" not in st.session_state:
  st.session_state.dynamic_targets = load_custom_targets()

c_btn_add, c_btn_save = st.columns([2, 3])
with c_btn_add:
  if st.button("➕ إضافة رابط جديد"):
    st.session_state.dynamic_targets.append(
        {"url": "", "platform": "كشف تلقائي من الرابط", "kw": ""}
    )
    save_custom_targets(st.session_state.dynamic_targets)
    st.rerun()
with c_btn_save:
  if st.button("💾 حفظ الروابط الحالية بشكل دائم"):
    save_custom_targets(st.session_state.dynamic_targets)
    st.toast("✅ تم حفظ قائمة الروابط بنجاح.")

targets_to_run = []
has_changes = False

for idx, item in enumerate(st.session_state.dynamic_targets):
  with st.container():
    c_u1, c_u2, c_u3, c_u4 = st.columns([4, 2, 3, 1])
    with c_u1:
      new_url = st.text_input(
          f"الرابط #{idx+1}:",
          value=item.get("url", ""),
          key=f"t_url_{idx}",
          placeholder="مثال: https://facebook.com/page أو @channel",
      )
      if new_url != item.get("url", ""):
        item["url"] = new_url
        has_changes = True

    with c_u2:
      plat_opts = [
          "كشف تلقائي من الرابط",
          "Facebook",
          "YouTube",
          "X (Twitter)",
          "LinkedIn",
          "TikTok",
          "مواقع وصحف",
      ]
      cur_p = item.get("platform", "كشف تلقائي من الرابط")
      p_idx = plat_opts.index(cur_p) if cur_p in plat_opts else 0
      new_plat = st.selectbox(
          "المنصة:", options=plat_opts, index=p_idx, key=f"t_plat_{idx}"
      )
      if new_plat != item.get("platform", ""):
        item["platform"] = new_plat
        has_changes = True

    with c_u3:
      new_kw = st.text_input(
          "كلمة مفتاحية (اختياري):",
          value=item.get("kw", ""),
          key=f"t_kw_{idx}",
          placeholder="اتركه فارغاً لجلب كل المنشورات",
      )
      if new_kw != item.get("kw", ""):
        item["kw"] = new_kw
        has_changes = True

    with c_u4:
      st.write("")
      st.write("")
      if st.button("❌", key=f"del_{idx}", help="إزالة"):
        st.session_state.dynamic_targets.pop(idx)
        save_custom_targets(st.session_state.dynamic_targets)
        st.rerun()

    if item["url"].strip():
      targets_to_run.append(item)

if has_changes:
  save_custom_targets(st.session_state.dynamic_targets)

run_all_custom_btn = st.button(
    f"🎯 تشغيل الرصد المخصص لكافة الروابط ({len(targets_to_run)})",
    type="primary",
)

st.divider()

# حقول الرصد العام
st.markdown("### 🌐 الرصد العام الشامل للكلمة المفتاحية:")
col_g1, col_g2 = st.columns(2)
with col_g1:
  target_domain = st.text_input(
      "🎯 نطاق التقييم:",
      value="شؤون القضاء والعدالة والمحاكم والنيابة العامة بالمملكة المغربية حصراً",
  )
with col_g2:
  keywords_input = st.text_input(
      "🔑 استعلام البحث الرئيسي:",
      value="المجلس الأعلى للسلطة القضائية",
  )

start_general_btn = st.button("🚀 بدء الرصد العام عبر كل المنصات")


def get_time_params(time_mode):
  if time_mode == "آخر 24 ساعة (اليوم فقط)":
    return 30, "when:1d", "d"
  elif time_mode == "آخر 7 أيام (هذا الأسبوع)":
    return 180, "when:7d", "w"
  elif time_mode == "آخر 30 يوماً (هذا الشهر)":
    return 750, "when:30d", "m"
  return 999999, "", None


def execute_multi_target_monitor(targets_list, time_mode):
  max_h, time_op, _ = get_time_params(time_mode)
  now = datetime.now(timezone.utc)
  headers = {"User-Agent": "Mozilla/5.0"}

  results = []
  seen = set()

  for t in targets_list:
    raw_u = t["url"].strip()
    if not raw_u:
      continue
    auto_p, disp_name, query_str = parse_target_source(
        raw_u,
        "Facebook" if t["platform"] == "كشف تلقائي من الرابط" else t["platform"],
    )
    final_p = (
        auto_p if t["platform"] == "كشف تلقائي من الرابط" else t["platform"]
    )

    full_q = f"{query_str}"
    if t["kw"].strip():
      full_q += f' "{t["kw"].strip()}"'
    if time_op:
      full_q += f" {time_op}"

    try:
      enc = urllib.parse.quote(full_q.strip())
      url = f"https://news.google.com/rss/search?q={enc}&hl=ar&gl=MA&ceid=MA:ar"
      resp = requests.get(url, headers=headers, timeout=9)
      root = ET.fromstring(resp.content)
      for item in root.findall(".//item")[:10]:
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

        ts = calculate_precise_timestamp(pdate)
        if (now.timestamp() - ts) / 3600.0 > max_h:
          continue

        clean_d = re.sub(r"<[^>]+>", "", desc)
        results.append({
            "platform": final_p,
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

  return results


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

المطلوب:
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
  export_db_and_targets()
  return new_count


if run_all_custom_btn:
  if not targets_to_run:
    st.warning("⚠️ يرجى إضافة رابط واحد على الأقل.")
  elif not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API في الشريط الجانبي.")
  else:
    save_custom_targets(st.session_state.dynamic_targets)
    with st.spinner(f"جارٍ فحص {len(targets_to_run)} رابط وصفحة مستهدفة..."):
      c_items = execute_multi_target_monitor(targets_to_run, time_range)
      added_custom = process_and_save_items(
          c_items, "القضاء والعدالة بالمغرب والمواضيع المتابعة"
      )
      st.success(
          f"🎯 اكتمل الرصد! تم جلب {len(c_items)} مادة، وإضافة {added_custom}"
          " منشوراً جديداً."
      )

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

# استرجاع قاعدة البيانات بفرز صارم: الأحدث أولاً
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


# دالة تحديد الألوان والهوية البصرية لكل منصة
def get_platform_design(plat, is_t):
  if is_t:
    return "border-target", "badge-target", "رصد مخصص", "#059669"
  p = plat.lower()
  if "facebook" in p or "فيسبوك" in p:
    return "border-facebook", "badge-facebook", "فيسبوك", "#1877f2"
  elif "x" in p or "twitter" in p or "تويتر" in p or "إكس" in p:
    return "border-x", "badge-x", "إكس", "#0f1419"
  elif "youtube" in p or "يوتيوب" in p:
    return "border-youtube", "badge-youtube", "يوتيوب", "#dc2626"
  elif "instagram" in p or "إنستغرام" in p:
    return "border-instagram", "badge-instagram", "إنستغرام", "#db2777"
  elif "tiktok" in p or "تيك توك" in p:
    return "border-tiktok", "badge-tiktok", "تيك توك", "#0f172a"
  elif "linkedin" in p or "لينكد" in p:
    return "border-linkedin", "badge-linkedin", "لينكدإن", "#0284c7"
  return "border-news", "badge-news", "صحافة", "#1e3a8a"


def render_cards(items_list):
  if items_list:
    for idx, row in enumerate(items_list, 1):
      plat, src, title, link, d_pub, _, snip, ai_note, is_t, f_at = row
      border_cls, badge_cls, p_label, btn_color = get_platform_design(
          plat, is_t
      )
      is_target_tag = (
          " <span class='badge badge-target'>⭐ مخصص</span>" if is_t else ""
      )

      st.markdown(
          f"""
            <div class="result-card {border_cls}">
                <h4>#{idx} <span class="badge {badge_cls}">{p_label}</span>{is_target_tag} {title}</h4>
                <div class="meta-line">
                    🏛️ <b>الجهة / الناشر:</b> {src} &nbsp;|&nbsp; 
                    📅 <b>تاريخ النشر:</b> <span style="font-weight: bold; color: {btn_color};">{d_pub}</span> &nbsp;|&nbsp; 
                    ⏱️ <b>وقت الرصد:</b> {f_at}
                </div>
                <div class="desc-box">
                    <b>📝 مضمون المنشور:</b><br>{snip}
                </div>
                <div class="ai-box">
                    <b>💡 التقييم والملخص التنفيذي (Gemini):</b><br>{ai_note}
                </div>
                <p><a href="{link}" target="_blank" class="action-btn" style="background-color: {btn_color};">🔗 فتح المنشور الأصلي ➔</a></p>
            </div>
            """,
          unsafe_allow_html=True,
      )
  else:
    st.info("لا توجد مواد مسجلة في هذا القسم حالياً.")


# واجهة التبويبات المختصرة بكلمة أو كلمتين فقط لتناسب كافة الشاشات
tab_all, tab_custom, tab_press, tab_facebook, tab_x_plat, tab_youtube, tab_others = st.tabs([
    f"الكل ({len(all_records)})",
    f"المخصصة ({len(target_records)})",
    f"الصحف ({len(news_items)})",
    f"فيسبوك ({len(fb_items)})",
    f"إكس ({len(x_items)})",
    f"يوتيوب ({len(yt_items)})",
    f"أخرى ({len(other_social)})",
])

with tab_all:
  st.subheader("🌐 الخلاصة الشاملة (الأحدث أولاً)")
  render_cards(all_records)

with tab_custom:
  st.subheader("🎯 الرصد المخصص")
  render_cards(target_records)

with tab_press:
  st.subheader("📰 الصحف والمواقع المغربية")
  render_cards(news_items)

with tab_facebook:
  st.subheader("🟦 فيسبوك (Facebook)")
  render_cards(fb_items)

with tab_x_plat:
  st.subheader("⬛ منصة إكس (Twitter)")
  render_cards(x_items)

with tab_youtube:
  st.subheader("📺 يوتيوب (YouTube)")
  render_cards(yt_items)

with tab_others:
  st.subheader("🟪 لينكد إن وتيك توك وإنستغرام")
  render_cards(other_social)

if auto_refresh_enabled:
  sleep_seconds = INTERVAL_OPTIONS.get(selected_interval_label, 900)
  time.sleep(sleep_seconds)
  st.rerun()
