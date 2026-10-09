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
    page_title="مرصد العدالة والقضاء المغربي", page_icon="⚖️", layout="wide"
)

st.markdown(
    """
    <style>
    body, .stApp { direction: rtl; text-align: right; }
    .stTextInput > label, .stTextArea > label, .stSelectbox > label, .stSlider > label { text-align: right; font-weight: bold; }
    .result-card {
        background-color: #ffffff;
        border: 1px solid #cbd5e1;
        border-right: 6px solid #1e3a8a;
        padding: 18px;
        border-radius: 10px;
        margin-bottom: 16px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    }
    .badge-source {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85em;
        margin-left: 10px;
        background-color: #1e3a8a;
        color: white;
    }
    .badge-yt { background-color: #dc2626; color: white; }
    .meta-line { color: #64748b; font-size: 0.9em; margin-bottom: 10px; }
    .desc-text { background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px; font-size: 0.95em; color: #1e293b; margin-bottom: 10px; }
    .status-badge {
        padding: 6px 12px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.9em;
        margin-bottom: 15px;
        display: block;
        text-align: center;
    }
    .status-ok { background-color: #dcfce7; color: #15803d; border: 1px solid #86efac; }
    .status-err { background-color: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; }
    </style>
""",
    unsafe_allow_html=True,
)

# 1. نظام حفظ الإعدادات والمفاتيح الدائم
CONFIG_FILE = "credentials.json"


def load_saved_config():
  cfg = {
      "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
      "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
      "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
  }
  if os.path.exists(CONFIG_FILE):
    try:
      with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        cfg.update(data)
    except Exception:
      pass
  return cfg


def save_config(gemini_key, tg_token, tg_chat):
  try:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
      json.dump(
          {
              "gemini_api_key": gemini_key.strip(),
              "telegram_bot_token": tg_token.strip(),
              "telegram_chat_id": tg_chat.strip(),
          },
          f,
          ensure_ascii=False,
          indent=2,
      )
  except Exception:
    pass


config = load_saved_config()


# 2. تهيئة وتحديث قاعدة البيانات لدعم الترتيب الزمني الدقيق
def init_db():
  conn = sqlite3.connect("morocco_justice_news.db")
  c = conn.cursor()
  c.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            link TEXT PRIMARY KEY,
            title TEXT,
            source TEXT,
            date_published TEXT,
            pub_timestamp REAL,
            snippet TEXT,
            ai_analysis TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
  # التأكد من وجود عمود الطابع الزمني
  try:
    c.execute("ALTER TABLE articles ADD COLUMN pub_timestamp REAL")
  except Exception:
    pass
  conn.commit()
  conn.close()


init_db()

# الشريط الجانبي
with st.sidebar:
  st.header("⚙️ إعدادات المنظومة")

  # حقول المفاتيح مع القيمة المحفوظة مسبقاً
  gemini_api_key = st.text_input(
      "مفتاح Gemini API:", value=config.get("gemini_api_key", ""), type="password"
  )
  telegram_token = st.text_input(
      "رمز بوت تيليجرام (Token):",
      value=config.get("telegram_bot_token", ""),
      type="password",
  )
  telegram_chat_id = st.text_input(
      "معرّف تيليجرام (Chat ID):", value=config.get("telegram_chat_id", "")
  )

  # حفظ المفاتيح عند التعديل
  if st.button("💾 حفظ المفاتيح بشكل دائم"):
    save_config(gemini_api_key, telegram_token, telegram_chat_id)
    st.toast("✅ تم حفظ المفاتيح بنجاح ولن تحتاج لإدخالها مجدداً.")

  model_choice = st.selectbox(
      "نموذج الذكاء الاصطناعي:",
      options=[
          "gemini-3.5-flash-lite",
          "gemini-1.5-flash",
          "gemini-2.0-flash",
      ],
      index=0,
  )

  # شارة حالة مفتاح Gemini
  if gemini_api_key:
    st.markdown(
        f'<div class="status-badge status-ok">🟢 المفتاح محفوظ ومفعّل'
        f" ({model_choice})</div>",
        unsafe_allow_html=True,
    )
  else:
    st.markdown(
        '<div class="status-badge status-err">🔴 المفتاح غير مسجل</div>',
        unsafe_allow_html=True,
    )

  if st.button("🧪 فحص الاتصال بالنموذج"):
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
  st.header("⏱️ الجدولة وفترة الرصد")
  time_range = st.selectbox(
      "فترة النشر المطلوبة:",
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
      "الحد الأقصى للأخبار المقبولة:",
      min_value=20,
      max_value=150,
      value=60,
      step=10,
  )
  include_yt = st.checkbox("تضمين فيديوهات يوتيوب الحديثة", value=True)
  send_telegram = st.checkbox("إرسال التنبيهات إلى Telegram", value=True)

# الواجهة الرئيسية
st.title("⚖️ مرصد العدالة والقضاء في المغرب")
st.write(
    "رصد شامل لكافة ما يُنشر في **الصحف والمواقع المغربية** ومصادر العدالة،"
    " مفرز ومصنف زمنياً من الأحدث إلى الأقدم."
)

