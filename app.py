import base64
import concurrent.futures
import functools
import hashlib
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import gc
import gzip
import html
import io
import struct
import wave
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET

import requests

try:
  import streamlit as st
except ImportError:
  st = None

try:
  import google.generativeai as genai
except ImportError:
  genai = None

try:
  from duckduckgo_search import DDGS
except ImportError:
  DDGS = None

try:
  from bs4 import BeautifulSoup
except ImportError:
  BeautifulSoup = None

# =====================================================================
# 1. إعدادات النظام والثوابت الأساسية والفلاتر الصارمة
# =====================================================================
REPO_DB_FILE = "morocco_justice_hub.db"
DB_FILE = os.path.join(tempfile.gettempdir(), "morocco_justice_hub_runtime.db")
PERSISTENT_HOME_DB = os.path.join(os.path.expanduser("~"), ".morocco_justice_hub_persistent.db")
ARCHIVE_JSON_FILE = "articles_archive.json"
PERSISTENT_HOME_ARCHIVE_JSON = os.path.join(os.path.expanduser("~"), ".morocco_justice_archive_persistent.json")
CREDENTIALS_FILE = "credentials.json"
CUSTOM_TARGETS_FILE = "custom_targets.json"
PLATFORM_KEYWORD_TRACKERS_FILE = "platform_keyword_trackers.json"
MONITOR_STATE_FILE = "monitor_state.json"
TELEGRAM_LEDGER_FILE = "telegram_sent_ledger.json"

DEFAULT_TG_TOKEN = "8806182263:AAFw5HbBup_TRif3FHvZP0QFYj0YPI4mb6c"
DEFAULT_TG_CHAT_ID = "1357905784"
PLATFORM_OFFICIAL_NAME = "المرصد القضائي"
LEGACY_PLATFORM_NAME = "المرصد الوطني للعدالة والقضاء"
DAEMON_CODE_VERSION = "marsad_qadai_v7_2026_10_22_turbo_nonblocking"

GEMINI_MODELS_FALLBACK = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-3.5-flash-lite",
]
_WORKING_GEMINI_MODEL = None

DEFAULT_JUDICIAL_QUERIES = [
    "المجلس الأعلى للسلطة القضائية المغرب",
    "المجلس الأعلى للسلطة القضائية",
    "رئاسة النيابة العامة المغرب",
    "الشؤون القضائية المغرب",
    "القضاة بالمغرب",
    "القضاء بالمغرب",
    "العدالة بالمغرب",
    "محكمة النقض المغرب",
    "نادي قضاة المغرب",
    "الودادية الحسنية للقضاة",
    "المعهد العالي للقضاء المغرب",
    "المسطرة الجنائية المغرب",
]

# مصطلحات قضائية وعدلية مغربية خالصة (تدل بذاتها قطعيّاً على الشأن القضائي والعدلي بالمغرب)
STRICT_JUDICIAL_UNAMBIGUOUS = [
    "المجلس الأعلى للسلطة القضائية",
    "المجلس الاعلى للسلطة القضائية",
    "المفتشية العامة للشؤون القضائية",
    "رئاسة النيابة العامة بالمغرب",
    "النيابة العامة بالمغرب",
    "المعهد العالي للقضاء",
    "الودادية الحسنية للقضاة",
    "نادي قضاة المغرب",
    "محمد عبد النباوي",
    "عبد النباوي",
    "هشام البلاوي",
    "مولاي الحسن الداكي",
    "الحسن الداكي",
    "عبد اللطيف وهبي",
    "الوكيل العام للملك",
    "وكيل الملك",
    "القضاء المغربي",
    "القضاء بالمغرب",
    "القضاء في المغرب",
    "العدالة بالمغرب",
    "العدالة في المغرب",
    "القضاة بالمغرب",
    "القضاة في المغرب",
    "قضاة المغرب",
    "قضاة المملكة",
    "المحاكم المغربية",
    "محاكم المملكة",
    "بوابة المحاكم المغربية",
    "محكمة النقض بالرباط",
    "وزارة العدل المغربية",
    "وزير العدل المغربي",
    "الفرقة الوطنية للشرطة القضائية",
]

# مصطلحات قضائية وعدلية وقانونية عامة (يشترط لقبولها توفر سياق مغربي صريح وموثق)
JUDICIAL_GENERAL_TERMS = [
    "المجلس الأعلى للقضاء",
    "السلطة القضائية",
    "الشؤون القضائية",
    "رئاسة النيابة العامة",
    "النيابة العامة",
    "محكمة النقض",
    "محكمة الاستئناف",
    "المحكمة الابتدائية",
    "المحكمة الإدارية",
    "المحكمة التجارية",
    "المحكمة الدستورية",
    "المحاكم الإدارية",
    "المحاكم التجارية",
    "المحاكم الابتدائية",
    "محاكم الاستئناف",
    "قضاء الأسرة",
    "قسم قضاء الأسرة",
    "قضاء القرب",
    "قاضي التحقيق",
    "قاضي التطبيق",
    "قاضي الأحداث",
    "قاضي التوثيق",
    "المستشار المقرر",
    "هيئة الحكم",
    "غرفة الجنايات",
    "الغرفة الجنائية",
    "الغرفة الجنحية",
    "الغرفة المدنية",
    "الغرفة العقارية",
    "الغرفة التجارية",
    "الغرفة الإدارية",
    "القضاء",
    "قضائي",
    "قضائية",
    "القضائي",
    "القضائية",
    "القضاة",
    "قضاة",
    "القاضي",
    "للقضاة",
    "المحاكم",
    "محكمة",
    "العدالة",
    "عدلي",
    "عدلية",
    "منظومة العدالة",
    "إصلاح العدالة",
    "تحديث العدالة",
    "رقمنة العدالة",
    "رقمنة المحاكم",
    "وزارة العدل",
    "وزير العدل",
    "المسطرة الجنائية",
    "المسطرة المدنية",
    "القانون الجنائي",
    "مدونة الأسرة",
    "التنظيم القضائي",
    "العقوبات البديلة",
    "قانون العقوبات البديلة",
    "الاعتقال الاحتياطي",
    "السوار الإلكتروني",
    "الحراسة النظرية",
    "التحقيق الإعدادي",
    "المتابعة القضائية",
    "متابعة قضائية",
    "حكم قضائي",
    "أحكام قضائية",
    "قرار قضائي",
    "ملف قضائي",
    "الأمن القضائي",
    "النجاعة القضائية",
    "الاجتهاد القضائي",
    "السنة القضائية",
    "افتتاح السنة القضائية",
    "الحركة الانتقالية للقضاة",
    "التعيينات القضائية",
    "المسؤولين القضائيين",
    "الملحقين القضائيين",
    "استقلال القضاء",
    "استقلالية القضاء",
    "أخلاقيات القضاء",
    "هيئة المحامين",
    "جمعية هيئات المحامين",
    "نقيب المحامين",
    "المحامون",
    "المحامين",
    "مهنة المحاماة",
    "الضابطة القضائية",
    "الشرطة القضائية",
    "المفوضين القضائيين",
    "المفوضون القضائيون",
    "مفوض قضائي",
    "هيئة العدول",
    "خطة العدالة",
    "كتابة الضبط",
    "هيئة كتابة الضبط",
    "الخبراء القضائيون",
    "التراجمة المحلفون",
    "الموثقون",
    "هيئة الموثقين",
    "هيئة الدفاع",
    "المحاكمة العادلة",
    "المحاكمة عن بعد",
    "السجل العدلي",
    "السجن المحلي",
]

# مؤشرات السياق المغربي الصريحة (تُطابق ككلمات كاملة فقط لمنع أي التباس لفظي مع كلمات عامة)
MOROCCAN_CONTEXT_TERMS = [
    "المغرب",
    "مغربي",
    "مغربية",
    "مغاربة",
    "المغاربة",
    "بالمغرب",
    "المملكة المغربية",
    "الرباط",
    "الدار البيضاء",
    "مراكش",
    "فاس",
    "طنجة",
    "أكادير",
    "اكادير",
    "وجدة",
    "مكناس",
    "تطوان",
    "القنيطرة",
    "سلا",
    "الداخلة",
    "بني ملال",
    "آسفي",
    "الجديدة",
    "الناظور",
    "الحسيمة",
    "تازة",
    "سطات",
    "برشيد",
    "المحمدية",
    "تمارة",
    "كلميم",
    "الرشيدية",
    "خريبكة",
    "العرائش",
    "القصر الكبير",
    "الخميسات",
    "تارودانت",
    "ورزازات",
    "تيزنيت",
    "الصويرة",
    "صفرو",
    "إفران",
    "خنيفرة",
    "جرسيف",
    "تاوريرت",
    "سيدي قاسم",
    "سيدي سليمان",
    "بن جرير",
    "اليوسفية",
    "مدينة العيون",
    "استئنافية العيون",
    "ابتدائية العيون",
    "مدينة بركان",
    "ابتدائية بركان",
    "إقليم بركان",
    "عبد النباوي",
    "عبد اللطيف وهبي",
    "هشام البلاوي",
    "الحسن الداكي",
    "الداكي",
    "الوكيل العام للملك",
    "وكيل الملك",
    "هسبريس",
    "أخبارنا المغربية",
    "العمق المغربي",
    "جريدة الصباح",
    "برلمان كوم",
    "زنقة 20",
    "اليوم 24",
    "الأيام 24",
    "مدار 21",
    "كش 24",
    "أكادير 24",
    "طنجة 24",
    "ناظورسيتي",
    "القناة الثانية",
    "القناة الأولى",
    "مدي 1",
    "ميدي 1",
    "هبة بريس",
    "شوف تيفي",
]

# قائمة صارمة لاستبعاد أخبار التكنولوجيا، مايكروسوفت، تحديثات وأعطال منصة فيسبوك/ميتا، والأخبار الدولية أو الرياضية غير القضائية
BLOCKED_NON_JUDICIAL_AND_FOREIGN_TERMS = [
    "مايكروسوفت",
    "ميكروسوفت",
    "microsoft",
    "ويندوز",
    "windows 10",
    "windows 11",
    "office 365",
    "إكس بوكس",
    "xbox",
    "بلايستيشن",
    "playstation",
    "آيفون",
    "iphone",
    "آيباد",
    "ipad",
    "أندرويد",
    "android",
    "سامسونج",
    "samsung",
    "هواوي",
    "شاومي",
    "عطل فيسبوك",
    "عطل فايسبوك",
    "توقف فيسبوك",
    "تحديث فيسبوك",
    "تحديث تطبيق فيسبوك",
    "ميزة جديدة في فيسبوك",
    "ميزة جديدة في واتساب",
    "تحديث واتساب",
    "عطل واتساب",
    "عطل انستغرام",
    "مارك زوكربيرغ",
    "زوكربيرغ",
    "zuckerberg",
    "شركة ميتا",
    "أرباح ميتا",
    "سهم ميتا",
    "أسهم ميتا",
    "تطبيق ثريدز",
    "خوارزمية فيسبوك",
    "الربح من فيسبوك",
    "إعلانات فيسبوك",
    "استرجاع حساب فيسبوك",
    "تأمين حساب فيسبوك",
    "القضاء المصري",
    "محكمة النقض المصرية",
    "النيابة العامة المصرية",
    "النائب العام المصري",
    "مجلس الدولة المصري",
    "محكمة جنايات القاهرة",
    "محكمة جنايات الجيزة",
    "محكمة الأسرة بمصر",
    "القضاء التونسي",
    "القضاء الجزائري",
    "القضاء اللبناني",
    "القضاء السوري",
    "القضاء العراقي",
    "القضاء الأردني",
    "القضاء الكويتي",
    "القضاء السوداني",
    "القضاء الليبي",
    "القضاء اليمني",
    "القضاء الإيراني",
    "السلطة القضائية الإيرانية",
    "السلطة القضائية في إيران",
    "المحكمة العليا الأمريكية",
    "المحكمة العليا الإسرائيلية",
    "القضاء الإسرائيلي",
    "القضاء الفرنسي",
    "القضاء الإسباني",
    "القضاء البريطاني",
    "الكنيست",
    "الكونغرس الأمريكي",
    "البنتاغون",
    "دوري أبطال أوروبا",
    "دوري أبطال أفريقيا",
    "ريال مدريد",
    "برشلونة",
    "مانشستر سيتي",
    "مانشستر يونايتد",
    "ليفربول",
    "توقعات الأبراج",
    "حظك اليوم",
]

BLOCKED_NON_JUDICIAL_DOMAINS = (
    "microsoft.com",
    "msn.com",
    "live.com",
    "office.com",
    "windows.com",
    "xbox.com",
    "apple.com",
    "about.fb.com",
    "investor.fb.com",
    "meta.com",
    "developers.facebook.com",
    "techcrunch.com",
    "theverge.com",
    "aitnews.com",
    "unlimit-tech.com",
    "arageek.com",
    "youm7.com",
    "masrawy.com",
    "elwatannews.com",
    "shorouknews.com",
    "almasryalyoum.com",
    "vetogate.com",
    "akhbarelyom.com",
    "elbalad.news",
    "annahar.com",
    "echoroukonline.com",
    "ennaharonline.com",
    "elkhabar.com",
    "mosaiquefm.net",
    "jawharafm.net",
    "babnet.net",
    "turess.com",
    "irna.ir",
    "tasnimnews.com",
    "mehrnews.com",
    "sana.sy",
    "petra.gov.jo",
    "spa.gov.sa",
    "wam.ae",
    "kuna.net.kw",
    "qna.org.qa",
)

MOROCCAN_TRUSTED_MEDIA_DOMAINS = (
    "hespress.com",
    "al3omk.com",
    "alyaoum24.com",
    "madar21.com",
    "alayam24.com",
    "akhbarona.com",
    "goud.ma",
    "assabah.ma",
    "rue20.com",
    "kech24.com",
    "agadir24.info",
    "sabahagadir.com",
    "tanja24.com",
    "barlamane.com",
    "le360.ma",
    "hibapress.com",
    "nadorcity.com",
    "thevoice.ma",
    "snrtnews.com",
    "mapexpress.ma",
    "mapnews.ma",
    "2m.ma",
    "medi1tv.com",
    "aljarida24.ma",
    "febrayer.com",
    "lakome2.com",
    "anfaspress.com",
    "achtari24.com",
    "chattpress.com",
    "alittihad.info",
    "cspj.ma",
    "pmp.ma",
    "justice.gov.ma",
    "mahakim.ma",
)

BLOCKED_INAPPROPRIATE_TERMS = [
    "سكس",
    "إباحي",
    "اباحي",
    "اباحية",
    "إباحية",
    "جنس",
    "جنسي",
    "جنسية",
    "عاري",
    "عارية",
    "عراه",
    "بورن",
    "بورنو",
    "نيك",
    "شرموط",
    "قحب",
    "طيز",
    "زب",
    "كس ",
    "ثدي",
    "بزاز",
    "سحاق",
    "لواط",
    "شذوذ",
    "فضيحة",
    "فضائح",
    "روتيني اليومي",
    "رقص",
    "راقصة",
    "خلع",
    "مثير",
    "مثيرة",
    "ساخن",
    "ساخنة",
    "للكبار فقط",
    "+18",
    "18+",
    "فيلم كامل",
    "مشاهدة فيلم",
    "مسلسل",
    "حلقة",
    "كازينو",
    "مراهنات",
    "ربح المال",
    "تعارف",
    "زواج متعة",
    "مسيار",
    "شاجر",
    "porn",
    "xxx",
    "sex",
    "sexy",
    "nude",
    "naked",
    "nsfw",
    "onlyfans",
    "escort",
    "casino",
    "betting",
    "1xbet",
    "erotic",
    "hentai",
    "xvideos",
    "xnxx",
    "pornhub",
    "stripchat",
    "chaturbate",
    "cam4",
    "brazzers",
    "redtube",
    "youporn",
    "spankbang",
    "rule34",
    "jav",
    "milf",
    "fetish",
    "webcam",
    "hookup",
    "dating",
    "boobs",
    "pussy",
    "dick",
    "cock",
    "ass ",
    "anal",
    "blowjob",
    "bdsm",
    "lesbian",
    "gay",
    "transgender",
    "adult",
]

MOROCCAN_PRESS_SITES = [
    {"domain": "hespress.com", "name": "هسبريس", "rss": "https://www.hespress.com/feed"},
    {"domain": "akhbarona.com", "name": "أخبارنا", "rss": "https://www.akhbarona.com/feed"},
    {"domain": "agadir24.info", "name": "أكادير 24", "rss": "https://agadir24.info/feed"},
    {"domain": "kech24.com", "name": "كش 24", "rss": "https://www.kech24.com/feed"},
    {"domain": "alayam24.com", "name": "الأيام 24", "rss": "https://www.alayam24.com/feed"},
    {"domain": "madar21.com", "name": "مدار 21", "rss": "https://madar21.com/feed"},
    {"domain": "sabahagadir.com", "name": "صباح أكادير", "rss": "https://sabahagadir.com/feed"},
    {"domain": "goud.ma", "name": "كود", "rss": "https://www.goud.ma/feed"},
    {"domain": "assabah.ma", "name": "الصباح", "rss": "https://assabah.ma/feed"},
    {"domain": "thevoice.ma", "name": "ذا فويس", "rss": "https://thevoice.ma/feed"},
    {"domain": "nadorcity.com", "name": "ناظورسيتي", "rss": ""},
    {"domain": "al3omk.com", "name": "العمق المغربي", "rss": "https://al3omk.com/feed"},
    {"domain": "alyaoum24.com", "name": "اليوم 24", "rss": "https://alyaoum24.com/feed"},
    {"domain": "rue20.com", "name": "زنقة 20", "rss": "https://rue20.com/feed"},
    {"domain": "le360.ma", "name": "Le360", "rss": ""},
    {"domain": "barlamane.com", "name": "برلمان.كوم", "rss": "https://www.barlamane.com/feed"},
    {"domain": "tanja24.com", "name": "طنجة 24", "rss": "https://tanja24.com/feed"},
]

YT_BYPASS_COOKIES = {
    "SOCS": "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg",
    "CONSENT": "PENDING+999",
}

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar-MA,ar;q=0.9,fr-MA;q=0.8,fr;q=0.7,en;q=0.6",
}

# ترويسات خاصة يسمح لها فيسبوك بقراءة بيانات الصفحات والمنشورات العامة دون طلب تسجيل الدخول
FB_CRAWLER_HEADERS = {
    "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Accept-Language": "ar-MA,ar;q=0.9,fr;q=0.8,en;q=0.7",
}

FB_PREVIEW_BOT_HEADERS = [
    FB_CRAWLER_HEADERS,
    {
        "User-Agent": "WhatsApp/2.24.12.78 A",
        "Accept-Language": "ar-MA,ar;q=0.9,fr;q=0.8,en;q=0.7",
    },
    {
        "User-Agent": "TelegramBot (like TwitterBot)",
        "Accept-Language": "ar-MA,ar;q=0.9,fr;q=0.8,en;q=0.7",
    },
    {
        "User-Agent": "Twitterbot/1.0",
        "Accept-Language": "ar-MA,ar;q=0.9,fr;q=0.8,en;q=0.7",
    },
]

INTERVAL_MAP = {
    "كل 15 دقيقة": 900,
    "كل ساعة": 3600,
    "كل 3 ساعات": 10800,
    "كل 6 ساعات": 21600,
    "كل 12 ساعة": 43200,
    "كل 24 ساعة": 86400,
}

SEARCH_PERIOD_MAP = {
    "آخر ساعة": {
        "sec": 3600,
        "gnews": "1h",
        "ddg": "d",
        "yt": "EgIIAQ%3D%3D",
        "yt_date": "CAISBAgBEAE%3D",
        "yt_raw": "EgIIAQ==",
        "yt_date_raw": "CAISBAgBEAE=",
    },
    "آخر 24 ساعة": {
        "sec": 86400,
        "gnews": "1d",
        "ddg": "d",
        "yt": "EgIIAg%3D%3D",
        "yt_date": "CAISBAgCEAE%3D",
        "yt_raw": "EgIIAg==",
        "yt_date_raw": "CAISBAgCEAE=",
    },
    "آخر 7 أيام": {
        "sec": 7 * 86400,
        "gnews": "7d",
        "ddg": "w",
        "yt": "EgIIAw%3D%3D",
        "yt_date": "CAISBAgDEAE%3D",
        "yt_raw": "EgIIAw==",
        "yt_date_raw": "CAISBAgDEAE=",
    },
    "آخر شهر": {
        "sec": 30 * 86400,
        "gnews": "30d",
        "ddg": "m",
        "yt": "EgIIBA%3D%3D",
        "yt_date": "CAISBAgEEAE%3D",
        "yt_raw": "EgIIBA==",
        "yt_date_raw": "CAISBAgEEAE=",
    },
    "آخر 3 أشهر": {
        "sec": 90 * 86400,
        "gnews": "90d",
        "ddg": "y",
        "yt": "CAI%3D",
        "yt_date": "CAISAhAB",
        "yt_raw": "CAI=",
        "yt_date_raw": "CAISAhAB",
    },
    "آخر 6 أشهر": {
        "sec": 180 * 86400,
        "gnews": "180d",
        "ddg": "y",
        "yt": "CAI%3D",
        "yt_date": "CAISAhAB",
        "yt_raw": "CAI=",
        "yt_date_raw": "CAISAhAB",
    },
    "آخر 12 شهراً": {
        "sec": 365 * 86400,
        "gnews": "1y",
        "ddg": "y",
        "yt": "EgIIBQ%3D%3D",
        "yt_date": "CAISBAgFEAE%3D",
        "yt_raw": "EgIIBQ==",
        "yt_date_raw": "CAISBAgFEAE=",
    },
}

ARABIC_MONTHS = {
    "يناير": 1,
    "كانون الثاني": 1,
    "فبراير": 2,
    "شباط": 2,
    "مارس": 3,
    "آذار": 3,
    "اذار": 3,
    "أبريل": 4,
    "ابريل": 4,
    "نيسان": 4,
    "ماي": 5,
    "مايو": 5,
    "أيار": 5,
    "ايار": 5,
    "يونيو": 6,
    "حزيران": 6,
    "يوليوز": 7,
    "يوليو": 7,
    "تموز": 7,
    "غشت": 8,
    "أغسطس": 8,
    "اغسطس": 8,
    "آب": 8,
    "اب": 8,
    "شتنبر": 9,
    "سبتمبر": 9,
    "أيلول": 9,
    "ايلول": 9,
    "أكتوبر": 10,
    "اكتوبر": 10,
    "تشرين الأول": 10,
    "تشرين الاول": 10,
    "نونبر": 11,
    "نوفمبر": 11,
    "تشرين الثاني": 11,
    "دجنبر": 12,
    "ديسمبر": 12,
    "كانون الأول": 12,
    "كانون الاول": 12,
}

ENGLISH_MONTHS = {
    "jan": 1,
    "janv": 1,
    "feb": 2,
    "fevr": 2,
    "févr": 2,
    "mar": 3,
    "mars": 3,
    "apr": 4,
    "avr": 4,
    "may": 5,
    "mai": 5,
    "jun": 6,
    "juin": 6,
    "jul": 7,
    "juil": 7,
    "aug": 8,
    "aout": 8,
    "août": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
    "déc": 12,
}


def compact_html(raw_html: str) -> str:
  return "\n".join(
      line.strip() for line in str(raw_html).splitlines() if line.strip()
  )


def render_html(raw_html: str, target=None):
  cleaned = compact_html(raw_html)
  if target is not None:
    target.markdown(cleaned, unsafe_allow_html=True)
  elif st is not None:
    st.markdown(cleaned, unsafe_allow_html=True)


def clean_full_article_text(val: str) -> str:
  """تنظيف النص الكامل للمقال مع الحفاظ على تقسيم الفقرات (\n\n) لعرضه بشكل مريح في نافذة المعاينة الكاملة."""
  if not val:
    return ""
  txt = str(val).strip()
  txt = html.unescape(txt)
  txt = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]", "", txt)
  txt = re.sub(r"<\s*br\s*/?\s*>", "\n", txt, flags=re.IGNORECASE)
  txt = re.sub(r"</\s*(?:p|div|li|h[1-6]|blockquote|tr)\s*>", "\n\n", txt, flags=re.IGNORECASE)
  txt = re.sub(r"<[^>]+>", " ", txt)
  paragraphs = []
  for raw_line in re.split(r"\n+", txt):
    line = re.sub(r"[ \t\r]+", " ", raw_line).strip()
    if len(line) >= 3:
      if not paragraphs or paragraphs[-1] != line:
        paragraphs.append(line)
  res_full = "\n\n".join(paragraphs).strip()
  res_full = re.sub(r"\s*\[(?:رصد فيسبوك|رصد)[^\]]*الكلمة المفتاحية:[^\]]*\]", "", res_full)
  return res_full.replace("المرصد الوطني للعدالة والقضاء", "المرصد القضائي").strip()


def _arabic_token_matches_in_text(tok: str, norm_text: str) -> bool:
  """التحقق الذكي من وجود المفردة العربية في النص مع مراعاة الـ التعريف واللواصق العربية (لـ، بـ، و، فـ، كـ)."""
  if not tok:
    return True
  if tok in norm_text:
    return True
  stem = re.sub(r"^(?:وال|بال|لل|فال|كال|ال)", "", tok)
  if len(stem) >= 3:
    if stem in norm_text:
      return True
    if re.search(rf"(?:^|\s)(?:ال|وال|بال|لل|فال|كال|و|ف|ب|ل)?{re.escape(stem)}", norm_text):
      return True
  return False


def matches_custom_keywords(title: str, snippet: str, keywords_input: str) -> bool:
  """التحقق الدقيق من تطابق الخبر مع الكلمات أو العبارات المفتاحية التي أدخلها المستخدم (بعد تطبيع الهمزات والتاء المربوطة واللواصق العربية للمفردات والعبارات)."""
  if not keywords_input or not str(keywords_input).strip():
    return True
  raw_kws = [
      k.strip().strip('"\'«» ')
      for k in re.split(r"[,،\n]+", str(keywords_input))
      if k.strip().strip('"\'«» ')
  ]
  if not raw_kws:
    return True

  norm_combined = normalize_arabic_for_dedup(f"{title or ''} {snippet or ''}")
  raw_combined_low = f"{clean_display_text(title)} {clean_display_text(snippet)}".lower()

  for kw in raw_kws:
    norm_kw = normalize_arabic_for_dedup(kw)
    if not norm_kw:
      continue
    if norm_kw in norm_combined or kw.lower() in raw_combined_low:
      return True
    kw_tokens = [w for w in norm_kw.split() if len(w) >= 2]
    if kw_tokens and all(_arabic_token_matches_in_text(tok, norm_combined) for tok in kw_tokens):
      return True
  return False


@functools.lru_cache(maxsize=8192)
def clean_display_text(val: str) -> str:
  if not val:
    return ""
  txt = str(val).strip()
  txt = (
      re.sub(r"```(?:json|html)?", "", txt, flags=re.IGNORECASE)
      .replace("```", "")
      .strip()
  )
  if txt.startswith("{") and "summary" in txt:
    try:
      parsed = json.loads(txt)
      if isinstance(parsed, dict) and parsed.get("summary"):
        txt = str(parsed["summary"])
    except Exception:
      m = re.search(r'"summary"\s*:\s*"([^"]+)"', txt)
      if m:
        txt = m.group(1)
  txt = html.unescape(txt)
  txt = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]", "", txt)
  txt = re.sub(r"<[^>]+>", " ", txt)
  txt = re.sub(r"[\r\n\t]+", " ", txt)
  txt = re.sub(r"\[(?:رصد فيسبوك|رصد)[^\]]*الكلمة المفتاحية:[^\]]*\]", " ", txt)
  txt = re.sub(r"\s+", " ", txt).strip()
  return txt.replace("المرصد الوطني للعدالة والقضاء", "المرصد القضائي")


def strip_internal_url_fragments(url: str) -> str:
  return re.sub(r"#(?:plat|kwtrack|v4target|v3target|v2target|target)=[^\s#]*", "", str(url or "").strip())


def extract_internal_url_fragments(url: str) -> str:
  """استخراج كافة الوسوم الداخلية (#plat=... و #kwtrack=... و #v4target=...) للحفاظ عليها عند فك روابط Google News أو Bing."""
  tags = re.findall(r"#(?:plat|kwtrack|v4target|v3target|v2target|target)=[^\s#]*", str(url or "").strip())
  unique_tags = []
  for t in tags:
    if t not in unique_tags:
      unique_tags.append(t)
  return "".join(unique_tags)


def strip_source_suffix_from_title(title: str) -> str:
  """إزالة اسم الجريدة أو المنصة الملحق بنهاية العنوان (مثل: - هسبريس أو | العمق المغربي) لتوحيد بصمة العنوان عبر كافة المصادر."""
  t = clean_display_text(title)
  if not t:
    return ""
  # إزالة اللواحق القصيرة بعد الشرطة أو العمود الفاصل في نهاية العنوان
  for sep in (" - ", " – ", " — ", " | ", " // "):
    if sep in t:
      parts = t.rsplit(sep, 1)
      if len(parts[0].strip()) >= 18 and 2 <= len(parts[1].strip()) <= 32:
        t = parts[0].strip()
  return t


@functools.lru_cache(maxsize=8192)
def normalize_arabic_for_dedup(text: str) -> str:
  """تطبيع النص العربي بدقة عالية لكشف الأخبار والمنشورات المكررة حتى مع اختلاف التشكيل أو علامات الترقيم أو الهمزات."""
  if not text:
    return ""
  t = clean_display_text(text).lower()
  t = re.sub(r"https?://\S+", " ", t)
  t = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", t)
  t = re.sub(r"[أإآٱ]", "ا", t)
  t = re.sub(r"ة", "ه", t)
  t = re.sub(r"ى", "ي", t)
  t = re.sub(r"ؤ", "و", t)
  t = re.sub(r"ئ", "ي", t)
  t = re.sub(r"[^\u0600-\u06FFa-z0-9\s]", " ", t)
  t = re.sub(r"\s+", " ", t).strip()
  return t


def extract_canonical_post_or_video_id(url: str) -> str:
  """استخراج المعرف الفريد للفيديو أو المنشور (YouTube / Facebook / X) لمنع تكرار نفس المنشور بصيغ روابط مختلفة."""
  u = clean_social_post_url(url)
  if not u:
    return ""
  m_yt = re.search(
      r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
      u,
  )
  if m_yt:
    return f"yt:{m_yt.group(1)}"

  m_x = re.search(r"(?:x\.com|twitter\.com)/[^/]+/status/(\d{10,22})", u, re.IGNORECASE)
  if m_x:
    return f"x:{m_x.group(1)}"

  if "facebook.com" in u.lower() or "fb.watch" in u.lower():
    parsed = urllib.parse.urlparse(u)
    qs = urllib.parse.parse_qs(parsed.query)
    for k in ("story_fbid", "fbid", "v", "post_id", "post_ref", "q"):
      if qs.get(k) and len(qs[k][0].strip()) >= 4:
        val_k = qs[k][0].strip()
        if k == "q":
          val_k = hashlib.md5(val_k.encode("utf-8", errors="ignore")).hexdigest()[:12]
        return f"fb:{val_k}"
    parts = [p.strip() for p in urllib.parse.unquote(parsed.path).strip("/").split("/") if p.strip()]
    for idx, seg in enumerate(parts):
      if seg.lower() in ("posts", "videos", "reel", "reels", "photos", "permalink") and idx + 1 < len(parts):
        tail = parts[-1].strip()
        if tail.startswith("pfbid") or (tail.isdigit() and len(tail) >= 7):
          return f"fb:{tail}"
  return ""


def canonicalize_url_for_dedup(url: str) -> str:
  """توحيد الرابط الأساسي بدون وسوم داخلية أو معاملات تتبع لضمان عدم جلب أو إرسال نفس الخبر مرتين."""
  u = clean_social_post_url(url)
  if not u:
    return ""
  try:
    p = urllib.parse.urlparse(u)
    netloc = p.netloc.lower().replace("www.", "").replace("m.", "").replace("web.", "")
    # روابط Google News تتغير رموزها باستمرار لنفس الخبر، لذلك لا نعتمد على مسارها كمعرف وحيد
    if "news.google.com" in netloc:
      return ""
    path = urllib.parse.unquote(p.path).rstrip("/")
    if netloc in ("youtube.com", "youtu.be", "facebook.com", "x.com", "twitter.com"):
      pid = extract_canonical_post_or_video_id(u)
      if pid:
        return f"{netloc}/{pid}"
    return f"{netloc}{path}".lower()
  except Exception:
    return u.lower()


def compute_article_dedup_keys(title: str, url: str) -> set:
  """توليد مفاتيح البصمة الفريدة للخبر (الرابط الموحد + معرف المنشور + البصمة النصية الكاملة وبصمة صدر العنوان بدون اسم الجريدة)."""
  keys = set()
  raw_u = strip_internal_url_fragments(url)
  if raw_u and "news.google.com" not in raw_u.lower():
    keys.add(f"raw_u:{raw_u.lower().rstrip('/')}")
  canon_u = canonicalize_url_for_dedup(url)
  if canon_u and len(canon_u) >= 6:
    keys.add(f"canon_u:{canon_u}")
  pid = extract_canonical_post_or_video_id(url)
  if pid:
    keys.add(f"pid:{pid}")

  core_title = strip_source_suffix_from_title(title)
  for t_variant in (title, core_title):
    norm_t = normalize_arabic_for_dedup(t_variant)
    if len(norm_t) >= 14:
      keys.add(f"title:{norm_t[:85]}")
      keys.add(f"title_head:{norm_t[:46]}")
      words = [w for w in norm_t.split() if len(w) >= 2]
      if len(words) >= 5:
        keys.add(f"title_words:{' '.join(words[:8])}")
  return keys


def clean_social_post_url(url: str) -> str:
  """تنظيف وفك تغليف روابط منصات التواصل الاجتماعي مع الحفاظ الكامل على معرفات المنشور (story_fbid, id, fbid, v)."""
  u = strip_internal_url_fragments(url)
  if not u:
    return ""
  u = html.unescape(u).strip()

  # فك تغليف روابط Yahoo Search Redirect (/RU=https%3A%2F%2F.../RK=...)
  m_yahoo = re.search(r"/RU=(https?%3A%2F%2F[^/]+)/RK=", u, re.IGNORECASE)
  if m_yahoo:
    try:
      u = urllib.parse.unquote(m_yahoo.group(1)).strip()
    except Exception:
      pass

  # فك تغليف روابط DuckDuckGo Redirect (//duckduckgo.com/l/?uddg=...)
  if "uddg=" in u:
    try:
      qs_d = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
      if "uddg" in qs_d and qs_d["uddg"]:
        u = qs_d["uddg"][0].strip()
    except Exception:
      pass

  # فك تغليف روابط Bing RSS أو Bing Click
  if "bing.com/" in u.lower() and ("url=" in u or "u=" in u):
    try:
      qs_b = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
      if "url" in qs_b and qs_b["url"]:
        u = qs_b["url"][0].strip()
      elif "u" in qs_b and qs_b["u"]:
        raw_b = qs_b["u"][0].strip()
        if raw_b.startswith("a1"):
          padded = raw_b[2:] + "=" * ((4 - len(raw_b[2:]) % 4) % 4)
          u = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
    except Exception:
      pass

  # تحويل المسارات النسبية لفيسبوك إلى روابط كاملة
  if u.startswith("/") and not u.startswith("//"):
    u = urllib.parse.urljoin("https://www.facebook.com", u)
  elif u.startswith("//"):
    u = "https:" + u

  # فك تغليف روابط مشاركة أو تحويل فيسبوك (sharer.php, plugins/post.php, plugins/video.php, l.php, login.php)
  for _ in range(2):
    parsed_wrap = urllib.parse.urlparse(u)
    path_low = parsed_wrap.path.lower()
    if any(
        w in path_low
        for w in [
            "/sharer",
            "/plugins/post.php",
            "/plugins/video.php",
            "/l.php",
            "/login",
        ]
    ):
      qs_w = urllib.parse.parse_qs(parsed_wrap.query)
      inner_u = (
          (qs_w.get("u") or [None])[0]
          or (qs_w.get("href") or [None])[0]
          or (qs_w.get("next") or [None])[0]
      )
      if inner_u and inner_u.startswith("http"):
        u = html.unescape(inner_u).strip()
      else:
        break
    else:
      break

  try:
    parsed = urllib.parse.urlparse(u)
    netloc_low = parsed.netloc.lower()
    if netloc_low.endswith("facebook.com") or netloc_low == "fb.com":
      clean_netloc = "www.facebook.com"
      keep_params = {
          "story_fbid",
          "id",
          "fbid",
          "v",
          "set",
          "multi_permalinks",
          "post_id",
          "post_ref",
          "q",
      }
      filtered_qs = [
          (k, val)
          for k, val in urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
          if k.lower() in keep_params
      ]
      new_query = urllib.parse.urlencode(filtered_qs)
      u = urllib.parse.urlunparse(
          ("https", clean_netloc, parsed.path, "", new_query, "")
      )
  except Exception:
    pass

  return u


def is_direct_social_post_url(
    url: str, platform: str = "", allow_post_search: bool = False
) -> bool:
  """التحقق الصارم من أن الرابط يوجه إلى المنشور/الفيديو/التغريدة بعينها وليس إلى الصفحة العامة أو تبويب فرعي."""
  u = clean_social_post_url(url)
  if not u or not u.startswith("http"):
    return False

  parsed = urllib.parse.urlparse(u)
  dom = parsed.netloc.lower()
  path = urllib.parse.unquote(parsed.path).strip("/")
  path_low = path.lower()
  qs = urllib.parse.parse_qs(parsed.query)

  is_fb = (
      platform == "فيسبوك"
      or "facebook.com" in dom
      or "fb.com" in dom
      or "fb.watch" in dom
  )
  is_x = platform == "إكس" or "x.com" in dom or "twitter.com" in dom
  is_yt = platform == "يوتيوب" or "youtube.com" in dom or "youtu.be" in dom

  if is_fb:
    if "fb.watch" in dom and len(path) >= 4:
      return True
    if (
        (qs.get("story_fbid") or [""])[0].strip()
        or (qs.get("fbid") or [""])[0].strip()
        or (qs.get("post_id") or [""])[0].strip()
        or (qs.get("post_ref") or [""])[0].strip()
    ):
      return True
    if ("search/posts" in path_low or "search/top" in path_low) and len((qs.get("q") or [""])[0].strip()) >= 4:
      return True
    if any(
        bad in path_low
        for bad in [
            "plugins/page.php",
            "login",
            "sharer",
            "pages/category",
        ]
    ):
      return False

    if path_low in ("permalink.php", "story.php"):
      s_fbid = (qs.get("story_fbid") or qs.get("id") or [""])[0].strip()
      return bool(s_fbid and len(s_fbid) >= 5)

    if path_low in ("photo.php", "photo", "photos"):
      fbid = (qs.get("fbid") or [""])[0].strip()
      return bool(fbid and len(fbid) >= 5)

    if path_low in ("watch", "watch/live", "video.php"):
      v_id = (qs.get("v") or [""])[0].strip()
      return bool(v_id and len(v_id) >= 5)

    parts = [p.strip() for p in path.split("/") if p.strip()]
    parts_low = [p.lower() for p in parts]

    if len(parts_low) >= 3 and parts_low[0] == "share" and parts_low[1] in ("p", "v", "r"):
      return len(parts[2]) >= 4

    tab_words = {
        "posts",
        "videos",
        "photos",
        "reels",
        "reel",
        "about",
        "community",
        "Featured",
        "featured",
        "live",
        "live_videos",
        "streams",
        "mentions",
        "reviews",
        "followers",
        "following",
        "photos_by",
        "photos_albums",
    }

    for post_kind in ("posts", "permalink", "videos", "reel", "reels", "photos"):
      if post_kind in parts_low:
        idx = parts_low.index(post_kind)
        tail_segs = [s.strip() for s in parts[idx + 1 :] if s.strip() and s.strip().lower() not in tab_words]
        if not tail_segs:
          return False
        for seg_cand in tail_segs:
          if (
              seg_cand.startswith("pfbid")
              or (seg_cand.isdigit() and len(seg_cand) >= 6)
              or ":" in seg_cand
              or len(seg_cand) >= 5
          ):
            return True
        return False

    if "events" in parts_low:
      idx = parts_low.index("events")
      if idx + 1 < len(parts) and parts[idx + 1].isdigit() and len(parts[idx + 1]) >= 7:
        return True
      return False

    return False

  if is_x:
    return bool(re.search(r"/(?:status|statuses)/\d{8,}", u, re.IGNORECASE))

  if is_yt:
    if "youtu.be/" in u.lower():
      m_yb = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", u)
      return bool(m_yb)
    if "watch" in path_low:
      v_param = (qs.get("v") or [""])[0].strip()
      return bool(re.match(r"^[A-Za-z0-9_-]{11}$", v_param))
    m_short = re.search(r"^shorts/([A-Za-z0-9_-]{11})(?:$|/)", path)
    if m_short:
      return True
    return False

  return True


def _is_fb_post_owned_by_target(
    post_url: str,
    handle: str = "",
    page_id: str = "",
    page_official_name: str = "",
    og_title: str = "",
) -> bool:
  """التحقق من ملكية الصفحة للمنشور مع رفض المنشورات التابعة لصفحات أخرى وعدم حجب منشورات الصفحة بسبب جدار تسجيل الدخول."""
  u = clean_social_post_url(post_url)
  if not u or not is_direct_social_post_url(u, "فيسبوك"):
    return False
  parsed = urllib.parse.urlparse(u)
  path = urllib.parse.unquote(parsed.path).strip("/")
  parts = [p.strip() for p in path.split("/") if p.strip()]
  parts_low = [p.lower() for p in parts]
  qs = urllib.parse.parse_qs(parsed.query)

  clean_handle = (handle or "").strip().lower().lstrip("@")
  if clean_handle.startswith("fb_") or clean_handle.isdigit():
    clean_handle = ""
  clean_cid = (page_id or "").strip().lower()
  valid_owners = {x for x in [clean_handle, clean_cid] if x and len(x) >= 2}

  def _matches_official_name(text_to_check: str) -> bool:
    if not text_to_check or not page_official_name:
      return False
    t_norm = normalize_arabic_for_dedup(text_to_check)
    n_norm = normalize_arabic_for_dedup(page_official_name)
    if n_norm and len(n_norm) >= 3 and n_norm in t_norm:
      return True
    n_words = [w for w in n_norm.split() if len(w) >= 3]
    if len(n_words) >= 2 and all(w in t_norm for w in n_words[:2]):
      return True
    if len(n_words) == 1 and n_words[0] in t_norm:
      return True
    return False

  # 1) إذا كان الرابط منشور مجموعة: facebook.com/groups/{group_id_or_slug}/posts/...
  if len(parts_low) >= 2 and parts_low[0] == "groups":
    grp_owner = parts_low[1]
    if valid_owners:
      return grp_owner in valid_owners
    return _matches_official_name(og_title)

  # 2) إذا كان الرابط بصيغة people/{name}/{id}/... أو pages/{name}/{id}/...
  if len(parts_low) >= 3 and parts_low[0] in ("people", "pages"):
    p_name = parts_low[1].replace("-", " ")
    p_id = parts_low[2]
    if valid_owners:
      if (p_id in valid_owners) or (parts_low[1] in valid_owners) or (p_name in valid_owners):
        return True
      if clean_cid and p_id.isdigit() and p_id != clean_cid:
        return False
    if page_official_name and (_matches_official_name(p_name) or _matches_official_name(og_title)):
      return True
    return not bool(clean_handle)

  # 3) إذا كان الرابط يحتوي على اسم الصفحة الناشرة في المسار: facebook.com/{owner}/(posts|videos|photos|reels)/...
  if len(parts_low) >= 2 and parts_low[1] in ("posts", "videos", "photos", "reels", "permalink"):
    url_owner = parts_low[0]
    if url_owner in valid_owners:
      return True
    # إذا كان لدينا معرف نصي للصفحة (مثل hespress) وكان صاحب الرابط معرفاً نصياً مختلفاً، نرفضه فوراً
    if clean_handle and not url_owner.isdigit() and url_owner != clean_handle:
      return False
    # إذا كان لدينا معرف رقمي للصفحة وكان صاحب الرابط معرفاً رقمياً مختلفاً، نرفضه فوراً
    if clean_cid and clean_cid.isdigit() and url_owner.isdigit() and url_owner != clean_cid:
      return False
    if page_official_name and (_matches_official_name(url_owner.replace(".", " ").replace("-", " ")) or _matches_official_name(og_title)):
      return True
    # إذا كان صاحب الرابط رقمياً ولدينا handle نصي فقط (حيث يحول فيسبوك اسم الصفحة إلى رقمها في بعض الروابط)، نقبله ما لم يتعارض
    if url_owner.isdigit() and clean_handle:
      return True
    return bool(valid_owners or not page_official_name)

  # 4) إذا كان الرابط بصيغة permalink.php?story_fbid=...&id={page_id}
  if parts_low and parts_low[0] in ("permalink.php", "story.php"):
    url_id = ((qs.get("id") or [""])[0]).strip().lower()
    if url_id and clean_cid and clean_cid.isdigit():
      return url_id == clean_cid
    if _matches_official_name(og_title):
      return True
    return True

  # 5) الروابط المختصرة مثل watch/?v= أو reel/ أو photo.php?fbid= أو share/
  if og_title:
    if clean_handle and clean_handle in og_title.lower():
      return True
    if _matches_official_name(og_title):
      return True

  return True


def is_summary_just_title(title: str, summary: str) -> bool:
  t = clean_display_text(title)
  s = clean_display_text(summary)
  if not s or len(s) < 35:
    return True
  if "يتناول موضوع: «" in s or "رصد قضائي:" in s or "رصد إعلامي قضائي:" in s:
    return True
  s_core = re.sub(r"^[^:]+:\s*", "", s).strip()
  t_words = set(re.findall(r"[\u0600-\u06FF]{3,}", t))
  s_words = set(re.findall(r"[\u0600-\u06FF]{3,}", s_core))
  if not s_words:
    return True
  overlap = len(t_words & s_words) / max(1, len(s_words))
  if overlap > 0.82 and len(s_core) <= len(t) + 25:
    return True
  return False


_MOROCCAN_FB_OFFICIAL_HANDLES = {
    "pmpmaroc",
    "cspj.ma",
    "justice.gov.ma",
    "hespress",
    "al3omk",
    "alyaoum24",
    "madar21com",
    "alayam24",
    "goudmag",
    "akhbarona.page",
    "rue20.ma",
    "kech24",
    "tanja24",
    "barlamane",
    "agadir24",
}


@functools.lru_cache(maxsize=4096)
def _get_compiled_arabic_phrase_matcher(phrase: str):
  """تجهيز وتخزين التعبير النمطي المترجم مسبقاً (Pre-compiled Regex) مع الجذر النصي السريع لمنع إعادة بناء الـ Regex آلاف المرات."""
  norm_p = normalize_arabic_for_dedup(phrase)
  if not norm_p:
    return None
  if " " in norm_p:
    rx_exact = re.compile(rf"(?<![\u0600-\u06FFa-z0-9]){re.escape(norm_p)}(?![\u0600-\u06FFa-z0-9])")
    first_w, rest_w = norm_p.split(" ", 1)
    first_stem = re.sub(r"^(?:وال|بال|لل|فال|كال|ال)", "", first_w)
    rx_multi = None
    if len(first_stem) >= 3:
      rx_multi = re.compile(
          rf"(?<![\u0600-\u06FFa-z0-9])(?:ال|وال|بال|لل|فال|كال|و|ف|ب|ل)?{re.escape(first_stem)}\s+{re.escape(rest_w)}(?![\u0600-\u06FFa-z0-9])"
      )
    fast_sub = rest_w if len(rest_w) >= 2 else norm_p
    return ("multi", fast_sub, norm_p, rx_exact, rx_multi)
  stem = re.sub(r"^(?:وال|بال|لل|فال|كال|ال)", "", norm_p)
  if len(stem) < 2:
    return None
  rx_single = re.compile(
      rf"(?<![\u0600-\u06FFa-z0-9])(?:ال|وال|بال|لل|فال|كال|و|ف|ب|ل)?{re.escape(stem)}(?![\u0600-\u06FFa-z0-9])"
  )
  return ("single", stem, norm_p, rx_single, None)


def _contains_whole_arabic_phrase(norm_text: str, phrase: str) -> bool:
  """التحقق الفائق السرعة والصرامة من وجود المصطلح أو اسم المدينة ككلمة كاملة مستقلة في النص المطبّع."""
  if not norm_text or not phrase:
    return False
  matcher = _get_compiled_arabic_phrase_matcher(phrase)
  if matcher is None:
    return False
  kind, fast_sub, norm_p, rx1, rx2 = matcher
  if fast_sub not in norm_text and norm_p not in norm_text:
    return False
  if rx1.search(norm_text):
    return True
  if rx2 is not None and rx2.search(norm_text):
    return True
  return False


def has_authentic_moroccan_context(title: str, snippet: str = "", url: str = "") -> bool:
  """التحقق الدقيق من أن الخبر أو المنشور يرتبط فعلياً بالمغرب (مؤسسة قضائية مغربية، أو مدينة مغربية ككلمة كاملة، أو منبر إعلامي مغربي معتمد)."""
  u_unwrapped = clean_social_post_url(url) if url else ""
  u_low = u_unwrapped.lower()
  dom = _extract_clean_domain(u_unwrapped)

  if dom:
    if dom.endswith(".ma") or any(dom == md or dom.endswith("." + md) for md in MOROCCAN_TRUSTED_MEDIA_DOMAINS):
      return True
    if "facebook.com" in dom:
      try:
        p_parts = [urllib.parse.unquote(x).strip().lower() for x in urllib.parse.urlparse(u_unwrapped).path.strip("/").split("/") if x.strip()]
        if p_parts and p_parts[0] in _MOROCCAN_FB_OFFICIAL_HANDLES:
          return True
      except Exception:
        pass

  norm_combined = normalize_arabic_for_dedup(f"{title or ''} {snippet or ''}")
  if not norm_combined:
    return False

  for term in STRICT_JUDICIAL_UNAMBIGUOUS:
    if _contains_whole_arabic_phrase(norm_combined, term):
      return True

  for m_term in MOROCCAN_CONTEXT_TERMS:
    if _contains_whole_arabic_phrase(norm_combined, m_term):
      return True

  return False


def is_strictly_judicial_and_clean(
    title: str,
    snippet: str = "",
    url: str = "",
    keywords_input: str = "",
    is_target: bool = False,
) -> bool:
  """الفلتر القضائي المغربي الصارم: يضمن جلب الأخبار والمنشورات ذات البعد القضائي والعدلي التي تهم المغرب حصراً، ويستبعد أخبار التكنولوجيا وميكروسوفت وفيسبوك كمنصة والأخبار الدولية والعامة."""
  t_clean = clean_display_text(title)
  s_clean = clean_display_text(snippet)
  u_clean = str(url or "").lower()
  combined = f"{t_clean} {s_clean}".lower()
  combined_with_url = f"{combined} {u_clean}"
  norm_combined = normalize_arabic_for_dedup(f"{t_clean} {s_clean}")

  for bad_word in BLOCKED_INAPPROPRIATE_TERMS:
    if bad_word in combined_with_url:
      return False

  if len(t_clean) < 5 and len(s_clean) < 5:
    return False

  # 1) حظر صارم لروابط التكنولوجيا وميكروسوفت وصفحات المساعدة/السياسات الخاصة بفيسبوك والمواقع الأجنبية غير المغربية
  if url:
    u_unwrapped = clean_social_post_url(url)
    u_unwrapped_low = u_unwrapped.lower()
    u_dom = _extract_clean_domain(u_unwrapped)
    if any(u_dom == bd or u_dom.endswith("." + bd) for bd in BLOCKED_NON_JUDICIAL_DOMAINS):
      return False
    if any(
        bad_fb_p in u_unwrapped_low
        for bad_fb_p in (
            "facebook.com/help",
            "facebook.com/legal",
            "facebook.com/policies",
            "facebook.com/privacy",
            "facebook.com/business",
            "facebook.com/ads",
            "facebook.com/gaming",
            "facebook.com/marketplace",
            "developers.facebook.com",
            "about.fb.com",
            "support.microsoft.com",
            "go.microsoft.com",
            "learn.microsoft.com",
        )
    ):
      return False
    if any(
        d in u_dom
        for d in [
            "x.com",
            "twitter.com",
            "youtube.com",
            "youtu.be",
        ]
    ):
      if not is_direct_social_post_url(u_unwrapped):
        return False
    elif any(d in u_dom for d in ["facebook.com", "fb.com", "fb.watch"]):
      if is_target and not is_direct_social_post_url(u_unwrapped, "فيسبوك"):
        return False

  # 2) حظر صارم لأخبار التكنولوجيا وميكروسوفت وتحديثات/أعطال منصة فيسبوك والأخبار الدولية غير المغربية
  for non_jud_term in BLOCKED_NON_JUDICIAL_AND_FOREIGN_TERMS:
    nj_low = non_jud_term.lower()
    nj_norm = normalize_arabic_for_dedup(non_jud_term)
    if nj_low in combined or (nj_norm and _contains_whole_arabic_phrase(norm_combined, non_jud_term)):
      return False

  # 3) استخراج الكلمة المفتاحية المتتبعة (#kwtrack=...) إن وجدت والتحقق الصارم من وجودها الفعلي في النص
  m_kwtrack = re.search(r"#kwtrack=([^&#\s]+)", str(url or ""))
  if m_kwtrack and not (keywords_input and str(keywords_input).strip()):
    try:
      tracked_kw_from_url = urllib.parse.unquote(m_kwtrack.group(1)).strip()
      if tracked_kw_from_url:
        keywords_input = tracked_kw_from_url
    except Exception:
      pass

  has_explicit_kw = bool(keywords_input and str(keywords_input).strip())
  if has_explicit_kw:
    if not matches_custom_keywords(t_clean, s_clean, keywords_input):
      return False

  # بالنسبة للرصد المخصص (القنوات والصفحات التي أضافها المستخدم يدوياً في قائمة الرصد المخصص)
  if is_target:
    return True

  arabic_chars = re.findall(r"[\u0600-\u06FF]", f"{t_clean} {s_clean}")
  if len(arabic_chars) < 8:
    return False

  # 4) التحقق الإلزامي الصارم من توفر (البعد القضائي والعدلي) + (الارتباط بالمغرب حصراً) حتى في حال البحث بكلمة مفتاحية!
  for term in STRICT_JUDICIAL_UNAMBIGUOUS:
    if _contains_whole_arabic_phrase(norm_combined, term):
      return True

  has_general_judicial = False
  for term in JUDICIAL_GENERAL_TERMS:
    if _contains_whole_arabic_phrase(norm_combined, term):
      has_general_judicial = True
      break

  if has_general_judicial and has_authentic_moroccan_context(t_clean, s_clean, url):
    return True

  return False


# =====================================================================
# 2. تحليل الروابط المخصصة والتحقق الصارم من تبعية المنشور للقناة/الصفحة المضافة
# =====================================================================
GENERIC_SOCIAL_SEGMENTS = {
    "channel",
    "c",
    "user",
    "watch",
    "results",
    "feed",
    "shorts",
    "streams",
    "videos",
    "featured",
    "playlists",
    "community",
    "profile.php",
    "people",
    "pages",
    "groups",
    "posts",
    "photos",
    "reels",
    "share",
    "story.php",
    "permalink.php",
    "home",
    "explore",
    "search",
    "status",
    "i",
    "intent",
    "hashtag",
    "p",
    "reel",
    "stories",
    "in",
    "company",
}


def parse_custom_target_identity(target_url: str) -> dict:
  raw_u = str(target_url or "").strip()
  if not raw_u:
    return {}

  # دعم البحث المباشر باسم القناة أو الصفحة أو اسم صاحبها (بدون رابط)
  is_url_like = bool(
      "://" in raw_u
      or re.search(
          r"(?:^|\b)(?:youtube\.com|youtu\.be|facebook\.com|fb\.com|fb\.watch|x\.com|twitter\.com|tiktok\.com|instagram\.com|linkedin\.com|[a-zA-Z0-9-]+\.(?:com|ma|net|org|info|tv|me|io))\b",
          raw_u,
          re.IGNORECASE,
      )
  )
  if not is_url_like:
    clean_name = raw_u
    plat_hint = "شامل"
    for prefix_map, p_val in [
        (("يوتيوب:", "youtube:", "قناة يوتيوب", "يوتيوب"), "يوتيوب"),
        (("فيسبوك:", "فايسبوك:", "facebook:", "صفحة فيسبوك", "فيسبوك", "فايسبوك"), "فيسبوك"),
        (("إكس:", "اكس:", "تويتر:", "x:", "twitter:"), "إكس"),
    ]:
      for pref in prefix_map:
        if clean_name.lower().startswith(pref):
          plat_hint = p_val
          clean_name = clean_name[len(pref) :].strip(" :-–—")
          break
    clean_name = clean_name.strip() or raw_u.strip()
    tag_k = urllib.parse.quote(f"name_{clean_name.lower()}", safe="")
    return {
        "raw_url": clean_name,
        "domain": "",
        "platform": plat_hint,
        "handle": clean_name.lstrip("@") if clean_name.startswith("@") else "",
        "channel_id": "",
        "official_name_hint": clean_name.lstrip("@"),
        "is_name_target": True,
        "display_label": clean_name,
        "target_tag": f"#v4target={tag_k}",
    }

  full_u = raw_u if "://" in raw_u else f"https://{raw_u}"
  parsed = urllib.parse.urlparse(full_u)
  domain = (
      parsed.netloc.lower()
      .replace("www.", "")
      .replace("m.", "")
      .replace("web.", "")
      .replace("mbasic.", "")
  )
  path_parts = [
      urllib.parse.unquote(p).strip()
      for p in parsed.path.strip("/").split("/")
      if p.strip()
  ]
  qs = urllib.parse.parse_qs(parsed.query)

  if "youtube.com" in domain or "youtu.be" in domain:
    platform = "يوتيوب"
    base_domain = "youtube.com"
  elif "facebook.com" in domain or "fb.com" in domain or "fb.watch" in domain:
    platform = "فيسبوك"
    base_domain = "facebook.com"
  elif "x.com" in domain or "twitter.com" in domain:
    platform = "إكس"
    base_domain = "x.com"
  elif "tiktok.com" in domain:
    platform = "أخرى"
    base_domain = "tiktok.com"
  elif "instagram.com" in domain:
    platform = "أخرى"
    base_domain = "instagram.com"
  elif "linkedin.com" in domain:
    platform = "أخرى"
    base_domain = "linkedin.com"
  else:
    platform = "الصحف"
    base_domain = domain

  handle = ""
  channel_id = ""
  official_name_hint = ""
  display_label = domain

  if platform == "يوتيوب":
    for idx, seg in enumerate(path_parts):
      if seg.startswith("@"):
        handle = seg.lstrip("@")
        display_label = seg
        break
      if seg == "channel" and idx + 1 < len(path_parts):
        channel_id = path_parts[idx + 1]
        display_label = channel_id
        break
      if seg in ("c", "user") and idx + 1 < len(path_parts):
        handle = path_parts[idx + 1]
        display_label = handle
        break
      if seg.startswith("UC") and len(seg) >= 20:
        channel_id = seg
        display_label = seg
        break
      if seg.lower() not in GENERIC_SOCIAL_SEGMENTS and not handle:
        handle = seg
        display_label = seg
  elif platform in ("فيسبوك", "إكس", "أخرى"):
    if "id" in qs and qs["id"]:
      channel_id = qs["id"][0].strip()
      handle = ""
      display_label = f"fb_{channel_id}"
    elif len(path_parts) >= 2 and path_parts[0].lower() == "p":
      # روابط فيسبوك الحديثة بصيغة: facebook.com/p/Page-Name-100064581234567/
      raw_p_seg = path_parts[1].lstrip("@")
      m_pid_tail = re.search(r"^(.*?)-(\d{8,})$", raw_p_seg)
      if m_pid_tail:
        official_name_hint = m_pid_tail.group(1).replace("-", " ").strip()
        channel_id = m_pid_tail.group(2).strip()
        handle = ""
        display_label = official_name_hint or f"fb_{channel_id}"
      else:
        official_name_hint = raw_p_seg.replace("-", " ").strip()
        handle = raw_p_seg
        display_label = official_name_hint
    elif len(path_parts) >= 2 and path_parts[0].lower() in (
        "people",
        "pages",
        "company",
        "in",
        "groups",
    ):
      raw_seg1 = path_parts[1].lstrip("@")
      m_pid_tail = re.search(r"^(.*?)-(\d{8,})$", raw_seg1)
      if m_pid_tail:
        official_name_hint = m_pid_tail.group(1).replace("-", " ").strip()
        channel_id = m_pid_tail.group(2).strip()
      else:
        official_name_hint = raw_seg1.replace("-", " ")
      display_label = official_name_hint or raw_seg1
      if len(path_parts) >= 3 and path_parts[2].isdigit():
        channel_id = path_parts[2]
      elif path_parts[0].lower() == "groups":
        handle = path_parts[1]
    elif len(path_parts) >= 2 and path_parts[0].lower() == "share":
      # رابط مشاركة فيسبوك (share/...) يحتاج إلى فك التوجيه أولاً لمعرفة اسم ومعرف الصفحة الحقيقي
      handle = ""
      display_label = f"fb_share_{path_parts[-1]}"
    else:
      for seg in path_parts:
        if seg.lower() not in GENERIC_SOCIAL_SEGMENTS:
          m_pid_tail = re.search(r"^(.*?)-(\d{8,})$", seg)
          if seg.isdigit() and len(seg) >= 8:
            channel_id = seg
            display_label = f"fb_{seg}"
          elif m_pid_tail and platform == "فيسبوك":
            official_name_hint = m_pid_tail.group(1).replace("-", " ").strip()
            channel_id = m_pid_tail.group(2).strip()
            handle = ""
            display_label = official_name_hint or f"fb_{channel_id}"
          else:
            handle = seg.lstrip("@")
            display_label = handle
          break
  else:
    display_label = domain
    if path_parts:
      handle = path_parts[0]

  target_tag_key = urllib.parse.quote(
      (display_label or handle or channel_id or base_domain).lower(), safe=""
  )

  return {
      "raw_url": full_u,
      "domain": base_domain,
      "platform": platform,
      "handle": handle,
      "channel_id": channel_id,
      "official_name_hint": official_name_hint,
      "is_name_target": False,
      "display_label": display_label or base_domain,
      "target_tag": f"#v4target={target_tag_key}",
  }


def belongs_to_custom_target(item: dict, target_info: dict) -> bool:
  if not target_info or not item:
    return False

  raw_item_url = str(item.get("url") or "").strip()
  raw_item_url_low = raw_item_url.lower()
  u = clean_social_post_url(raw_item_url)
  item_plat = item.get("platform", "")
  t_plat = target_info.get("platform", "")
  handle = (target_info.get("handle") or "").strip()

  # 1) رفض قاطع لأي رابط على يوتيوب أو فيسبوك أو إكس يوجه إلى الصفحة الرئيسية للقناة/الصفحة بدلاً من الفيديو/المنشور بعينه
  u_dom = urllib.parse.urlparse(u).netloc.lower()
  if any(sd in u_dom for sd in ("youtube.com", "youtu.be", "facebook.com", "fb.com", "fb.watch", "x.com", "twitter.com")):
    check_plat = item_plat if item_plat in ("يوتيوب", "فيسبوك", "إكس") else t_plat
    if not is_direct_social_post_url(u, check_plat):
      return False

  # 2) تطهير أي نتائج قديمة من النسخ السابقة
  if any(old_t in raw_item_url_low for old_t in ("#target=", "#v2target=", "#v3target=")) and "#v4target=" not in raw_item_url_low:
    return False

  # 3) التحقق من وسم الهدف المخصص الموثق #v4target=
  t_tag = (target_info.get("target_tag") or "").lower()
  if t_tag and t_tag in raw_item_url_low:
    return True

  return False


def belongs_to_any_custom_target(item: dict, targets_list: list) -> bool:
  if not targets_list:
    return False
  for t in targets_list:
    t_info = parse_custom_target_identity(t.get("url", ""))
    if t_info and belongs_to_custom_target(item, t_info):
      return True
  return False


# =====================================================================
# 3. فك روابط Google News واستخراج النص الأصلي الكامل للموضوع حرفياً (Verbatim Full Text) والصورة الأصلية
# =====================================================================
MOROCCAN_SITE_DOMAIN_MAP = {
    "hespress.com": "هسبريس",
    "al3omk.com": "العمق المغربي",
    "alyaoum24.com": "اليوم 24",
    "madar21.com": "مدار 21",
    "alayam24.com": "الأيام 24",
    "akhbarona.com": "أخبارنا",
    "goud.ma": "كود",
    "assabah.ma": "الصباح",
    "rue20.com": "زنقة 20",
    "kech24.com": "كش 24",
    "agadir24.info": "أكادير 24",
    "sabahagadir.com": "صباح أكادير",
    "tanja24.com": "طنجة 24",
    "barlamane.com": "برلمان.كوم",
    "le360.ma": "Le360",
    "hibapress.com": "هبة بريس",
    "nadorcity.com": "ناظورسيتي",
    "thevoice.ma": "ذا فويس",
    "snrtnews.com": "SNRTnews",
    "mapexpress.ma": "وكالة المغرب العربي للأنباء",
    "mapnews.ma": "وكالة المغرب العربي للأنباء",
    "2m.ma": "القناة الثانية 2M",
    "medi1tv.com": "مدي 1 تيفي",
    "aljarida24.ma": "الجريدة 24",
    "febrayer.com": "فبراير.كوم",
    "lakome2.com": "لكم",
    "anfaspress.com": "أنفاس بريس",
    "achtari24.com": "أشطاري 24",
    "chattpress.com": "الشط بريس",
    "alittihad.info": "الاتحاد الاشتراكي",
    "alaraby.co.uk": "العربي الجديد",
    "skynewsarabia.com": "سكاي نيوز عربية",
    "aljazeera.net": "الجزيرة نت",
    "alarabiya.net": "العربية",
    "asharq.com": "الشرق للأخبار",
    "independentarabia.com": "اندبندنت عربية",
    "rt.com": "RT Arabic",
    "cnn.com": "CNN بالعربية",
    "bbc.com": "BBC News عربي",
    "france24.com": "فرانس 24",
    "dw.com": "DW عربية",
    "cspj.ma": "المجلس الأعلى للسلطة القضائية",
    "pmp.ma": "رئاسة النيابة العامة",
    "justice.gov.ma": "وزارة العدل",
    "mahakim.ma": "بوابة المحاكم المغربية",
}

MOROCCAN_NAME_TO_DOMAIN_ALIAS = {
    "هسبريس": "hespress.com",
    "hespress": "hespress.com",
    "العمق المغربي": "al3omk.com",
    "العمق": "al3omk.com",
    "al3omk": "al3omk.com",
    "اليوم 24": "alyaoum24.com",
    "اليوم24": "alyaoum24.com",
    "alyaoum24": "alyaoum24.com",
    "مدار 21": "madar21.com",
    "مدار21": "madar21.com",
    "madar21": "madar21.com",
    "الأيام 24": "alayam24.com",
    "الايام 24": "alayam24.com",
    "alayam24": "alayam24.com",
    "أخبارنا المغربية": "akhbarona.com",
    "أخبارنا": "akhbarona.com",
    "اخبارنا": "akhbarona.com",
    "akhbarona": "akhbarona.com",
    "كش 24": "kech24.com",
    "كشـ24": "kech24.com",
    "kech24": "kech24.com",
    "أكادير 24": "agadir24.info",
    "اكادير 24": "agadir24.info",
    "agadir24": "agadir24.info",
    "صباح أكادير": "sabahagadir.com",
    "sabahagadir": "sabahagadir.com",
    "كود": "goud.ma",
    "گود": "goud.ma",
    "goud": "goud.ma",
    "الصباح": "assabah.ma",
    "جريدة الصباح": "assabah.ma",
    "assabah": "assabah.ma",
    "برلمان.كوم": "barlamane.com",
    "برلمان كوم": "barlamane.com",
    "برلمان": "barlamane.com",
    "barlamane": "barlamane.com",
    "زنقة 20": "rue20.com",
    "الزنقة 20": "rue20.com",
    "rue20": "rue20.com",
    "طنجة 24": "tanja24.com",
    "tanja24": "tanja24.com",
    "ذا فويس": "thevoice.ma",
    "thevoice": "thevoice.ma",
    "ناظورسيتي": "nadorcity.com",
    "ناظور سيتي": "nadorcity.com",
    "nadorcity": "nadorcity.com",
    "هبة بريس": "hibapress.com",
    "hibapress": "hibapress.com",
    "le360": "le360.ma",
    "snrtnews": "snrtnews.com",
    "وكالة المغرب العربي للأنباء": "mapexpress.ma",
    "لاماب": "mapexpress.ma",
    "الجريدة 24": "aljarida24.ma",
    "aljarida24": "aljarida24.ma",
    "فبراير": "febrayer.com",
    "febrayer": "febrayer.com",
    "أنفاس بريس": "anfaspress.com",
    "anfaspress": "anfaspress.com",
    "أشطاري 24": "achtari24.com",
    "achtari24": "achtari24.com",
    "المجلس الأعلى للسلطة القضائية": "cspj.ma",
    "رئاسة النيابة العامة": "pmp.ma",
    "وزارة العدل": "justice.gov.ma",
}

REDIRECT_WRAPPER_DOMAINS = (
    "news.google.com",
    "google.com",
    "bing.com",
    "yahoo.com",
    "duckduckgo.com",
)


def _extract_clean_domain(url_str: str) -> str:
  """استخراج اسم النطاق الصافي (Domain) من الرابط مع تجاهل نطاقات محركات البحث التحويلية."""
  if not url_str:
    return ""
  u = strip_internal_url_fragments(str(url_str).strip())
  if not u:
    return ""
  if "://" not in u and re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/|$)", u):
    u = "https://" + u
  try:
    p = urllib.parse.urlparse(u)
    dom = p.netloc.lower().strip()
    for pref in ("www.", "m.", "web.", "mbasic.", "ar.", "fr.", "mobile."):
      if dom.startswith(pref):
        dom = dom[len(pref) :]
    if not dom or any(dom == rd or dom.endswith("." + rd) for rd in REDIRECT_WRAPPER_DOMAINS):
      return ""
    return dom
  except Exception:
    return ""


def _find_press_domain_by_source_or_url(source_name: str, url: str, source_url_hint: str = "") -> str:
  """تحديد النطاق الرسمي الدقيق (Domain) للجريدة أو الموقع من رابط المصدر أو الرابط المباشر أو اسم الجريدة."""
  for cand_u in (source_url_hint, url):
    dom_u = _extract_clean_domain(cand_u)
    if dom_u and dom_u not in ("facebook.com", "fb.com", "fb.watch", "youtube.com", "youtu.be", "x.com", "twitter.com", "instagram.com", "tiktok.com", "linkedin.com"):
      for known_dom in MOROCCAN_SITE_DOMAIN_MAP:
        if dom_u == known_dom or dom_u.endswith("." + known_dom):
          return known_dom
      return dom_u

  u_low = str(url or "").lower()
  s_clean = clean_display_text(source_name or "").lower()
  # التحقق مما إذا كان اسم المصدر يحتوي بالفعل على دومين بين قوسين مثل: هسبريس (hespress.com)
  m_dom_in_src = re.search(r"\b([a-z0-9-]+\.(?:com|ma|info|net|org|tv|co\.uk|me))\b", s_clean)
  if m_dom_in_src:
    cand_d = m_dom_in_src.group(1)
    if cand_d not in REDIRECT_WRAPPER_DOMAINS:
      return cand_d

  for site in MOROCCAN_PRESS_SITES:
    dom = site["domain"].lower()
    name_low = site["name"].lower()
    if dom in u_low or (name_low and name_low in s_clean):
      return dom

  for k_alias, dom_val in MOROCCAN_NAME_TO_DOMAIN_ALIAS.items():
    if k_alias in s_clean or k_alias in u_low:
      return dom_val
  return ""


def format_precise_source_with_domain(
    source_name: str,
    url: str = "",
    platform: str = "الصحف",
    source_url_hint: str = "",
    title_hint: str = "",
) -> str:
  """تحديد وتنسيق اسم المصدر بدقة عالية بحيث يعرض دائماً اسم الموقع مقترناً بالدومين الخاص به، مثل: هسبريس (hespress.com)."""
  raw_s = clean_display_text(source_name or "")
  is_target = raw_s.startswith("🎯")
  s_core = raw_s.lstrip("🎯").strip()

  # إزالة التكرار القديم إن وجد في اسم المصدر (مثل قوسين مكررين)
  s_core = re.sub(r"\s*\([a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^)]*)?\)\s*$", "", s_core).strip()

  # إذا كان اسم المصدر فارغاً أو عاماً، نحاول استنتاجه من آخر العنوان قبل التنظيف
  if (not s_core or s_core in ("الصحف", "صحافة", "الأخبار", "Google News")) and title_hint:
    for sep in (" - ", " | ", " – ", " — "):
      if sep in title_hint:
        tail_s = title_hint.rsplit(sep, 1)[-1].strip()
        if 2 <= len(tail_s) <= 32:
          s_core = tail_s
          break

  clean_u = clean_social_post_url(url)
  u_dom = _extract_clean_domain(clean_u)

  # 1) معالجة منصات التواصل الاجتماعي (فيسبوك، يوتيوب، إكس، أخرى) مع إظهار اسم الصفحة/القناة والدومين
  if platform == "فيسبوك" or u_dom in ("facebook.com", "fb.com", "fb.watch"):
    page_lbl = s_core
    if not page_lbl or page_lbl in ("فيسبوك", "الصحف"):
      page_lbl = _extract_fb_page_label_from_entry(clean_u, title_hint) if "clean_u" in locals() else "فيسبوك"
    if not page_lbl.startswith("فيسبوك") and not page_lbl.startswith("صفحة"):
      page_lbl = f"فيسبوك • {page_lbl}"
    fb_dom_label = "facebook.com"
    try:
      p_fb = urllib.parse.urlparse(clean_u)
      parts_fb = [urllib.parse.unquote(x).strip() for x in p_fb.path.strip("/").split("/") if x.strip()]
      if parts_fb and parts_fb[0].lower() not in GENERIC_SOCIAL_SEGMENTS and not parts_fb[0].isdigit():
        fb_dom_label = f"facebook.com/{parts_fb[0]}"
    except Exception:
      pass
    res = f"{page_lbl} ({fb_dom_label})"
    return f"🎯 {res}" if is_target else res

  if platform == "يوتيوب" or u_dom in ("youtube.com", "youtu.be"):
    ch_lbl = s_core or "يوتيوب"
    if ch_lbl.lower() == "youtube":
      ch_lbl = "يوتيوب"
    res = f"{ch_lbl} (youtube.com)"
    return f"🎯 {res}" if is_target else res

  if platform == "إكس" or u_dom in ("x.com", "twitter.com"):
    x_lbl = s_core or "منصة إكس"
    x_dom_label = "x.com"
    m_xh = re.search(r"(?:x\.com|twitter\.com)/([A-Za-z0-9_]{2,25})/status/", clean_u, re.IGNORECASE)
    if m_xh:
      handle_x = m_xh.group(1)
      x_dom_label = f"x.com/{handle_x}"
      if x_lbl in ("إكس", "منصة إكس", "X", "Twitter"):
        x_lbl = f"إكس • @{handle_x}"
    res = f"{x_lbl} ({x_dom_label})"
    return f"🎯 {res}" if is_target else res

  if platform == "أخرى" or u_dom in ("tiktok.com", "instagram.com", "linkedin.com"):
    soc_dom = u_dom or "social"
    soc_lbl = s_core or "منصة رقمية"
    res = f"{soc_lbl} ({soc_dom})" if soc_dom != "social" else soc_lbl
    return f"🎯 {res}" if is_target else res

  # 2) معالجة الصحف والمواقع الإخبارية: تحديد الدومين واسم الموقع بدقة
  press_dom = _find_press_domain_by_source_or_url(s_core, clean_u, source_url_hint=source_url_hint)
  if not press_dom and title_hint:
    press_dom = _find_press_domain_by_source_or_url(title_hint, clean_u, source_url_hint=source_url_hint)

  canonical_site_name = MOROCCAN_SITE_DOMAIN_MAP.get(press_dom, "")

  # تنظيف اسم المصدر إذا كان يحتوي على الدومين نفسه فقط
  if s_core.lower() == press_dom.lower() or s_core in ("الصحف", "صحافة", "موقع إخباري", ""):
    display_name = canonical_site_name or press_dom or "صحافة وطنية"
  else:
    display_name = canonical_site_name if (canonical_site_name and s_core.lower() in press_dom.lower()) else s_core

  if press_dom:
    if press_dom.lower() not in display_name.lower():
      res = f"{display_name} ({press_dom})"
    else:
      # إذا كان اسم المصدر هو الدومين فقط ولدينا اسم عربي معروف، نجمعهما معاً
      if canonical_site_name and canonical_site_name != display_name:
        res = f"{canonical_site_name} ({press_dom})"
      else:
        res = display_name
  else:
    res = display_name or "الصحف المغربية"

  return f"🎯 {res}" if is_target else res


def clean_and_validate_image_url(
    img_url: str, article_url: str = "", platform: str = "الصحف"
) -> str:
  """التحقق من صحة رابط الصورة المصغرة واستبعاد شعارات Google News والأيقونات المكسورة أو روابط التتبع."""
  u_art = clean_social_post_url(article_url)
  m_yt = re.search(
      r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
      u_art,
  )
  if m_yt:
    return f"https://i.ytimg.com/vi/{m_yt.group(1)}/hqdefault.jpg"

  if not img_url:
    return ""
  img = html.unescape(str(img_url).strip())
  if img.startswith("data:image/"):
    return img
  if img.startswith("//"):
    img = "https:" + img
  elif img.startswith("/") and u_art.startswith("http"):
    img = urllib.parse.urljoin(u_art, img)

  if not img.startswith("http"):
    return ""

  img_low = img.lower()
  bad_img_Tokens = [
      "1x1",
      "pixel",
      "tracker",
      "blank.gif",
      "spacer.gif",
      "favicon",
      "sprite",
      "default-avatar",
      "gravatar.com",
      "googleusercontent.com/j6_cofbogxhri9im864nl_ligxvsqp2aupskei7z0cnnfdvgumwuy20nuuhkreqyrpy4beeibuc",
      "lh3.googleusercontent.com/j6_co",
      "news.google.com",
      "gstatic.com/images/branding",
      "google.com/images/branding",
      "/plugins/close_popup",
      " safe_image.php?d=aq",
      "p50x50",
      "s50x50",
      "p32x32",
      "s32x32",
  ]
  if any(b_tok in img_low for b_tok in bad_img_Tokens):
    return ""
  if img_low.endswith(".svg") and any(w in img_low for w in ("logo", "icon", "header", "brand")):
    return ""
  return img


def _extract_wp_media_from_post_json(p_obj: dict, article_url: str = "") -> str:
  """استخراج الصورة البارزة عالية الدقة من كائن JSON لمقال WordPress بكافة الطرق الممكنة."""
  if not isinstance(p_obj, dict):
    return ""
  # 1) Jetpack featured media
  cand = str(p_obj.get("jetpack_featured_media_url") or "").strip()
  cand = clean_and_validate_image_url(cand, article_url)
  if cand:
    return cand

  # 2) Yoast SEO og_image
  og_imgs = p_obj.get("yoast_head_json", {}).get("og_image", [])
  if isinstance(og_imgs, list) and og_imgs and isinstance(og_imgs[0], dict):
    cand = clean_and_validate_image_url(str(og_imgs[0].get("url") or "").strip(), article_url)
    if cand:
      return cand

  # 3) WP REST API _embedded['wp:featuredmedia']
  embedded = p_obj.get("_embedded", {})
  if isinstance(embedded, dict):
    feat_list = embedded.get("wp:featuredmedia", [])
    if isinstance(feat_list, list) and feat_list and isinstance(feat_list[0], dict):
      fm = feat_list[0]
      cand = clean_and_validate_image_url(str(fm.get("source_url") or "").strip(), article_url)
      if cand:
        return cand
      sizes = fm.get("media_details", {}).get("sizes", {})
      if isinstance(sizes, dict):
        for sz_k in ("large", "medium_large", "full", "medium"):
          if isinstance(sizes.get(sz_k), dict) and sizes[sz_k].get("source_url"):
            cand = clean_and_validate_image_url(str(sizes[sz_k]["source_url"]).strip(), article_url)
            if cand:
              return cand

  # 4) الصورة الأولى داخل متن المقال rendered HTML
  rendered_html = p_obj.get("content", {}).get("rendered", "")
  if rendered_html:
    cand = extract_thumbnail_for_item(article_url, rendered_html, "الصحف")
    if cand:
      return cand
  return ""


def _fetch_wordpress_verbatim_article(domain: str, title: str, article_url: str = "") -> tuple:
  """جلب النص الأصلي الكامل للمقال حرفياً (فقرة بفقرة) والصورة والرابط المباشر عبر واجهة WordPress REST API الرسمية أو خلاصة البحث المباشرة للجريدة."""
  if not domain and not article_url:
    return "", "", ""

  # أ) إذا كان لدينا رابط مباشر للمقال يحتوي على معرف رقمي (مثل hespress.com/...-123456.html أو al3omk.com/123456.html)، نفحص WP REST API بالمعرف أولاً
  if article_url and "news.google.com" not in article_url:
    parsed_a = urllib.parse.urlparse(article_url)
    dom_a = _extract_clean_domain(article_url) or domain
    m_post_id = re.search(r"(?:-|/|\?p=)(\d{5,8})(?:\.html|/|&|$)", article_url)
    if m_post_id and dom_a:
      pid = m_post_id.group(1)
      wp_single_u = f"https://{dom_a}/wp-json/wp/v2/posts/{pid}?_embed=1"
      try:
        r_wp = requests.get(wp_single_u, headers=DEFAULT_HEADERS, timeout=4.5)
        if r_wp.status_code == 200:
          p_json = r_wp.json()
          if isinstance(p_json, dict) and p_json.get("content", {}).get("rendered"):
            full_txt = clean_full_article_text(p_json["content"]["rendered"])
            link_u = str(p_json.get("link") or article_url).strip()
            img_u = _extract_wp_media_from_post_json(p_json, link_u)
            if len(full_txt) >= 120 or img_u:
              return img_u, full_txt, link_u
      except Exception:
        pass

  if not domain or not title:
    return "", "", ""

  # تنظيف العنوان من اسم الجريدة في آخره للبحث الدقيق
  clean_t = strip_source_suffix_from_title(title)
  search_phrase = clean_t[:75].strip()
  if len(search_phrase) < 6:
    return "", "", ""

  norm_target_t = normalize_arabic_for_dedup(clean_t)
  target_words = [w for w in norm_target_t.split() if len(w) >= 3]

  def _title_matches_candidate(cand_title: str) -> bool:
    if not target_words:
      return True
    norm_cand_t = normalize_arabic_for_dedup(cand_title)
    if not norm_cand_t:
      return False
    if norm_target_t[:30] in norm_cand_t or norm_cand_t[:30] in norm_target_t:
      return True
    overlap = sum(1 for w in target_words[:8] if w in norm_cand_t or w.lstrip("ال") in norm_cand_t)
    min_req = 1 if len(target_words) <= 3 else 2
    return overlap >= min_req

  # ب) البحث في واجهة WordPress REST API الرسمية للجريدة (/wp-json/wp/v2/posts?search=...&_embed=1)
  wp_api_u = f"https://{domain}/wp-json/wp/v2/posts?search={urllib.parse.quote(search_phrase)}&per_page=5&_embed=1"
  try:
    r_api = requests.get(wp_api_u, headers=DEFAULT_HEADERS, timeout=5.0)
    if r_api.status_code == 200:
      posts_list = r_api.json()
      if isinstance(posts_list, list) and posts_list:
        for p_obj in posts_list:
          if not isinstance(p_obj, dict):
            continue
          cand_t = clean_display_text(p_obj.get("title", {}).get("rendered", ""))
          if not _title_matches_candidate(cand_t):
            continue
          rendered_html = p_obj.get("content", {}).get("rendered", "") or p_obj.get("excerpt", {}).get("rendered", "")
          full_txt = clean_full_article_text(rendered_html)
          link_u = str(p_obj.get("link") or "").strip()
          img_u = _extract_wp_media_from_post_json(p_obj, link_u)
          if len(full_txt) >= 100 or link_u:
            return img_u, full_txt, link_u
  except Exception:
    pass

  # ج) البحث في خلاصة WordPress RSS المباشرة للجريدة (/?s=...&feed=rss2) التي تحتوي على <content:encoded> الكامل
  wp_rss_u = f"https://{domain}/?s={urllib.parse.quote(search_phrase)}&feed=rss2"
  try:
    r_rss = requests.get(wp_rss_u, headers=DEFAULT_HEADERS, timeout=5.0)
    if r_rss.status_code == 200 and b"<item>" in r_rss.content:
      root = ET.fromstring(r_rss.content)
      ns_c = {"content": "http://purl.org/rss/1.0/modules/content/", "media": "http://search.yahoo.com/mrss/"}
      for it_el in root.findall(".//item")[:4]:
        cand_t = clean_display_text(it_el.findtext("title") or "")
        if not _title_matches_candidate(cand_t):
          continue
        raw_enc = it_el.findtext("content:encoded", default="", namespaces=ns_c) or it_el.findtext("description") or ""
        full_txt = clean_full_article_text(raw_enc)
        link_u = clean_social_post_url(it_el.findtext("link") or "")
        img_u = ""
        for m_tag in ["media:content", "media:thumbnail", "enclosure"]:
          el_m = it_el.find(m_tag, ns_c) if ":" in m_tag else it_el.find(m_tag)
          if el_m is not None and el_m.attrib.get("url"):
            img_u = clean_and_validate_image_url(el_m.attrib["url"].strip(), link_u)
            if img_u:
              break
        if not img_u:
          img_u = extract_thumbnail_for_item(link_u, raw_enc, "الصحف")
        if len(full_txt) >= 100 or link_u:
          return img_u, full_txt, link_u
  except Exception:
    pass

  return "", "", ""


def resolve_google_news_url(
    url: str, title_hint: str = "", source_hint: str = "", domain_hint: str = ""
) -> str:
  """فك تشفير روابط Google News الحديثة (CBMi...) عبر الكوكيز التجاوزية + batchexecute + واجهة WordPress + محركات البحث المباشرة."""
  u = strip_internal_url_fragments(url)
  if "news.google.com" not in u:
    return u

  m_b64 = re.search(r"/(?:articles|read)/([A-Za-z0-9_-]+)", u)
  if m_b64:
    token = m_b64.group(1)
    try:
      padded = token + "=" * ((4 - len(token) % 4) % 4)
      raw_bytes = base64.urlsafe_b64decode(padded)
      decoded_latin = raw_bytes.decode("latin-1", errors="ignore")
      m_http = re.search(
          r"(https?://[^\x00-\x1f\x7f-\xff\"\'<> ]+)", decoded_latin
      )
      if m_http and "google.com" not in m_http.group(1):
        return m_http.group(1)
    except Exception:
      pass

    gnews_cookies = {
        "CONSENT": "YES+cb.20240115-07-p0.ar+FX+999",
        "SOCS": "CAESHAgBEhJnd3NfMjAyNDAxMTUtMF9SQzIaAmFyIAEaBgiAo_CmBg",
    }
    for prefix_path in ("rss/articles", "articles"):
      try:
        art_page = f"https://news.google.com/{prefix_path}/{token}"
        r = requests.get(
            art_page,
            headers=DEFAULT_HEADERS,
            cookies=gnews_cookies,
            timeout=4.0,
            allow_redirects=True,
        )
        if r.status_code == 200 and r.text:
          if r.url and "news.google.com" not in r.url and "consent.google" not in r.url:
            return r.url
          sg_m = re.search(r'data-n-a-sg=["\']([^"\']+)["\']', r.text)
          ts_m = re.search(r'data-n-a-ts=["\']([^"\']+)["\']', r.text)
          if sg_m and ts_m:
            sg = sg_m.group(1)
            ts = ts_m.group(1)
            payload_inner = (
                f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"MA:ar",'
                f'null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,'
                f'null,0,0,null,0],"{token}",{ts},"{sg}"]'
            )
            req_data = {
                "f.req": json.dumps(
                    [[["Fbv4je", payload_inner, None, "generic"]]]
                )
            }
            headers_post = dict(DEFAULT_HEADERS)
            headers_post["Content-Type"] = (
                "application/x-www-form-urlencoded;charset=UTF-8"
            )
            rb = requests.post(
                "https://news.google.com/_/DotsSplashUi/data/batchexecute",
                data=req_data,
                headers=headers_post,
                cookies=gnews_cookies,
                timeout=4.0,
            )
            if rb.status_code == 200 and rb.text:
              unesc = rb.text.replace("\\/", "/").replace("\/", "/").replace("\u003d", "=").replace("\u0026", "&")
              m_res = re.search(
                  r'garturlres\*",\*"(https?://[^"\\]+)', unesc
              )
              if m_res and "google.com" not in m_res.group(1):
                return m_res.group(1)
      except Exception:
        pass

  # إذا لم ينفك رابط Google News، نستخدم الدومين وعنوان الخبر لإيجاد الرابط الأصلي المباشر
  if title_hint:
    dom_hint = domain_hint or _find_press_domain_by_source_or_url(source_hint, u)
    if dom_hint:
      _, _, wp_link = _fetch_wordpress_verbatim_article(dom_hint, title_hint)
      if wp_link and "news.google.com" not in wp_link:
        return wp_link
    _, _, b_link = fetch_bing_news_enrichment(title_hint, source_hint)
    if b_link and "news.google.com" not in b_link and b_link.startswith("http"):
      return b_link

  return u


def scrape_article_page_content_and_image(
    url: str, title_hint: str = "", source_hint: str = "", domain_hint: str = ""
):
  """جلب الصورة الأصلية والنص الأصلي الكامل للموضوع حرفياً (فقرة بفقرة كما ورد في المصدر الأصلي دون اختصار)."""
  real_url = resolve_google_news_url(
      url, title_hint=title_hint, source_hint=source_hint, domain_hint=domain_hint
  )

  # 1) إذا كان الخبر من جريدة مغربية تدعم WordPress API، نحاول جلب النص الأصلي الكامل والصورة والرابط المباشر منها
  press_dom = domain_hint or _find_press_domain_by_source_or_url(source_hint, real_url)
  if press_dom and ("news.google.com" in real_url or title_hint):
    wp_img, wp_full_text, wp_link = _fetch_wordpress_verbatim_article(
        press_dom, title_hint, "" if "news.google.com" in real_url else real_url
    )
    if wp_link and "news.google.com" in real_url:
      real_url = wp_link
    wp_img = clean_and_validate_image_url(wp_img, real_url)
    if len(wp_full_text) >= 240 and wp_img:
      return wp_img, wp_full_text, real_url

  if not real_url or "news.google.com" in real_url:
    # محاولة إضافية عبر محركات البحث للعثور على الرابط الأصلي للمقال من عنوانه ونطاقه
    if title_hint and len(title_hint) >= 12:
      clean_t_q = strip_source_suffix_from_title(title_hint)
      site_filter = f"site:{press_dom} " if press_dom else ""
      q_find = f'{site_filter}"{clean_t_q[:65]}"'.strip()
      for sr in _multi_engine_web_search(q_find, platform="الصحف", max_results=5):
        cand_u = clean_social_post_url(sr.get("url", ""))
        if cand_u and "news.google.com" not in cand_u and "facebook.com" not in cand_u:
          real_url = cand_u
          break
    if not real_url or "news.google.com" in real_url:
      return "", "", real_url

  m_yt = re.search(
      r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
      real_url,
  )
  if m_yt:
    vid_id = m_yt.group(1)
    yt_thumb = f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"
    yt_desc = ""
    try:
      ryt = requests.get(
          f"https://www.youtube.com/watch?v={vid_id}",
          headers=DEFAULT_HEADERS,
          cookies=YT_BYPASS_COOKIES,
          timeout=5.0,
      )
      if ryt.status_code == 200 and ryt.text:
        m_sd = re.search(
            r'"shortDescription"\s*:\s*"((?:[^"\\]|\\.){15,8000})"',
            ryt.text,
        )
        if m_sd:
          yt_desc = clean_full_article_text(decode_js_escaped_text(m_sd.group(1)))
        if not yt_desc:
          m_ogd = re.search(
              r'<meta[^>]+(?:property|name)=["\'](?:og:description|description)["\'][^>]+content=["\']([^"\']+)["\']',
              ryt.text[:45000],
              re.IGNORECASE,
          )
          if m_ogd:
            yt_desc = clean_full_article_text(m_ogd.group(1))
    except Exception:
      pass
    return yt_thumb, yt_desc, real_url

  if "facebook.com" in real_url.lower() or "fb.watch" in real_url.lower():
    emb_body, emb_img, _ = _fetch_fb_embed_plugin_content(real_url)
    if emb_body and len(emb_body) >= 20:
      return clean_and_validate_image_url(emb_img, real_url, "فيسبوك"), emb_body, real_url

  img_url = ""
  body_text = ""
  req_headers = (
      FB_CRAWLER_HEADERS
      if "facebook.com" in real_url or "fb.com" in real_url
      else DEFAULT_HEADERS
  )
  try:
    r = requests.get(real_url, headers=req_headers, timeout=6.0)
    if r.status_code != 200 or not r.text:
      if press_dom and title_hint:
        return _fetch_wordpress_verbatim_article(press_dom, title_hint, real_url)
      return "", "", real_url

    html_doc = r.text
    for meta_pattern in [
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|og:image:secure_url|twitter:image|twitter:image:src)["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|og:image:secure_url|twitter:image|twitter:image:src)["\']',
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
    ]:
      m_img = re.search(meta_pattern, html_doc[:55000], re.IGNORECASE)
      if m_img:
        candidate_img = clean_and_validate_image_url(m_img.group(1), real_url)
        if candidate_img:
          img_url = candidate_img
          break

    # 1) استخراج النص الأصلي الكامل وصورة JSON-LD إن وجدا
    ld_article_body = ""
    for m_ld in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_doc,
        re.DOTALL | re.IGNORECASE,
    ):
      ld_raw = m_ld.group(1).strip()
      if not img_url:
        m_ld_img = re.search(r'"image"\s*:\s*(?:\{[^{}]*"url"\s*:\s*"([^"]+)"|"([^"]+)")', ld_raw)
        if m_ld_img:
          cand_ldi = clean_and_validate_image_url(decode_js_escaped_text(m_ld_img.group(1) or m_ld_img.group(2) or ""), real_url)
          if cand_ldi:
            img_url = cand_ldi
      m_ab = re.search(r'"articleBody"\s*:\s*"((?:[^"\\]|\\.){80,})"', ld_raw)
      if m_ab:
        cand_ab = clean_full_article_text(decode_js_escaped_text(m_ab.group(1)))
        if len(cand_ab) > len(ld_article_body):
          ld_article_body = cand_ab

    paragraphs = []
    if BeautifulSoup is not None:
      soup = BeautifulSoup(html_doc, "html.parser")
      if not img_url:
        for img_tag in soup.select(
            "article img, .post-content img, .entry-content img, .single-post img, .featured-image img, .post-thumbnail img, main img"
        ):
          src_cand = (
              img_tag.get("data-src")
              or img_tag.get("data-lazy-src")
              or img_tag.get("data-original")
              or img_tag.get("src")
              or ""
          ).strip()
          if not src_cand and img_tag.get("srcset"):
            src_cand = img_tag.get("srcset").split(",")[0].strip().split(" ")[0]
          if src_cand and not src_cand.startswith("data:"):
            valid_c = clean_and_validate_image_url(src_cand, real_url)
            if valid_c and not any(x in valid_c.lower() for x in ["avatar", "logo", "icon", "author"]):
              img_url = valid_c
              break

      for tag in soup.select(
          "script, style, nav, footer, header, aside, form, .related-posts, .comments, .share-buttons, .tags, .post-tags, .author-box, .breadcrumb"
      ):
        tag.decompose()

      main_containers = soup.select(
          "[itemprop='articleBody'], .article-content, .entry-content, .post-content, .td-post-content, .single-content, .details-content, .article-body, .post_content, .story-body, article, main"
      )
      p_elements = []
      for mc in main_containers:
        cand_ps = mc.select("p, h2, h3, blockquote")
        if len(cand_ps) >= 2:
          p_elements = cand_ps
          break
      if not p_elements:
        p_elements = soup.select("p")

      for p_el in p_elements:
        p_txt = clean_display_text(p_el.get_text(" ", strip=True))
        if (
            len(p_txt) >= 20
            and len(re.findall(r"[\u0600-\u06FF]", p_txt)) >= 5
            and not any(
                noise in p_txt
                for noise in [
                    "جميع الحقوق محفوظة",
                    "اشترك في النشرة",
                    "تابعونا على",
                    "اتصل بنا",
                    "سياسة الخصوصية",
                ]
            )
        ):
          if p_txt not in paragraphs:
            paragraphs.append(p_txt)
          if len("\n\n".join(paragraphs)) > 14000:
            break
    else:
      for raw_p in re.findall(
          r"<p[^>]*>(.*?)</p>", html_doc, re.DOTALL | re.IGNORECASE
      ):
        p_txt = clean_display_text(raw_p)
        if (
            len(p_txt) >= 20
            and len(re.findall(r"[\u0600-\u06FF]", p_txt)) >= 5
        ):
          if p_txt not in paragraphs:
            paragraphs.append(p_txt)
          if len("\n\n".join(paragraphs)) > 14000:
            break

    dom_body = "\n\n".join(paragraphs)
    if len(ld_article_body) > len(dom_body) + 100:
      body_text = ld_article_body[:15000]
    else:
      body_text = dom_body[:15000]

    # إذا كانت الصفحة محمية أو أعادت نصاً قصيراً جداً أو بدون صورة، نستعين بواجهة WordPress الخاصة بالجريدة
    if (len(body_text) < 220 or not img_url) and press_dom and title_hint:
      wp_img2, wp_body2, wp_link2 = _fetch_wordpress_verbatim_article(press_dom, title_hint, real_url)
      if len(wp_body2) > len(body_text):
        body_text = wp_body2
      if wp_img2 and not img_url:
        img_url = clean_and_validate_image_url(wp_img2, real_url)
      if wp_link2 and "news.google.com" in real_url:
        real_url = wp_link2
  except Exception:
    pass

  return clean_and_validate_image_url(img_url, real_url), body_text, real_url


def fetch_bing_news_enrichment(title: str, source_name: str = ""):
  q_clean = strip_source_suffix_from_title(title)
  if not q_clean:
    return "", "", ""
  src_clean = re.sub(r"\(.*?\)", "", re.sub(r"🎯", "", clean_display_text(source_name))).strip()
  search_q = f"{q_clean[:75]} {src_clean}".strip()
  bing_url = (
      f"https://www.bing.com/news/search?q={urllib.parse.quote(search_q)}"
      "&format=rss&adlt=strict&cc=MA&setlang=ar"
  )
  try:
    r = requests.get(bing_url, headers=DEFAULT_HEADERS, timeout=3.5)
    if r.status_code == 200 and b"<item>" in r.content:
      raw_xml = r.text
      items_xml = re.findall(r"<item>(.*?)</item>", raw_xml, re.DOTALL)
      for it_x in items_xml[:3]:
        img_m = re.search(
            r"<News:Image>(https?://[^<]+)</News:Image>", it_x, re.IGNORECASE
        )
        if not img_m:
          img_m = re.search(r'url=["\'](https?://[^"\']+)["\']', it_x)
        desc_m = re.search(
            r"<description>(.*?)</description>", it_x, re.DOTALL | re.IGNORECASE
        )
        link_m = re.search(
            r"<link>(.*?)</link>", it_x, re.DOTALL | re.IGNORECASE
        )

        b_link = html.unescape(link_m.group(1).strip()) if link_m else ""
        if "url=" in b_link:
          qs = urllib.parse.parse_qs(urllib.parse.urlparse(b_link).query)
          if "url" in qs and qs["url"]:
            b_link = qs["url"][0]
        b_img = clean_and_validate_image_url(html.unescape(img_m.group(1).strip()) if img_m else "", b_link)
        b_desc = clean_display_text(desc_m.group(1)) if desc_m else ""

        if b_img or len(b_desc) > 45 or (b_link and "bing.com" not in b_link):
          return b_img, b_desc, b_link
  except Exception:
    pass
  return "", "", ""


def enrich_item_content_and_image(item: dict) -> dict:
  url = (item.get("url") or "").strip()
  title = clean_display_text(item.get("title") or "")
  plat = item.get("platform", "الصحف")
  src_dom_hint = (item.get("source_domain_hint") or "").strip()
  src = format_precise_source_with_domain(
      item.get("source_name", plat), url, plat, source_url_hint=src_dom_hint, title_hint=title
  )
  item["source_name"] = src

  raw_snip_full = clean_full_article_text(item.get("raw_snippet") or "")
  raw_snip = clean_display_text(raw_snip_full)
  img_url = clean_and_validate_image_url((item.get("image_url") or "").strip(), url, plat)

  if not img_url:
    img_url = extract_thumbnail_for_item(url, "", plat)

  # التحقق الصارم من تاريخ النشر الحقيقي لفيديوهات يوتيوب عبر بيانات الفيديو الرسمية (uploadDate / publishDate)
  m_yt_enrich = re.search(
      r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
      clean_social_post_url(url),
  )
  if m_yt_enrich or plat == "يوتيوب":
    vid_e = m_yt_enrich.group(1) if m_yt_enrich else ""
    if vid_e:
      yt_meta = fetch_youtube_video_exact_metadata(vid_e, rel_hint=str(item.get("pub_rel") or ""))
      if yt_meta.get("has_exact_date") and float(yt_meta.get("pub_timestamp") or 0) > 0:
        item["pub_date"] = yt_meta["pub_date"]
        item["pub_timestamp"] = float(yt_meta["pub_timestamp"])
        item["_yt_exact_verified"] = True
      if yt_meta.get("short_desc") and len(yt_meta["short_desc"]) > len(raw_snip_full):
        raw_snip_full = yt_meta["short_desc"]
        raw_snip = clean_display_text(raw_snip_full)
      if yt_meta.get("channel_name") and item.get("source_name") in ("", "يوتيوب", "YouTube", "يوتيوب (youtube.com)"):
        ch_n = yt_meta["channel_name"]
        ch_lbl = ch_n if ch_n.startswith("قناة") else f"قناة {ch_n}"
        item["source_name"] = format_precise_source_with_domain(ch_lbl, url, "يوتيوب", title_hint=title)
        src = item["source_name"]

  need_body = (
      not raw_snip_full
      or len(raw_snip_full) < 480
      or "news.google.com" in url
      or raw_snip.lower() == title.lower()
      or raw_snip.startswith(title[:30])
  )
  need_img = not img_url

  if need_img or need_body:
    page_img, page_body, resolved_u = scrape_article_page_content_and_image(
        url, title_hint=title, source_hint=src, domain_hint=src_dom_hint
    )
    if page_img and not img_url:
      img_url = clean_and_validate_image_url(page_img, resolved_u or url, plat)
    if page_body and len(page_body) > len(raw_snip_full):
      raw_snip_full = page_body
      raw_snip = clean_display_text(page_body)
    if (
        resolved_u
        and "news.google.com" not in resolved_u
        and "news.google.com" in url
    ):
      kept_tags = extract_internal_url_fragments(url)
      item["url"] = f"{strip_internal_url_fragments(resolved_u)}{kept_tags}"
      url = item["url"]

  # إذا بقي النص قصيراً أو الصورة مفقودة أو الرابط غير مفكوك في مقال صحفي، نفحص Bing News للحصول على رابط المقال المباشر والصورة
  if (
      plat == "الصحف"
      and not int(item.get("is_custom_target", 0))
      and (not img_url or "news.google.com" in url or len(raw_snip_full) < 350 or raw_snip.lower() == title.lower())
  ):
    b_img, b_desc, b_link = fetch_bing_news_enrichment(title, src)
    if b_img and not img_url:
      img_url = clean_and_validate_image_url(b_img, b_link or url, plat)
    if b_link and "news.google.com" in url and "bing.com" not in b_link:
      kept_tags = extract_internal_url_fragments(url)
      item["url"] = f"{strip_internal_url_fragments(b_link)}{kept_tags}"
      url = item["url"]
    if b_link and len(raw_snip_full) < 350:
      p_img2, p_body2, _ = scrape_article_page_content_and_image(
          b_link, title_hint=title, source_hint=src, domain_hint=src_dom_hint
      )
      if p_img2 and not img_url:
        img_url = clean_and_validate_image_url(p_img2, b_link, plat)
      if p_body2 and len(p_body2) > len(raw_snip_full):
        raw_snip_full = p_body2
    if len(raw_snip_full) < len(b_desc) and b_desc.lower() != title.lower():
      raw_snip_full = b_desc

  # تحديث اسم المصدر مع الدومين النهائي بعد فك الرابط
  item["source_name"] = format_precise_source_with_domain(
      item.get("source_name", src), item.get("url", url), plat, source_url_hint=src_dom_hint, title_hint=title
  )
  item["image_url"] = clean_and_validate_image_url(img_url, item.get("url", url), plat)
  final_full_text = raw_snip_full if len(raw_snip_full) >= len(raw_snip) else raw_snip
  item["raw_snippet"] = final_full_text[:15000]
  return item


def build_extractive_arabic_summary(
    title: str, snippet: str, platform: str, source_name: str
) -> str:
  t_clean = clean_display_text(title)
  s_clean = clean_display_text(snippet)

  if s_clean and t_clean:
    if s_clean.startswith(t_clean):
      s_clean = s_clean[len(t_clean) :].lstrip(" -–—:•|.")
    elif len(t_clean) > 25 and t_clean[:25] in s_clean[:40]:
      idx = s_clean.find(t_clean[:25])
      s_clean = s_clean[idx + len(t_clean) :].lstrip(" -–—:•|.")

  s_clean = re.sub(
      r"^(\d{1,2}\s+[^\s]+\s+20\d{2}|[A-Za-z]{3,9}\s+\d{1,2},?\s+20\d{2}|\d+\s*(?:hours?|days?|minutes?|ساعات|ساعة|يوم|أيام|دقيقة)\s*(?:ago)?)\s*[-–—·•:]\s*",
      "",
      s_clean,
      flags=re.IGNORECASE,
  ).strip()

  if s_clean and len(s_clean) >= 45 and s_clean.lower() != t_clean.lower():
    sentences = [
        seg.strip()
        for seg in re.split(r"(?<=[.!؟\n])\s+", s_clean)
        if len(seg.strip()) > 25 and seg.strip() != t_clean
    ]
    if sentences:
      summary_txt = " ".join(sentences[:3])
      return summary_txt[:420] + ("..." if len(summary_txt) > 420 else "")
    return s_clean[:420] + ("..." if len(s_clean) > 420 else "")

  src_label = clean_display_text(source_name or platform)
  return (
      f"تفيد المعطيات الواردة عبر ({src_label}) بمتابعة مستجدات تتعلق بـ {t_clean}، "
      "ضمن التغطية الإعلامية المتواصلة لأنشطة ومستجدات المصدر."
  )


def get_fallback_thumbnail_data_uri(platform: str, source_name: str = "") -> str:
  themes = {
      "الصحف": ("#064e3b", "#10b981", "PRESS", "⚖️ صحافة قضائية"),
      "فيسبوك": ("#1e3a8a", "#3b82f6", "FACEBOOK", "🟦 منشور فيسبوك"),
      "إكس": ("#0f172a", "#94a3b8", "X / TWITTER", "⬛ تغريدة إكس"),
      "يوتيوب": ("#7f1d1d", "#ef4444", "YOUTUBE", "🟥 فيديو يوتيوب"),
      "أخرى": ("#4c1d95", "#a855f7", "SOCIAL", "🟪 تواصل اجتماعي"),
  }
  bg1, accent, en_lbl, ar_lbl = themes.get(
      platform, ("#0f172a", "#38bdf8", "AL-MARSAD AL-QADAI", "⚖️ المرصد القضائي")
  )
  src_short = html.escape(clean_display_text(source_name or platform)[:26])
  svg = (
      f'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200" viewBox="0 0 320 200">'
      f"<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
      f"<stop offset='0%' stop-color='{bg1}'/><stop offset='100%' stop-color='#090d16'/>"
      f"</linearGradient></defs>"
      f"<rect width='320' height='200' rx='14' fill='url(#g)'/>"
      f"<circle cx='270' cy='40' r='55' fill='{accent}' fill-opacity='0.12'/>"
      f"<circle cx='45' cy='165' r='45' fill='{accent}' fill-opacity='0.1'/>"
      f"<rect x='16' y='16' width='288' height='168' rx='10' fill='none' stroke='{accent}' stroke-opacity='0.35' stroke-width='1.5'/>"
      f"<text x='160' y='78' text-anchor='middle' fill='{accent}' font-family='Cairo, sans-serif' font-size='15' font-weight='800'>{en_lbl}</text>"
      f"<text x='160' y='115' text-anchor='middle' fill='#f8fafc' font-family='Cairo, sans-serif' font-size='20' font-weight='900'>{ar_lbl}</text>"
      f"<text x='160' y='148' text-anchor='middle' fill='#cbd5e1' font-family='Cairo, sans-serif' font-size='13' font-weight='700'>{src_short}</text>"
      f"</svg>"
  )
  b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
  return f"data:image/svg+xml;base64,{b64}"


def extract_thumbnail_for_item(
    url: str, raw_html_desc: str = "", platform: str = "الصحف"
) -> str:
  u = strip_internal_url_fragments(url)
  m_yt = re.search(
      r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
      u,
  )
  if m_yt:
    return f"https://i.ytimg.com/vi/{m_yt.group(1)}/hqdefault.jpg"

  if raw_html_desc:
    for m_img in re.finditer(
        r'<img[^>]+(?:data-src|data-lazy-src|src)=["\']([^"\'>\s]+)["\']',
        str(raw_html_desc),
        re.IGNORECASE,
    ):
      img_u = clean_and_validate_image_url(m_img.group(1), u, platform)
      if img_u:
        return img_u

  return ""


# =====================================================================
# 4. قفل التزامن المركزي لمنع تضارب SQLite والخيوط (Thread-Safety)
# =====================================================================
_MODULE_DB_LOCK = threading.RLock()
_MODULE_SCAN_LOCK = threading.Lock()


def _create_shared_runtime():
  return {
      "db_lock": _MODULE_DB_LOCK,
      "scan_lock": _MODULE_SCAN_LOCK,
      "stop_requested": False,
      "abort_bg_for_manual": False,
      "active_scan": None,
      "daemon_started": False,
      "bg_scanning": False,
      "last_done_mode": None,
      "last_done_count": 0,
      "last_done_ts": 0.0,
      "cloud_restored": False,
      "cloud_backup_msg_id": 0,
      "cloud_backup_file_id": "",
      "last_cloud_push_ts": 0.0,
      "fulltext_checked_ids": set(),
      "gemini_tts_cooldown_until": 0.0,
      "db_initialized_version": "",
      "db_version_counter": 1,
      "cached_articles_list": None,
      "cached_articles_sig": None,
      "last_auto_completed_ts": 0.0,
  }


if st is not None and hasattr(st, "cache_resource"):
  get_shared_runtime = st.cache_resource(_create_shared_runtime)
else:
  _FALLBACK_RUNTIME = _create_shared_runtime()

  def get_shared_runtime():
    return _FALLBACK_RUNTIME


def invalidate_articles_cache():
  """إبطال ذاكرة التخزين المؤقت للأخبار عند إضافة أو تعديل أو حذف أي سجل لضمان تحديث الواجهة فوراً."""
  try:
    rt = get_shared_runtime()
    rt["db_version_counter"] = int(rt.get("db_version_counter", 1)) + 1
    rt["cached_articles_list"] = None
    rt["cached_articles_sig"] = None
  except Exception:
    pass


def get_db_lock():
  try:
    return get_shared_runtime()["db_lock"]
  except Exception:
    return _MODULE_DB_LOCK


def get_scan_lock():
  try:
    return get_shared_runtime()["scan_lock"]
  except Exception:
    return _MODULE_SCAN_LOCK


def request_stop_scan():
  try:
    rt = get_shared_runtime()
    rt["stop_requested"] = True
  except Exception:
    pass
  try:
    if st is not None:
      st.session_state["stop_scan"] = True
  except Exception:
    pass


def clear_stop_scan():
  """تصفير طلب الإيقاف وإعطاء الأولوية الفورية للرصد اليدوي عند النقر على أي زر تشغيل."""
  try:
    rt = get_shared_runtime()
    rt["stop_requested"] = False
    if rt.get("bg_scanning", False):
      rt["abort_bg_for_manual"] = True
  except Exception:
    pass
  try:
    if st is not None:
      st.session_state["stop_scan"] = False
  except Exception:
    pass


def is_stop_requested() -> bool:
  """التحقق الذكي من طلب الإيقاف مع الفصل التام بين خيط الرصد التلقائي الخلفي وبين الرصد اليدوي للمستخدم."""
  t_name = threading.current_thread().name or ""
  is_bg_thread = (
      t_name.startswith("JusticeAutoMonitor")
      or t_name.startswith("OnLoadAsyncCycle")
      or t_name.startswith("DeferredStartup")
  )
  try:
    rt = get_shared_runtime()
    if is_bg_thread:
      return bool(rt.get("abort_bg_for_manual", False))
    if rt.get("stop_requested", False):
      return True
  except Exception:
    pass
  if not is_bg_thread:
    try:
      if st is not None:
        return bool(st.session_state.get("stop_scan", False))
    except Exception:
      pass
  return False


# =====================================================================
# 5. إدارة قاعدة البيانات والأرشيف الدائم وتطهير البيانات غير المطابقة
# =====================================================================
REQUIRED_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "title": "TEXT DEFAULT ''",
    "summary": "TEXT DEFAULT ''",
    "source_name": "TEXT DEFAULT ''",
    "platform": "TEXT DEFAULT 'الصحف'",
    "url": "TEXT UNIQUE",
    "pub_date": "TEXT DEFAULT ''",
    "pub_timestamp": "REAL DEFAULT 0",
    "sentiment": "TEXT DEFAULT 'محايد'",
    "category": "TEXT DEFAULT 'شؤون قضائية'",
    "relevance_score": "INTEGER DEFAULT 85",
    "is_custom_target": "INTEGER DEFAULT 0",
    "raw_snippet": "TEXT DEFAULT ''",
    "image_url": "TEXT DEFAULT ''",
    "created_at": "REAL DEFAULT 0",
    "telegram_sent": "INTEGER DEFAULT 0",
}

INSERT_COLUMN_NAMES = [
    "title",
    "summary",
    "source_name",
    "platform",
    "url",
    "pub_date",
    "pub_timestamp",
    "sentiment",
    "category",
    "relevance_score",
    "is_custom_target",
    "raw_snippet",
    "image_url",
    "created_at",
]


def _open_sqlite_conn():
  conn = sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)
  try:
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA journal_mode=MEMORY;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
  except Exception:
    pass
  return conn


def _create_fresh_articles_table(c):
  c.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            source_name TEXT DEFAULT '',
            platform TEXT DEFAULT 'الصحف',
            url TEXT UNIQUE,
            pub_date TEXT DEFAULT '',
            pub_timestamp REAL DEFAULT 0,
            sentiment TEXT DEFAULT 'محايد',
            category TEXT DEFAULT 'شؤون قضائية',
            relevance_score INTEGER DEFAULT 85,
            is_custom_target INTEGER DEFAULT 0,
            raw_snippet TEXT DEFAULT '',
            image_url TEXT DEFAULT '',
            created_at REAL DEFAULT 0
        )
        """)


def _rebuild_articles_table_safely(conn):
  c = conn.cursor()
  try:
    c.execute("PRAGMA table_info(articles)")
    old_info = c.fetchall()
    old_cols = [r[1] for r in old_info]
    if not old_cols:
      _create_fresh_articles_table(c)
      conn.commit()
      return

    c.execute("DROP TABLE IF EXISTS articles_migration_tmp")
    c.execute("ALTER TABLE articles RENAME TO articles_migration_tmp")
    _create_fresh_articles_table(c)

    common_cols = [col for col in INSERT_COLUMN_NAMES if col in old_cols]
    if common_cols:
      cols_csv = ", ".join(common_cols)
      c.execute(
          f"INSERT OR IGNORE INTO articles ({cols_csv}) "
          f"SELECT {cols_csv} FROM articles_migration_tmp"
      )
    c.execute("DROP TABLE IF EXISTS articles_migration_tmp")
    conn.commit()
  except Exception:
    try:
      c.execute("DROP TABLE IF EXISTS articles")
      _create_fresh_articles_table(c)
      conn.commit()
    except Exception:
      pass


def _ensure_schema_on_conn(conn):
  c = conn.cursor()
  _create_fresh_articles_table(c)
  c.execute("PRAGMA table_info(articles)")
  info_rows = c.fetchall()
  existing_cols = {row[1] for row in info_rows}

  has_incompatible_notnull = any(
      (row[1] not in REQUIRED_COLUMNS and int(row[3]) == 1 and row[4] is None)
      for row in info_rows
  )
  if has_incompatible_notnull:
    _rebuild_articles_table_safely(conn)
    c.execute("PRAGMA table_info(articles)")
    existing_cols = {row[1] for row in c.fetchall()}

  for col_name, col_def in REQUIRED_COLUMNS.items():
    if col_name not in existing_cols and col_name != "id":
      col_def_clean = col_def.replace("UNIQUE", "").strip()
      try:
        c.execute(f"ALTER TABLE articles ADD COLUMN {col_name} {col_def_clean}")
      except Exception:
        pass

  try:
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_pub_ts ON articles(pub_timestamp DESC)"
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_platform ON articles(platform)")
  except Exception:
    pass
  conn.commit()


def load_custom_targets(force_disk: bool = False):
  rt = get_shared_runtime()
  if not force_disk and isinstance(rt.get("_cached_custom_targets"), list):
    return [dict(x) for x in rt["_cached_custom_targets"]]
  default_targets = [
      {"url": "https://www.hespress.com", "keyword": ""},
      {"url": "https://www.youtube.com/@Hespress", "keyword": ""},
  ]
  res = default_targets
  if os.path.exists(CUSTOM_TARGETS_FILE):
    try:
      with open(CUSTOM_TARGETS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
      if isinstance(data, list):
        cleaned = []
        for item in data:
          if isinstance(item, dict) and item.get("url", "").strip():
            cleaned.append({
                "url": item["url"].strip(),
                "keyword": item.get("keyword", "").strip(),
            })
        res = cleaned
    except Exception:
      pass
  rt["_cached_custom_targets"] = [dict(x) for x in res]
  return res


def _has_inappropriate_terms(title: str, snippet: str, url: str) -> bool:
  combined = f"{clean_display_text(title)} {clean_display_text(snippet)} {str(url or '')}".lower()
  return any(bad_w in combined for bad_w in BLOCKED_INAPPROPRIATE_TERMS)


def purge_invalid_articles_from_db():
  """تطهير الأخبار المخالفة وتصحيح تواريخ نشر فيديوهات يوتيوب الحقيقية لضمان عدم عرض أي فيديو قديم على أنه منشور حديثاً."""
  lock = get_db_lock()
  current_targets = load_custom_targets()
  now_ts = time.time()
  rt = get_shared_runtime()
  verified_yt_ids_set = rt.setdefault("verified_db_yt_vids", set())

  # استخراج معرفات فيديوهات يوتيوب غير المفحوصة بعد للتحقق المتوازي السريع من تاريخ نشرها الحقيقي
  yt_candidates_to_verify = []
  with lock:
    try:
      conn_pre = _open_sqlite_conn()
      _ensure_schema_on_conn(conn_pre)
      conn_pre.row_factory = sqlite3.Row
      c_pre = conn_pre.cursor()
      c_pre.execute("SELECT id, url, platform, pub_timestamp, created_at FROM articles WHERE platform = 'يوتيوب' OR url LIKE '%youtube.com%' OR url LIKE '%youtu.be%'")
      for r_y in c_pre.fetchall():
        u_y = clean_social_post_url(r_y["url"] or "")
        m_vy = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})", u_y)
        if m_vy:
          vid_y = m_vy.group(1)
          if vid_y not in verified_yt_ids_set:
            yt_candidates_to_verify.append((r_y["id"], vid_y, float(r_y["pub_timestamp"] or 0), float(r_y["created_at"] or 0)))
      conn_pre.close()
    except Exception:
      pass

  yt_verified_meta_map = {}
  for _, vid_k, _, _ in yt_candidates_to_verify:
    verified_yt_ids_set.add(vid_k)
    if vid_k in _YT_EXACT_META_CACHE:
      yt_verified_meta_map[vid_k] = _YT_EXACT_META_CACHE[vid_k]

  with lock:
    removed_any = False
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute(
          "SELECT id, title, summary, source_name, platform, raw_snippet, url, is_custom_target, pub_timestamp, created_at FROM articles"
      )
      rows = c.fetchall()
      bad_ids = []
      date_updates = []
      for r in rows:
        d = dict(r)
        snip = f"{d.get('summary') or ''} {d.get('raw_snippet') or ''}"
        u_str = d.get("url") or ""
        t_str = d.get("title") or ""
        if _has_inappropriate_terms(t_str, snip, u_str):
          bad_ids.append((d["id"],))
          continue

        pub_t = float(d.get("pub_timestamp") or 0)
        mon_t = float(d.get("created_at") or pub_t)

        # تصحيح تاريخ النشر الفعلي لفيديوهات يوتيوب المخزنة في القاعدة
        u_clean_y = clean_social_post_url(u_str)
        m_vy = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})", u_clean_y)
        if m_vy:
          vid_k = m_vy.group(1)
          meta_y = yt_verified_meta_map.get(vid_k) or _YT_EXACT_META_CACHE.get(vid_k)
          if meta_y and meta_y.get("has_exact_date") and float(meta_y.get("pub_timestamp") or 0) > 0:
            real_pts = float(meta_y["pub_timestamp"])
            real_pstr = meta_y["pub_date"]
            if abs(real_pts - pub_t) > 900:
              pub_t = real_pts
              # إذا كان الفيديو قديماً في الحقيقة (منشور منذ أكثر من 24 ساعة)، نضبط وقت رصده على وقت نشره الحقيقي حتى لا يظهر كفيديو جديد اليوم
              new_mon_t = real_pts if (now_ts - real_pts) >= 86400 else mon_t
              mon_t = new_mon_t
              date_updates.append((real_pstr, real_pts, new_mon_t, d["id"]))

        is_tgt = bool(d.get("is_custom_target"))
        if not is_strictly_judicial_and_clean(
            t_str, snip, u_str, "", is_target=is_tgt
        ):
          bad_ids.append((d["id"],))
        elif is_tgt and not belongs_to_any_custom_target(d, current_targets):
          bad_ids.append((d["id"],))
      try:
        c.execute(
            "UPDATE articles SET source_name = REPLACE(source_name, 'المرصد الوطني للعدالة والقضاء', 'المرصد القضائي'), "
            "summary = REPLACE(summary, 'المرصد الوطني للعدالة والقضاء', 'المرصد القضائي'), "
            "title = REPLACE(title, 'المرصد الوطني للعدالة والقضاء', 'المرصد القضائي') "
            "WHERE source_name LIKE '%المرصد الوطني%' OR summary LIKE '%المرصد الوطني%' OR title LIKE '%المرصد الوطني%'"
        )
        if c.rowcount and c.rowcount > 0:
          conn.commit()
          removed_any = True
      except Exception:
        pass
      if date_updates:
        c.executemany("UPDATE articles SET pub_date = ?, pub_timestamp = ?, created_at = ? WHERE id = ?", date_updates)
        conn.commit()
        removed_any = True
      if bad_ids:
        c.executemany("DELETE FROM articles WHERE id = ?", bad_ids)
        conn.commit()
        removed_any = True
      conn.close()
    except Exception:
      pass

  # تحديث ملفات الأرشيف خارج قفل SQLite لمنع حجز الواجهة
  if True:
    # تحديث تواريخ يوتيوب المصححة داخل ملفات الأرشيف JSON أيضاً
    if yt_verified_meta_map:
      for arch_path in (ARCHIVE_JSON_FILE, PERSISTENT_HOME_ARCHIVE_JSON):
        if os.path.exists(arch_path):
          try:
            with open(arch_path, "r", encoding="utf-8") as f:
              arch_data = json.load(f)
            if isinstance(arch_data, list):
              changed_arch_dates = False
              for item in arch_data:
                if not isinstance(item, dict):
                  continue
                u_a = clean_social_post_url(item.get("url") or "")
                m_va = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})", u_a)
                if m_va and m_va.group(1) in yt_verified_meta_map:
                  meta_a = yt_verified_meta_map[m_va.group(1)]
                  if meta_a.get("has_exact_date") and float(meta_a.get("pub_timestamp") or 0) > 0:
                    r_pts = float(meta_a["pub_timestamp"])
                    if abs(r_pts - float(item.get("pub_timestamp") or 0)) > 900:
                      item["pub_date"] = meta_a["pub_date"]
                      item["pub_timestamp"] = r_pts
                      if (now_ts - r_pts) >= 86400:
                        item["created_at"] = r_pts
                      changed_arch_dates = True
              if changed_arch_dates:
                with open(arch_path, "w", encoding="utf-8") as f:
                  json.dump(arch_data, f, ensure_ascii=False, indent=2)
                removed_any = True
          except Exception:
            pass

    for arch_path in (ARCHIVE_JSON_FILE, PERSISTENT_HOME_ARCHIVE_JSON):
      if os.path.exists(arch_path):
        try:
          with open(arch_path, "r", encoding="utf-8") as f:
            arch_data = json.load(f)
          if isinstance(arch_data, list):
            cleaned_arch = [
                item for item in arch_data
                if isinstance(item, dict)
                and is_strictly_judicial_and_clean(
                    item.get("title", ""),
                    f"{item.get('summary', '')} {item.get('raw_snippet', '')}",
                    item.get("url", ""),
                    "",
                    is_target=bool(item.get("is_custom_target", 0)),
                )
            ]
            if len(cleaned_arch) != len(arch_data):
              with open(arch_path, "w", encoding="utf-8") as f:
                json.dump(cleaned_arch, f, ensure_ascii=False, indent=2)
              removed_any = True
        except Exception:
          pass

    if removed_any and os.path.exists(DB_FILE):
      for dst_db in (REPO_DB_FILE, PERSISTENT_HOME_DB):
        try:
          shutil.copyfile(DB_FILE, dst_db)
        except Exception:
          pass


def load_telegram_sent_ledger() -> set:
  """تحميل سجل البصمات المرسلة سابقاً إلى تلغرام لمنع تكرار الإرسال نهائياً."""
  ledger = set()
  if os.path.exists(TELEGRAM_LEDGER_FILE):
    try:
      with open(TELEGRAM_LEDGER_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
      if isinstance(data, list):
        ledger.update(str(x) for x in data if x)
    except Exception:
      pass
  return ledger


def save_telegram_sent_ledger(ledger: set):
  try:
    trimmed = sorted(list(ledger))[-8000:]
    tmp_p = f"{TELEGRAM_LEDGER_FILE}.tmp"
    with open(tmp_p, "w", encoding="utf-8") as f:
      json.dump(trimmed, f, ensure_ascii=False)
    os.replace(tmp_p, TELEGRAM_LEDGER_FILE)
  except Exception:
    pass


def deduplicate_and_seed_telegram_ledger():
  """إزالة أي أخبار مكررة من قاعدة البيانات والأرشيف مع الحفاظ على أقدم وقت رصد (created_at) وتغذية سجل تلغرام."""
  lock = get_db_lock()
  with lock:
    ledger = load_telegram_sent_ledger()
    ledger_changed = False
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute("SELECT * FROM articles ORDER BY created_at ASC, pub_timestamp ASC, id ASC")
      rows = [dict(r) for r in c.fetchall()]
      seen_keys = set()
      dup_ids = []
      for r in rows:
        item_keys = compute_article_dedup_keys(r.get("title", ""), r.get("url", ""))
        if not item_keys.issubset(ledger):
          ledger.update(item_keys)
          ledger_changed = True
        plat_sc = r.get("platform") or "الصحف"
        tgt_sc = int(r.get("is_custom_target") or 0)
        scoped_keys = {f"{plat_sc}::{tgt_sc}::{k}" for k in item_keys}
        if scoped_keys & seen_keys:
          dup_ids.append((r["id"],))
        else:
          seen_keys.update(scoped_keys)
      if dup_ids:
        c.executemany("DELETE FROM articles WHERE id = ?", dup_ids)
        conn.commit()
      c.execute("UPDATE articles SET telegram_sent = 1 WHERE telegram_sent IS NULL OR telegram_sent = 0")
      conn.commit()
      conn.close()
    except Exception:
      pass

    if ledger_changed or not os.path.exists(TELEGRAM_LEDGER_FILE):
      save_telegram_sent_ledger(ledger)


def _merge_external_sqlite_into_runtime(src_db_path: str):
  """دمج كافة السجلات المحفوظة في قاعدة بيانات خارجية (REPO_DB_FILE أو PERSISTENT_HOME_DB) داخل قاعدة التشغيل دون فقدان أي عنصر من الأرشيف."""
  if not src_db_path or not os.path.exists(src_db_path) or os.path.getsize(src_db_path) == 0:
    return
  if os.path.abspath(src_db_path) == os.path.abspath(DB_FILE):
    return
  try:
    src_conn = sqlite3.connect(src_db_path, timeout=15.0)
    src_conn.row_factory = sqlite3.Row
    sc = src_conn.cursor()
    sc.execute("SELECT * FROM articles")
    src_rows = [dict(r) for r in sc.fetchall()]
    src_conn.close()
  except Exception:
    return

  if not src_rows:
    return

  try:
    dst_conn = _open_sqlite_conn()
    _ensure_schema_on_conn(dst_conn)
    dc = dst_conn.cursor()
    for r in src_rows:
      pub_ts = float(r.get("pub_timestamp") or (time.time() - 90000))
      # إذا كان العنصر قديماً ولم يسجل له created_at، نستخدم pub_timestamp حتى يبقى في الأرشيف ولا يعود للنشط
      c_at = float(r.get("created_at") or pub_ts)
      if c_at <= 0:
        c_at = pub_ts
      dc.execute(
          """
          INSERT OR IGNORE INTO articles (
              title, summary, source_name, platform, url,
              pub_date, pub_timestamp, sentiment, category,
              relevance_score, is_custom_target, raw_snippet,
              image_url, created_at, telegram_sent
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          """,
          (
              clean_display_text(r.get("title", "")),
              clean_display_text(r.get("summary", "")),
              clean_display_text(r.get("source_name", "")),
              r.get("platform", "الصحف"),
              r.get("url", ""),
              r.get("pub_date", ""),
              pub_ts,
              r.get("sentiment", "محايد"),
              r.get("category", "شؤون قضائية"),
              int(r.get("relevance_score") or 85),
              int(r.get("is_custom_target") or 0),
              clean_full_article_text(r.get("raw_snippet", "")),
              r.get("image_url", ""),
              c_at,
              1,
          ),
      )
    dst_conn.commit()
    dst_conn.close()
  except Exception:
    pass


_CLOUD_SYNC_LOCK = threading.Lock()


def _get_tg_credentials_fast() -> tuple:
  """جلب بيانات بوت تلغرام بسرعة لاستخدامها في استعادة ومزامنة السحابة التلقائية."""
  token = DEFAULT_TG_TOKEN
  chat_id = DEFAULT_TG_CHAT_ID
  if os.path.exists(CREDENTIALS_FILE):
    try:
      with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        d = json.load(f)
      if isinstance(d, dict):
        token = (d.get("telegram_bot_token") or token).strip()
        chat_id = (d.get("telegram_chat_id") or chat_id).strip()
    except Exception:
      pass
  env_t = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
  env_c = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
  if env_t:
    token = env_t
  if env_c:
    chat_id = env_c
  return token, chat_id



def ensure_telegram_bot_branding_updated(token: str = "", chat_id: str = "", force: bool = False):
  """تحديث اسم ووصف بوت التلغرام ومحادثته رسمياً من 'المرصد الوطني للعدالة والقضاء' إلى الاسم الجديد 'المرصد القضائي' عبر جميع اللغات."""
  rt = get_shared_runtime()
  if rt.get("tg_branding_version") == DAEMON_CODE_VERSION and not force:
    return
  if not token or not chat_id:
    t_fast, c_fast = _get_tg_credentials_fast()
    token = token or t_fast
    chat_id = chat_id or c_fast
  if not token:
    return
  rt["tg_branding_version"] = DAEMON_CODE_VERSION
  rt["tg_branding_updated"] = True

  def _sync_branding_worker():
    # 1) تحديث اسم البوت لجميع واجهات اللغات (الافتراضية، العربية، الفرنسية، الإنجليزية)
    for lang_c in ("", "ar", "fr", "en"):
      try:
        payload_name = {"name": "المرصد القضائي"}
        if lang_c:
          payload_name["language_code"] = lang_c
        requests.post(
            f"https://api.telegram.org/bot{token}/setMyName",
            json=payload_name,
            timeout=5,
        )
      except Exception:
        pass

    # 2) تحديث الوصف المختصر لجميع اللغات
    for lang_c in ("", "ar", "fr", "en"):
      try:
        payload_short = {
            "short_description": "⚖️ المرصد القضائي — منصة الرصد الإعلامي والقضائي الذكي"
        }
        if lang_c:
          payload_short["language_code"] = lang_c
        requests.post(
            f"https://api.telegram.org/bot{token}/setMyShortDescription",
            json=payload_short,
            timeout=5,
        )
      except Exception:
        pass

    # 3) تحديث الوصف الكامل مع الحفاظ على وسم المزامنة السحابية [CLOUD_STATE:...]
    try:
      r_desc = requests.get(
          f"https://api.telegram.org/bot{token}/getMyDescription", timeout=5
      )
      if r_desc.status_code == 200:
        curr_desc = r_desc.json().get("result", {}).get("description", "")
        m_sync = re.search(r"(\[CLOUD_STATE:\d+:[A-Za-z0-9_-]+\])", curr_desc)
        sync_tag = f"\n{m_sync.group(1)}" if m_sync else ""
        new_desc = (
            "⚖️ المرصد القضائي — نظام الرصد القضائي والأرشيف السحابي الدائم"
            f"{sync_tag}"
        )
        for lang_c in ("", "ar", "fr", "en"):
          p_desc = {"description": new_desc[:510]} if not lang_c else {"description": "⚖️ المرصد القضائي — نظام الرصد القضائي والأرشيف السحابي الدائم", "language_code": lang_c}
          requests.post(
              f"https://api.telegram.org/bot{token}/setMyDescription",
              json=p_desc,
              timeout=5,
          )
    except Exception:
      pass

    # 4) إذا كانت المحادثة قناة أو مجموعة، نحدّث عنوانها أيضاً، ونحدّث وصف الرسالة السحابية المثبتة
    if chat_id:
      try:
        requests.post(
            f"https://api.telegram.org/bot{token}/setChatTitle",
            json={"chat_id": chat_id, "title": "المرصد القضائي"},
            timeout=4,
        )
      except Exception:
        pass
      try:
        r_chat = requests.post(
            f"https://api.telegram.org/bot{token}/getChat",
            json={"chat_id": chat_id},
            timeout=5,
        )
        if r_chat.status_code == 200:
          pinned = r_chat.json().get("result", {}).get("pinned_message", {})
          if isinstance(pinned, dict) and pinned.get("message_id"):
            p_cap = str(pinned.get("caption") or "")
            if "المرصد الوطني" in p_cap:
              new_cap = p_cap.replace("المرصد الوطني للعدالة والقضاء", "المرصد القضائي").replace("المرصد الوطني", "المرصد القضائي")
              requests.post(
                  f"https://api.telegram.org/bot{token}/editMessageCaption",
                  json={
                      "chat_id": chat_id,
                      "message_id": int(pinned["message_id"]),
                      "caption": new_cap,
                  },
                  timeout=5,
              )
      except Exception:
        pass

  if os.environ.get("CRON_MODE") == "1" or force:
    _sync_branding_worker()
  else:
    threading.Thread(
        target=_sync_branding_worker,
        daemon=True,
        name="TelegramBotBrandingUpdater",
    ).start()


def restore_state_from_telegram_cloud(force: bool = False) -> bool:
  """استعادة قاعدة البيانات الكاملة والأرشيف وسجل إشعارات تلغرام والروابط المخصصة من سحابة تلغرام تلقائياً عند إعادة تشغيل السيرفر أو فتح المنصة."""
  token, chat_id = _get_tg_credentials_fast()
  if token:
    ensure_telegram_bot_branding_updated(token, chat_id)

  rt = get_shared_runtime()
  if rt.get("cloud_restored") and not force:
    return False

  if not token or not chat_id:
    rt["cloud_restored"] = True
    return False

  file_id_candidates = []
  detected_msg_id = 0

  # 1) فحص وصف البوت على خوادم تلغرام (يحفظ أحدث معرف ملف السحابة حتى لو ألغى المستخدم تثبيت الرسالة)
  try:
    r_desc = requests.get(
        f"https://api.telegram.org/bot{token}/getMyDescription", timeout=5
    )
    if r_desc.status_code == 200:
      desc_txt = r_desc.json().get("result", {}).get("description", "")
      m_sync = re.search(r"\[CLOUD_STATE:(\d+):([A-Za-z0-9_-]+)\]", desc_txt)
      if m_sync:
        detected_msg_id = int(m_sync.group(1))
        file_id_candidates.append(m_sync.group(2))
  except Exception:
    pass

  # 2) فحص الرسالة المثبتة في المحادثة عبر getChat
  try:
    r_chat = requests.post(
        f"https://api.telegram.org/bot{token}/getChat",
        json={"chat_id": chat_id},
        timeout=5,
    )
    if r_chat.status_code == 200:
      pinned = r_chat.json().get("result", {}).get("pinned_message", {})
      if isinstance(pinned, dict) and pinned.get("document"):
        p_mid = int(pinned.get("message_id") or 0)
        p_fid = str(pinned["document"].get("file_id") or "").strip()
        if p_mid and not detected_msg_id:
          detected_msg_id = p_mid
        if p_fid and p_fid not in file_id_candidates:
          file_id_candidates.append(p_fid)
  except Exception:
    pass

  if detected_msg_id:
    rt["cloud_backup_msg_id"] = detected_msg_id

  if not file_id_candidates:
    rt["cloud_restored"] = True
    return False

  payload = None
  for fid in file_id_candidates:
    try:
      r_gf = requests.get(
          f"https://api.telegram.org/bot{token}/getFile",
          params={"file_id": fid},
          timeout=5,
      )
      if r_gf.status_code != 200:
        continue
      f_path = r_gf.json().get("result", {}).get("file_path", "")
      if not f_path:
        continue
      r_dl = requests.get(
          f"https://api.telegram.org/file/bot{token}/{f_path}", timeout=10
      )
      if r_dl.status_code != 200 or not r_dl.content:
        continue
      try:
        raw_json_bytes = gzip.decompress(r_dl.content)
      except Exception:
        raw_json_bytes = r_dl.content
      payload = json.loads(raw_json_bytes.decode("utf-8"))
      if isinstance(payload, dict):
        rt["cloud_backup_file_id"] = fid
        break
    except Exception:
      pass

  rt["cloud_restored"] = True
  if not isinstance(payload, dict):
    return False

  lock = get_db_lock()
  with lock:
    # أ) استعادة سجل تلغرام المرسل سابقاً لمنع إعادة إرسال أي خبر قديم نهائياً
    cloud_ledger = payload.get("telegram_ledger", [])
    local_ledger = load_telegram_sent_ledger()
    if isinstance(cloud_ledger, list) and cloud_ledger:
      local_ledger.update(str(k) for k in cloud_ledger if k)

    # ب) استعادة الإعدادات ومفتاح Gemini API والروابط المخصصة إن وجدت
    cloud_creds = payload.get("credentials", {})
    if isinstance(cloud_creds, dict) and cloud_creds:
      try:
        curr_c = {}
        if os.path.exists(CREDENTIALS_FILE):
          with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            curr_c = json.load(f) or {}
        if not curr_c.get("gemini_api_key") and cloud_creds.get("gemini_api_key"):
          curr_c["gemini_api_key"] = cloud_creds["gemini_api_key"]
        for k_c, v_c in cloud_creds.items():
          if k_c not in curr_c or not curr_c[k_c]:
            curr_c[k_c] = v_c
        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
          json.dump(curr_c, f, ensure_ascii=False, indent=2)
      except Exception:
        pass

    cloud_targets = payload.get("custom_targets", [])
    if isinstance(cloud_targets, list) and cloud_targets and not os.path.exists(CUSTOM_TARGETS_FILE):
      try:
        with open(CUSTOM_TARGETS_FILE, "w", encoding="utf-8") as f:
          json.dump(cloud_targets, f, ensure_ascii=False, indent=2)
      except Exception:
        pass

    cloud_kw_trackers = payload.get("platform_keyword_trackers", [])
    if isinstance(cloud_kw_trackers, list) and cloud_kw_trackers and not os.path.exists(PLATFORM_KEYWORD_TRACKERS_FILE):
      try:
        with open(PLATFORM_KEYWORD_TRACKERS_FILE, "w", encoding="utf-8") as f:
          json.dump(cloud_kw_trackers, f, ensure_ascii=False, indent=2)
      except Exception:
        pass

    # ج) استعادة جميع الأخبار والأرشيف ودمجها في ملفات الأرشيف المحلية
    cloud_articles = payload.get("articles", [])
    if isinstance(cloud_articles, list) and cloud_articles:
      for a_it in cloud_articles:
        if isinstance(a_it, dict):
          local_ledger.update(
              compute_article_dedup_keys(a_it.get("title", ""), a_it.get("url", ""))
          )
      merged_arch = {}
      for arch_p in (PERSISTENT_HOME_ARCHIVE_JSON, ARCHIVE_JSON_FILE):
        if os.path.exists(arch_p):
          try:
            with open(arch_p, "r", encoding="utf-8") as f:
              loc_list = json.load(f)
            if isinstance(loc_list, list):
              for it_l in loc_list:
                if isinstance(it_l, dict) and it_l.get("url"):
                  merged_arch[it_l["url"]] = it_l
          except Exception:
            pass
      for it_c in cloud_articles:
        if isinstance(it_c, dict) and it_c.get("url"):
          if not is_strictly_judicial_and_clean(
              it_c.get("title", ""),
              f"{it_c.get('summary', '')} {it_c.get('raw_snippet', '')}",
              it_c.get("url", ""),
              "",
              is_target=bool(it_c.get("is_custom_target", 0)),
          ):
            continue
          it_c["telegram_sent"] = 1
          if it_c["url"] not in merged_arch:
            merged_arch[it_c["url"]] = it_c
      if merged_arch:
        sorted_merged = sorted(
            merged_arch.values(),
            key=lambda x: float(x.get("pub_timestamp", 0)),
            reverse=True,
        )[:2500]
        for arch_p in (ARCHIVE_JSON_FILE, PERSISTENT_HOME_ARCHIVE_JSON):
          try:
            with open(arch_p, "w", encoding="utf-8") as f:
              json.dump(sorted_merged, f, ensure_ascii=False, indent=2)
          except Exception:
            pass

    if local_ledger:
      save_telegram_sent_ledger(local_ledger)

  return True


def _push_state_to_telegram_cloud_sync():
  """رفع وتحديث نسخة الأرشيف وقاعدة البيانات وسجل تلغرام على سحابة تلغرام في نفس الرسالة المثبتة بصمت دون إرسال رسائل جديدة."""
  if not _CLOUD_SYNC_LOCK.acquire(blocking=False):
    return
  try:
    rt = get_shared_runtime()
    token, chat_id = _get_tg_credentials_fast()
    if not token or not chat_id:
      return

    lock = get_db_lock()
    with lock:
      articles_to_save = []
      if os.path.exists(ARCHIVE_JSON_FILE):
        try:
          with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
            data_a = json.load(f)
          if isinstance(data_a, list):
            articles_to_save = data_a[:2000]
        except Exception:
          pass
      ledger_set = load_telegram_sent_ledger()
      for a_it in articles_to_save:
        if isinstance(a_it, dict):
          ledger_set.update(
              compute_article_dedup_keys(a_it.get("title", ""), a_it.get("url", ""))
          )
      targets_to_save = load_custom_targets()

    if not articles_to_save and not ledger_set:
      return

    creds_to_save = {}
    if os.path.exists(CREDENTIALS_FILE):
      try:
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
          creds_to_save = json.load(f) or {}
      except Exception:
        pass
    payload = {
        "updated_at": time.time(),
        "articles": articles_to_save,
        "telegram_ledger": sorted(list(ledger_set))[-8000:],
        "custom_targets": targets_to_save,
        "platform_keyword_trackers": load_platform_keyword_trackers(),
        "credentials": creds_to_save,
    }
    raw_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    gz_bytes = gzip.compress(raw_bytes)

    msg_id = int(rt.get("cloud_backup_msg_id") or 0)
    if not msg_id:
      try:
        r_desc = requests.get(
            f"https://api.telegram.org/bot{token}/getMyDescription", timeout=5
        )
        if r_desc.status_code == 200:
          desc_txt = r_desc.json().get("result", {}).get("description", "")
          m_sync = re.search(r"\[CLOUD_STATE:(\d+):([A-Za-z0-9_-]+)\]", desc_txt)
          if m_sync:
            msg_id = int(m_sync.group(1))
      except Exception:
        pass

    if not msg_id:
      try:
        r_chat = requests.post(
            f"https://api.telegram.org/bot{token}/getChat",
            json={"chat_id": chat_id},
            timeout=5,
        )
        if r_chat.status_code == 200:
          pinned = r_chat.json().get("result", {}).get("pinned_message", {})
          if isinstance(pinned, dict) and pinned.get("document"):
            msg_id = int(pinned.get("message_id") or 0)
      except Exception:
        pass

    new_file_id = ""
    caption_txt = f"🗄️ [CLOUD_SYNC_STATE] النسخة السحابية التلقائية لمنصة المرصد القضائي ({len(articles_to_save)} خبر محفوظ)"

    # أ) إذا كانت رسالة السحابة المثبتة موجودة، نقوم بتحديث ملفها بصمت في مكانه عبر editMessageMedia دون إرسال أي رسالة جديدة
    if msg_id > 0:
      try:
        media_spec = json.dumps({
            "type": "document",
            "media": "attach://state_file",
            "caption": caption_txt,
        })
        r_edit = requests.post(
            f"https://api.telegram.org/bot{token}/editMessageMedia",
            data={"chat_id": chat_id, "message_id": msg_id, "media": media_spec},
            files={"state_file": ("justice_hub_cloud_state.json.gz", gz_bytes, "application/gzip")},
            timeout=12,
        )
        if r_edit.status_code == 200:
          res_doc = r_edit.json().get("result", {}).get("document", {})
          new_file_id = str(res_doc.get("file_id") or "").strip()
      except Exception:
        pass

    # ب) إذا لم تكن هناك رسالة سحابية سابقة، ننشئها مرة واحدة فقط بصمت ونثبتها
    if not new_file_id:
      try:
        r_send = requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={
                "chat_id": chat_id,
                "caption": caption_txt,
                "disable_notification": True,
            },
            files={"document": ("justice_hub_cloud_state.json.gz", gz_bytes, "application/gzip")},
            timeout=12,
        )
        if r_send.status_code == 200:
          res_msg = r_send.json().get("result", {})
          msg_id = int(res_msg.get("message_id") or 0)
          new_file_id = str(res_msg.get("document", {}).get("file_id") or "").strip()
          if msg_id > 0:
            try:
              requests.post(
                  f"https://api.telegram.org/bot{token}/pinChatMessage",
                  json={
                      "chat_id": chat_id,
                      "message_id": msg_id,
                      "disable_notification": True,
                  },
                  timeout=5,
              )
            except Exception:
              pass
      except Exception:
        pass

    if msg_id > 0 and new_file_id:
      rt["cloud_backup_msg_id"] = msg_id
      rt["cloud_backup_file_id"] = new_file_id
      rt["last_cloud_push_ts"] = time.time()
      try:
        desc_payload = (
            "⚖️ المرصد القضائي — نظام الرصد القضائي والأرشيف السحابي الدائم\n"
            f"[CLOUD_STATE:{msg_id}:{new_file_id}]"
        )
        requests.post(
            f"https://api.telegram.org/bot{token}/setMyDescription",
            json={"description": desc_payload[:510]},
            timeout=5,
        )
      except Exception:
        pass
  finally:
    try:
      _CLOUD_SYNC_LOCK.release()
    except Exception:
      pass


def trigger_cloud_state_backup(async_mode: bool = True):
  """جدولة حفظ الحالة في سحابة تلغرام في الخلفية أو بشكل متزامن عند الإغلاق."""
  if not async_mode or os.environ.get("CRON_MODE") == "1":
    _push_state_to_telegram_cloud_sync()
  else:
    threading.Thread(
        target=_push_state_to_telegram_cloud_sync,
        daemon=True,
        name="TelegramCloudStateSync",
    ).start()


def init_db(force: bool = False):
  """تهيئة فائقة السرعة لقاعدة البيانات تعمل مرة واحدة فقط عند إقلاع الخادم وتنفذ المزامنة السحابية في الخلفية دون تجميد الأزرار."""
  rt = get_shared_runtime()
  if not force and rt.get("db_initialized_version") == DAEMON_CODE_VERSION:
    return

  lock = get_db_lock()
  with lock:
    if (
        not force
        and rt.get("db_initialized_version") == DAEMON_CODE_VERSION
        and os.path.exists(DB_FILE)
    ):
      return

    if not os.path.exists(DB_FILE):
      for candidate_src in (PERSISTENT_HOME_DB, REPO_DB_FILE):
        if os.path.exists(candidate_src) and os.path.getsize(candidate_src) > 0:
          try:
            shutil.copyfile(candidate_src, DB_FILE)
            break
          except Exception:
            pass

    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      c = conn.cursor()
      c.execute("SELECT COUNT(*) FROM articles")
      row_count = int((c.fetchone() or [0])[0])
      conn.close()
    except sqlite3.DatabaseError:
      row_count = 0
      try:
        if os.path.exists(DB_FILE):
          os.remove(DB_FILE)
        conn = _open_sqlite_conn()
        _ensure_schema_on_conn(conn)
        conn.close()
      except Exception:
        pass
    except Exception:
      row_count = 0

    if row_count == 0:
      _merge_external_sqlite_into_runtime(REPO_DB_FILE)
      _merge_external_sqlite_into_runtime(PERSISTENT_HOME_DB)
      restore_db_from_json_if_needed()

    rt["db_initialized_version"] = DAEMON_CODE_VERSION
    invalidate_articles_cache()

  def _deferred_startup_maintenance():
    try:
      restored_cloud = restore_state_from_telegram_cloud()
      _merge_external_sqlite_into_runtime(REPO_DB_FILE)
      _merge_external_sqlite_into_runtime(PERSISTENT_HOME_DB)
      if restored_cloud:
        restore_db_from_json_if_needed()
      purge_invalid_articles_from_db()
      deduplicate_and_seed_telegram_ledger()
      sync_db_to_json()
      invalidate_articles_cache()
    except Exception:
      pass

  if os.environ.get("CRON_MODE") == "1":
    _deferred_startup_maintenance()
  else:
    threading.Thread(
        target=_deferred_startup_maintenance,
        daemon=True,
        name="DeferredStartupMaintenance",
    ).start()


def sync_db_to_json(extra_items: list = None):
  lock = get_db_lock()
  with lock:
    merged_by_url = {}
    for json_src in (PERSISTENT_HOME_ARCHIVE_JSON, ARCHIVE_JSON_FILE):
      if os.path.exists(json_src):
        try:
          with open(json_src, "r", encoding="utf-8") as f:
            existing_json = json.load(f)
          if isinstance(existing_json, list):
            for item in existing_json:
              if not isinstance(item, dict) or not item.get("url"):
                continue
              if not is_strictly_judicial_and_clean(
                  item.get("title", ""),
                  f"{item.get('summary', '')} {item.get('raw_snippet', '')}",
                  item.get("url", ""),
                  "",
                  is_target=bool(item.get("is_custom_target", 0)),
              ):
                continue
              merged_by_url[item["url"]] = item
        except Exception:
          pass

    if extra_items:
      for item in extra_items:
        if isinstance(item, dict) and item.get("url"):
          clean_copy = {
              k: v for k, v in item.items() if not str(k).startswith("_")
          }
          merged_by_url[clean_copy["url"]] = clean_copy

    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute(
          "SELECT title, summary, source_name, platform, url, pub_date, "
          "pub_timestamp, sentiment, category, relevance_score, "
          "is_custom_target, raw_snippet, image_url, created_at "
          "FROM articles ORDER BY pub_timestamp DESC LIMIT 2500"
      )
      for r in c.fetchall():
        d = dict(r)
        if d.get("url"):
          merged_by_url[d["url"]] = d
      conn.close()
    except Exception:
      pass

    if merged_by_url:
      sorted_rows = sorted(
          merged_by_url.values(),
          key=lambda x: float(x.get("pub_timestamp", 0)),
          reverse=True,
      )[:2500]
      for target_json in (ARCHIVE_JSON_FILE, PERSISTENT_HOME_ARCHIVE_JSON):
        try:
          tmp_file = f"{target_json}.tmp"
          with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(sorted_rows, f, ensure_ascii=False, indent=2)
          os.replace(tmp_file, target_json)
        except Exception:
          pass

    if os.path.exists(DB_FILE):
      for target_db in (REPO_DB_FILE, PERSISTENT_HOME_DB):
        try:
          shutil.copyfile(DB_FILE, target_db)
        except Exception:
          pass


def restore_db_from_json_if_needed():
  """استعادة ودمج جميع عناصر الأرشيف من ملفات JSON الدائمة داخل SQLite في كل تشغيل (حتى لو لم تكن القاعدة فارغة) مع الحفاظ على تواريخ الرصد الأصلية."""
  lock = get_db_lock()
  with lock:
    all_json_items = []
    for arch_file in (PERSISTENT_HOME_ARCHIVE_JSON, ARCHIVE_JSON_FILE):
      if os.path.exists(arch_file):
        try:
          with open(arch_file, "r", encoding="utf-8") as f:
            items = json.load(f)
          if isinstance(items, list):
            all_json_items.extend(items)
        except Exception:
          pass

    if not all_json_items:
      return

    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      c = conn.cursor()
      for item in all_json_items:
        if not isinstance(item, dict):
          continue
        try:
          t_clean = clean_display_text(item.get("title", ""))
          s_clean = clean_display_text(item.get("summary", ""))
          plat = item.get("platform", "الصحف")
          src = clean_display_text(item.get("source_name", "") or plat)
          raw_s = clean_full_article_text(item.get("raw_snippet", ""))
          u_str = item.get("url", "")
          is_tgt = int(item.get("is_custom_target", 0))
          if not t_clean or not u_str:
            continue
          if not is_strictly_judicial_and_clean(t_clean, f"{s_clean} {raw_s}", u_str, "", is_target=bool(is_tgt)):
            continue

          if is_summary_just_title(t_clean, s_clean):
            s_clean = build_extractive_arabic_summary(
                t_clean, raw_s, plat, src
            )
          pub_ts = float(item.get("pub_timestamp") or (time.time() - 90000))
          # الحفاظ الصارم على وقت الرصد الأصلي، وإذا لم يكن مسجلاً نعتمد وقت النشر (pub_ts) وليس time.time() حتى لا يختفي الأرشيف!
          orig_created = float(item.get("created_at") or 0)
          if orig_created <= 0:
            orig_created = pub_ts
          pub_dt = item.get("pub_date", "")
          if not pub_dt:
            pub_dt = datetime.fromtimestamp(
                pub_ts, tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M")
          img_u = item.get("image_url") or extract_thumbnail_for_item(
              u_str, "", plat
          )

          c.execute(
              """
              INSERT OR IGNORE INTO articles (
                  title, summary, source_name, platform, url,
                  pub_date, pub_timestamp, sentiment, category,
                  relevance_score, is_custom_target, raw_snippet,
                  image_url, created_at, telegram_sent
              ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
              """,
              (
                  t_clean,
                  s_clean,
                  src,
                  plat,
                  u_str,
                  pub_dt,
                  pub_ts,
                  item.get("sentiment", "محايد"),
                  item.get("category", "شؤون قضائية"),
                  int(item.get("relevance_score", 85)),
                  is_tgt,
                  raw_s,
                  img_u,
                  orig_created,
                  1,
              ),
          )
        except Exception:
          continue
      conn.commit()
      conn.close()
    except Exception:
      pass


def fetch_articles_from_db(force_refresh: bool = False):
  """جلب الأخبار المرصودة مع تخزين مؤقت فوري في الذاكرة (RAM Cache) لضمان استجابة الواجهة والأزرار في أجزاء من الألف من الثانية."""
  rt = get_shared_runtime()
  current_targets = load_custom_targets()
  targets_sig = tuple(sorted((t.get("url", ""), t.get("keyword", "")) for t in current_targets))
  cache_sig = (rt.get("db_version_counter", 1), targets_sig)
  if not force_refresh and rt.get("cached_articles_sig") == cache_sig and isinstance(rt.get("cached_articles_list"), list):
    return [dict(x) for x in rt["cached_articles_list"]]

  lock = get_db_lock()
  now_ts = time.time()
  with lock:
    db_rows = []
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute(
          "SELECT * FROM articles ORDER BY pub_timestamp DESC, id DESC LIMIT 2500"
      )
      for r in c.fetchall():
        d = dict(r)
        t_str = d.get("title", "")
        snip_str = f"{d.get('summary', '')} {d.get('raw_snippet', '')}"
        u_str = d.get("url", "")
        if _has_inappropriate_terms(t_str, snip_str, u_str):
          continue
        is_tgt = bool(d.get("is_custom_target", 0))
        if not is_strictly_judicial_and_clean(
            t_str, snip_str, u_str, "", is_target=is_tgt
        ):
          continue
        if is_tgt and not belongs_to_any_custom_target(d, current_targets):
          continue
        d["source_name"] = format_precise_source_with_domain(
            d.get("source_name") or d.get("platform") or "الصحف",
            u_str,
            d.get("platform") or "الصحف",
            title_hint=t_str,
        )
        d["image_url"] = clean_and_validate_image_url(
            d.get("image_url") or "", u_str, d.get("platform") or "الصحف"
        )
        db_rows.append(d)
      conn.close()
    except Exception:
      pass

    if db_rows:
      unique_rows = []
      seen_display_keys = set()
      for r in db_rows:
        dk = compute_article_dedup_keys(r.get("title", ""), r.get("url", ""))
        plat_sc = r.get("platform") or "الصحف"
        tgt_sc = int(r.get("is_custom_target") or 0)
        scoped_dk = {f"{plat_sc}::{tgt_sc}::{k}" for k in dk}
        if scoped_dk & seen_display_keys:
          continue
        seen_display_keys.update(scoped_dk)
        unique_rows.append(r)
      rt["cached_articles_list"] = [dict(x) for x in unique_rows]
      rt["cached_articles_sig"] = cache_sig
      return unique_rows

    for arch_file in (ARCHIVE_JSON_FILE, PERSISTENT_HOME_ARCHIVE_JSON):
      if os.path.exists(arch_file):
        try:
          with open(arch_file, "r", encoding="utf-8") as f:
            data = json.load(f)
          if isinstance(data, list) and data:
            valid_data = [
                d for d in data
                if isinstance(d, dict)
                and not _has_inappropriate_terms(
                    d.get("title", ""),
                    f"{d.get('summary', '')} {d.get('raw_snippet', '')}",
                    d.get("url", ""),
                )
            ]
            sorted_arch = sorted(
                valid_data,
                key=lambda x: float(x.get("pub_timestamp", 0)),
                reverse=True,
            )
            rt["cached_articles_list"] = [dict(x) for x in sorted_arch]
            rt["cached_articles_sig"] = cache_sig
            return sorted_arch
        except Exception:
          pass
    rt["cached_articles_list"] = []
    rt["cached_articles_sig"] = cache_sig
    return []


# =====================================================================
# 6. إدارة الإعدادات والروابط المخصصة وحالة الرصد الدوري وفترة البحث
# =====================================================================
def load_credentials():
  rt = get_shared_runtime()
  cfg = {
      "gemini_api_key": "",
      "telegram_bot_token": DEFAULT_TG_TOKEN,
      "telegram_chat_id": DEFAULT_TG_CHAT_ID,
      "keywords_input": "",
      "search_period": "آخر 7 أيام",
      "auto_monitor": True,
      "monitor_interval": "كل 15 دقيقة",
  }
  if isinstance(rt.get("_cached_credentials_disk"), dict):
    cfg.update(rt["_cached_credentials_disk"])
  elif os.path.exists(CREDENTIALS_FILE):
    try:
      with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        saved = json.load(f)
      if isinstance(saved, dict):
        rt["_cached_credentials_disk"] = dict(saved)
        cfg.update(saved)
    except Exception:
      pass

  try:
    if st is not None and hasattr(st, "secrets"):
      for k_sec in ("GEMINI_API_KEY", "gemini_api_key", "GOOGLE_API_KEY", "google_api_key", "GEMINI_KEY", "API_KEY"):
        if k_sec in st.secrets and st.secrets[k_sec]:
          cfg["gemini_api_key"] = str(st.secrets[k_sec]).strip()
          break
      if not cfg.get("gemini_api_key"):
        for sec_val in st.secrets.values():
          if isinstance(sec_val, dict):
            for k_sec in ("GEMINI_API_KEY", "gemini_api_key", "GOOGLE_API_KEY", "google_api_key", "api_key"):
              if sec_val.get(k_sec):
                cfg["gemini_api_key"] = str(sec_val[k_sec]).strip()
                break
      if (
          "TELEGRAM_BOT_TOKEN" in st.secrets
          and st.secrets["TELEGRAM_BOT_TOKEN"]
      ):
        cfg["telegram_bot_token"] = str(
            st.secrets["TELEGRAM_BOT_TOKEN"]
        ).strip()
      if "TELEGRAM_CHAT_ID" in st.secrets and st.secrets["TELEGRAM_CHAT_ID"]:
        cfg["telegram_chat_id"] = str(st.secrets["TELEGRAM_CHAT_ID"]).strip()
  except Exception:
    pass

  for env_k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY", "API_KEY"):
    env_gemini = os.environ.get(env_k, "").strip()
    if env_gemini:
      cfg["gemini_api_key"] = env_gemini
      break

  try:
    if st is not None and st.session_state.get("gemini_api_key_live"):
      cfg["gemini_api_key"] = str(st.session_state["gemini_api_key_live"]).strip()
  except Exception:
    pass
  env_tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
  if env_tg_token:
    cfg["telegram_bot_token"] = env_tg_token
  env_tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
  if env_tg_chat:
    cfg["telegram_chat_id"] = env_tg_chat

  if not cfg.get("telegram_bot_token"):
    cfg["telegram_bot_token"] = DEFAULT_TG_TOKEN
  if not cfg.get("telegram_chat_id"):
    cfg["telegram_chat_id"] = DEFAULT_TG_CHAT_ID
  if cfg.get("monitor_interval") not in INTERVAL_MAP:
    cfg["monitor_interval"] = "كل 15 دقيقة"
  if cfg.get("search_period") not in SEARCH_PERIOD_MAP:
    cfg["search_period"] = "آخر 7 أيام"
  return cfg


def save_credentials(cfg):
  try:
    get_shared_runtime()["_cached_credentials_disk"] = dict(cfg)
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
      json.dump(cfg, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


def save_custom_targets(targets):
  try:
    cleaned = [
        {"url": t.get("url", "").strip(), "keyword": t.get("keyword", "").strip()}
        for t in targets
        if t.get("url", "").strip()
    ]
    get_shared_runtime()["_cached_custom_targets"] = [dict(x) for x in cleaned]
    with open(CUSTOM_TARGETS_FILE, "w", encoding="utf-8") as f:
      json.dump(cleaned, f, ensure_ascii=False, indent=2)
    invalidate_articles_cache()
    threading.Thread(target=purge_invalid_articles_from_db, daemon=True).start()
    trigger_cloud_state_backup(async_mode=True)
  except Exception:
    pass


def load_platform_keyword_trackers() -> list:
  """تحميل قائمة قواعد تتبع المنصات بالكلمات المفتاحية مع تخزين مؤقت في الذاكرة لسرعة الاستجابة."""
  rt = get_shared_runtime()
  if isinstance(rt.get("_cached_kw_trackers"), list):
    return [dict(x) for x in rt["_cached_kw_trackers"]]
  cleaned = []
  if os.path.exists(PLATFORM_KEYWORD_TRACKERS_FILE):
    try:
      with open(PLATFORM_KEYWORD_TRACKERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
      if isinstance(data, list):
        seen = set()
        for item in data:
          if isinstance(item, dict):
            plat = str(item.get("platform") or "فيسبوك").strip()
            kw = str(item.get("keyword") or "").strip()
            sig = f"{plat}::{kw.lower()}"
            if kw and sig not in seen:
              seen.add(sig)
              cleaned.append({"platform": plat, "keyword": kw})
    except Exception:
      pass
  rt["_cached_kw_trackers"] = [dict(x) for x in cleaned]
  return cleaned


def save_platform_keyword_trackers(trackers: list):
  """حفظ قائمة قواعد تتبع المنصات بالكلمات المفتاحية ومزامنتها سحابياً."""
  try:
    cleaned = []
    seen = set()
    for t in trackers:
      if isinstance(t, dict):
        plat = str(t.get("platform") or "فيسبوك").strip()
        kw = str(t.get("keyword") or "").strip()
        sig = f"{plat}::{kw.lower()}"
        if kw and sig not in seen:
          seen.add(sig)
          cleaned.append({"platform": plat, "keyword": kw})
    get_shared_runtime()["_cached_kw_trackers"] = [dict(x) for x in cleaned]
    with open(PLATFORM_KEYWORD_TRACKERS_FILE, "w", encoding="utf-8") as f:
      json.dump(cleaned, f, ensure_ascii=False, indent=2)
    trigger_cloud_state_backup(async_mode=True)
  except Exception:
    pass


def load_monitor_state():
  rt = get_shared_runtime()
  if isinstance(rt.get("_cached_monitor_state"), dict):
    return dict(rt["_cached_monitor_state"])
  state = {"last_auto_run": 0.0, "last_auto_added": 0, "total_auto_cycles": 0}
  if os.path.exists(MONITOR_STATE_FILE):
    try:
      with open(MONITOR_STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
      if isinstance(data, dict):
        state.update(data)
    except Exception:
      pass
  rt["_cached_monitor_state"] = dict(state)
  return state


def save_monitor_state(state):
  try:
    get_shared_runtime()["_cached_monitor_state"] = dict(state)
    with open(MONITOR_STATE_FILE, "w", encoding="utf-8") as f:
      json.dump(state, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


# =====================================================================
# 7. استخراج ومعالجة تواريخ النشر الحقيقية وتاريخ الرصد
# =====================================================================
_EASTERN_ARABIC_DIGITS_MAP = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)

_ARABIC_NUMBER_WORDS = {
    "واحد": 1,
    "واحدة": 1,
    "واحده": 1,
    "اثنين": 2,
    "اثنان": 2,
    "ثلاث": 3,
    "ثلاثة": 3,
    "ثلاثه": 3,
    "اربع": 4,
    "أربع": 4,
    "اربعة": 4,
    "أربعة": 4,
    "اربعه": 4,
    "خمس": 5,
    "خمسة": 5,
    "خمسه": 5,
    "ست": 6,
    "ستة": 6,
    "سته": 6,
    "سبع": 7,
    "سبعة": 7,
    "سبعه": 7,
    "ثمان": 8,
    "ثماني": 8,
    "ثمانية": 8,
    "ثمانيه": 8,
    "تسع": 9,
    "تسعة": 9,
    "تسعه": 9,
    "عشر": 10,
    "عشرة": 10,
    "عشره": 10,
}


def _normalize_date_input_text(raw_str: str) -> str:
  """تنظيف وتطبيع نصوص التواريخ بإزالة التشكيل والتنوين (مثل: شهرًا -> شهرا، يومًا -> يوما) وعلامات الاتجاه الخفية وتحويل الأرقام الهندية إلى أرقام قياسية."""
  if not raw_str:
    return ""
  s = html.unescape(str(raw_str)).strip()
  s = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]", "", s)
  s = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", s)
  s = s.translate(_EASTERN_ARABIC_DIGITS_MAP)
  s = re.sub(r"\s+", " ", s).strip()
  return s


def has_explicit_parseable_date(date_str: str) -> bool:
  """التحقق مما إذا كان النص يحتوي فعلياً على تاريخ حقيقي أو وقت نسبي قابل للتحليل (دون اللجوء للتوقيت الافتراضي)."""
  if not date_str or not str(date_str).strip():
    return False
  _, ts = parse_any_date(str(date_str).strip(), fallback_offset_sec=-1)
  return bool(ts > 0)


def extract_date_from_url_or_text(
    url: str,
    text_snippet: str = "",
    raw_date: str = "",
    fallback_offset_sec: int = 3600,
):
  now_ts = time.time()

  if raw_date and str(raw_date).strip():
    d_str, d_ts = parse_any_date(str(raw_date).strip(), fallback_offset_sec=-1)
    if d_ts > 0:
      return d_str, d_ts

  if url:
    m_x = re.search(r"(?:x\.com|twitter\.com)/[^/]+/status/(\d{15,20})", url)
    if m_x:
      try:
        snowflake_id = int(m_x.group(1))
        tweet_ts = ((snowflake_id >> 22) + 1288834974657) / 1000.0
        if 1288834974 < tweet_ts <= now_ts + 3600:
          tweet_ts = min(tweet_ts, now_ts)
          return (
              datetime.fromtimestamp(tweet_ts, tz=timezone.utc).strftime(
                  "%Y-%m-%d %H:%M"
              ),
              tweet_ts,
          )
      except Exception:
        pass

    m_tt = re.search(r"tiktok\.com/.*/video/(\d{15,22})", url)
    if m_tt:
      try:
        tt_id = int(m_tt.group(1))
        tt_ts = float(tt_id >> 32)
        if 1450000000 < tt_ts <= now_ts + 3600:
          tt_ts = min(tt_ts, now_ts)
          return (
              datetime.fromtimestamp(tt_ts, tz=timezone.utc).strftime(
                  "%Y-%m-%d %H:%M"
              ),
              tt_ts,
          )
      except Exception:
        pass

    m_url_date = re.search(r"/(20\d{2})/(\d{1,2})/(\d{1,2})(?:/|$|-)", url)
    if m_url_date:
      try:
        dt = datetime(
            int(m_url_date.group(1)),
            int(m_url_date.group(2)),
            int(m_url_date.group(3)),
            12,
            0,
            tzinfo=timezone.utc,
        )
        ts = min(dt.timestamp(), now_ts)
        return dt.strftime("%Y-%m-%d %H:%M"), ts
      except Exception:
        pass

  if text_snippet:
    d_str, d_ts = parse_any_date(
        text_snippet[:300], fallback_offset_sec=-1
    )
    if d_ts > 0:
      return d_str, d_ts

  return parse_any_date("", fallback_offset_sec=fallback_offset_sec)


def parse_any_date(date_str: str, fallback_offset_sec: int = 3600):
  now_ts = time.time()
  if not date_str or not str(date_str).strip():
    if fallback_offset_sec < 0:
      return "", 0.0
    ts = now_ts - fallback_offset_sec
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M"), ts

  raw_orig = str(date_str).strip()
  raw = _normalize_date_input_text(raw_orig)
  if not raw:
    if fallback_offset_sec < 0:
      return "", 0.0
    ts = now_ts - fallback_offset_sec
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M"), ts

  # 1) طابع زمني رقمي مباشر (مثل data-utime في فيسبوك)
  if raw.isdigit() and len(raw) >= 9:
    try:
      ts = min(float(raw), now_ts)
      return (
          datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
              "%Y-%m-%d %H:%M"
          ),
          ts,
      )
    except Exception:
      pass

  # 2) صيغ RFC 2822 القياسية لـ RSS
  try:
    dt = parsedate_to_datetime(raw_orig)
    if dt.tzinfo is None:
      dt = dt.replace(tzinfo=timezone.utc)
    ts = min(dt.timestamp(), now_ts)
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        ts,
    )
  except Exception:
    pass

  # 3) صيغ ISO 8601 (مثل YouTube uploadDate / publishDate: 2026-10-13T18:30:00+00:00 أو 2024-05-12)
  try:
    iso_clean = raw.replace("Z", "+00:00")
    if re.match(r"^20\d{2}-\d{2}-\d{2}$", iso_clean):
      dt = datetime(
          int(iso_clean[0:4]),
          int(iso_clean[5:7]),
          int(iso_clean[8:10]),
          12,
          0,
          tzinfo=timezone.utc,
      )
    else:
      dt = datetime.fromisoformat(iso_clean)
      if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts = min(dt.timestamp(), now_ts)
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        ts,
    )
  except Exception:
    pass

  rel_lower = raw.lower()

  # 4) التواريخ الصريحة بالشهور العربية (مثل: 17 يوليوز 2026 أو 15 اكتوبر، 2023)
  for ar_m, m_idx in ARABIC_MONTHS.items():
    ar_m_norm = _normalize_date_input_text(ar_m)
    m_ar1 = re.search(rf"(\d{{1,2}})\s+{re.escape(ar_m_norm)}\s*[،,]?\s*(20\d{{2}})", raw)
    m_ar2 = re.search(rf"{re.escape(ar_m_norm)}\s+(\d{{1,2}})\s*[،,]?\s*(20\d{{2}})", raw)
    m_ar = m_ar1 or m_ar2
    if m_ar:
      try:
        dt = datetime(
            int(m_ar.group(2)),
            m_idx,
            int(m_ar.group(1)),
            12,
            0,
            tzinfo=timezone.utc,
        )
        ts = min(dt.timestamp(), now_ts)
        return dt.strftime("%Y-%m-%d %H:%M"), ts
      except Exception:
        pass

  # 5) التواريخ الصريحة بالشهور الإنجليزية/الفرنسية (مثل: Oct 2, 2026 أو 15 févr. 2024)
  for en_m, m_idx in ENGLISH_MONTHS.items():
    m_en1 = re.search(
        rf"\b{re.escape(en_m)}[a-z\.]*\s+(\d{{1,2}}),?\s+(20\d{{2}})", rel_lower
    )
    m_en2 = re.search(
        rf"\b(\d{{1,2}})\s+{re.escape(en_m)}[a-z\.]*,?\s+(20\d{{2}})", rel_lower
    )
    m_en = m_en1 or m_en2
    if m_en:
      try:
        dt = datetime(
            int(m_en.group(2)),
            m_idx,
            int(m_en.group(1)),
            12,
            0,
            tzinfo=timezone.utc,
        )
        ts = min(dt.timestamp(), now_ts)
        return dt.strftime("%Y-%m-%d %H:%M"), ts
      except Exception:
        pass

  # 6) التواريخ الرقمية الصريحة YYYY-MM-DD أو DD-MM-YYYY أو DD/MM/YYYY
  m_ymd = re.search(r"\b(20\d{2})[-/\.](0?[1-9]|1[0-2])[-/\.](0?[1-9]|[12]\d|3[01])\b", raw)
  if m_ymd:
    try:
      dt = datetime(
          int(m_ymd.group(1)),
          int(m_ymd.group(2)),
          int(m_ymd.group(3)),
          12,
          0,
          tzinfo=timezone.utc,
      )
      ts = min(dt.timestamp(), now_ts)
      return dt.strftime("%Y-%m-%d %H:%M"), ts
    except Exception:
      pass

  m_dmy = re.search(r"\b(0?[1-9]|[12]\d|3[01])[-/\.](0?[1-9]|1[0-2])[-/\.](20\d{2})\b", raw)
  if m_dmy:
    try:
      dt = datetime(
          int(m_dmy.group(3)),
          int(m_dmy.group(2)),
          int(m_dmy.group(1)),
          12,
          0,
          tzinfo=timezone.utc,
      )
      ts = min(dt.timestamp(), now_ts)
      return dt.strftime("%Y-%m-%d %H:%M"), ts
    except Exception:
      pass

  # 7) صيغ الوقت النسبي الفرنسية الصريحة (مثل: il y a 2 jours / il y a un an / il y a 6 mois / il y a une semaine)
  m_fr_rel = re.search(
      r"il y a\s+(?:environ\s+)?(\d+|un|une)\s*(seconde|secondes|minute|minutes|heure|heures|jour|jours|semaine|semaines|mois|an|ans|annee|annees|année|années)\b",
      rel_lower,
  )
  if m_fr_rel:
    num_tok_fr = m_fr_rel.group(1)
    n_fr = 1 if num_tok_fr in ("un", "une") else int(num_tok_fr)
    u_fr = m_fr_rel.group(2)
    if u_fr.startswith("sec"):
      ts = now_ts - n_fr
    elif u_fr.startswith("min"):
      ts = now_ts - n_fr * 60
    elif u_fr.startswith("heur"):
      ts = now_ts - n_fr * 3600
    elif u_fr.startswith("jour"):
      ts = now_ts - n_fr * 86400
    elif u_fr.startswith("sem"):
      ts = now_ts - n_fr * 7 * 86400
    elif u_fr.startswith("mois"):
      ts = now_ts - n_fr * 30 * 86400
    else:
      ts = now_ts - n_fr * 365 * 86400
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        ts,
    )

  if re.search(r"\b(yesterday|hier)\b", rel_lower):
    ts = now_ts - 86400
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        ts,
    )

  # 8) صيغ الوقت النسبي الإنجليزية الصريحة (مثل: 3 days ago / a year ago / an hour ago / Streamed 5 months ago)
  m_en_ago = re.search(
      r"(?:^|\b)(\d+|a|an)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|wk|wks|week|weeks|mo|mos|month|months|y|yr|yrs|year|years)\b(?:\s+ago)?",
      rel_lower,
  )
  if m_en_ago and (
      "ago" in rel_lower
      or "streamed" in rel_lower
      or "premiered" in rel_lower
      or "·" in rel_lower[:25]
      or len(raw) <= 28
  ):
    tok_en = m_en_ago.group(1)
    u = m_en_ago.group(2)
    # إذا كان الرمز a/an بدون كلمة ago فلا نقبله إلا مع وجود ago لمنع التباس الحرف a في النصوص العادية
    if tok_en in ("a", "an") and "ago" not in rel_lower:
      pass
    else:
      n = 1 if tok_en in ("a", "an") else int(tok_en)
      if u.startswith("s"):
        ts = now_ts - n
      elif u.startswith("mo"):
        ts = now_ts - n * 30 * 86400
      elif u.startswith("m"):
        ts = now_ts - n * 60
      elif u.startswith("h"):
        ts = now_ts - n * 3600
      elif u.startswith("d"):
        ts = now_ts - n * 86400
      elif u.startswith("w"):
        ts = now_ts - n * 7 * 86400
      else:
        ts = now_ts - n * 365 * 86400
      return (
          datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
          ts,
      )

  # 9) صيغ الوقت النسبي العربية الصريحة (بما فيها التنوين مثل: قبل 11 شهرًا / قبل 15 يومًا / قبل 12 عامًا / قبل سنتين / قبل شهرين)
  ar_units_pat = (
      r"(ثواني|ثوان|ثانية|ثانيه|لحظات|لحظة|لحظه|الآن|الان|"
      r"دقيقتين|دقيقتان|دقائق|دقيقة|دقيقه|"
      r"ساعتين|ساعتان|ساعات|ساعة|ساعه|"
      r"يومين|يومان|يوما|أيام|ايام|يوم|أمس|امس|البارحة|البارحه|"
      r"أسبوعين|اسبوعين|أسبوعان|اسبوعان|أسبوعا|اسبوعا|أسابيع|اسابيع|أسبوع|اسبوع|"
      r"شهرين|شهران|شهرا|أشهر|اشهر|شهور|شهر|"
      r"سنتين|سنتان|سنوات|سنة|سنه|عامين|عامان|أعوام|اعوام|عاما|عام)"
  )
  ar_num_words_pat = "|".join(_ARABIC_NUMBER_WORDS.keys())
  m_ar_rel = re.search(
      rf"(?:منذ|قبل)\s*(?:حوالي\s*|اكثر من\s*|أكثر من\s*|اقل من\s*|أقل من\s*|قرابة\s*)?(?:(\d+|{ar_num_words_pat})\s*)?{ar_units_pat}\b",
      rel_lower,
  )
  if not m_ar_rel and len(raw) <= 32:
    m_ar_rel = re.search(
        rf"^(?:تم البث\s+|بث مباشر\s+|العرض الاول\s+|العرض الأول\s+)?(?:منذ\s+|قبل\s+)?(?:(\d+|{ar_num_words_pat})\s*)?{ar_units_pat}\b",
        rel_lower,
    )
  if m_ar_rel:
    num_tok = (m_ar_rel.group(1) or "").strip()
    if num_tok.isdigit():
      num = int(num_tok)
    elif num_tok in _ARABIC_NUMBER_WORDS:
      num = _ARABIC_NUMBER_WORDS[num_tok]
    else:
      num = 1
    unit_ar = m_ar_rel.group(2)
    if unit_ar in ("ثانية", "ثانيه", "ثواني", "ثوان", "لحظة", "لحظه", "لحظات", "الآن", "الان"):
      ts = now_ts - 60
    elif unit_ar in ("دقيقة", "دقيقه", "دقائق", "دقيقتين", "دقيقتان"):
      if unit_ar in ("دقيقتين", "دقيقتان"):
        num = 2
      ts = now_ts - (num * 60)
    elif unit_ar in ("ساعة", "ساعه", "ساعات", "ساعتين", "ساعتان"):
      if unit_ar in ("ساعتين", "ساعتان"):
        num = 2
      ts = now_ts - (num * 3600)
    elif unit_ar in ("يوم", "يوما", "أيام", "ايام", "يومين", "يومان", "أمس", "امس", "البارحة", "البارحه"):
      if unit_ar in ("يومين", "يومان"):
        num = 2
      elif unit_ar in ("أمس", "امس", "البارحة", "البارحه"):
        num = 1
      ts = now_ts - (num * 86400)
    elif unit_ar in ("أسبوع", "اسبوع", "أسبوعا", "اسبوعا", "أسابيع", "اسابيع", "أسبوعين", "اسبوعين", "أسبوعان", "اسبوعان"):
      if unit_ar in ("أسبوعين", "اسبوعين", "أسبوعان", "اسبوعان"):
        num = 2
      ts = now_ts - (num * 7 * 86400)
    elif unit_ar in ("شهر", "شهرا", "أشهر", "اشهر", "شهور", "شهرين", "شهران"):
      if unit_ar in ("شهرين", "شهران"):
        num = 2
      ts = now_ts - (num * 30 * 86400)
    else:
      if unit_ar in ("سنتين", "سنتان", "عامين", "عامان"):
        num = 2
      ts = now_ts - (num * 365 * 86400)
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        ts,
    )

  if fallback_offset_sec < 0:
    return "", 0.0
  ts = now_ts - fallback_offset_sec
  dt_fmt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
  return dt_fmt, ts


def format_relative_arabic(pub_ts: float) -> str:
  diff = max(0, int(time.time() - float(pub_ts or 0)))
  if diff < 90:
    return "منذ لحظات"
  if diff < 3600:
    return f"منذ {diff // 60} دقيقة"
  if diff < 86400:
    return f"منذ {diff // 3600} ساعة"
  days = diff // 86400
  if days < 30:
    return f"منذ {days} يوم"
  if days < 365:
    return f"منذ {max(1, days // 30)} شهر"
  return f"منذ {max(1, days // 365)} سنة"


# =====================================================================
# 8. محركات الرصد الذكي المفلترة بدقة (الصحف، فيسبوك، إكس، يوتيوب، أخرى)
# =====================================================================
def get_period_config(period_label: str = ""):
  return SEARCH_PERIOD_MAP.get(
      period_label, SEARCH_PERIOD_MAP["آخر 7 أيام"]
  )


def build_search_queries(keywords_input: str):
  custom_kws = [
      k.strip()
      for k in re.split(r"[,،\n]+", str(keywords_input or ""))
      if k.strip()
  ]
  if custom_kws:
    queries = []
    for kw in custom_kws:
      kw_clean = kw.strip('"\' ')
      queries.append(f'"{kw_clean}"')
      if "المغرب" not in kw_clean:
        queries.append(f'"{kw_clean}" المغرب')
        queries.append(f'{kw_clean} المغرب')
        queries.append(f'"{kw_clean}" القضاء المغرب')
      else:
        queries.append(kw_clean)
    return queries
  return list(DEFAULT_JUDICIAL_QUERIES)


def clean_html_text(raw_html: str) -> str:
  return clean_display_text(raw_html)


def decode_js_escaped_text(raw_str: str) -> str:
  if not raw_str:
    return ""
  s = re.sub(
      r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), str(raw_str)
  )
  s = s.replace('\\"', '"').replace("\\/", "/").replace("\\n", " ")
  return clean_display_text(s)


def parse_rss_xml(
    xml_bytes: bytes,
    default_platform: str,
    default_source: str = "",
    fallback_offset: int = 1800,
    max_age_sec: int = 0,
):
  results = []
  try:
    root = ET.fromstring(xml_bytes)
  except Exception:
    return results

  ns = {
      "atom": "http://www.w3.org/2005/Atom",
      "yt": "http://www.youtube.com/xml/schemas/2015",
      "media": "http://search.yahoo.com/mrss/",
      "content": "http://purl.org/rss/1.0/modules/content/",
  }
  now_ts = time.time()

  for item in root.findall(".//item"):
    raw_title_full = clean_html_text(item.findtext("title") or "")
    title = raw_title_full
    link = clean_social_post_url((item.findtext("link") or "").strip())
    raw_desc_html = item.findtext("description") or ""
    raw_content_encoded = (
        item.findtext("content:encoded", default="", namespaces=ns) or ""
    )
    full_raw_html = f"{raw_content_encoded} {raw_desc_html}"
    desc = clean_full_article_text(raw_content_encoded) if len(clean_full_article_text(raw_content_encoded)) >= 120 else clean_full_article_text(raw_desc_html)

    pub_raw = (
        item.findtext("pubDate")
        or item.findtext("{http://purl.org/dc/elements/1.1/}date")
        or ""
    )
    source_el = item.find("source")
    source_url_attr = (
        (source_el.attrib.get("url") or "").strip()
        if source_el is not None and hasattr(source_el, "attrib")
        else ""
    )
    source_name = (
        clean_html_text(source_el.text)
        if source_el is not None and source_el.text
        else default_source
    )
    for sep in (" - ", " | ", " – ", " — "):
      if sep in title:
        parts = title.rsplit(sep, 1)
        if len(parts[0].strip()) >= 16 and 2 <= len(parts[1].strip()) <= 35:
          if not source_name or source_name == default_platform:
            source_name = parts[1].strip()
          title = parts[0].strip()
          break

    if not title or not link:
      continue

    img_url = ""
    for m_tag in ["media:content", "media:thumbnail", "enclosure"]:
      el = item.find(m_tag, ns) if ":" in m_tag else item.find(m_tag)
      if el is not None and el.attrib.get("url"):
        cand_img = clean_and_validate_image_url(el.attrib["url"].strip(), link, default_platform)
        if cand_img:
          img_url = cand_img
          break
    if not img_url:
      for child in item:
        if (
            child.tag.lower().endswith("image")
            and child.text
            and child.text.strip().startswith("http")
        ):
          cand_img = clean_and_validate_image_url(child.text.strip(), link, default_platform)
          if cand_img:
            img_url = cand_img
            break
    if not img_url:
      img_url = extract_thumbnail_for_item(
          link, full_raw_html, default_platform
      )

    pub_str, pub_ts = extract_date_from_url_or_text(
        link, desc, pub_raw, fallback_offset_sec=fallback_offset
    )
    if max_age_sec > 0 and (now_ts - pub_ts) > max_age_sec:
      continue

    precise_source = format_precise_source_with_domain(
        source_name or default_platform,
        link,
        default_platform,
        source_url_hint=source_url_attr,
        title_hint=raw_title_full,
    )

    results.append({
        "title": title,
        "url": link,
        "raw_snippet": desc[:15000] if desc else title,
        "source_name": precise_source,
        "source_domain_hint": _extract_clean_domain(source_url_attr),
        "platform": default_platform,
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": img_url,
    })

  for entry in root.findall(".//atom:entry", ns):
    title = clean_html_text(
        entry.findtext("atom:title", default="", namespaces=ns)
    )
    link_el = entry.find("atom:link", ns)
    link = link_el.attrib.get("href", "").strip() if link_el is not None else ""
    pub_raw = entry.findtext(
        "atom:published", default="", namespaces=ns
    ) or entry.findtext("atom:updated", default="", namespaces=ns)
    author_name = entry.findtext(
        "atom:author/atom:name", default=default_source, namespaces=ns
    )
    media_desc = entry.findtext(
        "media:group/media:description", default="", namespaces=ns
    )
    thumb_el = entry.find("media:group/media:thumbnail", ns)
    img_url = (
        clean_and_validate_image_url(thumb_el.attrib.get("url", "").strip(), link, default_platform)
        if thumb_el is not None
        else extract_thumbnail_for_item(link, "", default_platform)
    )
    snippet_txt = clean_html_text(media_desc) or title
    if not title or not link:
      continue
    pub_str, pub_ts = extract_date_from_url_or_text(
        link, snippet_txt, pub_raw, fallback_offset_sec=fallback_offset
    )
    if max_age_sec > 0 and (now_ts - pub_ts) > max_age_sec:
      continue

    precise_author = format_precise_source_with_domain(
        clean_html_text(author_name or default_source or default_platform),
        link,
        default_platform,
        title_hint=title,
    )

    results.append({
        "title": title,
        "url": link,
        "raw_snippet": clean_full_article_text(media_desc)[:15000] if media_desc else snippet_txt[:15000],
        "source_name": precise_author,
        "platform": default_platform,
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": img_url,
    })

  return results


def scrape_moroccan_press(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
):
  """رصد متوازٍ فائق السرعة للصحافة الوطنية المغربية عبر الخلاصات المباشرة وGoogle News وBing News."""
  items = []
  seen_urls = set()
  queries = build_search_queries(keywords_input)
  p_cfg = get_period_config(search_period)
  when_tag = p_cfg["gnews"]
  max_age = p_cfg["sec"]

  direct_sites = [s for s in MOROCCAN_PRESS_SITES if s.get("rss")]
  batch_size = 4
  site_batches = [
      MOROCCAN_PRESS_SITES[i : i + batch_size]
      for i in range(0, len(MOROCCAN_PRESS_SITES), batch_size)
  ]
  search_term_wp = (
      keywords_input.strip().split(",")[0].strip()
      if keywords_input.strip()
      else "القضاء"
  )
  core_kw = (
      queries[0]
      if keywords_input.strip()
      else "(القضاء OR العدالة OR المحكمة OR النيابة العامة OR السلطة القضائية)"
  )

  tasks = []
  for site_info in direct_sites[:8]:
    wp_u = f"https://{site_info['domain']}/?s={urllib.parse.quote(search_term_wp)}&feed=rss2"
    tasks.append(("direct", f"فحص الخلاصة المباشرة لجريدة {site_info['name']}...", [wp_u, site_info["rss"]], site_info["name"]))

  for q in queries:
    bing_u = f"https://www.bing.com/news/search?q={urllib.parse.quote(q)}&format=rss&adlt=strict&cc=MA&setlang=ar"
    gnews_u = f"https://news.google.com/rss/search?q={urllib.parse.quote(f'{q} when:{when_tag}')}&hl=ar&gl=MA&ceid=MA:ar"
    tasks.append(("query", f"رصد الصحافة الوطنية: {q}", [bing_u, gnews_u], ""))

  for batch in site_batches:
    names_label = "، ".join(s["name"] for s in batch[:2])
    sites_expr = " OR ".join(f"site:{s['domain']}" for s in batch)
    full_q = f"({sites_expr}) {core_kw} when:{when_tag}"
    rss_u = f"https://news.google.com/rss/search?q={urllib.parse.quote(full_q)}&hl=ar&gl=MA&ceid=MA:ar"
    tasks.append(("batch", f"مسح الصحف المغربية ({names_label}...)", [rss_u], ""))

  def _run_press_task(task_tuple):
    t_kind, t_label, url_list, def_src = task_tuple
    if is_stop_requested():
      return t_label, []
    found = []
    for u_feed in url_list:
      if is_stop_requested():
        break
      try:
        r = requests.get(u_feed, headers=DEFAULT_HEADERS, timeout=4.5)
        if r.status_code == 200 and (b"<rss" in r.content or b"<feed" in r.content or b"<item>" in r.content):
          parsed_entries = parse_rss_xml(r.content, "الصحف", default_source=def_src, max_age_sec=max_age)
          for entry in parsed_entries:
            if is_strictly_judicial_and_clean(entry["title"], entry["raw_snippet"], entry["url"], keywords_input):
              found.append(entry)
          if t_kind == "direct" and found:
            break
      except Exception:
        pass
    return t_label, found

  total_tasks = max(1, len(tasks))
  completed_tasks = 0
  try:
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
      future_map = {pool.submit(_run_press_task, t): t for t in tasks}
      for fut in concurrent.futures.as_completed(future_map):
        if is_stop_requested():
          break
        completed_tasks += 1
        try:
          t_lbl, entries_list = fut.result()
        except Exception:
          t_lbl, entries_list = "مسح الصحافة الوطنية...", []
        if progress_cb:
          progress_cb(min(0.96, completed_tasks / total_tasks), t_lbl)
        for entry in entries_list:
          if entry["url"] not in seen_urls:
            seen_urls.add(entry["url"])
            items.append(entry)
  except Exception:
    pass

  return items


MOROCCAN_JUDICIAL_YOUTUBE_CHANNELS = [
    ("@Hespress", "قناة هسبريس"),
    ("@2mtv", "القناة الثانية 2M"),
    ("@SNRTnews", "قناة SNRTnews"),
    ("@Medi1TV", "قناة مدي 1 تيفي"),
    ("@al3omk", "قناة العمق المغربي"),
    ("@Alyaoum24", "قناة اليوم 24"),
    ("@madar21", "قناة مدار 21"),
    ("@alayam24", "قناة الأيام 24"),
    ("@FebrayerTV", "قناة فبراير"),
    ("@Hibapress", "قناة هبة بريس"),
    ("@Le360Live", "قناة Le360"),
    ("@GoudMa", "قناة كود"),
    ("@kech24", "قناة كش 24"),
    ("@Tanja24", "قناة طنجة 24"),
]


def build_youtube_judicial_queries(keywords_input: str) -> list:
  """توليد استعلامات بحث يوتيوب الدقيقة والشاملة التي تغطي المجلس الأعلى للسلطة القضائية والشؤون القضائية والقضاة والعدالة بالمغرب."""
  custom_kws = [
      k.strip()
      for k in re.split(r"[,،\n]+", str(keywords_input or ""))
      if k.strip()
  ]
  if custom_kws:
    queries = []
    for kw in custom_kws:
      kw_clean = kw.strip('"\' ')
      queries.append(kw_clean)
      if "المغرب" not in kw_clean:
        queries.append(f"{kw_clean} المغرب")
        queries.append(f"{kw_clean} القضاء المغرب")
    return queries

  return [
      "المجلس الأعلى للسلطة القضائية",
      "المجلس الأعلى للسلطة القضائية المغرب",
      "رئاسة النيابة العامة المغرب",
      "الشؤون القضائية المغرب",
      "القضاة بالمغرب",
      "القضاء بالمغرب",
      "العدالة بالمغرب",
      "محكمة النقض المغرب",
      "نادي قضاة المغرب",
      "الودادية الحسنية للقضاة",
      "المعهد العالي للقضاء المغرب",
      "الوكيل العام للملك المغرب",
      "وكيل الملك المحكمة المغرب",
      "المسطرة الجنائية المغرب",
      "إصلاح العدالة المغرب",
  ]


_YT_EXACT_META_CACHE = {}


def _extract_yt_relative_time_from_text(text: str) -> str:
  """استخراج عبارة الوقت النسبي أو التاريخ الصريح (بما في ذلك صيغ التنوين مثل: قبل 11 شهرًا / قبل 15 يومًا / قبل سنتين / 2 days ago / il y a un an) من نصوص يوتيوب."""
  if not text:
    return ""
  norm_t = _normalize_date_input_text(text)
  if not norm_t:
    return ""

  ar_units = (
      r"(?:ثواني|ثوان|ثانية|ثانيه|دقيقتين|دقيقتان|دقائق|دقيقة|دقيقه|"
      r"ساعتين|ساعتان|ساعات|ساعة|ساعه|يومين|يومان|يوما|أيام|ايام|يوم|أمس|امس|"
      r"أسبوعين|اسبوعين|أسبوعان|اسبوعان|أسبوعا|اسبوعا|أسابيع|اسابيع|أسبوع|اسبوع|"
      r"شهرين|شهران|شهرا|أشهر|اشهر|شهور|شهر|"
      r"سنتين|سنتان|سنوات|سنة|سنه|عامين|عامان|أعوام|اعوام|عاما|عام)"
  )
  ar_num_w = "|".join(sorted(_ARABIC_NUMBER_WORDS.keys(), key=len, reverse=True))
  m_ar = re.search(
      rf"((?:تم البث\s+|بث مباشر\s+|العرض الاول\s+|العرض الأول\s+)?(?:قبل|منذ)\s+(?:حوالي\s+|اكثر من\s+|أكثر من\s+|اقل من\s+|أقل من\s+)?(?:(?:\d+|{ar_num_w})\s+)?{ar_units}\b(?:\s+واحد|\s+واحدة|\s+واحده)?)",
      norm_t,
      re.IGNORECASE,
  )
  if m_ar:
    return m_ar.group(1).strip()

  m_en = re.search(
      r"((?:Streamed\s+|Premiered\s+)?(?:\d+|a|an)\s+(?:second|seconds|minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\s+ago)",
      norm_t,
      re.IGNORECASE,
  )
  if m_en:
    return m_en.group(1).strip()

  m_fr = re.search(
      r"((?:Diffusé\s+|Première\s+)?il y a\s+(?:environ\s+)?(?:\d+|un|une)\s+(?:seconde|secondes|minute|minutes|heure|heures|jour|jours|semaine|semaines|mois|an|ans|année|années|annee|annees))",
      norm_t,
      re.IGNORECASE,
  )
  if m_fr:
    return m_fr.group(1).strip()

  if len(norm_t) <= 32 and has_explicit_parseable_date(norm_t):
    return norm_t

  return ""


def fetch_youtube_video_exact_metadata(vid_id: str, rel_hint: str = "") -> dict:
  """استخراج التاريخ الحقيقي الدقيق لنشر فيديو يوتيوب (uploadDate / publishDate / startTimestamp) مباشرة من بيانات الفيديو الرسمية لمنع أي التباس في التوقيت."""
  vid = str(vid_id or "").strip()
  if not vid or len(vid) != 11:
    return {"vid": vid, "has_exact_date": False, "pub_date": "", "pub_timestamp": 0.0}

  cached = _YT_EXACT_META_CACHE.get(vid)
  if isinstance(cached, dict) and cached.get("has_exact_date"):
    return cached

  pub_iso = ""
  watch_date_text = ""
  watch_rel_text = ""
  title = ""
  author = ""
  channel_id = ""
  short_desc = ""

  # 1) فحص واجهة YouTube InnerTube v1/player السريعة للحصول على microformat (publishDate / uploadDate / startTimestamp)
  player_url = "https://www.youtube.com/youtubei/v1/player?prettyPrint=false"
  payload = {
      "context": {
          "client": {
              "clientName": "WEB",
              "clientVersion": "2.20240726.00.00",
              "hl": "ar",
              "gl": "MA",
          }
      },
      "videoId": vid,
  }
  headers_json = dict(DEFAULT_HEADERS)
  headers_json["Content-Type"] = "application/json"
  try:
    rp = requests.post(
        player_url,
        json=payload,
        headers=headers_json,
        cookies=YT_BYPASS_COOKIES,
        timeout=4.2,
    )
    if rp.status_code == 200 and rp.text:
      p_data = rp.json()
      mf = p_data.get("microformat", {}).get("playerMicroformatRenderer", {})
      vd = p_data.get("videoDetails", {})
      if isinstance(mf, dict):
        live_b = mf.get("liveBroadcastDetails", {})
        if isinstance(live_b, dict):
          pub_iso = str(live_b.get("startTimestamp") or live_b.get("endTimestamp") or "").strip()
        if not pub_iso:
          pub_iso = str(mf.get("publishDate") or mf.get("uploadDate") or "").strip()
        author = clean_display_text(mf.get("ownerChannelName") or "")
        channel_id = str(mf.get("externalChannelId") or "").strip()
        title = clean_display_text((mf.get("title") or {}).get("simpleText") or "")
        short_desc = clean_full_article_text((mf.get("description") or {}).get("simpleText") or "")
      if isinstance(vd, dict):
        if not title:
          title = clean_display_text(vd.get("title") or "")
        if not author:
          author = clean_display_text(vd.get("author") or "")
        if not channel_id:
          channel_id = str(vd.get("channelId") or "").strip()
        if not short_desc and vd.get("shortDescription"):
          short_desc = clean_full_article_text(vd.get("shortDescription") or "")
  except Exception:
    pass

  # 2) فحص صفحة الفيديو المباشرة (watch?v=...) إذا لم يتوفر طابع زمني كامل أو لاستخراج dateText / uploadDate الدقيق
  if not pub_iso or len(pub_iso) <= 10:
    try:
      rw = requests.get(
          f"https://www.youtube.com/watch?v={vid}",
          headers=DEFAULT_HEADERS,
          cookies=YT_BYPASS_COOKIES,
          timeout=4.5,
      )
      if rw.status_code == 200 and rw.text:
        w_html = rw.text
        m_full_iso = re.search(
            r'(?:itemprop=["\'](?:datePublished|uploadDate)["\'][^>]+content=["\']|"(?:publishDate|uploadDate|startTimestamp)"\s*:\s*")(20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^"\'>]*)',
            w_html,
        )
        if m_full_iso:
          pub_iso = m_full_iso.group(1).strip()
        elif not pub_iso:
          m_date_iso = re.search(
              r'(?:itemprop=["\'](?:datePublished|uploadDate)["\'][^>]+content=["\']|"(?:publishDate|uploadDate)"\s*:\s*")(20\d{2}-\d{2}-\d{2})',
              w_html,
          )
          if m_date_iso:
            pub_iso = m_date_iso.group(1).strip()

        m_dt = re.search(r'"dateText"\s*:\s*\{"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"\}', w_html)
        if m_dt:
          watch_date_text = decode_js_escaped_text(m_dt.group(1))
        m_pt = re.search(r'"publishedTimeText"\s*:\s*\{"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"\}', w_html)
        if m_pt:
          watch_rel_text = decode_js_escaped_text(m_pt.group(1))
        if not author:
          m_au = re.search(r'"ownerChannelName"\s*:\s*"((?:[^"\\]|\\.)*)"', w_html)
          if m_au:
            author = decode_js_escaped_text(m_au.group(1))
        if not short_desc:
          m_sd = re.search(r'"shortDescription"\s*:\s*"((?:[^"\\]|\\.){15,8000})"', w_html)
          if m_sd:
            short_desc = clean_full_article_text(decode_js_escaped_text(m_sd.group(1)))
    except Exception:
      pass

  final_str = ""
  final_ts = 0.0

  if pub_iso:
    iso_str, iso_ts = parse_any_date(pub_iso, fallback_offset_sec=-1)
    if iso_ts > 0:
      final_str, final_ts = iso_str, iso_ts
      # إذا كان التاريخ المستخرج بصيغة يوم فقط (YYYY-MM-DD) ولدينا توقيت نسبي بالساعات أو الدقائق في نفس اليوم، ندمج دقة الساعات/الدقائق
      if "T" not in pub_iso:
        cand_rel = watch_rel_text or watch_date_text or rel_hint
        if cand_rel:
          r_str, r_ts = parse_any_date(cand_rel, fallback_offset_sec=-1)
          if r_ts > 0 and abs(r_ts - iso_ts) <= 36 * 3600:
            final_str, final_ts = r_str, r_ts

  if final_ts <= 0:
    for cand_txt in (watch_date_text, watch_rel_text):
      if cand_txt:
        c_str, c_ts = parse_any_date(cand_txt, fallback_offset_sec=-1)
        if c_ts > 0:
          final_str, final_ts = c_str, c_ts
          break

  res = {
      "vid": vid,
      "has_exact_date": bool(final_ts > 0),
      "pub_date": final_str,
      "pub_timestamp": float(final_ts),
      "title": title,
      "channel_name": author,
      "channel_id": channel_id,
      "short_desc": short_desc,
  }
  if res["has_exact_date"]:
    _YT_EXACT_META_CACHE[vid] = res
  return res


def _extract_yt_renderers_from_html(
    html_text: str, default_channel_name: str = "YouTube"
):
  results = []
  seen_vids = set()
  if not html_text:
    return results

  chunks = re.split(
      r'"(?:videoRenderer|gridVideoRenderer|compactVideoRenderer|reelItemRenderer|shortsLockupViewModel|lockupViewModel|playlistRenderer|channelRenderer|shelfRenderer|reelShelfRenderer|richItemRenderer)"\s*:',
      html_text,
  )[1:]
  for chunk in chunks[:90]:
    window = chunk[:12000]
    vid_m = re.search(
        r'"(?:videoId|contentId)"\s*:\s*"([a-zA-Z0-9_-]{11})"', window[:3500]
    )
    if not vid_m:
      continue
    vid = vid_m.group(1)
    if vid in seen_vids:
      continue

    title = ""
    acc_label_full = ""
    m_acc = re.search(r'"accessibilityData"\s*:\s*\{"label"\s*:\s*"((?:[^"\\]|\\.)*)"', window[:6500])
    if m_acc:
      acc_label_full = decode_js_escaped_text(m_acc.group(1))

    for t_pat in [
        r'"title"\s*:\s*\{[^{}]*"runs"\s*:\s*\[\{"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"title"\s*:\s*\{"runs"\s*:\s*\[\{"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"title"\s*:\s*\{[^{}]*"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"headline"\s*:\s*\{[^{}]*"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"lockupMetadataViewModel"\s*:\s*\{.*?"title"\s*:\s*\{"content"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"primaryText"\s*:\s*\{"content"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"title"\s*:\s*\{"content"\s*:\s*"((?:[^"\\]|\\.)*)"',
    ]:
      m_t = re.search(t_pat, window[:6000])
      if m_t:
        cand_t = decode_js_escaped_text(m_t.group(1))
        if len(cand_t) >= 4:
          title = cand_t
          break

    if not title and acc_label_full:
      title = re.sub(r"\s+(?:قبل|منذ)\s+\d+.*$", "", acc_label_full).strip()

    if not title or len(title) < 4:
      continue

    pub_rel = ""
    for p_pat in [
        r'"publishedTimeText"\s*:\s*\{"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"publishedTimeText"\s*:\s*\{"runs"\s*:\s*\[\{"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"dateText"\s*:\s*\{"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"',
    ]:
      pub_m = re.search(p_pat, window)
      if pub_m:
        pub_rel = decode_js_escaped_text(pub_m.group(1))
        break

    # استخراج جميع نصوص content داخل metadataParts في قوالب lockupViewModel الحديثة دون الانقطاع عند الأقواس المتداخلة
    meta_parts_texts = [
        decode_js_escaped_text(mp)
        for mp in re.findall(r'"content"\s*:\s*"((?:[^"\\]|\\.){2,90})"', window[:9000])
    ]
    if not pub_rel:
      for mp_txt in meta_parts_texts:
        cand_rel = _extract_yt_relative_time_from_text(mp_txt)
        if cand_rel:
          pub_rel = cand_rel
          break
    if not pub_rel and acc_label_full:
      pub_rel = _extract_yt_relative_time_from_text(acc_label_full)

    owner_m = re.search(
        r'"(?:ownerText|shortBylineText|longBylineText)"\s*:\s*\{"runs"\s*:\s*\[\{"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
        window,
    )
    channel_name = (
        decode_js_escaped_text(owner_m.group(1))
        if owner_m
        else ""
    )
    if not channel_name and meta_parts_texts:
      for mp_txt in meta_parts_texts:
        if (
            2 <= len(mp_txt) <= 45
            and mp_txt != title
            and not _extract_yt_relative_time_from_text(mp_txt)
            and not any(w in mp_txt.lower() for w in ("مشاهدة", "views", "vues", "ألف", "مليون", "قبل ", "منذ ", "ago", "il y a"))
        ):
          channel_name = mp_txt
          break
    if not channel_name:
      channel_name = default_channel_name

    owner_id_m = re.search(
        r'"(?:ownerText|shortBylineText|longBylineText)".*?"browseId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"',
        window,
    )
    owner_id = owner_id_m.group(1) if owner_id_m else ""

    owner_h_m = re.search(
        r'"canonicalBaseUrl"\s*:\s*"/(@?[^"\\]+)"',
        window,
    )
    owner_handle = (
        urllib.parse.unquote(owner_h_m.group(1)).lstrip("@")
        if owner_h_m
        else ""
    )

    desc_runs = re.findall(
        r'"detailedMetadataSnippets".*?"snippetText"\s*:\s*\{"runs"\s*:\s*\[(.*?)\]\s*\}',
        window,
    )
    if not desc_runs:
      desc_runs = re.findall(
          r'"descriptionSnippet"\s*:\s*\{"runs"\s*:\s*\[(.*?)\]\s*\}',
          window,
      )
    desc_text = ""
    if desc_runs:
      parts = re.findall(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', desc_runs[0])
      desc_text = decode_js_escaped_text(" ".join(parts))

    seen_vids.add(vid)
    results.append({
        "vid": vid,
        "title": title,
        "pub_rel": pub_rel,
        "channel_name": channel_name,
        "owner_id": owner_id,
        "owner_handle": owner_handle,
        "desc": desc_text or title,
    })
  return results


def _search_youtube_via_innertube_api(query: str, sp_params: str = "") -> list:
  """البحث المباشر عبر واجهة YouTube InnerTube v1 Search JSON API الرسمية لتجاوز قيود HTML وجلب الفيديوهات القضائية بدقة عالية."""
  api_url = "https://www.youtube.com/youtubei/v1/search?prettyPrint=false"
  payload = {
      "context": {
          "client": {
              "clientName": "WEB",
              "clientVersion": "2.20240726.00.00",
              "hl": "ar",
              "gl": "MA",
          }
      },
      "query": query,
  }
  if sp_params:
    payload["params"] = urllib.parse.unquote(sp_params)

  headers = dict(DEFAULT_HEADERS)
  headers["Content-Type"] = "application/json"
  try:
    r = requests.post(
        api_url,
        json=payload,
        headers=headers,
        cookies=YT_BYPASS_COOKIES,
        timeout=8.5,
    )
    if r.status_code == 200 and r.text:
      return _extract_yt_renderers_from_html(r.text)
  except Exception:
    pass
  return []


def _fetch_single_youtube_query_bundle(args_tuple: tuple) -> list:
  """تنفيذ استعلام بحث يوتيوب واحد عبر InnerTube API + صفحة نتائج يوتيوب مع التقيد الصارم بفلتر الفترة الزمنية المحددة."""
  q, yt_sp, yt_date_sp, yt_raw, yt_date_raw, _ = args_tuple
  if is_stop_requested():
    return []
  bundle_renderers = []
  seen_local_vids = set()

  def _collect(v_list):
    for v in v_list:
      vid = v.get("vid")
      if vid and vid not in seen_local_vids:
        seen_local_vids.add(vid)
        bundle_renderers.append(v)

  # 1) البحث عبر واجهة YouTube InnerTube JSON API بفلتر الفترة الزمنية المحددة حصراً (مرتبة بالأحدث ثم بالصلة ضمن نفس الفترة)
  raw_params_list = []
  for rp in (yt_date_raw, yt_raw):
    if rp and rp not in raw_params_list:
      raw_params_list.append(rp)

  for raw_p in raw_params_list:
    if is_stop_requested():
      break
    _collect(_search_youtube_via_innertube_api(q, raw_p))
    if len(bundle_renderers) >= 18:
      break

  # 2) البحث عبر صفحة نتائج يوتيوب HTML بفلتر الفترة المحددة حصراً
  sp_candidates = []
  for sp_c in (yt_date_sp, yt_sp):
    if sp_c and sp_c not in sp_candidates:
      sp_candidates.append(sp_c)

  for sp_val in sp_candidates:
    if is_stop_requested() or len(bundle_renderers) >= 24:
      break
    search_url = (
        f"https://www.youtube.com/results?search_query={urllib.parse.quote(q)}"
        + (f"&sp={sp_val}" if sp_val else "")
    )
    try:
      r = requests.get(
          search_url,
          headers=DEFAULT_HEADERS,
          cookies=YT_BYPASS_COOKIES,
          timeout=8.5,
      )
      if r.status_code == 200 and r.text:
        _collect(_extract_yt_renderers_from_html(r.text))
    except Exception:
      pass

  return bundle_renderers


def _search_single_moroccan_yt_channel_judicial(args_tuple: tuple) -> list:
  """البحث المباشر داخل القنوات الإخبارية والقضائية المغربية المعتمدة على يوتيوب عن فيديوهات المجلس الأعلى للسلطة القضائية والقضاء والعدالة."""
  ch_handle, ch_label, search_term = args_tuple
  if is_stop_requested():
    return []
  clean_h = ch_handle if ch_handle.startswith("@") else f"@{ch_handle}"
  ch_search_url = (
      f"https://www.youtube.com/{clean_h}/search?query={urllib.parse.quote(search_term)}"
  )
  try:
    r = requests.get(
        ch_search_url,
        headers=DEFAULT_HEADERS,
        cookies=YT_BYPASS_COOKIES,
        timeout=7.5,
    )
    if r.status_code == 200 and r.text:
      return _extract_yt_renderers_from_html(r.text, default_channel_name=ch_label)
  except Exception:
    pass
  return []


def scrape_youtube_platform(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
):
  """محرك رصد يوتيوب القضائي المتطور مع التحقق الصارم من تاريخ النشر الفعلي (uploadDate / publishDate) لكل فيديو والالتزام التام بفترة البحث المحددة."""
  items = []
  seen_vids = set()
  pending_candidates = []
  queries = build_youtube_judicial_queries(keywords_input)
  p_cfg = get_period_config(search_period)
  max_age = p_cfg["sec"]
  yt_sp = p_cfg.get("yt", "EgIIAw%3D%3D")
  yt_date_sp = p_cfg.get("yt_date", "CAISBAgDEAE%3D")
  yt_raw = p_cfg.get("yt_raw", "EgIIAw==")
  yt_date_raw = p_cfg.get("yt_date_raw", "CAISBAgDEAE=")
  now_ts = time.time()

  def _stage_yt_candidate(v: dict):
    vid = (v.get("vid") or "").strip()
    if not vid or vid in seen_vids:
      return
    v_url = f"https://www.youtube.com/watch?v={vid}"
    v_title = clean_display_text(v.get("title") or "")
    v_desc = clean_display_text(v.get("desc") or "") or v_title
    v_ch = clean_display_text(v.get("channel_name") or "يوتيوب")
    if not v_title or len(v_title) < 5:
      return

    combined_snip_for_check = f"{v_desc} {v_ch}"
    if not is_strictly_judicial_and_clean(
        v_title, combined_snip_for_check, v_url, keywords_input
    ):
      return

    pub_rel_raw = (v.get("pub_rel") or "").strip()
    if not pub_rel_raw:
      pub_rel_raw = _extract_yt_relative_time_from_text(v_desc)

    prelim_str, prelim_ts = "", 0.0
    if pub_rel_raw:
      prelim_str, prelim_ts = parse_any_date(pub_rel_raw, fallback_offset_sec=-1)
      # استبعاد فوري لأي فيديو يظهر من نصه النسبي أنه أقدم من فترة البحث المختارة
      if prelim_ts > 0 and max_age > 0 and (now_ts - prelim_ts) > max_age:
        seen_vids.add(vid)
        return

    seen_vids.add(vid)
    pending_candidates.append({
        "vid": vid,
        "url": v_url,
        "title": v_title,
        "desc": v_desc,
        "channel_name": v_ch,
        "pub_rel": pub_rel_raw,
        "prelim_str": prelim_str,
        "prelim_ts": prelim_ts,
    })

  # الطبقة 1 و 2: المسح المتوازي للاستعلامات القضائية عبر InnerTube API + YouTube Search HTML المقيدة بفترة البحث
  if progress_cb:
    progress_cb(0.15, f"مسح يوتيوب للمواضيع القضائية والمجلس الأعلى للسلطة القضائية ({search_period})...")

  query_tasks = [
      (q, yt_sp, yt_date_sp, yt_raw, yt_date_raw, False)
      for q in queries
  ]
  try:
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
      for q_idx, rendered_list in enumerate(pool.map(_fetch_single_youtube_query_bundle, query_tasks)):
        if is_stop_requested():
          break
        if progress_cb:
          progress_cb(
              min(0.50, 0.15 + 0.35 * ((q_idx + 1) / max(1, len(query_tasks)))),
              f"فحص نتائج يوتيوب القضائية: {queries[q_idx]}",
          )
        for v_item in rendered_list:
          _stage_yt_candidate(v_item)
  except Exception:
    pass

  # الطبقة 3: البحث القضائي المباشر داخل القنوات الإخبارية والمؤسساتية المغربية الكبرى على يوتيوب
  if not is_stop_requested():
    if progress_cb:
      progress_cb(0.65, "فحص الفيديوهات القضائية داخل القنوات المغربية المعتمدة على يوتيوب...")
    ch_kw = (
        keywords_input.strip().split(",")[0].strip()
        if (keywords_input and keywords_input.strip())
        else "المجلس الأعلى للسلطة القضائية القضاء"
    )
    ch_tasks = []
    for ch_h, ch_lbl in MOROCCAN_JUDICIAL_YOUTUBE_CHANNELS[:10]:
      ch_tasks.append((ch_h, ch_lbl, ch_kw))
      if not (keywords_input and keywords_input.strip()):
        ch_tasks.append((ch_h, ch_lbl, "النيابة العامة القضاة العدالة"))

    try:
      with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for ch_vids in pool.map(_search_single_moroccan_yt_channel_judicial, ch_tasks):
          if is_stop_requested():
            break
          for v_ch_item in ch_vids[:8]:
            _stage_yt_candidate(v_ch_item)
    except Exception:
      pass

  # الطبقة 4: البحث الموازي في فهارس الفيديو والويب مع إخضاع كل فيديو للتحقق الإلزامي من تاريخ النشر الحقيقي
  if not is_stop_requested() and len(pending_candidates) < 25:
    if progress_cb:
      progress_cb(0.78, "تعزيز الرصد عبر فهارس الفيديو لمحركات البحث...")
    if keywords_input and keywords_input.strip():
      web_yt_queries = [
          f'site:youtube.com "{keywords_input.strip()}" القضاء المغرب',
          f'site:youtube.com "{keywords_input.strip()}" المغرب',
      ]
    else:
      web_yt_queries = [
          'site:youtube.com "المجلس الأعلى للسلطة القضائية" المغرب',
          'site:youtube.com "رئاسة النيابة العامة" المغرب',
          'site:youtube.com ("الشؤون القضائية" OR "القضاة" OR "منظومة العدالة" OR "محكمة النقض") المغرب',
      ]

    for wq in web_yt_queries:
      if is_stop_requested():
        break
      for sr in _multi_engine_web_search(wq, platform="يوتيوب", default_source="يوتيوب", max_results=10):
        u_sr = clean_social_post_url(sr.get("url", ""))
        m_v = re.search(
            r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
            u_sr,
        )
        if not m_v:
          continue
        vid_w = m_v.group(1)
        if vid_w in seen_vids:
          continue
        t_sr = clean_display_text(sr.get("title") or "")
        t_sr = re.sub(r"\s*-\s*YouTube.*$", "", t_sr, flags=re.IGNORECASE).strip()
        s_sr = clean_display_text(sr.get("raw_snippet") or "")
        _stage_yt_candidate({
            "vid": vid_w,
            "title": t_sr,
            "desc": s_sr or t_sr,
            "pub_rel": _extract_yt_relative_time_from_text(f"{t_sr} {s_sr}"),
            "channel_name": "يوتيوب",
        })

  # المرحلة الحاسمة: التحقق المتوازي من تاريخ النشر الفعلي (uploadDate / publishDate) لكل فيديو مرشح ورفض أي فيديو قديم خارج فترة البحث
  if pending_candidates and not is_stop_requested():
    if progress_cb:
      progress_cb(0.88, f"التحقق الدقيق من توقيت النشر الحقيقي لفيديوهات يوتيوب ({len(pending_candidates[:45])} فيديو)...")

    def _verify_cand(cand_obj: dict):
      meta = fetch_youtube_video_exact_metadata(cand_obj["vid"], rel_hint=cand_obj.get("pub_rel", ""))
      return cand_obj, meta

    try:
      with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        for cand, exact_meta in pool.map(_verify_cand, pending_candidates[:45]):
          if is_stop_requested():
            break
          if exact_meta.get("has_exact_date") and float(exact_meta.get("pub_timestamp") or 0) > 0:
            final_pub_str = exact_meta["pub_date"]
            final_pub_ts = float(exact_meta["pub_timestamp"])
          elif float(cand.get("prelim_ts") or 0) > 0:
            final_pub_str = cand["prelim_str"]
            final_pub_ts = float(cand["prelim_ts"])
          else:
            # رفض قاطع لأي فيديو مجهول تاريخ النشر لمنع إعطائه تاريخ اليوم بالخطأ
            continue

          # تطبيق صارم ودقيق لفترة البحث المحددة من طرف المستخدم
          if max_age > 0 and (now_ts - final_pub_ts) > max_age:
            continue

          v_title = clean_display_text(exact_meta.get("title") or cand["title"])
          v_desc = clean_full_article_text(exact_meta.get("short_desc") or cand["desc"]) or v_title
          v_ch = clean_display_text(exact_meta.get("channel_name") or cand["channel_name"] or "يوتيوب")
          ch_clean = v_ch if v_ch.startswith("قناة") else f"قناة {v_ch}"

          items.append({
              "title": v_title,
              "url": cand["url"],
              "raw_snippet": v_desc if len(v_desc) >= len(v_title) else v_title,
              "source_name": format_precise_source_with_domain(ch_clean, cand["url"], "يوتيوب", title_hint=v_title),
              "platform": "يوتيوب",
              "pub_date": final_pub_str,
              "pub_timestamp": final_pub_ts,
              "image_url": f"https://i.ytimg.com/vi/{cand['vid']}/hqdefault.jpg",
              "_yt_exact_verified": True,
          })
    except Exception:
      pass

  items.sort(key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True)
  return items


def _multi_engine_social_search(
    platform_label: str,
    site_domains: list,
    keywords_input: str,
    search_period: str = "آخر 7 أيام",
    progress_cb=None,
):
  items = []
  seen_urls = set()
  queries = build_search_queries(keywords_input)[:3]
  p_cfg = get_period_config(search_period)
  when_tag = p_cfg["gnews"]
  ddg_tl = p_cfg["ddg"]
  max_age = p_cfg["sec"]
  now_ts = time.time()

  for idx, q in enumerate(queries):
    if is_stop_requested():
      break
    if progress_cb:
      progress_cb(
          (idx + 1) / max(1, len(queries) + 2),
          f"مسح {platform_label}: {q}",
      )

    for d in site_domains[:2]:
      if is_stop_requested():
        break
      site_q = f"site:{d} {q}"
      for bing_base in [
          "https://www.bing.com/search?q=",
          "https://www.bing.com/news/search?q=",
      ]:
        bing_rss = (
            f"{bing_base}{urllib.parse.quote(site_q)}"
            "&format=rss&adlt=strict&cc=MA&setlang=ar"
        )
        try:
          r = requests.get(bing_rss, headers=DEFAULT_HEADERS, timeout=9)
          if r.status_code == 200 and b"<item>" in r.content:
            for entry in parse_rss_xml(
                r.content,
                platform_label,
                default_source=platform_label,
                fallback_offset=3600,
                max_age_sec=max_age,
            ):
              if entry["url"] not in seen_urls and is_strictly_judicial_and_clean(
                  entry["title"],
                  entry["raw_snippet"],
                  entry["url"],
                  keywords_input,
              ):
                seen_urls.add(entry["url"])
                items.append(entry)
        except Exception:
          pass

    if DDGS is not None and not is_stop_requested():
      for d in site_domains[:2]:
        try:
          with DDGS() as ddgs:
            ddg_q = f"site:{d} {q}"
            for res in ddgs.text(
                ddg_q,
                region="xa-ar",
                safesearch="strict",
                timelimit=ddg_tl,
                max_results=10,
            ):
              href = clean_social_post_url(
                  (res.get("href") or res.get("url") or "").strip()
              )
              title = clean_html_text(res.get("title") or "")
              body = clean_html_text(res.get("body") or "")
              if not href or href in seen_urls:
                continue
              if not any(dom in href.lower() for dom in site_domains):
                continue
              if platform_label == "فيسبوك" and not is_direct_social_post_url(
                  href, "فيسبوك", allow_post_search=False
              ):
                href = resolve_direct_facebook_post_url(body, title)
              if not href or href in seen_urls:
                continue
              if not is_strictly_judicial_and_clean(
                  title, body, href, keywords_input
              ):
                continue
              pub_str, pub_ts = extract_date_from_url_or_text(
                  href, body, "", fallback_offset_sec=3600
              )
              if max_age > 0 and (now_ts - pub_ts) > max_age:
                continue
              seen_urls.add(href)
              items.append({
                  "title": title or body[:95],
                  "url": href,
                  "raw_snippet": body or title,
                  "source_name": platform_label,
                  "platform": platform_label,
                  "pub_date": pub_str,
                  "pub_timestamp": pub_ts,
                  "image_url": extract_thumbnail_for_item(
                      href, "", platform_label
                  ),
              })
        except Exception:
          pass

  if not is_stop_requested():
    if progress_cb:
      progress_cb(
          0.88, f"جلب المنشورات القضائية الموثوقة على {platform_label}..."
      )
    platform_simple_queries = {
        "فيسبوك": [
            f"المجلس الأعلى للسلطة القضائية فيسبوك المغرب when:{when_tag}",
            f"رئاسة النيابة العامة فيسبوك المغرب when:{when_tag}",
            f"القضاء بالمغرب فيسبوك when:{when_tag}",
            f"محكمة النقض المغرب فيسبوك when:{when_tag}",
            f"وزارة العدل المغرب فايسبوك when:{when_tag}",
        ],
        "إكس": [
            f"المجلس الأعلى للسلطة القضائية إكس المغرب when:{when_tag}",
            f"القضاء بالمغرب تغريدة when:{when_tag}",
            f"رئاسة النيابة العامة المغرب تويتر when:{when_tag}",
            f"العدالة بالمغرب منصة إكس when:{when_tag}",
            f"محكمة النقض المغرب تويتر when:{when_tag}",
        ],
        "أخرى": [
            f"المجلس الأعلى للسلطة القضائية تيك توك المغرب when:{when_tag}",
            f"القضاء بالمغرب إنستغرام when:{when_tag}",
            f"المجلس الأعلى للسلطة القضائية لينكدإن when:{when_tag}",
            f"رئاسة النيابة العامة المغرب مواقع التواصل when:{when_tag}",
        ],
    }
    social_g_queries = platform_simple_queries.get(platform_label, [])
    if keywords_input.strip():
      kw_clean = keywords_input.strip()
      if platform_label == "فيسبوك":
        social_g_queries = [
            f'"{kw_clean}" (فيسبوك OR فايسبوك OR منشور OR تدوينة) when:{when_tag}',
            f'"{kw_clean}" فيسبوك المغرب when:{when_tag}',
        ]
      elif platform_label == "إكس":
        social_g_queries = [
            f'"{kw_clean}" (تغريدة OR إكس OR تويتر) when:{when_tag}',
            f'"{kw_clean}" إكس المغرب when:{when_tag}',
        ]
      else:
        social_g_queries = [
            f'"{kw_clean}" (تيك توك OR إنستغرام OR لينكدإن) when:{when_tag}',
            f'"{kw_clean}" مواقع التواصل المغرب when:{when_tag}',
        ]

    plat_tag_slug = {"فيسبوك": "fb", "إكس": "x", "أخرى": "other"}.get(
        platform_label, "soc"
    )
    for sq in social_g_queries:
      if is_stop_requested():
        break
      gnews_social_url = (
          "https://news.google.com/rss/search?q="
          f"{urllib.parse.quote(sq)}&hl=ar&gl=MA&ceid=MA:ar"
      )
      try:
        r = requests.get(gnews_social_url, headers=DEFAULT_HEADERS, timeout=10)
        if r.status_code == 200:
          for entry in parse_rss_xml(
              r.content,
              platform_label,
              fallback_offset=3600,
              max_age_sec=max_age,
          ):
            tagged_url = f"{entry['url']}#plat={plat_tag_slug}"
            if (
                tagged_url not in seen_urls
                and is_strictly_judicial_and_clean(
                    entry["title"],
                    entry["raw_snippet"],
                    entry["url"],
                    keywords_input,
                )
            ):
              entry["url"] = tagged_url
              entry["platform"] = platform_label
              seen_urls.add(tagged_url)
              items.append(entry)
      except Exception:
        pass

  return items


def _extract_fb_page_label_from_entry(url: str, title: str) -> str:
  """استخراج اسم صفحة فيسبوك الناشرة من العنوان أو الرابط لعرضه بوضوح على البطاقة."""
  t_clean = _clean_social_page_title(title)
  if " - " in t_clean:
    first_part = t_clean.split(" - ")[0].strip()
    if 3 <= len(first_part) <= 42:
      return f"فيسبوك • {first_part}"
  try:
    parsed = urllib.parse.urlparse(clean_social_post_url(url))
    parts = [urllib.parse.unquote(p).strip() for p in parsed.path.strip("/").split("/") if p.strip()]
    if parts and parts[0].lower() not in GENERIC_SOCIAL_SEGMENTS and not parts[0].isdigit():
      return f"فيسبوك • {parts[0]}"
    if len(parts) >= 2 and parts[0].lower() in ("p", "people", "pages"):
      p_lbl = re.sub(r"-\d{8,}$", "", parts[1]).replace("-", " ").strip()
      if p_lbl:
        return f"فيسبوك • {p_lbl[:35]}"
  except Exception:
    pass
  return "فيسبوك"


MOROCCAN_JUDICIAL_AND_PRESS_FB_PAGES = [
    ("pmpmaroc", "فيسبوك • رئاسة النيابة العامة"),
    ("cspj.ma", "فيسبوك • المجلس الأعلى للسلطة القضائية"),
    ("justice.gov.ma", "فيسبوك • وزارة العدل"),
    ("Hespress", "فيسبوك • هسبريس"),
    ("al3omk", "فيسبوك • العمق المغربي"),
    ("alyaoum24", "فيسبوك • اليوم 24"),
    ("madar21com", "فيسبوك • مدار 21"),
    ("alayam24", "فيسبوك • الأيام 24"),
    ("goudmag", "فيسبوك • كود"),
    ("akhbarona.page", "فيسبوك • أخبارنا"),
    ("rue20.ma", "فيسبوك • زنقة 20"),
    ("kech24", "فيسبوك • كش 24"),
    ("tanja24", "فيسبوك • طنجة 24"),
    ("barlamane", "فيسبوك • برلمان.كوم"),
]

MOROCCAN_FB_SYNDICATION_MIRRORS = [
    {"fb_handle": "Hespress", "badge": "فيسبوك • هسبريس", "domain": "hespress.com", "rss": "https://www.hespress.com/feed"},
    {"fb_handle": "al3omk", "badge": "فيسبوك • العمق المغربي", "domain": "al3omk.com", "rss": "https://al3omk.com/feed"},
    {"fb_handle": "alyaoum24", "badge": "فيسبوك • اليوم 24", "domain": "alyaoum24.com", "rss": "https://alyaoum24.com/feed"},
    {"fb_handle": "madar21com", "badge": "فيسبوك • مدار 21", "domain": "madar21.com", "rss": "https://madar21.com/feed"},
    {"fb_handle": "alayam24", "badge": "فيسبوك • الأيام 24", "domain": "alayam24.com", "rss": "https://www.alayam24.com/feed"},
    {"fb_handle": "goudmag", "badge": "فيسبوك • كود", "domain": "goud.ma", "rss": "https://www.goud.ma/feed"},
    {"fb_handle": "akhbarona.page", "badge": "فيسبوك • أخبارنا", "domain": "akhbarona.com", "rss": "https://www.akhbarona.com/feed"},
    {"fb_handle": "rue20.ma", "badge": "فيسبوك • زنقة 20", "domain": "rue20.com", "rss": "https://rue20.com/feed"},
    {"fb_handle": "kech24", "badge": "فيسبوك • كش 24", "domain": "kech24.com", "rss": "https://www.kech24.com/feed"},
    {"fb_handle": "tanja24", "badge": "فيسبوك • طنجة 24", "domain": "tanja24.com", "rss": "https://tanja24.com/feed"},
    {"fb_handle": "barlamane", "badge": "فيسبوك • برلمان.كوم", "domain": "barlamane.com", "rss": "https://www.barlamane.com/feed"},
    {"fb_handle": "agadir24", "badge": "فيسبوك • أكادير 24", "domain": "agadir24.info", "rss": "https://agadir24.info/feed"},
]


def _clean_fb_follower_boilerplate(text: str) -> str:
  """تنظيف ديباجات عدد المتابعين والإعجابات في فيسبوك لإبقاء نص المنشور الإخباري الصافي فقط."""
  if not text:
    return ""
  t = _strip_fb_sidebar_noise(text)
  t = re.sub(
      r"^.*?(?:talking about this|يتحدث عن هذا|تسجيل إعجاب|likes?\s*·|followers?\s*·|متابع)\s*[.·•|-]?\s*",
      "",
      t,
      flags=re.IGNORECASE,
  ).strip()
  t = re.sub(
      r"^(?:الصفحة الرسمية|مرحباً بكم في الصفحة الرسمية|Official Page)[^.·•|-]*[.·•|-]\s*",
      "",
      t,
      flags=re.IGNORECASE,
  ).strip()
  return t


def _build_synthesized_fb_post_url(raw_u: str, post_text: str, fb_handle: str = "") -> str:
  """تحويل رابط صفحة فيسبوك أو نتيجة بحث إلى رابط منشور فريد ومباشر يحمل بصمة المنشور (?post_id=...) لضمان حفظه وفتحه بدقة."""
  u_clean = clean_social_post_url(raw_u)
  post_hash = hashlib.md5(normalize_arabic_for_dedup(post_text).encode("utf-8", errors="ignore")).hexdigest()[:12]
  if u_clean and ("facebook.com" in u_clean.lower() or "fb.watch" in u_clean.lower()):
    if is_direct_social_post_url(u_clean, "فيسبوك"):
      return u_clean
    sep = "&" if "?" in u_clean else "?"
    return f"{u_clean.rstrip('/')}{sep}post_id={post_hash}"
  if fb_handle and not fb_handle.isdigit():
    return f"https://www.facebook.com/{fb_handle}?post_id={post_hash}"
  q_short = " ".join(clean_display_text(post_text).split()[:9])
  return f"https://www.facebook.com/search/posts/?q={urllib.parse.quote(q_short)}&post_id={post_hash}"


def _harvest_single_moroccan_fb_mirror(args_tuple: tuple) -> list:
  """جلب المنشورات القضائية والعدلية المغربية المتزامنة مع الصفحات الرسمية للمنابر القضائية والإعلامية المغربية على فيسبوك."""
  mirror_cfg, kw_input, max_age_sec = args_tuple
  if is_stop_requested():
    return []
  dom = mirror_cfg["domain"]
  fb_handle = mirror_cfg["fb_handle"]
  fb_badge = mirror_cfg["badge"]
  rss_main = mirror_cfg.get("rss", "")
  out_posts = []
  now_ts = time.time()
  has_custom_kw = bool(kw_input and str(kw_input).strip())

  search_terms = (
      [k.strip().strip('"\'«» ') for k in re.split(r"[,،\n]+", str(kw_input)) if k.strip().strip('"\'«» ')][:3]
      if has_custom_kw
      else ["القضاء", "النيابة العامة", "المحكمة"]
  )

  base_host = f"www.{dom}" if dom in ("hespress.com", "alayam24.com", "goud.ma", "akhbarona.com", "kech24.com", "barlamane.com") else dom

  # 1) فحص واجهة WordPress REST API المباشرة لاستخراج المنشورات القضائية المغربية الكاملة وصورها عالية الدقة
  for sterm in search_terms[:2]:
    if is_stop_requested():
      break
    wp_api = f"https://{base_host}/wp-json/wp/v2/posts?search={urllib.parse.quote(sterm)}&per_page=8&_embed=1"
    try:
      r_wp = requests.get(wp_api, headers=DEFAULT_HEADERS, timeout=5.0)
      if r_wp.status_code == 200:
        posts_json = r_wp.json()
        if isinstance(posts_json, list):
          for p_obj in posts_json:
            if not isinstance(p_obj, dict):
              continue
            raw_t = clean_display_text(p_obj.get("title", {}).get("rendered", ""))
            raw_html_c = p_obj.get("content", {}).get("rendered", "") or p_obj.get("excerpt", {}).get("rendered", "")
            full_txt = clean_full_article_text(raw_html_c)
            if not raw_t or len(full_txt) < 35:
              continue
            # التحقق الصارم من أن المنشور ذو بعد قضائي/عدلي ويخص المغرب ويطابق الكلمة المفتاحية إن وجدت
            if not is_strictly_judicial_and_clean(raw_t, full_txt, f"https://{base_host}", kw_input, is_target=False):
              continue

            m_emb_fb = re.search(
                r"https?://(?:www\.|m\.|web\.)?facebook\.com/[^\"'\s<>\\]+/(?:posts|videos|photos|reel)/[^\"'\s<>\\]+",
                raw_html_c,
                re.IGNORECASE,
            )
            if m_emb_fb:
              fb_post_u = clean_social_post_url(m_emb_fb.group(0))
            else:
              fb_post_u = _build_synthesized_fb_post_url("", f"{raw_t} {full_txt[:120]}", fb_handle=fb_handle)

            pub_iso = str(p_obj.get("date_gmt") or p_obj.get("date") or "").strip()
            pub_str, pub_ts = extract_date_from_url_or_text(fb_post_u, full_txt, pub_iso, fallback_offset_sec=1800)
            if not has_custom_kw and max_age_sec > 0 and (now_ts - pub_ts) > max(max_age_sec, 14 * 86400):
              continue

            img_u = _extract_wp_media_from_post_json(p_obj, fb_post_u)
            out_posts.append({
                "title": raw_t,
                "url": f"{fb_post_u}#plat=fb",
                "raw_snippet": full_txt[:15000],
                "source_name": fb_badge,
                "platform": "فيسبوك",
                "pub_date": pub_str,
                "pub_timestamp": pub_ts,
                "image_url": img_u,
            })
          if out_posts:
            return out_posts
    except Exception:
      pass

  # 2) فحص خلاصة RSS المباشرة للمنبر المغربي واستخلاص المنشورات القضائية المغربية حصراً
  feed_candidates = [f"https://{base_host}/?s={urllib.parse.quote(search_terms[0])}&feed=rss2"]
  if rss_main and not has_custom_kw:
    feed_candidates.append(rss_main)
  for f_url in feed_candidates:
    if is_stop_requested():
      break
    try:
      rf = requests.get(f_url, headers=DEFAULT_HEADERS, timeout=5.0)
      if rf.status_code == 200 and (b"<rss" in rf.content or b"<feed" in rf.content):
        effective_max_age = 0 if has_custom_kw else max(max_age_sec, 14 * 86400)
        for entry in parse_rss_xml(rf.content, "فيسبوك", default_source=fb_badge, max_age_sec=effective_max_age):
          t_e = entry.get("title", "")
          s_e = entry.get("raw_snippet", "")
          if not is_strictly_judicial_and_clean(t_e, s_e, f"https://{base_host}", kw_input, is_target=False):
            continue
          fb_u = _build_synthesized_fb_post_url("", f"{t_e} {s_e[:120]}", fb_handle=fb_handle)
          entry["url"] = f"{fb_u}#plat=fb"
          entry["platform"] = "فيسبوك"
          entry["source_name"] = fb_badge
          out_posts.append(entry)
        if out_posts:
          break
    except Exception:
      pass

  return out_posts


def scrape_facebook_platform(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
):
  """محرك ذكي ودقيق لرصد المنشورات والأخبار ذات البعد القضائي والعدلي التي تهم المغرب حصراً على منصة فيسبوك."""
  items = []
  seen_urls = set()
  seen_norm_titles = set()
  p_cfg = get_period_config(search_period)
  when_tag = p_cfg["gnews"]
  max_age = p_cfg["sec"]
  now_ts = time.time()
  has_custom_kw = bool(keywords_input and str(keywords_input).strip())
  kw_clean_str = str(keywords_input or "").strip().strip('"\'«» ')
  kw_track_fragment = f"#kwtrack={urllib.parse.quote(kw_clean_str, safe='')}" if has_custom_kw else ""

  def _add_fb_item_safely(cand_item: dict):
    if not cand_item or not isinstance(cand_item, dict):
      return
    t_c = clean_display_text(cand_item.get("title") or "")
    s_c = clean_full_article_text(cand_item.get("raw_snippet") or "") or t_c
    u_c = clean_social_post_url(cand_item.get("url") or "")
    if not t_c or len(t_c) < 10 or not u_c:
      return
    # تحقق صارم ومزدوج قبل قبول أي منشور فيسبوك: يجب أن يكون قضائياً/عدلياً ومرتبطاً بالمغرب حصراً
    if not is_strictly_judicial_and_clean(t_c, s_c, u_c, kw_clean_str, is_target=False):
      return
    norm_t = normalize_arabic_for_dedup(strip_source_suffix_from_title(t_c))
    if not norm_t or len(norm_t) < 10:
      return
    t_head = norm_t[:55]
    if u_c in seen_urls or t_head in seen_norm_titles:
      return
    seen_urls.add(u_c)
    seen_norm_titles.add(t_head)
    cand_item["title"] = t_c
    cand_item["raw_snippet"] = s_c
    cand_item["url"] = f"{u_c}#plat=fb{kw_track_fragment}"
    cand_item["platform"] = "فيسبوك"
    if not cand_item.get("source_name") or cand_item["source_name"] == "الصحف":
      cand_item["source_name"] = "فيسبوك"
    items.append(cand_item)

  chrome_doc_headers = dict(DEFAULT_HEADERS)
  chrome_doc_headers.update({
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Sec-Fetch-Dest": "document",
      "Sec-Fetch-Mode": "navigate",
      "Sec-Fetch-Site": "none",
      "Upgrade-Insecure-Requests": "1",
  })

  # الطبقة 1: الفحص المباشر لأداة الخط الزمني لصفحات المؤسسات القضائية والمنابر الوطنية المغربية على فيسبوك
  pages_to_probe = MOROCCAN_JUDICIAL_AND_PRESS_FB_PAGES[:4] if has_custom_kw else MOROCCAN_JUDICIAL_AND_PRESS_FB_PAGES[:9]
  for p_idx, (fb_handle, fb_badge) in enumerate(pages_to_probe):
    if is_stop_requested():
      break
    if progress_cb:
      progress_cb(
          min(0.22, (p_idx + 1) / max(1, 25)),
          f"فحص منشورات {fb_badge} القضائية بالمغرب...",
      )
    page_u = f"https://www.facebook.com/{fb_handle}"

    plugin_posts = _scrape_facebook_plugin_timeline(
        page_u,
        {},
        fb_badge,
        "",
        keywords_input,
        handle=fb_handle,
        page_id="",
    )
    if not has_custom_kw:
      try:
        rc = requests.get(
            page_u,
            headers=chrome_doc_headers,
            cookies={"locale": "ar_AR"},
            timeout=4.0,
        )
        if rc.status_code == 200 and rc.text and len(rc.text) > 15000:
          plugin_posts.extend(
              _extract_facebook_posts_from_raw_html(
                  rc.text,
                  page_u,
                  fb_handle,
                  "",
                  {},
                  fb_badge,
                  "",
                  keywords_input,
                  page_official_name=fb_badge.replace("فيسبوك • ", ""),
              )
          )
      except Exception:
        pass

    for p in plugin_posts:
      u_p = clean_social_post_url(p.get("url", ""))
      if not u_p:
        continue
      p["source_name"] = fb_badge
      _add_fb_item_safely(p)

  # الطبقة 2: استخلاص المنشورات القضائية المغربية حصراً من فهارس site:facebook.com
  if has_custom_kw:
    custom_kws = [k.strip().strip('"\'«» ') for k in re.split(r"[,،\n]+", keywords_input) if k.strip().strip('"\'«» ')]
    fb_queries = []
    for kw in custom_kws[:3]:
      fb_queries.append(f'site:facebook.com "{kw}" (القضاء OR المحكمة OR العدالة OR "النيابة العامة" OR "السلطة القضائية") المغرب')
      fb_queries.append(f'site:facebook.com "{kw}" المغرب')
      fb_queries.append(f'site:facebook.com/posts "{kw}" المغرب')
      fb_queries.append(f'site:facebook.com/videos "{kw}" المغرب')
  else:
    fb_queries = [
        'site:facebook.com "المجلس الأعلى للسلطة القضائية" المغرب',
        'site:facebook.com "رئاسة النيابة العامة" المغرب',
        'site:facebook.com ("الوكيل العام للملك" OR "وكيل الملك") المغرب',
        'site:facebook.com ("محكمة النقض" OR "محكمة الاستئناف" OR "المحكمة الابتدائية") المغرب',
        'site:facebook.com ("القضاء المغربي" OR "المحاكم المغربية" OR "وزارة العدل") المغرب',
        'site:facebook.com ("نادي قضاة المغرب" OR "الودادية الحسنية للقضاة" OR "المعهد العالي للقضاء")',
    ]

  if not is_stop_requested():
    if progress_cb:
      progress_cb(0.42, "استخلاص المنشورات القضائية المغربية من فهارس فيسبوك...")

    def _run_one_fb_web_query(fq_str: str) -> list:
      if is_stop_requested():
        return []
      return _multi_engine_web_search(fq_str, platform="فيسبوك", default_source="فيسبوك", max_results=16)

    web_batches = []
    try:
      with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, max(1, len(fb_queries)))) as pool:
        for batch_res in pool.map(_run_one_fb_web_query, fb_queries):
          if batch_res:
            web_batches.extend(batch_res)
    except Exception:
      pass

    for entry in web_batches:
      if is_stop_requested():
        break
      raw_u = clean_social_post_url(entry.get("url", ""))
      if not raw_u or ("facebook.com" not in raw_u.lower() and "fb.watch" not in raw_u.lower()):
        continue

      raw_snip = _clean_fb_follower_boilerplate(entry.get("raw_snippet", ""))
      raw_title = _clean_fb_follower_boilerplate(_clean_social_page_title(entry.get("title", "")))
      combined_post_txt = f"{raw_title} — {raw_snip}" if (raw_title and raw_snip and raw_title not in raw_snip) else (raw_snip or raw_title)

      if len(combined_post_txt) < 22:
        continue

      if not is_direct_social_post_url(raw_u, "فيسبوك"):
        resolved_u = resolve_direct_facebook_post_url(raw_snip, raw_title)
        if resolved_u and is_direct_social_post_url(resolved_u, "فيسبوك"):
          raw_u = resolved_u
        else:
          raw_u = _build_synthesized_fb_post_url(raw_u, combined_post_txt)

      display_title = raw_snip[:115] + ("..." if len(raw_snip) > 115 else "") if len(raw_snip) >= 28 else raw_title[:115]
      if not display_title or len(display_title) < 12:
        continue

      if not is_strictly_judicial_and_clean(
          display_title, combined_post_txt, raw_u, kw_clean_str, is_target=False
      ):
        continue

      pub_str, pub_ts = extract_date_from_url_or_text(
          raw_u, combined_post_txt, entry.get("pub_date", ""), fallback_offset_sec=2400
      )
      if not has_custom_kw and max_age > 0 and (now_ts - pub_ts) > max(max_age, 14 * 86400):
        continue

      src_lbl = _extract_fb_page_label_from_entry(raw_u, entry.get("title", ""))
      _add_fb_item_safely({
          "title": display_title,
          "url": f"{raw_u}#plat=fb",
          "raw_snippet": combined_post_txt,
          "source_name": src_lbl,
          "platform": "فيسبوك",
          "pub_date": pub_str,
          "pub_timestamp": pub_ts,
          "image_url": entry.get("image_url", ""),
      })

  # الطبقة 3: الرصد المتوازي للبلاغات والأخبار القضائية والعدلية المغربية المتداولة على صفحات فيسبوك بالمغرب
  if not is_stop_requested():
    if progress_cb:
      progress_cb(0.68, "رصد البلاغات والمنشورات القضائية والعدلية الخاصة بالمغرب...")
    rss_feed_urls = []
    if has_custom_kw:
      gnews_qs = [
          f'"{kw_clean_str}" (القضاء OR المحكمة OR العدالة OR "النيابة العامة" OR "السلطة القضائية" OR "وكيل الملك" OR "وزارة العدل") المغرب when:{when_tag}',
          f'{kw_clean_str} (القضاء OR المحكمة OR العدالة OR "النيابة العامة" OR "السلطة القضائية") المغرب when:{when_tag}',
          f'"{kw_clean_str}" المغرب when:{when_tag}',
          f'"{kw_clean_str}" (القضاء OR المحكمة OR العدالة OR "النيابة العامة") المغرب',
      ]
      for gq in gnews_qs:
        rss_feed_urls.append(
            f"https://news.google.com/rss/search?q={urllib.parse.quote(gq)}&hl=ar&gl=MA&ceid=MA:ar"
        )
      bing_qs = [
          (f'site:facebook.com "{kw_clean_str}" القضاء المغرب', "search"),
          (f'site:facebook.com "{kw_clean_str}" المغرب', "search"),
          (f'"{kw_clean_str}" (القضاء OR المحكمة OR العدالة) المغرب', "news/search"),
      ]
      for bq, b_ep in bing_qs:
        rss_feed_urls.append(
            f"https://www.bing.com/{b_ep}?q={urllib.parse.quote(bq)}&format=rss&adlt=strict&cc=MA&setlang=ar"
        )
    else:
      fb_rss_queries = [
          f'"المجلس الأعلى للسلطة القضائية" المغرب when:{when_tag}',
          f'"رئاسة النيابة العامة" المغرب when:{when_tag}',
          f'("الوكيل العام للملك" OR "وكيل الملك" OR "قاضي التحقيق") المحكمة المغرب when:{when_tag}',
          f'("محكمة النقض" OR "محكمة الاستئناف" OR "المحكمة الابتدائية") القضاء المغرب when:{when_tag}',
          f'("وزارة العدل" OR "المعهد العالي للقضاء" OR "نادي قضاة المغرب" OR "الودادية الحسنية للقضاة" OR "المفتشية العامة للشؤون القضائية") المغرب when:{when_tag}',
          f'("العقوبات البديلة" OR "المسطرة الجنائية" OR "منظومة العدالة" OR "إصلاح العدالة") المغرب when:{when_tag}',
      ]
      for rq in fb_rss_queries:
        rss_feed_urls.append(
            f"https://news.google.com/rss/search?q={urllib.parse.quote(rq)}&hl=ar&gl=MA&ceid=MA:ar"
        )

    def _fetch_one_fb_rss(f_u: str) -> list:
      if is_stop_requested():
        return []
      try:
        rg = requests.get(f_u, headers=DEFAULT_HEADERS, timeout=6.5)
        if rg.status_code == 200 and (b"<item>" in rg.content or b"<entry>" in rg.content):
          eff_age = 0 if has_custom_kw else max(max_age, 14 * 86400)
          return parse_rss_xml(rg.content, "فيسبوك", fallback_offset=2400, max_age_sec=eff_age)
      except Exception:
        pass
      return []

    rss_entries_all = []
    try:
      with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(rss_feed_urls)))) as pool:
        for r_list in pool.map(_fetch_one_fb_rss, rss_feed_urls):
          if r_list:
            rss_entries_all.extend(r_list)
    except Exception:
      pass

    for entry in rss_entries_all:
      t_e = entry.get("title", "")
      s_e = entry.get("raw_snippet", "")
      u_e = entry.get("url", "")
      if not is_strictly_judicial_and_clean(t_e, s_e, u_e, kw_clean_str, is_target=False):
        continue
      orig_src = clean_display_text(entry.get("source_name") or "فيسبوك")
      if "فيسبوك" not in orig_src and "فايسبوك" not in orig_src:
        entry["source_name"] = f"فيسبوك • {orig_src}"
      entry["url"] = f"{strip_internal_url_fragments(u_e)}#plat=fb"
      entry["platform"] = "فيسبوك"
      _add_fb_item_safely(entry)

  # الطبقة 4: المزامنة الذكية المتوازية لمنشورات الصفحات القضائية والإخبارية المغربية المعتمدة على فيسبوك
  if not is_stop_requested():
    if progress_cb:
      progress_cb(0.88, "مزامنة المنشورات القضائية والعدلية من الصفحات الرسمية للمنابر المغربية على فيسبوك...")
    mirror_tasks = [(m_cfg, keywords_input, max_age) for m_cfg in MOROCCAN_FB_SYNDICATION_MIRRORS]
    try:
      with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for mirror_posts in pool.map(_harvest_single_moroccan_fb_mirror, mirror_tasks):
          for mp in mirror_posts:
            _add_fb_item_safely(mp)
    except Exception:
      pass

  items.sort(key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True)
  if has_custom_kw and max_age > 0:
    in_period = [it for it in items if (now_ts - float(it.get("pub_timestamp", 0))) <= max_age]
    if in_period:
      return in_period
  return items


def scrape_x_platform(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
):
  return _multi_engine_social_search(
      "إكس",
      ["x.com", "twitter.com"],
      keywords_input,
      search_period,
      progress_cb,
  )


def scrape_other_platforms(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
):
  return _multi_engine_social_search(
      "أخرى",
      ["tiktok.com", "instagram.com", "linkedin.com"],
      keywords_input,
      search_period,
      progress_cb,
  )


# =====================================================================
# 9. محرك الرصد المخصص الدقيق والمقيد حصرياً بالقناة أو الصفحة المضافة
# =====================================================================
def _tag_custom_target_item(item: dict, t_info: dict, source_badge: str) -> dict:
  """إلحاق وسم الرابط المخصص بمعرف الرابط المباشر للمنشور لضمان حفظه واسترجاعه في تبويب المخصص بنسبة 100%."""
  u_clean = clean_social_post_url(item.get("url", ""))
  t_tag = t_info.get("target_tag", "")
  item["url"] = f"{u_clean}{t_tag}"
  item["source_name"] = source_badge
  item["platform"] = t_info.get("platform", item.get("platform", "الصحف"))
  item["is_custom_target"] = 1
  item["_verified_target_owner"] = True
  return item


def _multi_engine_web_search(
    query: str,
    platform: str = "فيسبوك",
    default_source: str = "",
    max_results: int = 18,
) -> list:
  """بحث فائق الكفاءة عبر 5 محركات متوازية (Bing HTML, Yahoo HTML, DuckDuckGo POST/Lite, Bing RSS, DDGS) لجلب منشورات فيسبوك والمنصات بدقة."""
  collected = []
  seen_u = set()
  bad_boiler = [
      "قم بتسجيل الدخول إلى فيسبوك",
      "لبدء المشاركة والتواصل مع أصدقائك",
      "log in to facebook to start sharing",
      "log in or sign up to view",
  ]

  def _add_candidate(raw_href: str, raw_title: str, raw_body: str, raw_date: str = ""):
    u = clean_social_post_url(raw_href)
    if not u or u in seen_u or not u.startswith("http"):
      return
    if any(skip_d in u.lower() for skip_d in ["bing.com/ck/", "yahoo.com/search", "duckduckgo.com"]):
      return
    t_txt = _strip_fb_sidebar_noise(raw_title)
    b_txt = _strip_fb_sidebar_noise(raw_body)
    if any(bb in b_txt.lower() for bb in bad_boiler):
      b_txt = ""
    if not t_txt and not b_txt:
      return
    pub_str, pub_ts = extract_date_from_url_or_text(
        u, f"{t_txt} {b_txt}", raw_date, fallback_offset_sec=3600
    )
    seen_u.add(u)
    collected.append({
        "title": t_txt or b_txt[:110],
        "url": u,
        "raw_snippet": b_txt or t_txt,
        "source_name": default_source or platform,
        "platform": platform,
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": extract_thumbnail_for_item(u, "", platform),
    })

  cand_lock = threading.Lock()
  orig_add_candidate = _add_candidate

  def _threadsafe_add_candidate(raw_href: str, raw_title: str, raw_body: str, raw_date: str = ""):
    with cand_lock:
      orig_add_candidate(raw_href, raw_title, raw_body, raw_date)

  def _eng_bing_html():
    if is_stop_requested():
      return
    bing_html_url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count={max_results}&setlang=ar&cc=MA"
    try:
      rb_html = requests.get(bing_html_url, headers=DEFAULT_HEADERS, timeout=4.5)
      if rb_html.status_code == 200 and rb_html.text and BeautifulSoup is not None:
        soup_b = BeautifulSoup(rb_html.text, "html.parser")
        for li_el in soup_b.select("li.b_algo, div.b_algo"):
          a_el = li_el.select_one("h2 a[href], a[href]")
          if not a_el:
            continue
          href = a_el.get("href", "").strip()
          title_txt = clean_display_text(a_el.get_text(" ", strip=True))
          snip_el = li_el.select_one("div.b_caption p, p.b_lineclamp2, p.b_lineclamp3, p.b_lineclamp4, .b_caption")
          snip_txt = clean_display_text(snip_el.get_text(" ", strip=True)) if snip_el else ""
          _threadsafe_add_candidate(href, title_txt, snip_txt)
    except Exception:
      pass

  def _eng_yahoo_html():
    if is_stop_requested():
      return
    yahoo_url = f"https://search.yahoo.com/search?p={urllib.parse.quote(query)}&n={max_results}"
    try:
      ry = requests.get(yahoo_url, headers=DEFAULT_HEADERS, timeout=4.5)
      if ry.status_code == 200 and ry.text and BeautifulSoup is not None:
        soup_y = BeautifulSoup(ry.text, "html.parser")
        for algo in soup_y.select("div.algo, div.dd.algo, li div.algo-sr, div.Sr"):
          a_el = algo.select_one("h3 a[href], div.compTitle a[href], a.ac-algo[href], a[href]")
          if not a_el:
            continue
          href = a_el.get("href", "").strip()
          title_txt = clean_display_text(a_el.get_text(" ", strip=True))
          snip_el = algo.select_one("div.compText, p, span.fc-falcon")
          snip_txt = clean_display_text(snip_el.get_text(" ", strip=True)) if snip_el else ""
          _threadsafe_add_candidate(href, title_txt, snip_txt)
    except Exception:
      pass

  def _eng_ddg_post():
    if is_stop_requested():
      return
    ddg_post_headers = dict(DEFAULT_HEADERS)
    ddg_post_headers.update({
        "Referer": "https://html.duckduckgo.com/",
        "Origin": "https://html.duckduckgo.com",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
      rd = requests.post(
          "https://html.duckduckgo.com/html/",
          data={"q": query, "kl": "xa-ar"},
          headers=ddg_post_headers,
          timeout=4.5,
      )
      if rd.status_code == 200 and rd.text and BeautifulSoup is not None:
        soup_d = BeautifulSoup(rd.text, "html.parser")
        for res_box in soup_d.select("div.result, div.web-result, div.results_links"):
          a_el = res_box.select_one("a.result__a[href], h2 a[href]")
          if not a_el:
            continue
          href = a_el.get("href", "").strip()
          title_txt = clean_display_text(a_el.get_text(" ", strip=True))
          snip_el = res_box.select_one(".result__snippet, a.result__snippet")
          snip_txt = clean_display_text(snip_el.get_text(" ", strip=True)) if snip_el else ""
          _threadsafe_add_candidate(href, title_txt, snip_txt)
    except Exception:
      pass

  def _eng_bing_rss(bing_base: str):
    if is_stop_requested():
      return
    bing_u = f"{bing_base}{urllib.parse.quote(query)}&format=rss&adlt=strict&cc=MA&setlang=ar"
    try:
      rb = requests.get(bing_u, headers=DEFAULT_HEADERS, timeout=4.5)
      if rb.status_code == 200 and b"<item>" in rb.content:
        parsed_b = parse_rss_xml(
            rb.content,
            platform,
            default_source=default_source or platform,
            fallback_offset=3600,
            max_age_sec=0,
        )
        with cand_lock:
          for entry in parsed_b:
            u_e = clean_social_post_url(entry.get("url", ""))
            if u_e and u_e not in seen_u:
              seen_u.add(u_e)
              entry["url"] = u_e
              collected.append(entry)
    except Exception:
      pass

  try:
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
      futs = [
          pool.submit(_eng_bing_html),
          pool.submit(_eng_yahoo_html),
          pool.submit(_eng_ddg_post),
          pool.submit(_eng_bing_rss, "https://www.bing.com/search?q="),
          pool.submit(_eng_bing_rss, "https://www.bing.com/news/search?q="),
      ]
      concurrent.futures.wait(futs, timeout=5.5)
  except Exception:
    pass

  if DDGS is not None and len(collected) < 4 and not is_stop_requested():
    try:
      with DDGS() as ddgs:
        for res in ddgs.text(
            query,
            region="wt-wt",
            safesearch="strict",
            timelimit=None,
            max_results=max_results,
        ):
          _threadsafe_add_candidate(
              res.get("href") or res.get("url") or "",
              res.get("title") or "",
              res.get("body") or "",
          )
    except Exception:
      pass

  return collected


def _resolve_youtube_channel_via_innertube(channel_url: str) -> tuple:
  """استخدام واجهة YouTube InnerTube الرسمية (resolve_url) لتحويل أي رابط قناة (@handle أو /c/) إلى معرف القناة الدقيق UC... فوراً."""
  api_url = "https://www.youtube.com/youtubei/v1/navigation/resolve_url?prettyPrint=false"
  payload = {
      "context": {
          "client": {
              "clientName": "WEB",
              "clientVersion": "2.20240726.00.00",
              "hl": "ar",
              "gl": "MA",
          }
      },
      "url": channel_url,
  }
  headers = dict(DEFAULT_HEADERS)
  headers["Content-Type"] = "application/json"
  try:
    r = requests.post(
        api_url, json=payload, headers=headers, cookies=YT_BYPASS_COOKIES, timeout=8
    )
    if r.status_code == 200 and r.text:
      m_id = re.search(r'"browseId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"', r.text)
      if m_id:
        return m_id.group(1), ""
  except Exception:
    pass
  return "", ""


def _browse_youtube_channel_via_innertube(
    cid: str, channel_title: str = "YouTube"
) -> tuple:
  """جلب أحدث الفيديوهات والـ Shorts مباشرة من واجهة YouTube InnerTube (browse) لتجاوز عدم الأرشفة وجدران الكوكيز."""
  api_url = "https://www.youtube.com/youtubei/v1/browse?prettyPrint=false"
  headers = dict(DEFAULT_HEADERS)
  headers["Content-Type"] = "application/json"
  videos = []
  detected_title = channel_title

  # EgZ2aWRlb3PyBgQKAjoA = تبويب الفيديوهات مرتبة من الأحدث، EgZzaG9ydHPyBgUKA5oBAA%3D%3D = تبويب Shorts
  for tab_params in ["EgZ2aWRlb3PyBgQKAjoA", "EgZzaG9ydHPyBgUKA5oBAA==", "EgdzdHJlYW1z8gYECgJ6AA=="]:
    payload = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": "2.20240726.00.00",
                "hl": "ar",
                "gl": "MA",
            }
        },
        "browseId": cid,
        "params": tab_params,
    }
    try:
      r = requests.post(
          api_url,
          json=payload,
          headers=headers,
          cookies=YT_BYPASS_COOKIES,
          timeout=9,
      )
      if r.status_code == 200 and r.text:
        m_t = re.search(
            r'"channelMetadataRenderer"\s*:\s*\{[^{}]*"title"\s*:\s*"((?:[^"\\]|\\.)*)"',
            r.text,
        )
        if m_t:
          cand_t = decode_js_escaped_text(m_t.group(1))
          if cand_t:
            detected_title = cand_t
        v_list = _extract_yt_renderers_from_html(r.text, detected_title)
        videos.extend(v_list)
    except Exception:
      pass
  return videos, detected_title


def _verify_youtube_video_owner(
    video_url: str, handle: str = "", cid: str = "", channel_title: str = ""
) -> tuple:
  """التحقق عبر YouTube oEmbed الرسمي من أن الفيديو مرفوع فعلياً من القناة المطلوبة وليس من قناة أخرى."""
  oembed_u = f"https://www.youtube.com/oembed?url={urllib.parse.quote(video_url)}&format=json"
  try:
    r = requests.get(oembed_u, headers=DEFAULT_HEADERS, timeout=5)
    if r.status_code == 200:
      data = r.json()
      author_name = clean_display_text(data.get("author_name") or "")
      author_url = urllib.parse.unquote(str(data.get("author_url") or "")).lower()
      v_title = clean_display_text(data.get("title") or "")

      if handle and f"@{handle.lower().lstrip('@')}" in author_url:
        return True, v_title, author_name
      if handle and f"/{handle.lower().lstrip('@')}" in author_url:
        return True, v_title, author_name
      if cid and cid.lower() in author_url:
        return True, v_title, author_name
      if (
          channel_title
          and channel_title.lower() != "youtube"
          and not channel_title.startswith("@")
          and channel_title.lower() in author_name.lower()
      ):
        return True, v_title, author_name
      return False, v_title, author_name
  except Exception:
    pass
  return False, "", ""


def _does_yt_video_belong_to_channel(
    v: dict, handle: str = "", cid: str = "", channel_title: str = ""
) -> bool:
  """التحقق من أن الفيديو المستخرج من بحث يوتيوب الحي يعود للقناة المطلوبة حصراً."""
  v_cid = (v.get("owner_id") or "").strip().lower()
  v_handle = (v.get("owner_handle") or "").strip().lower().lstrip("@")
  v_ch_name = (v.get("channel_name") or "").strip().lower()

  t_cid = (cid or "").strip().lower()
  t_handle = (handle or "").strip().lower().lstrip("@")
  t_title = (channel_title or "").strip().lower().lstrip("@")

  if t_cid and v_cid:
    return v_cid == t_cid
  if t_handle and v_handle:
    if v_handle == t_handle or t_handle in v_handle or v_handle in t_handle:
      return True
  if t_handle and len(t_handle) >= 3 and t_handle in v_ch_name:
    return True
  if t_title and t_title != "youtube" and len(t_title) >= 3:
    if t_title in v_ch_name or v_ch_name in t_title:
      return True
    for part in re.split(r"[-|•–—:/()]+", t_title):
      p_clean = part.strip()
      if len(p_clean) >= 4 and p_clean in v_ch_name:
        return True
  return False


def _scrape_youtube_custom_channel(
    t_info: dict, t_kw: str, max_age_sec: int, seen_urls: set
) -> list:
  results = []
  all_channel_videos = []
  raw_u = t_info["raw_url"]
  cid = t_info.get("channel_id", "")
  handle = t_info.get("handle", "")
  name_hint = t_info.get("official_name_hint", "")
  is_name_target = bool(t_info.get("is_name_target", False))
  channel_title = name_hint or t_info.get("display_label", "YouTube")

  # إذا كان الرابط المضاف رابط فيديو يوتيوب مباشر، نرصده فوراً
  if not is_name_target:
    m_direct_v = re.search(
        r"(?:watch\?v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})", raw_u
    )
    if m_direct_v:
      vid_id = m_direct_v.group(1)
      v_url = f"https://www.youtube.com/watch?v={vid_id}"
      _, v_oembed_title, v_author = _verify_youtube_video_owner(v_url)
      _, p_body, _ = scrape_article_page_content_and_image(v_url)
      v_title = v_oembed_title or (
          p_body[:105] if p_body else f"فيديو يوتيوب ({vid_id})"
      )
      badge_lbl = f"🎯 {v_author or channel_title}"
      pub_str, pub_ts = extract_date_from_url_or_text(
          v_url, p_body, "", fallback_offset_sec=1800
      )
      entry = {
          "title": v_title,
          "url": v_url,
          "raw_snippet": p_body or v_title,
          "source_name": badge_lbl,
          "platform": "يوتيوب",
          "pub_date": pub_str,
          "pub_timestamp": pub_ts,
          "image_url": f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg",
      }
      _tag_custom_target_item(entry, t_info, badge_lbl)
      return [entry]

  page_html = ""
  if not is_name_target:
    parsed_u = urllib.parse.urlparse(raw_u)
    clean_base_u = urllib.parse.urlunparse(
        ("https", "www.youtube.com", parsed_u.path.rstrip("/"), "", "", "")
    )
    if cid and not handle:
      videos_tab_url = f"https://www.youtube.com/channel/{cid}/videos"
    elif handle:
      h_prefix = (
          f"@{handle}"
          if not handle.startswith("@")
          and "/c/" not in clean_base_u
          and "/user/" not in clean_base_u
          else handle
      )
      if "/c/" in clean_base_u or "/user/" in clean_base_u:
        videos_tab_url = f"{clean_base_u}/videos"
      else:
        videos_tab_url = f"https://www.youtube.com/{h_prefix}/videos"
    else:
      videos_tab_url = (
          clean_base_u
          if any(
              clean_base_u.endswith(x)
              for x in ["/videos", "/streams", "/shorts"]
          )
          else f"{clean_base_u}/videos"
      )

    # 1) استخراج معرف القناة الدقيق UC عبر ترويسة facebookexternalhit المسموحة دائماً على خوادم السحابة
    if not cid:
      try:
        r_crawler = requests.get(
            clean_base_u, headers=FB_CRAWLER_HEADERS, timeout=8
        )
        if r_crawler.status_code == 200 and r_crawler.text:
          for c_pat in [
              r"feeds/videos\.xml\?channel_id=(UC[a-zA-Z0-9_-]{20,})",
              r"https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]{20,})",
              r'"externalId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"',
          ]:
            m_cid = re.search(c_pat, r_crawler.text[:45000])
            if m_cid:
              cid = m_cid.group(1)
              break
          m_og_t = re.search(
              r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
              r_crawler.text[:35000],
              re.IGNORECASE,
          )
          if m_og_t and m_og_t.group(1).strip():
            c_title = clean_display_text(m_og_t.group(1).strip())
            c_title = re.sub(
                r"\s*-\s*YouTube.*$", "", c_title, flags=re.IGNORECASE
            ).strip()
            if c_title and c_title.lower() != "youtube":
              channel_title = c_title
      except Exception:
        pass

    if not cid:
      cid, _ = _resolve_youtube_channel_via_innertube(clean_base_u)

    # 2) جلب صفحة فيديوهات القناة المباشرة
    for candidate_yt_url in [videos_tab_url, clean_base_u]:
      try:
        r = requests.get(
            candidate_yt_url,
            headers=DEFAULT_HEADERS,
            cookies=YT_BYPASS_COOKIES,
            timeout=10,
        )
        if r.status_code == 200 and r.text:
          page_html = r.text
          og_t = re.search(
              r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']',
              page_html,
              re.IGNORECASE,
          )
          if og_t and og_t.group(1).strip():
            cand_name = clean_display_text(og_t.group(1).strip())
            cand_name = re.sub(
                r"\s*-\s*YouTube.*$", "", cand_name, flags=re.IGNORECASE
            ).strip()
            if cand_name and cand_name.lower() != "youtube":
              channel_title = cand_name

          if not cid:
            for pat in [
                r"feeds/videos\.xml\?channel_id=(UC[a-zA-Z0-9_-]{20,})",
                r'"channelMetadataRenderer"\s*:\s*\{[^{}]*"externalId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"',
                r'"externalId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"',
                r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]{20,})["\']',
                r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]{20,})["\']',
                r'<meta[^>]+itemprop=["\']channelId["\'][^>]+content=["\'](UC[a-zA-Z0-9_-]{20,})["\']',
            ]:
              m_c = re.search(pat, page_html)
              if m_c:
                cid = m_c.group(1)
                break
          if (
              cid
              or '"videoRenderer"' in page_html
              or '"gridVideoRenderer"' in page_html
          ):
            break
      except Exception:
        pass

  # 3) البحث المباشر داخل يوتيوب باسم القناة أو معرفها لاستخراج معرف UC والفيديوهات الحية غير المؤرشفة
  live_search_videos = []
  search_ident = (
      name_hint
      or (f"@{handle}" if handle else "")
      or (channel_title if channel_title.lower() != "youtube" else "")
  )
  if search_ident and (not cid or is_name_target or not page_html):
    for sp_param in ["", "&sp=CAI%253D"]:
      q_yt_live = f"{search_ident} {t_kw}".strip() if sp_param else search_ident
      yt_search_u = (
          "https://www.youtube.com/results?search_query="
          f"{urllib.parse.quote(q_yt_live)}{sp_param}"
      )
      try:
        rs_yt = requests.get(
            yt_search_u,
            headers=DEFAULT_HEADERS,
            cookies=YT_BYPASS_COOKIES,
            timeout=10,
        )
        if rs_yt.status_code == 200 and rs_yt.text:
          if not cid:
            # استخراج معرف القناة من بطاقة القناة الرسمية channelRenderer في نتائج البحث
            m_ch_card = re.search(
                r'"channelRenderer"\s*:\s*\{.*?"channelId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})".*?"title"\s*:\s*\{"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"',
                rs_yt.text[:60000],
            )
            if m_ch_card:
              cid = m_ch_card.group(1)
              det_t = decode_js_escaped_text(m_ch_card.group(2))
              if det_t:
                channel_title = det_t
            else:
              m_ch_simple = re.search(
                  r'"channelRenderer"\s*:\s*\{[^{}]*"channelId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"',
                  rs_yt.text[:60000],
              )
              if m_ch_simple:
                cid = m_ch_simple.group(1)

          extracted_from_search = _extract_yt_renderers_from_html(
              rs_yt.text, channel_title
          )
          for v_cand in extracted_from_search:
            if _does_yt_video_belong_to_channel(
                v_cand, handle=handle, cid=cid, channel_title=channel_title
            ):
              if not cid and v_cand.get("owner_id"):
                cid = v_cand["owner_id"]
              if (
                  v_cand.get("channel_name")
                  and channel_title.lower() == "youtube"
              ):
                channel_title = v_cand["channel_name"]
              live_search_videos.append(v_cand)
      except Exception:
        pass

  now_ts = time.time()
  seen_channel_vids = set()

  # 4) الجلب الفوري من واجهة YouTube InnerTube Browse API الخاصة بالقناة
  if cid:
    innertube_vids, it_title = _browse_youtube_channel_via_innertube(
        cid, channel_title
    )
    if it_title and it_title.lower() != "youtube":
      channel_title = it_title
  else:
    innertube_vids = []

  source_badge = f"🎯 {channel_title}"

  # 5) الجلب من خلاصة XML الرسمية للقناة (تحتوي على تاريخ النشر الدقيق بصيغة ISO-8601)
  if cid:
    xml_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    try:
      rx = requests.get(xml_url, headers=DEFAULT_HEADERS, timeout=10)
      if rx.status_code == 200:
        for entry in parse_rss_xml(
            rx.content,
            "يوتيوب",
            default_source=source_badge,
            max_age_sec=max_age_sec,
        ):
          u_clean_v = clean_social_post_url(entry.get("url", ""))
          if not is_direct_social_post_url(u_clean_v, "يوتيوب"):
            continue
          if not is_strictly_judicial_and_clean(
              entry["title"],
              entry["raw_snippet"],
              u_clean_v,
              t_kw,
              is_target=True,
          ):
            continue
          if u_clean_v not in seen_channel_vids:
            seen_channel_vids.add(u_clean_v)
            entry["url"] = u_clean_v
            entry["_yt_exact_verified"] = True
            _tag_custom_target_item(entry, t_info, source_badge)
            all_channel_videos.append(entry)
    except Exception:
      pass

  # 6) دمج الفيديوهات المستخرجة من InnerTube Browse ومن تبويب /videos ومن بحث يوتيوب الحي المفلتر بملكية القناة مع التحقق الدقيق من تاريخ نشرها
  direct_renderers = list(innertube_vids)
  if page_html:
    direct_renderers.extend(
        _extract_yt_renderers_from_html(page_html, channel_title)
    )
  direct_renderers.extend(live_search_videos)

  unverified_channel_cands = []
  for v in direct_renderers:
    v_url = f"https://www.youtube.com/watch?v={v['vid']}"
    if v_url in seen_channel_vids or not is_direct_social_post_url(
        v_url, "يوتيوب"
    ):
      continue
    if not is_strictly_judicial_and_clean(
        v["title"], v["desc"], v_url, t_kw, is_target=True
    ):
      continue
    pub_rel_v = (v.get("pub_rel") or "").strip() or _extract_yt_relative_time_from_text(v.get("desc") or "")
    p_str_v, p_ts_v = ("", 0.0)
    if pub_rel_v:
      p_str_v, p_ts_v = parse_any_date(pub_rel_v, fallback_offset_sec=-1)
      if p_ts_v > 0 and max_age_sec > 0 and (now_ts - p_ts_v) > max_age_sec:
        seen_channel_vids.add(v_url)
        continue
    seen_channel_vids.add(v_url)
    unverified_channel_cands.append((v, v_url, pub_rel_v, p_str_v, p_ts_v))

  if unverified_channel_cands:
    def _verify_ch_vid(c_tuple):
      v_obj, v_u, p_rel, p_s, p_t = c_tuple
      meta = fetch_youtube_video_exact_metadata(v_obj["vid"], rel_hint=p_rel)
      return v_obj, v_u, meta, p_s, p_t

    try:
      with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for v_obj, v_u, meta, p_s, p_t in pool.map(_verify_ch_vid, unverified_channel_cands[:25]):
          if meta.get("has_exact_date") and float(meta.get("pub_timestamp") or 0) > 0:
            pub_str, pub_ts = meta["pub_date"], float(meta["pub_timestamp"])
          elif p_t > 0:
            pub_str, pub_ts = p_s, float(p_t)
          else:
            continue
          if max_age_sec > 0 and (now_ts - pub_ts) > max_age_sec:
            continue
          v_badge = (
              f"🎯 {v_obj['channel_name']}"
              if v_obj.get("channel_name") and v_obj["channel_name"] != "YouTube"
              else source_badge
          )
          entry = {
              "title": clean_display_text(meta.get("title") or v_obj["title"]),
              "url": v_u,
              "raw_snippet": clean_full_article_text(meta.get("short_desc") or v_obj["desc"]),
              "source_name": v_badge,
              "platform": "يوتيوب",
              "pub_date": pub_str,
              "pub_timestamp": pub_ts,
              "image_url": f"https://i.ytimg.com/vi/{v_obj['vid']}/hqdefault.jpg",
              "_yt_exact_verified": True,
          }
          _tag_custom_target_item(entry, t_info, v_badge)
          all_channel_videos.append(entry)
    except Exception:
      pass

  # 6-ب) إذا حجب يوتيوب صفحة القناة على السحابة ولم يظهر معرف UC بعد، نستخرجه من أول فيديو موثق للقناة عبر oEmbed ثم نسحب خلاصة XML الرسمية الفورية
  if not cid and (handle or name_hint):
    yt_ident_probe = f"@{handle.lstrip('@')}" if handle else name_hint
    for probe_q in [f'site:youtube.com/watch "{yt_ident_probe}"', f'site:youtube.com "{yt_ident_probe}"']:
      if cid:
        break
      for cand_v in _multi_engine_web_search(probe_q, platform="يوتيوب", max_results=8):
        u_probe = clean_social_post_url(cand_v.get("url", ""))
        if not is_direct_social_post_url(u_probe, "يوتيوب"):
          continue
        is_own, _, real_auth = _verify_youtube_video_owner(
            u_probe, handle=handle, cid="", channel_title=channel_title
        )
        if is_own:
          if real_auth and real_auth.lower() != "youtube":
            channel_title = real_auth
            source_badge = f"🎯 {channel_title}"
          try:
            rv_page = requests.get(u_probe, headers=FB_CRAWLER_HEADERS, timeout=6)
            if rv_page.status_code == 200 and rv_page.text:
              m_vcid = re.search(
                  r'(?:itemprop=["\']channelId["\'][^>]+content=["\']|"channelId"\s*:\s*"|"externalChannelId"\s*:\s*")(UC[a-zA-Z0-9_-]{20,})',
                  rv_page.text[:65000],
              )
              if m_vcid:
                cid = m_vcid.group(1)
                break
          except Exception:
            pass
    if cid:
      xml_url_retry = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
      try:
        rx2 = requests.get(xml_url_retry, headers=DEFAULT_HEADERS, timeout=10)
        if rx2.status_code == 200:
          for entry in parse_rss_xml(
              rx2.content,
              "يوتيوب",
              default_source=source_badge,
              max_age_sec=max_age_sec,
          ):
            u_clean_v = clean_social_post_url(entry.get("url", ""))
            if not is_direct_social_post_url(u_clean_v, "يوتيوب"):
              continue
            if not is_strictly_judicial_and_clean(
                entry["title"], entry["raw_snippet"], u_clean_v, t_kw, is_target=True
            ):
              continue
            if u_clean_v not in seen_channel_vids:
              seen_channel_vids.add(u_clean_v)
              entry["url"] = u_clean_v
              entry["_yt_exact_verified"] = True
              _tag_custom_target_item(entry, t_info, source_badge)
              all_channel_videos.append(entry)
      except Exception:
        pass

  # 7) احتياطي أخير عبر محركات البحث مقيد بتحقق oEmbed والتحقق الإلزامي من تاريخ النشر الحقيقي (uploadDate)
  if not all_channel_videos and (handle or cid or name_hint):
    yt_ident = name_hint or (f"@{handle.lstrip('@')}" if handle else cid)
    q_web_yt = f'site:youtube.com "{yt_ident}" {t_kw}'.strip()
    for item_w in _multi_engine_web_search(
        q_web_yt,
        platform="يوتيوب",
        default_source=source_badge,
        max_results=10,
    ):
      u_w = clean_social_post_url(item_w.get("url", ""))
      if u_w in seen_channel_vids or not is_direct_social_post_url(
          u_w, "يوتيوب"
      ):
        continue
      m_vw = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})", u_w)
      if not m_vw:
        continue
      is_owner, real_v_title, real_author = _verify_youtube_video_owner(
          u_w, handle=handle, cid=cid, channel_title=channel_title
      )
      if not is_owner:
        continue
      meta_w = fetch_youtube_video_exact_metadata(m_vw.group(1))
      if not meta_w.get("has_exact_date") or float(meta_w.get("pub_timestamp") or 0) <= 0:
        continue
      w_pub_ts = float(meta_w["pub_timestamp"])
      if max_age_sec > 0 and (now_ts - w_pub_ts) > max_age_sec:
        continue
      item_w["pub_date"] = meta_w["pub_date"]
      item_w["pub_timestamp"] = w_pub_ts
      if real_v_title or meta_w.get("title"):
        item_w["title"] = real_v_title or meta_w["title"]
      if meta_w.get("short_desc"):
        item_w["raw_snippet"] = meta_w["short_desc"]
      if not is_strictly_judicial_and_clean(
          item_w["title"], item_w["raw_snippet"], u_w, t_kw, is_target=True
      ):
        continue
      seen_channel_vids.add(u_w)
      _tag_custom_target_item(
          item_w, t_info, f"🎯 {real_author or channel_title}"
      )
      all_channel_videos.append(item_w)

  all_channel_videos.sort(
      key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
  )

  in_window = [
      e
      for e in all_channel_videos
      if max_age_sec <= 0
      or (now_ts - float(e.get("pub_timestamp", 0))) <= max_age_sec
  ]
  chosen_list = in_window if max_age_sec > 0 else all_channel_videos[:12]
  for entry in chosen_list:
    if entry["url"] not in seen_urls:
      seen_urls.add(entry["url"])
      results.append(entry)

  return results


def _scrape_website_custom_target(
    t_info: dict, t_kw: str, when_tag: str, max_age_sec: int, seen_urls: set
) -> list:
  results = []
  all_site_items = []
  raw_u = t_info["raw_url"]
  domain = t_info["domain"]
  parsed = urllib.parse.urlparse(raw_u)
  base_origin = f"{parsed.scheme}://{parsed.netloc}"
  source_badge = f"🎯 {domain}"
  now_ts = time.time()

  candidate_feeds = [
      f"{raw_u.rstrip('/')}/feed",
      f"{base_origin}/feed",
      f"{base_origin}/rss",
      f"{base_origin}/rss.xml",
      f"{base_origin}/?feed=rss2",
  ]
  if t_kw:
    candidate_feeds.insert(
        0, f"{base_origin}/?s={urllib.parse.quote(t_kw)}&feed=rss2"
    )

  for feed_url in candidate_feeds:
    if is_stop_requested():
      break
    try:
      rf = requests.get(feed_url, headers=DEFAULT_HEADERS, timeout=8)
      if rf.status_code == 200 and (
          b"<rss" in rf.content or b"<feed" in rf.content
      ):
        for entry in parse_rss_xml(
            rf.content,
            "الصحف",
            default_source=source_badge,
            max_age_sec=0,
        ):
          if domain not in entry["url"].lower():
            continue
          if entry["url"].rstrip("/") == raw_u.rstrip("/"):
            continue
          if not is_strictly_judicial_and_clean(
              entry["title"],
              entry["raw_snippet"],
              entry["url"],
              t_kw,
              is_target=True,
          ):
            continue
          _tag_custom_target_item(entry, t_info, source_badge)
          all_site_items.append(entry)
        if all_site_items:
          break
    except Exception:
      pass

  if BeautifulSoup is not None and len(all_site_items) < 5:
    try:
      rp = requests.get(raw_u, headers=DEFAULT_HEADERS, timeout=9)
      if rp is not None and rp.status_code == 200 and rp.text:
        soup = BeautifulSoup(rp.text, "html.parser")
        for a_tag in soup.select(
            "article a, h2 a, h3 a, .post-title a, .entry-title a, a"
        ):
          href = (a_tag.get("href") or "").strip()
          if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
          full_href = urllib.parse.urljoin(raw_u, href)
          if domain not in full_href.lower():
            continue
          if full_href.rstrip("/") == raw_u.rstrip("/"):
            continue
          title_txt = clean_display_text(a_tag.get_text(" ", strip=True))
          if len(title_txt) < 22:
            continue
          if not is_strictly_judicial_and_clean(
              title_txt, "", full_href, t_kw, is_target=True
          ):
            continue
          pub_str, pub_ts = extract_date_from_url_or_text(
              full_href, title_txt, "", fallback_offset_sec=3600
          )
          entry = {
              "title": title_txt,
              "url": full_href,
              "raw_snippet": title_txt,
              "source_name": source_badge,
              "platform": "الصحف",
              "pub_date": pub_str,
              "pub_timestamp": pub_ts,
              "image_url": "",
          }
          _tag_custom_target_item(entry, t_info, source_badge)
          all_site_items.append(entry)
          if len(all_site_items) >= 15:
            break
    except Exception:
      pass

  all_site_items.sort(
      key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
  )
  in_window = [
      e
      for e in all_site_items
      if max_age_sec <= 0
      or (now_ts - float(e.get("pub_timestamp", 0))) <= max_age_sec
  ]
  chosen_list = in_window if in_window else all_site_items[:10]
  for entry in chosen_list:
    if entry["url"] not in seen_urls:
      seen_urls.add(entry["url"])
      results.append(entry)

  return results


def _unwrap_facebook_bigpipe_html(raw_html: str) -> str:
  """فك تعليقات BigPipe (<!-- ... -->) وسلاسل ServerJS (__html) في صفحات وأدوات فيسبوك لإظهار المنشورات الحية غير المؤرشفة."""
  if not raw_html:
    return ""
  expanded = raw_html.replace("<!--", "").replace("-->", "")
  extra_chunks = []
  for m_js in re.finditer(
      r'"__html"\s*:\s*"((?:[^"\\]|\\.)*)"', raw_html
  ):
    chunk_raw = m_js.group(1)
    try:
      decoded = json.loads(f'"{chunk_raw}"')
    except Exception:
      decoded = decode_js_escaped_text(chunk_raw)
    if decoded and ("_5pcr" in decoded or "userContent" in decoded or "story_fbid" in decoded or "/posts/" in decoded):
      extra_chunks.append(decoded)
  if extra_chunks:
    expanded = expanded + "\n" + "\n".join(extra_chunks)
  return expanded


def _extract_post_permalink_from_fb_box(
    box, canonical_fb_url: str, handle: str = "", page_id: str = ""
) -> str:
  """استخراج الرابط المباشر للمنشور بعينه من حاوية المنشور في فيسبوك دون توجيه المستخدم إلى الصفحة العامة."""
  for sel in ["a._5pcq[href]", "span.fsm a[href]", "a[href]"]:
    for a_el in box.select(sel):
      raw_h = (a_el.get("href") or "").strip()
      if not raw_h or raw_h.startswith("#") or raw_h.startswith("javascript:"):
        continue
      cand_u = clean_social_post_url(raw_h)
      if is_direct_social_post_url(cand_u, "فيسبوك") and _is_fb_post_owned_by_target(
          cand_u, handle=handle, page_id=page_id
      ):
        return cand_u

  ft_nodes = [box] + list(box.select("[data-ft]"))
  for node in ft_nodes:
    raw_ft = node.get("data-ft") if hasattr(node, "get") else None
    if not raw_ft:
      continue
    try:
      ft_json = json.loads(html.unescape(str(raw_ft)))
      post_id = str(
          ft_json.get("top_level_post_id")
          or ft_json.get("tl_objid")
          or ft_json.get("mf_story_key")
          or ""
      ).strip()
      owner_id = str(
          ft_json.get("page_id")
          or ft_json.get("content_owner_id_new")
          or page_id
          or ""
      ).strip()
      if post_id and len(post_id) >= 8:
        if handle and not handle.startswith("fb_") and not handle.isdigit():
          cand_u = f"https://www.facebook.com/{handle}/posts/{post_id}"
          if is_direct_social_post_url(cand_u, "فيسبوك"):
            return cand_u
        if owner_id:
          return f"https://www.facebook.com/permalink.php?story_fbid={post_id}&id={owner_id}"
    except Exception:
      m_pid = re.search(
          r'"(?:top_level_post_id|tl_objid|mf_story_key)"\s*:\s*"([^"]+)"',
          str(raw_ft),
      )
      m_oid = re.search(
          r'"(?:page_id|content_owner_id_new)"\s*:\s*"?(\d{6,})"?',
          str(raw_ft),
      )
      if m_pid:
        pid_val = m_pid.group(1).strip()
        oid_val = m_oid.group(1).strip() if m_oid else page_id
        if handle and not handle.startswith("fb_") and not handle.isdigit():
          return f"https://www.facebook.com/{handle}/posts/{pid_val}"
        if oid_val:
          return f"https://www.facebook.com/permalink.php?story_fbid={pid_val}&id={oid_val}"

  return ""


def _fetch_fb_embed_plugin_content(post_u: str) -> tuple:
  """استخراج النص الكامل والصورة والتاريخ لأي منشور أو فيديو فيسبوك عبر نقطة التضمين الرسمية (plugins/post.php و plugins/video.php) التي لا تطلب تسجيل الدخول على السحابة."""
  u_clean = clean_social_post_url(post_u)
  if not u_clean:
    return "", "", ""
  is_vid = any(x in u_clean.lower() for x in ("/videos/", "/watch", "/reel/", "fb.watch"))
  endpoint = "https://www.facebook.com/plugins/video.php" if is_vid else "https://www.facebook.com/plugins/post.php"
  embed_url = f"{endpoint}?href={urllib.parse.quote(u_clean)}&show_text=true&width=500"
  hdr = dict(DEFAULT_HEADERS)
  hdr.update({
      "Referer": "https://www.facebook.com/",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  })
  try:
    r = requests.get(embed_url, headers=hdr, timeout=6)
    if r.status_code != 200 or not r.text:
      return "", "", ""
    doc = _unwrap_facebook_bigpipe_html(r.text)
    if BeautifulSoup is None:
      return "", "", ""
    soup = BeautifulSoup(doc, "html.parser")
    texts = []
    for sel in ["div._5pbx", "div.userContent", "div[data-ad-preview='message']", "p"]:
      for el in soup.select(sel):
        t = clean_display_text(el.get_text(" ", strip=True))
        if len(t) >= 12 and t not in texts:
          texts.append(t)
    body = " ".join(texts[:3]).strip()
    body = re.sub(r"\b(?:عرض المزيد|See More|See more|عرض الترجمة)\b", "", body, flags=re.IGNORECASE).strip()

    img = ""
    for img_el in soup.select("img[src]"):
      s_img = html.unescape(img_el.get("src", "").strip())
      if s_img.startswith("http") and "scontent" in s_img and "p50x50" not in s_img and "s50x50" not in s_img:
        img = s_img
        break

    utime = ""
    ut_el = soup.select_one("abbr[data-utime], span[data-utime]")
    if ut_el:
      utime = str(ut_el.get("data-utime") or "").strip()
    return _strip_fb_sidebar_noise(body), img, utime
  except Exception:
    return "", "", ""


def _scrape_facebook_plugin_timeline(
    canonical_fb_url: str,
    t_info: dict,
    source_badge: str,
    page_avatar: str,
    t_kw: str,
    handle: str = "",
    page_id: str = "",
) -> list:
  """استخراج المنشورات الفورية غير المؤرشفة مباشرة من أداة الخط الزمني لفيسبوك (plugins/page.php) بعد فك تعليقات BigPipe ودعم المعرف الرقمي المباشر."""
  posts = []
  seen_post_urls = set()

  candidate_hrefs = []
  if handle and not handle.startswith("fb_") and not handle.isdigit():
    candidate_hrefs.append(f"https://www.facebook.com/{handle}")
  if page_id and page_id.isdigit():
    # أداة plugins/page.php تقبل المسار الرقمي المباشر facebook.com/{page_id} بينما ترفض profile.php?id=
    candidate_hrefs.append(f"https://www.facebook.com/{page_id}")
  if canonical_fb_url and canonical_fb_url not in candidate_hrefs:
    candidate_hrefs.append(canonical_fb_url)

  iframe_headers = dict(DEFAULT_HEADERS)
  iframe_headers.update({
      "Referer": "https://www.facebook.com/",
      "Sec-Fetch-Dest": "iframe",
      "Sec-Fetch-Mode": "navigate",
      "Sec-Fetch-Site": "same-origin",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  })

  for target_href in candidate_hrefs[:3]:
    plugin_url = (
        "https://www.facebook.com/plugins/page.php?"
        f"href={urllib.parse.quote(target_href)}"
        "&tabs=timeline&width=500&height=800&small_header=false"
        "&adapt_container_width=true&hide_cover=false&show_facepile=false"
    )
    for hdr in (iframe_headers, FB_CRAWLER_HEADERS):
      try:
        r = requests.get(plugin_url, headers=hdr, cookies={"locale": "ar_AR"}, timeout=9)
        if r.status_code != 200 or not r.text:
          continue

        unwrapped_doc = _unwrap_facebook_bigpipe_html(r.text)
        if not page_id:
          m_pid_doc = re.search(r'"(?:page_id|content_owner_id_new)"\s*:\s*"?(\d{6,})"?', unwrapped_doc)
          if m_pid_doc:
            page_id = m_pid_doc.group(1)

        if BeautifulSoup is not None:
          soup = BeautifulSoup(unwrapped_doc, "html.parser")
          post_containers = soup.select(
              "div._5pcr, div.userContentWrapper, div._4-u2._5v3q, div._4-u2._5pat, div[data-ft*='top_level_post_id'], div[data-ft*='tl_objid'], div[data-ft*='mf_story_key'], div[role='article']"
          )

          for idx, box in enumerate(post_containers[:18]):
            post_link = _extract_post_permalink_from_fb_box(
                box, target_href, handle=handle, page_id=page_id
            )
            if not post_link or not is_direct_social_post_url(post_link, "فيسبوك"):
              continue
            if not _is_fb_post_owned_by_target(
                post_link, handle=handle, page_id=page_id
            ):
              continue
            if post_link in seen_post_urls:
              continue

            text_el = box.select_one(
                "div._5pbx, div.userContent, div[data-ad-preview='message']"
            )
            if text_el:
              post_text = clean_display_text(text_el.get_text(" ", strip=True))
            else:
              p_tags = [
                  clean_display_text(p.get_text(" ", strip=True))
                  for p in box.select("p")
                  if len(clean_display_text(p.get_text(" ", strip=True))) >= 10
              ]
              post_text = (
                  " ".join(p_tags)
                  if p_tags
                  else clean_display_text(box.get_text(" ", strip=True))
              )

            post_text = re.sub(
                r"\b(?:عرض المزيد|See More|See more|عرض الترجمة)\b",
                "",
                post_text,
                flags=re.IGNORECASE,
            ).strip()

            if not post_text or len(post_text) < 12:
              emb_txt, emb_img, _ = _fetch_fb_embed_plugin_content(post_link)
              if emb_txt:
                post_text = emb_txt
              if emb_img and not page_avatar:
                page_avatar = emb_img

            if not post_text or len(post_text) < 12:
              continue
            if not is_strictly_judicial_and_clean(
                post_text, post_text, post_link, t_kw, is_target=bool(t_info)
            ):
              continue

            utime_el = box.select_one("abbr[data-utime], span[data-utime]")
            raw_utime = utime_el.get("data-utime", "") if utime_el else ""
            if not raw_utime and utime_el:
              raw_utime = clean_display_text(utime_el.get_text(" ", strip=True))

            post_img = page_avatar
            for img_el in box.select("img[src]"):
              s_img = html.unescape(img_el.get("src", "").strip())
              if (
                  s_img.startswith("http")
                  and "scontent" in s_img
                  and "p50x50" not in s_img
                  and "s50x50" not in s_img
              ):
                post_img = s_img
                break

            pub_str, pub_ts = extract_date_from_url_or_text(
                post_link,
                post_text,
                str(raw_utime),
                fallback_offset_sec=1800 + (idx * 600),
            )
            title_short = post_text[:115] + ("..." if len(post_text) > 115 else "")
            entry = {
                "title": title_short,
                "url": post_link,
                "raw_snippet": post_text,
                "source_name": source_badge,
                "platform": "فيسبوك",
                "pub_date": pub_str,
                "pub_timestamp": pub_ts,
                "image_url": post_img,
            }
            if t_info:
              _tag_custom_target_item(entry, t_info, source_badge)
            seen_post_urls.add(post_link)
            posts.append(entry)

        if not posts:
          extra_posts = _extract_facebook_posts_from_raw_html(
              unwrapped_doc,
              target_href,
              handle,
              page_id,
              t_info,
              source_badge,
              page_avatar,
              t_kw,
          )
          for ep in extra_posts:
            u_ep = clean_social_post_url(ep["url"])
            if u_ep not in seen_post_urls:
              seen_post_urls.add(u_ep)
              posts.append(ep)

        if posts:
          return posts
      except Exception:
        pass
  return posts


def _strip_fb_sidebar_noise(text: str) -> str:
  """إزالة نصوص الشريط الجانبي لفيسبوك (مثل: More videos you may like / فيديوهات أخرى قد تعجبك) من الملخصات."""
  if not text:
    return ""
  t = clean_display_text(text)
  for marker in [
      "More videos you may like",
      "فيديوهات أخرى قد تعجبك",
      "مقاطع فيديو أخرى قد تعجبك",
      "Related Pages",
      "صفحات ذات صلة",
      "See more from",
      "عرض المزيد من",
  ]:
    pos = t.lower().find(marker.lower())
    if pos != -1:
      t = t[:pos].strip(" -–—·•|.")
  return t


def _verify_and_enrich_fb_post_url(
    post_u: str,
    page_avatar: str = "",
    handle: str = "",
    page_id: str = "",
    page_official_name: str = "",
) -> tuple:
  """فحص رابط المنشور عبر ترويسات المعاينة + نقطة التضمين الرسمية (plugins/post.php) للتغلب على جدار تسجيل الدخول على السحابة."""
  try:
    p_html = ""
    rp = None
    for bot_hdr in FB_PREVIEW_BOT_HEADERS[:2]:
      try:
        r_try = requests.get(post_u, headers=bot_hdr, timeout=5)
        if r_try.status_code == 200 and r_try.text:
          rp = r_try
          p_html = r_try.text[:45000]
          if "og:description" in p_html or "og:title" in p_html:
            break
      except Exception:
        pass

    if not p_html:
      emb_body, emb_img, _ = _fetch_fb_embed_plugin_content(post_u)
      is_owned = _is_fb_post_owned_by_target(
          post_u, handle=handle, page_id=page_id, page_official_name=page_official_name
      )
      return is_owned, emb_body, emb_img or page_avatar, post_u

    post_title_og = ""
    for t_pat in [
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        r"<title>(.*?)</title>",
    ]:
      m_t = re.search(t_pat, p_html, re.IGNORECASE | re.DOTALL)
      if m_t:
        post_title_og = _strip_fb_sidebar_noise(m_t.group(1))
        break

    not_found_titles = [
        "page not found",
        "الصفحة غير موجودة",
    ]
    if post_title_og and any(bt in post_title_og.lower() for bt in not_found_titles):
      return False, "", "", post_u

    is_login_wall = bool(
        (rp is not None and rp.url and "login" in rp.url.lower())
        or (
            post_title_og
            and any(
                lw in post_title_og.lower()
                for lw in [
                    "log in",
                    "login",
                    "تسجيل الدخول",
                    "قم بتسجيل الدخول",
                    "content isn't available",
                    "this content isn't available",
                    "المحتوى غير متوفر",
                ]
            )
        )
    )
    if is_login_wall:
      # عند ظهور جدار تسجيل الدخول على السيرفر، نستعين بنقطة التضمين الرسمية plugins/post.php لاستخراج متن المنشور وصورته!
      emb_body, emb_img, _ = _fetch_fb_embed_plugin_content(post_u)
      is_owned = _is_fb_post_owned_by_target(
          post_u, handle=handle, page_id=page_id, page_official_name=page_official_name
      )
      return is_owned, emb_body, emb_img or page_avatar, post_u

    m_og_u = re.search(
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
        p_html,
        re.IGNORECASE,
    )
    resolved_u = post_u
    if m_og_u:
      cand_og_u = clean_social_post_url(m_og_u.group(1))
      if cand_og_u and "login" not in cand_og_u.lower() and is_direct_social_post_url(cand_og_u, "فيسبوك"):
        resolved_u = cand_og_u

    if not _is_fb_post_owned_by_target(
        resolved_u,
        handle=handle,
        page_id=page_id,
        page_official_name=page_official_name,
        og_title=post_title_og,
    ):
      return False, "", "", resolved_u

    post_desc = ""
    for d_pat in [
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
    ]:
      m_d = re.search(d_pat, p_html, re.IGNORECASE)
      if m_d:
        d_txt = _strip_fb_sidebar_noise(m_d.group(1))
        if len(d_txt) >= 10:
          post_desc = d_txt
          break

    post_img = page_avatar
    for i_pat in [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    ]:
      m_i = re.search(i_pat, p_html, re.IGNORECASE)
      if m_i:
        post_img = html.unescape(m_i.group(1).strip())
        break

    final_body = post_desc or post_title_og
    if final_body and any(
        lw in final_body.lower()
        for lw in [
            "قم بتسجيل الدخول",
            "log in to facebook",
            "تسجيل الدخول إلى فيسبوك",
            "log in or sign up",
        ]
    ):
      final_body = ""

    if not final_body or len(final_body) < 15:
      emb_body, emb_img, _ = _fetch_fb_embed_plugin_content(resolved_u)
      if emb_body:
        final_body = emb_body
      if emb_img and post_img == page_avatar:
        post_img = emb_img

    return True, final_body, post_img, resolved_u
  except Exception:
    is_owned = _is_fb_post_owned_by_target(
        post_u, handle=handle, page_id=page_id, page_official_name=page_official_name
    )
    return is_owned, "", page_avatar, post_u


def _walk_comet_json_for_stories(node, collected_stories: list, depth: int = 0):
  """تجول عودي ذكي داخل شجرة JSON الخاصة بـ Facebook Comet SSR لاستخراج كائنات المنشورات والفيديوهات الحية بدقة 100%."""
  if depth > 28 or node is None:
    return
  if isinstance(node, list):
    for item in node:
      _walk_comet_json_for_stories(item, collected_stories, depth + 1)
    return
  if not isinstance(node, dict):
    return

  # التحقق مما إذا كانت العقدة الحالية تمثل منشوراً أو قصة (Story) في فيسبوك
  has_msg = isinstance(node.get("message"), dict) and bool(node["message"].get("text"))
  has_comet_sec = isinstance(node.get("comet_sections"), dict)
  has_story_urls = any(k in node for k in ("permalink_url", "wwwURL", "shareable_url"))
  if has_msg or has_comet_sec or has_story_urls:
    collected_stories.append(node)

  for k, val in node.items():
    if isinstance(val, (dict, list)):
      _walk_comet_json_for_stories(val, collected_stories, depth + 1)


def _extract_fields_from_story_dict(story_node: dict, handle: str = "", page_id: str = "") -> dict:
  """استخراج نص المنشور، الرابط المباشر، وقت النشر، والصورة المصغرة من عقدة Story في Comet JSON."""
  texts = []
  urls = []
  timestamps = []
  images = []
  post_ids = []

  def _scan_story(sub, d=0):
    if d > 14 or sub is None:
      return
    if isinstance(sub, list):
      for x in sub:
        _scan_story(x, d + 1)
      return
    if not isinstance(sub, dict):
      return

    for k, v in sub.items():
      if k in ("message", "savable_description", "title") and isinstance(v, dict):
        t_val = v.get("text")
        if isinstance(t_val, str) and len(t_val.strip()) >= 12:
          texts.append(clean_display_text(t_val))
      elif k in ("permalink_url", "wwwURL", "url", "shareable_url") and isinstance(v, str):
        u_cand = clean_social_post_url(v)
        if is_direct_social_post_url(u_cand, "فيسبوك"):
          urls.append(u_cand)
      elif k in ("creation_time", "publish_time") and isinstance(v, (int, float)):
        if 1500000000 < v < 2100000000:
          timestamps.append(int(v))
      elif k in ("post_id", "story_fbid", "top_level_post_id") and isinstance(v, (str, int)):
        s_v = str(v).strip()
        if s_v.startswith("pfbid") or (s_v.isdigit() and len(s_v) >= 8):
          post_ids.append(s_v)
      elif k == "id" and isinstance(v, str) and v.startswith("UzpfS"):
        try:
          dec = base64.b64decode(v + "===").decode("utf-8", errors="ignore")
          m_sp = re.search(r"S:_I(\d{6,}):(\d{8,}|pfbid[A-Za-z0-9]+)", dec)
          if m_sp:
            post_ids.append(m_sp.group(2))
        except Exception:
          pass
      elif k == "uri" and isinstance(v, str) and "scontent" in v:
        if not any(sz in v for sz in ("p50x50", "s50x50", "p32x32", "s32x32", "p40x40")):
          images.append(v)

      if isinstance(v, (dict, list)):
        _scan_story(v, d + 1)

  _scan_story(story_node)

  best_text = ""
  for t_cand in texts:
    if len(t_cand) > len(best_text):
      best_text = t_cand

  best_url = ""
  for u_cand in urls:
    if _is_fb_post_owned_by_target(u_cand, handle=handle, page_id=page_id):
      best_url = u_cand
      break

  if not best_url and post_ids:
    pid = post_ids[0]
    if handle and not handle.startswith("fb_") and not handle.isdigit():
      best_url = f"https://www.facebook.com/{handle}/posts/{pid}"
    elif page_id:
      best_url = f"https://www.facebook.com/permalink.php?story_fbid={pid}&id={page_id}"

  return {
      "text": best_text,
      "url": best_url,
      "timestamp": timestamps[0] if timestamps else 0,
      "image": images[0] if images else "",
  }


def _extract_comet_relay_posts_from_html(
    raw_html: str,
    handle: str,
    page_id: str,
    page_official_name: str,
    t_info: dict,
    source_badge: str,
    page_avatar: str,
    t_kw: str,
) -> list:
  """تحليل بيانات Comet Relay JSON المضمنة في كود صفحة فيسبوك الحديث (عبر تحليل شجرة JSON + التعبير النمطي المرن) لاستخراج المنشورات الحية."""
  if not raw_html:
    return []

  posts = []
  seen_u = set()

  # 1) التحليل الشجري الكامل لجميع كتل <script type="application/json"> في الصفحة
  for m_script in re.finditer(
      r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
      raw_html,
      re.DOTALL | re.IGNORECASE,
  ):
    s_txt = m_script.group(1).strip()
    if len(s_txt) < 100 or not any(
        k in s_txt for k in ("message", "comet_sections", "pfbid", "story_fbid", "creation_time", "UzpfS")
    ):
      continue
    try:
      data_json = json.loads(s_txt)
      story_nodes = []
      _walk_comet_json_for_stories(data_json, story_nodes)
      for s_node in story_nodes:
        info = _extract_fields_from_story_dict(s_node, handle=handle, page_id=page_id)
        p_txt = _strip_fb_sidebar_noise(info["text"])
        p_url = clean_social_post_url(info["url"])
        if not p_txt or len(p_txt) < 14 or not p_url or p_url in seen_u:
          continue
        if not is_direct_social_post_url(p_url, "فيسبوك"):
          continue
        if not _is_fb_post_owned_by_target(
            p_url, handle=handle, page_id=page_id, page_official_name=page_official_name
        ):
          continue
        if not is_strictly_judicial_and_clean(
            p_txt, p_txt, p_url, t_kw, is_target=bool(t_info)
        ):
          continue
        raw_ts = str(info["timestamp"]) if info["timestamp"] else ""
        pub_str, pub_ts = extract_date_from_url_or_text(
            p_url, p_txt, raw_ts, fallback_offset_sec=1800
        )
        entry = {
            "title": p_txt[:115] + ("..." if len(p_txt) > 115 else ""),
            "url": p_url,
            "raw_snippet": p_txt,
            "source_name": source_badge,
            "platform": "فيسبوك",
            "pub_date": pub_str,
            "pub_timestamp": pub_ts,
            "image_url": info["image"] or page_avatar,
        }
        if t_info:
          _tag_custom_target_item(entry, t_info, source_badge)
        seen_u.add(p_url)
        posts.append(entry)
    except Exception:
      pass

  # 2) مسح احتياطي مرن يدعم الكائنات المتداخلة داخل "message" (مثل ranges/entity) في النصوص الخام
  unescaped = raw_html.replace("\\/", "/")
  for m_msg in re.finditer(
      r'"(?:message|savable_description)"\s*:\s*\{[\s\S]{0,2500}?"text"\s*:\s*"((?:[^"\\]|\\.){15,})"',
      raw_html,
  ):
    msg_txt = _strip_fb_sidebar_noise(decode_js_escaped_text(m_msg.group(1)))
    if not msg_txt or len(msg_txt) < 15:
      continue
    start_pos = max(0, m_msg.start() - 4000)
    end_pos = min(len(raw_html), m_msg.end() + 5000)
    window = raw_html[start_pos:end_pos].replace("\\/", "/")

    post_u = ""
    for u_pat in [
        r'"(?:permalink_url|wwwURL|url)"\s*:\s*"(https://www\.facebook\.com/[^"]+?/(?:posts|videos|photos|reel)/[^"]+)"',
        r'"(?:permalink_url|wwwURL|url)"\s*:\s*"(https://www\.facebook\.com/(?:permalink\.php|story\.php|reel/|watch/\?v=)[^"]+)"',
        r'(https://www\.facebook\.com/[^"\s<>\\]+/posts/pfbid[A-Za-z0-9]+)',
    ]:
      m_u = re.search(u_pat, window)
      if m_u:
        cand_u = clean_social_post_url(decode_js_escaped_text(m_u.group(1)))
        if is_direct_social_post_url(cand_u, "فيسبوك") and _is_fb_post_owned_by_target(
            cand_u, handle=handle, page_id=page_id, page_official_name=page_official_name
        ):
          post_u = cand_u
          break

    if not post_u:
      m_fid = re.search(
          r'(?:"(?:post_id|top_level_post_id|story_fbid)"\s*:\s*"|(pfbid[A-Za-z0-9]{16,}))(pfbid[A-Za-z0-9]+|\d{11,})?',
          window,
      )
      if m_fid:
        fid = (m_fid.group(1) or m_fid.group(2) or "").strip()
        if fid and len(fid) >= 10:
          if handle and not handle.startswith("fb_") and not handle.isdigit():
            post_u = f"https://www.facebook.com/{handle}/posts/{fid}"
          elif page_id:
            post_u = f"https://www.facebook.com/permalink.php?story_fbid={fid}&id={page_id}"

    if not post_u or post_u in seen_u:
      continue
    if not is_strictly_judicial_and_clean(
        msg_txt, msg_txt, post_u, t_kw, is_target=bool(t_info)
    ):
      continue

    m_ctime = re.search(r'"(?:creation_time|publish_time)"\s*:\s*(\d{10})', window)
    raw_ts_str = m_ctime.group(1) if m_ctime else ""

    post_img = page_avatar
    m_img = re.search(r'"uri"\s*:\s*"(https://scontent[^"]+)"', window)
    if m_img:
      cand_img = decode_js_escaped_text(m_img.group(1))
      if "p50x50" not in cand_img and "s50x50" not in cand_img:
        post_img = cand_img

    pub_str, pub_ts = extract_date_from_url_or_text(
        post_u, msg_txt, raw_ts_str, fallback_offset_sec=1800
    )
    entry = {
        "title": msg_txt[:115] + ("..." if len(msg_txt) > 115 else ""),
        "url": post_u,
        "raw_snippet": msg_txt,
        "source_name": source_badge,
        "platform": "فيسبوك",
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": post_img,
    }
    if t_info:
      _tag_custom_target_item(entry, t_info, source_badge)
    seen_u.add(post_u)
    posts.append(entry)

  return posts


def _extract_facebook_posts_from_raw_html(
    raw_html: str,
    canonical_fb_url: str,
    handle: str,
    page_id: str,
    t_info: dict,
    source_badge: str,
    page_avatar: str,
    t_kw: str,
    page_official_name: str = "",
) -> list:
  """استخراج روابط المنشورات المباشرة (pfbid, story_fbid, posts, videos, reel) المضمنة في كود صفحة فيسبوك."""
  if not raw_html:
    return []

  extracted_posts = _extract_comet_relay_posts_from_html(
      raw_html,
      handle,
      page_id,
      page_official_name,
      t_info,
      source_badge,
      page_avatar,
      t_kw,
  )
  seen_cand = {clean_social_post_url(p["url"]) for p in extracted_posts}

  discovered_links = []
  unescaped_html = raw_html.replace("\\/", "/")

  patterns = [
      r'https?://(?:www\.|m\.|web\.)?facebook\.com/[^"\'\s<>\\]+/(?:posts|videos|photos)/[^"\'\s<>\\]+',
      r'https?://(?:www\.|m\.|web\.)?facebook\.com/(?:permalink\.php|story\.php|photo\.php|photo/|watch/|reel/|share/[pvr]/)[^"\'\s<>\\]+',
      r'href=["\'](/(?:[^"\'\s<>]+/(?:posts|videos|photos)/[^"\'\s<>]+|(?:permalink\.php|story\.php|photo\.php|photo/|watch/|reel/|share/[pvr]/)[^"\'\s<>]+))["\']',
  ]
  for pat in patterns:
    for m in re.finditer(pat, unescaped_html, re.IGNORECASE):
      raw_cand = m.group(1) if m.lastindex else m.group(0)
      clean_u = clean_social_post_url(raw_cand)
      if (
          clean_u
          and clean_u not in seen_cand
          and is_direct_social_post_url(clean_u, "فيسبوك")
          and _is_fb_post_owned_by_target(clean_u, handle=handle, page_id=page_id, page_official_name=page_official_name)
      ):
        seen_cand.add(clean_u)
        discovered_links.append(clean_u)

  # استخراج أي معرف pfbid0 مباشر داخل الصفحة وبناء رابط المنشور منه
  for m_pfb in re.finditer(r"\b(pfbid0[A-Za-z0-9]{15,})\b", unescaped_html):
    pfb_id = m_pfb.group(1)
    if handle and not handle.startswith("fb_") and not handle.isdigit():
      cand_u = f"https://www.facebook.com/{handle}/posts/{pfb_id}"
    elif page_id:
      cand_u = f"https://www.facebook.com/permalink.php?story_fbid={pfb_id}&id={page_id}"
    else:
      continue
    clean_u = clean_social_post_url(cand_u)
    if clean_u not in seen_cand:
      seen_cand.add(clean_u)
      discovered_links.append(clean_u)

  for m_fbid in re.finditer(
      r'"(?:story_fbid|top_level_post_id|post_id)"\s*:\s*"(pfbid[A-Za-z0-9]+|\d{11,})"',
      unescaped_html,
  ):
    fid = m_fbid.group(1).strip()
    if handle and not handle.startswith("fb_") and not handle.isdigit():
      cand_u = f"https://www.facebook.com/{handle}/posts/{fid}"
    elif page_id:
      cand_u = f"https://www.facebook.com/permalink.php?story_fbid={fid}&id={page_id}"
    else:
      continue
    clean_u = clean_social_post_url(cand_u)
    if clean_u not in seen_cand and is_direct_social_post_url(clean_u, "فيسبوك"):
      seen_cand.add(clean_u)
      discovered_links.append(clean_u)

  for idx, post_u in enumerate(discovered_links[:10]):
    if is_stop_requested():
      break
    is_valid, final_text, post_img, resolved_u = _verify_and_enrich_fb_post_url(
        post_u,
        page_avatar=page_avatar,
        handle=handle,
        page_id=page_id,
        page_official_name=page_official_name,
    )
    if not is_valid or not final_text or len(final_text) < 15:
      continue
    if not is_strictly_judicial_and_clean(
        final_text, final_text, resolved_u, t_kw, is_target=bool(t_info)
    ):
      continue

    pub_str, pub_ts = extract_date_from_url_or_text(
        resolved_u, final_text, "", fallback_offset_sec=1800 + (idx * 600)
    )
    entry = {
        "title": final_text[:115] + ("..." if len(final_text) > 115 else ""),
        "url": resolved_u,
        "raw_snippet": final_text,
        "source_name": source_badge,
        "platform": "فيسبوك",
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": post_img,
    }
    if t_info:
      _tag_custom_target_item(entry, t_info, source_badge)
    extracted_posts.append(entry)

  return extracted_posts


def resolve_direct_facebook_post_url(
    snippet_text: str,
    title_text: str,
    handle: str = "",
    page_official_name: str = "",
    page_id: str = "",
) -> str:
  """البحث عن الرابط المباشر الحقيقي للمنشور والتأكد الصارم من ملكيته للصفحة المخصصة حصراً."""
  clean_snip = clean_display_text(snippet_text or title_text)
  if page_official_name:
    clean_snip = clean_snip.replace(page_official_name, "").strip(" -–—:|•.")

  if re.search(
      r"(?:يتابعها|تسجيل إعجاب|يتحدث عن هذا|likes\s*·|talking about this)",
      clean_snip,
      re.IGNORECASE,
  ) and len(clean_snip) < 110:
    return ""

  words = [
      w
      for w in re.findall(r"[\u0600-\u06FFa-zA-Z0-9]{2,}", clean_snip)
      if w.lower() not in {"facebook", "فيسبوك", "فايسبوك", "منشور", "صفحة"}
  ]
  if len(words) < 4:
    return ""

  quote_phrase = " ".join(words[:7])
  owner_tok = (
      handle
      if (handle and not handle.startswith("fb_"))
      else page_official_name
  )
  sq = f'site:facebook.com "{owner_tok}" "{quote_phrase}"'.strip()

  for item_res in _multi_engine_web_search(sq, platform="فيسبوك", max_results=6):
    cand_u = clean_social_post_url(item_res.get("url", ""))
    if is_direct_social_post_url(cand_u, "فيسبوك") and _is_fb_post_owned_by_target(
        cand_u, handle=handle, page_id=page_id
    ):
      return cand_u

  return ""


def _clean_social_page_title(raw_title: str) -> str:
  """تنظيف اسم الصفحة الرسمي المستخرج من og:title من اللواحق مثل | Facebook أو | Rabat أو - الصفحة الرئيسية."""
  t = clean_display_text(raw_title)
  if not t:
    return ""
  t = re.sub(
      r"\s*[-|•–—]\s*(?:Facebook|فيسبوك|فايسبوك|X|Twitter|TikTok|Instagram|LinkedIn|YouTube).*$",
      "",
      t,
      flags=re.IGNORECASE,
  ).strip()
  t = re.sub(
      r"\s+on\s+(?:Facebook|Reels|X|Twitter).*$", "", t, flags=re.IGNORECASE
  ).strip()
  if "|" in t:
    parts_pipe = [p.strip() for p in t.split("|") if p.strip()]
    if parts_pipe:
      t = parts_pipe[0]
  t = re.sub(
      r"\s*[-–—]\s*(?:الصفحة الرسمية|الصفحة الرئيسية|Home|Official Page|Officiel)\s*$",
      "",
      t,
      flags=re.IGNORECASE,
  ).strip()
  return t


def _scrape_social_custom_target(
    t_info: dict,
    t_kw: str,
    when_tag: str,
    ddg_tl: str,
    max_age_sec: int,
    seen_urls: set,
) -> list:
  results = []
  all_target_posts = []
  seen_target_urls = set()
  raw_u = t_info["raw_url"]
  domain = t_info["domain"] or "facebook.com"
  platform = t_info["platform"] if t_info["platform"] != "شامل" else "فيسبوك"
  handle = t_info.get("handle", "")
  cid = t_info.get("channel_id", "")
  name_hint = t_info.get("official_name_hint", "")
  is_name_target = bool(t_info.get("is_name_target", False))
  disp = t_info.get("display_label", domain)
  now_ts = time.time()

  # إذا كان الرابط المضاف أصلاً رابط منشور مباشر بعينه، نرصده مباشرة
  if not is_name_target and is_direct_social_post_url(raw_u, platform):
    clean_direct_u = clean_social_post_url(raw_u)
    p_img, p_body, _ = scrape_article_page_content_and_image(clean_direct_u)
    if p_body:
      pub_str, pub_ts = extract_date_from_url_or_text(
          clean_direct_u, p_body, "", fallback_offset_sec=900
      )
      direct_entry = {
          "title": p_body[:110] + ("..." if len(p_body) > 110 else ""),
          "url": clean_direct_u,
          "raw_snippet": p_body,
          "source_name": f"🎯 {disp}",
          "platform": platform,
          "pub_date": pub_str,
          "pub_timestamp": pub_ts,
          "image_url": p_img,
      }
      _tag_custom_target_item(direct_entry, t_info, f"🎯 {disp}")
      return [direct_entry]

  # 1) جلب بيانات الصفحة العامة عبر ترويسة facebookexternalhit الموثوقة
  page_official_name = name_hint
  page_description = ""
  page_avatar = ""
  page_raw_html = ""
  canonical_url = raw_u
  req_hdrs = FB_CRAWLER_HEADERS if platform == "فيسبوك" else DEFAULT_HEADERS

  if not is_name_target:
    try:
      rp = None
      hdr_list = FB_PREVIEW_BOT_HEADERS if platform == "فيسبوك" else [DEFAULT_HEADERS]
      for cand_h in hdr_list:
        try:
          r_try = requests.get(raw_u, headers=cand_h, timeout=7, allow_redirects=True)
          if r_try.status_code == 200 and r_try.text:
            rp = r_try
            # إذا وجدنا وسم meta refresh في صفحة فيسبوك نفك التوجيه منه فوراً
            m_ref = re.search(
                r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+content=["\'][^"\']*url=([^"\'>\s]+)',
                r_try.text[:15000],
                re.IGNORECASE,
            )
            if m_ref:
              ref_u = clean_social_post_url(html.unescape(m_ref.group(1)))
              if ref_u and "login" not in ref_u.lower() and ref_u != raw_u:
                r_try2 = requests.get(ref_u, headers=cand_h, timeout=7, allow_redirects=True)
                if r_try2.status_code == 200 and r_try2.text:
                  rp = r_try2
                  canonical_url = ref_u
            if "og:title" in rp.text[:30000] and "log in" not in rp.text[:5000].lower():
              break
        except Exception:
          pass
      if rp.status_code == 200 and rp.text:
        page_raw_html = rp.text
        if rp.url:
          unwrapped_rp_u = clean_social_post_url(rp.url)
          if unwrapped_rp_u and "login" not in unwrapped_rp_u.lower():
            canonical_url = unwrapped_rp_u

        m_og_u = re.search(
            r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
            rp.text[:35000],
            re.IGNORECASE,
        )
        if m_og_u:
          cand_og = clean_social_post_url(m_og_u.group(1))
          if cand_og and "login" not in cand_og.lower():
            canonical_url = cand_og

        re_parsed = parse_custom_target_identity(canonical_url)
        if re_parsed.get("handle") and not re_parsed["handle"].isdigit():
          handle = re_parsed["handle"]
        if re_parsed.get("channel_id") and not cid:
          cid = re_parsed["channel_id"]
        if re_parsed.get("official_name_hint") and not page_official_name:
          page_official_name = re_parsed["official_name_hint"]

        if not cid and platform == "فيسبوك":
          for id_pat in [
              r"fb://(?:page|profile)/(\d{6,})",
              r'"(?:page_id|delegate_page_id|entity_id|userID)"\s*:\s*"(\d{6,})"',
          ]:
            m_pid = re.search(id_pat, rp.text[:60000])
            if m_pid:
              cid = m_pid.group(1)
              break

        for t_pat in [
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
            r"<title>(.*?)</title>",
        ]:
          m_og_t = re.search(t_pat, rp.text[:35000], re.IGNORECASE | re.DOTALL)
          if m_og_t:
            cleaned_t = _clean_social_page_title(m_og_t.group(1))
            if (
                len(cleaned_t) >= 2
                and not any(
                    w in cleaned_t.lower()
                    for w in [
                        "log in",
                        "login",
                        "تسجيل الدخول",
                        "قم بتسجيل الدخول",
                        "not found",
                        "غير متوفر",
                    ]
                )
                and cleaned_t.lower() not in {"facebook", "فيسبوك", "فايسبوك"}
            ):
              page_official_name = cleaned_t
              break

        for d_pat in [
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        ]:
          m_og_d = re.search(d_pat, rp.text[:35000], re.IGNORECASE)
          if m_og_d:
            d_cand = clean_display_text(m_og_d.group(1))
            if len(d_cand) > 15:
              page_description = d_cand
              break

        for i_pat in [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        ]:
          m_og_img = re.search(i_pat, rp.text[:35000], re.IGNORECASE)
          if m_og_img:
            page_avatar = html.unescape(m_og_img.group(1).strip())
            break
    except Exception:
      pass

  source_badge = f"🎯 {page_official_name or handle or disp}"

  # 2) لصفحات فيسبوك: جلب المنشورات الحية غير المؤرشفة عبر أداة الخط الزمني (BigPipe) وعبر كود Comet Relay JSON المباشر
  if platform == "فيسبوك" and not is_name_target:
    fb_plugin_posts = _scrape_facebook_plugin_timeline(
        canonical_url,
        t_info,
        source_badge,
        page_avatar,
        t_kw,
        handle=handle,
        page_id=cid,
    )
    for p in fb_plugin_posts:
      u_p = clean_social_post_url(p["url"])
      if u_p not in seen_target_urls:
        seen_target_urls.add(u_p)
        all_target_posts.append(p)

    chrome_doc_headers = dict(DEFAULT_HEADERS)
    chrome_doc_headers.update({
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    })
    applebot_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
            "Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ar-MA,ar;q=0.9,fr;q=0.8,en;q=0.7",
    }
    raw_html_candidates = [page_raw_html] if page_raw_html else []
    fb_candidate_urls = [canonical_url]
    if handle and not handle.startswith("fb_") and not handle.isdigit():
      for u_var in [
          f"https://www.facebook.com/{handle}",
          f"https://web.facebook.com/{handle}?_rdc=1&_rdr",
      ]:
        if u_var not in fb_candidate_urls:
          fb_candidate_urls.append(u_var)
    elif cid:
      u_cid_var = f"https://www.facebook.com/profile.php?id={cid}"
      if u_cid_var not in fb_candidate_urls:
        fb_candidate_urls.append(u_cid_var)

    for target_fb_u in fb_candidate_urls[:2]:
      if len(raw_html_candidates) >= 3:
        break
      for cand_hdr in (chrome_doc_headers, applebot_headers):
        try:
          rc = requests.get(
              target_fb_u,
              headers=cand_hdr,
              cookies={"locale": "ar_AR"},
              timeout=9,
          )
          if rc.status_code == 200 and rc.text and len(rc.text) > 18000:
            raw_html_candidates.append(rc.text)
            if "comet_sections" in rc.text or "pfbid" in rc.text or "creation_time" in rc.text:
              break
        except Exception:
          pass

    for html_blob in raw_html_candidates:
      if not html_blob:
        continue
      html_direct_posts = _extract_facebook_posts_from_raw_html(
          html_blob,
          canonical_url,
          handle,
          cid,
          t_info,
          source_badge,
          page_avatar,
          t_kw,
          page_official_name=page_official_name,
      )
      for p in html_direct_posts:
        u_p = clean_social_post_url(p["url"])
        if u_p not in seen_target_urls:
          seen_target_urls.add(u_p)
          all_target_posts.append(p)

  # 3) لمنصة إكس (X/Twitter): فحص نقطة Syndication الرسمية الخاصة بالحساب نفسه (تعمل بالوقت الفعلي دون انتظار الأرشفة)
  if platform == "إكس" and handle and not is_name_target:
    synd_url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{urllib.parse.quote(handle)}"
    try:
      rs = requests.get(synd_url, headers=DEFAULT_HEADERS, timeout=9)
      if rs.status_code == 200 and rs.text:
        m_next = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            rs.text,
            re.DOTALL,
        )
        if m_next:
          next_data = json.loads(m_next.group(1))
          entries = (
              next_data.get("props", {})
              .get("pageProps", {})
              .get("timeline", {})
              .get("entries", [])
          )
          for ent in entries[:20]:
            tweet = ent.get("content", {}).get("tweet", {})
            if not tweet:
              continue
            t_id = str(tweet.get("id_str") or "").strip()
            full_txt = clean_display_text(
                tweet.get("full_text") or tweet.get("text") or ""
            )
            created_raw = tweet.get("created_at") or ""
            if not t_id or not full_txt:
              continue
            t_link = f"https://x.com/{handle}/status/{t_id}"
            if not is_strictly_judicial_and_clean(
                full_txt, full_txt, t_link, t_kw, is_target=True
            ):
              continue
            pub_str, pub_ts = extract_date_from_url_or_text(
                t_link, full_txt, created_raw, fallback_offset_sec=3600
            )
            t_img = page_avatar
            media_list = tweet.get("entities", {}).get("media", [])
            if media_list and isinstance(media_list, list):
              t_img = media_list[0].get("media_url_https") or t_img
            entry = {
                "title": full_txt[:115] + ("..." if len(full_txt) > 115 else ""),
                "url": t_link,
                "raw_snippet": full_txt,
                "source_name": source_badge,
                "platform": "إكس",
                "pub_date": pub_str,
                "pub_timestamp": pub_ts,
                "image_url": t_img,
            }
            _tag_custom_target_item(entry, t_info, source_badge)
            seen_target_urls.add(t_link)
            all_target_posts.append(entry)
    except Exception:
      pass

  # 3-ب) إذا حجب فيسبوك صفحة الهدف على خادم السحابة ولم نستخرج الاسم الرسمي للصفحة بعد، نستخرجه من نتائج البحث عن الرابط
  if platform == "فيسبوك" and not page_official_name and (handle or cid):
    probe_ident = handle if (handle and not handle.startswith("fb_")) else cid
    for p_res in _multi_engine_web_search(f'site:facebook.com "{probe_ident}"', platform="فيسبوك", max_results=5):
      cand_t = _clean_social_page_title(p_res.get("title", ""))
      if (
          cand_t
          and len(cand_t) >= 3
          and cand_t.lower() not in {"facebook", "فيسبوك", "فايسبوك", "log in", "login"}
      ):
        page_official_name = cand_t
        source_badge = f"🎯 {page_official_name}"
        break

  # 4) مسح شامل بالمعرف والاسم الرسمي معاً عبر عدة صيغ استعلام نظيفة متوافقة مع Bing وYahoo وDuckDuckGo
  target_queries = []
  if platform == "فيسبوك":
    if handle and not handle.startswith("fb_") and not handle.isdigit():
      target_queries.append(f'site:facebook.com "{handle}" {t_kw}'.strip())
      target_queries.append(f'"facebook.com/{handle}" {t_kw}'.strip())
      target_queries.append(f'site:facebook.com/{handle} {t_kw}'.strip())
    if page_official_name:
      target_queries.append(
          f'site:facebook.com "{page_official_name}" {t_kw}'.strip()
      )
      target_queries.append(
          f'facebook.com "{page_official_name}" {t_kw}'.strip()
      )
    if cid:
      target_queries.append(f'site:facebook.com "{cid}" {t_kw}'.strip())
      target_queries.append(f'facebook.com "{cid}" {t_kw}'.strip())
  else:
    if handle and not handle.startswith("fb_"):
      target_queries.append(f'site:{domain} "{handle}" {t_kw}'.strip())
      if platform == "إكس":
        target_queries.append(f'site:twitter.com "{handle}" {t_kw}'.strip())
    if page_official_name:
      target_queries.append(f'site:{domain} "{page_official_name}" {t_kw}'.strip())

  page_level_fallback_candidates = []

  for tq in target_queries[:6]:
    if is_stop_requested():
      break
    for entry in _multi_engine_web_search(
        tq, platform=platform, default_source=source_badge, max_results=18
    ):
      raw_entry_u = clean_social_post_url(entry.get("url", ""))
      if not raw_entry_u or raw_entry_u in seen_target_urls:
        continue

      entry["raw_snippet"] = _strip_fb_sidebar_noise(entry.get("raw_snippet", ""))
      entry["title"] = _strip_fb_sidebar_noise(entry.get("title", ""))

      if not is_direct_social_post_url(raw_entry_u, platform):
        if platform == "فيسبوك":
          resolved_u = resolve_direct_facebook_post_url(
              entry.get("raw_snippet", ""),
              entry.get("title", ""),
              handle=handle,
              page_official_name=page_official_name,
              page_id=cid,
          )
          if resolved_u and is_direct_social_post_url(resolved_u, "فيسبوك"):
            raw_entry_u = resolved_u
          else:
            # نحتفظ بالمنشورات المقتطفة من الخط الزمني للصفحة نفسها كخيار احتياطي إذا أخفى فيسبوك روابط pfbid الفردية عن محركات البحث
            u_low_check = raw_entry_u.lower()
            belongs_to_page_path = bool(
                (handle and not handle.startswith("fb_") and handle.lower() in u_low_check)
                or (cid and cid in u_low_check)
                or (page_official_name and normalize_arabic_for_dedup(page_official_name) in normalize_arabic_for_dedup(f"{entry.get('title', '')} {entry.get('raw_snippet', '')}"))
            )
            snip_cand = clean_display_text(entry.get("raw_snippet", ""))
            # إزالة ديباجة عدد المتابعين والإعجابات إن وجدت في بداية المقتطف
            snip_cand = re.sub(
                r"^.*?(?:talking about this|يتحدث عن هذا|تسجيل إعجاب|likes?\s*·)[^.]*[.·•-]?\s*",
                "",
                snip_cand,
                flags=re.IGNORECASE,
            ).strip()
            if belongs_to_page_path and len(snip_cand) >= 28:
              page_level_fallback_candidates.append((entry, snip_cand))
            continue
        else:
          continue

      if (
          platform == "إكس"
          and handle
          and not is_name_target
          and f"/{handle.lower()}/status/" not in raw_entry_u.lower()
      ):
        continue

      if raw_entry_u in seen_target_urls:
        continue

      if platform == "فيسبوك":
        is_ok, og_body, og_img, final_u = _verify_and_enrich_fb_post_url(
            raw_entry_u,
            page_avatar=page_avatar,
            handle=handle,
            page_id=cid,
            page_official_name=page_official_name,
        )
        if not is_ok:
          continue
        if og_body and len(og_body) >= 12:
          entry["raw_snippet"] = og_body
          entry["title"] = og_body[:115] + (
              "..." if len(og_body) > 115 else ""
          )
        else:
          # إذا واجه السيرفر جدار تسجيل الدخول في فيسبوك، ننظف عنوان البحث ونستخدم المقتطف المستخرج من محرك البحث
          cleaned_search_t = _clean_social_page_title(entry.get("title", ""))
          if entry["raw_snippet"] and len(entry["raw_snippet"]) >= 15:
            if not cleaned_search_t or len(cleaned_search_t) < 15 or cleaned_search_t == page_official_name:
              entry["title"] = entry["raw_snippet"][:115] + ("..." if len(entry["raw_snippet"]) > 115 else "")
            else:
              entry["title"] = cleaned_search_t
          elif cleaned_search_t and len(cleaned_search_t) >= 12:
            entry["title"] = cleaned_search_t
            entry["raw_snippet"] = cleaned_search_t
          else:
            continue
        if og_img:
          entry["image_url"] = og_img
        raw_entry_u = final_u

      entry["url"] = raw_entry_u
      if not is_strictly_judicial_and_clean(
          entry["title"],
          entry["raw_snippet"],
          entry["url"],
          t_kw,
          is_target=True,
      ):
        continue
      if not entry.get("image_url") and page_avatar:
        entry["image_url"] = page_avatar

      pub_str, pub_ts = extract_date_from_url_or_text(
          entry["url"],
          entry["raw_snippet"],
          entry.get("pub_date", ""),
          fallback_offset_sec=1800,
      )
      entry["pub_date"] = pub_str
      entry["pub_timestamp"] = pub_ts

      seen_target_urls.add(raw_entry_u)
      _tag_custom_target_item(entry, t_info, source_badge)
      all_target_posts.append(entry)

  # 4-ب) تفعيل المنشورات المستخلصة من مقتطفات الخط الزمني للصفحة المخصصة إذا أخفى فيسبوك روابط pfbid الفردية
  if not all_target_posts and page_level_fallback_candidates:
    for fb_ent, snip_cand in page_level_fallback_candidates[:10]:
      synth_u = _build_synthesized_fb_post_url(fb_ent.get("url", ""), snip_cand, fb_handle=handle)
      if synth_u in seen_target_urls:
        continue
      fb_ent["url"] = synth_u
      fb_ent["raw_snippet"] = snip_cand
      fb_ent["title"] = snip_cand[:115] + ("..." if len(snip_cand) > 115 else "")
      if not is_strictly_judicial_and_clean(fb_ent["title"], fb_ent["raw_snippet"], synth_u, t_kw, is_target=True):
        continue
      if not fb_ent.get("image_url") and page_avatar:
        fb_ent["image_url"] = page_avatar
      seen_target_urls.add(synth_u)
      _tag_custom_target_item(fb_ent, t_info, source_badge)
      all_target_posts.append(fb_ent)

  # 5) إذا حجب فيسبوك ومحركات البحث روابط pfbid المباشرة على خادم السحابة، نفحص خلاصات الأخبار الحية المقيدة حصرياً باسم الصفحة أو معرفها لاستخراج المنشورات والتصريحات الصادرة عنها
  if not all_target_posts and (page_official_name or (handle and not handle.startswith("fb_"))):
    ident_name = page_official_name or handle
    gnews_target_q = f'"{ident_name}" {t_kw} when:{when_tag}'.strip()
    gnews_t_url = (
        "https://news.google.com/rss/search?q="
        f"{urllib.parse.quote(gnews_target_q)}&hl=ar&gl=MA&ceid=MA:ar"
    )
    try:
      r_gt = requests.get(gnews_t_url, headers=DEFAULT_HEADERS, timeout=8)
      if r_gt.status_code == 200:
        for g_ent in parse_rss_xml(
            r_gt.content,
            platform,
            default_source=source_badge,
            fallback_offset=1800,
            max_age_sec=0,
        ):
          comb_g = normalize_arabic_for_dedup(f"{g_ent.get('title', '')} {g_ent.get('raw_snippet', '')}")
          ident_norm = normalize_arabic_for_dedup(ident_name)
          if ident_norm and len(ident_norm) >= 4 and ident_norm not in comb_g:
            continue
          if not is_strictly_judicial_and_clean(
              g_ent["title"], g_ent["raw_snippet"], g_ent["url"], t_kw, is_target=True
          ):
            continue
          if not g_ent.get("image_url") and page_avatar:
            g_ent["image_url"] = page_avatar
          _tag_custom_target_item(g_ent, t_info, source_badge)
          all_target_posts.append(g_ent)
    except Exception:
      pass

  all_target_posts.sort(
      key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
  )

  in_window = [
      e
      for e in all_target_posts
      if max_age_sec <= 0
      or (now_ts - float(e.get("pub_timestamp", 0))) <= max_age_sec
  ]
  chosen_list = in_window if in_window else all_target_posts[:12]
  for entry in chosen_list:
    if entry["url"] not in seen_urls:
      seen_urls.add(entry["url"])
      results.append(entry)

  return results


def _scrape_name_based_custom_target(
    t_info: dict,
    t_kw: str,
    when_tag: str,
    ddg_tl: str,
    max_age_sec: int,
    seen_urls: set,
) -> list:
  """رصد مخصص دقيق عند إدخال اسم القناة أو الصفحة (يجلب حصرياً فيديوهات القناة على يوتيوب ومنشورات الصفحة على فيسبوك الموثقة الملكية)."""
  results = []
  name_q = t_info.get("official_name_hint") or t_info.get("display_label", "")
  if not name_q:
    return results

  yt_t_info = dict(t_info)
  yt_t_info["platform"] = "يوتيوب"
  yt_items = _scrape_youtube_custom_channel(
      yt_t_info, t_kw, max_age_sec, seen_urls
  )
  results.extend(yt_items)

  fb_t_info = dict(t_info)
  fb_t_info["platform"] = "فيسبوك"
  fb_t_info["domain"] = "facebook.com"
  fb_items = _scrape_social_custom_target(
      fb_t_info, t_kw, when_tag, ddg_tl, max_age_sec, seen_urls
  )
  results.extend(fb_items)

  results.sort(key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True)
  return results


def scrape_custom_targets(
    targets: list,
    global_kw: str = "",
    search_period: str = "آخر 7 أيام",
    progress_cb=None,
):
  items = []
  seen_urls = set()
  valid_targets = [t for t in targets if t.get("url", "").strip()]
  if not valid_targets:
    return items

  p_cfg = get_period_config(search_period)
  when_tag = p_cfg["gnews"]
  ddg_tl = p_cfg["ddg"]
  max_age = p_cfg["sec"]

  for idx, target in enumerate(valid_targets):
    if is_stop_requested():
      break
    t_url = target["url"].strip()
    t_kw = target.get("keyword", "").strip()
    t_info = parse_custom_target_identity(t_url)
    if not t_info:
      continue

    if progress_cb:
      progress_cb(
          (idx + 1) / max(1, len(valid_targets)),
          f"رصد المصدر المخصص: {t_info['display_label']}...",
      )

    platform = t_info["platform"]
    if t_info.get("is_name_target") and platform == "شامل":
      items.extend(
          _scrape_name_based_custom_target(
              t_info, t_kw, when_tag, ddg_tl, max_age, seen_urls
          )
      )
    elif platform == "يوتيوب":
      items.extend(
          _scrape_youtube_custom_channel(t_info, t_kw, max_age, seen_urls)
      )
    elif platform == "الصحف":
      items.extend(
          _scrape_website_custom_target(
              t_info, t_kw, when_tag, max_age, seen_urls
          )
      )
    else:
      items.extend(
          _scrape_social_custom_target(
              t_info, t_kw, when_tag, ddg_tl, max_age, seen_urls
          )
      )

  return items


def scrape_platform_by_keyword(
    platform_name: str,
    keyword_input: str,
    search_period: str = "آخر 7 أيام",
    progress_cb=None,
) -> list:
  """رصد منصة معينة (مثل فيسبوك، الصحف، يوتيوب، إكس، أخرى، أو شامل) من خلال كلمة مفتاحية محددة وجلب كافة المنشورات المتعلقة بتلك الكلمة المفتاحية."""
  kw_clean = str(keyword_input or "").strip().strip('"\'«» ')
  if not kw_clean:
    return []

  plat = str(platform_name or "فيسبوك").strip()
  raw_collected = []

  if plat == "فيسبوك":
    raw_collected.extend(scrape_facebook_platform(kw_clean, search_period, progress_cb))
  elif plat == "الصحف":
    raw_collected.extend(scrape_moroccan_press(kw_clean, search_period, progress_cb))
  elif plat == "يوتيوب":
    raw_collected.extend(scrape_youtube_platform(kw_clean, search_period, progress_cb))
  elif plat == "إكس":
    raw_collected.extend(scrape_x_platform(kw_clean, search_period, progress_cb))
  elif plat == "أخرى":
    raw_collected.extend(scrape_other_platforms(kw_clean, search_period, progress_cb))
  else:
    steps_kw = [
        ("فيسبوك", lambda cb: scrape_facebook_platform(kw_clean, search_period, cb)),
        ("الصحف المغربية", lambda cb: scrape_moroccan_press(kw_clean, search_period, cb)),
        ("يوتيوب", lambda cb: scrape_youtube_platform(kw_clean, search_period, cb)),
        ("منصة إكس", lambda cb: scrape_x_platform(kw_clean, search_period, cb)),
        ("منصات أخرى", lambda cb: scrape_other_platforms(kw_clean, search_period, cb)),
    ]
    for s_idx, (_, s_fn) in enumerate(steps_kw):
      if is_stop_requested():
        break
      bp = s_idx / len(steps_kw)
      sp = 1.0 / len(steps_kw)
      raw_collected.extend(
          s_fn(
              lambda sub_p, msg, b=bp, s=sp: progress_cb(b + sub_p * s, msg)
              if progress_cb
              else None
          )
      )

  kw_tag = f"#kwtrack={urllib.parse.quote(kw_clean, safe='')}"
  verified_items = []
  seen_u = set()

  for it in raw_collected:
    if not isinstance(it, dict):
      continue
    t_str = clean_display_text(it.get("title") or "")
    s_str = clean_full_article_text(it.get("raw_snippet") or "")
    src_str = clean_display_text(it.get("source_name") or "")
    u_str = str(it.get("url") or "").strip()
    if not t_str or not u_str:
      continue
    if _has_inappropriate_terms(t_str, f"{s_str} {src_str}", u_str):
      continue
    if not is_strictly_judicial_and_clean(t_str, s_str, u_str, kw_clean, is_target=False):
      continue
    if "#kwtrack=" not in u_str:
      it["url"] = f"{u_str}{kw_tag}"
    canon_k = f"{it.get('platform', plat)}::{canonicalize_url_for_dedup(it['url']) or strip_internal_url_fragments(it['url'])}"
    if canon_k in seen_u:
      continue
    seen_u.add(canon_k)
    verified_items.append(it)

  verified_items.sort(key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True)
  return verified_items


# =====================================================================
# 10. تلخيص المحتوى الفعلي عبر Gemini API (مع دعم تعدد النماذج واستخلاص متن الخبر)
# =====================================================================
def _call_gemini_rest_or_sdk(prompt: str, api_key: str) -> str:
  global _WORKING_GEMINI_MODEL
  models_to_try = (
      [_WORKING_GEMINI_MODEL]
      + [m for m in GEMINI_MODELS_FALLBACK if m != _WORKING_GEMINI_MODEL]
      if _WORKING_GEMINI_MODEL
      else list(GEMINI_MODELS_FALLBACK)
  )

  for model_id in models_to_try:
    if not model_id:
      continue
    try:
      endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
      resp = requests.post(
          endpoint,
          json={
              "contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0.25, "maxOutputTokens": 350},
          },
          timeout=10,
      )
      if resp.status_code == 200:
        data = resp.json()
        txt = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        if txt:
          _WORKING_GEMINI_MODEL = model_id
          return txt.strip()
    except Exception:
      pass

    if genai is not None:
      try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_id)
        r_sdk = model.generate_content(prompt)
        if r_sdk and r_sdk.text:
          _WORKING_GEMINI_MODEL = model_id
          return r_sdk.text.strip()
      except Exception:
        pass

  return ""


def _pcm16_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 24000, channels: int = 1) -> bytes:
  """تحويل بيانات الصوت الخام PCM-16 الصادرة عن Gemini Native Audio API إلى ملف WAV قياسي جاهز للتشغيل في المتصفح."""
  buf = io.BytesIO()
  with wave.open(buf, "wb") as wf:
    wf.setnchannels(channels)
    wf.setsampwidth(2)
    wf.setframerate(sample_rate)
    wf.writeframes(pcm_bytes)
  return buf.getvalue()


def _strip_mp3_metadata_frames(mp3_data: bytes) -> bytes:
  """إزالة ترويسات ID3v2 و ID3v1 وإطارات Xing/Info VBR من مقاطع MP3 لضمان دمجها في ملف صوتي واحد متصل يُقرأ كاملاً دون توقف."""
  if not mp3_data or len(mp3_data) < 16:
    return mp3_data
  data = mp3_data
  while len(data) >= 10 and data[:3] == b"ID3":
    b6, b7, b8, b9 = data[6], data[7], data[8], data[9]
    tag_size = ((b6 & 0x7F) << 21) | ((b7 & 0x7F) << 14) | ((b8 & 0x7F) << 7) | (b9 & 0x7F)
    total_id3 = 10 + tag_size
    if len(data) > total_id3:
      data = data[total_id3:]
    else:
      break

  if len(data) > 128 and data[-128:-125] == b"TAG":
    data = data[:-128]

  if len(data) > 64:
    sync_idx = -1
    for i in range(min(512, len(data) - 4)):
      if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
        sync_idx = i
        break
    if sync_idx > 0:
      data = data[sync_idx:]
    first_window = data[:220]
    if b"Xing" in first_window or b"Info" in first_window or b"VBRI" in first_window:
      for j in range(36, min(650, len(data) - 4)):
        if data[j] == 0xFF and (data[j + 1] & 0xE0) == 0xE0 and (data[j + 1] & 0x18) != 0x08:
          data = data[j:]
          break
  return data


def prepare_arabic_text_for_speech(text: str, max_chars: int = 3800) -> str:
  """تنظيف وتجهيز النص العربي للقراءة الصوتية الإذاعية (إزالة الروابط والرموز المربكة للنطق مع الحفاظ على علامات الوقف)."""
  if not text:
    return ""
  t = clean_display_text(text)
  t = re.sub(r"https?://\S+", " ", t)
  t = re.sub(r"#\S+", " ", t)
  # إزالة الرموز التعبيرية والزخارف التي قد تربك محرك النطق
  t = re.sub(r"[🎯📰🟦⬛🟥🟪🌐🗄️📡📅📝🏷️🔗👁️📖🔊🎙️⚖️✨🛑✅⏳]", " ", t)
  t = re.sub(r"[«»\"'`~^*_\[\]{}<>|\\]", " ", t)
  t = re.sub(r"\s+", " ", t).strip()
  return t[:max_chars]


def _call_single_gemini_tts_chunk(chunk_text: str, api_key: str, model_id: str = "gemini-2.5-flash-preview-tts") -> tuple:
  """طلب توليد صوتي لمقطع نصي واحد عبر Gemini Native TTS API."""
  endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
  payload = {
      "contents": [{"parts": [{"text": chunk_text}]}],
      "generationConfig": {
          "responseModalities": ["AUDIO"],
          "speechConfig": {
              "voiceConfig": {
                  "prebuiltVoiceConfig": {"voiceName": "Aoede"}
              }
          },
      },
  }
  resp = requests.post(endpoint, json=payload, timeout=14)
  if resp.status_code == 200:
    data = resp.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    for p in parts:
      inline = p.get("inlineData") or p.get("inline_data")
      if inline and inline.get("data"):
        raw_audio = base64.b64decode(inline["data"])
        mime = str(inline.get("mimeType") or inline.get("mime_type") or "").lower()
        rate_m = re.search(r"rate=(\d+)", mime)
        sr = int(rate_m.group(1)) if rate_m else 24000
        return raw_audio, mime, sr
  return b"", "", 24000


def _vocalize_script_with_gemini(text: str, api_key: str) -> str:
  """استخدام مفتاح Gemini API العامل في المنصة لتشكيل الكلمات الأساسية وتحويل الأرقام والاختصارات لنص إذاعي عربي سليم النطق."""
  if not api_key or not text or len(text) > 900:
    return text
  prompt = (
      "أعد كتابة النص الإخباري التالي ليُقرأ صوتياً باللغة العربية الفصحى بإلقاء إذاعي واضح، "
      "مع وضع التشكيل الضروري على الكلمات التي قد تلتبس في النطق وتحويل الأرقام والتواريخ إلى كلمات عربية منطوقة، "
      "دون حذف أو تلخيص أي معلومة ودون إضافة أي مقدمات (أرجع النص المشكول الجاهز للقراءة فقط):\n\n"
      f"{text}"
  )
  try:
    global _WORKING_GEMINI_MODEL
    model_id = _WORKING_GEMINI_MODEL or "gemini-2.5-flash"
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
    resp = requests.post(
        endpoint,
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.15, "maxOutputTokens": 600},
        },
        timeout=4.5,
    )
    if resp.status_code == 200:
      cand = (
          resp.json()
          .get("candidates", [{}])[0]
          .get("content", {})
          .get("parts", [{}])[0]
          .get("text", "")
      )
      cleaned_cand = prepare_arabic_text_for_speech(cand, max_chars=1500)
      if len(cleaned_cand) >= int(len(text) * 0.65):
        return cleaned_cand
  except Exception:
    pass
  return text


def _fetch_single_tts_mp3_chunk(idx_and_chunk: tuple) -> tuple:
  """جلب مقطع صوتي MP3 واحد من عدة خوادم TTS عربية متوازية مع إزالة ترويسات ID3/Xing لضمان الاتصال السلس."""
  idx, ch = idx_and_chunk
  if not ch or not ch.strip():
    return idx, b""
  q_enc = urllib.parse.quote(ch.strip())
  endpoints = [
      f"https://translate.googleapis.com/translate_tts?client=gtx&ie=UTF-8&tl=ar&dt=t&q={q_enc}",
      f"https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=ar&q={q_enc}",
      f"https://translate.google.com.vn/translate_tts?ie=UTF-8&client=tw-ob&tl=ar&q={q_enc}",
      f"https://translate.google.com/translate_tts?ie=UTF-8&client=dict-chrome-ex&tl=ar&q={q_enc}",
      f"https://api.streamelements.com/kappa/v2/speech?voice=Zeina&text={q_enc}",
      f"https://texttospeech.responsivevoice.org/v1/text:synthesize?text={q_enc}&lang=ar&engine=g1&name=&pitch=0.5&rate=0.5&volume=1&key=0POmS5Y2&gender=male",
  ]
  tts_headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
      ),
      "Referer": "https://translate.google.com/",
      "Accept": "*/*",
  }
  for u in endpoints:
    try:
      r = requests.get(u, headers=tts_headers, timeout=5.0)
      if r.status_code == 200 and len(r.content) > 150:
        return idx, _strip_mp3_metadata_frames(r.content)
    except Exception:
      pass
  return idx, b""


def generate_gemini_or_server_tts_audio(text: str, api_key: str = "", mode: str = "summary") -> tuple:
  """توليد ملف صوتي عربي واضح ومتصل (WAV / MP3) لقراءة الملخص أو النص الأصلي الكامل عبر Gemini API المدمج + التوليد السحابي المتوازي."""
  max_len = 1200 if mode == "summary" else 3800
  speech_script = prepare_arabic_text_for_speech(text, max_chars=max_len)
  if not speech_script:
    return b"", ""

  key = str(api_key or "").strip()
  if not key:
    try:
      key = str(load_credentials().get("gemini_api_key") or "").strip()
    except Exception:
      key = ""

  rt = get_shared_runtime()
  cooldown_until = float(rt.get("gemini_tts_cooldown_until") or 0.0)

  # 1) المحاولة الأولى: استخدام Gemini Native TTS API (gemini-2.5-flash-preview-tts) بتقسيم متوازن يمنع انتهاء المهلة
  if key and time.time() >= cooldown_until:
    g_sents = [s.strip() for s in re.split(r"(?<=[.!؟،؛\n])\s+", speech_script) if s.strip()]
    g_chunks = []
    g_curr = ""
    for s in g_sents:
      if len(g_curr) + len(s) + 1 <= 550:
        g_curr = f"{g_curr} {s}".strip() if g_curr else s
      else:
        if g_curr:
          g_chunks.append(g_curr)
        g_curr = s[:550]
    if g_curr:
      g_chunks.append(g_curr)
    if not g_chunks:
      g_chunks = [speech_script[:550]]

    try:
      raw_0, mime_0, sr_0 = _call_single_gemini_tts_chunk(g_chunks[0], key, "gemini-2.5-flash-preview-tts")
      if raw_0:
        if "pcm" in mime_0 or "l16" in mime_0 or not mime_0:
          pcm_parts = [raw_0]
          for extra_ch in g_chunks[1:6]:
            r_ext, _, _ = _call_single_gemini_tts_chunk(extra_ch, key, "gemini-2.5-flash-preview-tts")
            if r_ext:
              pcm_parts.append(r_ext)
            else:
              break
          return _pcm16_to_wav_bytes(b"".join(pcm_parts), sample_rate=sr_0), "audio/wav"
        if "wav" in mime_0:
          return raw_0, "audio/wav"
        return raw_0, "audio/mpeg"
      else:
        rt["gemini_tts_cooldown_until"] = time.time() + 240
    except Exception:
      rt["gemini_tts_cooldown_until"] = time.time() + 240

  # 2) استخدام مفتاح Gemini API العامل في المنصة لتشكيل وتحسين النص الإذاعي قبل التوليد الصوتي المتوازي السريع
  if key and len(speech_script) <= 750:
    speech_script = _vocalize_script_with_gemini(speech_script, key)

  # 3) التوليد الصوتي المتوازي الفائق السرعة (ThreadPoolExecutor) مع دمج إطارات MP3 النظيفة بدون ترويسات قاطعة
  sentences = [s.strip() for s in re.split(r"(?<=[.!؟،؛:\n])\s+", speech_script) if s.strip()]
  chunks = []
  curr = ""
  for s in sentences:
    if len(curr) + len(s) + 1 <= 160:
      curr = f"{curr} {s}".strip() if curr else s
    else:
      if curr:
        chunks.append(curr)
      if len(s) <= 160:
        curr = s
      else:
        words = s.split()
        w_buf = ""
        for w in words:
          if len(w_buf) + len(w) + 1 <= 160:
            w_buf = f"{w_buf} {w}".strip() if w_buf else w
          else:
            if w_buf:
              chunks.append(w_buf)
            w_buf = w[:160]
        curr = w_buf
  if curr:
    chunks.append(curr)

  max_chunks = 10 if mode == "summary" else 26
  indexed_chunks = list(enumerate(chunks[:max_chunks]))
  if not indexed_chunks:
    return b"", ""

  ordered_results = {}
  with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(indexed_chunks))) as pool:
    for idx_res, mp3_part in pool.map(_fetch_single_tts_mp3_chunk, indexed_chunks):
      if mp3_part:
        ordered_results[idx_res] = mp3_part

  mp3_buffer = io.BytesIO()
  for idx_k in sorted(ordered_results.keys()):
    mp3_buffer.write(ordered_results[idx_k])

  mp3_bytes = mp3_buffer.getvalue()
  if mp3_bytes:
    return mp3_bytes, "audio/mpeg"
  return b"", ""


def ensure_verbatim_full_text_for_item(item: dict) -> str:
  """ضمان جلب وحفظ النص الأصلي الكامل للمقال حرفياً من المصدر الأصلي إذا كان المخزن سابقاً مجرد مقتطف قصير."""
  raw_full = clean_full_article_text(item.get("raw_snippet") or "")
  raw_sum = clean_display_text(item.get("summary") or "")
  raw_title = clean_display_text(item.get("title") or "")
  url = str(item.get("url") or "").strip()
  plat = item.get("platform") or "الصحف"
  src = item.get("source_name") or plat

  # إذا كان النص الأصلي طويلاً ومختلفاً عن الملخص، نعيده مباشرة كما هو حرفياً
  if (
      len(raw_full) >= 420
      and normalize_arabic_for_dedup(raw_full) != normalize_arabic_for_dedup(raw_sum)
      and normalize_arabic_for_dedup(raw_full) != normalize_arabic_for_dedup(raw_title)
  ):
    return raw_full

  # محاولة جلب النص الأصلي الكامل والرابط المباشر والصورة مباشرة من المصدر الأصلي أو واجهة WordPress للجريدة
  page_img, page_body, resolved_u = scrape_article_page_content_and_image(
      url, title_hint=raw_title, source_hint=src, domain_hint=item.get("source_domain_hint", "")
  )
  updated_any = False
  if page_body and len(page_body) > len(raw_full):
    raw_full = page_body
    item["raw_snippet"] = raw_full[:15000]
    updated_any = True
  valid_p_img = clean_and_validate_image_url(page_img, resolved_u or url, plat)
  if valid_p_img and not clean_and_validate_image_url(item.get("image_url", ""), url, plat):
    item["image_url"] = valid_p_img
    updated_any = True
  if resolved_u and "news.google.com" not in resolved_u and "news.google.com" in url:
    kept_tags = extract_internal_url_fragments(url)
    item["url"] = f"{strip_internal_url_fragments(resolved_u)}{kept_tags}"
    updated_any = True
  new_precise_src = format_precise_source_with_domain(
      item.get("source_name") or src, item.get("url") or url, plat, title_hint=raw_title
  )
  if new_precise_src != item.get("source_name"):
    item["source_name"] = new_precise_src
    updated_any = True
  if updated_any and item.get("id"):
    lock = get_db_lock()
    with lock:
      try:
        conn = _open_sqlite_conn()
        conn.execute(
            "UPDATE articles SET raw_snippet = ?, source_name = ?, image_url = ?, url = ? WHERE id = ?",
            (item.get("raw_snippet", raw_full), item.get("source_name", new_precise_src), item.get("image_url", ""), item.get("url", url), item["id"]),
        )
        conn.commit()
        conn.close()
      except Exception:
        pass

  return raw_full


def analyze_with_gemini(item: dict, api_key: str):
  title = clean_display_text(item.get("title", ""))
  snippet = clean_display_text(item.get("raw_snippet", "")) or title
  platform = item.get("platform", "الصحف")
  source_name = item.get("source_name", platform)

  fallback_summary = build_extractive_arabic_summary(
      title, snippet, platform, source_name
  )
  default_result = {
      "summary": fallback_summary,
      "sentiment": "محايد",
      "category": "شؤون قضائية",
      "relevance_score": 88,
  }

  if not api_key or not str(api_key).strip():
    return default_result

  prompt = (
      "أنت محلل إعلامي قضائي خبير بالمجلس الأعلى للسلطة القضائية بالمغرب.\n"
      "قم بقراءة عنوان وتفاصيل الخبر أو المنشور التالي، واكتب ملخصاً إخبارياً دقيقاً ومفصلاً "
      "في جملتين إلى ثلاث جمل بالعربية الفصحى يشرح الوقائع والتفاصيل والقرارات القضائية أو القانونية الواردة فيه.\n"
      "تحذير صارم: يُمنع منعاً باتاً إعادة كتابة العنوان نفسه كملخص أو الاكتفاء بعبارة يتناول موضوع كذا، بل لخّص المضمون والوقائع مباشرة.\n"
      "أرجع النتيجة بصيغة JSON فقط بالمفاتيح التالية:\n"
      '{"summary": "الملخص التفصيلي للوقائع هنا...", '
      '"sentiment": "إيجابي أو محايد أو سلبي", '
      '"category": "بلاغ رسمي أو محاكم وقضايا أو شؤون قضائية أو رأي ومتابعات", '
      '"relevance_score": 92}\n\n'
      f"المنصة والمصدر: {platform} - {source_name}\n"
      f"عنوان الخبر: {title}\n"
      f"متن وتفاصيل الخبر: {snippet[:1800]}"
  )

  txt = _call_gemini_rest_or_sdk(prompt, str(api_key).strip())
  if txt:
    try:
      m = re.search(r"\{.*\}", txt, re.DOTALL)
      if m:
        parsed = json.loads(m.group(0))
        ai_sum = clean_display_text(parsed.get("summary"))
        if ai_sum and not is_summary_just_title(title, ai_sum):
          return {
              "summary": ai_sum,
              "sentiment": (
                  clean_display_text(parsed.get("sentiment")) or "محايد"
              ),
              "category": (
                  clean_display_text(parsed.get("category")) or "شؤون قضائية"
              ),
              "relevance_score": int(parsed.get("relevance_score", 90)),
          }
      else:
        plain_ai = clean_display_text(txt)
        if len(plain_ai) > 40 and not is_summary_just_title(title, plain_ai):
          default_result["summary"] = plain_ai
    except Exception:
      pass

  return default_result



# =====================================================================
# 10-ب. التفريغ الصوتي لفيديوهات يوتيوب (متوافق 100% مع اللغة العربية الفصحى وخالٍ من الأخطاء) وإرسال الاستماع الصوتي لبوت تلغرام
# =====================================================================
_YT_TRANSCRIPT_CACHE = {}

_ARABIC_DARIJA_AND_ASR_CORRECTIONS = [
    (r"\bهادشي\b", "هذا الأمر"),
    (r"\bهاد\b", "هذا"),
    (r"\bهاذ\b", "هذا"),
    (r"\bهادي\b", "هذه"),
    (r"\bهذو\b", "هؤلاء"),
    (r"\bديال\b", "الخاص بـ"),
    (r"\bديالها\b", "الخاصة بها"),
    (r"\bديالو\b", "الخاص به"),
    (r"\bديالهم\b", "الخاص بهم"),
    (r"\bدابا\b", "الآن"),
    (r"\bباش\b", "لكي"),
    (r"\bعلاش\b", "لماذا"),
    (r"\bكيفاش\b", "كيف"),
    (r"\bوقتاش\b", "متى"),
    (r"\bفاش\b", "عندما"),
    (r"\bحيت\b", "لأن"),
    (r"\bلحقاش\b", "لأن"),
    (r"\bبزاف\b", "كثيراً"),
    (r"\bشويه\b", "قليلاً"),
    (r"\bشوية\b", "قليلاً"),
    (r"\bواش\b", "هل"),
    (r"\bغادي\b", "سوف"),
    (r"\bغادية\b", "سوف"),
    (r"\bكاين\b", "يوجد"),
    (r"\bكاينة\b", "توجد"),
    (r"\bكاينين\b", "يوجدون"),
    (r"\bماكاينش\b", "لا يوجد"),
    (r"\bمكاينش\b", "لا يوجد"),
    (r"\bماشي\b", "ليس"),
    (r"\bراه\b", "إن"),
    (r"\bزعما\b", "أي"),
    (r"\bخايب\b", "سيئ"),
    (r"\bمزيان\b", "جيد"),
    (r"\bمزيانة\b", "جيدة"),
    (r"\bبلي\b", "بأن"),
    (r"\bدارو\b", "قاموا بـ"),
    (r"\bقالو\b", "قالوا"),
    (r"\bأكدو\b", "أكدوا"),
    (r"\bاكدو\b", "أكدوا"),
    (r"\bكانو\b", "كانوا"),
    (r"\bجاو\b", "جاؤوا"),
    (r"\bمشاو\b", "ذهبوا"),
    (r"\bبغاو\b", "أرادوا"),
    (r"\bخصنا\b", "يجب علينا"),
    (r"\bخاصنا\b", "يجب علينا"),
    (r"\bخصو\b", "يجب عليه"),
    (r"\bخاصو\b", "يجب عليه"),
    (r"\bاللي\b", "الذي"),
    (r"\bلي\s+كان\b", "الذي كان"),
    (r"\bالقضائيه\b", "القضائية"),
    (r"\bقضائيه\b", "قضائية"),
    (r"\bالجنائيه\b", "الجنائية"),
    (r"\bجنائيه\b", "جنائية"),
    (r"\bالمدنيه\b", "المدنية"),
    (r"\bمدنيه\b", "مدنية"),
    (r"\bالنيابه\b", "النيابة"),
    (r"\bالعامه\b", "العامة"),
    (r"\bالمحكمه\b", "المحكمة"),
    (r"\bمحكمه\b", "محكمة"),
    (r"\bالابتدائيه\b", "الابتدائية"),
    (r"\bالاستئنافيه\b", "الاستئنافية"),
    (r"\bالاداريه\b", "الإدارية"),
    (r"\bالإداريه\b", "الإدارية"),
    (r"\bالتجاريه\b", "التجارية"),
    (r"\bالدستوريه\b", "الدستورية"),
    (r"\bالعداله\b", "العدالة"),
    (r"\bالمسطره\b", "المسطرة"),
    (r"\bالبديله\b", "البديلة"),
    (r"\bالعقوبه\b", "العقوبة"),
    (r"\bالمملكه\b", "المملكة"),
    (r"\bالمغربيه\b", "المغربية"),
    (r"\bمغربيه\b", "مغربية"),
    (r"\bالسلطه\b", "السلطة"),
    (r"\bالرئاسه\b", "الرئاسة"),
    (r"\bرئاسه\b", "رئاسة"),
    (r"\bالوزاره\b", "الوزارة"),
    (r"\bوزاره\b", "وزارة"),
    (r"\bالشرطه\b", "الشرطة"),
    (r"\bالضابطه\b", "الضابطة"),
    (r"\bالوطنيه\b", "الوطنية"),
    (r"\bالدوليه\b", "الدولية"),
    (r"\bالرسميه\b", "الرسمية"),
    (r"\bالقانونيه\b", "القانونية"),
    (r"\bالحقوقيه\b", "الحقوقية"),
    (r"\bالمؤسسه\b", "المؤسسة"),
    (r"\bالهيئه\b", "الهيئة"),
    (r"\bالغرفه\b", "الغرفة"),
    (r"\bالجلسه\b", "الجلسة"),
    (r"\bالقضيه\b", "القضية"),
    (r"\bقضيه\b", "قضية"),
    (r"\bشكايه\b", "شكاية"),
    (r"\bالشكايه\b", "الشكاية"),
    (r"\bالاعلى\b", "الأعلى"),
    (r"\bالاحكام\b", "الأحكام"),
    (r"\bالاحداث\b", "الأحداث"),
    (r"\bالامور\b", "الأمور"),
    (r"\bالامن\b", "الأمن"),
    (r"\bالامانه\b", "الأمانة"),
    (r"\bالاجراءات\b", "الإجراءات"),
    (r"\bالاصلاح\b", "الإصلاح"),
    (r"\bالافراج\b", "الإفراج"),
    (r"\bالاعتقال\b", "الاعتقال"),
    (r"\bاستئناف\b", "استئناف"),
    (r"\bالاستئناف\b", "الاستئناف"),
    (r"\bالي\s+(?=المحكمة|النيابة|المجلس|القضاء|السجن|الرباط|الدار)", "إلى "),
    (r"\bاكد\b", "أكد"),
    (r"\bاكدت\b", "أكدت"),
    (r"\bاوضح\b", "أوضح"),
    (r"\bاوضحت\b", "أوضحت"),
    (r"\bاشار\b", "أشار"),
    (r"\bاشارت\b", "أشارت"),
    (r"\bاعلن\b", "أعلن"),
    (r"\bاعلنت\b", "أعلنت"),
    (r"\bاصدر\b", "أصدر"),
    (r"\bاصدرت\b", "أصدرت"),
]


def _parse_yt_caption_payload(raw_text: str) -> str:
  """تحليل محتوى مسار الترجمة/التفريغ النصي من يوتيوب (سواء بصيغة JSON3 أو XML) ودمج الجمل بدون تكرار متداخل."""
  if not raw_text:
    return ""
  segments = []
  txt_strip = raw_text.strip()
  if txt_strip.startswith("{"):
    try:
      data = json.loads(txt_strip)
      for ev in data.get("events", []):
        if not isinstance(ev, dict):
          continue
        segs = ev.get("segs", [])
        if not isinstance(segs, list):
          continue
        line = "".join(str(s.get("utf8") or "") for s in segs if isinstance(s, dict)).strip()
        line = re.sub(r"\s+", " ", line)
        if line:
          segments.append(line)
    except Exception:
      pass

  if not segments and ("<text" in txt_strip or "<p " in txt_strip or "<s " in txt_strip):
    try:
      root = ET.fromstring(raw_text.encode("utf-8", errors="ignore"))
      for el in root.iter():
        if el.tag in ("text", "p") and el.text:
          line = html.unescape(el.text).strip()
          line = re.sub(r"\s+", " ", line)
          if line:
            segments.append(line)
    except Exception:
      for m_t in re.finditer(r"<text[^>]*>(.*?)</text>", raw_text, re.DOTALL | re.IGNORECASE):
        line = clean_display_text(m_t.group(1))
        if line:
          segments.append(line)

  if not segments:
    return ""

  # إزالة التكرار المتداخل بين مقاطع التفريغ التلقائي المتتالية في يوتيوب
  merged_words = []
  for seg in segments:
    w_list = seg.split()
    if not w_list:
      continue
    if not merged_words:
      merged_words.extend(w_list)
      continue
    overlap_len = 0
    max_check = min(len(w_list), len(merged_words), 8)
    for k in range(max_check, 0, -1):
      if merged_words[-k:] == w_list[:k]:
        overlap_len = k
        break
    merged_words.extend(w_list[overlap_len:])

  return " ".join(merged_words)


def _fetch_youtube_raw_captions(vid_id: str) -> str:
  """استخراج التفريغ النصي الخام (Captions / TimedText) لفيديو يوتيوب عبر عدة مسارات (YouTube Transcript API + InnerTube ANDROID/WEB + Watch HTML)."""
  vid = str(vid_id or "").strip()
  if not vid or len(vid) != 11:
    return ""

  # 1) محاولة عبر youtube_transcript_api إن كانت متوفرة في بيئة التشغيل
  try:
    from youtube_transcript_api import YouTubeTranscriptApi
    transcript_list = YouTubeTranscriptApi.list_transcripts(vid)
    for lang_codes in (["ar"], ["ar-MA", "ar-SA", "ar-EG"], ["fr", "en"]):
      try:
        tr = transcript_list.find_transcript(lang_codes)
        if not tr.language_code.startswith("ar") and tr.is_translatable:
          tr = tr.translate("ar")
        fetched = tr.fetch()
        if fetched:
          joined = " ".join(str(x.get("text") or "") for x in fetched if isinstance(x, dict))
          if len(joined.strip()) >= 40:
            return joined.strip()
      except Exception:
        continue
  except Exception:
    pass

  caption_tracks = []
  headers_json = dict(DEFAULT_HEADERS)
  headers_json["Content-Type"] = "application/json"

  # 2) استخراج مسارات captionTracks عبر واجهة YouTube InnerTube (ANDROID ثم WEB)
  for client_cfg in [
      {"clientName": "ANDROID", "clientVersion": "19.09.37", "androidSdkVersion": 30, "hl": "ar", "gl": "MA"},
      {"clientName": "WEB", "clientVersion": "2.20240726.00.00", "hl": "ar", "gl": "MA"},
  ]:
    try:
      rp = requests.post(
          "https://www.youtube.com/youtubei/v1/player?prettyPrint=false",
          json={"context": {"client": client_cfg}, "videoId": vid},
          headers=headers_json,
          cookies=YT_BYPASS_COOKIES,
          timeout=5.0,
      )
      if rp.status_code == 200 and rp.text:
        p_data = rp.json()
        tracks = (
            p_data.get("captions", {})
            .get("playerCaptionsTracklistRenderer", {})
            .get("captionTracks", [])
        )
        if isinstance(tracks, list) and tracks:
          caption_tracks = tracks
          break
    except Exception:
      pass

  # 3) استخراج captionTracks من صفحة الفيديو المباشرة watch?v= إذا لزم الأمر
  if not caption_tracks:
    try:
      rw = requests.get(
          f"https://www.youtube.com/watch?v={vid}&hl=ar",
          headers=DEFAULT_HEADERS,
          cookies=YT_BYPASS_COOKIES,
          timeout=5.0,
      )
      if rw.status_code == 200 and rw.text:
        m_ct = re.search(r'"captionTracks"\s*:\s*(\[.*?\])(?=\s*,\s*"audioTracks"|\s*\})', rw.text)
        if m_ct:
          caption_tracks = json.loads(m_ct.group(1))
    except Exception:
      pass

  if not caption_tracks:
    return ""

  # ترتيب المسارات بالأولوية: العربية اليدوية أولاً، ثم العربية التلقائية (asr)، ثم المسارات القابلة للترجمة للعربية
  selected_url = ""
  for tr in caption_tracks:
    if not isinstance(tr, dict):
      continue
    lc = str(tr.get("languageCode") or "").lower()
    kind = str(tr.get("kind") or "").lower()
    b_url = str(tr.get("baseUrl") or "").strip()
    if lc.startswith("ar") and kind != "asr" and b_url:
      selected_url = b_url
      break

  if not selected_url:
    for tr in caption_tracks:
      if not isinstance(tr, dict):
        continue
      lc = str(tr.get("languageCode") or "").lower()
      b_url = str(tr.get("baseUrl") or "").strip()
      if lc.startswith("ar") and b_url:
        selected_url = b_url
        break

  if not selected_url:
    for tr in caption_tracks:
      if not isinstance(tr, dict):
        continue
      b_url = str(tr.get("baseUrl") or "").strip()
      if b_url:
        selected_url = f"{b_url}&tlang=ar"
        break

  if not selected_url:
    return ""

  for fmt_suffix in ("&fmt=json3", ""):
    try:
      rc = requests.get(f"{selected_url}{fmt_suffix}", headers=DEFAULT_HEADERS, timeout=5.0)
      if rc.status_code == 200 and rc.text:
        parsed_txt = _parse_yt_caption_payload(rc.text)
        if len(parsed_txt) >= 30:
          return parsed_txt
    except Exception:
      pass

  return ""


def _deterministic_arabic_transcript_cleaner(
    raw_text: str, title: str = "", summary: str = "", source_name: str = ""
) -> str:
  """مدقق لغوي وقضائي حتمي يضمن خلو نص التفريغ الصوتي من الأخطاء الإملائية والرموز الأجنبية وتوافقه التام 100% مع اللغة العربية الفصحى."""
  base_txt = clean_full_article_text(raw_text)
  if not base_txt:
    base_txt = clean_full_article_text(f"{title}. {summary}")

  # 1) إزالة وسوم الضوضاء السمعية والرموز غير العربية والروابط والطوابع الزمنية
  base_txt = re.sub(r"https?://\S+|www\.\S+", " ", base_txt)
  base_txt = re.sub(
      r"\[\s*(?:موسيقى|تصفيق|ضحك|صمت|أغنية|غناء|music|applause|laughter|silence)\s*\]",
      " ",
      base_txt,
      flags=re.IGNORECASE,
  )
  base_txt = re.sub(r"[♪♫♬♩#@*_~^<>|\\]", " ", base_txt)
  base_txt = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", " ", base_txt)
  # إزالة الكلمات والحروف اللاتينية لضمان نص عربي خالص 100%
  base_txt = re.sub(r"[A-Za-z]+", " ", base_txt)
  base_txt = base_txt.translate(_EASTERN_ARABIC_DIGITS_MAP)

  # 2) تصحيح الأخطاء الإملائية الشائعة في التفريغ التلقائي (مع دعم اللواصق العربية و/ف/ب/ل/ك) وتحويل الألفاظ الدارجة إلى العربية الفصحى السليمة
  for pat_rx, repl_ar in _ARABIC_DARIJA_AND_ASR_CORRECTIONS:
    base_txt = re.sub(pat_rx, repl_ar, base_txt, flags=re.IGNORECASE)
    # دعم اتصال حروف العطف والجر (و، ف، ب، ل، ك) بالكلمات المعرفة بـ (الـ)
    if pat_rx.startswith(r"\bال") and repl_ar.startswith("ال"):
      stem_pat = pat_rx[4:]
      stem_repl = repl_ar[2:]
      base_txt = re.sub(rf"\b([وفبكل]{{1,2}})ال{stem_pat}", rf"\1ال{stem_repl}", base_txt)
      # حالة حرف اللام المدمج مع الـ التعريف مثل: للسلطه -> للسلطة، للنيابه -> للنيابة، للمحكمه -> للمحكمة
      base_txt = re.sub(rf"\b([وفب]?)لل{stem_pat}", rf"\1لل{stem_repl}", base_txt)
    elif pat_rx.startswith(r"\b") and not pat_rx.startswith(r"\bال"):
      stem_pat_no_al = pat_rx[2:]
      base_txt = re.sub(rf"\b([وفبكل]){stem_pat_no_al}", rf"\1{repl_ar}", base_txt)

  # تصحيح شامل لنهايات النسب والصفة المؤنثة المنتهية بـ (يه) بدلاً من (ية) في التفريغ الصوتي التلقائي (باستثناء ضمير الغائب مثل: فيه، عليه، إليه، لديه، يليه، نبيه، فقيه، وجيه، شبيه، كريه، سفيه، نزيه، بديه، تيه، يتيه)
  _excluded_yah_words = {
      "فيه", "عليه", "إليه", "اليه", "لديه", "يليه", "تليه", "نبيه", "فقيه",
      "وجيه", "شبيه", "كريه", "سفيه", "نزيه", "بديه", "تيه", "يتيه", "أبيه",
      "ابيه", "أخيه", "اخيه", "بنيه", "ذويه", "مشتبه", "ينتبه", "تشابه",
  }
  def _fix_feminine_yah(m_obj):
    w_full = m_obj.group(0)
    if w_full in _excluded_yah_words or w_full.lstrip("وفبكل") in _excluded_yah_words:
      return w_full
    return w_full[:-1] + "ة"
  base_txt = re.sub(r"\b[\u0600-\u06FF]{3,}يه\b", _fix_feminine_yah, base_txt)

  # 3) إزالة تكرار الكلمات أو العبارات المتتالية الناتج عن التلعثم الصوتي (ASR Stutter Removal)
  words = [w for w in re.split(r"\s+", base_txt) if w.strip()]
  cleaned_words = []
  i = 0
  n = len(words)
  while i < n:
    # فحص تكرار عبارة من كلمتين أو 3 كلمات متتالية
    if i + 5 < n and words[i : i + 3] == words[i + 3 : i + 6]:
      cleaned_words.extend(words[i : i + 3])
      i += 6
      continue
    if i + 3 < n and words[i : i + 2] == words[i + 2 : i + 4]:
      cleaned_words.extend(words[i : i + 2])
      i += 4
      continue
    if cleaned_words and words[i] == cleaned_words[-1]:
      i += 1
      continue
    cleaned_words.append(words[i])
    i += 1

  joined = " ".join(cleaned_words)
  # الاحتفاظ فقط بالحروف العربية والأرقام وعلامات الترقيم العربية المعتمدة
  joined = re.sub(r"[^\u0600-\u06FF0-9\s.,،؛:؟!()«»\-]", " ", joined)
  joined = re.sub(r"\s+", " ", joined).strip()

  if not joined or len(re.findall(r"[\u0600-\u06FF]", joined)) < 15:
    t_ar = re.sub(r"[A-Za-z]+", " ", clean_display_text(title))
    s_ar = re.sub(r"[A-Za-z]+", " ", clean_display_text(summary))
    joined = f"{t_ar}. {s_ar}".strip()
    for pat_rx, repl_ar in _ARABIC_DARIJA_AND_ASR_CORRECTIONS:
      joined = re.sub(pat_rx, repl_ar, joined, flags=re.IGNORECASE)

  # 4) تقسيم النص إلى جمل وفقرات عربية فصيحة متناسقة ومضبوطة الترقيم
  words_final = joined.split()
  if len(words_final) <= 35:
    if not joined.endswith((".", "!", "؟")):
      joined += "."
    return joined

  paragraphs = []
  curr_para = []
  curr_sent = []
  sentence_enders = {".", "!", "؟", "؛"}
  discourse_connectors = {
      "وأكد", " وأكدت", "وأوضح", "وأوضحت", "وأشار", "وأشارت",
      "وأضاف", "وأضافت", "كما", "وفي", "ومن", "وعلى", "حيث", "وذلك",
      "هذا", "وقد", "إلى", "من", "في",
  }

  for idx_w, w in enumerate(words_final):
    curr_sent.append(w)
    ends_punct = any(w.endswith(p) for p in sentence_enders)
    if ends_punct or (len(curr_sent) >= 22 and w in discourse_connectors):
      if not ends_punct:
        # نضع فاصلة أو نقطة قبل أداة الربط لبناء جملة عربية سليمة
        last_w = curr_sent.pop()
        sent_str = " ".join(curr_sent).strip(" ،.") + "،"
        curr_para.append(sent_str)
        curr_sent = [last_w]
      else:
        curr_para.append(" ".join(curr_sent))
        curr_sent = []
      if len(" ".join(curr_para)) >= 320:
        para_txt = " ".join(curr_para).strip()
        if para_txt.endswith("،"):
          para_txt = para_txt[:-1] + "."
        elif not any(para_txt.endswith(p) for p in sentence_enders):
          para_txt += "."
        paragraphs.append(para_txt)
        curr_para = []

  if curr_sent:
    curr_para.append(" ".join(curr_sent))
  if curr_para:
    para_txt = " ".join(curr_para).strip()
    if para_txt.endswith("،"):
      para_txt = para_txt[:-1] + "."
    elif not any(para_txt.endswith(p) for p in sentence_enders):
      para_txt += "."
    paragraphs.append(para_txt)

  return "\n\n".join(paragraphs)


def _refine_or_transcribe_yt_with_gemini(
    vid_id: str,
    title: str,
    summary: str,
    source_name: str,
    raw_captions: str,
    raw_desc: str,
    api_key: str,
) -> str:
  """استخدام Gemini AI لتوليد أو تدقيق التفريغ الصوتي للفيديو بحيث يكون خالياً من الأخطاء 100% ومتوافقاً كلياً مع اللغة العربية الفصحى."""
  if not api_key or not str(api_key).strip():
    return ""

  key = str(api_key).strip()
  video_url = f"https://www.youtube.com/watch?v={vid_id}" if vid_id else ""

  system_rules = (
      "أنت مدقق لغوي ومحرر قضائي خبير بالمرصد القضائي بالمغرب.\n"
      "المهمة: تقديم التفريغ الصوتي الكامل لمضمون هذا الفيديو باللغة العربية الفصحى السليمة 100%، "
      "بحيث يكون النص خالياً تماماً من أي أخطاء إملائية أو نحوية أو مطبعية أو ركاكة، وخالياً من أي حروف أو كلمات أجنبية.\n"
      "القواعد الإلزامية الصارمة:\n"
      "1. إذا تضمن الكلام المنطوق في الفيديو أي عبارات باللهجة العامية/الدارجة أو أخطاء نطق، قم بصياغتها وتحويلها فوراً إلى لغة عربية فصحى رصينة ومضبوطة 100% مع الحفاظ الكامل والأمين على جميع الوقائع والأفكار والأسماء والصفات القضائية والتواريخ.\n"
      "2. اضبط همزات القطع والوصل والتاء المربوطة والهاء والمصطلحات القضائية والقانونية وعلامات الترقيم العربية (الفواصل والنقاط) وقسّم النص إلى فقرات واضحة.\n"
      "3. أرجع نص التفريغ الصوتي باللغة العربية الفصحى مباشرة دون أي مقدمات أو تعليقات جانبية."
  )

  # أ) إذا لم يتوفر مسار ترجمة نصي جاهز ولدينا رابط فيديو يوتيوب، نطلب من Gemini تفريغ الفيديو صوتياً مباشرة (Multimodal Video Understanding)
  if (not raw_captions or len(raw_captions) < 80) and video_url:
    for m_id in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"):
      try:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{m_id}:generateContent?key={key}"
        mm_prompt = (
            f"{system_rules}\n\n"
            f"عنوان الفيديو: {title}\n"
            f"القناة الناشرة: {source_name}\n"
            f"معطيات إضافية: {raw_desc[:1500]}\n\n"
            "قم بتفريغ منطوق ومضمون هذا الفيديو تفريغاً صوتياً نصياً كاملاً باللغة العربية الفصحى السليمة 100% الخالية من الأخطاء:"
        )
        payload = {
            "contents": [{
                "parts": [
                    {"fileData": {"mimeType": "video/*", "fileUri": video_url}},
                    {"text": mm_prompt},
                ]
            }],
            "generationConfig": {"temperature": 0.15, "maxOutputTokens": 2048},
        }
        resp = requests.post(endpoint, json=payload, timeout=18)
        if resp.status_code == 200:
          cand_txt = (
              resp.json()
              .get("candidates", [{}])[0]
              .get("content", {})
              .get("parts", [{}])[0]
              .get("text", "")
          )
          if cand_txt and len(cand_txt.strip()) >= 80:
            return cand_txt.strip()
      except Exception:
        pass

  # ب) تدقيق وتحرير التفريغ الخام ومعلومات الفيديو عبر Gemini النصي السريع
  source_material = raw_captions if len(raw_captions) >= 60 else f"{raw_captions}\n{raw_desc}\n{summary}"
  text_prompt = (
      f"{system_rules}\n\n"
      f"عنوان الفيديو: {title}\n"
      f"القناة: {source_name}\n"
      f"النص الخام للتفريغ الصوتي ومضمون الفيديو:\n{source_material[:9000]}\n\n"
      "اكتب النص الكامل للتفريغ الصوتي بعد تصحيحه وتدقيقه ليكون متوافقاً 100% مع اللغة العربية الفصحى وخالياً تماماً من الأخطاء:"
  )
  try:
    for m_id in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"):
      endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{m_id}:generateContent?key={key}"
      resp = requests.post(
          endpoint,
          json={
              "contents": [{"parts": [{"text": text_prompt}]}],
              "generationConfig": {"temperature": 0.15, "maxOutputTokens": 2048},
          },
          timeout=14,
      )
      if resp.status_code == 200:
        cand_txt = (
            resp.json()
            .get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        if cand_txt and len(cand_txt.strip()) >= 60:
          return cand_txt.strip()
  except Exception:
    pass

  return ""


def transcribe_youtube_video_to_perfect_arabic(item: dict, api_key: str = "") -> str:
  """توليد التفريغ الصوتي الكامل لفيديو يوتيوب مضبوطاً 100% باللغة العربية الفصحى السليمة وخالياً من الأخطاء."""
  if not isinstance(item, dict):
    return ""
  raw_url = clean_social_post_url(item.get("url") or "")
  m_yt = re.search(
      r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
      raw_url,
  )
  vid_id = m_yt.group(1) if m_yt else ""
  cache_k = vid_id or get_stable_article_id(item)
  if cache_k in _YT_TRANSCRIPT_CACHE and len(_YT_TRANSCRIPT_CACHE[cache_k]) >= 60:
    return _YT_TRANSCRIPT_CACHE[cache_k]

  raw_title = clean_display_text(item.get("title") or "")
  raw_summary = clean_display_text(item.get("summary") or "")
  raw_src = clean_display_text(item.get("source_name") or "يوتيوب")
  raw_desc = clean_full_article_text(item.get("raw_snippet") or "")

  # جلب الوصف الكامل للفيديو من بيانات يوتيوب الرسمية إن كان قصيراً
  if vid_id and len(raw_desc) < 180:
    yt_meta = fetch_youtube_video_exact_metadata(vid_id)
    if yt_meta.get("short_desc") and len(yt_meta["short_desc"]) > len(raw_desc):
      raw_desc = yt_meta["short_desc"]

  # 1) سحب التفريغ الصوتي الخام من مسارات الفيديو في يوتيوب
  raw_captions = _fetch_youtube_raw_captions(vid_id) if vid_id else ""

  # 2) إذا كان الفيديو لا يحتوي على مسار ترجمة مضمن، نبحث أيضاً عن أي تغطية نصية مطابقة لعنوان الفيديو لإثراء المحتوى
  if not raw_captions and len(raw_desc) < 220 and raw_title:
    _, b_desc, _ = fetch_bing_news_enrichment(raw_title, raw_src)
    if b_desc and len(b_desc) > len(raw_desc):
      raw_desc = f"{raw_desc}\n\n{b_desc}".strip()

  key = str(api_key or "").strip()
  if not key:
    try:
      key = str(load_credentials().get("gemini_api_key") or "").strip()
    except Exception:
      key = ""

  # 3) التدقيق اللغوي والتحرير الكامل عبر Gemini AI (إن توفر المفتاح) ثم المصفاة اللغوية العربية الحتمية 100%
  ai_transcript = ""
  if key:
    ai_transcript = _refine_or_transcribe_yt_with_gemini(
        vid_id, raw_title, raw_summary, raw_src, raw_captions, raw_desc, key
    )

  candidate_text = ai_transcript if len(ai_transcript) >= 60 else (raw_captions if len(raw_captions) >= 50 else f"{raw_title}.\n\n{raw_desc}\n\n{raw_summary}")
  final_arabic_transcript = _deterministic_arabic_transcript_cleaner(
      candidate_text, title=raw_title, summary=raw_summary, source_name=raw_src
  )

  # حفظ التفريغ الصوتي المدقق في الذاكرة وقاعدة البيانات
  if final_arabic_transcript:
    _YT_TRANSCRIPT_CACHE[cache_k] = final_arabic_transcript
    item["raw_snippet"] = final_arabic_transcript[:15000]
    if item.get("id"):
      lock = get_db_lock()
      with lock:
        try:
          conn = _open_sqlite_conn()
          conn.execute(
              "UPDATE articles SET raw_snippet = ? WHERE id = ?",
              (item["raw_snippet"], item["id"]),
          )
          conn.commit()
          conn.close()
        except Exception:
          pass

  return final_arabic_transcript


def send_telegram_audio_for_item(
    item: dict, cfg: dict, reply_to_message_id: int = 0, prebuilt_audio: tuple = None
) -> bool:
  """توليد وإرسال ملف 'الاستماع الصوتي' للأخبار النصية إلى بوت تلغرام لإتاحة الاستماع للخبر كخيار إضافي إلى جانب قراءة الخبر."""
  if not isinstance(item, dict):
    return False
  plat = clean_display_text(item.get("platform") or "الصحف")
  clean_u = clean_social_post_url(item.get("url") or "")
  # لا نرسل استماعاً صوتياً لفيديوهات يوتيوب لأنها فيديو أصلاً
  if plat == "يوتيوب" or "youtube.com" in clean_u.lower() or "youtu.be" in clean_u.lower():
    return False

  token = (cfg.get("telegram_bot_token") or DEFAULT_TG_TOKEN).strip()
  chat_id = (cfg.get("telegram_chat_id") or DEFAULT_TG_CHAT_ID).strip()
  if not token or not chat_id:
    return False

  raw_title = clean_display_text(item.get("title") or "")
  raw_summary = clean_display_text(item.get("summary") or "")
  raw_snip = clean_display_text(item.get("raw_snippet") or "")
  precise_src = format_precise_source_with_domain(
      item.get("source_name") or plat, clean_u, plat, title_hint=raw_title
  )
  if is_summary_just_title(raw_title, raw_summary):
    raw_summary = build_extractive_arabic_summary(raw_title, raw_snip, plat, precise_src)

  api_key = (cfg.get("gemini_api_key") or "").strip()
  if prebuilt_audio and isinstance(prebuilt_audio, tuple) and len(prebuilt_audio) == 2 and prebuilt_audio[0]:
    audio_bytes, mime_t = prebuilt_audio
  else:
    body_for_speech = raw_summary
    if raw_snip and len(raw_snip) > len(raw_summary) + 40 and normalize_arabic_for_dedup(raw_snip[:80]) != normalize_arabic_for_dedup(raw_summary[:80]):
      body_for_speech = f"{raw_summary}. {raw_snip[:900]}"
    speech_script = f"المرصد القضائي. {raw_title}. المصدر: {precise_src}. تفاصيل الخبر: {body_for_speech}"
    audio_bytes, mime_t = generate_gemini_or_server_tts_audio(
        speech_script, api_key=api_key, mode="summary"
    )

  if not audio_bytes or len(audio_bytes) < 150:
    return False

  ext = "wav" if "wav" in str(mime_t).lower() else "mp3"
  mime_clean = "audio/wav" if ext == "wav" else "audio/mpeg"
  file_name = f"المرصد_القضائي_استماع_صوتي.{ext}"
  caption_txt = (
      f"🎧 الاستماع الصوتي للخبر — المرصد القضائي\n"
      f"📌 {raw_title[:120]}\n"
      f"🌐 المصدر: {precise_src}"
  )
  data_payload = {
      "chat_id": chat_id,
      "title": f"🎧 الاستماع الصوتي: {raw_title[:60]}",
      "performer": "المرصد القضائي",
      "caption": caption_txt[:1000],
  }
  if reply_to_message_id and int(reply_to_message_id) > 0:
    data_payload["reply_to_message_id"] = int(reply_to_message_id)

  try:
    r_aud = requests.post(
        f"https://api.telegram.org/bot{token}/sendAudio",
        data=data_payload,
        files={"audio": (file_name, audio_bytes, mime_clean)},
        timeout=14,
    )
    if r_aud.status_code == 200:
      return True
  except Exception:
    pass

  # احتياطي عبر sendVoice إذا تطلب الأمر
  try:
    r_vc = requests.post(
        f"https://api.telegram.org/bot{token}/sendVoice",
        data={"chat_id": chat_id, "caption": caption_txt[:1000]},
        files={"voice": (file_name, audio_bytes, mime_clean)},
        timeout=14,
    )
    return r_vc.status_code == 200
  except Exception:
    return False


def send_telegram_alert(item: dict, cfg: dict) -> bool:
  """إرسال إشعار تلغرام مرة واحدة فقط لكل خبر جديد بعد التحقق الصارم من سجل الإرسال الدائم."""
  token = (cfg.get("telegram_bot_token") or DEFAULT_TG_TOKEN).strip()
  chat_id = (cfg.get("telegram_chat_id") or DEFAULT_TG_CHAT_ID).strip()
  if not token or not chat_id:
    return False

  item_keys = compute_article_dedup_keys(item.get("title", ""), item.get("url", ""))
  lock = get_db_lock()
  with lock:
    ledger = load_telegram_sent_ledger()
    if int(item.get("telegram_sent", 0)) == 1 or (item_keys & ledger):
      return False
    # فحص إضافي مباشر في قاعدة البيانات للتأكد من عدم إرسال أي خبر مطابق في العنوان أو الرابط مسبقاً
    try:
      conn_chk = _open_sqlite_conn()
      c_chk = conn_chk.cursor()
      c_chk.execute("SELECT title, url FROM articles WHERE telegram_sent = 1")
      for sent_t, sent_u in c_chk.fetchall():
        sent_k = compute_article_dedup_keys(sent_t or "", sent_u or "")
        if item_keys & sent_k:
          ledger.update(item_keys)
          save_telegram_sent_ledger(ledger)
          conn_chk.close()
          return False
      conn_chk.close()
    except Exception:
      pass
    # نحجز بصمة الخبر فوراً في السجل قبل الإرسال لمنع أي خيط متزامن من إرساله مرة ثانية
    ledger.update(item_keys)
    save_telegram_sent_ledger(ledger)

  platform_icons = {
      "الصحف": "📰",
      "فيسبوك": "🟦",
      "إكس": "⬛",
      "يوتيوب": "🟥",
      "أخرى": "🟪",
  }
  icon = platform_icons.get(item.get("platform", "الصحف"), "📡")
  target_badge = "🎯 [رصد مخصص]\n" if item.get("is_custom_target") else ""
  monitored_dt = datetime.fromtimestamp(
      float(item.get("created_at") or time.time()), tz=timezone.utc
  ).strftime("%Y-%m-%d %H:%M")
  clean_u = clean_social_post_url(item.get("url", ""))
  plat_tg = item.get("platform", "الصحف")
  precise_src_tg = format_precise_source_with_domain(
      item.get("source_name", plat_tg), clean_u, plat_tg, title_hint=item.get("title", "")
  )
  ensure_telegram_bot_branding_updated(token, chat_id)
  msg = (
      f"⚖️ *المرصد القضائي*\n"
      f"{target_badge}"
      f"{icon} *المنصة:* {plat_tg} | *المصدر:* {precise_src_tg}\n"
      f"📅 *تاريخ النشر:* {item.get('pub_date', '')}\n"
      f"📡 *تاريخ الرصد:* {monitored_dt}\n"
      f"📌 *العنوان:* {item.get('title', '')}\n\n"
      f"📝 *الملخص:* {item.get('summary', '')}\n\n"
      f"🏷️ *التصنيف:* {item.get('category', '')}\n"
      f"🔗 [فتح المصدر الأصلي]({clean_u})"
  ).replace("المرصد الوطني للعدالة والقضاء", "المرصد القضائي").replace("المرصد الوطني", "المرصد القضائي")
  try:
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        },
        timeout=8,
    )
    if resp.status_code == 200:
      sent_msg_id = 0
      try:
        sent_msg_id = int(resp.json().get("result", {}).get("message_id") or 0)
      except Exception:
        sent_msg_id = 0
      # إرسال "الاستماع الصوتي" للأخبار النصية (غير فيديوهات يوتيوب) إلى بوت تلغرام كخيار إضافي إلى جانب قراءة الخبر
      if plat_tg != "يوتيوب" and "youtube.com" not in clean_u.lower() and "youtu.be" not in clean_u.lower():
        try:
          send_telegram_audio_for_item(item, cfg, reply_to_message_id=sent_msg_id)
        except Exception:
          pass
      return True
    return False
  except Exception:
    return False


def upgrade_incomplete_existing_articles(cfg: dict, max_upgrades: int = 8):
  lock = get_db_lock()
  to_upgrade = []
  with lock:
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute(
          "SELECT id, title, summary, source_name, platform, url, raw_snippet, image_url "
          "FROM articles ORDER BY pub_timestamp DESC LIMIT 40"
      )
      for r in c.fetchall():
        d = dict(r)
        valid_img = clean_and_validate_image_url(d.get("image_url") or "", d.get("url") or "", d.get("platform") or "الصحف")
        missing_img = not valid_img
        bad_sum = is_summary_just_title(
            d.get("title", ""), d.get("summary", "")
        )
        src_curr = clean_display_text(d.get("source_name") or "")
        missing_domain_in_src = ("(" not in src_curr or ")" not in src_curr)
        raw_s_check = clean_full_article_text(d.get("raw_snippet") or "")
        sum_check = clean_display_text(d.get("summary") or "")
        short_body = (len(raw_s_check) < 450 or normalize_arabic_for_dedup(raw_s_check) == normalize_arabic_for_dedup(sum_check) or "news.google.com" in str(d.get("url") or ""))
        if missing_img or bad_sum or short_body or missing_domain_in_src:
          to_upgrade.append(d)
          if len(to_upgrade) >= max_upgrades:
            break
      conn.close()
    except Exception:
      pass

  if not to_upgrade:
    return

  api_key = (cfg.get("gemini_api_key") or "").strip()
  upgraded_records = []
  for item in to_upgrade:
    if is_stop_requested():
      break
    enrich_item_content_and_image(item)
    ai_res = analyze_with_gemini(item, api_key)
    item["summary"] = clean_display_text(ai_res["summary"])
    upgraded_records.append(item)

  if upgraded_records:
    with lock:
      try:
        conn = _open_sqlite_conn()
        c = conn.cursor()
        for rec in upgraded_records:
          c.execute(
              "UPDATE articles SET summary = ?, source_name = ?, image_url = ?, raw_snippet = ?, url = ? WHERE id = ?",
              (
                  rec["summary"],
                  rec.get("source_name", ""),
                  rec.get("image_url", ""),
                  rec.get("raw_snippet", ""),
                  rec.get("url", ""),
                  rec["id"],
              ),
          )
        conn.commit()
        conn.close()
      except Exception:
        pass
    sync_db_to_json()


def quick_process_and_save(
    items: list, cfg: dict, is_target_run: bool = False, custom_kw_override: str = ""
) -> int:
  if not items:
    upgrade_incomplete_existing_articles(cfg, max_upgrades=6)
    return 0

  is_kw_override_run = bool(custom_kw_override and str(custom_kw_override).strip())
  kw_override_clean = str(custom_kw_override or "").strip().strip('"\'«» ')
  kw_override_tag = f"#kwtrack={urllib.parse.quote(kw_override_clean, safe='')}" if is_kw_override_run else ""

  existing_dedup_keys = set()
  non_target_url_map = {}
  sqlite_scoped_row_map = {}
  current_targets = load_custom_targets()
  lock = get_db_lock()
  with lock:
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      c = conn.cursor()
      now_check_ts = time.time()
      c.execute("SELECT id, url, title, platform, is_custom_target, pub_timestamp, created_at FROM articles")
      archived_id_map = {}
      for r_id, r_url, r_title, r_plat, r_tgt, r_pub_ts, r_created_at in c.fetchall():
        base_keys = compute_article_dedup_keys(r_title or "", r_url or "")
        plat_scope = r_plat or "الصحف"
        tgt_scope = int(r_tgt or 0)
        mon_ts_row = float(r_created_at or r_pub_ts or 0)
        is_row_archived = (now_check_ts - mon_ts_row) >= 86400
        for bk in base_keys:
          scoped_k = f"{plat_scope}::{tgt_scope}::{bk}"
          existing_dedup_keys.add(scoped_k)
          sqlite_scoped_row_map[scoped_k] = (r_id, str(r_url or ""))
          if is_row_archived:
            archived_id_map[scoped_k] = r_id
          if bk.startswith("raw_u:") or bk.startswith("pid:") or bk.startswith("canon_u:") or bk.startswith("title_words:"):
            existing_dedup_keys.add(f"global::{tgt_scope}::{bk}")
            if tgt_scope == 0:
              non_target_url_map[bk] = r_id
      conn.close()
    except Exception:
      pass

  # خارج قفل قاعدة البيانات لمنع أي تجميد للواجهة أثناء قراءة ملفات الأرشيف
  if True:
    if not is_kw_override_run:
      for arch_file_p in (ARCHIVE_JSON_FILE, PERSISTENT_HOME_ARCHIVE_JSON):
        if os.path.exists(arch_file_p):
          try:
            with open(arch_file_p, "r", encoding="utf-8") as f:
              arch_list_p = json.load(f)
            if isinstance(arch_list_p, list):
              for a_it in arch_list_p:
                if isinstance(a_it, dict):
                  base_keys = compute_article_dedup_keys(a_it.get("title", ""), a_it.get("url", ""))
                  plat_scope = a_it.get("platform") or "الصحف"
                  tgt_scope = int(a_it.get("is_custom_target") or 0)
                  for bk in base_keys:
                    existing_dedup_keys.add(f"{plat_scope}::{tgt_scope}::{bk}")
                    if bk.startswith("raw_u:") or bk.startswith("pid:") or bk.startswith("canon_u:") or bk.startswith("title_words:"):
                      existing_dedup_keys.add(f"global::{tgt_scope}::{bk}")
          except Exception:
            pass

  kw_filter = kw_override_clean if is_kw_override_run else cfg.get("keywords_input", "")
  candidates = []
  seen_batch_keys = set()
  refreshed_kw_ids = set()

  def _refresh_existing_sqlite_for_kw(scoped_keys_set: set, pub_date_val: str, pub_ts_val: float):
    if not is_kw_override_run:
      return
    matched_rows = [sqlite_scoped_row_map[sk] for sk in scoped_keys_set if sk in sqlite_scoped_row_map]
    if not matched_rows:
      return
    with lock:
      try:
        conn_kw = _open_sqlite_conn()
        for ex_id, ex_url in matched_rows:
          new_ex_url = ex_url if kw_override_tag.lower() in ex_url.lower() else f"{ex_url}{kw_override_tag}"
          if pub_ts_val > 0 and pub_date_val:
            conn_kw.execute(
                "UPDATE articles SET created_at = ?, url = ?, pub_date = ?, pub_timestamp = ? WHERE id = ?",
                (time.time(), new_ex_url, pub_date_val, pub_ts_val, ex_id),
            )
          else:
            conn_kw.execute(
                "UPDATE articles SET created_at = ?, url = ? WHERE id = ?",
                (time.time(), new_ex_url, ex_id),
            )
          refreshed_kw_ids.add(ex_id)
        conn_kw.commit()
        conn_kw.close()
      except Exception:
        pass

  for it in sorted(
      items, key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
  ):
    u = (it.get("url") or "").strip()
    t = clean_display_text(it.get("title") or "")
    s_raw = clean_display_text(it.get("raw_snippet") or "")
    is_tgt = bool(is_target_run or it.get("is_custom_target"))
    if not u or not t:
      continue
    if is_kw_override_run and kw_override_tag not in u:
      u = f"{u}{kw_override_tag}"
      it["url"] = u
    if not is_strictly_judicial_and_clean(
        t, s_raw, u, kw_filter if not is_tgt else "", is_target=is_tgt
    ):
      continue
    if is_tgt and not belongs_to_any_custom_target(it, current_targets):
      continue

    p_scope = it.get("platform", "الصحف")
    t_scope = 1 if is_tgt else 0
    base_pre_keys = compute_article_dedup_keys(t, u)
    if is_tgt:
      for bpk in base_pre_keys:
        if bpk in non_target_url_map:
          with lock:
            try:
              conn_up = _open_sqlite_conn()
              conn_up.execute(
                  "UPDATE articles SET is_custom_target = 1, url = ?, source_name = ? WHERE id = ?",
                  (u, clean_display_text(it.get("source_name") or p_scope), non_target_url_map[bpk]),
              )
              conn_up.commit()
              conn_up.close()
            except Exception:
              pass
    pre_keys = {f"{p_scope}::{t_scope}::{k}" for k in base_pre_keys}
    max_age_qps = get_period_config(cfg.get("search_period", "آخر 7 أيام"))["sec"]
    it_pub_ts_pre = float(it.get("pub_timestamp") or 0)

    if is_kw_override_run and (pre_keys & existing_dedup_keys):
      _refresh_existing_sqlite_for_kw(pre_keys, it.get("pub_date", ""), it_pub_ts_pre)
      continue

    if p_scope == "يوتيوب" and it_pub_ts_pre > 0 and (max_age_qps <= 0 or (time.time() - it_pub_ts_pre) <= max_age_qps):
      matched_arch_keys = [pk for pk in pre_keys if pk in archived_id_map]
      if matched_arch_keys:
        with lock:
          try:
            conn_act = _open_sqlite_conn()
            for mak in matched_arch_keys:
              conn_act.execute(
                  "UPDATE articles SET created_at = ?, pub_date = ?, pub_timestamp = ? WHERE id = ?",
                  (time.time(), it.get("pub_date", ""), it_pub_ts_pre, archived_id_map[mak]),
              )
            conn_act.commit()
            conn_act.close()
          except Exception:
            pass
    if (pre_keys & existing_dedup_keys) or (pre_keys & seen_batch_keys):
      continue

    seen_batch_keys.update(pre_keys)
    it["title"] = t
    candidates.append(it)

  if not candidates:
    if refreshed_kw_ids:
      invalidate_articles_cache()
    return len(refreshed_kw_ids)

  # إثراء المتون والصور بالتوازي (Parallel Enrichment) لأحدث 16 عنصراً مرشحاً لتسريع الرصد ومنع تجميد الواجهة
  to_enrich = candidates[:16]
  if to_enrich and not is_stop_requested():
    def _enrich_worker(cand_it):
      if not is_stop_requested():
        try:
          enrich_item_content_and_image(cand_it)
        except Exception:
          pass
      return cand_it

    try:
      with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_enrich_worker, to_enrich))
    except Exception:
      pass

  api_key = (cfg.get("gemini_api_key") or "").strip()
  filtered_candidates = []
  post_enrich_seen_keys = set()
  max_age_final = get_period_config(cfg.get("search_period", "آخر 7 أيام"))["sec"]

  for it in candidates:
    if is_stop_requested():
      break
    plat = it.get("platform", "الصحف")
    src = clean_display_text(it.get("source_name") or plat)

    if is_kw_override_run:
      curr_u_it = str(it.get("url") or "")
      if kw_override_tag.lower() not in curr_u_it.lower():
        it["url"] = f"{curr_u_it}{kw_override_tag}"
      curr_s_it = str(it.get("raw_snippet") or "")
      if not is_strictly_judicial_and_clean(it.get("title", ""), curr_s_it, it.get("url", ""), kw_override_clean, is_target=False):
        continue

    t_scope_post = 1 if (is_target_run or it.get("is_custom_target")) else 0
    base_post_keys = compute_article_dedup_keys(it.get("title", ""), it.get("url", ""))
    post_keys = {f"{plat}::{t_scope_post}::{k}" for k in base_post_keys}
    if is_kw_override_run and (post_keys & existing_dedup_keys):
      _refresh_existing_sqlite_for_kw(post_keys, it.get("pub_date", ""), float(it.get("pub_timestamp") or 0))
      continue
    if (post_keys & existing_dedup_keys) or (post_keys & post_enrich_seen_keys):
      continue
    post_enrich_seen_keys.update(post_keys)

    src = format_precise_source_with_domain(
        it.get("source_name") or src,
        it.get("url") or "",
        plat,
        source_url_hint=it.get("source_domain_hint", ""),
        title_hint=it.get("title", ""),
    )
    it["source_name"] = src
    raw_snip = clean_display_text(it.get("raw_snippet") or "")
    it["image_url"] = clean_and_validate_image_url((it.get("image_url") or "").strip(), it.get("url") or "", plat)

    pub_str = it.get("pub_date") or ""
    pub_ts = float(it.get("pub_timestamp") or 0)
    if pub_ts <= 0 or not pub_str:
      if plat == "يوتيوب":
        continue
      pub_str, pub_ts = extract_date_from_url_or_text(
          it.get("url", ""), raw_snip, pub_str, fallback_offset_sec=3600
      )
      it["pub_date"] = pub_str
      it["pub_timestamp"] = pub_ts

    if plat == "يوتيوب" and max_age_final > 0 and (time.time() - pub_ts) > max_age_final:
      continue

    filtered_candidates.append(it)

  if not filtered_candidates:
    if refreshed_kw_ids:
      invalidate_articles_cache()
    return len(refreshed_kw_ids)

  # تلخيص موازٍ عبر Gemini AI لأحدث 8 عناصر مرشحة واستخلاص فوري للبقية
  ai_results_map = {}
  if api_key and not is_stop_requested():
    ai_targets = filtered_candidates[:8]
    def _ai_worker(idx_and_it):
      idx_c, cand_it = idx_and_it
      if is_stop_requested():
        return idx_c, None
      return idx_c, analyze_with_gemini(cand_it, api_key)
    try:
      with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for idx_c, res_ai in pool.map(_ai_worker, enumerate(ai_targets)):
          if res_ai:
            ai_results_map[idx_c] = res_ai
    except Exception:
      pass

  prepared_rows = []
  for idx_c, it in enumerate(filtered_candidates):
    plat = it.get("platform", "الصحف")
    src = it.get("source_name", plat)
    raw_snip = clean_display_text(it.get("raw_snippet") or "")
    ai_res = ai_results_map.get(idx_c) or {
        "summary": build_extractive_arabic_summary(it["title"], raw_snip, plat, src),
        "sentiment": "محايد",
        "category": "شؤون قضائية",
        "relevance_score": 86,
    }
    pub_ts = float(it.get("pub_timestamp") or 0)
    record = {
        "title": it["title"],
        "summary": clean_display_text(ai_res["summary"]),
        "source_name": src,
        "platform": plat,
        "url": (it.get("url") or "").strip(),
        "pub_date": it.get("pub_date") or "",
        "pub_timestamp": pub_ts,
        "sentiment": clean_display_text(ai_res["sentiment"]),
        "category": clean_display_text(ai_res["category"]),
        "relevance_score": int(ai_res["relevance_score"]),
        "is_custom_target": (1 if (is_target_run or it.get("is_custom_target")) else 0),
        "raw_snippet": clean_full_article_text(it.get("raw_snippet") or "")[:15000],
        "image_url": it.get("image_url") or "",
        "created_at": time.time(),
        "telegram_sent": 1 if (time.time() - pub_ts) >= 86400 else 0,
    }
    prepared_rows.append(record)

  added_items = []
  with lock:
    for attempt in range(3):
      conn = None
      try:
        conn = _open_sqlite_conn()
        if attempt == 0:
          _ensure_schema_on_conn(conn)
        elif attempt == 1:
          _rebuild_articles_table_safely(conn)
        c = conn.cursor()
        for rec in prepared_rows:
          base_rec_keys = compute_article_dedup_keys(rec["title"], rec["url"])
          rec_keys = {f"{rec['platform']}::{rec['is_custom_target']}::{k}" for k in base_rec_keys}
          if rec_keys & existing_dedup_keys:
            continue
          c.execute(
              """
              INSERT OR IGNORE INTO articles (
                  title, summary, source_name, platform, url,
                  pub_date, pub_timestamp, sentiment, category,
                  relevance_score, is_custom_target, raw_snippet,
                  image_url, created_at, telegram_sent
              ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
              """,
              (
                  rec["title"],
                  rec["summary"],
                  rec["source_name"],
                  rec["platform"],
                  rec["url"],
                  rec["pub_date"],
                  rec["pub_timestamp"],
                  rec["sentiment"],
                  rec["category"],
                  rec["relevance_score"],
                  rec["is_custom_target"],
                  rec["raw_snippet"],
                  rec["image_url"],
                  rec["created_at"],
                  0,
              ),
          )
          if c.rowcount and c.rowcount > 0:
            existing_dedup_keys.update(rec_keys)
            added_items.append(rec)
        conn.commit()
        conn.close()
        break
      except Exception:
        if conn is not None:
          try:
            conn.close()
          except Exception:
            pass
        time.sleep(0.15)

  if added_items or refreshed_kw_ids:
    invalidate_articles_cache()

  def _async_post_save_pipeline(newly_added: list, cfg_snap: dict):
    try:
      if newly_added:
        fresh_for_tg = [r for r in newly_added if int(r.get("telegram_sent", 0)) == 0]
        for rec in fresh_for_tg[:10]:
          send_telegram_alert(rec, cfg_snap)
          rec["telegram_sent"] = 1
        with lock:
          ledger_now = load_telegram_sent_ledger()
          for rec in newly_added:
            rec["telegram_sent"] = 1
            ledger_now.update(compute_article_dedup_keys(rec["title"], rec["url"]))
          save_telegram_sent_ledger(ledger_now)
          try:
            conn_tg = _open_sqlite_conn()
            c_tg = conn_tg.cursor()
            c_tg.executemany(
                "UPDATE articles SET telegram_sent = 1 WHERE url = ?",
                [(r["url"],) for r in newly_added],
            )
            conn_tg.commit()
            conn_tg.close()
          except Exception:
            pass
        sync_db_to_json(extra_items=newly_added)
        trigger_cloud_state_backup(async_mode=True)
      upgrade_incomplete_existing_articles(cfg_snap, max_upgrades=3)
    except Exception:
      pass

  if os.environ.get("CRON_MODE") == "1":
    _async_post_save_pipeline(added_items, dict(cfg))
  else:
    threading.Thread(
        target=_async_post_save_pipeline,
        args=(list(added_items), dict(cfg)),
        daemon=True,
        name="AsyncPostSavePipeline",
    ).start()

  return len(added_items) + len(refreshed_kw_ids)


# =====================================================================
# 11. محرك الرصد الدوري الأوتوماتيكي (خلفية السيرفر + GitHub Actions)
# =====================================================================
def run_headless_background_cycle() -> int:
  rt = get_shared_runtime()
  if rt.get("active_scan") is not None:
    return 0

  scan_lock = get_scan_lock()
  if not scan_lock.acquire(blocking=False):
    return 0

  try:
    rt["bg_scanning"] = True
    rt["abort_bg_for_manual"] = False
  except Exception:
    pass

  try:
    init_db()
    cfg = load_credentials()
    targets = load_custom_targets()
    kw = cfg.get("keywords_input", "")
    s_period = cfg.get("search_period", "آخر 7 أيام")

    m_state = load_monitor_state()
    m_state["last_auto_run"] = time.time()
    save_monitor_state(m_state)

    raw_items = []
    for scraper_fn in (
        lambda: scrape_moroccan_press(kw, s_period),
        lambda: scrape_youtube_platform(kw, s_period),
        lambda: scrape_facebook_platform(kw, s_period),
        lambda: scrape_x_platform(kw, s_period),
        lambda: scrape_other_platforms(kw, s_period),
    ):
      if is_stop_requested() or rt.get("active_scan") is not None:
        break
      raw_items.extend(scraper_fn())

    added_general = 0
    if raw_items and not is_stop_requested():
      added_general = quick_process_and_save(raw_items, cfg, is_target_run=False)

    added_targets = 0
    if targets and not is_stop_requested() and rt.get("active_scan") is None:
      t_items = scrape_custom_targets(targets, kw, s_period)
      added_targets = quick_process_and_save(t_items, cfg, is_target_run=True)

    added_kw_trackers = 0
    kw_trackers_list = load_platform_keyword_trackers()
    for kwt in kw_trackers_list:
      if is_stop_requested() or rt.get("active_scan") is not None:
        break
      t_plat_k = kwt.get("platform", "فيسبوك")
      t_word_k = kwt.get("keyword", "").strip()
      if t_word_k:
        kw_items = scrape_platform_by_keyword(t_plat_k, t_word_k, s_period)
        added_kw_trackers += quick_process_and_save(
            kw_items, cfg, is_target_run=False, custom_kw_override=t_word_k
        )

    total_added = added_general + added_targets + added_kw_trackers
    m_state = load_monitor_state()
    m_state["last_auto_run"] = time.time()
    m_state["last_auto_added"] = total_added
    m_state["total_auto_cycles"] = int(m_state.get("total_auto_cycles", 0)) + 1
    save_monitor_state(m_state)
    rt["last_auto_completed_ts"] = time.time()
    if total_added > 0:
      invalidate_articles_cache()
    return total_added
  except Exception:
    return 0
  finally:
    if rt is not None:
      rt["bg_scanning"] = False
      rt["abort_bg_for_manual"] = False
    try:
      scan_lock.release()
    except Exception:
      pass


def _detect_public_app_url() -> str:
  """اكتشاف الرابط العام للمنصة تلقائياً (من ترويسات Streamlit أو متغيرات البيئة أو الإعدادات) لاستخدامه في نبضات منع السبات Keep-Alive."""
  try:
    cfg_u = str(load_credentials().get("app_public_url") or "").strip()
    if cfg_u.startswith("http"):
      return cfg_u.rstrip("/")
  except Exception:
    pass
  for env_k in ("STREAMLIT_APP_URL", "APP_PUBLIC_URL", "RENDER_EXTERNAL_URL", "PUBLIC_URL"):
    ev = os.environ.get(env_k, "").strip()
    if ev.startswith("http"):
      return ev.rstrip("/")
  if st is not None:
    try:
      hdrs = getattr(st, "context", None) and getattr(st.context, "headers", None)
      if hdrs:
        host = (hdrs.get("X-Forwarded-Host") or hdrs.get("Host") or "").strip()
        proto = (hdrs.get("X-Forwarded-Proto") or "https").strip()
        if host and "localhost" not in host and "127.0.0.1" not in host:
          detected = f"{proto}://{host}".rstrip("/")
          try:
            c_curr = load_credentials()
            if not c_curr.get("app_public_url"):
              c_curr["app_public_url"] = detected
              save_credentials(c_curr)
          except Exception:
            pass
          return detected
    except Exception:
      pass
  return ""


def _ping_keep_alive_endpoints():
  """إرسال نبضات HTTP خفيفة (Self-Ping) للخادم المحلي والرابط العام للمنصة لمنع دخول السيرفر في وضع السبات (Sleep Mode)."""
  rt = get_shared_runtime()
  port = os.environ.get("PORT") or os.environ.get("STREAMLIT_SERVER_PORT") or "8501"
  targets_to_ping = [
      f"http://127.0.0.1:{port}/_stcore/health",
      f"http://127.0.0.1:{port}/",
  ]
  pub_u = _detect_public_app_url()
  if pub_u and pub_u.startswith("http"):
    targets_to_ping.insert(0, f"{pub_u}/_stcore/health")
    targets_to_ping.insert(1, pub_u)

  for ping_u in targets_to_ping:
    try:
      requests.get(ping_u, headers=DEFAULT_HEADERS, timeout=4)
    except Exception:
      pass
  rt["last_keepalive_ping_ts"] = time.time()


def _neutralize_and_patch_legacy_daemon_threads():
  """إيقاف وتحديث أي خيط خلفية قديم (JusticeAutoMonitor) عالق في ذاكرة السيرفر من نسخة كود سابقة لمنعه من إرسال الاسم القديم نهائياً."""
  current_globals = globals()
  try:
    for obj in list(gc.get_objects()):
      if callable(obj) and hasattr(obj, "__name__") and hasattr(obj, "__globals__"):
        fn_name = getattr(obj, "__name__", "")
        fn_globals = getattr(obj, "__globals__", None)
        if isinstance(fn_globals, dict) and fn_globals is not current_globals:
          if fn_name in ("_daemon_loop", "run_headless_background_cycle", "send_telegram_alert", "quick_process_and_save"):
            # تحديث الدوال داخل مساحة الأسماء القديمة وإيقاف حلقتها الدورية
            fn_globals["send_telegram_alert"] = send_telegram_alert
            fn_globals["send_telegram_audio_for_item"] = send_telegram_audio_for_item
            fn_globals["quick_process_and_save"] = quick_process_and_save
            fn_globals["run_headless_background_cycle"] = lambda: 0
            fn_globals["load_credentials"] = lambda: {"auto_monitor": False}
  except Exception:
    pass


def ensure_background_daemon():
  rt = get_shared_runtime()
  if rt.get("daemon_started", False) and rt.get("daemon_version") == DAEMON_CODE_VERSION:
    return
  rt["daemon_started"] = True
  rt["daemon_version"] = DAEMON_CODE_VERSION
  my_version = DAEMON_CODE_VERSION
  _detect_public_app_url()
  threading.Thread(
      target=_neutralize_and_patch_legacy_daemon_threads,
      daemon=True,
      name="LegacyDaemonNeutralizer",
  ).start()

  def _daemon_loop():
    time.sleep(1.5)
    last_keepalive = 0.0
    while True:
      if rt.get("daemon_version") != my_version:
        break
      now_t = time.time()
      if now_t - last_keepalive >= 180:
        last_keepalive = now_t
        try:
          _ping_keep_alive_endpoints()
        except Exception:
          pass
      try:
        cfg_d = load_credentials()
        if cfg_d.get("auto_monitor", True) and rt.get("active_scan") is None and not rt.get("bg_scanning", False):
          interval_sec = INTERVAL_MAP.get(
              cfg_d.get("monitor_interval", "كل 15 دقيقة"), 900
          )
          state = load_monitor_state()
          last_run = float(state.get("last_auto_run", 0))
          if time.time() - last_run >= interval_sec:
            run_headless_background_cycle()
      except Exception:
        pass
      time.sleep(12)

  t = threading.Thread(
      target=_daemon_loop, daemon=True, name=f"JusticeAutoMonitor_{DAEMON_CODE_VERSION}"
  )
  t.start()


# دعم التشغيل السحابي المستقل عبر GitHub Actions (CRON_MODE=1) مع إيقاظ الموقع تلقائياً من وضع السبات
if os.environ.get("CRON_MODE") == "1" or st is None:
  init_db()
  _ping_keep_alive_endpoints()
  count = run_headless_background_cycle()
  print(f"[CRON_MODE] Completed cycle. Added {count} new items.")
  sys.exit(0)

# =====================================================================
# 12. تهيئة واجهة Streamlit والتصميم الزجاجي المتجاوب مع فرض صارم لاتجاه RTL
# =====================================================================
st.set_page_config(
    page_title="المرصد القضائي",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_db()
ensure_background_daemon()

render_html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');

*, *::before, *::after {
    box-sizing: border-box;
}

html, body, .stApp, .main,
[data-testid="stAppViewContainer"],
[data-testid="stMarkdownContainer"],
[data-testid="stVerticalBlock"],
[data-baseweb="tab-panel"],
[class*="st-emotion-cache"] {
    font-family: 'Cairo', sans-serif !important;
    direction: rtl !important;
    text-align: right !important;
}

.stApp {
    background: radial-gradient(circle at 15% 15%, #111c35 0%, #090d16 55%, #05080f 100%) !important;
    color: #f1f5f9 !important;
    overflow-x: hidden !important;
}

.block-container {
    padding-top: 1.1rem !important;
    padding-bottom: 2.2rem !important;
    padding-left: clamp(0.6rem, 2.2vw, 2rem) !important;
    padding-right: clamp(0.6rem, 2.2vw, 2rem) !important;
    max-width: 1440px !important;
    direction: rtl !important;
    text-align: right !important;
}

div[data-testid="stHorizontalBlock"] {
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 10px !important;
    align-items: stretch !important;
    direction: rtl !important;
}

div[data-testid="stHorizontalBlock"] > div[data-testid="column"],
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    flex: 1 1 145px !important;
    min-width: 140px !important;
}

.hero-glass {
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.88) 0%, rgba(30, 41, 59, 0.72) 100%);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(56, 189, 248, 0.28);
    border-radius: 18px;
    padding: clamp(12px, 2vw, 20px) clamp(14px, 2.5vw, 26px);
    margin-bottom: 14px;
    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
    direction: rtl !important;
    text-align: right !important;
}

.hero-title {
    font-size: clamp(1.2rem, 2.6vw, 1.75rem);
    font-weight: 900;
    background: linear-gradient(90deg, #38bdf8, #818cf8, #f472b6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    line-height: 1.35;
}

.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(16, 185, 129, 0.14);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: #34d399;
    padding: 5px 13px;
    border-radius: 999px;
    font-size: clamp(0.74rem, 1.4vw, 0.84rem);
    font-weight: 700;
    max-width: 100%;
    direction: rtl !important;
}

.pulse-dot {
    width: 9px;
    height: 9px;
    min-width: 9px;
    background: #10b981;
    border-radius: 50%;
    box-shadow: 0 0 10px #10b981;
    animation: pulseGlow 1.6s infinite ease-in-out;
}

@keyframes pulseGlow {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.35); opacity: 0.55; }
}

/* فرض الوضع الداكن ومنع الخلفية البيضاء الافتراضية لجميع أزرار Streamlit في كافة المتصفحات */
:root, html, body, .stApp {
    color-scheme: dark !important;
}

.stApp button[kind="secondary"],
.stApp button[kind="primary"],
.stApp [data-testid="stBaseButton-secondary"],
.stApp [data-testid="baseButton-secondary"],
.stApp [data-testid="stBaseButton-primary"],
.stApp [data-testid="baseButton-primary"],
div.stButton > button,
div[data-testid="stButton"] > button,
div.stDownloadButton > button,
div[data-testid="stFormSubmitButton"] > button {
    width: 100% !important;
    min-height: 42px !important;
    background: rgba(15, 23, 42, 0.78) !important;
    background-color: rgba(15, 23, 42, 0.78) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    color: #f8fafc !important;
    border: 1px solid rgba(148, 163, 184, 0.35) !important;
    border-radius: 12px !important;
    padding: 0.45rem 0.65rem !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
    font-size: 0.92rem !important;
    white-space: nowrap !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3) !important;
    transition: all 0.2s ease !important;
}

.stApp button *,
div.stButton > button *,
div[data-testid="stButton"] > button *,
div.stDownloadButton > button *,
div[data-testid="stFormSubmitButton"] > button * {
    color: #f8fafc !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
}

div.stButton > button:hover,
div[data-testid="stButton"] > button:hover,
div.stDownloadButton > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-2px) !important;
    border-color: #38bdf8 !important;
    box-shadow: 0 8px 22px rgba(56, 189, 248, 0.28) !important;
}

/* البطاقات الزجاجية الشفافة للرصد (Glassmorphic Monitoring Frames) */
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-marker)),
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scan-frame-marker) {
    border-radius: 18px !important;
    padding: 14px 16px 12px 16px !important;
    margin-bottom: 10px !important;
    backdrop-filter: blur(24px) saturate(170%) !important;
    -webkit-backdrop-filter: blur(24px) saturate(170%) !important;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.32), inset 0 1px 1px rgba(255, 255, 255, 0.22) !important;
    transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease !important;
}

div[data-testid="stVerticalBlock"]:has(.scan-frame-marker):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-marker)):hover,
div[data-testid="stVerticalBlockBorderWrapper"]:has(.scan-frame-marker):hover {
    transform: translateY(-3px) !important;
}

div[data-testid="stVerticalBlock"]:has(.scan-frame-all):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-all)) {
    background: linear-gradient(135deg, rgba(14, 165, 233, 0.20) 0%, rgba(15, 23, 42, 0.52) 100%) !important;
    border: 1px solid rgba(56, 189, 248, 0.48) !important;
}
div[data-testid="stVerticalBlock"]:has(.scan-frame-press):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-press)) {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.20) 0%, rgba(15, 23, 42, 0.52) 100%) !important;
    border: 1px solid rgba(52, 211, 153, 0.48) !important;
}
div[data-testid="stVerticalBlock"]:has(.scan-frame-fb):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-fb)) {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.22) 0%, rgba(15, 23, 42, 0.52) 100%) !important;
    border: 1px solid rgba(96, 165, 250, 0.48) !important;
}
div[data-testid="stVerticalBlock"]:has(.scan-frame-x):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-x)) {
    background: linear-gradient(135deg, rgba(148, 163, 184, 0.22) 0%, rgba(15, 23, 42, 0.56) 100%) !important;
    border: 1px solid rgba(203, 213, 225, 0.42) !important;
}
div[data-testid="stVerticalBlock"]:has(.scan-frame-yt):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-yt)) {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.22) 0%, rgba(15, 23, 42, 0.52) 100%) !important;
    border: 1px solid rgba(248, 113, 113, 0.48) !important;
}
div[data-testid="stVerticalBlock"]:has(.scan-frame-other):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-other)) {
    background: linear-gradient(135deg, rgba(168, 85, 247, 0.22) 0%, rgba(15, 23, 42, 0.52) 100%) !important;
    border: 1px solid rgba(192, 132, 252, 0.48) !important;
}
div[data-testid="stVerticalBlock"]:has(.scan-frame-target):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-target)) {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.24) 0%, rgba(15, 23, 42, 0.54) 100%) !important;
    border: 1px solid rgba(251, 191, 36, 0.52) !important;
}

/* ترويسة اسم المنصة داخل الإطار الزجاجي: عرض كامل وواضح بدون أي اقتطاع */
.scan-platform-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    direction: rtl !important;
    text-align: right !important;
    padding: 4px 2px 10px 2px;
    margin-bottom: 6px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
    width: 100%;
}

.scan-platform-right {
    display: flex;
    align-items: center;
    gap: 10px;
    direction: rtl !important;
    text-align: right !important;
    flex: 1 1 auto;
}

.scan-platform-icon {
    width: 40px;
    height: 40px;
    min-width: 40px;
    border-radius: 12px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    background: rgba(15, 23, 42, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.22);
    box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.18), 0 4px 10px rgba(0, 0, 0, 0.25);
}

.scan-platform-title {
    font-size: 1.04rem;
    font-weight: 900;
    color: #ffffff;
    line-height: 1.3;
    white-space: normal !important;
    overflow: visible !important;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.45);
}

.scan-platform-sub {
    font-size: 0.77rem;
    font-weight: 700;
    color: #e2e8f0;
    opacity: 0.92;
    white-space: normal !important;
    line-height: 1.25;
    margin-top: 2px;
}

.scan-platform-badge {
    font-size: 0.72rem;
    font-weight: 800;
    padding: 3px 9px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.12);
    border: 1px solid rgba(255, 255, 255, 0.22);
    color: #f8fafc;
    white-space: nowrap;
}

/* صف أزرار التشغيل (▶) والإيقاف (⏹) داخل الإطار الزجاجي */
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-marker)) div[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 8px !important;
}

div[data-testid="stVerticalBlock"]:has(.scan-frame-marker):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-marker)) div[data-testid="stHorizontalBlock"] > div[data-testid="column"],
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker):not(:has(div[data-testid="stVerticalBlock"] .scan-frame-marker)) div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    min-width: 0 !important;
    flex: 1 1 50% !important;
}

/* زر التشغيل الزجاجي (▶ تشغيل) — يستهدف جميع محددات Streamlit لضمان عدم ظهور أي خلفية بيضاء إطلاقاً */
[class*="st-key-start_scan_"] button,
div[data-testid="column"]:has(.media-play-marker) button,
div[data-testid="stColumn"]:has(.media-play-marker) button,
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) button[kind="primary"],
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) [data-testid="stBaseButton-primary"],
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) [data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.72) 0%, rgba(5, 150, 105, 0.88) 100%) !important;
    background-color: rgba(16, 185, 129, 0.8) !important;
    backdrop-filter: blur(14px) !important;
    -webkit-backdrop-filter: blur(14px) !important;
    border: 1.5px solid rgba(110, 231, 183, 0.75) !important;
    color: #ffffff !important;
    min-height: 42px !important;
    height: 42px !important;
    padding: 0 10px !important;
    border-radius: 12px !important;
    font-size: 0.94rem !important;
    font-weight: 900 !important;
    box-shadow: 0 4px 15px rgba(16, 185, 129, 0.32), inset 0 1px 0 rgba(255, 255, 255, 0.25) !important;
}

[class*="st-key-start_scan_"] button:hover,
div[data-testid="column"]:has(.media-play-marker) button:hover,
div[data-testid="stColumn"]:has(.media-play-marker) button:hover,
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) button[kind="primary"]:hover,
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) [data-testid="stBaseButton-primary"]:hover {
    background: linear-gradient(135deg, rgba(52, 211, 153, 0.88) 0%, rgba(4, 120, 87, 0.95) 100%) !important;
    border-color: #ffffff !important;
    box-shadow: 0 6px 20px rgba(16, 185, 129, 0.55) !important;
    transform: translateY(-1px) scale(1.02) !important;
}

/* زر الإيقاف الزجاجي (⏹ إيقاف) — يستهدف جميع محددات Streamlit لضمان عدم ظهور أي خلفية بيضاء إطلاقاً */
[class*="st-key-stop_scan_"] button,
div[data-testid="column"]:has(.media-stop-marker) button,
div[data-testid="stColumn"]:has(.media-stop-marker) button,
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) button[kind="secondary"],
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) [data-testid="stBaseButton-secondary"],
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) [data-testid="baseButton-secondary"] {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.68) 0%, rgba(153, 27, 27, 0.86) 100%) !important;
    background-color: rgba(220, 38, 38, 0.78) !important;
    backdrop-filter: blur(14px) !important;
    -webkit-backdrop-filter: blur(14px) !important;
    border: 1.5px solid rgba(252, 165, 165, 0.7) !important;
    color: #ffffff !important;
    min-height: 42px !important;
    height: 42px !important;
    padding: 0 10px !important;
    border-radius: 12px !important;
    font-size: 0.94rem !important;
    font-weight: 900 !important;
    box-shadow: 0 4px 15px rgba(239, 68, 68, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.22) !important;
}

[class*="st-key-stop_scan_"] button:hover,
div[data-testid="column"]:has(.media-stop-marker) button:hover,
div[data-testid="stColumn"]:has(.media-stop-marker) button:hover,
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) button[kind="secondary"]:hover,
div[data-testid="stVerticalBlock"]:has(.scan-frame-marker) [data-testid="stBaseButton-secondary"]:hover {
    background: linear-gradient(135deg, rgba(248, 113, 113, 0.88) 0%, rgba(185, 28, 28, 0.95) 100%) !important;
    border-color: #ffffff !important;
    box-shadow: 0 6px 20px rgba(239, 68, 68, 0.55) !important;
    transform: translateY(-1px) scale(1.02) !important;
}

.radar-panel {
    background: rgba(15, 23, 42, 0.88);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(56, 189, 248, 0.42);
    border-radius: 16px;
    padding: 14px 18px;
    margin: 10px 0 14px 0;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0 10px 30px rgba(2, 132, 199, 0.22);
    direction: rtl !important;
    text-align: right !important;
}

.radar-scanner {
    width: 58px;
    height: 58px;
    min-width: 58px;
    border-radius: 50%;
    position: relative;
    background:
        radial-gradient(circle, rgba(56, 189, 248, 0.15) 20%, transparent 21%),
        radial-gradient(circle, transparent 48%, rgba(56, 189, 248, 0.25) 49%, transparent 51%),
        #070d19;
    border: 2px solid #38bdf8;
    box-shadow: 0 0 18px rgba(56, 189, 248, 0.45), inset 0 0 12px rgba(56, 189, 248, 0.25);
    overflow: hidden;
}

.radar-scanner::before {
    content: "";
    position: absolute;
    inset: -50%;
    background: conic-gradient(from 0deg, transparent 55%, rgba(56, 189, 248, 0.8) 100%);
    animation: radarSpin 1.3s linear infinite;
}

.radar-scanner::after {
    content: "";
    position: absolute;
    top: 50%;
    left: 50%;
    width: 7px;
    height: 7px;
    background: #38bdf8;
    border-radius: 50%;
    transform: translate(-50%, -50%);
    box-shadow: 0 0 10px #38bdf8;
}

@keyframes radarSpin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.done-banner {
    background: linear-gradient(135deg, rgba(6, 95, 70, 0.88) 0%, rgba(4, 120, 87, 0.78) 100%);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(52, 211, 153, 0.55);
    border-radius: 14px;
    padding: 11px 18px;
    margin: 8px 0 14px 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    color: #ecfdf5;
    font-weight: 800;
    font-size: clamp(0.84rem, 1.5vw, 0.96rem);
    box-shadow: 0 8px 25px rgba(16, 185, 129, 0.25);
    direction: rtl !important;
    text-align: right !important;
}

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
    gap: 10px;
    margin: 10px 0 16px 0;
    direction: rtl !important;
}

.metric-glass {
    background: rgba(15, 23, 42, 0.72);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    padding: 12px 10px;
    text-align: center !important;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.28);
}

.metric-num {
    font-size: clamp(1.3rem, 2.2vw, 1.65rem);
    font-weight: 900;
    color: #38bdf8;
    line-height: 1.2;
    text-align: center !important;
}

.metric-lbl {
    font-size: clamp(0.75rem, 1.2vw, 0.84rem);
    color: #94a3b8;
    font-weight: 700;
    margin-top: 2px;
    text-align: center !important;
}

.news-card {
    background: linear-gradient(145deg, rgba(15, 23, 42, 0.92) 0%, rgba(30, 41, 59, 0.74) 100%);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-right: 5px solid #38bdf8;
    border-radius: 16px;
    padding: clamp(14px, 2vw, 20px);
    margin-bottom: 14px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    transition: transform 0.2s ease, border-color 0.2s ease;
    word-wrap: break-word;
    overflow-wrap: anywhere;
    direction: rtl !important;
    text-align: right !important;
}

.news-card:hover {
    transform: translateY(-2px);
    border-color: rgba(56, 189, 248, 0.5);
}

.news-card.plat-press { border-right-color: #10b981; }
.news-card.plat-fb { border-right-color: #3b82f6; }
.news-card.plat-x { border-right-color: #cbd5e1; }
.news-card.plat-yt { border-right-color: #ef4444; }
.news-card.plat-other { border-right-color: #a855f7; }

.news-card-layout {
    display: flex !important;
    flex-direction: row !important;
    align-items: flex-start !important;
    justify-content: flex-start !important;
    gap: 18px !important;
    direction: rtl !important;
    text-align: right !important;
    width: 100% !important;
}

.news-thumb-box {
    width: 195px;
    min-width: 195px;
    height: 132px;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(148, 163, 184, 0.28);
    background: #090d16;
    flex-shrink: 0;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
}

.news-thumb-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}

.news-body-col {
    flex: 1 1 auto !important;
    min-width: 0 !important;
    direction: rtl !important;
    text-align: right !important;
}

.news-dates-row {
    display: flex !important;
    flex-wrap: wrap !important;
    align-items: center !important;
    justify-content: flex-start !important;
    gap: 8px !important;
    margin: 6px 0 10px 0 !important;
    direction: rtl !important;
    text-align: right !important;
}

.date-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(15, 23, 42, 0.88);
    border: 1px solid rgba(56, 189, 248, 0.32);
    color: #e2e8f0;
    padding: 3px 11px;
    border-radius: 999px;
    font-size: clamp(0.74rem, 1.2vw, 0.82rem);
    font-weight: 700;
    direction: rtl !important;
}

.badge-plat {
    padding: 3px 11px;
    border-radius: 999px;
    font-weight: 800;
    font-size: 0.78rem;
    background: rgba(56, 189, 248, 0.18);
    color: #7dd3fc;
    border: 1px solid rgba(56, 189, 248, 0.38);
    display: inline-block;
}

.badge-target {
    padding: 3px 11px;
    border-radius: 999px;
    font-weight: 800;
    font-size: 0.76rem;
    background: rgba(217, 119, 6, 0.22);
    color: #fcd34d;
    border: 1px solid rgba(245, 158, 11, 0.45);
    display: inline-block;
}

.news-title {
    font-size: clamp(1.02rem, 1.8vw, 1.18rem);
    font-weight: 800;
    color: #f8fafc;
    margin: 6px 0 6px 0;
    line-height: 1.55;
    direction: rtl !important;
    text-align: right !important;
}

.news-summary-box {
    background: rgba(9, 13, 22, 0.58);
    border-right: 3px solid rgba(56, 189, 248, 0.6);
    border-radius: 10px;
    padding: 9px 13px;
    margin-bottom: 10px;
    font-size: clamp(0.87rem, 1.45vw, 0.95rem);
    color: #cbd5e1;
    line-height: 1.72;
    direction: rtl !important;
    text-align: right !important;
}

.news-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(56, 189, 248, 0.16);
    border: 1px solid rgba(56, 189, 248, 0.4);
    color: #38bdf8 !important;
    text-decoration: none !important;
    padding: 5px 14px;
    border-radius: 10px;
    font-size: 0.83rem;
    font-weight: 800;
    direction: rtl !important;
}

.news-link:hover {
    background: rgba(56, 189, 248, 0.3);
}

.news-actions-bar {
    display: flex !important;
    flex-wrap: wrap !important;
    align-items: center !important;
    gap: 10px !important;
    margin-top: 8px !important;
    direction: rtl !important;
    text-align: right !important;
}

.tts-listen-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.22) 0%, rgba(5, 150, 105, 0.34) 100%);
    border: 1px solid rgba(52, 211, 153, 0.55);
    color: #6ee7b7 !important;
    padding: 5px 14px;
    border-radius: 10px;
    font-family: 'Cairo', sans-serif !important;
    font-size: 0.83rem;
    font-weight: 800;
    cursor: pointer;
    transition: all 0.2s ease;
    direction: rtl !important;
    user-select: none;
}

.tts-listen-btn:hover {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.38) 0%, rgba(5, 150, 105, 0.52) 100%);
    border-color: #a7f3d0;
    color: #ffffff !important;
    transform: translateY(-1px);
}

.tts-listen-btn.playing {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.35) 0%, rgba(185, 28, 28, 0.55) 100%) !important;
    border-color: #fca5a5 !important;
    color: #ffffff !important;
    box-shadow: 0 0 14px rgba(239, 68, 68, 0.45);
}

details.article-preview-drawer {
    width: 100%;
    margin-top: 8px;
    direction: rtl !important;
    text-align: right !important;
}

details.article-preview-drawer > summary {
    list-style: none;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.24) 0%, rgba(109, 40, 217, 0.36) 100%);
    border: 1px solid rgba(167, 139, 250, 0.55);
    color: #ddd6fe !important;
    padding: 5px 15px;
    border-radius: 10px;
    font-size: 0.83rem;
    font-weight: 800;
    cursor: pointer;
    transition: all 0.2s ease;
    user-select: none;
}

details.article-preview-drawer > summary::-webkit-details-marker {
    display: none;
}

details.article-preview-drawer > summary:hover {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.42) 0%, rgba(109, 40, 217, 0.55) 100%);
    border-color: #ede9fe;
    color: #ffffff !important;
    transform: translateY(-1px);
}

details.article-preview-drawer[open] > summary {
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.65) 0%, rgba(91, 33, 182, 0.8) 100%);
    border-color: #ddd6fe;
    color: #ffffff !important;
    margin-bottom: 10px;
}

.full-article-modal-box {
    background: linear-gradient(145deg, rgba(9, 13, 22, 0.94) 0%, rgba(15, 23, 42, 0.92) 100%);
    border: 1px solid rgba(167, 139, 250, 0.42);
    border-right: 4px solid #8b5cf6;
    border-radius: 14px;
    padding: 16px 18px;
    margin-top: 6px;
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    direction: rtl !important;
    text-align: right !important;
}

.full-article-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    padding-bottom: 10px;
    margin-bottom: 12px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.2);
}

.full-article-body {
    font-size: clamp(0.92rem, 1.5vw, 1.02rem);
    color: #f1f5f9;
    line-height: 1.9;
    direction: rtl !important;
    text-align: right !important;
}

.full-article-body p {
    margin: 0 0 12px 0;
    text-align: justify;
    direction: rtl !important;
}

/* ترويسة احترافية موحدة لقسم الرصد المخصص وإدارة القنوات والصفحات */
.custom-targets-header-card {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.22) 0%, rgba(15, 23, 42, 0.78) 65%, rgba(30, 41, 59, 0.85) 100%);
    backdrop-filter: blur(22px) saturate(170%);
    -webkit-backdrop-filter: blur(22px) saturate(170%);
    border: 1px solid rgba(251, 191, 36, 0.52);
    border-right: 5px solid #f59e0b;
    border-radius: 18px;
    padding: 14px 20px;
    margin: 10px 0 6px 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35), inset 0 1px 1px rgba(255, 255, 255, 0.2);
    direction: rtl !important;
    text-align: right !important;
}

.custom-targets-header-right {
    display: flex;
    align-items: center;
    gap: 12px;
    direction: rtl !important;
    text-align: right !important;
}

.custom-targets-icon-box {
    width: 44px;
    height: 44px;
    min-width: 44px;
    border-radius: 13px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 1.35rem;
    background: rgba(245, 158, 11, 0.2);
    border: 1px solid rgba(251, 191, 36, 0.55);
    box-shadow: 0 4px 12px rgba(245, 158, 11, 0.25), inset 0 1px 1px rgba(255, 255, 255, 0.25);
}

.custom-targets-main-title {
    font-size: clamp(1.05rem, 1.9vw, 1.22rem);
    font-weight: 900;
    color: #fef3c7;
    margin: 0;
    line-height: 1.3;
}

.custom-targets-subtitle {
    font-size: 0.8rem;
    font-weight: 700;
    color: #cbd5e1;
    margin-top: 2px;
}

.custom-targets-count-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(245, 158, 11, 0.24);
    border: 1px solid rgba(251, 191, 36, 0.6);
    color: #fde68a;
    padding: 5px 14px;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 900;
    white-space: nowrap;
}

/* تصميم زجاجي فاخر لقسم وشريط 🎯 الروابط والقنوات المخصصة (Expander) */
div[data-testid="stExpander"],
details[data-testid="stExpander"] {
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.78) 0%, rgba(30, 41, 59, 0.58) 100%) !important;
    backdrop-filter: blur(22px) saturate(165%) !important;
    -webkit-backdrop-filter: blur(22px) saturate(165%) !important;
    border: 1px solid rgba(251, 191, 36, 0.42) !important;
    border-radius: 18px !important;
    margin: 8px 0 14px 0 !important;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35), inset 0 1px 1px rgba(255, 255, 255, 0.16) !important;
    overflow: hidden !important;
}

div[data-testid="stExpander"] summary,
details[data-testid="stExpander"] > summary,
div[data-testid="stExpander"] [ data-testid="stExpanderHeader"] {
    background: linear-gradient(90deg, rgba(217, 119, 6, 0.22) 0%, rgba(15, 23, 42, 0.65) 100%) !important;
    padding: 12px 18px !important;
    border-radius: 17px !important;
    color: #fef3c7 !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 900 !important;
    font-size: 0.98rem !important;
    direction: rtl !important;
    text-align: right !important;
    transition: all 0.2s ease !important;
}

div[data-testid="stExpander"] summary:hover,
details[data-testid="stExpander"] > summary:hover {
    background: linear-gradient(90deg, rgba(245, 158, 11, 0.32) 0%, rgba(30, 41, 59, 0.78) 100%) !important;
    color: #ffffff !important;
}

div[data-testid="stExpander"] summary *,
details[data-testid="stExpander"] > summary * {
    color: #fde68a !important;
    font-weight: 900 !important;
    font-size: 0.96rem !important;
}

div[data-testid="stExpanderDetails"] {
    padding: 12px 16px 16px 16px !important;
    background: rgba(9, 13, 22, 0.42) !important;
    border-top: 1px solid rgba(251, 191, 36, 0.22) !important;
}

div[data-testid="stForm"] {
    background: rgba(15, 23, 42, 0.62) !important;
    border: 1px solid rgba(56, 189, 248, 0.28) !important;
    border-radius: 14px !important;
    padding: 12px 14px !important;
    margin-bottom: 10px !important;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
}

.target-glass-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.68) 0%, rgba(15, 23, 42, 0.82) 100%);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(148, 163, 184, 0.26);
    border-right: 4px solid #f59e0b;
    border-radius: 12px;
    padding: 8px 14px;
    margin-bottom: 6px;
    direction: rtl !important;
    text-align: right !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
}

.target-plat-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(245, 158, 11, 0.18);
    border: 1px solid rgba(251, 191, 36, 0.45);
    color: #fde68a;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 800;
    white-space: nowrap;
}

.target-url-pill {
    font-size: 0.84rem;
    color: #e2e8f0;
    direction: ltr;
    text-align: left;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 700;
    max-width: 460px;
}

/* تصميم زجاجي احترافي لشريط التبويبات وقائمة عرض النتائج حسب المنصة (st.tabs) */
div[data-baseweb="tab-list"] {
    gap: 8px !important;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.84) 0%, rgba(9, 13, 22, 0.92) 100%) !important;
    backdrop-filter: blur(22px) saturate(170%) !important;
    -webkit-backdrop-filter: blur(22px) saturate(170%) !important;
    padding: 8px 10px !important;
    border-radius: 16px !important;
    border: 1px solid rgba(56, 189, 248, 0.32) !important;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.42), inset 0 1px 1px rgba(255, 255, 255, 0.14) !important;
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
    scrollbar-width: thin;
    direction: rtl !important;
    margin-bottom: 12px !important;
}

div[data-baseweb="tab-highlight"],
div[data-baseweb="tab-border"] {
    display: none !important;
}

button[data-baseweb="tab"] {
    background: rgba(30, 41, 59, 0.52) !important;
    border: 1px solid rgba(148, 163, 184, 0.24) !important;
    color: #cbd5e1 !important;
    border-radius: 12px !important;
    padding: 9px 15px !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
    font-size: clamp(0.8rem, 1.35vw, 0.92rem) !important;
    white-space: nowrap !important;
    flex-shrink: 0 !important;
    transition: all 0.22s ease !important;
    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.22) !important;
}

button[data-baseweb="tab"]:hover {
    background: rgba(51, 65, 85, 0.72) !important;
    border-color: rgba(56, 189, 248, 0.55) !important;
    color: #ffffff !important;
    transform: translateY(-2px) !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, rgba(2, 132, 199, 0.88) 0%, rgba(37, 99, 235, 0.92) 100%) !important;
    border: 1.5px solid rgba(125, 211, 252, 0.9) !important;
    color: #ffffff !important;
    box-shadow: 0 6px 20px rgba(2, 132, 199, 0.48), inset 0 1px 1px rgba(255, 255, 255, 0.35) !important;
    transform: translateY(-1px) !important;
}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div {
    background-color: rgba(15, 23, 42, 0.88) !important;
    border-color: rgba(148, 163, 184, 0.32) !important;
    color: #f8fafc !important;
    border-radius: 12px !important;
    direction: rtl !important;
    text-align: right !important;
}

input {
    color: #f8fafc !important;
    direction: rtl !important;
    text-align: right !important;
}

@media (max-width: 768px) {
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"],
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 1 1 calc(50% - 8px) !important;
        min-width: 130px !important;
    }
    .hero-glass {
        flex-direction: column;
        align-items: flex-start;
    }
    .metrics-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    .news-card-layout {
        flex-direction: column !important;
    }
    .news-thumb-box {
        width: 100% !important;
        height: 165px !important;
    }
    .radar-panel {
        padding: 12px 14px;
        gap: 12px;
    }
    .radar-scanner {
        width: 46px;
        height: 46px;
        min-width: 46px;
    }
}
</style>
""")

# =====================================================================
# 13. تحميل الإعدادات والبيانات
# =====================================================================
cfg = load_credentials()
custom_targets = load_custom_targets()
monitor_state = load_monitor_state()
rt_state = get_shared_runtime()

with st.sidebar:
  st.markdown("### ⚙️ إعدادات المرصد القضائي")
  gemini_key_in = st.text_input(
      "مفتاح Gemini API", value=cfg.get("gemini_api_key", ""), type="password"
  )
  if gemini_key_in.strip() and gemini_key_in.strip() != cfg.get("gemini_api_key", ""):
    cfg["gemini_api_key"] = gemini_key_in.strip()
    if st is not None:
      st.session_state["gemini_api_key_live"] = gemini_key_in.strip()
    save_credentials(cfg)
    trigger_cloud_state_backup(async_mode=True)
  tg_token_in = st.text_input(
      "Telegram Bot Token",
      value=cfg.get("telegram_bot_token", DEFAULT_TG_TOKEN),
  )
  tg_chat_in = st.text_input(
      "Telegram Chat ID", value=cfg.get("telegram_chat_id", DEFAULT_TG_CHAT_ID)
  )
  auto_mon_in = st.toggle(
      "تفعيل الرصد الدوري التلقائي", value=bool(cfg.get("auto_monitor", True))
  )
  interval_options = list(INTERVAL_MAP.keys())
  curr_interval = cfg.get("monitor_interval", "كل 15 دقيقة")
  interval_in = st.selectbox(
      "فترة الرصد التلقائي",
      options=interval_options,
      index=interval_options.index(curr_interval)
      if curr_interval in interval_options
      else 0,
  )

  app_url_in = st.text_input(
      "🌐 رابط المنصة العام (لمنع السبات Keep-Alive)",
      value=cfg.get("app_public_url", _detect_public_app_url()),
      placeholder="https://your-app.streamlit.app",
  )

  if st.button("💾 حفظ الإعدادات وتحديث اسم البوت"):
    cfg["gemini_api_key"] = gemini_key_in.strip()
    cfg["telegram_bot_token"] = tg_token_in.strip() or DEFAULT_TG_TOKEN
    cfg["telegram_chat_id"] = tg_chat_in.strip() or DEFAULT_TG_CHAT_ID
    cfg["auto_monitor"] = bool(auto_mon_in)
    cfg["monitor_interval"] = interval_in
    cfg["app_public_url"] = app_url_in.strip()
    save_credentials(cfg)
    ensure_telegram_bot_branding_updated(cfg["telegram_bot_token"], cfg["telegram_chat_id"], force=True)
    _ping_keep_alive_endpoints()
    st.success("تم حفظ الإعدادات وتحديث اسم البوت إلى (المرصد القضائي) بنجاح")

  st.markdown("### ⚡ استمرارية الرصد 24/7 ومنع السبات")
  gh_workflow_yaml = """name: Al-Marsad Al-Qadai 24/7 Auto Monitor & Keep-Alive

on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:

jobs:
  monitor_and_keep_alive:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install requests beautifulsoup4 duckduckgo-search python-docx pillow

      - name: Run Headless Judicial Monitor & Wake Up App
        env:
          CRON_MODE: "1"
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          STREAMLIT_APP_URL: ${{ secrets.STREAMLIT_APP_URL }}
        run: |
          python app.py
"""
  st.download_button(
      "⚡ تحميل ملف GitHub Actions للرصد 24/7 بدون توقف",
      data=gh_workflow_yaml.encode("utf-8"),
      file_name="marsad_qadai_cron.yml",
      mime="text/yaml",
      help="ضعه في مسار .github/workflows/marsad_qadai_cron.yml في مستودع GitHub ليعمل الرصد التلقائي وإرسال الأخبار لتلغرام كل 15 دقيقة حتى لو دخل الموقع في وضع السبات.",
  )

  st.markdown("### 🗄️ النسخ الاحتياطي")
  if os.path.exists(ARCHIVE_JSON_FILE) and os.path.getsize(ARCHIVE_JSON_FILE) > 2:
    try:
      with open(ARCHIVE_JSON_FILE, "rb") as f_arch_dl:
        json_export_bytes = f_arch_dl.read()
    except Exception:
      json_export_bytes = b"[]"
  else:
    json_export_bytes = json.dumps(fetch_articles_from_db(), ensure_ascii=False, indent=2).encode("utf-8")
  st.download_button(
      "⬇️ تحميل أرشيف البيانات (JSON)",
      data=json_export_bytes,
      file_name="المرصد_القضائي_أرشيف.json",
      mime="application/json",
  )

  uploaded_backup = st.file_uploader("⬆️ استعادة أرشيف JSON", type=["json"])
  if uploaded_backup is not None:
    try:
      restored_list = json.loads(uploaded_backup.read().decode("utf-8"))
      if isinstance(restored_list, list):
        with open(ARCHIVE_JSON_FILE, "w", encoding="utf-8") as f:
          json.dump(restored_list, f, ensure_ascii=False, indent=2)
        restore_db_from_json_if_needed()
        purge_invalid_articles_from_db()
        st.success("تمت استعادة الأرشيف بنجاح")
        st.rerun()
    except Exception:
      st.error("ملف غير صالح")

# =====================================================================
# 14. الهيدر الرئيسي وشريط البحث المخصص وتحديد فترة البحث والروابط المخصصة
# =====================================================================
last_auto_ts = float(monitor_state.get("last_auto_run", 0))
last_auto_label = (
    format_relative_arabic(last_auto_ts) if last_auto_ts > 0 else "قيد الانطلاق"
)
auto_badge_text = (
    f"الرصد التلقائي نشط ({cfg.get('monitor_interval', 'كل 15 دقيقة')}) • آخر فحص: {last_auto_label}"
    if cfg.get("auto_monitor", True)
    else "الرصد اليدوي"
)

render_html(f"""
<div class="hero-glass" dir="rtl">
    <h1 class="hero-title">⚖️ المرصد القضائي</h1>
    <div class="status-pill" dir="rtl">
        <span class="pulse-dot"></span>
        <span>{html.escape(auto_badge_text)}</span>
    </div>
</div>
""")

col_kw, col_period = st.columns([2.8, 1.2])
with col_kw:
  kw_input = st.text_input(
      "🔍 تخصيص بكلمات مفتاحية (اختياري)",
      value=cfg.get("keywords_input", ""),
      placeholder="🔍 اتركه فارغاً للرصد القضائي العام، أو أدخل كلمات مفتاحية مفصولة بفاصلة...",
      label_visibility="collapsed",
  )
  if kw_input != cfg.get("keywords_input", ""):
    cfg["keywords_input"] = kw_input
    save_credentials(cfg)

with col_period:
  period_options = list(SEARCH_PERIOD_MAP.keys())
  curr_period = cfg.get("search_period", "آخر 7 أيام")
  selected_period = st.selectbox(
      "⏱️ فترة البحث",
      options=period_options,
      index=period_options.index(curr_period)
      if curr_period in period_options
      else 2,
      label_visibility="collapsed",
  )
  if selected_period != cfg.get("search_period", ""):
    cfg["search_period"] = selected_period
    save_credentials(cfg)

platform_kw_trackers = load_platform_keyword_trackers()
triggered_platform_kw_scan = None

render_html(f"""
<div class="custom-targets-header-card" dir="rtl" style="background:linear-gradient(135deg, rgba(14, 165, 233, 0.24) 0%, rgba(15, 23, 42, 0.82) 65%, rgba(30, 41, 59, 0.88) 100%);border:1px solid rgba(56, 189, 248, 0.55);border-right:5px solid #38bdf8;">
    <div class="custom-targets-header-right" dir="rtl">
        <span class="custom-targets-icon-box" style="background:rgba(56, 189, 248, 0.2);border-color:rgba(56, 189, 248, 0.6);">🔎</span>
        <div>
            <div class="custom-targets-main-title" style="color:#e0f2fe;">رصد منصة معينة من خلال كلمة مفتاحية</div>
            <div class="custom-targets-subtitle">اختر المنصة (مثل فيسبوك أو يوتيوب أو الصحف أو إكس) واكتب الكلمة المفتاحية لجلب وتتبع جميع المنشورات التي تخص تلك الكلمة المفتاحية</div>
        </div>
    </div>
    <span class="custom-targets-count-pill" style="background:rgba(14, 165, 233, 0.24);border-color:rgba(56, 189, 248, 0.6);color:#bae6fd;">📌 كلمات قيد التتبع: {len(platform_kw_trackers)}</span>
</div>
""")

with st.expander(
    f"🔎 فتح لوحة رصد وتتبع منصة معينة من خلال كلمة مفتاحية ({len(platform_kw_trackers)} كلمة متتبعة)",
    expanded=True,
):
  PLAT_KW_OPTIONS = {
      "🟦 فيسبوك (Facebook)": "فيسبوك",
      "📰 الصحف المغربية (المواقع الإخبارية)": "الصحف",
      "🟥 يوتيوب (YouTube)": "يوتيوب",
      "⬛ منصة إكس (X / Twitter)": "إكس",
      "🟪 منصات أخرى (تيك توك • إنستغرام • لينكدإن)": "أخرى",
      "🚀 جميع المنصات (شامل)": "شامل",
  }
  pkw_c1, pkw_c2, pkw_c3, pkw_c4 = st.columns([1.45, 2.15, 1.25, 1.15])
  with pkw_c1:
    chosen_plat_label = st.selectbox(
        "اختر المنصة",
        options=list(PLAT_KW_OPTIONS.keys()),
        index=0,
        key="plat_kw_select_box",
        label_visibility="collapsed",
    )
    chosen_plat_val = PLAT_KW_OPTIONS[chosen_plat_label]
  with pkw_c2:
    typed_plat_kw = st.text_input(
        "الكلمة المفتاحية المراد تتبعها على المنصة",
        placeholder="✍️ اكتب الكلمة أو العبارة المفتاحية المراد جلب منشوراتها...",
        key="plat_kw_text_input",
        label_visibility="collapsed",
    )
  with pkw_c3:
    try:
      scan_now_pkw = st.button(
          "🚀 رصد وجلب المنشورات الآن",
          key="btn_scan_plat_kw_now",
          type="primary",
          use_container_width=True,
      )
    except TypeError:
      scan_now_pkw = st.button(
          "🚀 رصد وجلب المنشورات الآن",
          key="btn_scan_plat_kw_now",
      )
    if scan_now_pkw:
      if typed_plat_kw.strip():
        clear_stop_scan()
        triggered_platform_kw_scan = (chosen_plat_val, typed_plat_kw.strip())
        st.session_state["active_platform_kw_filter"] = {
            "platform": chosen_plat_val,
            "keyword": typed_plat_kw.strip(),
        }
      else:
        st.warning("⚠️ يرجى كتابة الكلمة المفتاحية أولاً قبل الضغط على زر الرصد.")
  with pkw_c4:
    save_track_pkw = st.button(
        "📌 تثبيت في التتبع التلقائي",
        key="btn_save_plat_kw_tracker",
        use_container_width=True,
    )
    if save_track_pkw:
      if typed_plat_kw.strip():
        platform_kw_trackers.append(
            {"platform": chosen_plat_val, "keyword": typed_plat_kw.strip()}
        )
        save_platform_keyword_trackers(platform_kw_trackers)
        clear_stop_scan()
        triggered_platform_kw_scan = (chosen_plat_val, typed_plat_kw.strip())
        st.session_state["active_platform_kw_filter"] = {
            "platform": chosen_plat_val,
            "keyword": typed_plat_kw.strip(),
        }
      else:
        st.warning("⚠️ يرجى كتابة الكلمة المفتاحية أولاً لتثبيتها في التتبع.")

  if platform_kw_trackers:
    render_html(
        "<div style='font-size:0.82rem;font-weight:800;color:#7dd3fc;margin:8px 0 6px 0;direction:rtl;text-align:right;'>"
        "📌 الكلمات المفتاحية المثبتة للرصد والتتبع التلقائي حسب المنصة:"
        "</div>"
    )
    plat_badge_icons = {
        "فيسبوك": "🟦 فيسبوك",
        "الصحف": "📰 الصحف",
        "يوتيوب": "🟥 يوتيوب",
        "إكس": "⬛ إكس",
        "أخرى": "🟪 منصات أخرى",
        "شامل": "🚀 جميع المنصات",
    }
    for k_idx, k_item in enumerate(list(platform_kw_trackers)):
      kc1, kc2, kc3, kc4 = st.columns([3.4, 1.0, 1.0, 0.7])
      k_plat = k_item.get("platform", "فيسبوك")
      k_word = k_item.get("keyword", "")
      k_badge = plat_badge_icons.get(k_plat, f"📡 {k_plat}")
      with kc1:
        render_html(
            f"""
            <div class="target-glass-item" dir="rtl" style="border-right-color:#38bdf8;">
                <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;direction:rtl;">
                    <span class="target-plat-chip" style="background:rgba(56,189,248,0.18);border-color:rgba(56,189,248,0.45);color:#7dd3fc;">{html.escape(k_badge)}</span>
                    <span style="font-weight:900;color:#f8fafc;font-size:0.92rem;">🔍 الكلمة المتتبعة: «{html.escape(k_word)}»</span>
                </div>
            </div>
            """
        )
      with kc2:
        if st.button("▶ رصد الآن", key=f"run_pkw_{k_idx}", use_container_width=True):
          clear_stop_scan()
          triggered_platform_kw_scan = (k_plat, k_word)
          st.session_state["active_platform_kw_filter"] = {
              "platform": k_plat,
              "keyword": k_word,
          }
      with kc3:
        if st.button("👁️ عرض المنشورات", key=f"view_pkw_{k_idx}", use_container_width=True):
          st.session_state["active_platform_kw_filter"] = {
              "platform": k_plat,
              "keyword": k_word,
          }
          st.rerun()
      with kc4:
        if st.button("🗑️", key=f"del_pkw_{k_idx}", help="حذف هذه الكلمة من التتبع", use_container_width=True):
          platform_kw_trackers.pop(k_idx)
          save_platform_keyword_trackers(platform_kw_trackers)
          st.rerun()

render_html(f"""
<div class="custom-targets-header-card" dir="rtl">
    <div class="custom-targets-header-right" dir="rtl">
        <span class="custom-targets-icon-box">🎯</span>
        <div>
            <div class="custom-targets-main-title">الرصد المخصص وإدارة القنوات والصفحات</div>
            <div class="custom-targets-subtitle">رصد مخصص ودقيق لصفحات فيسبوك وقنوات يوتيوب وحسابات إكس والمواقع الإخبارية المحددة</div>
        </div>
    </div>
    <span class="custom-targets-count-pill">📌 المصادر المفعلة: {len(custom_targets)}</span>
</div>
""")

with st.expander(
    f"⚙️ فتح لوحة التحكم في الروابط والقنوات والصفحات المخصصة ({len(custom_targets)} مصدر)", expanded=False
):
  render_html(
      "<div style='font-size:0.84rem;color:#cbd5e1;margin-bottom:8px;direction:rtl;text-align:right;'>"
      "أضف رابط أي صفحة فيسبوك أو قناة يوتيوب أو حساب إكس أو موقع إخباري (أو اكتب اسم القناة/الصفحة مباشرة) لرصد أحدث منشوراتها وفيديوهاتها بدقة:"
      "</div>"
  )
  with st.form("add_custom_target_form", clear_on_submit=True):
    c_u, c_k, c_b = st.columns([2.6, 1.4, 0.9])
    with c_u:
      new_t_url = st.text_input(
          "الرابط",
          placeholder="🔗 رابط صفحة فيسبوك / قناة يوتيوب / حساب إكس أو اسم القناة/الصفحة...",
          label_visibility="collapsed",
      )
    with c_k:
      new_t_kw = st.text_input(
          "كلمة (اختياري)",
          placeholder="🔍 كلمة فلترة داخل الصفحة (اختياري)...",
          label_visibility="collapsed",
      )
    with c_b:
      add_t_btn = st.form_submit_button("➕ إضافة المصدر")
    if add_t_btn and new_t_url.strip():
      custom_targets.append(
          {"url": new_t_url.strip(), "keyword": new_t_kw.strip()}
      )
      save_custom_targets(custom_targets)
      st.rerun()

  plat_icon_map = {
      "يوتيوب": "🟥 قناة يوتيوب",
      "فيسبوك": "🟦 صفحة فيسبوك",
      "إكس": "⬛ حساب إكس",
      "الصحف": "📰 موقع إخباري",
      "أخرى": "🟪 منصة رقمية",
      "شامل": "🎯 اسم مخصص",
  }
  for idx, t_item in enumerate(list(custom_targets)):
    tc1, tc2 = st.columns([5.2, 0.9])
    t_parsed = parse_custom_target_identity(t_item.get("url", ""))
    p_badge = plat_icon_map.get(t_parsed.get("platform", "شامل"), "🎯 مصدر مخصص")
    disp_name = t_parsed.get("display_label") or t_item.get("url", "")
    kw_chip = (
        f"<span style='background:rgba(56,189,248,0.18);border:1px solid rgba(56,189,248,0.4);color:#7dd3fc;padding:2px 8px;border-radius:999px;font-size:0.73rem;font-weight:800;'>🔍 {html.escape(t_item['keyword'])}</span>"
        if t_item.get("keyword")
        else ""
    )
    with tc1:
      render_html(
          f"""
          <div class="target-glass-item" dir="rtl">
              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;direction:rtl;">
                  <span class="target-plat-chip">{p_badge}</span>
                  <span style="font-weight:900;color:#f8fafc;font-size:0.88rem;">{html.escape(disp_name)}</span>
                  {kw_chip}
              </div>
              <div class="target-url-pill" title="{html.escape(t_item['url'])}">🔗 {html.escape(t_item['url'])}</div>
          </div>
          """
      )
    with tc2:
      if st.button("🗑️ حذف", key=f"del_target_{idx}"):
        custom_targets.pop(idx)
        save_custom_targets(custom_targets)
        st.rerun()

# =====================================================================
# 15. لوحة بطاقات الرصد الزجاجية الشفافة (اسم المنصة كاملاً + زر التشغيل ▶ وزر الإيقاف ⏹)
# =====================================================================
SCAN_MODES = [
    ("all", "الرصد الشامل", "جميع المنصات والمصادر", "شامل", "🚀", "scan-frame-all"),
    ("press", "الصحف المغربية", "المواقع والجرائد الوطنية", "صحافة", "📰", "scan-frame-press"),
    ("fb", "منصة فيسبوك", "الصفحات والمنشورات العامة", "فيسبوك", "🟦", "scan-frame-fb"),
    ("x", "منصة إكس (X)", "التغريدات والحسابات", "إكس", "⬛", "scan-frame-x"),
    ("yt", "منصة يوتيوب", "القنوات والفيديوهات", "يوتيوب", "🟥", "scan-frame-yt"),
    ("other", "منصات أخرى", "تيك توك • إنستغرام • لينكدإن", "أخرى", "🟪", "scan-frame-other"),
    ("target", "الرصد المخصص", f"القنوات والصفحات المحددة ({len(custom_targets)})", "مخصص", "🎯", "scan-frame-target"),
]

triggered_mode = None

# توزيع البطاقات الزجاجية في شبكتين متناسقتين بمساحة رحبة تضمن ظهور اسم المنصة كاملاً وبوضوح تام
row1_modes = SCAN_MODES[:4]
row2_modes = SCAN_MODES[4:]

for row_modes in (row1_modes, row2_modes):
  row_cols = st.columns(len(row_modes))
  for col_idx, (mode_key, mode_title, mode_sub, mode_badge, mode_icon, frame_cls) in enumerate(row_modes):
    with row_cols[col_idx]:
      with st.container():
        render_html(
            f"""
            <span class="scan-frame-marker {frame_cls}" style="display:none;"></span>
            <div class="scan-platform-header" dir="rtl">
                <div class="scan-platform-right" dir="rtl">
                    <span class="scan-platform-icon">{mode_icon}</span>
                    <div>
                        <div class="scan-platform-title">{html.escape(mode_title)}</div>
                        <div class="scan-platform-sub">{html.escape(mode_sub)}</div>
                    </div>
                </div>
                <span class="scan-platform-badge">{html.escape(mode_badge)}</span>
            </div>
            """
        )
        c_play, c_stop = st.columns(2)
        with c_play:
          render_html('<span class="media-play-marker" style="display:none;"></span>')
          try:
            play_clicked = st.button(
                "▶ تشغيل",
                key=f"start_scan_{mode_key}",
                help=f"تشغيل {mode_title}",
                type="primary",
                use_container_width=True,
            )
          except TypeError:
            play_clicked = st.button(
                "▶ تشغيل",
                key=f"start_scan_{mode_key}",
                help=f"تشغيل {mode_title}",
            )
          if play_clicked:
            clear_stop_scan()
            triggered_mode = mode_key
        with c_stop:
          render_html('<span class="media-stop-marker" style="display:none;"></span>')
          try:
            stop_clicked = st.button(
                "⏹ إيقاف",
                key=f"stop_scan_{mode_key}",
                help=f"إيقاف {mode_title}",
                type="secondary",
                use_container_width=True,
            )
          except TypeError:
            stop_clicked = st.button(
                "⏹ إيقاف",
                key=f"stop_scan_{mode_key}",
                help=f"إيقاف {mode_title}",
            )
          if stop_clicked:
            request_stop_scan()

# =====================================================================
# 16. منطقة الرادار الدوار 360° وشريط التقدم ومؤشر DONE
# =====================================================================
radar_placeholder = st.empty()
progress_placeholder = st.empty()
done_placeholder = st.empty()


def execute_interactive_scan(mode_key: str):
  clear_stop_scan()
  rt_state["active_scan"] = mode_key
  s_period = cfg.get("search_period", "آخر 7 أيام")

  def update_ui_progress(pct: float, status_msg: str):
    pct_int = max(5, min(100, int(pct * 100)))
    render_html(
        f"""
        <div class="radar-panel" dir="rtl">
            <div class="radar-scanner"></div>
            <div style="flex:1;direction:rtl;text-align:right;">
                <div style="font-size:1rem;font-weight:800;color:#38bdf8;margin-bottom:3px;">
                    📡 {html.escape(clean_display_text(status_msg))}
                </div>
                <div style="font-size:0.82rem;color:#94a3b8;">
                    مسح ذكي بزاوية 360° ({html.escape(s_period)})... ({pct_int}%)
                </div>
            </div>
        </div>
        """,
        target=radar_placeholder,
    )
    progress_placeholder.progress(pct_int / 100.0)

  kw = cfg.get("keywords_input", "")
  collected = []
  is_target_mode = mode_key == "target"

  if mode_key == "all":
    steps = [
        ("الصحف المغربية", lambda cb: scrape_moroccan_press(kw, s_period, cb)),
        ("يوتيوب", lambda cb: scrape_youtube_platform(kw, s_period, cb)),
        ("فيسبوك", lambda cb: scrape_facebook_platform(kw, s_period, cb)),
        ("منصة إكس", lambda cb: scrape_x_platform(kw, s_period, cb)),
        (
            "تيك توك وإنستغرام ولينكدإن",
            lambda cb: scrape_other_platforms(kw, s_period, cb),
        ),
        (
            "الروابط والقنوات المخصصة",
            lambda cb: scrape_custom_targets(custom_targets, kw, s_period, cb),
        ),
    ]
    for s_idx, (s_name, s_fn) in enumerate(steps):
      if is_stop_requested():
        break
      base_p = s_idx / len(steps)
      span_p = 1.0 / len(steps)
      collected.extend(
          s_fn(
              lambda sub_p, msg, bp=base_p, sp=span_p: update_ui_progress(
                  bp + sub_p * sp, msg
              )
          )
      )
  elif mode_key == "press":
    collected = scrape_moroccan_press(kw, s_period, update_ui_progress)
  elif mode_key == "fb":
    collected = scrape_facebook_platform(kw, s_period, update_ui_progress)
  elif mode_key == "x":
    collected = scrape_x_platform(kw, s_period, update_ui_progress)
  elif mode_key == "yt":
    collected = scrape_youtube_platform(kw, s_period, update_ui_progress)
  elif mode_key == "other":
    collected = scrape_other_platforms(kw, s_period, update_ui_progress)
  elif mode_key == "target":
    collected = scrape_custom_targets(
        custom_targets, kw, s_period, update_ui_progress
    )

  if not is_stop_requested():
    update_ui_progress(
        0.94, "استخراج صور المقالات ومتونها وتلخيصها عبر Gemini AI..."
    )
    added_count = quick_process_and_save(
        collected, cfg, is_target_run=is_target_mode
    )
    update_ui_progress(1.0, "اكتملت عملية الرصد بنجاح")
    time.sleep(0.25)
    rt_state["last_done_mode"] = mode_key
    rt_state["last_done_count"] = added_count
    rt_state["last_done_ts"] = time.time()
  else:
    rt_state["last_done_mode"] = "stopped"
    rt_state["last_done_count"] = 0
    rt_state["last_done_ts"] = time.time()

  rt_state["active_scan"] = None
  radar_placeholder.empty()
  progress_placeholder.empty()


def execute_platform_keyword_scan(target_platform: str, target_keyword: str):
  """تنفيذ رصد مباشر وعميق لمنصة محددة من خلال كلمة مفتاحية معينة وحفظ كافة المنشورات المطابقة."""
  clear_stop_scan()
  rt_state["active_scan"] = f"pkw_{target_platform}"
  s_period = cfg.get("search_period", "آخر 7 أيام")

  def update_pkw_progress(pct: float, status_msg: str):
    pct_int = max(5, min(100, int(pct * 100)))
    render_html(
        f"""
        <div class="radar-panel" dir="rtl">
            <div class="radar-scanner"></div>
            <div style="flex:1;direction:rtl;text-align:right;">
                <div style="font-size:1rem;font-weight:800;color:#38bdf8;margin-bottom:3px;">
                    📡 رصد منصة ({html.escape(target_platform)}) للكلمة المفتاحية «{html.escape(target_keyword)}»: {html.escape(clean_display_text(status_msg))}
                </div>
                <div style="font-size:0.82rem;color:#94a3b8;">
                    جلب كافة المنشورات المطابقة للكلمة المفتاحية خلال ({html.escape(s_period)})... ({pct_int}%)
                </div>
            </div>
        </div>
        """,
        target=radar_placeholder,
    )
    progress_placeholder.progress(pct_int / 100.0)

  update_pkw_progress(0.10, f"بدء مسح منصة {target_platform} عن «{target_keyword}»...")
  collected = scrape_platform_by_keyword(
      target_platform, target_keyword, s_period, progress_cb=update_pkw_progress
  )
  if not is_stop_requested():
    update_pkw_progress(
        0.92, f"تم العثور على {len(collected)} منشور مطابق — جاري استخلاص المتون وتلخيصها..."
    )
    added_count = quick_process_and_save(
        collected, cfg, is_target_run=False, custom_kw_override=target_keyword
    )
    update_pkw_progress(1.0, "اكتمل رصد الكلمة المفتاحية على المنصة بنجاح")
    time.sleep(0.25)
    rt_state["last_done_mode"] = f"pkw:{target_platform}:{target_keyword}"
    rt_state["last_done_count"] = added_count
    rt_state["last_done_ts"] = time.time()
  else:
    rt_state["last_done_mode"] = "stopped"
    rt_state["last_done_count"] = 0
    rt_state["last_done_ts"] = time.time()

  rt_state["active_scan"] = None
  radar_placeholder.empty()
  progress_placeholder.empty()


if triggered_platform_kw_scan:
  execute_platform_keyword_scan(triggered_platform_kw_scan[0], triggered_platform_kw_scan[1])
elif triggered_mode:
  execute_interactive_scan(triggered_mode)

if time.time() - float(rt_state.get("last_done_ts", 0)) < 25:
  if rt_state.get("last_done_mode") == "stopped":
    render_html(
        """
        <div class="done-banner" dir="rtl" style="background:rgba(127,29,29,0.85);border-color:#f87171;">
            <span>🛑 تم إيقاف عملية الرصد بطلب من المستخدم</span>
            <span>STOPPED</span>
        </div>
        """,
        target=done_placeholder,
    )
  elif rt_state.get("last_done_mode"):
    c_new = int(rt_state.get("last_done_count", 0))
    render_html(
        f"""
        <div class="done-banner" dir="rtl">
            <span>✨ تـم بنجاح / DONE — تم رصد وتحديث القاعدة ({c_new} منشور/خبر جديد)</span>
            <span>100% DONE ✅</span>
        </div>
        """,
        target=done_placeholder,
    )

# =====================================================================
# 17. فرز الأخبار زمنياً (الأحدث أولاً) وفصل الأخبار النشطة (24 ساعة من الرصد) عن الأرشيف
# =====================================================================
all_articles = fetch_articles_from_db()
now_ts = time.time()
selected_period_sec = get_period_config(cfg.get("search_period", "آخر 7 أيام"))[
    "sec"
]

live_articles = []
archive_articles = []
for a in all_articles:
  pub_t = float(a.get("pub_timestamp", 0))
  mon_t = float(a.get("created_at") or pub_t)
  if mon_t <= 0:
    mon_t = pub_t
  # التقيد بفترة البحث المختارة مع السماح بعرض المنشورات المرصودة حديثاً عبر تتبع الكلمات المفتاحية (#kwtrack=)
  has_kwtrack_tag = "#kwtrack=" in str(a.get("url") or "")
  is_within_selected_period = (selected_period_sec <= 0) or ((now_ts - pub_t) <= selected_period_sec)
  is_monitored_within_24h = (now_ts - mon_t) < 86400
  if (is_within_selected_period or has_kwtrack_tag) and (is_monitored_within_24h or a.get("platform") == "يوتيوب"):
    live_articles.append(a)
  else:
    archive_articles.append(a)

active_kw_query = cfg.get("keywords_input", "").strip()
if active_kw_query:
  live_articles = [
      a
      for a in live_articles
      if matches_custom_keywords(
          a.get("title", ""),
          f"{a.get('summary', '')} {a.get('raw_snippet', '')} {a.get('source_name', '')}",
          active_kw_query,
      )
  ]
  archive_articles = [
      a
      for a in archive_articles
      if matches_custom_keywords(
          a.get("title", ""),
          f"{a.get('summary', '')} {a.get('raw_snippet', '')} {a.get('source_name', '')}",
          active_kw_query,
      )
  ]
  render_html(
      f"""
      <div style="background:linear-gradient(90deg, rgba(2,132,199,0.25) 0%, rgba(15,23,42,0.85) 100%);border:1px solid rgba(56,189,248,0.5);border-right:4px solid #38bdf8;border-radius:12px;padding:9px 16px;margin:6px 0 12px 0;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;direction:rtl;text-align:right;">
          <span style="color:#e0f2fe;font-weight:800;font-size:0.88rem;">🔍 الفلترة الدقيقة بالكلمات المفتاحية نشطة: <strong style="color:#38bdf8;">«{html.escape(active_kw_query)}»</strong> — يتم عرض الأخبار والمنشورات المطابقة فقط ({len(live_articles)} نشط • {len(archive_articles)} في الأرشيف)</span>
          <span style="color:#94a3b8;font-size:0.78rem;font-weight:700;">امسح حقل الكلمات المفتاحية أعلاه لعرض كافة الأخبار</span>
      </div>
      """
  )

live_articles.sort(key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True)
archive_articles.sort(
    key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
)

press_live = [a for a in live_articles if a.get("platform") == "الصحف"]
fb_live = [a for a in live_articles if a.get("platform") == "فيسبوك"]
x_live = [a for a in live_articles if a.get("platform") == "إكس"]
yt_live = [a for a in live_articles if a.get("platform") == "يوتيوب"]
other_live = [a for a in live_articles if a.get("platform") == "أخرى"]
target_live = [
    a
    for a in live_articles
    if int(a.get("is_custom_target", 0)) == 1
    and belongs_to_any_custom_target(a, custom_targets)
]

metrics_data = [
    ("🌐 الكل (النشط)", len(live_articles)),
    ("📰 الصحف", len(press_live)),
    ("🟦 فيسبوك", len(fb_live)),
    ("⬛ إكس", len(x_live)),
    ("🟥 يوتيوب", len(yt_live)),
    ("🎯 المخصص", len(target_live)),
    ("🗄️ الأرشيف", len(archive_articles)),
]
metrics_cards_html = "".join(
    f'<div class="metric-glass" dir="rtl"><div class="metric-num">{m_val}</div><div class="metric-lbl">{m_label}</div></div>'
    for m_label, m_val in metrics_data
)
render_html(f'<div class="metrics-grid" dir="rtl">{metrics_cards_html}</div>')



def _format_verbatim_article_paragraphs_html(verbatim_text: str, title_text: str) -> str:
  """تنسيق النص الأصلي الكامل للخبر أو المنشور حرفياً كما ورد في المصدر في فقرات واضحة دون استبداله بالملخص."""
  cleaned_full = clean_full_article_text(verbatim_text)
  if not cleaned_full:
    cleaned_full = title_text
  paras = [p.strip() for p in re.split(r"\n\n+", cleaned_full) if p.strip()]
  if len(paras) == 1 and len(paras[0]) > 420:
    sents = [s.strip() for s in re.split(r"(?<=[.!؟])\s+", paras[0]) if s.strip()]
    grouped = []
    buf = []
    for s in sents:
      buf.append(s)
      if len(" ".join(buf)) >= 280:
        grouped.append(" ".join(buf))
        buf = []
    if buf:
      grouped.append(" ".join(buf))
    paras = grouped if grouped else paras

  return "".join(f"<p>{html.escape(p)}</p>" for p in paras)


if st is not None and "active_tts_audio" not in st.session_state:
  st.session_state["active_tts_audio"] = {}
if st is not None and "active_yt_transcripts" not in st.session_state:
  st.session_state["active_yt_transcripts"] = {}
if st is not None and "selected_export_articles" not in st.session_state:
  st.session_state["selected_export_articles"] = {}


def _render_youtube_transcript_component(transcript_text: str, video_title: str, source_name: str, video_url: str):
  """عرض لوحة التفريغ الصوتي الكامل للفيديو باللغة العربية الفصحى السليمة 100% مع زر نسخ النص الفوري."""
  paras_html = _format_verbatim_article_paragraphs_html(transcript_text, video_title)
  render_html(
      f"""
      <div style="background:linear-gradient(145deg, rgba(15, 23, 42, 0.96) 0%, rgba(30, 41, 59, 0.94) 100%);border:1.5px solid rgba(248, 113, 113, 0.65);border-right:5px solid #ef4444;border-radius:16px;padding:16px 20px;margin:8px 0 10px 0;box-shadow:0 12px 28px rgba(0,0,0,0.45);direction:rtl;text-align:right;">
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;padding-bottom:10px;margin-bottom:12px;border-bottom:1px solid rgba(248, 113, 113, 0.28);">
              <div style="display:flex;align-items:center;gap:8px;direction:rtl;">
                  <span style="background:rgba(239,68,68,0.22);border:1px solid rgba(248,113,113,0.6);color:#fca5a5;padding:3px 11px;border-radius:999px;font-size:0.78rem;font-weight:900;">📝 التفريغ الصوتي للفيديو (عربي فصيح 100%)</span>
                  <span style="font-weight:800;color:#e2e8f0;font-size:0.86rem;">{html.escape(source_name)}</span>
              </div>
              <span style="color:#6ee7b7;font-size:0.78rem;font-weight:800;">✅ مدقق لغوياً وخالٍ من الأخطاء</span>
          </div>
          <div class="full-article-body" dir="rtl" style="font-size:0.96rem;line-height:1.95;color:#f8fafc;">
              {paras_html}
          </div>
      </div>
      """
  )


def _render_interactive_audio_component(audio_b64: str, mime_type: str, spoken_text: str, label_text: str, auto_play: bool = True, api_key: str = ''):
  """مشغل صوتي تفاعلي مدمج يعمل بتقنية HTML5 Audio Blob + Web Speech API الاحتياطي لضمان عمل الصوت في جميع المتصفحات 100%."""
  try:
    import streamlit.components.v1 as components
  except Exception:
    return

  safe_label = html.escape(label_text)
  text_json = json.dumps(prepare_arabic_text_for_speech(spoken_text, max_chars=3600), ensure_ascii=False)
  auto_js = "true" if auto_play else "false"

  comp_html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@600;700;800&display=swap');
  * {{ box-sizing: border-box; font-family: 'Cairo', sans-serif; }}
  body {{
    margin: 0; padding: 0; background: transparent; color: #f8fafc; direction: rtl; overflow: hidden;
  }}
  .tts-box {{
    background: linear-gradient(135deg, rgba(6, 78, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%);
    border: 1.5px solid rgba(52, 211, 153, 0.7);
    border-radius: 14px;
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
  }}
  .tts-top {{
    display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap;
  }}
  .tts-title {{
    font-size: 0.84rem; font-weight: 800; color: #6ee7b7; display: flex; align-items: center; gap: 6px;
  }}
  .tts-controls {{
    display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
  }}
  .tts-btn {{
    background: rgba(16, 185, 129, 0.25);
    border: 1px solid rgba(52, 211, 153, 0.65);
    color: #ecfdf5;
    border-radius: 8px;
    padding: 3px 10px;
    font-size: 0.78rem;
    font-weight: 800;
    cursor: pointer;
    transition: all 0.15s ease;
  }}
  .tts-btn:hover {{
    background: rgba(16, 185, 129, 0.5);
    border-color: #ffffff;
  }}
  .tts-btn.stop {{
    background: rgba(239, 68, 68, 0.28);
    border-color: rgba(252, 165, 165, 0.65);
  }}
  audio {{
    width: 100%; height: 36px; border-radius: 8px; outline: none;
  }}
</style>
</head>
<body>
<div class="tts-box" dir="rtl">
  <div class="tts-top">
    <div class="tts-title">
      <span id="statusIcon">🎙️</span>
      <span id="statusText">{safe_label}</span>
    </div>
    <div class="tts-controls">
      <button class="tts-btn" onclick="togglePlay()">⏯️ تشغيل / إيقاف مؤقت</button>
      <button class="tts-btn stop" onclick="restartAudio()">🔄 من البداية</button>
      <button class="tts-btn" onclick="cycleSpeed()" id="speedBtn">⚡ السرعة: 1x</button>
    </div>
  </div>
  <audio id="mainAudio" controls preload="auto"></audio>
</div>
<script>
(function() {{
  const b64Data = "{audio_b64}";
  const mimeType = "{mime_type}" || "audio/mpeg";
  const fallbackText = {text_json};
  const shouldAutoPlay = {auto_js};
  const geminiKey = {json.dumps(str(api_key or "").strip())};
  const audioEl = document.getElementById("mainAudio");
  const statusText = document.getElementById("statusText");
  const speedBtn = document.getElementById("speedBtn");
  const speeds = [1.0, 1.25, 1.5];
  let speedIdx = 0;
  let usingWebSpeech = false;

  function b64ToBlobUrl(b64, mime) {{
    const binStr = atob(b64);
    const len = binStr.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {{
      bytes[i] = binStr.charCodeAt(i);
    }}
    const blob = new Blob([bytes], {{ type: mime }});
    return URL.createObjectURL(blob);
  }}

  let streamChunks = [];
  let streamIdx = 0;
  let usingStreamFallback = false;

  function buildTextChunks(txt) {{
    const rawSents = (txt || "").split(/(?<=[.!؟،؛:])\\s+/);
    const out = [];
    let cur = "";
    for (const s of rawSents) {{
      if ((cur + " " + s).trim().length <= 150) {{
        cur = (cur + " " + s).trim();
      }} else {{
        if (cur) out.push(cur);
        if (s.length <= 150) {{
          cur = s.trim();
        }} else {{
          const words = s.split(/\\s+/);
          let wb = "";
          for (const w of words) {{
            if ((wb + " " + w).trim().length <= 150) wb = (wb + " " + w).trim();
            else {{ if (wb) out.push(wb); wb = w; }}
          }}
          cur = wb;
        }}
      }}
    }}
    if (cur) out.push(cur);
    return out.slice(0, 28);
  }}

  function speakViaWebSpeech() {{
    if (!("speechSynthesis" in window) || !fallbackText) return;
    usingWebSpeech = true;
    window.speechSynthesis.cancel();
    const sents = fallbackText.split(/(?<=[.!؟،؛])\\s+/);
    sents.forEach((s) => {{
      if (!s.trim()) return;
      const u = new SpeechSynthesisUtterance(s.trim());
      u.lang = "ar-SA";
      u.rate = speeds[speedIdx];
      const voices = window.speechSynthesis.getVoices();
      const arVoice = voices.find(v => v.lang && v.lang.toLowerCase().startsWith("ar"));
      if (arVoice) u.voice = arVoice;
      window.speechSynthesis.speak(u);
    }});
    statusText.textContent = "{safe_label} (قراءة صوتية نشطة 🔊)";
  }}

  function startClientStreamFallback() {{
    streamChunks = buildTextChunks(fallbackText);
    if (!streamChunks.length) {{
      speakViaWebSpeech();
      return;
    }}
    usingStreamFallback = true;
    streamIdx = 0;
    audioEl.style.display = "block";
    audioEl.setAttribute("referrerpolicy", "no-referrer");
    playNextStreamChunk();
  }}

  function playNextStreamChunk() {{
    if (!usingStreamFallback || streamIdx >= streamChunks.length) {{
      statusText.textContent = "{safe_label} (اكتملت القراءة الصوتية ✅)";
      return;
    }}
    const q = encodeURIComponent(streamChunks[streamIdx]);
    audioEl.src = "https://translate.googleapis.com/translate_tts?client=gtx&ie=UTF-8&tl=ar&dt=t&q=" + q;
    audioEl.playbackRate = speeds[speedIdx];
    statusText.textContent = "{safe_label} (مقطع " + (streamIdx + 1) + "/" + streamChunks.length + " 🔊)";
    audioEl.onended = function() {{
      streamIdx += 1;
      playNextStreamChunk();
    }};
    audioEl.onerror = function() {{
      usingStreamFallback = false;
      speakViaWebSpeech();
    }};
    audioEl.play().catch(() => {{
      statusText.textContent = "{safe_label} — اضغط ▶ للتشغيل";
    }});
  }}

  if (b64Data && b64Data.length > 100) {{
    try {{
      const blobUrl = b64ToBlobUrl(b64Data, mimeType);
      audioEl.src = blobUrl;
      if (shouldAutoPlay) {{
        const p = audioEl.play();
        if (p !== undefined) {{
          p.then(() => {{
            statusText.textContent = "{safe_label} (يعمل الآن 🔊)";
          }}).catch(() => {{
            statusText.textContent = "{safe_label} — اضغط ▶ للتشغيل";
          }});
        }}
      }}
    }} catch (e) {{
      startClientStreamFallback();
    }}
  }} else {{
    tryBrowserGeminiTtsOrStream();
  }}

  function pcm16B64ToWavBlobUrl(pcmB64, sampleRate) {{
    const binStr = atob(pcmB64);
    const pcmLen = binStr.length;
    const wavBuffer = new ArrayBuffer(44 + pcmLen);
    const view = new DataView(wavBuffer);
    function writeStr(offset, s) {{
      for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i));
    }}
    writeStr(0, "RIFF");
    view.setUint32(4, 36 + pcmLen, true);
    writeStr(8, "WAVE");
    writeStr(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeStr(36, "data");
    view.setUint32(40, pcmLen, true);
    const bytes = new Uint8Array(wavBuffer, 44);
    for (let i = 0; i < pcmLen; i++) bytes[i] = binStr.charCodeAt(i);
    const blob = new Blob([wavBuffer], {{ type: "audio/wav" }});
    return URL.createObjectURL(blob);
  }}

  async function tryBrowserGeminiTtsOrStream() {{
    if (geminiKey && fallbackText) {{
      try {{
        statusText.textContent = "{safe_label} (جاري التوليد الصوتي عبر Gemini AI...)";
        const resp = await fetch(
          "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key=" + encodeURIComponent(geminiKey),
          {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{
              contents: [{{ parts: [{{ text: fallbackText.slice(0, 900) }}] }}],
              generationConfig: {{
                responseModalities: ["AUDIO"],
                speechConfig: {{
                  voiceConfig: {{ prebuiltVoiceConfig: {{ voiceName: "Aoede" }} }}
                }}
              }}
            }})
          }}
        );
        if (resp.ok) {{
          const data = await resp.json();
          const parts = (((data.candidates || [])[0] || {{}}).content || {{}}).parts || [];
          for (const p of parts) {{
            const inl = p.inlineData || p.inline_data;
            if (inl && inl.data) {{
              const wavUrl = pcm16B64ToWavBlobUrl(inl.data, 24000);
              audioEl.src = wavUrl;
              audioEl.play().then(() => {{
                statusText.textContent = "{safe_label} (يعمل الآن عبر Gemini AI 🔊)";
              }}).catch(() => {{
                statusText.textContent = "{safe_label} — اضغط ▶ للتشغيل";
              }});
              return;
            }}
          }}
        }}
      }} catch (err) {{}}
    }}
    startClientStreamFallback();
  }}

  window.togglePlay = function() {{
    if (usingWebSpeech && "speechSynthesis" in window) {{
      if (window.speechSynthesis.speaking) {{
        if (window.speechSynthesis.paused) window.speechSynthesis.resume();
        else window.speechSynthesis.pause();
      }} else {{
        speakViaWebSpeech();
      }}
      return;
    }}
    if (audioEl.paused) {{
      audioEl.play().catch(() => startClientStreamFallback());
    }} else {{
      audioEl.pause();
    }}
  }};

  window.restartAudio = function() {{
    if (usingWebSpeech && "speechSynthesis" in window) {{
      speakViaWebSpeech();
      return;
    }}
    if (usingStreamFallback) {{
      streamIdx = 0;
      playNextStreamChunk();
      return;
    }}
    audioEl.currentTime = 0;
    audioEl.play().catch(() => startClientStreamFallback());
  }};

  window.cycleSpeed = function() {{
    speedIdx = (speedIdx + 1) % speeds.length;
    const sp = speeds[speedIdx];
    audioEl.playbackRate = sp;
    speedBtn.textContent = "⚡ السرعة: " + sp + "x";
  }};
}})();
</script>
</body>
</html>"""
  components.html(comp_html, height=106, scrolling=False)



# =====================================================================
# 17-ب. محرك البحث في الأخبار المرصودة وتجميعها وتصديرها إلى Word (.docx) و PDF (.pdf)
# =====================================================================
def get_stable_article_id(item: dict) -> str:
  if not isinstance(item, dict):
    return "id_unknown"
  if item.get("id"):
    return f"id_{item['id']}"
  raw_t = clean_display_text(item.get("title") or "")
  raw_u = clean_social_post_url(item.get("url") or "")
  t_hash = hashlib.md5(f"{normalize_arabic_for_dedup(raw_t)}|{raw_u}".encode("utf-8", errors="ignore")).hexdigest()[:12]
  return f"th_{t_hash}"


def _create_fallback_png_bytes(platform: str = "الصحف", source_name: str = "") -> bytes:
  """توليد صورة مصغرة PNG أنيقة للأخبار التي لا تتوفر على رابط صورة خارجي أو عند انقطاع الاتصال لضمان اكتمال جدول Word و PDF."""
  palette = {
      "الصحف": ((6, 78, 59), (16, 185, 129), "MOROCCO PRESS"),
      "فيسبوك": ((30, 58, 138), (59, 130, 246), "FACEBOOK POST"),
      "إكس": ((15, 23, 42), (148, 163, 184), "X / TWITTER"),
      "يوتيوب": ((127, 29, 29), (239, 68, 68), "YOUTUBE VIDEO"),
      "أخرى": ((76, 29, 149), (168, 85, 247), "SOCIAL MEDIA"),
  }
  bg_rgb, accent_rgb, en_tag = palette.get(platform, ((15, 23, 42), (56, 189, 248), "JUSTICE HUB"))
  try:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (320, 200), color=bg_rgb)
    draw = ImageDraw.Draw(img)
    draw.rectangle([8, 8, 311, 191], outline=accent_rgb, width=3)
    draw.rectangle([18, 18, 301, 54], fill=accent_rgb)
    draw.text((85, 28), en_tag, fill=(255, 255, 255))
    draw.text((65, 95), "AL-MARSAD AL-QADAI", fill=(241, 245, 249))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
  except Exception:
    import zlib
    width, height = 160, 100
    raw_rows = b""
    r_b, g_b, b_b = bg_rgb
    row_bytes = b"\x00" + bytes([r_b, g_b, b_b]) * width
    raw_data = row_bytes * height
    def _png_chunk(c_type: bytes, c_data: bytes) -> bytes:
      return struct.pack(">I", len(c_data)) + c_type + c_data + struct.pack(">I", zlib.crc32(c_type + c_data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(raw_data)) + _png_chunk(b"IEND", b"")


def _fetch_single_export_image(item: dict) -> tuple:
  """جلب وتحويل صورة الخبر إلى PNG/JPEG متناسقة الأبعاد لدمجها داخل جدول PDF."""
  art_id = get_stable_article_id(item)
  plat = clean_display_text(item.get("platform") or "الصحف")
  raw_u = clean_social_post_url(item.get("url") or "")
  src = format_precise_source_with_domain(
      item.get("source_name") or plat, raw_u, plat, title_hint=item.get("title", "")
  )
  img_u = clean_and_validate_image_url((item.get("image_url") or "").strip(), raw_u, plat)
  if not img_u:
    img_u = extract_thumbnail_for_item(raw_u, "", plat)

  # إذا لم تكن الصورة متوفرة في السجل، نحاول سحبها سريعاً من صفحة الخبر
  if not img_u and raw_u.startswith("http"):
    try:
      scraped_img, _, resolved_u = scrape_article_page_content_and_image(
          raw_u, title_hint=item.get("title", ""), source_hint=src
      )
      if scraped_img:
        img_u = clean_and_validate_image_url(scraped_img, resolved_u or raw_u, plat)
    except Exception:
      pass

  if img_u and img_u.startswith("http"):
    try:
      r = requests.get(img_u, headers=DEFAULT_HEADERS, timeout=4.0)
      if r.status_code == 200 and len(r.content) > 200:
        try:
          from PIL import Image
          im = Image.open(io.BytesIO(r.content)).convert("RGB")
          im.thumbnail((320, 220))
          out_b = io.BytesIO()
          im.save(out_b, format="PNG")
          return art_id, out_b.getvalue()
        except Exception:
          return art_id, r.content
    except Exception:
      pass

  return art_id, _create_fallback_png_bytes(plat, src)


def prepare_export_images_map(selected_items: list) -> dict:
  """جلب صور الأخبار المحددة بالتوازي لضمان سرعة التصدير إلى PDF."""
  if not selected_items:
    return {}
  img_map = {}
  with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(selected_items))) as pool:
    for aid, img_bytes in pool.map(_fetch_single_export_image, selected_items):
      img_map[aid] = img_bytes
  return img_map


def _build_pure_python_openxml_docx(selected_items: list, search_kw: str = "") -> bytes:
  """مولد ملفات Word (.docx) احتياطي نقي (Pure-Python OpenXML ZIP) بـ 3 أعمدة واتجاه RTL صارم من اليمين إلى اليسار (العنوان | الملخص | المصدر (رابط الخبر))."""
  import zipfile
  buf = io.BytesIO()
  now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

  rels_xml = [
      '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
  ]
  rows_xml = []

  # ترويسة الجدول من اليمين إلى اليسار (3 أعمدة فقط بدون عمود الصورة): العنوان | الملخص | المصدر (رابط الخبر)
  rows_xml.append("""
    <w:tr>
      <w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>
      <w:tc><w:tcPr><w:tcW w:w="3000" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="0F172A"/></w:tcPr><w:p><w:pPr><w:bidi w:val="1"/><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Cairo" w:hAnsi="Cairo" w:cs="Cairo"/><w:b/><w:bCs/><w:color w:val="FFFFFF"/><w:sz w:val="22"/><w:szCs w:val="22"/><w:rtl w:val="1"/></w:rPr><w:t>العنوان</w:t></w:r></w:p></w:tc>
      <w:tc><w:tcPr><w:tcW w:w="4800" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="0F172A"/></w:tcPr><w:p><w:pPr><w:bidi w:val="1"/><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Cairo" w:hAnsi="Cairo" w:cs="Cairo"/><w:b/><w:bCs/><w:color w:val="FFFFFF"/><w:sz w:val="22"/><w:szCs w:val="22"/><w:rtl w:val="1"/></w:rPr><w:t>الملخص</w:t></w:r></w:p></w:tc>
      <w:tc><w:tcPr><w:tcW w:w="3000" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="0F172A"/></w:tcPr><w:p><w:pPr><w:bidi w:val="1"/><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Cairo" w:hAnsi="Cairo" w:cs="Cairo"/><w:b/><w:bCs/><w:color w:val="FFFFFF"/><w:sz w:val="22"/><w:szCs w:val="22"/><w:rtl w:val="1"/></w:rPr><w:t>المصدر (رابط الخبر)</w:t></w:r></w:p></w:tc>
    </w:tr>
  """)

  for idx, it in enumerate(selected_items):
    raw_t = clean_display_text(it.get("title") or "")
    plat_t = clean_display_text(it.get("platform") or "الصحف")
    clean_u = resolve_google_news_url(
        clean_social_post_url(it.get("url") or ""),
        title_hint=raw_t,
        source_hint=it.get("source_name") or plat_t,
    )
    precise_src = format_precise_source_with_domain(
        it.get("source_name") or plat_t, clean_u, plat_t, title_hint=raw_t
    )
    title_t = html.escape(f"[{idx + 1}] {raw_t}")
    sum_t = html.escape(clean_display_text(it.get("summary") or ""))
    src_line = html.escape(f"{precise_src} | المنصة: {plat_t} | التاريخ: {clean_display_text(it.get('pub_date') or '')}")
    url_line = html.escape(clean_u)
    rows_xml.append(f"""
      <w:tr>
        <w:trPr><w:cantSplit/></w:trPr>
        <w:tc><w:tcPr><w:tcW w:w="3000" w:type="dxa"/></w:tcPr><w:p><w:pPr><w:bidi w:val="1"/><w:jc w:val="right"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Cairo" w:hAnsi="Cairo" w:cs="Cairo"/><w:b/><w:bCs/><w:sz w:val="21"/><w:szCs w:val="21"/><w:rtl w:val="1"/></w:rPr><w:t>‏{title_t}</w:t></w:r></w:p></w:tc>
        <w:tc><w:tcPr><w:tcW w:w="4800" w:type="dxa"/></w:tcPr><w:p><w:pPr><w:bidi w:val="1"/><w:jc w:val="right"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Cairo" w:hAnsi="Cairo" w:cs="Cairo"/><w:sz w:val="20"/><w:szCs w:val="20"/><w:rtl w:val="1"/></w:rPr><w:t>‏{sum_t}</w:t></w:r></w:p></w:tc>
        <w:tc><w:tcPr><w:tcW w:w="3000" w:type="dxa"/></w:tcPr>
          <w:p><w:pPr><w:bidi w:val="1"/><w:jc w:val="right"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Cairo" w:hAnsi="Cairo" w:cs="Cairo"/><w:b/><w:bCs/><w:sz w:val="20"/><w:szCs w:val="20"/><w:rtl w:val="1"/></w:rPr><w:t>‏{src_line}</w:t></w:r></w:p>
          <w:p><w:pPr><w:bidi w:val="1"/><w:jc w:val="right"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Cairo"/><w:color w:val="2563EB"/><w:u w:val="single"/><w:sz w:val="19"/><w:szCs w:val="19"/></w:rPr><w:t>{url_line}</w:t></w:r></w:p>
        </w:tc>
      </w:tr>
    """)

  rels_xml.append("</Relationships>")
  doc_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:bidi w:val="1"/><w:jc w:val="right"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Cairo" w:hAnsi="Cairo" w:cs="Cairo"/><w:b/><w:bCs/><w:sz w:val="32"/><w:szCs w:val="32"/><w:rtl w:val="1"/></w:rPr><w:t>‏⚖️ المرصد القضائي — تقرير الأخبار القضائية المحددة ({len(selected_items)} خبر)</w:t></w:r></w:p>
    <w:p><w:pPr><w:bidi w:val="1"/><w:jc w:val="right"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Cairo" w:hAnsi="Cairo" w:cs="Cairo"/><w:b/><w:bCs/><w:color w:val="0369A1"/><w:sz w:val="21"/><w:szCs w:val="21"/><w:rtl w:val="1"/></w:rPr><w:t>‏المنصة: المرصد القضائي | تاريخ التصدير: {now_str} | الكلمة المفتاحية: {html.escape(search_kw or 'جميع الأخبار المرصودة')}</w:t></w:r></w:p>
    <w:tbl>
      <w:tblPr>
        <w:bidi/>
        <w:bidiVisual/>
        <w:jc w:val="right"/>
        <w:tblW w:w="5000" w:type="pct"/>
        <w:tblBorders>
          <w:top w:val="single" w:sz="8" w:space="0" w:color="0F172A"/>
          <w:bottom w:val="single" w:sz="8" w:space="0" w:color="0F172A"/>
          <w:left w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>
          <w:right w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>
          <w:insideH w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>
          <w:insideV w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>
        </w:tblBorders>
      </w:tblPr>
      {''.join(rows_xml)}
    </w:tbl>
    <w:sectPr>
      <w:pgSz w:w="16834" w:h="11909" w:orient="landscape"/>
      <w:pgMar w:top="936" w:right="936" w:bottom="936" w:left="936"/>
      <w:bidi/>
    </w:sectPr>
  </w:body>
</w:document>"""

  with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    zf.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    zf.writestr("word/_rels/document.xml.rels", "".join(rels_xml))
    zf.writestr("word/document.xml", doc_xml)
  return buf.getvalue()


def generate_selected_articles_docx(selected_items: list, search_kw: str = "", img_map: dict = None) -> bytes:
  """توليد ملف وورد (.docx) احترافي باتجاه عربي صارم من اليمين إلى اليسار (RTL) للعناوين والجدول، مكون من 3 أعمدة:
  العمود الأول (يمين): العنوان | العمود الثاني (وسط): الملخص | العمود الثالث (يسار): المصدر (رابط الخبر) — بدون عمود الصورة المصغرة."""
  if not selected_items:
    return b""

  try:
    import docx
    from docx.enum.section import WD_ORIENT
    from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.opc.constants import RELATIONSHIP_TYPE
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import nsdecls, qn
    from docx.shared import Inches, Pt, RGBColor

    doc = docx.Document()

    def _set_p_rtl(p_obj, align=WD_ALIGN_PARAGRAPH.RIGHT):
      p_obj.alignment = align
      pPr = p_obj._p.get_or_add_pPr()
      for old_bidi in pPr.findall(qn("w:bidi")):
        pPr.remove(old_bidi)
      bidi_el = OxmlElement("w:bidi")
      bidi_el.set(qn("w:val"), "1")
      pPr.append(bidi_el)
      jc_val = "center" if align == WD_ALIGN_PARAGRAPH.CENTER else ("left" if align == WD_ALIGN_PARAGRAPH.LEFT else "right")
      for old_jc in pPr.findall(qn("w:jc")):
        pPr.remove(old_jc)
      jc_el = OxmlElement("w:jc")
      jc_el.set(qn("w:val"), jc_val)
      pPr.append(jc_el)

    def _style_run_rtl(run_obj, font_name: str = "Cairo", size_pt: float = 10.5, bold: bool = False, color_rgb=None, is_rtl: bool = True):
      run_obj.font.name = font_name
      run_obj.font.size = Pt(size_pt)
      run_obj.font.bold = bold
      if color_rgb is not None:
        run_obj.font.color.rgb = color_rgb
      rPr = run_obj._r.get_or_add_rPr()
      rFonts = rPr.find(qn("w:rFonts"))
      if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
      rFonts.set(qn("w:ascii"), font_name)
      rFonts.set(qn("w:hAnsi"), font_name)
      rFonts.set(qn("w:cs"), "Cairo")
      sz_half = str(int(size_pt * 2))
      for tag_sz in ("w:sz", "w:szCs"):
        el_sz = rPr.find(qn(tag_sz))
        if el_sz is None:
          el_sz = OxmlElement(tag_sz)
          rPr.append(el_sz)
        el_sz.set(qn("w:val"), sz_half)
      if bold:
        for tag_b in ("w:b", "w:bCs"):
          if rPr.find(qn(tag_b)) is None:
            rPr.append(OxmlElement(tag_b))
      for old_rtl in rPr.findall(qn("w:rtl")):
        rPr.remove(old_rtl)
      if is_rtl:
        rtl_el = OxmlElement("w:rtl")
        rtl_el.set(qn("w:val"), "1")
        rPr.append(rtl_el)
        lang_el = OxmlElement("w:lang")
        lang_el.set(qn("w:bidi"), "ar-MA")
        rPr.append(lang_el)

    def _add_docx_hyperlink(paragraph, url: str, link_text: str):
      """إضافة رابط تشعبي قابل للنقر داخل خلية المصدر (رابط الخبر) في ملف Word."""
      try:
        part = paragraph.part
        r_id = part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("r:id"), r_id)
        new_run = OxmlElement("w:r")
        rPr = OxmlElement("w:rPr")
        rFonts = OxmlElement("w:rFonts")
        rFonts.set(qn("w:ascii"), "Cairo")
        rFonts.set(qn("w:hAnsi"), "Cairo")
        rFonts.set(qn("w:cs"), "Cairo")
        rPr.append(rFonts)
        c_el = OxmlElement("w:color")
        c_el.set(qn("w:val"), "2563EB")
        rPr.append(c_el)
        u_el = OxmlElement("w:u")
        u_el.set(qn("w:val"), "single")
        rPr.append(u_el)
        b_el = OxmlElement("w:b")
        rPr.append(b_el)
        bcs_el = OxmlElement("w:bCs")
        rPr.append(bcs_el)
        for t_sz in ("w:sz", "w:szCs"):
          s_el = OxmlElement(t_sz)
          s_el.set(qn("w:val"), "20")
          rPr.append(s_el)
        rtl_el = OxmlElement("w:rtl")
        rtl_el.set(qn("w:val"), "1")
        rPr.append(rtl_el)
        new_run.append(rPr)
        t_el = OxmlElement("w:t")
        t_el.text = f"‏{link_text}"
        new_run.append(t_el)
        hyperlink.append(new_run)
        paragraph._p.append(hyperlink)
      except Exception:
        r_fb = paragraph.add_run(f"‏{link_text}")
        _style_run_rtl(r_fb, "Cairo", 10, bold=True, color_rgb=RGBColor(37, 99, 235), is_rtl=True)

    # إعداد الصفحة بالوضع الأفقي (Landscape) وتفعيل اتجاه القسم من اليمين إلى اليسار (<w:bidi/>)
    for section in doc.sections:
      section.orientation = WD_ORIENT.LANDSCAPE
      section.page_width = Inches(11.69)
      section.page_height = Inches(8.27)
      section.top_margin = Inches(0.65)
      section.bottom_margin = Inches(0.65)
      section.left_margin = Inches(0.65)
      section.right_margin = Inches(0.65)
      sectPr = section._sectPr
      if sectPr.find(qn("w:bidi")) is None:
        sectPr.append(OxmlElement("w:bidi"))
      try:
        ftr_p = section.footer.paragraphs[0]
        _set_p_rtl(ftr_p, WD_ALIGN_PARAGRAPH.CENTER)
        ftr_run = ftr_p.add_run("‏⚖️ المرصد القضائي — تقرير الأخبار القضائية المرصودة")
        _style_run_rtl(ftr_run, "Cairo", 9.5, bold=False, color_rgb=RGBColor(100, 116, 139), is_rtl=True)
      except Exception:
        pass

    style_normal = doc.styles["Normal"]
    style_normal.font.name = "Cairo"
    style_normal.font.size = Pt(11)
    style_normal.font.color.rgb = RGBColor(15, 23, 42)
    norm_pPr = style_normal._element.get_or_add_pPr()
    if norm_pPr.find(qn("w:bidi")) is None:
      b_norm = OxmlElement("w:bidi")
      b_norm.set(qn("w:val"), "1")
      norm_pPr.append(b_norm)

    # عنوان التقرير الرئيسي من اليمين إلى اليسار
    title_p = doc.add_paragraph()
    _set_p_rtl(title_p, WD_ALIGN_PARAGRAPH.RIGHT)
    t_run = title_p.add_run("‏⚖️ المرصد القضائي — تقرير تجميعي للأخبار القضائية المحددة")
    _style_run_rtl(t_run, "Cairo", 18, bold=True, color_rgb=RGBColor(15, 23, 42), is_rtl=True)
    title_p.paragraph_format.space_after = Pt(4)
    title_p.paragraph_format.keep_with_next = True

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    kw_label = search_kw.strip() if (search_kw and search_kw.strip()) else "جميع الأخبار المرصودة"
    meta_p = doc.add_paragraph()
    _set_p_rtl(meta_p, WD_ALIGN_PARAGRAPH.RIGHT)
    m_run = meta_p.add_run(
        f"‏المنصة: المرصد القضائي   |   تاريخ التصدير: ‎{now_str}‏   |   عدد الأخبار المجمعة: {len(selected_items)} خبر   |   الكلمة المفتاحية للبحث: {kw_label}"
    )
    _style_run_rtl(m_run, "Cairo", 11, bold=True, color_rgb=RGBColor(3, 105, 161), is_rtl=True)
    meta_p.paragraph_format.space_after = Pt(12)
    meta_p.paragraph_format.keep_with_next = True

    # إنشاء الجدول المنظم بـ 3 أعمدة مرتبة من اليمين إلى اليسار (بدون عمود الصورة المصغرة):
    # العمود الأول (0 - يمين): العنوان | العمود الثاني (1 - وسط): الملخص | العمود الثالث (2 - يسار): المصدر (رابط الخبر)
    headers = ["العنوان", "الملخص", "المصدر (رابط الخبر)"]
    col_widths = [Inches(2.90), Inches(4.65), Inches(2.84)]

    table = doc.add_table(rows=1, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.RIGHT
    table.autofit = False
    tblPr = table._tbl.tblPr
    for old_b in tblPr.findall(qn("w:bidi")) + tblPr.findall(qn("w:bidiVisual")):
      tblPr.remove(old_b)
    tblPr.append(parse_xml(r'<w:bidi {} w:val="1"/>'.format(nsdecls("w"))))
    tblPr.append(parse_xml(r'<w:bidiVisual {}/>'.format(nsdecls("w"))))
    tblPr.append(
        parse_xml(
            r'<w:tblBorders {}>'
            r'<w:top w:val="single" w:sz="8" w:space="0" w:color="0F172A"/>'
            r'<w:bottom w:val="single" w:sz="8" w:space="0" w:color="0F172A"/>'
            r'<w:left w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            r'<w:right w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            r'<w:insideH w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            r'<w:insideV w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
            r"</w:tblBorders>".format(nsdecls("w"))
        )
    )

    hdr_row = table.rows[0]
    hdr_trPr = hdr_row._tr.get_or_add_trPr()
    hdr_trPr.append(parse_xml(r"<w:tblHeader {}/>".format(nsdecls("w"))))
    hdr_trPr.append(parse_xml(r"<w:cantSplit {}/>".format(nsdecls("w"))))

    for idx, h_text in enumerate(headers):
      cell = hdr_row.cells[idx]
      cell.width = col_widths[idx]
      cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
      tcPr = cell._tc.get_or_add_tcPr()
      tcPr.append(parse_xml(r'<w:shd {} w:fill="0F172A"/>'.format(nsdecls("w"))))
      p_cell = cell.paragraphs[0]
      _set_p_rtl(p_cell, WD_ALIGN_PARAGRAPH.CENTER)
      p_cell.paragraph_format.space_before = Pt(6)
      p_cell.paragraph_format.space_after = Pt(6)
      p_cell.paragraph_format.keep_with_next = True
      r_h = p_cell.add_run(f"‏{h_text}")
      _style_run_rtl(r_h, "Cairo", 11.5, bold=True, color_rgb=RGBColor(255, 255, 255), is_rtl=True)

    for row_idx, item in enumerate(selected_items):
      row = table.add_row()
      trPr = row._tr.get_or_add_trPr()
      trPr.append(parse_xml(r"<w:cantSplit {}/>".format(nsdecls("w"))))

      bg_hex = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
      for c_i, cell in enumerate(row.cells):
        cell.width = col_widths[c_i]
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        cell._tc.get_or_add_tcPr().append(
            parse_xml(r'<w:shd {} w:fill="{}"/>'.format(nsdecls("w"), bg_hex))
        )

      raw_t = clean_display_text(item.get("title") or "")
      plat = clean_display_text(item.get("platform") or "الصحف")
      raw_u_orig = clean_social_post_url(item.get("url") or "")
      clean_u = resolve_google_news_url(
          raw_u_orig, title_hint=raw_t, source_hint=item.get("source_name") or plat
      )
      precise_src = format_precise_source_with_domain(
          item.get("source_name") or plat, clean_u, plat, title_hint=raw_t
      )
      raw_sum = clean_display_text(item.get("summary") or "")
      raw_snip = clean_display_text(item.get("raw_snippet") or "")
      if is_summary_just_title(raw_t, raw_sum):
        raw_sum = build_extractive_arabic_summary(raw_t, raw_snip, plat, precise_src)
      pub_dt = clean_display_text(item.get("pub_date") or "")

      # العمود الأول (0 - يمين الجدول): العنوان
      c_title = row.cells[0]
      p_t = c_title.paragraphs[0]
      _set_p_rtl(p_t, WD_ALIGN_PARAGRAPH.RIGHT)
      p_t.paragraph_format.space_before = Pt(5)
      p_t.paragraph_format.space_after = Pt(5)
      r_num = p_t.add_run(f"‏({row_idx + 1}) ")
      _style_run_rtl(r_num, "Cairo", 10.5, bold=True, color_rgb=RGBColor(2, 132, 199), is_rtl=True)
      r_t = p_t.add_run(f"‏{raw_t}")
      _style_run_rtl(r_t, "Cairo", 10.5, bold=True, color_rgb=RGBColor(15, 23, 42), is_rtl=True)

      # العمود الثاني (1 - وسط الجدول): الملخص
      c_sum = row.cells[1]
      p_s = c_sum.paragraphs[0]
      _set_p_rtl(p_s, WD_ALIGN_PARAGRAPH.RIGHT)
      p_s.paragraph_format.space_before = Pt(5)
      p_s.paragraph_format.space_after = Pt(5)
      r_s = p_s.add_run(f"‏{raw_sum}")
      _style_run_rtl(r_s, "Cairo", 10.5, bold=False, color_rgb=RGBColor(51, 65, 85), is_rtl=True)

      # العمود الثالث (2 - يسار الجدول): المصدر (رابط الخبر)
      c_src = row.cells[2]
      p_src = c_src.paragraphs[0]
      _set_p_rtl(p_src, WD_ALIGN_PARAGRAPH.RIGHT)
      p_src.paragraph_format.space_before = Pt(5)
      p_src.paragraph_format.space_after = Pt(2)
      r_src_name = p_src.add_run(f"‏{precise_src}\n")
      _style_run_rtl(r_src_name, "Cairo", 10.5, bold=True, color_rgb=RGBColor(15, 23, 42), is_rtl=True)

      meta_src_line = f"‏المنصة: {plat}" + (f" | التاريخ: ‎{pub_dt}‏" if pub_dt else "")
      r_plat = p_src.add_run(meta_src_line)
      _style_run_rtl(r_plat, "Cairo", 9.5, bold=False, color_rgb=RGBColor(71, 85, 105), is_rtl=True)

      if clean_u:
        p_link = c_src.add_paragraph()
        _set_p_rtl(p_link, WD_ALIGN_PARAGRAPH.RIGHT)
        p_link.paragraph_format.space_before = Pt(2)
        p_link.paragraph_format.space_after = Pt(2)
        _add_docx_hyperlink(p_link, clean_u, "🔗 فتح رابط الخبر الأصلي")

        p_raw_u = c_src.add_paragraph()
        _set_p_rtl(p_raw_u, WD_ALIGN_PARAGRAPH.LEFT)
        p_raw_u.paragraph_format.space_before = Pt(1)
        p_raw_u.paragraph_format.space_after = Pt(4)
        r_u = p_raw_u.add_run(clean_u)
        _style_run_rtl(r_u, "Calibri", 8.5, bold=False, color_rgb=RGBColor(37, 99, 235), is_rtl=False)

    out_stream = io.BytesIO()
    doc.save(out_stream)
    return out_stream.getvalue()
  except Exception:
    return _build_pure_python_openxml_docx(selected_items, search_kw=search_kw)


def build_selected_articles_export_html(selected_items: list, search_kw: str = "", img_map: dict = None) -> str:
  """بناء وثيقة HTML5 RTL متكاملة ومستقلة لتوليد ملف PDF رسمي عالي الدقة مع الإبقاء على عمود الصورة المصغرة في ملف PDF (العنوان | الملخص | المصدر (رابط الخبر) | الصورة)."""
  if img_map is None:
    img_map = prepare_export_images_map(selected_items)
  now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
  kw_label = html.escape(search_kw.strip() if (search_kw and search_kw.strip()) else "جميع الأخبار المرصودة")

  rows_html = []
  for idx, item in enumerate(selected_items):
    raw_t = clean_display_text(item.get("title") or "")
    plat = clean_display_text(item.get("platform") or "الصحف")
    raw_u_orig = clean_social_post_url(item.get("url") or "")
    clean_u = resolve_google_news_url(
        raw_u_orig, title_hint=raw_t, source_hint=item.get("source_name") or plat
    )
    precise_src = format_precise_source_with_domain(
        item.get("source_name") or plat, clean_u, plat, title_hint=raw_t
    )
    raw_sum = clean_display_text(item.get("summary") or "")
    raw_snip = clean_display_text(item.get("raw_snippet") or "")
    if is_summary_just_title(raw_t, raw_sum):
      raw_sum = build_extractive_arabic_summary(raw_t, raw_snip, plat, precise_src)
    pub_dt = clean_display_text(item.get("pub_date") or "")

    aid = get_stable_article_id(item)
    img_bytes = img_map.get(aid) or _create_fallback_png_bytes(plat, precise_src)
    b64_img = base64.b64encode(img_bytes).decode("ascii")
    img_data_uri = f"data:image/png;base64,{b64_img}"

    rows_html.append(f"""
      <tr>
        <td class="col-title">
          <div class="title-txt"><span class="row-num">[{idx + 1}]</span> {html.escape(raw_t)}</div>
        </td>
        <td class="col-summary">
          <div class="summary-txt">{html.escape(raw_sum)}</div>
        </td>
        <td class="col-source">
          <div class="src-name">{html.escape(precise_src)}</div>
          <div class="src-meta">المنصة: {html.escape(plat)}</div>
          <div class="src-meta">النشر: <span dir="ltr">{html.escape(pub_dt)}</span></div>
          {f'<div class="src-link"><a href="{html.escape(clean_u, quote=True)}">🔗 رابط الخبر الأصلي</a><div class="src-url-text" dir="ltr">{html.escape(clean_u[:65] + ("..." if len(clean_u) > 65 else ""))}</div></div>' if clean_u else ''}
        </td>
        <td class="col-image">
          <img src="{img_data_uri}" alt="thumb" />
        </td>
      </tr>
    """)

  return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <title>المرصد القضائي — تقرير الأخبار القضائية المحددة</title>
  <style>
    @page {{
      size: A4 landscape;
      margin: 14mm 12mm;
      background: #ffffff;
      @bottom-right {{
        content: "المرصد القضائي — صفحة " counter(page) " من " counter(pages);
        font-family: "Noto Sans Arabic", "Cairo", Arial, sans-serif;
        font-size: 8.5pt;
        color: #475569;
      }}
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      padding: 0;
      font-family: "Noto Sans Arabic", "Cairo", "Amiri", Arial, sans-serif;
      font-size: 10pt;
      line-height: 1.55;
      color: #0f172a;
      direction: rtl;
      text-align: right;
      background: #ffffff;
    }}
    .report-header {{
      border-bottom: 2.5px solid #0f172a;
      padding-bottom: 10px;
      margin-bottom: 14px;
      direction: rtl;
      text-align: right;
    }}
    .report-header h1 {{
      font-size: 16pt;
      font-weight: 800;
      color: #0f172a;
      margin: 0 0 6px 0;
    }}
    .report-meta {{
      font-size: 9.5pt;
      font-weight: 700;
      color: #0369a1;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      direction: rtl;
    }}
    th, td {{
      border: 1px solid #cbd5e1;
      padding: 8px 10px;
      vertical-align: middle;
      text-align: right;
      word-wrap: break-word;
      overflow-wrap: break-word;
    }}
    thead th {{
      background-color: #0f172a;
      color: #ffffff;
      font-size: 10.5pt;
      font-weight: 800;
      text-align: center;
      border-color: #0f172a;
    }}
    tbody tr:nth-child(even) td {{
      background-color: #f8fafc;
    }}
    tr {{
      break-inside: avoid;
      page-break-inside: avoid;
    }}
    .col-title {{ width: 24%; }}
    .col-summary {{ width: 41%; }}
    .col-source {{ width: 20%; }}
    .col-image {{ width: 15%; text-align: center; }}
    .title-txt {{
      font-size: 10pt;
      font-weight: 700;
      color: #0f172a;
      line-height: 1.5;
    }}
    .row-num {{
      color: #0284c7;
      font-weight: 800;
    }}
    .summary-txt {{
      font-size: 9.5pt;
      color: #334155;
      line-height: 1.6;
    }}
    .src-name {{
      font-size: 9.5pt;
      font-weight: 700;
      color: #0f172a;
      margin-bottom: 3px;
    }}
    .src-meta {{
      font-size: 8.5pt;
      color: #475569;
      margin-bottom: 2px;
    }}
    .src-link a {{
      font-size: 8.5pt;
      font-weight: 700;
      color: #2563eb;
      text-decoration: underline;
    }}
    .src-url-text {{
      font-size: 7.5pt;
      color: #64748b;
      margin-top: 2px;
      word-break: break-all;
    }}
    .col-image img {{
      width: 125px;
      height: 82px;
      object-fit: cover;
      display: block;
      margin: 0 auto;
    }}
  </style>
</head>
<body>
  <div class="report-header">
    <h1>⚖️ المرصد القضائي — جدول الأخبار القضائية المحددة</h1>
    <div class="report-meta">
      المنصة: المرصد القضائي &nbsp;|&nbsp;
      تاريخ التصدير: <span dir="ltr">{html.escape(now_str)}</span> &nbsp;|&nbsp;
      عدد الأخبار المجمعة: {len(selected_items)} خبر &nbsp;|&nbsp;
      الكلمة المفتاحية للبحث: {kw_label}
    </div>
  </div>
  <table>
    <thead>
      <tr>
        <th class="col-title">العنوان</th>
        <th class="col-summary">الملخص</th>
        <th class="col-source">المصدر (رابط الخبر)</th>
        <th class="col-image">الصورة</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
</body>
</html>"""


def generate_selected_articles_pdf(selected_items: list, search_kw: str = "", img_map: dict = None) -> bytes:
  """توليد ملف PDF (.pdf) منظم يضم الأخبار المحددة في جدول بـ 4 أعمدة (العنوان | الملخص | المصدر (رابط الخبر) | الصورة) مع دعم WeasyPrint وبدائل بايثون."""
  if not selected_items:
    return b""
  if img_map is None:
    img_map = prepare_export_images_map(selected_items)
  html_doc = build_selected_articles_export_html(selected_items, search_kw=search_kw, img_map=img_map)

  try:
    import weasyprint
    pdf_bytes = weasyprint.HTML(string=html_doc).write_pdf()
    if pdf_bytes and len(pdf_bytes) > 500:
      return pdf_bytes
  except Exception:
    pass

  # احتياطي عبر ReportLab في حال عدم توفر WeasyPrint على السيرفر الخارجي
  try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet

    buf_pdf = io.BytesIO()
    doc_pdf = SimpleDocTemplate(buf_pdf, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    normal_st = styles["Normal"]
    table_rows = [["العنوان", "الملخص", "المصدر (رابط الخبر)", "الصورة"]]
    for item in selected_items:
      aid = get_stable_article_id(item)
      plat = clean_display_text(item.get("platform") or "الصحف")
      clean_u = clean_social_post_url(item.get("url") or "")
      precise_src = format_precise_source_with_domain(
          item.get("source_name") or plat, clean_u, plat, title_hint=item.get("title", "")
      )
      img_b = img_map.get(aid) or _create_fallback_png_bytes(plat, precise_src)
      rl_img = RLImage(io.BytesIO(img_b), width=95, height=60)
      table_rows.append([
          Paragraph(html.escape(clean_display_text(item.get("title") or "")), normal_st),
          Paragraph(html.escape(clean_display_text(item.get("summary") or "")), normal_st),
          Paragraph(html.escape(f"{precise_src} ({plat}) - {clean_u}"), normal_st),
          rl_img,
      ])
    t_obj = Table(table_rows, colWidths=[185, 300, 155, 115], repeatRows=1)
    t_obj.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    doc_pdf.build([t_obj])
    return buf_pdf.getvalue()
  except Exception:
    return b""


def get_or_build_export_files(selected_items: list, search_kw: str = "") -> tuple:
  """تجهيز وتخزين ملفات Word (.docx بـ 3 أعمدة بدون صورة) و PDF (.pdf بـ 4 أعمدة مع الصورة) في الذاكرة المؤقتة للجلسة."""
  if not selected_items:
    return b"", b"", ""
  sig_ids = tuple(get_stable_article_id(x) for x in selected_items)
  cache_key = (sig_ids, str(search_kw or "").strip(), "v2_rtl_3col_word_4col_pdf")
  if st is not None:
    cached = st.session_state.get("cached_export_bundle")
    if isinstance(cached, dict) and cached.get("key") == cache_key:
      return cached["docx"], cached["pdf"], cached["html"]

  img_map = prepare_export_images_map(selected_items)
  docx_b = generate_selected_articles_docx(selected_items, search_kw=search_kw, img_map=img_map)
  pdf_b = generate_selected_articles_pdf(selected_items, search_kw=search_kw, img_map=img_map)
  html_s = build_selected_articles_export_html(selected_items, search_kw=search_kw, img_map=img_map)

  if st is not None:
    st.session_state["cached_export_bundle"] = {
        "key": cache_key,
        "docx": docx_b,
        "pdf": pdf_b,
        "html": html_s,
    }
  return docx_b, pdf_b, html_s


def _render_client_side_pdf_printer(export_html_str: str, count_items: int):
  """زر تصدير وطباعة PDF فوري من المتصفح (يعمل بتقنية نافذة الطباعة المباشرة لضمان دعم العربية 100% على كافة المتصفحات)."""
  try:
    import streamlit.components.v1 as components
  except Exception:
    return
  b64_html = base64.b64encode(export_html_str.encode("utf-8")).decode("ascii")
  comp_code = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@700;800&display=swap');
  body {{ margin:0; padding:0; background:transparent; font-family:'Cairo',sans-serif; direction:rtl; }}
  .print-btn {{
    width:100%; height:42px; border-radius:12px; cursor:pointer;
    background:linear-gradient(135deg, rgba(220,38,38,0.82) 0%, rgba(153,27,27,0.92) 100%);
    border:1.5px solid rgba(252,165,165,0.8); color:#ffffff;
    font-family:'Cairo',sans-serif; font-size:0.9rem; font-weight:800;
    display:flex; align-items:center; justify-content:center; gap:8px;
    box-shadow:0 4px 14px rgba(220,38,38,0.3); transition:all 0.2s ease;
  }}
  .print-btn:hover {{
    border-color:#ffffff; transform:translateY(-1px);
    box-shadow:0 6px 18px rgba(220,38,38,0.5);
  }}
</style>
</head>
<body>
  <button class="print-btn" onclick="openPdfPrintWindow()">
    🖨️ معاينة وحفظ جدول PDF فوري ({count_items} خبر)
  </button>
  <script>
  function openPdfPrintWindow() {{
    const bin = atob("{b64_html}");
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const dec = new TextDecoder("utf-8").decode(bytes);
    const w = window.open("", "_blank");
    if (w) {{
      w.document.open();
      w.document.write(dec);
      w.document.close();
      setTimeout(() => {{ w.focus(); w.print(); }}, 550);
    }}
  }}
  </script>
</body>
</html>"""
  components.html(comp_code, height=48, scrolling=False)


def render_article_cards(
    items_list: list,
    empty_msg: str = "لا توجد منشورات مرصودة حالياً في هذا القسم.",
    tab_prefix: str = "tab",
):
  if not items_list:
    render_html(
        f"<div dir='rtl' style='direction:rtl;text-align:center;padding:30px;color:#64748b;background:rgba(15,23,42,0.5);border-radius:16px;border:1px dashed rgba(148,163,184,0.2);'>{html.escape(empty_msg)}</div>"
    )
    return

  plat_css_map = {
      "الصحف": "plat-press",
      "فيسبوك": "plat-fb",
      "إكس": "plat-x",
      "يوتيوب": "plat-yt",
      "أخرى": "plat-other",
  }

  plat_type_label = {
      "الصحف": "📰 مقال صحفي",
      "فيسبوك": "🟦 منشور فيسبوك",
      "إكس": "⬛ منشور إكس",
      "يوتيوب": "🟥 فيديو يوتيوب",
      "أخرى": "🟪 منشور رقمي",
  }

  api_key_curr = (cfg.get("gemini_api_key") or "").strip()
  page_limit_key = f"page_limit_{tab_prefix}"
  curr_page_limit = int(st.session_state.get(page_limit_key, 25))
  visible_items = items_list[:curr_page_limit]

  for idx, item in enumerate(visible_items):
    plat = clean_display_text(item.get("platform") or "الصحف")
    css_cls = plat_css_map.get(plat, "plat-press")
    type_badge_txt = plat_type_label.get(plat, plat)

    raw_title = clean_display_text(item.get("title") or "")
    raw_summary = clean_display_text(item.get("summary") or "")
    raw_full_text = clean_full_article_text(item.get("raw_snippet") or "")

    # معرف ثابت 100% لكل خبر لا يتغير أبداً عند تحديث الرابط أو بين التبويبات
    stable_art_id = get_stable_article_id(item)
    widget_uid = f"{tab_prefix}_{stable_art_id}_{idx}"

    raw_url = str(item.get("url") or "#").strip()
    clean_link_url = clean_social_post_url(raw_url)
    raw_img_candidate = clean_and_validate_image_url((item.get("image_url") or "").strip(), clean_link_url, plat)

    # تحديد اسم المصدر بدقة مع الدومين (اسم الموقع + الدومين) لجميع الأخبار الجديدة والقديمة
    raw_src = format_precise_source_with_domain(
        item.get("source_name") or plat,
        clean_link_url,
        plat,
        source_url_hint=item.get("source_domain_hint", ""),
        title_hint=raw_title,
    )
    item["source_name"] = raw_src

    raw_snip_flat = clean_display_text(raw_full_text)
    if is_summary_just_title(raw_title, raw_summary):
      raw_summary = build_extractive_arabic_summary(
          raw_title, raw_snip_flat, plat, raw_src
      )

    pub_ts = float(item.get("pub_timestamp") or (time.time() - 3600))
    raw_pub_date = clean_display_text(item.get("pub_date") or "")
    if not raw_pub_date:
      raw_pub_date = datetime.fromtimestamp(
          pub_ts, tz=timezone.utc
      ).strftime("%Y-%m-%d %H:%M")

    mon_ts = float(item.get("created_at") or pub_ts)
    mon_date_str = datetime.fromtimestamp(mon_ts, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M"
    )

    fallback_svg_uri = get_fallback_thumbnail_data_uri(plat, raw_src)
    raw_img = raw_img_candidate
    if not raw_img:
      raw_img = extract_thumbnail_for_item(clean_link_url, "", plat)
    final_img_src = html.escape(
        raw_img if raw_img else fallback_svg_uri, quote=True
    )
    fallback_svg_safe = html.escape(fallback_svg_uri, quote=True)

    title_safe = html.escape(raw_title)
    summary_safe = html.escape(raw_summary)
    source_safe = html.escape(raw_src)
    pub_date_safe = html.escape(raw_pub_date)
    mon_date_safe = html.escape(mon_date_str)
    rel_time = html.escape(format_relative_arabic(pub_ts))
    category_safe = html.escape(
        clean_display_text(item.get("category") or "شؤون قضائية")
    )
    url_safe = html.escape(clean_link_url, quote=True)
    target_tag = (
        '<span class="badge-target">🎯 رصد مخصص</span>'
        if int(item.get("is_custom_target", 0)) == 1
        else ""
    )

    verbatim_body = raw_full_text if len(raw_full_text) >= 40 else raw_title
    verbatim_paragraphs_html = _format_verbatim_article_paragraphs_html(
        verbatim_body, raw_title
    )

    card_html = (
        f'<div class="news-card {css_cls}" dir="rtl" style="direction:rtl !important;text-align:right !important;margin-bottom:6px;">'
        '<div class="news-card-layout" dir="rtl" style="display:flex;flex-direction:row;direction:rtl !important;text-align:right !important;">'
        '<div class="news-thumb-box">'
        f'<img class="news-thumb-img" src="{final_img_src}" alt="thumbnail" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src=\'{fallback_svg_safe}\';" />'
        "</div>"
        '<div class="news-body-col" dir="rtl" style="direction:rtl !important;text-align:right !important;">'
        '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;direction:rtl !important;text-align:right !important;">'
        f'<span class="badge-plat">{html.escape(type_badge_txt)}</span>'
        f"{target_tag}"
        f'<span style="font-weight:800;color:#38bdf8;background:rgba(15,23,42,0.75);border:1px solid rgba(56,189,248,0.35);padding:2px 10px;border-radius:999px;font-size:0.84rem;" dir="rtl">🌐 المصدر: {source_safe}</span>'
        f'<span style="color:#64748b;font-size:0.82rem;">• {category_safe}</span>'
        "</div>"
        f'<div class="news-title" dir="rtl" style="direction:rtl !important;text-align:right !important;"><a href="{url_safe}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:none;">{title_safe}</a></div>'
        '<div class="news-dates-row" dir="rtl" style="direction:rtl !important;text-align:right !important;">'
        f'<span class="date-chip" dir="rtl">📅 تاريخ النشر: <strong style="color:#38bdf8;" dir="ltr">{pub_date_safe}</strong> <span style="color:#34d399;">({rel_time})</span></span>'
        f'<span class="date-chip" dir="rtl">📡 تاريخ الرصد: <strong style="color:#f472b6;" dir="ltr">{mon_date_safe}</strong></span>'
        "</div>"
        f'<div class="news-summary-box" dir="rtl" style="direction:rtl !important;text-align:right !important;">'
        f'<strong style="color:#38bdf8;">📝 ملخص الخبر (AI): </strong>{summary_safe}'
        "</div>"
        '<details class="article-preview-drawer" dir="rtl">'
        f"<summary>{'📝 معاينة التفريغ النصي وتفاصيل الفيديو (دون مغادرة الموقع)' if (plat == 'يوتيوب' or 'youtube.com' in clean_link_url.lower() or 'youtu.be' in clean_link_url.lower()) else '👁️ معاينة النص الأصلي الكامل للموضوع (مطابق حرفياً للمصدر دون مغادرة الموقع)'}</summary>"
        '<div class="full-article-modal-box" dir="rtl">'
        '<div class="full-article-header" dir="rtl">'
        f'<div style="font-weight:900;color:#c4b5fd;font-size:0.94rem;">📖 {"التفريغ النصي وتفاصيل الفيديو كما وردت في" if (plat == "يوتيوب" or "youtube.com" in clean_link_url.lower() or "youtu.be" in clean_link_url.lower()) else "النص الأصلي الكامل للموضوع كما ورد في"} ({source_safe})</div>'
        f'<a class="news-link" href="{url_safe}" target="_blank" rel="noopener noreferrer">🔗 التحقق من المصدر الأصلي</a>'
        "</div>"
        f'<div class="full-article-body" dir="rtl">{verbatim_paragraphs_html}</div>'
        "</div>"
        "</details>"
        "</div>"
        "</div>"
        "</div>"
    )
    render_html(card_html)

    is_youtube_card = (
        plat == "يوتيوب"
        or "youtube.com" in clean_link_url.lower()
        or "youtu.be" in clean_link_url.lower()
    )

    # حاوية فورية لمشغل الصوت أو لوحة التفريغ الصوتي للفيديو تظهر مباشرة عند الضغط
    audio_slot = st.empty()
    transcript_slot = st.empty()
    just_triggered_audio = False
    just_triggered_transcript = False

    b_col1, b_col2, b_col3, b_col4 = st.columns([1.25, 1.35, 1.35, 1.15])
    with b_col1:
      if st.button("🔊 استماع صوتي للملخص", key=f"tts_sum_{widget_uid}", use_container_width=True):
        with audio_slot.container():
          render_html(
              '<div style="background:rgba(14,165,233,0.18);border:1px solid rgba(56,189,248,0.5);border-radius:10px;padding:8px 14px;margin:4px 0;color:#7dd3fc;font-weight:800;font-size:0.84rem;direction:rtl;text-align:right;">⏳ جاري توليد القراءة الصوتية للملخص...</div>'
          )
        tts_text_to_read = f"{raw_title}. {raw_summary}"
        audio_bytes, mime_t = generate_gemini_or_server_tts_audio(
            tts_text_to_read, api_key_curr, mode="summary"
        )
        st.session_state["active_tts_audio"][stable_art_id] = {
            "bytes": audio_bytes,
            "b64": base64.b64encode(audio_bytes).decode("ascii") if audio_bytes else "",
            "mime": mime_t or "audio/mpeg",
            "text": tts_text_to_read,
            "label": f"قراءة صوتية لملخص الخبر ({raw_src})",
            "active_tab": tab_prefix,
        }
        just_triggered_audio = True

    with b_col2:
      if is_youtube_card:
        if st.button("📝 التفريغ الصوتي للفيديو", key=f"yt_trans_{widget_uid}", use_container_width=True):
          with transcript_slot.container():
            render_html(
                '<div style="background:rgba(239,68,68,0.18);border:1px solid rgba(248,113,113,0.55);border-radius:10px;padding:8px 14px;margin:4px 0;color:#fecaca;font-weight:800;font-size:0.84rem;direction:rtl;text-align:right;">⏳ جاري استخراج وتدقيق التفريغ الصوتي للفيديو باللغة العربية الفصحى السليمة 100%...</div>'
            )
          perfect_ar_transcript = transcribe_youtube_video_to_perfect_arabic(
              item, api_key=api_key_curr
          )
          st.session_state.setdefault("active_yt_transcripts", {})[stable_art_id] = {
              "text": perfect_ar_transcript,
              "title": raw_title,
              "source": raw_src,
              "url": clean_link_url,
              "active_tab": tab_prefix,
          }
          just_triggered_transcript = True
      else:
        if st.button("🎙️ استماع للنص الأصلي الكامل", key=f"tts_full_{widget_uid}", use_container_width=True):
          with audio_slot.container():
            render_html(
                '<div style="background:rgba(139,92,246,0.2);border:1px solid rgba(167,139,250,0.55);border-radius:10px;padding:8px 14px;margin:4px 0;color:#ddd6fe;font-weight:800;font-size:0.84rem;direction:rtl;text-align:right;">⏳ جاري استخراج النص الأصلي الكامل وتوليد القراءة الصوتية...</div>'
            )
          full_fetched = ensure_verbatim_full_text_for_item(item)
          full_body_clean = clean_display_text(full_fetched or verbatim_body)
          if len(full_body_clean) < len(raw_summary):
            full_body_clean = f"{raw_summary}. {full_body_clean}"
          tts_full_to_read = f"{raw_title}. {full_body_clean}"
          audio_bytes, mime_t = generate_gemini_or_server_tts_audio(
              tts_full_to_read, api_key_curr, mode="full"
          )
          st.session_state["active_tts_audio"][stable_art_id] = {
              "bytes": audio_bytes,
              "b64": base64.b64encode(audio_bytes).decode("ascii") if audio_bytes else "",
              "mime": mime_t or "audio/mpeg",
              "text": tts_full_to_read,
              "label": f"قراءة صوتية للنص الأصلي الكامل ({raw_src})",
              "active_tab": tab_prefix,
          }
          just_triggered_audio = True

    with b_col3:
      selected_map_curr = st.session_state.setdefault("selected_export_articles", {})
      is_currently_sel = stable_art_id in selected_map_curr
      btn_sel_lbl = "✅ محدد للتصدير (إلغاء)" if is_currently_sel else "☑️ تحديد للتصدير (Word/PDF)"
      if st.button(btn_sel_lbl, key=f"sel_exp_{widget_uid}", use_container_width=True):
        if is_currently_sel:
          selected_map_curr.pop(stable_art_id, None)
        else:
          item_copy = dict(item)
          item_copy["summary"] = raw_summary
          item_copy["source_name"] = raw_src
          item_copy["url"] = clean_link_url
          if raw_img:
            item_copy["image_url"] = raw_img
          selected_map_curr[stable_art_id] = item_copy
        st.rerun()

    with b_col4:
      render_html(
          f'<div style="display:flex;align-items:center;justify-content:center;height:42px;"><a class="news-link" style="width:100%;justify-content:center;height:40px;" href="{url_safe}" target="_blank" rel="noopener noreferrer">🔗 فتح المصدر الأصلي</a></div>'
      )

    active_transcript_entry = st.session_state.get("active_yt_transcripts", {}).get(stable_art_id)
    if is_youtube_card and active_transcript_entry and (just_triggered_transcript or active_transcript_entry.get("active_tab", tab_prefix) == tab_prefix):
      with transcript_slot.container():
        tr_txt = active_transcript_entry.get("text") or ""
        _render_youtube_transcript_component(
            tr_txt,
            active_transcript_entry.get("title") or raw_title,
            active_transcript_entry.get("source") or raw_src,
            active_transcript_entry.get("url") or clean_link_url,
        )
        tr_c1, tr_c2 = st.columns([1.5, 1.5])
        with tr_c1:
          st.download_button(
              "⬇️ تحميل التفريغ الصوتي نصياً (.txt)",
              data=f"⚖️ المرصد القضائي — التفريغ الصوتي للفيديو\nالعنوان: {raw_title}\nالمصدر: {raw_src}\nالرابط: {clean_link_url}\n\n{tr_txt}".encode("utf-8"),
              file_name=f"تفريغ_صوتي_{stable_art_id}.txt",
              mime="text/plain",
              key=f"dl_tr_{widget_uid}",
              use_container_width=True,
          )
        with tr_c2:
          if st.button("✖️ إخفاء التفريغ الصوتي", key=f"close_tr_{widget_uid}", use_container_width=True):
            st.session_state.get("active_yt_transcripts", {}).pop(stable_art_id, None)
            st.rerun()

    active_audio_entry = st.session_state.get("active_tts_audio", {}).get(stable_art_id)
    if active_audio_entry and (just_triggered_audio or active_audio_entry.get("active_tab", tab_prefix) == tab_prefix):
      with audio_slot.container():
        a_bytes = active_audio_entry.get("bytes") or b""
        a_b64 = active_audio_entry.get("b64") or ""
        a_mime = active_audio_entry.get("mime") or "audio/mpeg"
        a_text = active_audio_entry.get("text") or f"{raw_title}. {raw_summary}"
        a_lbl = active_audio_entry.get("label") or "قراءة صوتية للخبر"
        _render_interactive_audio_component(
            a_b64,
            a_mime,
            a_text,
            a_lbl,
            auto_play=just_triggered_audio,
            api_key=api_key_curr,
        )
        if a_bytes and hasattr(st, "audio"):
          try:
            st.audio(a_bytes, format=a_mime, autoplay=just_triggered_audio)
          except TypeError:
            st.audio(a_bytes, format=a_mime)
        if not is_youtube_card:
          if st.button("✈️ إرسال الاستماع الصوتي لهذا الخبر إلى بوت تلغرام", key=f"tg_aud_{widget_uid}", use_container_width=True):
            sent_ok = send_telegram_audio_for_item(
                item, cfg, prebuilt_audio=(a_bytes, a_mime) if a_bytes else None
            )
            if sent_ok:
              st.success("✅ تم إرسال الملف الصوتي للخبر إلى بوت تلغرام (المرصد القضائي) بنجاح")
            else:
              st.warning("⚠️ تعذر إرسال الملف الصوتي حالياً، يرجى التحقق من إعدادات بوت تلغرام")

  if len(items_list) > curr_page_limit:
    rem_count = len(items_list) - curr_page_limit
    if st.button(
        f"➕ عرض المزيد من المنشورات في هذا القسم (متبقي {rem_count} منشور)",
        key=f"btn_more_{tab_prefix}_{curr_page_limit}",
        use_container_width=True,
    ):
      st.session_state[page_limit_key] = curr_page_limit + 25
      st.rerun()


# =====================================================================
# 18. مركز البحث في الأخبار المرصودة (الحالية والمؤرشفة) وتجميع وتصدير تقارير Word و PDF
# =====================================================================
def render_monitored_search_and_export_hub(all_monitored_pool: list, live_pool: list, archive_pool: list, key_prefix: str = "hub"):
  selected_map = st.session_state.setdefault("selected_export_articles", {})
  live_ids_set = {get_stable_article_id(x) for x in live_pool}

  render_html(
      f"""
      <div style="background:linear-gradient(135deg, rgba(14, 165, 233, 0.20) 0%, rgba(15, 23, 42, 0.88) 70%, rgba(30, 41, 59, 0.92) 100%);border:1px solid rgba(56, 189, 248, 0.52);border-right:5px solid #38bdf8;border-radius:18px;padding:14px 20px;margin:8px 0 12px 0;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;direction:rtl;text-align:right;">
          <div style="display:flex;align-items:center;gap:12px;direction:rtl;">
              <span style="width:44px;height:44px;min-width:44px;border-radius:13px;display:inline-flex;align-items:center;justify-content:center;font-size:1.35rem;background:rgba(56,189,248,0.2);border:1px solid rgba(56,189,248,0.55);">📑</span>
              <div>
                  <div style="font-size:clamp(1.02rem, 1.8vw, 1.18rem);font-weight:900;color:#f0f9ff;line-height:1.3;">المرصد القضائي — البحث في الأخبار المرصودة وتجميع وتصدير التقارير (Word & PDF)</div>
                  <div style="font-size:0.8rem;font-weight:700;color:#cbd5e1;margin-top:2px;">ابحث بالكلمة المفتاحية في الأخبار المعروضة حالياً أو المؤرشفة، وحدد الأخبار لتصديرها إلى Word (جدول RTL بـ 3 أعمدة: العنوان • الملخص • المصدر والرابط) أو PDF (مع عمود الصورة المصغرة)</div>
              </div>
          </div>
          <span style="background:rgba(16,185,129,0.22);border:1px solid rgba(52,211,153,0.6);color:#6ee7b7;padding:5px 14px;border-radius:999px;font-size:0.82rem;font-weight:900;">✅ الأخبار المحددة للتصدير: {len(selected_map)}</span>
      </div>
      """
  )

  c_s1, c_s2, c_s3 = st.columns([2.4, 1.3, 1.1])
  with c_s1:
    search_kw_val = st.text_input(
        "🔎 الكلمة المفتاحية للبحث في المرصود",
        placeholder="🔎 ابحث بكلمة مفتاحية في العنوان أو الملخص أو النص الكامل أو المصدر...",
        key=f"{key_prefix}_kw_input",
        label_visibility="collapsed",
    )
  with c_s2:
    scope_choice = st.selectbox(
        "نطاق البحث",
        options=[
            f"الكل: المعروضة حالياً + المؤرشفة ({len(all_monitored_pool)})",
            f"الأخبار المعروضة حالياً فقط ({len(live_pool)})",
            f"الأخبار المؤرشفة فقط ({len(archive_pool)})",
        ],
        key=f"{key_prefix}_scope_select",
        label_visibility="collapsed",
    )
  with c_s3:
    plat_choice = st.selectbox(
        "المنصة",
        options=["جميع المنصات", "الصحف", "فيسبوك", "إكس", "يوتيوب", "أخرى", "المخصص"],
        key=f"{key_prefix}_plat_select",
        label_visibility="collapsed",
    )

  if "المعروضة حالياً فقط" in scope_choice:
    candidate_pool = list(live_pool)
  elif "المؤرشفة فقط" in scope_choice:
    candidate_pool = list(archive_pool)
  else:
    candidate_pool = list(all_monitored_pool)

  if plat_choice == "المخصص":
    candidate_pool = [a for a in candidate_pool if int(a.get("is_custom_target", 0)) == 1]
  elif plat_choice != "جميع المنصات":
    candidate_pool = [a for a in candidate_pool if clean_display_text(a.get("platform") or "الصحف") == plat_choice]

  kw_clean = search_kw_val.strip()
  if kw_clean:
    matched_results = []
    q_norm = normalize_arabic_for_dedup(kw_clean)
    q_low = kw_clean.lower()
    for a in candidate_pool:
      t_a = a.get("title", "")
      s_a = a.get("summary", "")
      r_a = a.get("raw_snippet", "")
      src_a = format_precise_source_with_domain(
          a.get("source_name", ""), a.get("url", ""), a.get("platform", "الصحف"), title_hint=t_a
      )
      cat_a = a.get("category", "")
      combined_hay = f"{t_a} {s_a} {r_a} {src_a} {cat_a}"
      if (
          matches_custom_keywords(t_a, f"{s_a} {r_a} {src_a}", kw_clean)
          or (q_norm and q_norm in normalize_arabic_for_dedup(combined_hay))
          or (q_low in combined_hay.lower())
      ):
        matched_results.append(a)
  else:
    matched_results = candidate_pool

  # أزرار التحديد الجماعي وإلغاء التحديد
  act_c1, act_c2, act_c3 = st.columns([1.5, 1.5, 2.0])
  with act_c1:
    if st.button(f"☑️ تحديد كل نتائج البحث ({len(matched_results)})", key=f"{key_prefix}_sel_all_btn", use_container_width=True):
      for m_it in matched_results[:100]:
        aid = get_stable_article_id(m_it)
        it_copy = dict(m_it)
        raw_t = clean_display_text(it_copy.get("title") or "")
        raw_s = clean_display_text(it_copy.get("summary") or "")
        plat = clean_display_text(it_copy.get("platform") or "الصحف")
        clean_u = clean_social_post_url(it_copy.get("url") or "")
        src = format_precise_source_with_domain(
            it_copy.get("source_name") or plat, clean_u, plat, title_hint=raw_t
        )
        it_copy["source_name"] = src
        if is_summary_just_title(raw_t, raw_s):
          it_copy["summary"] = build_extractive_arabic_summary(raw_t, clean_display_text(it_copy.get("raw_snippet") or ""), plat, src)
        selected_map[aid] = it_copy
      st.rerun()
  with act_c2:
    if st.button(f"🗑️ مسح التحديد بالكامل ({len(selected_map)})", key=f"{key_prefix}_clear_sel_btn", use_container_width=True):
      selected_map.clear()
      st.session_state.pop("cached_export_bundle", None)
      st.rerun()
  with act_c3:
    render_html(
        f"<div style='height:42px;display:flex;align-items:center;justify-content:flex-start;padding:0 12px;background:rgba(15,23,42,0.65);border:1px solid rgba(148,163,184,0.28);border-radius:12px;color:#e2e8f0;font-size:0.84rem;font-weight:800;direction:rtl;'>📊 نتائج البحث المطابقة: <strong style='color:#38bdf8;margin:0 6px;'>{len(matched_results)}</strong> خبر  |  المحدد للتصدير: <strong style='color:#34d399;margin:0 6px;'>{len(selected_map)}</strong> خبر</div>"
    )

  # لوحة التصدير الفوري إلى Word (.docx) و PDF (.pdf) وعرض الجدول المنظم للأخبار المحددة
  if selected_map:
    selected_items_list = sorted(
        list(selected_map.values()),
        key=lambda x: float(x.get("pub_timestamp", 0)),
        reverse=True,
    )
    docx_bytes, pdf_bytes, export_html_str = get_or_build_export_files(selected_items_list, search_kw=kw_clean)
    ts_file_tag = datetime.now().strftime("%Y%m%d_%H%M")

    render_html(
        f"""
        <div style="background:linear-gradient(135deg, rgba(6, 78, 59, 0.45) 0%, rgba(15, 23, 42, 0.92) 100%);border:1.5px solid rgba(52, 211, 153, 0.65);border-radius:16px;padding:14px 18px;margin:10px 0 14px 0;direction:rtl;text-align:right;">
            <div style="font-size:0.96rem;font-weight:900;color:#6ee7b7;margin-bottom:6px;">📥 سلة التجميع والتصدير جاهزة ({len(selected_items_list)} خبر محدد) — اختر صيغة التحميل:</div>
            <div style="font-size:0.81rem;color:#cbd5e1;line-height:1.6;">
              • <strong>ملف Word (.docx):</strong> مصمم باتجاه عربي RTL من اليمين إلى اليسار بـ 3 أعمدة: <strong>(1) العنوان • (2) الملخص • (3) المصدر (رابط الخبر)</strong> (بدون عمود الصورة المصغرة).<br>
              • <strong>ملف PDF (.pdf):</strong> يضم 4 أعمدة: <strong>(1) العنوان • (2) الملخص • (3) المصدر (رابط الخبر) • (4) الصورة المصغرة</strong>.
            </div>
        </div>
        """
    )

    dl_col1, dl_col2, dl_col3 = st.columns([1.6, 1.6, 1.6])
    with dl_col1:
      if docx_bytes:
        st.download_button(
            label=f"📘 تحميل ملف وورد Word (.docx) [{len(selected_items_list)} خبر]",
            data=docx_bytes,
            file_name=f"المرصد_القضائي_تقرير_{ts_file_tag}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key=f"{key_prefix}_dl_docx_btn",
            use_container_width=True,
        )
    with dl_col2:
      if pdf_bytes:
        st.download_button(
            label=f"📕 تحميل ملف PDF (.pdf) [{len(selected_items_list)} خبر]",
            data=pdf_bytes,
            file_name=f"المرصد_القضائي_تقرير_{ts_file_tag}.pdf",
            mime="application/pdf",
            key=f"{key_prefix}_dl_pdf_btn",
            use_container_width=True,
        )
    with dl_col3:
      if export_html_str:
        _render_client_side_pdf_printer(export_html_str, len(selected_items_list))

    # معاينة مباشرة للجدول المنظم داخل المنصة
    preview_rows_html = []
    for s_idx, s_it in enumerate(selected_items_list):
      s_t = clean_display_text(s_it.get("title") or "")
      s_plat = clean_display_text(s_it.get("platform") or "الصحف")
      s_u = clean_social_post_url(s_it.get("url") or "#")
      s_src = format_precise_source_with_domain(
          s_it.get("source_name") or s_plat, s_u, s_plat, title_hint=s_t
      )
      s_sum = clean_display_text(s_it.get("summary") or "")
      if is_summary_just_title(s_t, s_sum):
        s_sum = build_extractive_arabic_summary(s_t, clean_display_text(s_it.get("raw_snippet") or ""), s_plat, s_src)
      s_dt = clean_display_text(s_it.get("pub_date") or "")
      s_fb_svg = get_fallback_thumbnail_data_uri(s_plat, s_src)
      s_img = clean_and_validate_image_url((s_it.get("image_url") or "").strip(), s_u, s_plat) or extract_thumbnail_for_item(s_u, "", s_plat) or s_fb_svg
      preview_rows_html.append(
          f"""
          <tr style="border-bottom:1px solid rgba(148,163,184,0.2);">
              <td style="padding:10px;font-weight:800;color:#f8fafc;width:24%;vertical-align:middle;"><span style="color:#38bdf8;">[{s_idx + 1}]</span> <a href="{html.escape(s_u, quote=True)}" target="_blank" style="color:#f8fafc;text-decoration:none;">{html.escape(s_t)}</a></td>
              <td style="padding:10px;color:#cbd5e1;font-size:0.86rem;line-height:1.65;width:40%;vertical-align:middle;">{html.escape(s_sum)}</td>
              <td style="padding:10px;color:#e2e8f0;font-size:0.83rem;font-weight:700;width:21%;vertical-align:middle;">
                {html.escape(s_src)}<br>
                <span style="color:#94a3b8;font-size:0.76rem;">{html.escape(s_plat)} • <span dir="ltr">{html.escape(s_dt)}</span></span><br>
                <a href="{html.escape(s_u, quote=True)}" target="_blank" style="color:#38bdf8;font-size:0.78rem;text-decoration:underline;">🔗 فتح رابط الخبر الأصلي</a>
              </td>
              <td style="padding:8px;text-align:center;width:15%;vertical-align:middle;"><img src="{html.escape(s_img, quote=True)}" onerror="this.onerror=null;this.src='{html.escape(s_fb_svg, quote=True)}';" style="width:115px;height:74px;object-fit:cover;border-radius:8px;border:1px solid rgba(148,163,184,0.35);display:block;margin:0 auto;" /></td>
          </tr>
          """
      )

    with st.expander(f"👁️ المرصد القضائي — معاينة الجدول المنظم للأخبار المحددة للتصدير ({len(selected_items_list)} خبر)", expanded=True):
      render_html(
          f"""
          <div style="overflow-x:auto;background:rgba(9,13,22,0.85);border:1px solid rgba(56,189,248,0.35);border-radius:14px;padding:10px;direction:rtl;text-align:right;">
              <div style="font-weight:900;color:#38bdf8;font-size:0.95rem;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid rgba(56,189,248,0.28);">⚖️ المرصد القضائي — جدول الأخبار القضائية المحددة ({len(selected_items_list)} خبر)</div>
              <table style="width:100%;border-collapse:collapse;direction:rtl;text-align:right;font-family:'Cairo',sans-serif;">
                  <thead>
                      <tr style="background:rgba(15,23,42,0.95);border-bottom:2px solid #38bdf8;">
                          <th style="padding:10px;color:#38bdf8;font-weight:900;text-align:center;width:24%;">العنوان</th>
                          <th style="padding:10px;color:#38bdf8;font-weight:900;text-align:center;width:40%;">الملخص</th>
                          <th style="padding:10px;color:#38bdf8;font-weight:900;text-align:center;width:21%;">المصدر (رابط الخبر)</th>
                          <th style="padding:10px;color:#38bdf8;font-weight:900;text-align:center;width:15%;">الصورة (تظهر في PDF فقط)</th>
                      </tr>
                  </thead>
                  <tbody>
                      {''.join(preview_rows_html)}
                  </tbody>
              </table>
          </div>
          """
      )

  # عرض قائمة نتائج البحث مع خانات الاختيار السريعة للتحديد
  if not matched_results:
    render_html(
        "<div dir='rtl' style='text-align:center;padding:24px;color:#94a3b8;background:rgba(15,23,42,0.5);border-radius:14px;border:1px dashed rgba(148,163,184,0.25);'>لا توجد أخبار مرصودة تطابق كلمة البحث أو الفلتر المحدد حالياً.</div>"
    )
    return

  hub_limit_key = f"{key_prefix}_display_limit"
  display_limit = int(st.session_state.get(hub_limit_key, 20))
  for r_idx, item in enumerate(matched_results[:display_limit]):
    aid = get_stable_article_id(item)
    is_sel = aid in selected_map
    is_live_item = aid in live_ids_set
    status_badge = (
        "<span style='background:rgba(16,185,129,0.18);border:1px solid rgba(52,211,153,0.45);color:#6ee7b7;padding:2px 9px;border-radius:999px;font-size:0.74rem;font-weight:800;'>🟢 معروض حالياً</span>"
        if is_live_item
        else "<span style='background:rgba(148,163,184,0.18);border:1px solid rgba(148,163,184,0.4);color:#cbd5e1;padding:2px 9px;border-radius:999px;font-size:0.74rem;font-weight:800;'>🗄️ مؤرشف</span>"
    )
    plat = clean_display_text(item.get("platform") or "الصحف")
    raw_t = clean_display_text(item.get("title") or "")
    clean_u = clean_social_post_url(item.get("url") or "#")
    raw_src = format_precise_source_with_domain(
        item.get("source_name") or plat, clean_u, plat, title_hint=raw_t
    )
    raw_sum = clean_display_text(item.get("summary") or "")
    if is_summary_just_title(raw_t, raw_sum):
      raw_sum = build_extractive_arabic_summary(raw_t, clean_display_text(item.get("raw_snippet") or ""), plat, raw_src)
    pub_dt = clean_display_text(item.get("pub_date") or "")
    fb_svg = get_fallback_thumbnail_data_uri(plat, raw_src)
    raw_img = clean_and_validate_image_url((item.get("image_url") or "").strip(), clean_u, plat) or extract_thumbnail_for_item(clean_u, "", plat) or fb_svg

    row_c1, row_c2 = st.columns([0.95, 5.05])
    with row_c1:
      new_sel_state = st.checkbox(
          "تحديد للتصدير",
          value=is_sel,
          key=f"{key_prefix}_chk_{aid}_{r_idx}",
      )
      if new_sel_state != is_sel:
        if new_sel_state:
          it_c = dict(item)
          it_c["summary"] = raw_sum
          it_c["source_name"] = raw_src
          it_c["url"] = clean_u
          selected_map[aid] = it_c
        else:
          selected_map.pop(aid, None)
        st.rerun()
    with row_c2:
      border_col = "rgba(52, 211, 153, 0.7)" if is_sel else "rgba(148, 163, 184, 0.24)"
      bg_col = "rgba(6, 78, 59, 0.25)" if is_sel else "rgba(15, 23, 42, 0.78)"
      render_html(
          f"""
          <div style="background:{bg_col};border:1px solid {border_col};border-right:4px solid {'#10b981' if is_sel else '#38bdf8'};border-radius:14px;padding:10px 14px;margin-bottom:8px;display:flex;align-items:center;gap:14px;direction:rtl;text-align:right;">
              <img src="{html.escape(raw_img, quote=True)}" onerror="this.onerror=null;this.src='{html.escape(fb_svg, quote=True)}';" style="width:110px;min-width:110px;height:72px;object-fit:cover;border-radius:9px;border:1px solid rgba(148,163,184,0.3);" />
              <div style="flex:1;min-width:0;direction:rtl;text-align:right;">
                  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px;">
                      {status_badge}
                      <span class="badge-plat">{html.escape(plat)}</span>
                      <span style="font-weight:800;color:#38bdf8;font-size:0.82rem;">🌐 {html.escape(raw_src)}</span>
                      <span style="color:#94a3b8;font-size:0.78rem;font-weight:700;" dir="ltr">📅 {html.escape(pub_dt)}</span>
                  </div>
                  <div style="font-weight:900;color:#f8fafc;font-size:0.96rem;margin-bottom:4px;"><a href="{html.escape(clean_u, quote=True)}" target="_blank" style="color:inherit;text-decoration:none;">{html.escape(raw_t)}</a></div>
                  <div style="color:#cbd5e1;font-size:0.84rem;line-height:1.55;">{html.escape(raw_sum[:260] + ('...' if len(raw_sum) > 260 else ''))}</div>
              </div>
          </div>
          """
      )

  if len(matched_results) > display_limit:
    if st.button(
        f"➕ عرض المزيد من نتائج البحث ({len(matched_results) - display_limit} نتيجة إضافية)",
        key=f"{key_prefix}_more_btn_{display_limit}",
        use_container_width=True,
    ):
      st.session_state[hub_limit_key] = display_limit + 25
      st.rerun()


# عرض نتائج رصد المنصة بالكلمة المفتاحية بشكل فوري ومباشر بعد تعريف جميع دوال العرض (لضمان عدم حدوث NameError)
active_pkw_filter = st.session_state.get("active_platform_kw_filter")
if isinstance(active_pkw_filter, dict) and active_pkw_filter.get("keyword"):
  f_plat = active_pkw_filter.get("platform", "فيسبوك")
  f_kw = active_pkw_filter.get("keyword", "").strip().strip('"\'«» ')
  f_kw_tag = f"#kwtrack={urllib.parse.quote(f_kw, safe='')}".lower()
  pkw_matched_articles = []
  pkw_all_time_matches = []
  for art_it in all_articles:
    art_plat = clean_display_text(art_it.get("platform") or "الصحف")
    if f_plat != "شامل" and art_plat != f_plat:
      continue
    raw_u_it = str(art_it.get("url") or "").lower()
    hay_txt = f"{art_it.get('title', '')} {art_it.get('summary', '')} {art_it.get('raw_snippet', '')} {art_it.get('source_name', '')}"
    if (f_kw and f_kw_tag in raw_u_it) or matches_custom_keywords(art_it.get("title", ""), hay_txt, f_kw):
      pkw_all_time_matches.append(art_it)
      art_pub_t = float(art_it.get("pub_timestamp", 0))
      if selected_period_sec <= 0 or (now_ts - art_pub_t) <= selected_period_sec or (f_kw and f_kw_tag in raw_u_it):
        pkw_matched_articles.append(art_it)

  if not pkw_matched_articles and pkw_all_time_matches:
    pkw_matched_articles = pkw_all_time_matches

  pkw_matched_articles.sort(key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True)

  pkw_hdr_c1, pkw_hdr_c2 = st.columns([4.8, 1.2])
  with pkw_hdr_c1:
    render_html(
        f"""
        <div style="background:linear-gradient(90deg, rgba(14,165,233,0.28) 0%, rgba(15,23,42,0.92) 100%);border:1.5px solid rgba(56,189,248,0.65);border-right:5px solid #38bdf8;border-radius:14px;padding:12px 18px;margin:6px 0 10px 0;direction:rtl;text-align:right;">
            <div style="font-size:1.02rem;font-weight:900;color:#f0f9ff;">
                🎯 نتائج رصد منصة <span style="color:#38bdf8;">({html.escape(f_plat)})</span> للكلمة المفتاحية <span style="color:#34d399;">«{html.escape(f_kw)}»</span>
                — إجمالي المنشورات المطابقة: <strong style="color:#fde68a;">{len(pkw_matched_articles)}</strong> منشور
            </div>
        </div>
        """
    )
  with pkw_hdr_c2:
    if st.button("✖️ إغلاق نافذة نتائج الكلمة", key="btn_close_pkw_results", use_container_width=True):
      st.session_state.pop("active_platform_kw_filter", None)
      st.rerun()

  with st.container():
    render_article_cards(
        pkw_matched_articles,
        empty_msg=f"لم يتم العثور على منشورات في منصة ({f_plat}) تطابق الكلمة المفتاحية «{f_kw}» خلال الفترة المحددة ({cfg.get('search_period', 'آخر 7 أيام')}). جرب توسيع فترة البحث أو الضغط على 🚀 رصد وجلب المنشورات الآن.",
        tab_prefix="pkw_res",
    )


selected_count_badge = len(st.session_state.get("selected_export_articles", {}))
with st.expander(
    f"🔎 البحث في الأخبار المرصودة (الحالية والمؤرشفة) وتجميع وتصدير ملفات Word و PDF ({selected_count_badge} خبر محدد)",
    expanded=bool(selected_count_badge > 0),
):
  render_monitored_search_and_export_hub(
      all_articles, live_articles, archive_articles, key_prefix="top_hub"
  )

# =====================================================================
# 18-ب. التبويبات الرئيسية
# =====================================================================
tabs = st.tabs([
    f"🌐 الكل ({len(live_articles)})",
    f"📰 الصحف ({len(press_live)})",
    f"🟦 فيسبوك ({len(fb_live)})",
    f"⬛ إكس ({len(x_live)})",
    f"🟥 يوتيوب ({len(yt_live)})",
    f"🟪 أخرى ({len(other_live)})",
    f"🎯 المخصص ({len(target_live)})",
    f"🗄️ الأرشيف ({len(archive_articles)})",
    f"📑 بحث وتصدير ({selected_count_badge})",
])

with tabs[0]:
  render_article_cards(live_articles, tab_prefix="all")

with tabs[1]:
  render_article_cards(press_live, tab_prefix="press")

with tabs[2]:
  render_article_cards(fb_live, tab_prefix="fb")

with tabs[3]:
  render_article_cards(x_live, tab_prefix="x")

with tabs[4]:
  render_article_cards(yt_live, tab_prefix="yt")

with tabs[5]:
  render_article_cards(other_live, tab_prefix="other")

with tabs[6]:
  render_article_cards(target_live, tab_prefix="target")

with tabs[7]:
  arch_q = st.text_input(
      "🔎 البحث في الأرشيف",
      placeholder="ابحث بالعنوان أو المصدر أو الكلمة المفتاحية...",
      key="archive_search_box",
  )
  filtered_arch = archive_articles
  if arch_q.strip():
    q_low = arch_q.strip().lower()
    filtered_arch = [
        a
        for a in archive_articles
        if matches_custom_keywords(
            a.get("title", ""),
            f"{a.get('summary', '')} {a.get('raw_snippet', '')} {a.get('source_name', '')}",
            arch_q.strip(),
        )
        or q_low
        in (
            a.get("title", "")
            + " "
            + a.get("summary", "")
            + " "
            + a.get("source_name", "")
        ).lower()
    ]
  render_article_cards(
      filtered_arch,
      empty_msg="لا توجد عناصر في الأرشيف حالياً (تنتقل الأخبار تلقائياً إلى الأرشيف بعد مرور 24 ساعة على رصدها).",
      tab_prefix="arch",
  )

with tabs[8]:
  render_monitored_search_and_export_hub(
      all_articles, live_articles, archive_articles, key_prefix="tab_hub"
  )

# =====================================================================
# 19. فحص الرصد الدوري غير المتزامن (بدون تجميد الواجهة أو إعادة تحميل قسرية)
# =====================================================================
def _check_and_trigger_auto_monitor():
  if not cfg.get("auto_monitor", True):
    return
  interval_sec = INTERVAL_MAP.get(
      cfg.get("monitor_interval", "كل 15 دقيقة"), 900
  )
  m_st = load_monitor_state()
  last_run_ts = float(m_st.get("last_auto_run", 0))
  if (
      time.time() - last_run_ts >= interval_sec
      and not rt_state.get("bg_scanning", False)
      and rt_state.get("active_scan") is None
  ):
    threading.Thread(
        target=run_headless_background_cycle,
        daemon=True,
        name="OnLoadAsyncCycle",
    ).start()


_check_and_trigger_auto_monitor()

if hasattr(st, "fragment"):
  try:
    @st.fragment(run_every="60s")
    def _auto_monitor_Silent_heartbeat():
      _check_and_trigger_auto_monitor()
      last_bg_done = float(rt_state.get("last_auto_completed_ts", 0.0))
      seen_bg_done = float(st.session_state.get("_seen_auto_completed_ts", 0.0))
      if last_bg_done > seen_bg_done:
        st.session_state["_seen_auto_completed_ts"] = last_bg_done
        m_st_now = load_monitor_state()
        if int(m_st_now.get("last_auto_added", 0)) > 0 and rt_state.get("active_scan") is None:
          st.rerun()

    _auto_monitor_Silent_heartbeat()
  except Exception:
    pass

if cfg.get("auto_monitor", True):
  render_html("""
    <script>
    (function() {
      if (window.__marsadKeepAliveStarted) return;
      window.__marsadKeepAliveStarted = true;
      setInterval(function() {
        try {
          fetch(window.location.origin + "/_stcore/health", { method: "GET", cache: "no-store" }).catch(function(){});
        } catch (e) {}
      }, 45000);
      if ("wakeLock" in navigator) {
        try { navigator.wakeLock.request("screen").catch(function(){}); } catch (e) {}
      }
    })();
    </script>
    """)
