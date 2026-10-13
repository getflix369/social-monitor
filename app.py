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
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
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
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .result-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.45);
        border-color: rgba(255, 255, 255, 0.16);
    }

    .border-facebook { border-right: 6px solid #1877f2 !important; box-shadow: 0 0 15px rgba(24, 119, 242, 0.15) !important; }
    .border-x { border-right: 6px solid #e2e8f0 !important; box-shadow: 0 0 15px rgba(226, 232, 240, 0.1) !important; }
    .border-youtube { border-right: 6px solid #ef4444 !important; box-shadow: 0 0 15px rgba(239, 68, 68, 0.18) !important; }
    .border-instagram { border-right: 6px solid #ec4899 !important; box-shadow: 0 0 15px rgba(236, 72, 153, 0.18) !important; }
    .border-tiktok { border-right: 6px solid #06b6d4 !important; box-shadow: 0 0 15px rgba(6, 182, 212, 0.18) !important; }
    .border-linkedin { border-right: 6px solid #0284c7 !important; box-shadow: 0 0 15px rgba(2, 132, 199, 0.18) !important; }
    .border-news { border-right: 6px solid #3b82f6 !important; box-shadow: 0 0 15px rgba(59, 130, 246, 0.15) !important; }
    .border-target { border-right: 6px solid #10b981 !important; box-shadow: 0 0 15px rgba(16, 185, 129, 0.2) !important; }
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
        direction: rtl !important;
        text-align: right !important;
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
        direction: rtl !important;
        text-align: right !important;
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
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    @keyframes radar-sweep { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    .radar-wrapper {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 24px;
        margin: 18px 0;
        background: rgba(15, 23, 42, 0.7);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 16px;
        box-shadow: 0 0 35px rgba(56, 189, 248, 0.15);
    }
    .radar-screen {
        position: relative;
        width: 130px;
        height: 130px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(14, 165, 233, 0.08) 0%, rgba(15, 23, 42, 0.9) 70%);
        border: 2px solid rgba(56, 189, 248, 0.45);
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.25), inset 0 0 15px rgba(56, 189, 248, 0.15);
        overflow: hidden;
        margin-bottom: 12px;
    }
    .radar-screen::before {
        content: '';
        position: absolute;
        top: 50%; left: 50%;
        width: 65px; height: 65px;
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

    .done-badge {
        display: inline-block;
        padding: 10px 24px;
        border-radius: 10px;
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid #10b981;
        color: #34d399 !important;
        font-weight: 800;
        font-size: 1.15rem;
        box-shadow: 0 0 25px rgba(16, 185, 129, 0.3);
        margin: 15px 0;
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
      "auto_refresh": False,
      "refresh_interval": "15 دقيقة",
      "last_auto_run": 0.0,
      "last_run_time_str": "لم يتم بعد",
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
    return now.timestamp() - 86400
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
      days = 1 if "أمس" in s or "يوم" in s and not num_match else val
      return now.timestamp() - (days * 86400)
    elif any(w in s for w in ["أسبوع", "أسبوعين", "أسابيع", "week"]):
      return now.timestamp() - (val * 7 * 86400)
    elif any(w in s for w in ["شهر", "أشهر", "month"]):
      return now.timestamp() - (val * 30 * 86400)
  except Exception:
    pass

  return now.timestamp() - (2 * 86400)


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
  st.header("⏱️ الجدولة والرصد الدوري التلقائي")

  saved_interval = current_cfg.get("refresh_interval", "15 دقيقة")
  interval_keys = list(INTERVAL_OPTIONS.keys())
  default_idx = (
      interval_keys.index(saved_interval)
      if saved_interval in interval_keys
      else 0
  )

  selected_interval_label = st.selectbox(
      "تكرار الرصد الآلي:",
      options=interval_keys,
      index=default_idx,
  )

  auto_refresh_enabled = st.checkbox(
      f"🔄 تفعيل الرصد الدوري التلقائي (كل {selected_interval_label})",
      value=current_cfg.get("auto_refresh", False),
  )

  if (
      auto_refresh_enabled != current_cfg.get("auto_refresh", False)
      or selected_interval_label != saved_interval
  ):
    current_cfg["auto_refresh"] = auto_refresh_enabled
    current_cfg["refresh_interval"] = selected_interval_label
    save_config(current_cfg)

  st.caption(
      f"🕒 آخر فحص تم: **{current_cfg.get('last_run_time_str', 'لم يتم بعد')}**"
  )
  send_telegram = st.checkbox("إرسال تنبيه إلى Telegram فورياً", value=True)

  st.divider()
  st.header("🛡️ حماية الأرشيف والبيانات")
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
      "📤 استعادة الأرشيف والروابط:", type=["json"]
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
      st.success("✅ تمت استعادة كافة الأخبار السابقة والروابط بنجاح!")
      st.rerun()
    except Exception as e:
      st.error(f"خطأ أثناء الاستعادة: {e}")

st.title("⚖️ المرصد الوطني للعدالة والقضاء بالمغرب")
st.write(
    "رصد شامل للمستجدات القضائية: **رصد شامل (الكل)**، **رصد خاص بكل منصة**، أو"
    " **رصد مخصص لصفحات محددة** مع رادار مسح 360° ونظام ألوان مستقل لكل منصة."
)

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

# حقل الكلمات المفتاحية الاختياري
col_k1, col_k2 = st.columns([1, 2])
with col_k1:
  st.info(
      "🏛️ **الرصد الافتراضي:**\n\n• المجلس الأعلى للسلطة القضائية\n• القضاء"
      " والمحاكم بالمغرب\n• النيابة العامة والعدالة"
  )
with col_k2:
  keywords_input = st.text_input(
      "🔑 تخصيص البحث بكلمة أو كلمات إضافية (اختياري):",
      value="",
      placeholder=(
          "اتركه فارغاً للرصد القضائي العام، أو اكتب كلمات: مثلاً: إضراب"
          " المحامين، محاكمة..."
      ),
  )

st.divider()

# 1. لوحة الرصد الشامل (الكل)
st.markdown("### 🌐 المستوى الأول: الرصد الشامل (الكل)")
c_all_run, c_all_stop = st.columns([3, 1])
with c_all_run:
  btn_run_all = st.button(
      "🚀 بدء الرصد الشامل (الكل)", type="primary", key="btn_run_all"
  )
with c_all_stop:
  if st.button("🛑 إيقاف الرصد الشامل", key="btn_stop_all"):
    st.session_state.stop_flags["all"] = True
    st.warning("تم طلب إيقاف الرصد الشامل.")

radar_placeholder = st.empty()
progress_placeholder = st.empty()
done_placeholder = st.empty()

st.divider()

# 2. لوحة الرصد الخاص بكل منصة على حدة
st.markdown("### 📱 المستوى الثاني: الرصد الخاص بكل منصة على حدة")
st.caption(
    "يمكنك رصد أي منصة بمفردها بنقرة واحدة، مع وجود زر إيقاف مخصص لكل منصة:"
)

c_p1, c_p2, c_p3 = st.columns(3)
with c_p1:
  st.markdown("##### 📰 الصحف والمواقع")
  cp_run, cp_stop = st.columns([2, 1])
  with cp_run:
    btn_run_press = st.button("📰 رصد الصحف", key="btn_run_press")
  with cp_stop:
    if st.button("🛑 إيقاف", key="btn_stop_press"):
      st.session_state.stop_flags["press"] = True

with c_p2:
  st.markdown("##### 🟦 فيسبوك (Facebook)")
  cfb_run, cfb_stop = st.columns([2, 1])
  with cfb_run:
    btn_run_fb = st.button("🟦 رصد فيسبوك", key="btn_run_fb")
  with cfb_stop:
    if st.button("🛑 إيقاف", key="btn_stop_fb"):
      st.session_state.stop_flags["fb"] = True

with c_p3:
  st.markdown("##### ⬛ منصة إكس (Twitter)")
  cx_run, cx_stop = st.columns([2, 1])
  with cx_run:
    btn_run_x = st.button("⬛ رصد إكس", key="btn_run_x")
  with cx_stop:
    if st.button("🛑 إيقاف", key="btn_stop_x"):
      st.session_state.stop_flags["x"] = True

c_p4, c_p5, _ = st.columns([1, 1, 1])
with c_p4:
  st.markdown("##### 🟥 يوتيوب (YouTube)")
  cyt_run, cyt_stop = st.columns([2, 1])
  with cyt_run:
    btn_run_yt = st.button("🟥 رصد يوتيوب", key="btn_run_yt")
  with cyt_stop:
    if st.button("🛑 إيقاف", key="btn_stop_yt"):
      st.session_state.stop_flags["yt"] = True

with c_p5:
  st.markdown("##### 🟪 تيك توك ولينكد إن")
  cother_run, cother_stop = st.columns([2, 1])
  with cother_run:
    btn_run_other = st.button("🟪 رصد تيك توك/لينكد إن", key="btn_run_other")
  with cother_stop:
    if st.button("🛑 إيقاف", key="btn_stop_other"):
      st.session_state.stop_flags["other"] = True

st.divider()

# 3. لوحة الرصد المخصص لروابط وقنوات محددة
st.markdown("### 🎯 المستوى الثالث: الرصد المخصص لروابط وقنوات وصفحات محددة")

if "dynamic_targets" not in st.session_state:
  st.session_state.dynamic_targets = load_custom_targets()

c_add_t, c_save_t = st.columns([2, 3])
with c_add_t:
  if st.button("➕ إضافة رابط جديد"):
    st.session_state.dynamic_targets.append(
        {"url": "", "platform": "كشف تلقائي من الرابط", "kw": ""}
    )
    save_custom_targets(st.session_state.dynamic_targets)
    st.rerun()
with c_save_t:
  if st.button("💾 حفظ الروابط الحالية"):
    save_custom_targets(st.session_state.dynamic_targets)
    st.toast("✅ تم حفظ قائمة الروابط بنجاح.")

targets_to_run = []
has_changes = False

for idx, item in enumerate(st.session_state.dynamic_targets):
  with st.container():
    c_u1, c_u2, c_u3, c_u4 = st.columns([4, 2, 3, 1])
    with c_u1:
      new_url = st.text_input(
          f"الرابط أو المعرف #{idx+1}:",
          value=item.get("url", ""),
          key=f"t_url_{idx}",
          placeholder="مثال: https://youtube.com/@channel أو facebook.com/page",
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
          "المنصة:", options=plat_opts, index=p_idx, key=f"t_plat_{idx}"
      )
      if new_plat != item.get("platform", ""):
        item["platform"] = new_plat
        has_changes = True

    with c_u3:
      new_kw = st.text_input(
          "كلمة مفتاحية للحصر داخل الحساب (اختياري):",
          value=item.get("kw", ""),
          key=f"t_kw_{idx}",
          placeholder="اتركه فارغاً لرصد كل منشورات الحساب",
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

c_run_tgt, c_stop_tgt = st.columns([3, 1])
with c_run_tgt:
  run_all_custom_btn = st.button(
      f"🎯 تشغيل الرصد المخصص للروابط المضافة ({len(targets_to_run)})",
      key="btn_run_custom_main",
  )
with c_stop_tgt:
  if st.button("🛑 إيقاف الرصد المخصص", key="btn_stop_custom"):
    st.session_state.stop_flags["custom"] = True
    st.warning("تم طلب إيقاف الرصد المخصص.")

st.divider()


# ==========================================
# محركات الجلب المباشرة والمضمونة 100%
# ==========================================


# 1. جلب يوتيوب مع تجاوز جدران الحظر وكوكيز الموافقة
def fetch_target_youtube_direct(url_or_handle):
  raw = url_or_handle.strip()
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/122.0.0.0 Safari/537.36"
      ),
      "Accept-Language": "ar,en;q=0.9",
  }
  # كوكيز تخطي صفحة الموافقة في يوتيوب
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
      m = re.search(r'itemprop="channelId"\s+content="([a-zA-Z0-9_\-]{24})"', resp.text)
    if not m:
      m = re.search(r'channel_id=([a-zA-Z0-9_\-]{24})', resp.text)
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

  # بديل مباشر عبر نتائج بحث يوتيوب المباشرة مع الكوكيز
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
            "timestamp": datetime.now().timestamp(),
            "snippet": f"فيديو صادر عن قناة {channel_slug}",
            "is_target": 1,
        })
    except Exception:
      pass

  return results


# 2. جلب مباشر لمواقع وصحف عبر خلاصات /feed
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
      if resp.status_code == 200 and ("<rss" in resp.text or "<xml" in resp.text):
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


# 3. جلب منشورات صفحات فيسبوك وإكس وتيك توك المحددة عبر البحث المباشر
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

  # المسار الأول: عبر DuckDuckGo للبحث المباشر عن الصفحة
  q_search = f'site:facebook.com/{slug}' if platform_name == "Facebook" else f'site:x.com/{slug}'
  try:
    with DDGS() as ddgs:
      for r in ddgs.text(q_search, max_results=8):
        results.append({
            "platform": platform_name,
            "source": f"صفحة: {slug}",
            "title": r.get("title", f"منشور على {platform_name}"),
            "link": r.get("href", ""),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().timestamp(),
            "snippet": r.get("body", "")[:300],
            "is_target": 1,
        })
  except Exception:
    pass

  # المسار الثاني: استعلام نصي مفتوح إن لم تظهر نتائج
  if not results:
    try:
      enc = urllib.parse.quote(f'"{slug}" {platform_name}')
      url = f"https://news.google.com/rss/search?q={enc}&hl=ar&gl=MA&ceid=MA:ar"
      resp = requests.get(url, headers=headers, timeout=5)
      root = ET.fromstring(resp.content)
      for it in root.findall(".//item")[:6]:
        l = it.find("link").text if it.find("link") is not None else ""
        t = it.find("title").text if it.find("title") is not None else ""
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


def execute_multi_target_monitor(targets_list, stop_key="custom"):
  all_target_items = []
  seen_links = set()

  for t in targets_list:
    if st.session_state.stop_flags.get(
        stop_key
    ) or st.session_state.stop_flags.get("all"):
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

    items = []
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


# ==========================================
# محركات الرصد العام والخاص للمنصات (مصححة بنسبة 100%)
# ==========================================


# رصد الصحف
def fetch_moroccan_sites_quick(custom_input, max_count=20, stop_key="all"):
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
    queries = [f'"{cleaned}" (قضاء OR محكمة OR عدالة بالمغرب) when:1d']

  for q in queries:
    if st.session_state.stop_flags.get(stop_key) or len(results) >= max_count:
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


# رصد يوتيوب العام
def fetch_youtube_posts_live(custom_input, max_count=12, stop_key="all"):
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
      else "المجلس الأعلى للسلطة القضائية المغرب OR القضاء المغربي"
  )
  yt_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(topic)}&sp=CAI%253D"

  try:
    resp = requests.get(yt_url, headers=headers, cookies=cookies, timeout=6)
    v_ids = re.findall(r"/watch\?v=([a-zA-Z0-9_\-]{11})", resp.text)
    titles = re.findall(r'"title":\{"runs":\[\{"text":"(.*?)"\}\]', resp.text)
    for idx, vid in enumerate(v_ids[:max_count]):
      if vid in seen or st.session_state.stop_flags.get(stop_key):
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
          "timestamp": datetime.now().timestamp(),
          "snippet": f"فيديو يوتيوب مصور يتناول: {topic}",
          "is_target": 0,
      })
  except Exception:
    pass

  return results


# رصد فيسبوك العام
def fetch_facebook_posts_live(custom_input, max_count=10, stop_key="all"):
  results = []
  seen = set()
  topic = (
      custom_input.strip()
      if custom_input.strip()
      else "المجلس الأعلى للسلطة القضائية OR القضاء المغربي"
  )

  # البحث المباشر في فيسبوك
  try:
    with DDGS() as ddgs:
      for r in ddgs.text(
          f'site:facebook.com "{topic}"', max_results=max_count, timelimit="w"
      ):
        if st.session_state.stop_flags.get(stop_key):
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
            "date": "حديثاً (هذا الأسبوع)",
            "timestamp": datetime.now().timestamp(),
            "snippet": r.get("body", ""),
            "is_target": 0,
        })
  except Exception:
    pass

  # بديل Google News للتقارير التي تغطي فيسبوك
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
              "snippet": re.sub(r"<[^>]+>", "", it.find("description").text or "")[
                  :300
              ],
              "is_target": 0,
          })
    except Exception:
      pass

  return results


