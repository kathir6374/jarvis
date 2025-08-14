
import speech_recognition as sr

def listen_multilingual(recognizer: sr.Recognizer, microphone: sr.Microphone):
    """
    Listens for voice input and tries Tamil first, then English.
    Handles Tanglish by falling back to English mode.
    """
    with microphone as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source)

    # Try Tamil mode
    try:
        text_ta = recognizer.recognize_google(audio, language='ta-IN')
        if text_ta.strip():
            print(f"[Tamil detected] {text_ta}")
            return text_ta
    except Exception:
        pass

    # Fallback to English/Tanglish
    try:
        text_en = recognizer.recognize_google(audio, language='en-IN')
        if text_en.strip():
            print(f"[English/Tanglish detected] {text_en}")
            return text_en
    except Exception:
        pass

    return ""

"""
Advanced Jarvis – fixed & upgraded (+ multilingual I/O: Tamil, English, Tanglish)

Adds:
- LanguageManager: detects Tamil/English/Tanglish, translates both ways, and speaks in same language
- Routes commands in English but replies in user's language (including Tanglish)
- gTTS speech with fallback to obj.tts
- Safe fallbacks when translation/TTS fails
"""
#from __future__ import annotations
import os
import re
import sys
import time
import json
import math
import queue
import random
import ctypes
import shutil
import platform
import datetime
import threading
import subprocess
from dataclasses import dataclass
from typing import Optional, Dict, Callable, Pattern, Tuple

# Third-party
import requests
import pyautogui
import pywhatkit
import pyjokes
import wikipedia
from PIL import Image
from PyQt5.QtCore import QTimer, QTime, QDate, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QMovie
from PyQt5.QtWidgets import QMainWindow, QApplication

# Language stack (all optional, handled with fallbacks)
try:
    from langdetect import detect
except Exception:
    detect = None
try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None
try:
    from gtts import gTTS
    import playsound
except Exception:
    gTTS = None
    playsound = None

# Selenium (for Chrome control)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

# Local package bits
from Jarvis import JarvisAssistant
from Jarvis.features.gui import Ui_MainWindow
from Jarvis.config import config

# ================================ UTIL / CONSTANTS ==========================================
obj = JarvisAssistant()

GREETINGS = [
    "hello jarvis", "jarvis", "wake up jarvis", "you there jarvis",
    "time to work jarvis", "hey jarvis", "ok jarvis", "are you there"
]
GREETINGS_RES = [
    "always there for you sir", "i am ready sir",
    "your wish my command", "how can i help you sir?", "i am online and ready sir"
]

EMAIL_DIC = {
    'myself': 'atharvaaingle@gmail.com',
    'my official email': 'atharvaaingle@gmail.com',
    'my second email': 'atharvaaingle@gmail.com',
    'my official mail': 'atharvaaingle@gmail.com',
    'my second mail': 'atharvaaingle@gmail.com'
}

CALENDAR_STRS = ["what do i have", "do i have plans", "am i busy"]

SOCIAL_MEDIA_LINKS = {
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://twitter.com",
    "x": "https://twitter.com",
    "linkedin": "https://www.linkedin.com",
    "youtube": "https://www.youtube.com/",
    "reddit": "https://www.reddit.com",
    "tiktok": "https://www.tiktok.com",
    "pinterest": "https://www.pinterest.com",
    "snapchat": "https://www.snapchat.com"
}

IS_WINDOWS = platform.system().lower() == "windows"

# ================================ MULTILINGUAL LAYER ========================================

