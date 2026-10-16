import base64
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
# 1. إعدادات النظام والثوابت الأساسية والفلاتر الصارمة
# =====================================================================
REPO_DB_FILE = "morocco_justice_hub.db"
DB_FILE = os.path.join(tempfile.gettempdir(), "morocco_justice_hub_runtime.db")
PERSISTENT_HOME_DB = os.path.join(os.path.expanduser("~"), ".morocco_justice_hub_persistent.db")
ARCHIVE_JSON_FILE = "articles_archive.json"
PERSISTENT_HOME_ARCHIVE_JSON = os.path.join(os.path.expanduser("~"), ".morocco_justice_archive_persistent.json")
CREDENTIALS_FILE = "credentials.json"
CUSTOM_TARGETS_FILE = "custom_targets.json"
MONITOR_STATE_FILE = "monitor_state.json"
TELEGRAM_LEDGER_FILE = "telegram_sent_ledger.json"

DEFAULT_TG_TOKEN = "8806182263:AAFw5HbBup_TRif3FHvZP0QFYj0YPI4mb6c"
DEFAULT_TG_CHAT_ID = "1357905784"

GEMINI_MODELS_FALLBACK = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-3.5-flash-lite",
]
_WORKING_GEMINI_MODEL = None

DEFAULT_JUDICIAL_QUERIES = [
    "المجلس الأعلى للسلطة القضائية المغرب",
    "رئاسة النيابة العامة المغرب",
    "القضاء بالمغرب",
    "العدالة بالمغرب",
    "محكمة النقض المغرب",
]

STRICT_JUDICIAL_UNAMBIGUOUS = [
    "المجلس الأعلى للسلطة القضائية",
    "السلطة القضائية",
    "رئاسة النيابة العامة",
    "محكمة النقض",
    "المعهد العالي للقضاء",
    "المفتشية العامة للشؤون القضائية",
    "الودادية الحسنية للقضاة",
    "نادي قضاة المغرب",
    "محمد عبد النباوي",
    "هشام البلاوي",
    "الوكيل العام للملك",
    "وكيل الملك",
    "قاضي التحقيق",
    "القضاء المغربي",
    "القضاء بالمغرب",
    "العدالة بالمغرب",
    "منظومة العدالة",
    "إصلاح العدالة",
    "المحاكم المغربية",
    "محكمة الاستئناف",
    "المحكمة الابتدائية",
    "المحكمة الإدارية",
    "المحكمة التجارية",
    "المحكمة الدستورية",
    "المسطرة الجنائية",
    "المسطرة المدنية",
    "القانون الجنائي",
    "التنظيم القضائي",
]

JUDICIAL_GENERAL_TERMS = [
    "النيابة العامة",
    "القضاء",
    "قضائي",
    "قضائية",
    "القضاة",
    "قضاة",
    "القاضي",
    "المحاكم",
    "محكمة",
    "العدالة",
    "وزارة العدل",
    "وزير العدل",
    "هيئة الحكم",
    "الغرفة الجنائية",
    "الغرفة الجنحية",
    "هيئة المحامين",
    "الضابطة القضائية",
    "الشرطة القضائية",
]

MOROCCAN_CONTEXT_TERMS = [
    "المغرب",
    "مغربي",
    "مغربية",
    "بالمغرب",
    "المملكة المغربية",
    "الرباط",
    "الدار البيضاء",
    "مراكش",
    "فاس",
    "طنجة",
    "أكادير",
    "اكادير",
    "وجدة",
    "مكناس",
    "تطوان",
    "القنيطرة",
    "سلا",
    "العيون",
    "الداخلة",
    "بني ملال",
    "آسفي",
    "الجديدة",
    "الناظور",
    "الحسيمة",
    "تازة",
    "سطات",
    "برشيد",
    "المحمدية",
    "تمارة",
    "كلميم",
    "الرشيدية",
    "خريبكة",
    "العرائش",
    "القصر الكبير",
    "الخميسات",
    "تارودانت",
    "ورزازات",
    "تيزنيت",
    "الصويرة",
    "صفرو",
    "إفران",
    "خنيفرة",
    "جرسيف",
    "تاوريرت",
    "بركان",
    "سيدي قاسم",
    "سيدي سليمان",
    "بن جرير",
    "اليوسفية",
    "عبد النباوي",
    "وهبي",
    "البلاوي",
    "هسبريس",
    "أخبارنا",
    "العمق",
    "كود",
    "الصباح",
    "برلمان",
    "زنقة 20",
    "اليوم 24",
    "الأيام 24",
    "مدار 21",
    "كش 24",
    "أكادير 24",
    "طنجة 24",
    "ناظورسيتي",
]

BLOCKED_INAPPROPRIATE_TERMS = [
    "سكس",
    "إباحي",
    "اباحي",
    "اباحية",
    "إباحية",
    "جنس",
    "جنسي",
    "جنسية",
    "عاري",
    "عارية",
    "عراه",
    "بورن",
    "بورنو",
    "نيك",
    "شرموط",
    "قحب",
    "طيز",
    "زب",
    "كس ",
    "ثدي",
    "بزاز",
    "سحاق",
    "لواط",
    "شذوذ",
    "فضيحة",
    "فضائح",
    "روتيني اليومي",
    "رقص",
    "راقصة",
    "خلع",
    "مثير",
    "مثيرة",
    "ساخن",
    "ساخنة",
    "للكبار فقط",
    "+18",
    "18+",
    "فيلم كامل",
    "مشاهدة فيلم",
    "مسلسل",
    "حلقة",
    "كازينو",
    "مراهنات",
    "ربح المال",
    "تعارف",
    "زواج متعة",
    "مسيار",
    "شاجر",
    "porn",
    "xxx",
    "sex",
    "sexy",
    "nude",
    "naked",
    "nsfw",
    "onlyfans",
    "escort",
    "casino",
    "betting",
    "1xbet",
    "erotic",
    "hentai",
    "xvideos",
    "xnxx",
    "pornhub",
    "stripchat",
    "chaturbate",
    "cam4",
    "brazzers",
    "redtube",
    "youporn",
    "spankbang",
    "rule34",
    "jav",
    "milf",
    "fetish",
    "webcam",
    "hookup",
    "dating",
    "boobs",
    "pussy",
    "dick",
    "cock",
    "ass ",
    "anal",
    "blowjob",
    "bdsm",
    "lesbian",
    "gay",
    "transgender",
    "adult",
]

