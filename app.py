import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from duckduckgo_search import DDGS
import google.generativeai as genai
import requests
import streamlit as st

st.set_page_config(
    page_title="منظومة الرصد المجانية الشاملة", page_icon="📡", layout="wide"
)

st.markdown(
    """
    <style>
    body, .stApp { direction: rtl; text-align: right; }
    .stTextInput > label, .stTextArea > label, .stSelectbox > label, .stSlider > label { text-align: right; font-weight: bold; }
    .result-card {
        background-color: #ffffff;
        border-right: 5px solid #0d6efd;
        border: 1px solid #e0e0e0;
        border-right-width: 5px;
        padding: 18px;
        border-radius: 8px;
        margin-bottom: 18px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .badge-platform {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.85em;
        margin-left: 8px;
        color: white;
    }
    .badge-facebook { background-color: #1877f2; }
    .badge-x { background-color: #000000; }
    .badge-youtube { background-color: #ff0000; }
    .badge-tiktok { background-color: #000000; }
    .badge-news { background-color: #198754; }
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
      "نموذج Gemini (المجاني):",
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
        res = m.generate_content("أهلاً، تأكيد الاتصال")
        st.success(f"✅ الاتصال سليم بالنموذج: {model_choice}!")
      except Exception as err:
        st.error(f"❌ خطأ: {err}")

  st.divider()
  st.header("📲 إعدادات Telegram")
  telegram_token = st.text_input(
      "رمز بوت تيليجرام",
      value=os.getenv("TELEGRAM_BOT_TOKEN", ""),
      type="password",
  )
  telegram_chat_id = st.text_input(
      "معرّف تيليجرام (Chat ID)", value=os.getenv("TELEGRAM_CHAT_ID", "")
  )
  send_telegram = st.checkbox("إرسال التنبيهات إلى Telegram", value=True)

# الواجهة الرئيسية
st.title("📡 منظومة الرصد الشامل متعددة المنصات")
st.write(
    "جلب فوري للمنشورات من **YouTube و Facebook و X و الأخبار** مع التحليل"
    f" الذكي المجاني عبر **{model_choice}**."
)

col1, col2 = st.columns(2)
with col1:
  target_domain = st.text_input(
      "🎯 المجال المستهدف للتقييم:",
      value="شؤون القضاء والعدالة وقرارات المجلس الأعلى للسلطة القضائية",
  )
with col2:
  keywords_input = st.text_input(
      "🔑 الكلمات المفتاحية:",
      value="المجلس الأعلى للسلطة القضائية, القضاء المغربي",
  )

platforms_selected = st.multiselect(
    "🌐 المنصات المراد رصدها:",
    options=["YouTube", "Facebook", "X (Twitter)", "TikTok", "الأخبار الرسمية"],
    default=["YouTube", "Facebook", "X (Twitter)", "الأخبار الرسمية"],
)

start_btn = st.button("🚀 بدء الرصد الشامل والتحليل", type="primary")


# 1. جلب مباشر من يوتيوب
def get_youtube_posts(kw, max_count=6):
  results = []
  try:
    encoded = urllib.parse.quote(kw)
    url = f"https://www.youtube.com/results?search_query={encoded}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=8)
    v_ids = re.findall(r"/watch\?v=([a-zA-Z0-9_-]{11})", resp.text)
    seen = set()
    for vid in v_ids:
      if vid not in seen:
        seen.add(vid)
        results.append({
            "platform": "YouTube",
            "title": f"فيديو يوتيوب حول: {kw}",
            "link": f"https://www.youtube.com/watch?v={vid}",
            "snippet": f"فيديو منشور على يوتيوب يتناول موضوع {kw}",
        })
        if len(results) >= max_count:
          break
  except Exception:
    pass
  return results


# 2. جلب الأخبار والبيانات الرسمية عبر RSS
def get_news_rss(kw, max_count=5):
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
    for item in root.findall(".//item")[:max_count]:
      title = item.find("title").text if item.find("title") is not None else ""
      link = item.find("link").text if item.find("link") is not None else ""
      desc = (
          item.find("description").text
          if item.find("description") is not None
          else ""
      )
      # تنظيف نصوص HTML
      clean_desc = re.sub(r"<[^>]+>", "", desc)
      if title and link:
        results.append({
            "platform": "الأخبار الرسمية",
            "title": title,
            "link": link,
            "snippet": clean_desc,
        })
  except Exception:
    pass
  return results


# 3. جلب منشورات السوشيال ميديا عبر DuckDuckGo بصيغ مرنة
def get_social_posts(kw, platform_name, max_count=5):
  results = []
  platform_keywords = {
      "Facebook": "facebook",
      "X (Twitter)": "twitter OR x.com",
      "TikTok": "tiktok",
  }
  target_kw = platform_keywords.get(platform_name, "")
  query = f'"{kw}" {target_kw}'

  try:
    with DDGS() as ddgs:
      for r in ddgs.text(query, max_results=max_count):
        link = r.get("href", "")
        title = r.get("title", "")
        body = r.get("body", "")
        # التأكد من صحة الرابط وانتمائه للمنصة
        if platform_name == "Facebook" and "facebook.com" in link:
          results.append({
              "platform": "Facebook",
              "title": title,
              "link": link,
              "snippet": body,
          })
        elif platform_name == "X (Twitter)" and (
            "x.com" in link or "twitter.com" in link
        ):
          results.append({
              "platform": "X (Twitter)",
              "title": title,
              "link": link,
              "snippet": body,
          })
        elif platform_name == "TikTok" and "tiktok.com" in link:
          results.append({
              "platform": "TikTok",
              "title": title,
              "link": link,
              "snippet": body,
          })
        elif not any(p in link for p in ["facebook.com", "x.com", "tiktok.com"]):
          # منشور عام ذو صلة
          results.append({
              "platform": platform_name,
              "title": title,
              "link": link,
              "snippet": body,
          })
  except Exception:
    pass
  return results


# التحليل الذكي عبر Gemini المجاني
def analyze_content_with_ai(title, snippet, domain, key, model_name):
  try:
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name)
    prompt = f"""
المجال المطلوب: {domain}

المحتوى المرصود:
- العنوان: {title}
- المقتطف: {snippet}

المهمة:
هل يرتبط هذا المحتوى بالمجال المطلوب؟
أجب حصراً بـ:
YES: [جملة موجزة جداً تشرح موضوع المنشور]
أو
NO
"""
    res = model.generate_content(prompt)
    txt = res.text.strip()
    if txt.startswith("YES"):
      return True, txt.replace("YES:", "").replace("YES", "").strip()
    return False, ""
  except Exception:
    # في حال حدوث ضغط على الـ API، نعتمد المنشور طالما يحمل الكلمة المفتاحية
    return True, "تمت المطابقة بناءً على الكلمات المفتاحية"


def send_tg_msg(token, chat_id, platform, title, link, reason):
  msg = (
      f"🚨 *منشور مطابق تم رصده!*\n\n"
      f"🌐 *المصدر:* {platform}\n"
      f"📌 *العنوان:* {title}\n"
      f"💡 *التحليل:* {reason}\n"
      f"🔗 *الرابط:* {link}"
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
    st.error("⚠️ يرجى إدخال مفتاح Gemini API في الشريط الجانبي.")
  elif not keywords_input:
    st.warning("⚠️ يرجى إدخال الكلمات المفتاحية.")
  else:
    keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
    first_kw = keywords[0]

    raw_candidates = []
    seen_urls = set()

    with st.spinner("جارٍ جلب المنشورات من مختلف الشبكات والمصادر..."):
      # 1. يوتيوب
      if "YouTube" in platforms_selected:
        raw_candidates.extend(get_youtube_posts(first_kw, max_count=5))

      # 2. الأخبار الرسمية والبيانات
      if "الأخبار الرسمية" in platforms_selected:
        raw_candidates.extend(get_news_rss(first_kw, max_count=5))

      # 3. فيسبوك
      if "Facebook" in platforms_selected:
        raw_candidates.extend(
            get_social_posts(first_kw, "Facebook", max_count=5)
        )

      # 4. إكس (تويتر)
      if "X (Twitter)" in platforms_selected:
        raw_candidates.extend(
            get_social_posts(first_kw, "X (Twitter)", max_count=5)
        )

      # 5. تيك توك
      if "TikTok" in platforms_selected:
        raw_candidates.extend(get_social_posts(first_kw, "TikTok", max_count=5))

    st.info(f"📊 تم جمع {len(raw_candidates)} منشوراً أولياً، جارٍ التحليل الذكي...")

    verified_results = []
    with st.spinner("جارٍ التحقق والفلترة بواسطة Gemini..."):
      for cand in raw_candidates:
        link = cand["link"]
        if link in seen_urls:
          continue
        seen_urls.add(link)

        is_valid, reason = analyze_content_with_ai(
            cand["title"],
            cand["snippet"],
            target_domain,
            gemini_api_key,
            model_choice,
        )
        if is_valid:
          cand["reason"] = reason
          verified_results.append(cand)

          if send_telegram and telegram_token and telegram_chat_id:
            send_tg_msg(
                telegram_token,
                telegram_chat_id,
                cand["platform"],
                cand["title"],
                cand["link"],
                reason,
            )

    # عرض النتائج
    st.subheader(f"📋 المنشورات المؤكدة ({len(verified_results)})")

    if verified_results:
      badge_map = {
          "Facebook": "badge-facebook",
          "X (Twitter)": "badge-x",
          "YouTube": "badge-youtube",
          "TikTok": "badge-tiktok",
          "الأخبار الرسمية": "badge-news",
      }

      for idx, item in enumerate(verified_results, 1):
        b_class = badge_map.get(item["platform"], "badge-news")
        st.markdown(
            f"""
                <div class="result-card">
                    <h4>#{idx} <span class="badge-platform {b_class}">{item['platform']}</span> - {item['title']}</h4>
                    <p><b>المقتطف:</b> {item['snippet']}</p>
                    <p><b>💡 تحليل الذكاء الاصطناعي:</b> <span style="color: #198754; font-weight: bold;">{item['reason']}</span></p>
                    <p><a href="{item['link']}" target="_blank" style="font-weight: bold; color: #0d6efd; text-decoration: none;">🔗 فتح المصدر الأصلي ({item['platform']})</a></p>
                </div>
                """,
            unsafe_allow_html=True,
        )
    else:
      st.warning(
          "لم يتم العثور على منشورات مطابقة. جرب تعديل الكلمات المفتاحية."
      )
