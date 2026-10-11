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

# 1. جلب المفاتيح مع إعطاء الأولوية القصوى لخزنة Streamlit Secrets الدائمة
ARCHIVE_JSON_FILE = "articles_archive.json"


def get_credentials():
  # محاولة القراءة من أسرار Streamlit أولاً
  gemini_k = ""
  tg_tok = ""
  tg_ch = ""

  try:
    gemini_k = st.secrets.get("GEMINI_API_KEY", "")
    tg_tok = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    tg_ch = st.secrets.get("TELEGRAM_CHAT_ID", "")
  except Exception:
    pass

  # بدائل البيئة أو الملف المحلي إن وجدت
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


# 2. تهيئة قاعدة البيانات المحلية واسترجاع الأرشيف المحفوظ
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

  # إذا كان هناك ملف أرشيف محفوظ على القرص أو المستودع، نقوم باستيراده تلقائياً
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


# حفظ نسخة احتياطية من قاعدة البيانات إلى ملف JSON لتفادي فقدانها
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

  # حفظ محلي إضافي
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

  # شارة حالة المفاتيح
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
      "الحد الأقصى للأخبار المجلوبة:",
      min_value=20,
      max_value=120,
      value=60,
      step=10,
  )
  send_telegram = st.checkbox("إرسال تنبيه إلى Telegram فورياً", value=True)

  st.divider()
  st.header("💾 حماية واستعادة الأرشيف")
  st.caption("احفظ أرشيف الأخبار لضمان عدم تصفيره عند سكون الموقع:")

  # زر تحميل الأرشيف كملف JSON
  if os.path.exists(ARCHIVE_JSON_FILE):
    with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
      archive_bytes = f.read()
    st.download_button(
        label="📥 تنزيل نسخة احتياطية من الأرشيف",
        data=archive_bytes,
        file_name="morocco_justice_backup.json",
        mime="application/json",
    )

  # خيار رفع واستعادة أرشيف سابق
  uploaded_backup = st.file_uploader(
      "📤 استعادة أرشيف سابق (ملف JSON):", type=["json"]
  )
  if uploaded_backup is not None:
    try:
      imported_items = json.load(uploaded_backup)
      conn = sqlite3.connect("morocco_justice_hub.db")
      c = conn.cursor()
      for it in imported_items:
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
      conn.close()
      export_db_to_archive_json()
      st.success("✅ تمت استعادة كافة الأخبار بنجاح إلى قاعدة البيانات!")
      st.rerun()
    except Exception as e:
      st.error(f"خطأ أثناء استعادة الأرشيف: {e}")

st.title("⚖️ المرصد الوطني للعدالة والقضاء بالمغرب")
st.write(
    "رصد وتتبع إخباري دائم ومستمر لقطاع العدالة والقضاء، محمي من فقدان"
    " البيانات."
)

col1, col2 = st.columns(2)
with col1:
  target_domain = st.text_input(
      "🎯 نطاق التقييم والفلترة:",
      value="شؤون القضاء والعدالة والمحاكم والنيابة العامة بالمملكة المغربية حصراً",
  )
with col2:
  keywords_input = st.text_input(
      "🔑 استعلام البحث الرئيسي:",
      value="المجلس الأعلى للسلطة القضائية, القضاء المغربي, محكمة النقض",
  )

start_btn = st.button("🚀 تشغيل الرصد الشامل والتحديث الآن", type="primary")