MOROCCAN_PRESS_SITES = [
    {"domain": "hespress.com", "name": "هسبريس", "rss": "https://www.hespress.com/feed"},
    {"domain": "akhbarona.com", "name": "أخبارنا", "rss": "https://www.akhbarona.com/feed"},
    {"domain": "agadir24.info", "name": "أكادير 24", "rss": "https://agadir24.info/feed"},
    {"domain": "kech24.com", "name": "كش 24", "rss": "https://www.kech24.com/feed"},
    {"domain": "alayam24.com", "name": "الأيام 24", "rss": "https://www.alayam24.com/feed"},
    {"domain": "madar21.com", "name": "مدار 21", "rss": "https://madar21.com/feed"},
    {"domain": "sabahagadir.com", "name": "صباح أكادير", "rss": "https://sabahagadir.com/feed"},
    {"domain": "goud.ma", "name": "كود", "rss": "https://www.goud.ma/feed"},
    {"domain": "assabah.ma", "name": "الصباح", "rss": "https://assabah.ma/feed"},
    {"domain": "thevoice.ma", "name": "ذا فويس", "rss": "https://thevoice.ma/feed"},
    {"domain": "nadorcity.com", "name": "ناظورسيتي", "rss": ""},
    {"domain": "al3omk.com", "name": "العمق المغربي", "rss": "https://al3omk.com/feed"},
    {"domain": "alyaoum24.com", "name": "اليوم 24", "rss": "https://alyaoum24.com/feed"},
    {"domain": "rue20.com", "name": "زنقة 20", "rss": "https://rue20.com/feed"},
    {"domain": "le360.ma", "name": "Le360", "rss": ""},
    {"domain": "barlamane.com", "name": "برلمان.كوم", "rss": "https://www.barlamane.com/feed"},
    {"domain": "tanja24.com", "name": "طنجة 24", "rss": "https://tanja24.com/feed"},
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

# ترويسات خاصة يسمح لها فيسبوك بقراءة بيانات الصفحات والمنشورات العامة دون طلب تسجيل الدخول
FB_CRAWLER_HEADERS = {
    "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Accept-Language": "ar-MA,ar;q=0.9,fr;q=0.8,en;q=0.7",
}

FB_PREVIEW_BOT_HEADERS = [
    FB_CRAWLER_HEADERS,
    {
        "User-Agent": "WhatsApp/2.24.12.78 A",
        "Accept-Language": "ar-MA,ar;q=0.9,fr;q=0.8,en;q=0.7",
    },
    {
        "User-Agent": "TelegramBot (like TwitterBot)",
        "Accept-Language": "ar-MA,ar;q=0.9,fr;q=0.8,en;q=0.7",
    },
    {
        "User-Agent": "Twitterbot/1.0",
        "Accept-Language": "ar-MA,ar;q=0.9,fr;q=0.8,en;q=0.7",
    },
]

INTERVAL_MAP = {
    "كل 15 دقيقة": 900,
    "كل ساعة": 3600,
    "كل 3 ساعات": 10800,
    "كل 6 ساعات": 21600,
    "كل 12 ساعة": 43200,
    "كل 24 ساعة": 86400,
}

SEARCH_PERIOD_MAP = {
    "آخر ساعة": {"sec": 3600, "gnews": "1h", "ddg": "d", "yt": "EgIIAQ%253D%253D"},
    "آخر 24 ساعة": {"sec": 86400, "gnews": "1d", "ddg": "d", "yt": "EgIIAg%253D%253D"},
    "آخر 7 أيام": {"sec": 7 * 86400, "gnews": "7d", "ddg": "w", "yt": "EgIIAw%253D%253D"},
    "آخر شهر": {"sec": 30 * 86400, "gnews": "30d", "ddg": "m", "yt": "EgIIBA%253D%253D"},
    "آخر 3 أشهر": {"sec": 90 * 86400, "gnews": "90d", "ddg": "y", "yt": "CAI%253D"},
    "آخر 6 أشهر": {"sec": 180 * 86400, "gnews": "180d", "ddg": "y", "yt": "CAI%253D"},
    "آخر 12 شهراً": {"sec": 365 * 86400, "gnews": "1y", "ddg": "y", "yt": "CAI%253D"},
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
  txt = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]", "", txt)
  txt = re.sub(r"<[^>]+>", " ", txt)
  txt = re.sub(r"[\r\n\t]+", " ", txt)
  txt = re.sub(r"\s+", " ", txt).strip()
  return txt


def strip_internal_url_fragments(url: str) -> str:
  return re.sub(r"#(?:plat|v4target|v3target|v2target|target)=[^\s#]*", "", str(url or "").strip())


def normalize_arabic_for_dedup(text: str) -> str:
  """تطبيع النص العربي بدقة عالية لكشف الأخبار والمنشورات المكررة حتى مع اختلاف التشكيل أو علامات الترقيم."""
  if not text:
    return ""
  t = clean_display_text(text).lower()
  t = re.sub(r"https?://\S+", " ", t)
  t = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", t)
  t = re.sub(r"[أإآٱ]", "ا", t)
  t = re.sub(r"ة", "ه", t)
  t = re.sub(r"ى", "ي", t)
  t = re.sub(r"ؤ", "و", t)
  t = re.sub(r"ئ", "ي", t)
  t = re.sub(r"[^\u0600-\u06FFa-z0-9\s]", " ", t)
  t = re.sub(r"\s+", " ", t).strip()
  return t


def extract_canonical_post_or_video_id(url: str) -> str:
  """استخراج المعرف الفريد للفيديو أو المنشور (YouTube / Facebook / X) لمنع تكرار نفس المنشور بصيغ روابط مختلفة."""
  u = clean_social_post_url(url)
  if not u:
    return ""
  m_yt = re.search(
      r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
      u,
  )
  if m_yt:
    return f"yt:{m_yt.group(1)}"

  m_x = re.search(r"(?:x\.com|twitter\.com)/[^/]+/status/(\d{10,22})", u, re.IGNORECASE)
  if m_x:
    return f"x:{m_x.group(1)}"

  if "facebook.com" in u.lower() or "fb.watch" in u.lower():
    parsed = urllib.parse.urlparse(u)
    qs = urllib.parse.parse_qs(parsed.query)
    for k in ("story_fbid", "fbid", "v"):
      if qs.get(k) and len(qs[k][0].strip()) >= 6:
        return f"fb:{qs[k][0].strip()}"
    parts = [p.strip() for p in urllib.parse.unquote(parsed.path).strip("/").split("/") if p.strip()]
    for idx, seg in enumerate(parts):
      if seg.lower() in ("posts", "videos", "reel", "reels", "photos", "permalink") and idx + 1 < len(parts):
        tail = parts[-1].strip()
        if tail.startswith("pfbid") or (tail.isdigit() and len(tail) >= 7):
          return f"fb:{tail}"
  return ""


def canonicalize_url_for_dedup(url: str) -> str:
  """توحيد الرابط الأساسي بدون وسوم داخلية أو معاملات تتبع لضمان عدم جلب أو إرسال نفس الخبر مرتين."""
  u = clean_social_post_url(url)
  if not u:
    return ""
  try:
    p = urllib.parse.urlparse(u)
    netloc = p.netloc.lower().replace("www.", "").replace("m.", "").replace("web.", "")
    path = urllib.parse.unquote(p.path).rstrip("/")
    if netloc in ("youtube.com", "youtu.be", "facebook.com", "x.com", "twitter.com"):
      pid = extract_canonical_post_or_video_id(u)
      if pid:
        return f"{netloc}/{pid}"
    return f"{netloc}{path}".lower()
  except Exception:
    return u.lower()


def compute_article_dedup_keys(title: str, url: str) -> set:
  """توليد مفاتيح البصمة الفريدة للخبر (الرابط الموحد + معرف المنشور + البصمة النصية للعنوان)."""
  keys = set()
  raw_u = strip_internal_url_fragments(url)
  if raw_u:
    keys.add(f"raw_u:{raw_u.lower().rstrip('/')}")
  canon_u = canonicalize_url_for_dedup(url)
  if canon_u and len(canon_u) >= 6:
    keys.add(f"canon_u:{canon_u}")
  pid = extract_canonical_post_or_video_id(url)
  if pid:
    keys.add(f"pid:{pid}")
  norm_t = normalize_arabic_for_dedup(title)
  if len(norm_t) >= 20:
    keys.add(f"title:{norm_t[:85]}")
  return keys


def clean_social_post_url(url: str) -> str:
  """تنظيف وفك تغليف روابط منصات التواصل الاجتماعي مع الحفاظ الكامل على معرفات المنشور (story_fbid, id, fbid, v)."""
  u = strip_internal_url_fragments(url)
  if not u:
    return ""
  u = html.unescape(u).strip()

  # فك تغليف روابط Yahoo Search Redirect (/RU=https%3A%2F%2F.../RK=...)
  m_yahoo = re.search(r"/RU=(https?%3A%2F%2F[^/]+)/RK=", u, re.IGNORECASE)
  if m_yahoo:
    try:
      u = urllib.parse.unquote(m_yahoo.group(1)).strip()
    except Exception:
      pass

  # فك تغليف روابط DuckDuckGo Redirect (//duckduckgo.com/l/?uddg=...)
  if "uddg=" in u:
    try:
      qs_d = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
      if "uddg" in qs_d and qs_d["uddg"]:
        u = qs_d["uddg"][0].strip()
    except Exception:
      pass

  # فك تغليف روابط Bing RSS أو Bing Click
  if "bing.com/" in u.lower() and ("url=" in u or "u=" in u):
    try:
      qs_b = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
      if "url" in qs_b and qs_b["url"]:
        u = qs_b["url"][0].strip()
      elif "u" in qs_b and qs_b["u"]:
        raw_b = qs_b["u"][0].strip()
        if raw_b.startswith("a1"):
          padded = raw_b[2:] + "=" * ((4 - len(raw_b[2:]) % 4) % 4)
          u = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
    except Exception:
      pass

  # تحويل المسارات النسبية لفيسبوك إلى روابط كاملة
  if u.startswith("/") and not u.startswith("//"):
    u = urllib.parse.urljoin("https://www.facebook.com", u)
  elif u.startswith("//"):
    u = "https:" + u

  # فك تغليف روابط مشاركة أو تحويل فيسبوك (sharer.php, plugins/post.php, plugins/video.php, l.php, login.php)
  for _ in range(2):
    parsed_wrap = urllib.parse.urlparse(u)
    path_low = parsed_wrap.path.lower()
    if any(
        w in path_low
        for w in [
            "/sharer",
            "/plugins/post.php",
            "/plugins/video.php",
            "/l.php",
            "/login",
        ]
    ):
      qs_w = urllib.parse.parse_qs(parsed_wrap.query)
      inner_u = (
          (qs_w.get("u") or [None])[0]
          or (qs_w.get("href") or [None])[0]
          or (qs_w.get("next") or [None])[0]
      )
      if inner_u and inner_u.startswith("http"):
        u = html.unescape(inner_u).strip()
      else:
        break
    else:
      break

  try:
    parsed = urllib.parse.urlparse(u)
    netloc_low = parsed.netloc.lower()
    if netloc_low.endswith("facebook.com") or netloc_low == "fb.com":
      clean_netloc = "www.facebook.com"
      keep_params = {
          "story_fbid",
          "id",
          "fbid",
          "v",
          "set",
          "multi_permalinks",
          "post_id",
          "post_ref",
      }
      filtered_qs = [
          (k, val)
          for k, val in urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
          if k.lower() in keep_params
      ]
      new_query = urllib.parse.urlencode(filtered_qs)
      u = urllib.parse.urlunparse(
          ("https", clean_netloc, parsed.path, "", new_query, "")
      )
  except Exception:
    pass

  return u


def is_direct_social_post_url(
    url: str, platform: str = "", allow_post_search: bool = False
) -> bool:
  """التحقق الصارم من أن الرابط يوجه إلى المنشور/الفيديو/التغريدة بعينها وليس إلى الصفحة العامة أو تبويب فرعي."""
  u = clean_social_post_url(url)
  if not u or not u.startswith("http"):
    return False

  parsed = urllib.parse.urlparse(u)
  dom = parsed.netloc.lower()
  path = urllib.parse.unquote(parsed.path).strip("/")
  path_low = path.lower()
  qs = urllib.parse.parse_qs(parsed.query)

  is_fb = (
      platform == "فيسبوك"
      or "facebook.com" in dom
      or "fb.com" in dom
      or "fb.watch" in dom
  )
  is_x = platform == "إكس" or "x.com" in dom or "twitter.com" in dom
  is_yt = platform == "يوتيوب" or "youtube.com" in dom or "youtu.be" in dom

  if is_fb:
    if "fb.watch" in dom and len(path) >= 4:
      return True
    if any(
        bad in path_low
        for bad in [
            "plugins/page.php",
            "login",
            "sharer",
            "hashtag/",
            "public/",
            "pages/category",
            "search/posts",
            "search/top",
            "search/",
        ]
    ):
      return False



    if (qs.get("story_fbid") or [""])[0].strip() or (qs.get("fbid") or [""])[0].strip() or (qs.get("post_id") or [""])[0].strip():
      return True

    if path_low in ("permalink.php", "story.php"):
      s_fbid = (qs.get("story_fbid") or qs.get("id") or [""])[0].strip()
      return bool(s_fbid and len(s_fbid) >= 5)

    if path_low in ("photo.php", "photo", "photos"):
      fbid = (qs.get("fbid") or [""])[0].strip()
      return bool(fbid and len(fbid) >= 5)

    if path_low in ("watch", "watch/live", "video.php"):
      v_id = (qs.get("v") or [""])[0].strip()
      return bool(v_id and len(v_id) >= 5)

    parts = [p.strip() for p in path.split("/") if p.strip()]
    parts_low = [p.lower() for p in parts]

    if len(parts_low) >= 3 and parts_low[0] == "share" and parts_low[1] in ("p", "v", "r"):
      return len(parts[2]) >= 4

    tab_words = {
        "posts",
        "videos",
        "photos",
        "reels",
        "reel",
        "about",
        "community",
        "Featured",
        "featured",
        "live",
        "live_videos",
        "streams",
        "mentions",
        "reviews",
        "followers",
        "following",
        "photos_by",
        "photos_albums",
    }

    for post_kind in ("posts", "permalink", "videos", "reel", "reels", "photos"):
      if post_kind in parts_low:
        idx = parts_low.index(post_kind)
        tail_segs = [s.strip() for s in parts[idx + 1 :] if s.strip() and s.strip().lower() not in tab_words]
        if not tail_segs:
          return False
        for seg_cand in tail_segs:
          if (
              seg_cand.startswith("pfbid")
              or (seg_cand.isdigit() and len(seg_cand) >= 6)
              or ":" in seg_cand
              or len(seg_cand) >= 5
          ):
            return True
        return False

    if "events" in parts_low:
      idx = parts_low.index("events")
      if idx + 1 < len(parts) and parts[idx + 1].isdigit() and len(parts[idx + 1]) >= 7:
        return True
      return False

    return False

  if is_x:
    return bool(re.search(r"/(?:status|statuses)/\d{8,}", u, re.IGNORECASE))

  if is_yt:
    if "youtu.be/" in u.lower():
      m_yb = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", u)
      return bool(m_yb)
    if "watch" in path_low:
      v_param = (qs.get("v") or [""])[0].strip()
      return bool(re.match(r"^[A-Za-z0-9_-]{11}$", v_param))
    m_short = re.search(r"^shorts/([A-Za-z0-9_-]{11})(?:$|/)", path)
    if m_short:
      return True
    return False

  return True


def _is_fb_post_owned_by_target(
    post_url: str,
    handle: str = "",
    page_id: str = "",
    page_official_name: str = "",
    og_title: str = "",
) -> bool:
  """التحقق من ملكية الصفحة للمنشور مع رفض المنشورات التابعة لصفحات أخرى وعدم حجب منشورات الصفحة بسبب جدار تسجيل الدخول."""
  u = clean_social_post_url(post_url)
  if not u or not is_direct_social_post_url(u, "فيسبوك"):
    return False
  parsed = urllib.parse.urlparse(u)
  path = urllib.parse.unquote(parsed.path).strip("/")
  parts = [p.strip() for p in path.split("/") if p.strip()]
  parts_low = [p.lower() for p in parts]
  qs = urllib.parse.parse_qs(parsed.query)

  clean_handle = (handle or "").strip().lower().lstrip("@")
  if clean_handle.startswith("fb_") or clean_handle.isdigit():
    clean_handle = ""
  clean_cid = (page_id or "").strip().lower()
  valid_owners = {x for x in [clean_handle, clean_cid] if x and len(x) >= 2}

  def _matches_official_name(text_to_check: str) -> bool:
    if not text_to_check or not page_official_name:
      return False
    t_norm = normalize_arabic_for_dedup(text_to_check)
    n_norm = normalize_arabic_for_dedup(page_official_name)
    if n_norm and len(n_norm) >= 3 and n_norm in t_norm:
      return True
    n_words = [w for w in n_norm.split() if len(w) >= 3]
    if len(n_words) >= 2 and all(w in t_norm for w in n_words[:2]):
      return True
    if len(n_words) == 1 and n_words[0] in t_norm:
      return True
    return False

  # 1) إذا كان الرابط منشور مجموعة: facebook.com/groups/{group_id_or_slug}/posts/...
  if len(parts_low) >= 2 and parts_low[0] == "groups":
    grp_owner = parts_low[1]
    if valid_owners:
      return grp_owner in valid_owners
    return _matches_official_name(og_title)

  # 2) إذا كان الرابط بصيغة people/{name}/{id}/... أو pages/{name}/{id}/...
  if len(parts_low) >= 3 and parts_low[0] in ("people", "pages"):
    p_name = parts_low[1].replace("-", " ")
    p_id = parts_low[2]
    if valid_owners:
      if (p_id in valid_owners) or (parts_low[1] in valid_owners) or (p_name in valid_owners):
        return True
      if clean_cid and p_id.isdigit() and p_id != clean_cid:
        return False
    if page_official_name and (_matches_official_name(p_name) or _matches_official_name(og_title)):
      return True
    return not bool(clean_handle)

  # 3) إذا كان الرابط يحتوي على اسم الصفحة الناشرة في المسار: facebook.com/{owner}/(posts|videos|photos|reels)/...
  if len(parts_low) >= 2 and parts_low[1] in ("posts", "videos", "photos", "reels", "permalink"):
    url_owner = parts_low[0]
    if url_owner in valid_owners:
      return True
    # إذا كان لدينا معرف نصي للصفحة (مثل hespress) وكان صاحب الرابط معرفاً نصياً مختلفاً، نرفضه فوراً
    if clean_handle and not url_owner.isdigit() and url_owner != clean_handle:
      return False
    # إذا كان لدينا معرف رقمي للصفحة وكان صاحب الرابط معرفاً رقمياً مختلفاً، نرفضه فوراً
    if clean_cid and clean_cid.isdigit() and url_owner.isdigit() and url_owner != clean_cid:
      return False
    if page_official_name and (_matches_official_name(url_owner.replace(".", " ").replace("-", " ")) or _matches_official_name(og_title)):
      return True
    # إذا كان صاحب الرابط رقمياً ولدينا handle نصي فقط (حيث يحول فيسبوك اسم الصفحة إلى رقمها في بعض الروابط)، نقبله ما لم يتعارض
    if url_owner.isdigit() and clean_handle:
      return True
    return bool(valid_owners or not page_official_name)

  # 4) إذا كان الرابط بصيغة permalink.php?story_fbid=...&id={page_id}
  if parts_low and parts_low[0] in ("permalink.php", "story.php"):
    url_id = ((qs.get("id") or [""])[0]).strip().lower()
    if url_id and clean_cid and clean_cid.isdigit():
      return url_id == clean_cid
    if _matches_official_name(og_title):
      return True
    return True

  # 5) الروابط المختصرة مثل watch/?v= أو reel/ أو photo.php?fbid= أو share/
  if og_title:
    if clean_handle and clean_handle in og_title.lower():
      return True
    if _matches_official_name(og_title):
      return True

  return True


def is_summary_just_title(title: str, summary: str) -> bool:
  t = clean_display_text(title)
  s = clean_display_text(summary)
  if not s or len(s) < 35:
    return True
  if "يتناول موضوع: «" in s or "رصد قضائي:" in s or "رصد إعلامي قضائي:" in s:
    return True
  s_core = re.sub(r"^[^:]+:\s*", "", s).strip()
  t_words = set(re.findall(r"[\u0600-\u06FF]{3,}", t))
  s_words = set(re.findall(r"[\u0600-\u06FF]{3,}", s_core))
  if not s_words:
    return True
  overlap = len(t_words & s_words) / max(1, len(s_words))
  if overlap > 0.82 and len(s_core) <= len(t) + 25:
    return True
  return False


def is_strictly_judicial_and_clean(
    title: str,
    snippet: str = "",
    url: str = "",
    keywords_input: str = "",
    is_target: bool = False,
) -> bool:
  t_clean = clean_display_text(title)
  s_clean = clean_display_text(snippet)
  u_clean = str(url or "").lower()
  combined = f"{t_clean} {s_clean}".lower()
  combined_with_url = f"{combined} {u_clean}"

  for bad_word in BLOCKED_INAPPROPRIATE_TERMS:
    if bad_word in combined_with_url:
      return False

  if len(t_clean) < 3 and len(s_clean) < 3:
    return False

  # رفض أي رابط لمنصات التواصل الاجتماعي يوجه إلى الصفحة العامة أو القناة بدلاً من المنشور/الفيديو بعينه
  if url:
    u_unwrapped = clean_social_post_url(url)
    u_dom = urllib.parse.urlparse(u_unwrapped).netloc.lower()
    if any(
        d in u_dom
        for d in [
            "facebook.com",
            "fb.com",
            "fb.watch",
            "x.com",
            "twitter.com",
            "youtube.com",
            "youtu.be",
        ]
    ):
      if not is_direct_social_post_url(u_unwrapped):
        return False

  custom_kws = [
      k.strip().lower()
      for k in re.split(r"[,،\n]+", str(keywords_input or ""))
      if k.strip()
  ]
  if custom_kws:
    if not any(k in combined for k in custom_kws):
      return False

  # بالنسبة للرصد المخصص لصفحة أو قناة اختارها المستخدم بنفسه، نكتفي بسلامة المحتوى والفلتر المخصص للرابط
  if is_target:
    return True

  arabic_chars = re.findall(r"[\u0600-\u06FF]", f"{t_clean} {s_clean}")
  if len(arabic_chars) < 6:
    return False

  if any(term.lower() in combined for term in STRICT_JUDICIAL_UNAMBIGUOUS):
    return True

  has_general_judicial = any(
      term.lower() in combined for term in JUDICIAL_GENERAL_TERMS
  )
  if has_general_judicial:
    has_morocco_ctx = (
        any(m.lower() in combined_with_url for m in MOROCCAN_CONTEXT_TERMS)
        or ".ma/" in u_clean
        or any(s["domain"] in u_clean for s in MOROCCAN_PRESS_SITES)
    )
    if has_morocco_ctx:
      return True

  return False


# =====================================================================
# 2. تحليل الروابط المخصصة والتحقق الصارم من تبعية المنشور للقناة/الصفحة المضافة
# =====================================================================
GENERIC_SOCIAL_SEGMENTS = {
    "channel",
    "c",
    "user",
    "watch",
    "results",
    "feed",
    "shorts",
    "streams",
    "videos",
    "featured",
    "playlists",
    "community",
    "profile.php",
    "people",
    "pages",
    "groups",
    "posts",
    "photos",
    "reels",
    "share",
    "story.php",
    "permalink.php",
    "home",
    "explore",
    "search",
    "status",
    "i",
    "intent",
    "hashtag",
    "p",
    "reel",
    "stories",
    "in",
    "company",
}


def parse_custom_target_identity(target_url: str) -> dict:
  raw_u = str(target_url or "").strip()
  if not raw_u:
    return {}

  # دعم البحث المباشر باسم القناة أو الصفحة أو اسم صاحبها (بدون رابط)
  is_url_like = bool(
      "://" in raw_u
      or re.search(
          r"(?:^|\b)(?:youtube\.com|youtu\.be|facebook\.com|fb\.com|fb\.watch|x\.com|twitter\.com|tiktok\.com|instagram\.com|linkedin\.com|[a-zA-Z0-9-]+\.(?:com|ma|net|org|info|tv|me|io))\b",
          raw_u,
          re.IGNORECASE,
      )
  )
  if not is_url_like:
    clean_name = raw_u
    plat_hint = "شامل"
    for prefix_map, p_val in [
        (("يوتيوب:", "youtube:", "قناة يوتيوب", "يوتيوب"), "يوتيوب"),
        (("فيسبوك:", "فايسبوك:", "facebook:", "صفحة فيسبوك", "فيسبوك", "فايسبوك"), "فيسبوك"),
        (("إكس:", "اكس:", "تويتر:", "x:", "twitter:"), "إكس"),
    ]:
      for pref in prefix_map:
        if clean_name.lower().startswith(pref):
          plat_hint = p_val
          clean_name = clean_name[len(pref) :].strip(" :-–—")
          break
    clean_name = clean_name.strip() or raw_u.strip()
    tag_k = urllib.parse.quote(f"name_{clean_name.lower()}", safe="")
    return {
        "raw_url": clean_name,
        "domain": "",
        "platform": plat_hint,
        "handle": clean_name.lstrip("@") if clean_name.startswith("@") else "",
        "channel_id": "",
        "official_name_hint": clean_name.lstrip("@"),
        "is_name_target": True,
        "display_label": clean_name,
        "target_tag": f"#v4target={tag_k}",
    }

  full_u = raw_u if "://" in raw_u else f"https://{raw_u}"
  parsed = urllib.parse.urlparse(full_u)
  domain = (
      parsed.netloc.lower()
      .replace("www.", "")
      .replace("m.", "")
      .replace("web.", "")
      .replace("mbasic.", "")
  )
  path_parts = [
      urllib.parse.unquote(p).strip()
      for p in parsed.path.strip("/").split("/")
      if p.strip()
  ]
  qs = urllib.parse.parse_qs(parsed.query)

  if "youtube.com" in domain or "youtu.be" in domain:
    platform = "يوتيوب"
    base_domain = "youtube.com"
  elif "facebook.com" in domain or "fb.com" in domain or "fb.watch" in domain:
    platform = "فيسبوك"
    base_domain = "facebook.com"
  elif "x.com" in domain or "twitter.com" in domain:
    platform = "إكس"
    base_domain = "x.com"
  elif "tiktok.com" in domain:
    platform = "أخرى"
    base_domain = "tiktok.com"
  elif "instagram.com" in domain:
    platform = "أخرى"
    base_domain = "instagram.com"
  elif "linkedin.com" in domain:
    platform = "أخرى"
    base_domain = "linkedin.com"
  else:
    platform = "الصحف"
    base_domain = domain

  handle = ""
  channel_id = ""
  official_name_hint = ""
  display_label = domain

  if platform == "يوتيوب":
    for idx, seg in enumerate(path_parts):
      if seg.startswith("@"):
        handle = seg.lstrip("@")
        display_label = seg
        break
      if seg == "channel" and idx + 1 < len(path_parts):
        channel_id = path_parts[idx + 1]
        display_label = channel_id
        break
      if seg in ("c", "user") and idx + 1 < len(path_parts):
        handle = path_parts[idx + 1]
        display_label = handle
        break
      if seg.startswith("UC") and len(seg) >= 20:
        channel_id = seg
        display_label = seg
        break
      if seg.lower() not in GENERIC_SOCIAL_SEGMENTS and not handle:
        handle = seg
        display_label = seg
  elif platform in ("فيسبوك", "إكس", "أخرى"):
    if "id" in qs and qs["id"]:
      channel_id = qs["id"][0].strip()
      handle = ""
      display_label = f"fb_{channel_id}"
    elif len(path_parts) >= 2 and path_parts[0].lower() == "p":
      # روابط فيسبوك الحديثة بصيغة: facebook.com/p/Page-Name-100064581234567/
      raw_p_seg = path_parts[1].lstrip("@")
      m_pid_tail = re.search(r"^(.*?)-(\d{8,})$", raw_p_seg)
      if m_pid_tail:
        official_name_hint = m_pid_tail.group(1).replace("-", " ").strip()
        channel_id = m_pid_tail.group(2).strip()
        handle = ""
        display_label = official_name_hint or f"fb_{channel_id}"
      else:
        official_name_hint = raw_p_seg.replace("-", " ").strip()
        handle = raw_p_seg
        display_label = official_name_hint
    elif len(path_parts) >= 2 and path_parts[0].lower() in (
        "people",
        "pages",
        "company",
        "in",
        "groups",
    ):
      raw_seg1 = path_parts[1].lstrip("@")
      m_pid_tail = re.search(r"^(.*?)-(\d{8,})$", raw_seg1)
      if m_pid_tail:
        official_name_hint = m_pid_tail.group(1).replace("-", " ").strip()
        channel_id = m_pid_tail.group(2).strip()
      else:
        official_name_hint = raw_seg1.replace("-", " ")
      display_label = official_name_hint or raw_seg1
      if len(path_parts) >= 3 and path_parts[2].isdigit():
        channel_id = path_parts[2]
      elif path_parts[0].lower() == "groups":
        handle = path_parts[1]
    elif len(path_parts) >= 2 and path_parts[0].lower() == "share":
      # رابط مشاركة فيسبوك (share/...) يحتاج إلى فك التوجيه أولاً لمعرفة اسم ومعرف الصفحة الحقيقي
      handle = ""
      display_label = f"fb_share_{path_parts[-1]}"
    else:
      for seg in path_parts:
        if seg.lower() not in GENERIC_SOCIAL_SEGMENTS:
          m_pid_tail = re.search(r"^(.*?)-(\d{8,})$", seg)
          if seg.isdigit() and len(seg) >= 8:
            channel_id = seg
            display_label = f"fb_{seg}"
          elif m_pid_tail and platform == "فيسبوك":
            official_name_hint = m_pid_tail.group(1).replace("-", " ").strip()
            channel_id = m_pid_tail.group(2).strip()
            handle = ""
            display_label = official_name_hint or f"fb_{channel_id}"
          else:
            handle = seg.lstrip("@")
            display_label = handle
          break
  else:
    display_label = domain
    if path_parts:
      handle = path_parts[0]

  target_tag_key = urllib.parse.quote(
      (display_label or handle or channel_id or base_domain).lower(), safe=""
  )

  return {
      "raw_url": full_u,
      "domain": base_domain,
      "platform": platform,
      "handle": handle,
      "channel_id": channel_id,
      "official_name_hint": official_name_hint,
      "is_name_target": False,
      "display_label": display_label or base_domain,
      "target_tag": f"#v4target={target_tag_key}",
  }


def belongs_to_custom_target(item: dict, target_info: dict) -> bool:
  if not target_info or not item:
    return False

  raw_item_url = str(item.get("url") or "").strip()
  raw_item_url_low = raw_item_url.lower()
  u = clean_social_post_url(raw_item_url)
  item_plat = item.get("platform", "")
  t_plat = target_info.get("platform", "")
  handle = (target_info.get("handle") or "").strip()

  # 1) رفض قاطع لأي رابط على يوتيوب أو فيسبوك أو إكس يوجه إلى الصفحة الرئيسية للقناة/الصفحة بدلاً من الفيديو/المنشور بعينه
  u_dom = urllib.parse.urlparse(u).netloc.lower()
  if any(sd in u_dom for sd in ("youtube.com", "youtu.be", "facebook.com", "fb.com", "fb.watch", "x.com", "twitter.com")):
    check_plat = item_plat if item_plat in ("يوتيوب", "فيسبوك", "إكس") else t_plat
    if not is_direct_social_post_url(u, check_plat):
      return False

  # 2) تطهير أي نتائج قديمة من النسخ السابقة
  if any(old_t in raw_item_url_low for old_t in ("#target=", "#v2target=", "#v3target=")) and "#v4target=" not in raw_item_url_low:
    return False

  # 3) التحقق من وسم الهدف المخصص الموثق #v4target=
  t_tag = (target_info.get("target_tag") or "").lower()
  if t_tag and t_tag in raw_item_url_low:
    return True

  return False


def belongs_to_any_custom_target(item: dict, targets_list: list) -> bool:
  if not targets_list:
    return False
  for t in targets_list:
    t_info = parse_custom_target_identity(t.get("url", ""))
    if t_info and belongs_to_custom_target(item, t_info):
      return True
  return False


# =====================================================================
# 3. فك روابط Google News واستخراج متن الخبر الحقيقي والصورة المصغرة الأصلية
# =====================================================================
def resolve_google_news_url(url: str) -> str:
  u = strip_internal_url_fragments(url)
  if "news.google.com" not in u:
    return u

  m_b64 = re.search(r"/(?:articles|read)/([A-Za-z0-9_-]+)", u)
  if m_b64:
    token = m_b64.group(1)
    try:
      padded = token + "=" * ((4 - len(token) % 4) % 4)
      raw_bytes = base64.urlsafe_b64decode(padded)
      decoded_latin = raw_bytes.decode("latin-1", errors="ignore")
      m_http = re.search(
          r"(https?://[^\x00-\x1f\x7f-\xff\"\'<> ]+)", decoded_latin
      )
      if m_http and "google.com" not in m_http.group(1):
        return m_http.group(1)
    except Exception:
      pass

    try:
      art_page = f"https://news.google.com/articles/{token}"
      r = requests.get(art_page, headers=DEFAULT_HEADERS, timeout=3.5)
      if r.status_code == 200:
        sg_m = re.search(r'data-n-a-sg="([^"]+)"', r.text)
        ts_m = re.search(r'data-n-a-ts="([^"]+)"', r.text)
        if sg_m and ts_m:
          sg = sg_m.group(1)
          ts = ts_m.group(1)
          payload_inner = (
              f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"MA:ar",'
              f'null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,'
              f'null,0,0,null,0],"{token}",{ts},"{sg}"]'
          )
          req_data = {
              "f.req": json.dumps(
                  [[["Fbv4je", payload_inner, None, "generic"]]]
              )
          }
          headers_post = dict(DEFAULT_HEADERS)
          headers_post["Content-Type"] = (
              "application/x-www-form-urlencoded;charset=UTF-8"
          )
          rb = requests.post(
              "https://news.google.com/_/DotsSplashUi/data/batchexecute",
              data=req_data,
              headers=headers_post,
              timeout=3.5,
          )
          if rb.status_code == 200:
            m_res = re.search(
                r'\\"garturlres\\",\\"(https?://[^\\"]+)\\"', rb.text
            )
            if m_res:
              return m_res.group(1)
    except Exception:
      pass

  return u


def scrape_article_page_content_and_image(url: str):
  real_url = resolve_google_news_url(url)
  if not real_url or "news.google.com" in real_url:
    return "", "", real_url

  m_yt = re.search(
      r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
      real_url,
  )
  if m_yt:
    vid_id = m_yt.group(1)
    yt_thumb = f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
    yt_desc = ""
    try:
      ryt = requests.get(
          f"https://www.youtube.com/watch?v={vid_id}",
          headers=DEFAULT_HEADERS,
          cookies=YT_BYPASS_COOKIES,
          timeout=4.0,
      )
      if ryt.status_code == 200 and ryt.text:
        m_sd = re.search(
            r'"shortDescription"\s*:\s*"((?:[^"\\]|\\.){15,800})"',
            ryt.text,
        )
        if m_sd:
          yt_desc = decode_js_escaped_text(m_sd.group(1))
        if not yt_desc:
          m_ogd = re.search(
              r'<meta[^>]+(?:property|name)=["\'](?:og:description|description)["\'][^>]+content=["\']([^"\']+)["\']',
              ryt.text[:35000],
              re.IGNORECASE,
          )
          if m_ogd:
            yt_desc = clean_display_text(m_ogd.group(1))
    except Exception:
      pass
    return yt_thumb, yt_desc, real_url

  img_url = ""
  body_text = ""
  req_headers = (
      FB_CRAWLER_HEADERS
      if "facebook.com" in real_url or "fb.com" in real_url
      else DEFAULT_HEADERS
  )
  try:
    r = requests.get(real_url, headers=req_headers, timeout=4.0)
    if r.status_code != 200 or not r.text:
      return "", "", real_url

    html_doc = r.text
    for meta_pattern in [
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|og:image:secure_url|twitter:image|twitter:image:src)["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|og:image:secure_url|twitter:image|twitter:image:src)["\']',
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
    ]:
      m_img = re.search(meta_pattern, html_doc[:25000], re.IGNORECASE)
      if m_img:
        candidate_img = html.unescape(m_img.group(1).strip())
        if candidate_img.startswith("//"):
          candidate_img = "https:" + candidate_img
        elif candidate_img.startswith("/"):
          candidate_img = urllib.parse.urljoin(real_url, candidate_img)
        if candidate_img.startswith("http"):
          img_url = candidate_img
          break

    meta_desc = ""
    bad_login_phrases = [
        "قم بتسجيل الدخول",
        "تسجيل الدخول إلى فيسبوك",
        "لبدء المشاركة والتواصل",
        "log in to facebook",
        "log in or sign up",
        "connect with friends",
        "page not found",
        "الصفحة غير موجودة",
    ]
    for desc_pattern in [
        r'<meta[^>]+(?:property|name)=["\'](?:og:description|description|twitter:description)["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:description|description|twitter:description)["\']',
    ]:
      m_d = re.search(desc_pattern, html_doc[:25000], re.IGNORECASE)
      if m_d:
        cand_d = _strip_fb_sidebar_noise(m_d.group(1))
        if any(bp in cand_d.lower() for bp in bad_login_phrases):
          continue
        if len(cand_d) > 25:
          meta_desc = cand_d
          break

    paragraphs = []
    if BeautifulSoup is not None:
      soup = BeautifulSoup(html_doc, "html.parser")
      if not img_url:
        for img_tag in soup.select(
            "article img, .post-content img, .entry-content img, .single-post img, main img"
        ):
          src_cand = (
              img_tag.get("data-src")
              or img_tag.get("data-lazy-src")
              or img_tag.get("src")
              or ""
          ).strip()
          if src_cand and not src_cand.startswith("data:"):
            if src_cand.startswith("//"):
              src_cand = "https:" + src_cand
            elif src_cand.startswith("/"):
              src_cand = urllib.parse.urljoin(real_url, src_cand)
            if src_cand.startswith("http") and not any(
                x in src_cand.lower() for x in ["avatar", "logo", "icon", "1x1"]
            ):
              img_url = src_cand
              break

      for tag in soup.select("script, style, nav, footer, header, aside"):
        tag.decompose()

      p_elements = soup.select(
          "article p, .entry-content p, .post-content p, .article-content p, .td-post-content p, main p, p"
      )
      for p_el in p_elements:
        p_txt = clean_display_text(p_el.get_text(" ", strip=True))
        if (
            len(p_txt) >= 50
            and len(re.findall(r"[\u0600-\u06FF]", p_txt)) >= 15
        ):
          if p_txt not in paragraphs:
            paragraphs.append(p_txt)
          if len(" ".join(paragraphs)) > 1600:
            break
    else:
      for raw_p in re.findall(
          r"<p[^>]*>(.*?)</p>", html_doc, re.DOTALL | re.IGNORECASE
      ):
        p_txt = clean_display_text(raw_p)
        if (
            len(p_txt) >= 50
            and len(re.findall(r"[\u0600-\u06FF]", p_txt)) >= 15
        ):
          if p_txt not in paragraphs:
            paragraphs.append(p_txt)
          if len(" ".join(paragraphs)) > 1600:
            break

    combined_parts = []
    if meta_desc and len(meta_desc) > 35:
      combined_parts.append(meta_desc)
    for p in paragraphs[:6]:
      if p not in combined_parts:
        combined_parts.append(p)
    body_text = " ".join(combined_parts)[:2200]
  except Exception:
    pass

  return img_url, body_text, real_url


def fetch_bing_news_enrichment(title: str, source_name: str = ""):
  q_clean = clean_display_text(title)
  if not q_clean:
    return "", "", ""
  src_clean = re.sub(r"🎯", "", clean_display_text(source_name)).strip()
  search_q = f"{q_clean[:75]} {src_clean}".strip()
  bing_url = (
      f"https://www.bing.com/news/search?q={urllib.parse.quote(search_q)}"
      "&format=rss&adlt=strict&cc=MA&setlang=ar"
  )
  try:
    r = requests.get(bing_url, headers=DEFAULT_HEADERS, timeout=3.5)
    if r.status_code == 200 and b"<item>" in r.content:
      raw_xml = r.text
      items_xml = re.findall(r"<item>(.*?)</item>", raw_xml, re.DOTALL)
      for it_x in items_xml[:3]:
        img_m = re.search(
            r"<News:Image>(https?://[^<]+)</News:Image>", it_x, re.IGNORECASE
        )
        if not img_m:
          img_m = re.search(r'url=["\'](https?://[^"\']+)["\']', it_x)
        desc_m = re.search(
            r"<description>(.*?)</description>", it_x, re.DOTALL | re.IGNORECASE
        )
        link_m = re.search(
            r"<link>(.*?)</link>", it_x, re.DOTALL | re.IGNORECASE
        )

        b_img = html.unescape(img_m.group(1).strip()) if img_m else ""
        b_desc = clean_display_text(desc_m.group(1)) if desc_m else ""
        b_link = html.unescape(link_m.group(1).strip()) if link_m else ""
        if "url=" in b_link:
          qs = urllib.parse.parse_qs(urllib.parse.urlparse(b_link).query)
          if "url" in qs:
            b_link = qs["url"][0]

        if b_img or len(b_desc) > 45:
          return b_img, b_desc, b_link
  except Exception:
    pass
  return "", "", ""


def enrich_item_content_and_image(item: dict) -> dict:
  url = (item.get("url") or "").strip()
  title = clean_display_text(item.get("title") or "")
  plat = item.get("platform", "الصحف")
  src = item.get("source_name", plat)
  raw_snip = clean_display_text(item.get("raw_snippet") or "")
  img_url = (item.get("image_url") or "").strip()

  if not img_url:
    img_url = extract_thumbnail_for_item(url, "", plat)

  need_body = (
      not raw_snip
      or len(raw_snip) < 85
      or raw_snip.lower() == title.lower()
      or raw_snip.startswith(title[:30])
  )
  need_img = not img_url

  if need_img or need_body:
    page_img, page_body, resolved_u = scrape_article_page_content_and_image(url)
    if page_img and not img_url:
      img_url = page_img
    if page_body and len(page_body) > len(raw_snip):
      raw_snip = page_body
    if (
        resolved_u
        and "news.google.com" not in resolved_u
        and "news.google.com" in url
    ):
      m_tag = re.search(r"(#(?:plat|v4target|v3target|v2target|target)=[^\s#]*)$", url)
      item["url"] = f"{resolved_u}{m_tag.group(1) if m_tag else ''}"

  # عدم استدعاء Bing News للأهداف المخصصة أو منصات الفيديو/التواصل حتى لا يُستبدل ملخص الفيديو أو المنشور بمقال صحفي آخر
  if (
      plat == "الصحف"
      and not int(item.get("is_custom_target", 0))
      and (not img_url or len(raw_snip) < 70 or raw_snip.lower() == title.lower())
  ):
    b_img, b_desc, b_link = fetch_bing_news_enrichment(title, src)
    if b_img and not img_url:
      img_url = b_img
    if (
        b_desc
        and len(b_desc) > len(raw_snip)
        and b_desc.lower() != title.lower()
    ):
      raw_snip = b_desc
    if b_link and (not img_url or len(raw_snip) < 80):
      p_img2, p_body2, _ = scrape_article_page_content_and_image(b_link)
      if p_img2 and not img_url:
        img_url = p_img2
      if p_body2 and len(p_body2) > len(raw_snip):
        raw_snip = p_body2

  item["image_url"] = img_url
  item["raw_snippet"] = raw_snip[:2000]
  return item


def build_extractive_arabic_summary(
    title: str, snippet: str, platform: str, source_name: str
) -> str:
  t_clean = clean_display_text(title)
  s_clean = clean_display_text(snippet)

  if s_clean and t_clean:
    if s_clean.startswith(t_clean):
      s_clean = s_clean[len(t_clean) :].lstrip(" -–—:•|.")
    elif len(t_clean) > 25 and t_clean[:25] in s_clean[:40]:
      idx = s_clean.find(t_clean[:25])
      s_clean = s_clean[idx + len(t_clean) :].lstrip(" -–—:•|.")

  s_clean = re.sub(
      r"^(\d{1,2}\s+[^\s]+\s+20\d{2}|[A-Za-z]{3,9}\s+\d{1,2},?\s+20\d{2}|\d+\s*(?:hours?|days?|minutes?|ساعات|ساعة|يوم|أيام|دقيقة)\s*(?:ago)?)\s*[-–—·•:]\s*",
      "",
      s_clean,
      flags=re.IGNORECASE,
  ).strip()

  if s_clean and len(s_clean) >= 45 and s_clean.lower() != t_clean.lower():
    sentences = [
        seg.strip()
        for seg in re.split(r"(?<=[.!؟\n])\s+", s_clean)
        if len(seg.strip()) > 25 and seg.strip() != t_clean
    ]
    if sentences:
      summary_txt = " ".join(sentences[:3])
      return summary_txt[:420] + ("..." if len(summary_txt) > 420 else "")
    return s_clean[:420] + ("..." if len(s_clean) > 420 else "")

  src_label = clean_display_text(source_name or platform)
  return (
      f"تفيد المعطيات الواردة عبر ({src_label}) بمتابعة مستجدات تتعلق بـ {t_clean}، "
      "ضمن التغطية الإعلامية المتواصلة لأنشطة ومستجدات المصدر."
  )


def get_fallback_thumbnail_data_uri(platform: str, source_name: str = "") -> str:
  themes = {
      "الصحف": ("#064e3b", "#10b981", "PRESS", "⚖️ صحافة قضائية"),
      "فيسبوك": ("#1e3a8a", "#3b82f6", "FACEBOOK", "🟦 منشور فيسبوك"),
      "إكس": ("#0f172a", "#94a3b8", "X / TWITTER", "⬛ تغريدة إكس"),
      "يوتيوب": ("#7f1d1d", "#ef4444", "YOUTUBE", "🟥 فيديو يوتيوب"),
      "أخرى": ("#4c1d95", "#a855f7", "SOCIAL", "🟪 تواصل اجتماعي"),
  }
  bg1, accent, en_lbl, ar_lbl = themes.get(
      platform, ("#0f172a", "#38bdf8", "JUSTICE", "⚖️ رصد قضائي")
  )
  src_short = html.escape(clean_display_text(source_name or platform)[:18])
  svg = (
      f'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200" viewBox="0 0 320 200">'
      f"<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
      f"<stop offset='0%' stop-color='{bg1}'/><stop offset='100%' stop-color='#090d16'/>"
      f"</linearGradient></defs>"
      f"<rect width='320' height='200' rx='14' fill='url(#g)'/>"
      f"<circle cx='270' cy='40' r='55' fill='{accent}' fill-opacity='0.12'/>"
      f"<circle cx='45' cy='165' r='45' fill='{accent}' fill-opacity='0.1'/>"
      f"<rect x='16' y='16' width='288' height='168' rx='10' fill='none' stroke='{accent}' stroke-opacity='0.35' stroke-width='1.5'/>"
      f"<text x='160' y='78' text-anchor='middle' fill='{accent}' font-family='Cairo, sans-serif' font-size='15' font-weight='800'>{en_lbl}</text>"
      f"<text x='160' y='115' text-anchor='middle' fill='#f8fafc' font-family='Cairo, sans-serif' font-size='20' font-weight='900'>{ar_lbl}</text>"
      f"<text x='160' y='148' text-anchor='middle' fill='#cbd5e1' font-family='Cairo, sans-serif' font-size='14' font-weight='700'>{src_short}</text>"
      f"</svg>"
  )
  b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
  return f"data:image/svg+xml;base64,{b64}"


def extract_thumbnail_for_item(
    url: str, raw_html_desc: str = "", platform: str = "الصحف"
) -> str:
  u = strip_internal_url_fragments(url)
  m_yt = re.search(
      r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
      u,
  )
  if m_yt:
    return f"https://i.ytimg.com/vi/{m_yt.group(1)}/hqdefault.jpg"

  if raw_html_desc:
    m_img = re.search(
        r'<img[^>]+src=["\'](https?://[^"\'>\s]+)["\']',
        str(raw_html_desc),
        re.IGNORECASE,
    )
    if m_img:
      img_u = html.unescape(m_img.group(1).strip())
      if not any(
          skip in img_u.lower()
          for skip in [
              "1x1",
              "pixel",
              "tracker",
              "blank.gif",
              "googleusercontent.com/J6_coFbogxhRI9iM864NL_liGXvsQp2AupsKei7z0cNNfDvGUmWUy20nuUhkREQyrpY4bEeIBuc",
          ]
      ):
        return img_u

  return ""


# =====================================================================
# 4. قفل التزامن المركزي لمنع تضارب SQLite والخيوط (Thread-Safety)
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
# 5. إدارة قاعدة البيانات والأرشيف الدائم وتطهير البيانات غير المطابقة
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
    "image_url": "TEXT DEFAULT ''",
    "created_at": "REAL DEFAULT 0",
    "telegram_sent": "INTEGER DEFAULT 0",
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
    "image_url",
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
            image_url TEXT DEFAULT '',
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


def _has_inappropriate_terms(title: str, snippet: str, url: str) -> bool:
  combined = f"{clean_display_text(title)} {clean_display_text(snippet)} {str(url or '')}".lower()
  return any(bad_w in combined for bad_w in BLOCKED_INAPPROPRIATE_TERMS)


def purge_invalid_articles_from_db():
  """تطهير الأخبار المخالفة فقط مع حماية الأرشيف التاريخي بالكامل من الحذف عند تحديث الكود أو تعديل الروابط المخصصة."""
  lock = get_db_lock()
  current_targets = load_custom_targets()
  now_ts = time.time()
  with lock:
    removed_any = False
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute(
          "SELECT id, title, summary, source_name, platform, raw_snippet, url, is_custom_target, pub_timestamp, created_at FROM articles"
      )
      rows = c.fetchall()
      bad_ids = []
      for r in rows:
        d = dict(r)
        snip = f"{d.get('summary') or ''} {d.get('raw_snippet') or ''}"
        u_str = d.get("url") or ""
        t_str = d.get("title") or ""
        if _has_inappropriate_terms(t_str, snip, u_str):
          bad_ids.append((d["id"],))
          continue
        pub_t = float(d.get("pub_timestamp") or 0)
        mon_t = float(d.get("created_at") or pub_t)
        is_archived_item = ((now_ts - mon_t) >= 86400) or ((now_ts - pub_t) >= 86400 and abs(mon_t - pub_t) < 120)
        # لا نحذف العناصر المحفوظة في الأرشيف إطلاقاً طالما أنها نظيفة
        if is_archived_item:
          continue
        is_tgt = bool(d.get("is_custom_target"))
        if not is_strictly_judicial_and_clean(
            t_str, snip, u_str, "", is_target=is_tgt
        ):
          bad_ids.append((d["id"],))
        elif is_tgt and not belongs_to_any_custom_target(d, current_targets):
          bad_ids.append((d["id"],))
      if bad_ids:
        c.executemany("DELETE FROM articles WHERE id = ?", bad_ids)
        conn.commit()
        removed_any = True
      conn.close()
    except Exception:
      pass

    for arch_path in (ARCHIVE_JSON_FILE, PERSISTENT_HOME_ARCHIVE_JSON):
      if os.path.exists(arch_path):
        try:
          with open(arch_path, "r", encoding="utf-8") as f:
            arch_data = json.load(f)
          if isinstance(arch_data, list):
            cleaned_arch = [
                item for item in arch_data
                if isinstance(item, dict)
                and not _has_inappropriate_terms(
                    item.get("title", ""),
                    f"{item.get('summary', '')} {item.get('raw_snippet', '')}",
                    item.get("url", ""),
                )
            ]
            if len(cleaned_arch) != len(arch_data):
              with open(arch_path, "w", encoding="utf-8") as f:
                json.dump(cleaned_arch, f, ensure_ascii=False, indent=2)
              removed_any = True
        except Exception:
          pass

    if removed_any and os.path.exists(DB_FILE):
      for dst_db in (REPO_DB_FILE, PERSISTENT_HOME_DB):
        try:
          shutil.copyfile(DB_FILE, dst_db)
        except Exception:
          pass


def load_telegram_sent_ledger() -> set:
  """تحميل سجل البصمات المرسلة سابقاً إلى تلغرام لمنع تكرار الإرسال نهائياً."""
  ledger = set()
  if os.path.exists(TELEGRAM_LEDGER_FILE):
    try:
      with open(TELEGRAM_LEDGER_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
      if isinstance(data, list):
        ledger.update(str(x) for x in data if x)
    except Exception:
      pass
  return ledger


def save_telegram_sent_ledger(ledger: set):
  try:
    trimmed = sorted(list(ledger))[-8000:]
    tmp_p = f"{TELEGRAM_LEDGER_FILE}.tmp"
    with open(tmp_p, "w", encoding="utf-8") as f:
      json.dump(trimmed, f, ensure_ascii=False)
    os.replace(tmp_p, TELEGRAM_LEDGER_FILE)
  except Exception:
    pass


def deduplicate_and_seed_telegram_ledger():
  """إزالة أي أخبار مكررة من قاعدة البيانات والأرشيف مع الحفاظ على أقدم وقت رصد (created_at) وتغذية سجل تلغرام."""
  lock = get_db_lock()
  with lock:
    ledger = load_telegram_sent_ledger()
    ledger_changed = False
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute("SELECT * FROM articles ORDER BY created_at ASC, pub_timestamp ASC, id ASC")
      rows = [dict(r) for r in c.fetchall()]
      seen_keys = set()
      dup_ids = []
      for r in rows:
        item_keys = compute_article_dedup_keys(r.get("title", ""), r.get("url", ""))
        if not item_keys.issubset(ledger):
          ledger.update(item_keys)
          ledger_changed = True
        if item_keys & seen_keys:
          dup_ids.append((r["id"],))
        else:
          seen_keys.update(item_keys)
      if dup_ids:
        c.executemany("DELETE FROM articles WHERE id = ?", dup_ids)
        conn.commit()
      c.execute("UPDATE articles SET telegram_sent = 1 WHERE telegram_sent IS NULL OR telegram_sent = 0")
      conn.commit()
      conn.close()
    except Exception:
      pass

    if ledger_changed or not os.path.exists(TELEGRAM_LEDGER_FILE):
      save_telegram_sent_ledger(ledger)


def _merge_external_sqlite_into_runtime(src_db_path: str):
  """دمج كافة السجلات المحفوظة في قاعدة بيانات خارجية (REPO_DB_FILE أو PERSISTENT_HOME_DB) داخل قاعدة التشغيل دون فقدان أي عنصر من الأرشيف."""
  if not src_db_path or not os.path.exists(src_db_path) or os.path.getsize(src_db_path) == 0:
    return
  if os.path.abspath(src_db_path) == os.path.abspath(DB_FILE):
    return
  try:
    src_conn = sqlite3.connect(src_db_path, timeout=15.0)
    src_conn.row_factory = sqlite3.Row
    sc = src_conn.cursor()
    sc.execute("SELECT * FROM articles")
    src_rows = [dict(r) for r in sc.fetchall()]
    src_conn.close()
  except Exception:
    return

  if not src_rows:
    return

  try:
    dst_conn = _open_sqlite_conn()
    _ensure_schema_on_conn(dst_conn)
    dc = dst_conn.cursor()
    for r in src_rows:
      pub_ts = float(r.get("pub_timestamp") or (time.time() - 90000))
      # إذا كان العنصر قديماً ولم يسجل له created_at، نستخدم pub_timestamp حتى يبقى في الأرشيف ولا يعود للنشط
      c_at = float(r.get("created_at") or pub_ts)
      if c_at <= 0:
        c_at = pub_ts
      dc.execute(
          """
          INSERT OR IGNORE INTO articles (
              title, summary, source_name, platform, url,
              pub_date, pub_timestamp, sentiment, category,
              relevance_score, is_custom_target, raw_snippet,
              image_url, created_at, telegram_sent
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          """,
          (
              clean_display_text(r.get("title", "")),
              clean_display_text(r.get("summary", "")),
              clean_display_text(r.get("source_name", "")),
              r.get("platform", "الصحف"),
              r.get("url", ""),
              r.get("pub_date", ""),
              pub_ts,
              r.get("sentiment", "محايد"),
              r.get("category", "شؤون قضائية"),
              int(r.get("relevance_score") or 85),
              int(r.get("is_custom_target") or 0),
              clean_display_text(r.get("raw_snippet", "")),
              r.get("image_url", ""),
              c_at,
              1,
          ),
      )
    dst_conn.commit()
    dst_conn.close()
  except Exception:
    pass


def init_db():
  lock = get_db_lock()
  with lock:
    if not os.path.exists(DB_FILE):
      for candidate_src in (PERSISTENT_HOME_DB, REPO_DB_FILE):
        if os.path.exists(candidate_src) and os.path.getsize(candidate_src) > 0:
          try:
            shutil.copyfile(candidate_src, DB_FILE)
            break
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

    # دمج جميع قواعد البيانات وملفات الأرشيف الدائمة في كل مرة يتم فيها تشغيل أو تحديث الكود لضمان عدم ضياع الأرشيف أبداً
    _merge_external_sqlite_into_runtime(REPO_DB_FILE)
    _merge_external_sqlite_into_runtime(PERSISTENT_HOME_DB)
    restore_db_from_json_if_needed()
    purge_invalid_articles_from_db()
    deduplicate_and_seed_telegram_ledger()
    sync_db_to_json()


def sync_db_to_json(extra_items: list = None):
  lock = get_db_lock()
  with lock:
    merged_by_url = {}
    for json_src in (PERSISTENT_HOME_ARCHIVE_JSON, ARCHIVE_JSON_FILE):
      if os.path.exists(json_src):
        try:
          with open(json_src, "r", encoding="utf-8") as f:
            existing_json = json.load(f)
          if isinstance(existing_json, list):
            for item in existing_json:
              if not isinstance(item, dict) or not item.get("url"):
                continue
              if _has_inappropriate_terms(
                  item.get("title", ""),
                  f"{item.get('summary', '')} {item.get('raw_snippet', '')}",
                  item.get("url", ""),
              ):
                continue
              merged_by_url[item["url"]] = item
        except Exception:
          pass

    if extra_items:
      for item in extra_items:
        if isinstance(item, dict) and item.get("url"):
          clean_copy = {
              k: v for k, v in item.items() if not str(k).startswith("_")
          }
          merged_by_url[clean_copy["url"]] = clean_copy

    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute(
          "SELECT title, summary, source_name, platform, url, pub_date, "
          "pub_timestamp, sentiment, category, relevance_score, "
          "is_custom_target, raw_snippet, image_url, created_at "
          "FROM articles ORDER BY pub_timestamp DESC LIMIT 2500"
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
      )[:2500]
      for target_json in (ARCHIVE_JSON_FILE, PERSISTENT_HOME_ARCHIVE_JSON):
        try:
          tmp_file = f"{target_json}.tmp"
          with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(sorted_rows, f, ensure_ascii=False, indent=2)
          os.replace(tmp_file, target_json)
        except Exception:
          pass

    if os.path.exists(DB_FILE):
      for target_db in (REPO_DB_FILE, PERSISTENT_HOME_DB):
        try:
          shutil.copyfile(DB_FILE, target_db)
        except Exception:
          pass


def restore_db_from_json_if_needed():
  """استعادة ودمج جميع عناصر الأرشيف من ملفات JSON الدائمة داخل SQLite في كل تشغيل (حتى لو لم تكن القاعدة فارغة) مع الحفاظ على تواريخ الرصد الأصلية."""
  lock = get_db_lock()
  with lock:
    all_json_items = []
    for arch_file in (PERSISTENT_HOME_ARCHIVE_JSON, ARCHIVE_JSON_FILE):
      if os.path.exists(arch_file):
        try:
          with open(arch_file, "r", encoding="utf-8") as f:
            items = json.load(f)
          if isinstance(items, list):
            all_json_items.extend(items)
        except Exception:
          pass

    if not all_json_items:
      return

    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      c = conn.cursor()
      for item in all_json_items:
        if not isinstance(item, dict):
          continue
        try:
          t_clean = clean_display_text(item.get("title", ""))
          s_clean = clean_display_text(item.get("summary", ""))
          plat = item.get("platform", "الصحف")
          src = clean_display_text(item.get("source_name", "") or plat)
          raw_s = clean_display_text(item.get("raw_snippet", ""))
          u_str = item.get("url", "")
          is_tgt = int(item.get("is_custom_target", 0))
          if not t_clean or not u_str:
            continue
          if _has_inappropriate_terms(t_clean, f"{s_clean} {raw_s}", u_str):
            continue

          if is_summary_just_title(t_clean, s_clean):
            s_clean = build_extractive_arabic_summary(
                t_clean, raw_s, plat, src
            )
          pub_ts = float(item.get("pub_timestamp") or (time.time() - 90000))
          # الحفاظ الصارم على وقت الرصد الأصلي، وإذا لم يكن مسجلاً نعتمد وقت النشر (pub_ts) وليس time.time() حتى لا يختفي الأرشيف!
          orig_created = float(item.get("created_at") or 0)
          if orig_created <= 0:
            orig_created = pub_ts
          pub_dt = item.get("pub_date", "")
          if not pub_dt:
            pub_dt = datetime.fromtimestamp(
                pub_ts, tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M")
          img_u = item.get("image_url") or extract_thumbnail_for_item(
              u_str, "", plat
          )

          c.execute(
              """
              INSERT OR IGNORE INTO articles (
                  title, summary, source_name, platform, url,
                  pub_date, pub_timestamp, sentiment, category,
                  relevance_score, is_custom_target, raw_snippet,
                  image_url, created_at, telegram_sent
              ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
              """,
              (
                  t_clean,
                  s_clean,
                  src,
                  plat,
                  u_str,
                  pub_dt,
                  pub_ts,
                  item.get("sentiment", "محايد"),
                  item.get("category", "شؤون قضائية"),
                  int(item.get("relevance_score", 85)),
                  is_tgt,
                  raw_s,
                  img_u,
                  orig_created,
                  1,
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
  current_targets = load_custom_targets()
  now_ts = time.time()
  with lock:
    db_rows = []
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute(
          "SELECT * FROM articles ORDER BY pub_timestamp DESC, id DESC LIMIT 2500"
      )
      for r in c.fetchall():
        d = dict(r)
        t_str = d.get("title", "")
        snip_str = f"{d.get('summary', '')} {d.get('raw_snippet', '')}"
        u_str = d.get("url", "")
        if _has_inappropriate_terms(t_str, snip_str, u_str):
          continue
        pub_t = float(d.get("pub_timestamp") or 0)
        mon_t = float(d.get("created_at") or pub_t)
        is_archived = ((now_ts - mon_t) >= 86400) or ((now_ts - pub_t) >= 86400 and abs(mon_t - pub_t) < 120)
        if not is_archived:
          is_tgt = bool(d.get("is_custom_target", 0))
          if not is_strictly_judicial_and_clean(
              t_str, snip_str, u_str, "", is_target=is_tgt
          ):
            continue
          if is_tgt and not belongs_to_any_custom_target(d, current_targets):
            continue
        db_rows.append(d)
      conn.close()
    except Exception:
      pass

    if db_rows:
      unique_rows = []
      seen_display_keys = set()
      for r in db_rows:
        dk = compute_article_dedup_keys(r.get("title", ""), r.get("url", ""))
        if dk & seen_display_keys:
          continue
        seen_display_keys.update(dk)
        unique_rows.append(r)
      return unique_rows

    for arch_file in (ARCHIVE_JSON_FILE, PERSISTENT_HOME_ARCHIVE_JSON):
      if os.path.exists(arch_file):
        try:
          with open(arch_file, "r", encoding="utf-8") as f:
            data = json.load(f)
          if isinstance(data, list) and data:
            valid_data = [
                d for d in data
                if isinstance(d, dict)
                and not _has_inappropriate_terms(
                    d.get("title", ""),
                    f"{d.get('summary', '')} {d.get('raw_snippet', '')}",
                    d.get("url", ""),
                )
            ]
            return sorted(
                valid_data,
                key=lambda x: float(x.get("pub_timestamp", 0)),
                reverse=True,
            )
        except Exception:
          pass
    return []


# =====================================================================
# 6. إدارة الإعدادات والروابط المخصصة وحالة الرصد الدوري وفترة البحث
# =====================================================================
def load_credentials():
  cfg = {
      "gemini_api_key": "",
      "telegram_bot_token": DEFAULT_TG_TOKEN,
      "telegram_chat_id": DEFAULT_TG_CHAT_ID,
      "keywords_input": "",
      "search_period": "آخر 7 أيام",
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
  if cfg.get("search_period") not in SEARCH_PERIOD_MAP:
    cfg["search_period"] = "آخر 7 أيام"
  return cfg


def save_credentials(cfg):
  try:
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
      json.dump(cfg, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


def save_custom_targets(targets):
  try:
    cleaned = [
        {"url": t.get("url", "").strip(), "keyword": t.get("keyword", "").strip()}
        for t in targets
        if t.get("url", "").strip()
    ]
    with open(CUSTOM_TARGETS_FILE, "w", encoding="utf-8") as f:
      json.dump(cleaned, f, ensure_ascii=False, indent=2)
    purge_invalid_articles_from_db()
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
# 7. استخراج ومعالجة تواريخ النشر الحقيقية وتاريخ الرصد
# =====================================================================
def extract_date_from_url_or_text(
    url: str,
    text_snippet: str = "",
    raw_date: str = "",
    fallback_offset_sec: int = 3600,
):
  now_ts = time.time()

  if raw_date and str(raw_date).strip():
    d_str, d_ts = parse_any_date(str(raw_date).strip(), fallback_offset_sec=0)
    if d_ts > 0 and abs(now_ts - d_ts) > 5:
      return d_str, d_ts

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

  if text_snippet:
    return parse_any_date(
        text_snippet[:240], fallback_offset_sec=fallback_offset_sec
    )

  return parse_any_date("", fallback_offset_sec=fallback_offset_sec)


def parse_any_date(date_str: str, fallback_offset_sec: int = 3600):
  now_ts = time.time()
  if not date_str or not str(date_str).strip():
    ts = now_ts - fallback_offset_sec
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M"), ts

  raw = str(date_str).strip()

  # 1) طابع زمني رقمي مباشر (مثل data-utime في فيسبوك)
  if raw.isdigit() and len(raw) >= 9:
    try:
      ts = min(float(raw), now_ts)
      return (
          datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
              "%Y-%m-%d %H:%M"
          ),
          ts,
      )
    except Exception:
      pass

  # 2) صيغ RFC 2822 القياسية لـ RSS
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

  # 3) صيغ ISO 8601 (مثل YouTube Atom XML: 2026-10-13T18:30:00+00:00)
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

  # 4) التواريخ الصريحة بالشهور العربية (مثل: 17 يوليوز 2026)
  for ar_m, m_idx in ARABIC_MONTHS.items():
    m_ar = re.search(rf"(\d{{1,2}})\s+{ar_m}\s*,?\s*(20\d{{2}})", raw)
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

  # 5) التواريخ الصريحة بالشهور الإنجليزية/الفرنسية (مثل: Oct 2, 2026 أو July 03 2026)
  for en_m, m_idx in ENGLISH_MONTHS.items():
    m_en1 = re.search(
        rf"\b{en_m}[a-z]*\s+(\d{{1,2}}),?\s+(20\d{{2}})", rel_lower
    )
    m_en2 = re.search(
        rf"\b(\d{{1,2}})\s+{en_m}[a-z]*,?\s+(20\d{{2}})", rel_lower
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

  # 6) التواريخ الرقمية الصريحة YYYY-MM-DD أو DD-MM-YYYY
  m_ymd = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", raw)
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

  m_dmy = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b", raw)
  if m_dmy:
    try:
      dt = datetime(
          int(m_dmy.group(3)),
          int(m_dmy.group(2)),
          int(m_dmy.group(1)),
          12,
          0,
          tzinfo=timezone.utc,
      )
      ts = min(dt.timestamp(), now_ts)
      return dt.strftime("%Y-%m-%d %H:%M"), ts
    except Exception:
      pass

  # 7) صيغ الوقت النسبي الإنجليزية الصريحة (مثل: 5d · أو 3 days ago أو 18h ago)
  m_short_rel = re.search(
      r"(?:^|\b)(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|wk|wks|week|weeks|mo|month|months|y|yr|yrs|year|years)\b(?:\s*ago|\s*·)?",
      rel_lower,
  )
  if m_short_rel and (
      "ago" in rel_lower
      or "·" in rel_lower[:25]
      or len(raw) <= 28
  ):
    n = int(m_short_rel.group(1))
    u = m_short_rel.group(2)
    if u.startswith("s"):
      ts = now_ts - n
    elif u.startswith("mo"):
      ts = now_ts - n * 30 * 86400
    elif u.startswith("m"):
      ts = now_ts - n * 60
    elif u.startswith("h"):
      ts = now_ts - n * 3600
    elif u.startswith("d"):
      ts = now_ts - n * 86400
    elif u.startswith("w"):
      ts = now_ts - n * 7 * 86400
    else:
      ts = now_ts - n * 365 * 86400
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        ts,
    )

  # 8) صيغ الوقت النسبي العربية الصريحة فقط (مسبوقة بـ "منذ" أو "قبل" أو نص قصير مثل "قبل 3 ساعات" حتى لا تلتبس مع كلمات مثل "النيابة العامة" أو "اليوم")
  m_ar_rel = re.search(
      r"(?:منذ|قبل)\s*(?:حوالي\s*|أكثر من\s*|أقل من\s*)?(?:(\d+)\s*)?(ثانية|ثواني|دقيقة|دقائق|دقيقتين|ساعة|ساعات|ساعتين|يوم|أيام|يومين|أسبوع|أسابيع|اسبوع|أسبوعين|شهر|أشهر|شهور|شهرين|سنة|سنوات|عام|أعوام|سنتين|عامين|لحظات)\b",
      rel_lower,
  )
  if not m_ar_rel and len(raw) <= 26:
    m_ar_rel = re.search(
        r"^(?:(\d+)\s*)?(ثانية|ثواني|دقيقة|دقائق|دقيقتين|ساعة|ساعات|ساعتين|يوم|أيام|يومين|أسبوع|أسابيع|اسبوع|أسبوعين|شهر|أشهر|شهور|شهرين|سنة|سنوات|عام|أعوام|سنتين|عامين|أمس|الآن)\b",
        rel_lower,
    )
  if m_ar_rel:
    num = int(m_ar_rel.group(1)) if m_ar_rel.group(1) else 1
    unit_ar = m_ar_rel.group(2)
    if unit_ar in ("ثانية", "ثواني", "لحظات", "الآن"):
      ts = now_ts - 60
    elif unit_ar in ("دقيقة", "دقائق", "دقيقتين"):
      if unit_ar == "دقيقتين":
        num = 2
      ts = now_ts - (num * 60)
    elif unit_ar in ("ساعة", "ساعات", "ساعتين"):
      if unit_ar == "ساعتين":
        num = 2
      ts = now_ts - (num * 3600)
    elif unit_ar in ("يوم", "أيام", "يومين", "أمس"):
      if unit_ar == "يومين":
        num = 2
      elif unit_ar == "أمس":
        num = 1
      ts = now_ts - (num * 86400)
    elif unit_ar in ("أسبوع", "أسابيع", "اسبوع", "أسبوعين"):
      if unit_ar == "أسبوعين":
        num = 2
      ts = now_ts - (num * 7 * 86400)
    elif unit_ar in ("شهر", "أشهر", "شهور", "شهرين"):
      if unit_ar == "شهرين":
        num = 2
      ts = now_ts - (num * 30 * 86400)
    else:
      if unit_ar in ("سنتين", "عامين"):
        num = 2
      ts = now_ts - (num * 365 * 86400)
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        ts,
    )

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
# 8. محركات الرصد الذكي المفلترة بدقة (الصحف، فيسبوك، إكس، يوتيوب، أخرى)
# =====================================================================
def get_period_config(period_label: str = ""):
  return SEARCH_PERIOD_MAP.get(
      period_label, SEARCH_PERIOD_MAP["آخر 7 أيام"]
  )


def build_search_queries(keywords_input: str):
  custom_kws = [
      k.strip()
      for k in re.split(r"[,،\n]+", str(keywords_input or ""))
      if k.strip()
  ]
  if custom_kws:
    queries = []
    for kw in custom_kws:
      if "المغرب" not in kw:
        queries.append(f"{kw} القضاء المغرب")
      else:
        queries.append(kw)
    return queries
  return list(DEFAULT_JUDICIAL_QUERIES)


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
    max_age_sec: int = 0,
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
      "content": "http://purl.org/rss/1.0/modules/content/",
  }
  now_ts = time.time()

  for item in root.findall(".//item"):
    title = clean_html_text(item.findtext("title") or "")
    link = clean_social_post_url((item.findtext("link") or "").strip())
    raw_desc_html = item.findtext("description") or ""
    raw_content_encoded = (
        item.findtext("content:encoded", default="", namespaces=ns) or ""
    )
    full_raw_html = f"{raw_content_encoded} {raw_desc_html}"
    desc = clean_html_text(full_raw_html)

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

    img_url = ""
    for m_tag in ["media:content", "media:thumbnail", "enclosure"]:
      el = item.find(m_tag, ns) if ":" in m_tag else item.find(m_tag)
      if el is not None and el.attrib.get("url"):
        img_url = el.attrib["url"].strip()
        break
    if not img_url:
      for child in item:
        if (
            child.tag.lower().endswith("image")
            and child.text
            and child.text.strip().startswith("http")
        ):
          img_url = child.text.strip()
          break
    if not img_url:
      img_url = extract_thumbnail_for_item(
          link, full_raw_html, default_platform
      )

    pub_str, pub_ts = extract_date_from_url_or_text(
        link, desc, pub_raw, fallback_offset_sec=fallback_offset
    )
    if max_age_sec > 0 and (now_ts - pub_ts) > max_age_sec:
      continue

    results.append({
        "title": title,
        "url": link,
        "raw_snippet": desc[:1800] if desc else title,
        "source_name": source_name or default_platform,
        "platform": default_platform,
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": img_url,
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
    thumb_el = entry.find("media:group/media:thumbnail", ns)
    img_url = (
        thumb_el.attrib.get("url", "").strip()
        if thumb_el is not None
        else extract_thumbnail_for_item(link, "", default_platform)
    )
    snippet_txt = clean_html_text(media_desc) or title
    if not title or not link:
      continue
    pub_str, pub_ts = extract_date_from_url_or_text(
        link, snippet_txt, pub_raw, fallback_offset_sec=fallback_offset
    )
    if max_age_sec > 0 and (now_ts - pub_ts) > max_age_sec:
      continue

    results.append({
        "title": title,
        "url": link,
        "raw_snippet": snippet_txt[:1800],
        "source_name": clean_html_text(
            author_name or default_source or default_platform
        ),
        "platform": default_platform,
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": img_url,
    })

  return results


def scrape_moroccan_press(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
):
  items = []
  seen_urls = set()
  queries = build_search_queries(keywords_input)
  p_cfg = get_period_config(search_period)
  when_tag = p_cfg["gnews"]
  max_age = p_cfg["sec"]

  direct_sites = [s for s in MOROCCAN_PRESS_SITES if s.get("rss")]
  batch_size = 4
  site_batches = [
      MOROCCAN_PRESS_SITES[i : i + batch_size]
      for i in range(0, len(MOROCCAN_PRESS_SITES), batch_size)
  ]
  total_steps = len(direct_sites[:6]) + len(queries) + len(site_batches)
  step = 0

  search_term_wp = (
      keywords_input.strip().split(",")[0].strip()
      if keywords_input.strip()
      else "القضاء"
  )
  for site_info in direct_sites[:6]:
    if is_stop_requested():
      break
    step += 1
    if progress_cb:
      progress_cb(
          min(0.95, step / max(1, total_steps)),
          f"فحص الخلاصة المباشرة لجريدة {site_info['name']}...",
      )
    wp_search_rss = f"https://{site_info['domain']}/?s={urllib.parse.quote(search_term_wp)}&feed=rss2"
    for feed_u in [wp_search_rss, site_info["rss"]]:
      try:
        rf = requests.get(feed_u, headers=DEFAULT_HEADERS, timeout=6)
        if rf.status_code == 200 and (
            b"<rss" in rf.content or b"<feed" in rf.content
        ):
          for entry in parse_rss_xml(
              rf.content,
              "الصحف",
              default_source=site_info["name"],
              max_age_sec=max_age,
          ):
            if entry["url"] not in seen_urls and is_strictly_judicial_and_clean(
                entry["title"],
                entry["raw_snippet"],
                entry["url"],
                keywords_input,
            ):
              seen_urls.add(entry["url"])
              items.append(entry)
          break
      except Exception:
        pass

  for q in queries:
    if is_stop_requested():
      break
    step += 1
    if progress_cb:
      progress_cb(
          min(0.95, step / max(1, total_steps)), f"رصد الصحافة الوطنية: {q}"
      )
    bing_news_u = (
        f"https://www.bing.com/news/search?q={urllib.parse.quote(q)}"
        "&format=rss&adlt=strict&cc=MA&setlang=ar"
    )
    try:
      rb = requests.get(bing_news_u, headers=DEFAULT_HEADERS, timeout=8)
      if rb.status_code == 200 and b"<item>" in rb.content:
        for entry in parse_rss_xml(rb.content, "الصحف", max_age_sec=max_age):
          if entry["url"] not in seen_urls and is_strictly_judicial_and_clean(
              entry["title"],
              entry["raw_snippet"],
              entry["url"],
              keywords_input,
          ):
            seen_urls.add(entry["url"])
            items.append(entry)
    except Exception:
      pass

    rss_url = (
        "https://news.google.com/rss/search?q="
        f"{urllib.parse.quote(f'{q} when:{when_tag}')}&hl=ar&gl=MA&ceid=MA:ar"
    )
    try:
      r = requests.get(rss_url, headers=DEFAULT_HEADERS, timeout=10)
      if r.status_code == 200:
        for entry in parse_rss_xml(r.content, "الصحف", max_age_sec=max_age):
          if entry["url"] not in seen_urls and is_strictly_judicial_and_clean(
              entry["title"],
              entry["raw_snippet"],
              entry["url"],
              keywords_input,
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
    full_q = f"({sites_expr}) {core_kw} when:{when_tag}"
    rss_url = (
        "https://news.google.com/rss/search?q="
        f"{urllib.parse.quote(full_q)}&hl=ar&gl=MA&ceid=MA:ar"
    )
    try:
      r = requests.get(rss_url, headers=DEFAULT_HEADERS, timeout=10)
      if r.status_code == 200:
        for entry in parse_rss_xml(r.content, "الصحف", max_age_sec=max_age):
          if entry["url"] not in seen_urls and is_strictly_judicial_and_clean(
              entry["title"],
              entry["raw_snippet"],
              entry["url"],
              keywords_input,
          ):
            seen_urls.add(entry["url"])
            items.append(entry)
    except Exception:
      pass

  return items


def _extract_yt_renderers_from_html(
    html_text: str, default_channel_name: str = "YouTube"
):
  results = []
  seen_vids = set()
  chunks = re.split(
      r'"(?:videoRenderer|gridVideoRenderer|compactVideoRenderer|reelItemRenderer|shortsLockupViewModel|lockupViewModel)"\s*:',
      html_text,
  )[1:]
  for chunk in chunks[:45]:
    vid_m = re.search(
        r'"(?:videoId|contentId)"\s*:\s*"([a-zA-Z0-9_-]{11})"', chunk[:2500]
    )
    if not vid_m:
      continue
    vid = vid_m.group(1)
    if vid in seen_vids:
      continue

    title = ""
    for t_pat in [
        r'"title"\s*:\s*\{[^{}]*"runs"\s*:\s*\[\{"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"title"\s*:\s*\{"runs"\s*:\s*\[\{"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"title"\s*:\s*\{[^{}]*"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"headline"\s*:\s*\{[^{}]*"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"primaryText"\s*:\s*\{"content"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"title"\s*:\s*\{"content"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"accessibilityData"\s*:\s*\{"label"\s*:\s*"((?:[^"\\]|\\.)*)"',
    ]:
      m_t = re.search(t_pat, chunk[:3500])
      if m_t:
        cand_t = decode_js_escaped_text(m_t.group(1))
        if len(cand_t) >= 4:
          title = cand_t
          break

    if not title:
      continue

    pub_rel = ""
    for p_pat in [
        r'"publishedTimeText"\s*:\s*\{"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"publishedTimeText"\s*:\s*\{"runs"\s*:\s*\[\{"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
    ]:
      pub_m = re.search(p_pat, chunk[:4000])
      if pub_m:
        pub_rel = decode_js_escaped_text(pub_m.group(1))
        break

    owner_m = re.search(
        r'"(?:ownerText|shortBylineText|longBylineText)"\s*:\s*\{"runs"\s*:\s*\[\{"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
        chunk[:4500],
    )
    channel_name = (
        decode_js_escaped_text(owner_m.group(1))
        if owner_m
        else default_channel_name
    )

    owner_id_m = re.search(
        r'"(?:ownerText|shortBylineText|longBylineText)".*?"browseId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"',
        chunk[:4500],
    )
    owner_id = owner_id_m.group(1) if owner_id_m else ""

    owner_h_m = re.search(
        r'"canonicalBaseUrl"\s*:\s*"/(@?[^"\\]+)"',
        chunk[:4500],
    )
    owner_handle = (
        urllib.parse.unquote(owner_h_m.group(1)).lstrip("@")
        if owner_h_m
        else ""
    )

    desc_runs = re.findall(
        r'"detailedMetadataSnippets".*?"snippetText"\s*:\s*\{"runs"\s*:\s*\[(.*?)\]\s*\}',
        chunk[:5000],
    )
    if not desc_runs:
      desc_runs = re.findall(
          r'"descriptionSnippet"\s*:\s*\{"runs"\s*:\s*\[(.*?)\]\s*\}',
          chunk[:5000],
      )
    desc_text = ""
    if desc_runs:
      parts = re.findall(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', desc_runs[0])
      desc_text = decode_js_escaped_text(" ".join(parts))

    seen_vids.add(vid)
    results.append({
        "vid": vid,
        "title": title,
        "pub_rel": pub_rel,
        "channel_name": channel_name,
        "owner_id": owner_id,
        "owner_handle": owner_handle,
        "desc": desc_text or title,
    })
  return results


def scrape_youtube_platform(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
):
  items = []
  seen_urls = set()
  queries = build_search_queries(keywords_input)[:4]
  p_cfg = get_period_config(search_period)
  max_age = p_cfg["sec"]
  yt_sp = p_cfg["yt"]
  now_ts = time.time()

  for idx, q in enumerate(queries):
    if is_stop_requested():
      break
    if progress_cb:
      progress_cb((idx + 1) / max(1, len(queries)), f"مسح يوتيوب: {q}")
    search_url = (
        "https://www.youtube.com/results?search_query="
        f"{urllib.parse.quote(q)}&sp={yt_sp}"
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
          if not is_strictly_judicial_and_clean(
              v["title"], v["desc"], v_url, keywords_input
          ):
            continue
          pub_str, pub_ts = extract_date_from_url_or_text(
              v_url, v["desc"], v["pub_rel"], fallback_offset_sec=3600
          )
          if max_age > 0 and (now_ts - pub_ts) > max_age:
            continue
          seen_urls.add(v_url)
          items.append({
              "title": v["title"],
              "url": v_url,
              "raw_snippet": v["desc"],
              "source_name": f"قناة {v['channel_name']}",
              "platform": "يوتيوب",
              "pub_date": pub_str,
              "pub_timestamp": pub_ts,
              "image_url": f"https://i.ytimg.com/vi/{v['vid']}/hqdefault.jpg",
          })
    except Exception:
      pass

  return items


def _multi_engine_social_search(
    platform_label: str,
    site_domains: list,
    keywords_input: str,
    search_period: str = "آخر 7 أيام",
    progress_cb=None,
):
  items = []
  seen_urls = set()
  queries = build_search_queries(keywords_input)[:3]
  p_cfg = get_period_config(search_period)
  when_tag = p_cfg["gnews"]
  ddg_tl = p_cfg["ddg"]
  max_age = p_cfg["sec"]
  now_ts = time.time()

  for idx, q in enumerate(queries):
    if is_stop_requested():
      break
    if progress_cb:
      progress_cb(
          (idx + 1) / max(1, len(queries) + 2),
          f"مسح {platform_label}: {q}",
      )

    for d in site_domains[:2]:
      if is_stop_requested():
        break
      site_q = f"site:{d} {q}"
      for bing_base in [
          "https://www.bing.com/search?q=",
          "https://www.bing.com/news/search?q=",
      ]:
        bing_rss = (
            f"{bing_base}{urllib.parse.quote(site_q)}"
            "&format=rss&adlt=strict&cc=MA&setlang=ar"
        )
        try:
          r = requests.get(bing_rss, headers=DEFAULT_HEADERS, timeout=9)
          if r.status_code == 200 and b"<item>" in r.content:
            for entry in parse_rss_xml(
                r.content,
                platform_label,
                default_source=platform_label,
                fallback_offset=3600,
                max_age_sec=max_age,
            ):
              if entry["url"] not in seen_urls and is_strictly_judicial_and_clean(
                  entry["title"],
                  entry["raw_snippet"],
                  entry["url"],
                  keywords_input,
              ):
                seen_urls.add(entry["url"])
                items.append(entry)
        except Exception:
          pass

    if DDGS is not None and not is_stop_requested():
      for d in site_domains[:2]:
        try:
          with DDGS() as ddgs:
            ddg_q = f"site:{d} {q}"
            for res in ddgs.text(
                ddg_q,
                region="xa-ar",
                safesearch="strict",
                timelimit=ddg_tl,
                max_results=10,
            ):
              href = clean_social_post_url(
                  (res.get("href") or res.get("url") or "").strip()
              )
              title = clean_html_text(res.get("title") or "")
              body = clean_html_text(res.get("body") or "")
              if not href or href in seen_urls:
                continue
              if not any(dom in href.lower() for dom in site_domains):
                continue
              if platform_label == "فيسبوك" and not is_direct_social_post_url(
                  href, "فيسبوك", allow_post_search=False
              ):
                href = resolve_direct_facebook_post_url(body, title)
              if not href or href in seen_urls:
                continue
              if not is_strictly_judicial_and_clean(
                  title, body, href, keywords_input
              ):
                continue
              pub_str, pub_ts = extract_date_from_url_or_text(
                  href, body, "", fallback_offset_sec=3600
              )
              if max_age > 0 and (now_ts - pub_ts) > max_age:
                continue
              seen_urls.add(href)
              items.append({
                  "title": title or body[:95],
                  "url": href,
                  "raw_snippet": body or title,
                  "source_name": platform_label,
                  "platform": platform_label,
                  "pub_date": pub_str,
                  "pub_timestamp": pub_ts,
                  "image_url": extract_thumbnail_for_item(
                      href, "", platform_label
                  ),
              })
        except Exception:
          pass

  if not is_stop_requested():
    if progress_cb:
      progress_cb(
          0.88, f"جلب المنشورات القضائية الموثوقة على {platform_label}..."
      )
    platform_simple_queries = {
        "فيسبوك": [
            f"المجلس الأعلى للسلطة القضائية فيسبوك المغرب when:{when_tag}",
            f"رئاسة النيابة العامة فيسبوك المغرب when:{when_tag}",
            f"القضاء بالمغرب فيسبوك when:{when_tag}",
            f"محكمة النقض المغرب فيسبوك when:{when_tag}",
            f"وزارة العدل المغرب فايسبوك when:{when_tag}",
        ],
        "إكس": [
            f"المجلس الأعلى للسلطة القضائية إكس المغرب when:{when_tag}",
            f"القضاء بالمغرب تغريدة when:{when_tag}",
            f"رئاسة النيابة العامة المغرب تويتر when:{when_tag}",
            f"العدالة بالمغرب منصة إكس when:{when_tag}",
            f"محكمة النقض المغرب تويتر when:{when_tag}",
        ],
        "أخرى": [
            f"المجلس الأعلى للسلطة القضائية تيك توك المغرب when:{when_tag}",
            f"القضاء بالمغرب إنستغرام when:{when_tag}",
            f"المجلس الأعلى للسلطة القضائية لينكدإن when:{when_tag}",
            f"رئاسة النيابة العامة المغرب مواقع التواصل when:{when_tag}",
        ],
    }
    social_g_queries = platform_simple_queries.get(platform_label, [])
    if keywords_input.strip():
      kw_clean = keywords_input.strip()
      if platform_label == "فيسبوك":
        social_g_queries = [
            f"{kw_clean} القضاء فيسبوك المغرب when:{when_tag}",
            f"{kw_clean} العدالة فايسبوك المغرب when:{when_tag}",
        ]
      elif platform_label == "إكس":
        social_g_queries = [
            f"{kw_clean} القضاء تغريدة المغرب when:{when_tag}",
            f"{kw_clean} العدالة منصة إكس المغرب when:{when_tag}",
        ]
      else:
        social_g_queries = [
            f"{kw_clean} القضاء تيك توك المغرب when:{when_tag}",
            f"{kw_clean} القضاء إنستغرام المغرب when:{when_tag}",
        ]

    plat_tag_slug = {"فيسبوك": "fb", "إكس": "x", "أخرى": "other"}.get(
        platform_label, "soc"
    )
    for sq in social_g_queries:
      if is_stop_requested():
        break
      gnews_social_url = (
          "https://news.google.com/rss/search?q="
          f"{urllib.parse.quote(sq)}&hl=ar&gl=MA&ceid=MA:ar"
      )
      try:
        r = requests.get(gnews_social_url, headers=DEFAULT_HEADERS, timeout=10)
        if r.status_code == 200:
          for entry in parse_rss_xml(
              r.content,
              platform_label,
              fallback_offset=3600,
              max_age_sec=max_age,
          ):
            tagged_url = f"{entry['url']}#plat={plat_tag_slug}"
            if (
                tagged_url not in seen_urls
                and is_strictly_judicial_and_clean(
                    entry["title"],
                    entry["raw_snippet"],
                    entry["url"],
                    keywords_input,
                )
            ):
              entry["url"] = tagged_url
              entry["platform"] = platform_label
              seen_urls.add(tagged_url)
              items.append(entry)
      except Exception:
        pass

  return items


def _extract_fb_page_label_from_entry(url: str, title: str) -> str:
  """استخراج اسم صفحة فيسبوك الناشرة من العنوان أو الرابط لعرضه بوضوح على البطاقة."""
  t_clean = _clean_social_page_title(title)
  if " - " in t_clean:
    first_part = t_clean.split(" - ")[0].strip()
    if 3 <= len(first_part) <= 42:
      return f"فيسبوك • {first_part}"
  try:
    parsed = urllib.parse.urlparse(clean_social_post_url(url))
    parts = [urllib.parse.unquote(p).strip() for p in parsed.path.strip("/").split("/") if p.strip()]
    if parts and parts[0].lower() not in GENERIC_SOCIAL_SEGMENTS and not parts[0].isdigit():
      return f"فيسبوك • {parts[0]}"
    if len(parts) >= 2 and parts[0].lower() in ("p", "people", "pages"):
      p_lbl = re.sub(r"-\d{8,}$", "", parts[1]).replace("-", " ").strip()
      if p_lbl:
        return f"فيسبوك • {p_lbl[:35]}"
  except Exception:
    pass
  return "فيسبوك"


MOROCCAN_JUDICIAL_AND_PRESS_FB_PAGES = [
    ("pmpmaroc", "فيسبوك • رئاسة النيابة العامة"),
    ("Hespress", "فيسبوك • هسبريس"),
    ("al3omk", "فيسبوك • العمق المغربي"),
    ("alyaoum24", "فيسبوك • اليوم 24"),
    ("madar21com", "فيسبوك • مدار 21"),
    ("alayam24", "فيسبوك • الأيام 24"),
    ("goudmag", "فيسبوك • كود"),
    ("akhbarona.page", "فيسبوك • أخبارنا"),
    ("rue20.ma", "فيسبوك • زنقة 20"),
]


def scrape_facebook_platform(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
):
  """محرك رصد شامل لمنصة فيسبوك يجمع بين الفحص المباشر للخط الزمني لصفحات القضاء والصحافة المغربية على فيسبوك والبحث المتعدد المحركات."""
  items = []
  seen_urls = set()
  p_cfg = get_period_config(search_period)
  max_age = p_cfg["sec"]
  now_ts = time.time()

  chrome_doc_headers = dict(DEFAULT_HEADERS)
  chrome_doc_headers.update({
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Sec-Fetch-Dest": "document",
      "Sec-Fetch-Mode": "navigate",
      "Sec-Fetch-Site": "none",
      "Upgrade-Insecure-Requests": "1",
  })

  # 1) الفحص المباشر للخط الزمني لصفحات المؤسسات القضائية والصحف المغربية الكبرى على فيسبوك (يعمل حتى لو حجبت محركات البحث site:facebook.com)
  for p_idx, (fb_handle, fb_badge) in enumerate(MOROCCAN_JUDICIAL_AND_PRESS_FB_PAGES):
    if is_stop_requested():
      break
    if progress_cb:
      progress_cb(
          min(0.55, (p_idx + 1) / max(1, len(MOROCCAN_JUDICIAL_AND_PRESS_FB_PAGES) * 2)),
          f"فحص منشورات {fb_badge} الحية...",
      )
    page_u = f"https://www.facebook.com/{fb_handle}"
    is_pure_judicial_page = fb_handle == "pmpmaroc"

    # أ) فحص أداة الخط الزمني لفيسبوك (BigPipe plugin)
    plugin_posts = _scrape_facebook_plugin_timeline(
        page_u,
        {},
        fb_badge,
        "",
        keywords_input,
        handle=fb_handle,
        page_id="",
    )
    # ب) فحص كود Comet SSR JSON المباشر للصفحة
    try:
      rc = requests.get(
          page_u,
          headers=chrome_doc_headers,
          cookies={"locale": "ar_AR"},
          timeout=7,
      )
      if rc.status_code == 200 and rc.text and len(rc.text) > 15000:
        plugin_posts.extend(
            _extract_facebook_posts_from_raw_html(
                rc.text,
                page_u,
                fb_handle,
                "",
                {},
                fb_badge,
                "",
                keywords_input,
                page_official_name=fb_badge.replace("فيسبوك • ", ""),
            )
        )
    except Exception:
      pass

    for p in plugin_posts:
      u_p = clean_social_post_url(p.get("url", ""))
      if not u_p or u_p in seen_urls or not is_direct_social_post_url(u_p, "فيسبوك"):
        continue
      # إذا كانت صفحة صحفية عامة، نشترط أن يكون المنشور قضائياً؛ أما صفحة رئاسة النيابة العامة فجميع منشوراتها قضائية
      if not is_strictly_judicial_and_clean(
          p.get("title", ""),
          p.get("raw_snippet", ""),
          u_p,
          keywords_input,
          is_target=is_pure_judicial_page and not bool(keywords_input.strip()),
      ):
        continue
      seen_urls.add(u_p)
      p["url"] = f"{u_p}#plat=fb"
      p["platform"] = "فيسبوك"
      p["source_name"] = fb_badge
      items.append(p)

  # 2) البحث العميق في منشورات وفيديوهات فيسبوك عبر محركات البحث المتوازية
  if keywords_input and keywords_input.strip():
    custom_kws = [k.strip() for k in re.split(r"[,،\n]+", keywords_input) if k.strip()]
    fb_queries = []
    for kw in custom_kws[:4]:
      fb_queries.append(f'site:facebook.com "{kw}" القضاء المغرب')
      fb_queries.append(f'facebook.com "{kw}" المحكمة OR النيابة العامة المغرب')
  else:
    fb_queries = [
        'site:facebook.com "المجلس الأعلى للسلطة القضائية"',
        'site:facebook.com "رئاسة النيابة العامة" المغرب',
        'site:facebook.com "محكمة النقض" المغرب',
        'site:facebook.com "الوكيل العام للملك" OR "وكيل الملك" المغرب',
        'facebook.com/posts "القضاء" OR "النيابة العامة" المغرب',
        'facebook.com/videos "القضاء" OR "المجلس الأعلى للسلطة القضائية" المغرب',
    ]

  total_q = len(fb_queries)
  for idx, fq in enumerate(fb_queries):
    if is_stop_requested():
      break
    if progress_cb:
      progress_cb(
          min(0.92, 0.55 + 0.37 * ((idx + 1) / max(1, total_q))),
          f"مسح منشورات وفيديوهات فيسبوك القضائية ({idx + 1}/{total_q})...",
      )

    search_results = _multi_engine_web_search(
        fq, platform="فيسبوك", default_source="فيسبوك", max_results=16
    )
    for entry in search_results:
      if is_stop_requested():
        break
      raw_u = clean_social_post_url(entry.get("url", ""))
      if not raw_u or ("facebook.com" not in raw_u.lower() and "fb.watch" not in raw_u.lower()):
        continue

      raw_snip = _strip_fb_sidebar_noise(entry.get("raw_snippet", ""))
      raw_title = _strip_fb_sidebar_noise(entry.get("title", ""))

      if not is_direct_social_post_url(raw_u, "فيسبوك"):
        resolved_u = resolve_direct_facebook_post_url(raw_snip, raw_title)
        if resolved_u and is_direct_social_post_url(resolved_u, "فيسبوك"):
          raw_u = resolved_u
        else:
          continue

      if raw_u in seen_urls:
        continue

      if len(items) < 14:
        is_ok, og_body, og_img, final_u = _verify_and_enrich_fb_post_url(raw_u)
        if not is_ok:
          continue
        if og_body and len(og_body) >= 20:
          raw_snip = og_body
        if og_img and not entry.get("image_url"):
          entry["image_url"] = og_img
        raw_u = final_u

      display_title = raw_snip[:115] + ("..." if len(raw_snip) > 115 else "") if len(raw_snip) >= 25 else _clean_social_page_title(raw_title)
      if not display_title or len(display_title) < 12:
        continue

      if not is_strictly_judicial_and_clean(
          display_title, raw_snip, raw_u, keywords_input, is_target=False
      ):
        continue

      pub_str, pub_ts = extract_date_from_url_or_text(
          raw_u, raw_snip, entry.get("pub_date", ""), fallback_offset_sec=2400
      )
      if max_age > 0 and (now_ts - pub_ts) > max(max_age, 7 * 86400):
        continue

      src_lbl = _extract_fb_page_label_from_entry(raw_u, raw_title)
      seen_urls.add(raw_u)
      items.append({
          "title": display_title,
          "url": f"{raw_u}#plat=fb",
          "raw_snippet": raw_snip or display_title,
          "source_name": src_lbl,
          "platform": "فيسبوك",
          "pub_date": pub_str,
          "pub_timestamp": pub_ts,
          "image_url": entry.get("image_url", ""),
      })

  # 3) استكمال الرصد من التغطيات القضائية الموثوقة لمنشورات فيسبوك
  if len(items) < 8 and not is_stop_requested():
    extra_social = _multi_engine_social_search(
        "فيسبوك", ["facebook.com"], keywords_input, search_period, progress_cb=None
    )
    for ex in extra_social:
      u_ex = clean_social_post_url(ex.get("url", ""))
      if u_ex and u_ex not in seen_urls:
        seen_urls.add(u_ex)
        items.append(ex)

  return items


def scrape_x_platform(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
):
  return _multi_engine_social_search(
      "إكس",
      ["x.com", "twitter.com"],
      keywords_input,
      search_period,
      progress_cb,
  )


def scrape_other_platforms(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
):
  return _multi_engine_social_search(
      "أخرى",
      ["tiktok.com", "instagram.com", "linkedin.com"],
      keywords_input,
      search_period,
      progress_cb,
  )


# =====================================================================
# 9. محرك الرصد المخصص الدقيق والمقيد حصرياً بالقناة أو الصفحة المضافة
# =====================================================================
def _tag_custom_target_item(item: dict, t_info: dict, source_badge: str) -> dict:
  """إلحاق وسم الرابط المخصص بمعرف الرابط المباشر للمنشور لضمان حفظه واسترجاعه في تبويب المخصص بنسبة 100%."""
  u_clean = clean_social_post_url(item.get("url", ""))
  t_tag = t_info.get("target_tag", "")
  item["url"] = f"{u_clean}{t_tag}"
  item["source_name"] = source_badge
  item["platform"] = t_info.get("platform", item.get("platform", "الصحف"))
  item["is_custom_target"] = 1
  item["_verified_target_owner"] = True
  return item


def _multi_engine_web_search(
    query: str,
    platform: str = "فيسبوك",
    default_source: str = "",
    max_results: int = 18,
) -> list:
  """بحث فائق الكفاءة عبر 5 محركات متوازية (Bing HTML, Yahoo HTML, DuckDuckGo POST/Lite, Bing RSS, DDGS) لجلب منشورات فيسبوك والمنصات بدقة."""
  collected = []
  seen_u = set()
  bad_boiler = [
      "قم بتسجيل الدخول إلى فيسبوك",
      "لبدء المشاركة والتواصل مع أصدقائك",
      "log in to facebook to start sharing",
      "log in or sign up to view",
  ]

  def _add_candidate(raw_href: str, raw_title: str, raw_body: str, raw_date: str = ""):
    u = clean_social_post_url(raw_href)
    if not u or u in seen_u or not u.startswith("http"):
      return
    if any(skip_d in u.lower() for skip_d in ["bing.com/ck/", "yahoo.com/search", "duckduckgo.com"]):
      return
    t_txt = _strip_fb_sidebar_noise(raw_title)
    b_txt = _strip_fb_sidebar_noise(raw_body)
    if any(bb in b_txt.lower() for bb in bad_boiler):
      b_txt = ""
    if not t_txt and not b_txt:
      return
    pub_str, pub_ts = extract_date_from_url_or_text(
        u, f"{t_txt} {b_txt}", raw_date, fallback_offset_sec=3600
    )
    seen_u.add(u)
    collected.append({
        "title": t_txt or b_txt[:110],
        "url": u,
        "raw_snippet": b_txt or t_txt,
        "source_name": default_source or platform,
        "platform": platform,
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": extract_thumbnail_for_item(u, "", platform),
    })

  # 1) محرك Bing Web Search HTML المباشر (الأقوى في فهرسة صفحات ومنشورات فيسبوك العربية والمغربية)
  bing_html_url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count={max_results}&setlang=ar&cc=MA"
  try:
    rb_html = requests.get(bing_html_url, headers=DEFAULT_HEADERS, timeout=8)
    if rb_html.status_code == 200 and rb_html.text and BeautifulSoup is not None:
      soup_b = BeautifulSoup(rb_html.text, "html.parser")
      for li_el in soup_b.select("li.b_algo, div.b_algo"):
        a_el = li_el.select_one("h2 a[href], a[href]")
        if not a_el:
          continue
        href = a_el.get("href", "").strip()
        title_txt = clean_display_text(a_el.get_text(" ", strip=True))
        snip_el = li_el.select_one("div.b_caption p, p.b_lineclamp2, p.b_lineclamp3, p.b_lineclamp4, .b_caption")
        snip_txt = (
            clean_display_text(snip_el.get_text(" ", strip=True))
            if snip_el
            else ""
        )
        _add_candidate(href, title_txt, snip_txt)
  except Exception:
    pass

  # 2) محرك Yahoo Search HTML (موسع ليدعم جميع قوالب Yahoo الحديثة)
  yahoo_url = f"https://search.yahoo.com/search?p={urllib.parse.quote(query)}&n={max_results}"
  try:
    ry = requests.get(yahoo_url, headers=DEFAULT_HEADERS, timeout=8)
    if ry.status_code == 200 and ry.text and BeautifulSoup is not None:
      soup_y = BeautifulSoup(ry.text, "html.parser")
      for algo in soup_y.select("div.algo, div.dd.algo, li div.algo-sr, div.Sr"):
        a_el = algo.select_one("h3 a[href], div.compTitle a[href], a.ac-algo[href], a[href]")
        if not a_el:
          continue
        href = a_el.get("href", "").strip()
        title_txt = clean_display_text(a_el.get_text(" ", strip=True))
        snip_el = algo.select_one("div.compText, p, span.fc-falcon")
        snip_txt = (
            clean_display_text(snip_el.get_text(" ", strip=True))
            if snip_el
            else ""
        )
        _add_candidate(href, title_txt, snip_txt)
  except Exception:
    pass

  # 3) محرك DuckDuckGo HTML عبر طلب POST (يتجاوز حظر الـ 202 الذي يحدث مع طلبات GET على السحابة)
  ddg_post_headers = dict(DEFAULT_HEADERS)
  ddg_post_headers.update({
      "Referer": "https://html.duckduckgo.com/",
      "Origin": "https://html.duckduckgo.com",
      "Content-Type": "application/x-www-form-urlencoded",
  })
  try:
    rd = requests.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query, "kl": "xa-ar"},
        headers=ddg_post_headers,
        timeout=8,
    )
    if rd.status_code == 200 and rd.text and BeautifulSoup is not None:
      soup_d = BeautifulSoup(rd.text, "html.parser")
      for res_box in soup_d.select("div.result, div.web-result, div.results_links"):
        a_el = res_box.select_one("a.result__a[href], h2 a[href]")
        if not a_el:
          continue
        href = a_el.get("href", "").strip()
        title_txt = clean_display_text(a_el.get_text(" ", strip=True))
        snip_el = res_box.select_one(".result__snippet, a.result__snippet")
        snip_txt = (
            clean_display_text(snip_el.get_text(" ", strip=True))
            if snip_el
            else ""
        )
        _add_candidate(href, title_txt, snip_txt)
  except Exception:
    pass

  # 4) محرك Bing Search RSS & Bing News RSS
  for bing_base in [
      "https://www.bing.com/search?q=",
      "https://www.bing.com/news/search?q=",
  ]:
    bing_u = (
        f"{bing_base}{urllib.parse.quote(query)}"
        "&format=rss&adlt=strict&cc=MA&setlang=ar"
    )
    try:
      rb = requests.get(bing_u, headers=DEFAULT_HEADERS, timeout=7)
      if rb.status_code == 200 and b"<item>" in rb.content:
        for entry in parse_rss_xml(
            rb.content,
            platform,
            default_source=default_source or platform,
            fallback_offset=3600,
            max_age_sec=0,
        ):
          u_e = clean_social_post_url(entry.get("url", ""))
          if u_e and u_e not in seen_u:
            seen_u.add(u_e)
            entry["url"] = u_e
            collected.append(entry)
    except Exception:
      pass

  # 5) مكتبة DDGS الاحتياطية
  if DDGS is not None and len(collected) < max_results:
    try:
      with DDGS() as ddgs:
        for res in ddgs.text(
            query,
            region="wt-wt",
            safesearch="strict",
            timelimit=None,
            max_results=max_results,
        ):
          _add_candidate(
              res.get("href") or res.get("url") or "",
              res.get("title") or "",
              res.get("body") or "",
          )
    except Exception:
      pass

  return collected


def _resolve_youtube_channel_via_innertube(channel_url: str) -> tuple:
  """استخدام واجهة YouTube InnerTube الرسمية (resolve_url) لتحويل أي رابط قناة (@handle أو /c/) إلى معرف القناة الدقيق UC... فوراً."""
  api_url = "https://www.youtube.com/youtubei/v1/navigation/resolve_url?prettyPrint=false"
  payload = {
      "context": {
          "client": {
              "clientName": "WEB",
              "clientVersion": "2.20240726.00.00",
              "hl": "ar",
              "gl": "MA",
          }
      },
      "url": channel_url,
  }
  headers = dict(DEFAULT_HEADERS)
  headers["Content-Type"] = "application/json"
  try:
    r = requests.post(
        api_url, json=payload, headers=headers, cookies=YT_BYPASS_COOKIES, timeout=8
    )
    if r.status_code == 200 and r.text:
      m_id = re.search(r'"browseId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"', r.text)
      if m_id:
        return m_id.group(1), ""
  except Exception:
    pass
  return "", ""


def _browse_youtube_channel_via_innertube(
    cid: str, channel_title: str = "YouTube"
) -> tuple:
  """جلب أحدث الفيديوهات والـ Shorts مباشرة من واجهة YouTube InnerTube (browse) لتجاوز عدم الأرشفة وجدران الكوكيز."""
  api_url = "https://www.youtube.com/youtubei/v1/browse?prettyPrint=false"
  headers = dict(DEFAULT_HEADERS)
  headers["Content-Type"] = "application/json"
  videos = []
  detected_title = channel_title

  # EgZ2aWRlb3PyBgQKAjoA = تبويب الفيديوهات مرتبة من الأحدث، EgZzaG9ydHPyBgUKA5oBAA%3D%3D = تبويب Shorts
  for tab_params in ["EgZ2aWRlb3PyBgQKAjoA", "EgZzaG9ydHPyBgUKA5oBAA==", "EgdzdHJlYW1z8gYECgJ6AA=="]:
    payload = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20240726.00.00",
                "hl": "ar",
                "gl": "MA",
            }
        },
        "browseId": cid,
        "params": tab_params,
    }
    try:
      r = requests.post(
          api_url,
          json=payload,
          headers=headers,
          cookies=YT_BYPASS_COOKIES,
          timeout=9,
      )
      if r.status_code == 200 and r.text:
        m_t = re.search(
            r'"channelMetadataRenderer"\s*:\s*\{[^{}]*"title"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r.text,
        )
        if m_t:
          cand_t = decode_js_escaped_text(m_t.group(1))
          if cand_t:
            detected_title = cand_t
        v_list = _extract_yt_renderers_from_html(r.text, detected_title)
        videos.extend(v_list)
    except Exception:
      pass
  return videos, detected_title


def _verify_youtube_video_owner(
    video_url: str, handle: str = "", cid: str = "", channel_title: str = ""
) -> tuple:
  """التحقق عبر YouTube oEmbed الرسمي من أن الفيديو مرفوع فعلياً من القناة المطلوبة وليس من قناة أخرى."""
  oembed_u = f"https://www.youtube.com/oembed?url={urllib.parse.quote(video_url)}&format=json"
  try:
    r = requests.get(oembed_u, headers=DEFAULT_HEADERS, timeout=5)
    if r.status_code == 200:
      data = r.json()
      author_name = clean_display_text(data.get("author_name") or "")
      author_url = urllib.parse.unquote(str(data.get("author_url") or "")).lower()
      v_title = clean_display_text(data.get("title") or "")

      if handle and f"@{handle.lower().lstrip('@')}" in author_url:
        return True, v_title, author_name
      if handle and f"/{handle.lower().lstrip('@')}" in author_url:
        return True, v_title, author_name
      if cid and cid.lower() in author_url:
        return True, v_title, author_name
      if (
          channel_title
          and channel_title.lower() != "youtube"
          and not channel_title.startswith("@")
          and channel_title.lower() in author_name.lower()
      ):
        return True, v_title, author_name
      return False, v_title, author_name
  except Exception:
    pass
  return False, "", ""


def _does_yt_video_belong_to_channel(
    v: dict, handle: str = "", cid: str = "", channel_title: str = ""
) -> bool:
  """التحقق من أن الفيديو المستخرج من بحث يوتيوب الحي يعود للقناة المطلوبة حصراً."""
  v_cid = (v.get("owner_id") or "").strip().lower()
  v_handle = (v.get("owner_handle") or "").strip().lower().lstrip("@")
  v_ch_name = (v.get("channel_name") or "").strip().lower()

  t_cid = (cid or "").strip().lower()
  t_handle = (handle or "").strip().lower().lstrip("@")
  t_title = (channel_title or "").strip().lower().lstrip("@")

  if t_cid and v_cid:
    return v_cid == t_cid
  if t_handle and v_handle:
    if v_handle == t_handle or t_handle in v_handle or v_handle in t_handle:
      return True
  if t_handle and len(t_handle) >= 3 and t_handle in v_ch_name:
    return True
  if t_title and t_title != "youtube" and len(t_title) >= 3:
    if t_title in v_ch_name or v_ch_name in t_title:
      return True
    for part in re.split(r"[-|•–—:/()]+", t_title):
      p_clean = part.strip()
      if len(p_clean) >= 4 and p_clean in v_ch_name:
        return True
  return False


def _scrape_youtube_custom_channel(
    t_info: dict, t_kw: str, max_age_sec: int, seen_urls: set
) -> list:
  results = []
  all_channel_videos = []
  raw_u = t_info["raw_url"]
  cid = t_info.get("channel_id", "")
  handle = t_info.get("handle", "")
  name_hint = t_info.get("official_name_hint", "")
  is_name_target = bool(t_info.get("is_name_target", False))
  channel_title = name_hint or t_info.get("display_label", "YouTube")

  # إذا كان الرابط المضاف رابط فيديو يوتيوب مباشر، نرصده فوراً
  if not is_name_target:
    m_direct_v = re.search(
        r"(?:watch\?v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})", raw_u
    )
    if m_direct_v:
      vid_id = m_direct_v.group(1)
      v_url = f"https://www.youtube.com/watch?v={vid_id}"
      _, v_oembed_title, v_author = _verify_youtube_video_owner(v_url)
      _, p_body, _ = scrape_article_page_content_and_image(v_url)
      v_title = v_oembed_title or (
          p_body[:105] if p_body else f"فيديو يوتيوب ({vid_id})"
      )
      badge_lbl = f"🎯 {v_author or channel_title}"
      pub_str, pub_ts = extract_date_from_url_or_text(
          v_url, p_body, "", fallback_offset_sec=1800
      )
      entry = {
          "title": v_title,
          "url": v_url,
          "raw_snippet": p_body or v_title,
          "source_name": badge_lbl,
          "platform": "يوتيوب",
          "pub_date": pub_str,
          "pub_timestamp": pub_ts,
          "image_url": f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg",
      }
      _tag_custom_target_item(entry, t_info, badge_lbl)
      return [entry]

  page_html = ""
  if not is_name_target:
    parsed_u = urllib.parse.urlparse(raw_u)
    clean_base_u = urllib.parse.urlunparse(
        ("https", "www.youtube.com", parsed_u.path.rstrip("/"), "", "", "")
    )
    if cid and not handle:
      videos_tab_url = f"https://www.youtube.com/channel/{cid}/videos"
    elif handle:
      h_prefix = (
          f"@{handle}"
          if not handle.startswith("@")
          and "/c/" not in clean_base_u
          and "/user/" not in clean_base_u
          else handle
      )
      if "/c/" in clean_base_u or "/user/" in clean_base_u:
        videos_tab_url = f"{clean_base_u}/videos"
      else:
        videos_tab_url = f"https://www.youtube.com/{h_prefix}/videos"
    else:
      videos_tab_url = (
          clean_base_u
          if any(
              clean_base_u.endswith(x)
              for x in ["/videos", "/streams", "/shorts"]
          )
          else f"{clean_base_u}/videos"
      )

    # 1) استخراج معرف القناة الدقيق UC عبر ترويسة facebookexternalhit المسموحة دائماً على خوادم السحابة
    if not cid:
      try:
        r_crawler = requests.get(
            clean_base_u, headers=FB_CRAWLER_HEADERS, timeout=8
        )
        if r_crawler.status_code == 200 and r_crawler.text:
          for c_pat in [
              r"feeds/videos\.xml\?channel_id=(UC[a-zA-Z0-9_-]{20,})",
              r"https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]{20,})",
              r'"externalId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"',
          ]:
            m_cid = re.search(c_pat, r_crawler.text[:45000])
            if m_cid:
              cid = m_cid.group(1)
              break
          m_og_t = re.search(
              r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
              r_crawler.text[:35000],
              re.IGNORECASE,
          )
          if m_og_t and m_og_t.group(1).strip():
            c_title = clean_display_text(m_og_t.group(1).strip())
            c_title = re.sub(
                r"\s*-\s*YouTube.*$", "", c_title, flags=re.IGNORECASE
            ).strip()
            if c_title and c_title.lower() != "youtube":
              channel_title = c_title
      except Exception:
        pass

    if not cid:
      cid, _ = _resolve_youtube_channel_via_innertube(clean_base_u)

    # 2) جلب صفحة فيديوهات القناة المباشرة
    for candidate_yt_url in [videos_tab_url, clean_base_u]:
      try:
        r = requests.get(
            candidate_yt_url,
            headers=DEFAULT_HEADERS,
            cookies=YT_BYPASS_COOKIES,
            timeout=10,
        )
        if r.status_code == 200 and r.text:
          page_html = r.text
          og_t = re.search(
              r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
              page_html,
              re.IGNORECASE,
          )
          if og_t and og_t.group(1).strip():
            cand_name = clean_display_text(og_t.group(1).strip())
            cand_name = re.sub(
                r"\s*-\s*YouTube.*$", "", cand_name, flags=re.IGNORECASE
            ).strip()
            if cand_name and cand_name.lower() != "youtube":
              channel_title = cand_name

          if not cid:
            for pat in [
                r"feeds/videos\.xml\?channel_id=(UC[a-zA-Z0-9_-]{20,})",
                r'"channelMetadataRenderer"\s*:\s*\{[^{}]*"externalId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"',
                r'"externalId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"',
                r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]{20,})["\']',
                r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]{20,})["\']',
                r'<meta[^>]+itemprop=["\']channelId["\'][^>]+content=["\'](UC[a-zA-Z0-9_-]{20,})["\']',
            ]:
              m_c = re.search(pat, page_html)
              if m_c:
                cid = m_c.group(1)
                break
          if (
              cid
              or '"videoRenderer"' in page_html
              or '"gridVideoRenderer"' in page_html
          ):
            break
      except Exception:
        pass

  # 3) البحث المباشر داخل يوتيوب باسم القناة أو معرفها لاستخراج معرف UC والفيديوهات الحية غير المؤرشفة
  live_search_videos = []
  search_ident = (
      name_hint
      or (f"@{handle}" if handle else "")
      or (channel_title if channel_title.lower() != "youtube" else "")
  )
  if search_ident and (not cid or is_name_target or not page_html):
    for sp_param in ["", "&sp=CAI%253D"]:
      q_yt_live = f"{search_ident} {t_kw}".strip() if sp_param else search_ident
      yt_search_u = (
          "https://www.youtube.com/results?search_query="
          f"{urllib.parse.quote(q_yt_live)}{sp_param}"
      )
      try:
        rs_yt = requests.get(
            yt_search_u,
            headers=DEFAULT_HEADERS,
            cookies=YT_BYPASS_COOKIES,
            timeout=10,
        )
        if rs_yt.status_code == 200 and rs_yt.text:
          if not cid:
            # استخراج معرف القناة من بطاقة القناة الرسمية channelRenderer في نتائج البحث
            m_ch_card = re.search(
                r'"channelRenderer"\s*:\s*\{.*?"channelId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})".*?"title"\s*:\s*\{"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"',
                rs_yt.text[:60000],
            )
            if m_ch_card:
              cid = m_ch_card.group(1)
              det_t = decode_js_escaped_text(m_ch_card.group(2))
              if det_t:
                channel_title = det_t
            else:
              m_ch_simple = re.search(
                  r'"channelRenderer"\s*:\s*\{[^{}]*"channelId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"',
                  rs_yt.text[:60000],
              )
              if m_ch_simple:
                cid = m_ch_simple.group(1)

          extracted_from_search = _extract_yt_renderers_from_html(
              rs_yt.text, channel_title
          )
          for v_cand in extracted_from_search:
            if _does_yt_video_belong_to_channel(
                v_cand, handle=handle, cid=cid, channel_title=channel_title
            ):
              if not cid and v_cand.get("owner_id"):
                cid = v_cand["owner_id"]
              if (
                  v_cand.get("channel_name")
                  and channel_title.lower() == "youtube"
              ):
                channel_title = v_cand["channel_name"]
              live_search_videos.append(v_cand)
      except Exception:
        pass

  now_ts = time.time()
  seen_channel_vids = set()

  # 4) الجلب الفوري من واجهة YouTube InnerTube Browse API الخاصة بالقناة
  if cid:
    innertube_vids, it_title = _browse_youtube_channel_via_innertube(
        cid, channel_title
    )
    if it_title and it_title.lower() != "youtube":
      channel_title = it_title
  else:
    innertube_vids = []

  source_badge = f"🎯 {channel_title}"

  # 5) الجلب من خلاصة XML الرسمية للقناة (تتحدث بالثانية فور رفع أي فيديو جديد دون انتظار أرشفة محركات البحث)
  if cid:
    xml_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    try:
      rx = requests.get(xml_url, headers=DEFAULT_HEADERS, timeout=10)
      if rx.status_code == 200:
        for entry in parse_rss_xml(
            rx.content,
            "يوتيوب",
            default_source=source_badge,
            max_age_sec=0,
        ):
          u_clean_v = clean_social_post_url(entry.get("url", ""))
          if not is_direct_social_post_url(u_clean_v, "يوتيوب"):
            continue
          if not is_strictly_judicial_and_clean(
              entry["title"],
              entry["raw_snippet"],
              u_clean_v,
              t_kw,
              is_target=True,
          ):
            continue
          if u_clean_v not in seen_channel_vids:
            seen_channel_vids.add(u_clean_v)
            entry["url"] = u_clean_v
            _tag_custom_target_item(entry, t_info, source_badge)
            all_channel_videos.append(entry)
    except Exception:
      pass

  # 6) دمج الفيديوهات المستخرجة من InnerTube Browse ومن تبويب /videos ومن بحث يوتيوب الحي المفلتر بملكية القناة
  direct_renderers = list(innertube_vids)
  if page_html:
    direct_renderers.extend(
        _extract_yt_renderers_from_html(page_html, channel_title)
    )
  direct_renderers.extend(live_search_videos)

  for v in direct_renderers:
    v_url = f"https://www.youtube.com/watch?v={v['vid']}"
    if v_url in seen_channel_vids or not is_direct_social_post_url(
        v_url, "يوتيوب"
    ):
      continue
    if not is_strictly_judicial_and_clean(
        v["title"], v["desc"], v_url, t_kw, is_target=True
    ):
      continue
    pub_str, pub_ts = extract_date_from_url_or_text(
        v_url, v["desc"], v["pub_rel"], fallback_offset_sec=3600
    )
    v_badge = (
        f"🎯 {v['channel_name']}"
        if v.get("channel_name") and v["channel_name"] != "YouTube"
        else source_badge
    )
    entry = {
        "title": v["title"],
        "url": v_url,
        "raw_snippet": v["desc"],
        "source_name": v_badge,
        "platform": "يوتيوب",
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": f"https://i.ytimg.com/vi/{v['vid']}/hqdefault.jpg",
    }
    seen_channel_vids.add(v_url)
    _tag_custom_target_item(entry, t_info, v_badge)
    all_channel_videos.append(entry)

  # 6-ب) إذا حجب يوتيوب صفحة القناة على السحابة ولم يظهر معرف UC بعد، نستخرجه من أول فيديو موثق للقناة عبر oEmbed ثم نسحب خلاصة XML الرسمية الفورية
  if not cid and (handle or name_hint):
    yt_ident_probe = f"@{handle.lstrip('@')}" if handle else name_hint
    for probe_q in [f'site:youtube.com/watch "{yt_ident_probe}"', f'site:youtube.com "{yt_ident_probe}"']:
      if cid:
        break
      for cand_v in _multi_engine_web_search(probe_q, platform="يوتيوب", max_results=8):
        u_probe = clean_social_post_url(cand_v.get("url", ""))
        if not is_direct_social_post_url(u_probe, "يوتيوب"):
          continue
        is_own, _, real_auth = _verify_youtube_video_owner(
            u_probe, handle=handle, cid="", channel_title=channel_title
        )
        if is_own:
          if real_auth and real_auth.lower() != "youtube":
            channel_title = real_auth
            source_badge = f"🎯 {channel_title}"
          try:
            rv_page = requests.get(u_probe, headers=FB_CRAWLER_HEADERS, timeout=6)
            if rv_page.status_code == 200 and rv_page.text:
              m_vcid = re.search(
                  r'(?:itemprop=["\']channelId["\'][^>]+content=["\']|"channelId"\s*:\s*"|"externalChannelId"\s*:\s*")(UC[a-zA-Z0-9_-]{20,})',
                  rv_page.text[:65000],
              )
              if m_vcid:
                cid = m_vcid.group(1)
                break
          except Exception:
            pass
    if cid:
      xml_url_retry = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
      try:
        rx2 = requests.get(xml_url_retry, headers=DEFAULT_HEADERS, timeout=10)
        if rx2.status_code == 200:
          for entry in parse_rss_xml(
              rx2.content,
              "يوتيوب",
              default_source=source_badge,
              max_age_sec=0,
          ):
            u_clean_v = clean_social_post_url(entry.get("url", ""))
            if not is_direct_social_post_url(u_clean_v, "يوتيوب"):
              continue
            if not is_strictly_judicial_and_clean(
                entry["title"], entry["raw_snippet"], u_clean_v, t_kw, is_target=True
            ):
              continue
            if u_clean_v not in seen_channel_vids:
              seen_channel_vids.add(u_clean_v)
              entry["url"] = u_clean_v
              _tag_custom_target_item(entry, t_info, source_badge)
              all_channel_videos.append(entry)
      except Exception:
        pass

  # 7) احتياطي أخير عبر محركات البحث مقيد بتحقق oEmbed
  if not all_channel_videos and (handle or cid or name_hint):
    yt_ident = name_hint or (f"@{handle.lstrip('@')}" if handle else cid)
    q_web_yt = f'site:youtube.com "{yt_ident}" {t_kw}'.strip()
    for item_w in _multi_engine_web_search(
        q_web_yt,
        platform="يوتيوب",
        default_source=source_badge,
        max_results=10,
    ):
      u_w = clean_social_post_url(item_w.get("url", ""))
      if u_w in seen_channel_vids or not is_direct_social_post_url(
          u_w, "يوتيوب"
      ):
        continue
      is_owner, real_v_title, real_author = _verify_youtube_video_owner(
          u_w, handle=handle, cid=cid, channel_title=channel_title
      )
      if not is_owner:
        continue
      if real_v_title:
        item_w["title"] = real_v_title
      if not is_strictly_judicial_and_clean(
          item_w["title"], item_w["raw_snippet"], u_w, t_kw, is_target=True
      ):
        continue
      seen_channel_vids.add(u_w)
      _tag_custom_target_item(
          item_w, t_info, f"🎯 {real_author or channel_title}"
      )
      all_channel_videos.append(item_w)

  all_channel_videos.sort(
      key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
  )

  in_window = [
      e
      for e in all_channel_videos
      if max_age_sec <= 0
      or (now_ts - float(e.get("pub_timestamp", 0))) <= max_age_sec
  ]
  chosen_list = in_window if in_window else all_channel_videos[:12]
  for entry in chosen_list:
    if entry["url"] not in seen_urls:
      seen_urls.add(entry["url"])
      results.append(entry)

  return results


def _scrape_website_custom_target(
    t_info: dict, t_kw: str, when_tag: str, max_age_sec: int, seen_urls: set
) -> list:
  results = []
  all_site_items = []
  raw_u = t_info["raw_url"]
  domain = t_info["domain"]
  parsed = urllib.parse.urlparse(raw_u)
  base_origin = f"{parsed.scheme}://{parsed.netloc}"
  source_badge = f"🎯 {domain}"
  now_ts = time.time()

  candidate_feeds = [
      f"{raw_u.rstrip('/')}/feed",
      f"{base_origin}/feed",
      f"{base_origin}/rss",
      f"{base_origin}/rss.xml",
      f"{base_origin}/?feed=rss2",
  ]
  if t_kw:
    candidate_feeds.insert(
        0, f"{base_origin}/?s={urllib.parse.quote(t_kw)}&feed=rss2"
    )

  for feed_url in candidate_feeds:
    if is_stop_requested():
      break
    try:
      rf = requests.get(feed_url, headers=DEFAULT_HEADERS, timeout=8)
      if rf.status_code == 200 and (
          b"<rss" in rf.content or b"<feed" in rf.content
      ):
        for entry in parse_rss_xml(
            rf.content,
            "الصحف",
            default_source=source_badge,
            max_age_sec=0,
        ):
          if domain not in entry["url"].lower():
            continue
          if entry["url"].rstrip("/") == raw_u.rstrip("/"):
            continue
          if not is_strictly_judicial_and_clean(
              entry["title"],
              entry["raw_snippet"],
              entry["url"],
              t_kw,
              is_target=True,
          ):
            continue
          _tag_custom_target_item(entry, t_info, source_badge)
          all_site_items.append(entry)
        if all_site_items:
          break
    except Exception:
      pass

  if BeautifulSoup is not None and len(all_site_items) < 5:
    try:
      rp = requests.get(raw_u, headers=DEFAULT_HEADERS, timeout=9)
      if rp is not None and rp.status_code == 200 and rp.text:
        soup = BeautifulSoup(rp.text, "html.parser")
        for a_tag in soup.select(
            "article a, h2 a, h3 a, .post-title a, .entry-title a, a"
        ):
          href = (a_tag.get("href") or "").strip()
          if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
          full_href = urllib.parse.urljoin(raw_u, href)
          if domain not in full_href.lower():
            continue
          if full_href.rstrip("/") == raw_u.rstrip("/"):
            continue
          title_txt = clean_display_text(a_tag.get_text(" ", strip=True))
          if len(title_txt) < 22:
            continue
          if not is_strictly_judicial_and_clean(
              title_txt, "", full_href, t_kw, is_target=True
          ):
            continue
          pub_str, pub_ts = extract_date_from_url_or_text(
              full_href, title_txt, "", fallback_offset_sec=3600
          )
          entry = {
              "title": title_txt,
              "url": full_href,
              "raw_snippet": title_txt,
              "source_name": source_badge,
              "platform": "الصحف",
              "pub_date": pub_str,
              "pub_timestamp": pub_ts,
              "image_url": "",
          }
          _tag_custom_target_item(entry, t_info, source_badge)
          all_site_items.append(entry)
          if len(all_site_items) >= 15:
            break
    except Exception:
      pass

  all_site_items.sort(
      key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
  )
  in_window = [
      e
      for e in all_site_items
      if max_age_sec <= 0
      or (now_ts - float(e.get("pub_timestamp", 0))) <= max_age_sec
  ]
  chosen_list = in_window if in_window else all_site_items[:10]
  for entry in chosen_list:
    if entry["url"] not in seen_urls:
      seen_urls.add(entry["url"])
      results.append(entry)

  return results


def _unwrap_facebook_bigpipe_html(raw_html: str) -> str:
  """فك تعليقات BigPipe (<!-- ... -->) وسلاسل ServerJS (__html) في صفحات وأدوات فيسبوك لإظهار المنشورات الحية غير المؤرشفة."""
  if not raw_html:
    return ""
  expanded = raw_html.replace("<!--", "").replace("-->", "")
  extra_chunks = []
  for m_js in re.finditer(
      r'"__html"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_html
  ):
    chunk_raw = m_js.group(1)
    try:
      decoded = json.loads(f'"{chunk_raw}"')
    except Exception:
      decoded = decode_js_escaped_text(chunk_raw)
    if decoded and ("_5pcr" in decoded or "userContent" in decoded or "story_fbid" in decoded or "/posts/" in decoded):
      extra_chunks.append(decoded)
  if extra_chunks:
    expanded = expanded + "\n" + "\n".join(extra_chunks)
  return expanded


def _extract_post_permalink_from_fb_box(
    box, canonical_fb_url: str, handle: str = "", page_id: str = ""
) -> str:
  """استخراج الرابط المباشر للمنشور بعينه من حاوية المنشور في فيسبوك دون توجيه المستخدم إلى الصفحة العامة."""
  for sel in ["a._5pcq[href]", "span.fsm a[href]", "a[href]"]:
    for a_el in box.select(sel):
      raw_h = (a_el.get("href") or "").strip()
      if not raw_h or raw_h.startswith("#") or raw_h.startswith("javascript:"):
        continue
      cand_u = clean_social_post_url(raw_h)
      if is_direct_social_post_url(cand_u, "فيسبوك") and _is_fb_post_owned_by_target(
          cand_u, handle=handle, page_id=page_id
      ):
        return cand_u

  ft_nodes = [box] + list(box.select("[data-ft]"))
  for node in ft_nodes:
    raw_ft = node.get("data-ft") if hasattr(node, "get") else None
    if not raw_ft:
      continue
    try:
      ft_json = json.loads(html.unescape(str(raw_ft)))
      post_id = str(
          ft_json.get("top_level_post_id")
          or ft_json.get("tl_objid")
          or ft_json.get("mf_story_key")
          or ""
      ).strip()
      owner_id = str(
          ft_json.get("page_id")
          or ft_json.get("content_owner_id_new")
          or page_id
          or ""
      ).strip()
      if post_id and len(post_id) >= 8:
        if handle and not handle.startswith("fb_") and not handle.isdigit():
          cand_u = f"https://www.facebook.com/{handle}/posts/{post_id}"
          if is_direct_social_post_url(cand_u, "فيسبوك"):
            return cand_u
        if owner_id:
          return f"https://www.facebook.com/permalink.php?story_fbid={post_id}&id={owner_id}"
    except Exception:
      m_pid = re.search(
          r'"(?:top_level_post_id|tl_objid|mf_story_key)"\s*:\s*"([^"]+)"',
          str(raw_ft),
      )
      m_oid = re.search(
          r'"(?:page_id|content_owner_id_new)"\s*:\s*"?(\d{6,})"?',
          str(raw_ft),
      )
      if m_pid:
        pid_val = m_pid.group(1).strip()
        oid_val = m_oid.group(1).strip() if m_oid else page_id
        if handle and not handle.startswith("fb_") and not handle.isdigit():
          return f"https://www.facebook.com/{handle}/posts/{pid_val}"
        if oid_val:
          return f"https://www.facebook.com/permalink.php?story_fbid={pid_val}&id={oid_val}"

  return ""


def _fetch_fb_embed_plugin_content(post_u: str) -> tuple:
  """استخراج النص الكامل والصورة والتاريخ لأي منشور أو فيديو فيسبوك عبر نقطة التضمين الرسمية (plugins/post.php و plugins/video.php) التي لا تطلب تسجيل الدخول على السحابة."""
  u_clean = clean_social_post_url(post_u)
  if not u_clean:
    return "", "", ""
  is_vid = any(x in u_clean.lower() for x in ("/videos/", "/watch", "/reel/", "fb.watch"))
  endpoint = "https://www.facebook.com/plugins/video.php" if is_vid else "https://www.facebook.com/plugins/post.php"
  embed_url = f"{endpoint}?href={urllib.parse.quote(u_clean)}&show_text=true&width=500"
  hdr = dict(DEFAULT_HEADERS)
  hdr.update({
      "Referer": "https://www.facebook.com/",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  })
  try:
    r = requests.get(embed_url, headers=hdr, timeout=6)
    if r.status_code != 200 or not r.text:
      return "", "", ""
    doc = _unwrap_facebook_bigpipe_html(r.text)
    if BeautifulSoup is None:
      return "", "", ""
    soup = BeautifulSoup(doc, "html.parser")
    texts = []
    for sel in ["div._5pbx", "div.userContent", "div[data-ad-preview='message']", "p"]:
      for el in soup.select(sel):
        t = clean_display_text(el.get_text(" ", strip=True))
        if len(t) >= 12 and t not in texts:
          texts.append(t)
    body = " ".join(texts[:3]).strip()
    body = re.sub(r"\b(?:عرض المزيد|See More|See more|عرض الترجمة)\b", "", body, flags=re.IGNORECASE).strip()

    img = ""
    for img_el in soup.select("img[src]"):
      s_img = html.unescape(img_el.get("src", "").strip())
      if s_img.startswith("http") and "scontent" in s_img and "p50x50" not in s_img and "s50x50" not in s_img:
        img = s_img
        break

    utime = ""
    ut_el = soup.select_one("abbr[data-utime], span[data-utime]")
    if ut_el:
      utime = str(ut_el.get("data-utime") or "").strip()
    return _strip_fb_sidebar_noise(body), img, utime
  except Exception:
    return "", "", ""


def _scrape_facebook_plugin_timeline(
    canonical_fb_url: str,
    t_info: dict,
    source_badge: str,
    page_avatar: str,
    t_kw: str,
    handle: str = "",
    page_id: str = "",
) -> list:
  """استخراج المنشورات الفورية غير المؤرشفة مباشرة من أداة الخط الزمني لفيسبوك (plugins/page.php) بعد فك تعليقات BigPipe ودعم المعرف الرقمي المباشر."""
  posts = []
  seen_post_urls = set()

  candidate_hrefs = []
  if handle and not handle.startswith("fb_") and not handle.isdigit():
    candidate_hrefs.append(f"https://www.facebook.com/{handle}")
  if page_id and page_id.isdigit():
    # أداة plugins/page.php تقبل المسار الرقمي المباشر facebook.com/{page_id} بينما ترفض profile.php?id=
    candidate_hrefs.append(f"https://www.facebook.com/{page_id}")
  if canonical_fb_url and canonical_fb_url not in candidate_hrefs:
    candidate_hrefs.append(canonical_fb_url)

  iframe_headers = dict(DEFAULT_HEADERS)
  iframe_headers.update({
      "Referer": "https://www.facebook.com/",
      "Sec-Fetch-Dest": "iframe",
      "Sec-Fetch-Mode": "navigate",
      "Sec-Fetch-Site": "same-origin",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  })

  for target_href in candidate_hrefs[:3]:
    plugin_url = (
        "https://www.facebook.com/plugins/page.php?"
        f"href={urllib.parse.quote(target_href)}"
        "&tabs=timeline&width=500&height=800&small_header=false"
        "&adapt_container_width=true&hide_cover=false&show_facepile=false"
    )
    for hdr in (iframe_headers, FB_CRAWLER_HEADERS):
      try:
        r = requests.get(plugin_url, headers=hdr, cookies={"locale": "ar_AR"}, timeout=9)
        if r.status_code != 200 or not r.text:
          continue

        unwrapped_doc = _unwrap_facebook_bigpipe_html(r.text)
        if not page_id:
          m_pid_doc = re.search(r'"(?:page_id|content_owner_id_new)"\s*:\s*"?(\d{6,})"?', unwrapped_doc)
          if m_pid_doc:
            page_id = m_pid_doc.group(1)

        if BeautifulSoup is not None:
          soup = BeautifulSoup(unwrapped_doc, "html.parser")
          post_containers = soup.select(
              "div._5pcr, div.userContentWrapper, div._4-u2._5v3q, div._4-u2._5pat, div[data-ft*='top_level_post_id'], div[data-ft*='tl_objid'], div[data-ft*='mf_story_key'], div[role='article']"
          )

          for idx, box in enumerate(post_containers[:18]):
            post_link = _extract_post_permalink_from_fb_box(
                box, target_href, handle=handle, page_id=page_id
            )
            if not post_link or not is_direct_social_post_url(post_link, "فيسبوك"):
              continue
            if not _is_fb_post_owned_by_target(
                post_link, handle=handle, page_id=page_id
            ):
              continue
            if post_link in seen_post_urls:
              continue

            text_el = box.select_one(
                "div._5pbx, div.userContent, div[data-ad-preview='message']"
            )
            if text_el:
              post_text = clean_display_text(text_el.get_text(" ", strip=True))
            else:
              p_tags = [
                  clean_display_text(p.get_text(" ", strip=True))
                  for p in box.select("p")
                  if len(clean_display_text(p.get_text(" ", strip=True))) >= 10
              ]
              post_text = (
                  " ".join(p_tags)
                  if p_tags
                  else clean_display_text(box.get_text(" ", strip=True))
              )

            post_text = re.sub(
                r"\b(?:عرض المزيد|See More|See more|عرض الترجمة)\b",
                "",
                post_text,
                flags=re.IGNORECASE,
            ).strip()

            if not post_text or len(post_text) < 12:
              emb_txt, emb_img, _ = _fetch_fb_embed_plugin_content(post_link)
              if emb_txt:
                post_text = emb_txt
              if emb_img and not page_avatar:
                page_avatar = emb_img

            if not post_text or len(post_text) < 12:
              continue
            if not is_strictly_judicial_and_clean(
                post_text, post_text, post_link, t_kw, is_target=bool(t_info)
            ):
              continue

            utime_el = box.select_one("abbr[data-utime], span[data-utime]")
            raw_utime = utime_el.get("data-utime", "") if utime_el else ""
            if not raw_utime and utime_el:
              raw_utime = clean_display_text(utime_el.get_text(" ", strip=True))

            post_img = page_avatar
            for img_el in box.select("img[src]"):
              s_img = html.unescape(img_el.get("src", "").strip())
              if (
                  s_img.startswith("http")
                  and "scontent" in s_img
                  and "p50x50" not in s_img
                  and "s50x50" not in s_img
              ):
                post_img = s_img
                break

            pub_str, pub_ts = extract_date_from_url_or_text(
                post_link,
                post_text,
                str(raw_utime),
                fallback_offset_sec=1800 + (idx * 600),
            )
            title_short = post_text[:115] + ("..." if len(post_text) > 115 else "")
            entry = {
                "title": title_short,
                "url": post_link,
                "raw_snippet": post_text,
                "source_name": source_badge,
                "platform": "فيسبوك",
                "pub_date": pub_str,
                "pub_timestamp": pub_ts,
                "image_url": post_img,
            }
            if t_info:
              _tag_custom_target_item(entry, t_info, source_badge)
            seen_post_urls.add(post_link)
            posts.append(entry)

        if not posts:
          extra_posts = _extract_facebook_posts_from_raw_html(
              unwrapped_doc,
              target_href,
              handle,
              page_id,
              t_info,
              source_badge,
              page_avatar,
              t_kw,
          )
          for ep in extra_posts:
            u_ep = clean_social_post_url(ep["url"])
            if u_ep not in seen_post_urls:
              seen_post_urls.add(u_ep)
              posts.append(ep)

        if posts:
          return posts
      except Exception:
        pass
  return posts


def _strip_fb_sidebar_noise(text: str) -> str:
  """إزالة نصوص الشريط الجانبي لفيسبوك (مثل: More videos you may like / فيديوهات أخرى قد تعجبك) من الملخصات."""
  if not text:
    return ""
  t = clean_display_text(text)
  for marker in [
      "More videos you may like",
      "فيديوهات أخرى قد تعجبك",
      "مقاطع فيديو أخرى قد تعجبك",
      "Related Pages",
      "صفحات ذات صلة",
      "See more from",
      "عرض المزيد من",
  ]:
    pos = t.lower().find(marker.lower())
    if pos != -1:
      t = t[:pos].strip(" -–—·•|.")
  return t


def _verify_and_enrich_fb_post_url(
    post_u: str,
    page_avatar: str = "",
    handle: str = "",
    page_id: str = "",
    page_official_name: str = "",
) -> tuple:
  """فحص رابط المنشور عبر ترويسات المعاينة + نقطة التضمين الرسمية (plugins/post.php) للتغلب على جدار تسجيل الدخول على السحابة."""
  try:
    p_html = ""
    rp = None
    for bot_hdr in FB_PREVIEW_BOT_HEADERS[:2]:
      try:
        r_try = requests.get(post_u, headers=bot_hdr, timeout=5)
        if r_try.status_code == 200 and r_try.text:
          rp = r_try
          p_html = r_try.text[:45000]
          if "og:description" in p_html or "og:title" in p_html:
            break
      except Exception:
        pass

    if not p_html:
      emb_body, emb_img, _ = _fetch_fb_embed_plugin_content(post_u)
      is_owned = _is_fb_post_owned_by_target(
          post_u, handle=handle, page_id=page_id, page_official_name=page_official_name
      )
      return is_owned, emb_body, emb_img or page_avatar, post_u

    post_title_og = ""
    for t_pat in [
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        r"<title>(.*?)</title>",
    ]:
      m_t = re.search(t_pat, p_html, re.IGNORECASE | re.DOTALL)
      if m_t:
        post_title_og = _strip_fb_sidebar_noise(m_t.group(1))
        break

    not_found_titles = [
        "page not found",
        "الصفحة غير موجودة",
    ]
    if post_title_og and any(bt in post_title_og.lower() for bt in not_found_titles):
      return False, "", "", post_u

    is_login_wall = bool(
        (rp is not None and rp.url and "login" in rp.url.lower())
        or (
            post_title_og
            and any(
                lw in post_title_og.lower()
                for lw in [
                    "log in",
                    "login",
                    "تسجيل الدخول",
                    "قم بتسجيل الدخول",
                    "content isn't available",
                    "this content isn't available",
                    "المحتوى غير متوفر",
                ]
            )
        )
    )
    if is_login_wall:
      # عند ظهور جدار تسجيل الدخول على السيرفر، نستعين بنقطة التضمين الرسمية plugins/post.php لاستخراج متن المنشور وصورته!
      emb_body, emb_img, _ = _fetch_fb_embed_plugin_content(post_u)
      is_owned = _is_fb_post_owned_by_target(
          post_u, handle=handle, page_id=page_id, page_official_name=page_official_name
      )
      return is_owned, emb_body, emb_img or page_avatar, post_u

    m_og_u = re.search(
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
        p_html,
        re.IGNORECASE,
    )
    resolved_u = post_u
    if m_og_u:
      cand_og_u = clean_social_post_url(m_og_u.group(1))
      if cand_og_u and "login" not in cand_og_u.lower() and is_direct_social_post_url(cand_og_u, "فيسبوك"):
        resolved_u = cand_og_u

    if not _is_fb_post_owned_by_target(
        resolved_u,
        handle=handle,
        page_id=page_id,
        page_official_name=page_official_name,
        og_title=post_title_og,
    ):
      return False, "", "", resolved_u

    post_desc = ""
    for d_pat in [
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
    ]:
      m_d = re.search(d_pat, p_html, re.IGNORECASE)
      if m_d:
        d_txt = _strip_fb_sidebar_noise(m_d.group(1))
        if len(d_txt) >= 10:
          post_desc = d_txt
          break

    post_img = page_avatar
    for i_pat in [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    ]:
      m_i = re.search(i_pat, p_html, re.IGNORECASE)
      if m_i:
        post_img = html.unescape(m_i.group(1).strip())
        break

    final_body = post_desc or post_title_og
    if final_body and any(
        lw in final_body.lower()
        for lw in [
            "قم بتسجيل الدخول",
            "log in to facebook",
            "تسجيل الدخول إلى فيسبوك",
            "log in or sign up",
        ]
    ):
      final_body = ""

    if not final_body or len(final_body) < 15:
      emb_body, emb_img, _ = _fetch_fb_embed_plugin_content(resolved_u)
      if emb_body:
        final_body = emb_body
      if emb_img and post_img == page_avatar:
        post_img = emb_img

    return True, final_body, post_img, resolved_u
  except Exception:
    is_owned = _is_fb_post_owned_by_target(
        post_u, handle=handle, page_id=page_id, page_official_name=page_official_name
    )
    return is_owned, "", page_avatar, post_u


def _walk_comet_json_for_stories(node, collected_stories: list, depth: int = 0):
  """تجول عودي ذكي داخل شجرة JSON الخاصة بـ Facebook Comet SSR لاستخراج كائنات المنشورات والفيديوهات الحية بدقة 100%."""
  if depth > 28 or node is None:
    return
  if isinstance(node, list):
    for item in node:
      _walk_comet_json_for_stories(item, collected_stories, depth + 1)
    return
  if not isinstance(node, dict):
    return

  # التحقق مما إذا كانت العقدة الحالية تمثل منشوراً أو قصة (Story) في فيسبوك
  has_msg = isinstance(node.get("message"), dict) and bool(node["message"].get("text"))
  has_comet_sec = isinstance(node.get("comet_sections"), dict)
  has_story_urls = any(k in node for k in ("permalink_url", "wwwURL", "shareable_url"))
  if has_msg or has_comet_sec or has_story_urls:
    collected_stories.append(node)

  for k, val in node.items():
    if isinstance(val, (dict, list)):
      _walk_comet_json_for_stories(val, collected_stories, depth + 1)


def _extract_fields_from_story_dict(story_node: dict, handle: str = "", page_id: str = "") -> dict:
  """استخراج نص المنشور، الرابط المباشر، وقت النشر، والصورة المصغرة من عقدة Story في Comet JSON."""
  texts = []
  urls = []
  timestamps = []
  images = []
  post_ids = []

  def _scan_story(sub, d=0):
    if d > 14 or sub is None:
      return
    if isinstance(sub, list):
      for x in sub:
        _scan_story(x, d + 1)
      return
    if not isinstance(sub, dict):
      return

    for k, v in sub.items():
      if k in ("message", "savable_description", "title") and isinstance(v, dict):
        t_val = v.get("text")
        if isinstance(t_val, str) and len(t_val.strip()) >= 12:
          texts.append(clean_display_text(t_val))
      elif k in ("permalink_url", "wwwURL", "url", "shareable_url") and isinstance(v, str):
        u_cand = clean_social_post_url(v)
        if is_direct_social_post_url(u_cand, "فيسبوك"):
          urls.append(u_cand)
      elif k in ("creation_time", "publish_time") and isinstance(v, (int, float)):
        if 1500000000 < v < 2100000000:
          timestamps.append(int(v))
      elif k in ("post_id", "story_fbid", "top_level_post_id") and isinstance(v, (str, int)):
        s_v = str(v).strip()
        if s_v.startswith("pfbid") or (s_v.isdigit() and len(s_v) >= 8):
          post_ids.append(s_v)
      elif k == "id" and isinstance(v, str) and v.startswith("UzpfS"):
        try:
          dec = base64.b64decode(v + "===").decode("utf-8", errors="ignore")
          m_sp = re.search(r"S:_I(\d{6,}):(\d{8,}|pfbid[A-Za-z0-9]+)", dec)
          if m_sp:
            post_ids.append(m_sp.group(2))
        except Exception:
          pass
      elif k == "uri" and isinstance(v, str) and "scontent" in v:
        if not any(sz in v for sz in ("p50x50", "s50x50", "p32x32", "s32x32", "p40x40")):
          images.append(v)

      if isinstance(v, (dict, list)):
        _scan_story(v, d + 1)

  _scan_story(story_node)

  best_text = ""
  for t_cand in texts:
    if len(t_cand) > len(best_text):
      best_text = t_cand

  best_url = ""
  for u_cand in urls:
    if _is_fb_post_owned_by_target(u_cand, handle=handle, page_id=page_id):
      best_url = u_cand
      break

  if not best_url and post_ids:
    pid = post_ids[0]
    if handle and not handle.startswith("fb_") and not handle.isdigit():
      best_url = f"https://www.facebook.com/{handle}/posts/{pid}"
    elif page_id:
      best_url = f"https://www.facebook.com/permalink.php?story_fbid={pid}&id={page_id}"

  return {
      "text": best_text,
      "url": best_url,
      "timestamp": timestamps[0] if timestamps else 0,
      "image": images[0] if images else "",
  }


def _extract_comet_relay_posts_from_html(
    raw_html: str,
    handle: str,
    page_id: str,
    page_official_name: str,
    t_info: dict,
    source_badge: str,
    page_avatar: str,
    t_kw: str,
) -> list:
  """تحليل بيانات Comet Relay JSON المضمنة في كود صفحة فيسبوك الحديث (عبر تحليل شجرة JSON + التعبير النمطي المرن) لاستخراج المنشورات الحية."""
  if not raw_html:
    return []

  posts = []
  seen_u = set()

  # 1) التحليل الشجري الكامل لجميع كتل <script type="application/json"> في الصفحة
  for m_script in re.finditer(
      r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
      raw_html,
      re.DOTALL | re.IGNORECASE,
  ):
    s_txt = m_script.group(1).strip()
    if len(s_txt) < 100 or not any(
        k in s_txt for k in ("message", "comet_sections", "pfbid", "story_fbid", "creation_time", "UzpfS")
    ):
      continue
    try:
      data_json = json.loads(s_txt)
      story_nodes = []
      _walk_comet_json_for_stories(data_json, story_nodes)
      for s_node in story_nodes:
        info = _extract_fields_from_story_dict(s_node, handle=handle, page_id=page_id)
        p_txt = _strip_fb_sidebar_noise(info["text"])
        p_url = clean_social_post_url(info["url"])
        if not p_txt or len(p_txt) < 14 or not p_url or p_url in seen_u:
          continue
        if not is_direct_social_post_url(p_url, "فيسبوك"):
          continue
        if not _is_fb_post_owned_by_target(
            p_url, handle=handle, page_id=page_id, page_official_name=page_official_name
        ):
          continue
        if not is_strictly_judicial_and_clean(
            p_txt, p_txt, p_url, t_kw, is_target=bool(t_info)
        ):
          continue
        raw_ts = str(info["timestamp"]) if info["timestamp"] else ""
        pub_str, pub_ts = extract_date_from_url_or_text(
            p_url, p_txt, raw_ts, fallback_offset_sec=1800
        )
        entry = {
            "title": p_txt[:115] + ("..." if len(p_txt) > 115 else ""),
            "url": p_url,
            "raw_snippet": p_txt,
            "source_name": source_badge,
            "platform": "فيسبوك",
            "pub_date": pub_str,
            "pub_timestamp": pub_ts,
            "image_url": info["image"] or page_avatar,
        }
        if t_info:
          _tag_custom_target_item(entry, t_info, source_badge)
        seen_u.add(p_url)
        posts.append(entry)
    except Exception:
      pass

  # 2) مسح احتياطي مرن يدعم الكائنات المتداخلة داخل "message" (مثل ranges/entity) في النصوص الخام
  unescaped = raw_html.replace("\\/", "/")
  for m_msg in re.finditer(
      r'"(?:message|savable_description)"\s*:\s*\{[\s\S]{0,2500}?"text"\s*:\s*"((?:[^"\\]|\\.){15,})"',
      raw_html,
  ):
    msg_txt = _strip_fb_sidebar_noise(decode_js_escaped_text(m_msg.group(1)))
    if not msg_txt or len(msg_txt) < 15:
      continue
    start_pos = max(0, m_msg.start() - 4000)
    end_pos = min(len(raw_html), m_msg.end() + 5000)
    window = raw_html[start_pos:end_pos].replace("\\/", "/")

    post_u = ""
    for u_pat in [
        r'"(?:permalink_url|wwwURL|url)"\s*:\s*"(https://www\.facebook\.com/[^"]+?/(?:posts|videos|photos|reel)/[^"]+)"',
        r'"(?:permalink_url|wwwURL|url)"\s*:\s*"(https://www\.facebook\.com/(?:permalink\.php|story\.php|reel/|watch/\?v=)[^"]+)"',
        r'(https://www\.facebook\.com/[^"\s<>\\]+/posts/pfbid[A-Za-z0-9]+)',
    ]:
      m_u = re.search(u_pat, window)
      if m_u:
        cand_u = clean_social_post_url(decode_js_escaped_text(m_u.group(1)))
        if is_direct_social_post_url(cand_u, "فيسبوك") and _is_fb_post_owned_by_target(
            cand_u, handle=handle, page_id=page_id, page_official_name=page_official_name
        ):
          post_u = cand_u
          break

    if not post_u:
      m_fid = re.search(
          r'(?:"(?:post_id|top_level_post_id|story_fbid)"\s*:\s*"|(pfbid[A-Za-z0-9]{16,}))(pfbid[A-Za-z0-9]+|\d{11,})?',
          window,
      )
      if m_fid:
        fid = (m_fid.group(1) or m_fid.group(2) or "").strip()
        if fid and len(fid) >= 10:
          if handle and not handle.startswith("fb_") and not handle.isdigit():
            post_u = f"https://www.facebook.com/{handle}/posts/{fid}"
          elif page_id:
            post_u = f"https://www.facebook.com/permalink.php?story_fbid={fid}&id={page_id}"

    if not post_u or post_u in seen_u:
      continue
    if not is_strictly_judicial_and_clean(
        msg_txt, msg_txt, post_u, t_kw, is_target=bool(t_info)
    ):
      continue

    m_ctime = re.search(r'"(?:creation_time|publish_time)"\s*:\s*(\d{10})', window)
    raw_ts_str = m_ctime.group(1) if m_ctime else ""

    post_img = page_avatar
    m_img = re.search(r'"uri"\s*:\s*"(https://scontent[^"]+)"', window)
    if m_img:
      cand_img = decode_js_escaped_text(m_img.group(1))
      if "p50x50" not in cand_img and "s50x50" not in cand_img:
        post_img = cand_img

    pub_str, pub_ts = extract_date_from_url_or_text(
        post_u, msg_txt, raw_ts_str, fallback_offset_sec=1800
    )
    entry = {
        "title": msg_txt[:115] + ("..." if len(msg_txt) > 115 else ""),
        "url": post_u,
        "raw_snippet": msg_txt,
        "source_name": source_badge,
        "platform": "فيسبوك",
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": post_img,
    }
    if t_info:
      _tag_custom_target_item(entry, t_info, source_badge)
    seen_u.add(post_u)
    posts.append(entry)

  return posts


def _extract_facebook_posts_from_raw_html(
    raw_html: str,
    canonical_fb_url: str,
    handle: str,
    page_id: str,
    t_info: dict,
    source_badge: str,
    page_avatar: str,
    t_kw: str,
    page_official_name: str = "",
) -> list:
  """استخراج روابط المنشورات المباشرة (pfbid, story_fbid, posts, videos, reel) المضمنة في كود صفحة فيسبوك."""
  if not raw_html:
    return []

  extracted_posts = _extract_comet_relay_posts_from_html(
      raw_html,
      handle,
      page_id,
      page_official_name,
      t_info,
      source_badge,
      page_avatar,
      t_kw,
  )
  seen_cand = {clean_social_post_url(p["url"]) for p in extracted_posts}

  discovered_links = []
  unescaped_html = raw_html.replace("\\/", "/")

  patterns = [
      r'https?://(?:www\.|m\.|web\.)?facebook\.com/[^"\'\s<>\\]+/(?:posts|videos|photos)/[^"\'\s<>\\]+',
      r'https?://(?:www\.|m\.|web\.)?facebook\.com/(?:permalink\.php|story\.php|photo\.php|photo/|watch/|reel/|share/[pvr]/)[^"\'\s<>\\]+',
      r'href=["\'](/(?:[^"\'\s<>]+/(?:posts|videos|photos)/[^"\'\s<>]+|(?:permalink\.php|story\.php|photo\.php|photo/|watch/|reel/|share/[pvr]/)[^"\'\s<>]+))["\']',
  ]
  for pat in patterns:
    for m in re.finditer(pat, unescaped_html, re.IGNORECASE):
      raw_cand = m.group(1) if m.lastindex else m.group(0)
      clean_u = clean_social_post_url(raw_cand)
      if (
          clean_u
          and clean_u not in seen_cand
          and is_direct_social_post_url(clean_u, "فيسبوك")
          and _is_fb_post_owned_by_target(clean_u, handle=handle, page_id=page_id, page_official_name=page_official_name)
      ):
        seen_cand.add(clean_u)
        discovered_links.append(clean_u)

  # استخراج أي معرف pfbid0 مباشر داخل الصفحة وبناء رابط المنشور منه
  for m_pfb in re.finditer(r"\b(pfbid0[A-Za-z0-9]{15,})\b", unescaped_html):
    pfb_id = m_pfb.group(1)
    if handle and not handle.startswith("fb_") and not handle.isdigit():
      cand_u = f"https://www.facebook.com/{handle}/posts/{pfb_id}"
    elif page_id:
      cand_u = f"https://www.facebook.com/permalink.php?story_fbid={pfb_id}&id={page_id}"
    else:
      continue
    clean_u = clean_social_post_url(cand_u)
    if clean_u not in seen_cand:
      seen_cand.add(clean_u)
      discovered_links.append(clean_u)

  for m_fbid in re.finditer(
      r'"(?:story_fbid|top_level_post_id|post_id)"\s*:\s*"(pfbid[A-Za-z0-9]+|\d{11,})"',
      unescaped_html,
  ):
    fid = m_fbid.group(1).strip()
    if handle and not handle.startswith("fb_") and not handle.isdigit():
      cand_u = f"https://www.facebook.com/{handle}/posts/{fid}"
    elif page_id:
      cand_u = f"https://www.facebook.com/permalink.php?story_fbid={fid}&id={page_id}"
    else:
      continue
    clean_u = clean_social_post_url(cand_u)
    if clean_u not in seen_cand and is_direct_social_post_url(clean_u, "فيسبوك"):
      seen_cand.add(clean_u)
      discovered_links.append(clean_u)

  for idx, post_u in enumerate(discovered_links[:10]):
    if is_stop_requested():
      break
    is_valid, final_text, post_img, resolved_u = _verify_and_enrich_fb_post_url(
        post_u,
        page_avatar=page_avatar,
        handle=handle,
        page_id=page_id,
        page_official_name=page_official_name,
    )
    if not is_valid or not final_text or len(final_text) < 15:
      continue
    if not is_strictly_judicial_and_clean(
        final_text, final_text, resolved_u, t_kw, is_target=bool(t_info)
    ):
      continue

    pub_str, pub_ts = extract_date_from_url_or_text(
        resolved_u, final_text, "", fallback_offset_sec=1800 + (idx * 600)
    )
    entry = {
        "title": final_text[:115] + ("..." if len(final_text) > 115 else ""),
        "url": resolved_u,
        "raw_snippet": final_text,
        "source_name": source_badge,
        "platform": "فيسبوك",
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": post_img,
    }
    if t_info:
      _tag_custom_target_item(entry, t_info, source_badge)
    extracted_posts.append(entry)

  return extracted_posts


def resolve_direct_facebook_post_url(
    snippet_text: str,
    title_text: str,
    handle: str = "",
    page_official_name: str = "",
    page_id: str = "",
) -> str:
  """البحث عن الرابط المباشر الحقيقي للمنشور والتأكد الصارم من ملكيته للصفحة المخصصة حصراً."""
  clean_snip = clean_display_text(snippet_text or title_text)
  if page_official_name:
    clean_snip = clean_snip.replace(page_official_name, "").strip(" -–—:|•.")

  if re.search(
      r"(?:يتابعها|تسجيل إعجاب|يتحدث عن هذا|likes\s*·|talking about this)",
      clean_snip,
      re.IGNORECASE,
  ) and len(clean_snip) < 110:
    return ""

  words = [
      w
      for w in re.findall(r"[\u0600-\u06FFa-zA-Z0-9]{2,}", clean_snip)
      if w.lower() not in {"facebook", "فيسبوك", "فايسبوك", "منشور", "صفحة"}
  ]
  if len(words) < 4:
    return ""

  quote_phrase = " ".join(words[:7])
  owner_tok = (
      handle
      if (handle and not handle.startswith("fb_"))
      else page_official_name
  )
  sq = f'site:facebook.com "{owner_tok}" "{quote_phrase}"'.strip()

  for item_res in _multi_engine_web_search(sq, platform="فيسبوك", max_results=6):
    cand_u = clean_social_post_url(item_res.get("url", ""))
    if is_direct_social_post_url(cand_u, "فيسبوك") and _is_fb_post_owned_by_target(
        cand_u, handle=handle, page_id=page_id
    ):
      return cand_u

  return ""


def _clean_social_page_title(raw_title: str) -> str:
  """تنظيف اسم الصفحة الرسمي المستخرج من og:title من اللواحق مثل | Facebook أو | Rabat أو - الصفحة الرئيسية."""
  t = clean_display_text(raw_title)
  if not t:
    return ""
  t = re.sub(
      r"\s*[-|•–—]\s*(?:Facebook|فيسبوك|فايسبوك|X|Twitter|TikTok|Instagram|LinkedIn|YouTube).*$",
      "",
      t,
      flags=re.IGNORECASE,
  ).strip()
  t = re.sub(
      r"\s+on\s+(?:Facebook|Reels|X|Twitter).*$", "", t, flags=re.IGNORECASE
  ).strip()
  if "|" in t:
    parts_pipe = [p.strip() for p in t.split("|") if p.strip()]
    if parts_pipe:
      t = parts_pipe[0]
  t = re.sub(
      r"\s*[-–—]\s*(?:الصفحة الرسمية|الصفحة الرئيسية|Home|Official Page|Officiel)\s*$",
      "",
      t,
      flags=re.IGNORECASE,
  ).strip()
  return t


def _scrape_social_custom_target(
    t_info: dict,
    t_kw: str,
    when_tag: str,
    ddg_tl: str,
    max_age_sec: int,
    seen_urls: set,
) -> list:
  results = []
  all_target_posts = []
  seen_target_urls = set()
  raw_u = t_info["raw_url"]
  domain = t_info["domain"] or "facebook.com"
  platform = t_info["platform"] if t_info["platform"] != "شامل" else "فيسبوك"
  handle = t_info.get("handle", "")
  cid = t_info.get("channel_id", "")
  name_hint = t_info.get("official_name_hint", "")
  is_name_target = bool(t_info.get("is_name_target", False))
  disp = t_info.get("display_label", domain)
  now_ts = time.time()

  # إذا كان الرابط المضاف أصلاً رابط منشور مباشر بعينه، نرصده مباشرة
  if not is_name_target and is_direct_social_post_url(raw_u, platform):
    clean_direct_u = clean_social_post_url(raw_u)
    p_img, p_body, _ = scrape_article_page_content_and_image(clean_direct_u)
    if p_body:
      pub_str, pub_ts = extract_date_from_url_or_text(
          clean_direct_u, p_body, "", fallback_offset_sec=900
      )
      direct_entry = {
          "title": p_body[:110] + ("..." if len(p_body) > 110 else ""),
          "url": clean_direct_u,
          "raw_snippet": p_body,
          "source_name": f"🎯 {disp}",
          "platform": platform,
          "pub_date": pub_str,
          "pub_timestamp": pub_ts,
          "image_url": p_img,
      }
      _tag_custom_target_item(direct_entry, t_info, f"🎯 {disp}")
      return [direct_entry]

  # 1) جلب بيانات الصفحة العامة عبر ترويسة facebookexternalhit الموثوقة
  page_official_name = name_hint
  page_description = ""
  page_avatar = ""
  page_raw_html = ""
  canonical_url = raw_u
  req_hdrs = FB_CRAWLER_HEADERS if platform == "فيسبوك" else DEFAULT_HEADERS

  if not is_name_target:
    try:
      rp = None
      hdr_list = FB_PREVIEW_BOT_HEADERS if platform == "فيسبوك" else [DEFAULT_HEADERS]
      for cand_h in hdr_list:
        try:
          r_try = requests.get(raw_u, headers=cand_h, timeout=7, allow_redirects=True)
          if r_try.status_code == 200 and r_try.text:
            rp = r_try
            # إذا وجدنا وسم meta refresh في صفحة فيسبوك نفك التوجيه منه فوراً
            m_ref = re.search(
                r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+content=["\'][^"\']*url=([^"\'>\s]+)',
                r_try.text[:15000],
                re.IGNORECASE,
            )
            if m_ref:
              ref_u = clean_social_post_url(html.unescape(m_ref.group(1)))
              if ref_u and "login" not in ref_u.lower() and ref_u != raw_u:
                r_try2 = requests.get(ref_u, headers=cand_h, timeout=7, allow_redirects=True)
                if r_try2.status_code == 200 and r_try2.text:
                  rp = r_try2
                  canonical_url = ref_u
            if "og:title" in rp.text[:30000] and "log in" not in rp.text[:5000].lower():
              break
        except Exception:
          pass
      if rp.status_code == 200 and rp.text:
        page_raw_html = rp.text
        if rp.url:
          unwrapped_rp_u = clean_social_post_url(rp.url)
          if unwrapped_rp_u and "login" not in unwrapped_rp_u.lower():
            canonical_url = unwrapped_rp_u

        m_og_u = re.search(
            r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
            rp.text[:35000],
            re.IGNORECASE,
        )
        if m_og_u:
          cand_og = clean_social_post_url(m_og_u.group(1))
          if cand_og and "login" not in cand_og.lower():
            canonical_url = cand_og

        re_parsed = parse_custom_target_identity(canonical_url)
        if re_parsed.get("handle") and not re_parsed["handle"].isdigit():
          handle = re_parsed["handle"]
        if re_parsed.get("channel_id") and not cid:
          cid = re_parsed["channel_id"]
        if re_parsed.get("official_name_hint") and not page_official_name:
          page_official_name = re_parsed["official_name_hint"]

        if not cid and platform == "فيسبوك":
          for id_pat in [
              r"fb://(?:page|profile)/(\d{6,})",
              r'"(?:page_id|delegate_page_id|entity_id|userID)"\s*:\s*"(\d{6,})"',
          ]:
            m_pid = re.search(id_pat, rp.text[:60000])
            if m_pid:
              cid = m_pid.group(1)
              break

        for t_pat in [
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
            r"<title>(.*?)</title>",
        ]:
          m_og_t = re.search(t_pat, rp.text[:35000], re.IGNORECASE | re.DOTALL)
          if m_og_t:
            cleaned_t = _clean_social_page_title(m_og_t.group(1))
            if (
                len(cleaned_t) >= 2
                and not any(
                    w in cleaned_t.lower()
                    for w in [
                        "log in",
                        "login",
                        "تسجيل الدخول",
                        "قم بتسجيل الدخول",
                        "not found",
                        "غير متوفر",
                    ]
                )
                and cleaned_t.lower() not in {"facebook", "فيسبوك", "فايسبوك"}
            ):
              page_official_name = cleaned_t
              break

        for d_pat in [
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        ]:
          m_og_d = re.search(d_pat, rp.text[:35000], re.IGNORECASE)
          if m_og_d:
            d_cand = clean_display_text(m_og_d.group(1))
            if len(d_cand) > 15:
              page_description = d_cand
              break

        for i_pat in [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        ]:
          m_og_img = re.search(i_pat, rp.text[:35000], re.IGNORECASE)
          if m_og_img:
            page_avatar = html.unescape(m_og_img.group(1).strip())
            break
    except Exception:
      pass

  source_badge = f"🎯 {page_official_name or handle or disp}"

  # 2) لصفحات فيسبوك: جلب المنشورات الحية غير المؤرشفة عبر أداة الخط الزمني (BigPipe) وعبر كود Comet Relay JSON المباشر
  if platform == "فيسبوك" and not is_name_target:
    fb_plugin_posts = _scrape_facebook_plugin_timeline(
        canonical_url,
        t_info,
        source_badge,
        page_avatar,
        t_kw,
        handle=handle,
        page_id=cid,
    )
    for p in fb_plugin_posts:
      u_p = clean_social_post_url(p["url"])
      if u_p not in seen_target_urls:
        seen_target_urls.add(u_p)
        all_target_posts.append(p)

    chrome_doc_headers = dict(DEFAULT_HEADERS)
    chrome_doc_headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    })
    applebot_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
            "Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ar-MA,ar;q=0.9,fr;q=0.8,en;q=0.7",
    }
    raw_html_candidates = [page_raw_html] if page_raw_html else []
    fb_candidate_urls = [canonical_url]
    if handle and not handle.startswith("fb_") and not handle.isdigit():
      for u_var in [
          f"https://www.facebook.com/{handle}",
          f"https://web.facebook.com/{handle}?_rdc=1&_rdr",
      ]:
        if u_var not in fb_candidate_urls:
          fb_candidate_urls.append(u_var)
    elif cid:
      u_cid_var = f"https://www.facebook.com/profile.php?id={cid}"
      if u_cid_var not in fb_candidate_urls:
        fb_candidate_urls.append(u_cid_var)

    for target_fb_u in fb_candidate_urls[:2]:
      if len(raw_html_candidates) >= 3:
        break
      for cand_hdr in (chrome_doc_headers, applebot_headers):
        try:
          rc = requests.get(
              target_fb_u,
              headers=cand_hdr,
              cookies={"locale": "ar_AR"},
              timeout=9,
          )
          if rc.status_code == 200 and rc.text and len(rc.text) > 18000:
            raw_html_candidates.append(rc.text)
            if "comet_sections" in rc.text or "pfbid" in rc.text or "creation_time" in rc.text:
              break
        except Exception:
          pass

    for html_blob in raw_html_candidates:
      if not html_blob:
        continue
      html_direct_posts = _extract_facebook_posts_from_raw_html(
          html_blob,
          canonical_url,
          handle,
          cid,
          t_info,
          source_badge,
          page_avatar,
          t_kw,
          page_official_name=page_official_name,
      )
      for p in html_direct_posts:
        u_p = clean_social_post_url(p["url"])
        if u_p not in seen_target_urls:
          seen_target_urls.add(u_p)
          all_target_posts.append(p)

  # 3) لمنصة إكس (X/Twitter): فحص نقطة Syndication الرسمية الخاصة بالحساب نفسه (تعمل بالوقت الفعلي دون انتظار الأرشفة)
  if platform == "إكس" and handle and not is_name_target:
    synd_url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{urllib.parse.quote(handle)}"
    try:
      rs = requests.get(synd_url, headers=DEFAULT_HEADERS, timeout=9)
      if rs.status_code == 200 and rs.text:
        m_next = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            rs.text,
            re.DOTALL,
        )
        if m_next:
          next_data = json.loads(m_next.group(1))
          entries = (
              next_data.get("props", {})
              .get("pageProps", {})
              .get("timeline", {})
              .get("entries", [])
          )
          for ent in entries[:20]:
            tweet = ent.get("content", {}).get("tweet", {})
            if not tweet:
              continue
            t_id = str(tweet.get("id_str") or "").strip()
            full_txt = clean_display_text(
                tweet.get("full_text") or tweet.get("text") or ""
            )
            created_raw = tweet.get("created_at") or ""
            if not t_id or not full_txt:
              continue
            t_link = f"https://x.com/{handle}/status/{t_id}"
            if not is_strictly_judicial_and_clean(
                full_txt, full_txt, t_link, t_kw, is_target=True
            ):
              continue
            pub_str, pub_ts = extract_date_from_url_or_text(
                t_link, full_txt, created_raw, fallback_offset_sec=3600
            )
            t_img = page_avatar
            media_list = tweet.get("entities", {}).get("media", [])
            if media_list and isinstance(media_list, list):
              t_img = media_list[0].get("media_url_https") or t_img
            entry = {
                "title": full_txt[:115] + ("..." if len(full_txt) > 115 else ""),
                "url": t_link,
                "raw_snippet": full_txt,
                "source_name": source_badge,
                "platform": "إكس",
                "pub_date": pub_str,
                "pub_timestamp": pub_ts,
                "image_url": t_img,
            }
            _tag_custom_target_item(entry, t_info, source_badge)
            seen_target_urls.add(t_link)
            all_target_posts.append(entry)
    except Exception:
      pass

  # 3-ب) إذا حجب فيسبوك صفحة الهدف على خادم السحابة ولم نستخرج الاسم الرسمي للصفحة بعد، نستخرجه من نتائج البحث عن الرابط
  if platform == "فيسبوك" and not page_official_name and (handle or cid):
    probe_ident = handle if (handle and not handle.startswith("fb_")) else cid
    for p_res in _multi_engine_web_search(f'site:facebook.com "{probe_ident}"', platform="فيسبوك", max_results=5):
      cand_t = _clean_social_page_title(p_res.get("title", ""))
      if (
          cand_t
          and len(cand_t) >= 3
          and cand_t.lower() not in {"facebook", "فيسبوك", "فايسبوك", "log in", "login"}
      ):
        page_official_name = cand_t
        source_badge = f"🎯 {page_official_name}"
        break

  # 4) مسح شامل بالمعرف والاسم الرسمي معاً عبر عدة صيغ استعلام نظيفة متوافقة مع Bing وYahoo وDuckDuckGo
  target_queries = []
  if platform == "فيسبوك":
    if handle and not handle.startswith("fb_") and not handle.isdigit():
      target_queries.append(f'site:facebook.com "{handle}" {t_kw}'.strip())
      target_queries.append(f'"facebook.com/{handle}" {t_kw}'.strip())
      target_queries.append(f'site:facebook.com/{handle} {t_kw}'.strip())
    if page_official_name:
      target_queries.append(
          f'site:facebook.com "{page_official_name}" {t_kw}'.strip()
      )
      target_queries.append(
          f'facebook.com "{page_official_name}" {t_kw}'.strip()
      )
    if cid:
      target_queries.append(f'site:facebook.com "{cid}" {t_kw}'.strip())
      target_queries.append(f'facebook.com "{cid}" {t_kw}'.strip())
  else:
    if handle and not handle.startswith("fb_"):
      target_queries.append(f'site:{domain} "{handle}" {t_kw}'.strip())
      if platform == "إكس":
        target_queries.append(f'site:twitter.com "{handle}" {t_kw}'.strip())
    if page_official_name:
      target_queries.append(f'site:{domain} "{page_official_name}" {t_kw}'.strip())

  page_level_fallback_candidates = []

  for tq in target_queries[:6]:
    if is_stop_requested():
      break
    for entry in _multi_engine_web_search(
        tq, platform=platform, default_source=source_badge, max_results=18
    ):
      raw_entry_u = clean_social_post_url(entry.get("url", ""))
      if not raw_entry_u or raw_entry_u in seen_target_urls:
        continue

      entry["raw_snippet"] = _strip_fb_sidebar_noise(entry.get("raw_snippet", ""))
      entry["title"] = _strip_fb_sidebar_noise(entry.get("title", ""))

      if not is_direct_social_post_url(raw_entry_u, platform):
        if platform == "فيسبوك":
          resolved_u = resolve_direct_facebook_post_url(
              entry.get("raw_snippet", ""),
              entry.get("title", ""),
              handle=handle,
              page_official_name=page_official_name,
              page_id=cid,
          )
          if resolved_u and is_direct_social_post_url(resolved_u, "فيسبوك"):
            raw_entry_u = resolved_u
          else:
            # نحتفظ بالمنشورات المقتطفة من الخط الزمني للصفحة نفسها كخيار احتياطي إذا أخفى فيسبوك روابط pfbid الفردية عن محركات البحث
            u_low_check = raw_entry_u.lower()
            belongs_to_page_path = bool(
                (handle and not handle.startswith("fb_") and handle.lower() in u_low_check)
                or (cid and cid in u_low_check)
                or (page_official_name and normalize_arabic_for_dedup(page_official_name) in normalize_arabic_for_dedup(f"{entry.get('title', '')} {entry.get('raw_snippet', '')}"))
            )
            snip_cand = clean_display_text(entry.get("raw_snippet", ""))
            # إزالة ديباجة عدد المتابعين والإعجابات إن وجدت في بداية المقتطف
            snip_cand = re.sub(
                r"^.*?(?:talking about this|يتحدث عن هذا|تسجيل إعجاب|likes?\s*·)[^.]*[.·•-]?\s*",
                "",
                snip_cand,
                flags=re.IGNORECASE,
            ).strip()
            if belongs_to_page_path and len(snip_cand) >= 28:
              page_level_fallback_candidates.append((entry, snip_cand))
            continue
        else:
          continue

      if (
          platform == "إكس"
          and handle
          and not is_name_target
          and f"/{handle.lower()}/status/" not in raw_entry_u.lower()
      ):
        continue

      if raw_entry_u in seen_target_urls:
        continue

      if platform == "فيسبوك":
        is_ok, og_body, og_img, final_u = _verify_and_enrich_fb_post_url(
            raw_entry_u,
            page_avatar=page_avatar,
            handle=handle,
            page_id=cid,
            page_official_name=page_official_name,
        )
        if not is_ok:
          continue
        if og_body and len(og_body) >= 12:
          entry["raw_snippet"] = og_body
          entry["title"] = og_body[:115] + (
              "..." if len(og_body) > 115 else ""
          )
        else:
          # إذا واجه السيرفر جدار تسجيل الدخول في فيسبوك، ننظف عنوان البحث ونستخدم المقتطف المستخرج من محرك البحث
          cleaned_search_t = _clean_social_page_title(entry.get("title", ""))
          if entry["raw_snippet"] and len(entry["raw_snippet"]) >= 15:
            if not cleaned_search_t or len(cleaned_search_t) < 15 or cleaned_search_t == page_official_name:
              entry["title"] = entry["raw_snippet"][:115] + ("..." if len(entry["raw_snippet"]) > 115 else "")
            else:
              entry["title"] = cleaned_search_t
          elif cleaned_search_t and len(cleaned_search_t) >= 12:
            entry["title"] = cleaned_search_t
            entry["raw_snippet"] = cleaned_search_t
          else:
            continue
        if og_img:
          entry["image_url"] = og_img
        raw_entry_u = final_u

      entry["url"] = raw_entry_u
      if not is_strictly_judicial_and_clean(
          entry["title"],
          entry["raw_snippet"],
          entry["url"],
          t_kw,
          is_target=True,
      ):
        continue
      if not entry.get("image_url") and page_avatar:
        entry["image_url"] = page_avatar

      pub_str, pub_ts = extract_date_from_url_or_text(
          entry["url"],
          entry["raw_snippet"],
          entry.get("pub_date", ""),
          fallback_offset_sec=1800,
      )
      entry["pub_date"] = pub_str
      entry["pub_timestamp"] = pub_ts

      seen_target_urls.add(raw_entry_u)
      _tag_custom_target_item(entry, t_info, source_badge)
      all_target_posts.append(entry)

  # 5) إذا حجب فيسبوك ومحركات البحث روابط pfbid المباشرة على خادم السحابة، نفحص خلاصات الأخبار الحية المقيدة حصرياً باسم الصفحة أو معرفها لاستخراج المنشورات والتصريحات الصادرة عنها
  if not all_target_posts and (page_official_name or (handle and not handle.startswith("fb_"))):
    ident_name = page_official_name or handle
    gnews_target_q = f'"{ident_name}" {t_kw} when:{when_tag}'.strip()
    gnews_t_url = (
        "https://news.google.com/rss/search?q="
        f"{urllib.parse.quote(gnews_target_q)}&hl=ar&gl=MA&ceid=MA:ar"
    )
    try:
      r_gt = requests.get(gnews_t_url, headers=DEFAULT_HEADERS, timeout=8)
      if r_gt.status_code == 200:
        for g_ent in parse_rss_xml(
            r_gt.content,
            platform,
            default_source=source_badge,
            fallback_offset=1800,
            max_age_sec=0,
        ):
          comb_g = normalize_arabic_for_dedup(f"{g_ent.get('title', '')} {g_ent.get('raw_snippet', '')}")
          ident_norm = normalize_arabic_for_dedup(ident_name)
          if ident_norm and len(ident_norm) >= 4 and ident_norm not in comb_g:
            continue
          if not is_strictly_judicial_and_clean(
              g_ent["title"], g_ent["raw_snippet"], g_ent["url"], t_kw, is_target=True
          ):
            continue
          if not g_ent.get("image_url") and page_avatar:
            g_ent["image_url"] = page_avatar
          _tag_custom_target_item(g_ent, t_info, source_badge)
          all_target_posts.append(g_ent)
    except Exception:
      pass

  all_target_posts.sort(
      key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
  )

  in_window = [
      e
      for e in all_target_posts
      if max_age_sec <= 0
      or (now_ts - float(e.get("pub_timestamp", 0))) <= max_age_sec
  ]
  chosen_list = in_window if in_window else all_target_posts[:12]
  for entry in chosen_list:
    if entry["url"] not in seen_urls:
      seen_urls.add(entry["url"])
      results.append(entry)

  return results


