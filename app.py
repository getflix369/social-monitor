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
ARCHIVE_JSON_FILE = "articles_archive.json"
CREDENTIALS_FILE = "credentials.json"
CUSTOM_TARGETS_FILE = "custom_targets.json"
MONITOR_STATE_FILE = "monitor_state.json"

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
  return re.sub(r"#(?:plat|target)=[^\s#]*", "", str(url or "").strip())


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
  """التحقق الصارم من أن الرابط يوجه إلى المنشور/الفيديو/التغريدة بعينها وليس إلى الصفحة العامة أو صفحة خطأ."""
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
    # رفض مسارات البحث الداخلي في فيسبوك (search/posts, search/top) لأنها تظهر خطأ Not Found للمستخدم
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

    # 1) permalink.php أو story.php مع story_fbid
    if path_low in ("permalink.php", "story.php"):
      s_fbid = (qs.get("story_fbid") or [""])[0].strip()
      return bool(s_fbid and len(s_fbid) >= 6)

    # 2) photo.php أو photo/ مع fbid
    if path_low in ("photo.php", "photo"):
      fbid = (qs.get("fbid") or [""])[0].strip()
      return bool(fbid and len(fbid) >= 6)

    # 3) watch/ أو video.php مع v
    if path_low in ("watch", "video.php"):
      v_id = (qs.get("v") or [""])[0].strip()
      return bool(v_id and len(v_id) >= 5)

    # 4) مسارات تحتوي على /posts/ أو /videos/ أو /reel/ أو /photos/ أو /share/p/
    parts = [p.strip() for p in path.split("/") if p.strip()]
    parts_low = [p.lower() for p in parts]

    if len(parts_low) >= 3 and parts_low[0] == "share" and parts_low[1] in ("p", "v", "r"):
      return len(parts[2]) >= 4

    if "posts" in parts_low:
      idx = parts_low.index("posts")
      tail_segs = parts[idx + 1 :]
      if not tail_segs:
        return False
      for seg in tail_segs:
        if re.match(r"^1[678]\d{8}$", seg):
          return False
        if seg.startswith("pfbid") or (seg.isdigit() and len(seg) >= 8) or len(seg) >= 11 or ":" in seg:
          return True
      return False

    if "permalink" in parts_low:
      idx = parts_low.index("permalink")
      tail_segs = parts[idx + 1 :]
      return any(len(s) >= 8 for s in tail_segs)

    if "videos" in parts_low:
      idx = parts_low.index("videos")
      tail_segs = parts[idx + 1 :]
      for seg in tail_segs:
        if seg.lower() != "videos" and ((seg.isdigit() and len(seg) >= 7) or len(seg) >= 10):
          return True
      return False

    if "reel" in parts_low or "reels" in parts_low:
      key_r = "reel" if "reel" in parts_low else "reels"
      idx = parts_low.index(key_r)
      if idx + 1 < len(parts) and len(parts[idx + 1]) >= 6:
        return True
      return False

    if "photos" in parts_low:
      idx = parts_low.index("photos")
      tail_segs = parts[idx + 1 :]
      for seg in tail_segs:
        if seg.startswith("pfbid") or (seg.isdigit() and len(seg) >= 8):
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
    return bool(
        re.search(
            r"(?:watch\?v=|youtu\.be/|/shorts/|/live/)[A-Za-z0-9_-]{11}",
            u,
            re.IGNORECASE,
        )
    )

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
  full_u = raw_u if "://" in raw_u else f"https://{raw_u}"
  parsed = urllib.parse.urlparse(full_u)
  domain = (
      parsed.netloc.lower()
      .replace("www.", "")
      .replace("m.", "")
      .replace("web.", "")
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
  elif "facebook.com" in domain or "fb.com" in domain:
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
      handle = qs["id"][0].strip()
      channel_id = handle
      display_label = f"fb_{handle}"
    elif len(path_parts) >= 2 and path_parts[0].lower() in (
        "people",
        "pages",
        "company",
        "in",
        "groups",
    ):
      handle = path_parts[1].lstrip("@").replace("-", " ")
      display_label = path_parts[1]
      if len(path_parts) >= 3 and path_parts[2].isdigit():
        channel_id = path_parts[2]
    elif len(path_parts) >= 2 and path_parts[0].lower() == "share":
      handle = path_parts[-1]
      display_label = f"fb_{handle}"
    else:
      for seg in path_parts:
        if seg.lower() not in GENERIC_SOCIAL_SEGMENTS:
          handle = seg.lstrip("@")
          display_label = handle
          break
  else:
    display_label = domain
    if path_parts:
      handle = path_parts[0]

  target_tag_key = urllib.parse.quote(
      (display_label or handle or base_domain).lower(), safe=""
  )

  return {
      "raw_url": full_u,
      "domain": base_domain,
      "platform": platform,
      "handle": handle,
      "channel_id": channel_id,
      "display_label": display_label or base_domain,
      "target_tag": f"#target={target_tag_key}",
  }


def belongs_to_custom_target(item: dict, target_info: dict) -> bool:
  if not target_info or not item:
    return False

  raw_item_url = str(item.get("url") or "").strip().lower()
  t_tag = (target_info.get("target_tag") or "").lower()
  if t_tag and t_tag in raw_item_url:
    return True

  u = strip_internal_url_fragments(raw_item_url)
  src = str(item.get("source_name") or "").lower()
  title = str(item.get("title") or "").lower()
  snippet = str(item.get("raw_snippet") or "").lower()
  t_dom = target_info.get("domain", "").lower()
  t_plat = target_info.get("platform", "")
  handle = (target_info.get("handle") or "").lower()
  cid = (target_info.get("channel_id") or "").lower()
  disp = (target_info.get("display_label") or "").lower().lstrip("@")

  if t_plat in ("يوتيوب", "فيسبوك", "إكس", "أخرى"):
    if "news.google.com" in u:
      return False

  if t_plat == "يوتيوب":
    if "youtube.com" not in u and "youtu.be" not in u:
      return False
    if item.get("_verified_target_owner"):
      return True
    if handle and (handle in src or handle in u):
      return True
    if cid and (cid in src or cid in u):
      return True
    if disp and disp in src:
      return True
    return False

  if t_plat in ("فيسبوك", "إكس", "أخرى"):
    allowed_doms = (
        ["x.com", "twitter.com"]
        if t_plat == "إكس"
        else ([t_dom, "fb.com"] if t_plat == "فيسبوك" else [t_dom])
    )
    if not any(d in u for d in allowed_doms) and not item.get(
        "_verified_target_owner"
    ):
      return False
    if item.get("_verified_target_owner"):
      return True
    identifiers = [x for x in [handle, cid, disp] if x and len(x) >= 2]
    if not identifiers:
      return True
    return any(
        ident in u or ident in src or ident in title or ident in snippet
        for ident in identifiers
    )

  return bool(t_dom and t_dom in u)


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
    return f"https://i.ytimg.com/vi/{m_yt.group(1)}/hqdefault.jpg", "", real_url

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
    for desc_pattern in [
        r'<meta[^>]+(?:property|name)=["\'](?:og:description|description|twitter:description)["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:description|description|twitter:description)["\']',
    ]:
      m_d = re.search(desc_pattern, html_doc[:25000], re.IGNORECASE)
      if m_d:
        meta_desc = clean_display_text(m_d.group(1))
        if len(meta_desc) > 35:
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
      m_tag = re.search(r"(#(?:plat|target)=[^\s#]*)$", url)
      item["url"] = f"{resolved_u}{m_tag.group(1) if m_tag else ''}"

  if not img_url or len(raw_snip) < 70 or raw_snip.lower() == title.lower():
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


def purge_invalid_articles_from_db():
  lock = get_db_lock()
  current_targets = load_custom_targets()
  with lock:
    removed_any = False
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute(
          "SELECT id, title, summary, source_name, platform, raw_snippet, url, is_custom_target FROM articles"
      )
      rows = c.fetchall()
      bad_ids = []
      for r in rows:
        d = dict(r)
        is_tgt = bool(d.get("is_custom_target"))
        snip = f"{d.get('summary') or ''} {d.get('raw_snippet') or ''}"
        if not is_strictly_judicial_and_clean(
            d.get("title") or "", snip, d.get("url") or "", "", is_target=is_tgt
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

    if os.path.exists(ARCHIVE_JSON_FILE):
      try:
        with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
          arch_data = json.load(f)
        if isinstance(arch_data, list):
          cleaned_arch = []
          for item in arch_data:
            if not isinstance(item, dict):
              continue
            is_tgt = bool(item.get("is_custom_target", 0))
            if not is_strictly_judicial_and_clean(
                item.get("title", ""),
                f"{item.get('summary', '')} {item.get('raw_snippet', '')}",
                item.get("url", ""),
                "",
                is_target=is_tgt,
            ):
              continue
            if is_tgt and not belongs_to_any_custom_target(
                item, current_targets
            ):
              continue
            cleaned_arch.append(item)
          if len(cleaned_arch) != len(arch_data):
            with open(ARCHIVE_JSON_FILE, "w", encoding="utf-8") as f:
              json.dump(cleaned_arch, f, ensure_ascii=False, indent=2)
            removed_any = True
      except Exception:
        pass

    if removed_any and os.path.exists(DB_FILE):
      try:
        shutil.copyfile(DB_FILE, REPO_DB_FILE)
      except Exception:
        pass


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
    purge_invalid_articles_from_db()


def sync_db_to_json(extra_items: list = None):
  lock = get_db_lock()
  current_targets = load_custom_targets()
  with lock:
    merged_by_url = {}
    if os.path.exists(ARCHIVE_JSON_FILE):
      try:
        with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
          existing_json = json.load(f)
        if isinstance(existing_json, list):
          for item in existing_json:
            if not isinstance(item, dict) or not item.get("url"):
              continue
            is_tgt = bool(item.get("is_custom_target", 0))
            if not is_strictly_judicial_and_clean(
                item.get("title", ""),
                f"{item.get('summary', '')} {item.get('raw_snippet', '')}",
                item.get("url", ""),
                "",
                is_target=is_tgt,
            ):
              continue
            if is_tgt and not belongs_to_any_custom_target(
                item, current_targets
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
  current_targets = load_custom_targets()
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
              u_str = item.get("url", "")
              is_tgt = int(item.get("is_custom_target", 0))
              if not is_strictly_judicial_and_clean(
                  t_clean,
                  f"{s_clean} {raw_s}",
                  u_str,
                  "",
                  is_target=bool(is_tgt),
              ):
                continue
              if is_tgt and not belongs_to_any_custom_target(
                  item, current_targets
              ):
                continue

              if is_summary_just_title(t_clean, s_clean):
                s_clean = build_extractive_arabic_summary(
                    t_clean, raw_s, plat, src
                )
              pub_ts = float(item.get("pub_timestamp", time.time() - 3600))
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
                                    image_url, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
  current_targets = load_custom_targets()
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
      for r in c.fetchall():
        d = dict(r)
        is_tgt = bool(d.get("is_custom_target", 0))
        if not is_strictly_judicial_and_clean(
            d.get("title", ""),
            f"{d.get('summary', '')} {d.get('raw_snippet', '')}",
            d.get("url", ""),
            "",
            is_target=is_tgt,
        ):
          continue
        if is_tgt and not belongs_to_any_custom_target(d, current_targets):
          continue
        db_rows.append(d)
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
          valid_data = []
          for d in data:
            if not isinstance(d, dict):
              continue
            is_tgt = bool(d.get("is_custom_target", 0))
            if not is_strictly_judicial_and_clean(
                d.get("title", ""),
                f"{d.get('summary', '')} {d.get('raw_snippet', '')}",
                d.get("url", ""),
                "",
                is_target=is_tgt,
            ):
              continue
            if is_tgt and not belongs_to_any_custom_target(d, current_targets):
              continue
            valid_data.append(d)
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
      r'"(?:videoRenderer|gridVideoRenderer|compactVideoRenderer|reelItemRenderer)"\s*:',
      html_text,
  )[1:]
  for chunk in chunks[:35]:
    vid_m = re.search(r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"', chunk[:2500])
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
        chunk[:4000],
    )
    channel_name = (
        decode_js_escaped_text(owner_m.group(1))
        if owner_m
        else default_channel_name
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


def scrape_facebook_platform(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
):
  return _multi_engine_social_search(
      "فيسبوك",
      ["facebook.com"],
      keywords_input,
      search_period,
      progress_cb,
  )


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
    max_results: int = 15,
) -> list:
  """بحث متوازي عبر Yahoo Search HTML وDuckDuckGo HTML وBing RSS وDDGS لجلب الروابط المباشرة للمنشورات والفيديوهات."""
  collected = []
  seen_u = set()

  def _add_candidate(raw_href: str, raw_title: str, raw_body: str, raw_date: str = ""):
    u = clean_social_post_url(raw_href)
    if not u or u in seen_u or not u.startswith("http"):
      return
    t_txt = clean_display_text(raw_title)
    b_txt = clean_display_text(raw_body)
    if not t_txt and not b_txt:
      return
    pub_str, pub_ts = extract_date_from_url_or_text(
        u, f"{t_txt} {b_txt}", raw_date, fallback_offset_sec=3600
    )
    seen_u.add(u)
    collected.append({
        "title": t_txt or b_txt[:105],
        "url": u,
        "raw_snippet": b_txt or t_txt,
        "source_name": default_source or platform,
        "platform": platform,
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": extract_thumbnail_for_item(u, "", platform),
    })

  # 1) محرك Yahoo Search HTML (يعمل بكفاءة عالية على خوادم السحابة ويستخرج فهرس Bing الكامل بدون حظر)
  yahoo_url = f"https://search.yahoo.com/search?p={urllib.parse.quote(query)}&n={max_results}"
  try:
    ry = requests.get(yahoo_url, headers=DEFAULT_HEADERS, timeout=8)
    if ry.status_code == 200 and ry.text and BeautifulSoup is not None:
      soup_y = BeautifulSoup(ry.text, "html.parser")
      for algo in soup_y.select("div.algo, div.dd.algo, li div.algo-sr"):
        a_el = algo.select_one("h3 a[href], a.ac-algo[href], a[href]")
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

  # 2) محرك DuckDuckGo HTML المباشر (بدون قيود التوكن)
  ddg_html_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
  try:
    rd = requests.get(ddg_html_url, headers=DEFAULT_HEADERS, timeout=8)
    if rd.status_code == 200 and rd.text and BeautifulSoup is not None:
      soup_d = BeautifulSoup(rd.text, "html.parser")
      for res_box in soup_d.select("div.result, div.web-result"):
        a_el = res_box.select_one("a.result__a[href]")
        if not a_el:
          continue
        href = a_el.get("href", "").strip()
        title_txt = clean_display_text(a_el.get_text(" ", strip=True))
        snip_el = res_box.select_one(".result__snippet")
        snip_txt = (
            clean_display_text(snip_el.get_text(" ", strip=True))
            if snip_el
            else ""
        )
        _add_candidate(href, title_txt, snip_txt)
  except Exception:
    pass

  # 3) محرك Bing Search RSS & Bing News RSS
  for bing_base in [
      "https://www.bing.com/search?q=",
      "https://www.bing.com/news/search?q=",
  ]:
    bing_u = (
        f"{bing_base}{urllib.parse.quote(query)}"
        "&format=rss&adlt=strict&cc=MA&setlang=ar"
    )
    try:
      rb = requests.get(bing_u, headers=DEFAULT_HEADERS, timeout=8)
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

  # 4) مكتبة DDGS (بدون قيد timelimit الضيق الذي يحجب منشورات فيسبوك ويوتيوب المخصصة)
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


def _scrape_youtube_custom_channel(
    t_info: dict, t_kw: str, max_age_sec: int, seen_urls: set
) -> list:
  results = []
  all_channel_videos = []
  raw_u = t_info["raw_url"]
  cid = t_info.get("channel_id", "")
  handle = t_info.get("handle", "")
  channel_title = t_info.get("display_label", "YouTube")

  # إذا كان الرابط المضاف رابط فيديو يوتيوب مباشر، نرصده فوراً
  m_direct_v = re.search(
      r"(?:watch\?v=|youtu\.be/|/shorts/|/live/)([A-Za-z0-9_-]{11})", raw_u
  )
  if m_direct_v:
    vid_id = m_direct_v.group(1)
    v_url = f"https://www.youtube.com/watch?v={vid_id}"
    _, p_body, _ = scrape_article_page_content_and_image(v_url)
    v_title = p_body[:105] if p_body else f"فيديو يوتيوب ({vid_id})"
    pub_str, pub_ts = extract_date_from_url_or_text(
        v_url, p_body, "", fallback_offset_sec=1800
    )
    entry = {
        "title": v_title,
        "url": v_url,
        "raw_snippet": p_body or v_title,
        "source_name": f"🎯 {channel_title}",
        "platform": "يوتيوب",
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg",
    }
    _tag_custom_target_item(entry, t_info, f"🎯 {channel_title}")
    return [entry]

  # بناء رابط نظيف لتبويب الفيديوهات بدون معاملات التتبع (?si=...) التي تسبب خطأ 404
  parsed_u = urllib.parse.urlparse(raw_u)
  clean_base_u = urllib.parse.urlunparse(
      ("https", "www.youtube.com", parsed_u.path.rstrip("/"), "", "", "")
  )
  if cid and not handle:
    videos_tab_url = f"https://www.youtube.com/channel/{cid}/videos"
  elif handle:
    h_prefix = f"@{handle}" if not handle.startswith("@") and "/c/" not in clean_base_u and "/user/" not in clean_base_u else handle
    if "/c/" in clean_base_u or "/user/" in clean_base_u:
      videos_tab_url = f"{clean_base_u}/videos"
    else:
      videos_tab_url = f"https://www.youtube.com/{h_prefix}/videos"
  else:
    videos_tab_url = (
        clean_base_u
        if any(clean_base_u.endswith(x) for x in ["/videos", "/streams", "/shorts"])
        else f"{clean_base_u}/videos"
    )

  page_html = ""
  for candidate_yt_url in [videos_tab_url, clean_base_u]:
    try:
      r = requests.get(
          candidate_yt_url,
          headers=DEFAULT_HEADERS,
          cookies=YT_BYPASS_COOKIES,
          timeout=11,
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
          cand_name = re.sub(r"\s*-\s*YouTube.*$", "", cand_name, flags=re.IGNORECASE).strip()
          if cand_name and cand_name.lower() != "youtube":
            channel_title = cand_name

        if not cid:
          for pat in [
              r'"(?:channelId|externalId|externalChannelId|browseId)"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"',
              r'channel_id=(UC[a-zA-Z0-9_-]{20,})',
              r'/channel/(UC[a-zA-Z0-9_-]{20,})',
          ]:
            m_c = re.search(pat, page_html)
            if m_c:
              cid = m_c.group(1)
              break
        if cid or '"videoRenderer"' in page_html or '"gridVideoRenderer"' in page_html:
          break
    except Exception:
      pass

  # إذا لم يتم العثور على معرف القناة UC عبر الصفحة المباشرة، نستخرجه من بحث يوتيوب عن معرف القناة
  if not cid and (handle or channel_title):
    q_ch = f"@{handle}" if handle else channel_title
    yt_search_u = f"https://www.youtube.com/results?search_query={urllib.parse.quote(q_ch)}"
    try:
      rs_yt = requests.get(
          yt_search_u,
          headers=DEFAULT_HEADERS,
          cookies=YT_BYPASS_COOKIES,
          timeout=10,
      )
      if rs_yt.status_code == 200 and rs_yt.text:
        m_ch_id = re.search(
            r'"channelRenderer"\s*:\s*\{[^{}]*"channelId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"',
            rs_yt.text,
        )
        if not m_ch_id:
          m_ch_id = re.search(
              r'"channelId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"', rs_yt.text
          )
        if m_ch_id:
          cid = m_ch_id.group(1)
        if not page_html:
          page_html = rs_yt.text
    except Exception:
      pass

  source_badge = f"🎯 {channel_title}"
  now_ts = time.time()
  seen_channel_vids = set()

  # 1) الجلب من خلاصة XML الرسمية للقناة (تضمن أحدث 15 فيديو بتواريخ نشرها الدقيقة بالثانية)
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
          if not is_strictly_judicial_and_clean(
              entry["title"],
              entry["raw_snippet"],
              entry["url"],
              t_kw,
              is_target=True,
          ):
            continue
          u_clean_v = clean_social_post_url(entry["url"])
          if u_clean_v not in seen_channel_vids:
            seen_channel_vids.add(u_clean_v)
            _tag_custom_target_item(entry, t_info, source_badge)
            all_channel_videos.append(entry)
    except Exception:
      pass

  # 2) الجلب من كود صفحة فيديوهات القناة المباشر
  if page_html:
    for v in _extract_yt_renderers_from_html(page_html, channel_title):
      v_url = f"https://www.youtube.com/watch?v={v['vid']}"
      if v_url in seen_channel_vids:
        continue
      if not is_strictly_judicial_and_clean(
          v["title"], v["desc"], v_url, t_kw, is_target=True
      ):
        continue
      pub_str, pub_ts = extract_date_from_url_or_text(
          v_url, v["desc"], v["pub_rel"], fallback_offset_sec=3600
      )
      entry = {
          "title": v["title"],
          "url": v_url,
          "raw_snippet": v["desc"],
          "source_name": source_badge,
          "platform": "يوتيوب",
          "pub_date": pub_str,
          "pub_timestamp": pub_ts,
          "image_url": f"https://i.ytimg.com/vi/{v['vid']}/hqdefault.jpg",
      }
      seen_channel_vids.add(v_url)
      _tag_custom_target_item(entry, t_info, source_badge)
      all_channel_videos.append(entry)

  # 3) احتياطي إضافي عبر محركات البحث إذا حجب يوتيوب عنوان IP السحابي
  if len(all_channel_videos) < 3:
    yt_ident = handle or channel_title or cid
    if yt_ident:
      q_web_yt = f'site:youtube.com "{yt_ident}" {t_kw}'.strip()
      for item_w in _multi_engine_web_search(
          q_web_yt, platform="يوتيوب", default_source=source_badge, max_results=12
      ):
        u_w = clean_social_post_url(item_w.get("url", ""))
        if u_w in seen_channel_vids or not is_direct_social_post_url(u_w, "يوتيوب"):
          continue
        if not is_strictly_judicial_and_clean(
            item_w["title"], item_w["raw_snippet"], u_w, t_kw, is_target=True
        ):
          continue
        seen_channel_vids.add(u_w)
        _tag_custom_target_item(item_w, t_info, source_badge)
        all_channel_videos.append(item_w)

  # ترتيب فيديوهات القناة من الأحدث إلى الأقدم
  all_channel_videos.sort(
      key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
  )

  in_window = [
      e
      for e in all_channel_videos
      if max_age_sec <= 0
      or (now_ts - float(e.get("pub_timestamp", 0))) <= max_age_sec
  ]
  chosen_list = in_window if in_window else all_channel_videos[:10]
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
      if rp.status_code == 200 and rp.text:
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
      if is_direct_social_post_url(cand_u, "فيسبوك"):
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


def _scrape_facebook_plugin_timeline(
    canonical_fb_url: str,
    t_info: dict,
    source_badge: str,
    page_avatar: str,
    t_kw: str,
    handle: str = "",
    page_id: str = "",
) -> list:
  """استخراج المنشورات مع روابطها المباشرة الدقيقة من أداة الخط الزمني العامة لفيسبوك (plugins/page.php)."""
  posts = []
  seen_post_urls = set()
  plugin_url = (
      "https://www.facebook.com/plugins/page.php?"
      f"href={urllib.parse.quote(canonical_fb_url)}"
      "&tabs=timeline&width=500&height=800&small_header=false"
      "&adapt_container_width=true&hide_cover=false&show_facepile=false"
  )
  for hdr in (DEFAULT_HEADERS, FB_CRAWLER_HEADERS):
    try:
      r = requests.get(plugin_url, headers=hdr, timeout=10)
      if r.status_code != 200 or not r.text:
        continue

      if BeautifulSoup is not None:
        soup = BeautifulSoup(r.text, "html.parser")
        post_containers = soup.select("div._5pcr, div.userContentWrapper")
        if not post_containers:
          post_containers = soup.select(
              "div[data-ft*='top_level_post_id'], div[role='article']"
          )

        for idx, box in enumerate(post_containers[:15]):
          post_link = _extract_post_permalink_from_fb_box(
              box, canonical_fb_url, handle=handle, page_id=page_id
          )
          if not post_link or not is_direct_social_post_url(post_link, "فيسبوك"):
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
            continue
          if not is_strictly_judicial_and_clean(
              post_text, post_text, post_link, t_kw, is_target=True
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
          title_short = post_text[:110] + ("..." if len(post_text) > 110 else "")
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
          _tag_custom_target_item(entry, t_info, source_badge)
          seen_post_urls.add(post_link)
          posts.append(entry)

      if not posts:
        extra_posts = _extract_facebook_posts_from_raw_html(
            r.text,
            canonical_fb_url,
            handle,
            page_id,
            t_info,
            source_badge,
            page_avatar,
            t_kw,
        )
        posts.extend(extra_posts)

      if posts:
        break
    except Exception:
      pass
  return posts


def _verify_and_enrich_fb_post_url(
    post_u: str, page_avatar: str = ""
) -> tuple:
  """فحص رابط المنشور عبر ترويسة facebookexternalhit للتأكد من أنه يعمل (ليس Not Found) واستخراج النص الكامل والصورة."""
  try:
    rp = requests.get(post_u, headers=FB_CRAWLER_HEADERS, timeout=6)
    if rp.status_code != 200 or not rp.text:
      return True, "", "", post_u
    p_html = rp.text[:40000]

    post_title_og = ""
    for t_pat in [
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        r"<title>(.*?)</title>",
    ]:
      m_t = re.search(t_pat, p_html, re.IGNORECASE | re.DOTALL)
      if m_t:
        post_title_og = clean_display_text(m_t.group(1))
        break

    # إذا كان الرابط معطوباً أو محذوفاً (Not Found / المحتوى غير متوفر)
    bad_titles = [
        "page not found",
        "content isn't available",
        "this content isn't available",
        "المحتوى غير متوفر",
        "الصفحة غير موجودة",
        "غير متوفر حاليا",
    ]
    if post_title_og and any(bt in post_title_og.lower() for bt in bad_titles):
      return False, "", "", post_u

    post_desc = ""
    for d_pat in [
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
    ]:
      m_d = re.search(d_pat, p_html, re.IGNORECASE)
      if m_d:
        d_txt = clean_display_text(m_d.group(1))
        if len(d_txt) >= 12:
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

    m_og_u = re.search(
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
        p_html,
        re.IGNORECASE,
    )
    resolved_u = post_u
    if m_og_u:
      cand_og_u = clean_social_post_url(m_og_u.group(1))
      if is_direct_social_post_url(cand_og_u, "فيسبوك"):
        resolved_u = cand_og_u

    final_body = post_desc or post_title_og
    if final_body and any(
        lw in final_body.lower()
        for lw in ["قم بتسجيل الدخول", "log in to facebook", "تسجيل الدخول إلى فيسبوك"]
    ):
      final_body = ""

    return True, final_body, post_img, resolved_u
  except Exception:
    return True, "", page_avatar, post_u


def _extract_facebook_posts_from_raw_html(
    raw_html: str,
    canonical_fb_url: str,
    handle: str,
    page_id: str,
    t_info: dict,
    source_badge: str,
    page_avatar: str,
    t_kw: str,
) -> list:
  """استخراج روابط المنشورات المباشرة (pfbid, story_fbid, posts, videos, reel) المضمنة في كود صفحة فيسبوك."""
  if not raw_html:
    return []

  discovered_links = []
  seen_cand = set()
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
      ):
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

  extracted_posts = []
  for idx, post_u in enumerate(discovered_links[:8]):
    if is_stop_requested():
      break
    is_valid, final_text, post_img, resolved_u = _verify_and_enrich_fb_post_url(
        post_u, page_avatar
    )
    if not is_valid or not final_text or len(final_text) < 15:
      continue
    if not is_strictly_judicial_and_clean(
        final_text, final_text, resolved_u, t_kw, is_target=True
    ):
      continue

    pub_str, pub_ts = extract_date_from_url_or_text(
        resolved_u, final_text, "", fallback_offset_sec=1800 + (idx * 600)
    )
    entry = {
        "title": final_text[:110] + ("..." if len(final_text) > 110 else ""),
        "url": resolved_u,
        "raw_snippet": final_text,
        "source_name": source_badge,
        "platform": "فيسبوك",
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": post_img,
    }
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
  """البحث عن الرابط المباشر الحقيقي للمنشور (/posts/ أو /videos/ أو permalink.php) وإرجاع نص فارغ إذا لم يوجد (تجنباً لروابط Not Found)."""
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
    if is_direct_social_post_url(cand_u, "فيسبوك"):
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
  # إزالة اسم المدينة أو اللاحقة العامة بعد الفاصل العمودي | (مثل: رئاسة النيابة العامة | Rabat)
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
  domain = t_info["domain"]
  platform = t_info["platform"]
  handle = t_info.get("handle", "")
  cid = t_info.get("channel_id", "")
  disp = t_info.get("display_label", domain)
  now_ts = time.time()

  # إذا كان الرابط المضاف أصلاً رابط منشور مباشر بعينه، نرصده مباشرة
  if is_direct_social_post_url(raw_u, platform):
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

  # 1) جلب بيانات الصفحة العامة عبر ترويسة facebookexternalhit الموثوقة (تتخطى جدار تسجيل الدخول في فيسبوك)
  page_official_name = ""
  page_description = ""
  page_avatar = ""
  page_raw_html = ""
  canonical_url = raw_u
  req_hdrs = FB_CRAWLER_HEADERS if platform == "فيسبوك" else DEFAULT_HEADERS

  try:
    rp = requests.get(raw_u, headers=req_hdrs, timeout=8, allow_redirects=True)
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
      if re_parsed.get("handle") and (
          not handle or handle.startswith("fb_") or handle != re_parsed["handle"]
      ):
        handle = re_parsed["handle"]
      if re_parsed.get("channel_id") and not cid:
        cid = re_parsed["channel_id"]

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
          if len(cleaned_t) >= 2 and not any(
              w in cleaned_t.lower()
              for w in [
                  "log in",
                  "login",
                  "تسجيل الدخول",
                  "قم بتسجيل الدخول",
                  "not found",
                  "غير متوفر",
              ]
          ) and cleaned_t.lower() not in {"facebook", "فيسبوك", "فايسبوك"}:
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

  source_badge = f"🎯 {page_official_name or disp}"

  # 2) إذا كانت صفحة فيسبوك: فحص أداة الخط الزمني وكود الصفحة المباشر
  if platform == "فيسبوك":
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

    if len(all_target_posts) < 3 and page_raw_html:
      html_direct_posts = _extract_facebook_posts_from_raw_html(
          page_raw_html,
          canonical_url,
          handle,
          cid,
          t_info,
          source_badge,
          page_avatar,
          t_kw,
      )
      for p in html_direct_posts:
        u_p = clean_social_post_url(p["url"])
        if u_p not in seen_target_urls:
          seen_target_urls.add(u_p)
          all_target_posts.append(p)

  # 3) إذا كان الحساب على منصة إكس (X/Twitter): فحص نقطة Syndication الرسمية الخاصة بالحساب نفسه
  if platform == "إكس" and handle:
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

  # 4) مسح شامل لمنشورات وفيديوهات الصفحة عبر المحركات المتعددة (Yahoo + DDG HTML + Bing RSS + DDGS)
  target_queries = []
  if platform == "فيسبوك":
    if handle and not handle.startswith("fb_"):
      target_queries.append(f'site:facebook.com "{handle}" {t_kw}'.strip())
      target_queries.append(f'site:facebook.com "{handle}" posts {t_kw}'.strip())
      target_queries.append(f'site:facebook.com "{handle}" videos {t_kw}'.strip())
    if page_official_name:
      target_queries.append(
          f'site:facebook.com "{page_official_name}" {t_kw}'.strip()
      )
      target_queries.append(
          f'site:facebook.com "{page_official_name}" posts {t_kw}'.strip()
      )
    if cid:
      target_queries.append(f'site:facebook.com "{cid}" {t_kw}'.strip())
  else:
    if handle and not handle.startswith("fb_"):
      target_queries.append(f'site:{domain} "{handle}" {t_kw}'.strip())
      if platform == "إكس":
        target_queries.append(f'site:twitter.com "{handle}" {t_kw}'.strip())
    if page_official_name:
      target_queries.append(
          f'site:{domain} "{page_official_name}" {t_kw}'.strip()
      )

  # بناء قائمة الكلمات المميزة لملكية الصفحة (مع تقسيم الاسم المركب مثل: Sawt Al Adala - صوت العدالة)
  match_tokens = []
  for raw_tok in [handle, cid, page_official_name]:
    if not raw_tok or str(raw_tok).startswith("fb_"):
      continue
    clean_tok = str(raw_tok).strip().lower()
    if len(clean_tok) >= 3 and clean_tok not in match_tokens:
      match_tokens.append(clean_tok)
    for sub_part in re.split(r"[-|•–—:/()]+", clean_tok):
      sp = sub_part.strip()
      if len(sp) >= 4 and sp not in match_tokens:
        match_tokens.append(sp)

  for tq in target_queries[:5]:
    if is_stop_requested():
      break
    for entry in _multi_engine_web_search(
        tq, platform=platform, default_source=source_badge, max_results=15
    ):
      raw_entry_u = clean_social_post_url(entry.get("url", ""))
      if not raw_entry_u or raw_entry_u in seen_target_urls:
        continue

      unquoted_u = urllib.parse.unquote(raw_entry_u).lower()
      comb_entry = f"{entry['title']} {entry['raw_snippet']} {unquoted_u}".lower()
      if match_tokens and not any(tok in comb_entry for tok in match_tokens):
        continue

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
            continue
        else:
          continue

      if raw_entry_u in seen_target_urls:
        continue

      # التحقق من أن رابط المنشور يعمل وجلب نصه الكامل وصورته عبر ترويسة facebookexternalhit
      if platform == "فيسبوك" and len(all_target_posts) < 12:
        is_ok, og_body, og_img, final_u = _verify_and_enrich_fb_post_url(
            raw_entry_u, page_avatar
        )
        if not is_ok:
          continue
        if og_body and len(og_body) > len(entry.get("raw_snippet", "")):
          entry["raw_snippet"] = og_body
          if len(entry.get("title", "")) < 25 or "facebook" in entry.get("title", "").lower():
            entry["title"] = og_body[:110] + ("..." if len(og_body) > 110 else "")
        if og_img and not entry.get("image_url"):
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

      # إعادة استخراج التاريخ بعد إثراء النص لضمان دقة تاريخ النشر
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

  # ترتيب جميع المنشورات المكتشفة من الأحدث إلى الأقدم
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
    if platform == "يوتيوب":
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
  monitored_dt = datetime.fromtimestamp(
      float(item.get("created_at") or time.time()), tz=timezone.utc
  ).strftime("%Y-%m-%d %H:%M")
  clean_u = strip_internal_url_fragments(item.get("url", ""))
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

  existing_urls = set()
  existing_plat_titles = set()
  current_targets = load_custom_targets()
  lock = get_db_lock()
  with lock:
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      c = conn.cursor()
      c.execute("SELECT url, platform, title, is_custom_target FROM articles")
      for r_url, r_plat, r_title, r_tgt in c.fetchall():
        if r_url:
          existing_urls.add(r_url.strip())
        if r_title:
          existing_plat_titles.add(
              f"{r_plat or ''}::{int(r_tgt or 0)}::{r_title.strip()}"
          )
      conn.close()
    except Exception:
      pass

  kw_filter = cfg.get("keywords_input", "")
  candidates = []
  seen_batch_urls = set()
  seen_batch_plat_titles = set()
  for it in sorted(
      items, key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
  ):
    u = (it.get("url") or "").strip()
    t = clean_display_text(it.get("title") or "")
    s_raw = clean_display_text(it.get("raw_snippet") or "")
    p = it.get("platform", "الصحف")
    is_tgt = bool(is_target_run or it.get("is_custom_target"))
    if not u or not t:
      continue
    if not is_strictly_judicial_and_clean(
        t, s_raw, u, kw_filter if not is_tgt else "", is_target=is_tgt
    ):
      continue
    if is_tgt and not belongs_to_any_custom_target(it, current_targets):
      continue
    pt_key = f"{p}::{1 if is_tgt else 0}::{t}"
    if u in existing_urls or pt_key in existing_plat_titles:
      continue
    if u in seen_batch_urls or pt_key in seen_batch_plat_titles:
      continue
    seen_batch_urls.add(u)
    seen_batch_plat_titles.add(pt_key)
    it["title"] = t
    candidates.append(it)

  if not candidates:
    upgrade_incomplete_existing_articles(cfg, max_upgrades=6)
    return 0

  api_key = (cfg.get("gemini_api_key") or "").strip()
  prepared_rows = []
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
                            relevance_score, is_custom_target, raw_snippet,
                            image_url, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

  upgrade_incomplete_existing_articles(cfg, max_upgrades=4)

  if added_items:
    sync_db_to_json(extra_items=added_items)
    for rec in added_items[:10]:
      send_telegram_alert(rec, cfg)

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
    f"🎯 الروابط والقنوات المخصصة ({len(custom_targets)})", expanded=False
):
  with st.form("add_custom_target_form", clear_on_submit=True):
    c_u, c_k, c_b = st.columns([2.5, 1.5, 1.0])
    with c_u:
      new_t_url = st.text_input(
          "الرابط",
          placeholder="https://www.youtube.com/@... أو رابط صفحة فيسبوك/إكس/موقع",
          label_visibility="collapsed",
      )
    with c_k:
      new_t_kw = st.text_input(
          "كلمة (اختياري)",
          placeholder="كلمة فلترة داخل القناة/الصفحة (اختياري)...",
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
# 15. لوحة أزرار الرصد المتجاوبة (تلتف تلقائياً حسب عرض الشاشة)
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
  is_monitored_within_24h = (now_ts - mon_t) < 86400
  is_within_search_period = (now_ts - pub_t) <= max(selected_period_sec, 86400)
  is_tgt_item = int(a.get("is_custom_target", 0)) == 1
  if (
      (is_monitored_within_24h and is_within_search_period)
      or ((now_ts - pub_t) < 86400)
      or (is_tgt_item and is_monitored_within_24h)
  ):
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
    for a in all_articles
    if int(a.get("is_custom_target", 0)) == 1
    and belongs_to_any_custom_target(a, custom_targets)
]

metrics_data = [
    ("الكل (النشط)", len(live_articles)),
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
