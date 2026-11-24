import difflib
import base64
import io
import zipfile
try:
  from zoneinfo import ZoneInfo
except Exception:
  ZoneInfo = None
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import concurrent.futures
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
ARCHIVE_JSON_FILE = "articles_archive.json"
CREDENTIALS_FILE = "credentials.json"
CUSTOM_TARGETS_FILE = "custom_targets.json"
MONITOR_STATE_FILE = "monitor_state.json"
TELEGRAM_LEDGER_FILE = "telegram_sent_ledger.json"

DEFAULT_TG_TOKEN = "8806182263:AAFw5HbBup_TRif3FHvZP0QFYj0YPI4mb6c"
DEFAULT_TG_CHAT_ID = "1357905784"
DEFAULT_ADMIN_PIN = "2026"
DEFAULT_GEMINI_API_KEY = "AQ.Ab8RN6L0QyUl0JoF76pZJqwGl8oo7SROd0CrCJtxlglyu_D7WQ"

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
    "رئاسة النيابة العامة المغرب",
    "القضاء بالمغرب",
    "العدالة بالمغرب",
    "محكمة النقض المغرب",
]

STRICT_JUDICIAL_UNAMBIGUOUS = [
    "المجلس الأعلى للسلطة القضائية",
    "السلطة القضائية",
    "رئاسة النيابة العامة",
    "محكمة النقض",
    "المعهد العالي للقضاء",
    "المفتشية العامة للشؤون القضائية",
    "الودادية الحسنية للقضاة",
    "نادي قضاة المغرب",
    "محمد عبد النباوي",
    "هشام البلاوي",
    "الوكيل العام للملك",
    "وكيل الملك",
    "قاضي التحقيق",
    "القضاء المغربي",
    "القضاء بالمغرب",
    "العدالة بالمغرب",
    "منظومة العدالة",
    "إصلاح العدالة",
    "المحاكم المغربية",
    "محكمة الاستئناف",
    "المحكمة الابتدائية",
    "المحكمة الإدارية",
    "المحكمة التجارية",
    "المحكمة الدستورية",
    "المسطرة الجنائية",
    "المسطرة المدنية",
    "القانون الجنائي",
    "التنظيم القضائي",
]

JUDICIAL_GENERAL_TERMS = [
    "النيابة العامة",
    "القضاء",
    "قضائي",
    "قضائية",
    "القضاة",
    "قضاة",
    "القاضي",
    "المحاكم",
    "محكمة",
    "العدالة",
    "وزارة العدل",
    "وزير العدل",
    "هيئة الحكم",
    "الغرفة الجنائية",
    "الغرفة الجنحية",
    "هيئة المحامين",
    "الضابطة القضائية",
    "الشرطة القضائية",
]

MOROCCAN_CONTEXT_TERMS = [
    "المغرب",
    "مغربي",
    "مغربية",
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
    "العيون",
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
    "بركان",
    "سيدي قاسم",
    "سيدي سليمان",
    "بن جرير",
    "اليوسفية",
    "عبد النباوي",
    "وهبي",
    "البلاوي",
    "هسبريس",
    "أخبارنا",
    "العمق",
    "كود",
    "الصباح",
    "برلمان",
    "زنقة 20",
    "اليوم 24",
    "الأيام 24",
    "مدار 21",
    "كش 24",
    "أكادير 24",
    "طنجة 24",
    "ناظورسيتي",
]

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
    {"domain": "hespress.com", "name": "هسبريس", "rss": "https://www.hespress.com/feed", "live_url": "https://www.hespress.com/", "wp": True},
    {"domain": "madar21.com", "name": "مدار 21", "rss": "https://madar21.com/feed", "live_url": "https://madar21.com/", "wp": True},
    {"domain": "hibapress.com", "name": "هبة بريس", "rss": "https://ar.hibapress.com/feed", "live_url": "https://ar.hibapress.com/", "wp": True},
    {"domain": "akhbarona.com", "name": "أخبارنا", "rss": "https://www.akhbarona.com/feed", "live_url": "https://www.akhbarona.com/", "wp": False},
    {"domain": "al3omk.com", "name": "العمق المغربي", "rss": "https://al3omk.com/feed", "live_url": "https://al3omk.com/", "wp": True},
    {"domain": "alyaoum24.com", "name": "اليوم 24", "rss": "https://alyaoum24.com/feed", "live_url": "https://alyaoum24.com/", "wp": True},
    {"domain": "rue20.com", "name": "زنقة 20", "rss": "https://rue20.com/feed", "live_url": "https://rue20.com/", "wp": True},
    {"domain": "barlamane.com", "name": "برلمان.كوم", "rss": "https://www.barlamane.com/feed", "live_url": "https://www.barlamane.com/", "wp": True},
    {"domain": "alayam24.com", "name": "الأيام 24", "rss": "https://www.alayam24.com/feed", "live_url": "https://www.alayam24.com/", "wp": True},
    {"domain": "goud.ma", "name": "كود", "rss": "https://www.goud.ma/feed", "live_url": "https://www.goud.ma/", "wp": True},
    {"domain": "assabah.ma", "name": "الصباح", "rss": "https://assabah.ma/feed", "live_url": "https://assabah.ma/", "wp": True},
    {"domain": "achkayen.com", "name": "آشكاين", "rss": "https://achkayen.com/feed", "live_url": "https://achkayen.com/", "wp": True},
    {"domain": "alaoual.com", "name": "الأول", "rss": "https://alaoual.com/feed", "live_url": "https://alaoual.com/", "wp": True},
    {"domain": "lakome2.com", "name": "لكم", "rss": "https://lakome2.com/feed", "live_url": "https://lakome2.com/", "wp": True},
    {"domain": "assahifa.com", "name": "الصحيفة", "rss": "https://www.assahifa.com/feed", "live_url": "https://www.assahifa.com/", "wp": True},
    {"domain": "howiyapress.com", "name": "هوية بريس", "rss": "https://howiyapress.com/feed", "live_url": "https://howiyapress.com/", "wp": True},
    {"domain": "ahdath.info", "name": "الأحداث المغربية", "rss": "https://ahdath.info/feed", "live_url": "https://ahdath.info/", "wp": True},
    {"domain": "febrayer.com", "name": "فبراير.كوم", "rss": "https://www.febrayer.com/feed", "live_url": "https://www.febrayer.com/", "wp": True},
    {"domain": "chouftv.ma", "name": "شوف تيفي", "rss": "https://chouftv.ma/feed", "live_url": "https://chouftv.ma/", "wp": True},
    {"domain": "anfaspress.com", "name": "أنفاس بريس", "rss": "https://anfaspress.com/feed", "live_url": "https://anfaspress.com/", "wp": False},
    {"domain": "telquel.ma", "name": "تيل كيل عربي", "rss": "https://ar.telquel.ma/feed", "live_url": "https://ar.telquel.ma/", "wp": True},
    {"domain": "le360.ma", "name": "Le360 عربي", "rss": "https://ar.le360.ma/arc/outboundfeeds/rss/", "sitemap": "https://ar.le360.ma/arc/outboundfeeds/news-sitemap/", "live_url": "https://ar.le360.ma/", "wp": False},
    {"domain": "snrtnews.com", "name": "SNRT News", "rss": "https://snrtnews.com/rss.xml", "live_url": "https://snrtnews.com/", "wp": False},
    {"domain": "medi1news.com", "name": "ميدي 1 نيوز", "rss": "https://www.medi1news.com/ar/rss", "live_url": "https://www.medi1news.com/ar", "wp": False},
    {"domain": "mapexpress.ma", "name": "وكالة المغرب العربي MAP", "rss": "https://www.mapexpress.ma/ar/feed/", "live_url": "https://www.mapexpress.ma/ar/", "wp": True},
    {"domain": "kech24.com", "name": "كش 24", "rss": "https://www.kech24.com/feed", "live_url": "https://www.kech24.com/", "wp": True},
    {"domain": "marrakechalaan.com", "name": "مراكش الآن", "rss": "https://marrakechalaan.com/feed", "live_url": "https://marrakechalaan.com/", "wp": True},
    {"domain": "agadir24.info", "name": "أكادير 24", "rss": "https://agadir24.info/feed", "live_url": "https://agadir24.info/", "wp": True},
    {"domain": "sabahagadir.com", "name": "صباح أكادير", "rss": "https://sabahagadir.com/feed", "live_url": "https://sabahagadir.com/", "wp": True},
    {"domain": "tanja24.com", "name": "طنجة 24", "rss": "https://tanja24.com/feed", "live_url": "https://tanja24.com/", "wp": True},
    {"domain": "tanjanews.com", "name": "طنجة نيوز", "rss": "https://www.tanjanews.com/feed", "live_url": "https://www.tanjanews.com/", "wp": True},
    {"domain": "fesnews.media", "name": "فاس نيوز", "rss": "https://fesnews.media/feed", "live_url": "https://fesnews.media/", "wp": True},
    {"domain": "nadorcity.com", "name": "ناظورسيتي", "rss": "https://www.nadorcity.com/xml/syndication.rss", "live_url": "https://www.nadorcity.com/", "wp": False},
    {"domain": "oujdacity.net", "name": "وجدة سيتي", "rss": "https://www.oujdacity.net/feed", "live_url": "https://www.oujdacity.net/", "wp": True},
    {"domain": "meknespress.com", "name": "مكناس بريس", "rss": "https://www.meknespress.com/feed", "live_url": "https://www.meknespress.com/", "wp": True},
    {"domain": "thevoice.ma", "name": "ذا فويس", "rss": "https://thevoice.ma/feed", "live_url": "https://thevoice.ma/", "wp": True},
    {"domain": "bayanealyaoume.press.ma", "name": "بيان اليوم", "rss": "https://bayanealyaoume.press.ma/feed", "live_url": "https://bayanealyaoume.press.ma/", "wp": True},
    {"domain": "lematin.ma", "name": "Le Matin", "rss": "https://lematin.ma/rssFeed/0", "live_url": "https://lematin.ma/", "wp": False},
    {"domain": "medias24.com", "name": "Médias24", "rss": "https://medias24.com/feed/", "live_url": "https://medias24.com/", "wp": True},
    {"domain": "lopinion.ma", "name": "L'Opinion", "rss": "https://www.lopinion.ma/xml/syndication.rss", "live_url": "https://www.lopinion.ma/", "wp": False},
    {"domain": "leconomiste.com", "name": "L'Économiste", "rss": "https://www.leconomiste.com/rss-leconomiste", "live_url": "https://www.leconomiste.com/", "wp": False},
    {"domain": "inews.ma", "name": "آي نيوز المغرب", "rss": "https://inews.ma/feed", "live_url": "https://inews.ma/", "wp": True},
    {"domain": "aabbir.com", "name": "عبّر.كوم", "rss": "https://aabbir.com/feed", "live_url": "https://aabbir.com/", "wp": True},
    {"domain": "i3lamtv.com", "name": "إعلام تيفي", "rss": "https://i3lamtv.com/feed", "live_url": "https://i3lamtv.com/", "wp": True},
    {"domain": "expresstv.ma", "name": "إكسبريس تيفي", "rss": "https://expresstv.ma/feed", "live_url": "https://expresstv.ma/", "wp": True},
    {"domain": "le12.ma", "name": "Le12.ma", "rss": "https://le12.ma/feed", "live_url": "https://le12.ma/", "wp": True},
    {"domain": "belpresse.com", "name": "بلبريس", "rss": "https://www.belpresse.com/feed", "live_url": "https://www.belpresse.com/", "wp": True},
]