def _scrape_name_based_custom_target(
    t_info: dict,
    t_kw: str,
    when_tag: str,
    ddg_tl: str,
    max_age_sec: int,
    seen_urls: set,
) -> list:
  """رصد مخصص دقيق عند إدخال اسم القناة أو الصفحة (يجلب حصرياً فيديوهات القناة على يوتيوب ومنشورات الصفحة على فيسبوك الموثقة الملكية)."""
  results = []
  name_q = t_info.get("official_name_hint") or t_info.get("display_label", "")
  if not name_q:
    return results

  yt_t_info = dict(t_info)
  yt_t_info["platform"] = "يوتيوب"
  yt_items = _scrape_youtube_custom_channel(
      yt_t_info, t_kw, max_age_sec, seen_urls
  )
  results.extend(yt_items)

  fb_t_info = dict(t_info)
  fb_t_info["platform"] = "فيسبوك"
  fb_t_info["domain"] = "facebook.com"
  fb_items = _scrape_social_custom_target(
      fb_t_info, t_kw, when_tag, ddg_tl, max_age_sec, seen_urls
  )
  results.extend(fb_items)

  results.sort(key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True)
  return results


def scrape_custom_targets(
    targets: list,
    global_kw: str = "",
    search_period: str = "آخر 7 أيام",
    progress_cb=None,
):
  items = []
  seen_urls = set()
  valid_targets = [t for t in targets if t.get("url", "").strip()]
  if not valid_targets:
    return items

  p_cfg = get_period_config(search_period)
  when_tag = p_cfg["gnews"]
  ddg_tl = p_cfg["ddg"]
  max_age = p_cfg["sec"]

  for idx, target in enumerate(valid_targets):
    if is_stop_requested():
      break
    t_url = target["url"].strip()
    t_kw = target.get("keyword", "").strip()
    t_info = parse_custom_target_identity(t_url)
    if not t_info:
      continue

    if progress_cb:
      progress_cb(
          (idx + 1) / max(1, len(valid_targets)),
          f"رصد المصدر المخصص: {t_info['display_label']}...",
      )

    platform = t_info["platform"]
    if t_info.get("is_name_target") and platform == "شامل":
      items.extend(
          _scrape_name_based_custom_target(
              t_info, t_kw, when_tag, ddg_tl, max_age, seen_urls
          )
      )
    elif platform == "يوتيوب":
      items.extend(
          _scrape_youtube_custom_channel(t_info, t_kw, max_age, seen_urls)
      )
    elif platform == "الصحف":
      items.extend(
          _scrape_website_custom_target(
              t_info, t_kw, when_tag, max_age, seen_urls
          )
      )
    else:
      items.extend(
          _scrape_social_custom_target(
              t_info, t_kw, when_tag, ddg_tl, max_age, seen_urls
          )
      )

  return items