# 1. محرك المواقع والصحف المغربية
def fetch_moroccan_sites(time_mode, max_count=60):
  results = []
  seen = set()
  time_hours = 999999
  time_op = ""
  if time_mode == "آخر 24 ساعة (اليوم فقط)":
    time_hours = 30
    time_op = "when:1d"
  elif time_mode == "آخر 7 أيام (هذا الأسبوع)":
    time_hours = 180
    time_op = "when:7d"
  elif time_mode == "آخر 30 يوماً (هذا الشهر)":
    time_hours = 750
    time_op = "when:30d"

  moroccan_direct_feeds = [
      ("أخبارنا المغربية (Akhbarona)", "https://www.akhbarona.com/feed"),
      ("أكادير 24 (Agadir24)", "https://agadir24.info/feed"),
      ("كشـ24 (Kech24)", "https://kech24.com/feed"),
      ("الأيام 24 (Alayam24)", "https://www.alayam24.com/feed"),
      ("مدار 21 (Madar21)", "https://madar21.com/feed"),
      ("صباح أكادير (SabahAgadir)", "https://sabahagadir.ma/feed"),
      ("كود (Goud)", "https://www.goud.ma/feed"),
      ("جريدة الصباح (Assabah)", "https://assabah.ma/feed"),
      ("صوت المغرب (TheVoice.ma)", "https://thevoice.ma/feed"),
      ("ناظورسيتي (NadorCity)", "https://www.nadorcity.com/feed"),
      ("هسبريس مجتمع وقضاء", "https://www.hespress.com/societe/feed"),
      ("هسبريس العامة", "https://www.hespress.com/feed"),
      ("العمق المغربي", "https://al3omk.com/feed"),
      ("اليوم 24", "https://alyaoum24.com/feed"),
      ("زنقة 20 (Rue20)", "https://rue20.com/feed"),
      ("Le360 المغرب", "https://ar.le360.ma/rss/"),
      ("برلمان.كوم", "https://www.barlamane.com/feed/"),
      ("طنجة 24", "https://tanja24.com/feed/"),
  ]

  target_sites_query = (
      "(site:kech24.com OR site:agadir24.info OR site:madar21.com OR"
      " site:alayam24.com OR site:assabah.ma OR site:thevoice.ma OR"
      " site:nadorcity.com OR site:goud.ma OR site:akhbarona.com) (قضاء OR"
      f" محكمة OR محاكمة) {time_op}".strip()
  )

  queries = [
      target_sites_query,
      f"المجلس الأعلى للسلطة القضائية {time_op}".strip(),
      f"القضاء المغربي OR المحاكم المغربية {time_op}".strip(),
      f"وزارة العدل المغربية OR النيابة العامة {time_op}".strip(),
      f"محكمة النقض المغرب {time_op}".strip(),
      f"وكيل الملك OR قاضي التحقيق المغرب {time_op}".strip(),
      f"هيئة المحامين بالمغرب {time_op}".strip(),
      f"محاكمة OR حكم قضائي المغرب {time_op}".strip(),
  ]

  now = datetime.now(timezone.utc)
  headers = {"User-Agent": "Mozilla/5.0"}

  # فحص الخلاصات المباشرة
  for name, feed_url in moroccan_direct_feeds:
    if len(results) >= max_count:
      break
    try:
      resp = requests.get(feed_url, headers=headers, timeout=6)
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
            if (now - dt).total_seconds() / 3600.0 > time_hours:
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

  # فحص استعلامات Google News المغرب
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
            if (now - dt).total_seconds() / 3600.0 > time_hours:
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

  return results


# 2. محرك يوتيوب مع فلترة إيجابية صارمة
def fetch_youtube_strictly_recent(time_mode, max_count=12):
  results = []
  if time_mode == "جميع الأوقات":
    return results

  try:
    url = "https://www.youtube.com/results?search_query=القضاء+المغربي+المجلس+الاعلى+للسلطة+القضائية&sp=CAI%253D"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        ),
        "Accept-Language": "ar,en;q=0.9",
    }
    resp = requests.get(url, headers=headers, timeout=8)
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
        items = sec.get("itemSectionRenderer", {}).get("contents", [])
        for item in items:
          v = item.get("videoRenderer")
          if v:
            time_str = v.get("publishedTimeText", {}).get(
                "simpleText", ""
            ).lower()

            # الفلترة الإيجابية الصارمة
            forbidden_words = [
                "سنة",
                "سنتين",
                "سنوات",
                "عام",
                "عامين",
                "أعوام",
                "شهر",
                "شهرين",
                "أشهر",
                "شهور",
                "أسبوع",
                "أسبوعين",
                "أسابيع",
                "year",
                "years",
                "month",
                "months",
                "week",
                "weeks",
            ]
            if any(fw in time_str for fw in forbidden_words):
              continue

            if time_mode == "آخر 24 ساعة (اليوم فقط)":
              if not any(
                  w in time_str
                  for w in [
                      "دقيقة",
                      "دقائق",
                      "ساعة",
                      "ساعات",
                      "minute",
                      "hour",
                      "hours",
                  ]
              ):
                continue

            if time_mode == "آخر 7 أيام (هذا الأسبوع)":
              valid_week = any(
                  w in time_str
                  for w in [
                      "دقيقة",
                      "دقائق",
                      "ساعة",
                      "ساعات",
                      "يوم",
                      "يومان",
                      "أيام",
                      "أمس",
                      "day",
                      "days",
                      "yesterday",
                  ]
              )
              if not valid_week:
                continue

            vid_id = v.get("videoId")
            title = (
                v.get("title", {}).get("runs", [{}])[0].get("text", "فيديو")
            )
            channel = (
                v.get("ownerText", {})
                .get("runs", [{}])[0]
                .get("text", "قناة يوتيوب")
            )
            snippet = (
                v.get("detailedMetadataSnippets", [{}])[0]
                .get("snippetText", {})
                .get("runs", [{}])[0]
                .get("text", "")
            )

            results.append({
                "platform": "YouTube",
                "source": f"YouTube: {channel}",
                "title": title,
                "link": f"https://www.youtube.com/watch?v={vid_id}",
                "date": time_str,
                "timestamp": datetime.now().timestamp(),
                "snippet": snippet or f"تغطية مصورة عبر قناة {channel}",
            })
            if len(results) >= max_count:
              return results
  except Exception:
    pass
  return results