class LanguageManager:
    """
    Detects user language (en/ta + Tanglish heuristic), translates to/from English,
    and speaks back in the same language. If Tanglish is detected, console shows
    romanized Tanglish while TTS speaks proper Tamil.
    """
    # A tiny list of frequent romanized Tamil tokens to spot Tanglish quickly
    _TANGLISH_HINTS = [
        "vanakkam", "saptingla", "saptinglaa", "saptiya", "eppadi", "enna", "epdi",
        "seri", "ille", "illai", "podu", "venum", "thambi", "akka", "anna",
        "ungalukku", "enaku", "na", "naan", "podunga", "thooku", "veetla",
        "pa", "da", "amma", "appa", "nanri", "romba", "super", "semma"
    ]

    # Basic Tamil->Latin map (minimal but readable Tanglish)
    _TA2LAT = [
        ("க்ஷ", "ksha"), ("ஞ்", "nj"), ("ங்", "ng"), ("ச்", "ch"), ("ண்", "n"),
        ("த்", "th"), ("த்", "t"), ("ந்", "n"), ("ப்", "p"), ("ம்", "m"),
        ("ய்", "y"), ("ர்", "r"), ("ல்", "l"), ("வ்", "v"), ("ழ்", "zh"),
        ("ள்", "L"), ("ற்", "R"), ("ன்", "n"),
        ("அ", "a"), ("ஆ", "aa"), ("இ", "i"), ("ஈ", "ii"), ("உ", "u"), ("ஊ", "uu"),
        ("எ", "e"), ("ஏ", "ee"), ("ஐ", "ai"), ("ஒ", "o"), ("ஓ", "oo"), ("ஔ", "au"),
        ("அ", "a"), ("ா", "aa"), ("ி", "i"), ("ீ", "ii"), ("ு", "u"), ("ூ", "uu"),
        ("ெ", "e"), ("ே", "ee"), ("ை", "ai"), ("ொ", "o"), ("ோ", "oo"), ("ௌ", "au"),
        ("க்", "k"), ("க", "ka"), ("ச", "sa"), ("ஞ", "nja"), ("ட", "ta"), ("ண", "na"),
        ("த", "tha"), ("ந", "na"), ("ப", "pa"), ("ம", "ma"), ("ய", "ya"), ("ர", "ra"),
        ("ல", "la"), ("வ", "va"), ("ழ", "zha"), ("ள", "La"), ("ற", "Ra"), ("ன", "na"),
        # digits
        ("௦","0"),("௧","1"),("௨","2"),("௩","3"),("௪","4"),("௫","5"),("௬","6"),("௭","7"),("௮","8"),("௯","9"),
    ]

    def __init__(self):
        self.last_lang: str = "en"
        self.is_tanglish: bool = False

    # ---- detection ----
    def detect_lang(self, text: str) -> Tuple[str, bool]:
        text = (text or "").strip()
        if not text:
            return ("en", False)

        # Tanglish heuristic: English letters but with many Tamil romanized tokens
        lowered = text.lower()
        hint_hits = sum(1 for w in self._TANGLISH_HINTS if w in lowered)
        looks_english_letters = bool(re.fullmatch(r"[0-9A-Za-z\s\.\,\-\?\!\:;\'\"]+", lowered))

        lang = "en"
        if detect:
            try:
                lang = detect(text)
            except Exception:
                lang = "en"

        is_tanglish = (lang == "en") and looks_english_letters and (hint_hits >= 1)
        return ("ta" if lang == "ta" else "en", is_tanglish)

    # ---- translation ----
    def _translate(self, text: str, src: str, dst: str) -> str:
        if not text:
            return text
        if src == dst:
            return text
        if GoogleTranslator is None:
            return text  # graceful fallback
        try:
            # deep_translator accepts 'auto' too; we pass explicit src if known
            translator = GoogleTranslator(source=src or "auto", target=dst)
            return translator.translate(text)
        except Exception:
            return text

    def to_english(self, text: str, src_lang: str, is_tanglish: bool) -> str:
        # If Tanglish, first translate to Tamil, then Tamil->English for better accuracy
        if is_tanglish:
            ta = self._translate(text, "auto", "ta")
            return self._translate(ta, "ta", "en")
        # Normal path
        return self._translate(text, src_lang or "auto", "en")

    def from_english(self, text_en: str, target_lang: str, as_tanglish: bool) -> Tuple[str, str]:
        """
        Returns (display_text, tts_text).
        - For Tamil target: display Tanglish when needed; TTS always uses Tamil script
        - For English target: both are English
        """
        if target_lang == "en":
            return (text_en, text_en)

        # English -> Tamil
        ta = self._translate(text_en, "en", "ta")
        if as_tanglish:
            return (self.tamil_to_tanglish(ta), ta)  # show Tanglish, speak Tamil
        return (ta, ta)

    # ---- transliteration (very lightweight) ----
    def tamil_to_tanglish(self, s: str) -> str:
        if not s:
            return s
        out = s
        for ta, lat in self._TA2LAT:
            out = out.replace(ta, lat)
        return out

    # ---- TTS ----
    def speak(self, text: str, lang: str):
        # Try gTTS if available; else JarvisAssistant's tts; else print
        if gTTS and playsound:
            try:
                # map aliases
                lang_map = {"en": "en", "ta": "ta"}
                use_lang = lang_map.get(lang, "en")
                fn = "temp_reply.mp3"
                gTTS(text=text, lang=use_lang).save(fn)
                playsound.playsound(fn)
                try:
                    os.remove(fn)
                except Exception:
                    pass
                return
            except Exception:
                pass
        # fallback to JarvisAssistant
        try:
            obj.tts(text)
        except Exception:
            print(f"[SAY]: {text}")