# =====================================================================
# 10. تلخيص المحتوى الفعلي عبر Gemini API (مع دعم تعدد النماذج واستخلاص متن الخبر)
# =====================================================================
def _call_gemini_rest_or_sdk(prompt: str, api_key: str) -> str:
  global _WORKING_GEMINI_MODEL
  models_to_try = (
      [_WORKING_GEMINI_MODEL]
      + [m for m in GEMINI_MODELS_FALLBACK if m != _WORKING_GEMINI_MODEL]
      if _WORKING_GEMINI_MODEL
      else list(GEMINI_MODELS_FALLBACK)
  )

  for model_id in models_to_try:
    if not model_id:
      continue
    try:
      endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
      resp = requests.post(
          endpoint,
          json={
              "contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0.25, "maxOutputTokens": 350},
          },
          timeout=10,
      )
      if resp.status_code == 200:
        data = resp.json()
        txt = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        if txt:
          _WORKING_GEMINI_MODEL = model_id
          return txt.strip()
    except Exception:
      pass

    if genai is not None:
      try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_id)
        r_sdk = model.generate_content(prompt)
        if r_sdk and r_sdk.text:
          _WORKING_GEMINI_MODEL = model_id
          return r_sdk.text.strip()
      except Exception:
        pass

  return ""