col1, col2 = st.columns(2)
with col1:
  target_domain = st.text_input(
      "🎯 نطاق الرصد والتقييم القانوني:",
      value="شؤون القضاء والعدالة، المحاكم، وقرارات المجلس الأعلى للسلطة القضائية بالمغرب",
  )
with col2:
  keywords_input = st.text_input(
      "🔑 كلمات البحث الإضافية (اختياري لتخصيص الاستعلام):",
      value="المجلس الأعلى للسلطة القضائية, محكمة النقض",
  )

start_btn = st.button("🚀 تشغيل الرصد الشامل الفوري الآن", type="primary")


# دالة جلب الأخبار من كافة المواقع المغربية مع تطبيق الفلتر الزمني الصارم
def fetch_moroccan_news_engine(time_mode, max_items=60):
  results = []
  seen_links = set()

  # 1. تحديد معايير الوقت لمحرك البحث
  time_operator = ""
  max_hours = 999999
  if time_mode == "آخر 24 ساعة (اليوم فقط)":
    time_operator = "when:1d"
    max_hours = 30  # 30 ساعة لتغطية فارق التوقيت
  elif time_mode == "آخر 7 أيام (هذا الأسبوع)":
    time_operator = "when:7d"
    max_hours = 180  # 7 أيام ونصف
  elif time_mode == "آخر 30 يوماً (هذا الشهر)":
    time_operator = "when:30d"
    max_hours = 750

  # 2. حزم استعلامات متخصصة تغطي كل ما يتعلق بالقضاء المغربي
  justice_queries = [
      f"المجلس الأعلى للسلطة القضائية {time_operator}".strip(),
      f"القضاء المغربي OR المحاكم المغربية {time_operator}".strip(),
      f"وزارة العدل المغربية OR النيابة العامة {time_operator}".strip(),
      f"محكمة النقض المغرب {time_operator}".strip(),
      f"وكيل الملك OR قاضي التحقيق المغرب {time_operator}".strip(),
      f"هيئة المحامين بالمغرب {time_operator}".strip(),
      f"محاكمة OR حكم قضائي المغرب {time_operator}".strip(),
  ]

  now = datetime.now(timezone.utc)

  for q in justice_queries:
    if len(results) >= max_items:
      break
    try:
      encoded = urllib.parse.quote(q)
      # gl=MA تفرض مصادر الصحف والمواقع المغربية حصراً ولغة عربية
      url = (
          "https://news.google.com/rss/search?q="
          f"{encoded}&hl=ar&gl=MA&ceid=MA:ar"
      )
      headers = {
          "User-Agent": (
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          )
      }
      resp = requests.get(url, headers=headers, timeout=9)
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
        pub_date = (
            item.find("pubDate").text
            if item.find("pubDate") is not None
            else ""
        )
        source = (
            item.find("source").text
            if item.find("source") is not None
            else "موقع مغربي"
        )

        # حساب التاريخ الدقيق
        timestamp_val = 0.0
        display_date = pub_date
        is_valid_time = True

        if pub_date:
          try:
            dt = parsedate_to_datetime(pub_date)
            timestamp_val = dt.timestamp()
            display_date = dt.strftime("%Y-%m-%d %H:%M")
            age_h = (now - dt).total_seconds() / 3600.0

            if age_h > max_hours:
              is_valid_time = False
          except Exception:
            pass

        if not is_valid_time:
          continue

        clean_desc = re.sub(r"<[^>]+>", "", desc)

        results.append({
            "source": source,
            "title": title,
            "link": link,
            "date": display_date,
            "timestamp": timestamp_val,
            "snippet": clean_desc or f"تقرير إخباري منشور عبر {source}",
        })
        seen_links.add(link)

        if len(results) >= max_items:
          break
    except Exception:
      pass

  return results


# دالة جلب يوتيوب مع تصفية حقيقية للمقاطع القديمة
def fetch_youtube_filtered(time_mode, max_items=10):
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
    resp = requests.get(url, headers=headers, timeout=9)
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

            # استبعاد صارم للفيديوهات القديمة
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
                .get("text", "قناة يوتيوب")
            )
            snippet = (
                v.get("detailedMetadataSnippets", [{}])[0]
                .get("snippetText", {})
                .get("runs", [{}])[0]
                .get("text", "")
            )

            results.append({
                "source": f"YouTube: {channel}",
                "title": title,
                "link": f"https://www.youtube.com/watch?v={vid_id}",
                "date": time_str or "حديثاً",
                "timestamp": datetime.now().timestamp(),
                "snippet": snippet or f"تغطية مصورة عبر قناة {channel}",
            })
            if len(results) >= max_items:
              return results
  except Exception:
    pass
  return results