# keep simple direct wrapper (used outside MainThread sometimes)
def speak(text: str):
    try:
        obj.tts(text)
    except Exception:
        print(f"[SAY]: {text}")

# ================================ CHROME ASSISTANT ==========================================

class ChromeAssistant:
    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None

    def start(self):
        if self.driver:
            return
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_experimental_option("detach", True)
        self.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

    def ensure(self):
        if not self.driver:
            self.start()
        return self.driver

    def open_url(self, url: str):
        d = self.ensure()
        if not url.startswith("http"):
            url = "https://" + url
        d.get(url)

    def search(self, query: str):
        d = self.ensure()
        if not d.current_url or "google" not in d.current_url:
            d.get("https://www.google.com")
        box = d.find_element(By.NAME, "q")
        box.clear()
        box.send_keys(query)
        box.send_keys(Keys.ENTER)

    def new_tab(self, url: Optional[str] = None):
        d = self.ensure()
        d.switch_to.new_window('tab')
        if url:
            self.open_url(url)

    def close_tab(self):
        d = self.ensure()
        d.close()

    def next_tab(self):
        d = self.ensure()
        handles = d.window_handles
        idx = handles.index(d.current_window_handle)
        d.switch_to.window(handles[(idx + 1) % len(handles)])

    def prev_tab(self):
        d = self.ensure()
        handles = d.window_handles
        idx = handles.index(d.current_window_handle)
        d.switch_to.window(handles[(idx - 1) % len(handles)])

    def back(self):
        self.ensure().back()

    def forward(self):
        self.ensure().forward()

    def scroll_down(self, amount: int = 800):
        d = self.ensure()
        d.execute_script(f"window.scrollBy(0, {int(amount)});")

    def scroll_up(self, amount: int = 800):
        d = self.ensure()
        d.execute_script(f"window.scrollBy(0, -{int(amount)});")

# ================================ SYSTEM CONTROL ============================================

class SystemController:
    def lock(self):
        if IS_WINDOWS:
            ctypes.windll.user32.LockWorkStation()
        else:
            subprocess.call(["xdg-screensaver", "lock"]) if shutil.which("xdg-screensaver") else None

    def sleep(self):
        if IS_WINDOWS:
            subprocess.call(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], shell=True)
        else:
            subprocess.call(["systemctl", "suspend"]) if shutil.which("systemctl") else None

    def shutdown(self):
        if IS_WINDOWS:
            os.system("shutdown /s /t 0")
        else:
            os.system("shutdown -h now")

    def restart(self):
        if IS_WINDOWS:
            os.system("shutdown /r /t 0")
        else:
            os.system("shutdown -r now")

    def logoff(self):
        if IS_WINDOWS:
            os.system("shutdown /l")

    def volume_mute(self):
        if IS_WINDOWS:
            pyautogui.press("volumemute")

    def volume_up(self, steps: int = 5):
        for _ in range(max(1, steps)):
            pyautogui.press("volumeup")

    def volume_down(self, steps: int = 5):
        for _ in range(max(1, steps)):
            pyautogui.press("volumedown")

    def open_app(self, name: str):
        name = name.strip().strip('"').lower()
        if shutil.which(name):
            subprocess.Popen([name])
            return True
        try:
            os.startfile(name)  # type: ignore[attr-defined]
            return True
        except Exception:
            pass
        known = {
            'chrome': r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            'notepad': "notepad.exe",
            'cmd': "cmd.exe",
            'powershell': "powershell.exe"
        }
        path = known.get(name)
        if path and os.path.exists(path) or shutil.which(path or ""):
            subprocess.Popen([path])
            return True
        return False

