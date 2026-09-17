import os
from duckduckgo_search import DDGS
import google.generativeai as genai
import requests
import streamlit as st

# ضبط إعدادات الصفحة
st.set_page_config(
    page_title="لوحة رصد وسائل التواصل بالذكاء الاصطناعي",
    page_icon="📡",
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
    .stTextInput > label, .stTextArea > label, .stSelectbox > label {
        text-align: right;
        font-weight: bold;
    }
    .result-card {
        background-color: #f8f9fa;
        border-right: 5px solid #0d6efd;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
        color: #212529;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# جلب المفاتيح من البيئة أو من شريط الإعدادات الجانبي
api_key_env = os.getenv("GEMINI_API_KEY", "")
bot_token_env = os.getenv("TELEGRAM_BOT_TOKEN", "")
chat_id_env = os.getenv("TELEGRAM_CHAT_ID", "")

# القائمة الجانبية (Sidebar) للإعدادات والمفاتيح
with st.sidebar:
  st.header("⚙️ إعدادات الربط والمفاتيح")
  gemini_api_key = st.text_input(
      "مفتاح Gemini API",
      value=api_key_env,
      type="password",
      help="مفتاح الذكاء الاصطناعي من Google AI Studio",
  )
  telegram_token = st.text_input(
      "رمز بوت تيليجرام (Bot Token)", value=bot_token_env, type="password"
  )
  telegram_chat_id = st.text_input(
      "معرّف تيليجرام (Chat ID)", value=chat_id_env
  )
  send_telegram = st.checkbox("إرسال تنبيه إلى تيليجرام عند العثور على منشور", value=True)

# واجهة المستخدم الرئيسية
st.title("📡 لوحة رصد وتتبع المحتوى الرقمي")
st.write(
    "حدد المجال والكلمات المفتاحية والحسابات، ثم اضغط على زر التشغيل لبدء"
    " الفحص الذكي."
)

col1, col2 = st.columns(2)

with col1:
  target_domain = st.text_input(
      "🎯 المجال المستهدف:",
      value="القانون الرياضي والنزاعات الرياضية",
      placeholder="مثال: الذكاء الاصطناعي، القانون، الاقتصاد...",
  )
  keywords_input = st.text_area(
      "🔑 الكلمات المفتاحية (افصل بينها بفاصلة):",
      value="محكمة التحكيم, الطاس, نزاع, قرار تأديبي",
      placeholder="كلمة 1, كلمة 2, كلمة 3...",
  )

with col2:
  platforms_selected = st.multiselect(
      "🌐 المنصات المستهدفة:",
      options=["YouTube", "X (Twitter)", "Facebook", "TikTok"],
      default=["YouTube", "X (Twitter)"],
  )
  accounts_input = st.text_area(
      "👤 أسماء الحسابات أو الروابط المستهدفة (حساب في كل سطر):",
      value="FRMFOfficiel\nFIFAcom",
      placeholder="اسم المستخدم أو رابط الحساب...",
  )

# زر التشغيل الرئيسي
start_btn = st.button("🚀 بدء الرصد والتحليل الآن", type="primary")


# دوال المساعدة للرصد والذكاء الاصطناعي
def analyze_with_ai(title, snippet, domain, keywords_list, key):
  try:
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"""
        أنت محلل محتوى خبير.
        المجال المطلوب: {domain}
        الكلمات المفتاحية: {', '.join(keywords_list)}

        المنشور:
        - العنوان: {title}
        - المقتطف/النص: {snippet}

        السؤال:
        هل هذا المنشور يرتبط بشكل صريح ومباشر بالمجال المطلوب والكلمات المفتاحية؟
        أجب حصراً بـ:
        YES: [سبب موجز جداً في جملة واحدة يوضح العلاقة]
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


def send_tg_msg(token, chat_id, platform, title, link, reason):
  msg = (
      f"🚨 *منشور مطابق جديد تم رصده عبر اللوحة!*\n\n"
      f"🌐 *المنصة:* {platform}\n"
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
    print(e)


# تنفيذ عملية الرصد
if start_btn:
  if not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API في القائمة الجانبية.")
  elif not target_domain or not keywords_input:
    st.warning("⚠️ يرجى إدخال المجال والكلمات المفتاحية.")
  else:
    keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
    accounts = [a.strip() for a in accounts_input.split("\n") if a.strip()]

    st.info(
        f"🔍 جارٍ البحث عن الكلمات: ({', '.join(keywords)}) في حسابات:"
        f" ({', '.join(accounts)})..."
    )

    platform_domains = {
        "YouTube": "youtube.com",
        "X (Twitter)": "x.com",
        "Facebook": "facebook.com",
        "TikTok": "tiktok.com",
    }

    results_found = []

    with st.spinner("جارٍ فحص الويب ومطابقة المحتوى بواسطة الذكاء الاصطناعي..."):
      with DDGS() as ddgs:
        for platform in platforms_selected:
          p_domain = platform_domains.get(platform, "")
          for acc in accounts:
            kw_part = " OR ".join([f'"{k}"' for k in keywords[:3]])
            search_query = f'site:{p_domain} "{acc}" ({kw_part})'

            try:
              raw_results = list(ddgs.text(search_query, max_results=4))
              for item in raw_results:
                title = item.get("title", "")
                snippet = item.get("body", "")
                link = item.get("href", "")

                # تحليل المنشور
                is_match, reason = analyze_with_ai(
                    title, snippet, target_domain, keywords, gemini_api_key
                )

                if is_match:
                  match_data = {
                      "platform": platform,
                      "account": acc,
                      "title": title,
                      "link": link,
                      "reason": reason,
                      "snippet": snippet,
                  }
                  results_found.append(match_data)

                  # إرسال إلى تيليجرام إذا كان مفعلاً
                  if (
                      send_telegram
                      and telegram_token
                      and telegram_chat_id
                  ):
                    send_tg_msg(
                        telegram_token,
                        telegram_chat_id,
                        platform,
                        title,
                        link,
                        reason,
                    )

            except Exception as e:
              st.error(f"حدث خطأ أثناء البحث في {platform}: {e}")

    # عرض النتائج في الواجهة
    st.success(f"✅ اكتمل الرصد! تم العثور على {len(results_found)} منشور مطابق.")

    if results_found:
      for idx, res in enumerate(results_found, 1):
        st.markdown(
            f"""
                <div class="result-card">
                    <h4>#{idx} - المنصة: {res['platform']} | الحساب: {res['account']}</h4>
                    <p><b>العنوان:</b> {res['title']}</p>
                    <p><b>تحليل الذكاء الاصطناعي:</b> {res['reason']}</p>
                    <p><a href="{res['link']}" target="_blank">🔗 فتح المنشور الأصلي</a></p>
                </div>
                """,
            unsafe_allow_html=True,
        )
    else:
      st.warning("لم يتم العثور على منشورات مطابقة للشروط الحالية.")