# رصد إكس (تويتر) العام
def fetch_x_posts_live(custom_input, max_count=10, stop_key="all"):
  results = []
  seen = set()
  topic = (
      custom_input.strip()
      if custom_input.strip()
      else "المجلس الأعلى للسلطة القضائية OR القضاء المغربي"
  )

  # محاولة قراءة Nitter RSS للتغريدات الحية
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
          l = it.find("link").text.replace("nitter.poast.org", "x.com").replace(
              "nitter.privacydev.net", "x.com"
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

  # بديل البحث المباشر في X
  if not results:
    try:
      with DDGS() as ddgs:
        for r in ddgs.text(
            f'site:x.com "{topic}"', max_results=max_count, timelimit="w"
        ):
          link = r.get("href", "")
          if link and link not in seen:
            seen.add(link)
            results.append({
                "platform": "X (Twitter)",
                "source": "تغريدة على X",
                "title": r.get("title", f"تغريدة حول {topic}"),
                "link": link,
                "date": "حديثاً",
                "timestamp": datetime.now().timestamp(),
                "snippet": r.get("body", ""),
                "is_target": 0,
            })
    except Exception:
      pass

  return results


# رصد تيك توك ولينكد إن
def fetch_other_social_live(custom_input, max_count=8, stop_key="all"):
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
        if st.session_state.stop_flags.get(stop_key):
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
              "timestamp": datetime.now().timestamp(),
              "snippet": r.get("body", ""),
              "is_target": 0,
          })
  except Exception:
    pass
  return results