# ================================ AI / KNOWLEDGE ===========================================

class AIClient:
    def __init__(self, openai_key: Optional[str]):
        self.openai_key = openai_key
        self._openai = None
        if openai_key:
            try:
                from openai import OpenAI
                self._openai = OpenAI(api_key=openai_key)
            except Exception:
                self._openai = None

    def ask(self, prompt: str) -> str:
        if self._openai:
            try:
                model_name = getattr(config, 'openai_model', 'gpt-4o-mini')
                resp = self._openai.chat.completions.create(model=model_name, messages=[
                    {"role": "system", "content": "You are Jarvis, a concise, helpful desktop assistant."},
                    {"role": "user", "content": prompt}
                ])
                return resp.choices[0].message.content.strip()
            except Exception:
                pass
        try:
            import wolframalpha as wf
            app_id = getattr(config, 'wolframalpha_id', None)
            if app_id:
                client = wf.Client(app_id)
                answer = client.query(prompt)
                return next(answer.results).text
        except Exception:
            pass
        try:
            wikipedia.set_lang("en")
            return wikipedia.summary(prompt, sentences=2)
        except Exception:
            return "Sorry, I couldn't fetch that right now."

# ================================ MAIN WORKER THREAD ========================================

class MainThread(QThread):
    status = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.screenshot_name: Optional[str] = None
        self.chrome = ChromeAssistant()
        self.system = SystemController()
        self.ai = AIClient(getattr(config, 'openai_api_key', None))
        self._stop_flag = False

        # multilingual state
        self.langman = LanguageManager()
        self.current_lang = "en"    # 'en' or 'ta'
        self.is_tanglish = False    # show romanized if True

    def run(self):
        self.TaskExecution()

    def stop(self):
        self._stop_flag = True

    # === Centralized, language-aware speak+status ===
    def _say_and_status(self, english_text: str):
        """
        Accepts English text, translates to user's language (Tamil/English),
        displays Tanglish if needed, and speaks in that language.
        """
        try:
            display_text, tts_text = self.langman.from_english(
                english_text, self.current_lang, self.is_tanglish
            )
        except Exception:
            display_text, tts_text = english_text, english_text

        # Speak
        try:
            self.langman.speak(tts_text, self.current_lang)
        except Exception:
            try:
                obj.tts(tts_text)
            except Exception:
                print(f"[SAY]: {tts_text}")

        # Update GUI/console
        try:
            self.status.emit(display_text)
        except Exception:
            pass

    # Convenience for prompts that must be in user's language
    def _ask_user(self, english_prompt: str) -> str:
        self._say_and_status(english_prompt)
        try:
            heard = obj.mic_input()
        except Exception:
            heard = ""
        return heard or ""

    def TaskExecution(self):
        self._startup()
        self._say_and_status("Please tell me how may I help you")

        while not self._stop_flag:
            try:
                raw = obj.mic_input().strip()
            except Exception:
                raw = ""
            if not raw:
                continue

            # Detect language and prep for routing
            lang, tanglish = self.langman.detect_lang(raw)
            self.current_lang = lang
            self.is_tanglish = tanglish

            # Route commands in EN
            try:
                command = self.langman.to_english(raw, lang, tanglish).lower().strip()
            except Exception:
                command = raw.lower().strip()

            # ==== quick replies ====
            if command in GREETINGS:
                self._say_and_status(random.choice(GREETINGS_RES))
                continue

            # ==== time & date ====
            if re.search(r"\bdate\b", command):
                date = obj.tell_me_date()
                self._say_and_status(date)
                continue
            if re.search(r"\btime\b", command):
                time_c = obj.tell_time()
                self._say_and_status(f"Sir the time is {time_c}")
                continue

            # ==== chrome assistant ====
            if command.startswith("open chrome"):
                self.chrome.start()
                self._say_and_status("Chrome is ready.")
                continue
            if command.startswith("search for ") or command.startswith("google "):
                q = command.replace("search for ", "").replace("google ", "").strip()
                self.chrome.search(q)
                self._say_and_status(f"Searching for {q} in Chrome")
                continue
            if command.startswith("open url "):
                url = command.replace("open url ", "").strip()
                self.chrome.open_url(url)
                self._say_and_status(f"Opening {url} in Chrome")
                continue
            if command == "new tab" or command.startswith("new tab "):
                suffix = command.replace("new tab", "").strip()
                url = suffix if suffix else None
                self.chrome.new_tab(url)
                self._say_and_status("Opened new tab")
                continue
            if command in ("close tab", "close this tab"):
                self.chrome.close_tab()
                self._say_and_status("Closed tab")
                continue
            if command in ("next tab", "switch tab"):
                self.chrome.next_tab()
                self._say_and_status("Switched to next tab")
                continue
            if command in ("previous tab", "prev tab"):
                self.chrome.prev_tab()
                self._say_and_status("Switched to previous tab")
                continue
            if command in ("back", "go back"):
                self.chrome.back(); self._say_and_status("Going back")
                continue
            if command in ("forward", "go forward"):
                self.chrome.forward(); self._say_and_status("Going forward")
                continue
            if command in ("scroll down", "page down"):
                self.chrome.scroll_down(); self._say_and_status("Scrolled down")
                continue
            if command in ("scroll up", "page up"):
                self.chrome.scroll_up(); self._say_and_status("Scrolled up")
                continue

            # ==== simple app launch ====
            if command.startswith("launch ") or command.startswith("open app "):
                app = command.replace("launch ", "").replace("open app ", "").strip()
                ok = self.system.open_app(app)
                self._say_and_status(f"Launching {app}" if ok else f"Couldn't find {app}")
                continue

            # ==== social / sites ====
            if command.startswith("open ") and len(command.split()) == 2:
                site = command.split()[1]
                url = SOCIAL_MEDIA_LINKS.get(site)
                if url:
                    obj.website_opener(url)
                    self._say_and_status(f"Opening {site}")
                    continue

            # ==== weather ====
            if "weather" in command:
                parts = command.split()
                city = parts[-1] if parts else ""
                weather_res = obj.weather(city=city)
                self._say_and_status(weather_res)
                continue

            # ==== wikipedia ====
            if command.startswith("tell me about "):
                topic = command.replace("tell me about ", "").strip()
                if topic:
                    wiki_res = obj.tell_me(topic)
                    self._say_and_status(wiki_res)
                else:
                    self._say_and_status("Sorry sir. Please say the topic again.")
                continue

            # ==== news ====
            if any(w in command for w in ("buzzing", "news", "headlines")):
                news_res = obj.news()
                self._say_and_status('Source: The Times Of India')
                self._say_and_status("Today's headlines are…")
                for index, articles in enumerate(news_res):
                    title = articles.get('title', '')
                    # translate each title to user's language for speaking/console
                    disp, tts = self.langman.from_english(title, self.current_lang, self.is_tanglish)
                    self.langman.speak(tts, self.current_lang)
                    try:
                        self.status.emit(disp)
                    except Exception:
                        pass
                    if index >= 9:
                        break
                self._say_and_status('These were the top headlines. Have a nice day Sir!')
                continue

            # ==== web search ====
            if 'search google for' in command:
                obj.search_anything_google(command)
                continue

            # ==== music ====
            if any(p in command for p in ("play music", "hit some music")):
                music_dir = getattr(config, 'music_folder', None) or os.path.expanduser("~/Music")
                if os.path.isdir(music_dir):
                    songs = [os.path.join(music_dir, s) for s in os.listdir(music_dir)]
                    for song in songs:
                        try:
                            os.startfile(song)  # type: ignore[attr-defined]
                        except Exception:
                            pass
                    self._say_and_status("Enjoy the music, Sir")
                else:
                    self._say_and_status("Music folder not found in config or ~/Music")
                continue

            # ==== YouTube ====
            if command.startswith('youtube'):
                video = command.replace('youtube', '').strip()
                if video:
                    self._say_and_status(f"Okay sir, playing {video} on YouTube")
                    pywhatkit.playonyt(video)
                else:
                    self._say_and_status("Please tell me what to play on YouTube.")
                continue

            # ==== Email ====
            if "send email" in command or command == "email":
                sender_email = getattr(config, 'email', None)
                sender_password = getattr(config, 'email_password', None)
                if not (sender_email and sender_password):
                    self._say_and_status("Email is not configured in settings.")
                    continue
                try:
                    recipient = self._ask_user("Whom do you want to email sir ?").strip().lower()
                    receiver_email = EMAIL_DIC.get(recipient)
                    if receiver_email:
                        subject = self._ask_user("What is the subject sir ?")
                        message = self._ask_user("What should I say?")
                        msg = f'Subject: {subject}\n\n{message}'
                        obj.send_mail(sender_email, sender_password, receiver_email, msg)
                        self._say_and_status("Email has been successfully sent")
                    else:
                        self._say_and_status("I couldn't find that email in my database.")
                except Exception:
                    self._say_and_status("Sorry sir. Couldn't send your mail. Please try again.")
                continue

            # ==== Calculator / Q&A ====
            if command.startswith("calculate") or command.startswith("what is") or command.startswith("who is"):
                ans = self.ai.ask(command)
                self._say_and_status(ans)
                continue

            # ==== Calendar ====
            if any(phrase in command for phrase in CALENDAR_STRS):
                try:
                    obj.google_calendar_events(command)
                except Exception:
                    self._say_and_status("Calendar error. Please check credentials.")
                continue

            # ==== Notes ====
            if any(p in command for p in ("make a note", "write this down", "remember this")):
                note_text = self._ask_user("What would you like me to write down?")
                obj.take_note(note_text)
                self._say_and_status("I've made a note of that")
                continue
            if any(p in command for p in ("close the note", "close notepad")):
                self._say_and_status("Okay sir, closing notepad")
                os.system("taskkill /f /im notepad.exe")
                os.system("taskkill /f /im notepad++.exe")
                continue

            # ==== Jokes ====
            if "joke" in command:
                try:
                    joke = pyjokes.get_joke()
                except Exception:
                    joke = "Why did the function return early? Because it had a base case!"
                self._say_and_status(joke)
                continue

            # ==== System info ====
            if "system" in command:
                try:
                    sys_info = obj.system_info()
                except Exception:
                    sys_info = platform.platform()
                self._say_and_status(str(sys_info))
                continue

            # ==== Location ====
            if command.startswith("where is "):
                place = command.split('where is ', 1)[1]
                try:
                    current_loc, target_loc, distance = obj.location(place)
                    city = target_loc.get('city', '')
                    state = target_loc.get('state', '')
                    country = target_loc.get('country', '')
                    if city:
                        res = f"{place} is in {state} state and country {country}. It is {distance} km away from your current location"
                    else:
                        res = f"{state} is a state in {country}. It is {distance} km away from your current location"
                    self._say_and_status(res)
                except Exception:
                    self._say_and_status("Sorry, I couldn't fetch the location.")
                continue

            # ==== IP ====
            if "ip address" in command:
                try:
                    ip = requests.get('https://api.ipify.org', timeout=5).text
                    self._say_and_status(f"Your IP address is {ip}")
                except Exception:
                    self._say_and_status("Couldn't fetch the IP address right now.")
                continue

            # ==== Window switching ====
            if any(p in command for p in ("switch the window", "switch window")):
                self._say_and_status("Okay sir, switching the window")
                pyautogui.keyDown("alt"); pyautogui.press("tab"); time.sleep(1); pyautogui.keyUp("alt")
                continue

            # ==== Current location (self) ====
            if any(p in command for p in ("where i am", "current location", "where am i")):
                try:
                    city, state, country = obj.my_location()
                    self._say_and_status(f"You are currently in {city} city which is in {state} state and country {country}")
                except Exception:
                    self._say_and_status("Sorry sir, I couldn't fetch your current location.")
                continue

            # ==== Screenshot ====
            if "take screenshot" in command:
                name_q = self._ask_user("By what name do you want to save the screenshot?")
                self.screenshot_name = (name_q.strip().replace(' ', '_') or f"screenshot_{int(time.time())}")
                self._say_and_status("Alright sir, taking the screenshot")
                img = pyautogui.screenshot()
                filename = f"{self.screenshot_name}.png"
                img.save(filename)
                self._say_and_status(f"Screenshot saved as {filename}")
                continue
            if "show me the screenshot" in command:
                if self.screenshot_name and os.path.exists(f"{self.screenshot_name}.png"):
                    try:
                        Image.open(f"{self.screenshot_name}.png").show()
                        self._say_and_status("Here it is sir")
                    except Exception:
                        self._say_and_status("Sorry, I am unable to display the screenshot")
                else:
                    self._say_and_status("No screenshot found. Please take one first.")
                continue

            # ==== Hide/Unhide files (folder) ====
            if any(p in command for p in ("hide all files", "hide this folder")):
                if IS_WINDOWS:
                    os.system("attrib +h /s /d")
                    self._say_and_status("Sir, all the files in this folder are now hidden")
                else:
                    self._say_and_status("Hide attribute is Windows-only")
                continue
            if any(p in command for p in ("visible", "make files visible")):
                if IS_WINDOWS:
                    os.system("attrib -h /s /d")
                    self._say_and_status("Sir, all the files in this folder are now visible to everyone")
                else:
                    self._say_and_status("Unhide attribute is Windows-only")
                continue

            # ==== System power commands ====
            if command in ("lock", "lock system", "lock pc"):
                self.system.lock(); continue
            if command in ("sleep", "go to sleep"):
                self.system.sleep(); continue
            if command in ("shutdown", "power off"):
                self.system.shutdown(); continue
            if command in ("restart", "reboot"):
                self.system.restart(); continue
            if command in ("log off", "sign out"):
                self.system.logoff(); continue
            if command in ("mute", "mute volume"):
                self.system.volume_mute(); continue
            if command.startswith("volume up"):
                m = re.search(r"volume up( \d+)?", command)
                steps = int(m.group(1)) if m and m.group(1) else 5
                self.system.volume_up(steps); continue
            if command.startswith("volume down"):
                m = re.search(r"volume down( \d+)?", command)
                steps = int(m.group(1)) if m and m.group(1) else 5
                self.system.volume_down(steps); continue

            # ==== Goodbye ====
            if any(p in command for p in ("goodbye", "offline", "bye")):
                self._say_and_status("Alright sir, going offline. It was nice working with you")
                os._exit(0)

            # ==== Fallback: AI chat ====
            fallback = self.ai.ask(command)
            self._say_and_status(fallback)

    def _startup(self):
        # Greeting in English first (safe), then say current time in user's language once detected later
        try:
            obj.tts("Now I am online")
        except Exception:
            print("[SAY]: Now I am online")
        hour = int(datetime.datetime.now().hour)
        if 0 <= hour <= 12:
            speak("Good Morning")
        elif 12 < hour < 18:
            speak("Good afternoon")
        else:
            speak("Good evening")
        c_time = obj.tell_time()
        speak(f"Currently it is {c_time}")
        speak("I am Jarvis. Online and ready sir.")

