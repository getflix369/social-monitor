import os
import re
from duckduckgo_search import DDGS
import google.generativeai as genai
import requests
import streamlit as st

# ضبط إعدادات الصفحة
st.set_page_config(
    page_title="الرصد الشامل لمنصات التواصل بالذكاء الاصطناعي",
    page_icon="🌐",
    layout="wide",
)

# تخصيص الاتجاه ليدعم العربية (RTL)
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
        color: #212529;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# القائمة الجانبية للإعدادات والمفاتيح
with st.sidebar:
  st.header("⚙️ المفاتيح والإعدادات")
  gemini_api_key = st.text_input(
      "مفتاح Gemini API",
      value=os.getenv("GEMINI_API_KEY", ""),
      type="password",
      help="مفتاح الذكاء الاصطناعي من Google AI Studio",
  )
  telegram_token = st.text_input(
      "رمز بوت تيليجرام (Bot Token)",
      value=os.getenv("TELEGRAM_BOT_TOKEN", ""),
      type="password",
  )
  telegram_chat_id = st.text_input(
      "معرّف تيليجرام (Chat ID)", value=os.getenv("TELEGRAM_CHAT_ID", "")
  )
  send_telegram = st.checkbox("إرسال إشعار فوري إلى تيليجرام", value=True)

  st.divider()
  st.subheader("⏱️ خيارات البحث المتقدم")
  time_filter = st.selectbox(
      "النطاق الزمني للمنشورات:",
      options=["آخر 24 ساعة (الأحدث)", "آخر أسبوع", "آخر شهر", "أي وقت"],
      index=1,
  )
  time_map = {
      "آخر 24 ساعة (الأحدث)": "d",
      "آخر أسبوع": "w",
      "آخر شهر": "m",
      "أي وقت": None,
  }

  max_results = st.slider(
      "عدد النتائج المفحوصة لكل منصة:", min_value=5, max_value=25, value=10
  )

# الواجهة الرئيسية
st.title("🌐 الرصد الشامل لمنصات التواصل الاجتماعي")
st.write(
    "ابحث عن أي محتوى منشور على المنصات بالكامل يطابق مجالك وكلماتك المفتاحية"
    " مع تقييم ذكي لكل منشور."
)

col1, col2 = st.columns([1, 1])

with col1:
  target_domain = st.text_input(
      "🎯 المجال أو الموضوع المستهدف:",
      value="القانون الرياضي والنزاعات الرياضية بالمغرب",
      placeholder="مثال: الذكاء الاصطناعي التوليدي، أخبار الطاقة المتجددة...",
  )

with col2:
  keywords_input = st.text_input(
      "🔑 الكلمات المفتاحية (افصل بينها بفاصلة):",
      value="التحكيم الرياضي, الطاس, الجامعة الملكية, نزاع",
      placeholder="كلمة 1, كلمة 2, كلمة 3...",
  )

platforms_selected = st.multiselect(
    "📱 المنصات المراد رصدها:",
    options=["YouTube", "X (Twitter)", "Facebook", "TikTok"],
    default=["YouTube", "X (Twitter)", "Facebook"],
)

# حقل اختياري لحصر البحث في حساب معين إن رغبت
specific_account = st.text_input(
    "👤 حصر البحث في حساب أو قناة معينة (اختياري - اتركه فارغاً للبحث الشامل"
    " في كل المنصة):",
    value="",
    placeholder="مثال: @username (اتركه فارغاً للبحث في كل الحسابات)",
)

start_btn = st.button("🚀 بدء الرصد الشامل والتحليل", type="primary")


# دوال المساعدة
def extract_account_from_url(url, platform):
  """استخراج اسم الحساب أو القناة من رابط المنشور"""
  try:
    if platform == "X (Twitter)":
      m = re.search(r"x\.com/([^/]+)", url)
      return f"@{m.group(1)}" if m else "حساب غير محدد"
    elif platform == "TikTok":
      m = re.search(r"tiktok\.com/@([^/]+)", url)
      return f"@{m.group(1)}" if m else "حساب غير محدد"
    elif platform == "YouTube":
      m = re.search(r"youtube\.com/(@[^/]+)", url)
      return m.group(1) if m else "قناة YouTube"
    elif platform == "Facebook":
      m = re.search(r"facebook\.com/([^/]+)", url)
      return m.group(1) if m else "صفحة Facebook"
  except Exception:
    pass
  return "حساب عام"


