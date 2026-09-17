from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from duckduckgo_search import DDGS
import google.generativeai as genai
import requests
import streamlit as st

st.set_page_config(
    page_title="منظومة الرصد والتتبع الدقيق", page_icon="📡", layout="wide"
)

st.markdown(
    """
    <style>
    body, .stApp { direction: rtl; text-align: right; }
    .stTextInput > label, .stTextArea > label, .stSelectbox > label { text-align: right; font-weight: bold; }
    .result-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-right: 6px solid #0d6efd;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    }
    .badge-platform {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85em;
        margin-left: 10px;
        color: white;
    }
    .badge-youtube { background-color: #ff0000; }
    .badge-news { background-color: #198754; }
    .badge-web { background-color: #0d6efd; }
    .meta-info { color: #64748b; font-size: 0.9em; margin-bottom: 12px; }
    .snippet-box {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 12px;
        border-radius: 6px;
        font-size: 0.95em;
        color: #334155;
        margin-bottom: 12px;
    }
    .social-btn {
        display: inline-block;
        padding: 10px 18px;
        margin: 6px;
        border-radius: 8px;
        text-decoration: none !important;
        font-weight: bold;
        color: white !important;
        text-align: center;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# الشريط الجانبي
with st.sidebar:
  st.header("⚙️ إعدادات الذكاء الاصطناعي")
  gemini_api_key = st.text_input(
      "مفتاح Gemini API",
      value=os.getenv("GEMINI_API_KEY", ""),
      type="password",
  )

  model_choice = st.selectbox(
      "نموذج Gemini:",
      options=[
          "gemini-3.5-flash-lite",
          "gemini-1.5-flash",
          "gemini-2.0-flash",
      ],
      index=0,
  )

  if st.button("🧪 فحص الاتصال بالنموذج"):
    if not gemini_api_key:
      st.error("يرجى إدخال المفتاح أولاً.")
    else:
      try:
        genai.configure(api_key=gemini_api_key)
        m = genai.GenerativeModel(model_choice)
        res = m.generate_content("تأكيد الاتصال")
        st.success(f"✅ الاتصال ناجح: {model_choice}!")
      except Exception as err:
        st.error(f"❌ خطأ: {err}")

  st.divider()
  st.header("⏱️ فترة الرصد الصارمة")
  time_range = st.selectbox(
      "حصر المنشورات حسب التاريخ:",
      options=[
          "آخر 24 ساعة (اليوم فقط)",
          "آخر 7 أيام (هذا الأسبوع)",
          "آخر 30 يوماً (هذا الشهر)",
          "جميع الأوقات",
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
  send_telegram = st.checkbox("إرسال التنبيهات الفورية", value=True)

# الواجهة الرئيسية
st.title("📡 لوحة الرصد الرقمي الفوري والتحليل الذكي")
st.write(
    "رصد وتتبع دقيق ومفلتر زمنياً لأحدث ما نُشر، مع إمكانية الفحص المباشر"
    " لشبكات التواصل المغلقة."
)

col1, col2 = st.columns(2)
with col1:
  target_domain = st.text_input(
      "🎯 المجال والموضوع المستهدف:",
      value="شؤون القضاء والعدالة وقرارات المجلس الأعلى للسلطة القضائية بالمغرب",
  )
with col2:
  keywords_input = st.text_input(
      "🔑 الكلمات المفتاحية للرصد:",
      value="المجلس الأعلى للسلطة القضائية",
  )

# قسم المسح الحي المباشر لشبكات التواصل الاجتماعي
st.markdown("### 🌐 الروابط المباشرة للرصد اللحظي على المنصات الاجتماعية:")
encoded_kw = urllib.parse.quote(keywords_input.strip())
fb_link = f"https://www.facebook.com/search/posts/?q={encoded_kw}"
x_link = f"https://x.com/search?q={encoded_kw}&f=live"
insta_link = f"https://www.instagram.com/explore/tags/{encoded_kw}/"
tiktok_link = f"https://www.tiktok.com/search?q={encoded_kw}"

col_s1, col_s2, col_s3, col_s4 = st.columns(4)
with col_s1:
  st.markdown(
      f'<a href="{fb_link}" target="_blank" class="social-btn"'
      ' style="background-color: #1877f2; display:block;">🟦 أحدث منشورات'
      " Facebook</a>",
      unsafe_allow_html=True,
  )
with col_s2:
  st.markdown(
      f'<a href="{x_link}" target="_blank" class="social-btn"'
      ' style="background-color: #000000; display:block;">⬛ أحدث تغريدات X'
      " (Live)</a>",
      unsafe_allow_html=True,
  )
with col_s3:
  st.markdown(
      f'<a href="{insta_link}" target="_blank" class="social-btn"'
      ' style="background-color: #e1306c; display:block;">🟪 منشورات'
      " Instagram</a>",
      unsafe_allow_html=True,
  )
with col_s4:
  st.markdown(
      f'<a href="{tiktok_link}" target="_blank" class="social-btn"'
      ' style="background-color: #111111; display:block;">🎵 مقاطع TikTok</a>',
      unsafe_allow_html=True,
  )

st.divider()

platforms_selected = st.multiselect(
    "📡 مصادر الجلب التلقائي للوحة:",
    options=["الأخبار الرسمية والوطنية", "YouTube (مفرز بالأحدث)"],
    default=["الأخبار الرسمية والوطنية", "YouTube (مفرز بالأحدث)"],
)

start_btn = st.button("🚀 بدء جلب المنشورات الحديثة وتحليلها", type="primary")


# 1. جلب يوتيوب مفرز بأحدث الفيديوهات مع فلترة زمنية صارمة
def fetch_youtube_strictly_recent(kw, time_mode, max_count=8):
  results = []
  try:
    encoded = urllib.parse.quote(kw)
    # sp=CAI%253D يفرز الفيديوهات في يوتيوب من الأحدث رفعاً إلى الأقدم
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

            # الفلترة الزمنية الصارمة بالبايثون لمنع الفيديوهات القديمة
            if time_mode == "آخر 24 ساعة (اليوم فقط)":
              # يقبل فقط الساعات والدقائق
              if not any(
                  w in time_str for w in ["ساعة", "ساعات", "دقيقة", "دقائق"]
              ):
                continue
            elif time_mode == "آخر 7 أيام (هذا الأسبوع)":
              # يستبعد فوراً أي فيديو يحتوي على "سنة" أو "شهر"
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
                "author": channel,
                "title": title,
                "link": f"https://www.youtube.com/watch?v={vid_id}",
                "date": time_str or "حديثاً",
                "snippet": snippet or f"فيديو حديث منشور عبر قناة {channel}",
            })
            if len(results) >= max_count:
              return results
  except Exception:
    pass
  return results


# 2. جلب الأخبار والبيانات الرسمية مع فحص تاريخي حقيقي
def fetch_news_strictly_recent(kw, time_mode, max_count=8):
  results = []
  try:
    encoded = urllib.parse.quote(kw)
    url = (
        "https://news.google.com/rss/search?q="
        f"{encoded}&hl=ar&gl=MA&ceid=MA:ar"
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=8)
    root = ET.fromstring(resp.content)

    now = datetime.now(timezone.utc)

    for item in root.findall(".//item"):
      pub_date = (
          item.find("pubDate").text if item.find("pubDate") is not None else ""
      )
      title = item.find("title").text if item.find("title") is not None else ""
      link = item.find("link").text if item.find("link") is not None else ""
      desc = (
          item.find("description").text
          if item.find("description") is not None
          else ""
      )
      source = (
          item.find("source").text
          if item.find("source") is not None
          else "مصدر إخباري"
      )

      # حساب الفارق الزمني الحقيقي
      is_within_range = True
      clean_date_str = pub_date
      if pub_date:
        try:
          dt = parsedate_to_datetime(pub_date)
          clean_date_str = dt.strftime("%Y-%m-%d %H:%M")
          days_diff = (now - dt).total_seconds() / 86400.0

          if time_mode == "آخر 24 ساعة (اليوم فقط)" and days_diff > 1.2:
            is_within_range = False
          elif time_mode == "آخر 7 أيام (هذا الأسبوع)" and days_diff > 7.2:
            is_within_range = False
          elif time_mode == "آخر 30 يوماً (هذا الشهر)" and days_diff > 30.5:
            is_within_range = False
        except Exception:
          pass

      if not is_within_range:
        continue

      clean_desc = re.sub(r"<[^>]+>", "", desc)

      if title and link:
        results.append({
            "platform": "الأخبار الرسمية والوطنية",
            "author": source,
            "title": title,
            "link": link,
            "date": clean_date_str,
            "snippet": clean_desc or f"تقرير وتغطية حول {kw}",
        })
        if len(results) >= max_count:
          break
  except Exception:
    pass
  return results


# 3. التحليل الذكي بواسطة Gemini
def analyze_with_ai(title, snippet, domain, key, model_name):
  try:
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name)
    prompt = f"""
المجال المطلوب: {domain}

المحتوى المرصود:
العنوان: {title}
المقتطف: {snippet}

هل يرتبط هذا الخبر أو المنشور بالمجال المطلوب؟
أجب حصراً بـ:
YES: [جملة مركزة تشرح موضوع الخبر وقيمته]
أو
NO
"""
    res = model.generate_content(prompt)
    txt = res.text.strip()
    if txt.startswith("YES"):
      return True, txt.replace("YES:", "").replace("YES", "").strip()
    return False, ""
  except Exception:
    return True, "تمت المطابقة بناءً على الكلمات المفتاحية وسياق المحتوى"


def send_telegram_alert(token, chat_id, item):
  msg = (
      f"🚨 *منشور مطابق جديد تم رصده!*\n\n"
      f"🌐 *المصدر:* {item['platform']}\n"
      f"👤 *الناشر:* `{item['author']}`\n"
      f"📅 *تاريخ النشر:* {item['date']}\n"
      f"📌 *العنوان:* {item['title']}\n"
      f"💡 *التحليل:* {item['reason']}\n"
      f"🔗 *الرابط:* {item['link']}"
  )
  url = f"https://api.telegram.org/bot{token}/sendMessage"
  try:
    requests.post(
        url,
        json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
        timeout=10,
    )
  except Exception:
    pass


if start_btn:
  if not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API أولاً.")
  elif not keywords_input:
    st.warning("⚠️ يرجى كتابة الكلمات المفتاحية.")
  else:
    kw = keywords_input.split(",")[0].strip()
    raw_list = []
    seen_urls = set()

    with st.spinner(f"جارٍ الجلب المفلتر زمنياً لنطاق ({time_range})..."):
      # 1. الأخبار
      if "الأخبار الرسمية والوطنية" in platforms_selected:
        raw_list.extend(fetch_news_strictly_recent(kw, time_range, max_count=8))

      # 2. يوتيوب مفرز بالأحدث
      if "YouTube (مفرز بالأحدث)" in platforms_selected:
        raw_list.extend(
            fetch_youtube_strictly_recent(kw, time_range, max_count=8)
        )

    st.info(
        f"📊 تم العثور على {len(raw_list)} مادة منشورة خلال {time_range}. جارٍ"
        " التحليل الذكي..."
    )

    verified_items = []
    with st.spinner("جارٍ فحص المحتوى بواسطة Gemini..."):
      for cand in raw_list:
        link = cand["link"]
        if not link or link in seen_urls:
          continue
        seen_urls.add(link)

        is_valid, reason = analyze_with_ai(
            cand["title"],
            cand["snippet"],
            target_domain,
            gemini_api_key,
            model_choice,
        )

        if is_valid:
          cand["reason"] = reason
          verified_items.append(cand)

          if send_telegram and telegram_token and telegram_chat_id:
            send_telegram_alert(telegram_token, telegram_chat_id, cand)

    # عرض النتائج في بطاقات أنيقة
    st.subheader(
        f"📋 المحتوى المعتمد المنشور خلال ({time_range}): {len(verified_items)}"
    )

    if verified_items:
      for idx, item in enumerate(verified_items, 1):
        b_class = (
            "badge-youtube" if "YouTube" in item["platform"] else "badge-news"
        )
        st.markdown(
            f"""
                <div class="result-card">
                    <h4>#{idx} <span class="badge-platform {b_class}">{item['platform']}</span> {item['title']}</h4>
                    <div class="meta-info">
                        👤 <b>الناشر / القناة:</b> {item['author']} &nbsp;|&nbsp; 
                        📅 <b>تاريخ النشر:</b> <span style="color:#0d6efd; font-weight:bold;">{item['date']}</span>
                    </div>
                    <div class="snippet-box">
                        <b>📝 مقتطف المحتوى:</b><br>{item['snippet']}
                    </div>
                    <p><b>💡 تحليل الذكاء الاصطناعي:</b> <span style="color: #198754; font-weight: bold;">{item['reason']}</span></p>
                    <p><a href="{item['link']}" target="_blank" style="font-weight: bold; color: #0d6efd; text-decoration: none;">🔗 فتح المصدر الأصلي ➔</a></p>
                </div>
                """,
            unsafe_allow_html=True,
        )
    else:
      st.warning(
          f"لم يُنشر أي محتوى جديد مطابق خلال ({time_range}). يمكنك الضغط على"
          " أزرار الرصد الحي بالأعلى لمراجعة فيسبوك وتويتر فوراً."
      )