# =====================================================================
# قوائم ومصادر الصحافة الدولية والقضاء المقارن (فرنسا، إسبانيا، الجزائر، ودولية)
# =====================================================================
INTERNATIONAL_PRESS_SITES = [
    # --- فرنسا (France) ---
    {"domain": "lemonde.fr", "name": "Le Monde (فرنسا)", "country": "فرنسا", "lang": "fr", "rss": "https://www.lemonde.fr/rss/une.xml"},
    {"domain": "lefigaro.fr", "name": "Le Figaro (فرنسا)", "country": "فرنسا", "lang": "fr", "rss": "https://www.lefigaro.fr/rss/figaro_actualites.xml"},
    {"domain": "liberation.fr", "name": "Libération (فرنسا)", "country": "فرنسا", "lang": "fr", "rss": "https://www.liberation.fr/arc/outboundfeeds/rss-all/collection/accueil-une/"},
    {"domain": "france24.com", "name": "France 24 (فرنسا)", "country": "فرنسا", "lang": "ar", "rss": "https://www.france24.com/ar/rss"},
    {"domain": "rfi.fr", "name": "RFI (فرنسا)", "country": "فرنسا", "lang": "ar", "rss": "https://www.rfi.fr/ar/rss"},
    {"domain": "afp.com", "name": "وكالة الصحافة الفرنسية AFP", "country": "فرنسا", "lang": "ar", "rss": "https://www.afp.com/en/news-hub/rss", "live_url": "https://www.afp.com/en/news-hub"},
    {"domain": "mediapart.fr", "name": "Mediapart (فرنسا)", "country": "فرنسا", "lang": "fr", "rss": "https://www.mediapart.fr/articles/feed", "live_url": "https://www.mediapart.fr/journal/international"},
    {"domain": "jeuneafrique.com", "name": "Jeune Afrique (باريس)", "country": "فرنسا", "lang": "fr", "rss": "https://www.jeuneafrique.com/feed/"},
    {"domain": "lexpress.fr", "name": "L'Express (فرنسا)", "country": "فرنسا", "lang": "fr", "rss": "https://www.lexpress.fr/rss/alaune.xml"},
    {"domain": "lepoint.fr", "name": "Le Point (فرنسا)", "country": "فرنسا", "lang": "fr", "rss": "https://www.lepoint.fr/rss.xml"},
    {"domain": "nouvelobs.com", "name": "L'Obs (فرنسا)", "country": "فرنسا", "lang": "fr", "rss": "https://www.nouvelobs.com/rss.xml"},
    {"domain": "la-croix.com", "name": "La Croix (فرنسا)", "country": "فرنسا", "lang": "fr", "rss": "https://www.la-croix.com/rss"},
    {"domain": "courrierinternational.com", "name": "Courrier International (فرنسا)", "country": "فرنسا", "lang": "fr", "rss": "https://www.courrierinternational.com/feed/all/rss.xml"},
    {"domain": "20minutes.fr", "name": "20 Minutes (فرنسا)", "country": "فرنسا", "lang": "fr", "rss": "https://www.20minutes.fr/feeds/rss-une.xml"},
    {"domain": "leparisien.fr", "name": "Le Parisien (فرنسا)", "country": "فرنسا", "lang": "fr", "rss": "https://feeds.leparisien.fr/leparisien/rss/actu"},

    # --- إسبانيا (Spain) ---
    {"domain": "elpais.com", "name": "El País (إسبانيا)", "country": "إسبانيا", "lang": "es", "rss": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"},
    {"domain": "elmundo.es", "name": "El Mundo (إسبانيا)", "country": "إسبانيا", "lang": "es", "rss": "https://e00-elmundo.uecdn.es/elmundo/rss/portada.xml"},
    {"domain": "abc.es", "name": "ABC (إسبانيا)", "country": "إسبانيا", "lang": "es", "rss": "https://www.abc.es/rss/2.0/portada/"},
    {"domain": "larazon.es", "name": "La Razón (إسبانيا)", "country": "إسبانيا", "lang": "es", "rss": "https://www.larazon.es/rss/espana.xml"},
    {"domain": "lavanguardia.com", "name": "La Vanguardia (إسبانيا)", "country": "إسبانيا", "lang": "es", "rss": "https://www.lavanguardia.com/rss/home.xml"},
    {"domain": "elconfidencial.com", "name": "El Confidencial (إسبانيا)", "country": "إسبانيا", "lang": "es", "rss": "https://rss.elconfidencial.com/espana/"},
    {"domain": "eldiario.es", "name": "elDiario.es (إسبانيا)", "country": "إسبانيا", "lang": "es", "rss": "https://www.eldiario.es/rss/"},
    {"domain": "efe.com", "name": "وكالة الأنباء الإسبانية EFE", "country": "إسبانيا", "lang": "es", "rss": "https://efe.com/feed/"},
    {"domain": "europapress.es", "name": "Europa Press (إسبانيا)", "country": "إسبانيا", "lang": "es", "rss": "https://www.europapress.es/rss/rss.aspx"},
    {"domain": "elespanol.com", "name": "El Español (إسبانيا)", "country": "إسبانيا", "lang": "es", "rss": "https://www.elespanol.com/rss/"},
    {"domain": "periodistadigital.com", "name": "Periodista Digital (إسبانيا)", "country": "إسبانيا", "lang": "es", "rss": "https://www.periodistadigital.com/feed/"},
    {"domain": "theobjective.com", "name": "The Objective (إسبانيا)", "country": "إسبانيا", "lang": "es", "rss": "https://theobjective.com/feed/"},
    {"domain": "vozpopuli.com", "name": "Vozpópuli (إسبانيا)", "country": "إسبانيا", "lang": "es", "rss": "https://www.vozpopuli.com/rss/"},
    {"domain": "elindependiente.com", "name": "El Independiente (إسبانيا)", "country": "إسبانيا", "lang": "es", "rss": "https://www.elindependiente.com/feed/"},

    # --- الجزائر (Algeria) ---
    {"domain": "elwatan-dz.com", "name": "El Watan (الجزائر)", "country": "الجزائر", "lang": "fr", "rss": "https://elwatan-dz.com/feed"},
    {"domain": "tsa-algerie.com", "name": "TSA Tout sur l'Algérie", "country": "الجزائر", "lang": "fr", "rss": "https://www.tsa-algerie.com/feed/"},
    {"domain": "echoroukonline.com", "name": "الشروق الجزائرية", "country": "الجزائر", "lang": "ar", "rss": "https://www.echoroukonline.com/feed"},
    {"domain": "elkhabar.com", "name": "الخبر الجزائرية", "country": "الجزائر", "lang": "ar", "rss": "https://www.elkhabar.com/press/rss/"},
    {"domain": "ennaharonline.com", "name": "النهار الجزائرية", "country": "الجزائر", "lang": "ar", "rss": "https://www.ennaharonline.com/feed/"},
    {"domain": "aps.dz", "name": "وكالة الأنباء الجزائرية APS", "country": "الجزائر", "lang": "ar", "rss": "https://www.aps.dz/algerie/feed"},
    {"domain": "algerie-eco.com", "name": "Algérie Eco", "country": "الجزائر", "lang": "fr", "rss": "https://www.algerie-eco.com/feed/"},
    {"domain": "lexpressiondz.com", "name": "L'Expression (الجزائر)", "country": "الجزائر", "lang": "fr", "rss": "https://www.lexpressiondz.com/feed"},
    {"domain": "algerie360.com", "name": "Algérie 360", "country": "الجزائر", "lang": "fr", "rss": "https://www.algerie360.com/feed/"},
    {"domain": "radioalgerie.dz", "name": "الإذاعة الجزائرية", "country": "الجزائر", "lang": "ar", "rss": "https://news.radioalgerie.dz/ar/rss.xml"},

    # --- الولايات المتحدة الأمريكية (USA) ---
    {"domain": "nytimes.com", "name": "New York Times (أمريكا)", "country": "الولايات المتحدة", "lang": "en", "rss": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
    {"domain": "washingtonpost.com", "name": "Washington Post (أمريكا)", "country": "الولايات المتحدة", "lang": "en", "rss": "https://feeds.washingtonpost.com/rss/world"},
    {"domain": "wsj.com", "name": "Wall Street Journal (أمريكا)", "country": "الولايات المتحدة", "lang": "en", "rss": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"},
    {"domain": "apnews.com", "name": "Associated Press AP (أمريكا)", "country": "الولايات المتحدة", "lang": "en", "rss": "https://feedx.net/rss/ap.xml", "sitemap": "https://apnews.com/news-sitemap-content.xml", "live_url": "https://apnews.com/hub/world-news"},
    {"domain": "bloomberg.com", "name": "Bloomberg (أمريكا)", "country": "الولايات المتحدة", "lang": "en", "rss": "https://feeds.bloomberg.com/politics/news.rss"},
    {"domain": "cnn.com", "name": "CNN (أمريكا)", "country": "الولايات المتحدة", "lang": "en", "rss": "http://rss.cnn.com/rss/edition_world.rss"},
    {"domain": "politico.com", "name": "Politico (أمريكا)", "country": "الولايات المتحدة", "lang": "en", "rss": "https://rss.politico.com/politics-news.xml"},
    {"domain": "npr.org", "name": "NPR (أمريكا)", "country": "الولايات المتحدة", "lang": "en", "rss": "https://feeds.npr.org/1004/rss.xml"},
    {"domain": "al-monitor.com", "name": "Al-Monitor (واشنطن)", "country": "الولايات المتحدة", "lang": "en", "rss": "https://www.al-monitor.com/rss"},
    {"domain": "usatoday.com", "name": "USA Today (أمريكا)", "country": "الولايات المتحدة", "lang": "en", "rss": "https://rssfeeds.usatoday.com/usatoday-NewsTopStories"},

    # --- صحافة ووكالات وهيئات دولية كبرى ---
    {"domain": "aljazeera.net", "name": "الجزيرة نت (دولي)", "country": "دولي", "lang": "ar", "rss": "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b135-bfdff8b8cab9"},
    {"domain": "bbc.com", "name": "BBC عربي (دولي)", "country": "دولي", "lang": "ar", "rss": "https://feeds.bbci.co.uk/arabic/rss.xml"},
    {"domain": "reuters.com", "name": "رويترز Reuters (دولي)", "country": "دولي", "lang": "ar", "rss": "", "sitemap": "https://www.reuters.com/arc/outboundfeeds/news-sitemap/?outputType=xml", "live_url": "https://www.reuters.com/world/africa/"},
    {"domain": "dw.com", "name": "دويتشه فيله DW (ألمانيا)", "country": "دولي", "lang": "ar", "rss": "https://rss.dw.com/rdf/rss-ar-all"},
    {"domain": "independentarabia.com", "name": "إندبندنت عربية", "country": "دولي", "lang": "ar", "rss": "https://www.independentarabia.com/rss.xml", "live_url": "https://www.independentarabia.com/"},
    {"domain": "alquds.com", "name": "جريدة القدس (دولي)", "country": "دولي", "lang": "ar", "rss": "https://alquds.com/feed/", "live_url": "https://alquds.com/", "wp": True},
    {"domain": "elaph.com", "name": "إيلاف (دولي)", "country": "دولي", "lang": "ar", "rss": "https://elaph.com/rss.xml", "live_url": "https://elaph.com/", "wp": False},
    {"domain": "zahraa.mr", "name": "زهرة شنقيط (موريتانيا)", "country": "دولي", "lang": "ar", "rss": "https://zahraa.mr/rss.xml", "live_url": "https://zahraa.mr/", "wp": False},
    {"domain": "twaslnews1.twaslnews.com", "name": "تواصل نيوز (دولي)", "country": "دولي", "lang": "ar", "rss": "https://twaslnews1.twaslnews.com/feed", "live_url": "https://twaslnews1.twaslnews.com/", "wp": True},
    {"domain": "aawsat.com", "name": "الشرق الأوسط (دولي)", "country": "دولي", "lang": "ar", "rss": "https://aawsat.com/feed"},
    {"domain": "curia.europa.eu", "name": "محكمة العدل الأوروبية CJUE", "country": "دولي", "lang": "fr", "rss": "https://curia.europa.eu/jcms/jcms/Jo2_7052/fr/?portal=rss", "live_url": "https://curia.europa.eu/jcms/jcms/Jo2_7052/fr/"},
    {"domain": "icj-cij.org", "name": "محكمة العدل الدولية CIJ", "country": "دولي", "lang": "fr", "rss": "https://www.icj-cij.org/rss.xml", "live_url": "https://www.icj-cij.org/press-releases"},
    {"domain": "icc-cpi.int", "name": "المحكمة الجنائية الدولية CPI", "country": "دولي", "lang": "fr", "rss": "https://www.icc-cpi.int/rss/news"},
]

# خلاصات حية مباشرة للصحف والمواقع الرياضية الدولية والعربية المتخصصة (رصد فوري في وقت النشر بدون أرشفة)
DIRECT_SPORTS_AND_SPECIALIZED_FEEDS = [
    {"domain": "lequipe.fr", "name": "L'Équipe (فرنسا - رياضة)", "country": "فرنسا", "rss": "https://dwh.lequipe.fr/api/edito/rss?path=/"},
    {"domain": "marca.com", "name": "Marca (إسبانيا - رياضة)", "country": "إسبانيا", "rss": "https://e00-marca.uecdn.es/rss/portada.xml"},
    {"domain": "as.com", "name": "Diario AS (إسبانيا - رياضة)", "country": "إسبانيا", "rss": "https://feeds.as.com/mrss-s/pages/as/site/as.com/portada"},
    {"domain": "mundodeportivo.com", "name": "Mundo Deportivo (إسبانيا)", "country": "إسبانيا", "rss": "https://www.mundodeportivo.com/rss/home.xml"},
    {"domain": "sport.es", "name": "Sport (إسبانيا - رياضة)", "country": "إسبانيا", "rss": "https://www.sport.es/es/rss/last_news/rss.xml"},
    {"domain": "rmcsport.bfmtv.com", "name": "RMC Sport (فرنسا)", "country": "فرنسا", "rss": "https://rmcsport.bfmtv.com/rss/fil-sport/"},
    {"domain": "footmercato.net", "name": "Foot Mercato (فرنسا)", "country": "فرنسا", "rss": "https://www.footmercato.net/flux-rss"},
    {"domain": "gazzetta.it", "name": "La Gazzetta dello Sport (إيطاليا)", "country": "دولي", "rss": "https://www.gazzetta.it/dynamic-feed/rss/section/last.xml"},
    {"domain": "kicker.de", "name": "Kicker (ألمانيا - رياضة)", "country": "دولي", "rss": "https://newsfeed.kicker.de/news/aktuell"},
    {"domain": "espn.com", "name": "ESPN (عالمي - رياضة)", "country": "الولايات المتحدة", "rss": "https://www.espn.com/espn/rss/news"},
    {"domain": "skysports.com", "name": "Sky Sports (بريطانيا)", "country": "دولي", "rss": "https://www.skysports.com/rss/12040"},
    {"domain": "bbc.com", "name": "BBC Sport (بريطانيا)", "country": "دولي", "rss": "https://feeds.bbci.co.uk/sport/rss.xml"},
    {"domain": "hesport.com", "name": "هسبورت (المغرب - رياضة)", "country": "المغرب", "rss": "https://www.hesport.com/feed", "wp": True},
    {"domain": "elbotola.com", "name": "البطولة (المغرب - رياضة)", "country": "المغرب", "rss": "https://www.elbotola.com/feed", "wp": True},
    {"domain": "almountakhab.com", "name": "المنتخب (المغرب - رياضة)", "country": "المغرب", "rss": "https://www.almountakhab.com/feed", "wp": True},
    {"domain": "winwin.com", "name": "WinWin (رياضة عربي)", "country": "دولي", "rss": "https://www.winwin.com/rss.xml"},
]

MOROCCO_EXPLICIT_AND_IMPLICIT_TERMS = [
    # العربية: صريح
    "المغرب", "مغربي", "مغربية", "مغاربة", "المغاربة", "بالمغرب", "المملكة المغربية", "الرباط",
    "الدار البيضاء", "مراكش", "طنجة", "فاس", "أكادير", "وجدة", "تطوان", "الناظور", "العيون", "الداخلة",
    # العربية: إشارات ومسائل ضمنية
    "الصحراء المغربية", "نزاع الصحراء", "محكمة العدل الأوروبية", "اتفاقية الصيد البحري",
    "الاتفاق الفلاحي", "بيغاسوس", "سبتة", "مليلية", "مضيق جبل طارق", "الهجرة غير النظامية",
    "أنبوب الغاز المغاربي", "معبر الكركرات", "الاتحاد الإفريقي", "اتفاق الصخيرات", "قضية إسكوبار الصحراء",
    "أراضي الريف", "قضية بوعشرين", "قضية الراضي", "قضية الريسوني", "مجلس الأمن", "المينورسو",
    "تسليم المطلوبين", "التعاون الأمني والقضائي", "مكافحة الإرهاب", "تهريب المخدرات",
    # الفرنسية: Maroc & Termes Associés
    "maroc", "marocain", "marocaine", "marocains", "marocaines", "rabat", "casablanca", "tanger",
    "marrakech", "fes", "agadir", "oujda", "tetouan", "nador", "laayoune", "dakhla", "royaume du maroc",
    "sahara occidental", "cour de justice de l'union européenne", "cjue", "accord de pêche",
    "accord agricole", "pegasus", "ceuta", "melilla", "détroit de gibraltar", "guerguerat",
    "mandat d'arrêt", "extradition", "cour d'appel de paris", "justice française", "coopération judiciaire",
    # الإسبانية: Marruecos & Términos Asociados
    "marruecos", "marroquí", "marroquies", "marroqui", "rabat", "casablanca", "tánger", "tanger",
    "marrakech", "ceuta", "melilla", "sahara occidental", "tribunal supremo", "audiencia nacional",
    "tribunal de justicia de la unión europea", "tjue", "acuerdo de pesca", "acuerdo agrícola",
    "orden de detención", "extradición", "frontera sur", "cooperación judicial", "fiscalía general",
    # الإنجليزية: Morocco & US/International Judicial Terms
    "morocco", "moroccan", "moroccans", "kingdom of morocco", "rabat", "casablanca", "tangier",
    "western sahara", "minurso", "us-morocco", "king mohammed vi", "marrakech", "dakhla", "laayoune",
]

# مصطلحات القضاء والعدالة الدولية (عربي، فرنسي، إسباني)
INTERNATIONAL_JUDICIAL_TERMS = [
    # العربية
    "محكمة العدل الدولية", "المحكمة الجنائية الدولية", "محكمة العدل الأوروبية", "مجلس حقوق الإنسان",
    "المحكمة الأوروبية لحقوق الإنسان", "محكمة النقض", "مجلس الدولة", "الادعاء العام", "النائب العام",
    "قاضي التحقيق", "مذكرة توقيف دولية", "تسليم المجرمين", "التعاون القضائي الدولي", "حكم قضائي",
    "استئناف", "نقض", "دعوى قضائية", "محاكمة", "سلطة قضائية", "براءة", "إدانة", "حبس نافذ",
    # الفرنسية
    "cour internationale de justice", "cour pénale internationale", "cpi", "cjue", "cour de cassation",
    "conseil d'état", "tribunal judiciaire", "parquet", "procureur", "juge d'instruction", "mandat d'arrêt",
    "extradition", "coopération judiciaire", "procès", "verdict", "jugement", "condamnation", "acquittement",
    # الإسبانية
    "tribunal internacional de justicia", "corte penal internacional", "audiencia nacional", "tribunal supremo",
    "tribunal constitucional", "fiscalía", "fiscal general", "juez de instrucción", "orden de extradición",
    "juicio", "sentencia", "condena", "absolución", "cooperación judicial internacional",
    # الإنجليزية
    "supreme court", "department of justice", "doj", "federal court", "district court", "appeals court",
    "court of appeals", "attorney general", "prosecutor", "indictment", "extradition", "verdict",
    "ruling", "lawsuit", "trial", "conviction", "acquittal", "judicial", "judiciary", "magistrate",
    "international court of justice", "international criminal court", "european court of justice",
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
    "كل ساعة": 3600,
    "كل ساعتين": 7200,
    "كل 3 ساعات": 10800,
    "كل 6 ساعات": 21600,
    "كل 12 ساعة": 43200,
    "كل 24 ساعة": 86400,
}

SEARCH_PERIOD_MAP = {
    "آخر ساعة": {"sec": 3600, "gnews": "1h", "ddg": "d", "yt": "EgIIAQ%253D%253D"},
    "آخر 24 ساعة": {"sec": 86400, "gnews": "1d", "ddg": "d", "yt": "EgIIAg%253D%253D"},
    "آخر 7 أيام": {"sec": 7 * 86400, "gnews": "7d", "ddg": "w", "yt": "EgIIAw%253D%253D"},
    "آخر شهر": {"sec": 30 * 86400, "gnews": "30d", "ddg": "m", "yt": "EgIIBA%253D%253D"},
    "آخر 3 أشهر": {"sec": 90 * 86400, "gnews": "90d", "ddg": "y", "yt": "CAI%253D"},
    "آخر 6 أشهر": {"sec": 180 * 86400, "gnews": "180d", "ddg": "y", "yt": "CAI%253D"},
    "آخر 12 شهراً": {"sec": 365 * 86400, "gnews": "1y", "ddg": "y", "yt": "CAI%253D"},
}

ARABIC_MONTHS = {
    "يناير": 1,
    "فبراير": 2,
    "مارس": 3,
    "أبريل": 4,
    "ابريل": 4,
    "ماي": 5,
    "مايو": 5,
    "يونيو": 6,
    "يوليوز": 7,
    "يوليو": 7,
    "غشت": 8,
    "أغسطس": 8,
    "شتنبر": 9,
    "سبتمبر": 9,
    "أكتوبر": 10,
    "اكتوبر": 10,
    "نونبر": 11,
    "نوفمبر": 11,
    "دجنبر": 12,
    "ديسمبر": 12,
}

ENGLISH_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
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
  txt = re.sub(r"\s+", " ", txt).strip()
  return txt


def strip_internal_url_fragments(url: str) -> str:
  return re.sub(r"#(?:plat|v4target|v3target|v2target|target)=[^\s#]*", "", str(url or "").strip())


def normalize_arabic_for_dedup(text: str) -> str:
  """تطبيع النص العربي بدقة عالية لكشف الأخبار والمنشورات المكررة حتى مع اختلاف التشكيل أو علامات الترقيم."""
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



def _arabic_light_stem(word: str) -> str:
  """تجريد خفيف للكلمات العربية (حذف السوابق واللواحق الشائعة) لإيجاد النتائج المشابهة صرفياً."""
  w = word.strip()
  if len(w) <= 3:
    return w
  for pref in ("وال", "بال", "كال", "فال", "لال", "ال"):
    if w.startswith(pref) and len(w) - len(pref) >= 3:
      w = w[len(pref):]
      break
  else:
    if w[0] in ("و", "ب", "ف", "ك", "ل") and len(w) >= 4:
      w = w[1:]
  for suf in ("ات", "ون", "ين", "ية", "ان", "ه", "ها", "هم", "كم"):
    if w.endswith(suf) and len(w) - len(suf) >= 3:
      w = w[:-len(suf)]
      break
  return w


def smart_search_articles(articles_list: list, query_str: str) -> list:
  """محرك بحث ذكي يدعم كلمة واحدة، كلمتين، ثلاث كلمات، أو جملة كاملة،
  ويرتب النتائج من المطابقة التامة إلى المطابقة المشابهة (دلالياً وصرفياً)."""
  q_raw = clean_display_text(query_str or "")
  if not q_raw or not articles_list:
    return list(articles_list or [])

  q_norm = normalize_arabic_for_dedup(q_raw)
  if not q_norm:
    return list(articles_list)

  stop_words = {"في", "من", "على", "عن", "الى", "إلى", "مع", "ان", "أن", "ما", "هو", "هي", "هذا", "هذه", "تم", "بعد", "قبل", "حول", "بشأن", "بين", "او", "أو", "و", "le", "la", "les", "de", "du", "des", "et", "en", "el", "los", "las", "y", "the", "of", "and", "in", "to"}
  raw_tokens = [t for t in q_norm.split() if len(t) >= 2 and t not in stop_words]
  if not raw_tokens:
    raw_tokens = [t for t in q_norm.split() if t]
  if not raw_tokens:
    return list(articles_list)

  q_stems = [_arabic_light_stem(t) for t in raw_tokens]
  scored_results = []

  for item in articles_list:
    t_txt = item.get("title", "") or ""
    s_txt = item.get("summary", "") or ""
    r_txt = item.get("raw_snippet", "") or ""
    src_txt = item.get("source_name", "") or ""
    cat_txt = item.get("category", "") or ""
    plat_txt = item.get("platform", "") or ""

    t_norm = normalize_arabic_for_dedup(t_txt)
    s_norm = normalize_arabic_for_dedup(s_txt)
    r_norm = normalize_arabic_for_dedup(r_txt)
    meta_norm = normalize_arabic_for_dedup(f"{src_txt} {cat_txt} {plat_txt}")
    full_norm = f"{t_norm} {s_norm} {r_norm} {meta_norm}"

    score = 0.0

    # 1) تطابق الجملة أو العبارة كاملة (الأعلى دقة)
    if len(q_norm) >= 3:
      if q_norm in t_norm:
        score += 120.0
      elif q_norm in s_norm:
        score += 85.0
      elif q_norm in full_norm:
        score += 65.0

    # 2) تطابق الكلمات الفردية والجذور المشابهة
    full_words = full_norm.split()
    full_stems = {_arabic_light_stem(w) for w in full_words if len(w) >= 2}

    matched_exact = 0
    matched_stem = 0
    for tok, st_tok in zip(raw_tokens, q_stems):
      if tok in t_norm:
        matched_exact += 1
        score += 30.0
      elif tok in s_norm or tok in meta_norm:
        matched_exact += 1
        score += 20.0
      elif tok in r_norm:
        matched_exact += 1
        score += 14.0
      elif st_tok in full_stems or any(st_tok in w for w in full_words if len(w) >= len(st_tok)):
        matched_stem += 1
        score += 12.0

    total_hits = matched_exact + matched_stem
    n_tok = len(raw_tokens)

    # مكافأة استيفاء جميع كلمات البحث (2 أو 3 كلمات أو جملة)
    if total_hits == n_tok:
      score += 45.0
    elif n_tok >= 2 and total_hits >= max(1, (n_tok + 1) // 2):
      score += 15.0 * (total_hits / n_tok)

    # 3) فحص التشابه التقريبي (Fuzzy Match) إذا لم يتحقق تطابق كافٍ بعد
    if score == 0.0 and len(q_norm) >= 4:
      # مطابقة تقريبية مع كلمات العنوان
      best_sim = 0.0
      for w in t_norm.split():
        if len(w) >= 3:
          sim = difflib.SequenceMatcher(None, q_norm[:30], w).ratio()
          if sim > best_sim:
            best_sim = sim
      if best_sim >= 0.76:
        score += best_sim * 25.0

    if score > 0.0:
      scored_results.append((score, float(item.get("pub_timestamp", 0)), item))

  scored_results.sort(key=lambda x: (x[0], x[1]), reverse=True)
  return [x[2] for x in scored_results]


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
    for k in ("story_fbid", "fbid", "v"):
      if qs.get(k) and len(qs[k][0].strip()) >= 6:
        return f"fb:{qs[k][0].strip()}"
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
    path = urllib.parse.unquote(p.path).rstrip("/")
    if netloc in ("youtube.com", "youtu.be", "facebook.com", "x.com", "twitter.com"):
      pid = extract_canonical_post_or_video_id(u)
      if pid:
        return f"{netloc}/{pid}"
    return f"{netloc}{path}".lower()
  except Exception:
    return u.lower()


def compute_article_dedup_keys(title: str, url: str) -> set:
  """توليد مفاتيح البصمة الفريدة للخبر (الرابط الموحد + معرف المنشور + البصمة النصية للعنوان)."""
  keys = set()
  raw_u = strip_internal_url_fragments(url)
  if raw_u:
    keys.add(f"raw_u:{raw_u.lower().rstrip('/')}")
  canon_u = canonicalize_url_for_dedup(url)
  if canon_u and len(canon_u) >= 6:
    keys.add(f"canon_u:{canon_u}")
  pid = extract_canonical_post_or_video_id(url)
  if pid:
    keys.add(f"pid:{pid}")
  norm_t = normalize_arabic_for_dedup(title)
  if len(norm_t) >= 20:
    keys.add(f"title:{norm_t[:85]}")
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
    if any(
        bad in path_low
        for bad in [
            "plugins/page.php",
            "login",
            "sharer",
            "hashtag/",
            "public/",
            "pages/category",
            "search/posts",
            "search/top",
            "search/",
        ]
    ):
      return False



    if (qs.get("story_fbid") or [""])[0].strip() or (qs.get("fbid") or [""])[0].strip() or (qs.get("post_id") or [""])[0].strip():
      return True

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


def is_strictly_judicial_and_clean(
    title: str,
    snippet: str = "",
    url: str = "",
    keywords_input: str = "",
    is_target: bool = False,
    is_international: bool = False,
) -> bool:
  """فحص ذكي متعدد اللغات (عربي، فرنسي، إسباني):
  1) التحقق الصارم من البعد القضائي/القانوني (وطني أو دولي).
  2) قبول الأخبار الدولية ذات الطابع القضائي العام (CJUE, CPI, CIJ, المحاكم الدولية).
  3) قبول الأخبار الدولية التي تتطرق للمغرب بشكل مباشر أو تشير إليه ضمنياً (الصحافة الفرنسية، الإسبانية، والجزائرية)."""
  t_clean = clean_display_text(title)
  s_clean = clean_display_text(snippet)
  u_clean = str(url or "").lower()
  combined = f"{t_clean} {s_clean}".lower()
  combined_with_url = f"{combined} {u_clean}"

  for bad_word in BLOCKED_INAPPROPRIATE_TERMS:
    if bad_word in combined_with_url:
      return False

  if len(t_clean) < 3 and len(s_clean) < 3:
    return False

  if url:
    u_unwrapped = clean_social_post_url(url)
    u_dom = urllib.parse.urlparse(u_unwrapped).netloc.lower()
    if any(
        d in u_dom
        for d in [
            "facebook.com",
            "fb.com",
            "fb.watch",
            "x.com",
            "twitter.com",
            "youtube.com",
            "youtu.be",
        ]
    ):
      if not is_direct_social_post_url(u_unwrapped):
        return False

  custom_kws = [
      k.strip().lower()
      for k in re.split(r"[,،\n]+", str(keywords_input or ""))
      if k.strip()
  ]
  if custom_kws:
    if not any(k in combined for k in custom_kws):
      return False

  if is_target:
    return True

  # 1) فحص الطابع القضائي (وطني، دولي، أو متعدد اللغات)
  has_strict_judicial = any(term.lower() in combined for term in STRICT_JUDICIAL_UNAMBIGUOUS)
  has_general_judicial = any(term.lower() in combined for term in JUDICIAL_GENERAL_TERMS)
  has_intl_judicial = any(term.lower() in combined for term in INTERNATIONAL_JUDICIAL_TERMS)

  is_judicial = has_strict_judicial or has_general_judicial or has_intl_judicial

  # 2) فحص البعد المغربي (صريح أو ضمني باللغات الثلاث)
  has_morocco_ctx = (
      any(m.lower() in combined_with_url for m in MOROCCAN_CONTEXT_TERMS)
      or any(m.lower() in combined_with_url for m in MOROCCO_EXPLICIT_AND_IMPLICIT_TERMS)
      or ".ma/" in u_clean
      or any(s["domain"] in u_clean for s in MOROCCAN_PRESS_SITES)
  )

  # أ) إذا كان المصدر صحافة دولية أو أجنبية (فرنسية، إسبانية، جزائرية، دولية):
  is_intl_source = (
      is_international
      or any(s["domain"] in u_clean for s in INTERNATIONAL_PRESS_SITES)
  )

  if is_intl_source:
    if has_morocco_ctx and is_judicial:
      return True
    if has_morocco_ctx:
      implicit_indicators = [
          "صحراء", "sahara", "cjue", "صيد", "pêche", "pesca", "peche", "pegasus",
          "سبتة", "ceuta", "مليلية", "melilla", "كركرات", "guerguerat", "مذكرة", "mandat",
          "تسليم", "extradition", "محكمة", "tribunal", "cour", "قضاء", "justice", "homicidio",
          "drogue", "drogas", "police", "امن", "أمن", "حدود", "frontière", "frontera"
      ]
      if any(ind in combined_with_url for ind in implicit_indicators):
        return True
    if has_intl_judicial and ("cjue" in combined or "عدل دولية" in combined or "جنائية دولية" in combined or "cour internationale" in combined or "cour pénale" in combined):
      return True
    return False

  # ب) بالنسبة للمصادر الوطنية العامة: يلزم حد أدنى من الحروف العربية والبعد القضائي
  arabic_chars = re.findall(r"[\u0600-\u06FF]", f"{t_clean} {s_clean}")
  if len(arabic_chars) < 5:
    return False

  if has_strict_judicial:
    return True

  if has_general_judicial and has_morocco_ctx:
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
  if item_plat in ("يوتيوب", "فيسبوك", "إكس") or t_plat in ("يوتيوب", "فيسبوك", "إكس"):
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
# 3. فك روابط Google News واستخراج متن الخبر الحقيقي والصورة المصغرة الأصلية
# =====================================================================
def resolve_google_news_url(url: str) -> str:
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

    try:
      art_page = f"https://news.google.com/articles/{token}"
      r = requests.get(art_page, headers=DEFAULT_HEADERS, timeout=3.5)
      if r.status_code == 200:
        sg_m = re.search(r'data-n-a-sg="([^"]+)"', r.text)
        ts_m = re.search(r'data-n-a-ts="([^"]+)"', r.text)
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
              timeout=3.5,
          )
          if rb.status_code == 200:
            m_res = re.search(
                r'\\"garturlres\\",\\"(https?://[^\\"]+)\\"', rb.text
            )
            if m_res:
              return m_res.group(1)
    except Exception:
      pass

  return u


def scrape_article_page_content_and_image(url: str):
  real_url = resolve_google_news_url(url)
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
          timeout=4.0,
      )
      if ryt.status_code == 200 and ryt.text:
        m_sd = re.search(
            r'"shortDescription"\s*:\s*"((?:[^"\\]|\\.){15,800})"',
            ryt.text,
        )
        if m_sd:
          yt_desc = decode_js_escaped_text(m_sd.group(1))
        if not yt_desc:
          m_ogd = re.search(
              r'<meta[^>]+(?:property|name)=["\'](?:og:description|description)["\'][^>]+content=["\']([^"\']+)["\']',
              ryt.text[:35000],
              re.IGNORECASE,
          )
          if m_ogd:
            yt_desc = clean_display_text(m_ogd.group(1))
    except Exception:
      pass
    return yt_thumb, yt_desc, real_url

  img_url = ""
  body_text = ""
  req_headers = (
      FB_CRAWLER_HEADERS
      if "facebook.com" in real_url or "fb.com" in real_url
      else DEFAULT_HEADERS
  )
  try:
    r = requests.get(real_url, headers=req_headers, timeout=4.0)
    if r.status_code != 200 or not r.text:
      return "", "", real_url

    html_doc = r.text
    for meta_pattern in [
        r'<meta[^>]+(?:property|name)=["\'](?:og:image|og:image:secure_url|twitter:image|twitter:image:src)["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|og:image:secure_url|twitter:image|twitter:image:src)["\']',
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
    ]:
      m_img = re.search(meta_pattern, html_doc[:25000], re.IGNORECASE)
      if m_img:
        candidate_img = html.unescape(m_img.group(1).strip())
        if candidate_img.startswith("//"):
          candidate_img = "https:" + candidate_img
        elif candidate_img.startswith("/"):
          candidate_img = urllib.parse.urljoin(real_url, candidate_img)
        if candidate_img.startswith("http"):
          img_url = candidate_img
          break

    meta_desc = ""
    bad_login_phrases = [
        "قم بتسجيل الدخول",
        "تسجيل الدخول إلى فيسبوك",
        "لبدء المشاركة والتواصل",
        "log in to facebook",
        "log in or sign up",
        "connect with friends",
        "page not found",
        "الصفحة غير موجودة",
    ]
    for desc_pattern in [
        r'<meta[^>]+(?:property|name)=["\'](?:og:description|description|twitter:description)["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:description|description|twitter:description)["\']',
    ]:
      m_d = re.search(desc_pattern, html_doc[:25000], re.IGNORECASE)
      if m_d:
        cand_d = _strip_fb_sidebar_noise(m_d.group(1))
        if any(bp in cand_d.lower() for bp in bad_login_phrases):
          continue
        if len(cand_d) > 25:
          meta_desc = cand_d
          break

    paragraphs = []
    if BeautifulSoup is not None:
      soup = BeautifulSoup(html_doc, "html.parser")
      if not img_url:
        for img_tag in soup.select(
            "article img, .post-content img, .entry-content img, .single-post img, main img"
        ):
          src_cand = (
              img_tag.get("data-src")
              or img_tag.get("data-lazy-src")
              or img_tag.get("src")
              or ""
          ).strip()
          if src_cand and not src_cand.startswith("data:"):
            if src_cand.startswith("//"):
              src_cand = "https:" + src_cand
            elif src_cand.startswith("/"):
              src_cand = urllib.parse.urljoin(real_url, src_cand)
            if src_cand.startswith("http") and not any(
                x in src_cand.lower() for x in ["avatar", "logo", "icon", "1x1"]
            ):
              img_url = src_cand
              break

      for tag in soup.select("script, style, nav, footer, header, aside"):
        tag.decompose()

      p_elements = soup.select(
          "article p, .entry-content p, .post-content p, .article-content p, .td-post-content p, main p, p"
      )
      for p_el in p_elements:
        p_txt = clean_display_text(p_el.get_text(" ", strip=True))
        if (
            len(p_txt) >= 50
            and len(re.findall(r"[\u0600-\u06FF]", p_txt)) >= 15
        ):
          if p_txt not in paragraphs:
            paragraphs.append(p_txt)
          if len(" ".join(paragraphs)) > 1600:
            break
    else:
      for raw_p in re.findall(
          r"<p[^>]*>(.*?)</p>", html_doc, re.DOTALL | re.IGNORECASE
      ):
        p_txt = clean_display_text(raw_p)
        if (
            len(p_txt) >= 50
            and len(re.findall(r"[\u0600-\u06FF]", p_txt)) >= 15
        ):
          if p_txt not in paragraphs:
            paragraphs.append(p_txt)
          if len(" ".join(paragraphs)) > 1600:
            break

    combined_parts = []
    if meta_desc and len(meta_desc) > 35:
      combined_parts.append(meta_desc)
    for p in paragraphs[:6]:
      if p not in combined_parts:
        combined_parts.append(p)
    body_text = " ".join(combined_parts)[:2200]
  except Exception:
    pass

  return img_url, body_text, real_url


def fetch_bing_news_enrichment(title: str, source_name: str = ""):
  q_clean = clean_display_text(title)
  if not q_clean:
    return "", "", ""
  src_clean = re.sub(r"🎯", "", clean_display_text(source_name)).strip()
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

        b_img = html.unescape(img_m.group(1).strip()) if img_m else ""
        b_desc = clean_display_text(desc_m.group(1)) if desc_m else ""
        b_link = html.unescape(link_m.group(1).strip()) if link_m else ""
        if "url=" in b_link:
          qs = urllib.parse.parse_qs(urllib.parse.urlparse(b_link).query)
          if "url" in qs:
            b_link = qs["url"][0]

        if b_img or len(b_desc) > 45:
          return b_img, b_desc, b_link
  except Exception:
    pass
  return "", "", ""


def enrich_item_content_and_image(item: dict) -> dict:
  url = (item.get("url") or "").strip()
  title = clean_display_text(item.get("title") or "")
  plat = item.get("platform", "الصحف")
  src = item.get("source_name", plat)
  raw_snip = clean_display_text(item.get("raw_snippet") or "")
  img_url = (item.get("image_url") or "").strip()

  if not img_url:
    img_url = extract_thumbnail_for_item(url, "", plat)

  need_body = (
      not raw_snip
      or len(raw_snip) < 85
      or raw_snip.lower() == title.lower()
      or raw_snip.startswith(title[:30])
  )
  need_img = not img_url

  if need_img or need_body:
    page_img, page_body, resolved_u = scrape_article_page_content_and_image(url)
    if page_img and not img_url:
      img_url = page_img
    if page_body and len(page_body) > len(raw_snip):
      raw_snip = page_body
    if (
        resolved_u
        and "news.google.com" not in resolved_u
        and "news.google.com" in url
    ):
      m_tag = re.search(r"(#(?:plat|v4target|v3target|v2target|target)=[^\s#]*)$", url)
      item["url"] = f"{resolved_u}{m_tag.group(1) if m_tag else ''}"

  # عدم استدعاء Bing News للأهداف المخصصة أو منصات الفيديو/التواصل حتى لا يُستبدل ملخص الفيديو أو المنشور بمقال صحفي آخر
  if (
      plat == "الصحف"
      and not int(item.get("is_custom_target", 0))
      and (not img_url or len(raw_snip) < 70 or raw_snip.lower() == title.lower())
  ):
    b_img, b_desc, b_link = fetch_bing_news_enrichment(title, src)
    if b_img and not img_url:
      img_url = b_img
    if (
        b_desc
        and len(b_desc) > len(raw_snip)
        and b_desc.lower() != title.lower()
    ):
      raw_snip = b_desc
    if b_link and (not img_url or len(raw_snip) < 80):
      p_img2, p_body2, _ = scrape_article_page_content_and_image(b_link)
      if p_img2 and not img_url:
        img_url = p_img2
      if p_body2 and len(p_body2) > len(raw_snip):
        raw_snip = p_body2

  item["image_url"] = img_url
  item["raw_snippet"] = raw_snip[:2000]
  return item



# =====================================================================
# تصنيف الدولة والموضوع والترجمة الفورية لعناوين وملخصات الصحف الأجنبية
# =====================================================================
MOROCCAN_EXTRA_DOMAINS = (
    "hespress.com", "akhbarona.com", "agadir24.info", "kech24.com", "alayam24.com",
    "madar21.com", "sabahagadir.com", "goud.ma", "assabah.ma", "thevoice.ma",
    "nadorcity.com", "al3omk.com", "alyaoum24.com", "rue20.com", "le360.ma",
    "barlamane.com", "tanja24.com", "medias24.com", "lematin.ma", "telquel.ma",
    "hibapress.com", "chouftv.ma", "febrayer.com", "lakome2.com", "yabiladi.com",
    "bladi.net", "mapnews.ma", "mapexpress.ma", "ahdath.info", "almassae.press.ma",
    "alittihad.info", "snrtnews.com", "2m.ma", "maroc.ma", "cspj.ma", "justice.gov.ma",
    "pmp.ma", "courdecassation.ma",
)

FRENCH_MEDIA_DOMAINS = (
    "lemonde.fr", "lefigaro.fr", "liberation.fr", "france24.com", "rfi.fr",
    "afp.com", "mediapart.fr", "jeuneafrique.com", "lexpress.fr", "lepoint.fr",
    "nouvelobs.com", "la-croix.com", "courrierinternational.com", "20minutes.fr",
    "leparisien.fr", "francetvinfo.fr", "bfmtv.com", "tf1info.fr", "humanite.fr",
    "latribune.fr", "lesechos.fr", "huffingtonpost.fr", "marianne.net",
    "valeursactuelles.com", "franceinfo.fr", "ouest-france.fr", "sudouest.fr",
)

SPANISH_MEDIA_DOMAINS = (
    "elpais.com", "elmundo.es", "abc.es", "larazon.es", "lavanguardia.com",
    "elconfidencial.com", "eldiario.es", "efe.com", "europapress.es",
    "elespanol.com", "periodistadigital.com", "theobjective.com", "vozpopuli.com",
    "elindependiente.com", "publico.es", "20minutos.es", "okdiario.com",
    "rtve.es", "lasexta.com", "antena3.com", "cadenaser.com", "elcorreo.com",
)

ALGERIAN_MEDIA_DOMAINS = (
    "elwatan-dz.com", "tsa-algerie.com", "echoroukonline.com", "elkhabar.com",
    "ennaharonline.com", "aps.dz", "algerie-eco.com", "lexpressiondz.com",
    "algerie360.com", "radioalgerie.dz", "entv.dz", "inter-lignes.com",
    "algerie-focus.com", "djazairess.com", "lesoirdalgerie.com", "elmoudjahid.dz",
)

US_MEDIA_DOMAINS = (
    "nytimes.com", "washingtonpost.com", "wsj.com", "apnews.com", "bloomberg.com",
    "cnn.com", "arabic.cnn.com", "politico.com", "npr.org", "al-monitor.com",
    "usatoday.com", "latimes.com", "nbcnews.com", "foxnews.com", "voanews.com",
    "abcnews.go.com", "cbsnews.com", "supremecourt.gov", "justice.gov",
)

GLOBAL_MEDIA_DOMAINS = (
    "aljazeera.net", "bbc.com", "reuters.com", "dw.com", "independentarabia.com",
    "aawsat.com", "curia.europa.eu", "icj-cij.org", "icc-cpi.int", "euronews.com",
    "skynewsarabia.com", "alarabiya.net", "rt.com", "un.org",
    "ohchr.org", "hrw.org", "amnesty.org",
)


def _unwrap_any_redirect_url(url: str) -> str:
  u = clean_social_post_url(url or "")
  if "bing.com/news/apiclick" in u.lower() and "url=" in u.lower():
    try:
      qs = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
      if qs.get("url"):
        u = qs["url"][0].strip()
    except Exception:
      pass
  return u


def detect_article_country_and_topic(title: str, snippet: str, url: str, source_name: str, platform: str) -> tuple:
  """استنتاج دقيق وحتمي لبلد المصدر (المغرب، فرنسا، إسبانيا، الجزائر، دولي)
  وموضوع الخبر (يتطرق للمغرب، قضاء دولي، قضايا وتسليم واتفاقيات، شؤون قضائية ومحاكم)."""
  t_c = clean_display_text(title).lower()
  s_c = clean_display_text(snippet).lower()
  u_unwrapped = _unwrap_any_redirect_url(url)
  u_c = str(u_unwrapped or "").lower()
  try:
    dom = urllib.parse.urlparse(u_c).netloc.lower().replace("www.", "")
  except Exception:
    dom = ""
  src_c = clean_display_text(source_name).lower()
  combined = f"{t_c} {s_c} {u_c} {src_c}"

  # 1) استنتاج الدولة بدقة عالية (دون افتراض خاطئ لفرنسا)
  country = ""

  # التحقق أولاً من النطاقات الصريحة
  if any(d in dom for d in MOROCCAN_EXTRA_DOMAINS) or dom.endswith(".ma"):
    country = "المغرب"
  elif any(d in dom for d in FRENCH_MEDIA_DOMAINS) or dom.endswith(".fr"):
    country = "فرنسا"
  elif any(d in dom for d in SPANISH_MEDIA_DOMAINS) or dom.endswith(".es"):
    country = "إسبانيا"
  elif any(d in dom for d in ALGERIAN_MEDIA_DOMAINS) or dom.endswith(".dz"):
    country = "الجزائر"
  elif any(d in dom for d in US_MEDIA_DOMAINS):
    country = "الولايات المتحدة"
  elif any(d in dom for d in GLOBAL_MEDIA_DOMAINS):
    country = "دولي"

  # التحقق عبر اسم المصدر في INTERNATIONAL_PRESS_SITES أو الأسماء الشائعة
  if not country:
    for s_info in INTERNATIONAL_PRESS_SITES:
      if (s_info["domain"] in u_c) or (s_info["name"].lower() in src_c):
        country = s_info.get("country", "")
        break

  if not country:
    if any(k in src_c for k in ("فرنسا", "le monde", "figaro", "france 24", "france24", "rfi", "afp", "mediapart", "libération", "liberation", "jeune afrique", "لوموند", "لوفيغارو", "فرانس 24", "فرانس برس")):
      country = "فرنسا"
    elif any(k in src_c for k in ("إسبانيا", "اسبانيا", "el país", "elpais", "el mundo", "abc", "la razón", "lavanguardia", "el confidencial", "efe", "europa press", "eldiario", "إل باييس", "إل موندو", "إيفي")):
      country = "إسبانيا"
    elif any(k in src_c for k in ("الجزائر", "جزائر", "el watan", "tsa", "echorouk", "el khabar", "ennahar", "aps", "الشروق", "الخبر", "النهار", "الإذاعة الجزائرية")):
      country = "الجزائر"
    elif any(k in src_c for k in ("أمريكا", "الولايات المتحدة", "new york times", "nytimes", "washington post", "wall street", "wsj", "ap news", "associated press", "cnn", "politico", "npr", "bloomberg", "al-monitor", "usa today")):
      country = "الولايات المتحدة"
    elif any(k in src_c for k in ("دولي", "الجزيرة", "bbc", "بي بي سي", "رويترز", "reuters", "dw", "دويتشه", "الشرق الأوسط", "إندبندنت", "euronews", "يورونيوز", "العربية", "سكاي نيوز", "cjue", "cij", "cpi", "محكمة العدل")):
      country = "دولي"
    elif any(s["name"].lower() in src_c for s in MOROCCAN_PRESS_SITES):
      country = "المغرب"

  if not country:
    country = "دولي" if platform == "صحافة دولية" else "المغرب"

  # 2) استنتاج الموضوع
  topic = "شؤون قضائية ومحاكم"

  has_major_intl_court = any(term.lower() in combined for term in [
      "محكمة العدل الدولية", "المحكمة الجنائية الدولية", "محكمة العدل الأوروبية", "cjue", "cpi", "cij",
      "cour internationale", "cour pénale", "tribunal internacional", "corte penal", "tjue"
  ])

  morocco_direct_keywords = [
      "المغرب", "مغربي", "مغربية", "مغاربة", "المغاربة", "المملكة المغربية", "الرباط", "الدار البيضاء",
      "مراكش", "طنجة", "فاس", "أكادير", "العيون", "الداخلة", "الناظور", "تطوان", "وجدة",
      "maroc", "marocain", "marocaine", "marocains", "marruecos", "marroquí", "marroqui", "morocco", "moroccan",
      "الصحراء المغربية", "نزاع الصحراء", "sahara occidental", "western sahara", "minurso", "المينورسو",
      "سبتة", "مليلية", "ceuta", "melilla", "كركرات", "guerguerat", "pegasus", "بيغاسوس",
      "اتفاقية الصيد البحري", "الاتفاق الفلاحي", "accord de pêche", "accord agricole", "acuerdo de pesca",
      "تسليم المطلوبين إلى المغرب", "extradition vers le maroc", "extradición a marruecos",
  ]
  has_morocco_direct = any(m.lower() in combined for m in morocco_direct_keywords)

  if has_morocco_direct and (country != "المغرب"):
    topic = "يتطرق للمغرب"
  elif has_major_intl_court:
    topic = "قضاء دولي"
  elif any(term.lower() in combined for term in [
      "تسليم", "extradition", "extradición", "mandat d'arrêt", "orden de detención", "مذكرة توقيف",
      "صيد", "pêche", "pesca", "حدود", "frontière", "frontera", "سبتة", "مليلية", "ceuta", "melilla", "narcotráfico", "drogue"
  ]):
    topic = "قضايا وتسليم واتفاقيات"

  return country, topic


def normalize_press_platform_and_source(entry: dict) -> dict:
  """ضمان عدم اختلاط الصحافة الوطنية المغربية بالصحافة الدولية أبداً بناءً على النطاق واسم المصدر."""
  if not isinstance(entry, dict):
    return entry
  plat = entry.get("platform", "الصحف")
  if plat not in ("الصحف", "صحافة دولية"):
    return entry
  country, _ = detect_article_country_and_topic(
      entry.get("title", ""),
      entry.get("raw_snippet", ""),
      entry.get("url", ""),
      entry.get("source_name", ""),
      plat,
  )
  if country in ("فرنسا", "إسبانيا", "الجزائر", "الولايات المتحدة", "دولي"):
    entry["platform"] = "صحافة دولية"
  elif country == "المغرب":
    entry["platform"] = "الصحف"
  return entry


COMPREHENSIVE_FR_ES_TRANSLATIONS = {
    # --- مصطلحات قضائية ومحاكم فرنسية ---
    "cour de cassation": "محكمة النقض",
    "cour d'appel": "محكمة الاستئناف",
    "cour de justice de l'union européenne": "محكمة العدل الأوروبية",
    "cour de justice": "محكمة العدل",
    "cour pénale internationale": "المحكمة الجنائية الدولية",
    "cour internationale de justice": "محكمة العدل الدولية",
    "conseil d'état": "مجلس الدولة",
    "tribunal judiciaire": "المحكمة الابتدائية",
    "tribunal administratif": "المحكمة الإدارية",
    "tribunal de commerce": "المحكمة التجارية",
    "parquet général": "النيابة العامة",
    "parquet national financier": "النيابة العامة المالية",
    "le parquet": "النيابة العامة",
    "procureur général": "الوكيل العام للملك",
    "procureur de la république": "المدعي العام",
    "juge d'instruction": "قاضي التحقيق",
    "juge des libertés": "قاضي الحريات والتحقيق",
    "chambre criminelle": "الغرفة الجنائية",
    "mandat d'arrêt international": "مذكرة توقيف دولية",
    "mandat d'arrêt": "مذكرة توقيف",
    "demande d'extradition": "طلب تسليم المطلوبين",
    "extradition vers le maroc": "تسليم المطلوبين إلى المغرب",
    "extradition": "تسليم المطلوبين",
    "coopération judiciaire": "التعاون القضائي",
    "garde à vue": "الحراسة النظرية",
    "détention provisoire": "الاعتقال الاحتياطي",
    "mis en examen": "المتابعة في حالة تحقيق",
    "procès verbal": "محضر رسمي",
    "procès": "محاكمة",
    "jugement": "حكم قضائي",
    "condamné à": "إدانة بـ",
    "condamnation": "إدانة قضائية",
    "acquittement": "حكم بالبراءة",
    "plainte déposée": "شكاية قضائية",
    "saisie judiciaire": "حجز قضائي",
    "escroquerie": "نصب واحتيال",
    "blanchiment d'argent": "غسيل الأموال",
    "narcotrafic": "الاتجار الدولي بالمخدرات",
    "trafic de drogue": "تهريب المخدرات",
    "crime organisé": "الجريمة المنظمة",
    "terrorisme": "الإرهاب",
    "accord de pêche": "اتفاقية الصيد البحري",
    "accord agricole": "الاتفاق الفلاحي",
    "sahara occidental": "الصحراء المغربية",
    "au maroc": "في المغرب",
    "le maroc": "المغرب",
    "maroc": "المغرب",
    "marocain": "مغربي",
    "marocaine": "مغربية",
    "marocains": "مغاربة",
    "france": "فرنسا",
    "paris": "باريس",
    "algérie": "الجزائر",
    "alger": "الجزائر",
    "espagne": "إسبانيا",
    "madrid": "مدريد",
    "rabat": "الرباط",

    # --- مصطلحات قضائية ومحاكم إسبانية ---
    "tribunal supremo": "المحكمة العليا",
    "audiencia nacional": "المحكمة الوطنية العليا",
    "tribunal constitucional": "المحكمة الدستورية",
    "tribunal de justicia de la unión europea": "محكمة العدل الأوروبية",
    "corte penal internacional": "المحكمة الجنائية الدولية",
    "tribunal superior de justicia": "المحكمة العليا للعدالة",
    "juzgado de instrucción": "محكمة التحقيق",
    "juez de instrucción": "قاضي التحقيق",
    "fiscalía general del estado": "الادعاء العام للدولة",
    "fiscalía general": "النيابة العامة",
    "fiscalía": "الادعاء العام",
    "orden de detención internacional": "مذكرة توقيف دولية",
    "orden de detención": "أمر ضبط وإحضار",
    "orden de extradición": "أمر بتسليم المطلوبين",
    "extradición a marruecos": "تسليم المطلوبين إلى المغرب",
    "extradición": "تسليم المطلوبين",
    "cooperación judicial": "التعاون القضائي",
    "prisión provisional": "الحبس الاحتياطي",
    "ingreso en prisión": "الإيداع بالسجن",
    "detenido": "توقيف مشتبه به",
    "detención": "عملية توقيف",
    "juicio oral": "جلسة محاكمة",
    "juicio": "محاكمة",
    "sentencia firme": "حكم قضائي نهائي",
    "sentencia": "حكم قضائي",
    "condena a": "إدانة بـ",
    "condenado": "مدان قضائياً",
    "absuelto": "تبرئة المتهم",
    "absolución": "حكم بالبراءة",
    "narcotráfico": "الاتجار بالمخدرات",
    "tráfico de drogas": "تهريب المخدرات",
    "blanqueo de capitales": "غسيل الأموال",
    "crimen organizado": "الجريمة المنظمة",
    "terrorismo": "الإرهاب",
    "acuerdo de pesca": "اتفاقية الصيد البحري",
    "acuerdo agrícola": "الاتفاق الفلاحي",
    "frontera sur": "الحدود الجنوبية",
    "ceuta y melilla": "سبتة ومليلية",
    "ceuta": "سبتة",
    "melilla": "مليلية",
    "en marruecos": "في المغرب",
    "marruecos": "المغرب",
    "marroquí": "مغربي",
    "marroquíes": "مغاربة",
    "españa": "إسبانيا",
    "madrid": "مدريد",

    # --- مصطلحات قضائية وإعلامية إنجليزية ---
    "supreme court": "المحكمة العليا",
    "court of justice": "محكمة العدل",
    "international court of justice": "محكمة العدل الدولية",
    "european court": "المحكمة الأوروبية",
    "criminal court": "المحكمة الجنائية",
    "federal court": "المحكمة الفيدرالية",
    "high court": "المحكمة العليا",
    "appeals court": "محكمة الاستئناف",
    "department of justice": "وزارة العدل",
    "justice department": "وزارة العدل",
    "attorney general": "المدعي العام",
    "prosecutor": "النيابة العامة",
    "extradition": "تسليم المطلوبين",
    "judicial cooperation": "التعاون القضائي",
    "judicial": "قضائي",
    "justice": "العدالة",
    "verdict": "حكم قضائي",
    "ruling": "قرار قضائي",
    "lawsuit": "دعوى قضائية",
    "indictment": "لائحة اتهام",
    "trial": "محاكمة",
    "human rights": "حقوق الإنسان",
    "western sahara": "الصحراء المغربية",
    "morocco": "المغرب",
    "moroccan": "مغربي",
    "rabat": "الرباط",
}

_TRANSLATION_CACHE = {}

def _is_predominantly_arabic(text: str) -> bool:
  if not text:
    return False
  ar_count = len(re.findall(r"[\u0600-\u06FF]", text))
  lat_count = len(re.findall(r"[A-Za-zÀ-ÿ]", text))
  if ar_count >= 12 and ar_count >= lat_count * 0.5:
    return True
  if ar_count >= 6 and lat_count < 6:
    return True
  return False


def translate_text_to_arabic_live(text: str, source_lang: str = "auto") -> str:
  """ترجمة فورية ودقيقة للنصوص والعناوين الأجنبية (الفرنسية، الإسبانية، الإنجليزية) إلى العربية الفصحى عبر 4 مسارات متتابعة."""
  txt = clean_display_text(text or "")
  if not txt or len(txt) < 3:
    return txt
  if _is_predominantly_arabic(txt):
    return txt

  cache_k = f"{source_lang}::{txt[:300]}"
  if cache_k in _TRANSLATION_CACHE:
    return _TRANSLATION_CACHE[cache_k]

  # 1) Google Translate POST (يتجاوز قيود طول الرابط GET)
  try:
    r_gt = requests.post(
        f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={urllib.parse.quote(source_lang)}&tl=ar&dt=t",
        data={"q": txt[:2000]},
        headers=DEFAULT_HEADERS,
        timeout=5.0,
    )
    if r_gt.status_code == 200:
      data_gt = r_gt.json()
      if isinstance(data_gt, list) and data_gt and isinstance(data_gt[0], list):
        translated_parts = [str(seg[0]) for seg in data_gt[0] if isinstance(seg, list) and seg and seg[0]]
        joined_ar = clean_display_text("".join(translated_parts))
        if joined_ar and len(re.findall(r"[\u0600-\u06FF]", joined_ar)) >= 4:
          _TRANSLATION_CACHE[cache_k] = joined_ar
          return joined_ar
  except Exception:
    pass

  # 2) Google Translate Chrome-Extension Endpoint (بديل موثوق)
  try:
    r_c5 = requests.get(
        f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl={urllib.parse.quote(source_lang)}&tl=ar&q={urllib.parse.quote(txt[:1200])}",
        headers=DEFAULT_HEADERS,
        timeout=4.5,
    )
    if r_c5.status_code == 200:
      d_c5 = r_c5.json()
      joined_c5 = ""
      if isinstance(d_c5, list):
        if d_c5 and isinstance(d_c5[0], list):
          joined_c5 = clean_display_text(str(d_c5[0][0]))
        elif d_c5 and isinstance(d_c5[0], str):
          joined_c5 = clean_display_text(" ".join(str(x) for x in d_c5))
      if joined_c5 and len(re.findall(r"[\u0600-\u06FF]", joined_c5)) >= 4:
        _TRANSLATION_CACHE[cache_k] = joined_c5
        return joined_c5
  except Exception:
    pass

  # 3) Free Translate API (ftapi.pythonanywhere.com)
  try:
    r_ft = requests.get(
        f"https://ftapi.pythonanywhere.com/translate?dl=ar&text={urllib.parse.quote(txt[:1000])}",
        headers=DEFAULT_HEADERS,
        timeout=4.5,
    )
    if r_ft.status_code == 200:
      d_ft = r_ft.json()
      ft_txt = clean_display_text(d_ft.get("destination-text") or "")
      if ft_txt and len(re.findall(r"[\u0600-\u06FF]", ft_txt)) >= 4:
        _TRANSLATION_CACHE[cache_k] = ft_txt
        return ft_txt
  except Exception:
    pass

  # 4) MyMemory Translation API
  try:
    sl_mm = source_lang if source_lang in ("fr", "es", "en") else "fr"
    if source_lang == "auto":
      low_t = txt.lower()
      if any(w in low_t for w in ("tribunal supremo", "audiencia nacional", "marruecos", "españa", "fiscalía", "sentencia", "detención", " del ", " los ", " las ")):
        sl_mm = "es"
      elif any(w in low_t for w in ("the ", "and ", "court ", "morocco", "with ", "from ", "justice ", "supreme ")):
        sl_mm = "en"
    mm_url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(txt[:480])}&langpair={sl_mm}|ar"
    r_mm = requests.get(mm_url, headers=DEFAULT_HEADERS, timeout=4.5)
    if r_mm.status_code == 200:
      mm_data = r_mm.json()
      mm_txt = clean_display_text((mm_data.get("responseData") or {}).get("translatedText") or "")
      if mm_txt and "MYMEMORY WARNING" not in mm_txt.upper() and len(re.findall(r"[\u0600-\u06FF]", mm_txt)) >= 4:
        _TRANSLATION_CACHE[cache_k] = mm_txt
        return mm_txt
  except Exception:
    pass

  return ""


def translate_foreign_title_to_arabic_rulebased(foreign_title: str) -> str:
  """ترجمة العنوان الأجنبي إلى العربية عبر محرك الترجمة الحي أولاً، ثم القاموس القضائي عند تعذر الاتصال."""
  if not foreign_title:
    return ""
  txt = clean_display_text(foreign_title)
  if _is_predominantly_arabic(txt):
    return txt

  # تنظيف اسم الجريدة الملحق بالعنوان قبل الترجمة
  txt_clean = re.sub(r"\s*[-|•–—]\s*(?:Le Monde|Le Figaro|El País|El Mundo|Libération|France 24|RFI|ABC|La Razón|El Confidencial|Echorouk|El Watan|Mediapart|Jeune Afrique|EFE|Europa Press).*$", "", txt, flags=re.IGNORECASE).strip()

  live_ar = translate_text_to_arabic_live(txt_clean or txt)
  if live_ar:
    return live_ar

  low = txt_clean.lower()
  matched_terms = []
  for term_raw, ar_term in sorted(COMPREHENSIVE_FR_ES_TRANSLATIONS.items(), key=lambda x: len(x[0]), reverse=True):
    if term_raw in low:
      matched_terms.append(ar_term)
      low = low.replace(term_raw, " ")
      if len(matched_terms) >= 3:
        break

  if matched_terms:
    main_action = matched_terms[0]
    sub_detail = (" بخصوص " + matched_terms[1]) if len(matched_terms) > 1 else ""
    third_detail = (" و" + matched_terms[2]) if len(matched_terms) > 2 else ""
    return f"{main_action}{sub_detail}{third_detail}"

  return txt



def _has_morocco_reference(text: str) -> bool:
  if not text:
    return False
  low = clean_display_text(text).lower()
  return any(
      m.lower() in low
      for m in (
          "المغرب", "مغربي", "مغربية", "مغاربة", "المغاربة", "المملكة المغربية", "الرباط",
          "maroc", "marocain", "marocaine", "marruecos", "marroquí", "morocco", "moroccan",
          "الصحراء", "sahara", "سبتة", "مليلية", "ceuta", "melilla", "كركرات", "guerguerat",
          "بيغاسوس", "pegasus", "المينورسو", "minurso", "اتفاقية الصيد", "accord de pêche",
      )
  )


def _extract_morocco_focused_sentences(raw_text: str) -> str:
  """استخراج الجمل من المتن الأصلي (الأجنبي أو العربي) التي تتحدث عن المغرب أولاً قبل ترجمتها وتلخيصها."""
  if not raw_text:
    return ""
  sents = [
      seg.strip()
      for seg in re.split(r"(?<=[.!؟\n])\s+", raw_text)
      if len(seg.strip()) > 15
  ]
  if not sents:
    return raw_text[:1200]
  ma_sents = [s for s in sents if _has_morocco_reference(s)]
  other_sents = [s for s in sents if s not in ma_sents]
  if ma_sents:
    return " ".join(ma_sents[:3] + other_sents[:1])[:1400]
  return " ".join(sents[:3])[:1200]


def _extract_morocco_focused_sentences_ar(translated_body: str, orig_text: str, is_international: bool = True) -> str:
  """استخلاص الجمل العربية التي تركز على صلة الخبر الدولي بالمغرب وتقديمها في صدارة الملخص."""
  if not translated_body:
    return ""
  sentences = [
      seg.strip()
      for seg in re.split(r"(?<=[.!؟\n])\s+", translated_body)
      if len(seg.strip()) > 16
  ]
  if not sentences:
    return translated_body[:450]

  ma_sents = [
      s for s in sentences
      if any(k in s for k in ("المغرب", "مغربي", "مغربية", "المغاربة", "الرباط", "الدار البيضاء", "الصحراء", "سبتة", "مليلية", "طنجة", "مراكش", "فاس", "أكادير", "العيون", "الداخلة"))
  ]
  other_sents = [s for s in sentences if s not in ma_sents]

  if ma_sents:
    ordered = ma_sents[:2] + other_sents[:1]
    res = " ".join(ordered)
  else:
    res = " ".join(sentences[:3])
    if is_international and _has_morocco_reference(orig_text) and not any(k in res for k in ("المغرب", "مغربي", "مغربية", "المغاربة")):
      res = f"فيما يتعلق بالمغرب: {res}"

  return res[:450] + ("..." if len(res) > 450 else "")


def translate_foreign_snippet_to_arabic_rulebased(snippet: str, title: str, source_name: str, is_international: bool = True) -> str:
  """ترجمة متن الخبر الأجنبي إلى العربية الفصحى مع إعطاء الأولوية للجمل التي تتطرق للمغرب."""
  s_clean = clean_display_text(snippet or "")
  t_clean = clean_display_text(title or "")
  prioritized_source = _extract_morocco_focused_sentences(s_clean) if len(s_clean) > len(t_clean) + 10 else f"{t_clean}. {s_clean}".strip(". ")

  live_body_ar = translate_text_to_arabic_live(prioritized_source[:1500])
  if live_body_ar and len(live_body_ar) >= 20 and _is_predominantly_arabic(live_body_ar):
    return _extract_morocco_focused_sentences_ar(live_body_ar, f"{t_clean} {s_clean}", is_international=is_international)

  t_ar = translate_foreign_title_to_arabic_rulebased(t_clean)
  if t_ar and _is_predominantly_arabic(t_ar):
    if is_international and _has_morocco_reference(f"{t_clean} {s_clean}") and not any(k in t_ar for k in ("المغرب", "مغربي", "مغربية")):
      return f"يتناول الخبر ما يتعلق بالمغرب بخصوص: {t_ar}."
    return f"{t_ar}."
  return t_ar or s_clean[:420] or t_clean


def build_extractive_arabic_summary(
    title: str, snippet: str, platform: str, source_name: str
) -> str:
  t_clean = clean_display_text(title)
  s_clean = clean_display_text(snippet)
  is_intl = (platform == "صحافة دولية")

  # إذا كان المتن بلغة أجنبية، نترجم المتن الفعلي للخبر نفسه مع التركيز على الجمل المتعلقة بالمغرب
  if s_clean and not _is_predominantly_arabic(s_clean):
    translated_body = translate_foreign_snippet_to_arabic_rulebased(s_clean, t_clean, source_name or platform, is_international=is_intl)
    if translated_body and _is_predominantly_arabic(translated_body):
      return translated_body

  if not _is_predominantly_arabic(f"{t_clean} {s_clean}"):
    return translate_foreign_snippet_to_arabic_rulebased(s_clean, t_clean, source_name or platform, is_international=is_intl)

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

  if s_clean and len(s_clean) >= 35 and s_clean.lower() != t_clean.lower():
    sentences = [
        seg.strip()
        for seg in re.split(r"(?<=[.!؟\n])\s+", s_clean)
        if len(seg.strip()) > 20 and seg.strip() != t_clean
    ]
    if sentences:
      if is_intl and _has_morocco_reference(f"{t_clean} {s_clean}"):
        return _extract_morocco_focused_sentences_ar(" ".join(sentences), f"{t_clean} {s_clean}", is_international=True)
      summary_txt = " ".join(sentences[:3])
      return summary_txt[:450] + ("..." if len(summary_txt) > 450 else "")
    return s_clean[:450] + ("..." if len(s_clean) > 450 else "")

  return s_clean or t_clean


def get_fallback_thumbnail_data_uri(platform: str, source_name: str = "") -> str:
  themes = {
      "الصحف": ("#064e3b", "#10b981", "PRESS", "⚖️ صحافة قضائية"),
      "صحافة دولية": ("#0c4a6e", "#38bdf8", "INTL PRESS", "🌍 صحافة دولية"),
      "فيسبوك": ("#1e3a8a", "#3b82f6", "FACEBOOK", "🟦 منشور فيسبوك"),
      "إكس": ("#0f172a", "#94a3b8", "X / TWITTER", "⬛ تغريدة إكس"),
      "يوتيوب": ("#7f1d1d", "#ef4444", "YOUTUBE", "🟥 فيديو يوتيوب"),
      "أخرى": ("#4c1d95", "#a855f7", "SOCIAL", "🟪 تواصل اجتماعي"),
  }
  bg1, accent, en_lbl, ar_lbl = themes.get(
      platform, ("#0f172a", "#38bdf8", "JUSTICE", "⚖️ رصد قضائي")
  )
  src_short = html.escape(clean_display_text(source_name or platform)[:18])
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
      f"<text x='160' y='148' text-anchor='middle' fill='#cbd5e1' font-family='Cairo, sans-serif' font-size='14' font-weight='700'>{src_short}</text>"
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
    m_img = re.search(
        r'<img[^>]+src=["\'](https?://[^"\'>\s]+)["\']',
        str(raw_html_desc),
        re.IGNORECASE,
    )
    if m_img:
      img_u = html.unescape(m_img.group(1).strip())
      if not any(
          skip in img_u.lower()
          for skip in [
              "1x1",
              "pixel",
              "tracker",
              "blank.gif",
              "googleusercontent.com/J6_coFbogxhRI9iM864NL_liGXvsQp2AupsKei7z0cNNfDvGUmWUy20nuUhkREQyrpY4bEeIBuc",
          ]
      ):
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
      "active_scan": None,
      "daemon_started": False,
      "bg_scanning": False,
      "last_done_mode": None,
      "last_done_count": 0,
      "last_done_ts": 0.0,
  }


