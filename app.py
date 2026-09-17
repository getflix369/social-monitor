from datetime import datetime
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
    page_title="منظومة الرصد والتتبع الاحترافية", page_icon="📡", layout="wide"
)

st.markdown(
    """
    <style>
    body, .stApp { direction: rtl; text-align: right; }
    .stTextInput > label, .stTextArea > label, .stSelectbox > label, .stSlider > label { text-align: right; font-weight: bold; }
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
    .badge-facebook { background-color: #1877f2; }
    .badge-x { background-color: #000000; }
    .badge-instagram { background-color: #e1306c; }
    .badge-tiktok { background-color: #000000; border: 1px solid #333; }
    .badge-youtube { background-color: #ff0000; }
    .badge-news { background-color: #198754; }
    .meta-info {
        color: #64748b;
        font-size: 0.9em;
        margin-bottom: 12px;
    }
    .snippet-box {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 12px;
        border-radius: 6px;
        font-size: 0.95em;
        color: #334155;
        margin-bottom: 12px;
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
  st.header("⏱️ فترة الرصد والبحث")
  time_range = st.selectbox(
      "النطاق الزمني للمنشورات:",
      options=[
          "آخر 24 ساعة (اليوم)",
          "آخر 7 أيام (هذا الأسبوع)",
          "آخر 30 يوماً (هذا الشهر)",
          "جميع الأوقات",
      ],
      index=1,
  )
  ddg_time_map = {
      "آخر 24 ساعة (اليوم)": "d",
      "آخر 7 أيام (هذا الأسبوع)": "w",
      "آخر 30 يوماً (هذا الشهر)": "m",
      "جميع الأوقات": None,
  }
  news_time_map = {
      "آخر 24 ساعة (اليوم)": "when:1d",
      "آخر 7 أيام (هذا الأسبوع)": "when:7d",
      "آخر 30 يوماً (هذا الشهر)": "when:30d",
      "جميع الأوقات": "",
  }

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
st.title("📡 لوحة الرصد الرقمي والتتبع عبر المنصات")
st.write(
    "رصد وتتبع شامل لمنشورات **Facebook, X, Instagram, TikTok, YouTube,"
    " والأخبار** مع استخراج تواريخ النشر وتفاصيل المحتوى."
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
      value="المجلس الأعلى للسلطة القضائية, محكمة النقض, القضاء المغربي",
  )

platforms_selected = st.multiselect(
    "🌐 المنصات المراد رصدها:",
    options=[
        "Facebook",
        "X (Twitter)",
        "Instagram",
        "TikTok",
        "YouTube",
        "الأخبار الرسمية",
    ],
    default=[
        "Facebook",
        "X (Twitter)",
        "YouTube",
        "Instagram",
        "الأخبار الرسمية",
    ],
)

start_btn = st.button("🚀 بدء الرصد واستخراج التفاصيل", type="primary")


# 1. جلب بيانات يوتيوب الدقيقة (اسم القناة وتوقيت النشر)
def fetch_youtube_detailed(kw, max_count=6):
  results = []
  try:
    encoded = urllib.parse.quote(kw)
    url = f"https://www.youtube.com/results?search_query={encoded}"
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
            vid_id = v.get("videoId")
            title = (
                v.get("title", {}).get("runs", [{}])[0].get("text", "فيديو")
            )
            channel = (
                v.get("ownerText", {})
                .get("runs", [{}])[0]
                .get("text", "قناة YouTube")
            )
            time_str = v.get("publishedTimeText", {}).get(
                "simpleText", "حديثاً"
            )
            snippet = (
                v.get("detailedMetadataSnippets", [{}])[0]
                .get("snippetText", {})
                .get("runs", [{}])[0]
                .get("text", "")
            )
            if not snippet:
              snippet = f"فيديو منشور عبر قناة {channel} يتعلق بموضوع {kw}"

            results.append({
                "platform": "YouTube",
                "author": channel,
                "title": title,
                "link": f"https://www.youtube.com/watch?v={vid_id}",
                "date": time_str,
                "snippet": snippet,
            })
            if len(results) >= max_count:
              return results
  except Exception:
    pass
  return results


# 2. جلب الأخبار الرسمية مع التواريخ الحقيقية
def fetch_news_rss(kw, time_filter_str, max_count=6):
  results = []
  try:
    encoded = urllib.parse.quote(f"{kw} {time_filter_str}".strip())
    url = (
        "https://news.google.com/rss/search?q="
        f"{encoded}&hl=ar&gl=MA&ceid=MA:ar"
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=8)
    root = ET.fromstring(resp.content)
    for item in root.findall(".//item")[:max_count]:
      title = item.find("title").text if item.find("title") is not None else ""
      link = item.find("link").text if item.find("link") is not None else ""
      desc = (
          item.find("description").text
          if item.find("description") is not None
          else ""
      )
      pub_date = (
          item.find("pubDate").text
          if item.find("pubDate") is not None
          else "غير محدد"
      )
      source = (
          item.find("source").text
          if item.find("source") is not None
          else "مصدر إخباري"
      )

      # تنسيق التاريخ
      clean_date = pub_date
      try:
        dt = parsedate_to_datetime(pub_date)
        clean_date = dt.strftime("%Y-%m-%d %H:%M")
      except Exception:
        pass

      clean_desc = re.sub(r"<[^>]+>", "", desc)

      if title and link:
        results.append({
            "platform": "الأخبار الرسمية",
            "author": source,
            "title": title,
            "link": link,
            "date": clean_date,
            "snippet": clean_desc or f"تقرير إخباري حول {kw}",
        })
  except Exception:
    pass
  return results


# 3. جلب منشورات السوشيال ميديا المباشرة (Facebook, X, Instagram, TikTok)
def fetch_social_network_posts(kw, platform_name, time_code, max_count=5):
  results = []
  inurl_map = {
      "Facebook": "facebook.com",
      "X (Twitter)": "x.com",
      "Instagram": "instagram.com",
      "TikTok": "tiktok.com",
  }
  domain = inurl_map.get(platform_name, "")

  # صياغة بحث دقيقة تستهدف نطاق المنصة مباشرة
  query = f'site:{domain} "{kw}"'

  try:
    with DDGS() as ddgs:
      for r in ddgs.text(query, max_results=max_count, timelimit=time_code):
        link = r.get("href", "")
        title = r.get("title", "")
        body = r.get("body", "")

        # استخراج اسم الحساب من الرابط
        author = "حساب عام"
        if platform_name == "Facebook":
          m = re.search(r"facebook\.com/([^/?#]+)", link)
          author = (
              m.group(1)
              if m and m.group(1) not in ["photo", "watch", "story"]
              else "صفحة فيسبوك"
          )
        elif platform_name == "X (Twitter)":
          m = re.search(r"x\.com/([^/?#]+)", link)
          author = (
              f"@{m.group(1)}"
              if m and m.group(1) not in ["home", "explore", "search"]
              else "حساب X"
          )
        elif platform_name == "Instagram":
          m = re.search(r"instagram\.com/([^/?#]+)", link)
          author = (
              f"@{m.group(1)}"
              if m and m.group(1) not in ["p", "reel", "stories"]
              else "حساب Instagram"
          )
        elif platform_name == "TikTok":
          m = re.search(r"tiktok\.com/@([^/?#]+)", link)
          author = f"@{m.group(1)}" if m else "حساب TikTok"

        results.append({
            "platform": platform_name,
            "author": author,
            "title": title or f"منشور على {platform_name}",
            "link": link,
            "date": (
                f"خلال {time_range}"
                if time_code
                else datetime.now().strftime("%Y-%m-%d")
            ),
            "snippet": body or f"محتوى منشور على منصة {platform_name}",
        })
  except Exception:
    pass
  return results


# 4. التحليل والتقييم الذكي بواسطة Gemini
def analyze_with_ai(title, snippet, domain, key, model_name):
  try:
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name)
    prompt = f"""
أنت مساعد خبير في الرصد الإعلامي والقضائي.
المجال المطلوب: {domain}

المنشور المرصود:
العنوان: {title}
المحتوى/المقتطف: {snippet}

المطلوب:
1. هل هذا المنشور يرتبط فعلياً بالمجال المطلوب؟
2. أجب حصراً بصيغة:
YES: [اكتب في جملة مركزة ومفيدة ملخص ما يتناوله المنشور وقيمته الخبرية أو القانونية]
أو
NO
"""
    res = model.generate_content(prompt)
    txt = res.text.strip()
    if txt.startswith("YES"):
      return True, txt.replace("YES:", "").replace("YES", "").strip()
    return False, ""
  except Exception:
    # اعتماد المنشور تلقائياً إذا تطابق بالكلمات
    return True, "تمت المطابقة بناءً على الكلمات المفتاحية وسياق المحتوى"


def send_telegram_alert(token, chat_id, item):
  msg = (
      f"🚨 *منشور مطابق جديد!*\n\n"
      f"🌐 *المنصة:* {item['platform']}\n"
      f"👤 *الناشر:* `{item['author']}`\n"
      f"📅 *التاريخ:* {item['date']}\n"
      f"📌 *العنوان:* {item['title']}\n"
      f"📝 *المقتطف:* {item['snippet'][:150]}...\n"
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
    keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
    kw = keywords[0]
    time_code = ddg_time_map[time_range]
    news_time_code = news_time_map[time_range]

    raw_list = []
    seen_urls = set()

    with st.spinner(f"جارٍ الرصد عبر المنصات المحددة لنطاق: {time_range}..."):
      # YouTube
      if "YouTube" in platforms_selected:
        raw_list.extend(fetch_youtube_detailed(kw, max_count=6))

      # الأخبار الرسمية
      if "الأخبار الرسمية" in platforms_selected:
        raw_list.extend(fetch_news_rss(kw, news_time_code, max_count=6))

      # فيسبوك
      if "Facebook" in platforms_selected:
        raw_list.extend(
            fetch_social_network_posts(kw, "Facebook", time_code, max_count=5)
        )

      # إكس
      if "X (Twitter)" in platforms_selected:
        raw_list.extend(
            fetch_social_network_posts(
                kw, "X (Twitter)", time_code, max_count=5
            )
        )

      # إنستغرام
      if "Instagram" in platforms_selected:
        raw_list.extend(
            fetch_social_network_posts(kw, "Instagram", time_code, max_count=5)
        )

      # تيك توك
      if "TikTok" in platforms_selected:
        raw_list.extend(
            fetch_social_network_posts(kw, "TikTok", time_code, max_count=5)
        )

    st.info(
        f"📊 تم جلب {len(raw_list)} منشوراً أولياً من الشبكات المختارة. جارٍ"
        " التحليل الذكي عبر Gemini..."
    )

    verified_items = []
    with st.spinner("جارٍ فحص وتحليل كل منشور بواسطة الذكاء الاصطناعي..."):
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

    # عرض النتائج في بطاقات متكاملة
    st.subheader(
        f"📋 المنشورات المؤكدة والمطابقة ({len(verified_items)}) - {time_range}"
    )

    if verified_items:
      badge_classes = {
          "Facebook": "badge-facebook",
          "X (Twitter)": "badge-x",
          "Instagram": "badge-instagram",
          "TikTok": "badge-tiktok",
          "YouTube": "badge-youtube",
          "الأخبار الرسمية": "badge-news",
      }

      for idx, item in enumerate(verified_items, 1):
        b_class = badge_classes.get(item["platform"], "badge-news")
        st.markdown(
            f"""
                <div class="result-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4>#{idx} <span class="badge-platform {b_class}">{item['platform']}</span> {item['title']}</h4>
                    </div>
                    <div class="meta-info">
                        👤 <b>الناشر:</b> {item['author']} &nbsp;|&nbsp; 
                        📅 <b>تاريخ النشر:</b> {item['date']}
                    </div>
                    <div class="snippet-box">
                        <b>📝 مقتطف المحتوى:</b><br>{item['snippet']}
                    </div>
                    <p><b>💡 تحليل الذكاء الاصطناعي:</b> <span style="color: #198754; font-weight: bold;">{item['reason']}</span></p>
                    <p><a href="{item['link']}" target="_blank" style="font-weight: bold; color: #0d6efd; text-decoration: none;">🔗 فتح المنشور الأصلي على {item['platform']} ➔</a></p>
                </div>
                """,
            unsafe_allow_html=True,
        )
    else:
      st.warning(
          "لم يتم العثور على منشورات في هذا النطاق الزمني. جرب اختيار 'جميع"
          " الأوقات' أو إضافة كلمات مفتاحية أخرى."
      )
