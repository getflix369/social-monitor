from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import os
import re
import sqlite3
import time
import urllib.parse
import xml.etree.ElementTree as ET
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
    .social-link-btn {
        display: block;
        padding: 12px;
        margin: 5px 0;
        border-radius: 8px;
        text-align: center;
        color: white !important;
        font-weight: bold;
        text-decoration: none !important;
    }
    @media (max-width: 768px) {
        .stApp { padding: 8px !important; }
        .result-card { padding: 14px !important; }
        h1 { font-size: 1.5rem !important; }
        div[data-baseweb="tab-list"] {
            overflow-x: auto !important;
            flex-wrap: nowrap !important;
        }
        button[data-baseweb="tab"] {
            font-size: 0.9rem !important;
            padding: 8px 12px !important;
            white-space: nowrap !important;
        }
    }
    </style>
""",
    unsafe_allow_html=True,
)

CONFIG_FILE = "credentials.json"


def load_config():
  cfg = {
      "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
      "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
      "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
  }
  if os.path.exists(CONFIG_FILE):
    try:
      with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg.update(json.load(f))
    except Exception:
      pass
  return cfg


def save_config(gemini_k, tg_tok, tg_ch):
  try:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
      json.dump(
          {
              "gemini_api_key": gemini_k.strip(),
              "telegram_bot_token": tg_tok.strip(),
              "telegram_chat_id": tg_ch.strip(),
          },
          f,
          ensure_ascii=False,
          indent=2,
      )
  except Exception:
    pass


saved_cfg = load_config()


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
  conn.close()


init_db()

# الشريط الجانبي
with st.sidebar:
  st.header("⚙️ إعدادات المنظومة")

  gemini_api_key = st.text_input(
      "مفتاح Gemini API:",
      value=saved_cfg.get("gemini_api_key", ""),
      type="password",
  )
  telegram_token = st.text_input(
      "رمز بوت تيليجرام (Token):",
      value=saved_cfg.get("telegram_bot_token", ""),
      type="password",
  )
  telegram_chat_id = st.text_input(
      "معرّف تيليجرام (Chat ID):", value=saved_cfg.get("telegram_chat_id", "")
  )

  if st.button("💾 حفظ المفاتيح بشكل دائم"):
    save_config(gemini_api_key, telegram_token, telegram_chat_id)
    st.toast("✅ تم حفظ المفاتيح بنجاح ولن يُطلب إدخالها ثانية.")

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
        f'<div class="status-pill status-pill-ok">🟢 المفتاح محفوظ ومفعّل'
        f" ({model_choice})</div>",
        unsafe_allow_html=True,
    )
  else:
    st.markdown(
        '<div class="status-pill status-pill-err">🔴 المفتاح غير مسجل</div>',
        unsafe_allow_html=True,
    )

  if st.button("🧪 اختبار صلاحية المفتاح"):
    if not gemini_api_key:
      st.error("يرجى إدخال المفتاح أولاً.")
    else:
      try:
        genai.configure(api_key=gemini_api_key)
        m = genai.GenerativeModel(model_choice)
        res = m.generate_content("اختبار")
        st.success(f"✅ الاتصال سليم بالنموذج: {model_choice}")
      except Exception as err:
        st.error(f"❌ خطأ في الاتصال: {err}")

  st.divider()
  st.header("⏱️ إعدادات الرصد")
  time_range = st.selectbox(
      "النطاق الزمني للنشر:",
      options=[
          "آخر 24 ساعة (اليوم فقط)",
          "آخر 7 أيام (هذا الأسبوع)",
          "آخر 30 يوماً (هذا الشهر)",
          "جميع الأوقات",
      ],
      index=0,
  )

  auto_refresh = st.checkbox("🔄 تفعيل الرصد الدوري التلقائي (كل 15 دقيقة)")
  fetch_limit = st.slider(
      "الحد الأقصى للأخبار المجلوبة:",
      min_value=30,
      max_value=200,
      value=80,
      step=10,
  )
  send_telegram = st.checkbox("إرسال تنبيه إلى Telegram فورياً", value=True)

  st.divider()
  with st.expander("🌐 شبكة المواقع المغربية المشمولة (18+ موقعاً)"):
    st.caption(
        "• أخبارنا (Akhbarona)\n• أكادير 24 (Agadir24)\n• كشـ24 (Kech24)\n•"
        " الأيام 24 (Alayam24)\n• مدار 21 (Madar21)\n• صباح أكادير"
        " (SabahAgadir)\n• كود (Goud)\n• جريدة الصباح (Assabah)\n• صوت المغرب"
        " (TheVoice.ma)\n• ناظورسيتي (NadorCity)\n• هسبريس (Hespress)\n• العمق"
        " المغربي (Al3omk)\n• اليوم 24 (Alyaoum24)\n• زنقة 20 (Rue20)\n• Le360"
        " المغرب\n• برلمان.كوم (Barlamane)\n• طنجة 24 (Tanja24)"
    )

st.title("⚖️ المرصد الوطني للعدالة والقضاء بالمغرب")
st.write(
    "رصد شامل لكافة ما يُنشر في **الصحف والمواقع المغربية الوطنية والجهوية**"
    " وقنوات العدالة الرسمية."
)

col1, col2 = st.columns(2)
with col1:
  target_domain = st.text_input(
      "🎯 نطاق التقييم والفلترة:",
      value="شؤون القضاء والعدالة والمحاكم والنيابة العامة بالمملكة المغربية حصراً",
  )
with col2:
  keywords_input = st.text_input(
      "🔑 كلمات البحث الإضافية (اختياري):",
      value="المجلس الأعلى للسلطة القضائية, محكمة النقض",
  )

start_btn = st.button("🚀 تشغيل الرصد الشامل والتحديث الآن", type="primary")


# 1. محرك التغطيات المباشرة للمواقع المغربية (خلاصات RSS المباشرة + الاستعلامات المخصصة)
def fetch_moroccan_sites_content(time_mode, max_count=80):
  results = []
  seen_links = set()

  time_hours = 999999
  time_operator = ""
  if time_mode == "آخر 24 ساعة (اليوم فقط)":
    time_hours = 30
    time_operator = "when:1d"
  elif time_mode == "آخر 7 أيام (هذا الأسبوع)":
    time_hours = 180
    time_operator = "when:7d"
  elif time_mode == "آخر 30 يوماً (هذا الشهر)":
    time_hours = 750
    time_operator = "when:30d"

  # قائمة تغذيات RSS المباشرة الشاملة للمواقع المطلوبة
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

  # استعلام مخصص يستهدف أسماء النطاقات المحددة بالاسم
  target_sites_query = (
      "(site:kech24.com OR site:agadir24.info OR site:madar21.com OR"
      " site:alayam24.com OR site:assabah.ma OR site:thevoice.ma OR"
      " site:nadorcity.com OR site:goud.ma OR site:sabahagadir.ma OR"
      " site:akhbarona.com) (قضاء OR محكمة OR محاكمة OR عدالة OR 'وكيل الملك')"
      f" {time_operator}".strip()
  )

  general_morocco_queries = [
      target_sites_query,
      f"المجلس الأعلى للسلطة القضائية {time_operator}".strip(),
      f"القضاء المغربي OR المحاكم المغربية {time_operator}".strip(),
      f"وزارة العدل المغربية OR النيابة العامة {time_operator}".strip(),
      f"محكمة النقض المغرب {time_operator}".strip(),
      f"وكيل الملك OR قاضي التحقيق المغرب {time_operator}".strip(),
      f"هيئة المحامين بالمغرب {time_operator}".strip(),
      f"محاكمة OR حكم قضائي المغرب {time_operator}".strip(),
  ]

  now = datetime.now(timezone.utc)
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }

  # أولاً: فحص خلاصات المواقع المباشرة
  for name, feed_url in moroccan_direct_feeds:
    if len(results) >= max_count:
      break
    try:
      resp = requests.get(feed_url, headers=headers, timeout=6)
      root = ET.fromstring(resp.content)
      for item in root.findall(".//item"):
        link = item.find("link").text if item.find("link") is not None else ""
        if not link or link in seen_links:
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
        seen_links.add(link)
        if len(results) >= max_count:
          break
    except Exception:
      pass

  # ثانياً: فحص استعلامات Google News المغربية
  for q in general_morocco_queries:
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
        if not link or link in seen_links:
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
        seen_links.add(link)
        if len(results) >= max_count:
          break
    except Exception:
      pass

  return results


# 2. محرك جلب يوتيوب المغربي المفرز زمنياً
def fetch_moroccan_youtube(time_mode, max_count=10):
  results = []
  if time_mode == "جميع الأوقات":
    return results
  try:
    url = "https://www.youtube.com/results?search_query=القضاء+المغربي+المحكمة+المجلس+الاعلى+للسلطة+القضائية&sp=CAI%253D"
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

            if any(
                w in time_str
                for w in ["سنة", "عام", "أشهر", "شهور", "شهر", "year", "month"]
            ):
              continue
            if time_mode == "آخر 24 ساعة (اليوم فقط)" and not any(
                w in time_str for w in ["ساعة", "ساعات", "دقيقة", "دقائق"]
            ):
              continue

            vid_id = v.get("videoId")
            title = (
                v.get("title", {}).get("runs", [{}])[0].get("text", "فيديو")
            )
            channel = (
                v.get("ownerText", {})
                .get("runs", [{}])[0]
                .get("text", "قناة مغربية")
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
                "date": time_str or "حديثاً",
                "timestamp": datetime.now().timestamp(),
                "snippet": snippet or f"تغطية مصورة عبر قناة {channel}",
            })
            if len(results) >= max_count:
              return results
  except Exception:
    pass
  return results


# 3. التحليل الصارم بـ Gemini (مغربي + قضائي حصراً)
def analyze_with_gemini_strictly(title, snippet, key, model_name):
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

بيانات المادة:
العنوان: {title}
المقتطف: {snippet}

المهمة - أجب بناءً على شرطين حاسمين معاً:
1. هل هذا الخبر يخص المملكة المغربية حصراً؟ (إذا كان خبراً دولياً أو أجنبياً أجب بـ NO).
2. هل يتعلق مباشرة أو ضمناً بقطاع العدالة، القضاء، المحاكم، النيابة العامة، المجلس الأعلى للسلطة القضائية، القضاة، المحامين، أو قضايا وتحقيقات بمحاكم المغرب؟ (إذا كان خبراً سياسياً عاماً أو رياضياً أو حوادث عادية بدون بعد قضائي، أجب بـ NO).

إذا تطابق الشرطان معاً، أجب حصراً بـ:
YES: [جملة مركزة تلخص الجانب القضائي والقانوني المغربي للخبر]
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
        "سلا",
        "مكناس",
        "وجدة",
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
        "استئناف",
        "نقض",
        "محاكمة",
        "حكم قضائي",
        "وزارة العدل",
    ]
    is_morocco = any(
        k in f"{title} {snippet}" for k in morocco_keywords
    ) or any(
        k in title
        for k in [
            "المجلس الأعلى للسلطة القضائية",
            "نادي قضاة",
            "كشـ24",
            "أكادير 24",
            "أخبارنا",
            "ناظورسيتي",
        ]
    )
    is_justice = any(k in f"{title} {snippet}" for k in justice_keywords)
    if is_morocco and is_justice:
      return True, "تم التحقق من صلة الخبر بالقضاء المغربي"
    return False, ""


def send_tg_notification(token, chat_id, item):
  msg = (
      f"⚖️ *مرصد القضاء المغربي | خبر مطابق*\n\n"
      f"📰 *المصدر:* {item['source']}\n"
      f"📅 *تاريخ النشر:* {item['date']}\n"
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


def execute_monitoring():
  st.toast("🔍 جارٍ مسح الصحف المغربية المحددة وقنوات القضاء...")
  raw_items = []
  raw_items.extend(fetch_moroccan_sites_content(time_range, max_count=80))
  raw_items.extend(fetch_moroccan_youtube(time_range, max_count=10))

  conn = sqlite3.connect("morocco_justice_hub.db")
  c = conn.cursor()

  new_count = 0
  for item in raw_items:
    c.execute("SELECT link FROM items WHERE link = ?", (item["link"],))
    if c.fetchone():
      continue

    is_valid, reason = analyze_with_gemini_strictly(
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
  return new_count, len(raw_items)


if start_btn:
  if not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API في الشريط الجانبي أولاً.")
  else:
    save_config(gemini_api_key, telegram_token, telegram_chat_id)
    with st.spinner("جارٍ فحص المواقع المغربية ومطابقة المحتوى بذكاء..."):
      added, total_scanned = execute_monitoring()
      st.success(
          f"✅ اكتمل الفحص! تم فحص {total_scanned} مادة، وإضافة {added} خبراً"
          f" قضائياً جديداً لنطاق ({time_range})."
      )

# واجهة العرض
conn = sqlite3.connect("morocco_justice_hub.db")
c = conn.cursor()
c.execute(
    "SELECT platform, source, title, link, date_published, snippet,"
    " ai_analysis, fetched_at FROM items ORDER BY pub_timestamp DESC,"
    " fetched_at DESC LIMIT 200"
)
all_records = c.fetchall()
conn.close()

news_items = [r for r in all_records if r[0] == "مواقع وصحف"]
yt_items = [r for r in all_records if r[0] == "YouTube"]

tab_news, tab_yt, tab_fb, tab_x, tab_insta, tab_stats = st.tabs([
    f"📰 الصحف والمواقع المغربية ({len(news_items)})",
    f"📺 يوتيوب ({len(yt_items)})",
    "🟦 فيسبوك (Facebook)",
    "⬛ منصة إكس (Twitter)",
    "🟪 إنستغرام وتيك توك",
    "📊 إحصائيات المرصد والمصادر",
])

with tab_news:
  st.subheader(
      "📰 مقالات وأخبار المواقع والصحف المغربية (مرتبة من الأحدث إلى الأقدم)"
  )
  if news_items:
    for idx, row in enumerate(news_items, 1):
      _, src, title, link, d_pub, snip, ai_note, f_at = row
      st.markdown(
          f"""
            <div class="result-card">
                <h4>#{idx} <span class="badge badge-site">{src}</span> {title}</h4>
                <div class="meta-line">
                    📅 <b>تاريخ النشر:</b> <span style="color: #1e3a8a; font-weight: bold;">{d_pub}</span> &nbsp;|&nbsp; 
                    ⏱️ <b>وقت الرصد:</b> {f_at}
                </div>
                <div class="desc-box">
                    <b>📝 مقتطف المقال:</b><br>{snip}
                </div>
                <div class="ai-box">
                    <b>💡 التقييم القضائي (Gemini):</b> {ai_note}
                </div>
                <p><a href="{link}" target="_blank" class="action-btn">🔗 قراءة المقال بالكامل من المصدر الأصلي ➔</a></p>
            </div>
            """,
          unsafe_allow_html=True,
      )
  else:
    st.info(
        "لا توجد مقالات مسجلة حالياً. اضغط على زر 'تشغيل الرصد الشامل والتحديث"
        " الآن'."
    )

with tab_yt:
  st.subheader("📺 الفيديوهات والتغطيات القضائية الحديثة (YouTube)")
  if yt_items:
    for idx, row in enumerate(yt_items, 1):
      _, src, title, link, d_pub, snip, ai_note, f_at = row
      st.markdown(
          f"""
            <div class="result-card">
                <h4>#{idx} <span class="badge badge-yt">YouTube</span> {title}</h4>
                <div class="meta-line">
                    👤 <b>القناة:</b> {src.replace('YouTube: ', '')} &nbsp;|&nbsp; 
                    📅 <b>تاريخ النشر:</b> <span style="color: #dc2626; font-weight: bold;">{d_pub}</span>
                </div>
                <div class="desc-box">
                    <b>📝 ملخص الفيديو:</b><br>{snip}
                </div>
                <div class="ai-box">
                    <b>💡 التحليل القضائي:</b> {ai_note}
                </div>
                <p><a href="{link}" target="_blank" class="action-btn" style="background-color: #dc2626;">▶️ مشاهدة الفيديو على YouTube ➔</a></p>
            </div>
            """,
          unsafe_allow_html=True,
      )
  else:
    st.info("لا توجد مقاطع يوتيوب حديثة مسجلة في هذا النطاق الزمني.")

with tab_fb:
  st.subheader("🟦 رصد منشورات وتفاعلات فيسبوك (Facebook)")
  fb_kw = urllib.parse.quote(
      "المجلس الأعلى للسلطة القضائية OR القضاء المغربي"
  )
  st.markdown(
      f"""
    <div style="background-color:#f0f2f5; padding:20px; border-radius:10px; margin-bottom:15px;">
        <h4>🔍 روابط الاستعلام الحي اللحظي على فيسبوك المغرب:</h4>
        <a href="https://www.facebook.com/search/posts/?q={fb_kw}" target="_blank" class="social-link-btn" style="background-color: #1877f2;">
            🔎 فتح أحدث منشورات فيسبوك حول القضاء والعدالة بالمغرب (مباشر)
        </a>
    </div>
    """,
      unsafe_allow_html=True,
  )

with tab_x:
  st.subheader("⬛ رصد التغريدات اللحظية على منصة X (Twitter)")
  x_kw = urllib.parse.quote("القضاء المغربي OR المحاكم المغربية")
  st.markdown(
      f"""
    <div style="background-color:#f8fafc; padding:20px; border-radius:10px; border:1px solid #e2e8f0;">
        <h4>⚡ بحث التغريدات اللحظي (Live Feed):</h4>
        <a href="https://x.com/search?q={x_kw}&f=live" target="_blank" class="social-link-btn" style="background-color: #000000;">
            🐦 استعراض أحدث التغريدات اللحظية حول القضاء المغربي
        </a>
    </div>
    """,
      unsafe_allow_html=True,
  )

with tab_insta:
  st.subheader("🟪 إنستغرام وتيك توك")
  c_in1, c_in2 = st.columns(2)
  with c_in1:
    st.markdown(
        f"""
        <div style="background-color:#fdf2f8; padding:15px; border-radius:10px; border:1px solid #fbcfe8;">
            <h4>📸 Instagram</h4>
            <a href="https://www.instagram.com/explore/tags/{urllib.parse.quote('القضاء_المغربي')}/" target="_blank" class="social-link-btn" style="background-color: #e1306c;">
                وسم #القضاء_المغربي
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )
  with c_in2:
    st.markdown(
        f"""
        <div style="background-color:#f1f5f9; padding:15px; border-radius:10px; border:1px solid #cbd5e1;">
            <h4>🎵 TikTok</h4>
            <a href="https://www.tiktok.com/search?q={urllib.parse.quote('القضاء المغربي')}" target="_blank" class="social-link-btn" style="background-color: #111111;">
                مقاطع تيك توك: القضاء المغربي
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

with tab_stats:
  st.subheader("📊 إحصائيات المرصد والمصادر المغطاة")
  col_m1, col_m2, col_m3 = st.columns(3)
  with col_m1:
    st.metric("إجمالي المواد المرصودة", len(all_records))
  with col_m2:
    st.metric("مقالات الصحف والمواقع", len(news_items))
  with col_m3:
    st.metric("فيديوهات يوتيوب", len(yt_items))

  if all_records:
    st.divider()
    st.write("📈 **توزيع الأخبار حسب المصادر والمواقع المغربية:**")
    source_counts = {}
    for r in all_records:
      s = r[1]
      source_counts[s] = source_counts.get(s, 0) + 1

    sorted_sources = sorted(
        source_counts.items(), key=lambda x: x[1], reverse=True
    )
    for s_name, count in sorted_sources:
      st.write(f"- **{s_name}**: {count} مقالاً مسجلاً")

if auto_refresh:
  time.sleep(900)
  st.rerun()