def analyze_with_gemini(item: dict, api_key: str):
  title = clean_display_text(item.get("title", ""))
  snippet = clean_display_text(item.get("raw_snippet", "")) or title
  platform = item.get("platform", "الصحف")
  source_name = item.get("source_name", platform)

  fallback_summary = build_extractive_arabic_summary(
      title, snippet, platform, source_name
  )
  default_result = {
      "summary": fallback_summary,
      "sentiment": "محايد",
      "category": "شؤون قضائية",
      "relevance_score": 88,
  }

  if not api_key or not str(api_key).strip():
    return default_result

  prompt = (
      "أنت محلل إعلامي قضائي خبير بالمجلس الأعلى للسلطة القضائية بالمغرب.\n"
      "قم بقراءة عنوان وتفاصيل الخبر أو المنشور التالي، واكتب ملخصاً إخبارياً دقيقاً ومفصلاً "
      "في جملتين إلى ثلاث جمل بالعربية الفصحى يشرح الوقائع والتفاصيل والقرارات القضائية أو القانونية الواردة فيه.\n"
      "تحذير صارم: يُمنع منعاً باتاً إعادة كتابة العنوان نفسه كملخص أو الاكتفاء بعبارة يتناول موضوع كذا، بل لخّص المضمون والوقائع مباشرة.\n"
      "أرجع النتيجة بصيغة JSON فقط بالمفاتيح التالية:\n"
      '{"summary": "الملخص التفصيلي للوقائع هنا...", '
      '"sentiment": "إيجابي أو محايد أو سلبي", '
      '"category": "بلاغ رسمي أو محاكم وقضايا أو شؤون قضائية أو رأي ومتابعات", '
      '"relevance_score": 92}\n\n'
      f"المنصة والمصدر: {platform} - {source_name}\n"
      f"عنوان الخبر: {title}\n"
      f"متن وتفاصيل الخبر: {snippet[:1800]}"
  )

  txt = _call_gemini_rest_or_sdk(prompt, str(api_key).strip())
  if txt:
    try:
      m = re.search(r"\{.*\}", txt, re.DOTALL)
      if m:
        parsed = json.loads(m.group(0))
        ai_sum = clean_display_text(parsed.get("summary"))
        if ai_sum and not is_summary_just_title(title, ai_sum):
          return {
              "summary": ai_sum,
              "sentiment": (
                  clean_display_text(parsed.get("sentiment")) or "محايد"
              ),
              "category": (
                  clean_display_text(parsed.get("category")) or "شؤون قضائية"
              ),
              "relevance_score": int(parsed.get("relevance_score", 90)),
          }
      else:
        plain_ai = clean_display_text(txt)
        if len(plain_ai) > 40 and not is_summary_just_title(title, plain_ai):
          default_result["summary"] = plain_ai
    except Exception:
      pass

  return default_result


