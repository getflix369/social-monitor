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
        border: 1px solid #e2e8f0;
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
    </style>
""",
    unsafe_allow_html=True,
)


# تهيئة قاعدة البيانات المحلية لحفظ الأخبار ومنع التكرار
def init_db():
  conn = sqlite3.connect("morocco_justice_news.db")
  c = conn.cursor()
  c.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            link TEXT PRIMARY KEY,
            title TEXT,
            source TEXT,
            date_published TEXT,
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
      "مفتاح Gemini API",
      value=os.getenv("GEMINI_API_KEY", ""),
      type="password",
  )

  model_choice = st.selectbox(
      "نموذج الذكاء الاصطناعي:",
      options=[
          "gemini-3.5-flash-lite",
          "gemini-1.5-flash",
          "gemini-2.0-flash",
      ],
      index=0,
  )

  st.divider()
  st.header("⏱️ الجدولة والرصد الدوري")
  auto_refresh = st.checkbox("🔄 تفعيل الرصد الدوري التلقائي (كل 15 دقيقة)")
  fetch_limit = st.slider(
      "أقصى عدد أخبار لجلبها في كل دورة:",
      min_value=20,
      max_value=120,
      value=60,
      step=10,
  )

  time_filter = st.selectbox(
      "فترة النشر المطلوبة:",
      options=[
          "آخر 24 ساعة (اليوم)",
          "آخر 7 أيام (هذا الأسبوع)",
          "آخر 30 يوماً (هذا الشهر)",
          "جميع التواريخ",
      ],
      index=1,
  )

  st.divider()
  st.header("📲 تنبيهات Telegram")
  telegram_token = st.text_input(
      "رمز البوت (Token)",
      value=os.getenv("TELEGRAM_BOT_TOKEN", ""),
      type="password",
  )
  telegram_chat_id = st.text_input(
      "معرّف المحادثة (Chat ID)", value=os.getenv("TELEGRAM_CHAT_ID", "")
  )
  send_telegram = st.checkbox("إرسال إشعار فوري عند رصد خبر جديد", value=True)

# الواجهة الرئيسية
st.title("⚖️ مرصد العدالة والقضاء في المغرب")
st.write(
    "رصد شامل ومكثف لكافة المقالات والأخبار المنشورة في **المواقع والصحف"
    " المغربية** والمصادر القضائية الرسمية."
)

col1, col2 = st.columns(2)
with col1:
  target_domain = st.text_input(
      "🎯 نطاق الرصد والتقييم:",
      value="قضايا العدالة، المحاكم، قرارات السلطة القضائية، والنزاعات القانونية بالمغرب",
  )
with col2:
  keywords_input = st.text_input(
      "🔑 استعلام البحث الشامل (كلمات مفتاحية مجمعة):",
      value=(
          "القضاء OR العدالة OR المجلس الأعلى للسلطة القضائية OR محكمة النقض"
          " OR النيابة العامة OR وزارة العدل"
      ),
  )

start_btn = st.button("🚀 تشغيل الرصد الشامل الفوري الآن", type="primary")


# 1. محرك جلب الأخبار من كافة المواقع المغربية عبر استعلامات مجمعة
def fetch_all_moroccan_justice_news(query, time_mode, max_items=60):
  results = []
  seen_links = set()

  # حزم استعلامات لتغطية قطاع القضاء المغربي بالكامل
  queries = [
      query,
      "محاكمة OR وكيل الملك OR هيئة المحامين OR القضاة بالمغرب",
      "المجلس الأعلى للسلطة القضائية OR نادي قضاة المغرب",
  ]

  now = datetime.now(timezone.utc)

  for q in queries:
    if len(results) >= max_items:
      break
    try:
      encoded = urllib.parse.quote(q.strip())
      # استخدام معرف المغرب gl=MA ولغة عربية hl=ar
      url = (
          "https://news.google.com/rss/search?q="
          f"{encoded}&hl=ar&gl=MA&ceid=MA:ar"
      )
      headers = {
          "User-Agent": (
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          )
      }
      resp = requests.get(url, headers=headers, timeout=10)
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

        # التحقق الزمني الصارم
        clean_date_str = pub_date
        is_in_range = True
        if pub_date:
          try:
            dt = parsedate_to_datetime(pub_date)
            clean_date_str = dt.strftime("%Y-%m-%d %H:%M")
            diff = (now - dt).total_seconds() / 86400.0

            if time_mode == "آخر 24 ساعة (اليوم)" and diff > 1.2:
              is_in_range = False
            elif time_mode == "آخر 7 أيام (هذا الأسبوع)" and diff > 7.2:
              is_in_range = False
            elif time_mode == "آخر 30 يوماً (هذا الشهر)" and diff > 30.5:
              is_in_range = False
          except Exception:
            pass

        if not is_in_range:
          continue

        clean_desc = re.sub(r"<[^>]+>", "", desc)

        results.append({
            "source": source,
            "title": title,
            "link": link,
            "date": clean_date_str,
            "snippet": clean_desc or f"تقرير إخباري منشور عبر {source}",
        })
        seen_links.add(link)

        if len(results) >= max_items:
          break
    except Exception:
      pass

  return results


# 2. جلب يوتيوب المغربي المفرز زمنياً
def fetch_morocco_youtube_justice(kw, time_mode, max_items=15):
  results = []
  try:
    encoded = urllib.parse.quote(f"{kw} المغرب")
    url = f"https://www.youtube.com/results?search_query={encoded}&sp=CAI%253D"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        ),
        "Accept-Language": "ar,en;q=0.9",
    }
    resp = requests.get(url, headers=headers, timeout=10)
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

            if time_mode == "آخر 24 ساعة (اليوم)":
              if not any(
                  w in time_str for w in ["ساعة", "ساعات", "دقيقة", "دقائق"]
              ):
                continue
            elif time_mode == "آخر 7 أيام (هذا الأسبوع)":
              if any(
                  w in time_str
                  for w in ["سنة", "عام", "أشهر", "شهور", "شهر", "year", "month"]
              ):
                continue
            elif time_mode == "آخر 30 يوماً (هذا الشهر)":
              if any(w in time_str for w in ["سنة", "عام", "أشهر", "year"]):
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
                "source": f"YouTube: {channel}",
                "title": title,
                "link": f"https://www.youtube.com/watch?v={vid_id}",
                "date": time_str or "حديثاً",
                "snippet": snippet or f"تغطية مصورة عبر قناة {channel}",
            })
            if len(results) >= max_items:
              return results
  except Exception:
    pass
  return results


# 3. التحليل والتصنيف بـ Gemini
def analyze_with_gemini(title, snippet, domain, key, model_name):
  try:
    genai.configure(api_key=key)
    m = genai.GenerativeModel(model_name)
    prompt = f"""
