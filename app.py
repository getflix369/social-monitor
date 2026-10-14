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

# =====================================================================
# 1. إعدادات النظام والثوابت الأساسية
# =====================================================================
# استخدام المسار المؤقت للنظام (tmpfs) لتشغيل SQLite بسرعة فائقة وبدون أخطاء القفل
# في بيئة Streamlit Cloud (/mount/src)، مع المزامنة الفورية لملفات المستودع الدائمة.
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
    "العدالة",
    "النيابة العامة",
    "محكمة النقض",
    "المحاكم",
    "قاضي",
    "قضاة",
    "وكيل الملك",
    "الوكيل العام",
    "محمد عبد النباوي",
    "رئاسة النيابة العامة",
    "هشام البلاوي",
    "وزارة العدل",
    "محكمة الاستئناف",
    "المحكمة الابتدائية",
    "المحكمة الإدارية",
    "المحكمة التجارية",
    "المعهد العالي للقضاء",
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
              c.execute(
                  """
                                INSERT OR IGNORE INTO articles (
                                    title, summary, source_name, platform, url,
                                    pub_date, pub_timestamp, sentiment, category,
                                    relevance_score, is_custom_target, raw_snippet, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                  (
                      item.get("title", ""),
                      item.get("summary", ""),
                      item.get("source_name", ""),
                      item.get("platform", "الصحف"),
                      item.get("url", ""),
                      item.get("pub_date", ""),
                      float(item.get("pub_timestamp", time.time() - 3600)),
                      item.get("sentiment", "محايد"),
                      item.get("category", "شؤون قضائية"),
                      int(item.get("relevance_score", 85)),
                      int(item.get("is_custom_target", 0)),
                      item.get("raw_snippet", ""),
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
# 5. معالجة التواريخ وترتيب الزمن الحقيقي
# =====================================================================
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
  num_match = re.search(r"(\d+)", rel_lower)
  num = int(num_match.group(1)) if num_match else 1

  if any(w in rel_lower for w in ["ثانية", "ثواني", "second", "sec", "الآن", "just now"]):
    ts = now_ts - 60
  elif any(w in rel_lower for w in ["دقيقة", "دقائق", "دقيقتين", "minute", "min"]):
    if "دقيقتين" in rel_lower:
      num = 2
    ts = now_ts - (num * 60)
  elif any(w in rel_lower for w in ["ساعة", "ساعات", "ساعتين", "hour", "hr"]):
    if "ساعتين" in rel_lower:
      num = 2
    ts = now_ts - (num * 3600)
  elif any(w in rel_lower for w in ["يوم", "أيام", "يومين", "أمس", "day", "yesterday"]):
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
    title: str, snippet: str, keywords_input: str, is_target: bool = False
) -> bool:
  text = f"{title} {snippet}".lower()
  custom_kws = [
      k.strip().lower()
      for k in re.split(r"[,،\n]+", str(keywords_input or ""))
      if k.strip()
  ]
  if custom_kws:
    return any(k in text for k in custom_kws)
  if is_target:
    return True
  return any(term.lower() in text for term in JUDICIAL_CORE_TERMS)


def clean_html_text(raw_html: str) -> str:
  if not raw_html:
    return ""
  txt = html.unescape(str(raw_html))
  txt = re.sub(r"<[^>]+>", " ", txt)
  txt = re.sub(r"\s+", " ", txt).strip()
  return txt


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

  ns = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}

  for item in root.findall(".//item"):
    title = clean_html_text(item.findtext("title") or "")
    link = (item.findtext("link") or "").strip()
    desc = clean_html_text(item.findtext("description") or "")
    pub_raw = item.findtext("pubDate") or item.findtext("dc:date") or ""
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
    pub_str, pub_ts = parse_any_date(pub_raw, fallback_offset_sec=fallback_offset)
    results.append({
        "title": title,
        "url": link,
        "raw_snippet": desc[:500] if desc else title,
        "source_name": source_name or default_platform,
        "platform": default_platform,
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
    })

  for entry in root.findall(".//atom:entry", ns):
    title = clean_html_text(entry.findtext("atom:title", default="", namespaces=ns))
    link_el = entry.find("atom:link", ns)
    link = link_el.attrib.get("href", "").strip() if link_el is not None else ""
    pub_raw = (
        entry.findtext("atom:published", default="", namespaces=ns)
        or entry.findtext("atom:updated", default="", namespaces=ns)
    )
    author_name = entry.findtext(
        "atom:author/atom:name", default=default_source, namespaces=ns
    )
    if not title or not link:
      continue
    pub_str, pub_ts = parse_any_date(pub_raw, fallback_offset_sec=fallback_offset)
    results.append({
        "title": title,
        "url": link,
        "raw_snippet": title,
        "source_name": author_name or default_source or default_platform,
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
      progress_cb(min(0.95, step / max(1, total_steps)), f"رصد الصحافة الوطنية: {q}")
    rss_url = (
        "https://news.google.com/rss/search?q="
        f"{urllib.parse.quote(q + ' when:7d')}&hl=ar&gl=MA&ceid=MA:ar"
    )
    try:
      r = requests.get(rss_url, headers=DEFAULT_HEADERS, timeout=10)
      if r.status_code == 200:
        for entry in parse_rss_xml(r.content, "الصحف"):
          if entry["url"] not in seen_urls and is_relevant_item(
              entry["title"], entry["raw_snippet"], keywords_input
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
              entry["title"], entry["raw_snippet"], keywords_input
          ):
            seen_urls.add(entry["url"])
            items.append(entry)
    except Exception:
      pass

  return items


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
        m = re.search(r"var ytInitialData = (\{.*?\});</script>", r.text)
        if not m:
          m = re.search(r"ytInitialData\s*=\s*(\{.*?\});", r.text)
        if m:
          video_blocks = re.findall(
              r'"videoRenderer":\{"videoId":"([a-zA-Z0-9_-]{11})".*?"title":\{"runs":\[\{"text":"(.*?)"\}\]'
              r'.*?(?:"publishedTimeText":\{"simpleText":"(.*?)"\})?',
              m.group(1),
          )
          for vid, raw_title, pub_rel in video_blocks[:15]:
            v_url = f"https://www.youtube.com/watch?v={vid}"
            if v_url in seen_urls:
              continue
            title = clean_html_text(
                raw_title.encode("utf-8").decode("unicode_escape", errors="ignore")
                if "\\u" in raw_title
                else raw_title
            )
            if not is_relevant_item(title, "", keywords_input):
              continue
            pub_str, pub_ts = parse_any_date(pub_rel, fallback_offset_sec=5400)
            seen_urls.add(v_url)
            items.append({
                "title": title,
                "url": v_url,
                "raw_snippet": title,
                "source_name": "YouTube",
                "platform": "يوتيوب",
                "pub_date": pub_str,
                "pub_timestamp": pub_ts,
            })
    except Exception:
      pass

  return items


def _multi_engine_social_search(
    platform_label: str,
    site_domains: list,
    keywords_input: str,
    progress_cb=None,
):
  items = []
  seen_urls = set()
  queries = build_search_queries(keywords_input)[:3]
  site_filter = " OR ".join(f"site:{d}" for d in site_domains)

  for idx, q in enumerate(queries):
    if is_stop_requested():
      break
    if progress_cb:
      progress_cb(
          (idx + 1) / max(1, len(queries) + 1),
          f"مسح {platform_label}: {q}",
      )

    for d in site_domains[:2]:
      if is_stop_requested():
        break
      bing_q = f"site:{d} {q}"
      bing_rss = f"https://www.bing.com/search?q={urllib.parse.quote(bing_q)}&format=rss"
      try:
        r = requests.get(bing_rss, headers=DEFAULT_HEADERS, timeout=10)
        if r.status_code == 200 and b"<item>" in r.content:
          for entry in parse_rss_xml(
              r.content,
              platform_label,
              default_source=platform_label,
              fallback_offset=5400,
          ):
            if entry["url"] not in seen_urls and is_relevant_item(
                entry["title"], entry["raw_snippet"], keywords_input
            ):
              seen_urls.add(entry["url"])
              items.append(entry)
      except Exception:
        pass

    if DDGS is not None and not is_stop_requested():
      try:
        with DDGS() as ddgs:
          ddg_q = f"({site_filter}) {q}"
          for res in ddgs.text(ddg_q, max_results=10):
            href = (res.get("href") or res.get("url") or "").strip()
            title = clean_html_text(res.get("title") or "")
            body = clean_html_text(res.get("body") or "")
            if not href or href in seen_urls:
              continue
            if not is_relevant_item(title, body, keywords_input):
              continue
            pub_str, pub_ts = parse_any_date("", fallback_offset_sec=7200)
            seen_urls.add(href)
            items.append({
                "title": title or body[:90],
                "url": href,
                "raw_snippet": body or title,
                "source_name": platform_label,
                "platform": platform_label,
                "pub_date": pub_str,
                "pub_timestamp": pub_ts,
            })
      except Exception:
        pass

  if not is_stop_requested():
    platform_ar_keywords = {
        "فيسبوك": "فيسبوك OR فايسبوك OR Facebook",
        "إكس": "منصة إكس OR تويتر OR تغريدة",
        "أخرى": "تيك توك OR إنستغرام OR لينكدإن OR TikTok",
    }
    p_kw = platform_ar_keywords.get(platform_label, platform_label)
    base_q = queries[0] if queries else "المجلس الأعلى للسلطة القضائية المغرب"
    gnews_social_url = (
        "https://news.google.com/rss/search?q="
        f"{urllib.parse.quote(f'{base_q} ({p_kw}) when:7d')}&hl=ar&gl=MA&ceid=MA:ar"
    )
    try:
      r = requests.get(gnews_social_url, headers=DEFAULT_HEADERS, timeout=10)
      if r.status_code == 200:
        for entry in parse_rss_xml(
            r.content, platform_label, fallback_offset=3600
        ):
          if entry["url"] not in seen_urls and is_relevant_item(
              entry["title"], entry["raw_snippet"], keywords_input
          ):
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
              pub_str, pub_ts = parse_any_date("", fallback_offset_sec=5400)
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
  title = item.get("title", "")
  snippet = item.get("raw_snippet", "") or title

  default_result = {
      "summary": snippet if len(snippet) > 30 else f"رصد إعلامي قضائي: {title}",
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
        "حلل الخبر التالي وأرجع JSON فقط بالمفاتيح التالية:\n"
        '{"summary": "ملخص مركز ودقيق في جملتين بالعربية", '
        '"sentiment": "إيجابي أو محايد أو سلبي", '
        '"category": "بلاغ رسمي أو محاكم وقضايا أو شؤون قضائية أو رأي ومتابعات", '
        '"relevance_score": 90}\n'
        f"العنوان: {title}\n"
        f"المقتطف: {snippet[:400]}"
    )
    resp = model.generate_content(prompt)
    txt = (resp.text or "").strip()
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if m:
      parsed = json.loads(m.group(0))
      return {
          "summary": parsed.get("summary") or default_result["summary"],
          "sentiment": parsed.get("sentiment") or "محايد",
          "category": parsed.get("category") or "شؤون قضائية",
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
      f"📌 *العنوان:* {item.get('title', '')}\n\n"
      f"📝 *الملخص:* {item.get('summary', '')}\n\n"
      f"🕒 *التاريخ:* {item.get('pub_date', '')} | *التصنيف:* {item.get('category', '')}\n"
      f"🔗 [رابط المصدر الأصلي]({item.get('url', '')})"
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

  # 1. قراءة الروابط والعناوين الموجودة سريعا جدا مع قفل آمن وإغلاق الاتصال فورا
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

  # 2. فلترة العناصر الجديدة وترتيبها زمنيا (خارج اتصال SQLite تماما لمنع أي قفل!)
  candidates = []
  seen_batch_urls = set()
  seen_batch_titles = set()
  for it in sorted(
      items, key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
  ):
    u = (it.get("url") or "").strip()
    t = (it.get("title") or "").strip()
    if not u or not t:
      continue
    if u in existing_urls or t in existing_titles:
      continue
    if u in seen_batch_urls or t in seen_batch_titles:
      continue
    seen_batch_urls.add(u)
    seen_batch_titles.add(t)
    candidates.append(it)

  if not candidates:
    return 0

  # 3. تحليل الذكاء الاصطناعي خارج اتصال قاعدة البيانات
  api_key = (cfg.get("gemini_api_key") or "").strip()
  prepared_rows = []
  ai_calls = 0

  for it in candidates:
    if is_stop_requested():
      break
    if ai_calls < 8 and api_key.startswith("AIza"):
      ai_res = analyze_with_gemini(it, api_key)
      ai_calls += 1
    else:
      snippet = it.get("raw_snippet") or it.get("title", "")
      ai_res = {
          "summary": (
              snippet
              if len(snippet) > 30
              else f"رصد قضائي: {it.get('title', '')}"
          ),
          "sentiment": "محايد",
          "category": "شؤون قضائية",
          "relevance_score": 85,
      }

    pub_str = it.get("pub_date") or ""
    pub_ts = float(it.get("pub_timestamp") or 0)
    if pub_ts <= 0:
      pub_str, pub_ts = parse_any_date(pub_str, fallback_offset_sec=3600)

    record = {
        "title": it.get("title", "").strip(),
        "summary": ai_res["summary"],
        "source_name": it.get("source_name") or it.get("platform", "الصحف"),
        "platform": it.get("platform", "الصحف"),
        "url": it.get("url", "").strip(),
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "sentiment": ai_res["sentiment"],
        "category": ai_res["category"],
        "relevance_score": int(ai_res["relevance_score"]),
        "is_custom_target": (
            1 if (is_target_run or it.get("is_custom_target")) else 0
        ),
        "raw_snippet": (it.get("raw_snippet") or "")[:600],
        "created_at": time.time(),
    }
    prepared_rows.append(record)

  if not prepared_rows:
    return 0

  # 4. إدخال دفعة واحدة سريعة ومؤمنة بالكامل داخل قفل SQLite مع إصلاح ذاتي للجدول
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

  # 5. تحديث ملف الأرشيف الدائم وإرسال تنبيهات تيليجرام
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

    # تحديث طابع آخر تشغيل فورا لمنع أي خيط آخر من تكرار الدورة بالتوازي
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
# 9. تهيئة واجهة Streamlit والتصميم الزجاجي المظلم (Dark Glassmorphism)
# =====================================================================
st.set_page_config(
    page_title="المرصد الوطني للعدالة والقضاء",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_db()
ensure_background_daemon()

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Cairo', sans-serif !important;
    direction: rtl !important;
    text-align: right !important;
    background: radial-gradient(circle at 15% 15%, #111c35 0%, #090d16 55%, #05080f 100%) !important;
    color: #f1f5f9 !important;
}

.block-container {
    padding-top: 1.4rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 1420px !important;
}

/* الهيدر الزجاجي الفخم */
.hero-glass {
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.82) 0%, rgba(30, 41, 59, 0.65) 100%);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(56, 189, 248, 0.25);
    border-radius: 20px;
    padding: 18px 26px;
    margin-bottom: 18px;
    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 14px;
}

.hero-title {
    font-size: 1.75rem;
    font-weight: 900;
    background: linear-gradient(90deg, #38bdf8, #818cf8, #f472b6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    letter-spacing: -0.3px;
}

.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(16, 185, 129, 0.14);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: #34d399;
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 0.84rem;
    font-weight: 700;
}

.pulse-dot {
    width: 9px;
    height: 9px;
    background: #10b981;
    border-radius: 50%;
    box-shadow: 0 0 10px #10b981;
    animation: pulseGlow 1.6s infinite ease-in-out;
}

@keyframes pulseGlow {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.35); opacity: 0.55; }
}

/* إلغاء الخلفية البيضاء لجميع الأزرار بشكل مطلق وتطبيق تدرجات داكنة احترافية */
div.stButton > button,
div.stDownloadButton > button,
div[data-testid="stFormSubmitButton"] > button {
    width: 100% !important;
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important;
    color: #f8fafc !important;
    border: 1px solid rgba(148, 163, 184, 0.32) !important;
    border-radius: 13px !important;
    padding: 0.62rem 0.9rem !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
    font-size: 0.92rem !important;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.38) !important;
    transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1) !important;
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
    box-shadow: 0 10px 24px rgba(56, 189, 248, 0.28) !important;
}

/* ألوان مخصصة لكل منصة ولكل زر عبر :has() */
div[data-testid="stVerticalBlock"]:has(.btn-marker-all) div.stButton > button {
    background: linear-gradient(135deg, #0284c7 0%, #1d4ed8 100%) !important;
    border: 1px solid rgba(125, 211, 252, 0.5) !important;
    box-shadow: 0 6px 20px rgba(2, 132, 199, 0.35) !important;
}
div[data-testid="stVerticalBlock"]:has(.btn-marker-press) div.stButton > button {
    background: linear-gradient(135deg, #059669 0%, #065f46 100%) !important;
    border: 1px solid rgba(110, 231, 183, 0.45) !important;
    box-shadow: 0 6px 20px rgba(5, 150, 105, 0.32) !important;
}
div[data-testid="stVerticalBlock"]:has(.btn-marker-fb) div.stButton > button {
    background: linear-gradient(135deg, #2563eb 0%, #1e3a8a 100%) !important;
    border: 1px solid rgba(147, 197, 253, 0.45) !important;
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.35) !important;
}
div[data-testid="stVerticalBlock"]:has(.btn-marker-x) div.stButton > button {
    background: linear-gradient(135deg, #334155 0%, #0f172a 100%) !important;
    border: 1px solid rgba(203, 213, 225, 0.4) !important;
    box-shadow: 0 6px 20px rgba(51, 65, 85, 0.4) !important;
}
div[data-testid="stVerticalBlock"]:has(.btn-marker-yt) div.stButton > button {
    background: linear-gradient(135deg, #dc2626 0%, #7f1d1d 100%) !important;
    border: 1px solid rgba(252, 165, 165, 0.45) !important;
    box-shadow: 0 6px 20px rgba(220, 38, 38, 0.35) !important;
}
div[data-testid="stVerticalBlock"]:has(.btn-marker-other) div.stButton > button {
    background: linear-gradient(135deg, #7c3aed 0%, #4c1d95 100%) !important;
    border: 1px solid rgba(196, 181, 253, 0.45) !important;
    box-shadow: 0 6px 20px rgba(124, 58, 237, 0.35) !important;
}
div[data-testid="stVerticalBlock"]:has(.btn-marker-target) div.stButton > button {
    background: linear-gradient(135deg, #d97706 0%, #78350f 100%) !important;
    border: 1px solid rgba(253, 230, 138, 0.45) !important;
    box-shadow: 0 6px 20px rgba(217, 119, 6, 0.35) !important;
}
div[data-testid="stVerticalBlock"]:has(.btn-marker-stop) div.stButton > button {
    background: linear-gradient(135deg, #991b1b 0%, #450a0a 100%) !important;
    border: 1px solid rgba(248, 113, 113, 0.45) !important;
    padding: 0.38rem 0.65rem !important;
    font-size: 0.8rem !important;
}

/* رادار المسح الضوئي 360 درجة */
.radar-panel {
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(56, 189, 248, 0.38);
    border-radius: 18px;
    padding: 18px 24px;
    margin: 12px 0 18px 0;
    display: flex;
    align-items: center;
    gap: 20px;
    box-shadow: 0 10px 30px rgba(2, 132, 199, 0.22);
}

.radar-scanner {
    width: 66px;
    height: 66px;
    min-width: 66px;
    border-radius: 50%;
    position: relative;
    background:
        radial-gradient(circle, rgba(56, 189, 248, 0.15) 20%, transparent 21%),
        radial-gradient(circle, transparent 48%, rgba(56, 189, 248, 0.25) 49%, transparent 51%),
        #070d19;
    border: 2px solid #38bdf8;
    box-shadow: 0 0 20px rgba(56, 189, 248, 0.45), inset 0 0 15px rgba(56, 189, 248, 0.25);
    overflow: hidden;
}

.radar-scanner::before {
    content: "";
    position: absolute;
    inset: -50%;
    background: conic-gradient(from 0deg, transparent 55%, rgba(56, 189, 248, 0.75) 100%);
    animation: radarSpin 1.35s linear infinite;
}

.radar-scanner::after {
    content: "";
    position: absolute;
    top: 50%;
    left: 50%;
    width: 8px;
    height: 8px;
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
    background: linear-gradient(135deg, rgba(6, 95, 70, 0.85) 0%, rgba(4, 120, 87, 0.75) 100%);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(52, 211, 153, 0.55);
    border-radius: 16px;
    padding: 12px 22px;
    margin: 10px 0 16px 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    color: #ecfdf5;
    font-weight: 800;
    box-shadow: 0 8px 25px rgba(16, 185, 129, 0.25);
}

/* بطاقات الإحصائيات الزجاجية */
.metric-glass {
    background: rgba(15, 23, 42, 0.68);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 16px;
    padding: 14px 16px;
    text-align: center;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
}

.metric-num {
    font-size: 1.65rem;
    font-weight: 900;
    color: #38bdf8;
    line-height: 1.2;
}

.metric-lbl {
    font-size: 0.82rem;
    color: #94a3b8;
    font-weight: 700;
}

/* بطاقات الأخبار والمنشورات الزجاجية */
.news-card {
    background: linear-gradient(145deg, rgba(15, 23, 42, 0.84) 0%, rgba(30, 41, 59, 0.64) 100%);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-right: 4px solid #38bdf8;
    border-radius: 16px;
    padding: 18px 22px;
    margin-bottom: 14px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.32);
    transition: transform 0.2s ease, border-color 0.2s ease;
}

.news-card:hover {
    transform: translateY(-2px);
    border-color: rgba(56, 189, 248, 0.45);
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
    gap: 8px;
    margin-bottom: 8px;
    font-size: 0.82rem;
    color: #94a3b8;
}

.badge-plat {
    padding: 3px 11px;
    border-radius: 999px;
    font-weight: 800;
    font-size: 0.78rem;
    background: rgba(56, 189, 248, 0.16);
    color: #7dd3fc;
    border: 1px solid rgba(56, 189, 248, 0.35);
}

.news-title {
    font-size: 1.12rem;
    font-weight: 800;
    color: #f8fafc;
    margin: 4px 0 8px 0;
    line-height: 1.5;
}

.news-summary {
    font-size: 0.94rem;
    color: #cbd5e1;
    line-height: 1.65;
    margin-bottom: 12px;
}

.news-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(56, 189, 248, 0.14);
    border: 1px solid rgba(56, 189, 248, 0.35);
    color: #38bdf8 !important;
    text-decoration: none !important;
    padding: 5px 14px;
    border-radius: 10px;
    font-size: 0.84rem;
    font-weight: 700;
}

.news-link:hover {
    background: rgba(56, 189, 248, 0.28);
}

/* التبويبات وحقول الإدخال الداكنة */
div[data-baseweb="tab-list"] {
    gap: 8px !important;
    background: rgba(15, 23, 42, 0.75) !important;
    padding: 6px !important;
    border-radius: 14px !important;
    border: 1px solid rgba(148, 163, 184, 0.18) !important;
}

button[data-baseweb="tab"] {
    background: transparent !important;
    color: #94a3b8 !important;
    border-radius: 10px !important;
    padding: 8px 16px !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, #0284c7 0%, #1e40af 100%) !important;
    color: #ffffff !important;
}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div {
    background-color: rgba(15, 23, 42, 0.85) !important;
    border-color: rgba(148, 163, 184, 0.3) !important;
    color: #f8fafc !important;
    border-radius: 12px !important;
}

input {
    color: #f8fafc !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# =====================================================================
# 10. تحميل الإعدادات والبيانات
# =====================================================================
cfg = load_credentials()
custom_targets = load_custom_targets()
monitor_state = load_monitor_state()
rt_state = get_shared_runtime()

# القائمة الجانبية للإعدادات والنسخ الاحتياطي
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
# 11. الهيدر الرئيسي وشريط البحث المخصص
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

st.markdown(
    f"""
<div class="hero-glass">
    <h1 class="hero-title">⚖️ المرصد الوطني للعدالة والقضاء</h1>
    <div class="status-pill">
        <span class="pulse-dot"></span>
        <span>{auto_badge_text}</span>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# شريط البحث الاختياري وإدارة الروابط المخصصة
col_search, col_target_exp = st.columns([2.2, 1.8])
with col_search:
  kw_input = st.text_input(
      "🔍 تخصيص بكلمات مفتاحية (اختياري)",
      value=cfg.get("keywords_input", ""),
      placeholder="اتركه فارغاً للرصد القضائي العام، أو أدخل كلمات مفصولة بفاصلة...",
      label_visibility="collapsed",
  )
  if kw_input != cfg.get("keywords_input", ""):
    cfg["keywords_input"] = kw_input
    save_credentials(cfg)

with col_target_exp:
  with st.expander(
      f"🎯 الروابط والقنوات المخصصة ({len(custom_targets)})", expanded=False
  ):
    with st.form("add_custom_target_form", clear_on_submit=True):
      c_u, c_k, c_b = st.columns([2.2, 1.3, 0.9])
      with c_u:
        new_t_url = st.text_input(
            "الرابط", placeholder="https://...", label_visibility="collapsed"
        )
      with c_k:
        new_t_kw = st.text_input(
            "كلمة (اختياري)",
            placeholder="كلمة فلترة...",
            label_visibility="collapsed",
        )
      with c_b:
        add_t_btn = st.form_submit_button("➕ إضافة")
      if add_t_btn and new_t_url.strip():
        custom_targets.append(
            {"url": new_t_url.strip(), "keyword": new_t_kw.strip()}
        )
        save_custom_targets(custom_targets)
        st.rerun()

    for idx, t_item in enumerate(list(custom_targets)):
      tc1, tc2 = st.columns([4.5, 1])
      with tc1:
        kw_tag = f" ({t_item['keyword']})" if t_item.get("keyword") else ""
        st.markdown(
            f"<div style='font-size:0.82rem;color:#cbd5e1;direction:ltr;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'>🔗 {html.escape(t_item['url'])}{html.escape(kw_tag)}</div>",
            unsafe_allow_html=True,
        )
      with tc2:
        if st.button("❌", key=f"del_target_{idx}"):
          custom_targets.pop(idx)
          save_custom_targets(custom_targets)
          st.rerun()

# =====================================================================
# 12. لوحة أزرار الرصد (الشامل، الخاص بكل منصة، والمخصص) مع أزرار الإيقاف
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
    st.markdown(f'<span class="{marker_cls}"></span>', unsafe_allow_html=True)
    if st.button(mode_label, key=f"start_scan_{mode_key}"):
      clear_stop_scan()
      triggered_mode = mode_key
    st.markdown('<span class="btn-marker-stop"></span>', unsafe_allow_html=True)
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
    radar_placeholder.markdown(
        f"""
        <div class="radar-panel">
            <div class="radar-scanner"></div>
            <div style="flex:1;">
                <div style="font-size:1.05rem;font-weight:800;color:#38bdf8;margin-bottom:4px;">
                    📡 {html.escape(status_msg)}
                </div>
                <div style="font-size:0.85rem;color:#94a3b8;">
                    مسح ذكي بزاوية 360° للمصادر القضائية والإعلامية... ({pct_int}%)
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
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
    done_placeholder.markdown(
        """
        <div class="done-banner" style="background:rgba(127,29,29,0.82);border-color:#f87171;">
            <span>🛑 تم إيقاف عملية الرصد بطلب من المستخدم</span>
            <span>STOPPED</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
  elif rt_state.get("last_done_mode"):
    c_new = int(rt_state.get("last_done_count", 0))
    done_placeholder.markdown(
        f"""
        <div class="done-banner">
            <span>✨ تـم بنجاح / DONE — تم رصد وتحديث القاعدة ({c_new} منشور/خبر جديد)</span>
            <span>100% DONE ✅</span>
        </div>
        """,
        unsafe_allow_html=True,
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

# شريط الإحصائيات السريع
m_cols = st.columns(6)
metrics_data = [
    ("الكل (24 ساعة)", len(live_articles)),
    ("الصحف", len(press_live)),
    ("فيسبوك", len(fb_live)),
    ("إكس", len(x_live)),
    ("يوتيوب", len(yt_live)),
    ("الأرشيف", len(archive_articles)),
]
for idx, (m_label, m_val) in enumerate(metrics_data):
  with m_cols[idx]:
    st.markdown(
        f"""
        <div class="metric-glass">
            <div class="metric-num">{m_val}</div>
            <div class="metric-lbl">{m_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)


def render_article_cards(
    items_list: list,
    empty_msg: str = "لا توجد منشورات مرصودة حالياً في هذا القسم.",
):
  if not items_list:
    st.markdown(
        f"<div style='text-align:center;padding:32px;color:#64748b;background:rgba(15,23,42,0.5);border-radius:16px;border:1px dashed rgba(148,163,184,0.2);'>{empty_msg}</div>",
        unsafe_allow_html=True,
    )
    return

  plat_css_map = {
      "الصحف": "plat-press",
      "فيسبوك": "plat-fb",
      "إكس": "plat-x",
      "يوتيوب": "plat-yt",
      "أخرى": "plat-other",
  }

  for item in items_list:
    plat = item.get("platform", "الصحف")
    css_cls = plat_css_map.get(plat, "plat-press")
    title_safe = html.escape(item.get("title") or "")
    summary_safe = html.escape(item.get("summary") or "")
    source_safe = html.escape(item.get("source_name") or plat)
    pub_date_safe = html.escape(item.get("pub_date") or "")
    rel_time = format_relative_arabic(float(item.get("pub_timestamp", 0)))
    category_safe = html.escape(item.get("category") or "شؤون قضائية")
    url_safe = html.escape(item.get("url") or "#")
    target_tag = (
        '<span class="badge-plat" style="background:rgba(217,119,6,0.2);color:#fcd34d;border-color:#f59e0b;">🎯 مخصص</span>'
        if int(item.get("is_custom_target", 0)) == 1
        else ""
    )

    st.markdown(
        f"""
        <div class="news-card {css_cls}">
            <div class="news-meta">
                <div>
                    <span class="badge-plat">{html.escape(plat)}</span>
                    {target_tag}
                    <span style="margin-right:8px;font-weight:700;color:#e2e8f0;">{source_safe}</span>
                    <span style="margin-right:8px;color:#64748b;">• {category_safe}</span>
                </div>
                <div style="direction:rtl;">
                    🕒 <strong style="color:#38bdf8;">{rel_time}</strong> ({pub_date_safe})
                </div>
            </div>
            <div class="news-title">{title_safe}</div>
            <div class="news-summary">{summary_safe}</div>
            <div>
                <a class="news-link" href="{url_safe}" target="_blank" rel="noopener noreferrer">
                    🔗 فتح المصدر الأصلي
                </a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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

  # تحديث تلقائي خفيف لواجهة المتصفح كل 60 ثانية لعرض المستجدات دون تدخل يدوي
  st.markdown(
      """
      <script>
      setTimeout(function() {
          window.parent.location.reload();
      }, 60000);
      </script>
      """,
      unsafe_allow_html=True,
  )