def send_telegram_alert(item: dict, cfg: dict) -> bool:
  """إرسال إشعار تلغرام مرة واحدة فقط لكل خبر جديد بعد التحقق الصارم من سجل الإرسال الدائم."""
  token = (cfg.get("telegram_bot_token") or DEFAULT_TG_TOKEN).strip()
  chat_id = (cfg.get("telegram_chat_id") or DEFAULT_TG_CHAT_ID).strip()
  if not token or not chat_id:
    return False

  item_keys = compute_article_dedup_keys(item.get("title", ""), item.get("url", ""))
  lock = get_db_lock()
  with lock:
    ledger = load_telegram_sent_ledger()
    if int(item.get("telegram_sent", 0)) == 1 or (item_keys & ledger):
      return False
    # نحجز بصمة الخبر فوراً في السجل قبل الإرسال لمنع أي خيط متزامن من إرساله مرة ثانية
    ledger.update(item_keys)
    save_telegram_sent_ledger(ledger)

  platform_icons = {
      "الصحف": "📰",
      "فيسبوك": "🟦",
      "إكس": "⬛",
      "يوتيوب": "🟥",
      "أخرى": "🟪",
  }
  icon = platform_icons.get(item.get("platform", "الصحف"), "📡")
  target_badge = "🎯 [رصد مخصص]\n" if item.get("is_custom_target") else ""
  monitored_dt = datetime.fromtimestamp(
      float(item.get("created_at") or time.time()), tz=timezone.utc
  ).strftime("%Y-%m-%d %H:%M")
  clean_u = clean_social_post_url(item.get("url", ""))
  msg = (
      f"⚖️ *المرصد الوطني للعدالة والقضاء*\n"
      f"{target_badge}"
      f"{icon} *المنصة:* {item.get('platform', 'الصحف')} | *المصدر:* {item.get('source_name', '')}\n"
      f"📅 *تاريخ النشر:* {item.get('pub_date', '')}\n"
      f"📡 *تاريخ الرصد:* {monitored_dt}\n"
      f"📌 *العنوان:* {item.get('title', '')}\n\n"
      f"📝 *الملخص:* {item.get('summary', '')}\n\n"
      f"🏷️ *التصنيف:* {item.get('category', '')}\n"
      f"🔗 [فتح المصدر الأصلي]({clean_u})"
  )
  try:
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        },
        timeout=8,
    )
    return resp.status_code == 200
  except Exception:
    return False


