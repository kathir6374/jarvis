# google_search.py
# language-aware Google search helper (callable, no input())
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import re
import os
import time

# Try to use gTTS for language TTS if available; else fallback to prints
try:
    from gtts import gTTS
    import playsound
except Exception:
    gTTS = None
    playsound = None

# Minimal tanglish hint list (same as main LanguageManager if needed)
_TANGLISH_HINTS = [
    "vanakkam", "saptingla", "eppadi", "enna", "seri", "ille", "illai",
    "venum", "thambi", "akka", "anna", "ungalukku", "enaku", "naan", "nanri"
]

def _is_tanglish(text: str) -> bool:
    t = (text or "").lower()
    hits = sum(1 for w in _TANGLISH_HINTS if w in t)
    looks_roman = bool(re.fullmatch(r"[0-9A-Za-z\s\.\,\-\?\!\:;\'\"]+", t))
    return hits >= 1 and looks_roman

def _speak(text: str, lang: str = "en"):
    if gTTS and playsound:
        try:
            fn = f"tmp_google_search_{int(time.time()*1000)}.mp3"
            gTTS(text=text, lang=lang).save(fn)
            playsound.playsound(fn)
            try:
                os.remove(fn)
            except Exception:
                pass
            return
        except Exception:
            pass
    # fallback
    print("[SAY]:", text)

def google_search(query: str, tts_lang: str = "en"):
    """
    Performs a Google search in a browser.
    - query: search string (can be Tamil / Tanglish / English)
    - tts_lang: language code for TTS ('en' or 'ta'); helper will speak a confirmation
    """
    if not query:
        _speak("No query provided", tts_lang)
        return

    # Start browser (assumes chromedriver in PATH or webdriver_manager used externally)
    try:
        # best-effort: try to use webdriver_manager if available
        from selenium.webdriver.chrome.service import Service as ChromeService
        from webdriver_manager.chrome import ChromeDriverManager
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    except Exception:
        # fallback: try to use default constructor (requires chromedriver in PATH)
        try:
            driver = webdriver.Chrome()
        except Exception as e:
            _speak("Could not start Chrome for searching.", tts_lang)
            print("Chrome start error:", e)
            return

    try:
        driver.get("https://www.google.com")
        search_box = driver.find_element("name", "q")
        search_box.clear()
        search_box.send_keys(query)
        search_box.send_keys(Keys.RETURN)
        _speak(f"Searching for {query}", tts_lang)
    except Exception as e:
        _speak("Search failed", tts_lang)
        print("Search error:", e)
