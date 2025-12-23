"""
Supported languages and utilities.

Supports all major left-to-right languages.
RTL languages (Arabic, Hebrew, Urdu) are supported but not in priority warm-up.
"""

from enum import Enum


class Language(str, Enum):
    """Supported languages."""
    
    # === TIER 1: Major world languages (warm-up priority) ===
    EN = "en"      # English
    ES = "es"      # Spanish (500M+ speakers)
    ZH = "zh"      # Chinese Simplified (1B+ speakers)
    PT = "pt"      # Portuguese (250M+ speakers)
    FR = "fr"      # French (300M+ speakers)
    DE = "de"      # German (100M+ speakers)
    JA = "ja"      # Japanese (125M speakers)
    KO = "ko"      # Korean (80M speakers)
    IT = "it"      # Italian (65M speakers)
    RU = "ru"      # Russian (250M speakers)
    
    # === TIER 2: Large regional languages ===
    ZH_TW = "zh-tw"  # Chinese Traditional (Taiwan, HK)
    NL = "nl"        # Dutch (25M speakers)
    PL = "pl"        # Polish (45M speakers)
    VI = "vi"        # Vietnamese (85M speakers)
    TH = "th"        # Thai (60M speakers)
    TR = "tr"        # Turkish (80M speakers)
    ID = "id"        # Indonesian (200M+ speakers)
    MS = "ms"        # Malay (30M speakers)
    TL = "tl"        # Tagalog/Filipino (70M speakers)
    
    # === TIER 3: European languages ===
    SV = "sv"      # Swedish
    NO = "no"      # Norwegian
    DA = "da"      # Danish
    FI = "fi"      # Finnish
    EL = "el"      # Greek
    CS = "cs"      # Czech
    SK = "sk"      # Slovak
    HU = "hu"      # Hungarian
    RO = "ro"      # Romanian
    BG = "bg"      # Bulgarian
    HR = "hr"      # Croatian
    SR = "sr"      # Serbian
    SL = "sl"      # Slovenian
    UK = "uk"      # Ukrainian
    LT = "lt"      # Lithuanian
    LV = "lv"      # Latvian
    ET = "et"      # Estonian
    
    # === TIER 4: Other major languages ===
    HI = "hi"      # Hindi (600M+ speakers)
    BN = "bn"      # Bengali (230M speakers)
    TA = "ta"      # Tamil (75M speakers)
    TE = "te"      # Telugu (80M speakers)
    MR = "mr"      # Marathi (85M speakers)
    GU = "gu"      # Gujarati (55M speakers)
    KN = "kn"      # Kannada (45M speakers)
    ML = "ml"      # Malayalam (35M speakers)
    PA = "pa"      # Punjabi (125M speakers)
    
    # === RTL Languages (supported but not warm-up priority) ===
    AR = "ar"      # Arabic (310M speakers) - RTL
    HE = "he"      # Hebrew (9M speakers) - RTL
    FA = "fa"      # Persian/Farsi (110M speakers) - RTL
    UR = "ur"      # Urdu (230M speakers) - RTL
    
    # === African languages ===
    SW = "sw"      # Swahili (100M+ speakers)
    AM = "am"      # Amharic (30M speakers)
    HA = "ha"      # Hausa (70M speakers)
    YO = "yo"      # Yoruba (45M speakers)
    ZU = "zu"      # Zulu (12M speakers)


# Human-readable names
LANGUAGE_NAMES: dict[str, str] = {
    # Tier 1
    "en": "English",
    "es": "Spanish",
    "zh": "Chinese (Simplified)",
    "pt": "Portuguese",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "ko": "Korean",
    "it": "Italian",
    "ru": "Russian",
    # Tier 2
    "zh-tw": "Chinese (Traditional)",
    "nl": "Dutch",
    "pl": "Polish",
    "vi": "Vietnamese",
    "th": "Thai",
    "tr": "Turkish",
    "id": "Indonesian",
    "ms": "Malay",
    "tl": "Tagalog",
    # Tier 3 - European
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "el": "Greek",
    "cs": "Czech",
    "sk": "Slovak",
    "hu": "Hungarian",
    "ro": "Romanian",
    "bg": "Bulgarian",
    "hr": "Croatian",
    "sr": "Serbian",
    "sl": "Slovenian",
    "uk": "Ukrainian",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "et": "Estonian",
    # Tier 4 - Indian
    "hi": "Hindi",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Punjabi",
    # RTL
    "ar": "Arabic",
    "he": "Hebrew",
    "fa": "Persian",
    "ur": "Urdu",
    # African
    "sw": "Swahili",
    "am": "Amharic",
    "ha": "Hausa",
    "yo": "Yoruba",
    "zu": "Zulu",
}


# =============================================================================
# Priority Lists for Cache Warming
# =============================================================================


# Languages to pre-warm cache for (highest traffic expected)
WARM_UP_LANGUAGES: list[Language] = [
    Language.ES,     # Spanish - huge market
    Language.FR,     # French - Europe + Africa
    Language.DE,     # German - Europe
    Language.PT,     # Portuguese - Brazil + Portugal
    Language.ZH,     # Chinese - massive market
    Language.JA,     # Japanese - tech-savvy elderly population
    Language.KO,     # Korean - tech-savvy
    Language.IT,     # Italian - large diaspora
    Language.NL,     # Dutch - high English fluency but prefer native
    Language.PL,     # Polish - large diaspora
    Language.VI,     # Vietnamese - large diaspora in US
    Language.RU,     # Russian - large population
]


# RTL languages (need special UI handling)
RTL_LANGUAGES: list[Language] = [
    Language.AR,
    Language.HE,
    Language.FA,
    Language.UR,
]


# All supported (for API)
SUPPORTED_LANGUAGES = list(Language)


# LTR only (for simpler UI implementations)
LTR_LANGUAGES = [lang for lang in Language if lang not in RTL_LANGUAGES]


# =============================================================================
# Utilities
# =============================================================================


def get_language_name(code: str) -> str:
    """Get human-readable language name."""
    return LANGUAGE_NAMES.get(code.lower(), code)


def normalize_language_code(code: str) -> str:
    """Normalize language code to standard form."""
    code = code.lower().strip()
    
    # Handle common variants
    variants = {
        "english": "en",
        "spanish": "es",
        "french": "fr",
        "german": "de",
        "chinese": "zh",
        "japanese": "ja",
        "korean": "ko",
        "portuguese": "pt",
        "italian": "it",
        "russian": "ru",
        "arabic": "ar",
        "hindi": "hi",
        "dutch": "nl",
        "polish": "pl",
        "vietnamese": "vi",
        "thai": "th",
        "turkish": "tr",
        "indonesian": "id",
        "swedish": "sv",
        "norwegian": "no",
        "danish": "da",
        "finnish": "fi",
        "greek": "el",
        "czech": "cs",
        "hungarian": "hu",
        "romanian": "ro",
        "ukrainian": "uk",
        "hebrew": "he",
        "persian": "fa",
        "farsi": "fa",
        "bengali": "bn",
        "tamil": "ta",
        "telugu": "te",
        "swahili": "sw",
        # Common misspellings
        "portugese": "pt",
        "tagalo": "tl",
    }
    
    return variants.get(code, code)


def is_rtl(code: str) -> bool:
    """Check if language is right-to-left."""
    code = normalize_language_code(code)
    return code in ["ar", "he", "fa", "ur"]


def get_language_by_code(code: str) -> Language | None:
    """Get Language enum by code."""
    code = normalize_language_code(code)
    try:
        return Language(code)
    except ValueError:
        return None
