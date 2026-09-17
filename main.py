import os
import re
from duckduckgo_search import DDGS
import google.generativeai as genai
import requests

# 1. استدعاء المفاتيح من متغيرات البيئة
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# إعداد نموذج الذكاء الاصطناعي
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ==========================================
# 2. تخصيص إعدادات الرصد
# ==========================================
# المجال المستهدف بدقة
TARGET_DOMAIN = (
    "المجال المستهدف (مثال: القانون الرياضي، الذكاء الاصطناعي، الإعلام)"
)

# الكلمات المفتاحية
KEYWORDS = ["قانون", "محكمة", "رياضة", "قرار", "جامعة"]

# قائمة الحسابات أو الكيانات المستهدفة على المنصات
# يمكنك وضع معرّف الحساب أو رابط الصفحة لكل منصة
TARGET_PROFILES = [
  {"platform": "YouTube", "query": 'site:youtube.com "@FRMFOfficiel"'},
  {"platform": "X (Twitter)", "query": 'site:x.com/FRMFOFFICIEL'},
  {"platform": "Facebook", "query": 'site:facebook.com/frmf.ma'},
  {"platform": "TikTok", "query": 'site:tiktok.com/@frmf_officiel'},
]

SEEN_FILE = "seen_urls.txt"


def load_seen_urls():
  if not os.path.exists(SEEN_FILE):
    return set()
  with open(SEEN_FILE, "r", encoding="utf-8") as f:
    return set(line.strip() for line in f if line.strip())


def save_seen_url(url):
  with open(SEEN_FILE, "a", encoding="utf-8") as f:
    f.write(url + "\n")


def send_telegram_alert(platform, title, link, reason):
  message = (
      f"🚨 *منشور مطابق جديد تم رصده!*\n\n"
      f"🌐 *المنصة:* {platform}\n"
      f"📌 *العنوان:* {title}\n"
      f"💡 *تحليل الذكاء الاصطناعي:* {reason}\n"
      f"🔗 *الرابط:* {link}"
  )
  url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
  payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
  try:
    requests.post(url, json=payload, timeout=10)
  except Exception as e:
    print(f"Error sending telegram message: {e}")


def analyze_with_gemini(title, snippet, domain, keywords):
  prompt = f"""
أنت مساعد ذكي متخصص في رصد المحتوى الرقمي.
المجال المطلوب: {domain}
الكلمات المفتاحية المطلوبة: {', '.join(keywords)}

المنشور:
العنوان: {title}
المقتطف: {snippet}

المهمة:
هل هذا المحتوى يرتبط فعلياً بالمجال المطلوب ويتضمن موضوعاً ذا صلة بالكلمات المفتاحية؟
أجب بصيغة محددة جداً:
إذا كان مطابقاً، ابدأ السطر بـ YES متبوعة بـ نقطتين وتفسير موجز جداً في جملة واحدة.
إذا كان غير مطابق، اكتب NO فقط.
"""
  try:
    response = model.generate_content(prompt)
    text = response.text.strip()
    if text.startswith("YES"):
      reason = text.replace("YES:", "").replace("YES", "").strip()
      return True, reason
    return False, ""
  except Exception as e:
    print(f"Gemini API error: {e}")
    return False, ""


def main():
  seen_urls = load_seen_urls()
  print("بدء عملية البحث والرصد العميق...")

  with DDGS() as ddgs:
    for target in TARGET_PROFILES:
      platform = target["platform"]
      # دمج كلمات البحث مع معرّف الحساب
      kw_query = " OR ".join([f'"{k}"' for k in KEYWORDS[:3]])
      full_query = f"{target['query']} ({kw_query})"

      print(f"البحث عن: {full_query}")
      try:
        # البحث في الويب عن آخر النتائج
        results = list(ddgs.text(full_query, max_results=5))
        for res in results:
          url = res.get("href")
          title = res.get("title", "")
          body = res.get("body", "")

          if not url or url in seen_urls:
            continue

          # التحليل المعمق بواسطة الذكاء الاصطناعي
          is_relevant, reason = analyze_with_gemini(
              title, body, TARGET_DOMAIN, KEYWORDS
          )

          if is_relevant:
            print(f"تم العثور على محتوى مطابق: {title}")
            send_telegram_alert(platform, title, url, reason)
            save_seen_url(url)
            seen_urls.add(url)
          else:
            # تسجيل الرابط حتى لا يعاد تحليله كل مرة
            save_seen_url(url)
            seen_urls.add(url)

      except Exception as e:
        print(f"خطأ أثناء البحث في {platform}: {e}")

  print("انتهت دورة الرصد بنجاح.")


if __name__ == "__main__":
  main()