def analyze_with_ai(title, snippet, domain, keywords_list, key):
  try:
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"""
أنت مساعد متخصص في رصد وفلترة المحتوى الرقمي.
المجال المطلوب بدقة: {domain}
الكلمات المفتاحية: {', '.join(keywords_list)}

بيانات المنشور المرصود:
العنوان: {title}
المحتوى/المقتطف: {snippet}

المهمة:
هل هذا المنشور يتناول فعلياً المجال المطلوب بشكل ذي قيمة ومطابق للكلمات المفتاحية؟
أجب بإحدى الصيغتين فقط:
YES: [اكتب سبباً موجزاً جداً في جملة واحدة يوضح ما يناقشه المنشور]
أو
NO
"""
    res = model.generate_content(prompt)
    txt = res.text.strip()
    if txt.startswith("YES"):
      reason = txt.replace("YES:", "").replace("YES", "").strip()
      return True, reason
    return False, ""
  except Exception as e:
    return False, f"خطأ في التحليل: {e}"


def send_tg_msg(token, chat_id, platform, account, title, link, reason):
  msg = (
      f"🚨 *منشور مطابق جديد تم رصده!*\n\n"
      f"🌐 *المنصة:* {platform}\n"
      f"👤 *الناشر/الحساب:* `{account}`\n"
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
  except Exception as e:
    print(f"Telegram Error: {e}")


# تنفيذ الرصد
if start_btn:
  if not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API في القائمة الجانبية.")
  elif not target_domain or not keywords_input:
    st.warning("⚠️ يرجى تحديد المجال والكلمات المفتاحية.")
  else:
    keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
    selected_time = time_map[time_filter]

    st.info(f"🔍 جارٍ البحث الشامل عبر: {', '.join(platforms_selected)}...")

    platform_domains = {
        "YouTube": "youtube.com",
        "X (Twitter)": "x.com",
        "Facebook": "facebook.com",
        "TikTok": "tiktok.com",
    }

    results_found = []
    seen_links = set()

    with st.spinner("جارٍ فحص المنصات وتحليل المحتوى بواسطة الذكاء الاصطناعي..."):
      with DDGS() as ddgs:
        for platform in platforms_selected:
          p_domain = platform_domains.get(platform, "")

          # صياغة استعلام بحث شامل للمنصة بالكامل
          kw_queries = " OR ".join([f'"{k}"' for k in keywords[:4]])
          if specific_account.strip():
            search_query = f'site:{p_domain} "{specific_account.strip()}" ({kw_queries}) "{target_domain}"'
          else:
            # بحث عام عبر كامل المنصة
            search_query = (
                f'site:{p_domain} ({kw_queries}) "{target_domain}"'
            )

          try:
            raw_results = list(
                ddgs.text(
                    search_query,
                    max_results=max_results,
                    timelimit=selected_time,
                )
            )

            for item in raw_results:
              link = item.get("href", "")
              title = item.get("title", "")
              snippet = item.get("body", "")

              if not link or link in seen_links:
                continue
              seen_links.add(link)

              account_name = extract_account_from_url(link, platform)

              # فحص المحتوى بواسطة الذكاء الاصطناعي
              is_match, reason = analyze_with_ai(
                  title, snippet, target_domain, keywords, gemini_api_key
              )

              if is_match:
                match_data = {
                    "platform": platform,
                    "account": account_name,
                    "title": title,
                    "link": link,
                    "reason": reason,
                    "snippet": snippet,
                }
                results_found.append(match_data)

                # إرسال إشعار تيليجرام
                if send_telegram and telegram_token and telegram_chat_id:
                  send_tg_msg(
                      telegram_token,
                      telegram_chat_id,
                      platform,
                      account_name,
                      title,
                      link,
                      reason,
                  )

          except Exception as e:
            st.warning(f"ملاحظة حول البحث في {platform}: {e}")

    # عرض النتائج
    st.success(
        f"✅ انتهت عملية الفحص! تم رصد وتأكيد {len(results_found)} منشور مطابق"
        " للمجال والشروط."
    )

    if results_found:
      for idx, res in enumerate(results_found, 1):
        st.markdown(
            f"""
                <div class="result-card">
                    <h4>#{idx} - المنصة: <b>{res['platform']}</b> | الناشر: <code>{res['account']}</code></h4>
                    <p><b>العنوان:</b> {res['title']}</p>
                    <p><b>المقتطف:</b> {res['snippet']}</p>
                    <p><b>تحليل الذكاء الاصطناعي:</b> <span style="color: #28a745; font-weight: bold;">{res['reason']}</span></p>
                    <p><a href="{res['link']}" target="_blank" style="text-decoration: none; font-weight: bold;">🔗 فتح المنشور على {res['platform']}</a></p>
                </div>
                """,
            unsafe_allow_html=True,
        )
    else:
      st.warning(
          "لم يتم العثور على منشورات مطابقة. جرب توسيع النطاق الزمني (مثلاً"
          " اختيار 'آخر شهر' أو 'أي وقت') أو تقليل الكلمات المفتاحية المركبة."
      )
