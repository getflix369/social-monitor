import os
import re
import urllib.parse
import google.generativeai as genai
import requests
import streamlit as st

st.set_page_config(
    page_title="الرصد الشامل متعدد المنصات - Gemini Grounding",
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
    }
    .badge-facebook { background-color: #1877f2; color: white; }
    .badge-x { background-color: #000000; color: white; }
    .badge-instagram { background-color: #e1306c; color: white; }
    .badge-tiktok { background-color: #000000; color: white; }
    .badge-youtube { background-color: #ff0000; color: white; }
    .badge-web { background-color: #6c757d; color: white; }
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
      "نموذج Gemini المعتمد:",
      options=[
          "gemini-3.5-flash-lite",
          "gemini-2.0-flash",
          "gemini-1.5-flash",
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
        res = m.generate_content("قل مرحباً")
        st.success(f"✅ الاتصال ناجح بالنموذج: {model_choice}!")
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
st.title("📡 الرصد الشامل عبر منصات التواصل (Google Grounding + Gemini)")
st.write(
    "رصد حي ومباشر عبر خوادم Google الرسمية لاكتشاف منشورات **Facebook, X,"
    f" Instagram, TikTok, YouTube** وتحليلها عبر **{model_choice}** دون حظر."
)

col1, col2 = st.columns(2)
with col1:
  target_domain = st.text_input(
      "🎯 المجال المستهدف للتقييم:",
      value="شؤون القضاء والعدالة وقرارات المجلس الأعلى للسلطة القضائية بالمغرب",
  )
with col2:
  keywords_input = st.text_input(
      "🔑 الكلمات المفتاحية للرصد:",
      value="المجلس الأعلى للسلطة القضائية, القضاء المغربي, محكمة النقض",
  )

platforms_selected = st.multiselect(
    "🌐 المنصات المراد رصدها:",
    options=["Facebook", "X (Twitter)", "Instagram", "TikTok", "YouTube"],
    default=["Facebook", "X (Twitter)", "YouTube", "Instagram"],
)

start_btn = st.button("🚀 بدء الرصد الشامل الفوري", type="primary")


def send_tg_msg(token, chat_id, platform, title, link, reason):
  msg = (
      f"🚨 *منشور مطابق جديد تم رصده!*\n\n"
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
  except Exception:
    pass


def perform_grounded_social_monitoring(
    key, model_name, domain, keywords, platforms
):
  """استخدام ميزة البحث في Google عبر سيرفرات Gemini لجلب المنشورات من مختلف الشبكات"""
  genai.configure(api_key=key)

  # تفعيل أداة البحث في جوجل
  try:
    model = genai.GenerativeModel(model_name, tools=[{"google_search": {}}])
  except Exception:
    try:
      model = genai.GenerativeModel(
          model_name, tools="google_search_retrieval"
      )
    except Exception:
      model = genai.GenerativeModel(model_name)

  prompt = f"""
أنت منظومة متقدمة لرصد وسائل التواصل الاجتماعي والويب.
المجال المطلوب: {domain}
الكلمات المفتاحية: {keywords}
المنصات المطلوب رصدها بدقة: {', '.join(platforms)}

المهمة:
قم بالبحث الحي عبر محرك Google عن أحدث المنشورات والفيديوهات والصفحات المنشورة على وسائل التواصل الاجتماعي المحددة ({', '.join(platforms)}) والتي تتناول هذا الموضوع والكلمات المفتاحية.

استخرج المنشورات الحقيقية الموجودة، وقدم النتائج على شكل عناصر مفصولة بالعلامة "---".
لكل منشور، التزم تماماً بالهيكل التالي:
---
المنصة: [اسم المنصة مثل Facebook أو X (Twitter) أو Instagram أو TikTok أو YouTube]
العنوان: [عنوان المنشور أو موضوعه بدقة]
الرابط: [ضع الرابط المباشر للمنشور أو الصفحة على المنصة URL]
التحليل: [جملة تشرح ملخص المنشور وعلاقته بالمجال المطلوب]
---

ملاحظة هامة: احرص على تنويع النتائج لتشمل المنصات المختلفة وخاصة Facebook و X و Instagram و YouTube.
"""
  response = model.generate_content(prompt)
  return response.text


if start_btn:
  if not gemini_api_key:
    st.error("⚠️ يرجى إدخال مفتاح Gemini API في الشريط الجانبي.")
  elif not keywords_input:
    st.warning("⚠️ يرجى كتابة الكلمات المفتاحية.")
  else:
    results_found = []

    with st.spinner(
        "جارٍ استطلاع شبكات التواصل عبر سيرفرات Google وتحليل المحتوى بواسطة"
        " Gemini..."
    ):
      try:
        raw_text = perform_grounded_social_monitoring(
            gemini_api_key,
            model_choice,
            target_domain,
            keywords_input,
            platforms_selected,
        )

        # تقسيم وتحليل النتائج المستخرجة
        blocks = raw_text.split("---")
        for block in blocks:
          if "المنصة:" in block and "الرابط:" in block:
            lines = [line.strip() for line in block.strip().split("\n") if line]
            item = {
                "platform": "عام",
                "title": "",
                "link": "",
                "reason": "",
            }
            for line in lines:
              if line.startswith("المنصة:"):
                item["platform"] = line.replace("المنصة:", "").strip()
              elif line.startswith("العنوان:"):
                item["title"] = line.replace("العنوان:", "").strip()
              elif line.startswith("الرابط:"):
                item["link"] = line.replace("الرابط:", "").strip()
              elif line.startswith("التحليل:"):
                item["reason"] = line.replace("التحليل:", "").strip()

            # تنظيف الرابط إذا كان بصيغة ماركداون [link](url)
            link_match = re.search(r"\((https?://[^\)]+)\)", item["link"])
            if link_match:
              item["link"] = link_match.group(1)
            else:
              link_match2 = re.search(r"(https?://[^\s]+)", item["link"])
              if link_match2:
                item["link"] = link_match2.group(1)

            if item["title"] and item["link"]:
              results_found.append(item)
              if send_telegram and telegram_token and telegram_chat_id:
                send_tg_msg(
                    telegram_token,
                    telegram_chat_id,
                    item["platform"],
                    item["title"],
                    item["link"],
                    item["reason"],
                )

      except Exception as e:
        st.error(f"حدث خطأ أثناء الرصد: {e}")

    # عرض النتائج في بطاقات مميزة
    st.subheader(
        f"📋 المنشورات المرصودة عبر مختلف الشبكات ({len(results_found)})"
    )

    if results_found:
      for idx, res in enumerate(results_found, 1):
        # تلوين شارة المنصة
        p_name = res["platform"].lower()
        badge_class = "badge-web"
        if "facebook" in p_name:
          badge_class = "badge-facebook"
        elif "x" in p_name or "twitter" in p_name:
          badge_class = "badge-x"
        elif "instagram" in p_name:
          badge_class = "badge-instagram"
        elif "tiktok" in p_name:
          badge_class = "badge-tiktok"
        elif "youtube" in p_name:
          badge_class = "badge-youtube"

        st.markdown(
            f"""
                <div class="result-card">
                    <h4>#{idx} <span class="badge-platform {badge_class}">{res['platform']}</span> - {res['title']}</h4>
                    <p><b>💡 تحليل الذكاء الاصطناعي:</b> <span style="color: #28a745; font-weight: bold;">{res['reason']}</span></p>
                    <p><a href="{res['link']}" target="_blank" style="font-weight: bold; color: #0d6efd; text-decoration: none;">🔗 فتح المنشور الأصلي على {res['platform']}</a></p>
                </div>
                """,
            unsafe_allow_html=True,
        )
    else:
      st.warning(
          "لم يتم العثور على منشورات مطابقة. يرجى التأكد من تفعيل الاتصال"
          " بالمفتاح أو تجربة كلمات مفتاحية إضافية."
      )