# 3. محرك منشورات فيسبوك
def fetch_facebook_posts(time_mode, max_count=10):
  results = []
  time_limit = (
      "d"
      if "24 ساعة" in time_mode
      else ("w" if "7 أيام" in time_mode else None)
  )
  queries = [
      'site:facebook.com "المجلس الأعلى للسلطة القضائية"',
      'site:facebook.com "القضاء المغربي" OR "محكمة النقض المغرب"',
  ]
  seen = set()
  try:
    with DDGS() as ddgs:
      for q in queries:
        if len(results) >= max_count:
          break
        for r in ddgs.text(q, max_results=max_count, timelimit=time_limit):
          link = r.get("href", "")
          if not link or "facebook.com" not in link or link in seen:
            continue
          seen.add(link)

          title = r.get("title", "")
          body = r.get("body", "")

          author = "صفحة فيسبوك"
          m = re.search(r"facebook\.com/([^/?#]+)", link)
          if m and m.group(1) not in ["photo", "watch", "story", "share"]:
            author = f"صفحة: {m.group(1)}"

          results.append({
              "platform": "Facebook",
              "source": author,
              "title": title or "منشور فيسبوك حول القضاء المغربي",
              "link": link,
              "date": f"خلال {time_mode}",
              "timestamp": datetime.now().timestamp(),
              "snippet": body or "منشور متداول على منصة فيسبوك بالمغرب",
          })
          if len(results) >= max_count:
            break
        time.sleep(0.5)
  except Exception:
    pass
  return results


# 4. محرك تغريدات إكس (Twitter/X)
def fetch_twitter_posts(time_mode, max_count=10):
  results = []
  time_limit = (
      "d"
      if "24 ساعة" in time_mode
      else ("w" if "7 أيام" in time_mode else None)
  )
  queries = [
      '(site:x.com OR site:twitter.com) "المجلس الأعلى للسلطة القضائية"',
      '(site:x.com OR site:twitter.com) "القضاء المغربي"',
  ]
  seen = set()
  try:
    with DDGS() as ddgs:
      for q in queries:
        if len(results) >= max_count:
          break
        for r in ddgs.text(q, max_results=max_count, timelimit=time_limit):
          link = r.get("href", "")
          if (
              not link
              or not any(d in link for d in ["x.com", "twitter.com"])
              or link in seen
          ):
            continue
          seen.add(link)

          title = r.get("title", "")
          body = r.get("body", "")

          author = "تغريدة على X"
          m = re.search(r"(?:x\.com|twitter\.com)/([^/?#]+)", link)
          if m and m.group(1) not in ["home", "explore", "search"]:
            author = f"@{m.group(1)}"

          results.append({
              "platform": "X (Twitter)",
              "source": author,
              "title": title or "تغريدة على منصة X حول القضاء المغربي",
              "link": link,
              "date": f"خلال {time_mode}",
              "timestamp": datetime.now().timestamp(),
              "snippet": body or "تغريدة متداولة على منصة X بالمغرب",
          })
          if len(results) >= max_count:
            break
        time.sleep(0.5)
  except Exception:
    pass
  return results


