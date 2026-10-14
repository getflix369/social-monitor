from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

try:
  import streamlit as st
except ImportError:
  st = None

try:
  import google.generativeai as genai
except ImportError:
  genai = None

try:
  from duckduckgo_search import DDGS
except ImportError:
  DDGS = None

try:
  from bs4 import BeautifulSoup
except ImportError:
  BeautifulSoup = None

# =====================================================================
# 1. إعدادات النظام والثوابت الأساسية
# =====================================================================
REPO_DB_FILE = "morocco_justice_hub.db"
DB_FILE = os.path.join(tempfile.gettempdir(), "morocco_justice_hub_runtime.db")
ARCHIVE_JSON_FILE = "articles_archive.json"
CREDENTIALS_FILE = "credentials.json"
CUSTOM_TARGETS_FILE = "custom_targets.json"
MONITOR_STATE_FILE = "monitor_state.json"

DEFAULT_TG_TOKEN = "8806182263:AAFw5HbBup_TRif3FHvZP0QFYj0YPI4mb6c"
DEFAULT_TG_CHAT_ID = "1357905784"
GEMINI_MODEL_NAME = "gemini-3.5-flash-lite"

DEFAULT_JUDICIAL_QUERIES = [
    "المجلس الأعلى للسلطة القضائية المغرب",
    "القضاء بالمغرب",
    "العدالة بالمغرب",
    "النيابة العامة المغرب",
    "محكمة النقض المغرب",
]

JUDICIAL_CORE_TERMS = [
    "المجلس الأعلى للسلطة القضائية",
    "السلطة القضائية",
    "القضاء",
    "قضائي",
    "قضائية",
    "العدالة",
    "النيابة العامة",
    "محكمة النقض",
    "المحاكم",
    "محكمة",
    "قاضي",
    "قضاة",
    "وكيل الملك",
    "الوكيل العام",
    "محمد عبد النباوي",
    "رئاسة النيابة العامة",
    "هشام البلاوي",
    "وزارة العدل",
    "وزير العدل",
    "محكمة الاستئناف",
    "المحكمة الابتدائية",
    "المحكمة الإدارية",
    "المحكمة التجارية",
    "المعهد العالي للقضاء",
    "هيئة الحكم",
    "المفتشية العامة للشؤون القضائية",
]

MOROCCAN_PRESS_SITES = [
    {"domain": "hespress.com", "name": "هسبريس"},
    {"domain": "akhbarona.com", "name": "أخبارنا"},
    {"domain": "agadir24.info", "name": "أكادير 24"},
    {"domain": "kech24.com", "name": "كش 24"},
    {"domain": "alayam24.com", "name": "الأيام 24"},
    {"domain": "madar21.com", "name": "مدار 21"},
    {"domain": "sabahagadir.com", "name": "صباح أكادير"},
    {"domain": "goud.ma", "name": "كود"},
    {"domain": "assabah.ma", "name": "الصباح"},
    {"domain": "thevoice.ma", "name": "ذا فويس"},
    {"domain": "nadorcity.com", "name": "ناظورسيتي"},
    {"domain": "al3omk.com", "name": "العمق المغربي"},
    {"domain": "alyaoum24.com", "name": "اليوم 24"},
    {"domain": "rue20.com", "name": "زنقة 20"},
    {"domain": "le360.ma", "name": "Le360"},
    {"domain": "barlamane.com", "name": "برلمان.كوم"},
    {"domain": "tanja24.com", "name": "طنجة 24"},
]

YT_BYPASS_COOKIES = {
    "SOCS": "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg",
    "CONSENT": "PENDING+999",
}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar-MA,ar;q=0.9,fr-MA;q=0.8,fr;q=0.7,en;q=0.6",
}

INTERVAL_MAP = {
    "كل 15 دقيقة": 900,
    "كل ساعة": 3600,
    "كل 3 ساعات": 10800,
    "كل 6 ساعات": 21600,
    "كل 12 ساعة": 43200,
    "كل 24 ساعة": 86400,
}

ARABIC_MONTHS = {
    "يناير": 1,
    "فبراير": 2,
    "مارس": 3,
    "أبريل": 4,
    "ابريل": 4,
    "ماي": 5,
    "مايو": 5,
    "يونيو": 6,
    "يوليوز": 7,
    "يوليو": 7,
    "غشت": 8,
    "أغسطس": 8,
    "شتنبر": 9,
    "سبتمبر": 9,
    "أكتوبر": 10,
    "اكتوبر": 10,
    "نونبر": 11,
    "نوفمبر": 11,
    "دجنبر": 12,
    "ديسمبر": 12,
}

ENGLISH_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def compact_html(raw_html: str) -> str:
  """إزالة المسافات البادئة والأسطر الفارغة لمنع Markdown من تحويل HTML إلى كود نصي."""
  return "\n".join(
      line.strip() for line in str(raw_html).splitlines() if line.strip()
  )


def render_html(raw_html: str, target=None):
  cleaned = compact_html(raw_html)
  if target is not None:
    target.markdown(cleaned, unsafe_allow_html=True)
  elif st is not None:
    st.markdown(cleaned, unsafe_allow_html=True)


def clean_display_text(val: str) -> str:
  """تنظيف النصوص من أي بقايا HTML أو JSON أو أسطر متعددة قبل عرضها في البطاقات."""
  if not val:
    return ""
  txt = str(val).strip()
  txt = (
      re.sub(r"```(?:json|html)?", "", txt, flags=re.IGNORECASE)
      .replace("```", "")
      .strip()
  )
  if txt.startswith("{") and "summary" in txt:
    try:
      parsed = json.loads(txt)
      if isinstance(parsed, dict) and parsed.get("summary"):
        txt = str(parsed["summary"])
    except Exception:
      m = re.search(r'"summary"\s*:\s*"([^"]+)"', txt)
      if m:
        txt = m.group(1)
  txt = html.unescape(txt)
  txt = re.sub(r"<[^>]+>", " ", txt)
  txt = re.sub(r"[\r\n\t]+", " ", txt)
  txt = re.sub(r"\s+", " ", txt).strip()
  return txt


def build_rich_arabic_summary(
    title: str, snippet: str, platform: str, source_name: str
) -> str:
  """توليد ملخص عربي واضح ومفصل للمقال أو الفيديو أو المنشور في حال غياب ملخص ذكاء اصطناعي."""
  t_clean = clean_display_text(title)
  s_clean = clean_display_text(snippet)

  # إزالة تكرار العنوان من بداية المقتطف إن وجد
  if s_clean and t_clean and s_clean.startswith(t_clean[:30]):
    s_clean = s_clean[len(t_clean) :].lstrip(" -–—:•|.")

  # إزالة البادئات الزمنية مثل "14 أكتوبر 2026 —" من بداية الملخص
  s_clean = re.sub(
      r"^(\d{1,2}\s+[^\s]+\s+20\d{2}|[A-Za-z]{3,9}\s+\d{1,2},?\s+20\d{2}|\d+\s*(?:hours?|days?|minutes?|ساعات|ساعة|يوم|أيام|دقيقة)\s*(?:ago)?)\s*[-–—·•:]\s*",
      "",
      s_clean,
      flags=re.IGNORECASE,
  ).strip()

  plat_type_map = {
      "الصحف": "مقال صحفي منشور عبر",
      "فيسبوك": "منشور متداول على منصة فيسبوك عبر",
      "إكس": "تغريدة/منشور على منصة إكس (تويتر) عبر",
      "يوتيوب": "محتوى مرئي (فيديو) منشور على قناة يوتيوب",
      "أخرى": "منشور رقمي عبر شبكات التواصل الاجتماعي",
  }
  prefix_desc = plat_type_map.get(platform, "محتوى إعلامي مرصود عبر")
  src_label = clean_display_text(source_name or platform)

  if s_clean and len(s_clean) > 35 and s_clean.lower() != t_clean.lower():
    return f"{prefix_desc} ({src_label}): {s_clean}"
  return (
      f"{prefix_desc} ({src_label}) يتناول موضوع: «{t_clean}»، "
      "وذلك في إطار المتابعة الإعلامية المستمرة لمستجدات الشأن القضائي والعدالة بالمملكة المغربية."
  )


# =====================================================================
# 2. قفل التزامن المركزي لمنع تضارب SQLite والخيوط (Thread-Safety)
# =====================================================================
_MODULE_DB_LOCK = threading.RLock()
_MODULE_SCAN_LOCK = threading.Lock()


def _create_shared_runtime():
  return {
      "db_lock": _MODULE_DB_LOCK,
      "scan_lock": _MODULE_SCAN_LOCK,
      "stop_requested": False,
      "active_scan": None,
      "daemon_started": False,
      "bg_scanning": False,
      "last_done_mode": None,
      "last_done_count": 0,
      "last_done_ts": 0.0,
  }


if st is not None and hasattr(st, "cache_resource"):
  get_shared_runtime = st.cache_resource(_create_shared_runtime)
else:
  _FALLBACK_RUNTIME = _create_shared_runtime()

  def get_shared_runtime():
    return _FALLBACK_RUNTIME


def get_db_lock():
  try:
    return get_shared_runtime()["db_lock"]
  except Exception:
    return _MODULE_DB_LOCK


def get_scan_lock():
  try:
    return get_shared_runtime()["scan_lock"]
  except Exception:
    return _MODULE_SCAN_LOCK


def request_stop_scan():
  try:
    rt = get_shared_runtime()
    rt["stop_requested"] = True
  except Exception:
    pass
  try:
    if st is not None:
      st.session_state["stop_scan"] = True
  except Exception:
    pass


def clear_stop_scan():
  try:
    rt = get_shared_runtime()
    rt["stop_requested"] = False
  except Exception:
    pass
  try:
    if st is not None:
      st.session_state["stop_scan"] = False
  except Exception:
    pass


def is_stop_requested() -> bool:
  try:
    if get_shared_runtime().get("stop_requested", False):
      return True
  except Exception:
    pass
  try:
    if st is not None:
      return bool(st.session_state.get("stop_scan", False))
  except Exception:
    pass
  return False


# =====================================================================
# 3. إدارة قاعدة البيانات والأرشيف الدائم (محمية بالكامل ضد OperationalError)
# =====================================================================
REQUIRED_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "title": "TEXT DEFAULT ''",
    "summary": "TEXT DEFAULT ''",
    "source_name": "TEXT DEFAULT ''",
    "platform": "TEXT DEFAULT 'الصحف'",
    "url": "TEXT UNIQUE",
    "pub_date": "TEXT DEFAULT ''",
    "pub_timestamp": "REAL DEFAULT 0",
    "sentiment": "TEXT DEFAULT 'محايد'",
    "category": "TEXT DEFAULT 'شؤون قضائية'",
    "relevance_score": "INTEGER DEFAULT 85",
    "is_custom_target": "INTEGER DEFAULT 0",
    "raw_snippet": "TEXT DEFAULT ''",
    "created_at": "REAL DEFAULT 0",
}

INSERT_COLUMN_NAMES = [
    "title",
    "summary",
    "source_name",
    "platform",
    "url",
    "pub_date",
    "pub_timestamp",
    "sentiment",
    "category",
    "relevance_score",
    "is_custom_target",
    "raw_snippet",
    "created_at",
]


def _open_sqlite_conn():
  conn = sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)
  try:
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA journal_mode=MEMORY;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
  except Exception:
    pass
  return conn