if st is not None and hasattr(st, "cache_resource"):
  get_shared_runtime = st.cache_resource(_create_shared_runtime)
else:
  _FALLBACK_RUNTIME = _create_shared_runtime()

  def get_shared_runtime():
    return _FALLBACK_RUNTIME


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
  try:
    rt = get_shared_runtime()
    rt["stop_requested"] = False
  except Exception:
    pass
  try:
    if st is not None:
      st.session_state["stop_scan"] = False
  except Exception:
    pass


def is_stop_requested() -> bool:
  try:
    if get_shared_runtime().get("stop_requested", False):
      return True
  except Exception:
    pass
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
    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=FILE;")
    conn.execute("PRAGMA cache_size=-1500;")
    conn.execute("PRAGMA mmap_size=0;")
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


def load_custom_targets():
  default_targets = []
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
        return cleaned
    except Exception:
      pass
  return default_targets


def purge_invalid_articles_from_db():
  lock = get_db_lock()
  current_targets = load_custom_targets()
  with lock:
    removed_any = False
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute(
          "SELECT id, title, summary, source_name, platform, raw_snippet, url, is_custom_target FROM articles"
      )
      rows = c.fetchall()
      bad_ids = []
      for r in rows:
        d = dict(r)
        is_tgt = bool(d.get("is_custom_target"))
        snip = f"{d.get('summary') or ''} {d.get('raw_snippet') or ''}"
        is_intl_row = (d.get("platform") == "صحافة دولية")
        if not is_strictly_judicial_and_clean(
            d.get("title") or "", snip, d.get("url") or "", "", is_target=is_tgt, is_international=is_intl_row
        ):
          bad_ids.append((d["id"],))
        elif is_tgt and not belongs_to_any_custom_target(d, current_targets):
          bad_ids.append((d["id"],))
      if bad_ids:
        c.executemany("DELETE FROM articles WHERE id = ?", bad_ids)
        conn.commit()
        removed_any = True
      conn.close()
    except Exception:
      pass

    if os.path.exists(ARCHIVE_JSON_FILE):
      try:
        with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
          arch_data = json.load(f)
        if isinstance(arch_data, list):
          cleaned_arch = []
          for item in arch_data:
            if not isinstance(item, dict):
              continue
            is_tgt = bool(item.get("is_custom_target", 0))
            if not is_strictly_judicial_and_clean(
                item.get("title", ""),
                f"{item.get('summary', '')} {item.get('raw_snippet', '')}",
                item.get("url", ""),
                "",
                is_target=is_tgt,
            ):
              continue
            if is_tgt and not belongs_to_any_custom_target(
                item, current_targets
            ):
              continue
            cleaned_arch.append(item)
          if len(cleaned_arch) != len(arch_data):
            with open(ARCHIVE_JSON_FILE, "w", encoding="utf-8") as f:
              json.dump(cleaned_arch, f, ensure_ascii=False, indent=2)
            removed_any = True
      except Exception:
        pass

    if removed_any and os.path.exists(DB_FILE):
      try:
        shutil.copyfile(DB_FILE, REPO_DB_FILE)
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
  """إزالة أي أخبار مكررة من قاعدة البيانات والأرشيف مع الحفاظ على أقدم وقت رصد (created_at) لببقائها 24 ساعة ثم إحالتها للأرشيف، وتغذية سجل تلغرام."""
  lock = get_db_lock()
  with lock:
    ledger = load_telegram_sent_ledger()
    ledger_changed = False
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute("SELECT * FROM articles ORDER BY created_at ASC, id ASC")
      rows = [dict(r) for r in c.fetchall()]
      seen_keys = set()
      dup_ids = []
      for r in rows:
        item_keys = compute_article_dedup_keys(r.get("title", ""), r.get("url", ""))
        # جميع الأخبار المرصودة سابقاً في القاعدة تُسجل في سجل تلغرام حتى لا يُعاد إرسالها عند تشغيل الرصد التلقائي
        if not item_keys.issubset(ledger):
          ledger.update(item_keys)
          ledger_changed = True
        if item_keys & seen_keys:
          dup_ids.append((r["id"],))
        else:
          seen_keys.update(item_keys)
      if dup_ids:
        c.executemany("DELETE FROM articles WHERE id = ?", dup_ids)
        conn.commit()
      c.execute("UPDATE articles SET telegram_sent = 1 WHERE telegram_sent IS NULL OR telegram_sent = 0")
      conn.commit()
      conn.close()
    except Exception:
      pass

    if os.path.exists(ARCHIVE_JSON_FILE):
      try:
        with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
          arch_list = json.load(f)
        if isinstance(arch_list, list):
          # نرتب من الأقدم في الرصد إلى الأحدث للحفاظ على أول رصد، ثم نعيد الترتيب حسب النشر
          arch_sorted = sorted(arch_list, key=lambda x: float(x.get("created_at") or x.get("pub_timestamp") or 0))
          seen_arch_keys = set()
          deduped_arch = []
          for item in arch_sorted:
            if not isinstance(item, dict):
              continue
            ik = compute_article_dedup_keys(item.get("title", ""), item.get("url", ""))
            if not ik.issubset(ledger):
              ledger.update(ik)
              ledger_changed = True
            if ik & seen_arch_keys:
              continue
            seen_arch_keys.update(ik)
            item["telegram_sent"] = 1
            deduped_arch.append(item)
          deduped_arch.sort(key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True)
          if len(deduped_arch) != len(arch_list):
            with open(ARCHIVE_JSON_FILE, "w", encoding="utf-8") as f:
              json.dump(deduped_arch, f, ensure_ascii=False, indent=2)
      except Exception:
        pass

    if ledger_changed or not os.path.exists(TELEGRAM_LEDGER_FILE):
      save_telegram_sent_ledger(ledger)


def init_db(force: bool = False):
  rt = get_shared_runtime()
  if not force and rt.get("_db_initialized_once"):
    return
  lock = get_db_lock()
  with lock:
    if (
        not os.path.exists(DB_FILE)
        and os.path.exists(REPO_DB_FILE)
        and os.path.getsize(REPO_DB_FILE) > 0
    ):
      try:
        shutil.copyfile(REPO_DB_FILE, DB_FILE)
      except Exception:
        pass

    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.close()
    except sqlite3.DatabaseError:
      try:
        if os.path.exists(DB_FILE):
          os.remove(DB_FILE)
        conn = _open_sqlite_conn()
        _ensure_schema_on_conn(conn)
        conn.close()
      except Exception:
        pass
    except Exception:
      pass
    restore_db_from_json_if_needed()
    purge_invalid_articles_from_db()
    deduplicate_and_seed_telegram_ledger()
    rt["_db_initialized_once"] = True


def sync_db_to_json(extra_items: list = None):
  invalidate_articles_cache()
  lock = get_db_lock()
  current_targets = load_custom_targets()
  with lock:
    merged_by_url = {}
    if os.path.exists(ARCHIVE_JSON_FILE):
      try:
        with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
          existing_json = json.load(f)
        if isinstance(existing_json, list):
          for item in existing_json:
            if not isinstance(item, dict) or not item.get("url"):
              continue
            is_tgt = bool(item.get("is_custom_target", 0))
            if not is_strictly_judicial_and_clean(
                item.get("title", ""),
                f"{item.get('summary', '')} {item.get('raw_snippet', '')}",
                item.get("url", ""),
                "",
                is_target=is_tgt,
            ):
              continue
            if is_tgt and not belongs_to_any_custom_target(
                item, current_targets
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
          "FROM articles ORDER BY pub_timestamp DESC LIMIT 1500"
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
      )[:1500]
      try:
        tmp_file = f"{ARCHIVE_JSON_FILE}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
          json.dump(sorted_rows, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, ARCHIVE_JSON_FILE)
      except Exception:
        pass

    if os.path.exists(DB_FILE):
      try:
        shutil.copyfile(DB_FILE, REPO_DB_FILE)
      except Exception:
        pass


def restore_db_from_json_if_needed():
  if not os.path.exists(ARCHIVE_JSON_FILE):
    return
  lock = get_db_lock()
  current_targets = load_custom_targets()
  with lock:
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      c = conn.cursor()
      c.execute("SELECT COUNT(*) FROM articles")
      count = c.fetchone()[0]
      if count == 0:
        with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
          items = json.load(f)
        if isinstance(items, list) and items:
          for item in items:
            try:
              t_clean = clean_display_text(item.get("title", ""))
              s_clean = clean_display_text(item.get("summary", ""))
              plat = item.get("platform", "الصحف")
              src = clean_display_text(item.get("source_name", "") or plat)
              raw_s = clean_display_text(item.get("raw_snippet", ""))
              u_str = item.get("url", "")
              is_tgt = int(item.get("is_custom_target", 0))
              if not is_strictly_judicial_and_clean(
                  t_clean,
                  f"{s_clean} {raw_s}",
                  u_str,
                  "",
                  is_target=bool(is_tgt),
              ):
                continue
              if is_tgt and not belongs_to_any_custom_target(
                  item, current_targets
              ):
                continue

              if is_summary_just_title(t_clean, s_clean):
                s_clean = build_extractive_arabic_summary(
                    t_clean, raw_s, plat, src
                )
              pub_ts = float(item.get("pub_timestamp", time.time() - 3600))
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
                                    image_url, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                      float(item.get("created_at", time.time())),
                  ),
              )
            except Exception:
              continue
          conn.commit()
      conn.close()
    except Exception:
      pass


def invalidate_articles_cache():
  try:
    rt = get_shared_runtime()
    rt["_articles_cache_ts"] = 0
    rt["_articles_cache_data"] = None
  except Exception:
    pass


def fetch_articles_from_db(use_cache: bool = True):
  try:
    rt = get_shared_runtime()
    if (
        use_cache
        and rt.get("_articles_cache_data") is not None
        and (time.time() - float(rt.get("_articles_cache_ts", 0))) < 20.0
    ):
      return list(rt["_articles_cache_data"])
  except Exception:
    rt = None
  lock = get_db_lock()
  current_targets = load_custom_targets()
  with lock:
    db_rows = []
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute(
          "SELECT * FROM articles ORDER BY pub_timestamp DESC, id DESC LIMIT"
          " 1500"
      )
      for r in c.fetchall():
        d = dict(r)
        is_tgt = bool(d.get("is_custom_target", 0))
        if d.get("category") != "رصد حر بالويب" and not is_strictly_judicial_and_clean(
            d.get("title", ""),
            f"{d.get('summary', '')} {d.get('raw_snippet', '')}",
            d.get("url", ""),
            "",
            is_target=is_tgt,
            is_international=(d.get("platform") == "صحافة دولية"),
        ):
          continue
        if is_tgt and not belongs_to_any_custom_target(d, current_targets):
          continue
        db_rows.append(d)
      conn.close()
    except Exception:
      pass

    if db_rows:
      unique_rows = []
      seen_display_keys = set()
      for r in db_rows:
        dk = compute_article_dedup_keys(r.get("title", ""), r.get("url", ""))
        if dk & seen_display_keys:
          continue
        seen_display_keys.update(dk)
        unique_rows.append(r)
      if rt is not None:
        rt["_articles_cache_data"] = unique_rows
        rt["_articles_cache_ts"] = time.time()
      return list(unique_rows)

    if os.path.exists(ARCHIVE_JSON_FILE):
      try:
        with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
          data = json.load(f)
        if isinstance(data, list):
          valid_data = []
          for d in data:
            if not isinstance(d, dict):
              continue
            is_tgt = bool(d.get("is_custom_target", 0))
            if not is_strictly_judicial_and_clean(
                d.get("title", ""),
                f"{d.get('summary', '')} {d.get('raw_snippet', '')}",
                d.get("url", ""),
                "",
                is_target=is_tgt,
            ):
              continue
            if is_tgt and not belongs_to_any_custom_target(d, current_targets):
              continue
            valid_data.append(d)
          return sorted(
              valid_data,
              key=lambda x: float(x.get("pub_timestamp", 0)),
              reverse=True,
          )
      except Exception:
        pass
    return []


# =====================================================================
# 6. إدارة الإعدادات والروابط المخصصة وحالة الرصد الدوري وفترة البحث
# =====================================================================
def load_credentials():
  cfg = {
      "gemini_api_key": DEFAULT_GEMINI_API_KEY,
      "telegram_bot_token": DEFAULT_TG_TOKEN,
      "telegram_chat_id": DEFAULT_TG_CHAT_ID,
      "keywords_input": "",
      "search_period": "آخر 7 أيام",
      "auto_monitor": True,
      "monitor_interval": "كل ساعة",
      "admin_pin": DEFAULT_ADMIN_PIN,
      "daily_report_enabled": True,
      "daily_report_hour": 21,
  }
  if os.path.exists(CREDENTIALS_FILE):
    try:
      with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        saved = json.load(f)
      if isinstance(saved, dict):
        cfg.update(saved)
    except Exception:
      pass

  try:
    if st is not None and hasattr(st, "secrets"):
      if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"]:
        cfg["gemini_api_key"] = str(st.secrets["GEMINI_API_KEY"]).strip()
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

  env_gemini = os.environ.get("GEMINI_API_KEY", "").strip()
  if env_gemini:
    cfg["gemini_api_key"] = env_gemini
  env_tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
  if env_tg_token:
    cfg["telegram_bot_token"] = env_tg_token
  env_tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
  if env_tg_chat:
    cfg["telegram_chat_id"] = env_tg_chat

  if not cfg.get("gemini_api_key"):
    cfg["gemini_api_key"] = DEFAULT_GEMINI_API_KEY
  if not cfg.get("telegram_bot_token"):
    cfg["telegram_bot_token"] = DEFAULT_TG_TOKEN
  if not cfg.get("telegram_chat_id"):
    cfg["telegram_chat_id"] = DEFAULT_TG_CHAT_ID
  if cfg.get("monitor_interval") not in INTERVAL_MAP:
    cfg["monitor_interval"] = "كل ساعة"
  if cfg.get("search_period") not in SEARCH_PERIOD_MAP:
    cfg["search_period"] = "آخر 7 أيام"
  if not str(cfg.get("admin_pin") or "").strip():
    cfg["admin_pin"] = DEFAULT_ADMIN_PIN
  return cfg


def save_credentials(cfg):
  try:
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
    with open(CUSTOM_TARGETS_FILE, "w", encoding="utf-8") as f:
      json.dump(cleaned, f, ensure_ascii=False, indent=2)
    purge_invalid_articles_from_db()
  except Exception:
    pass