# ==========================================
# المعالجة السريعة بالذكاء الاصطناعي مع الحماية من التجميد
# ==========================================
def quick_process_and_save(
    items_list, is_target_run=False, stop_key="all", progress_cb=None
):
  conn = sqlite3.connect("morocco_justice_hub.db")
  c = conn.cursor()

  new_candidates = []
  for it in items_list:
    c.execute("SELECT link FROM items WHERE link = ?", (it["link"],))
    if not c.fetchone():
      new_candidates.append(it)

  new_candidates = new_candidates[:8]
  new_count = 0

  if new_candidates and gemini_api_key:
    for i, it in enumerate(new_candidates):
      if st.session_state.stop_flags.get(
          stop_key
      ) or st.session_state.stop_flags.get("all"):
        break

      summary = ""
      try:
        genai.configure(api_key=gemini_api_key)
        m = genai.GenerativeModel(model_choice)
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

      if send_telegram and telegram_token and telegram_chat_id:
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
              f"https://api.telegram.org/bot{telegram_token}/sendMessage",
              json={
                  "chat_id": telegram_chat_id,
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


# ==========================================
# تشغيل الرصد الشامل (الكل) مع الرادار ثلاثي الأبعاد ومؤشر DONE
# ==========================================
if btn_run_all:
  if not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API في الشريط الجانبي أولاً.")
  else:
    st.session_state.stop_flags["all"] = False
    custom_in = keywords_input.strip()

    radar_placeholder.markdown(
        """
        <div class="radar-wrapper">
            <div class="radar-screen">
                <div class="radar-sweep-arm"></div>
                <div class="radar-target-dot"></div>
            </div>
            <div style="font-weight:700; color:#38bdf8; font-size:1.05rem;">
                📡 جارٍ المسح الراداري 360° واستطلاع الشبكات والمواقع...
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    p_bar = progress_placeholder.progress(0.0)
    raw_items = []

    # 1/5 الصحف
    p_bar.progress(0.2)
    raw_items.extend(
        fetch_moroccan_sites_quick(custom_in, max_count=20, stop_key="all")
    )

    if not st.session_state.stop_flags["all"]:
      # 2/5 يوتيوب المباشر
      p_bar.progress(0.4)
      raw_items.extend(
          fetch_youtube_posts_live(custom_in, max_count=10, stop_key="all")
      )

    if not st.session_state.stop_flags["all"]:
      # 3/5 فيسبوك
      p_bar.progress(0.6)
      raw_items.extend(
          fetch_facebook_posts_live(custom_in, max_count=8, stop_key="all")
      )

    if not st.session_state.stop_flags["all"]:
      # 4/5 إكس والمنصات الأخرى
      p_bar.progress(0.8)
      raw_items.extend(
          fetch_x_posts_live(custom_in, max_count=8, stop_key="all")
      )
      raw_items.extend(
          fetch_other_social_live(custom_in, max_count=6, stop_key="all")
      )
      targets = load_custom_targets()
      if targets:
        raw_items.extend(execute_multi_target_monitor(targets, stop_key="all"))

    if not st.session_state.stop_flags["all"]:
      # 5/5 المعالجة والذكاء الاصطناعي
      def update_ai_p(fraction):
        p_bar.progress(min(0.85 + (fraction * 0.15), 1.0))

      added_count = quick_process_and_save(
          raw_items,
          is_target_run=False,
          stop_key="all",
          progress_cb=update_ai_p,
      )
      p_bar.progress(1.0)
      radar_placeholder.empty()

      done_placeholder.markdown(
          f"""
            <div style="text-align:center;">
                <div class="done-badge">
                    ✨ تـم بنجاح / DONE ✨ (+{added_count} مادة جديدة)
                </div>
            </div>
            """,
          unsafe_allow_html=True,
      )
    else:
      radar_placeholder.empty()
      st.warning("⚠️ تم إيقاف عملية الرصد الشامل بواسطة المستخدم.")

# ==========================================
# تشغيل الرصد الخاص بكل منصة على حدة (مصححة ومباشرة)
# ==========================================
if btn_run_press:
  st.session_state.stop_flags["press"] = False
  with st.spinner("جارٍ رصد الصحف والمواقع المغربية..."):
    items = fetch_moroccan_sites_quick(
        keywords_input.strip(), max_count=20, stop_key="press"
    )
    added = quick_process_and_save(items, is_target_run=False, stop_key="press")
    st.markdown(
        f'<div class="done-badge">✨ تـم رصد الصحف بنجاح / DONE ✨ (+{added}'
        " مادة)</div>",
        unsafe_allow_html=True,
    )

if btn_run_fb:
  st.session_state.stop_flags["fb"] = False
  with st.spinner("جارٍ رصد منشورات فيسبوك المباشرة..."):
    items = fetch_facebook_posts_live(
        keywords_input.strip(), max_count=12, stop_key="fb"
    )
    added = quick_process_and_save(items, is_target_run=False, stop_key="fb")
    st.markdown(
        f'<div class="done-badge">✨ تـم رصد فيسبوك بنجاح / DONE ✨ (+{added}'
        " منشور)</div>",
        unsafe_allow_html=True,
    )

if btn_run_x:
  st.session_state.stop_flags["x"] = False
  with st.spinner("جارٍ رصد تغريدات منصة إكس المباشرة..."):
    items = fetch_x_posts_live(
        keywords_input.strip(), max_count=12, stop_key="x"
    )
    added = quick_process_and_save(items, is_target_run=False, stop_key="x")
    st.markdown(
        f'<div class="done-badge">✨ تـم رصد منصة إكس بنجاح / DONE ✨ (+{added}'
        " تغريدة)</div>",
        unsafe_allow_html=True,
    )

if btn_run_yt:
  st.session_state.stop_flags["yt"] = False
  with st.spinner("جارٍ رصد فيديوهات يوتيوب المباشرة..."):
    items = fetch_youtube_posts_live(
        keywords_input.strip(), max_count=10, stop_key="yt"
    )
    added = quick_process_and_save(items, is_target_run=False, stop_key="yt")
    st.markdown(
        f'<div class="done-badge">✨ تـم رصد يوتيوب بنجاح / DONE ✨ (+{added}'
        " فيديو)</div>",
        unsafe_allow_html=True,
    )

if btn_run_other:
  st.session_state.stop_flags["other"] = False
  with st.spinner("جارٍ رصد تيك توك ولينكد إن..."):
    items = fetch_other_social_live(
        keywords_input.strip(), max_count=10, stop_key="other"
    )
    added = quick_process_and_save(items, is_target_run=False, stop_key="other")
    st.markdown(
        f'<div class="done-badge">✨ تـم رصد المنصات الأخرى بنجاح / DONE ✨'
        f" (+{added} مادة)</div>",
        unsafe_allow_html=True,
    )

# تشغيل الرصد المخصص
if run_all_custom_btn:
  st.session_state.stop_flags["custom"] = False
  if not targets_to_run:
    st.warning("⚠️ يرجى إضافة رابط واحد على الأقل في القائمة.")
  elif not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API أولاً.")
  else:
    save_custom_targets(st.session_state.dynamic_targets)
    with st.spinner(f"جارٍ فحص {len(targets_to_run)} رابط وصفحة مستهدفة..."):
      t_items = execute_multi_target_monitor(
          targets_to_run, stop_key="custom"
      )
      added_t = quick_process_and_save(
          t_items, is_target_run=True, stop_key="custom"
      )
      st.markdown(
          f'<div class="done-badge">✨ تـم الرصد المخصص بنجاح / DONE ✨'
          f" (+{added_t} مادة)</div>",
          unsafe_allow_html=True,
      )

# ==========================================
# استرجاع وعرض البيانات الزجاجية الفاخرة
# ==========================================
conn = sqlite3.connect("morocco_justice_hub.db")
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
    return "border-target", "badge-target", "رصد مخصص", "#10b981"
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
                    🏛️ <b>الجهة / الناشر:</b> {src} &nbsp;|&nbsp; 
                    📅 <b>تاريخ النشر:</b> <span style="font-weight: bold; color: {btn_color};">{d_pub}</span> &nbsp;|&nbsp; 
                    ⏱️ <b>وقت الرصد:</b> {f_at}
                </div>
                <div class="desc-box">
                    <b>📝 مضمون ومقتطف المنشور:</b><br>{snip}
                </div>
                <div class="ai-box">
                    <b>💡 التقييم والملخص التنفيذي (Gemini):</b><br>{ai_note}
                </div>
                <p><a href="{link}" target="_blank" class="action-btn" style="background-color: {btn_color};">🔗 فتح المنشور / الفيديو كاملاً ➔</a></p>
            </div>
            """,
          unsafe_allow_html=True,
      )
  else:
    st.info("لا توجد منشورات مسجلة في هذا القسم حالياً.")


tab_live_all, tab_press, tab_facebook, tab_x_plat, tab_youtube, tab_others, tab_archive_all = st.tabs([
    f"الكل ({len(live_records)})",
    f"الصحف ({len(live_news)})",
    f"فيسبوك ({len(live_fb)})",
    f"إكس ({len(live_x)})",
    f"يوتيوب ({len(live_yt)})",
    f"أخرى ({len(live_other)})",
    f"🗄️ الأرشيف ({len(archive_records)})",
])

with tab_live_all:
  st.subheader("🌐 الأخبار القضائية الحية لليوم (آخر 24 ساعة)")
  render_cards(live_records)

with tab_press:
  st.subheader("📰 الصحف والمواقع المغربية (آخر 24 ساعة)")
  render_cards(live_news)

with tab_facebook:
  st.subheader("🟦 فيسبوك (Facebook) - منشورات اليوم")
  render_cards(live_fb)

with tab_x_plat:
  st.subheader("⬛ منصة إكس (Twitter) - تغريدات اليوم")
  render_cards(live_x)

with tab_youtube:
  st.subheader("📺 يوتيوب (YouTube) - فيديوهات اليوم")
  render_cards(live_yt)

with tab_others:
  st.subheader("🟪 لينكد إن وتيك توك وإنستغرام")
  render_cards(live_other)

with tab_archive_all:
  st.subheader("🗄️ أرشيف الأخبار والمنشورات السابقة (أقدم من 24 ساعة)")
  st.caption(
      "كافة الأخبار والتقارير التي مر عليها أكثر من 24 ساعة تُحال تلقائياً إلى"
      " هنا وتبقى محفوظة بشكل دائم دون حذف."
  )

  search_archive = st.text_input(
      "🔍 ابحث في سجلات الأرشيف:", placeholder="ابحث في الأخبار السابقة..."
  )
  if search_archive.strip():
    q_s = search_archive.strip().lower()
    filtered_archive = [
        r
        for r in archive_records
        if q_s in r[2].lower() or q_s in r[6].lower() or q_s in r[7].lower()
    ]
    st.write(f"عُثر في الأرشيف على: **{len(filtered_archive)}** مادة مطابقة.")
    render_cards(filtered_archive, is_archive_view=True)
  else:
    render_cards(archive_records, is_archive_view=True)