def _create_fresh_articles_table(c):
  c.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            source_name TEXT DEFAULT '',
            platform TEXT DEFAULT 'الصحف',
            url TEXT UNIQUE,
            pub_date TEXT DEFAULT '',
            pub_timestamp REAL DEFAULT 0,
            sentiment TEXT DEFAULT 'محايد',
            category TEXT DEFAULT 'شؤون قضائية',
            relevance_score INTEGER DEFAULT 85,
            is_custom_target INTEGER DEFAULT 0,
            raw_snippet TEXT DEFAULT '',
            created_at REAL DEFAULT 0
        )
        """)


def _rebuild_articles_table_safely(conn):
  c = conn.cursor()
  try:
    c.execute("PRAGMA table_info(articles)")
    old_info = c.fetchall()
    old_cols = [r[1] for r in old_info]
    if not old_cols:
      _create_fresh_articles_table(c)
      conn.commit()
      return

    c.execute("DROP TABLE IF EXISTS articles_migration_tmp")
    c.execute("ALTER TABLE articles RENAME TO articles_migration_tmp")
    _create_fresh_articles_table(c)

    common_cols = [col for col in INSERT_COLUMN_NAMES if col in old_cols]
    if common_cols:
      cols_csv = ", ".join(common_cols)
      c.execute(
          f"INSERT OR IGNORE INTO articles ({cols_csv}) "
          f"SELECT {cols_csv} FROM articles_migration_tmp"
      )
    c.execute("DROP TABLE IF EXISTS articles_migration_tmp")
    conn.commit()
  except Exception:
    try:
      c.execute("DROP TABLE IF EXISTS articles")
      _create_fresh_articles_table(c)
      conn.commit()
    except Exception:
      pass


def _ensure_schema_on_conn(conn):
  c = conn.cursor()
  _create_fresh_articles_table(c)
  c.execute("PRAGMA table_info(articles)")
  info_rows = c.fetchall()
  existing_cols = {row[1] for row in info_rows}

  has_incompatible_notnull = any(
      (row[1] not in REQUIRED_COLUMNS and int(row[3]) == 1 and row[4] is None)
      for row in info_rows
  )
  if has_incompatible_notnull:
    _rebuild_articles_table_safely(conn)
    c.execute("PRAGMA table_info(articles)")
    existing_cols = {row[1] for row in c.fetchall()}

  for col_name, col_def in REQUIRED_COLUMNS.items():
    if col_name not in existing_cols and col_name != "id":
      col_def_clean = col_def.replace("UNIQUE", "").strip()
      try:
        c.execute(f"ALTER TABLE articles ADD COLUMN {col_name} {col_def_clean}")
      except Exception:
        pass

  try:
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_pub_ts ON articles(pub_timestamp DESC)"
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_platform ON articles(platform)")
  except Exception:
    pass
  conn.commit()


def init_db():
  lock = get_db_lock()
  with lock:
    if (
        not os.path.exists(DB_FILE)
        and os.path.exists(REPO_DB_FILE)
        and os.path.getsize(REPO_DB_FILE) > 0
    ):
      try:
        shutil.copyfile(REPO_DB_FILE, DB_FILE)
      except Exception:
        pass

    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.close()
    except sqlite3.DatabaseError:
      try:
        if os.path.exists(DB_FILE):
          os.remove(DB_FILE)
        conn = _open_sqlite_conn()
        _ensure_schema_on_conn(conn)
        conn.close()
      except Exception:
        pass
    except Exception:
      pass
    restore_db_from_json_if_needed()


def sync_db_to_json(extra_items: list = None):
  lock = get_db_lock()
  with lock:
    merged_by_url = {}
    if os.path.exists(ARCHIVE_JSON_FILE):
      try:
        with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
          existing_json = json.load(f)
        if isinstance(existing_json, list):
          for item in existing_json:
            if isinstance(item, dict) and item.get("url"):
              merged_by_url[item["url"]] = item
      except Exception:
        pass

    if extra_items:
      for item in extra_items:
        if isinstance(item, dict) and item.get("url"):
          merged_by_url[item["url"]] = item

    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute(
          "SELECT title, summary, source_name, platform, url, pub_date, "
          "pub_timestamp, sentiment, category, relevance_score, "
          "is_custom_target, raw_snippet, created_at "
          "FROM articles ORDER BY pub_timestamp DESC LIMIT 1500"
      )
      for r in c.fetchall():
        d = dict(r)
        if d.get("url"):
          merged_by_url[d["url"]] = d
      conn.close()
    except Exception:
      pass

    if merged_by_url:
      sorted_rows = sorted(
          merged_by_url.values(),
          key=lambda x: float(x.get("pub_timestamp", 0)),
          reverse=True,
      )[:1500]
      try:
        tmp_file = f"{ARCHIVE_JSON_FILE}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
          json.dump(sorted_rows, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, ARCHIVE_JSON_FILE)
      except Exception:
        pass

    if os.path.exists(DB_FILE):
      try:
        shutil.copyfile(DB_FILE, REPO_DB_FILE)
      except Exception:
        pass


def restore_db_from_json_if_needed():
  if not os.path.exists(ARCHIVE_JSON_FILE):
    return
  lock = get_db_lock()
  with lock:
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      c = conn.cursor()
      c.execute("SELECT COUNT(*) FROM articles")
      count = c.fetchone()[0]
      if count == 0:
        with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
          items = json.load(f)
        if isinstance(items, list) and items:
          for item in items:
            try:
              t_clean = clean_display_text(item.get("title", ""))
              s_clean = clean_display_text(item.get("summary", ""))
              plat = item.get("platform", "الصحف")
              src = clean_display_text(item.get("source_name", "") or plat)
              raw_s = clean_display_text(item.get("raw_snippet", ""))
              if not s_clean or s_clean == t_clean or len(s_clean) < 25:
                s_clean = build_rich_arabic_summary(t_clean, raw_s, plat, src)
              pub_ts = float(item.get("pub_timestamp", time.time() - 3600))
              pub_dt = item.get("pub_date", "")
              if not pub_dt:
                pub_dt = datetime.fromtimestamp(
                    pub_ts, tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M")

              c.execute(
                  """
                                INSERT OR IGNORE INTO articles (
                                    title, summary, source_name, platform, url,
                                    pub_date, pub_timestamp, sentiment, category,
                                    relevance_score, is_custom_target, raw_snippet, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                  (
                      t_clean,
                      s_clean,
                      src,
                      plat,
                      item.get("url", ""),
                      pub_dt,
                      pub_ts,
                      item.get("sentiment", "محايد"),
                      item.get("category", "شؤون قضائية"),
                      int(item.get("relevance_score", 85)),
                      int(item.get("is_custom_target", 0)),
                      raw_s,
                      float(item.get("created_at", time.time())),
                  ),
              )
            except Exception:
              continue
          conn.commit()
      conn.close()
    except Exception:
      pass


def fetch_articles_from_db():
  lock = get_db_lock()
  with lock:
    db_rows = []
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute(
          "SELECT * FROM articles ORDER BY pub_timestamp DESC, id DESC LIMIT"
          " 1500"
      )
      db_rows = [dict(r) for r in c.fetchall()]
      conn.close()
    except Exception:
      pass

    if db_rows:
      return db_rows

    if os.path.exists(ARCHIVE_JSON_FILE):
      try:
        with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
          data = json.load(f)
        if isinstance(data, list):
          return sorted(
              data,
              key=lambda x: float(x.get("pub_timestamp", 0)),
              reverse=True,
          )
      except Exception:
        pass
    return []


# =====================================================================
# 4. إدارة الإعدادات والروابط المخصصة وحالة الرصد الدوري
# =====================================================================
def load_credentials():
  cfg = {
      "gemini_api_key": "",
      "telegram_bot_token": DEFAULT_TG_TOKEN,
      "telegram_chat_id": DEFAULT_TG_CHAT_ID,
      "keywords_input": "",
      "auto_monitor": True,
      "monitor_interval": "كل 15 دقيقة",
  }
  if os.path.exists(CREDENTIALS_FILE):
    try:
      with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        saved = json.load(f)
      if isinstance(saved, dict):
        cfg.update(saved)
    except Exception:
      pass

  try:
    if st is not None and hasattr(st, "secrets"):
      if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"]:
        cfg["gemini_api_key"] = str(st.secrets["GEMINI_API_KEY"]).strip()
      if (
          "TELEGRAM_BOT_TOKEN" in st.secrets
          and st.secrets["TELEGRAM_BOT_TOKEN"]
      ):
        cfg["telegram_bot_token"] = str(
            st.secrets["TELEGRAM_BOT_TOKEN"]
        ).strip()
      if "TELEGRAM_CHAT_ID" in st.secrets and st.secrets["TELEGRAM_CHAT_ID"]:
        cfg["telegram_chat_id"] = str(st.secrets["TELEGRAM_CHAT_ID"]).strip()
  except Exception:
    pass

  env_gemini = os.environ.get("GEMINI_API_KEY", "").strip()
  if env_gemini:
    cfg["gemini_api_key"] = env_gemini
  env_tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
  if env_tg_token:
    cfg["telegram_bot_token"] = env_tg_token
  env_tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
  if env_tg_chat:
    cfg["telegram_chat_id"] = env_tg_chat

  if not cfg.get("telegram_bot_token"):
    cfg["telegram_bot_token"] = DEFAULT_TG_TOKEN
  if not cfg.get("telegram_chat_id"):
    cfg["telegram_chat_id"] = DEFAULT_TG_CHAT_ID
  if cfg.get("monitor_interval") not in INTERVAL_MAP:
    cfg["monitor_interval"] = "كل 15 دقيقة"
  return cfg