# ================================ MAIN APP (GUI) ============================================

startExecution = MainThread()

class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.pushButton.clicked.connect(self.startTask)
        self.ui.pushButton_2.clicked.connect(self.close)
        try:
            startExecution.status.connect(self._append_status)
        except Exception:
            pass

    def __del__(self):
        sys.stdout = sys.__stdout__

    def startTask(self):
        try:
            self.ui.movie = QMovie("Jarvis/utils/images/live_wallpaper.gif")
            self.ui.label.setMovie(self.ui.movie)
            self.ui.movie.start()
        except Exception:
            pass

        try:
            self.ui.movie2 = QMovie("Jarvis/utils/images/initiating.gif")
            self.ui.label_2.setMovie(self.ui.movie2)
            self.ui.movie2.start()
        except Exception:
            pass

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.showTime)
        self.timer.start(1000)

        startExecution.start()

    def showTime(self):
        current_time = QTime.currentTime()
        current_date = QDate.currentDate()
        label_time = current_time.toString('hh:mm:ss')
        label_date = current_date.toString(Qt.ISODate)
        try:
            self.ui.textBrowser.setText(label_date)
            self.ui.textBrowser_2.setText(label_time)
        except Exception:
            pass

    def _append_status(self, text: str):
        try:
            curr = self.ui.console.toPlainText() if hasattr(self.ui, 'console') else ''
            new_txt = (curr + "\n" + text).strip()
            if hasattr(self.ui, 'console'):
                self.ui.console.setPlainText(new_txt)
        except Exception:
            pass


def main():
    app = QApplication(sys.argv)
    jarvis = Main()
    jarvis.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
