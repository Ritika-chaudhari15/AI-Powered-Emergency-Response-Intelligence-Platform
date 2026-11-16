"""Small, dependency-free translation layer for API-facing text.

The API chooses a locale per request.  Prefer the ``Accept-Language`` header;
clients may use ``?lang=ta`` when a header cannot be set (for example, while
testing an endpoint in a browser).  Internal values such as database statuses,
resource names, and enum codes deliberately stay language-neutral.
"""

from collections.abc import Mapping

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = {
    "en": "English",
    "ta": "Tamil",
    "hi": "Hindi",
    "te": "Telugu",
    "ml": "Malayalam",
}

# Message IDs make translations stable even when the English copy is revised.
MESSAGES: dict[str, dict[str, str]] = {
    "invalid_access_token": {
        "en": "Invalid or expired access token", "ta": "தவறான அல்லது காலாவதியான அணுகல் டோக்கன்",
        "hi": "अमान्य या समाप्त हो चुका एक्सेस टोकन", "te": "చెల్లని లేదా గడువు ముగిసిన యాక్సెస్ టోకెన్", "ml": "അസാധുവായതോ കാലഹരണപ്പെട്ടതോ ആയ ആക്സസ് ടോക്കൺ",
    },
    "account_exists": {
        "en": "An account with this email already exists", "ta": "இந்த மின்னஞ்சலுடன் ஒரு கணக்கு ஏற்கனவே உள்ளது",
        "hi": "इस ईमेल से एक खाता पहले से मौजूद है", "te": "ఈ ఇమెయిల్‌తో ఖాతా ఇప్పటికే ఉంది", "ml": "ഈ ഇമെയിൽ ഉപയോഗിച്ച് ഒരു അക്കൗണ്ട് ഇതിനകം നിലവിലുണ്ട്",
    },
    "incorrect_credentials": {
        "en": "Incorrect email or password", "ta": "மின்னஞ்சல் அல்லது கடவுச்சொல் தவறானது",
        "hi": "ईमेल या पासवर्ड गलत है", "te": "ఇమెయిల్ లేదా పాస్‌వర్డ్ తప్పు", "ml": "ഇമെയിലോ പാസ്‌വേഡോ തെറ്റാണ്",
    },
    "logged_out": {
        "en": "Logged out successfully", "ta": "வெற்றிகரமாக வெளியேறிவிட்டீர்கள்",
        "hi": "सफलतापूर्वक लॉग आउट हो गया", "te": "విజయవంతంగా లాగ్ అవుట్ అయ్యారు", "ml": "വിജയകരമായി ലോഗ് ഔട്ട് ചെയ്തു",
    },
    "disaster_not_found": {
        "en": "Disaster report not found", "ta": "பேரிடர் அறிக்கை கிடைக்கவில்லை",
        "hi": "आपदा रिपोर्ट नहीं मिली", "te": "విపత్తు నివేదిక కనుగొనబడలేదు", "ml": "ദുരന്ത റിപ്പോർട്ട് കണ്ടെത്തിയില്ല",
    },
    "notification_not_found": {
        "en": "Notification not found", "ta": "அறிவிப்பு கிடைக்கவில்லை",
        "hi": "सूचना नहीं मिली", "te": "నోటిఫికేషన్ కనుగొనబడలేదు", "ml": "അറിയിപ്പ് കണ്ടെത്തിയില്ല",
    },
    "duplicate_report": {
        "en": "Duplicate disaster report detected.", "ta": "நகல் பேரிடர் அறிக்கை கண்டறியப்பட்டது.",
        "hi": "डुप्लिकेट आपदा रिपोर्ट मिली.", "te": "నకిలీ విపత్తు నివేదిక గుర్తించబడింది.", "ml": "ആവർത്തിച്ച ദുരന്ത റിപ്പോർട്ട് കണ്ടെത്തി.",
    },
    "weather_unavailable": {
        "en": "Current weather data is unavailable. Please retry shortly.", "ta": "தற்போதைய வானிலைத் தரவு கிடைக்கவில்லை. சிறிது நேரத்தில் மீண்டும் முயற்சிக்கவும்.",
        "hi": "वर्तमान मौसम डेटा उपलब्ध नहीं है। कृपया थोड़ी देर बाद फिर प्रयास करें।", "te": "ప్రస్తుత వాతావరణ డేటా అందుబాటులో లేదు. కొద్దిసేపటికి మళ్లీ ప్రయత్నించండి.", "ml": "നിലവിലെ കാലാവസ്ഥാ ഡാറ്റ ലഭ്യമല്ല. അൽപ്പസമയത്തിനുശേഷം വീണ്ടും ശ്രമിക്കുക.",
    },
    "model_prediction_failed": {
        "en": "The trained model could not make a prediction", "ta": "பயிற்சி பெற்ற மாதிரியால் கணிப்பு செய்ய முடியவில்லை",
        "hi": "प्रशिक्षित मॉडल पूर्वानुमान नहीं लगा सका", "te": "శిక్షణ పొందిన మోడల్ అంచనా వేయలేకపోయింది", "ml": "പരിശീലിപ്പിച്ച മോഡലിന് പ്രവചനം നടത്താനായില്ല",
    },
    "predict_before_allocate": {
        "en": "Predict this disaster report before allocating resources", "ta": "வளங்களை ஒதுக்குவதற்கு முன் இந்த பேரிடர் அறிக்கையை கணிக்கவும்",
        "hi": "संसाधन आवंटित करने से पहले इस आपदा रिपोर्ट का पूर्वानुमान करें", "te": "వనరులు కేటాయించే ముందు ఈ విపత్తు నివేదికను అంచనా వేయండి", "ml": "വിഭവങ്ങൾ അനുവദിക്കുന്നതിന് മുമ്പ് ഈ ദുരന്ത റിപ്പോർട്ട് പ്രവചിക്കുക",
    },
}

_ENGLISH_TO_KEY = {values["en"]: key for key, values in MESSAGES.items()}


def resolve_locale(override: str | None, accept_language: str | None) -> str:
    """Return a supported ISO 639-1 locale, falling back safely to English."""
    candidates = [override] if override else []
    if accept_language:
        candidates.extend(part.split(";", 1)[0].strip() for part in accept_language.split(","))
    for candidate in candidates:
        if candidate:
            language = candidate.lower().replace("_", "-").split("-", 1)[0]
            if language in SUPPORTED_LOCALES:
                return language
    return DEFAULT_LOCALE


def translate(key: str, locale: str) -> str:
    return MESSAGES.get(key, {}).get(locale) or MESSAGES.get(key, {}).get(DEFAULT_LOCALE) or key


def translate_detail(detail: object, locale: str) -> object:
    """Translate known HTTP exception text while preserving error shape/codes."""
    if isinstance(detail, str):
        key = _ENGLISH_TO_KEY.get(detail)
        return translate(key, locale) if key else detail
    if isinstance(detail, Mapping):
        return {key: translate_detail(value, locale) for key, value in detail.items()}
    if isinstance(detail, list):
        return [translate_detail(value, locale) for value in detail]
    return detail