def save_credentials(cfg):
  try:
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
      json.dump(cfg, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


def load_custom_targets():
  default_targets = [
      {"url": "https://www.hespress.com", "keyword": ""},
      {"url": "https://www.youtube.com/@Hespress", "keyword": ""},
  ]
  if os.path.exists(CUSTOM_TARGETS_FILE):
    try:
      with open(CUSTOM_TARGETS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
      if isinstance(data, list):
        cleaned = []
        for item in data:
          if isinstance(item, dict) and item.get("url", "").strip():
            cleaned.append({
                "url": item["url"].strip(),
                "keyword": item.get("keyword", "").strip(),
            })
        return cleaned
    except Exception:
      pass
  return default_targets


def save_custom_targets(targets):
  try:
    cleaned = [
        {"url": t.get("url", "").strip(), "keyword": t.get("keyword", "").strip()}
        for t in targets
        if t.get("url", "").strip()
    ]
    with open(CUSTOM_TARGETS_FILE, "w", encoding="utf-8") as f:
      json.dump(cleaned, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


def load_monitor_state():
  state = {"last_auto_run": 0.0, "last_auto_added": 0, "total_auto_cycles": 0}
  if os.path.exists(MONITOR_STATE_FILE):
    try:
      with open(MONITOR_STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
      if isinstance(data, dict):
        state.update(data)
    except Exception:
      pass
  return state


def save_monitor_state(state):
  try:
    with open(MONITOR_STATE_FILE, "w", encoding="utf-8") as f:
      json.dump(state, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


# =====================================================================
# 5. استخراج ومعالجة تواريخ النشر الحقيقية (للصحف، يوتيوب، فيسبوك، إكس، وتيك توك)
# =====================================================================
def extract_date_from_url_or_text(
    url: str, text_snippet: str = "", raw_date: str = "", fallback_offset_sec: int = 3600
):
  now_ts = time.time()

  # 1. إذا كان هناك تاريخ مباشر، نحلله أولا
  if raw_date and str(raw_date).strip():
    d_str, d_ts = parse_any_date(str(raw_date).strip(), fallback_offset_sec=0)
    if d_ts > 0 and abs(now_ts - d_ts) > 5:
      return d_str, d_ts

  # 2. استخراج التوقيت الدقيق من معرف تغريدة إكس/تويتر (Snowflake ID)
  if url:
    m_x = re.search(r"(?:x\.com|twitter\.com)/[^/]+/status/(\d{15,20})", url)
    if m_x:
      try:
        snowflake_id = int(m_x.group(1))
        tweet_ts = ((snowflake_id >> 22) + 1288834974657) / 1000.0
        if 1288834974 < tweet_ts <= now_ts + 3600:
          tweet_ts = min(tweet_ts, now_ts)
          return (
              datetime.fromtimestamp(tweet_ts, tz=timezone.utc).strftime(
                  "%Y-%m-%d %H:%M"
              ),
              tweet_ts,
          )
      except Exception:
        pass

    # 3. استخراج التوقيت الدقيق من معرف فيديو تيك توك (64-bit ID)
    m_tt = re.search(r"tiktok\.com/.*/video/(\d{15,22})", url)
    if m_tt:
      try:
        tt_id = int(m_tt.group(1))
        tt_ts = float(tt_id >> 32)
        if 1450000000 < tt_ts <= now_ts + 3600:
          tt_ts = min(tt_ts, now_ts)
          return (
              datetime.fromtimestamp(tt_ts, tz=timezone.utc).strftime(
                  "%Y-%m-%d %H:%M"
              ),
              tt_ts,
          )
      except Exception:
        pass

    # 4. استخراج التاريخ من مسار الرابط الإخباري (مثل /2026/10/14/)
    m_url_date = re.search(r"/(20\d{2})/(\d{1,2})/(\d{1,2})/", url)
    if m_url_date:
      try:
        dt = datetime(
            int(m_url_date.group(1)),
            int(m_url_date.group(2)),
            int(m_url_date.group(3)),
            12,
            0,
            tzinfo=timezone.utc,
        )
        ts = min(dt.timestamp(), now_ts)
        return dt.strftime("%Y-%m-%d %H:%M"), ts
      except Exception:
        pass

  # 5. استخراج التاريخ من بداية أو متن مقتطف البحث (مثل "14 أكتوبر 2026" أو "Oct 14, 2026" أو "منذ 3 ساعات")
  if text_snippet:
    return parse_any_date(text_snippet[:120], fallback_offset_sec=fallback_offset_sec)

  return parse_any_date("", fallback_offset_sec=fallback_offset_sec)


def parse_any_date(date_str: str, fallback_offset_sec: int = 3600):
  now_ts = time.time()
  if not date_str or not str(date_str).strip():
    ts = now_ts - fallback_offset_sec
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M"), ts

  raw = str(date_str).strip()

  try:
    dt = parsedate_to_datetime(raw)
    if dt.tzinfo is None:
      dt = dt.replace(tzinfo=timezone.utc)
    ts = min(dt.timestamp(), now_ts)
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        ts,
    )
  except Exception:
    pass

  try:
    iso_clean = raw.replace("Z", "+00:00")
    dt = datetime.fromisoformat(iso_clean)
    if dt.tzinfo is None:
      dt = dt.replace(tzinfo=timezone.utc)
    ts = min(dt.timestamp(), now_ts)
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        ts,
    )
  except Exception:
    pass

  rel_lower = raw.lower()

  # عبارات زمنية نسبية مختصرة مثل "3h ago", "2d ago", "45m ago"
  m_short_rel = re.search(
      r"\b(\d+)\s*(s|sec|secs|m|min|mins|h|hr|hrs|d|day|days|w|wk|wks)\b(?:\s*ago)?",
      rel_lower,
  )
  if m_short_rel and ("ago" in rel_lower or len(raw) < 25):
    n = int(m_short_rel.group(1))
    u = m_short_rel.group(2)
    if u.startswith("s"):
      ts = now_ts - n
    elif u.startswith("m"):
      ts = now_ts - n * 60
    elif u.startswith("h"):
      ts = now_ts - n * 3600
    elif u.startswith("d"):
      ts = now_ts - n * 86400
    else:
      ts = now_ts - n * 7 * 86400
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        ts,
    )

  num_match = re.search(r"(\d+)", rel_lower)
  num = int(num_match.group(1)) if num_match else 1

  if any(
      w in rel_lower
      for w in ["ثانية", "ثواني", "second", "just now", "الآن", "قبل لحظات"]
  ):
    ts = now_ts - 60
  elif any(
      w in rel_lower for w in ["دقيقة", "دقائق", "دقيقتين", "minute"]
  ):
    if "دقيقتين" in rel_lower:
      num = 2
    ts = now_ts - (num * 60)
  elif any(w in rel_lower for w in ["ساعة", "ساعات", "ساعتين", "hour"]):
    if "ساعتين" in rel_lower:
      num = 2
    ts = now_ts - (num * 3600)
  elif any(
      w in rel_lower for w in ["يوم", "أيام", "يومين", "أمس", "yesterday"]
  ):
    if "يومين" in rel_lower:
      num = 2
    elif "أمس" in rel_lower or "yesterday" in rel_lower:
      num = 1
    ts = now_ts - (num * 86400)
  elif any(w in rel_lower for w in ["أسبوع", "أسابيع", "اسبوع", "week"]):
    ts = now_ts - (num * 7 * 86400)
  elif any(w in rel_lower for w in ["شهر", "أشهر", "شهور", "month"]):
    ts = now_ts - (num * 30 * 86400)
  elif any(w in rel_lower for w in ["سنة", "سنوات", "عام", "year"]):
    ts = now_ts - (num * 365 * 86400)
  else:
    # صيغة تاريخ عربي مثل "14 أكتوبر 2026"
    for ar_m, m_idx in ARABIC_MONTHS.items():
      m_ar = re.search(rf"(\d{{1,2}})\s+{ar_m}\s+(20\d{{2}})", raw)
      if m_ar:
        try:
          dt = datetime(
              int(m_ar.group(2)),
              m_idx,
              int(m_ar.group(1)),
              12,
              0,
              tzinfo=timezone.utc,
          )
          ts = min(dt.timestamp(), now_ts)
          return dt.strftime("%Y-%m-%d %H:%M"), ts
        except Exception:
          pass

    # صيغة تاريخ إنجليزي مثل "Oct 14, 2026" أو "14 Oct 2026"
    for en_m, m_idx in ENGLISH_MONTHS.items():
      m_en1 = re.search(
          rf"\b{en_m}[a-z]*\s+(\d{{1,2}}),?\s+(20\d{{2}})", rel_lower
      )
      m_en2 = re.search(
          rf"(\d{{1,2}})\s+{en_m}[a-z]*,?\s+(20\d{{2}})", rel_lower
      )
      m_en = m_en1 or m_en2
      if m_en:
        try:
          dt = datetime(
              int(m_en.group(2)),
              m_idx,
              int(m_en.group(1)),
              12,
              0,
              tzinfo=timezone.utc,
          )
          ts = min(dt.timestamp(), now_ts)
          return dt.strftime("%Y-%m-%d %H:%M"), ts
        except Exception:
          pass

    m_ymd = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", raw)
    if m_ymd:
      try:
        dt = datetime(
            int(m_ymd.group(1)),
            int(m_ymd.group(2)),
            int(m_ymd.group(3)),
            12,
            0,
            tzinfo=timezone.utc,
        )
        ts = min(dt.timestamp(), now_ts)
        return dt.strftime("%Y-%m-%d %H:%M"), ts
      except Exception:
        pass
    ts = now_ts - fallback_offset_sec

  dt_fmt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
  return dt_fmt, ts


def format_relative_arabic(pub_ts: float) -> str:
  diff = max(0, int(time.time() - float(pub_ts or 0)))
  if diff < 90:
    return "منذ لحظات"
  if diff < 3600:
    return f"منذ {diff // 60} دقيقة"
  if diff < 86400:
    return f"منذ {diff // 3600} ساعة"
  return f"منذ {diff // 86400} يوم"


# =====================================================================
# 6. محركات الرصد الذكي (الصحف، فيسبوك، إكس، يوتيوب، أخرى، والمخصص)
# =====================================================================
def build_search_queries(keywords_input: str):
  custom_kws = [
      k.strip()
      for k in re.split(r"[,،\n]+", str(keywords_input or ""))
      if k.strip()
  ]
  if custom_kws:
    queries = []
    for kw in custom_kws:
      queries.append(kw)
      if "المغرب" not in kw and "القضا" not in kw and "العدالة" not in kw:
        queries.append(f"{kw} القضاء المغرب")
    return queries
  return list(DEFAULT_JUDICIAL_QUERIES)


def is_relevant_item(
    title: str,
    snippet: str,
    keywords_input: str,
    is_target: bool = False,
    from_judicial_query: bool = False,
) -> bool:
  text = f"{title} {snippet}".lower()
  custom_kws = [
      k.strip().lower()
      for k in re.split(r"[,،\n]+", str(keywords_input or ""))
      if k.strip()
  ]
  if custom_kws:
    return any(k in text for k in custom_kws)
  if is_target or from_judicial_query:
    return True
  return any(term.lower() in text for term in JUDICIAL_CORE_TERMS)


def clean_html_text(raw_html: str) -> str:
  return clean_display_text(raw_html)


def decode_js_escaped_text(raw_str: str) -> str:
  if not raw_str:
    return ""
  s = re.sub(
      r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), str(raw_str)
  )
  s = s.replace('\\"', '"').replace("\\/", "/").replace("\\n", " ")
  return clean_display_text(s)


def parse_rss_xml(
    xml_bytes: bytes,
    default_platform: str,
    default_source: str = "",
    fallback_offset: int = 1800,
):
  results = []
  try:
    root = ET.fromstring(xml_bytes)
  except Exception:
    return results

  ns = {
      "atom": "http://www.w3.org/2005/Atom",
      "yt": "http://www.youtube.com/xml/schemas/2015",
      "media": "http://search.yahoo.com/mrss/",
  }

  for item in root.findall(".//item"):
    title = clean_html_text(item.findtext("title") or "")
    link = (item.findtext("link") or "").strip()
    desc = clean_html_text(item.findtext("description") or "")
    pub_raw = (
        item.findtext("pubDate")
        or item.findtext("{http://purl.org/dc/elements/1.1/}date")
        or ""
    )
    source_el = item.find("source")
    source_name = (
        clean_html_text(source_el.text)
        if source_el is not None and source_el.text
        else default_source
    )
    if not source_name and " - " in title:
      parts = title.rsplit(" - ", 1)
      if len(parts[1]) < 35:
        title, source_name = parts[0].strip(), parts[1].strip()

    if not title or not link:
      continue
    pub_str, pub_ts = extract_date_from_url_or_text(
        link, desc, pub_raw, fallback_offset_sec=fallback_offset
    )
    results.append({
        "title": title,
        "url": link,
        "raw_snippet": desc[:600] if desc else title,
        "source_name": source_name or default_platform,
        "platform": default_platform,
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
    })

  for entry in root.findall(".//atom:entry", ns):
    title = clean_html_text(
        entry.findtext("atom:title", default="", namespaces=ns)
    )
    link_el = entry.find("atom:link", ns)
    link = link_el.attrib.get("href", "").strip() if link_el is not None else ""
    pub_raw = entry.findtext(
        "atom:published", default="", namespaces=ns
    ) or entry.findtext("atom:updated", default="", namespaces=ns)
    author_name = entry.findtext(
        "atom:author/atom:name", default=default_source, namespaces=ns
    )
    media_desc = entry.findtext(
        "media:group/media:description", default="", namespaces=ns
    )
    snippet_txt = clean_html_text(media_desc) or title
    if not title or not link:
      continue
    pub_str, pub_ts = extract_date_from_url_or_text(
        link, snippet_txt, pub_raw, fallback_offset_sec=fallback_offset
    )
    results.append({
        "title": title,
        "url": link,
        "raw_snippet": snippet_txt[:600],
        "source_name": clean_html_text(
            author_name or default_source or default_platform
        ),
        "platform": default_platform,
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
    })

  return results


def scrape_moroccan_press(keywords_input: str, progress_cb=None):
  items = []
  seen_urls = set()
  queries = build_search_queries(keywords_input)

  batch_size = 4
  site_batches = [
      MOROCCAN_PRESS_SITES[i : i + batch_size]
      for i in range(0, len(MOROCCAN_PRESS_SITES), batch_size)
  ]
  total_steps = len(queries) + len(site_batches)
  step = 0

  for q in queries:
    if is_stop_requested():
      break
    step += 1
    if progress_cb:
      progress_cb(
          min(0.95, step / max(1, total_steps)), f"رصد الصحافة الوطنية: {q}"
      )
    rss_url = (
        "https://news.google.com/rss/search?q="
        f"{urllib.parse.quote(q + ' when:7d')}&hl=ar&gl=MA&ceid=MA:ar"
    )
    try:
      r = requests.get(rss_url, headers=DEFAULT_HEADERS, timeout=10)
      if r.status_code == 200:
        for entry in parse_rss_xml(r.content, "الصحف"):
          if entry["url"] not in seen_urls and is_relevant_item(
              entry["title"],
              entry["raw_snippet"],
              keywords_input,
              from_judicial_query=True,
          ):
            seen_urls.add(entry["url"])
            items.append(entry)
    except Exception:
      pass

  core_kw = (
      queries[0]
      if keywords_input.strip()
      else "(القضاء OR العدالة OR المحكمة OR النيابة العامة OR السلطة القضائية)"
  )
  for batch in site_batches:
    if is_stop_requested():
      break
    step += 1
    names_label = "، ".join(s["name"] for s in batch[:2])
    if progress_cb:
      progress_cb(
          min(0.98, step / max(1, total_steps)),
          f"مسح الصحف المغربية ({names_label}...)",
      )
    sites_expr = " OR ".join(f"site:{s['domain']}" for s in batch)
    full_q = f"({sites_expr}) {core_kw} when:7d"
    rss_url = (
        "https://news.google.com/rss/search?q="
        f"{urllib.parse.quote(full_q)}&hl=ar&gl=MA&ceid=MA:ar"
    )
    try:
      r = requests.get(rss_url, headers=DEFAULT_HEADERS, timeout=10)
      if r.status_code == 200:
        for entry in parse_rss_xml(r.content, "الصحف"):
          if entry["url"] not in seen_urls and is_relevant_item(
              entry["title"],
              entry["raw_snippet"],
              keywords_input,
              from_judicial_query=True,
          ):
            seen_urls.add(entry["url"])
            items.append(entry)
    except Exception:
      pass

  return items


def _extract_yt_renderers_from_html(html_text: str):
  """استخراج الفيديوهات مع عنوانها، اسم القناة، تاريخ النشر، والوصف المختصر من صفحة يوتيوب."""
  results = []
  chunks = html_text.split('"videoRenderer":')[1:]
  for chunk in chunks[:20]:
    vid_m = re.search(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', chunk)
    title_m = re.search(
        r'"title"\s*:\s*\{"runs"\s*:\s*\[\{"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
        chunk,
    )
    if not vid_m or not title_m:
      continue
    vid = vid_m.group(1)
    title = decode_js_escaped_text(title_m.group(1))
    pub_m = re.search(
        r'"publishedTimeText"\s*:\s*\{"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"',
        chunk,
    )
    pub_rel = decode_js_escaped_text(pub_m.group(1)) if pub_m else ""
    owner_m = re.search(
        r'"ownerText"\s*:\s*\{"runs"\s*:\s*\[\{"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
        chunk,
    )
    channel_name = (
        decode_js_escaped_text(owner_m.group(1)) if owner_m else "YouTube"
    )
    desc_runs = re.findall(
        r'"detailedMetadataSnippets".*?"snippetText"\s*:\s*\{"runs"\s*:\s*\[(.*?)\]\s*\}',
        chunk,
    )
    desc_text = ""
    if desc_runs:
      parts = re.findall(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', desc_runs[0])
      desc_text = decode_js_escaped_text(" ".join(parts))

    results.append({
        "vid": vid,
        "title": title,
        "pub_rel": pub_rel,
        "channel_name": channel_name,
        "desc": desc_text or title,
    })
  return results


def scrape_youtube_platform(keywords_input: str, progress_cb=None):
  items = []
  seen_urls = set()
  queries = build_search_queries(keywords_input)[:4]

  for idx, q in enumerate(queries):
    if is_stop_requested():
      break
    if progress_cb:
      progress_cb((idx + 1) / max(1, len(queries)), f"مسح يوتيوب: {q}")
    search_url = (
        "https://www.youtube.com/results?search_query="
        f"{urllib.parse.quote(q)}&sp=CAI%253D"
    )
    try:
      r = requests.get(
          search_url,
          headers=DEFAULT_HEADERS,
          cookies=YT_BYPASS_COOKIES,
          timeout=12,
      )
      if r.status_code == 200:
        for v in _extract_yt_renderers_from_html(r.text):
          v_url = f"https://www.youtube.com/watch?v={v['vid']}"
          if v_url in seen_urls:
            continue
          if not is_relevant_item(
              v["title"],
              v["desc"],
              keywords_input,
              from_judicial_query=True,
          ):
            continue
          pub_str, pub_ts = extract_date_from_url_or_text(
              v_url, v["desc"], v["pub_rel"], fallback_offset_sec=3600
          )
          seen_urls.add(v_url)
          items.append({
              "title": v["title"],
              "url": v_url,
              "raw_snippet": v["desc"],
              "source_name": f"قناة {v['channel_name']}",
              "platform": "يوتيوب",
              "pub_date": pub_str,
              "pub_timestamp": pub_ts,
          })
    except Exception:
      pass

  return items


def _scrape_yahoo_and_ddg_html(
    query: str,
    platform_label: str,
    allowed_domains: list,
    keywords_input: str,
    seen_urls: set,
):
  """جلب مباشر لمنشورات فيسبوك وإكس وتيك توك عبر محركات Yahoo وDuckDuckGo HTML التي لا تحظر السحابة."""
  found = []

  # 1) محرك بحث Yahoo HTML
  yahoo_url = f"https://search.yahoo.com/search?p={urllib.parse.quote(query)}&n=15"
  try:
    ry = requests.get(yahoo_url, headers=DEFAULT_HEADERS, timeout=10)
    if ry.status_code == 200 and BeautifulSoup is not None:
      soup = BeautifulSoup(ry.text, "html.parser")
      for div in soup.select("div.algo, div.Sr"):
        a_el = div.select_one("h3 a, a")
        if not a_el:
          continue
        href = a_el.get("href", "")
        if "RU=" in href:
          m_ru = re.search(r"/RU=([^/]+)/RK=", href)
          if m_ru:
            href = urllib.parse.unquote(m_ru.group(1))
        href = href.strip()
        if not href or href in seen_urls:
          continue
        if allowed_domains and not any(d in href.lower() for d in allowed_domains):
          continue
        title = clean_html_text(a_el.get_text(" ", strip=True))
        comp_text = div.select_one("div.compText, p")
        snippet = (
            clean_html_text(comp_text.get_text(" ", strip=True))
            if comp_text
            else title
        )
        time_span = div.select_one("span.fc-falcon, span.s-time")
        raw_dt = (
            clean_html_text(time_span.get_text(" ", strip=True))
            if time_span
            else ""
        )
        if not title or not is_relevant_item(
            title, snippet, keywords_input, from_judicial_query=True
        ):
          continue
        pub_str, pub_ts = extract_date_from_url_or_text(
            href, snippet, raw_dt, fallback_offset_sec=3600
        )
        seen_urls.add(href)
        found.append({
            "title": title,
            "url": href,
            "raw_snippet": snippet,
            "source_name": platform_label,
            "platform": platform_label,
            "pub_date": pub_str,
            "pub_timestamp": pub_ts,
        })
  except Exception:
    pass

  # 2) محرك بحث DuckDuckGo HTML
  ddg_html_url = "https://html.duckduckgo.com/html/"
  try:
    rd = requests.post(
        ddg_html_url,
        data={"q": query},
        headers=DEFAULT_HEADERS,
        timeout=10,
    )
    if rd.status_code == 200 and BeautifulSoup is not None:
      soup = BeautifulSoup(rd.text, "html.parser")
      for res_div in soup.select("div.result, div.web-result"):
        a_el = res_div.select_one("a.result__a")
        if not a_el:
          continue
        href = a_el.get("href", "").strip()
        if "uddg=" in href:
          parsed_qs = urllib.parse.parse_qs(
              urllib.parse.urlparse(href).query
          )
          if "uddg" in parsed_qs:
            href = parsed_qs["uddg"][0]
        if not href or href in seen_urls:
          continue
        if allowed_domains and not any(d in href.lower() for d in allowed_domains):
          continue
        title = clean_html_text(a_el.get_text(" ", strip=True))
        snip_el = res_div.select_one("a.result__snippet, div.result__snippet")
        snippet = (
            clean_html_text(snip_el.get_text(" ", strip=True))
            if snip_el
            else title
        )
        if not title or not is_relevant_item(
            title, snippet, keywords_input, from_judicial_query=True
        ):
          continue
        pub_str, pub_ts = extract_date_from_url_or_text(
            href, snippet, "", fallback_offset_sec=3600
        )
        seen_urls.add(href)
        found.append({
            "title": title,
            "url": href,
            "raw_snippet": snippet,
            "source_name": platform_label,
            "platform": platform_label,
            "pub_date": pub_str,
            "pub_timestamp": pub_ts,
        })
  except Exception:
    pass

  return found


def _multi_engine_social_search(
    platform_label: str,
    site_domains: list,
    keywords_input: str,
    progress_cb=None,
):
  items = []
  seen_urls = set()
  queries = build_search_queries(keywords_input)[:3]

  for idx, q in enumerate(queries):
    if is_stop_requested():
      break
    if progress_cb:
      progress_cb(
          (idx + 1) / max(1, len(queries) + 1),
          f"مسح {platform_label}: {q}",
      )

    # 1) فحص محركات Yahoo HTML + DuckDuckGo HTML + Bing RSS لكل نطاق
    for d in site_domains[:2]:
      if is_stop_requested():
        break
      site_q = f"site:{d} {q}"

      # أ. Yahoo & DDG HTML
      html_hits = _scrape_yahoo_and_ddg_html(
          site_q, platform_label, site_domains, keywords_input, seen_urls
      )
      items.extend(html_hits)

      # ب. Bing Search & News RSS
      for bing_base in [
          "https://www.bing.com/search?q=",
          "https://www.bing.com/news/search?q=",
      ]:
        bing_rss = f"{bing_base}{urllib.parse.quote(site_q)}&format=rss"
        try:
          r = requests.get(bing_rss, headers=DEFAULT_HEADERS, timeout=9)
          if r.status_code == 200 and b"<item>" in r.content:
            for entry in parse_rss_xml(
                r.content,
                platform_label,
                default_source=platform_label,
                fallback_offset=3600,
            ):
              if entry["url"] not in seen_urls and is_relevant_item(
                  entry["title"],
                  entry["raw_snippet"],
                  keywords_input,
                  from_judicial_query=True,
              ):
                seen_urls.add(entry["url"])
                items.append(entry)
        except Exception:
          pass

    # 2) مكتبة DDGS باستعلام مباشر نظيف بدون أقواس معقدة
    if DDGS is not None and not is_stop_requested():
      for d in site_domains[:2]:
        try:
          with DDGS() as ddgs:
            ddg_q = f"site:{d} {q}"
            for res in ddgs.text(ddg_q, max_results=10):
              href = (res.get("href") or res.get("url") or "").strip()
              title = clean_html_text(res.get("title") or "")
              body = clean_html_text(res.get("body") or "")
              if not href or href in seen_urls:
                continue
              if not is_relevant_item(
                  title, body, keywords_input, from_judicial_query=True
              ):
                continue
              pub_str, pub_ts = extract_date_from_url_or_text(
                  href, body, "", fallback_offset_sec=4200
              )
              seen_urls.add(href)
              items.append({
                  "title": title or body[:95],
                  "url": href,
                  "raw_snippet": body or title,
                  "source_name": platform_label,
                  "platform": platform_label,
                  "pub_date": pub_str,
                  "pub_timestamp": pub_ts,
              })
        except Exception:
          pass

  # 3) تغطية Google News RSS الواسعة للمنشورات والتدوينات والتغريدات القضائية المتداولة
  if not is_stop_requested():
    platform_ar_queries = {
        "فيسبوك": [
            '(القضاء OR العدالة OR المحكمة OR "المجلس الأعلى للسلطة القضائية") (فيسبوك OR فايسبوك OR "تدوينة" OR "صفحة") المغرب',
            'site:facebook.com القضاء المغرب',
        ],
        "إكس": [
            '(القضاء OR العدالة OR المحكمة OR "السلطة القضائية") (تغريدة OR "منصة إكس" OR تويتر) المغرب',
            '(القضاء OR المحكمة OR النيابة العامة) (إكس OR تويتر) المغرب',
        ],
        "أخرى": [
            '(القضاء OR العدالة OR المحكمة) (تيك توك OR إنستغرام OR لينكدإن OR فيديو) المغرب',
        ],
    }
    social_g_queries = platform_ar_queries.get(platform_label, [])
    if keywords_input.strip():
      social_g_queries = [
          f"{keywords_input.strip()} ({platform_label} OR تدوينة OR منشور) المغرب"
      ]

    for sq in social_g_queries:
      gnews_social_url = (
          "https://news.google.com/rss/search?q="
          f"{urllib.parse.quote(sq)}&hl=ar&gl=MA&ceid=MA:ar"
      )
      try:
        r = requests.get(gnews_social_url, headers=DEFAULT_HEADERS, timeout=10)
        if r.status_code == 200:
          for entry in parse_rss_xml(
              r.content, platform_label, fallback_offset=3600
          ):
            if entry["url"] not in seen_urls and is_relevant_item(
                entry["title"],
                entry["raw_snippet"],
                keywords_input,
                from_judicial_query=True,
            ):
              entry["platform"] = platform_label
              seen_urls.add(entry["url"])
              items.append(entry)
      except Exception:
        pass

  return items


def scrape_facebook_platform(keywords_input: str, progress_cb=None):
  return _multi_engine_social_search(
      "فيسبوك", ["facebook.com", "fb.watch"], keywords_input, progress_cb
  )


def scrape_x_platform(keywords_input: str, progress_cb=None):
  return _multi_engine_social_search(
      "إكس", ["x.com", "twitter.com"], keywords_input, progress_cb
  )


def scrape_other_platforms(keywords_input: str, progress_cb=None):
  return _multi_engine_social_search(
      "أخرى",
      ["tiktok.com", "instagram.com", "linkedin.com"],
      keywords_input,
      progress_cb,
  )


def scrape_custom_targets(targets: list, global_kw: str = "", progress_cb=None):
  items = []
  seen_urls = set()
  valid_targets = [t for t in targets if t.get("url", "").strip()]
  if not valid_targets:
    return items

  for idx, target in enumerate(valid_targets):
    if is_stop_requested():
      break
    t_url = target["url"].strip()
    t_kw = target.get("keyword", "").strip() or global_kw.strip()
    if progress_cb:
      progress_cb(
          (idx + 1) / max(1, len(valid_targets)),
          f"رصد الرابط المخصص: {t_url[:45]}...",
      )

    parsed = urllib.parse.urlparse(
        t_url if "://" in t_url else f"https://{t_url}"
    )
    domain = parsed.netloc.lower().replace("www.", "")
    path_slug = (
        parsed.path.strip("/").split("/")[0] if parsed.path.strip("/") else ""
    )
    handle_clean = path_slug.lstrip("@")

    if "youtube.com" in domain or "youtu.be" in domain:
      platform = "يوتيوب"
    elif "facebook.com" in domain or "fb." in domain:
      platform = "فيسبوك"
    elif "x.com" in domain or "twitter.com" in domain:
      platform = "إكس"
    elif any(
        d in domain for d in ["tiktok.com", "instagram.com", "linkedin.com"]
    ):
      platform = "أخرى"
    else:
      platform = "الصحف"

    if platform == "يوتيوب":
      try:
        r = requests.get(
            t_url,
            headers=DEFAULT_HEADERS,
            cookies=YT_BYPASS_COOKIES,
            timeout=10,
        )
        if r.status_code == 200:
          cid_match = re.search(
              r'"(?:channelId|externalId)"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"',
              r.text,
          )
          if cid_match:
            cid = cid_match.group(1)
            xml_url = (
                f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
            )
            rx = requests.get(xml_url, headers=DEFAULT_HEADERS, timeout=10)
            if rx.status_code == 200:
              for entry in parse_rss_xml(
                  rx.content,
                  "يوتيوب",
                  default_source=f"🎯 {handle_clean or 'YouTube'}",
              ):
                if t_kw and not is_relevant_item(
                    entry["title"], entry["raw_snippet"], t_kw, is_target=True
                ):
                  continue
                if entry["url"] not in seen_urls:
                  entry["is_custom_target"] = 1
                  seen_urls.add(entry["url"])
                  items.append(entry)
      except Exception:
        pass

      if handle_clean:
        q_yt = f"{handle_clean} {t_kw}".strip()
        for entry in scrape_youtube_platform(q_yt):
          if entry["url"] not in seen_urls:
            entry["is_custom_target"] = 1
            entry["source_name"] = f"🎯 {handle_clean}"
            seen_urls.add(entry["url"])
            items.append(entry)

    elif platform == "الصحف":
      for feed_suffix in ["/feed", "/rss", "/rss.xml", "/feed/"]:
        if is_stop_requested():
          break
        feed_url = f"{parsed.scheme}://{parsed.netloc}{feed_suffix}"
        try:
          rf = requests.get(feed_url, headers=DEFAULT_HEADERS, timeout=8)
          if rf.status_code == 200 and (
              b"<rss" in rf.content or b"<feed" in rf.content
          ):
            for entry in parse_rss_xml(
                rf.content, "الصحف", default_source=f"🎯 {domain}"
            ):
              if t_kw and not is_relevant_item(
                  entry["title"], entry["raw_snippet"], t_kw, is_target=True
              ):
                continue
              if entry["url"] not in seen_urls:
                entry["is_custom_target"] = 1
                seen_urls.add(entry["url"])
                items.append(entry)
            break
        except Exception:
          pass

      g_q = f"site:{domain} {t_kw}".strip()
      rss_u = (
          "https://news.google.com/rss/search?q="
          f"{urllib.parse.quote(g_q)}&hl=ar&gl=MA&ceid=MA:ar"
      )
      try:
        rg = requests.get(rss_u, headers=DEFAULT_HEADERS, timeout=10)
        if rg.status_code == 200:
          for entry in parse_rss_xml(
              rg.content, "الصحف", default_source=f"🎯 {domain}"
          ):
            if entry["url"] not in seen_urls:
              entry["is_custom_target"] = 1
              seen_urls.add(entry["url"])
              items.append(entry)
      except Exception:
        pass

    else:
      search_term = f"site:{domain} {handle_clean} {t_kw}".strip()
      for h_item in _scrape_yahoo_and_ddg_html(
          search_term, platform, [domain], t_kw, seen_urls
      ):
        h_item["is_custom_target"] = 1
        h_item["source_name"] = f"🎯 {handle_clean or domain}"
        items.append(h_item)

      bing_u = f"https://www.bing.com/search?q={urllib.parse.quote(search_term)}&format=rss"
      try:
        rb = requests.get(bing_u, headers=DEFAULT_HEADERS, timeout=10)
        if rb.status_code == 200 and b"<item>" in rb.content:
          for entry in parse_rss_xml(
              rb.content,
              platform,
              default_source=f"🎯 {handle_clean or domain}",
              fallback_offset=3600,
          ):
            if entry["url"] not in seen_urls:
              entry["is_custom_target"] = 1
              seen_urls.add(entry["url"])
              items.append(entry)
      except Exception:
        pass

      if DDGS is not None and not is_stop_requested():
        try:
          with DDGS() as ddgs:
            for res in ddgs.text(search_term, max_results=8):
              href = (res.get("href") or res.get("url") or "").strip()
              title = clean_html_text(res.get("title") or "")
              body = clean_html_text(res.get("body") or "")
              if not href or href in seen_urls:
                continue
              pub_str, pub_ts = extract_date_from_url_or_text(
                  href, body, "", fallback_offset_sec=5400
              )
              seen_urls.add(href)
              items.append({
                  "title": title or body[:90],
                  "url": href,
                  "raw_snippet": body or title,
                  "source_name": f"🎯 {handle_clean or domain}",
                  "platform": platform,
                  "pub_date": pub_str,
                  "pub_timestamp": pub_ts,
                  "is_custom_target": 1,
              })
        except Exception:
          pass

  return items


# =====================================================================
# 7. تحليل الذكاء الاصطناعي Gemini وتنبيهات تيليجرام وحفظ آمن
# =====================================================================
def analyze_with_gemini(item: dict, api_key: str):
  title = clean_display_text(item.get("title", ""))
  snippet = clean_display_text(item.get("raw_snippet", "")) or title
  platform = item.get("platform", "الصحف")
  source_name = item.get("source_name", platform)

  fallback_summary = build_rich_arabic_summary(
      title, snippet, platform, source_name
  )
  default_result = {
      "summary": fallback_summary,
      "sentiment": "محايد",
      "category": "شؤون قضائية",
      "relevance_score": 88,
  }

  if not api_key or genai is None or not str(api_key).startswith("AIza"):
    return default_result

  try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    prompt = (
        "أنت محلل إعلامي قضائي بالمجلس الأعلى للسلطة القضائية بالمغرب.\n"
        "حلل المحتوى التالي (سواء كان مقالاً صحفياً أو فيديو يوتيوب أو منشور فيسبوك/إكس) "
        "وأرجع JSON فقط بالمفاتيح التالية:\n"
        '{"summary": "ملخص وافٍ ومركز في جملتين أو ثلاث جمل بالعربية يوضح مضمون الخبر أو المنشور أو الفيديو", '
        '"sentiment": "إيجابي أو محايد أو سلبي", '
        '"category": "بلاغ رسمي أو محاكم وقضايا أو شؤون قضائية أو رأي ومتابعات", '
        '"relevance_score": 90}\n'
        f"المنصة: {platform} ({source_name})\n"
        f"العنوان: {title}\n"
        f"المقتطف/التفاصيل: {snippet[:500]}"
    )
    resp = model.generate_content(prompt)
    txt = (resp.text or "").strip()
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if m:
      parsed = json.loads(m.group(0))
      ai_sum = clean_display_text(parsed.get("summary"))
      if not ai_sum or len(ai_sum) < 25:
        ai_sum = fallback_summary
      return {
          "summary": ai_sum,
          "sentiment": clean_display_text(parsed.get("sentiment")) or "محايد",
          "category": (
              clean_display_text(parsed.get("category")) or "شؤون قضائية"
          ),
          "relevance_score": int(parsed.get("relevance_score", 88)),
      }
  except Exception:
    pass
  return default_result


def send_telegram_alert(item: dict, cfg: dict):
  token = (cfg.get("telegram_bot_token") or DEFAULT_TG_TOKEN).strip()
  chat_id = (cfg.get("telegram_chat_id") or DEFAULT_TG_CHAT_ID).strip()
  if not token or not chat_id:
    return
  platform_icons = {
      "الصحف": "📰",
      "فيسبوك": "🟦",
      "إكس": "⬛",
      "يوتيوب": "🟥",
      "أخرى": "🟪",
  }
  icon = platform_icons.get(item.get("platform", "الصحف"), "📡")
  target_badge = "🎯 [رصد مخصص]\n" if item.get("is_custom_target") else ""
  msg = (
      f"⚖️ *المرصد الوطني للعدالة والقضاء*\n"
      f"{target_badge}"
      f"{icon} *المنصة:* {item.get('platform', 'الصحف')} | *المصدر:* {item.get('source_name', '')}\n"
      f"📅 *تاريخ النشر:* {item.get('pub_date', '')}\n"
      f"📌 *العنوان:* {item.get('title', '')}\n\n"
      f"📝 *الملخص:* {item.get('summary', '')}\n\n"
      f"🏷️ *التصنيف:* {item.get('category', '')}\n"
      f"🔗 [فتح المصدر الأصلي]({item.get('url', '')})"
  )
  try:
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        },
        timeout=8,
    )
  except Exception:
    pass


def quick_process_and_save(
    items: list, cfg: dict, is_target_run: bool = False
) -> int:
  if not items:
    return 0

  existing_urls = set()
  existing_titles = set()
  lock = get_db_lock()
  with lock:
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      c = conn.cursor()
      c.execute("SELECT url, title FROM articles")
      for r_url, r_title in c.fetchall():
        if r_url:
          existing_urls.add(r_url.strip())
        if r_title:
          existing_titles.add(r_title.strip())
      conn.close()
    except Exception:
      pass

    if not existing_urls and os.path.exists(ARCHIVE_JSON_FILE):
      try:
        with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
          for row in json.load(f):
            if isinstance(row, dict):
              if row.get("url"):
                existing_urls.add(row["url"].strip())
              if row.get("title"):
                existing_titles.add(row["title"].strip())
      except Exception:
        pass

  candidates = []
  seen_batch_urls = set()
  seen_batch_titles = set()
  for it in sorted(
      items, key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
  ):
    u = (it.get("url") or "").strip()
    t = clean_display_text(it.get("title") or "")
    if not u or not t:
      continue
    if u in existing_urls or t in existing_titles:
      continue
    if u in seen_batch_urls or t in seen_batch_titles:
      continue
    seen_batch_urls.add(u)
    seen_batch_titles.add(t)
    it["title"] = t
    candidates.append(it)

  if not candidates:
    return 0

  api_key = (cfg.get("gemini_api_key") or "").strip()
  prepared_rows = []
  ai_calls = 0

  for it in candidates:
    if is_stop_requested():
      break
    plat = it.get("platform", "الصحف")
    src = clean_display_text(it.get("source_name") or plat)
    raw_snip = clean_display_text(it.get("raw_snippet") or "")

    if ai_calls < 10 and api_key.startswith("AIza"):
      ai_res = analyze_with_gemini(it, api_key)
      ai_calls += 1
    else:
      ai_res = {
          "summary": build_rich_arabic_summary(
              it["title"], raw_snip, plat, src
          ),
          "sentiment": "محايد",
          "category": "شؤون قضائية",
          "relevance_score": 86,
      }

    pub_str = it.get("pub_date") or ""
    pub_ts = float(it.get("pub_timestamp") or 0)
    if pub_ts <= 0 or not pub_str:
      pub_str, pub_ts = extract_date_from_url_or_text(
          it.get("url", ""), raw_snip, pub_str, fallback_offset_sec=3600
      )

    record = {
        "title": it["title"],
        "summary": clean_display_text(ai_res["summary"]),
        "source_name": src,
        "platform": plat,
        "url": it.get("url", "").strip(),
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "sentiment": clean_display_text(ai_res["sentiment"]),
        "category": clean_display_text(ai_res["category"]),
        "relevance_score": int(ai_res["relevance_score"]),
        "is_custom_target": (
            1 if (is_target_run or it.get("is_custom_target")) else 0
        ),
        "raw_snippet": raw_snip[:600],
        "created_at": time.time(),
    }
    prepared_rows.append(record)

  if not prepared_rows:
    return 0

  added_items = []
  with lock:
    for attempt in range(3):
      conn = None
      try:
        conn = _open_sqlite_conn()
        if attempt == 0:
          _ensure_schema_on_conn(conn)
        elif attempt == 1:
          _rebuild_articles_table_safely(conn)
        c = conn.cursor()
        for rec in prepared_rows:
          c.execute(
              """
                        INSERT OR IGNORE INTO articles (
                            title, summary, source_name, platform, url,
                            pub_date, pub_timestamp, sentiment, category,
                            relevance_score, is_custom_target, raw_snippet, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
              (
                  rec["title"],
                  rec["summary"],
                  rec["source_name"],
                  rec["platform"],
                  rec["url"],
                  rec["pub_date"],
                  rec["pub_timestamp"],
                  rec["sentiment"],
                  rec["category"],
                  rec["relevance_score"],
                  rec["is_custom_target"],
                  rec["raw_snippet"],
                  rec["created_at"],
              ),
          )
          if c.rowcount and c.rowcount > 0:
            added_items.append(rec)
        conn.commit()
        conn.close()
        break
      except Exception:
        if conn is not None:
          try:
            conn.close()
          except Exception:
            pass
        time.sleep(0.25)
        if attempt == 2:
          added_items = list(prepared_rows)

  if added_items:
    sync_db_to_json(extra_items=added_items)
    for rec in added_items[:10]:
      send_telegram_alert(rec, cfg)

  return len(added_items)


# =====================================================================
# 8. محرك الرصد الدوري الأوتوماتيكي (خلفية السيرفر + GitHub Actions)
# =====================================================================
def run_headless_background_cycle() -> int:
  scan_lock = get_scan_lock()
  if not scan_lock.acquire(blocking=False):
    return 0

  try:
    rt = get_shared_runtime()
    rt["bg_scanning"] = True
  except Exception:
    rt = None

  try:
    init_db()
    cfg = load_credentials()
    targets = load_custom_targets()
    kw = cfg.get("keywords_input", "")

    m_state = load_monitor_state()
    m_state["last_auto_run"] = time.time()
    save_monitor_state(m_state)

    raw_items = []
    raw_items.extend(scrape_moroccan_press(kw))
    raw_items.extend(scrape_youtube_platform(kw))
    raw_items.extend(scrape_facebook_platform(kw))
    raw_items.extend(scrape_x_platform(kw))
    raw_items.extend(scrape_other_platforms(kw))

    added_general = quick_process_and_save(raw_items, cfg, is_target_run=False)

    added_targets = 0
    if targets:
      t_items = scrape_custom_targets(targets, kw)
      added_targets = quick_process_and_save(t_items, cfg, is_target_run=True)

    total_added = added_general + added_targets
    m_state = load_monitor_state()
    m_state["last_auto_run"] = time.time()
    m_state["last_auto_added"] = total_added
    m_state["total_auto_cycles"] = int(m_state.get("total_auto_cycles", 0)) + 1
    save_monitor_state(m_state)
    return total_added
  except Exception:
    return 0
  finally:
    if rt is not None:
      rt["bg_scanning"] = False
    try:
      scan_lock.release()
    except Exception:
      pass


def ensure_background_daemon():
  rt = get_shared_runtime()
  if rt.get("daemon_started", False):
    return
  rt["daemon_started"] = True

  def _daemon_loop():
    time.sleep(2)
    while True:
      try:
        cfg = load_credentials()
        if cfg.get("auto_monitor", True):
          interval_sec = INTERVAL_MAP.get(
              cfg.get("monitor_interval", "كل 15 دقيقة"), 900
          )
          state = load_monitor_state()
          last_run = float(state.get("last_auto_run", 0))
          if time.time() - last_run >= interval_sec:
            run_headless_background_cycle()
      except Exception:
        pass
      time.sleep(30)

  t = threading.Thread(
      target=_daemon_loop, daemon=True, name="JusticeAutoMonitor"
  )
  t.start()


# دعم التشغيل السحابي المستقل عبر GitHub Actions (CRON_MODE=1)
if os.environ.get("CRON_MODE") == "1" or st is None:
  init_db()
  count = run_headless_background_cycle()
  print(f"[CRON_MODE] Completed cycle. Added {count} new items.")
  sys.exit(0)

# =====================================================================
# 9. تهيئة واجهة Streamlit والتصميم الزجاجي المتجاوب مع فرض صارم لاتجاه RTL
# =====================================================================
st.set_page_config(
    page_title="المرصد الوطني للعدالة والقضاء",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_db()
ensure_background_daemon()

render_html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');

*, *::before, *::after {
    box-sizing: border-box;
}

/* فرض صارم لاتجاه اللغة العربية RTL على التطبيق وجميع الحاويات والتبويبات */
html, body, .stApp, .main,
[data-testid="stAppViewContainer"],
[data-testid="stMarkdownContainer"],
[data-testid="stVerticalBlock"],
[data-baseweb="tab-panel"],
[class*="st-emotion-cache"] {
    font-family: 'Cairo', sans-serif !important;
    direction: rtl !important;
    text-align: right !important;
}

.stApp {
    background: radial-gradient(circle at 15% 15%, #111c35 0%, #090d16 55%, #05080f 100%) !important;
    color: #f1f5f9 !important;
    overflow-x: hidden !important;
}

.block-container {
    padding-top: 1.1rem !important;
    padding-bottom: 2.2rem !important;
    padding-left: clamp(0.6rem, 2.2vw, 2rem) !important;
    padding-right: clamp(0.6rem, 2.2vw, 2rem) !important;
    max-width: 1440px !important;
    direction: rtl !important;
    text-align: right !important;
}

/* تجاوب الأعمدة والأزرار تلقائياً على جميع مقاسات الشاشات */
div[data-testid="stHorizontalBlock"] {
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 10px !important;
    align-items: stretch !important;
    direction: rtl !important;
}

div[data-testid="stHorizontalBlock"] > div[data-testid="column"],
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    flex: 1 1 145px !important;
    min-width: 140px !important;
}

/* الهيدر الزجاجي المتجاوب */
.hero-glass {
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.88) 0%, rgba(30, 41, 59, 0.72) 100%);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(56, 189, 248, 0.28);
    border-radius: 18px;
    padding: clamp(12px, 2vw, 20px) clamp(14px, 2.5vw, 26px);
    margin-bottom: 14px;
    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
    direction: rtl !important;
    text-align: right !important;
}

.hero-title {
    font-size: clamp(1.2rem, 2.6vw, 1.75rem);
    font-weight: 900;
    background: linear-gradient(90deg, #38bdf8, #818cf8, #f472b6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    line-height: 1.35;
}

.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(16, 185, 129, 0.14);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: #34d399;
    padding: 5px 13px;
    border-radius: 999px;
    font-size: clamp(0.74rem, 1.4vw, 0.84rem);
    font-weight: 700;
    max-width: 100%;
    direction: rtl !important;
}

.pulse-dot {
    width: 9px;
    height: 9px;
    min-width: 9px;
    background: #10b981;
    border-radius: 50%;
    box-shadow: 0 0 10px #10b981;
    animation: pulseGlow 1.6s infinite ease-in-out;
}

@keyframes pulseGlow {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.35); opacity: 0.55; }
}

/* إلغاء الخلفية البيضاء لجميع الأزرار وتطبيق تدرجات داكنة احترافية */
div.stButton > button,
div.stDownloadButton > button,
div[data-testid="stFormSubmitButton"] > button {
    width: 100% !important;
    min-height: 44px !important;
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important;
    color: #f8fafc !important;
    border: 1px solid rgba(148, 163, 184, 0.35) !important;
    border-radius: 12px !important;
    padding: 0.5rem 0.65rem !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
    font-size: clamp(0.8rem, 1.3vw, 0.92rem) !important;
    white-space: nowrap !important;
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.35) !important;
    transition: all 0.2s ease !important;
}

div.stButton > button *,
div.stDownloadButton > button *,
div[data-testid="stFormSubmitButton"] > button * {
    color: #f8fafc !important;
}

div.stButton > button:hover,
div.stDownloadButton > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-2px) !important;
    border-color: #38bdf8 !important;
    box-shadow: 0 8px 22px rgba(56, 189, 248, 0.28) !important;
}

/* ألوان مخصصة لكل منصة ولكل زر */
div[data-testid="stVerticalBlock"]:has(.btn-marker-all) div.stButton > button {
    background: linear-gradient(135deg, #0284c7 0%, #1d4ed8 100%) !important;
    border: 1px solid rgba(125, 211, 252, 0.55) !important;
}
div[data-testid="stVerticalBlock"]:has(.btn-marker-press) div.stButton > button {
    background: linear-gradient(135deg, #059669 0%, #065f46 100%) !important;
    border: 1px solid rgba(110, 231, 183, 0.5) !important;
}
div[data-testid="stVerticalBlock"]:has(.btn-marker-fb) div.stButton > button {
    background: linear-gradient(135deg, #2563eb 0%, #1e3a8a 100%) !important;
    border: 1px solid rgba(147, 197, 253, 0.5) !important;
}
div[data-testid="stVerticalBlock"]:has(.btn-marker-x) div.stButton > button {
    background: linear-gradient(135deg, #334155 0%, #0f172a 100%) !important;
    border: 1px solid rgba(203, 213, 225, 0.45) !important;
}
div[data-testid="stVerticalBlock"]:has(.btn-marker-yt) div.stButton > button {
    background: linear-gradient(135deg, #dc2626 0%, #7f1d1d 100%) !important;
    border: 1px solid rgba(252, 165, 165, 0.5) !important;
}
div[data-testid="stVerticalBlock"]:has(.btn-marker-other) div.stButton > button {
    background: linear-gradient(135deg, #7c3aed 0%, #4c1d95 100%) !important;
    border: 1px solid rgba(196, 181, 253, 0.5) !important;
}
div[data-testid="stVerticalBlock"]:has(.btn-marker-target) div.stButton > button {
    background: linear-gradient(135deg, #d97706 0%, #78350f 100%) !important;
    border: 1px solid rgba(253, 230, 138, 0.5) !important;
}
div[data-testid="stVerticalBlock"]:has(.btn-marker-stop) div.stButton > button {
    background: linear-gradient(135deg, #991b1b 0%, #450a0a 100%) !important;
    border: 1px solid rgba(248, 113, 113, 0.5) !important;
    min-height: 34px !important;
    padding: 0.25rem 0.5rem !important;
    font-size: 0.76rem !important;
}

/* رادار المسح الضوئي 360 درجة */
.radar-panel {
    background: rgba(15, 23, 42, 0.88);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(56, 189, 248, 0.42);
    border-radius: 16px;
    padding: 14px 18px;
    margin: 10px 0 14px 0;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0 10px 30px rgba(2, 132, 199, 0.22);
    direction: rtl !important;
    text-align: right !important;
}

.radar-scanner {
    width: 58px;
    height: 58px;
    min-width: 58px;
    border-radius: 50%;
    position: relative;
    background:
        radial-gradient(circle, rgba(56, 189, 248, 0.15) 20%, transparent 21%),
        radial-gradient(circle, transparent 48%, rgba(56, 189, 248, 0.25) 49%, transparent 51%),
        #070d19;
    border: 2px solid #38bdf8;
    box-shadow: 0 0 18px rgba(56, 189, 248, 0.45), inset 0 0 12px rgba(56, 189, 248, 0.25);
    overflow: hidden;
}

.radar-scanner::before {
    content: "";
    position: absolute;
    inset: -50%;
    background: conic-gradient(from 0deg, transparent 55%, rgba(56, 189, 248, 0.8) 100%);
    animation: radarSpin 1.3s linear infinite;
}

.radar-scanner::after {
    content: "";
    position: absolute;
    top: 50%;
    left: 50%;
    width: 7px;
    height: 7px;
    background: #38bdf8;
    border-radius: 50%;
    transform: translate(-50%, -50%);
    box-shadow: 0 0 10px #38bdf8;
}

@keyframes radarSpin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* شارة اكتمال الرصد DONE */
.done-banner {
    background: linear-gradient(135deg, rgba(6, 95, 70, 0.88) 0%, rgba(4, 120, 87, 0.78) 100%);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(52, 211, 153, 0.55);
    border-radius: 14px;
    padding: 11px 18px;
    margin: 8px 0 14px 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    color: #ecfdf5;
    font-weight: 800;
    font-size: clamp(0.84rem, 1.5vw, 0.96rem);
    box-shadow: 0 8px 25px rgba(16, 185, 129, 0.25);
    direction: rtl !important;
    text-align: right !important;
}

/* شبكة الإحصائيات المتجاوبة (CSS Grid) */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
    gap: 10px;
    margin: 10px 0 16px 0;
    direction: rtl !important;
}

.metric-glass {
    background: rgba(15, 23, 42, 0.72);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    padding: 12px 10px;
    text-align: center !important;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.28);
}

.metric-num {
    font-size: clamp(1.3rem, 2.2vw, 1.65rem);
    font-weight: 900;
    color: #38bdf8;
    line-height: 1.2;
    text-align: center !important;
}

.metric-lbl {
    font-size: clamp(0.75rem, 1.2vw, 0.84rem);
    color: #94a3b8;
    font-weight: 700;
    margin-top: 2px;
    text-align: center !important;
}

/* بطاقات الأخبار والمنشورات الزجاجية المتجاوبة باتجاه RTL صارم */
.news-card {
    background: linear-gradient(145deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 41, 59, 0.72) 100%);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-right: 5px solid #38bdf8;
    border-radius: 16px;
    padding: clamp(14px, 2vw, 22px);
    margin-bottom: 14px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    transition: transform 0.2s ease, border-color 0.2s ease;
    word-wrap: break-word;
    overflow-wrap: anywhere;
    direction: rtl !important;
    text-align: right !important;
}

.news-card:hover {
    transform: translateY(-2px);
    border-color: rgba(56, 189, 248, 0.48);
}

.news-card.plat-press { border-right-color: #10b981; }
.news-card.plat-fb { border-right-color: #3b82f6; }
.news-card.plat-x { border-right-color: #cbd5e1; }
.news-card.plat-yt { border-right-color: #ef4444; }
.news-card.plat-other { border-right-color: #a855f7; }

.news-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.14);
    font-size: clamp(0.78rem, 1.3vw, 0.86rem);
    color: #94a3b8;
    direction: rtl !important;
    text-align: right !important;
}

.news-meta-right {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    direction: rtl !important;
}

.pub-date-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(56, 189, 248, 0.35);
    color: #e2e8f0;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: clamp(0.75rem, 1.25vw, 0.83rem);
    font-weight: 700;
    direction: rtl !important;
}

.badge-plat {
    padding: 3px 11px;
    border-radius: 999px;
    font-weight: 800;
    font-size: 0.78rem;
    background: rgba(56, 189, 248, 0.18);
    color: #7dd3fc;
    border: 1px solid rgba(56, 189, 248, 0.38);
    display: inline-block;
}

.badge-target {
    padding: 3px 11px;
    border-radius: 999px;
    font-weight: 800;
    font-size: 0.76rem;
    background: rgba(217, 119, 6, 0.22);
    color: #fcd34d;
    border: 1px solid rgba(245, 158, 11, 0.45);
    display: inline-block;
}

.news-title {
    font-size: clamp(1.02rem, 1.8vw, 1.18rem);
    font-weight: 800;
    color: #f8fafc;
    margin: 8px 0 10px 0;
    line-height: 1.6;
    direction: rtl !important;
    text-align: right !important;
}

.news-summary-box {
    background: rgba(9, 13, 22, 0.55);
    border-right: 3px solid rgba(56, 189, 248, 0.55);
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 12px;
    font-size: clamp(0.88rem, 1.5vw, 0.96rem);
    color: #cbd5e1;
    line-height: 1.75;
    direction: rtl !important;
    text-align: right !important;
}

.news-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
    direction: rtl !important;
    text-align: right !important;
}

.news-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(56, 189, 248, 0.16);
    border: 1px solid rgba(56, 189, 248, 0.4);
    color: #38bdf8 !important;
    text-decoration: none !important;
    padding: 6px 15px;
    border-radius: 10px;
    font-size: 0.84rem;
    font-weight: 800;
    direction: rtl !important;
}

.news-link:hover {
    background: rgba(56, 189, 248, 0.3);
}

/* التبويبات القابلة للتمرير الأفقي السلس على الهواتف */
div[data-baseweb="tab-list"] {
    gap: 6px !important;
    background: rgba(15, 23, 42, 0.78) !important;
    padding: 6px !important;
    border-radius: 14px !important;
    border: 1px solid rgba(148, 163, 184, 0.2) !important;
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
    scrollbar-width: thin;
    direction: rtl !important;
}

button[data-baseweb="tab"] {
    background: transparent !important;
    color: #94a3b8 !important;
    border-radius: 10px !important;
    padding: 7px 13px !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
    font-size: clamp(0.78rem, 1.4vw, 0.9rem) !important;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, #0284c7 0%, #1e40af 100%) !important;
    color: #ffffff !important;
}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div {
    background-color: rgba(15, 23, 42, 0.88) !important;
    border-color: rgba(148, 163, 184, 0.32) !important;
    color: #f8fafc !important;
    border-radius: 12px !important;
    direction: rtl !important;
    text-align: right !important;
}

input {
    color: #f8fafc !important;
    direction: rtl !important;
    text-align: right !important;
}

/* تحسينات خاصة لشاشات الهواتف والأجهزة اللوحية */
@media (max-width: 768px) {
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"],
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 1 1 calc(50% - 8px) !important;
        min-width: 130px !important;
    }
    .hero-glass {
        flex-direction: column;
        align-items: flex-start;
    }
    .metrics-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    .radar-panel {
        padding: 12px 14px;
        gap: 12px;
    }
    .radar-scanner {
        width: 46px;
        height: 46px;
        min-width: 46px;
    }
}
</style>
""")

# =====================================================================
# 10. تحميل الإعدادات والبيانات
# =====================================================================
cfg = load_credentials()
custom_targets = load_custom_targets()
monitor_state = load_monitor_state()
rt_state = get_shared_runtime()

with st.sidebar:
  st.markdown("### ⚙️ إعدادات المنصة")
  gemini_key_in = st.text_input(
      "مفتاح Gemini API", value=cfg.get("gemini_api_key", ""), type="password"
  )
  tg_token_in = st.text_input(
      "Telegram Bot Token",
      value=cfg.get("telegram_bot_token", DEFAULT_TG_TOKEN),
  )
  tg_chat_in = st.text_input(
      "Telegram Chat ID", value=cfg.get("telegram_chat_id", DEFAULT_TG_CHAT_ID)
  )
  auto_mon_in = st.toggle(
      "تفعيل الرصد الدوري التلقائي", value=bool(cfg.get("auto_monitor", True))
  )
  interval_options = list(INTERVAL_MAP.keys())
  curr_interval = cfg.get("monitor_interval", "كل 15 دقيقة")
  interval_in = st.selectbox(
      "فترة الرصد التلقائي",
      options=interval_options,
      index=interval_options.index(curr_interval)
      if curr_interval in interval_options
      else 0,
  )

  if st.button("💾 حفظ الإعدادات"):
    cfg["gemini_api_key"] = gemini_key_in.strip()
    cfg["telegram_bot_token"] = tg_token_in.strip() or DEFAULT_TG_TOKEN
    cfg["telegram_chat_id"] = tg_chat_in.strip() or DEFAULT_TG_CHAT_ID
    cfg["auto_monitor"] = bool(auto_mon_in)
    cfg["monitor_interval"] = interval_in
    save_credentials(cfg)
    st.success("تم حفظ الإعدادات بنجاح")

  st.markdown("### 🗄️ النسخ الاحتياطي")
  all_db_articles = fetch_articles_from_db()
  json_export_str = json.dumps(all_db_articles, ensure_ascii=False, indent=2)
  st.download_button(
      "⬇️ تحميل أرشيف البيانات (JSON)",
      data=json_export_str.encode("utf-8"),
      file_name="justice_monitor_backup.json",
      mime="application/json",
  )

  uploaded_backup = st.file_uploader("⬆️ استعادة أرشيف JSON", type=["json"])
  if uploaded_backup is not None:
    try:
      restored_list = json.loads(uploaded_backup.read().decode("utf-8"))
      if isinstance(restored_list, list):
        with open(ARCHIVE_JSON_FILE, "w", encoding="utf-8") as f:
          json.dump(restored_list, f, ensure_ascii=False, indent=2)
        restore_db_from_json_if_needed()
        st.success("تمت استعادة الأرشيف بنجاح")
        st.rerun()
    except Exception:
      st.error("ملف غير صالح")

# =====================================================================
# 11. الهيدر الرئيسي وشريط البحث المخصص والروابط المخصصة
# =====================================================================
last_auto_ts = float(monitor_state.get("last_auto_run", 0))
last_auto_label = (
    format_relative_arabic(last_auto_ts) if last_auto_ts > 0 else "قيد الانطلاق"
)
auto_badge_text = (
    f"الرصد التلقائي نشط ({cfg.get('monitor_interval', 'كل 15 دقيقة')}) • آخر فحص: {last_auto_label}"
    if cfg.get("auto_monitor", True)
    else "الرصد اليدوي"
)

render_html(f"""
<div class="hero-glass" dir="rtl">
    <h1 class="hero-title">⚖️ المرصد الوطني للعدالة والقضاء</h1>
    <div class="status-pill" dir="rtl">
        <span class="pulse-dot"></span>
        <span>{html.escape(auto_badge_text)}</span>
    </div>
</div>
""")

kw_input = st.text_input(
    "🔍 تخصيص بكلمات مفتاحية (اختياري)",
    value=cfg.get("keywords_input", ""),
    placeholder="🔍 اتركه فارغاً للرصد القضائي العام، أو أدخل كلمات مفتاحية مفصولة بفاصلة...",
    label_visibility="collapsed",
)
if kw_input != cfg.get("keywords_input", ""):
  cfg["keywords_input"] = kw_input
  save_credentials(cfg)

with st.expander(
    f"🎯 الروابط والقنوات المخصصة ({len(custom_targets)})", expanded=False
):
  with st.form("add_custom_target_form", clear_on_submit=True):
    c_u, c_k, c_b = st.columns([2.5, 1.5, 1.0])
    with c_u:
      new_t_url = st.text_input(
          "الرابط",
          placeholder="https://www.youtube.com/@... أو رابط صفحة/موقع",
          label_visibility="collapsed",
      )
    with c_k:
      new_t_kw = st.text_input(
          "كلمة (اختياري)",
          placeholder="كلمة فلترة (اختياري)...",
          label_visibility="collapsed",
      )
    with c_b:
      add_t_btn = st.form_submit_button("➕ إضافة رابط")
    if add_t_btn and new_t_url.strip():
      custom_targets.append(
          {"url": new_t_url.strip(), "keyword": new_t_kw.strip()}
      )
      save_custom_targets(custom_targets)
      st.rerun()

  for idx, t_item in enumerate(list(custom_targets)):
    tc1, tc2 = st.columns([5, 1])
    with tc1:
      kw_tag = f" ({t_item['keyword']})" if t_item.get("keyword") else ""
      render_html(
          f"<div style='font-size:0.84rem;color:#cbd5e1;direction:ltr;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:4px 0;'>🔗 {html.escape(t_item['url'])}{html.escape(kw_tag)}</div>"
      )
    with tc2:
      if st.button("❌ حذف", key=f"del_target_{idx}"):
        custom_targets.pop(idx)
        save_custom_targets(custom_targets)
        st.rerun()

# =====================================================================
# 12. لوحة أزرار الرصد المتجاوبة (تلتف تلقائياً حسب عرض الشاشة)
# =====================================================================
SCAN_MODES = [
    ("all", "🚀 رصد الشامل", "btn-marker-all"),
    ("press", "📰 رصد الصحف", "btn-marker-press"),
    ("fb", "🟦 رصد فيسبوك", "btn-marker-fb"),
    ("x", "⬛ رصد إكس", "btn-marker-x"),
    ("yt", "🟥 رصد يوتيوب", "btn-marker-yt"),
    ("other", "🟪 رصد أخرى", "btn-marker-other"),
    ("target", "🎯 رصد المخصص", "btn-marker-target"),
]

btn_cols = st.columns(len(SCAN_MODES))
triggered_mode = None

for col_idx, (mode_key, mode_label, marker_cls) in enumerate(SCAN_MODES):
  with btn_cols[col_idx]:
    render_html(f'<span class="{marker_cls}"></span>')
    if st.button(mode_label, key=f"start_scan_{mode_key}"):
      clear_stop_scan()
      triggered_mode = mode_key
    render_html('<span class="btn-marker-stop"></span>')
    if st.button("🛑 إيقاف", key=f"stop_scan_{mode_key}"):
      request_stop_scan()

# =====================================================================
# 13. منطقة الرادار الدوار 360° وشريط التقدم ومؤشر DONE
# =====================================================================
radar_placeholder = st.empty()
progress_placeholder = st.empty()
done_placeholder = st.empty()


def execute_interactive_scan(mode_key: str):
  clear_stop_scan()
  rt_state["active_scan"] = mode_key

  def update_ui_progress(pct: float, status_msg: str):
    pct_int = max(5, min(100, int(pct * 100)))
    render_html(
        f"""
        <div class="radar-panel" dir="rtl">
            <div class="radar-scanner"></div>
            <div style="flex:1;direction:rtl;text-align:right;">
                <div style="font-size:1rem;font-weight:800;color:#38bdf8;margin-bottom:3px;">
                    📡 {html.escape(clean_display_text(status_msg))}
                </div>
                <div style="font-size:0.82rem;color:#94a3b8;">
                    مسح ذكي بزاوية 360° للمصادر القضائية والإعلامية... ({pct_int}%)
                </div>
            </div>
        </div>
        """,
        target=radar_placeholder,
    )
    progress_placeholder.progress(pct_int / 100.0)

  kw = cfg.get("keywords_input", "")
  collected = []
  is_target_mode = mode_key == "target"

  if mode_key == "all":
    steps = [
        ("الصحف المغربية", lambda cb: scrape_moroccan_press(kw, cb)),
        ("يوتيوب", lambda cb: scrape_youtube_platform(kw, cb)),
        ("فيسبوك", lambda cb: scrape_facebook_platform(kw, cb)),
        ("منصة إكس", lambda cb: scrape_x_platform(kw, cb)),
        (
            "تيك توك وإنستغرام ولينكدإن",
            lambda cb: scrape_other_platforms(kw, cb),
        ),
    ]
    for s_idx, (s_name, s_fn) in enumerate(steps):
      if is_stop_requested():
        break
      base_p = s_idx / len(steps)
      span_p = 1.0 / len(steps)
      collected.extend(
          s_fn(
              lambda sub_p, msg, bp=base_p, sp=span_p: update_ui_progress(
                  bp + sub_p * sp, msg
              )
          )
      )
  elif mode_key == "press":
    collected = scrape_moroccan_press(kw, update_ui_progress)
  elif mode_key == "fb":
    collected = scrape_facebook_platform(kw, update_ui_progress)
  elif mode_key == "x":
    collected = scrape_x_platform(kw, update_ui_progress)
  elif mode_key == "yt":
    collected = scrape_youtube_platform(kw, update_ui_progress)
  elif mode_key == "other":
    collected = scrape_other_platforms(kw, update_ui_progress)
  elif mode_key == "target":
    collected = scrape_custom_targets(custom_targets, kw, update_ui_progress)

  if not is_stop_requested():
    update_ui_progress(0.96, "تحليل النتائج وترتيبها زمنياً وحفظها...")
    added_count = quick_process_and_save(
        collected, cfg, is_target_run=is_target_mode
    )
    update_ui_progress(1.0, "اكتملت عملية الرصد بنجاح")
    time.sleep(0.25)
    rt_state["last_done_mode"] = mode_key
    rt_state["last_done_count"] = added_count
    rt_state["last_done_ts"] = time.time()
  else:
    rt_state["last_done_mode"] = "stopped"
    rt_state["last_done_count"] = 0
    rt_state["last_done_ts"] = time.time()

  rt_state["active_scan"] = None
  radar_placeholder.empty()
  progress_placeholder.empty()


if triggered_mode:
  execute_interactive_scan(triggered_mode)

if time.time() - float(rt_state.get("last_done_ts", 0)) < 25:
  if rt_state.get("last_done_mode") == "stopped":
    render_html(
        """
        <div class="done-banner" dir="rtl" style="background:rgba(127,29,29,0.85);border-color:#f87171;">
            <span>🛑 تم إيقاف عملية الرصد بطلب من المستخدم</span>
            <span>STOPPED</span>
        </div>
        """,
        target=done_placeholder,
    )
  elif rt_state.get("last_done_mode"):
    c_new = int(rt_state.get("last_done_count", 0))
    render_html(
        f"""
        <div class="done-banner" dir="rtl">
            <span>✨ تـم بنجاح / DONE — تم رصد وتحديث القاعدة ({c_new} منشور/خبر جديد)</span>
            <span>100% DONE ✅</span>
        </div>
        """,
        target=done_placeholder,
    )

# =====================================================================
# 14. فرز الأخبار زمنياً (الأحدث أولاً) وفصل الـ 24 ساعة عن الأرشيف
# =====================================================================
all_articles = fetch_articles_from_db()
now_ts = time.time()
cutoff_24h = now_ts - 86400

live_articles = [
    a for a in all_articles if float(a.get("pub_timestamp", 0)) >= cutoff_24h
]
archive_articles = [
    a for a in all_articles if float(a.get("pub_timestamp", 0)) < cutoff_24h
]

live_articles.sort(key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True)
archive_articles.sort(
    key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
)

press_live = [a for a in live_articles if a.get("platform") == "الصحف"]
fb_live = [a for a in live_articles if a.get("platform") == "فيسبوك"]
x_live = [a for a in live_articles if a.get("platform") == "إكس"]
yt_live = [a for a in live_articles if a.get("platform") == "يوتيوب"]
other_live = [a for a in live_articles if a.get("platform") == "أخرى"]
target_live = [
    a for a in all_articles if int(a.get("is_custom_target", 0)) == 1
]

# شبكة الإحصائيات المتجاوبة بالكامل عبر CSS Grid
metrics_data = [
    ("الكل (24 ساعة)", len(live_articles)),
    ("الصحف", len(press_live)),
    ("فيسبوك", len(fb_live)),
    ("إكس", len(x_live)),
    ("يوتيوب", len(yt_live)),
    ("الأرشيف", len(archive_articles)),
]
metrics_cards_html = "".join(
    f'<div class="metric-glass" dir="rtl"><div class="metric-num">{m_val}</div><div class="metric-lbl">{m_label}</div></div>'
    for m_label, m_val in metrics_data
)
render_html(f'<div class="metrics-grid" dir="rtl">{metrics_cards_html}</div>')


def render_article_cards(
    items_list: list,
    empty_msg: str = "لا توجد منشورات مرصودة حالياً في هذا القسم.",
):
  if not items_list:
    render_html(
        f"<div dir='rtl' style='direction:rtl;text-align:center;padding:30px;color:#64748b;background:rgba(15,23,42,0.5);border-radius:16px;border:1px dashed rgba(148,163,184,0.2);'>{html.escape(empty_msg)}</div>"
    )
    return

  plat_css_map = {
      "الصحف": "plat-press",
      "فيسبوك": "plat-fb",
      "إكس": "plat-x",
      "يوتيوب": "plat-yt",
      "أخرى": "plat-other",
  }

  plat_type_label = {
      "الصحف": "📰 مقال صحفي",
      "فيسبوك": "🟦 منشور فيسبوك",
      "إكس": "⬛ منشور إكس",
      "يوتيوب": "🟥 فيديو يوتيوب",
      "أخرى": "🟪 منشور رقمي",
  }

  cards_buffer = []
  for item in items_list:
    plat = clean_display_text(item.get("platform") or "الصحف")
    css_cls = plat_css_map.get(plat, "plat-press")
    type_badge_txt = plat_type_label.get(plat, plat)

    raw_title = clean_display_text(item.get("title") or "")
    raw_summary = clean_display_text(item.get("summary") or "")
    raw_snip = clean_display_text(item.get("raw_snippet") or "")
    raw_src = clean_display_text(item.get("source_name") or plat)

    # ضمان وجود ملخص غني ومفصل لكل مقال أو فيديو أو منشور حتى للبيانات المخزنة مسبقا
    if (
        not raw_summary
        or raw_summary.lower() == raw_title.lower()
        or len(raw_summary) < 25
    ):
      raw_summary = build_rich_arabic_summary(
          raw_title, raw_snip, plat, raw_src
      )

    pub_ts = float(item.get("pub_timestamp") or (time.time() - 3600))
    raw_pub_date = clean_display_text(item.get("pub_date") or "")
    if not raw_pub_date:
      raw_pub_date = datetime.fromtimestamp(
          pub_ts, tz=timezone.utc
      ).strftime("%Y-%m-%d %H:%M")

    title_safe = html.escape(raw_title)
    summary_safe = html.escape(raw_summary)
    source_safe = html.escape(raw_src)
    pub_date_safe = html.escape(raw_pub_date)
    rel_time = html.escape(format_relative_arabic(pub_ts))
    category_safe = html.escape(
        clean_display_text(item.get("category") or "شؤون قضائية")
    )
    raw_url = str(item.get("url") or "#").strip()
    url_safe = html.escape(raw_url, quote=True)
    target_tag = (
        '<span class="badge-target">🎯 رصد مخصص</span>'
        if int(item.get("is_custom_target", 0)) == 1
        else ""
    )

    card_html = (
        f'<div class="news-card {css_cls}" dir="rtl" style="direction:rtl;text-align:right;">'
        '<div class="news-meta" dir="rtl" style="direction:rtl;text-align:right;">'
        '<div class="news-meta-right" dir="rtl">'
        f'<span class="badge-plat">{html.escape(type_badge_txt)}</span>'
        f"{target_tag}"
        f'<span style="font-weight:800;color:#e2e8f0;">{source_safe}</span>'
        f'<span style="color:#64748b;">• {category_safe}</span>'
        "</div>"
        '<div class="pub-date-pill" dir="rtl">'
        f'<span>📅 تاريخ النشر: <strong style="color:#38bdf8;" dir="ltr">{pub_date_safe}</strong></span>'
        f'<span style="color:#34d399;font-weight:800;">({rel_time})</span>'
        "</div>"
        "</div>"
        f'<div class="news-title" dir="rtl" style="direction:rtl;text-align:right;">{title_safe}</div>'
        f'<div class="news-summary-box" dir="rtl" style="direction:rtl;text-align:right;">'
        f'<strong style="color:#38bdf8;">📝 ملخص المحتوى: </strong>{summary_safe}'
        "</div>"
        '<div class="news-footer" dir="rtl" style="direction:rtl;text-align:right;">'
        f'<a class="news-link" href="{url_safe}" target="_blank" rel="noopener noreferrer">🔗 فتح المصدر الأصلي</a>'
        "</div>"
        "</div>"
    )
    cards_buffer.append(card_html)

  render_html("\n".join(cards_buffer))


# =====================================================================
# 15. التبويبات الرئيسية (بأسماء مختصرة من كلمة واحدة)
# =====================================================================
tabs = st.tabs([
    f"الكل ({len(live_articles)})",
    f"الصحف ({len(press_live)})",
    f"فيسبوك ({len(fb_live)})",
    f"إكس ({len(x_live)})",
    f"يوتيوب ({len(yt_live)})",
    f"أخرى ({len(other_live)})",
    f"المخصص ({len(target_live)})",
    f"الأرشيف ({len(archive_articles)})",
])

with tabs[0]:
  render_article_cards(live_articles)

with tabs[1]:
  render_article_cards(press_live)

with tabs[2]:
  render_article_cards(fb_live)

with tabs[3]:
  render_article_cards(x_live)

with tabs[4]:
  render_article_cards(yt_live)

with tabs[5]:
  render_article_cards(other_live)

with tabs[6]:
  render_article_cards(target_live)

with tabs[7]:
  arch_q = st.text_input(
      "🔎 البحث في الأرشيف",
      placeholder="ابحث بالعنوان أو المصدر أو الكلمة المفتاحية...",
      key="archive_search_box",
  )
  filtered_arch = archive_articles
  if arch_q.strip():
    q_low = arch_q.strip().lower()
    filtered_arch = [
        a
        for a in archive_articles
        if q_low
        in (
            a.get("title", "")
            + " "
            + a.get("summary", "")
            + " "
            + a.get("source_name", "")
        ).lower()
    ]
  render_article_cards(
      filtered_arch,
      empty_msg="لا توجد عناصر في الأرشيف حالياً (تنتقل الأخبار تلقائياً إلى الأرشيف بعد مرور 24 ساعة).",
  )

# =====================================================================
# 16. فحص الرصد الدوري غير المتزامن (بدون تجميد الواجهة أو قفل SQLite)
# =====================================================================
if cfg.get("auto_monitor", True):
  interval_sec = INTERVAL_MAP.get(
      cfg.get("monitor_interval", "كل 15 دقيقة"), 900
  )
  last_run_ts = float(monitor_state.get("last_auto_run", 0))
  if (
      time.time() - last_run_ts >= interval_sec
      and not rt_state.get("bg_scanning", False)
      and rt_state.get("active_scan") is None
  ):
    threading.Thread(
        target=run_headless_background_cycle,
        daemon=True,
        name="OnLoadAsyncCycle",
    ).start()

  render_html("""
    <script>
    setTimeout(function() {
        window.parent.location.reload();
    }, 60000);
    </script>
    """)