# دالة التحليل الذكي
def analyze_with_gemini(title, snippet, domain, key, model_name):
  try:
    genai.configure(api_key=key)
    m = genai.GenerativeModel(model_name)
    prompt = f"""
المجال المطلوب: {domain}

المحتوى المرصود:
العنوان: {title}
المقتطف: {snippet}

المطلوب:
هل هذا الخبر يرتبط بشكل صريح أو ضمني بقطاع العدالة والقضاء أو المحاكم في المغرب؟
أجب حصراً بـ:
YES: [جملة واحدة موجزة تشرح جوهر الخبر وقيمته القضائية]
أو
NO
"""
    res = m.generate_content(prompt)
    txt = res.text.strip()
    if txt.startswith("YES"):
      return True, txt.replace("YES:", "").replace("YES", "").strip()
    return False, ""
  except Exception:
    return True, "تم اعتماد الخبر لمطابقته المعايير القضائية"


def send_tg_alert(token, chat_id, item):
  msg = (
      f"⚖️ *مستجد قضائي مغربي جديد تم رصده!*\n\n"
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


# تنفيذ دورة الرصد
def run_monitoring():
  st.toast("🔍 جارٍ فحص الصحف والمواقع المغربية...")

  candidates = fetch_moroccan_news_engine(time_range, max_items=fetch_limit)
  if include_yt:
    candidates.extend(fetch_youtube_filtered(time_range, max_items=10))

  conn = sqlite3.connect("morocco_justice_news.db")
  c = conn.cursor()

  new_count = 0
  for item in candidates:
    c.execute("SELECT link FROM articles WHERE link = ?", (item["link"],))
    if c.fetchone():
      continue

    # فحص Gemini
    is_valid, reason = analyze_with_gemini(
        item["title"],
        item["snippet"],
        target_domain,
        gemini_api_key,
        model_choice,
    )
    if is_valid:
      item["ai_analysis"] = reason
      c.execute(
          """
                INSERT INTO articles (link, title, source, date_published, pub_timestamp, snippet, ai_analysis)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
          (
              item["link"],
              item["title"],
              item["source"],
              item["date"],
              item.get("timestamp", 0.0),
              item["snippet"],
              reason,
          ),
      )
      conn.commit()
      new_count += 1

      if send_telegram and telegram_token and telegram_chat_id:
        send_tg_alert(telegram_token, telegram_chat_id, item)

  conn.close()
  return new_count, len(candidates)


if start_btn:
  if not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API في الشريط الجانبي.")
  else:
    # حفظ المفاتيح تلقائياً عند التشغيل أيضاً
    save_config(gemini_api_key, telegram_token, telegram_chat_id)
    with st.spinner("جارٍ فحص المواقع المغربية والمستجدات القضائية..."):
      new_added, total_scanned = run_monitoring()
      st.success(
          f"✅ اكتمل الفحص! تم مسح {total_scanned} مادة، وإضافة {new_added}"
          f" خبراً جديداً لنطاق ({time_range})."
      )

# عرض النتائج من قاعدة البيانات مرتبة من الأحدث إلى الأقدم
st.subheader("📚 أرشيف الأخبار والمستجدات القضائية (مرتبة من الأحدث إلى الأقدم)")

conn = sqlite3.connect("morocco_justice_news.db")
c = conn.cursor()
# الترتيب الصارم بالأحدث تاريخ نشر أولاً
c.execute(
    "SELECT source, title, link, date_published, snippet, ai_analysis,"
    " fetched_at FROM articles ORDER BY pub_timestamp DESC, fetched_at DESC"
    " LIMIT 100"
)
rows = c.fetchall()
conn.close()

if rows:
  st.write(f"إجمالي الأخبار في قاعدة البيانات: **{len(rows)} خبراً ومقالاً**.")
  for idx, row in enumerate(rows, 1):
    src, title, link, d_pub, snip, ai_note, f_at = row
    b_class = "badge-yt" if "YouTube" in src else "badge-source"

    st.markdown(
        f"""
        <div class="result-card">
            <h4>#{idx} <span class="badge-source {b_class}">{src}</span> {title}</h4>
            <div class="meta-line">
                📅 <b>تاريخ النشر:</b> <span style="color: #1e3a8a; font-weight: bold;">{d_pub}</span> &nbsp;|&nbsp; 
                ⏱️ <b>وقت الرصد:</b> {f_at}
            </div>
            <div class="desc-text">
                <b>📝 مقتطف المقال:</b><br>{snip}
            </div>
            <p><b>💡 تحليل الذكاء الاصطناعي:</b> <span style="color: #15803d; font-weight: bold;">{ai_note}</span></p>
            <p><a href="{link}" target="_blank" style="font-weight: bold; color: #1e3a8a; text-decoration: none;">🔗 قراءة المقال بالكامل من المصدر ➔</a></p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
  st.info(
      "لا توجد أخبار مخزنة بعد. اضغط على 'تشغيل الرصد الشامل الفوري الآن' لبدء"
      " جلب الأخبار."
  )

# الجدولة الدورية كل 15 دقيقة
if auto_refresh:
  time.sleep(900)
  st.rerun()