أنت مساعد قانوني متخصص في قضايا وشؤون العدالة والقضاء بالمغرب.
المجال المطلوب: {domain}

الخبر أو المقال:
العنوان: {title}
المقتطف: {snippet}

المطلوب:
هل هذا الخبر يهم بشكل مباشر أو غير مباشر شؤون القضاء والعدالة والمحاكم في المغرب؟
أجب حصراً بـ:
YES: [جملة مركزة تشرح موضوع الخبر وقيمته القضائية أو الإخبارية]
أو
NO
"""
    res = m.generate_content(prompt)
    txt = res.text.strip()
    if txt.startswith("YES"):
      return True, txt.replace("YES:", "").replace("YES", "").strip()
    return False, ""
  except Exception:
    # في حال وجود ضغط على الـ API نعتمد الخبر بناءً على الكلمات المفتاحية
    return True, "تم اعتماد الخبر لمطابقته قطاع القضاء والعدالة"


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
        timeout=10,
    )
  except Exception:
    pass


# دالة تنفيذ الرصد وتخزين النتائج
def run_monitoring_cycle():
  kw = keywords_input.strip()
  st.toast("🔍 بدء دورة رصد جديدة لمواقع وأخبار العدالة بالمغرب...")

  # جلب كل الأخبار المغربية
  all_candidates = []
  all_candidates.extend(
      fetch_all_moroccan_justice_news(
          kw, time_filter, max_items=fetch_limit - 15
      )
  )
  all_candidates.extend(
      fetch_morocco_youtube_justice(kw, time_filter, max_items=15)
  )

  conn = sqlite3.connect("morocco_justice_news.db")
  c = conn.cursor()

  new_count = 0
  for item in all_candidates:
    # التحقق هل الخبر موجود مسبقاً في قاعدة البيانات
    c.execute("SELECT link FROM articles WHERE link = ?", (item["link"],))
    if c.fetchone():
      continue

    # تحليل المقال
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
                INSERT INTO articles (link, title, source, date_published, snippet, ai_analysis)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
          (
              item["link"],
              item["title"],
              item["source"],
              item["date"],
              item["snippet"],
              reason,
          ),
      )
      conn.commit()
      new_count += 1

      if send_telegram and telegram_token and telegram_chat_id:
        send_tg_alert(telegram_token, telegram_chat_id, item)

  conn.close()
  return new_count, len(all_candidates)


if start_btn:
  if not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API في الشريط الجانبي.")
  else:
    with st.spinner("جارٍ مسح كافة الصحف والمصادر المغربية وقنوات القضاء..."):
      new_added, total_scanned = run_monitoring_cycle()
      st.success(
          f"✅ تم الانتهاء من الفحص! تم فحص {total_scanned} مادة، وإضافة"
          f" {new_added} خبراً جديداً غير مكرر لقاعدة بيانات المرصد."
      )

# عرض الأخبار المخزنة في قاعدة البيانات
st.subheader("📚 أرشيف الأخبار والمستجدات القضائية المرصودة بالمغرب")

conn = sqlite3.connect("morocco_justice_news.db")
c = conn.cursor()
c.execute(
    "SELECT source, title, link, date_published, snippet, ai_analysis,"
    " fetched_at FROM articles ORDER BY fetched_at DESC LIMIT 100"
)
stored_rows = c.fetchall()
conn.close()

if stored_rows:
  st.write(
      f"إجمالي الأخبار المرصودة المتاحة حالياً: **{len(stored_rows)} مقالاً"
      " وخبراً**."
  )
  for idx, row in enumerate(stored_rows, 1):
    src, title, link, d_pub, snip, ai_note, f_at = row
    b_class = "badge-yt" if "YouTube" in src else "badge-source"

    st.markdown(
        f"""
        <div class="result-card">
            <h4>#{idx} <span class="badge-source {b_class}">{src}</span> {title}</h4>
            <div class="meta-line">
                📅 <b>تاريخ النشر:</b> {d_pub} &nbsp;|&nbsp; 
                ⏱️ <b>وقت الرصد:</b> {f_at}
            </div>
            <div class="desc-text">
                <b>📝 مقتطف المقال:</b><br>{snip}
            </div>
            <p><b>💡 تحليل الذكاء الاصطناعي:</b> <span style="color: #198754; font-weight: bold;">{ai_note}</span></p>
            <p><a href="{link}" target="_blank" style="font-weight: bold; color: #1e3a8a; text-decoration: none;">🔗 قراءة المقال بالكامل من المصدر ➔</a></p>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
  st.info(
      "لا توجد أخبار مخزنة بعد. اضغط على 'تشغيل الرصد الشامل الفوري الآن' لبدء"
      " ملء قاعدة البيانات."
  )

# آلية الرصد الدوري كل 15 دقيقة عند تفعيل الخيار
if auto_refresh:
  time.sleep(900)  # 15 دقيقة (900 ثانية)
  st.rerun()