def load_monitor_state():
  state = {"last_auto_run": 0.0, "last_auto_added": 0, "total_auto_cycles": 0}
  if os.path.exists(MONITOR_STATE_FILE):
    try:
      with open(MONITOR_STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
      if isinstance(data, dict):
        state.update(data)
    except Exception:
      pass
  return state


def save_monitor_state(state):
  try:
    with open(MONITOR_STATE_FILE, "w", encoding="utf-8") as f:
      json.dump(state, f, ensure_ascii=False, indent=2)
  except Exception:
    pass


# =====================================================================
# 7. استخراج ومعالجة تواريخ النشر الحقيقية وتاريخ الرصد
# =====================================================================
def extract_date_from_url_or_text(
    url: str,
    text_snippet: str = "",
    raw_date: str = "",
    fallback_offset_sec: int = 3600,
):
  now_ts = time.time()

  if raw_date and str(raw_date).strip():
    d_str, d_ts = parse_any_date(str(raw_date).strip(), fallback_offset_sec=0)
    if d_ts > 0 and abs(now_ts - d_ts) > 5:
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

    m_url_date = re.search(r"/(20\d{2})/(\d{1,2})/(\d{1,2})/", url)
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
    return parse_any_date(
        text_snippet[:240], fallback_offset_sec=fallback_offset_sec
    )

  return parse_any_date("", fallback_offset_sec=fallback_offset_sec)


def parse_any_date(date_str: str, fallback_offset_sec: int = 3600):
  now_ts = time.time()
  if not date_str or not str(date_str).strip():
    ts = now_ts - fallback_offset_sec
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M"), ts

  raw = str(date_str).strip()

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
    dt = parsedate_to_datetime(raw)
    if dt.tzinfo is None:
      dt = dt.replace(tzinfo=timezone.utc)
    ts = min(dt.timestamp(), now_ts)
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        ts,
    )
  except Exception:
    pass

  # 3) صيغ ISO 8601 (مثل YouTube Atom XML: 2026-10-13T18:30:00+00:00)
  try:
    iso_clean = raw.replace("Z", "+00:00")
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

  # 4) التواريخ الصريحة بالشهور العربية (مثل: 17 يوليوز 2026)
  for ar_m, m_idx in ARABIC_MONTHS.items():
    m_ar = re.search(rf"(\d{{1,2}})\s+{ar_m}\s*,?\s*(20\d{{2}})", raw)
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

  # 5) التواريخ الصريحة بالشهور الإنجليزية/الفرنسية (مثل: Oct 2, 2026 أو July 03 2026)
  for en_m, m_idx in ENGLISH_MONTHS.items():
    m_en1 = re.search(
        rf"\b{en_m}[a-z]*\s+(\d{{1,2}}),?\s+(20\d{{2}})", rel_lower
    )
    m_en2 = re.search(
        rf"\b(\d{{1,2}})\s+{en_m}[a-z]*,?\s+(20\d{{2}})", rel_lower
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

  # 6) التواريخ الرقمية الصريحة YYYY-MM-DD أو DD-MM-YYYY
  m_ymd = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", raw)
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

  m_dmy = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b", raw)
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

  # 7) صيغ الوقت النسبي الإنجليزية الصريحة (مثل: 5d · أو 3 days ago أو 18h ago)
  m_short_rel = re.search(
      r"(?:^|\b)(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|wk|wks|week|weeks|mo|month|months|y|yr|yrs|year|years)\b(?:\s*ago|\s*·)?",
      rel_lower,
  )
  if m_short_rel and (
      "ago" in rel_lower
      or "·" in rel_lower[:25]
      or len(raw) <= 28
  ):
    n = int(m_short_rel.group(1))
    u = m_short_rel.group(2)
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

  # 8) صيغ الوقت النسبي العربية الصريحة فقط (مسبوقة بـ "منذ" أو "قبل" أو نص قصير مثل "قبل 3 ساعات" حتى لا تلتبس مع كلمات مثل "النيابة العامة" أو "اليوم")
  m_ar_rel = re.search(
      r"(?:منذ|قبل)\s*(?:حوالي\s*|أكثر من\s*|أقل من\s*)?(?:(\d+)\s*)?(ثانية|ثواني|دقيقة|دقائق|دقيقتين|ساعة|ساعات|ساعتين|يوم|أيام|يومين|أسبوع|أسابيع|اسبوع|أسبوعين|شهر|أشهر|شهور|شهرين|سنة|سنوات|عام|أعوام|سنتين|عامين|لحظات)\b",
      rel_lower,
  )
  if not m_ar_rel and len(raw) <= 26:
    m_ar_rel = re.search(
        r"^(?:(\d+)\s*)?(ثانية|ثواني|دقيقة|دقائق|دقيقتين|ساعة|ساعات|ساعتين|يوم|أيام|يومين|أسبوع|أسابيع|اسبوع|أسبوعين|شهر|أشهر|شهور|شهرين|سنة|سنوات|عام|أعوام|سنتين|عامين|أمس|الآن)\b",
        rel_lower,
    )
  if m_ar_rel:
    num = int(m_ar_rel.group(1)) if m_ar_rel.group(1) else 1
    unit_ar = m_ar_rel.group(2)
    if unit_ar in ("ثانية", "ثواني", "لحظات", "الآن"):
      ts = now_ts - 60
    elif unit_ar in ("دقيقة", "دقائق", "دقيقتين"):
      if unit_ar == "دقيقتين":
        num = 2
      ts = now_ts - (num * 60)
    elif unit_ar in ("ساعة", "ساعات", "ساعتين"):
      if unit_ar == "ساعتين":
        num = 2
      ts = now_ts - (num * 3600)
    elif unit_ar in ("يوم", "أيام", "يومين", "أمس"):
      if unit_ar == "يومين":
        num = 2
      elif unit_ar == "أمس":
        num = 1
      ts = now_ts - (num * 86400)
    elif unit_ar in ("أسبوع", "أسابيع", "اسبوع", "أسبوعين"):
      if unit_ar == "أسبوعين":
        num = 2
      ts = now_ts - (num * 7 * 86400)
    elif unit_ar in ("شهر", "أشهر", "شهور", "شهرين"):
      if unit_ar == "شهرين":
        num = 2
      ts = now_ts - (num * 30 * 86400)
    else:
      if unit_ar in ("سنتين", "عامين"):
        num = 2
      ts = now_ts - (num * 365 * 86400)
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        ts,
    )

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
  return f"منذ {diff // 86400} يوم"


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
      if "المغرب" not in kw:
        queries.append(f"{kw} القضاء المغرب")
      else:
        queries.append(kw)
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
    title = clean_html_text(item.findtext("title") or "")
    link = clean_social_post_url((item.findtext("link") or "").strip())
    raw_desc_html = item.findtext("description") or ""
    raw_content_encoded = (
        item.findtext("content:encoded", default="", namespaces=ns) or ""
    )
    full_raw_html = f"{raw_content_encoded} {raw_desc_html}"
    desc = clean_html_text(full_raw_html)

    pub_raw = (
        item.findtext("pubDate")
        or item.findtext("{http://purl.org/dc/elements/1.1/}date")
        or ""
    )
    source_el = item.find("source")
    source_name = (
        clean_html_text(source_el.text)
        if source_el is not None and source_el.text
        else default_source
    )
    if not source_name and " - " in title:
      parts = title.rsplit(" - ", 1)
      if len(parts[1]) < 35:
        title, source_name = parts[0].strip(), parts[1].strip()

    if not title or not link:
      continue

    img_url = ""
    for m_tag in ["media:content", "media:thumbnail", "enclosure"]:
      el = item.find(m_tag, ns) if ":" in m_tag else item.find(m_tag)
      if el is not None and el.attrib.get("url"):
        img_url = el.attrib["url"].strip()
        break
    if not img_url:
      for child in item:
        if (
            child.tag.lower().endswith("image")
            and child.text
            and child.text.strip().startswith("http")
        ):
          img_url = child.text.strip()
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

    results.append({
        "title": title,
        "url": link,
        "raw_snippet": desc[:1800] if desc else title,
        "source_name": source_name or default_platform,
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
        thumb_el.attrib.get("url", "").strip()
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

    results.append({
        "title": title,
        "url": link,
        "raw_snippet": snippet_txt[:1800],
        "source_name": clean_html_text(
            author_name or default_source or default_platform
        ),
        "platform": default_platform,
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": img_url,
    })

  return results



# =====================================================================
# محرك الرصد الفوري المباشر من خوادم الناشرين (بدون انتظار أرشفة Google News)
# WordPress REST API + Live No-Cache RSS/Atom + News Sitemaps + Parallel Workers
# =====================================================================
LIVE_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "ar,fr-FR;q=0.9,fr;q=0.8,en-US;q=0.7,en;q=0.6",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

try:
  import cloudscraper as _cloudscraper_mod
except Exception:
  _cloudscraper_mod = None


def _direct_http_get(url: str, timeout: float = 6.0):
  """جلب مباشر من خادم الناشر مع تجاوز ذكي لقيود User-Agent / www وتجربة cloudscraper عند حظر 403/503."""
  try:
    r = requests.get(url, headers=LIVE_FETCH_HEADERS, timeout=timeout, allow_redirects=True)
    if r.status_code == 200 and r.content:
      return r
    if r.status_code in (403, 503, 429) and _cloudscraper_mod is not None:
      try:
        sc = _cloudscraper_mod.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
        r_cs = sc.get(url, timeout=timeout + 2.0)
        if r_cs.status_code == 200 and r_cs.content:
          return r_cs
      except Exception:
        pass
    # تجربة تبديل www. عند فشل الاستجابة
    p_u = urllib.parse.urlparse(url)
    if p_u.netloc and r.status_code in (403, 404, 500, 502, 503):
      alt_netloc = p_u.netloc[4:] if p_u.netloc.startswith("www.") else f"www.{p_u.netloc}"
      alt_url = urllib.parse.urlunparse((p_u.scheme, alt_netloc, p_u.path, p_u.params, p_u.query, p_u.fragment))
      r_alt = requests.get(alt_url, headers=LIVE_FETCH_HEADERS, timeout=timeout, allow_redirects=True)
      if r_alt.status_code == 200 and r_alt.content:
        return r_alt
    return r
  except Exception:
    return None


def parse_news_sitemap_xml(
    xml_bytes: bytes,
    default_platform: str,
    default_source: str = "",
    max_age_sec: int = 0,
) -> list:
  """قراءة خرائط الأخبار المباشرة (Google News Sitemap XML) التي يحدّثها الناشر فور النشر بالثانية."""
  results = []
  try:
    root = ET.fromstring(xml_bytes)
  except Exception:
    return results
  now_ts = time.time()
  for url_el in root.findall(".//{*}url"):
    loc = ""
    title = ""
    pub_raw = ""
    for child in url_el:
      tag_low = child.tag.lower()
      if tag_low.endswith("loc") and child.text:
        loc = child.text.strip()
      elif tag_low.endswith("lastmod") and child.text and not pub_raw:
        pub_raw = child.text.strip()
      elif tag_low.endswith("news"):
        for n_child in child:
          nt = n_child.tag.lower()
          if nt.endswith("title") and n_child.text:
            title = clean_html_text(n_child.text)
          elif nt.endswith("publication_date") and n_child.text:
            pub_raw = n_child.text.strip()
    if not loc or not title:
      continue
    pub_str, pub_ts = extract_date_from_url_or_text(loc, title, pub_raw, fallback_offset_sec=9999999)
    if max_age_sec > 0 and (now_ts - pub_ts) > max_age_sec:
      continue
    results.append({
        "title": title,
        "url": clean_social_post_url(loc),
        "raw_snippet": title,
        "source_name": default_source or default_platform,
        "platform": default_platform,
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": "",
    })
  return results


def _get_site_origin(site_info: dict) -> str:
  """استخراج النطاق الفرعي الدقيق للموقع (مثل https://ar.hibapress.com أو https://www.hespress.com)."""
  for k in ("live_url", "rss", "sitemap"):
    u = str(site_info.get(k) or "").strip()
    if u.startswith("http"):
      p_u = urllib.parse.urlparse(u)
      if p_u.netloc:
        return f"{p_u.scheme}://{p_u.netloc}"
  dom = str(site_info.get("domain") or "").strip()
  return f"https://{dom}" if dom else ""


def fetch_wp_rest_posts(
    domain_or_origin: str,
    source_name: str,
    default_platform: str = "الصحف",
    keyword: str = "",
    max_age_sec: int = 0,
    per_page: int = 30,
) -> list:
  """جلب المقالات مباشرة من واجهة WordPress REST API الخاصة بالموقع لحظة نشرها الفعلي مع توقيت GMT الدقيق."""
  results = []
  now_ts = time.time()
  origin = domain_or_origin.rstrip("/") if domain_or_origin.startswith("http") else f"https://{domain_or_origin}"
  params = [f"per_page={per_page}", "orderby=date", "order=desc", "_fields=link,title,excerpt,date_gmt,date,jetpack_featured_media_url"]
  if keyword and keyword.strip():
    params.append(f"search={urllib.parse.quote(keyword.strip())}")
  if max_age_sec > 0:
    after_iso = datetime.fromtimestamp(now_ts - max_age_sec, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    params.append(f"after={urllib.parse.quote(after_iso)}")
  api_url = f"{origin}/wp-json/wp/v2/posts?{'&'.join(params)}"
  try:
    r = _direct_http_get(api_url, timeout=6.0)
    if r is None or r.status_code != 200:
      return results
    data = r.json()
    if not isinstance(data, list):
      return results
    for post in data:
      if not isinstance(post, dict):
        continue
      link = clean_social_post_url(str(post.get("link") or "").strip())
      raw_t = (post.get("title") or {}).get("rendered", "") if isinstance(post.get("title"), dict) else str(post.get("title") or "")
      raw_ex = (post.get("excerpt") or {}).get("rendered", "") if isinstance(post.get("excerpt"), dict) else str(post.get("excerpt") or "")
      title = clean_html_text(raw_t)
      desc = clean_html_text(raw_ex) or title
      if not link or not title:
        continue
      date_raw = str(post.get("date_gmt") or post.get("date") or "").strip()
      pub_str, pub_ts = extract_date_from_url_or_text(link, desc, date_raw, fallback_offset_sec=1800)
      if max_age_sec > 0 and (now_ts - pub_ts) > max_age_sec:
        continue
      img_u = str(post.get("jetpack_featured_media_url") or "").strip()
      results.append({
          "title": title,
          "url": link,
          "raw_snippet": desc[:1800],
          "source_name": source_name,
          "platform": default_platform,
          "pub_date": pub_str,
          "pub_timestamp": pub_ts,
          "image_url": img_u,
      })
  except Exception:
    pass
  return results


def _fetch_single_publisher_live(
    site_info: dict,
    default_platform: str,
    max_age_sec: int,
    keyword: str = "",
) -> list:
  """فحص ناشر واحد مباشرة عبر WP REST API (العام + البحث القضائي المباشر) + RSS الحي + News Sitemap + الصفحة الحية بدون المرور بمحركات الأرشفة."""
  collected = []
  seen_u = set()
  domain = site_info.get("domain", "")
  name = site_info.get("name", domain)
  origin = _get_site_origin(site_info)

  # 1) واجهة WordPress REST API المباشرة على نفس خادم الجريدة (المقالات الأحدث + البحث الداخلي الفوري في الجريدة)
  if site_info.get("wp") and origin:
    search_terms = [keyword.strip()] if (keyword and keyword.strip()) else (["", "القضاء", "المحكمة"] if default_platform == "الصحف" else [""])
    for sterm in search_terms:
      per_p = 35 if not sterm else 12
      for item in fetch_wp_rest_posts(origin, name, default_platform, keyword=sterm, max_age_sec=max_age_sec, per_page=per_p):
        if item["url"] not in seen_u:
          seen_u.add(item["url"])
          collected.append(item)

  # 2) خلاصة RSS / Atom الحية مباشرة من خادم الناشر (+ خلاصة البحث المباشر على الموقع للمواقع المغربية)
  rss_u = site_info.get("rss", "")
  rss_urls_to_try = []
  if rss_u:
    rss_urls_to_try.append(rss_u)
  if origin:
    for candidate_r in (f"{origin}/feed/", f"{origin}/rss.xml"):
      if candidate_r not in rss_urls_to_try and not rss_u:
        rss_urls_to_try.append(candidate_r)
  if default_platform == "الصحف" and site_info.get("wp") and origin:
    q_s = keyword.strip() if (keyword and keyword.strip()) else "القضاء"
    rss_urls_to_try.append(f"{origin}/?s={urllib.parse.quote(q_s)}&feed=rss2")

  if rss_urls_to_try and (not collected or (default_platform == "الصحف" and len(collected) < 12)):
    for r_target in rss_urls_to_try:
      try:
        rf = _direct_http_get(r_target, timeout=6.0)
        if rf is not None and rf.status_code == 200 and (b"<rss" in rf.content or b"<feed" in rf.content or b"<rdf" in rf.content or b"<item" in rf.content):
          for entry in parse_rss_xml(rf.content, default_platform, default_source=name, fallback_offset=1800, max_age_sec=max_age_sec):
            if entry["url"] not in seen_u:
              seen_u.add(entry["url"])
              entry["source_name"] = name
              collected.append(entry)
      except Exception:
        pass

  # 3) خريطة الأخبار الفورية (News Sitemap) مباشرة من خادم الناشر
  sm_candidates = [site_info.get("sitemap", "")] if site_info.get("sitemap") else []
  if not collected and origin and not sm_candidates:
    sm_candidates = [f"{origin}/news-sitemap.xml", f"{origin}/sitemap_news.xml", f"{origin}/post-sitemap.xml"]
  for sm_u in sm_candidates:
    if collected or not sm_u:
      break
    try:
      rs = _direct_http_get(sm_u, timeout=5.0)
      if rs is not None and rs.status_code == 200 and b"<url" in rs.content:
        for entry in parse_news_sitemap_xml(rs.content, default_platform, default_source=name, max_age_sec=max_age_sec):
          if entry["url"] not in seen_u:
            seen_u.add(entry["url"])
            collected.append(entry)
    except Exception:
      pass

  # 4) المسح المباشر للصفحة الرئيسية / صفحة المستجدات الحية للناشر (HTML Live Scrape + JSON-LD + a[title])
  if (not collected or len(collected) < 3) and origin and BeautifulSoup is not None:
    live_page_u = site_info.get("live_url") or f"{origin}/"
    try:
      rh = _direct_http_get(live_page_u, timeout=6.0)
      if rh is not None and rh.status_code == 200 and rh.text:
        soup = BeautifulSoup(rh.text, "html.parser")
        now_ts = time.time()
        # اكتشاف تلقائي لأي رابط RSS بديل في ترويسة الصفحة
        alt_rss = soup.find("link", attrs={"type": re.compile(r"rss|atom", re.I)})
        if alt_rss and alt_rss.get("href") and not collected:
          alt_u = urllib.parse.urljoin(live_page_u, alt_rss["href"])
          try:
            ra = _direct_http_get(alt_u, timeout=5.0)
            if ra is not None and ra.status_code == 200 and (b"<rss" in ra.content or b"<feed" in ra.content):
              for entry in parse_rss_xml(ra.content, default_platform, default_source=name, fallback_offset=1800, max_age_sec=max_age_sec):
                if entry["url"] not in seen_u:
                  seen_u.add(entry["url"])
                  entry["source_name"] = name
                  collected.append(entry)
          except Exception:
            pass
        # استخراج المقالات المباشرة من بنية الصفحة الحية (عناوين h1/h2/h3 وبطاقات article وسمة title)
        for art_node in soup.select("article, .post, .card, .news-item, .entry-title a, h2 a, h3 a, a[title]")[:45]:
          a_el = art_node if art_node.name == "a" else art_node.find("a", href=True)
          if not a_el or not a_el.get("href"):
            continue
          href = urllib.parse.urljoin(live_page_u, a_el["href"].strip())
          if domain not in href or href in seen_u:
            continue
          if any(skip_p in href.lower() for skip_p in ("/category/", "/tag/", "/author/", "/page/", "wp-login", "#")):
            continue
          title_txt = clean_display_text(a_el.get_text(" ", strip=True) or a_el.get("title") or "")
          if len(title_txt) < 18:
            title_txt = clean_display_text(a_el.get("title") or title_txt)
          if len(title_txt) < 18:
            continue
          time_el = art_node.find("time") if art_node.name != "a" else None
          dt_raw = (time_el.get("datetime") or time_el.get_text(" ", strip=True)) if time_el else ""
          pub_str, pub_ts = extract_date_from_url_or_text(href, title_txt, dt_raw, fallback_offset_sec=1800)
          if max_age_sec > 0 and (now_ts - pub_ts) > max_age_sec:
            continue
          seen_u.add(href)
          collected.append({
              "title": title_txt,
              "url": clean_social_post_url(href),
              "raw_snippet": title_txt,
              "source_name": name,
              "platform": default_platform,
              "pub_date": pub_str,
              "pub_timestamp": pub_ts,
              "image_url": "",
          })
    except Exception:
      pass

  return collected


# =====================================================================
# محرك رصد الصحافة الدولية (الفرنسية، الإسبانية، الجزائرية، والدولية)
# =====================================================================
def scrape_international_press(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
) -> list:
  """رصد مباشر وفوري للصحافة الدولية (فرنسا، إسبانيا، الجزائر، أمريكا، والهيئات الدولية)
  عبر الاتصال المتوازي بخوادم الصحف مباشرة (RSS / Atom / WP API) مع فرض صارم لتاريخ النشر الفعلي."""
  items = []
  seen_urls = set()
  p_cfg = get_period_config(search_period)
  max_age = p_cfg["sec"]
  direct_sites = [s for s in INTERNATIONAL_PRESS_SITES if s.get("rss") or s.get("sitemap") or s.get("wp")]
  total_sites = max(1, len(direct_sites))

  if progress_cb:
    progress_cb(0.10, f"اتصال مباشر متوازي بـ {total_sites} صحيفة دولية (رصد فوري في وقت النشر)...")

  done_cnt = 0
  with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    fut_map = {
        pool.submit(_fetch_single_publisher_live, site_info, "صحافة دولية", max_age, keywords_input): site_info
        for site_info in direct_sites
    }
    for fut in concurrent.futures.as_completed(fut_map):
      if is_stop_requested():
        break
      done_cnt += 1
      site_info = fut_map[fut]
      if progress_cb and (done_cnt % 4 == 0 or done_cnt == total_sites):
        progress_cb(
            0.10 + 0.72 * (done_cnt / total_sites),
            f"رصد فوري مباشر للصحافة الدولية ({done_cnt}/{total_sites}): {site_info['name']}...",
        )
      try:
        for entry in fut.result():
          e_url = entry["url"]
          if e_url not in seen_urls and is_strictly_judicial_and_clean(
              entry["title"],
              entry["raw_snippet"],
              e_url,
              keywords_input,
              is_international=True,
          ):
            seen_urls.add(e_url)
            entry["platform"] = "صحافة دولية"
            entry["source_name"] = site_info["name"]
            items.append(entry)
      except Exception:
        pass

  # مسار تكميلي سريع ومضبوط زمنياً فقط للوكالات التي لا تتيح خلاصة RSS مفتوحة (مثل AP/Reuters/WSJ)
  if not is_stop_requested() and len(items) < 12:
    supp_queries = [
        'Morocco justice OR court OR extradition (site:reuters.com OR site:apnews.com OR site:wsj.com)',
        'Maroc justice OR tribunal OR extradition (site:mediapart.fr OR site:afp.com)',
    ]
    for q_idx, q_str in enumerate(supp_queries, 1):
      if is_stop_requested():
        break
      if progress_cb:
        progress_cb(0.84 + 0.06 * q_idx, "فحص تكميلي للوكالات الدولية بدون RSS...")
      try:
        rb = requests.get(
            f"https://www.bing.com/news/search?q={urllib.parse.quote(q_str)}&format=rss&adlt=strict",
            headers=LIVE_FETCH_HEADERS,
            timeout=5.5,
        )
        if rb.status_code == 200 and b"<item>" in rb.content:
          for entry in parse_rss_xml(rb.content, "صحافة دولية", default_source="صحافة دولية", fallback_offset=9999999, max_age_sec=max_age):
            e_url = _unwrap_any_redirect_url(entry["url"])
            entry["url"] = e_url
            u_domain = urllib.parse.urlparse(e_url).netloc.lower().replace("www.", "")
            if u_domain.endswith(".ma") or any(d in u_domain for d in MOROCCAN_EXTRA_DOMAINS):
              continue
            if e_url not in seen_urls and is_strictly_judicial_and_clean(
                entry["title"], entry["raw_snippet"], e_url, keywords_input, is_international=True
            ):
              seen_urls.add(e_url)
              entry["platform"] = "صحافة دولية"
              items.append(entry)
      except Exception:
        pass

  items.sort(key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True)
  return items


def scrape_open_web_keyword(
    keyword_query: str, search_period: str = "آخر 7 أيام", progress_cb=None
) -> list:
  """رصد حر وفوري في الوقت الفعلي لكلمة أو عبارة مفتاحية عبر:
  1) الفحص المباشر المتوازي للصحف الرياضية الدولية والمواقع المتخصصة والصحف العالمية والمغربية (لحظة النشر).
  2) مسح تكميلي لمحركات الأخبار والويب مع احترام صارم لتاريخ النشر الفعلي ضمن الفترة الزمنية المحددة."""
  kw = clean_display_text(keyword_query or "")
  if not kw:
    return []
  items = []
  seen_urls = set()
  p_cfg = get_period_config(search_period)
  when_tag = p_cfg["gnews"]
  max_age = p_cfg["sec"]

  # 1) الرصد المباشر في وقت النشر الفعلي من خوادم الصحف الرياضية والدولية والمغربية بالتوازي
  all_direct_publishers = (
      DIRECT_SPORTS_AND_SPECIALIZED_FEEDS
      + list(MOROCCAN_PRESS_SITES)
      + list(INTERNATIONAL_PRESS_SITES)
  )
  if progress_cb:
    progress_cb(0.12, f"رصد فوري مباشر في {len(all_direct_publishers)} صحيفة رياضية ودولية ووطنية عن: {kw}")

  raw_direct_pool = []
  with concurrent.futures.ThreadPoolExecutor(max_workers=14) as pool:
    futs = [
        pool.submit(
            _fetch_single_publisher_live,
            site_info,
            "صحافة دولية" if site_info.get("country", "") not in ("", "المغرب") else "الصحف",
            max_age,
            kw if site_info.get("wp") else "",
        )
        for site_info in all_direct_publishers
    ]
    for fut in concurrent.futures.as_completed(futs):
      if is_stop_requested():
        break
      try:
        raw_direct_pool.extend(fut.result())
      except Exception:
        pass

  # تصفية المقالات الفورية المباشرة وفق الكلمة المفتاحية (تطابق دقيق أو مشابه/مشتق)
  if raw_direct_pool:
    matched_direct = smart_search_articles(raw_direct_pool, kw)
    for entry in matched_direct:
      u = entry.get("url", "")
      if u and u not in seen_urls:
        seen_urls.add(u)
        normalize_press_platform_and_source(entry)
        entry["category"] = "رصد حر بالويب"
        entry["_open_web_kw"] = True
        items.append(entry)

  # 2) مسار تكميلي فوري مرتب بالتاريخ (بدون Google News المؤرشف) مع فرض صارم لتاريخ النشر الفعلي
  if not is_stop_requested():
    if progress_cb:
      progress_cb(0.72, f"فحص التغطيات الحية المرتبة بالوقت ({search_period}): {kw}")
    web_feeds = [
        f"https://www.bing.com/news/search?q={urllib.parse.quote(kw)}&format=rss&qft=sortbydate%3d%221%22",
        f"https://www.bing.com/news/search?q={urllib.parse.quote(kw)}&format=rss&cc=FR&setlang=fr&qft=sortbydate%3d%221%22",
        f"https://www.bing.com/news/search?q={urllib.parse.quote(kw)}&format=rss&cc=ES&setlang=es&qft=sortbydate%3d%221%22",
        f"https://www.bing.com/news/search?q={urllib.parse.quote(kw)}&format=rss&cc=US&setlang=en&qft=sortbydate%3d%221%22",
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
      def _get_feed(u_f):
        try:
          r = requests.get(u_f, headers=LIVE_FETCH_HEADERS, timeout=6.0)
          if r.status_code == 200 and (b"<rss" in r.content or b"<feed" in r.content):
            return parse_rss_xml(r.content, "صحافة دولية", default_source="ويب مفتوح", fallback_offset=9999999, max_age_sec=max_age)
        except Exception:
          pass
        return []
      for fut in concurrent.futures.as_completed([pool.submit(_get_feed, u_f) for u_f in web_feeds]):
        if is_stop_requested():
          break
        for entry in fut.result():
          u = entry.get("url", "")
          if u and u not in seen_urls:
            seen_urls.add(u)
            normalize_press_platform_and_source(entry)
            entry["category"] = "رصد حر بالويب"
            entry["_open_web_kw"] = True
            items.append(entry)

  items.sort(key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True)
  return items


def scrape_moroccan_press(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
):
  """رصد مباشر وفوري للصحف والمواقع المغربية في وقت النشر الفعلي عبر الاتصال المتوازي بخوادم الصحف
  (WordPress REST API + RSS الحي + News Sitemap) دون انتظار أرشفة Google News."""
  items = []
  seen_urls = set()
  p_cfg = get_period_config(search_period)
  max_age = p_cfg["sec"]
  total_sites = max(1, len(MOROCCAN_PRESS_SITES))

  if progress_cb:
    progress_cb(0.10, f"رصد فوري مباشر لـ {total_sites} جريدة وموقع مغربي (وقت النشر الفعلي)...")

  done_cnt = 0
  with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    fut_map = {
        pool.submit(_fetch_single_publisher_live, site_info, "الصحف", max_age, keywords_input): site_info
        for site_info in MOROCCAN_PRESS_SITES
    }
    for fut in concurrent.futures.as_completed(fut_map):
      if is_stop_requested():
        break
      done_cnt += 1
      site_info = fut_map[fut]
      if progress_cb and (done_cnt % 3 == 0 or done_cnt == total_sites):
        progress_cb(
            0.10 + 0.78 * (done_cnt / total_sites),
            f"رصد فوري مباشر للصحافة الوطنية ({done_cnt}/{total_sites}): {site_info['name']}...",
        )
      try:
        for entry in fut.result():
          if entry["url"] not in seen_urls and is_strictly_judicial_and_clean(
              entry["title"],
              entry["raw_snippet"],
              entry["url"],
              keywords_input,
          ):
            seen_urls.add(entry["url"])
            entry["platform"] = "الصحف"
            entry["source_name"] = site_info["name"]
            items.append(entry)
      except Exception:
        pass

  items.sort(key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True)
  return items


def _extract_yt_renderers_from_html(
    html_text: str, default_channel_name: str = "YouTube"
):
  results = []
  seen_vids = set()
  chunks = re.split(
      r'"(?:videoRenderer|gridVideoRenderer|compactVideoRenderer|reelItemRenderer|shortsLockupViewModel|lockupViewModel)"\s*:',
      html_text,
  )[1:]
  for chunk in chunks[:45]:
    vid_m = re.search(
        r'"(?:videoId|contentId)"\s*:\s*"([a-zA-Z0-9_-]{11})"', chunk[:2500]
    )
    if not vid_m:
      continue
    vid = vid_m.group(1)
    if vid in seen_vids:
      continue

    title = ""
    for t_pat in [
        r'"title"\s*:\s*\{[^{}]*"runs"\s*:\s*\[\{"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"title"\s*:\s*\{"runs"\s*:\s*\[\{"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"title"\s*:\s*\{[^{}]*"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"headline"\s*:\s*\{[^{}]*"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"primaryText"\s*:\s*\{"content"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"title"\s*:\s*\{"content"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"accessibilityData"\s*:\s*\{"label"\s*:\s*"((?:[^"\\]|\\.)*)"',
    ]:
      m_t = re.search(t_pat, chunk[:3500])
      if m_t:
        cand_t = decode_js_escaped_text(m_t.group(1))
        if len(cand_t) >= 4:
          title = cand_t
          break

    if not title:
      continue

    pub_rel = ""
    for p_pat in [
        r'"publishedTimeText"\s*:\s*\{"simpleText"\s*:\s*"((?:[^"\\]|\\.)*)"',
        r'"publishedTimeText"\s*:\s*\{"runs"\s*:\s*\[\{"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
    ]:
      pub_m = re.search(p_pat, chunk[:4000])
      if pub_m:
        pub_rel = decode_js_escaped_text(pub_m.group(1))
        break

    owner_m = re.search(
        r'"(?:ownerText|shortBylineText|longBylineText)"\s*:\s*\{"runs"\s*:\s*\[\{"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
        chunk[:4500],
    )
    channel_name = (
        decode_js_escaped_text(owner_m.group(1))
        if owner_m
        else default_channel_name
    )

    owner_id_m = re.search(
        r'"(?:ownerText|shortBylineText|longBylineText)".*?"browseId"\s*:\s*"(UC[a-zA-Z0-9_-]{20,})"',
        chunk[:4500],
    )
    owner_id = owner_id_m.group(1) if owner_id_m else ""

    owner_h_m = re.search(
        r'"canonicalBaseUrl"\s*:\s*"/(@?[^"\\]+)"',
        chunk[:4500],
    )
    owner_handle = (
        urllib.parse.unquote(owner_h_m.group(1)).lstrip("@")
        if owner_h_m
        else ""
    )

    desc_runs = re.findall(
        r'"detailedMetadataSnippets".*?"snippetText"\s*:\s*\{"runs"\s*:\s*\[(.*?)\]\s*\}',
        chunk[:5000],
    )
    if not desc_runs:
      desc_runs = re.findall(
          r'"descriptionSnippet"\s*:\s*\{"runs"\s*:\s*\[(.*?)\]\s*\}',
          chunk[:5000],
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


def scrape_youtube_platform(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
):
  items = []
  seen_urls = set()
  queries = build_search_queries(keywords_input)[:4]
  p_cfg = get_period_config(search_period)
  max_age = p_cfg["sec"]
  yt_sp = p_cfg["yt"]
  now_ts = time.time()

  for idx, q in enumerate(queries):
    if is_stop_requested():
      break
    if progress_cb:
      progress_cb((idx + 1) / max(1, len(queries)), f"مسح يوتيوب: {q}")
    search_url = (
        "https://www.youtube.com/results?search_query="
        f"{urllib.parse.quote(q)}&sp={yt_sp}"
    )
    try:
      r = requests.get(
          search_url,
          headers=DEFAULT_HEADERS,
          cookies=YT_BYPASS_COOKIES,
          timeout=12,
      )
      if r.status_code == 200:
        for v in _extract_yt_renderers_from_html(r.text):
          v_url = f"https://www.youtube.com/watch?v={v['vid']}"
          if v_url in seen_urls:
            continue
          if not is_strictly_judicial_and_clean(
              v["title"], v["desc"], v_url, keywords_input
          ):
            continue
          pub_str, pub_ts = extract_date_from_url_or_text(
              v_url, v["desc"], v["pub_rel"], fallback_offset_sec=3600
          )
          if max_age > 0 and (now_ts - pub_ts) > max_age:
            continue
          seen_urls.add(v_url)
          items.append({
              "title": v["title"],
              "url": v_url,
              "raw_snippet": v["desc"],
              "source_name": f"قناة {v['channel_name']}",
              "platform": "يوتيوب",
              "pub_date": pub_str,
              "pub_timestamp": pub_ts,
              "image_url": f"https://i.ytimg.com/vi/{v['vid']}/hqdefault.jpg",
          })
    except Exception:
      pass

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
            f"{kw_clean} القضاء فيسبوك المغرب when:{when_tag}",
            f"{kw_clean} العدالة فايسبوك المغرب when:{when_tag}",
        ]
      elif platform_label == "إكس":
        social_g_queries = [
            f"{kw_clean} القضاء تغريدة المغرب when:{when_tag}",
            f"{kw_clean} العدالة منصة إكس المغرب when:{when_tag}",
        ]
      else:
        social_g_queries = [
            f"{kw_clean} القضاء تيك توك المغرب when:{when_tag}",
            f"{kw_clean} القضاء إنستغرام المغرب when:{when_tag}",
        ]

    plat_tag_slug = {"فيسبوك": "fb", "إكس": "x", "أخرى": "other"}.get(
        platform_label, "soc"
    )
    for sq in social_g_queries:
      if is_stop_requested():
        break
      sq_clean = re.sub(r"\s+when:\S+", "", sq).strip()
      bing_social_url = (
          "https://www.bing.com/news/search?q="
          f"{urllib.parse.quote(sq_clean)}&format=rss&adlt=strict&qft=sortbydate%3d%221%22"
      )
      try:
        r = requests.get(bing_social_url, headers=LIVE_FETCH_HEADERS, timeout=7)
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
    ("Hespress", "فيسبوك • هسبريس"),
    ("al3omk", "فيسبوك • العمق المغربي"),
    ("alyaoum24", "فيسبوك • اليوم 24"),
    ("madar21com", "فيسبوك • مدار 21"),
    ("alayam24", "فيسبوك • الأيام 24"),
    ("goudmag", "فيسبوك • كود"),
    ("akhbarona.page", "فيسبوك • أخبارنا"),
    ("rue20.ma", "فيسبوك • زنقة 20"),
]


def scrape_facebook_platform(
    keywords_input: str, search_period: str = "آخر 7 أيام", progress_cb=None
):
  """محرك رصد شامل لمنصة فيسبوك يجمع بين الفحص المباشر للخط الزمني لصفحات القضاء والصحافة المغربية على فيسبوك والبحث المتعدد المحركات."""
  items = []
  seen_urls = set()
  p_cfg = get_period_config(search_period)
  max_age = p_cfg["sec"]
  now_ts = time.time()

  chrome_doc_headers = dict(DEFAULT_HEADERS)
  chrome_doc_headers.update({
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Sec-Fetch-Dest": "document",
      "Sec-Fetch-Mode": "navigate",
      "Sec-Fetch-Site": "none",
      "Upgrade-Insecure-Requests": "1",
  })

  # 1) الفحص المباشر للخط الزمني لصفحات المؤسسات القضائية والصحف المغربية الكبرى على فيسبوك (يعمل حتى لو حجبت محركات البحث site:facebook.com)
  for p_idx, (fb_handle, fb_badge) in enumerate(MOROCCAN_JUDICIAL_AND_PRESS_FB_PAGES):
    if is_stop_requested():
      break
    if progress_cb:
      progress_cb(
          min(0.55, (p_idx + 1) / max(1, len(MOROCCAN_JUDICIAL_AND_PRESS_FB_PAGES) * 2)),
          f"فحص منشورات {fb_badge} الحية...",
      )
    page_u = f"https://www.facebook.com/{fb_handle}"
    is_pure_judicial_page = fb_handle == "pmpmaroc"

    # أ) فحص أداة الخط الزمني لفيسبوك (BigPipe plugin)
    plugin_posts = _scrape_facebook_plugin_timeline(
        page_u,
        {},
        fb_badge,
        "",
        keywords_input,
        handle=fb_handle,
        page_id="",
    )
    # ب) فحص كود Comet SSR JSON المباشر للصفحة
    try:
      rc = requests.get(
          page_u,
          headers=chrome_doc_headers,
          cookies={"locale": "ar_AR"},
          timeout=7,
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
      if not u_p or u_p in seen_urls or not is_direct_social_post_url(u_p, "فيسبوك"):
        continue
      # إذا كانت صفحة صحفية عامة، نشترط أن يكون المنشور قضائياً؛ أما صفحة رئاسة النيابة العامة فجميع منشوراتها قضائية
      if not is_strictly_judicial_and_clean(
          p.get("title", ""),
          p.get("raw_snippet", ""),
          u_p,
          keywords_input,
          is_target=is_pure_judicial_page and not bool(keywords_input.strip()),
      ):
        continue
      seen_urls.add(u_p)
      p["url"] = f"{u_p}#plat=fb"
      p["platform"] = "فيسبوك"
      p["source_name"] = fb_badge
      items.append(p)

  # 2) البحث العميق في منشورات وفيديوهات فيسبوك عبر محركات البحث المتوازية
  if keywords_input and keywords_input.strip():
    custom_kws = [k.strip() for k in re.split(r"[,،\n]+", keywords_input) if k.strip()]
    fb_queries = []
    for kw in custom_kws[:4]:
      fb_queries.append(f'site:facebook.com "{kw}" القضاء المغرب')
      fb_queries.append(f'facebook.com "{kw}" المحكمة OR النيابة العامة المغرب')
  else:
    fb_queries = [
        'site:facebook.com "المجلس الأعلى للسلطة القضائية"',
        'site:facebook.com "رئاسة النيابة العامة" المغرب',
        'site:facebook.com "محكمة النقض" المغرب',
        'site:facebook.com "الوكيل العام للملك" OR "وكيل الملك" المغرب',
        'facebook.com/posts "القضاء" OR "النيابة العامة" المغرب',
        'facebook.com/videos "القضاء" OR "المجلس الأعلى للسلطة القضائية" المغرب',
    ]

  total_q = len(fb_queries)
  for idx, fq in enumerate(fb_queries):
    if is_stop_requested():
      break
    if progress_cb:
      progress_cb(
          min(0.92, 0.55 + 0.37 * ((idx + 1) / max(1, total_q))),
          f"مسح منشورات وفيديوهات فيسبوك القضائية ({idx + 1}/{total_q})...",
      )

    search_results = _multi_engine_web_search(
        fq, platform="فيسبوك", default_source="فيسبوك", max_results=16
    )
    for entry in search_results:
      if is_stop_requested():
        break
      raw_u = clean_social_post_url(entry.get("url", ""))
      if not raw_u or ("facebook.com" not in raw_u.lower() and "fb.watch" not in raw_u.lower()):
        continue

      raw_snip = _strip_fb_sidebar_noise(entry.get("raw_snippet", ""))
      raw_title = _strip_fb_sidebar_noise(entry.get("title", ""))

      if not is_direct_social_post_url(raw_u, "فيسبوك"):
        resolved_u = resolve_direct_facebook_post_url(raw_snip, raw_title)
        if resolved_u and is_direct_social_post_url(resolved_u, "فيسبوك"):
          raw_u = resolved_u
        else:
          continue

      if raw_u in seen_urls:
        continue

      if len(items) < 14:
        is_ok, og_body, og_img, final_u = _verify_and_enrich_fb_post_url(raw_u)
        if not is_ok:
          continue
        if og_body and len(og_body) >= 20:
          raw_snip = og_body
        if og_img and not entry.get("image_url"):
          entry["image_url"] = og_img
        raw_u = final_u

      display_title = raw_snip[:115] + ("..." if len(raw_snip) > 115 else "") if len(raw_snip) >= 25 else _clean_social_page_title(raw_title)
      if not display_title or len(display_title) < 12:
        continue

      if not is_strictly_judicial_and_clean(
          display_title, raw_snip, raw_u, keywords_input, is_target=False
      ):
        continue

      pub_str, pub_ts = extract_date_from_url_or_text(
          raw_u, raw_snip, entry.get("pub_date", ""), fallback_offset_sec=2400
      )
      if max_age > 0 and (now_ts - pub_ts) > max(max_age, 7 * 86400):
        continue

      src_lbl = _extract_fb_page_label_from_entry(raw_u, raw_title)
      seen_urls.add(raw_u)
      items.append({
          "title": display_title,
          "url": f"{raw_u}#plat=fb",
          "raw_snippet": raw_snip or display_title,
          "source_name": src_lbl,
          "platform": "فيسبوك",
          "pub_date": pub_str,
          "pub_timestamp": pub_ts,
          "image_url": entry.get("image_url", ""),
      })

  # 3) استكمال الرصد من التغطيات القضائية الموثوقة لمنشورات فيسبوك
  if len(items) < 8 and not is_stop_requested():
    extra_social = _multi_engine_social_search(
        "فيسبوك", ["facebook.com"], keywords_input, search_period, progress_cb=None
    )
    for ex in extra_social:
      u_ex = clean_social_post_url(ex.get("url", ""))
      if u_ex and u_ex not in seen_urls:
        seen_urls.add(u_ex)
        items.append(ex)

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

  # 1) محرك Bing Web Search HTML المباشر (الأقوى في فهرسة صفحات ومنشورات فيسبوك العربية والمغربية)
  bing_html_url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count={max_results}&setlang=ar&cc=MA"
  try:
    rb_html = requests.get(bing_html_url, headers=DEFAULT_HEADERS, timeout=8)
    if rb_html.status_code == 200 and rb_html.text and BeautifulSoup is not None:
      soup_b = BeautifulSoup(rb_html.text, "html.parser")
      for li_el in soup_b.select("li.b_algo, div.b_algo"):
        a_el = li_el.select_one("h2 a[href], a[href]")
        if not a_el:
          continue
        href = a_el.get("href", "").strip()
        title_txt = clean_display_text(a_el.get_text(" ", strip=True))
        snip_el = li_el.select_one("div.b_caption p, p.b_lineclamp2, p.b_lineclamp3, p.b_lineclamp4, .b_caption")
        snip_txt = (
            clean_display_text(snip_el.get_text(" ", strip=True))
            if snip_el
            else ""
        )
        _add_candidate(href, title_txt, snip_txt)
  except Exception:
    pass

  # 2) محرك Yahoo Search HTML (موسع ليدعم جميع قوالب Yahoo الحديثة)
  yahoo_url = f"https://search.yahoo.com/search?p={urllib.parse.quote(query)}&n={max_results}"
  try:
    ry = requests.get(yahoo_url, headers=DEFAULT_HEADERS, timeout=8)
    if ry.status_code == 200 and ry.text and BeautifulSoup is not None:
      soup_y = BeautifulSoup(ry.text, "html.parser")
      for algo in soup_y.select("div.algo, div.dd.algo, li div.algo-sr, div.Sr"):
        a_el = algo.select_one("h3 a[href], div.compTitle a[href], a.ac-algo[href], a[href]")
        if not a_el:
          continue
        href = a_el.get("href", "").strip()
        title_txt = clean_display_text(a_el.get_text(" ", strip=True))
        snip_el = algo.select_one("div.compText, p, span.fc-falcon")
        snip_txt = (
            clean_display_text(snip_el.get_text(" ", strip=True))
            if snip_el
            else ""
        )
        _add_candidate(href, title_txt, snip_txt)
  except Exception:
    pass

  # 3) محرك DuckDuckGo HTML عبر طلب POST (يتجاوز حظر الـ 202 الذي يحدث مع طلبات GET على السحابة)
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
        timeout=8,
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
        snip_txt = (
            clean_display_text(snip_el.get_text(" ", strip=True))
            if snip_el
            else ""
        )
        _add_candidate(href, title_txt, snip_txt)
  except Exception:
    pass

  # 4) محرك Bing Search RSS & Bing News RSS
  for bing_base in [
      "https://www.bing.com/search?q=",
      "https://www.bing.com/news/search?q=",
  ]:
    bing_u = (
        f"{bing_base}{urllib.parse.quote(query)}"
        "&format=rss&adlt=strict&cc=MA&setlang=ar"
    )
    try:
      rb = requests.get(bing_u, headers=DEFAULT_HEADERS, timeout=7)
      if rb.status_code == 200 and b"<item>" in rb.content:
        for entry in parse_rss_xml(
            rb.content,
            platform,
            default_source=default_source or platform,
            fallback_offset=3600,
            max_age_sec=0,
        ):
          u_e = clean_social_post_url(entry.get("url", ""))
          if u_e and u_e not in seen_u:
            seen_u.add(u_e)
            entry["url"] = u_e
            collected.append(entry)
    except Exception:
      pass

  # 5) مكتبة DDGS الاحتياطية
  if DDGS is not None and len(collected) < max_results:
    try:
      with DDGS() as ddgs:
        for res in ddgs.text(
            query,
            region="wt-wt",
            safesearch="strict",
            timelimit=None,
            max_results=max_results,
        ):
          _add_candidate(
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

  # 5) الجلب من خلاصة XML الرسمية للقناة (تتحدث بالثانية فور رفع أي فيديو جديد دون انتظار أرشفة محركات البحث)
  if cid:
    xml_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    try:
      rx = requests.get(xml_url, headers=DEFAULT_HEADERS, timeout=10)
      if rx.status_code == 200:
        for entry in parse_rss_xml(
            rx.content,
            "يوتيوب",
            default_source=source_badge,
            max_age_sec=0,
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
            _tag_custom_target_item(entry, t_info, source_badge)
            all_channel_videos.append(entry)
    except Exception:
      pass

  # 6) دمج الفيديوهات المستخرجة من InnerTube Browse ومن تبويب /videos ومن بحث يوتيوب الحي المفلتر بملكية القناة
  direct_renderers = list(innertube_vids)
  if page_html:
    direct_renderers.extend(
        _extract_yt_renderers_from_html(page_html, channel_title)
    )
  direct_renderers.extend(live_search_videos)

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
    pub_str, pub_ts = extract_date_from_url_or_text(
        v_url, v["desc"], v["pub_rel"], fallback_offset_sec=3600
    )
    v_badge = (
        f"🎯 {v['channel_name']}"
        if v.get("channel_name") and v["channel_name"] != "YouTube"
        else source_badge
    )
    entry = {
        "title": v["title"],
        "url": v_url,
        "raw_snippet": v["desc"],
        "source_name": v_badge,
        "platform": "يوتيوب",
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "image_url": f"https://i.ytimg.com/vi/{v['vid']}/hqdefault.jpg",
    }
    seen_channel_vids.add(v_url)
    _tag_custom_target_item(entry, t_info, v_badge)
    all_channel_videos.append(entry)

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
              max_age_sec=0,
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
              _tag_custom_target_item(entry, t_info, source_badge)
              all_channel_videos.append(entry)
      except Exception:
        pass

  # 7) احتياطي أخير عبر محركات البحث مقيد بتحقق oEmbed
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
      is_owner, real_v_title, real_author = _verify_youtube_video_owner(
          u_w, handle=handle, cid=cid, channel_title=channel_title
      )
      if not is_owner:
        continue
      if real_v_title:
        item_w["title"] = real_v_title
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
  chosen_list = in_window if in_window else all_channel_videos[:12]
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


def _scrape_facebook_plugin_timeline(
    canonical_fb_url: str,
    t_info: dict,
    source_badge: str,
    page_avatar: str,
    t_kw: str,
    handle: str = "",
    page_id: str = "",
) -> list:
  """استخراج المنشورات الفورية غير المؤرشفة مباشرة من أداة الخط الزمني لفيسبوك (plugins/page.php) بعد فك تعليقات BigPipe."""
  posts = []
  seen_post_urls = set()

  candidate_hrefs = [canonical_fb_url]
  if handle and not handle.startswith("fb_") and not handle.isdigit():
    u_h = f"https://www.facebook.com/{handle}"
    if u_h not in candidate_hrefs:
      candidate_hrefs.append(u_h)
  if page_id and page_id.isdigit():
    u_pid = f"https://www.facebook.com/profile.php?id={page_id}"
    if u_pid not in candidate_hrefs:
      candidate_hrefs.append(u_pid)

  iframe_headers = dict(DEFAULT_HEADERS)
  iframe_headers.update({
      "Referer": "https://www.facebook.com/",
      "Sec-Fetch-Dest": "iframe",
      "Sec-Fetch-Mode": "navigate",
      "Sec-Fetch-Site": "same-origin",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
  })

  for target_href in candidate_hrefs[:2]:
    plugin_url = (
        "https://www.facebook.com/plugins/page.php?"
        f"href={urllib.parse.quote(target_href)}"
        "&tabs=timeline&width=500&height=800&small_header=false"
        "&adapt_container_width=true&hide_cover=false&show_facepile=false"
    )
    for hdr in (iframe_headers, FB_CRAWLER_HEADERS):
      try:
        r = requests.get(plugin_url, headers=hdr, timeout=10)
        if r.status_code != 200 or not r.text:
          continue

        unwrapped_doc = _unwrap_facebook_bigpipe_html(r.text)

        if BeautifulSoup is not None:
          soup = BeautifulSoup(unwrapped_doc, "html.parser")
          post_containers = soup.select("div._5pcr, div.userContentWrapper")
          if not post_containers:
            post_containers = soup.select(
                "div[data-ft*='top_level_post_id'], div[role='article']"
            )

          for idx, box in enumerate(post_containers[:15]):
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
              continue
            if not is_strictly_judicial_and_clean(
                post_text, post_text, post_link, t_kw, is_target=True
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
            title_short = post_text[:110] + ("..." if len(post_text) > 110 else "")
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
  """فحص رابط المنشور عبر ترويسة facebookexternalhit مع التعامل الذكي مع جدار تسجيل الدخول على السحابة دون إسقاط المنشور."""
  try:
    rp = requests.get(post_u, headers=FB_CRAWLER_HEADERS, timeout=6)
    if rp.status_code != 200 or not rp.text:
      is_owned = _is_fb_post_owned_by_target(
          post_u, handle=handle, page_id=page_id, page_official_name=page_official_name
      )
      return is_owned, "", page_avatar, post_u
    p_html = rp.text[:45000]

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

    # نرفض فقط الروابط المعطوبة فعلياً (Page Not Found)، أما جدار تسجيل الدخول فيعني أن الرابط سليم ولكن فيسبوك يطلب الدخول من السيرفر
    not_found_titles = [
        "page not found",
        "الصفحة غير موجودة",
    ]
    if post_title_og and any(bt in post_title_og.lower() for bt in not_found_titles):
      return False, "", "", post_u

    is_login_wall = bool(
        (rp.url and "login" in rp.url.lower())
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
      is_owned = _is_fb_post_owned_by_target(
          post_u, handle=handle, page_id=page_id, page_official_name=page_official_name
      )
      return is_owned, "", page_avatar, post_u

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


def analyze_with_gemini(item: dict, api_key: str):
  """تحليل ذكي فائق الدقة عبر Gemini AI مع ترجمة فورية دقيقة كخط أساس:
  1. ترجمة العنوان الأجنبي ترجمة صحفية دقيقة إلى العربية الفصحى.
  2. تلخيص الوقائع المحددة للخبر نفسه (الأسماء، المحاكم، القرارات) باللغة العربية الفصحى دون تعميم."""
  title = clean_display_text(item.get("title", ""))
  snippet = clean_display_text(item.get("raw_snippet", "")) or title
  platform = item.get("platform", "الصحف")
  source_name = item.get("source_name", platform)
  url = item.get("url", "")

  detected_country, detected_topic = detect_article_country_and_topic(
      title, snippet, url, source_name, platform
  )

  # الترجمة الآلية الدقيقة للعنوان والمتن كخط أساس مضمون
  is_foreign_title = not _is_predominantly_arabic(title)
  arabic_title_fallback = translate_foreign_title_to_arabic_rulebased(title) if is_foreign_title else title

  fallback_summary = build_extractive_arabic_summary(
      arabic_title_fallback, snippet, platform, source_name
  )

  default_result = {
      "translated_title": arabic_title_fallback,
      "summary": fallback_summary,
      "sentiment": "محايد",
      "category": detected_topic,
      "relevance_score": 88,
  }

  if not api_key or not str(api_key).strip():
    return default_result

  prompt = (
      "أنت مترجم ومحلل إعلامي وقضائي محترف في مرصد القضاء والعدالة.\n"
      "قم بقراءة الخبر التالي الصادر عن الصحافة (عربي أو فرنسي أو إسباني أو إنجليزي) ونفذ بدقة تامة:\n"
      "1) translated_title: ترجم العنوان الأصلي ترجمة حرفية وصحفية دقيقة إلى اللغة العربية الفصحى (إذا كان بلغة أجنبية، اذكر الوقائع والأطراف بدقة دون اختصار مخل أو عبارات عامة).\n"
      "2) summary: لخص مضمون الخبر نفسه في جملتين إلى ثلاث جمل بالعربية الفصحى تشرح الوقائع المحددة والأطراف والمحكمة والقرار الوارد في النص مباشرة.\n"
      "3) إذا كان المقال صادراً عن صحافة دولية أجنبية ويتطرق إلى المغرب (بشكل مباشر أو ضمني مثل الصحراء المغربية، اتفاقيات الصيد أو الفلاحة، سبتة ومليلية، أو تسليم مطلوبين)، فيجب إجبارياً تركيز الملخص باللغة العربية على ما يخص المغرب في هذا الخبر. أما الصحف الوطنية المغربية فلا تضف لها عبارة يتطرق للمغرب أو يهم المغرب.\n"
      "أرجع النتيجة بصيغة JSON فقط بالمفاتيح التالية:\n"
      '{"translated_title": "الترجمة العربية الدقيقة للعنوان...", '
      '"summary": "ملخص الوقائع المباشرة للخبر باللغة العربية...", '
      '"sentiment": "إيجابي أو محايد أو سلبي", '
      '"category": "يتطرق للمغرب أو شؤون قضائية ومحاكم أو قضاء دولي أو قضايا وتسليم واتفاقيات", '
      '"relevance_score": 92}\n\n'
      f"المصدر: {source_name}\n"
      f"العنوان الأصلي: {title}\n"
      f"متن الخبر: {snippet[:2000]}"
  )

  txt = _call_gemini_rest_or_sdk(prompt, str(api_key).strip())
  if txt:
    try:
      m = re.search(r"\{.*\}", txt, re.DOTALL)
      if m:
        parsed = json.loads(m.group(0))
        ai_title = clean_display_text(parsed.get("translated_title"))
        ai_sum = clean_display_text(parsed.get("summary"))
        final_t = ai_title if (ai_title and _is_predominantly_arabic(ai_title) and len(ai_title) >= 8) else arabic_title_fallback
        final_s = ai_sum if (ai_sum and _is_predominantly_arabic(ai_sum) and not is_summary_just_title(title, ai_sum)) else fallback_summary
        return {
            "translated_title": final_t,
            "summary": final_s,
            "sentiment": clean_display_text(parsed.get("sentiment")) or "محايد",
            "category": clean_display_text(parsed.get("category")) or detected_topic,
            "relevance_score": int(parsed.get("relevance_score", 90)),
        }
      else:
        plain_ai = clean_display_text(txt)
        if len(plain_ai) > 40 and _is_predominantly_arabic(plain_ai) and not is_summary_just_title(title, plain_ai):
          default_result["summary"] = plain_ai
    except Exception:
      pass

  return default_result


def _persist_translated_article_to_db(item: dict, ar_title: str, ar_summary: str):
  """حفظ العنوان والملخص المعرّبين في قاعدة البيانات كي لا يُعاد طلبهما أو يظهرا بلغة أجنبية لاحقاً."""
  art_id = item.get("id")
  if not art_id:
    return
  if ar_title == item.get("title") and ar_summary == item.get("summary"):
    return
  item["title"] = ar_title
  item["summary"] = ar_summary
  try:
    lock = get_db_lock()
    with lock:
      conn = _open_sqlite_conn()
      c = conn.cursor()
      c.execute(
          "UPDATE articles SET title = ?, summary = ? WHERE id = ?",
          (ar_title, ar_summary, art_id),
      )
      conn.commit()
      conn.close()
  except Exception:
    pass


def _translate_via_gemini_fallback(foreign_title: str, foreign_body: str, source_name: str, is_intl: bool) -> tuple:
  """مسار احتياطي عبر Gemini API عند تعذر محركات الترجمة المجانية."""
  try:
    api_key = (load_credentials().get("gemini_api_key") or DEFAULT_GEMINI_API_KEY or "").strip()
    if not api_key:
      return "", ""
    extra_ma = " وإبراز ما يخص المغرب في صدارة الملخص إذا أشار النص للمغرب" if is_intl else ""
    prompt = (
        f"ترجم العنوان التالي إلى العربية الفصحى ولخّص الخبر في جملتين بالعربية الفصحى{extra_ma}. "
        'أرجع JSON فقط: {"title": "...", "summary": "..."}\n'
        f"المصدر: {source_name}\nالعنوان: {foreign_title}\nالنص: {foreign_body[:1000]}"
    )
    txt = _call_gemini_rest_or_sdk(prompt, api_key)
    if txt:
      m = re.search(r"\{.*\}", txt, re.DOTALL)
      if m:
        parsed = json.loads(m.group(0))
        return clean_display_text(parsed.get("title")), clean_display_text(parsed.get("summary"))
  except Exception:
    pass
  return "", ""


def _translate_foreign_title_instant_local(foreign_title: str, source_name: str = "", country_lbl: str = "") -> str:
  """ترجمة فورية محلية (0ms) بدون انتظار الشبكة لضمان سرعة تحميل الصفحة."""
  txt = clean_display_text(foreign_title or "")
  if not txt or _is_predominantly_arabic(txt):
    return txt
  cache_Hit = _TRANSLATION_CACHE.get(f"auto::{txt[:300]}")
  if cache_Hit and _is_predominantly_arabic(cache_Hit):
    return cache_Hit
  low = txt.lower()
  matched_terms = []
  for term_raw, ar_term in sorted(COMPREHENSIVE_FR_ES_TRANSLATIONS.items(), key=lambda x: len(x[0]), reverse=True):
    if term_raw in low:
      matched_terms.append(ar_term)
      low = low.replace(term_raw, " ")
      if len(matched_terms) >= 4:
        break
  if matched_terms:
    return " — ".join(matched_terms[:3])
  return f"تغطية إعلامية عبر {source_name or 'الصحافة الدولية'}" + (f" ({country_lbl})" if country_lbl else "")


def _ensure_arabic_title_and_summary(item: dict, fast_render: bool = False) -> tuple:
  """ضمان تعريب العنوان والملخص إجبارياً 100% إلى العربية قبل العرض في الويب أو الإرسال إلى بوت تلغرام (النسخة الأصلية تبقى في رابط المصدر)."""
  orig_t = clean_display_text(item.get("title") or "")
  orig_s = clean_display_text(item.get("summary") or "")
  raw_title = orig_t
  raw_summary = orig_s
  raw_snip = clean_display_text(item.get("raw_snippet") or "")
  plat = clean_display_text(item.get("platform") or "الصحف")
  raw_src = clean_display_text(item.get("source_name") or plat)
  is_intl_plat = (plat == "صحافة دولية")

  c_lbl, _ = detect_article_country_and_topic(orig_t, raw_snip, item.get("url", ""), raw_src, plat)

  if fast_render:
    if raw_title and not _is_predominantly_arabic(raw_title):
      raw_title = _translate_foreign_title_instant_local(raw_title, raw_src, c_lbl)
    if not raw_summary or not _is_predominantly_arabic(raw_summary):
      cached_s = _TRANSLATION_CACHE.get(f"auto::{(raw_snip or orig_s)[:300]}")
      if cached_s and _is_predominantly_arabic(cached_s):
        raw_summary = cached_s
      else:
        local_s = _translate_foreign_title_instant_local(raw_snip or orig_s, raw_src, c_lbl)
        if item.get("_open_web_kw") or item.get("category") == "رصد حر بالويب":
          raw_summary = f"تغطية منشورة على {raw_src} ({c_lbl}) حول: {raw_title}."
        elif _has_morocco_reference(f"{orig_t} {raw_snip} {orig_s}") and is_intl_plat:
          raw_summary = f"يتناول هذا التقرير الصادر عن {raw_src} ({c_lbl}) مستجدات قضائية تتعلق بالمغرب حول: {raw_title}."
        else:
          raw_summary = f"تقرير إعلامي صادر عن {raw_src} ({c_lbl}) يتناول: {local_s}."
  else:
    if raw_title and not _is_predominantly_arabic(raw_title):
      tr_t = translate_foreign_title_to_arabic_rulebased(raw_title)
      if tr_t and _is_predominantly_arabic(tr_t):
        raw_title = tr_t

    generic_markers = (
        "أفادت تقارير صادرة عن",
        "تفيد المعطيات الواردة عبر",
        "متابعة إعلامية وقضائية دولية",
        "متابعة قضائية دولية: مستجدات",
        "تقرير قضائي دولي:",
    )
    if (
        not raw_summary
        or is_summary_just_title(raw_title, raw_summary)
        or not _is_predominantly_arabic(raw_summary)
        or any(gm in raw_summary for gm in generic_markers)
    ):
      if raw_summary and not _is_predominantly_arabic(raw_summary) and len(raw_summary) > 30:
        tr_s_direct = translate_text_to_arabic_live(raw_summary)
        if tr_s_direct and _is_predominantly_arabic(tr_s_direct):
          raw_summary = tr_s_direct
      if not raw_summary or not _is_predominantly_arabic(raw_summary) or any(gm in raw_summary for gm in generic_markers):
        raw_summary = build_extractive_arabic_summary(raw_title, raw_snip or item.get("summary") or "", plat, raw_src)
        if raw_summary and not _is_predominantly_arabic(raw_summary):
          tr_s = translate_text_to_arabic_live(raw_summary)
          if tr_s and _is_predominantly_arabic(tr_s):
            raw_summary = tr_s

    if (raw_title and not _is_predominantly_arabic(raw_title)) or (not raw_summary or not _is_predominantly_arabic(raw_summary)):
      gem_t, gem_s = _translate_via_gemini_fallback(orig_t, raw_snip or orig_s, raw_src, is_intl_plat)
      if gem_t and _is_predominantly_arabic(gem_t):
        raw_title = gem_t
      if gem_s and _is_predominantly_arabic(gem_s):
        raw_summary = gem_s

  if raw_title and not _is_predominantly_arabic(raw_title):
    c_lbl, _ = detect_article_country_and_topic(orig_t, raw_snip, item.get("url", ""), raw_src, plat)
    if item.get("_open_web_kw") or item.get("category") == "رصد حر بالويب":
      raw_title = f"تغطية عبر {raw_src} ({c_lbl})"
    else:
      raw_title = f"مستجد قضائي في {raw_src} ({c_lbl})"

  if not raw_summary or not _is_predominantly_arabic(raw_summary):
    c_lbl, _ = detect_article_country_and_topic(orig_t, raw_snip, item.get("url", ""), raw_src, plat)
    if is_intl_plat and _has_morocco_reference(f"{orig_t} {raw_snip} {orig_s}"):
      raw_summary = f"تقرير إعلامي صادر عن {raw_src} ({c_lbl}) يتطرق إلى مستجدات قضائية ذات صلة بالمغرب؛ يمكن الاطلاع على النص الكامل بلغته الأصلية عبر رابط المصدر."
    else:
      raw_summary = f"تقرير إعلامي صادر عن {raw_src} ({c_lbl}): {raw_title}."

  if not is_intl_plat:
    raw_title = re.sub(r"\s*\((?:يتطرق للمغرب|يتعلق بالمغرب|يهم المغرب)\)\s*", "", raw_title).strip()
    raw_summary = re.sub(r"^(?:🇲🇦\s*)?(?:\((?:يتعلق بالمغرب|يتطرق للمغرب|يهم المغرب)\)|في سياق يهم المغرب|فيما يتعلق بالمغرب)\s*:?\s*", "", raw_summary).strip()
    if item.get("category") in ("يتطرق للمغرب", "يهم المغرب"):
      item["category"] = "شؤون قضائية ومحاكم"
  else:
    orig_combined = f"{orig_t} {raw_snip} {orig_s} {item.get('category', '')}"
    if _has_morocco_reference(orig_combined):
      if raw_snip and not fast_render:
        focused_ar = translate_foreign_snippet_to_arabic_rulebased(raw_snip, orig_t, raw_src, is_international=True)
        if focused_ar and _is_predominantly_arabic(focused_ar) and any(k in focused_ar for k in ("المغرب", "مغربي", "مغربية", "المغاربة", "الرباط", "الصحراء", "سبتة", "مليلية")):
          raw_summary = focused_ar
      raw_summary = _extract_morocco_focused_sentences_ar(raw_summary, orig_combined, is_international=True)
      if raw_title and not any(k in raw_title for k in ("المغرب", "مغربي", "مغربية", "المغاربة", "الرباط", "الصحراء")):
        raw_title = f"{raw_title} (يتطرق للمغرب)"

  if not fast_render and (orig_t != raw_title or orig_s != raw_summary):
    _persist_translated_article_to_db(item, raw_title, raw_summary)

  return raw_title, raw_summary


def send_telegram_alert(item: dict, cfg: dict) -> bool:
  """إرسال إشعار تلغرام مرة واحدة فقط لكل خبر جديد بتنسيق HTML آمن وأزرار تصنيف تفاعلية."""
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
    ledger.update(item_keys)
    save_telegram_sent_ledger(ledger)

  platform_icons = {
      "الصحف": "📰",
      "صحافة دولية": "🌍",
      "فيسبوك": "🟦",
      "إكس": "⬛",
      "يوتيوب": "🟥",
      "أخرى": "🟪",
  }
  plat_tg = item.get("platform", "الصحف")
  icon = platform_icons.get(plat_tg, "📡")
  target_badge = "🎯 <b>[رصد مخصص]</b>\n" if item.get("is_custom_target") else ""
  monitored_dt = datetime.fromtimestamp(
      float(item.get("created_at") or time.time()), tz=timezone.utc
  ).strftime("%Y-%m-%d %H:%M")
  clean_u = clean_social_post_url(item.get("url", ""))

  country_tag, topic_tag = detect_article_country_and_topic(
      item.get("title", ""), item.get("raw_snippet", ""), clean_u, item.get("source_name", ""), plat_tg
  )
  country_flags = {"المغرب": "🇲🇦", "فرنسا": "🇫🇷", "إسبانيا": "🇪🇸", "الجزائر": "🇩🇿", "دولي": "🌐"}
  c_flag = country_flags.get(country_tag, "🌍")

  ar_title_tg, ar_summary_tg = _ensure_arabic_title_and_summary(item)
  msg_html = (
      f"⚖️ <b>المرصد القضائي</b>\n"
      f"{target_badge}"
      f"{icon} <b>المنصة:</b> {html.escape(plat_tg)} | {c_flag} <b>الدولة:</b> {html.escape(country_tag)}\n"
      f"🗞️ <b>المصدر:</b> {html.escape(str(item.get('source_name', '')))}\n"
      f"📅 <b>تاريخ النشر:</b> {html.escape(str(item.get('pub_date', '')))} | 📡 <b>الرصد:</b> {monitored_dt}\n"
      f"📌 <b>العنوان:</b> {html.escape(ar_title_tg)}\n\n"
      f"📝 <b>الملخص:</b> {html.escape(ar_summary_tg)}\n\n"
      f"🏷️ <b>التصنيف:</b> {html.escape(str(item.get('category', '') or topic_tag))}"
  )

  inline_kb = [
      [
          {"text": "🔗 فتح المصدر الأصلي", "url": clean_u},
          {"text": f"{c_flag} أخبار {country_tag}", "callback_data": {"الولايات المتحدة": "c_us", "فرنسا": "c_fr", "إسبانيا": "c_es", "الجزائر": "c_dz", "دولي": "c_gl"}.get(country_tag, "p_press")}
      ]
  ]

  try:
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": msg_html,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
            "reply_markup": {"inline_keyboard": inline_kb},
        },
        timeout=8,
    )
    return resp.status_code == 200
  except Exception:
    return False


def upgrade_incomplete_existing_articles(cfg: dict, max_upgrades: int = 12):
  lock = get_db_lock()
  to_upgrade = []
  generic_markers = (
      "أفادت تقارير صادرة عن",
      "تفيد المعطيات الواردة عبر",
      "متابعة إعلامية وقضائية دولية",
      "متابعة قضائية دولية: مستجدات",
      "تقرير قضائي دولي:",
      "تقرير قضائي:",
  )
  with lock:
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      conn.row_factory = sqlite3.Row
      c = conn.cursor()
      c.execute(
          "SELECT id, title, summary, source_name, platform, url, raw_snippet, image_url, category "
          "FROM articles ORDER BY pub_timestamp DESC LIMIT 60"
      )
      for r in c.fetchall():
        d = dict(r)
        t_cur = d.get("title", "")
        s_cur = d.get("summary", "")
        missing_img = not (d.get("image_url") or "").strip()
        bad_sum = is_summary_just_title(t_cur, s_cur) or any(gm in s_cur for gm in generic_markers) or (not _is_predominantly_arabic(s_cur))
        foreign_title = not _is_predominantly_arabic(t_cur)
        if missing_img or bad_sum or foreign_title:
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
    new_t = clean_display_text(ai_res.get("translated_title") or item.get("title", ""))
    new_s = clean_display_text(ai_res.get("summary") or item.get("summary", ""))
    if new_t:
      item["title"] = new_t
    if new_s:
      item["summary"] = new_s
    if ai_res.get("category"):
      item["category"] = ai_res["category"]
    upgraded_records.append(item)

  if upgraded_records:
    with lock:
      try:
        conn = _open_sqlite_conn()
        c = conn.cursor()
        for rec in upgraded_records:
          c.execute(
              "UPDATE articles SET title = ?, summary = ?, category = ?, image_url = ?, raw_snippet = ?, url = ? WHERE id = ?",
              (
                  rec["title"],
                  rec["summary"],
                  rec.get("category", "شؤون قضائية"),
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


def _send_telegram_batch_digest_bulletin(newly_added: list, cfg: dict):
  """إرسال بطاقة ملخص مصنفة بأزرار تفاعلية لكل وسيلة ودولة فور رصد أخبار جديدة."""
  if not newly_added:
    return
  token = (cfg.get("telegram_bot_token") or DEFAULT_TG_TOKEN).strip()
  chat_id = (cfg.get("telegram_chat_id") or DEFAULT_TG_CHAT_ID).strip()
  if not token or not chat_id:
    return

  c_press = len([x for x in newly_added if x.get("platform") == "الصحف"])
  c_intl = len([x for x in newly_added if x.get("platform") == "صحافة دولية"])
  c_fb = len([x for x in newly_added if x.get("platform") == "فيسبوك"])
  c_x = len([x for x in newly_added if x.get("platform") == "إكس"])
  c_yt = len([x for x in newly_added if x.get("platform") == "يوتيوب"])

  bulletin_lines = [
      "⚖️ *المرصد القضائي — موجز المستجدات الجديد*",
      f"📡 تم رصد وتوثيق *{len(newly_added)}* خبر ومستجد قضائي جديد:",
  ]
  if c_press:
    bulletin_lines.append(f"• 📰 *الصحافة المغربية:* {c_press} مقال")
  if c_intl:
    bulletin_lines.append(f"• 🌍 *الصحافة الدولية:* {c_intl} مقال")
  if c_fb:
    bulletin_lines.append(f"• 🟦 *فيسبوك:* {c_fb} منشور")
  if c_x:
    bulletin_lines.append(f"• ⬛ *إكس (تويتر):* {c_x} تغريدة")
  if c_yt:
    bulletin_lines.append(f"• 🟥 *يوتيوب:* {c_yt} فيديو")

  bulletin_lines.append("\n👇 *تصفح الأخبار مصنفة حسب الوسيلة والدولة عبر الأزرار أدناه:*")

  inline_kb = [
      [
          {"text": f"📰 الصحف ({c_press})", "callback_data": "p_press"},
          {"text": f"🌍 القائمة الفرعية للدولية ({c_intl})", "callback_data": "menu_intl"}
      ],
      [
          {"text": "🇺🇸 أمريكا", "callback_data": "c_us"},
          {"text": "🇫🇷 فرنسا", "callback_data": "c_fr"},
          {"text": "🇪🇸 إسبانيا", "callback_data": "c_es"},
          {"text": "🇩🇿 الجزائر", "callback_data": "c_dz"}
      ],
      [
          {"text": f"🟦 فيسبوك ({c_fb})", "callback_data": "p_fb"},
          {"text": f"⬛ إكس ({c_x})", "callback_data": "p_x"},
          {"text": f"🟥 يوتيوب ({c_yt})", "callback_data": "p_yt"}
      ],
      [
          {"text": "⚡ تشغيل رصد فوري الآن", "callback_data": "action_run_scan"},
          {"text": "🔙 القائمة الرئيسية", "callback_data": "menu_main"}
      ]
  ]

  try:
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "\n".join(bulletin_lines),
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": inline_kb},
        },
        timeout=8,
    )
  except Exception:
    pass


def _get_all_articles_for_bot() -> list:
  """جلب كافة المقالات من قاعدة البيانات والأرشيف مع التطبيع لضمان عدم فراغ أي تصنيف في البوت."""
  try:
    arts = fetch_articles_from_db()
    if arts:
      for a in arts:
        normalize_press_platform_and_source(a)
      return arts
  except Exception:
    pass
  # احتياطي مباشر من ملف الأرشيف JSON
  if os.path.exists(ARCHIVE_JSON_FILE):
    try:
      with open(ARCHIVE_JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
      if isinstance(data, list):
        for a in data:
          if isinstance(a, dict):
            normalize_press_platform_and_source(a)
        return [a for a in data if isinstance(a, dict)]
    except Exception:
      pass
  return []


# =====================================================================
# محرك التقرير اليومي التركيبي والمخصص (21:00) وتصدير PDF / Word وجولة في الصحافة لتلغرام
# =====================================================================
def _get_morocco_now() -> datetime:
  """إرجاع التوقيت المحلي الحالي بالمغرب (Africa/Casablanca أو UTC+1)."""
  try:
    if ZoneInfo is not None:
      return datetime.now(ZoneInfo("Africa/Casablanca"))
  except Exception:
    pass
  return datetime.now(timezone(timedelta(hours=1)))


def _select_daily_composite_articles(all_arts: list, max_hours: int = 24) -> list:
  """انتقاء أهم الأخبار الوطنية والدولية (القضاء والعدالة وما يتطرق للمغرب) خلال آخر 24 ساعة."""
  now_ts = time.time()
  recent = []
  for a in all_arts:
    if not isinstance(a, dict):
      continue
    if a.get("category") == "رصد حر بالويب":
      continue
    pub_t = float(a.get("pub_timestamp") or a.get("created_at") or 0)
    mon_t = float(a.get("created_at") or pub_t)
    if (now_ts - min(pub_t, mon_t)) <= max_hours * 3600 or (now_ts - mon_t) <= max_hours * 3600:
      recent.append(a)
  # في حال كان عدد أخبار آخر 24 ساعة قليلاً جداً، نأخذ أحدث 20 خبراً متاحاً في القاعدة
  pool = recent if len(recent) >= 3 else [a for a in all_arts if isinstance(a, dict) and a.get("category") != "رصد حر بالويب"][:25]
  pool.sort(key=lambda x: float(x.get("pub_timestamp") or x.get("created_at") or 0), reverse=True)
  return pool


def _generate_executive_synthesis_ar(national_items: list, intl_items: list, morocco_intl_items: list, cfg: dict, report_mode_label: str) -> str:
  """توليد خلاصة تركيبية مهنية باللغة العربية الفصحى عبر Gemini AI مع بديل تركيبي حتمي."""
  sample_lines = []
  for it in (national_items[:8] + morocco_intl_items[:6] + intl_items[:6]):
    t_ar, s_ar = _ensure_arabic_title_and_summary(it, fast_render=True)
    sample_lines.append(f"- [{it.get('platform', '')} | {it.get('source_name', '')}] {t_ar}: {s_ar[:180]}")

  api_key = (cfg.get("gemini_api_key") or "").strip() if isinstance(cfg, dict) else ""
  if api_key and sample_lines:
    prompt = (
        "أنت محرر صحفي وقضائي محترف في «المرصد القضائي».\n"
        f"صُغ خلاصة تركيبية مهنية وموجزة (فقرتان إلى ثلاث فقرات بالعربية الفصحى السليمة، بدون رموز ماركداون مثل * أو #) "
        f"بمثابة جولة في الصحافة لـ ({report_mode_label})، تجمع أبرز المستجدات القضائية الوطنية في المغرب "
        "وأهم ما تناولته الصحافة الدولية حول القضاء أو ما يتطرق للمغرب، مع إبراز القضايا والمحاكم والاتجاهات المشتركة:\n\n"
        + "\n".join(sample_lines[:18])
    )
    ai_txt = _call_gemini_rest_or_sdk(prompt, api_key)
    if ai_txt and _is_predominantly_arabic(ai_txt) and len(ai_txt) >= 60:
      cleaned_ai = re.sub(r"[*#`]+", "", ai_txt).strip()
      return cleaned_ai

  # بديل تركيبي حتمي ومنظم عند عدم توفر Gemini
  parts = []
  if national_items:
    top_nat_titles = "، و".join(_ensure_arabic_title_and_summary(x, fast_render=True)[0][:90] for x in national_items[:3])
    parts.append(
        f"على الصعيد الوطني، رصدت المنصة {len(national_items)} مستجداً قضائياً عبر الصحافة والمواقع المغربية، "
        f"تصدرتها مواضيع: {top_nat_titles}."
    )
  if morocco_intl_items:
    top_ma_intl = "، و".join(_ensure_arabic_title_and_summary(x, fast_render=True)[0][:90] for x in morocco_intl_items[:3])
    parts.append(
        f"وفي الصحافة الدولية المتطرقة للمغرب، تم توثيق {len(morocco_intl_items)} تغطية إعلامية بارزة، "
        f"من أبرزها: {top_ma_intl}."
    )
  elif intl_items:
    top_intl = "، و".join(_ensure_arabic_title_and_summary(x, fast_render=True)[0][:90] for x in intl_items[:3])
    parts.append(
        f"وعلى مستوى القضاء الدولي والصحافة الأجنبية، جرى رصد {len(intl_items)} مقالاً وتقريراً، "
        f"أبرزها: {top_intl}."
    )
  if not parts:
    return "تم إعداد هذا التقرير بناءً على المعطيات المتاحة حالياً في قاعدة بيانات المرصد القضائي."
  return " ".join(parts)


def build_daily_report_data(
    articles: list,
    cfg: dict,
    report_type: str = "composite",
    filter_summary: str = "",
) -> dict:
  """بناء البنية الكاملة للتقرير اليومي (تركيبي شامل أو مخصص حسب الفلاتر)."""
  ma_now = _get_morocco_now()
  date_str = ma_now.strftime("%Y-%m-%d")
  time_str = ma_now.strftime("%H:%M")

  if report_type == "composite":
    working = _select_daily_composite_articles(articles, max_hours=24)
    title = f"التقرير اليومي التركيبي — جولة في الصحافة ({date_str})"
    subtitle = "تقرير مركب لأهم المستجدات القضائية الوطنية والدولية وما يتطرق للمغرب (إصدار الساعة 21:00)"
  else:
    working = list(articles or [])
    title = f"تقرير رصد مخصص — المرصد القضائي ({date_str})"
    subtitle = filter_summary or "تقرير مخصص بناءً على معايير الفلترة المختارة في المنصة"

  national_items = []
  morocco_intl_items = []
  other_intl_items = []
  social_items = []

  for raw_a in working:
    a = dict(raw_a)
    normalize_press_platform_and_source(a)
    plat = a.get("platform", "الصحف")
    ar_t, ar_s = _ensure_arabic_title_and_summary(a, fast_render=True)
    a["_ar_title"] = ar_t
    a["_ar_summary"] = ar_s
    c_tag, t_tag = detect_article_country_and_topic(
        a.get("title", ""), a.get("raw_snippet", ""), a.get("url", ""), a.get("source_name", ""), plat
    )
    a["_country"] = c_tag
    a["_topic"] = t_tag

    if plat == "الصحف":
      national_items.append(a)
    elif plat == "صحافة دولية":
      if t_tag == "يتطرق للمغرب" or a.get("category") == "يتطرق للمغرب" or _has_morocco_reference(f"{ar_t} {ar_s}"):
        morocco_intl_items.append(a)
      else:
        other_intl_items.append(a)
    else:
      social_items.append(a)

  synthesis = _generate_executive_synthesis_ar(
      national_items, other_intl_items, morocco_intl_items, cfg, title
  )

  return {
      "title": title,
      "subtitle": subtitle,
      "report_type": report_type,
      "date_str": date_str,
      "time_str": time_str,
      "filter_summary": filter_summary,
      "synthesis": synthesis,
      "total_count": len(working),
      "national_items": national_items[:25],
      "morocco_intl_items": morocco_intl_items[:20],
      "other_intl_items": other_intl_items[:15],
      "social_items": social_items[:15],
  }


def generate_report_html(report_data: dict) -> str:
  """توليد نسخة HTML احترافية منسقة للطباعة وتصدير PDF بدعم كامل للغة العربية RTL."""
  def _render_sec(sec_title: str, items: list, accent_hex: str) -> str:
    if not items:
      return ""
    blocks = []
    for idx, it in enumerate(items, 1):
      t_safe = html.escape(it.get("_ar_title") or it.get("title") or "")
      s_safe = html.escape(it.get("_ar_summary") or it.get("summary") or "")
      src_safe = html.escape(clean_display_text(it.get("source_name") or it.get("platform") or ""))
      dt_safe = html.escape(clean_display_text(it.get("pub_date") or ""))
      cnt_safe = html.escape(clean_display_text(it.get("_country") or ""))
      u_safe = html.escape(clean_social_post_url(it.get("url") or "#"), quote=True)
      blocks.append(f"""
      <div class="item-card" style="border-right:4px solid {accent_hex};">
        <div class="item-meta">
          <span class="badge">{idx}</span>
          <strong>{src_safe}</strong>
          <span>• {cnt_safe}</span>
          <span dir="ltr">• {dt_safe}</span>
        </div>
        <div class="item-title"><a href="{u_safe}">{t_safe}</a></div>
        <div class="item-summary">{s_safe}</div>
        <div class="item-url"><a href="{u_safe}">{u_safe}</a></div>
      </div>
      """)
    return f"""
    <section class="report-sec">
      <h2 class="sec-title" style="border-right:5px solid {accent_hex};">{html.escape(sec_title)} ({len(items)})</h2>
      {''.join(blocks)}
    </section>
    """

  sec_nat = _render_sec("أولاً: أبرز أخبار القضاء والعدالة في الصحافة الوطنية المغربية", report_data["national_items"], "#059669")
  sec_ma_intl = _render_sec("ثانياً: الصحافة الدولية — الأخبار المتطرقة للمغرب", report_data["morocco_intl_items"], "#b45309")
  sec_intl = _render_sec("ثالثاً: مستجدات القضاء الدولي والصحافة الأجنبية", report_data["other_intl_items"], "#0369a1")
  sec_soc = _render_sec("رابعاً: رصد المنصات الرقمية وشبكات التواصل", report_data["social_items"], "#6d28d9")

  filter_badge = (
      f'<div class="filter-strip"><strong>معايير التصفية المطبقة:</strong> {html.escape(report_data["filter_summary"])}</div>'
      if report_data.get("filter_summary")
      else ""
  )

  return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8" />
<title>{html.escape(report_data['title'])}</title>
<style>
  @page {{ size: A4; margin: 16mm 14mm; }}
  body {{
    font-family: 'DejaVu Sans', 'Cairo', 'Tahoma', Arial, sans-serif;
    direction: rtl;
    text-align: right;
    color: #0f172a;
    background: #ffffff;
    margin: 0;
    padding: 0;
    line-height: 1.65;
    font-size: 10.5pt;
  }}
  .cover-header {{
    background: #071920;
    color: #ffffff;
    padding: 18px 22px;
    border-radius: 10px;
    border-bottom: 4px solid #d4af37;
    margin-bottom: 14px;
  }}
  .cover-brand {{ font-size: 11pt; color: #f3e5ab; font-weight: 700; margin-bottom: 4px; }}
  .cover-title {{ font-size: 16pt; font-weight: 900; margin: 0 0 6px 0; color: #ffffff; }}
  .cover-sub {{ font-size: 9.5pt; color: #cbd5e1; margin: 0; }}
  .kpi-table {{ width: 100%; border-collapse: separate; border-spacing: 6px; margin-bottom: 14px; }}
  .kpi-cell {{
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    border-top: 3px solid #0b2229;
    border-radius: 8px;
    padding: 8px 6px;
    text-align: center;
    width: 25%;
  }}
  .kpi-num {{ font-size: 15pt; font-weight: 900; color: #071920; }}
  .kpi-lbl {{ font-size: 8.5pt; color: #475569; font-weight: 700; }}
  .filter-strip {{
    background: #fef9c3;
    border: 1px solid #eab308;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 9pt;
    margin-bottom: 12px;
  }}
  .synthesis-box {{
    background: #f0fdfa;
    border: 1px solid #99f6e4;
    border-right: 5px solid #0d9488;
    border-radius: 8px;
    padding: 12px 15px;
    margin-bottom: 16px;
  }}
  .synthesis-title {{ font-size: 11.5pt; font-weight: 900; color: #0f766e; margin: 0 0 6px 0; }}
  .sec-title {{
    font-size: 12pt;
    font-weight: 900;
    color: #071920;
    background: #f1f5f9;
    padding: 7px 12px;
    border-radius: 6px;
    margin: 14px 0 10px 0;
  }}
  .item-card {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 9px;
    page-break-inside: avoid;
  }}
  .item-meta {{ font-size: 8.5pt; color: #475569; margin-bottom: 4px; }}
  .badge {{
    display: inline-block;
    background: #071920;
    color: #f3e5ab;
    padding: 1px 7px;
    border-radius: 10px;
    font-weight: 700;
    margin-left: 6px;
  }}
  .item-title {{ font-size: 10.5pt; font-weight: 800; color: #0f172a; margin-bottom: 4px; }}
  .item-title a {{ color: #0f172a; text-decoration: none; }}
  .item-summary {{ font-size: 9.5pt; color: #334155; margin-bottom: 4px; }}
  .item-url {{ font-size: 7.5pt; color: #0284c7; word-break: break-all; direction: ltr; text-align: left; }}
  .item-url a {{ color: #0284c7; text-decoration: none; }}
  .footer {{
    margin-top: 18px;
    padding-top: 8px;
    border-top: 1px solid #cbd5e1;
    font-size: 8.5pt;
    color: #64748b;
    text-align: center;
  }}
</style>
</head>
<body>
  <div class="cover-header">
    <div class="cover-brand">⚖️ المرصد القضائي — التقرير الإعلامي والقضائي</div>
    <h1 class="cover-title">{html.escape(report_data['title'])}</h1>
    <p class="cover-sub">{html.escape(report_data['subtitle'])} • تاريخ الإصدار: {html.escape(report_data['date_str'])} على الساعة {html.escape(report_data['time_str'])}</p>
  </div>

  <table class="kpi-table">
    <tr>
      <td class="kpi-cell"><div class="kpi-num">{report_data['total_count']}</div><div class="kpi-lbl">إجمالي الأخبار المشمولة</div></td>
      <td class="kpi-cell"><div class="kpi-num">{len(report_data['national_items'])}</div><div class="kpi-lbl">الصحافة الوطنية المغربية</div></td>
      <td class="kpi-cell"><div class="kpi-num">{len(report_data['morocco_intl_items'])}</div><div class="kpi-lbl">دولية تتطرق للمغرب</div></td>
      <td class="kpi-cell"><div class="kpi-num">{len(report_data['other_intl_items']) + len(report_data['social_items'])}</div><div class="kpi-lbl">قضاء دولي ومنصات رقمية</div></td>
    </tr>
  </table>

  {filter_badge}

  <div class="synthesis-box">
    <div class="synthesis-title">📌 الخلاصة التركيبية (جولة في الصحافة)</div>
    <div>{html.escape(report_data['synthesis']).replace(chr(10), '<br/>')}</div>
  </div>

  {sec_nat}
  {sec_ma_intl}
  {sec_intl}
  {sec_soc}

  <div class="footer">صدر آلياً عن منصة المرصد القضائي • {html.escape(report_data['date_str'])} {html.escape(report_data['time_str'])}</div>
</body>
</html>"""


def generate_report_pdf_bytes(report_data: dict) -> tuple:
  """توليد ملف PDF احترافي بدعم كامل للعربية عبر WeasyPrint، مع بديل HTML جاهز للطباعة إن لم تكن WeasyPrint مثبتة."""
  report_html = generate_report_html(report_data)
  try:
    import weasyprint
    pdf_bytes = weasyprint.HTML(string=report_html).write_pdf()
    if pdf_bytes and pdf_bytes[:4] == b"%PDF":
      return pdf_bytes, "application/pdf", f"marsad_report_{report_data['date_str']}.pdf"
  except Exception:
    pass
  return report_html.encode("utf-8"), "text/html", f"marsad_report_{report_data['date_str']}_printable.html"


def _xml_escape_docx(text: str) -> str:
  return (
      str(text or "")
      .replace("&", "&amp;")
      .replace("<", "&lt;")
      .replace(">", "&gt;")
      .replace('"', "&quot;")
      .replace("'", "&apos;")
  )


def generate_report_docx_bytes(report_data: dict) -> bytes:
  """توليد ملف Word (.docx) احترافي باتجاه RTL كامل عبر python-docx، مع محرك OOXML مدمج كبديل مضمون بدون مكتبات خارجية."""
  try:
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor

    doc = docx.Document()

    def _set_rtl_para(p_obj):
      p_obj.alignment = WD_ALIGN_PARAGRAPH.RIGHT
      pPr = p_obj._p.get_or_add_pPr()
      bidi = OxmlElement("w:bidi")
      pPr.append(bidi)

    def _add_ar_para(text: str, bold: bool = False, size_pt: int = 11, color_rgb=(15, 23, 42), space_after: int = 4):
      p_o = doc.add_paragraph()
      _set_rtl_para(p_o)
      p_o.paragraph_format.space_after = Pt(space_after)
      run = p_o.add_run(text)
      run.bold = bold
      run.font.name = "Arial"
      run.font.size = Pt(size_pt)
      run.font.color.rgb = RGBColor(*color_rgb)
      rPr = run._r.get_or_add_rPr()
      rtl_el = OxmlElement("w:rtl")
      rPr.append(rtl_el)
      return p_o

    _add_ar_para("⚖️ المرصد القضائي — التقرير الإعلامي والقضائي", bold=True, size_pt=12, color_rgb=(180, 130, 20), space_after=2)
    _add_ar_para(report_data["title"], bold=True, size_pt=16, color_rgb=(7, 25, 32), space_after=4)
    _add_ar_para(
        f"{report_data['subtitle']} | التاريخ: {report_data['date_str']} — الساعة: {report_data['time_str']}",
        bold=False, size_pt=10, color_rgb=(71, 85, 105), space_after=8
    )

    if report_data.get("filter_summary"):
      _add_ar_para(f"معايير التصفية: {report_data['filter_summary']}", bold=True, size_pt=10, color_rgb=(146, 64, 14), space_after=6)

    # جدول المؤشرات الموجز
    tbl = doc.add_table(rows=2, cols=4)
    tbl.style = "Table Grid"
    headers_k = ["إجمالي الأخبار", "الصحافة الوطنية", "دولية عن المغرب", "قضاء دولي ومنصات"]
    vals_k = [
        str(report_data["total_count"]),
        str(len(report_data["national_items"])),
        str(len(report_data["morocco_intl_items"])),
        str(len(report_data["other_intl_items"]) + len(report_data["social_items"])),
    ]
    for ci in range(4):
      c0 = tbl.rows[0].cells[ci].paragraphs[0]
      _set_rtl_para(c0)
      r0 = c0.add_run(headers_k[ci])
      r0.bold = True
      r0.font.size = Pt(10)
      c1 = tbl.rows[1].cells[ci].paragraphs[0]
      _set_rtl_para(c1)
      r1 = c1.add_run(vals_k[ci])
      r1.bold = True
      r1.font.size = Pt(12)

    _add_ar_para("📌 الخلاصة التركيبية (جولة في الصحافة)", bold=True, size_pt=13, color_rgb=(13, 148, 136), space_after=4)
    _add_ar_para(report_data["synthesis"], bold=False, size_pt=11, color_rgb=(30, 41, 59), space_after=10)

    sections = [
        ("أولاً: أبرز أخبار القضاء والعدالة في الصحافة الوطنية المغربية", report_data["national_items"]),
        ("ثانياً: الصحافة الدولية — الأخبار المتطرقة للمغرب", report_data["morocco_intl_items"]),
        ("ثالثاً: مستجدات القضاء الدولي والصحافة الأجنبية", report_data["other_intl_items"]),
        ("رابعاً: رصد المنصات الرقمية وشبكات التواصل", report_data["social_items"]),
    ]
    for sec_title, items_s in sections:
      if not items_s:
        continue
      _add_ar_para(f"{sec_title} ({len(items_s)})", bold=True, size_pt=13, color_rgb=(7, 25, 32), space_after=5)
      for idx, it in enumerate(items_s, 1):
        t_ar = it.get("_ar_title") or it.get("title") or ""
        s_ar = it.get("_ar_summary") or it.get("summary") or ""
        src_n = clean_display_text(it.get("source_name") or it.get("platform") or "")
        pub_d = clean_display_text(it.get("pub_date") or "")
        u_clean = clean_social_post_url(it.get("url") or "")
        _add_ar_para(f"{idx}. {t_ar}", bold=True, size_pt=11, color_rgb=(15, 23, 42), space_after=2)
        _add_ar_para(f"المصدر: {src_n} | التاريخ: {pub_d}", bold=False, size_pt=9, color_rgb=(100, 116, 139), space_after=2)
        _add_ar_para(f"الملخص: {s_ar}", bold=False, size_pt=10, color_rgb=(51, 65, 85), space_after=2)
        if u_clean:
          _add_ar_para(f"الرابط: {u_clean}", bold=False, size_pt=8, color_rgb=(2, 132, 199), space_after=6)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
  except Exception:
    # بديل OOXML نقي ببايثون القياسية لضمان عمل التصدير إلى Word حتى بدون python-docx
    paras_xml = []
    def _mk_p(txt, bold=False, sz=22):
      b_tag = "<w:b/>" if bold else ""
      return (
          f'<w:p><w:pPr><w:bidi/><w:jc w:val="right"/></w:pPr>'
          f'<w:r><w:rPr><w:rtl/>{b_tag}<w:sz w:val="{sz}"/></w:rPr>'
          f'<w:t xml:space="preserve">{_xml_escape_docx(txt)}</w:t></w:r></w:p>'
      )
    paras_xml.append(_mk_p(report_data["title"], bold=True, sz=32))
    paras_xml.append(_mk_p(f"{report_data['subtitle']} ({report_data['date_str']} {report_data['time_str']})", sz=20))
    paras_xml.append(_mk_p("الخلاصة التركيبية:", bold=True, sz=26))
    paras_xml.append(_mk_p(report_data["synthesis"], sz=22))
    for sec_lbl, lst in [
        ("الصحافة الوطنية المغربية", report_data["national_items"]),
        ("الصحافة الدولية المتطرقة للمغرب", report_data["morocco_intl_items"]),
        ("القضاء الدولي والصحافة الأجنبية", report_data["other_intl_items"]),
        ("المنصات الرقمية", report_data["social_items"]),
    ]:
      if not lst:
        continue
      paras_xml.append(_mk_p(f"{sec_lbl} ({len(lst)})", bold=True, sz=26))
      for i, it in enumerate(lst, 1):
        paras_xml.append(_mk_p(f"{i}. {it.get('_ar_title') or it.get('title', '')}", bold=True, sz=22))
        paras_xml.append(_mk_p(f"الملخص: {it.get('_ar_summary') or it.get('summary', '')}", sz=20))
        paras_xml.append(_mk_p(f"المصدر: {it.get('source_name', '')} | {it.get('url', '')}", sz=18))

    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{"".join(paras_xml)}<w:sectPr/></w:body></w:document>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
      zf.writestr("[Content_Types].xml", content_types)
      zf.writestr("_rels/.rels", rels_xml)
      zf.writestr("word/document.xml", doc_xml)
    return buf.getvalue()


def send_telegram_daily_press_review(
    chat_id: str,
    token: str,
    articles_pool: list = None,
    cfg: dict = None,
    report_type: str = "composite",
    filter_summary: str = "",
) -> bool:
  """إرسال التقرير اليومي «جولة في الصحافة» إلى بوت التلغرام بتنسيق منظم ومقسم بذكاء دون تجاوز حد تلغرام."""
  if not token or not chat_id:
    return False
  cfg = cfg if isinstance(cfg, dict) else load_credentials()
  pool = articles_pool if articles_pool is not None else _get_all_articles_for_bot()
  rep = build_daily_report_data(pool, cfg, report_type=report_type, filter_summary=filter_summary)

  header = (
      f"🗞️ <b>جولة في الصحافة — المرصد القضائي</b>\n"
      f"📅 <b>التاريخ:</b> {html.escape(rep['date_str'])} | 🕘 <b>الساعة:</b> {html.escape(rep['time_str'])}\n"
      f"📊 <b>الإحصائيات:</b> {rep['total_count']} خبر "
      f"(وطنية: {len(rep['national_items'])} • دولية عن المغرب: {len(rep['morocco_intl_items'])} • دولية أخرى: {len(rep['other_intl_items'])})\n"
      f"━━━━━━━━━━━━━━━━━━\n"
      f"📌 <b>الخلاصة التركيبية:</b>\n{html.escape(rep['synthesis'][:950])}"
  )

  chunks = [header]

  def _append_section_chunks(sec_header: str, items_list: list, limit: int = 6):
    if not items_list:
      return
    cur = f"<b>{html.escape(sec_header)}</b>"
    for idx, it in enumerate(items_list[:limit], 1):
      t_ar = html.escape((it.get("_ar_title") or it.get("title") or "")[:140])
      s_ar = html.escape((it.get("_ar_summary") or it.get("summary") or "")[:170])
      src_n = html.escape(clean_display_text(it.get("source_name") or it.get("platform") or ""))
      u_c = html.escape(clean_social_post_url(it.get("url") or "#"), quote=True)
      block = f'\n\n<b>{idx}.</b> <a href="{u_c}">{t_ar}</a>\n📝 {s_ar}\n🗞️ <i>{src_n}</i>'
      if len(cur) + len(block) > 3600:
        chunks.append(cur)
        cur = f"<b>{html.escape(sec_header)} (تتمة)</b>" + block
      else:
        cur += block
    if cur:
      chunks.append(cur)

  _append_section_chunks("📰 أولاً: أبرز عناوين الصحافة الوطنية المغربية", rep["national_items"], limit=6)
  _append_section_chunks("🇲🇦 ثانياً: الصحافة الدولية — ما يتطرق للمغرب", rep["morocco_intl_items"], limit=6)
  _append_section_chunks("🌍 ثالثاً: القضاء الدولي والصحافة الأجنبية", rep["other_intl_items"], limit=4)

  ok_any = False
  total_chunks = len(chunks)
  for c_idx, ch_txt in enumerate(chunks, 1):
    payload = {
        "chat_id": chat_id,
        "text": ch_txt[:3950],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if c_idx == total_chunks:
      payload["reply_markup"] = {
          "inline_keyboard": [
              [
                  {"text": "📰 الصحف الوطنية", "callback_data": "p_press"},
                  {"text": "🇲🇦 دولية عن المغرب", "callback_data": "t_ma"},
              ],
              [
                  {"text": "🔄 تحديث الجولة الصحفية", "callback_data": "action_daily_report"},
                  {"text": "🔙 القائمة الرئيسية", "callback_data": "menu_main"},
              ],
          ]
      }
    try:
      resp = requests.post(
          f"https://api.telegram.org/bot{token}/sendMessage",
          json=payload,
          timeout=8,
      )
      if resp.status_code == 200:
        ok_any = True
    except Exception:
      pass
  return ok_any


def check_and_run_scheduled_daily_report() -> bool:
  """التحقق من بلوغ الساعة التاسعة مساءً (21:00 بتوقيت المغرب) وإرسال التقرير اليومي «جولة في الصحافة» تلقائياً مرة واحدة يومياً."""
  try:
    cfg = load_credentials()
    if not cfg.get("daily_report_enabled", True):
      return False
    target_hour = int(cfg.get("daily_report_hour", 21))
    ma_now = _get_morocco_now()
    today_str = ma_now.strftime("%Y-%m-%d")
    if ma_now.hour < target_hour:
      return False
    m_state = load_monitor_state()
    if m_state.get("last_daily_report_date") == today_str:
      return False
    token = (cfg.get("telegram_bot_token") or DEFAULT_TG_TOKEN).strip()
    chat_id = (cfg.get("telegram_chat_id") or DEFAULT_TG_CHAT_ID).strip()
    if not token or not chat_id:
      return False
    sent_ok = send_telegram_daily_press_review(chat_id, token, cfg=cfg, report_type="composite")
    if sent_ok:
      m_state["last_daily_report_date"] = today_str
      m_state["last_daily_report_ts"] = time.time()
      save_monitor_state(m_state)
      return True
  except Exception:
    pass
  return False


def _telegram_send_main_menu(chat_id: str, token: str):
  """إرسال القائمة الرئيسية لبوت تلغرام بشكل سلس وواضح في رسالة واحدة."""
  if not token or not chat_id:
    return
  welcome_msg = (
      "⚖️ <b>المرصد القضائي — القائمة الرئيسية</b>\n\n"
      "اختر نوع الأخبار أو التصنيف الذي تريد الاطلاع عليه الآن:"
  )
  inline_main = [
      [{"text": "📰 الصحف المغربية", "callback_data": "p_press"}, {"text": "🌍 الصحافة الدولية (حسب الدولة ▾)", "callback_data": "menu_intl"}],
      [{"text": "🇲🇦 أخبار دولية عن المغرب", "callback_data": "t_ma"}, {"text": "🏛️ قضاء دولي", "callback_data": "t_intl_court"}],
      [{"text": "🟦 فيسبوك", "callback_data": "p_fb"}, {"text": "⬛ إكس", "callback_data": "p_x"}, {"text": "🟥 يوتيوب", "callback_data": "p_yt"}],
      [{"text": "🗞️ التقرير اليومي (جولة في الصحافة)", "callback_data": "action_daily_report"}],
      [{"text": "🌐 جميع الأخبار", "callback_data": "p_all"}, {"text": "⚡ تشغيل رصد فوري", "callback_data": "action_run_scan"}],
  ]
  try:
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": welcome_msg, "parse_mode": "HTML", "reply_markup": {"inline_keyboard": inline_main}},
        timeout=6,
    )
  except Exception:
    pass


def _telegram_send_international_submenu(chat_id: str, token: str):
  """القائمة الفرعية للصحافة الدولية في تلغرام بأسماء الدول وأعداد الأخبار المتوفرة."""
  if not token or not chat_id:
    return

  counts = {"الولايات المتحدة": 0, "فرنسا": 0, "إسبانيا": 0, "الجزائر": 0, "دولي": 0, "يتطرق للمغرب": 0, "total": 0}
  for d in _get_all_articles_for_bot():
    if d.get("platform") == "صحافة دولية":
      counts["total"] += 1
      c_tag, t_tag = detect_article_country_and_topic(
          d.get("title", ""), d.get("raw_snippet", ""), d.get("url", ""), d.get("source_name", ""), "صحافة دولية"
      )
      if c_tag in counts:
        counts[c_tag] += 1
      if t_tag == "يتطرق للمغرب" or d.get("category") == "يتطرق للمغرب" or _has_morocco_reference(f"{d.get('title', '')} {d.get('raw_snippet', '')}"):
        counts["يتطرق للمغرب"] += 1

  sub_msg = (
      "🌍 <b>الصحافة الدولية — اختر الدولة أو الموضوع:</b>\n\n"
      "انقر على أي دولة لعرض أحدث أخبارها القضائية والمتطرقة للمغرب مترجمة للعربية:"
  )

  inline_intl = [
      [
          {"text": f"🇺🇸 أمريكا ({counts['الولايات المتحدة']})", "callback_data": "c_us"},
          {"text": f"🇫🇷 فرنسا ({counts['فرنسا']})", "callback_data": "c_fr"}
      ],
      [
          {"text": f"🇪🇸 إسبانيا ({counts['إسبانيا']})", "callback_data": "c_es"},
          {"text": f"🇩🇿 الجزائر ({counts['الجزائر']})", "callback_data": "c_dz"}
      ],
      [
          {"text": f"🏛️ هيئات دولية ({counts['دولي']})", "callback_data": "c_gl"},
          {"text": f"🇲🇦 عن المغرب ({counts['يتطرق للمغرب']})", "callback_data": "t_ma"}
      ],
      [
          {"text": f"🌍 كل الدولية ({counts['total']})", "callback_data": "p_intl"},
          {"text": "🔙 القائمة الرئيسية", "callback_data": "menu_main"}
      ]
  ]

  try:
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": sub_msg, "parse_mode": "HTML", "reply_markup": {"inline_keyboard": inline_intl}},
        timeout=6,
    )
  except Exception:
    pass


def _format_bot_article_card_html(item: dict) -> tuple:
  """تنسيق الخبر في بوت التلغرام بنفس البطاقة التفصيلية الافتراضية للمنصة والبوت (المنصة، الدولة، المصدر، التاريخ، العنوان بالعربية، الملخص الكامل بالعربية، والتصنيف)."""
  platform_icons = {
      "الصحف": "📰",
      "صحافة دولية": "🌍",
      "فيسبوك": "🟦",
      "إكس": "⬛",
      "يوتيوب": "🟥",
      "أخرى": "🟪",
  }
  plat_tg = item.get("platform", "الصحف")
  icon = platform_icons.get(plat_tg, "📡")
  clean_u = clean_social_post_url(item.get("url", ""))

  country_tag, topic_tag = detect_article_country_and_topic(
      item.get("title", ""), item.get("raw_snippet", ""), clean_u, item.get("source_name", ""), plat_tg
  )
  country_flags = {
      "المغرب": "🇲🇦",
      "الولايات المتحدة": "🇺🇸",
      "فرنسا": "🇫🇷",
      "إسبانيا": "🇪🇸",
      "الجزائر": "🇩🇿",
      "دولي": "🏛️",
  }
  c_flag = country_flags.get(country_tag, "🌍")

  ar_title_tg, ar_summary_tg = _ensure_arabic_title_and_summary(item)
  monitored_dt = datetime.fromtimestamp(
      float(item.get("created_at") or item.get("pub_timestamp") or time.time()), tz=timezone.utc
  ).strftime("%Y-%m-%d %H:%M")
  pub_dt_str = clean_display_text(str(item.get("pub_date") or monitored_dt))

  cat_label = clean_display_text(str(item.get("category") or topic_tag or "شؤون قضائية"))
  if plat_tg != "صحافة دولية" and cat_label in ("يتطرق للمغرب", "يهم المغرب"):
    cat_label = "شؤون قضائية ومحاكم"

  card_lines = [
      "⚖️ <b>المرصد القضائي</b>",
      f"{icon} <b>المنصة:</b> {html.escape(plat_tg)} | {c_flag} <b>الدولة:</b> {html.escape(country_tag)}",
      f"🗞️ <b>المصدر:</b> {html.escape(str(item.get('source_name') or plat_tg))}",
      f"📅 <b>تاريخ النشر:</b> {html.escape(pub_dt_str)} | 📡 <b>الرصد:</b> {monitored_dt}",
      f"📌 <b>العنوان:</b> {html.escape(ar_title_tg)}",
      "",
      f"📝 <b>الملخص:</b> {html.escape(ar_summary_tg)}",
      "",
      f"🏷️ <b>التصنيف:</b> {html.escape(cat_label)}",
  ]
  return "\n".join(card_lines), clean_u


def _telegram_bot_send_filtered_response(filter_key: str, filter_type: str, chat_id: str, token: str):
  """عرض الأخبار المطابقة للزر المختار في البوت على شكل بطاقات إخبارية كاملة مع وضع أزرار التنقل في آخر بطاقة كي تظهر مباشرة أمام المستخدم دون الحاجة للتمرير (Scrolling)."""
  if not token or not chat_id:
    return

  titles_map = {
      "الولايات المتحدة": "🇺🇸 الصحافة الأمريكية",
      "فرنسا": "🇫🇷 الصحافة الفرنسية",
      "إسبانيا": "🇪🇸 الصحافة الإسبانية",
      "الجزائر": "🇩🇿 الصحافة الجزائرية",
      "دولي": "🏛️ الهيئات والمحاكم الدولية",
      "الصحف": "📰 الصحف المغربية الوطنية",
      "صحافة دولية": "🌍 كل الصحافة الدولية",
      "فيسبوك": "🟦 منشورات فيسبوك",
      "إكس": "⬛ منشورات منصة إكس",
      "يوتيوب": "🟥 فيديوهات يوتيوب",
      "يتطرق للمغرب": "🇲🇦 أخبار دولية تتطرق للمغرب",
      "قضاء دولي": "🏛️ قرارات القضاء الدولي",
      "all": "🌐 جميع المستجدات القضائية",
  }
  label = titles_map.get(filter_key, f"تصنيف: {filter_key}")

  all_articles = _get_all_articles_for_bot()
  rows = []
  for r in all_articles:
    r_plat = r.get("platform", "الصحف")
    r_country, r_topic = detect_article_country_and_topic(
        r.get("title", ""), r.get("raw_snippet", ""), r.get("url", ""), r.get("source_name", ""), r_plat
    )
    if filter_type == "country":
      if r_plat == "صحافة دولية" and r_country == filter_key:
        rows.append(r)
    elif filter_type == "topic":
      if filter_key == "يتطرق للمغرب":
        if r_plat == "صحافة دولية" and (
            r_topic == "يتطرق للمغرب"
            or r.get("category") == "يتطرق للمغرب"
            or _has_morocco_reference(f"{r.get('title', '')} {r.get('raw_snippet', '')} {r.get('summary', '')}")
        ):
          rows.append(r)
      elif filter_key == "قضاء دولي":
        if r_plat == "صحافة دولية" and (r_topic == "قضاء دولي" or "قضاء دولي" in str(r.get("category", ""))):
          rows.append(r)
    elif filter_type == "platform":
      if filter_key == "all" or r_plat == filter_key:
        rows.append(r)
    if len(rows) >= 4:
      break

  inline_nav = [
      [
          {"text": "📰 الصحف الوطنية", "callback_data": "p_press"},
          {"text": "🌍 دولية (حسب الدولة)", "callback_data": "menu_intl"},
      ],
      [
          {"text": "🇲🇦 دولية عن المغرب", "callback_data": "t_ma"},
          {"text": "🔙 القائمة الرئيسية", "callback_data": "menu_main"},
      ],
  ]

  if not rows:
    msg_empty = "\n".join([
        f"⚖️ <b>{html.escape(label)}</b>",
        "",
        "لا توجد أخبار مسجلة حالياً ضمن هذا التصنيف.",
        "💡 يمكنك النقر على <b>⚡ تشغيل رصد فوري</b> لجلب أحدث المستجدات.",
    ])
    try:
      requests.post(
          f"https://api.telegram.org/bot{token}/sendMessage",
          json={
              "chat_id": chat_id,
              "text": msg_empty,
              "parse_mode": "HTML",
              "reply_markup": {"inline_keyboard": [[{"text": "⚡ تشغيل رصد فوري", "callback_data": "action_run_scan"}, {"text": "🔙 القائمة الرئيسية", "callback_data": "menu_main"}]]},
          },
          timeout=6,
      )
    except Exception:
      pass
    return

  # إرسال كل خبر في بطاقة كاملة بنفس الشكل الافتراضي للبوت والمنصة حتى تظهر مباشرة في أسفل الشاشة أمام المستخدم
  total_r = len(rows)
  for idx, r in enumerate(rows, 1):
    card_html, clean_u = _format_bot_article_card_html(r)
    header_line = f"📂 <b>{html.escape(label)} ({idx}/{total_r})</b>\n━━━━━━━━━━━━━━━━━━\n"
    full_card_text = (header_line + card_html)[:3900]

    kb_rows = []
    if clean_u and clean_u.startswith("http"):
      kb_rows.append([{"text": "🔗 فتح المصدر الأصلي للخبر", "url": clean_u}])
    # في البطاقة الأخيرة نضيف أزرار التنقل السريع حتى تبقى في أسفل الشاشة أمام عين المستخدم مباشرة
    if idx == total_r:
      kb_rows.extend(inline_nav)

    try:
      requests.post(
          f"https://api.telegram.org/bot{token}/sendMessage",
          json={
              "chat_id": chat_id,
              "text": full_card_text,
              "parse_mode": "HTML",
              "disable_web_page_preview": True,
              "reply_markup": {"inline_keyboard": kb_rows},
          },
          timeout=8,
      )
    except Exception:
      pass


_TG_CALLBACK_MAP = {
    "c_us": ("country", "الولايات المتحدة"),
    "c_fr": ("country", "فرنسا"),
    "c_es": ("country", "إسبانيا"),
    "c_dz": ("country", "الجزائر"),
    "c_gl": ("country", "دولي"),
    "t_ma": ("topic", "يتطرق للمغرب"),
    "t_intl_court": ("topic", "قضاء دولي"),
    "p_press": ("platform", "الصحف"),
    "p_intl": ("platform", "صحافة دولية"),
    "p_fb": ("platform", "فيسبوك"),
    "p_x": ("platform", "إكس"),
    "p_yt": ("platform", "يوتيوب"),
    "p_all": ("platform", "all"),
}


def _handle_single_telegram_update(upd: dict, token_curr: str, chat_curr: str):
  """معالجة تحديث واحد من تلغرام (ضغط زر inline أو رسالة/أمر نصي)."""
  cb = upd.get("callback_query")
  if cb:
    cb_id = cb.get("id")
    cb_data = str(cb.get("data") or "").strip()
    cb_chat_id = str(cb.get("message", {}).get("chat", {}).get("id") or chat_curr)
    try:
      requests.post(
          f"https://api.telegram.org/bot{token_curr}/answerCallbackQuery",
          json={"callback_query_id": cb_id},
          timeout=4,
      )
    except Exception:
      pass

    if cb_data == "menu_main":
      _telegram_send_main_menu(cb_chat_id, token_curr)
    elif cb_data == "menu_intl":
      _telegram_send_international_submenu(cb_chat_id, token_curr)
    elif cb_data in _TG_CALLBACK_MAP:
      f_type, f_key = _TG_CALLBACK_MAP[cb_data]
      _telegram_bot_send_filtered_response(f_key, f_type, cb_chat_id, token_curr)
    elif cb_data.startswith("country_"):
      _telegram_bot_send_filtered_response(cb_data.replace("country_", ""), "country", cb_chat_id, token_curr)
    elif cb_data.startswith("topic_"):
      _telegram_bot_send_filtered_response(cb_data.replace("topic_", ""), "topic", cb_chat_id, token_curr)
    elif cb_data.startswith("cat_"):
      _telegram_bot_send_filtered_response(cb_data.replace("cat_", ""), "platform", cb_chat_id, token_curr)
    elif cb_data == "action_daily_report":
      send_telegram_daily_press_review(cb_chat_id, token_curr, cfg=load_credentials(), report_type="composite")
    elif cb_data == "action_run_scan":
      try:
        requests.post(
            f"https://api.telegram.org/bot{token_curr}/sendMessage",
            json={"chat_id": cb_chat_id, "text": "⏳ <b>بدأت الآن عملية الرصد الشامل من تلغرام...</b> جاري فحص الصحف الوطنية والدولية وشبكات التواصل.", "parse_mode": "HTML"},
            timeout=5,
        )
      except Exception:
        pass
      added = run_headless_background_cycle()
      try:
        requests.post(
            f"https://api.telegram.org/bot{token_curr}/sendMessage",
            json={"chat_id": cb_chat_id, "text": f"✅ <b>اكتمل الرصد الشامل بنجاح!</b> تم توثيق وحفظ {added} مستجد جديد.", "parse_mode": "HTML", "reply_markup": {"inline_keyboard": [[{"text": "🔙 القائمة الرئيسية", "callback_data": "menu_main"}]]}},
            timeout=5,
        )
      except Exception:
        pass
    return

  msg = upd.get("message") or upd.get("channel_post")
  if msg:
    text_in = str(msg.get("text") or "").strip().lower()
    m_chat_id = str(msg.get("chat", {}).get("id") or chat_curr)
    if not text_in:
      return

    if text_in in ("/scan", "رصد", "تحديث", "رصد الان", "رصد الآن", "⚡ تشغيل رصد فوري", "تشغيل رصد فوري"):
      try:
        requests.post(
            f"https://api.telegram.org/bot{token_curr}/sendMessage",
            json={"chat_id": m_chat_id, "text": "⏳ <b>بدأت عملية الرصد الشامل مباشرة من تلغرام...</b>", "parse_mode": "HTML"},
            timeout=5,
        )
      except Exception:
        pass
      added = run_headless_background_cycle()
      try:
        requests.post(
            f"https://api.telegram.org/bot{token_curr}/sendMessage",
            json={"chat_id": m_chat_id, "text": f"✅ <b>اكتمل الرصد بنجاح!</b> تم جلب وتوثيق {added} خبر جديد.", "parse_mode": "HTML", "reply_markup": {"inline_keyboard": [[{"text": "🔙 القائمة الرئيسية", "callback_data": "menu_main"}]]}},
            timeout=5,
        )
      except Exception:
        pass
    elif text_in in ("/intl", "🌍 الصحافة الدولية", "الصحافة الدولية", "الدولية", "دولية"):
      _telegram_send_international_submenu(m_chat_id, token_curr)
    elif text_in in ("/usa", "/us", "أمريكا", "امريكا", "الولايات المتحدة", "🇺🇸 الولايات المتحدة"):
      _telegram_bot_send_filtered_response("الولايات المتحدة", "country", m_chat_id, token_curr)
    elif text_in in ("/france", "فرنسا", "🇫🇷 فرنسا"):
      _telegram_bot_send_filtered_response("فرنسا", "country", m_chat_id, token_curr)
    elif text_in in ("/spain", "إسبانيا", "اسبانيا", "🇪🇸 إسبانيا"):
      _telegram_bot_send_filtered_response("إسبانيا", "country", m_chat_id, token_curr)
    elif text_in in ("/algeria", "الجزائر", "🇩🇿 الجزائر"):
      _telegram_bot_send_filtered_response("الجزائر", "country", m_chat_id, token_curr)
    elif text_in in ("/global", "هيئات دولية", "🏛️ هيئات دولية"):
      _telegram_bot_send_filtered_response("دولي", "country", m_chat_id, token_curr)
    elif text_in in ("/morocco_intl", "يتطرق للمغرب", "🇲🇦 يتطرق للمغرب"):
      _telegram_bot_send_filtered_response("يتطرق للمغرب", "topic", m_chat_id, token_curr)
    elif text_in in ("كل الدولية", "🌍 كل الدولية"):
      _telegram_bot_send_filtered_response("صحافة دولية", "platform", m_chat_id, token_curr)
    elif text_in in ("/press", "الصحف", "صحف", "📰 الصحف", "📰 الصحف الوطنية", "الصحف الوطنية"):
      _telegram_bot_send_filtered_response("الصحف", "platform", m_chat_id, token_curr)
    elif text_in in ("/x", "إكس", "تويتر", "⬛ إكس"):
      _telegram_bot_send_filtered_response("إكس", "platform", m_chat_id, token_curr)
    elif text_in in ("/fb", "فيسبوك", "فايسبوك", "🟦 فيسبوك"):
      _telegram_bot_send_filtered_response("فيسبوك", "platform", m_chat_id, token_curr)
    elif text_in in ("/yt", "يوتيوب", "🟥 يوتيوب"):
      _telegram_bot_send_filtered_response("يوتيوب", "platform", m_chat_id, token_curr)
    elif text_in in ("/report", "التقرير اليومي", "جولة في الصحافة", "تقرير اليوم", "🗞️ التقرير اليومي"):
      send_telegram_daily_press_review(m_chat_id, token_curr, cfg=load_credentials(), report_type="composite")
    elif text_in in ("/all", "الكل", "جميع", "🌐 الكل"):
      _telegram_bot_send_filtered_response("all", "platform", m_chat_id, token_curr)
    elif text_in.startswith("/search ") or text_in.startswith("بحث "):
      q_tg = text_in.split(" ", 1)[1].strip() if " " in text_in else ""
      if q_tg:
        hits_tg = smart_search_articles(_get_all_articles_for_bot(), q_tg)[:5]
        if hits_tg:
          lines_s = [f"🔎 <b>نتائج البحث في المرصد عن:</b> {html.escape(q_tg)}"]
          for idx_s, r_s in enumerate(hits_tg, 1):
            ar_t_s, ar_s_s = _ensure_arabic_title_and_summary(r_s)
            t_s = html.escape(ar_t_s)
            u_s = html.escape(clean_social_post_url(r_s.get("url") or ""))
            src_s = html.escape(clean_display_text(r_s.get("source_name") or r_s.get("platform") or ""))
            lines_s.append(f"\n<b>{idx_s}.</b> <a href=\"{u_s}\">{t_s}</a>\n    📝 {html.escape(ar_s_s[:120])}...\n    🏷️ {src_s}")
          requests.post(
              f"https://api.telegram.org/bot{token_curr}/sendMessage",
              json={"chat_id": m_chat_id, "text": "\n".join(lines_s), "parse_mode": "HTML", "disable_web_page_preview": True},
              timeout=8,
          )
        else:
          requests.post(
              f"https://api.telegram.org/bot{token_curr}/sendMessage",
              json={"chat_id": m_chat_id, "text": f"🔎 لم يتم العثور على أخبار مطابقة لعبارة: <b>{html.escape(q_tg)}</b>", "parse_mode": "HTML"},
              timeout=6,
          )
    elif text_in in ("/start", "/help", "/menu", "مساعدة", "القائمة الرئيسية", "🔙 القائمة الرئيسية"):
      _telegram_send_main_menu(m_chat_id, token_curr)


def _setup_telegram_bot_commands_and_webhook(token: str):
  """حذف أي Webhook عالق لتفعيل getUpdates وتسجيل قائمة الأوامر الرسمية للبوت."""
  if not token:
    return
  try:
    requests.post(
        f"https://api.telegram.org/bot{token}/deleteWebhook",
        json={"drop_pending_updates": False},
        timeout=5,
    )
  except Exception:
    pass
  try:
    cmds = [
        {"command": "start", "description": "🏠 القائمة الرئيسية للبوت"},
        {"command": "intl", "description": "🌍 القائمة الفرعية للدول (أمريكا، فرنسا، إسبانيا، الجزائر)"},
        {"command": "usa", "description": "🇺🇸 الصحافة الأمريكية"},
        {"command": "france", "description": "🇫🇷 الصحافة الفرنسية"},
        {"command": "spain", "description": "🇪🇸 الصحافة الإسبانية"},
        {"command": "algeria", "description": "🇩🇿 الصحافة الجزائرية"},
        {"command": "press", "description": "📰 الصحف المغربية الوطنية"},
        {"command": "report", "description": "🗞️ التقرير اليومي (جولة في الصحافة)"},
        {"command": "scan", "description": "⚡ تشغيل رصد فوري الآن"},
        {"command": "all", "description": "🌐 جميع المستجدات"},
    ]
    requests.post(f"https://api.telegram.org/bot{token}/setMyCommands", json={"commands": cmds}, timeout=5)
  except Exception:
    pass


def _process_pending_telegram_updates_once():
  """معالجة أي نقرات أزرار أو أوامر منتظرة في تلغرام مرة واحدة (مفيد أثناء تشغيل CRON_MODE)."""
  try:
    cfg = load_credentials()
    token_curr = cfg.get("telegram_bot_token") or DEFAULT_TG_TOKEN
    chat_curr = cfg.get("telegram_chat_id") or DEFAULT_TG_CHAT_ID
    _setup_telegram_bot_commands_and_webhook(token_curr)
    r = requests.post(
        f"https://api.telegram.org/bot{token_curr}/getUpdates",
        json={"timeout": 0, "allowed_updates": ["message", "callback_query", "channel_post"]},
        timeout=8,
    )
    if r.status_code == 200:
      updates = r.json().get("result", [])
      max_id = 0
      for upd in updates:
        max_id = max(max_id, int(upd.get("update_id", 0)))
        _handle_single_telegram_update(upd, token_curr, chat_curr)
      if max_id > 0:
        requests.post(
            f"https://api.telegram.org/bot{token_curr}/getUpdates",
            json={"offset": max_id + 1, "timeout": 0},
            timeout=5,
        )
  except Exception:
    pass


def _telegram_bot_updates_listener():
  """خادم استماع غير مانع لبوت تلغرام يعالج نقرات الأزرار والأوامر فوراً."""
  offset = 0
  setup_done_for_token = ""
  time.sleep(2.0)
  while True:
    try:
      cfg = load_credentials()
      token_curr = cfg.get("telegram_bot_token") or DEFAULT_TG_TOKEN
      chat_curr = cfg.get("telegram_chat_id") or DEFAULT_TG_CHAT_ID
      if token_curr and token_curr != setup_done_for_token:
        _setup_telegram_bot_commands_and_webhook(token_curr)
        setup_done_for_token = token_curr
      resp = requests.post(
          f"https://api.telegram.org/bot{token_curr}/getUpdates",
          json={"offset": offset, "timeout": 20, "allowed_updates": ["message", "callback_query", "channel_post"]},
          timeout=25,
      )
      if resp.status_code == 200:
        data = resp.json()
        updates = data.get("result", [])
        for upd in updates:
          offset = max(offset, int(upd.get("update_id", 0)) + 1)
          _handle_single_telegram_update(upd, token_curr, chat_curr)
      elif resp.status_code == 409:
        # إذا كان هناك Webhook عالق نحذفه فوراً
        _setup_telegram_bot_commands_and_webhook(token_curr)
        time.sleep(2)
    except Exception:
      time.sleep(4)
    time.sleep(0.5)


def quick_process_and_save(
    items: list, cfg: dict, is_target_run: bool = False, open_web_keyword: bool = False
) -> int:
  if not items:
    upgrade_incomplete_existing_articles(cfg, max_upgrades=6)
    return 0

  existing_dedup_keys = set()
  non_target_url_map = {}
  current_targets = load_custom_targets()
  lock = get_db_lock()
  with lock:
    try:
      conn = _open_sqlite_conn()
      _ensure_schema_on_conn(conn)
      c = conn.cursor()
      c.execute("SELECT id, url, title, platform, is_custom_target FROM articles")
      for r_id, r_url, r_title, r_plat, r_tgt in c.fetchall():
        base_keys = compute_article_dedup_keys(r_title or "", r_url or "")
        plat_scope = r_plat or "الصحف"
        tgt_scope = int(r_tgt or 0)
        for bk in base_keys:
          existing_dedup_keys.add(f"{plat_scope}::{tgt_scope}::{bk}")
          if bk.startswith("raw_u:") or bk.startswith("pid:"):
            existing_dedup_keys.add(f"global::{tgt_scope}::{bk}")
            if tgt_scope == 0:
              non_target_url_map[bk] = r_id
      conn.close()
    except Exception:
      pass

  kw_filter = cfg.get("keywords_input", "")
  candidates = []
  seen_batch_keys = set()
  for it in sorted(
      items, key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True
  ):
    u = (it.get("url") or "").strip()
    t = clean_display_text(it.get("title") or "")
    s_raw = clean_display_text(it.get("raw_snippet") or "")
    is_tgt = bool(is_target_run or it.get("is_custom_target"))
    if not u or not t:
      continue
    if not open_web_keyword and not is_strictly_judicial_and_clean(
        t, s_raw, u, kw_filter if not is_tgt else "", is_target=is_tgt
    ):
      continue
    if is_tgt and not belongs_to_any_custom_target(it, current_targets):
      continue

    p_scope = it.get("platform", "الصحف")
    t_scope = 1 if is_tgt else 0
    base_pre_keys = compute_article_dedup_keys(t, u)
    # إذا كان الرصد مخصصاً وكان المنشور موجوداً مسبقاً كمنشور عام غير مخصص، نقوم بترقيته ليظهر في تبويب المخصص أيضاً
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
    pre_keys = {f"{p_scope}::{t_scope}::{k}" for k in base_pre_keys} | {
        f"global::{t_scope}::{k}" for k in base_pre_keys if k.startswith("raw_u:") or k.startswith("pid:")
    }
    # الفحص الأول قبل فك الروابط: إذا كان الخبر مرصوداً سابقاً في نفس القسم نتخطاه فوراً ليبقى 24 ساعة من وقت رصده الأول ثم يحال للأرشيف
    if (pre_keys & existing_dedup_keys) or (pre_keys & seen_batch_keys):
      continue

    seen_batch_keys.update(pre_keys)
    it["title"] = t
    candidates.append(it)

  if not candidates:
    upgrade_incomplete_existing_articles(cfg, max_upgrades=6)
    return 0

  api_key = (cfg.get("gemini_api_key") or "").strip()
  prepared_rows = []
  post_enrich_seen_keys = set()
  ai_calls = 0
  enrichment_calls = 0

  for it in candidates:
    if is_stop_requested():
      break
    normalize_press_platform_and_source(it)
    plat = it.get("platform", "الصحف")
    src = clean_display_text(it.get("source_name") or plat)

    is_foreign_it = not _is_predominantly_arabic(it.get("title", "")) or (plat == "صحافة دولية")
    if enrichment_calls < 18 or (is_foreign_it and len(clean_display_text(it.get("raw_snippet") or "")) < 140 and enrichment_calls < 35):
      enrichment_calls += 1
      enrich_item_content_and_image(it)

    # الفحص الثاني بعد فك روابط Google News وتحديث العنوان والرابط النهائي: يمنع دخول أي خبر مكرر بعد فك التوجيه
    t_scope_post = 1 if (is_target_run or it.get("is_custom_target")) else 0
    base_post_keys = compute_article_dedup_keys(it.get("title", ""), it.get("url", ""))
    post_keys = {f"{plat}::{t_scope_post}::{k}" for k in base_post_keys} | {
        f"global::{t_scope_post}::{k}" for k in base_post_keys if k.startswith("raw_u:") or k.startswith("pid:")
    }
    if (post_keys & existing_dedup_keys) or (post_keys & post_enrich_seen_keys):
      continue
    post_enrich_seen_keys.update(post_keys)

    raw_snip = clean_display_text(it.get("raw_snippet") or "")
    img_url = (it.get("image_url") or "").strip()

    if open_web_keyword:
      ar_t_kw, ar_s_kw = _ensure_arabic_title_and_summary(it, fast_render=False)
      ai_res = {
          "translated_title": ar_t_kw or it.get("title", ""),
          "summary": ar_s_kw or raw_snip,
          "sentiment": "محايد",
          "category": "رصد حر بالويب",
          "relevance_score": 95,
      }
    elif ai_calls < 20 and api_key:
      ai_res = analyze_with_gemini(it, api_key)
      ai_calls += 1
    else:
      det_country, det_topic = detect_article_country_and_topic(
          it.get("title", ""), raw_snip, it.get("url", ""), src, plat
      )
      is_for_t = not _is_predominantly_arabic(it.get("title", ""))
      ar_t_fall = translate_foreign_title_to_arabic_rulebased(it.get("title", "")) if is_for_t else it["title"]
      ai_res = {
          "translated_title": ar_t_fall,
          "summary": build_extractive_arabic_summary(
              ar_t_fall, raw_snip, plat, src
          ),
          "sentiment": "محايد",
          "category": det_topic,
          "relevance_score": 86,
      }

    pub_str = it.get("pub_date") or ""
    pub_ts = float(it.get("pub_timestamp") or 0)
    if pub_ts <= 0 or not pub_str:
      pub_str, pub_ts = extract_date_from_url_or_text(
          it.get("url", ""), raw_snip, pub_str, fallback_offset_sec=3600
      )

    final_display_title = clean_display_text(ai_res.get("translated_title") or it["title"])

    record = {
        "title": final_display_title,
        "summary": clean_display_text(ai_res["summary"]),
        "source_name": src,
        "platform": plat,
        "url": (it.get("url") or "").strip(),
        "pub_date": pub_str,
        "pub_timestamp": pub_ts,
        "sentiment": clean_display_text(ai_res["sentiment"]),
        "category": clean_display_text(ai_res["category"]),
        "relevance_score": int(ai_res["relevance_score"]),
        "is_custom_target": (
            1 if (is_target_run or it.get("is_custom_target")) else 0
        ),
        "raw_snippet": raw_snip[:1200],
        "image_url": img_url,
        "created_at": time.time(),
        "telegram_sent": 0,
    }
    _ar_t_final, _ar_s_final = _ensure_arabic_title_and_summary(record)
    if _ar_t_final:
      record["title"] = _ar_t_final
    if _ar_s_final:
      record["summary"] = _ar_s_final
    prepared_rows.append(record)

  if not prepared_rows:
    return 0

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
        time.sleep(0.25)

  upgrade_incomplete_existing_articles(cfg, max_upgrades=4)

  if added_items:
    # إرسال بطاقة موجز مجمعة ومصنفة بأزرار الدول والوسائل أولاً
    if len(added_items) >= 2:
      _send_telegram_batch_digest_bulletin(added_items, cfg)
    for rec in added_items[:8]:
      sent_ok = send_telegram_alert(rec, cfg)
      rec["telegram_sent"] = 1
      # حتى لو تجاوز العدد 10 في دفعة واحدة، نسجل البقية في السجل حتى لا ترسل في الدورات التلقائية اللاحقة كأخبار قديمة
    with lock:
      ledger_now = load_telegram_sent_ledger()
      for rec in added_items:
        rec["telegram_sent"] = 1
        ledger_now.update(compute_article_dedup_keys(rec["title"], rec["url"]))
      save_telegram_sent_ledger(ledger_now)
      try:
        conn = _open_sqlite_conn()
        c = conn.cursor()
        c.executemany(
            "UPDATE articles SET telegram_sent = 1 WHERE url = ?",
            [(r["url"],) for r in added_items],
        )
        conn.commit()
        conn.close()
      except Exception:
        pass
    sync_db_to_json(extra_items=added_items)

  return len(added_items)


# =====================================================================
# 11. محرك الرصد الدوري الأوتوماتيكي (خلفية السيرفر + GitHub Actions)
# =====================================================================
def run_headless_background_cycle() -> int:
  scan_lock = get_scan_lock()
  if not scan_lock.acquire(blocking=False):
    return 0

  try:
    rt = get_shared_runtime()
    rt["bg_scanning"] = True
  except Exception:
    rt = None

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
    raw_items.extend(scrape_moroccan_press(kw, s_period))
    raw_items.extend(scrape_international_press(kw, s_period))
    raw_items.extend(scrape_youtube_platform(kw, s_period))
    raw_items.extend(scrape_facebook_platform(kw, s_period))
    raw_items.extend(scrape_x_platform(kw, s_period))
    raw_items.extend(scrape_other_platforms(kw, s_period))

    added_general = quick_process_and_save(raw_items, cfg, is_target_run=False)

    added_targets = 0
    if targets:
      t_items = scrape_custom_targets(targets, kw, s_period)
      added_targets = quick_process_and_save(t_items, cfg, is_target_run=True)

    total_added = added_general + added_targets
    m_state = load_monitor_state()
    m_state["last_auto_run"] = time.time()
    m_state["last_auto_added"] = total_added
    m_state["total_auto_cycles"] = int(m_state.get("total_auto_cycles", 0)) + 1
    save_monitor_state(m_state)
    return total_added
  except Exception:
    return 0
  finally:
    if rt is not None:
      rt["bg_scanning"] = False
    try:
      scan_lock.release()
    except Exception:
      pass



# =====================================================================
# محرك منع السبات التلقائي (Active Keep-Alive & Self-Ping Engine)
# =====================================================================
def _detect_public_app_url() -> str:
  """اكتشاف الرابط العام للمنصة تلقائياً لمنع دخولها في وضع السبات."""
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
  """إرسال نبضات دورية (Self-Ping كل 90 ثانية) للخادم المحلي والرابط العام لمنع السبات نهائياً."""
  rt = get_shared_runtime()
  port = os.environ.get("PORT") or os.environ.get("STREAMLIT_SERVER_PORT") or "8501"
  targets_to_ping = [
      f"http://127.0.0.1:{port}/_stcore/health",
      f"http://127.0.0.1:{port}/_stcore/stream",
      f"http://127.0.0.1:{port}/",
  ]
  pub_u = _detect_public_app_url()
  if pub_u and pub_u.startswith("http"):
    targets_to_ping.insert(0, f"{pub_u}/_stcore/health")
    targets_to_ping.insert(1, f"{pub_u}/")

  ping_headers = dict(DEFAULT_HEADERS)
  ping_headers.update({
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AlMarsadKeepAlive/3.0",
      "Cache-Control": "no-cache",
  })
  for ping_u in targets_to_ping:
    try:
      requests.get(ping_u, headers=ping_headers, timeout=4.0)
    except Exception:
      pass
  rt["last_keepalive_ping_ts"] = time.time()
def ensure_background_daemon():
  rt = get_shared_runtime()
  # التحقق الدائم من أن خادم استماع بوت تلغرام يعمل فعلياً في الخلفية
  if not any(th.name == "TelegramBotListener_v3" and th.is_alive() for th in threading.enumerate()):
    try:
      threading.Thread(
          target=_telegram_bot_updates_listener,
          daemon=True,
          name="TelegramBotListener_v3",
      ).start()
    except Exception:
      pass

  if rt.get("daemon_started", False):
    return
  rt["daemon_started"] = True

  def _daemon_loop():
    time.sleep(5)
    last_keepalive = 0.0
    while True:
      now_t = time.time()
      # إرسال نبضة منع السبات كل 90 ثانية لضمان بقاء السيرفر نشطاً
      if now_t - last_keepalive >= 90:
        last_keepalive = now_t
        try:
          _ping_keep_alive_endpoints()
        except Exception:
          pass
      try:
        cfg = load_credentials()
        if cfg.get("auto_monitor", True):
          interval_sec = INTERVAL_MAP.get(
              cfg.get("monitor_interval", "كل ساعة"), 3600
          )
          state = load_monitor_state()
          last_run = float(state.get("last_auto_run", 0))
          if time.time() - last_run >= interval_sec:
            run_headless_background_cycle()
        check_and_run_scheduled_daily_report()
      except Exception:
        pass
      time.sleep(15)

  t = threading.Thread(
      target=_daemon_loop, daemon=True, name="JusticeAutoMonitor"
  )
  t.start()



# دعم التشغيل السحابي المستقل عبر GitHub Actions (CRON_MODE=1)
if os.environ.get("CRON_MODE") == "1" or st is None:
  init_db()
  _process_pending_telegram_updates_once()
  count = run_headless_background_cycle()
  check_and_run_scheduled_daily_report()
  print(f"[CRON_MODE] Completed cycle. Added {count} new items.")
  sys.exit(0)

# =====================================================================
# 12. تهيئة واجهة Streamlit والتصميم الزجاجي المتجاوب مع فرض صارم لاتجاه RTL
# =====================================================================
try:
  _st_cfg_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit")
  os.makedirs(_st_cfg_dir, exist_ok=True)
  _st_cfg_path = os.path.join(_st_cfg_dir, "config.toml")
  _desired_toml = (
      '[theme]\n'
      'base = "dark"\n'
      'primaryColor = "#d4af37"\n'
      'backgroundColor = "#061318"\n'
      'secondaryBackgroundColor = "#091c22"\n'
      'textColor = "#ffffff"\n'
  )
  if not os.path.exists(_st_cfg_path) or 'base = "dark"' not in open(_st_cfg_path, encoding="utf-8").read():
    with open(_st_cfg_path, "w", encoding="utf-8") as _tf:
      _tf.write(_desired_toml)
except Exception:
  pass

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
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&family=Tajawal:wght@500;700;800&display=swap');

:root {
    --bg-primary: #061318;
    --bg-secondary: #0b2027;
    --bg-card: rgba(11, 32, 39, 0.88);
    --bg-field: #091a20;
    --bg-dropdown: #08181e;
    --gold-primary: #d4af37;
    --gold-light: #f3e5ab;
    --emerald-accent: #10b981;
    --teal-accent: #14b8a6;
    --text-bright: #ffffff;
    --text-main: #f8fafc;
    --text-sub: #cbd5e1;
    --border-gold: rgba(212, 175, 55, 0.36);
    --border-teal: rgba(20, 184, 166, 0.34);
    color-scheme: dark !important;
}

*, *::before, *::after {
    box-sizing: border-box;
}

html, body, .stApp, .main,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
[data-testid="stMarkdownContainer"],
[data-testid="stVerticalBlock"],
[data-baseweb="tab-panel"],
[class*="st-emotion-cache"] {
    font-family: 'Cairo', 'Tajawal', sans-serif !important;
    direction: rtl !important;
    text-align: right !important;
    color: var(--text-main) !important;
}

[data-testid="stHeader"] {
    background: transparent !important;
}

.stApp,
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 12% 10%, rgba(20, 184, 166, 0.14) 0%, transparent 40%),
        radial-gradient(circle at 88% 18%, rgba(212, 175, 55, 0.11) 0%, transparent 38%),
        linear-gradient(160deg, #071920 0%, #051116 55%, #030a0e 100%) !important;
    color: var(--text-main) !important;
    overflow-x: hidden !important;
}

.block-container {
    padding-top: 1rem !important;
    padding-bottom: 2.4rem !important;
    padding-left: clamp(0.8rem, 2vw, 1.8rem) !important;
    padding-right: clamp(0.8rem, 2vw, 1.8rem) !important;
    max-width: 98% !important;
    width: 98% !important;
    direction: rtl !important;
    text-align: right !important;
}

/* إخفاء الشريط الجانبي الافتراضي الضيق لـ Streamlit لاعتماد تخطيط 25% / 75% الثابت داخل الصفحة */
section[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {
    display: none !important;
}

div[data-testid="stHorizontalBlock"] {
    direction: rtl !important;
    align-items: flex-start !important;
    gap: 20px !important;
}

/* =====================================================================
   علاج جذري وشامل للقوائم المنسدلة وحقول الإدخال (قبل الفتح وبعد الفتح)
   ===================================================================== */
div[data-testid="stSelectbox"] label,
div[data-testid="stSelectbox"] label p,
div[data-testid="stTextInput"] label,
div[data-testid="stTextInput"] label p,
div[data-testid="stFileUploader"] label,
div[data-testid="stFileUploader"] label p,
label[data-testid="stWidgetLabel"] p {
    color: #f3e5ab !important;
    font-size: 0.92rem !important;
    font-weight: 800 !important;
    margin-bottom: 4px !important;
}

/* صندوق القائمة المنسدلة قبل فتحها (Closed Selectbox) + حقول الإدخال بأعلى أولوية ممكنة */
html body .stApp [data-testid="stTextInputRootElement"],
html body .stApp [data-testid="stTextInputRootElement"] > div,
html body .stApp [data-testid="stTextInputRootElement"] > div > div,
html body .stApp div[data-testid="stTextInput"] > div,
html body .stApp div[data-testid="stTextInput"] > div > div,
html body .stApp div[data-testid="stTextInput"] > div > div > div,
html body .stApp div[data-baseweb="select"],
html body .stApp div[data-baseweb="select"] > div,
html body .stApp div[data-baseweb="select"] > div > div,
html body .stApp div[data-baseweb="select"] > div > div > div,
html body .stApp div[data-testid="stSelectbox"] > div,
html body .stApp div[data-testid="stSelectbox"] div[data-baseweb="select"],
html body .stApp div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
html body .stApp div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div,
html body .stApp div[data-baseweb="input"],
html body .stApp div[data-baseweb="input"] > div,
html body .stApp div[data-baseweb="base-input"],
html body .stApp div[data-baseweb="base-input"] > div {
    background: linear-gradient(145deg, #0b2229 0%, #07161b 100%) !important;
    background-color: #091c22 !important;
    border: 1.5px solid rgba(212, 175, 55, 0.42) !important;
    border-radius: 12px !important;
    min-height: 48px !important;
    color: #ffffff !important;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.06) !important;
    direction: rtl !important;
    text-align: right !important;
}

div[data-baseweb="select"] > div:hover,
div[data-baseweb="input"] > div:hover,
div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="input"] > div:focus-within {
    border-color: #d4af37 !important;
    box-shadow: 0 0 0 2px rgba(212, 175, 55, 0.22), 0 6px 18px rgba(0, 0, 0, 0.45) !important;
}

/* النص المعروض داخل القائمة المنسدلة قبل فتحها: أبيض ناصع وواضح بدون أي خلفية بيضاء داخلية */
div[data-baseweb="select"] *,
div[data-testid="stSelectbox"] div[data-baseweb="select"] span,
div[data-testid="stSelectbox"] div[data-baseweb="select"] div {
    background: transparent !important;
    background-color: transparent !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-family: 'Cairo', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 800 !important;
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: unset !important;
    opacity: 1 !important;
}

div[data-baseweb="select"] svg {
    fill: #d4af37 !important;
    color: #d4af37 !important;
}

/* القائمة المنسدلة بعد فتحها (Opened Dropdown Portal / Popover / Listbox) */
html body div[data-baseweb="popover"],
html body div[data-baseweb="popover"] > div,
html body div[data-baseweb="popover"] > div > div,
html body div[data-baseweb="menu"],
html body ul[data-testid="stSelectboxVirtualDropdown"],
html body div[data-testid="stSelectboxVirtualDropdown"],
html body ul[role="listbox"],
html body div[role="listbox"] {
    background: #081b21 !important;
    background-color: #081b21 !important;
    border: 1.5px solid rgba(212, 175, 55, 0.55) !important;
    border-radius: 14px !important;
    box-shadow: 0 18px 40px rgba(0, 0, 0, 0.78) !important;
    padding: 6px !important;
    direction: rtl !important;
    text-align: right !important;
}

/* عناصر وخيارات القائمة المفتوحة: خط أبيض ناصع وعريض واضح تماماً فوق الخلفية الزمردية الداكنة */
div[data-baseweb="popover"] li,
div[data-baseweb="popover"] [role="option"],
div[data-baseweb="menu"] li,
ul[data-testid="stSelectboxVirtualDropdown"] li,
li[role="option"] {
    background: rgba(13, 37, 45, 0.65) !important;
    background-color: rgba(13, 37, 45, 0.65) !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-family: 'Cairo', sans-serif !important;
    font-size: 0.94rem !important;
    font-weight: 800 !important;
    padding: 10px 14px !important;
    margin-bottom: 4px !important;
    border-radius: 10px !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    direction: rtl !important;
    text-align: right !important;
    white-space: normal !important;
    line-height: 1.45 !important;
    opacity: 1 !important;
}

div[data-baseweb="popover"] li *,
div[data-baseweb="popover"] [role="option"] *,
div[data-baseweb="menu"] li *,
ul[data-testid="stSelectboxVirtualDropdown"] li *,
li[role="option"] * {
    background: transparent !important;
    background-color: transparent !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
    opacity: 1 !important;
}

/* تمييز الخيار عند التمرير بالماوس أو الاختيار باللون الذهبي والزمردي */
div[data-baseweb="popover"] li:hover,
div[data-baseweb="popover"] [role="option"]:hover,
ul[data-testid="stSelectboxVirtualDropdown"] li:hover,
li[role="option"]:hover,
li[role="option"][aria-selected="true"] {
    background: linear-gradient(135deg, rgba(20, 184, 166, 0.32) 0%, rgba(212, 175, 55, 0.24) 100%) !important;
    border-color: rgba(212, 175, 55, 0.65) !important;
}

li[role="option"][aria-selected="true"] *,
li[role="option"]:hover * {
    color: #f3e5ab !important;
    -webkit-text-fill-color: #f3e5ab !important;
}

/* حقول النصوص والكلمات المفتاحية والمفاتيح السرية — ظهور فوري وواضح 100% أثناء الكتابة */
html body .stApp input,
html body .stApp textarea,
html body .stApp input[type="text"],
html body .stApp input[type="password"],
html body .stApp input[type="search"],
html body .stApp div[data-baseweb="input"] input,
html body .stApp div[data-baseweb="base-input"] input,
html body .stApp div[data-testid="stTextInputRootElement"] input,
html body .stApp div[data-testid="stTextInput"] input {
    background: #07171d !important;
    background-color: #07171d !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    caret-color: #f3e5ab !important;
    font-family: 'Cairo', sans-serif !important;
    font-size: 15px !important;
    font-weight: 700 !important;
    line-height: normal !important;
    height: auto !important;
    min-height: 42px !important;
    padding: 10px 14px !important;
    opacity: 1 !important;
    visibility: visible !important;
    text-shadow: none !important;
    -webkit-background-clip: border-box !important;
    background-clip: border-box !important;
    direction: rtl !important;
    text-align: right !important;
    z-index: 2 !important;
}

html body .stApp div[data-testid="InputInstructions"] {
    display: none !important;
}

input::placeholder,
textarea::placeholder {
    color: #94a3b8 !important;
    -webkit-text-fill-color: #94a3b8 !important;
    opacity: 0.85 !important;
}

input:-webkit-autofill,
input:-webkit-autofill:hover,
input:-webkit-autofill:focus,
input:-webkit-autofill:active {
    -webkit-box-shadow: 0 0 0 40px #091c22 inset !important;
    -webkit-text-fill-color: #ffffff !important;
    caret-color: #d4af37 !important;
}

/* زر إظهار/إخفاء كلمة المرور داخل حقول المفاتيح */
div[data-baseweb="input"] button,
div[data-baseweb="base-input"] button,
div[data-testid="stTextInput"] button {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #d4af37 !important;
    min-height: 28px !important;
    width: auto !important;
    padding: 0 8px !important;
}

/* صناديق الأكورديون (Expander) والنماذج */
details[data-testid="stExpander"],
div[data-testid="stExpander"],
div[data-testid="stForm"],
section[data-testid="stFileUploaderDropzone"],
div[data-testid="stFileUploader"] section {
    background: rgba(9, 28, 34, 0.88) !important;
    background-color: #091c22 !important;
    border: 1px solid rgba(212, 175, 55, 0.32) !important;
    border-radius: 14px !important;
    color: #ffffff !important;
}

details[data-testid="stExpander"] summary,
div[data-testid="stExpander"] summary {
    background: rgba(13, 39, 47, 0.78) !important;
    border-radius: 12px !important;
    padding: 10px 14px !important;
    color: #f3e5ab !important;
    font-weight: 800 !important;
}

details[data-testid="stExpander"] summary *,
div[data-testid="stExpander"] summary * {
    color: #f3e5ab !important;
    font-weight: 800 !important;
}

/* =====================================================================
   الهيدر المؤسساتي والبطاقات والإحصائيات والأزرار
   ===================================================================== */
.hero-glass {
    background: linear-gradient(135deg, rgba(11, 36, 44, 0.95) 0%, rgba(7, 22, 28, 0.92) 100%);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(212, 175, 55, 0.42);
    border-right: 5px solid #d4af37;
    border-radius: 18px;
    padding: clamp(14px, 2vw, 20px) clamp(16px, 2.5vw, 28px);
    margin-bottom: 18px;
    box-shadow: 0 14px 36px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
    direction: rtl !important;
    text-align: right !important;
}

.hero-title {
    font-size: clamp(1.3rem, 2.6vw, 1.85rem);
    font-weight: 900;
    background: linear-gradient(90deg, #f3e5ab 0%, #d4af37 50%, #34d399 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
    line-height: 1.35;
}

.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(16, 185, 129, 0.16);
    border: 1px solid rgba(52, 211, 153, 0.45);
    color: #6ee7b7;
    padding: 6px 14px;
    border-radius: 999px;
    font-size: clamp(0.76rem, 1.4vw, 0.86rem);
    font-weight: 800;
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

.sidebar-section-card {
    background: linear-gradient(145deg, rgba(11, 36, 44, 0.95) 0%, rgba(7, 22, 28, 0.92) 100%) !important;
    border: 1px solid rgba(212, 175, 55, 0.4) !important;
    border-right: 4px solid #d4af37 !important;
    border-radius: 16px !important;
    padding: 14px 16px !important;
    margin-bottom: 14px !important;
    box-shadow: 0 10px 26px rgba(0, 0, 0, 0.4) !important;
    direction: rtl !important;
    text-align: right !important;
}

.sidebar-section-title {
    font-size: 1.05rem;
    font-weight: 900;
    color: #f3e5ab !important;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
}

.sidebar-section-sub {
    font-size: 0.82rem;
    color: #cbd5e1 !important;
    line-height: 1.45;
}

.active-feed-banner {
    background: linear-gradient(135deg, rgba(13, 42, 50, 0.94) 0%, rgba(8, 25, 31, 0.94) 100%);
    border: 1px solid rgba(212, 175, 55, 0.42);
    border-right: 5px solid #d4af37;
    border-radius: 14px;
    padding: 12px 18px;
    margin: 10px 0 14px 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
    direction: rtl !important;
    text-align: right !important;
}

/* الأزرار العامة وأزرار التشغيل والإيقاف */
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
    min-height: 44px !important;
    background: linear-gradient(135deg, #0d2932 0%, #081b21 100%) !important;
    background-color: #0b2229 !important;
    color: #ffffff !important;
    border: 1px solid rgba(212, 175, 55, 0.42) !important;
    border-radius: 12px !important;
    padding: 0.48rem 0.75rem !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
    font-size: 0.93rem !important;
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.35) !important;
    transition: all 0.2s ease !important;
}

.stApp button *,
div.stButton > button *,
div[data-testid="stButton"] > button *,
div.stDownloadButton > button *,
div[data-testid="stFormSubmitButton"] > button * {
    color: #ffffff !important;
    font-family: 'Cairo', sans-serif !important;
    font-weight: 800 !important;
}

div.stButton > button:hover,
div[data-testid="stButton"] > button:hover,
div.stDownloadButton > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-1px) !important;
    border-color: #d4af37 !important;
    box-shadow: 0 8px 22px rgba(212, 175, 55, 0.25) !important;
}

/* زر تشغيل الرصد باللون الزمردي الفاخر */
[class*="st-key-sidebar_start_scan_btn"] button,
.stApp button[kind="primary"],
.stApp [data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
    border: 1.5px solid #6ee7b7 !important;
    color: #ffffff !important;
    box-shadow: 0 6px 18px rgba(16, 185, 129, 0.35) !important;
}

/* زر إيقاف الرصد باللون القرمزي المتناسق */
[class*="st-key-sidebar_stop_scan_btn"] button {
    background: linear-gradient(135deg, rgba(185, 28, 28, 0.85) 0%, rgba(127, 29, 29, 0.92) 100%) !important;
    border: 1.5px solid rgba(252, 165, 165, 0.65) !important;
    color: #ffffff !important;
}

/* شريط الإحصائيات */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(125px, 1fr));
    gap: 10px;
    margin: 6px 0 16px 0;
    direction: rtl !important;
}

.metric-glass {
    background: linear-gradient(145deg, rgba(11, 35, 43, 0.92) 0%, rgba(7, 22, 28, 0.88) 100%);
    border: 1px solid rgba(212, 175, 55, 0.28);
    border-radius: 14px;
    padding: 12px 10px;
    text-align: center !important;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.32);
}

.metric-num {
    font-size: clamp(1.3rem, 2.1vw, 1.65rem);
    font-weight: 900;
    color: #f3e5ab;
    line-height: 1.2;
    text-align: center !important;
}

.metric-lbl {
    font-size: clamp(0.76rem, 1.2vw, 0.85rem);
    color: #cbd5e1;
    font-weight: 700;
    margin-top: 3px;
    text-align: center !important;
}

/* بطاقات الأخبار الاحترافية */
.news-card {
    background: linear-gradient(145deg, rgba(11, 35, 43, 0.95) 0%, rgba(7, 22, 28, 0.90) 100%);
    border: 1px solid rgba(212, 175, 55, 0.26);
    border-right: 5px solid #d4af37;
    border-radius: 16px;
    padding: clamp(15px, 2vw, 22px);
    margin-bottom: 14px;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.42);
    transition: transform 0.2s ease, border-color 0.2s ease;
    word-wrap: break-word;
    overflow-wrap: anywhere;
    direction: rtl !important;
    text-align: right !important;
}

.news-card:hover {
    transform: translateY(-2px);
    border-color: rgba(212, 175, 55, 0.65);
}

.news-card.plat-press { border-right-color: #10b981; }
.news-card.plat-intl { border-right-color: #d4af37; }
.news-card.plat-fb { border-right-color: #38bdf8; }
.news-card.plat-x { border-right-color: #e2e8f0; }
.news-card.plat-yt { border-right-color: #f87171; }
.news-card.plat-other { border-right-color: #c084fc; }

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
    border: 1px solid rgba(212, 175, 55, 0.35);
    background: #061318;
    flex-shrink: 0;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.45);
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
    margin: 7px 0 10px 0 !important;
    direction: rtl !important;
    text-align: right !important;
}

.date-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(6, 19, 24, 0.88);
    border: 1px solid rgba(212, 175, 55, 0.32);
    color: #f1f5f9;
    padding: 3px 11px;
    border-radius: 999px;
    font-size: clamp(0.75rem, 1.2vw, 0.83rem);
    font-weight: 700;
    direction: rtl !important;
}

.badge-plat {
    padding: 3px 12px;
    border-radius: 999px;
    font-weight: 800;
    font-size: 0.79rem;
    background: rgba(212, 175, 55, 0.16);
    color: #f3e5ab;
    border: 1px solid rgba(212, 175, 55, 0.42);
    display: inline-block;
}

.badge-target {
    padding: 3px 11px;
    border-radius: 999px;
    font-weight: 800;
    font-size: 0.76rem;
    background: rgba(16, 185, 129, 0.2);
    color: #6ee7b7;
    border: 1px solid rgba(16, 185, 129, 0.45);
    display: inline-block;
}

.news-title {
    font-size: clamp(1.04rem, 1.8vw, 1.2rem);
    font-weight: 900;
    color: #ffffff;
    margin: 6px 0 6px 0;
    line-height: 1.55;
    direction: rtl !important;
    text-align: right !important;
}

.news-summary-box {
    background: rgba(5, 16, 20, 0.72);
    border-right: 3px solid #d4af37;
    border-radius: 10px;
    padding: 10px 14px;
    margin-bottom: 10px;
    font-size: clamp(0.89rem, 1.45vw, 0.97rem);
    color: #f1f5f9;
    line-height: 1.75;
    direction: rtl !important;
    text-align: right !important;
}

.news-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(212, 175, 55, 0.16);
    border: 1px solid rgba(212, 175, 55, 0.45);
    color: #f3e5ab !important;
    text-decoration: none !important;
    padding: 6px 15px;
    border-radius: 10px;
    font-size: 0.84rem;
    font-weight: 800;
    direction: rtl !important;
}

.news-link:hover {
    background: rgba(212, 175, 55, 0.3);
}

.radar-panel {
    background: rgba(8, 25, 31, 0.92);
    border: 1px solid rgba(212, 175, 55, 0.45);
    border-radius: 16px;
    padding: 14px 18px;
    margin: 10px 0 14px 0;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
    direction: rtl !important;
    text-align: right !important;
}

.radar-scanner {
    width: 54px;
    height: 54px;
    min-width: 54px;
    border-radius: 50%;
    position: relative;
    background: radial-gradient(circle, rgba(212, 175, 55, 0.2) 20%, transparent 21%), #051116;
    border: 2px solid #d4af37;
    overflow: hidden;
}

.radar-scanner::before {
    content: "";
    position: absolute;
    inset: -50%;
    background: conic-gradient(from 0deg, transparent 55%, rgba(212, 175, 55, 0.85) 100%);
    animation: radarSpin 1.3s linear infinite;
}

@keyframes radarSpin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.done-banner {
    background: linear-gradient(135deg, rgba(6, 95, 70, 0.92) 0%, rgba(4, 120, 87, 0.85) 100%);
    border: 1px solid rgba(110, 231, 183, 0.6);
    border-radius: 14px;
    padding: 11px 18px;
    margin: 8px 0 14px 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    color: #ffffff;
    font-weight: 800;
    direction: rtl !important;
    text-align: right !important;
}

@media (max-width: 900px) {
    div[data-testid="stHorizontalBlock"] {
        flex-direction: column !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"],
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        width: 100% !important;
        flex: 1 1 100% !important;
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
}
</style>
""")
try:
  import streamlit.components.v1 as _st_components
  _st_components.html(
      """
      <script>
      (function() {
          try {
              var parentDoc = window.parent.document;
              var styleId = "marsad-parent-dark-select-override";
              var existing = parentDoc.getElementById(styleId);
              if (existing) existing.remove();
              var stEl = parentDoc.createElement("style");
              stEl.id = styleId;
              stEl.innerHTML = `
                  html body div[data-baseweb="select"],
                  html body div[data-baseweb="select"] > div,
                  html body div[data-baseweb="select"] > div > div,
                  html body div[data-baseweb="input"],
                  html body div[data-baseweb="input"] > div,
                  html body div[data-baseweb="base-input"],
                  html body div[data-baseweb="base-input"] > div {
                      background: #091c22 !important;
                      background-color: #091c22 !important;
                      border-color: rgba(212, 175, 55, 0.48) !important;
                      color: #ffffff !important;
                  }
                  html body div[data-baseweb="select"] * {
                      color: #ffffff !important;
                      -webkit-text-fill-color: #ffffff !important;
                      background-color: transparent !important;
                      font-weight: 800 !important;
                  }
                  html body input,
                  html body textarea,
                  html body div[data-baseweb="input"] input,
                  html body div[data-baseweb="base-input"] input,
                  html body div[data-testid="stTextInput"] input {
                      background: #07171d !important;
                      background-color: #07171d !important;
                      color: #ffffff !important;
                      -webkit-text-fill-color: #ffffff !important;
                      caret-color: #f3e5ab !important;
                      font-size: 1rem !important;
                      font-weight: 800 !important;
                      opacity: 1 !important;
                      visibility: visible !important;
                      -webkit-background-clip: border-box !important;
                  }
                  html body div[data-baseweb="popover"],
                  html body div[data-baseweb="popover"] > div,
                  html body div[data-baseweb="popover"] > div > div,
                  html body div[data-baseweb="menu"],
                  html body ul[data-testid="stSelectboxVirtualDropdown"],
                  html body div[data-testid="stSelectboxVirtualDropdown"],
                  html body ul[role="listbox"],
                  html body div[role="listbox"] {
                      background: #081b21 !important;
                      background-color: #081b21 !important;
                      border: 1.5px solid rgba(212, 175, 55, 0.6) !important;
                  }
                  html body div[data-baseweb="popover"] li,
                  html body div[data-baseweb="popover"] [role="option"],
                  html body ul[data-testid="stSelectboxVirtualDropdown"] li,
                  html body li[role="option"] {
                      background: #0c252e !important;
                      background-color: #0c252e !important;
                      color: #ffffff !important;
                      -webkit-text-fill-color: #ffffff !important;
                      font-weight: 800 !important;
                      margin-bottom: 3px !important;
                      border-radius: 8px !important;
                  }
                  html body div[data-baseweb="popover"] li *,
                  html body div[data-baseweb="popover"] [role="option"] *,
                  html body ul[data-testid="stSelectboxVirtualDropdown"] li *,
                  html body li[role="option"] * {
                      color: #ffffff !important;
                      -webkit-text-fill-color: #ffffff !important;
                      background-color: transparent !important;
                      font-weight: 800 !important;
                  }
                  html body div[data-baseweb="popover"] li:hover,
                  html body li[role="option"]:hover,
                  html body li[role="option"][aria-selected="true"] {
                      background: #134e4a !important;
                      background-color: #134e4a !important;
                      border: 1px solid #d4af37 !important;
                  }
              `;
              parentDoc.head.appendChild(stEl);
          } catch (err) {}

          if (!window.parent._marsad_keep_alive_active) {
              window.parent._marsad_keep_alive_active = true;
              setInterval(function() {
                  try {
                      fetch(window.parent.location.href, { method: "HEAD", cache: "no-store" }).catch(function(){});
                  } catch(e) {}
              }, 120000);
          }
      })();
      </script>
      """,
      height=0,
  )
except Exception:
  pass


# =====================================================================
# 13. تحميل الإعدادات والبيانات وتجهيز القوائم
# =====================================================================
cfg = load_credentials()
custom_targets = load_custom_targets()
monitor_state = load_monitor_state()
rt_state = get_shared_runtime()

all_articles = fetch_articles_from_db()
now_ts = time.time()

live_articles = []
archive_articles = []
for a in all_articles:
  pub_t = float(a.get("pub_timestamp", 0))
  mon_t = float(a.get("created_at") or pub_t)
  if (now_ts - mon_t) < 86400:
    live_articles.append(a)
  else:
    archive_articles.append(a)

live_articles.sort(key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True)
archive_articles.sort(key=lambda x: float(x.get("pub_timestamp", 0)), reverse=True)

for _a_live in live_articles:
  normalize_press_platform_and_source(_a_live)
  if _a_live.get("platform") == "صحافة دولية":
    _c_tag, _t_tag = detect_article_country_and_topic(
        _a_live.get("title", ""),
        _a_live.get("raw_snippet", ""),
        _a_live.get("url", ""),
        _a_live.get("source_name", ""),
        "صحافة دولية",
    )
    _a_live["_intl_country"] = _c_tag
    _a_live["_intl_topic"] = _t_tag

press_live = [a for a in live_articles if a.get("platform") == "الصحف"]
intl_live = [a for a in live_articles if a.get("platform") == "صحافة دولية"]
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

SCAN_MODES = [
    ("all", "🚀 الرصد الشامل (الكل)", "الرصد الشامل", len(live_articles)),
    ("press", "📰 الصحف المغربية", "الصحف المغربية", len(press_live)),
    ("intl", "🌍 الصحافة الدولية", "الصحافة الدولية", len(intl_live)),
    ("fb", "🟦 منصة فيسبوك", "منصة فيسبوك", len(fb_live)),
    ("x", "⬛ منصة إكس (X)", "منصة إكس (X)", len(x_live)),
    ("yt", "🟥 منصة يوتيوب", "منصة يوتيوب", len(yt_live)),
    ("other", "🟪 منصات أخرى", "منصات أخرى", len(other_live)),
    ("target", "🎯 الرصد المخصص", "الرصد المخصص", len(target_live)),
    ("archive", "🗄️ الأرشيف العام", "الأرشيف", len(archive_articles)),
]

MODE_KEY_TO_INFO = {m[0]: m for m in SCAN_MODES}
MODE_KEYS_LIST = [m[0] for m in SCAN_MODES]

if "selected_nav_mode" not in st.session_state or st.session_state["selected_nav_mode"] not in MODE_KEY_TO_INFO:
  st.session_state["selected_nav_mode"] = "all"

if "admin_settings_unlocked" not in st.session_state:
  st.session_state["admin_settings_unlocked"] = False

triggered_mode = None

# =====================================================================
# 14. القائمة الموحدة لجميع وظائف الرصد والتنقل التفاعلي السريع
# =====================================================================
UNIFIED_MONITOR_OPTIONS = [
    ("all", "🌐 جميع الأخبار النشطة (الرصد الشامل)", "الرصد الشامل", len(live_articles)),
    ("press", "📰 الصحف والمواقع الوطنية المغربية", "الصحف المغربية", len(press_live)),
    ("intl", "🌍 الصحافة الدولية (جميع الدول)", "الصحافة الدولية", len(intl_live)),
    ("intl_ma", "🇲🇦 أخبار دولية تتطرق للمغرب", "صحافة دولية عن المغرب", len([a for a in intl_live if a.get("_intl_topic") == "يتطرق للمغرب" or a.get("category") == "يتطرق للمغرب"])),
    ("intl_us", "🇺🇸 الصحافة الأمريكية (USA)", "الصحافة الأمريكية", len([a for a in intl_live if a.get("_intl_country") == "الولايات المتحدة"])),
    ("intl_fr", "🇫🇷 الصحافة الفرنسية (France)", "الصحافة الفرنسية", len([a for a in intl_live if a.get("_intl_country") == "فرنسا"])),
    ("intl_es", "🇪🇸 الصحافة الإسبانية (Spain)", "الصحافة الإسبانية", len([a for a in intl_live if a.get("_intl_country") == "إسبانيا"])),
    ("intl_dz", "🇩🇿 الصحافة الجزائرية (Algeria)", "الصحافة الجزائرية", len([a for a in intl_live if a.get("_intl_country") == "الجزائر"])),
    ("intl_gl", "🏛️ المحاكم والهيئات الدولية (CIJ / CPI / CJUE)", "الهيئات الدولية", len([a for a in intl_live if a.get("_intl_country") == "دولي"])),
    ("fb", "🟦 منصة فيسبوك (Facebook)", "منصة فيسبوك", len(fb_live)),
    ("x", "⬛ منصة إكس (X / Twitter)", "منصة إكس", len(x_live)),
    ("yt", "🟥 منصة يوتيوب (YouTube)", "منصة يوتيوب", len(yt_live)),
    ("other", "🟪 منصات رقمية أخرى (تيك توك • إنستغرام • لينكدإن)", "منصات أخرى", len(other_live)),
    ("target", f"🎯 الرصد المخصص للقنوات والروابط ({len(custom_targets)})", "الرصد المخصص", len(target_live)),
    ("archive", "🗄️ الأرشيف الشامل للأخبار السابقة (+24 ساعة)", "الأرشيف العام", len(archive_articles)),
]

UNIFIED_KEY_TO_INFO = {m[0]: m for m in UNIFIED_MONITOR_OPTIONS}
UNIFIED_KEYS_LIST = [m[0] for m in UNIFIED_MONITOR_OPTIONS]

if "selected_nav_mode" not in st.session_state or st.session_state["selected_nav_mode"] not in UNIFIED_KEY_TO_INFO:
  st.session_state["selected_nav_mode"] = "all"

if "feed_page_limit" not in st.session_state:
  st.session_state["feed_page_limit"] = 15

def _switch_active_view(mode_k: str):
  if mode_k in UNIFIED_KEY_TO_INFO:
    st.session_state["selected_nav_mode"] = mode_k
    st.session_state["sidebar_mode_selector"] = mode_k
    st.session_state["feed_page_limit"] = 15

last_auto_ts = float(monitor_state.get("last_auto_run", 0))
last_auto_label = (
    format_relative_arabic(last_auto_ts) if last_auto_ts > 0 else "قيد الانطلاق"
)
auto_badge_text = (
    f"الرصد التلقائي نشط ({cfg.get('monitor_interval', 'كل ساعة')}) • آخر تحديث: {last_auto_label}"
    if cfg.get("auto_monitor", True)
    else "وضع الرصد اليدوي"
)

render_html(f"""
<div class="hero-glass" dir="rtl">
    <div>
        <h1 class="hero-title">⚖️ المرصد القضائي</h1>
        <div style="font-size:0.84rem;color:#cbd5e1;font-weight:700;margin-top:2px;">منظومة الرصد الإعلامي والقضائي الوطني والدولي</div>
    </div>
    <div class="status-pill" dir="rtl">
        <span class="pulse-dot"></span>
        <span>{html.escape(auto_badge_text)}</span>
    </div>
</div>
""")

# شريط بطاقات التصنيف التفاعلية القابلة للنقر (Clickable Category Switcher Cards)
QUICK_NAV_CARDS = [
    ("all", "🌐 الكل", len(live_articles)),
    ("press", "📰 الصحف الوطنية", len(press_live)),
    ("intl", "🌍 الصحافة الدولية", len(intl_live)),
    ("intl_ma", "🇲🇦 دولية عن المغرب", len([a for a in intl_live if a.get("_intl_topic") == "يتطرق للمغرب" or a.get("category") == "يتطرق للمغرب"])),
    ("fb", "🟦 فيسبوك", len(fb_live)),
    ("x", "⬛ إكس (X)", len(x_live)),
    ("yt", "🟥 يوتيوب", len(yt_live)),
    ("target", "🎯 الرصد المخصص", len(target_live)),
    ("archive", "🗄️ الأرشيف", len(archive_articles)),
]

nav_cols = st.columns(len(QUICK_NAV_CARDS), gap="small")
for idx_nc, (nc_key, nc_label, nc_count) in enumerate(QUICK_NAV_CARDS):
  with nav_cols[idx_nc]:
    is_active_nc = (st.session_state["selected_nav_mode"] == nc_key)
    if st.button(
        f"{nc_label} ({nc_count})",
        key=f"quick_nav_card_{nc_key}",
        type="primary" if is_active_nc else "secondary",
        use_container_width=True,
    ):
      _switch_active_view(nc_key)
      st.rerun()

# تقسيم الصفحة الرئيسية: 25% للوحة وظائف الرصد الموحدة والإعدادات و 75% لمنصة عرض الأخبار والفلاتر المتقدمة
col_side_panel, col_main_feed = st.columns([1, 3], gap="large")

with col_side_panel:
  render_html("""
  <div class="sidebar-section-card" dir="rtl">
      <div class="sidebar-section-title">📡 القائمة الموحدة لوظائف الرصد</div>
      <div class="sidebar-section-sub">اختر نوع الرصد أو المنصة أو الدولة لعرض أخبارها فوراً أو تشغيل الفحص المباشر</div>
  </div>
  """)

  def _on_dropdown_change():
    sel_val = st.session_state.get("sidebar_mode_selector", "all")
    st.session_state["selected_nav_mode"] = sel_val
    st.session_state["feed_page_limit"] = 15

  selected_mode_key = st.selectbox(
      "📂 قائمة الرصد الموحدة (اختر نوع الرصد):",
      options=UNIFIED_KEYS_LIST,
      index=UNIFIED_KEYS_LIST.index(st.session_state["selected_nav_mode"]),
      format_func=lambda k: f"{UNIFIED_KEY_TO_INFO[k][1]} — [{UNIFIED_KEY_TO_INFO[k][3]}]",
      key="sidebar_mode_selector",
      on_change=_on_dropdown_change,
  )
  st.session_state["selected_nav_mode"] = selected_mode_key

  # تحديد محرك الفحص المقابل للخيار المحدد في القائمة الموحدة
  if selected_mode_key.startswith("intl"):
    scan_target_key = "intl"
  elif selected_mode_key == "archive":
    scan_target_key = "all"
  else:
    scan_target_key = selected_mode_key
  scan_target_short = UNIFIED_KEY_TO_INFO[selected_mode_key][2]

  if st.button(
      f"▶ تشغيل رصد ({scan_target_short})",
      key="sidebar_start_scan_btn",
      type="primary",
      use_container_width=True,
  ):
    clear_stop_scan()
    triggered_mode = scan_target_key

  if st.button(
      "⏹ إيقاف عملية الرصد",
      key="sidebar_stop_scan_btn",
      type="secondary",
      use_container_width=True,
  ):
    request_stop_scan()

  # إعدادات الرصد المخصص تظهر مباشرة كجزء من اختيار الرصد المخصص في القائمة الموحدة
  if selected_mode_key == "target":
    render_html("""
    <div class="sidebar-section-card" dir="rtl" style="margin-top:10px;">
        <div class="sidebar-section-title">🎯 إدارة قنوات وروابط الرصد المخصص</div>
        <div class="sidebar-section-sub">أضف رابط أو اسم قناة (يوتيوب / فيسبوك / إكس / موقع) لرصدها ضمن هذا القسم</div>
    </div>
    """)
    with st.form("add_custom_target_form", clear_on_submit=True):
      new_t_url = st.text_input(
          "الرابط أو اسم القناة/الصفحة",
          placeholder="رابط أو اسم قناة (يوتيوب/فيسبوك/إكس)...",
      )
      new_t_kw = st.text_input(
          "كلمة فلترة داخل القناة (اختياري)",
          placeholder="مثال: المجلس الأعلى، محكمة...",
      )
      add_t_btn = st.form_submit_button("➕ إضافة إلى قائمة الرصد المخصص")
      if add_t_btn and new_t_url.strip():
        custom_targets.append({"url": new_t_url.strip(), "keyword": new_t_kw.strip()})
        save_custom_targets(custom_targets)
        invalidate_articles_cache()
        st.rerun()

    for idx, t_item in enumerate(list(custom_targets)):
      kw_tag = f" ({t_item['keyword']})" if t_item.get("keyword") else ""
      render_html(
          f"<div style='font-size:0.82rem;color:#f8fafc;direction:ltr;text-align:left;word-break:break-all;background:rgba(9,28,34,0.85);border:1px solid rgba(212,175,55,0.3);padding:6px 8px;border-radius:8px;margin-top:6px;'>🔗 {html.escape(t_item['url'])}{html.escape(kw_tag)}</div>"
      )
      if st.button(f"🗑️ حذف الرابط #{idx + 1}", key=f"del_target_{idx}", use_container_width=True):
        custom_targets.pop(idx)
        save_custom_targets(custom_targets)
        invalidate_articles_cache()
        st.rerun()

  render_html('''
  <div style="margin-top:10px;margin-bottom:4px;font-size:0.88rem;font-weight:800;color:#f3e5ab;">
      🎯 رصد الويب بكلمة مفتاحية والفترة الزمنية:
  </div>
  ''')
  kw_input_side = st.text_input(
      "كلمة مفتاحية للرصد في الويب (اختياري):",
      value=cfg.get("keywords_input", ""),
      placeholder="اكتب كلمة أو جملة لرصدها في الويب...",
      key="sidebar_kw_direct_input",
  )
  period_options = list(SEARCH_PERIOD_MAP.keys())
  curr_period = cfg.get("search_period", "آخر 7 أيام")
  selected_period = st.selectbox(
      "⏱️ الفترة الزمنية للرصد:",
      options=period_options,
      index=period_options.index(curr_period) if curr_period in period_options else 2,
      key="sidebar_period_direct_select",
  )
  if kw_input_side != cfg.get("keywords_input", "") or selected_period != cfg.get("search_period", ""):
    cfg["keywords_input"] = kw_input_side.strip()
    cfg["search_period"] = selected_period
    save_credentials(cfg)

  if st.button(
      "📡 رصد الكلمة المفتاحية في الويب الآن",
      key="sidebar_kw_launch_scan_btn",
      use_container_width=True,
  ):
    cfg["keywords_input"] = kw_input_side.strip()
    save_credentials(cfg)
    if kw_input_side.strip():
      st.session_state["global_site_search"] = kw_input_side.strip()
      clear_stop_scan()
      triggered_mode = "web_keyword"
    else:
      clear_stop_scan()
      triggered_mode = scan_target_key

  # قسم إعدادات المشرف والمفاتيح السرية (مقفل برمز سري)
  with st.expander("🔒 إعدادات المشرف والمفاتيح (محمي)", expanded=False):
    current_admin_pin = str(cfg.get("admin_pin") or DEFAULT_ADMIN_PIN).strip()
    if not st.session_state.get("admin_settings_unlocked", False):
      render_html(
          "<div style='font-size:0.82rem;color:#cbd5e1;margin-bottom:8px;'>هذا القسم مخصص لمشرف المنصة فقط. أدخل الرمز السري للوصول إلى المفاتيح والإعدادات:</div>"
      )
      pin_input = st.text_input(
          "🔑 الرمز السري للمشرف",
          type="password",
          key="admin_pin_login_input",
          placeholder="أدخل رمز المشرف...",
      )
      if st.button("🔓 فتح قفل الإعدادات", key="btn_unlock_admin", use_container_width=True):
        if pin_input.strip() == current_admin_pin:
          st.session_state["admin_settings_unlocked"] = True
          st.rerun()
        else:
          st.error("❌ الرمز السري غير صحيح")
    else:
      if st.button("🔒 قفل الإعدادات وإخفاء المفاتيح", key="btn_lock_admin", use_container_width=True):
        st.session_state["admin_settings_unlocked"] = False
        st.rerun()

      st.markdown("##### ⚙️ مفاتيح الربط والرصد التلقائي")
      gemini_key_in = st.text_input(
          "مفتاح Gemini API",
          value=cfg.get("gemini_api_key", ""),
          type="password",
      )
      tg_token_in = st.text_input(
          "Telegram Bot Token",
          value=cfg.get("telegram_bot_token", DEFAULT_TG_TOKEN),
          type="password",
      )
      tg_chat_in = st.text_input(
          "Telegram Chat ID",
          value=cfg.get("telegram_chat_id", DEFAULT_TG_CHAT_ID),
          type="password",
      )
      auto_mon_in = st.toggle(
          "تفعيل الرصد الدوري التلقائي",
          value=bool(cfg.get("auto_monitor", True)),
      )
      interval_options = list(INTERVAL_MAP.keys())
      curr_interval = cfg.get("monitor_interval", "كل ساعة")
      interval_in = st.selectbox(
          "فترة الرصد التلقائي",
          options=interval_options,
          index=interval_options.index(curr_interval) if curr_interval in interval_options else 0,
      )

      st.markdown("##### 🛡️ تغيير الرمز السري للمشرف")
      new_pin_in = st.text_input(
          "الرمز السري الجديد (اتركه فارغاً للإبقاء على الحالي)",
          type="password",
          key="new_admin_pin_input",
      )
      confirm_pin_in = st.text_input(
          "تأكيد الرمز السري الجديد",
          type="password",
          key="confirm_admin_pin_input",
      )

      if st.button("💾 حفظ جميع الإعدادات", key="btn_save_admin_cfg", use_container_width=True):
        if new_pin_in.strip():
          if new_pin_in.strip() != confirm_pin_in.strip():
            st.error("❌ الرمز السري الجديد وتأكيده غير متطابقين")
          elif len(new_pin_in.strip()) < 4:
            st.error("❌ يجب أن يتكون الرمز السري من 4 رموز على الأقل")
          else:
            cfg["admin_pin"] = new_pin_in.strip()
            cfg["gemini_api_key"] = gemini_key_in.strip()
            cfg["telegram_bot_token"] = tg_token_in.strip() or DEFAULT_TG_TOKEN
            cfg["telegram_chat_id"] = tg_chat_in.strip() or DEFAULT_TG_CHAT_ID
            cfg["auto_monitor"] = bool(auto_mon_in)
            cfg["monitor_interval"] = interval_in
            save_credentials(cfg)
            st.success("✅ تم حفظ الإعدادات وتحديث الرمز السري بنجاح")
        else:
          cfg["gemini_api_key"] = gemini_key_in.strip()
          cfg["telegram_bot_token"] = tg_token_in.strip() or DEFAULT_TG_TOKEN
          cfg["telegram_chat_id"] = tg_chat_in.strip() or DEFAULT_TG_CHAT_ID
          cfg["auto_monitor"] = bool(auto_mon_in)
          cfg["monitor_interval"] = interval_in
          save_credentials(cfg)
          st.success("✅ تم حفظ الإعدادات بنجاح")

      st.markdown("##### 🗄️ النسخ الاحتياطي للأرشيف")
      json_export_str = json.dumps(all_articles, ensure_ascii=False, indent=2)
      st.download_button(
          "⬇️ تحميل أرشيف البيانات (JSON)",
          data=json_export_str.encode("utf-8"),
          file_name="justice_monitor_backup.json",
          mime="application/json",
          use_container_width=True,
      )
      uploaded_backup = st.file_uploader("⬆️ استعادة أرشيف JSON", type=["json"])
      if uploaded_backup is not None:
        try:
          restored_list = json.loads(uploaded_backup.read().decode("utf-8"))
          if isinstance(restored_list, list):
            with open(ARCHIVE_JSON_FILE, "w", encoding="utf-8") as f:
              json.dump(restored_list, f, ensure_ascii=False, indent=2)
            init_db(force=True)
            invalidate_articles_cache()
            st.success("تمت استعادة الأرشيف بنجاح")
            st.rerun()
        except Exception:
          st.error("ملف غير صالح")


def render_article_cards(
    items_list: list,
    empty_msg: str = "لا توجد منشورات مرصودة حالياً في هذا القسم.",
):
  if not items_list:
    render_html(
        f"<div dir='rtl' style='direction:rtl;text-align:center;padding:30px;color:#cbd5e1;background:rgba(9,28,34,0.75);border-radius:16px;border:1px dashed rgba(212,175,55,0.35);'>{html.escape(empty_msg)}</div>"
    )
    return

  plat_css_map = {
      "الصحف": "plat-press",
      "صحافة دولية": "plat-intl",
      "فيسبوك": "plat-fb",
      "إكس": "plat-x",
      "يوتيوب": "plat-yt",
      "أخرى": "plat-other",
  }

  plat_type_label = {
      "الصحف": "📰 صحافة وطنية",
      "صحافة دولية": "🌍 صحافة دولية",
      "فيسبوك": "🟦 منشور فيسبوك",
      "إكس": "⬛ منشور إكس",
      "يوتيوب": "🟥 فيديو يوتيوب",
      "أخرى": "🟪 منشور رقمي",
  }

  cards_buffer = []
  for item in items_list:
    plat = clean_display_text(item.get("platform") or "الصحف")
    css_cls = plat_css_map.get(plat, "plat-press")
    type_badge_txt = plat_type_label.get(plat, plat)

    raw_src = clean_display_text(item.get("source_name") or plat)
    # fast_render=True يمنع أي طلب HTTP متزامن أثناء رسم البطاقات لضمان تحميل فوري (0ms)
    raw_title, raw_summary = _ensure_arabic_title_and_summary(item, fast_render=True)

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

    raw_url = str(item.get("url") or "#").strip()
    clean_link_url = clean_social_post_url(raw_url)

    fallback_svg_uri = get_fallback_thumbnail_data_uri(plat, raw_src)
    raw_img = (item.get("image_url") or "").strip()
    if not raw_img and ("youtube.com" in clean_link_url or "youtu.be" in clean_link_url):
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
    raw_cat_val = clean_display_text(item.get("category") or "شؤون قضائية")
    if plat != "صحافة دولية" and raw_cat_val in ("يتطرق للمغرب", "يهم المغرب", "يتعلق بالمغرب"):
      raw_cat_val = "شؤون قضائية ومحاكم"
    category_safe = html.escape(raw_cat_val)
    url_safe = html.escape(clean_link_url, quote=True)
    target_tag = (
        '<span class="badge-target">🎯 رصد مخصص</span>'
        if int(item.get("is_custom_target", 0)) == 1
        else ""
    )

    card_html = (
        f'<div class="news-card {css_cls}" dir="rtl" style="direction:rtl !important;text-align:right !important;">'
        '<div class="news-card-layout" dir="rtl" style="display:flex;flex-direction:row;direction:rtl !important;text-align:right !important;">'
        '<div class="news-thumb-box">'
        f'<img class="news-thumb-img" src="{final_img_src}" alt="thumbnail" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src=\'{fallback_svg_safe}\';" />'
        "</div>"
        '<div class="news-body-col" dir="rtl" style="direction:rtl !important;text-align:right !important;">'
        '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;direction:rtl !important;text-align:right !important;">'
        f'<span class="badge-plat">{html.escape(type_badge_txt)}</span>'
        f"{target_tag}"
        f'<span style="font-weight:800;color:#e2e8f0;font-size:0.86rem;">{source_safe}</span>'
        f'<span style="color:#cbd5e1;font-size:0.82rem;">• {category_safe}</span>'
        "</div>"
        f'<div class="news-title" dir="rtl" style="direction:rtl !important;text-align:right !important;"><a href="{url_safe}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:none;">{title_safe}</a></div>'
        '<div class="news-dates-row" dir="rtl" style="direction:rtl !important;text-align:right !important;">'
        f'<span class="date-chip" dir="rtl">📅 تاريخ النشر: <strong style="color:#f3e5ab;" dir="ltr">{pub_date_safe}</strong> <span style="color:#6ee7b7;">({rel_time})</span></span>'
        f'<span class="date-chip" dir="rtl">📡 تاريخ الرصد: <strong style="color:#5eead4;" dir="ltr">{mon_date_safe}</strong></span>'
        "</div>"
        f'<div class="news-summary-box" dir="rtl" style="direction:rtl !important;text-align:right !important;">'
        f'<strong style="color:#f3e5ab;">📝 ملخص الخبر: </strong>{summary_safe}'
        "</div>"
        '<div dir="rtl" style="direction:rtl !important;text-align:right !important;">'
        f'<a class="news-link" href="{url_safe}" target="_blank" rel="noopener noreferrer">🔗 فتح المصدر الأصلي</a>'
        "</div>"
        "</div>"
        "</div>"
        "</div>"
    )
    cards_buffer.append(card_html)

  render_html("\n".join(cards_buffer))


# =====================================================================
# 15. القسم الرئيسي المقابل للقائمة الجانبية (75% من الصفحة): محرك البحث والفلاتر المتقدمة وعرض الأخبار الفوري
# =====================================================================
with col_main_feed:
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
                  <div style="font-size:1rem;font-weight:800;color:#f3e5ab;margin-bottom:3px;">
                      📡 {html.escape(clean_display_text(status_msg))}
                  </div>
                  <div style="font-size:0.82rem;color:#cbd5e1;">
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
          ("الصحافة الدولية", lambda cb: scrape_international_press(kw, s_period, cb)),
          ("يوتيوب", lambda cb: scrape_youtube_platform(kw, s_period, cb)),
          ("فيسبوك", lambda cb: scrape_facebook_platform(kw, s_period, cb)),
          ("منصة إكس", lambda cb: scrape_x_platform(kw, s_period, cb)),
          ("تيك توك وإنستغرام ولينكدإن", lambda cb: scrape_other_platforms(kw, s_period, cb)),
          ("الروابط والقنوات المخصصة", lambda cb: scrape_custom_targets(custom_targets, kw, s_period, cb)),
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
    elif mode_key == "intl":
      collected = scrape_international_press(kw, s_period, update_ui_progress)
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
    elif mode_key == "web_keyword":
      active_kw_q = (st.session_state.get("global_site_search") or kw or "").strip()
      collected = scrape_open_web_keyword(
          active_kw_q, s_period, update_ui_progress
      )

    if not is_stop_requested():
      update_ui_progress(
          0.94, "استخراج صور المقالات ومتونها وتلخيصها عبر Gemini AI..."
      )
      is_web_kw = (mode_key == "web_keyword")
      added_count = quick_process_and_save(
          collected, cfg, is_target_run=is_target_mode, open_web_keyword=is_web_kw
      )
      if is_web_kw:
        translated_kw_list = []
        for _wk_item in collected[:30]:
          _ar_t, _ar_s = _ensure_arabic_title_and_summary(_wk_item, fast_render=False)
          _wk_item["title"] = _ar_t
          _wk_item["summary"] = _ar_s
          _wk_item["category"] = "رصد حر بالويب"
          translated_kw_list.append(_wk_item)
        st.session_state["last_web_keyword_results"] = translated_kw_list
        st.session_state["last_web_keyword_query"] = (st.session_state.get("global_site_search") or kw or "").strip()
        st.session_state["last_web_keyword_period"] = s_period
      invalidate_articles_cache()
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

  if triggered_mode:
    execute_interactive_scan(triggered_mode)
    st.rerun()

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

  # تحديد القائمة الأساسية وفق الخيار المحدد في القائمة الموحدة أو البطاقات التفاعلية
  mode_feeds_map = {
      "all": (live_articles, "جميع الأخبار النشطة (الرصد الشامل)"),
      "press": (press_live, "الصحف والمواقع الوطنية المغربية"),
      "intl": (intl_live, "الصحافة الدولية — جميع الدول"),
      "intl_ma": ([a for a in intl_live if a.get("_intl_topic") == "يتطرق للمغرب" or a.get("category") == "يتطرق للمغرب"], "الصحافة الدولية — أخبار تتطرق للمغرب"),
      "intl_us": ([a for a in intl_live if a.get("_intl_country") == "الولايات المتحدة"], "الصحافة الأمريكية (USA)"),
      "intl_fr": ([a for a in intl_live if a.get("_intl_country") == "فرنسا"], "الصحافة الفرنسية (France)"),
      "intl_es": ([a for a in intl_live if a.get("_intl_country") == "إسبانيا"], "الصحافة الإسبانية (Spain)"),
      "intl_dz": ([a for a in intl_live if a.get("_intl_country") == "الجزائر"], "الصحافة الجزائرية (Algeria)"),
      "intl_gl": ([a for a in intl_live if a.get("_intl_country") == "دولي"], "المحاكم والهيئات الدولية (CIJ / CPI / CJUE)"),
      "fb": (fb_live, "منصة فيسبوك — الصفحات والمنشورات القضائية"),
      "x": (x_live, "منصة إكس (X) — التغريدات والحسابات"),
      "yt": (yt_live, "منصة يوتيوب — القنوات والفيديوهات"),
      "other": (other_live, "منصات رقمية أخرى — تيك توك • إنستغرام • لينكدإن"),
      "target": (target_live, "الرصد المخصص — القنوات والصفحات المحددة"),
      "archive": (archive_articles, "الأرشيف الشامل للأخبار السابقة (+24 ساعة)"),
  }

  active_feed_list, active_feed_title = mode_feeds_map.get(
      selected_mode_key, (live_articles, "جميع الأخبار النشطة")
  )
  displayed_articles = list(active_feed_list)

  # =====================================================================
  # لوحة البحث والرصد المباشر بالكلمات المفتاحية + الفلاتر المتقدمة
  # =====================================================================
  render_html("""
  <div style="background:linear-gradient(145deg, rgba(11,36,44,0.95) 0%, rgba(7,22,28,0.92) 100%);border:1px solid rgba(212,175,55,0.45);border-right:4px solid #d4af37;border-radius:16px;padding:12px 16px;margin-bottom:10px;" dir="rtl">
      <div style="font-size:0.98rem;font-weight:900;color:#f3e5ab;margin-bottom:3px;">🔎 محرك البحث والرصد الفوري بالكلمات المفتاحية</div>
      <div style="font-size:0.8rem;color:#cbd5e1;">اكتب كلمة أو عدة كلمات مفتاحية أو جملة، ثم اضغط <b>«🔎 بحث في المرصد»</b> لتصفية الأخبار المخزنة أو <b>«📡 رصد الكلمة في الويب»</b> لجلب أخبارها مباشرة من الإنترنت</div>
  </div>
  """)

  if "global_site_search" not in st.session_state:
    st.session_state["global_site_search"] = ""

  with st.form("main_keyword_hub_form", clear_on_submit=False):
    col_kw_box, col_btn_search, col_btn_webscan, col_btn_reset = st.columns([2.7, 1.15, 1.35, 0.7])
    with col_kw_box:
      kw_form_val = st.text_input(
          "أدخل الكلمة أو الكلمات المفتاحية للبحث أو الرصد:",
          value=st.session_state.get("global_site_search", ""),
          placeholder="✍️ اكتب هنا الكلمة المفتاحية (مثال: المجلس الأعلى، محكمة النقض، المغرب)...",
          label_visibility="collapsed",
      )
    with col_btn_search:
      search_clicked = st.form_submit_button(
          "🔎 بحث في المرصد",
          type="primary",
          use_container_width=True,
      )
    with col_btn_webscan:
      webscan_clicked = st.form_submit_button(
          "📡 رصد الكلمة في الويب",
          type="primary",
          use_container_width=True,
      )
    with col_btn_reset:
      reset_clicked = st.form_submit_button(
          "🔄 مسح",
          use_container_width=True,
      )

  if reset_clicked:
    st.session_state["global_site_search"] = ""
    st.session_state.pop("last_web_keyword_results", None)
    st.session_state.pop("last_web_keyword_query", None)
    st.session_state["adv_filter_country"] = "الكل"
    st.session_state["adv_filter_topic"] = "الكل"
    st.session_state["adv_filter_source"] = "الكل"
    st.session_state["adv_filter_time"] = "كل الأوقات"
    st.session_state["feed_page_limit"] = 15
    if cfg.get("keywords_input"):
      cfg["keywords_input"] = ""
      save_credentials(cfg)
    st.rerun()
  elif search_clicked:
    st.session_state["global_site_search"] = (kw_form_val or "").strip()
    st.session_state["feed_page_limit"] = 20
  elif webscan_clicked:
    entered_kw = (kw_form_val or "").strip()
    st.session_state["global_site_search"] = entered_kw
    cfg["keywords_input"] = entered_kw
    save_credentials(cfg)
    clear_stop_scan()
    execute_interactive_scan("web_keyword" if entered_kw else scan_target_key)
    st.rerun()

  global_search_q = st.session_state.get("global_site_search", "")

  col_gs_scope, col_gs_sort = st.columns(2)
  with col_gs_scope:
    search_scope = st.selectbox(
        "📂 نطاق البحث:",
        options=["في جميع الأخبار النشطة والأرشيف", "في القسم المعروض حالياً", "في الأخبار النشطة فقط", "في الأرشيف فقط"],
        key="global_search_scope",
    )
  with col_gs_sort:
    sort_order = st.selectbox(
        "↕️ ترتيب النتائج:",
        options=["الأحدث نشراً أولاً", "الأحدث رصداً أولاً", "الأقدم أولاً"],
        key="global_sort_order",
    )

  # شريط الفلاتر المتقدمة (الدولة، الموضوع القضائي، المصدر/الجريدة، والنافذة الزمنية)
  available_sources = sorted(list({clean_display_text(a.get("source_name") or "") for a in displayed_articles if clean_display_text(a.get("source_name") or "")}))
  col_af_country, col_af_topic, col_af_source, col_af_time = st.columns(4)
  with col_af_country:
    adv_country = st.selectbox(
        "🌍 تصفية حسب الدولة:",
        options=["الكل", "المغرب", "الولايات المتحدة", "فرنسا", "إسبانيا", "الجزائر", "دولي"],
        key="adv_filter_country",
    )
  with col_af_topic:
    adv_topic = st.selectbox(
        "⚖️ تصفية حسب الموضوع:",
        options=["الكل", "شؤون قضائية ومحاكم", "يتطرق للمغرب", "قضاء دولي", "قضايا وتسليم واتفاقيات"],
        key="adv_filter_topic",
    )
  with col_af_source:
    adv_source = st.selectbox(
        "🗞️ تصفية حسب المصدر / الصحيفة:",
        options=["الكل"] + available_sources[:80],
        key="adv_filter_source",
    )
  with col_af_time:
    adv_time = st.selectbox(
        "⏱️ تصفية حسب وقت النشر:",
        options=["كل الأوقات", "آخر 6 ساعات", "آخر 24 ساعة", "آخر 3 أيام", "آخر 7 أيام", "آخر 30 يوماً"],
        key="adv_filter_time",
    )

  # تطبيق البحث النصي الشامل إن وجد
  if global_search_q.strip():
    q_gs = global_search_q.strip()
    if search_scope == "في القسم المعروض حالياً":
      pool_gs = displayed_articles
    elif search_scope == "في الأخبار النشطة فقط":
      pool_gs = list(live_articles)
    elif search_scope == "في الأرشيف فقط":
      pool_gs = list(archive_articles)
    else:
      seen_gs_u = set()
      pool_gs = []
      for _it_g in live_articles + archive_articles:
        _u_g = _it_g.get("url", "")
        if _u_g not in seen_gs_u:
          seen_gs_u.add(_u_g)
          pool_gs.append(_it_g)
    displayed_articles = smart_search_articles(pool_gs, q_gs)

  # تطبيق الفلاتر المتقدمة الأربعة
  if adv_country != "الكل":
    displayed_articles = [
        a for a in displayed_articles
        if (a.get("_intl_country") or detect_article_country_and_topic(
            a.get("title", ""), a.get("raw_snippet", ""), a.get("url", ""), a.get("source_name", ""), a.get("platform", "")
        )[0]) == adv_country
    ]

  if adv_topic != "الكل":
    displayed_articles = [
        a for a in displayed_articles
        if adv_topic in str(a.get("category", ""))
        or (a.get("_intl_topic") or detect_article_country_and_topic(
            a.get("title", ""), a.get("raw_snippet", ""), a.get("url", ""), a.get("source_name", ""), a.get("platform", "")
        )[1]) == adv_topic
    ]

  if adv_source != "الكل":
    displayed_articles = [
        a for a in displayed_articles
        if clean_display_text(a.get("source_name") or "") == adv_source
    ]

  if adv_time != "كل الأوقات":
    time_win_map = {
        "آخر 6 ساعات": 6 * 3600,
        "آخر 24 ساعة": 24 * 3600,
        "آخر 3 أيام": 3 * 86400,
        "آخر 7 أيام": 7 * 86400,
        "آخر 30 يوماً": 30 * 86400,
    }
    max_age_sec = time_win_map.get(adv_time, 0)
    if max_age_sec > 0:
      displayed_articles = [
          a for a in displayed_articles
          if (now_ts - float(a.get("pub_timestamp") or a.get("created_at") or now_ts)) <= max_age_sec
      ]

  # تطبيق الترتيب المختار (عند عدم وجود بحث نصي يرتب حسب التطابق)
  if not global_search_q.strip():
    if sort_order == "الأحدث رصداً أولاً":
      displayed_articles.sort(key=lambda x: float(x.get("created_at") or x.get("pub_timestamp") or 0), reverse=True)
    elif sort_order == "الأقدم أولاً":
      displayed_articles.sort(key=lambda x: float(x.get("pub_timestamp") or 0), reverse=False)
    else:
      displayed_articles.sort(key=lambda x: float(x.get("pub_timestamp") or 0), reverse=True)

  # إذا كان المستخدم قد أطلق لتوه عملية رصد شامل في الويب عن كلمة مفتاحية، نعرض نتائج الويب المستخرجة فوراً في الصدارة
  web_kw_res = st.session_state.get("last_web_keyword_results")
  web_kw_q = (st.session_state.get("last_web_keyword_query") or "").strip()
  if isinstance(web_kw_res, list) and web_kw_q and web_kw_q == (global_search_q or "").strip():
    seen_wk_u = set()
    merged_wk = []
    for _w_it in web_kw_res + displayed_articles:
      _wu = _w_it.get("url", "")
      if _wu and _wu not in seen_wk_u:
        seen_wk_u.add(_wu)
        merged_wk.append(_w_it)
    displayed_articles = merged_wk
    active_feed_title = f"نتائج الرصد الشامل في الويب لـ «{web_kw_q}» ({st.session_state.get('last_web_keyword_period', '')})"

  total_matching = len(displayed_articles)
  page_limit = int(st.session_state.get("feed_page_limit", 15))
  paginated_articles = displayed_articles[:page_limit]

  # =====================================================================
  # استوديو التقرير اليومي (إصدار الساعة 21:00) وتصدير PDF / Word وجولة في الصحافة لتلغرام
  # =====================================================================
  with st.expander("📑 التقرير اليومي (21:00) — تصدير PDF / Word وإرسال «جولة في الصحافة» لتلغرام", expanded=False):
    ma_clock_now = _get_morocco_now()
    last_rep_dt = monitor_state.get("last_daily_report_date") or "لم يُرسل بعد"
    render_html(
        f"""
        <div style="background:rgba(7,25,32,0.85);border:1px solid rgba(212,175,55,0.4);border-right:4px solid #d4af37;border-radius:12px;padding:10px 14px;margin-bottom:10px;" dir="rtl">
            <div style="font-size:0.94rem;font-weight:900;color:#f3e5ab;">🕘 جدولة التقرير اليومي الآلي: الساعة 21:00 مساءً (توقيت المغرب)</div>
            <div style="font-size:0.8rem;color:#cbd5e1;margin-top:2px;">
                التوقيت الحالي بالمغرب: <strong style="color:#6ee7b7;" dir="ltr">{ma_clock_now.strftime('%Y-%m-%d %H:%M')}</strong>
                • آخر إرسال تلقائي لتلغرام: <strong style="color:#f3e5ab;" dir="ltr">{html.escape(str(last_rep_dt))}</strong>
            </div>
        </div>
        """
    )

    col_rep_mode, col_rep_auto = st.columns([2.2, 1.2])
    with col_rep_mode:
      rep_mode_choice = st.selectbox(
          "📋 نوع التقرير المطلوب إعداده وتصديره:",
          options=[
              "تقرير يومي تركيبي شامل (أهم أخبار القضاء الوطني والدولي والمغرب)",
              "تقرير مخصص بناءً على الفلاتر والنتائج المعروضة حالياً",
          ],
          key="daily_report_mode_select",
      )
    with col_rep_auto:
      daily_auto_toggle = st.toggle(
          "إرسال تلقائي يومي لتلغرام (21:00)",
          value=bool(cfg.get("daily_report_enabled", True)),
          key="toggle_daily_21h_report",
      )
      if daily_auto_toggle != bool(cfg.get("daily_report_enabled", True)):
        cfg["daily_report_enabled"] = bool(daily_auto_toggle)
        cfg["daily_report_hour"] = 21
        save_credentials(cfg)

    is_custom_rep = "مخصص" in rep_mode_choice
    active_filters_desc = (
        f"القسم: {active_feed_title} | الدولة: {adv_country} | الموضوع: {adv_topic} | "
        f"المصدر: {adv_source} | الوقت: {adv_time}"
        + (f" | البحث: «{global_search_q.strip()}»" if global_search_q.strip() else "")
    )
    rep_source_pool = displayed_articles if is_custom_rep else all_articles

    col_gen_btn, col_tg_btn = st.columns(2)
    with col_gen_btn:
      if st.button("✨ توليد ومعاينة التقرير الآن", key="btn_build_daily_report_now", type="primary", use_container_width=True):
        st.session_state["generated_report_obj"] = build_daily_report_data(
            rep_source_pool,
            cfg,
            report_type="custom" if is_custom_rep else "composite",
            filter_summary=active_filters_desc if is_custom_rep else "",
        )
    with col_tg_btn:
      if st.button("✈️ إرسال «جولة في الصحافة» إلى تلغرام الآن", key="btn_send_tg_press_review_now", use_container_width=True):
        tok_r = (cfg.get("telegram_bot_token") or DEFAULT_TG_TOKEN).strip()
        cid_r = (cfg.get("telegram_chat_id") or DEFAULT_TG_CHAT_ID).strip()
        ok_tg = send_telegram_daily_press_review(
            cid_r,
            tok_r,
            articles_pool=rep_source_pool,
            cfg=cfg,
            report_type="custom" if is_custom_rep else "composite",
            filter_summary=active_filters_desc if is_custom_rep else "",
        )
        if ok_tg:
          st.success("✅ تم إرسال التقرير اليومي «جولة في الصحافة» إلى بوت التلغرام بنجاح")
        else:
          st.error("❌ تعذر إرسال التقرير إلى تلغرام؛ تحقق من إعدادات البوت")

    gen_rep = st.session_state.get("generated_report_obj")
    if isinstance(gen_rep, dict):
      render_html(
          f"""
          <div style="background:rgba(11,36,44,0.92);border:1px solid rgba(20,184,166,0.45);border-radius:12px;padding:12px 15px;margin:10px 0;" dir="rtl">
              <div style="font-size:1rem;font-weight:900;color:#f3e5ab;margin-bottom:4px;">{html.escape(gen_rep['title'])}</div>
              <div style="font-size:0.82rem;color:#6ee7b7;margin-bottom:8px;">
                  إجمالي الأخبار: {gen_rep['total_count']} • وطنية: {len(gen_rep['national_items'])} • دولية عن المغرب: {len(gen_rep['morocco_intl_items'])} • قضاء دولي ومنصات: {len(gen_rep['other_intl_items']) + len(gen_rep['social_items'])}
              </div>
              <div style="font-size:0.88rem;color:#f1f5f9;line-height:1.75;background:rgba(5,16,20,0.65);padding:10px 12px;border-radius:8px;border-right:3px solid #d4af37;">
                  <strong style="color:#f3e5ab;">📌 الخلاصة التركيبية:</strong><br/>{html.escape(gen_rep['synthesis'])}
              </div>
          </div>
          """
      )
      pdf_bytes, pdf_mime, pdf_fname = generate_report_pdf_bytes(gen_rep)
      docx_bytes = generate_report_docx_bytes(gen_rep)
      col_dl_pdf, col_dl_docx = st.columns(2)
      with col_dl_pdf:
        st.download_button(
            "📄 تصدير التقرير (PDF)",
            data=pdf_bytes,
            file_name=pdf_fname,
            mime=pdf_mime,
            key="dl_daily_report_pdf",
            use_container_width=True,
        )
      with col_dl_docx:
        st.download_button(
            "📝 تصدير التقرير (Word .docx)",
            data=docx_bytes,
            file_name=f"marsad_report_{gen_rep['date_str']}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key="dl_daily_report_docx",
            use_container_width=True,
        )

  render_html(
      f"""
      <div class="active-feed-banner" dir="rtl">
          <div style="font-size:1.02rem;font-weight:900;color:#f8fafc;">
              📌 القسم المعروض: <span style="color:#f3e5ab;">{html.escape(active_feed_title)}</span>
          </div>
          <div style="font-size:0.84rem;font-weight:800;color:#6ee7b7;background:rgba(16,185,129,0.16);border:1px solid rgba(52,211,153,0.4);padding:4px 14px;border-radius:999px;">
              إجمالي النتائج المطابقة: {total_matching} (المعروض حالياً: {len(paginated_articles)})
          </div>
      </div>
      """
  )

  render_article_cards(
      paginated_articles,
      empty_msg="لا توجد منشورات تطابق معايير الفلترة الحالية. جرّب تغيير الفلتر أو اضغط (🔄 ضبط) أو شغّل الرصد من القائمة الموحدة.",
  )

  if total_matching > page_limit:
    if st.button(f"⬇️ عرض المزيد من الأخبار ({total_matching - page_limit} خبر إضافي)", key="btn_load_more_articles", use_container_width=True):
      st.session_state["feed_page_limit"] = page_limit + 20
      st.rerun()

# =====================================================================
# 19. فحص الرصد الدوري غير المتزامن (بدون تجميد الواجهة أو قفل SQLite)
# =====================================================================
if cfg.get("auto_monitor", True):
  interval_sec = INTERVAL_MAP.get(
      cfg.get("monitor_interval", "كل ساعة"), 900
  )
  last_run_ts = float(monitor_state.get("last_auto_run", 0))
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