def upgrade_incomplete_existing_articles(cfg: dict, max_upgrades: int = 8):
  lock = get_db_lock()
  to_upgrade = []
  with lock:
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute(
          "SELECT id, title, summary, source_name, platform, url, raw_snippet, image_url "
          "FROM articles ORDER BY pub_timestamp DESC LIMIT 40"
      )
      for r in c.fetchall():
        d = dict(r)
        missing_img = not (d.get("image_url") or "").strip()
        bad_sum = is_summary_just_title(
            d.get("title", ""), d.get("summary", "")
        )
        if missing_img or bad_sum:
          to_upgrade.append(d)
          if len(to_upgrade) >= max_upgrades:
            break
      conn.close()
    except Exception:
      pass

  if not to_upgrade:
    return

  api_key = (cfg.get("gemini_api_key") or "").strip()
  upgraded_records = []
  for item in to_upgrade:
    if is_stop_requested():
      break
    enrich_item_content_and_image(item)
    ai_res = analyze_with_gemini(item, api_key)
    item["summary"] = clean_display_text(ai_res["summary"])
    upgraded_records.append(item)

  if upgraded_records:
    with lock:
      try:
        conn = _open_sqlite_conn()
        c = conn.cursor()
        for rec in upgraded_records:
          c.execute(
              "UPDATE articles SET summary = ?, image_url = ?, raw_snippet = ?, url = ? WHERE id = ?",
              (
                  rec["summary"],
                  rec.get("image_url", ""),
                  rec.get("raw_snippet", ""),
                  rec.get("url", ""),
                  rec["id"],
              ),
          )
        conn.commit()
        conn.close()
      except Exception:
        pass
    sync_db_to_json()


