import os
import re
from duckduckgo_search import DDGS
import google.generativeai as genai
import requests
import streamlit as st

st.set_page_config(
    page_title="منظومة الرصد الذكي - Gemini 3.5 Flash-Lite",
    page_icon="📡",
    layout="wide",
)

st.markdown(
    """
    <style>
    body, .stApp { direction: rtl; text-align: right; }
    .stTextInput > label, .stTextArea > label, .stSelectbox > label, .stSlider > label { text-align: right; font-weight: bold; }
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

# الشريط الجانبي
with st.sidebar:
  st.header("⚙️ إعدادات الذكاء الاصطناعي")

  gemini_api_key = st.text_input(
      "مفتاح Gemini API",
      value=os.getenv("GEMINI_API_KEY", ""),
      type="password",
  )

  # تحديد النموذج المعتمد
  model_choice = st.selectbox(
      "نموذج الذكاء الاصطناعي:",
      options=[
          "gemini-3.5-flash-lite",
          "gemini-3.5-flash",
          "gemini-1.5-flash",
          "gemini-2.0-flash",
      ],
      index=0,
      help="تم تعيين Gemini 3.5 Flash-Lite كخيار افتراضي مجاني وسريع",
  )

  # زر فحص الاتصال بالنموذج
  if st.button("🧪 فحص المفتاح والاتصال بالنموذج"):
    if not gemini_api_key:
      st.error("يرجى كتابة المفتاح أولاً.")
    else:
      try:
        genai.configure(api_key=gemini_api_key)
        m = genai.GenerativeModel(model_choice)
        res = m.generate_content("قل مرحباً باختصار")
        st.success(f"✅ الاتصال ناجح بالنموذج: {model_choice}!")
        st.info(f"رد النموذج: {res.text.strip()}")
      except Exception as err:
        st.error(f"❌ خطأ في الاتصال بالنموذج: {err}")

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

  st.divider()
  max_results = st.slider("عدد النتائج لكل منصة:", 5, 20, 8)

# الواجهة الرئيسية
st.title("📡 الرصد الشامل عبر منصات التواصل (Gemini 3.5 Flash-Lite)")
st.write(
    "رصد المحتوى المنشور عبر المنصات باستخدام البحث المباشر والتقييم الذكي عبر"
    f" **{model_choice}**."
)

col1, col2 = st.columns(2)
with col1:
  target_domain = st.text_input(
      "🎯 المجال المستهدف للتقييم:",
      value="القانون الرياضي والنزاعات الرياضية بالمغرب",
  )
with col2:
  keywords_input = st.text_input(
      "🔑 الكلمات المفتاحية (كلمات رئيسية مباشرة):",
      value="التحكيم الرياضي, الطاس, الجامعة الملكية, نزاع",
  )

platforms_selected = st.multiselect(
    "🌐 المنصات المراد رصدها:",
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


def analyze_with_ai(title, snippet, domain, key, model_name):
  try:
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name)
    prompt = f"""
أنت مساعد خبير في رصد المحتوى الرقمي.
المجال المطلوب: {domain}

المحتوى المرصود:
- العنوان: {title}
- المقتطف: {snippet}

المطلوب:
هل هذا المنشور يتناول المجال المطلوب أو يرتبط به بشكل واضح؟
أجب حصراً بإحدى الصيغتين:
YES: [جملة واحدة موجزة توضح الفكرة المطابقة]
أو
NO
"""
    res = model.generate_content(prompt)
    txt = res.text.strip()
    if txt.startswith("YES"):
      return True, txt.replace("YES:", "").replace("YES", "").strip(), ""
    return False, "", "غير مطابق للمجال"
  except Exception as e:
    return False, "", f"خطأ في الـ API: {e}"


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
    raw_keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
    platform_domains = {
        "YouTube": "youtube.com",
        "X (Twitter)": "x.com",
        "Facebook": "facebook.com",
        "TikTok": "tiktok.com",
    }

    results_found = []
    seen_links = set()
    debug_logs = []

    with st.spinner(f"جارٍ البحث والتحليل باستخدام {model_choice}..."):
      with DDGS() as ddgs:
        for platform in platforms_selected:
          p_domain = platform_domains.get(platform, "")

          for kw in raw_keywords[:2]:
            search_query = f"site:{p_domain} {kw}"
            debug_logs.append(
                f"🔍 **استعلام ({platform})**: `{search_query}`"
            )

            try:
              raw_results = list(
                  ddgs.text(search_query, max_results=max_results)
              )
              debug_logs.append(
                  f"📊 **{platform}** للكلمة `{kw}`: تم العثور على"
                  f" {len(raw_results)} نتيجة أولية."
              )

              for item in raw_results:
                link = item.get("href", "")
                title = item.get("title", "")
                snippet = item.get("body", "")

                if not link or link in seen_links:
                  continue
                seen_links.add(link)

                # التحليل بواسطة النموذج المختار
                is_match, reason, error_msg = analyze_with_ai(
                    title, snippet, target_domain, gemini_api_key, model_choice
                )

                if is_match:
                  acc = extract_account_from_url(link, platform)
                  results_found.append({
                      "platform": platform,
                      "account": acc,
                      "title": title,
                      "link": link,
                      "reason": reason,
                      "snippet": snippet,
                  })
                  debug_logs.append(f"✅ **تم اعتماده**: {title}")

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
                  if error_msg.startswith("خطأ"):
                    debug_logs.append(
                        f"🚨 **خطأ في استدعاء الذكاء الاصطناعي**: {error_msg}"
                    )
                  else:
                    debug_logs.append(f"❌ **مستبعد**: {title}")

            except Exception as e:
              debug_logs.append(f"⚠️ خطأ في البحث عبر {platform}: {e}")

    # عرض النتائج
    st.subheader(f"📋 النتائج المعتمدة ({len(results_found)})")

    if results_found:
      for idx, res in enumerate(results_found, 1):
        st.markdown(
            f"""
                <div class="result-card">
                    <h4>#{idx} - {res['platform']} | الناشر: <code>{res['account']}</code></h4>
                    <p><b>العنوان:</b> {res['title']}</p>
                    <p><b>المقتطف:</b> {res['snippet']}</p>
                    <p><b>تحليل الذكاء الاصطناعي:</b> <span style="color: #28a745; font-weight: bold;">{res['reason']}</span></p>
                    <p><a href="{res['link']}" target="_blank">🔗 فتح المنشور الأصلي على {res['platform']}</a></p>
                </div>
                """,
            unsafe_allow_html=True,
        )
    else:
      st.warning(
          "لم يتم العثور على نتائج مطابقة. افتح سجل الفحص والتشخيص بالأسفل لمعرفة"
          " التفاصيل."
      )

    with st.expander("🛠️ اضغط هنا لعرض سجل الفحص والتشخيص (Debug Logs)"):
      for log in debug_logs:
        st.markdown(log)
