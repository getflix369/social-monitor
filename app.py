import os
import re
from duckduckgo_search import DDGS
import google.generativeai as genai
import requests
import streamlit as st

st.set_page_config(
    page_title="الرصد الشامل لمنصات التواصل بالذكاء الاصطناعي",
    page_icon="🌐",
    layout="wide",
)

st.markdown(
    """
    <style>
    body, .stApp {
        direction: rtl;
        text-align: right;
    }
    .stTextInput > label, .stTextArea > label, .stSelectbox > label, .stSlider > label {
        text-align: right;
        font-weight: bold;
    }
    .result-card {
        background-color: #ffffff;
        border-right: 5px solid #28a745;
        border: 1px solid #e0e0e0;
        border-right-width: 5px;
        padding: 16px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# الإعدادات في الشريط الجانبي
with st.sidebar:
  st.header("⚙️ المفاتيح والإعدادات")
  gemini_api_key = st.text_input(
      "مفتاح Gemini API",
      value=os.getenv("GEMINI_API_KEY", ""),
      type="password",
  )
  telegram_token = st.text_input(
      "رمز بوت تيليجرام (Bot Token)",
      value=os.getenv("TELEGRAM_BOT_TOKEN", ""),
      type="password",
  )
  telegram_chat_id = st.text_input(
      "معرّف تيليجرام (Chat ID)", value=os.getenv("TELEGRAM_CHAT_ID", "")
  )
  send_telegram = st.checkbox("إرسال إشعار إلى تيليجرام", value=True)

  st.divider()
  max_results = st.slider(
      "أقصى عدد نتائج لكل منصة:", min_value=5, max_value=25, value=10
  )

st.title("🌐 الرصد الذكي لمنصات التواصل الاجتماعي")
st.write(
    "رصد شامل في كافة أرجاء المنصات للكلمات المفتاحية، مع التحقق الذكي من"
    " المحتوى بواسطة Gemini."
)

col1, col2 = st.columns(2)

with col1:
  target_domain = st.text_input(
      "🎯 المجال المستهدف للتقييم:",
      value="القانون والنزاعات والقرارات التأديبية في الرياضة",
      placeholder="المجال الذي سيحكم الذكاء الاصطناعي بناءً عليه...",
  )

with col2:
  keywords_input = st.text_input(
      "🔑 كلمات البحث (افصل بينها بفاصلة):",
      value="التحكيم الرياضي, الطاس, نزاع رياضي, لجنة التأديب",
      placeholder="كلمات للبحث في المنصات...",
  )

platforms_selected = st.multiselect(
    "📱 المنصات المراد رصدها:",
    options=["YouTube", "X (Twitter)", "Facebook", "TikTok"],
    default=["YouTube", "X (Twitter)", "Facebook"],
)

start_btn = st.button("🚀 بدء الرصد والتحليل الآن", type="primary")


def extract_account_from_url(url, platform):
  try:
    if platform == "X (Twitter)":
      m = re.search(r"x\.com/([^/?#]+)", url)
      return (
          f"@{m.group(1)}"
          if m and m.group(1) not in ["home", "explore", "search"]
          else "حساب X"
      )
    elif platform == "TikTok":
      m = re.search(r"tiktok\.com/@([^/?#]+)", url)
      return f"@{m.group(1)}" if m else "حساب TikTok"
    elif platform == "YouTube":
      m = re.search(r"youtube\.com/(@[^/?#]+)", url)
      return m.group(1) if m else "قناة YouTube"
    elif platform == "Facebook":
      m = re.search(r"facebook\.com/([^/?#]+)", url)
      return (
          m.group(1)
          if m and m.group(1) not in ["photo", "watch", "story"]
          else "صفحة Facebook"
      )
  except Exception:
    pass
  return "ناشر"


def analyze_with_ai(title, snippet, domain, key):
  try:
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"""
أنت خبير في تصنيف المحتوى.
المجال المطلوب: {domain}

المحتوى المرصود:
العنوان: {title}
المقتطف: {snippet}

هل يرتبط هذا المحتوى بالمجال المطلوب؟
أجب فقط بـ:
YES: [سبب موجز جداً في جملة واحدة]
أو
NO
"""
    res = model.generate_content(prompt)
    txt = res.text.strip()
    if txt.startswith("YES"):
      return True, txt.replace("YES:", "").replace("YES", "").strip()
    return False, ""
  except Exception as e:
    return False, f"خطأ API: {e}"


def send_tg_msg(token, chat_id, platform, account, title, link, reason):
  msg = (
      f"🚨 *منشور مطابق جديد!*\n\n"
      f"🌐 *المنصة:* {platform}\n"
      f"👤 *الناشر:* `{account}`\n"
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
    st.warning("⚠️ يرجى إدخال كلمات البحث المفتاحية.")
  else:
    keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
    platform_domains = {
        "YouTube": "youtube.com",
        "X (Twitter)": "x.com",
        "Facebook": "facebook.com",
        "TikTok": "tiktok.com",
    }

    results_found = []
    seen_links = set()
    debug_logs = []

    with st.spinner("جارٍ البحث في الويب والتحليل الذكي..."):
      with DDGS() as ddgs:
        for platform in platforms_selected:
          p_domain = platform_domains.get(platform, "")

          # صياغة بحث بسيطة وسلسة بدون تعقيد
          # مثال: site:youtube.com التحكيم الرياضي OR الطاس
          clean_kw = " OR ".join(keywords[:3])
          search_query = f"site:{p_domain} {clean_kw}"

          debug_logs.append(f"🔎 **{platform}**: الاستعلام هو `{search_query}`")

          try:
            raw_results = list(ddgs.text(search_query, max_results=max_results))
            debug_logs.append(
                f"📊 **{platform}**: عثر محرك البحث على {len(raw_results)} نتيجة"
                " أولية."
            )

            for item in raw_results:
              link = item.get("href", "")
              title = item.get("title", "")
              snippet = item.get("body", "")

              if not link or link in seen_links:
                continue
              seen_links.add(link)

              # تحليل الذكاء الاصطناعي
              is_match, reason = analyze_with_ai(
                  title, snippet, target_domain, gemini_api_key
              )

              if is_match:
                acc = extract_account_from_url(link, platform)
                match_data = {
                    "platform": platform,
                    "account": acc,
                    "title": title,
                    "link": link,
                    "reason": reason,
                    "snippet": snippet,
                }
                results_found.append(match_data)
                debug_logs.append(
                    f"✅ **مطابق ({platform})**: {title} -> {reason}"
                )

                if send_telegram and telegram_token and telegram_chat_id:
                  send_tg_msg(
                      telegram_token,
                      telegram_chat_id,
                      platform,
                      acc,
                      title,
                      link,
                      reason,
                  )
              else:
                debug_logs.append(
                    f"❌ **مستبعد ({platform})**: {title} (لم يرتبط مباشرة"
                    " بالمجال)"
                )

          except Exception as e:
            debug_logs.append(f"⚠️ خطأ في البحث عبر {platform}: {e}")

    # عرض النتائج في بطاقات واضحة
    st.subheader(f"📋 النتائج المؤكدة والمطابقة ({len(results_found)})")

    if results_found:
      for idx, res in enumerate(results_found, 1):
        st.markdown(
            f"""
                <div class="result-card">
                    <h4>#{idx} - {res['platform']} | الناشر: <code>{res['account']}</code></h4>
                    <p><b>العنوان:</b> {res['title']}</p>
                    <p><b>المقتطف:</b> {res['snippet']}</p>
                    <p><b>تحليل الذكاء الاصطناعي:</b> <span style="color: #28a745; font-weight: bold;">{res['reason']}</span></p>
                    <p><a href="{res['link']}" target="_blank">🔗 فتح المنشور الأصلي</a></p>
                </div>
                """,
            unsafe_allow_html=True,
        )
    else:
      st.info(
          "لم يتم اعتماد أي منشور مطابق بعد فحص الذكاء الاصطناعي للنتائج"
          " الأولية."
      )

    # عرض تفاصيل الفحص لتسهيل المتابعة
    with st.expander("🛠️ اضغط هنا لعرض تفاصيل عمليات البحث والتحليل (Logs)"):
      for log in debug_logs:
        st.markdown(log)
