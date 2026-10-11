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
        transition: all 0.2s ease-in-out;
    }
    .result-card:hover {
        box-shadow: 0 6px 12px rgba(0,0,0,0.08);
        border-color: #cbd5e1;
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


def get_credentials():
  gemini_k = ""
  tg_tok = ""
  tg_ch = ""
  try:
    gemini_k = st.secrets.get("GEMINI_API_KEY", "")
    tg_tok = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    tg_ch = st.secrets.get("TELEGRAM_CHAT_ID", "")
  except Exception:
    pass

  if not gemini_k:
    gemini_k = os.getenv("GEMINI_API_KEY", "")
  if not tg_tok:
    tg_tok = os.getenv("TELEGRAM_BOT_TOKEN", "")
  if not tg_ch:
    tg_ch = os.getenv("TELEGRAM_CHAT_ID", "")

  if os.path.exists("credentials.json"):
    try:
      with open("credentials.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        gemini_k = gemini_k or data.get("gemini_api_key", "")
        tg_tok = tg_tok or data.get("telegram_bot_token", "")
        tg_ch = tg_ch or data.get("telegram_chat_id", "")
    except Exception:
      pass

  return gemini_k, tg_tok, tg_ch


gemini_default, tg_tok_default, tg_ch_default = get_credentials()


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
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
  conn.commit()

  if os.path.exists(ARCHIVE_JSON_FILE):
    try:
      with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
        archived_data = json.load(f)
        for it in archived_data:
          c.execute(
              """
                    INSERT OR IGNORE INTO items (link, platform, source, title, date_published, pub_timestamp, snippet, ai_analysis, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        " snippet, ai_analysis, fetched_at FROM items"
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
          "fetched_at": r[8],
      })
    with open(ARCHIVE_JSON_FILE, "w", encoding="utf-8") as f:
      json.dump(items_list, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


# الشريط الجانبي
with st.sidebar:
  st.header("⚙️ إعدادات المنظومة")

  gemini_api_key = st.text_input(
      "مفتاح Gemini API:", value=gemini_default, type="password"
  )
  telegram_token = st.text_input(
      "رمز بوت تيليجرام (Token):", value=tg_tok_default, type="password"
  )
  telegram_chat_id = st.text_input(
      "معرّف تيليجرام (Chat ID):", value=tg_ch_default
  )

  if st.button("💾 حفظ المفاتيح محلياً"):
    try:
      with open("credentials.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "gemini_api_key": gemini_api_key.strip(),
                "telegram_bot_token": telegram_token.strip(),
                "telegram_chat_id": telegram_chat_id.strip(),
            },
            f,
        )
      st.toast("✅ تم حفظ المفاتيح.")
    except Exception:
      pass

  model_choice = st.selectbox(
      "نموذج الذكاء الاصطناعي:",
      options=[
          "gemini-3.5-flash-lite",
          "gemini-1.5-flash",
          "gemini-2.0-flash",
      ],
      index=0,
  )

  is_from_secrets = bool(
      st.secrets.get("GEMINI_API_KEY") if hasattr(st, "secrets") else False
  )
  if gemini_api_key:
    if is_from_secrets:
      st.markdown(
          f'<div class="status-pill status-pill-ok">🔒 المفاتيح مثبتة في'
          f' Streamlit Secrets<br>({model_choice}) - دائمة للأبد</div>',
          unsafe_allow_html=True,
      )
    else:
      st.markdown(
          f'<div class="status-pill status-pill-ok">🟢 المفتاح نشط'
          f" ({model_choice})</div>",
          unsafe_allow_html=True,
      )
  else:
    st.markdown(
        '<div class="status-pill status-pill-err">🔴 المفتاح غير مسجل</div>',
        unsafe_allow_html=True,
    )

  st.divider()
  st.header("⏱️ إعدادات الرصد والجدولة")
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

  auto_refresh = st.checkbox("🔄 تفعيل الرصد الدوري التلقائي (كل 15 دقيقة)")
  fetch_limit = st.slider(
      "الحد الأقصى لكل منصة:", min_value=10, max_value=80, value=25, step=5
  )
  send_telegram = st.checkbox("إرسال تنبيه إلى Telegram فورياً", value=True)

  st.divider()
  st.header("💾 حماية الأرشيف")
  if os.path.exists(ARCHIVE_JSON_FILE):
    with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
      st.download_button(
          "📥 تنزيل نسخة احتياطية من الأرشيف",
          f.read(),
          file_name="morocco_justice_backup.json",
          mime="application/json",
      )

st.title("⚖️ المرصد الوطني للعدالة والقضاء بالمغرب")
st.write(
    "رصد شامل ودقيق للكلمة المفتاحية عبر **الصحف والمواقع، فيسبوك، إكس، يوتيوب،"
    " وإنستغرام وتيك توك**."
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
      help="سيتم البحث عن هذه الكلمة تحديداً في كافة المنصات",
  )

start_btn = st.button("🚀 بدء الرصد الشامل للكلمة المفتاحية الآن", type="primary")


# دالة مساعدة لتحديد ساعات الفلترة وصيغة الوقت
def get_time_params(time_mode):
  if time_mode == "آخر 24 ساعة (اليوم فقط)":
    return 30, "when:1d", "d"
  elif time_mode == "آخر 7 أيام (هذا الأسبوع)":
    return 180, "when:7d", "w"
  elif time_mode == "آخر 30 يوماً (هذا الشهر)":
    return 750, "when:30d", "m"
  return 999999, "", None


# 1. محرك المواقع والصحف المغربية (باستخدام كلمتك المفتاحية حصراً)
def fetch_moroccan_sites(user_kw, time_mode, max_count=40):
  results = []
  seen = set()
  max_h, time_op, _ = get_time_params(time_mode)
  now = datetime.now(timezone.utc)
  headers = {"User-Agent": "Mozilla/5.0"}

  # استعلامات بحث تعتمد كلياً على الكلمة المفتاحية التي كتبتها
  queries = [
      f'"{user_kw}" (المغرب OR مغربية) {time_op}'.strip(),
      (
          f'"{user_kw}" (site:.ma OR site:hespress.com OR site:akhbarona.com OR'
          " site:kech24.com OR site:agadir24.info OR site:madar21.com OR"
          " site:alayam24.com OR site:assabah.ma OR site:thevoice.ma OR"
          " site:nadorcity.com OR site:goud.ma OR site:al3omk.com OR"
          f" site:alyaoum24.com OR site:rue20.com) {time_op}".strip()
      ),
      f"{user_kw} محكمة OR قضاء المغرب {time_op}".strip(),
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
        })
        seen.add(link)
        if len(results) >= max_count:
          break
    except Exception:
      pass

  # فحص خلاصات الصحف المغربية المباشرة للكلمة المفتاحية
  direct_feeds = [
      ("هسبريس مجتمع وقضاء", "https://www.hespress.com/societe/feed"),
      ("هسبريس العامة", "https://www.hespress.com/feed"),
      ("أخبارنا المغربية", "https://www.akhbarona.com/feed"),
      ("كشـ24", "https://kech24.com/feed"),
      ("أكادير 24", "https://agadir24.info/feed"),
      ("العمق المغربي", "https://al3omk.com/feed"),
      ("اليوم 24", "https://alyaoum24.com/feed"),
      ("زنقة 20", "https://rue20.com/feed"),
      ("مدار 21", "https://madar21.com/feed"),
      ("ناظورسيتي", "https://www.nadorcity.com/feed"),
  ]
  user_kw_clean = user_kw.lower().strip()
  for name, feed_url in direct_feeds:
    if len(results) >= max_count:
      break
    try:
      resp = requests.get(feed_url, headers=headers, timeout=6)
      root = ET.fromstring(resp.content)
      for item in root.findall(".//item"):
        title = (
            item.find("title").text if item.find("title") is not None else ""
        )
        desc = (
            item.find("description").text
            if item.find("description") is not None
            else ""
        )
        # التحقق من أن المقال في الخلاصة يحتوي على الكلمة المفتاحية
        full_text = f"{title} {desc}".lower()
        if user_kw_clean not in full_text and not any(
            w in full_text for w in user_kw_clean.split() if len(w) > 3
        ):
          continue

        link = item.find("link").text if item.find("link") is not None else ""
        if not link or link in seen:
          continue
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
            "platform": "مواقع وصحف",
            "source": name,
            "title": title,
            "link": link,
            "date": disp_date,
            "timestamp": ts,
            "snippet": clean_d,
        })
        seen.add(link)
        if len(results) >= max_count:
          break
    except Exception:
      pass

  return results


# 2. محرك فيديوهات يوتيوب (البحث المباشر عبر Google News لـ site:youtube.com للكلمة المفتاحية)
def fetch_youtube_posts(user_kw, time_mode, max_count=15):
  results = []
  seen = set()
  max_h, time_op, _ = get_time_params(time_mode)
  now = datetime.now(timezone.utc)
  headers = {"User-Agent": "Mozilla/5.0"}

  # استعلام Google News لجلب فيديوهات يوتيوب الدقيقة للكلمة المفتاحية
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
          "source": "قناة YouTube",
          "title": title.replace(" - YouTube", ""),
          "link": link,
          "date": disp_date,
          "timestamp": ts,
          "snippet": (
              re.sub(r"<[^>]+>", "", desc)
              or f"فيديو يوتيوب يتناول: {user_kw}"
          ),
      })
      seen.add(link)
      if len(results) >= max_count:
        break
  except Exception:
    pass

  # طريقة إضافية مباشرة من يوتيوب
  if len(results) < max_count:
    try:
      enc_yt = urllib.parse.quote(f"{user_kw} المغرب")
      yt_url = f"https://www.youtube.com/results?search_query={enc_yt}&sp=CAI%253D"
      resp = requests.get(
          yt_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8
      )
      match = re.search(r"var ytInitialData = ({.*?});</script>", resp.text)
      if match:
        data = json.loads(match.group(1))
        contents = (
            data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
        )
        for sec in contents:
          for item in sec.get("itemSectionRenderer", {}).get("contents", []):
            v = item.get("videoRenderer")
            if v:
              time_str = v.get("publishedTimeText", {}).get(
                  "simpleText", ""
              ).lower()
              # تصفية السنوات والشهور
              if any(
                  fw in time_str
                  for fw in [
                      "سنة",
                      "سنتين",
                      "سنوات",
                      "عام",
                      "عامين",
                      "شهر",
                      "أشهر",
                      "year",
                      "month",
                  ]
              ):
                continue
              vid_id = v.get("videoId")
              link = f"https://www.youtube.com/watch?v={vid_id}"
              if link in seen:
                continue
              t_title = (
                  v.get("title", {}).get("runs", [{}])[0].get("text", "فيديو")
              )
              ch_name = (
                  v.get("ownerText", {})
                  .get("runs", [{}])[0]
                  .get("text", "YouTube")
              )
              results.append({
                  "platform": "YouTube",
                  "source": f"قناة: {ch_name}",
                  "title": t_title,
                  "link": link,
                  "date": time_str or "حديثاً",
                  "timestamp": datetime.now().timestamp(),
                  "snippet": f"فيديو مصور عبر قناة {ch_name} حول {user_kw}",
              })
              seen.add(link)
              if len(results) >= max_count:
                break
    except Exception:
      pass

  return results


# 3. محرك منشورات فيسبوك (Facebook Engine للكلمة المفتاحية)
def fetch_facebook_posts(user_kw, time_mode, max_count=15):
  results = []
  seen = set()
  max_h, time_op, ddg_time = get_time_params(time_mode)
  now = datetime.now(timezone.utc)
  headers = {"User-Agent": "Mozilla/5.0"}

  # المسار الأول: عبر Google Index لـ site:facebook.com (لا يتعرض لأي حظر خوادم)
  queries = [
      f'site:facebook.com "{user_kw}" {time_op}'.strip(),
      f'facebook.com "{user_kw}" المغرب {time_op}'.strip(),
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
            "platform": "Facebook",
            "source": "صفحة فيسبوك",
            "title": title.replace(" - Facebook", ""),
            "link": link,
            "date": disp_date,
            "timestamp": ts,
            "snippet": (
                re.sub(r"<[^>]+>", "", desc)
                or f"منشور على فيسبوك يتعلق بـ {user_kw}"
            ),
        })
        seen.add(link)
        if len(results) >= max_count:
          break
    except Exception:
      pass

  # المسار الثاني: عبر DuckDuckGo كبديل
  if len(results) < max_count:
    try:
      with DDGS() as ddgs:
        q_ddg = f'site:facebook.com "{user_kw}"'
        for r in ddgs.text(q_ddg, max_results=max_count, timelimit=ddg_time):
          link = r.get("href", "")
          if not link or link in seen or "facebook.com" not in link:
            continue
          seen.add(link)
          results.append({
              "platform": "Facebook",
              "source": "منشور Facebook",
              "title": r.get("title", f"منشور فيسبوك حول {user_kw}"),
              "link": link,
              "date": f"خلال {time_mode}",
              "timestamp": datetime.now().timestamp(),
              "snippet": r.get("body", ""),
          })
          if len(results) >= max_count:
            break
    except Exception:
      pass

  return results


# 4. محرك تغريدات إكس (Twitter/X Engine للكلمة المفتاحية)
def fetch_twitter_posts(user_kw, time_mode, max_count=15):
  results = []
  seen = set()
  max_h, time_op, ddg_time = get_time_params(time_mode)
  now = datetime.now(timezone.utc)
  headers = {"User-Agent": "Mozilla/5.0"}

  # المسار الأول: عبر Google Index لـ site:x.com و site:twitter.com
  queries = [
      f'(site:x.com OR site:twitter.com) "{user_kw}" {time_op}'.strip(),
      f'twitter.com "{user_kw}" المغرب {time_op}'.strip(),
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
            "platform": "X (Twitter)",
            "source": "تغريدة على X",
            "title": title.replace(" - X", "").replace(" - Twitter", ""),
            "link": link,
            "date": disp_date,
            "timestamp": ts,
            "snippet": (
                re.sub(r"<[^>]+>", "", desc)
                or f"تغريدة على منصة X تتعلق بـ {user_kw}"
            ),
        })
        seen.add(link)
        if len(results) >= max_count:
          break
    except Exception:
      pass

  # المسار الثاني: عبر DuckDuckGo كبديل
  if len(results) < max_count:
    try:
      with DDGS() as ddgs:
        q_ddg = f'(site:x.com OR site:twitter.com) "{user_kw}"'
        for r in ddgs.text(q_ddg, max_results=max_count, timelimit=ddg_time):
          link = r.get("href", "")
          if (
              not link
              or link in seen
              or not any(d in link for d in ["x.com", "twitter.com"])
          ):
            continue
          seen.add(link)
          results.append({
              "platform": "X (Twitter)",
              "source": "تغريدة على X",
              "title": r.get("title", f"تغريدة حول {user_kw}"),
              "link": link,
              "date": f"خلال {time_mode}",
              "timestamp": datetime.now().timestamp(),
              "snippet": r.get("body", ""),
          })
          if len(results) >= max_count:
            break
    except Exception:
      pass

  return results


# 5. محرك تيك توك وإنستغرام (TikTok & Instagram Engine)
def fetch_tiktok_and_insta(user_kw, time_mode, max_count=15):
  results = []
  seen = set()
  _, time_op, _ = get_time_params(time_mode)
  headers = {"User-Agent": "Mozilla/5.0"}

  queries = [
      (
          "TikTok",
          f'site:tiktok.com "{user_kw}" (المغرب OR مغربية) {time_op}'.strip(),
      ),
      (
          "Instagram",
          f'site:instagram.com "{user_kw}" (المغرب OR مغربية) {time_op}'.strip(),
      ),
  ]
  for plat, q in queries:
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

        results.append({
            "platform": plat,
            "source": f"حساب {plat}",
            "title": title,
            "link": link,
            "date": pdate or f"خلال {time_mode}",
            "timestamp": datetime.now().timestamp(),
            "snippet": (
                re.sub(r"<[^>]+>", "", desc)
                or f"مقطع فيديو منشور على {plat} حول {user_kw}"
            ),
        })
        seen.add(link)
        if len(results) >= max_count:
          break
    except Exception:
      pass

  return results


# 6. التحليل الصارم بـ Gemini للكلمة المفتاحية المحددة حصراً
def analyze_with_gemini(title, snippet, user_kw, domain, key, model_name):
  # استبعاد صريح للدول الأخرى إلا إذا ذكر المغرب
  negative_countries = [
      "مصر",
      "الجزائر",
      "تونس",
      "السعودية",
      "العراق",
      "سوريا",
      "غزة",
      "فرنسا",
      "الكويت",
      "إسرائيل",
      "أوكرانيا",
      "روسيا",
  ]
  if any(nc in title for nc in negative_countries) and not any(
      mc in title for mc in ["المغرب", "مغربي", "مغربية"]
  ):
    return False, ""

  try:
    genai.configure(api_key=key)
    m = genai.GenerativeModel(model_name)
    prompt = f"""
أنت قاضٍ ومستشار قانوني وخبير رصد إعلامي بالمملكة المغربية.

الموضوع / الكلمة المفتاحية المطلوبة: {user_kw}
المجال الإضافي: {domain}

بيانات المادة المرصودة:
العنوان: {title}
المقتطف: {snippet}

المهمة - أجب بناءً على شرطين حاسمين معاً:
1. هل هذا الخبر يخص المملكة المغربية حصراً؟ (إذا كان خبراً دولياً أو أجنبياً أجب بـ NO).
2. هل يرتبط مباشرة بالكلمة المفتاحية المطلوبة ({user_kw}) أو الشأن القضائي/القانوني المرتبط بها في المغرب؟ (إذا لم يكن له علاقة بالموضوع المطلوب، أجب بـ NO).

إذا تطابق الشرطان معاً، أجب حصراً بـ:
YES: [جملة مركزة تلخص مضمون الخبر وعلاقته بالكلمة المفتاحية المطلوبة]
أو
NO
"""
    res = m.generate_content(prompt)
    txt = res.text.strip()
    if txt.startswith("YES"):
      return True, txt.replace("YES:", "").replace("YES", "").strip()
    return False, ""
  except Exception:
    # فلترة موضعية بديلة في حال بطء الـ API
    full_t = f"{title} {snippet}".lower()
    kw_words = [w for w in user_kw.lower().split() if len(w) > 2]
    if any(w in full_t for w in kw_words):
      return True, f"مطابق للكلمة المفتاحية: {user_kw}"
    return False, ""


def send_tg_notification(token, chat_id, item):
  msg = (
      f"⚖️ *مرصد القضاء المغربي | خبر مطابق*\n\n"
      f"🌐 *المنصة:* {item['platform']}\n"
      f"📰 *المصدر:* {item['source']}\n"
      f"📅 *التاريخ:* {item['date']}\n"
      f"📌 *العنوان:* {item['title']}\n"
      f"💡 *التحليل:* {item['ai_analysis']}\n"
      f"🔗 *الرابط:* {item['link']}"
  )
  try:
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
        timeout=8,
    )
  except Exception:
    pass


# دورة التنفيذ المعتمدة كلياً على الكلمة المفتاحية
def execute_monitoring_for_keyword(user_kw):
  st.toast(f"🔍 جارٍ رصد كافة المنصات للكلمة: '{user_kw}'...")
  raw_items = []

  # جلب متوازي لكافة المنصات بناءً على الكلمة المفتاحية
  raw_items.extend(
      fetch_moroccan_sites(user_kw, time_range, max_count=fetch_limit)
  )
  raw_items.extend(fetch_youtube_posts(user_kw, time_range, max_count=15))
  raw_items.extend(fetch_facebook_posts(user_kw, time_range, max_count=15))
  raw_items.extend(fetch_twitter_posts(user_kw, time_range, max_count=15))
  raw_items.extend(fetch_tiktok_and_insta(user_kw, time_range, max_count=15))

  conn = sqlite3.connect("morocco_justice_hub.db")
  c = conn.cursor()

  new_count = 0
  for item in raw_items:
    c.execute("SELECT link FROM items WHERE link = ?", (item["link"],))
    if c.fetchone():
      continue

    is_valid, reason = analyze_with_gemini(
        item["title"],
        item["snippet"],
        user_kw,
        target_domain,
        gemini_api_key,
        model_choice,
    )
    if is_valid:
      item["ai_analysis"] = reason
      c.execute(
          """
                INSERT INTO items (link, platform, source, title, date_published, pub_timestamp, snippet, ai_analysis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
          (
              item["link"],
              item["platform"],
              item["source"],
              item["title"],
              item["date"],
              item.get("timestamp", 0.0),
              item["snippet"],
              reason,
          ),
      )
      conn.commit()
      new_count += 1

      if send_telegram and telegram_token and telegram_chat_id:
        send_tg_notification(telegram_token, telegram_chat_id, item)

  conn.close()
  export_db_to_archive_json()
  return new_count, len(raw_items)


if start_btn:
  clean_kw = keywords_input.strip()
  if not clean_kw:
    st.warning("⚠️ يرجى كتابة كلمة مفتاحية في خانة البحث.")
  elif not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API في الشريط الجانبي أولاً.")
  else:
    with st.spinner(f"جارٍ فحص كافة المنصات للكلمة المفتاحية '{clean_kw}'..."):
      added, total_scanned = execute_monitoring_for_keyword(clean_kw)
      st.success(
          f"✅ اكتمل الفحص! تم فحص {total_scanned} مادة، وإضافة {added} خبراً"
          f" ومنشوراً يطابق الكلمة '{clean_kw}'."
      )

# واجهة العرض والتبويبات
conn = sqlite3.connect("morocco_justice_hub.db")
c = conn.cursor()
c.execute(
    "SELECT platform, source, title, link, date_published, snippet,"
    " ai_analysis, fetched_at FROM items ORDER BY pub_timestamp DESC,"
    " fetched_at DESC LIMIT 250"
)
all_records = c.fetchall()
conn.close()

news_items = [r for r in all_records if r[0] == "مواقع وصحف"]
yt_items = [r for r in all_records if r[0] == "YouTube"]
fb_items = [r for r in all_records if r[0] == "Facebook"]
x_items = [r for r in all_records if r[0] == "X (Twitter)"]
insta_tiktok_items = [r for r in all_records if r[0] in ["Instagram", "TikTok"]]

tab_news, tab_fb, tab_x, tab_yt, tab_insta, tab_stats = st.tabs([
    f"📰 الصحف والمواقع ({len(news_items)})",
    f"🟦 فيسبوك ({len(fb_items)})",
    f"⬛ منصة إكس ({len(x_items)})",
    f"📺 يوتيوب ({len(yt_items)})",
    f"🟪 إنستغرام وتيك توك ({len(insta_tiktok_items)})",
    "📊 إحصائيات المرصد",
])


def render_cards(items_list, badge_class, btn_text):
  if items_list:
    for idx, row in enumerate(items_list, 1):
      plat, src, title, link, d_pub, snip, ai_note, f_at = row
      st.markdown(
          f"""
            <div class="result-card">
                <h4>#{idx} <span class="badge {badge_class}">{plat}</span> {title}</h4>
                <div class="meta-line">
                    👤 <b>الناشر / الحساب:</b> {src} &nbsp;|&nbsp; 
                    📅 <b>تاريخ النشر:</b> <span style="font-weight: bold; color:#1e3a8a;">{d_pub}</span> &nbsp;|&nbsp; 
                    ⏱️ <b>وقت الرصد:</b> {f_at}
                </div>
                <div class="desc-box">
                    <b>📝 مقتطف المحتوى:</b><br>{snip}
                </div>
                <div class="ai-box">
                    <b>💡 التقييم القضائي (Gemini):</b> {ai_note}
                </div>
                <p><a href="{link}" target="_blank" class="action-btn">🔗 {btn_text} ➔</a></p>
            </div>
            """,
          unsafe_allow_html=True,
      )
  else:
    st.info("لا توجد منشورات مسجلة في هذا التبويب حالياً لهذا النطاق الزمني.")


with tab_news:
  st.subheader("📰 مقالات وأخبار الصحف والمواقع المغربية")
  render_cards(
      news_items, "badge-site", "قراءة المقال بالكامل من المصدر الأصلي"
  )

with tab_fb:
  st.subheader("🟦 منشورات وتفاعلات فيسبوك (Facebook)")
  render_cards(fb_items, "badge-fb", "فتح المنشور الأصلي على فيسبوك")

with tab_x:
  st.subheader("⬛ تغريدات منصة X (Twitter)")
  render_cards(x_items, "badge-x", "فتح التغريدة على منصة X")

with tab_yt:
  st.subheader("📺 الفيديوهات والتغطيات المرئية الحديثة (YouTube)")
  render_cards(yt_items, "badge-yt", "مشاهدة الفيديو على YouTube")

with tab_insta:
  st.subheader("🟪 مقاطع إنستغرام وتيك توك (Instagram & TikTok)")
  render_cards(
      insta_tiktok_items, "badge-insta", "مشاهدة المحتوى على المنصة الأصلية"
  )

with tab_stats:
  st.subheader("📊 إحصائيات المرصد وتوزيع المواد عبر المنصات")
  c1, c2, c3, c4 = st.columns(4)
  with c1:
    st.metric("إجمالي المواد المرصودة", len(all_records))
  with c2:
    st.metric("الصحف والمواقع", len(news_items))
  with c3:
    st.metric("فيسبوك و X", len(fb_items) + len(x_items))
  with c4:
    st.metric("يوتيوب والميديا", len(yt_items) + len(insta_tiktok_items))

if auto_refresh:
  time.sleep(900)
  st.rerun()