def quick_process_and_save(
    items: list, cfg: dict, is_target_run: bool = False
) -> int:
  if not items:
    upgrade_incomplete_existing_articles(cfg, max_upgrades=6)
    return 0

  existing_dedup_keys = set()
  non_target_url_map = {}
  current_targets = load_custom_targets()
  lock = get_db_lock()
  with lock:
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      c = conn.cursor()
      c.execute("SELECT id, url, title, platform, is_custom_target FROM articles")
      for r_id, r_url, r_title, r_plat, r_tgt in c.fetchall():
        base_keys = compute_article_dedup_keys(r_title or "", r_url or "")
        plat_scope = r_plat or "الصحف"
        tgt_scope = int(r_tgt or 0)
        for bk in base_keys:
          existing_dedup_keys.add(f"{plat_scope}::{tgt_scope}::{bk}")
          if bk.startswith("raw_u:") or bk.startswith("pid:"):
            existing_dedup_keys.add(f"global::{tgt_scope}::{bk}")
            if tgt_scope == 0:
              non_target_url_map[bk] = r_id
      conn.close()
    except Exception:
      pass

  kw_filter = cfg.get("keywords_input", "")
  candidates = []
  seen_batch_keys = set()
  for it in sorted(
      items, key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
  ):
    u = (it.get("url") or "").strip()
    t = clean_display_text(it.get("title") or "")
    s_raw = clean_display_text(it.get("raw_snippet") or "")
    is_tgt = bool(is_target_run or it.get("is_custom_target"))
    if not u or not t:
      continue
    if not is_strictly_judicial_and_clean(
        t, s_raw, u, kw_filter if not is_tgt else "", is_target=is_tgt
    ):
      continue
    if is_tgt and not belongs_to_any_custom_target(it, current_targets):
      continue

    p_scope = it.get("platform", "الصحف")
    t_scope = 1 if is_tgt else 0
    base_pre_keys = compute_article_dedup_keys(t, u)
    # إذا كان الرصد مخصصاً وكان المنشور موجوداً مسبقاً كمنشور عام غير مخصص، نقوم بترقيته ليظهر في تبويب المخصص أيضاً
    if is_tgt:
      for bpk in base_pre_keys:
        if bpk in non_target_url_map:
          with lock:
            try:
              conn_up = _open_sqlite_conn()
              conn_up.execute(
                  "UPDATE articles SET is_custom_target = 1, url = ?, source_name = ? WHERE id = ?",
                  (u, clean_display_text(it.get("source_name") or p_scope), non_target_url_map[bpk]),
              )
              conn_up.commit()
              conn_up.close()
            except Exception:
              pass
    pre_keys = {f"{p_scope}::{t_scope}::{k}" for k in base_pre_keys} | {
        f"global::{t_scope}::{k}" for k in base_pre_keys if k.startswith("raw_u:") or k.startswith("pid:")
    }
    # الفحص الأول قبل فك الروابط: إذا كان الخبر مرصوداً سابقاً في نفس القسم نتخطاه فوراً ليبقى 24 ساعة من وقت رصده الأول ثم يحال للأرشيف
    if (pre_keys & existing_dedup_keys) or (pre_keys & seen_batch_keys):
      continue

    seen_batch_keys.update(pre_keys)
    it["title"] = t
    candidates.append(it)

  if not candidates:
    upgrade_incomplete_existing_articles(cfg, max_upgrades=6)
    return 0

  api_key = (cfg.get("gemini_api_key") or "").strip()
  prepared_rows = []
  post_enrich_seen_keys = set()
  ai_calls = 0
  enrichment_calls = 0

  for it in candidates:
    if is_stop_requested():
      break
    plat = it.get("platform", "الصحف")
    src = clean_display_text(it.get("source_name") or plat)

    if enrichment_calls < 14:
      enrichment_calls += 1
      enrich_item_content_and_image(it)

    # الفحص الثاني بعد فك روابط Google News وتحديث العنوان والرابط النهائي: يمنع دخول أي خبر مكرر بعد فك التوجيه
    t_scope_post = 1 if (is_target_run or it.get("is_custom_target")) else 0
    base_post_keys = compute_article_dedup_keys(it.get("title", ""), it.get("url", ""))
    post_keys = {f"{plat}::{t_scope_post}::{k}" for k in base_post_keys} | {
        f"global::{t_scope_post}::{k}" for k in base_post_keys if k.startswith("raw_u:") or k.startswith("pid:")
    }
    if (post_keys & existing_dedup_keys) or (post_keys & post_enrich_seen_keys):
      continue
    post_enrich_seen_keys.update(post_keys)

    raw_snip = clean_display_text(it.get("raw_snippet") or "")
    img_url = (it.get("image_url") or "").strip()

    if ai_calls < 12 and api_key:
      ai_res = analyze_with_gemini(it, api_key)
      ai_calls += 1
    else:
      ai_res = {
          "summary": build_extractive_arabic_summary(
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
        "url": (it.get("url") or "").strip(),
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "sentiment": clean_display_text(ai_res["sentiment"]),
        "category": clean_display_text(ai_res["category"]),
        "relevance_score": int(ai_res["relevance_score"]),
        "is_custom_target": (
            1 if (is_target_run or it.get("is_custom_target")) else 0
        ),
        "raw_snippet": raw_snip[:1200],
        "image_url": img_url,
        "created_at": time.time(),
        "telegram_sent": 0,
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
          base_rec_keys = compute_article_dedup_keys(rec["title"], rec["url"])
          rec_keys = {f"{rec['platform']}::{rec['is_custom_target']}::{k}" for k in base_rec_keys}
          if rec_keys & existing_dedup_keys:
            continue
          c.execute(
              """
                        INSERT OR IGNORE INTO articles (
                            title, summary, source_name, platform, url,
                            pub_date, pub_timestamp, sentiment, category,
                            relevance_score, is_custom_target, raw_snippet,
                            image_url, created_at, telegram_sent
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                  rec["image_url"],
                  rec["created_at"],
                  0,
              ),
          )
          if c.rowcount and c.rowcount > 0:
            existing_dedup_keys.update(rec_keys)
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

  upgrade_incomplete_existing_articles(cfg, max_upgrades=4)

  if added_items:
    for rec in added_items[:10]:
      sent_ok = send_telegram_alert(rec, cfg)
      rec["telegram_sent"] = 1
      # حتى لو تجاوز العدد 10 في دفعة واحدة، نسجل البقية في السجل حتى لا ترسل في الدورات التلقائية اللاحقة كأخبار قديمة
    with lock:
      ledger_now = load_telegram_sent_ledger()
      for rec in added_items:
        rec["telegram_sent"] = 1
        ledger_now.update(compute_article_dedup_keys(rec["title"], rec["url"]))
      save_telegram_sent_ledger(ledger_now)
      try:
        conn = _open_sqlite_conn()
        c = conn.cursor()
        c.executemany(
            "UPDATE articles SET telegram_sent = 1 WHERE url = ?",
            [(r["url"],) for r in added_items],
        )
        conn.commit()
        conn.close()
      except Exception:
        pass
    sync_db_to_json(extra_items=added_items)

  return len(added_items)


# =====================================================================
# 11. محرك الرصد الدوري الأوتوماتيكي (خلفية السيرفر + GitHub Actions)
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
    s_period = cfg.get("search_period", "آخر 7 أيام")

    m_state = load_monitor_state()
    m_state["last_auto_run"] = time.time()
    save_monitor_state(m_state)

    raw_items = []
    raw_items.extend(scrape_moroccan_press(kw, s_period))
    raw_items.extend(scrape_youtube_platform(kw, s_period))
    raw_items.extend(scrape_facebook_platform(kw, s_period))
    raw_items.extend(scrape_x_platform(kw, s_period))
    raw_items.extend(scrape_other_platforms(kw, s_period))

    added_general = quick_process_and_save(raw_items, cfg, is_target_run=False)

    added_targets = 0
    if targets:
      t_items = scrape_custom_targets(targets, kw, s_period)
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
# 12. تهيئة واجهة Streamlit والتصميم الزجاجي المتجاوب مع فرض صارم لاتجاه RTL
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

/* فرض الوضع الداكن ومنع الخلفية البيضاء الافتراضية لجميع أزرار Streamlit في كافة المتصفحات */
:root, html, body, .stApp {
    color-scheme: dark !important;
}

.stApp button[kind="secondary"],
.stApp button[kind="primary"],
.stApp [data-testid="stBaseButton-secondary"],
.stApp [data-testid="baseButton-secondary"],
.stApp [data-testid="stBaseButton-primary"],
.stApp [data-testid="baseButton-primary"],
div.stButton > button,
div[data-testid="stButton"] > button,
div.stDownloadButton > button,
div[data-testid="stFormSubmitButton"] > button {
    width: 100% !important;
    min-height: 42px !important;
    background: rgba(15, 23, 42, 0.78) !important;
    background-color: rgba(15, 23, 42, 0.78) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    color: #f8fafc !important;
    border: 1px solid rgba(148, 163, 184, 0.35) !important;
    border-radius: 12px !important;
    padding: 0.45rem 0.65rem !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
    font-size: 0.92rem !important;
    white-space: nowrap !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3) !important;
    transition: all 0.2s ease !important;
}

.stApp button *,
div.stButton > button *,
div[data-testid="stButton"] > button *,
div.stDownloadButton > button *,
div[data-testid="stFormSubmitButton"] > button * {
    color: #f8fafc !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
}

div.stButton > button:hover,
div[data-testid="stButton"] > button:hover,
div.stDownloadButton > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-2px) !important;
    border-color: #38bdf8 !important;
    box-shadow: 0 8px 22px rgba(56, 189, 248, 0.28) !important;
}

/* البطاقات الزجاجية الشفافة للرصد (Glassmorphic Monitoring Frames) */
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-marker)),
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scan-frame-marker) {
    border-radius: 18px !important;
    padding: 14px 16px 12px 16px !important;
    margin-bottom: 10px !important;
    backdrop-filter: blur(24px) saturate(170%) !important;
    -webkit-backdrop-filter: blur(24px) saturate(170%) !important;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.32), inset 0 1px 1px rgba(255, 255, 255, 0.22) !important;
    transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease !important;
}

div[data-testid="stVerticalBlock"]:has(.scan-frame-marker):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-marker)):hover,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scan-frame-marker):hover {
    transform: translateY(-3px) !important;
}

div[data-testid="stVerticalBlock"]:has(.scan-frame-all):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-all)) {
    background: linear-gradient(135deg, rgba(14, 165, 233, 0.20) 0%, rgba(15, 23, 42, 0.52) 100%) !important;
    border: 1px solid rgba(56, 189, 248, 0.48) !important;
}
div[data-testid="stVerticalBlock"]:has(.scan-frame-press):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-press)) {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.20) 0%, rgba(15, 23, 42, 0.52) 100%) !important;
    border: 1px solid rgba(52, 211, 153, 0.48) !important;
}
div[data-testid="stVerticalBlock"]:has(.scan-frame-fb):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-fb)) {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.22) 0%, rgba(15, 23, 42, 0.52) 100%) !important;
    border: 1px solid rgba(96, 165, 250, 0.48) !important;
}
div[data-testid="stVerticalBlock"]:has(.scan-frame-x):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-x)) {
    background: linear-gradient(135deg, rgba(148, 163, 184, 0.22) 0%, rgba(15, 23, 42, 0.56) 100%) !important;
    border: 1px solid rgba(203, 213, 225, 0.42) !important;
}
div[data-testid="stVerticalBlock"]:has(.scan-frame-yt):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-yt)) {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.22) 0%, rgba(15, 23, 42, 0.52) 100%) !important;
    border: 1px solid rgba(248, 113, 113, 0.48) !important;
}
div[data-testid="stVerticalBlock"]:has(.scan-frame-other):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-other)) {
    background: linear-gradient(135deg, rgba(168, 85, 247, 0.22) 0%, rgba(15, 23, 42, 0.52) 100%) !important;
    border: 1px solid rgba(192, 132, 252, 0.48) !important;
}
div[data-testid="stVerticalBlock"]:has(.scan-frame-target):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-target)) {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.24) 0%, rgba(15, 23, 42, 0.54) 100%) !important;
    border: 1px solid rgba(251, 191, 36, 0.52) !important;
}

/* ترويسة اسم المنصة داخل الإطار الزجاجي: عرض كامل وواضح بدون أي اقتطاع */
.scan-platform-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    direction: rtl !important;
    text-align: right !important;
    padding: 4px 2px 10px 2px;
    margin-bottom: 6px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
    width: 100%;
}

.scan-platform-right {
    display: flex;
    align-items: center;
    gap: 10px;
    direction: rtl !important;
    text-align: right !important;
    flex: 1 1 auto;
}

.scan-platform-icon {
    width: 40px;
    height: 40px;
    min-width: 40px;
    border-radius: 12px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    background: rgba(15, 23, 42, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.22);
    box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.18), 0 4px 10px rgba(0, 0, 0, 0.25);
}

.scan-platform-title {
    font-size: 1.04rem;
    font-weight: 900;
    color: #ffffff;
    line-height: 1.3;
    white-space: normal !important;
    overflow: visible !important;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.45);
}

.scan-platform-sub {
    font-size: 0.77rem;
    font-weight: 700;
    color: #e2e8f0;
    opacity: 0.92;
    white-space: normal !important;
    line-height: 1.25;
    margin-top: 2px;
}

.scan-platform-badge {
    font-size: 0.72rem;
    font-weight: 800;
    padding: 3px 9px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.12);
    border: 1px solid rgba(255, 255, 255, 0.22);
    color: #f8fafc;
    white-space: nowrap;
}

/* صف أزرار التشغيل (▶) والإيقاف (⏹) داخل الإطار الزجاجي */
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-marker)) div[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 8px !important;
}

div[data-testid="stVerticalBlock"]:has(.scan-frame-marker):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-marker)) div[data-testid="stHorizontalBlock"] > div[data-testid="column"],
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-marker)) div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    min-width: 0 !important;
    flex: 1 1 50% !important;
}

/* زر التشغيل الزجاجي (▶ تشغيل) — يستهدف جميع محددات Streamlit لضمان عدم ظهور أي خلفية بيضاء إطلاقاً */
[class*="st-key-start_scan_"] button,
div[data-testid="column"]:has(.media-play-marker) button,
div[data-testid="stColumn"]:has(.media-play-marker) button,
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) button[kind="primary"],
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) [data-testid="stBaseButton-primary"],
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) [data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.72) 0%, rgba(5, 150, 105, 0.88) 100%) !important;
    background-color: rgba(16, 185, 129, 0.8) !important;
    backdrop-filter: blur(14px) !important;
    -webkit-backdrop-filter: blur(14px) !important;
    border: 1.5px solid rgba(110, 231, 183, 0.75) !important;
    color: #ffffff !important;
    min-height: 42px !important;
    height: 42px !important;
    padding: 0 10px !important;
    border-radius: 12px !important;
    font-size: 0.94rem !important;
    font-weight: 900 !important;
    box-shadow: 0 4px 15px rgba(16, 185, 129, 0.32), inset 0 1px 0 rgba(255, 255, 255, 0.25) !important;
}

[class*="st-key-start_scan_"] button:hover,
div[data-testid="column"]:has(.media-play-marker) button:hover,
div[data-testid="stColumn"]:has(.media-play-marker) button:hover,
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) button[kind="primary"]:hover,
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) [data-testid="stBaseButton-primary"]:hover {
    background: linear-gradient(135deg, rgba(52, 211, 153, 0.88) 0%, rgba(4, 120, 87, 0.95) 100%) !important;
    border-color: #ffffff !important;
    box-shadow: 0 6px 20px rgba(16, 185, 129, 0.55) !important;
    transform: translateY(-1px) scale(1.02) !important;
}

/* زر الإيقاف الزجاجي (⏹ إيقاف) — يستهدف جميع محددات Streamlit لضمان عدم ظهور أي خلفية بيضاء إطلاقاً */
[class*="st-key-stop_scan_"] button,
div[data-testid="column"]:has(.media-stop-marker) button,
div[data-testid="stColumn"]:has(.media-stop-marker) button,
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) button[kind="secondary"],
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) [data-testid="stBaseButton-secondary"],
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) [data-testid="baseButton-secondary"] {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.68) 0%, rgba(153, 27, 27, 0.86) 100%) !important;
    background-color: rgba(220, 38, 38, 0.78) !important;
    backdrop-filter: blur(14px) !important;
    -webkit-backdrop-filter: blur(14px) !important;
    border: 1.5px solid rgba(252, 165, 165, 0.7) !important;
    color: #ffffff !important;
    min-height: 42px !important;
    height: 42px !important;
    padding: 0 10px !important;
    border-radius: 12px !important;
    font-size: 0.94rem !important;
    font-weight: 900 !important;
    box-shadow: 0 4px 15px rgba(239, 68, 68, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.22) !important;
}

[class*="st-key-stop_scan_"] button:hover,
div[data-testid="column"]:has(.media-stop-marker) button:hover,
div[data-testid="stColumn"]:has(.media-stop-marker) button:hover,
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) button[kind="secondary"]:hover,
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) [data-testid="stBaseButton-secondary"]:hover {
    background: linear-gradient(135deg, rgba(248, 113, 113, 0.88) 0%, rgba(185, 28, 28, 0.95) 100%) !important;
    border-color: #ffffff !important;
    box-shadow: 0 6px 20px rgba(239, 68, 68, 0.55) !important;
    transform: translateY(-1px) scale(1.02) !important;
}

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

.news-card {
    background: linear-gradient(145deg, rgba(15, 23, 42, 0.92) 0%, rgba(30, 41, 59, 0.74) 100%);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-right: 5px solid #38bdf8;
    border-radius: 16px;
    padding: clamp(14px, 2vw, 20px);
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
    border-color: rgba(56, 189, 248, 0.5);
}

.news-card.plat-press { border-right-color: #10b981; }
.news-card.plat-fb { border-right-color: #3b82f6; }
.news-card.plat-x { border-right-color: #cbd5e1; }
.news-card.plat-yt { border-right-color: #ef4444; }
.news-card.plat-other { border-right-color: #a855f7; }

.news-card-layout {
    display: flex !important;
    flex-direction: row !important;
    align-items: flex-start !important;
    justify-content: flex-start !important;
    gap: 18px !important;
    direction: rtl !important;
    text-align: right !important;
    width: 100% !important;
}

.news-thumb-box {
    width: 195px;
    min-width: 195px;
    height: 132px;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(148, 163, 184, 0.28);
    background: #090d16;
    flex-shrink: 0;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
}

.news-thumb-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}

.news-body-col {
    flex: 1 1 auto !important;
    min-width: 0 !important;
    direction: rtl !important;
    text-align: right !important;
}

.news-dates-row {
    display: flex !important;
    flex-wrap: wrap !important;
    align-items: center !important;
    justify-content: flex-start !important;
    gap: 8px !important;
    margin: 6px 0 10px 0 !important;
    direction: rtl !important;
    text-align: right !important;
}

.date-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(15, 23, 42, 0.88);
    border: 1px solid rgba(56, 189, 248, 0.32);
    color: #e2e8f0;
    padding: 3px 11px;
    border-radius: 999px;
    font-size: clamp(0.74rem, 1.2vw, 0.82rem);
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
    margin: 6px 0 6px 0;
    line-height: 1.55;
    direction: rtl !important;
    text-align: right !important;
}

.news-summary-box {
    background: rgba(9, 13, 22, 0.58);
    border-right: 3px solid rgba(56, 189, 248, 0.6);
    border-radius: 10px;
    padding: 9px 13px;
    margin-bottom: 10px;
    font-size: clamp(0.87rem, 1.45vw, 0.95rem);
    color: #cbd5e1;
    line-height: 1.72;
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
    padding: 5px 14px;
    border-radius: 10px;
    font-size: 0.83rem;
    font-weight: 800;
    direction: rtl !important;
}

.news-link:hover {
    background: rgba(56, 189, 248, 0.3);
}

/* تصميم زجاجي فاخر لقسم وشريط 🎯 الروابط والقنوات المخصصة (Expander) */
div[data-testid="stExpander"],
details[data-testid="stExpander"] {
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.78) 0%, rgba(30, 41, 59, 0.58) 100%) !important;
    backdrop-filter: blur(22px) saturate(165%) !important;
    -webkit-backdrop-filter: blur(22px) saturate(165%) !important;
    border: 1px solid rgba(251, 191, 36, 0.42) !important;
    border-radius: 18px !important;
    margin: 8px 0 14px 0 !important;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35), inset 0 1px 1px rgba(255, 255, 255, 0.16) !important;
    overflow: hidden !important;
}

div[data-testid="stExpander"] summary,
details[data-testid="stExpander"] > summary,
div[data-testid="stExpander"] [ data-testid="stExpanderHeader"] {
    background: linear-gradient(90deg, rgba(217, 119, 6, 0.22) 0%, rgba(15, 23, 42, 0.65) 100%) !important;
    padding: 12px 18px !important;
    border-radius: 17px !important;
    color: #fef3c7 !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 900 !important;
    font-size: 0.98rem !important;
    direction: rtl !important;
    text-align: right !important;
    transition: all 0.2s ease !important;
}

div[data-testid="stExpander"] summary:hover,
details[data-testid="stExpander"] > summary:hover {
    background: linear-gradient(90deg, rgba(245, 158, 11, 0.32) 0%, rgba(30, 41, 59, 0.78) 100%) !important;
    color: #ffffff !important;
}

div[data-testid="stExpander"] summary *,
details[data-testid="stExpander"] > summary * {
    color: #fde68a !important;
    font-weight: 900 !important;
    font-size: 0.96rem !important;
}

div[data-testid="stExpanderDetails"] {
    padding: 12px 16px 16px 16px !important;
    background: rgba(9, 13, 22, 0.42) !important;
    border-top: 1px solid rgba(251, 191, 36, 0.22) !important;
}

div[data-testid="stForm"] {
    background: rgba(15, 23, 42, 0.62) !important;
    border: 1px solid rgba(56, 189, 248, 0.28) !important;
    border-radius: 14px !important;
    padding: 12px 14px !important;
    margin-bottom: 10px !important;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
}

.target-glass-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.68) 0%, rgba(15, 23, 42, 0.82) 100%);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(148, 163, 184, 0.26);
    border-right: 4px solid #f59e0b;
    border-radius: 12px;
    padding: 8px 14px;
    margin-bottom: 6px;
    direction: rtl !important;
    text-align: right !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
}

.target-plat-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(245, 158, 11, 0.18);
    border: 1px solid rgba(251, 191, 36, 0.45);
    color: #fde68a;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 800;
    white-space: nowrap;
}

.target-url-pill {
    font-size: 0.84rem;
    color: #e2e8f0;
    direction: ltr;
    text-align: left;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 700;
    max-width: 460px;
}

/* تصميم زجاجي احترافي لشريط التبويبات وقائمة عرض النتائج حسب المنصة (st.tabs) */
div[data-baseweb="tab-list"] {
    gap: 8px !important;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.84) 0%, rgba(9, 13, 22, 0.92) 100%) !important;
    backdrop-filter: blur(22px) saturate(170%) !important;
    -webkit-backdrop-filter: blur(22px) saturate(170%) !important;
    padding: 8px 10px !important;
    border-radius: 16px !important;
    border: 1px solid rgba(56, 189, 248, 0.32) !important;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.42), inset 0 1px 1px rgba(255, 255, 255, 0.14) !important;
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
    scrollbar-width: thin;
    direction: rtl !important;
    margin-bottom: 12px !important;
}

div[data-baseweb="tab-highlight"],
div[data-baseweb="tab-border"] {
    display: none !important;
}

button[data-baseweb="tab"] {
    background: rgba(30, 41, 59, 0.52) !important;
    border: 1px solid rgba(148, 163, 184, 0.24) !important;
    color: #cbd5e1 !important;
    border-radius: 12px !important;
    padding: 9px 15px !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
    font-size: clamp(0.8rem, 1.35vw, 0.92rem) !important;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
    transition: all 0.22s ease !important;
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.22) !important;
}

button[data-baseweb="tab"]:hover {
    background: rgba(51, 65, 85, 0.72) !important;
    border-color: rgba(56, 189, 248, 0.55) !important;
    color: #ffffff !important;
    transform: translateY(-2px) !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, rgba(2, 132, 199, 0.88) 0%, rgba(37, 99, 235, 0.92) 100%) !important;
    border: 1.5px solid rgba(125, 211, 252, 0.9) !important;
    color: #ffffff !important;
    box-shadow: 0 6px 20px rgba(2, 132, 199, 0.48), inset 0 1px 1px rgba(255, 255, 255, 0.35) !important;
    transform: translateY(-1px) !important;
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
    .news-card-layout {
        flex-direction: column !important;
    }
    .news-thumb-box {
        width: 100% !important;
        height: 165px !important;
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
# 13. تحميل الإعدادات والبيانات
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
        purge_invalid_articles_from_db()
        st.success("تمت استعادة الأرشيف بنجاح")
        st.rerun()
    except Exception:
      st.error("ملف غير صالح")

# =====================================================================
# 14. الهيدر الرئيسي وشريط البحث المخصص وتحديد فترة البحث والروابط المخصصة
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

col_kw, col_period = st.columns([2.8, 1.2])
with col_kw:
  kw_input = st.text_input(
      "🔍 تخصيص بكلمات مفتاحية (اختياري)",
      value=cfg.get("keywords_input", ""),
      placeholder="🔍 اتركه فارغاً للرصد القضائي العام، أو أدخل كلمات مفتاحية مفصولة بفاصلة...",
      label_visibility="collapsed",
  )
  if kw_input != cfg.get("keywords_input", ""):
    cfg["keywords_input"] = kw_input
    save_credentials(cfg)

with col_period:
  period_options = list(SEARCH_PERIOD_MAP.keys())
  curr_period = cfg.get("search_period", "آخر 7 أيام")
  selected_period = st.selectbox(
      "⏱️ فترة البحث",
      options=period_options,
      index=period_options.index(curr_period)
      if curr_period in period_options
      else 2,
      label_visibility="collapsed",
  )
  if selected_period != cfg.get("search_period", ""):
    cfg["search_period"] = selected_period
    save_credentials(cfg)

with st.expander(
    f"🎯 إدارة الروابط والقنوات والصفحات المخصصة ({len(custom_targets)} مصدر مضاف)", expanded=False
):
  render_html(
      "<div style='font-size:0.84rem;color:#cbd5e1;margin-bottom:8px;direction:rtl;text-align:right;'>"
      "أضف رابط أي صفحة فيسبوك أو قناة يوتيوب أو حساب إكس أو موقع إخباري (أو اكتب اسم القناة/الصفحة مباشرة) لرصد أحدث منشوراتها وفيديوهاتها بدقة:"
      "</div>"
  )
  with st.form("add_custom_target_form", clear_on_submit=True):
    c_u, c_k, c_b = st.columns([2.6, 1.4, 0.9])
    with c_u:
      new_t_url = st.text_input(
          "الرابط",
          placeholder="🔗 رابط صفحة فيسبوك / قناة يوتيوب / حساب إكس أو اسم القناة/الصفحة...",
          label_visibility="collapsed",
      )
    with c_k:
      new_t_kw = st.text_input(
          "كلمة (اختياري)",
          placeholder="🔍 كلمة فلترة داخل الصفحة (اختياري)...",
          label_visibility="collapsed",
      )
    with c_b:
      add_t_btn = st.form_submit_button("➕ إضافة المصدر")
    if add_t_btn and new_t_url.strip():
      custom_targets.append(
          {"url": new_t_url.strip(), "keyword": new_t_kw.strip()}
      )
      save_custom_targets(custom_targets)
      st.rerun()

  plat_icon_map = {
      "يوتيوب": "🟥 قناة يوتيوب",
      "فيسبوك": "🟦 صفحة فيسبوك",
      "إكس": "⬛ حساب إكس",
      "الصحف": "📰 موقع إخباري",
      "أخرى": "🟪 منصة رقمية",
      "شامل": "🎯 اسم مخصص",
  }
  for idx, t_item in enumerate(list(custom_targets)):
    tc1, tc2 = st.columns([5.2, 0.9])
    t_parsed = parse_custom_target_identity(t_item.get("url", ""))
    p_badge = plat_icon_map.get(t_parsed.get("platform", "شامل"), "🎯 مصدر مخصص")
    disp_name = t_parsed.get("display_label") or t_item.get("url", "")
    kw_chip = (
        f"<span style='background:rgba(56,189,248,0.18);border:1px solid rgba(56,189,248,0.4);color:#7dd3fc;padding:2px 8px;border-radius:999px;font-size:0.73rem;font-weight:800;'>🔍 {html.escape(t_item['keyword'])}</span>"
        if t_item.get("keyword")
        else ""
    )
    with tc1:
      render_html(
          f"""
          <div class="target-glass-item" dir="rtl">
              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;direction:rtl;">
                  <span class="target-plat-chip">{p_badge}</span>
                  <span style="font-weight:900;color:#f8fafc;font-size:0.88rem;">{html.escape(disp_name)}</span>
                  {kw_chip}
              </div>
              <div class="target-url-pill" title="{html.escape(t_item['url'])}">🔗 {html.escape(t_item['url'])}</div>
          </div>
          """
      )
    with tc2:
      if st.button("🗑️ حذف", key=f"del_target_{idx}"):
        custom_targets.pop(idx)
        save_custom_targets(custom_targets)
        st.rerun()

# =====================================================================
# 15. لوحة بطاقات الرصد الزجاجية الشفافة (اسم المنصة كاملاً + زر التشغيل ▶ وزر الإيقاف ⏹)
# =====================================================================
SCAN_MODES = [
    ("all", "الرصد الشامل", "جميع المنصات والمصادر", "شامل", "🚀", "scan-frame-all"),
    ("press", "الصحف المغربية", "المواقع والجرائد الوطنية", "صحافة", "📰", "scan-frame-press"),
    ("fb", "منصة فيسبوك", "الصفحات والمنشورات العامة", "فيسبوك", "🟦", "scan-frame-fb"),
    ("x", "منصة إكس (X)", "التغريدات والحسابات", "إكس", "⬛", "scan-frame-x"),
    ("yt", "منصة يوتيوب", "القنوات والفيديوهات", "يوتيوب", "🟥", "scan-frame-yt"),
    ("other", "منصات أخرى", "تيك توك • إنستغرام • لينكدإن", "أخرى", "🟪", "scan-frame-other"),
    ("target", "الرصد المخصص", f"القنوات والصفحات المحددة ({len(custom_targets)})", "مخصص", "🎯", "scan-frame-target"),
]

triggered_mode = None

# توزيع البطاقات الزجاجية في شبكتين متناسقتين بمساحة رحبة تضمن ظهور اسم المنصة كاملاً وبوضوح تام
row1_modes = SCAN_MODES[:4]
row2_modes = SCAN_MODES[4:]

for row_modes in (row1_modes, row2_modes):
  row_cols = st.columns(len(row_modes))
  for col_idx, (mode_key, mode_title, mode_sub, mode_badge, mode_icon, frame_cls) in enumerate(row_modes):
    with row_cols[col_idx]:
      with st.container():
        render_html(
            f"""
            <span class="scan-frame-marker {frame_cls}" style="display:none;"></span>
            <div class="scan-platform-header" dir="rtl">
                <div class="scan-platform-right" dir="rtl">
                    <span class="scan-platform-icon">{mode_icon}</span>
                    <div>
                        <div class="scan-platform-title">{html.escape(mode_title)}</div>
                        <div class="scan-platform-sub">{html.escape(mode_sub)}</div>
                    </div>
                </div>
                <span class="scan-platform-badge">{html.escape(mode_badge)}</span>
            </div>
            """
        )
        c_play, c_stop = st.columns(2)
        with c_play:
          render_html('<span class="media-play-marker" style="display:none;"></span>')
          try:
            play_clicked = st.button(
                "▶ تشغيل",
                key=f"start_scan_{mode_key}",
                help=f"تشغيل {mode_title}",
                type="primary",
                use_container_width=True,
            )
          except TypeError:
            play_clicked = st.button(
                "▶ تشغيل",
                key=f"start_scan_{mode_key}",
                help=f"تشغيل {mode_title}",
            )
          if play_clicked:
            clear_stop_scan()
            triggered_mode = mode_key
        with c_stop:
          render_html('<span class="media-stop-marker" style="display:none;"></span>')
          try:
            stop_clicked = st.button(
                "⏹ إيقاف",
                key=f"stop_scan_{mode_key}",
                help=f"إيقاف {mode_title}",
                type="secondary",
                use_container_width=True,
            )
          except TypeError:
            stop_clicked = st.button(
                "⏹ إيقاف",
                key=f"stop_scan_{mode_key}",
                help=f"إيقاف {mode_title}",
            )
          if stop_clicked:
            request_stop_scan()

# =====================================================================
# 16. منطقة الرادار الدوار 360° وشريط التقدم ومؤشر DONE
# =====================================================================
radar_placeholder = st.empty()
progress_placeholder = st.empty()
done_placeholder = st.empty()


def execute_interactive_scan(mode_key: str):
  clear_stop_scan()
  rt_state["active_scan"] = mode_key
  s_period = cfg.get("search_period", "آخر 7 أيام")

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
                    مسح ذكي بزاوية 360° ({html.escape(s_period)})... ({pct_int}%)
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
        ("الصحف المغربية", lambda cb: scrape_moroccan_press(kw, s_period, cb)),
        ("يوتيوب", lambda cb: scrape_youtube_platform(kw, s_period, cb)),
        ("فيسبوك", lambda cb: scrape_facebook_platform(kw, s_period, cb)),
        ("منصة إكس", lambda cb: scrape_x_platform(kw, s_period, cb)),
        (
            "تيك توك وإنستغرام ولينكدإن",
            lambda cb: scrape_other_platforms(kw, s_period, cb),
        ),
        (
            "الروابط والقنوات المخصصة",
            lambda cb: scrape_custom_targets(custom_targets, kw, s_period, cb),
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
    collected = scrape_moroccan_press(kw, s_period, update_ui_progress)
  elif mode_key == "fb":
    collected = scrape_facebook_platform(kw, s_period, update_ui_progress)
  elif mode_key == "x":
    collected = scrape_x_platform(kw, s_period, update_ui_progress)
  elif mode_key == "yt":
    collected = scrape_youtube_platform(kw, s_period, update_ui_progress)
  elif mode_key == "other":
    collected = scrape_other_platforms(kw, s_period, update_ui_progress)
  elif mode_key == "target":
    collected = scrape_custom_targets(
        custom_targets, kw, s_period, update_ui_progress
    )

  if not is_stop_requested():
    update_ui_progress(
        0.94, "استخراج صور المقالات ومتونها وتلخيصها عبر Gemini AI..."
    )
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
# 17. فرز الأخبار زمنياً (الأحدث أولاً) وفصل الأخبار النشطة (24 ساعة من الرصد) عن الأرشيف
# =====================================================================
all_articles = fetch_articles_from_db()
now_ts = time.time()
selected_period_sec = get_period_config(cfg.get("search_period", "آخر 7 أيام"))[
    "sec"
]

live_articles = []
archive_articles = []
for a in all_articles:
  pub_t = float(a.get("pub_timestamp", 0))
  mon_t = float(a.get("created_at") or pub_t)
  if mon_t <= 0:
    mon_t = pub_t
  # يبقى الخبر المرصود في الواجهة النشطة لمدة 24 ساعة من وقت رصده الأول (created_at)، وبمجرد مرور 24 ساعة يُحال تلقائياً إلى الأرشيف الدائم
  is_monitored_within_24h = (now_ts - mon_t) < 86400
  if is_monitored_within_24h:
    live_articles.append(a)
  else:
    archive_articles.append(a)

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
    a
    for a in live_articles
    if int(a.get("is_custom_target", 0)) == 1
    and belongs_to_any_custom_target(a, custom_targets)
]

metrics_data = [
    ("🌐 الكل (النشط)", len(live_articles)),
    ("📰 الصحف", len(press_live)),
    ("🟦 فيسبوك", len(fb_live)),
    ("⬛ إكس", len(x_live)),
    ("🟥 يوتيوب", len(yt_live)),
    ("🎯 المخصص", len(target_live)),
    ("🗄️ الأرشيف", len(archive_articles)),
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

    if is_summary_just_title(raw_title, raw_summary):
      raw_summary = build_extractive_arabic_summary(
          raw_title, raw_snip, plat, raw_src
      )

    pub_ts = float(item.get("pub_timestamp") or (time.time() - 3600))
    raw_pub_date = clean_display_text(item.get("pub_date") or "")
    if not raw_pub_date:
      raw_pub_date = datetime.fromtimestamp(
          pub_ts, tz=timezone.utc
      ).strftime("%Y-%m-%d %H:%M")

    mon_ts = float(item.get("created_at") or pub_ts)
    mon_date_str = datetime.fromtimestamp(mon_ts, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M"
    )

    raw_url = str(item.get("url") or "#").strip()
    clean_link_url = clean_social_post_url(raw_url)

    fallback_svg_uri = get_fallback_thumbnail_data_uri(plat, raw_src)
    raw_img = (item.get("image_url") or "").strip()
    if not raw_img:
      raw_img = extract_thumbnail_for_item(clean_link_url, "", plat)
    final_img_src = html.escape(
        raw_img if raw_img else fallback_svg_uri, quote=True
    )
    fallback_svg_safe = html.escape(fallback_svg_uri, quote=True)

    title_safe = html.escape(raw_title)
    summary_safe = html.escape(raw_summary)
    source_safe = html.escape(raw_src)
    pub_date_safe = html.escape(raw_pub_date)
    mon_date_safe = html.escape(mon_date_str)
    rel_time = html.escape(format_relative_arabic(pub_ts))
    category_safe = html.escape(
        clean_display_text(item.get("category") or "شؤون قضائية")
    )
    url_safe = html.escape(clean_link_url, quote=True)
    target_tag = (
        '<span class="badge-target">🎯 رصد مخصص</span>'
        if int(item.get("is_custom_target", 0)) == 1
        else ""
    )

    card_html = (
        f'<div class="news-card {css_cls}" dir="rtl" style="direction:rtl !important;text-align:right !important;">'
        '<div class="news-card-layout" dir="rtl" style="display:flex;flex-direction:row;direction:rtl !important;text-align:right !important;">'
        '<div class="news-thumb-box">'
        f'<img class="news-thumb-img" src="{final_img_src}" alt="thumbnail" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src=\'{fallback_svg_safe}\';" />'
        "</div>"
        '<div class="news-body-col" dir="rtl" style="direction:rtl !important;text-align:right !important;">'
        '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;direction:rtl !important;text-align:right !important;">'
        f'<span class="badge-plat">{html.escape(type_badge_txt)}</span>'
        f"{target_tag}"
        f'<span style="font-weight:800;color:#e2e8f0;font-size:0.86rem;">{source_safe}</span>'
        f'<span style="color:#64748b;font-size:0.82rem;">• {category_safe}</span>'
        "</div>"
        f'<div class="news-title" dir="rtl" style="direction:rtl !important;text-align:right !important;"><a href="{url_safe}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:none;">{title_safe}</a></div>'
        '<div class="news-dates-row" dir="rtl" style="direction:rtl !important;text-align:right !important;">'
        f'<span class="date-chip" dir="rtl">📅 تاريخ النشر: <strong style="color:#38bdf8;" dir="ltr">{pub_date_safe}</strong> <span style="color:#34d399;">({rel_time})</span></span>'
        f'<span class="date-chip" dir="rtl">📡 تاريخ الرصد: <strong style="color:#f472b6;" dir="ltr">{mon_date_safe}</strong></span>'
        "</div>"
        f'<div class="news-summary-box" dir="rtl" style="direction:rtl !important;text-align:right !important;">'
        f'<strong style="color:#38bdf8;">📝 ملخص الخبر: </strong>{summary_safe}'
        "</div>"
        '<div dir="rtl" style="direction:rtl !important;text-align:right !important;">'
        f'<a class="news-link" href="{url_safe}" target="_blank" rel="noopener noreferrer">🔗 فتح المصدر الأصلي</a>'
        "</div>"
        "</div>"
        "</div>"
        "</div>"
    )
    cards_buffer.append(card_html)

  render_html("\n".join(cards_buffer))


# =====================================================================
# 18. التبويبات الرئيسية (بأسماء مختصرة من كلمة واحدة)
# =====================================================================
tabs = st.tabs([
    f"🌐 الكل ({len(live_articles)})",
    f"📰 الصحف ({len(press_live)})",
    f"🟦 فيسبوك ({len(fb_live)})",
    f"⬛ إكس ({len(x_live)})",
    f"🟥 يوتيوب ({len(yt_live)})",
    f"🟪 أخرى ({len(other_live)})",
    f"🎯 المخصص ({len(target_live)})",
    f"🗄️ الأرشيف ({len(archive_articles)})",
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
      empty_msg="لا توجد عناصر في الأرشيف حالياً (تنتقل الأخبار تلقائياً إلى الأرشيف بعد مرور 24 ساعة على رصدها).",
  )

# =====================================================================
# 19. فحص الرصد الدوري غير المتزامن (بدون تجميد الواجهة أو قفل SQLite)
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