# 5. محرك تيك توك وإنستغرام
def fetch_tiktok_and_insta(time_mode, max_count=10):
  results = []
  seen = set()
  queries = [
      (
          "TikTok",
          'site:tiktok.com "المجلس الأعلى للسلطة القضائية" OR "القضاء المغربي"',
      ),
      (
          "Instagram",
          'site:instagram.com "المجلس الأعلى للسلطة القضائية" OR "القضاء'
          ' المغربي"',
      ),
  ]
  try:
    with DDGS() as ddgs:
      for plat, q in queries:
        for r in ddgs.text(q, max_results=max_count // 2):
          link = r.get("href", "")
          if not link or link in seen:
            continue
          seen.add(link)

          title = r.get("title", "")
          body = r.get("body", "")

          results.append({
              "platform": plat,
              "source": f"حساب {plat}",
              "title": title or f"محتوى على {plat} حول القضاء المغربي",
              "link": link,
              "date": f"خلال {time_mode}",
              "timestamp": datetime.now().timestamp(),
              "snippet": body or f"مقطع متداول على منصة {plat}",
          })
        time.sleep(0.5)
  except Exception:
    pass
  return results


# 6. التحليل الصارم بـ Gemini
def analyze_strictly_with_gemini(title, snippet, key, model_name):
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
أنت قاضٍ ومستشار قانوني ورئيس تحرير لمرصد متخصص حصرياً في شؤون القضاء والعدالة بالمملكة المغربية.

المحتوى المرصود:
العنوان: {title}
المقتطف: {snippet}

المهمة:
تحقق بناءً على شرطين حاسمين معاً:
1. هل هذا المحتوى يخص المملكة المغربية حصراً؟ (إذا كان دولياً أو أجنبياً أجب بـ NO).
2. هل يتعلق مباشرة أو ضمناً بقطاع العدالة، القضاء، المحاكم، النيابة العامة، المجلس الأعلى للسلطة القضائية، القضاة، المحامين، أو قضايا وتحقيقات بمحاكم المغرب؟ (إذا كان خبراً عاماً أو سياسياً أو حوادث عادية بدون بعد قضائي، أجب بـ NO).

إذا تطابق الشرطان، أجب بـ:
YES: [جملة مركزة تلخص الجانب القضائي والقانوني المغربي للمحتوى]
أو
NO
"""
    res = m.generate_content(prompt)
    txt = res.text.strip()
    if txt.startswith("YES"):
      return True, txt.replace("YES:", "").replace("YES", "").strip()
    return False, ""
  except Exception:
    morocco_keywords = [
        "المغرب",
        "المغربي",
        "المغربية",
        "الرباط",
        "الدار البيضاء",
        "فاس",
        "مراكش",
        "طنجة",
        "أكادير",
        "الناظور",
        "تطوان",
    ]
    justice_keywords = [
        "قضاء",
        "محكمة",
        "محاكم",
        "المجلس الأعلى",
        "السلطة القضائية",
        "النيابة العامة",
        "وكيل الملك",
        "محام",
        "قاضي",
        "محاكمة",
        "وزارة العدل",
    ]
    is_morocco = any(k in f"{title} {snippet}" for k in morocco_keywords)
    is_justice = any(k in f"{title} {snippet}" for k in justice_keywords)
    if is_morocco and is_justice:
      return True, "تم التحقق من صلة المحتوى بالقضاء المغربي"
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


# تنفيذ دورة الرصد وحفظ الأرشيف تلقائياً
def execute_full_monitoring():
  st.toast("🔍 جارٍ مسح الصحف، فيسبوك، إكس، تيك توك، وإنستغرام...")
  raw_items = []

  raw_items.extend(fetch_moroccan_sites(time_range, max_count=fetch_limit))
  raw_items.extend(fetch_youtube_strictly_recent(time_range, max_count=12))
  raw_items.extend(fetch_facebook_posts(time_range, max_count=10))
  raw_items.extend(fetch_twitter_posts(time_range, max_count=10))
  raw_items.extend(fetch_tiktok_and_insta(time_range, max_count=10))

  conn = sqlite3.connect("morocco_justice_hub.db")
  c = conn.cursor()

  new_count = 0
  for item in raw_items:
    c.execute("SELECT link FROM items WHERE link = ?", (item["link"],))
    if c.fetchone():
      continue

    is_valid, reason = analyze_strictly_with_gemini(
        item["title"], item["snippet"], gemini_api_key, model_choice
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

  # تحديث ملف الأرشيف الثابت لمنع التصفير
  export_db_to_archive_json()

  return new_count, len(raw_items)


if start_btn:
  if not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API في الشريط الجانبي أولاً.")
  else:
    with st.spinner("جارٍ فحص المنصات ومطابقة المحتوى بذكاء..."):
      added, total_scanned = execute_full_monitoring()
      st.success(
          f"✅ اكتمل الفحص! تم فحص {total_scanned} مادة عبر مختلف المنصات،"
          f" وإضافة {added} مادة قضائية جديدة لنطاق ({time_range})."
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
  st.subheader(
      "📰 مقالات وأخبار المواقع والصحف المغربية (مرتبة من الأحدث إلى الأقدم)"
  )
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
  st.subheader("📺 الفيديوهات والتغطيات القضائية الحديثة (YouTube)")
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
