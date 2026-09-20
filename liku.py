"""
Liku - A free voice assistant for Windows.

This is the main file. It listens for the wake word "Hey Liku",
then processes your voice command: opening apps, playing YouTube,
controlling volume, chatting with a local AI, and more.

Uses Google's free Speech Recognition for accurate voice understanding
(same engine as Google Search voice input — no API key needed).
Falls back to Vosk offline recognition when there's no internet.

Author: Built with love for beginners.
"""

# =============================================================================
# IMPORTS
# =============================================================================
import io
import os
import re
import sys
import json
import time
import shutil
import ctypes
import asyncio
import difflib
import subprocess
import webbrowser
import threading
import queue
import urllib.parse
from datetime import datetime

# Suppress pygame welcome banner
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

# Third-party imports (install via: pip install -r requirements.txt)
try:
    import sounddevice as sd
except ImportError:
    sd = None

try:
    from vosk import Model, KaldiRecognizer
except ImportError:
    Model = None
    KaldiRecognizer = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import edge_tts
except ImportError:
    edge_tts = None

try:
    import pygame
except ImportError:
    pygame = None

try:
    import ollama
except ImportError:
    ollama = None  # We'll handle this gracefully later

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None  # Screenshots won't work, but everything else will

try:
    import yt_dlp
except ImportError:
    yt_dlp = None  # YouTube search won't work, but everything else will

try:
    import speech_recognition as sr
except ImportError:
    sr = None  # Google Speech Recognition won't work, Vosk will be used instead


# =============================================================================
# CONFIGURATION
# =============================================================================

# Voice settings:
# Realistic human young female voices:
#   "en-IN-NeerjaExpressiveNeural" <- Expressive young Indian-English female voice (Default)
#   "en-US-AvaNeural"              <- Warm, sweet, expressive American girl voice
#   "en-US-EmmaNeural"             <- Soft, gentle, pretty young woman voice
#   "en-US-JennyNeural"            <- Cheerful, friendly conversational assistant
NEURAL_VOICE = "en-IN-NeerjaExpressiveNeural"  # Pretty, warm expressive Indian-English girl
VOICE_PITCH = "+2Hz"    # Slightly bright, cheerful tone
VOICE_SPEED = "-3%"     # Slightly slower for clarity and a more natural feel
USE_NEURAL_VOICE = True # Ultra-realistic human voice with automatic offline fallback

# Multi-language voice settings
# Hindi: warm female voice
HINDI_VOICE = "hi-IN-SwaraNeural"
HINDI_PITCH = "+2Hz"
HINDI_SPEED = "-3%"

# Odia: female voice
ODIA_VOICE = "or-IN-SubhasiniNeural"
ODIA_PITCH = "+2Hz"
ODIA_SPEED = "-3%"

# Offline voice settings (pyttsx3 fallback)
OFFLINE_VOICE_RATE = 175
OFFLINE_VOICE_VOLUME = 1.0

# How similar a word must be to count as a match (0.0 to 1.0)
WAKE_WORD_THRESHOLD = 0.65   # For wake word fuzzy matching
APP_MATCH_THRESHOLD = 0.6    # For app name fuzzy matching

# How long to wait for a follow-up command after just saying "Hey Liku"
FOLLOW_UP_TIMEOUT = 8  # seconds

# Wake word requirement:
# When ALLOW_DIRECT_COMMANDS = False, Liku strictly requires every command to start with "Hey Liku" or "Liku"!
ALLOW_DIRECT_COMMANDS = False

# When ALLOW_AI_WITHOUT_WAKE_WORD = False, Liku never responds to ambient room speech unless addressed with wake word.
ALLOW_AI_WITHOUT_WAKE_WORD = False



# Ollama model name - defaults to installed model (e.g. phi3:mini or llama3.2:1b)
OLLAMA_MODEL = "phi3:mini"

# Audio settings
SAMPLE_RATE = 16000   # 16 kHz sample rate
CHANNELS = 1          # Mono audio
BLOCK_SIZE = 8000     # Audio block size (0.5 seconds of audio)

# Google Speech Recognition language codes
# These map Liku's current_language to Google's language codes for accurate recognition
GOOGLE_LANG_CODES = {
    "english": "en-IN",   # Indian English — best for Indian accent
    "hindi":   "hi-IN",   # Hindi recognition
    "odia":    "or-IN",   # Odia recognition
}


# =============================================================================
# APPS DICTIONARY
# =============================================================================
# Maps what you SAY -> the Windows command to launch that app.
#
# HOW TO ADD YOUR OWN APP:
#   1. Find the app's .exe path (right-click shortcut -> Properties -> Target)
#   2. Add a new entry like this:
#      "my app": r'"C:\\Program Files\\MyApp\\myapp.exe"',
#   3. You can add multiple names for the same app (aliases).
#
# Example with full path:
#   "photoshop": r'"C:\\Program Files\\Adobe\\Photoshop\\Photoshop.exe"',
# =============================================================================
APPS = {
    # --- Code Editors ---
    "vs code":              "code",
    "vscode":               "code",
    "v s code":             "code",
    "visual studio code":   "code",

    # --- Browsers ---
    "chrome":               "start chrome",
    "google chrome":        "start chrome",
    "edge":                 "start msedge",
    "microsoft edge":       "start msedge",
    "firefox":              "start firefox",

    # --- Windows Built-in ---
    "notepad":              "notepad",
    "calculator":           "calc",
    "calc":                 "calc",
    "paint":                "mspaint",
    "command prompt":       "cmd",
    "cmd":                  "cmd",
    "powershell":           "powershell",
    "file explorer":        "explorer",
    "explorer":             "explorer",
    "task manager":         "taskmgr",
    "settings":             "start ms-settings:",
    "control panel":        "control",
    "snipping tool":        "snippingtool",
    "camera":               "start microsoft.windows.camera:",

    # --- Microsoft Office ---
    "word":                 "start winword",
    "excel":                "start excel",
    "powerpoint":           "start powerpnt",

    # --- Other Apps ---
    "spotify":              "start spotify:",
    "whatsapp":             "start whatsapp:",
}


# =============================================================================
# WEBSITES DICTIONARY
# =============================================================================
# Maps what you SAY -> the URL to open in your default browser.
# "open google" will open the website, NOT search for an app.
# =============================================================================
WEBSITES = {
    "google":           "https://www.google.com",
    "gmail":            "https://mail.google.com",
    "youtube":          "https://www.youtube.com",
    "you tube":         "https://www.youtube.com",
    "the youtube":      "https://www.youtube.com",
    "facebook":         "https://www.facebook.com",
    "instagram":        "https://www.instagram.com",
    "github":           "https://github.com",
    "chatgpt":          "https://chat.openai.com",
    "chat gpt":         "https://chat.openai.com",
    "claude":           "https://claude.ai",
    "linkedin":         "https://www.linkedin.com",
    "amazon":           "https://www.amazon.com",
    "flipkart":         "https://www.flipkart.com",
    "google maps":      "https://maps.google.com",
    "whatsapp web":     "https://web.whatsapp.com",
    "stack overflow":   "https://stackoverflow.com",
    "stackoverflow":    "https://stackoverflow.com",
}


# =============================================================================
# PROCESS NAMES DICTIONARY (for closing apps)
# =============================================================================
# Maps what you SAY -> the Windows process name used by taskkill.
# Find process names in Task Manager -> Details tab.
# =============================================================================
PROCESS_NAMES = {
    "vs code":          "Code.exe",
    "vscode":           "Code.exe",
    "chrome":           "chrome.exe",
    "google chrome":    "chrome.exe",
    "edge":             "msedge.exe",
    "firefox":          "firefox.exe",
    "notepad":          "notepad.exe",
    "calculator":       "Calculator.exe",
    "paint":            "mspaint.exe",
    "word":             "WINWORD.EXE",
    "excel":            "EXCEL.EXE",
    "powerpoint":       "POWERPNT.EXE",
    "spotify":          "Spotify.exe",
    "task manager":     "Taskmgr.exe",
    "command prompt":   "cmd.exe",
    "powershell":       "powershell.exe",
    "file explorer":    "explorer.exe",
}


# =============================================================================
# WINDOWS VIRTUAL KEY CODES (for media controls)
# =============================================================================
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT = 0xB0
VK_MEDIA_PREV = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3

# Flags for keybd_event
KEYEVENTF_KEYDOWN = 0x0000
KEYEVENTF_KEYUP = 0x0002


# =============================================================================
# GLOBAL STATE
# =============================================================================

# When True, the microphone input is ignored (so Liku doesn't hear itself)
is_speaking = False

# Chat history for the AI (keeps the last 12 messages for context)
chat_history = []

# Current language for Liku's responses: "english", "hindi", "odia"
current_language = "english"

# System prompt that tells the AI how to behave
SYSTEM_PROMPT = (
    "You are Liku, a friendly voice assistant. "
    "Reply in one to three short sentences, plain text only, no lists or markdown."
)

# Language-specific greetings and phrases
LANG_PHRASES = {
    "english": {
        "switched":   "Okay! I'll speak in English now.",
        "yes":        "Yes?",
        "goodbye":    "Goodbye! Have a great day!",
        "no_command": "I didn't hear a command. Say Hey Liku again when you're ready.",
        "hello":      "Hello! I'm Liku, your voice assistant. Say Hey Liku to wake me up!",
    },
    "hindi": {
        "switched":   "Theek hai! Ab main Hindi mein baat karungi.",
        "yes":        "Haan, bolo?",
        "goodbye":    "Alvida! Aapka din achha rahe!",
        "no_command": "Maine koi command nahi suni. Phir se Hey Liku boliye.",
        "hello":      "Namaste! Main Liku hoon, aapki voice assistant. Hey Liku bolke mujhe jagaiye!",
    },
    "odia": {
        "switched":   "Thik acha! Mun Odia re kathah kahibi.",
        "yes":        "Hain, bolanti?",
        "goodbye":    "Vidai! Aapanka dina bhalha hagatu!",
        "no_command": "Mun kichi command shuninahin. Pheri Hey Liku bolanti.",
        "hello":      "Namaskar! Mun Liku, aapanka voice assistant. Hey Liku boli mote jaganti!",
    },
}


# =============================================================================
# VOICE OUTPUT - Text to Speech
# =============================================================================

def speak_neural(text, voice=None, pitch=None, rate=None):
    """Speak using Edge-TTS high-definition neural voice — pretty, expressive girl voice."""
    # Select voice/pitch/rate based on current language if not overridden
    if voice is None:
        if current_language == "hindi":
            voice = HINDI_VOICE
            pitch = pitch or HINDI_PITCH
            rate  = rate  or HINDI_SPEED
        elif current_language == "odia":
            voice = ODIA_VOICE
            pitch = pitch or ODIA_PITCH
            rate  = rate  or ODIA_SPEED
        else:
            voice = NEURAL_VOICE
            pitch = pitch or VOICE_PITCH
            rate  = rate  or VOICE_SPEED
    else:
        pitch = pitch or VOICE_PITCH
        rate  = rate  or VOICE_SPEED

    async def _generate():
        communicate = edge_tts.Communicate(
            text,
            voice,
            pitch=pitch,
            rate=rate,
        )
        audio_data = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])
        return audio_data

    loop = asyncio.new_event_loop()
    try:
        audio_data = loop.run_until_complete(_generate())
    finally:
        loop.close()

    if not audio_data:
        raise RuntimeError("No audio returned from neural TTS")

    if not pygame.mixer.get_init():
        pygame.mixer.init(frequency=24000)

    sound_file = io.BytesIO(audio_data)
    pygame.mixer.music.load(sound_file)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(20)

    try:
        pygame.mixer.music.unload()
    except Exception:
        pass


def speak_offline(text):
    """Speak using offline pyttsx3 Windows female voice."""
    if pyttsx3 is None:
        return

    try:
        engine = pyttsx3.init("sapi5")
        engine.setProperty("rate", OFFLINE_VOICE_RATE)
        engine.setProperty("volume", OFFLINE_VOICE_VOLUME)

        # Select the best available female voice (Zira, Heera, etc.)
        for v in engine.getProperty("voices"):
            name_lower = v.name.lower()
            if "zira" in name_lower or "heera" in name_lower or "female" in getattr(v, "gender", "").lower():
                engine.setProperty("voice", v.id)
                break

        engine.say(text)
        engine.runAndWait()
        engine.stop()
        del engine
    except Exception as e:
        print(f"[Offline TTS error]: {e}")


def speak(text):
    """
    Speak the given text out loud.
    Uses the pretty neural voice selected for the current language (English/Hindi/Odia).
    Falls back to offline Windows voice if Edge-TTS is unavailable.
    """
    global is_speaking

    if not text or not text.strip():
        return

    print(f"[Liku]: {text}")

    try:
        is_speaking = True

        # 1. Try neural voice first (Edge-TTS) — pretty girl voice
        if USE_NEURAL_VOICE and edge_tts is not None and pygame is not None:
            try:
                # Try Odia fallback to Hindi if Odia voice is unavailable
                if current_language == "odia":
                    try:
                        speak_neural(text)
                        return
                    except Exception:
                        # Odia voice may not be available — fall back to Hindi
                        speak_neural(text, voice=HINDI_VOICE, pitch=HINDI_PITCH, rate=HINDI_SPEED)
                        return
                speak_neural(text)
                return
            except Exception as e:
                print(f"[Neural TTS notice]: {e} (using offline voice)")

        # 2. Offline fallback (pyttsx3 with female voice)
        speak_offline(text)

    except Exception as e:
        print(f"[Speech error]: {e}")
    finally:
        is_speaking = False


def phrase(key):
    """Return the current-language phrase for a given key (e.g. 'yes', 'goodbye')."""
    return LANG_PHRASES.get(current_language, LANG_PHRASES["english"]).get(
        key, LANG_PHRASES["english"].get(key, "")
    )


# =============================================================================
# BROWSER & NORMALIZATION HELPERS
# =============================================================================

def open_url(url):
    """Safely open a URL in the user's default browser."""
    # 1. Native Windows ShellExecute (most reliable on Windows)
    try:
        if hasattr(os, "startfile"):
            os.startfile(url)
            return True
    except Exception:
        pass

    # 2. Python webbrowser module
    try:
        if webbrowser.open(url):
            return True
    except Exception:
        pass

    # 3. Windows 'start' shell command fallback
    try:
        subprocess.Popen(f'start "" "{url}"', shell=True)
        return True
    except Exception as e:
        print(f"[Browser error]: {e}")
        return False


def normalize_command(command):
    """
    Normalize speech recognition text:
    - Fixes common speech quirks ('you tube' -> 'youtube', 'vs code')
    - Strips leading polite/filler words ('please', 'can you', etc.)
    """
    command = command.lower().strip()
    command = re.sub(r"\b(you\s+tube|u\s+tube)\b", "youtube", command)
    command = re.sub(r"\b(v\s+s\s+code|visual\s+studio\s+code)\b", "vs code", command)

    # Strip leading conversational / polite prefixes repeatedly
    fillers = [
        r"^(?:please|can\s+you|could\s+you|would\s+you|will\s+you)\s+",
        r"^(?:kindly|just|i\s+want\s+to|i\s+want\s+you\s+to|help\s+me)\s+",
        r"^(?:tell\s+me|show\s+me)\s+",
    ]
    changed = True
    while changed:
        changed = False
        for pattern in fillers:
            new_cmd = re.sub(pattern, "", command).strip()
            if new_cmd != command:
                command = new_cmd
                changed = True

    return command


# =============================================================================
# WAKE WORD DETECTION
# =============================================================================

def check_wake_word(text):
    """
    Check if the command starts with the wake word ("Hey Liku", "Liku", etc.)
    Strictly requires the wake word at the beginning of the command.
    If the spoken phrase does not start with 'Hey Liku' or 'Liku', Liku will not trigger.

    Accepts at start:
      'hey liku', 'hi liku', 'hello liku', 'ok liku', 'liku',
      'namaste liku', 'suno liku', 'are liku', and phonetic variants like 'leeku', 'like you'.
    """
    text = text.lower().strip()
    if not text:
        return (False, "")

    # Normalize speech recognition text first
    text = re.sub(r"\b(you\s+tube|u\s+tube)\b", "youtube", text)
    text = re.sub(r"\b(v\s+s\s+code|visual\s+studio\s+code)\b", "vs code", text)
    text = re.sub(r"\bnote\s+pad\b", "notepad", text)

    words = text.split()
    if not words:
        return (False, "")

    liku_variants = [
        "liku", "leeku", "liko", "leku", "liqu", "leko", "lyku", "licoo",
        "like", "look", "lake", "leak", "luck", "luka", "lock", "lego", "leek", "link", "lico", "licu"
    ]
    greetings = [
        "hey", "hi", "hai", "hello", "ok", "okay", "yo", "ay", "ae", "he",
        "namaste", "namaskar", "suno", "sun", "are", "bhai"
    ]

    def is_liku(w):
        return any(difflib.SequenceMatcher(None, w, v).ratio() >= WAKE_WORD_THRESHOLD for v in liku_variants)

    def is_greeting(w):
        return any(difflib.SequenceMatcher(None, w, g).ratio() >= 0.65 for g in greetings)

    # 1. Greeting + "like you" at start (e.g. "hey like you open notepad...")
    if len(words) >= 3 and is_greeting(words[0]):
        if difflib.SequenceMatcher(None, words[1] + " " + words[2], "like you").ratio() >= 0.75:
            cmd = " ".join(words[3:]).strip()
            return (True, cmd)

    # 2. "like you" at start (e.g. "like you write any program...")
    if len(words) >= 2 and difflib.SequenceMatcher(None, words[0] + " " + words[1], "like you").ratio() >= 0.75:
        cmd = " ".join(words[2:]).strip()
        return (True, cmd)

    # 3. Greeting + Liku at start (e.g. "hey liku open notepad and write a python program...")
    if len(words) >= 2 and is_greeting(words[0]) and is_liku(words[1]):
        cmd = " ".join(words[2:]).strip()
        return (True, cmd)

    # 4. Standalone Liku at start (e.g. "liku write any program in notepad")
    if is_liku(words[0]):
        cmd = " ".join(words[1:]).strip()
        return (True, cmd)

    # If it does not start with Liku or Hey Liku, do not trigger
    return (False, "")


def is_direct_command(command):
    """
    Check if a spoken phrase is a clear, actionable command.
    Allows users to say e.g. 'open youtube', 'open vs code', or 'volume up' without
    needing to repeat the wake word if they forgot it.
    """
    cmd = command.lower().strip()
    cmd = normalize_command(cmd)

    # 1. YouTube commands
    if extract_youtube_query(cmd) is not None:
        return True

    # 2. Direct app or website name alone (e.g. "vs code", "chrome", "notepad", "calculator", "spotify")
    if cmd in APPS or cmd in WEBSITES:
        return True

    # 3. Opening apps or websites
    if re.match(r"^(?:open|turn\s+on|launch|start|run|go\s+to|visit)\s+", cmd):
        return True

    # 4. Google search
    if re.match(r"^(?:search\s+google|google\s+search|search\s+for|google)\s+", cmd):
        return True

    # 5. Closing apps
    if re.match(r"^(?:close|kill|shut\s+down|exit)\s+", cmd):
        return True

    # 6. Media & volume
    if any(cmd.startswith(v) for v in ["volume up", "volume down", "mute", "unmute"]):
        return True
    if cmd in ["pause", "resume", "play", "stop", "exit", "quit", "goodbye", "next", "previous", "skip"]:
        return True

    # 7. Utilities
    if "screenshot" in cmd or "screen shot" in cmd:
        return True
    if "lock" in cmd and ("computer" in cmd or "pc" in cmd or "screen" in cmd or "system" in cmd):
        return True
    if "time" in cmd and ("what" in cmd or "tell" in cmd or "current" in cmd):
        return True
    if "date" in cmd and ("what" in cmd or "tell" in cmd or "today" in cmd):
        return True

    return False


# =============================================================================
# APP FINDER (with fuzzy matching and fallbacks)
# =============================================================================

def find_app(name):
    """
    Find the launch command for an app by name.

    Search order:
      1. Exact match in APPS dictionary
      2. Fuzzy match in APPS dictionary (using difflib)
      3. Check if the command exists on PATH (using shutil.which)

    Returns:
        (command, matched_name) if found
        None if not found
    """
    name = name.lower().strip()

    # 1. Exact match
    if name in APPS:
        return (APPS[name], name)

    # 2. Fuzzy match - find the closest app name
    app_names = list(APPS.keys())
    matches = difflib.get_close_matches(name, app_names, n=1, cutoff=APP_MATCH_THRESHOLD)
    if matches:
        matched = matches[0]
        return (APPS[matched], matched)

    # 3. Check if it's a command on the system PATH
    if shutil.which(name):
        return (name, name)

    # 4. Not found
    return None


def find_website(name):
    """
    Find the URL for a website by name, with fuzzy matching.

    Returns:
        (url, matched_name) if found
        None if not found
    """
    name = name.lower().strip()

    # 1. Exact match
    if name in WEBSITES:
        return (WEBSITES[name], name)

    # 2. Fuzzy match
    site_names = list(WEBSITES.keys())
    matches = difflib.get_close_matches(name, site_names, n=1, cutoff=APP_MATCH_THRESHOLD)
    if matches:
        matched = matches[0]
        return (WEBSITES[matched], matched)

    return None


# =============================================================================
# YOUTUBE HANDLER
# =============================================================================

def extract_youtube_query(command):
    """
    Extract the search query from a YouTube-related voice command.

    Handles many spoken variants including speech recognition quirks.
    Returns:
        query string, or "" for just opening YouTube, or None if not a YouTube command
    """
    command = command.lower().strip()
    # Normalize 'you tube' -> 'youtube'
    command = re.sub(r"\b(you\s+tube|u\s+tube)\b", "youtube", command)

    # 1. Just open YouTube (no search)
    open_yt_patterns = [
        r"^(?:open|turn\s+on|launch|start|go\s+to|visit)\s+(?:the\s+)?youtube(?:\.com)?$",
        r"^youtube(?:\.com)?$",
    ]
    for p in open_yt_patterns:
        if re.match(p, command):
            return ""

    # 2. "play <query> on/in youtube"
    m = re.match(r"^play\s+(.+?)\s+(?:on|in)\s+youtube$", command)
    if m:
        return m.group(1).strip()

    # 3. "(turn on / open / launch) youtube (and) play <query>"
    m = re.match(r"^(?:turn\s+on|open|launch)\s+youtube\s+(?:and\s+)?play\s+(.+)$", command)
    if m:
        return m.group(1).strip()

    # 4. "search (for) <query> on/in youtube"
    m = re.match(r"^search\s+(?:for\s+)?(.+?)\s+(?:on|in)\s+youtube$", command)
    if m:
        return m.group(1).strip()

    # 5. "search youtube for/about <query>"
    m = re.match(r"^search\s+youtube\s+(?:for|about)?\s*(.+)$", command)
    if m:
        return m.group(1).strip()

    # 6. "on/in youtube play <query>"
    m = re.match(r"^(?:on|in)\s+youtube\s+play\s+(.+)$", command)
    if m:
        return m.group(1).strip()

    # 7. "youtube <query>" (e.g. "youtube magician video")
    m = re.match(r"^youtube\s+(.+)$", command)
    if m:
        return m.group(1).strip()

    # 8. General "play <query>" (e.g. "play magician video", "play lofi music")
    m = re.match(r"^play\s+(.+)$", command)
    if m:
        query = m.group(1).strip()
        if query not in ["next", "previous", "track", "again"]:
            return query

    return None


def handle_youtube(command):
    """
    Handle YouTube-related commands.
    Opens YouTube and optionally searches for and plays a video.

    Returns True if this was a YouTube command, False otherwise.
    """
    query = extract_youtube_query(command)

    # Not a YouTube command
    if query is None:
        return False

    # Just "open youtube" - no search needed
    if query == "":
        speak("Opening YouTube.")
        open_url("https://www.youtube.com")
        return True

    # Search YouTube for the query
    if yt_dlp is None:
        speak("Sorry, yt-dlp is not installed. I cannot search YouTube. "
              "Please run: pip install yt-dlp")
        return True

    speak(f"Searching YouTube for {query}.")

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # ytsearch1: means "search YouTube, return 1 result"
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)

            if info and "entries" in info and len(info["entries"]) > 0:
                video = info["entries"][0]
                video_url = video.get("url") or video.get("webpage_url") or ""
                if video_url and not video_url.startswith("http"):
                    video_url = f"https://www.youtube.com/watch?v={video_url}"
                video_title = video.get("title", "a video")

                if video_url:
                    speak(f"Playing {video_title}.")
                    open_url(video_url)
                else:
                    speak("I found a video but couldn't get the link.")
            else:
                speak(f"Sorry, I couldn't find any results for {query}.")

    except Exception as e:
        print(f"[YouTube error]: {e}")
        speak("Sorry, something went wrong searching YouTube.")

    return True


# =============================================================================
# VOLUME & MEDIA CONTROLS
# =============================================================================

def press_key(vk_code):
    """Simulate a key press and release using Windows API."""
    ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYDOWN, 0)
    ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)


def handle_media(command):
    """
    Handle volume and media playback commands.

    Supported commands:
      - "volume up"        - increases volume
      - "volume down"      - decreases volume
      - "mute" / "unmute"  - toggles mute
      - "pause" / "resume" - play/pause toggle
      - "next" / "next song" / "next track"
      - "previous" / "previous song" / "previous track"

    Returns True if this was a media command, False otherwise.
    """
    command = command.lower().strip()

    if "volume up" in command:
        # Press volume up 5 times for a noticeable change
        for _ in range(5):
            press_key(VK_VOLUME_UP)
        speak("Volume up.")
        return True

    elif "volume down" in command:
        for _ in range(5):
            press_key(VK_VOLUME_DOWN)
        speak("Volume down.")
        return True

    elif command in ["mute", "unmute", "mute volume", "unmute volume"]:
        press_key(VK_VOLUME_MUTE)
        speak("Toggled mute.")
        return True

    elif command in ["pause", "resume", "pause music", "resume music",
                     "play", "play music"]:
        press_key(VK_MEDIA_PLAY_PAUSE)
        speak("Done.")
        return True

    elif command in ["next", "next song", "next track", "skip"]:
        press_key(VK_MEDIA_NEXT)
        speak("Next track.")
        return True

    elif command in ["previous", "previous song", "previous track",
                     "go back"]:
        press_key(VK_MEDIA_PREV)
        speak("Previous track.")
        return True

    return False


# =============================================================================
# SCREENSHOT
# =============================================================================

def take_screenshot():
    """Take a screenshot and save it to the Pictures folder."""
    if ImageGrab is None:
        speak("Sorry, Pillow is not installed. I cannot take screenshots. "
              "Please run: pip install Pillow")
        return

    try:
        # Save to the user's Pictures folder
        pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures")
        os.makedirs(pictures_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = os.path.join(pictures_dir, filename)

        screenshot = ImageGrab.grab()
        screenshot.save(filepath)
        speak(f"Screenshot saved to your Pictures folder as {filename}.")

    except Exception as e:
        print(f"[Screenshot error]: {e}")
        speak("Sorry, I couldn't take the screenshot.")


# =============================================================================
# LOCK COMPUTER
# =============================================================================

def lock_computer():
    """Lock the Windows workstation."""
    speak("Locking the computer.")
    try:
        ctypes.windll.user32.LockWorkStation()
    except Exception as e:
        print(f"[Lock error]: {e}")
        speak("Sorry, I couldn't lock the computer.")


# =============================================================================
# GOOGLE SEARCH
# =============================================================================

def google_search(query):
    """Open a Google search in the default browser."""
    speak(f"Searching Google for {query}.")
    url = f"https://www.google.com/search?q={query}"
    webbrowser.open(url)


# =============================================================================
# TIME & DATE
# =============================================================================

def get_time():
    """Speak the current time."""
    now = datetime.now().strftime("%I:%M %p")
    speak(f"The time is {now}.")


def get_date():
    """Speak today's date."""
    today = datetime.now().strftime("%A, %B %d, %Y")
    speak(f"Today is {today}.")


# =============================================================================
# OPEN & CLOSE APPS
# =============================================================================

def open_app(name):
    """
    Try to open an app by name.
    Uses the APPS dictionary, fuzzy matching, shutil.which, and 'start' as fallbacks.
    """
    result = find_app(name)

    if result:
        command, matched_name = result
        speak(f"Opening {matched_name}.")
        try:
            subprocess.Popen(command, shell=True)
        except Exception as e:
            print(f"[Error opening {matched_name}]: {e}")
            speak(f"Sorry, I couldn't open {matched_name}.")
        return True

    # Last resort: try the Windows 'start' command
    try:
        speak(f"Trying to open {name}.")
        subprocess.Popen(f"start {name}", shell=True)
        return True
    except Exception:
        pass

    # Nothing worked - tell the user how to add it
    speak(f"Sorry, I don't know how to open {name}. "
          f"You can add it to the APPS dictionary in liku.py with its full path.")
    return False


def close_app(name):
    """
    Close an app by killing its process.
    Uses the PROCESS_NAMES dictionary with fuzzy matching.
    """
    name = name.lower().strip()

    # Exact match
    process = PROCESS_NAMES.get(name)

    # Fuzzy match
    if not process:
        matches = difflib.get_close_matches(
            name, list(PROCESS_NAMES.keys()), n=1, cutoff=APP_MATCH_THRESHOLD
        )
        if matches:
            name = matches[0]
            process = PROCESS_NAMES[name]

    if process:
        speak(f"Closing {name}.")
        try:
            subprocess.Popen(
                f"taskkill /f /im {process}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"[Error closing {name}]: {e}")
            speak(f"Sorry, I couldn't close {name}.")
    else:
        speak(f"Sorry, I don't know the process name for {name}. "
              f"You can add it to the PROCESS_NAMES dictionary in liku.py.")


# =============================================================================
# LANGUAGE DETECTION
# =============================================================================

def detect_language_command(command):
    """
    Detect if the user is asking Liku to switch language.
    Returns the new language string ('english', 'hindi', 'odia') or None.

    Supported phrases:
      English: 'speak english', 'switch to english', 'use english', 'english mode'
      Hindi:   'speak hindi', 'speak in hindi', 'switch to hindi', 'hindi mein bolo'
      Odia:    'speak odia', 'speak in odia', 'switch to odia', 'odia re bola'
    """
    cmd = command.lower().strip()

    hindi_triggers = [
        "speak hindi", "speak in hindi", "switch to hindi", "use hindi",
        "hindi mein", "hindi me bolo", "hindi mode", "change to hindi",
        "talk in hindi", "respond in hindi", "answer in hindi",
    ]
    odia_triggers = [
        "speak odia", "speak in odia", "switch to odia", "use odia",
        "odia re", "odia te bola", "odia mode", "change to odia",
        "talk in odia", "respond in odia", "answer in odia",
    ]
    english_triggers = [
        "speak english", "speak in english", "switch to english", "use english",
        "english mode", "change to english", "talk in english",
        "respond in english", "answer in english",
    ]

    for t in hindi_triggers:
        if t in cmd:
            return "hindi"
    for t in odia_triggers:
        if t in cmd:
            return "odia"
    for t in english_triggers:
        if t in cmd:
            return "english"

    return None


# =============================================================================
# CODE WRITING (Ollama generates code, saved to Desktop, opened in VS Code)
# =============================================================================

def is_code_request(command):
    """
    Returns True if the command is a request to write/generate code.
    Examples:
      - 'open note pad and write a python program to find out prime no from a given string'
      - 'write any program in notepad'
      - 'write a program to calculate factorial'
      - 'create a python script to download files'
    """
    cmd = command.lower().strip()
    cmd = re.sub(r"\bnote\s+pad\b", "notepad", cmd)

    patterns = [
        r"\b(?:write|create|make|generate|type)\b.*?\b(?:program|code|script|python)\b",
        r"\b(?:program|code|script)\b.*?\b(?:in\s+notepad|on\s+notepad)\b",
        r"\bopen\s+notepad\s+and\s+(?:write|type|create|make|code)\b",
        r"\bcode\s+for\b",
        r"\bpython\s+code\b",
    ]
    if any(re.search(p, cmd) for p in patterns):
        return True

    triggers = [
        "write a program", "write program", "write any program", "write code", "write a code",
        "create a program", "create program", "create a script", "create script",
        "make a program", "make program", "make a script",
        "code for", "python code", "write python", "generate code",
        "write a python", "write script", "write a script",
    ]
    return any(t in cmd for t in triggers)


def extract_clean_code(text):
    """
    Extract pure Python code from model output, handling markdown code fences
    or returning raw code lines cleanly.
    """
    if not text:
        return ""
    # Try finding fenced block ```python ... ``` or ``` ... ```
    match = re.search(r"```(?:python)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match and match.group(1).strip():
        return match.group(1).strip()

    # If no fences, remove conversational preamble before code
    lines = text.strip().splitlines()
    code_lines = []
    started = False
    for line in lines:
        stripped = line.strip()
        if not started:
            if stripped.startswith(("import ", "from ", "def ", "class ", "#", "print(", "if __name__")):
                started = True
                code_lines.append(line)
        else:
            code_lines.append(line)

    if code_lines:
        return "\n".join(code_lines).strip()
    return text.strip()


def write_code(command):
    """
    Ask Ollama to generate code based on the user's description.
    Saves the code to Desktop and opens it in Notepad (or VS Code if requested).
    """
    global chat_history

    if ollama is None:
        speak("The ollama package is not installed. Please run pip install ollama.")
        return

    cmd_lower = command.lower().strip()
    cmd_lower = re.sub(r"\bnote\s+pad\b", "notepad", cmd_lower)

    # Determine editor: Default to Notepad, unless VS Code explicitly asked
    use_vscode = ("vs code" in cmd_lower or "vscode" in cmd_lower) and ("notepad" not in cmd_lower)
    editor_name = "VS Code" if use_vscode else "Notepad"

    # Clean the task description for the Ollama prompt
    clean_task = re.sub(r"\b(?:open\s+(?:the\s+)?(?:notepad|vs\s*code)\s+and\s+)", "", cmd_lower, flags=re.I)
    clean_task = re.sub(r"\b(?:in|on|using|with)\s+(?:notepad|vs\s*code)\b", "", clean_task, flags=re.I).strip()
    clean_task = re.sub(r"^(?:please\s+|can\s+you\s+|liku\s+)", "", clean_task, flags=re.I).strip()

    if not clean_task or clean_task in {"write any program", "write a program", "write program", "write code"}:
        clean_task = "a Python program with a complete working example, such as finding prime numbers or a guessing game"

    speak(f"Sure! Writing your Python program in {editor_name}.")
    print(f"[Code Request]: {clean_task} (Target: {editor_name})")

    try:
        model_to_use = OLLAMA_MODEL
        try:
            installed_models = [m.model for m in ollama.list().models]
            if not any(model_to_use in m for m in installed_models) and installed_models:
                model_to_use = installed_models[0]
        except Exception:
            pass

        code_prompt = (
            f"You are an expert Python programmer. Write complete, well-formatted, working Python code for: {clean_task}.\n"
            "Requirements:\n"
            "- Include clear comments explaining how it works.\n"
            "- Include an example input and print statements displaying the output.\n"
            "- Output ONLY valid Python code inside a ```python ``` block.\n"
            "- Do not write conversational text outside the code block."
        )

        response = ollama.chat(
            model=model_to_use,
            messages=[{"role": "user", "content": code_prompt}],
        )

        raw_output = response["message"]["content"].strip()
        code_text = extract_clean_code(raw_output)

        if not code_text:
            code_text = raw_output

        # Generate a descriptive filename
        words = re.findall(r"[a-zA-Z]+", clean_task)
        stopwords = {"write", "a", "an", "the", "program", "python", "code", "script", "to", "for", "and", "in", "any", "of", "from", "given", "out", "find", "me"}
        keywords = [w.lower() for w in words if w.lower() not in stopwords]
        slug = "_".join(keywords[:3]) if keywords else "program"

        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        os.makedirs(desktop, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"liku_{slug}_{timestamp}.py"
        filepath = os.path.join(desktop, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code_text)

        print(f"[Code saved]: {filepath}")

        # Open in requested editor (Notepad is default!)
        if use_vscode:
            try:
                subprocess.Popen(f'code "{filepath}"', shell=True)
                speak(f"Done! I've written the program and opened it in VS Code for you.")
            except Exception:
                subprocess.Popen(["notepad.exe", filepath])
                speak(f"Done! I've written the program and opened it in Notepad for you.")
        else:
            subprocess.Popen(["notepad.exe", filepath])
            speak(f"Done! I've written the program and opened it in Notepad for you.")

    except Exception as e:
        error_msg = str(e).lower()
        print(f"[Code writing error]: {e}")
        if "connection" in error_msg or "refused" in error_msg:
            speak("I can't reach Ollama. Please make sure Ollama is running.")
        else:
            speak("Sorry, I couldn't write the code. Make sure Ollama is running.")


# =============================================================================
# AI CHAT (Ollama with llama3.2:1b)
# =============================================================================

def chat_with_ai(user_message):
    """
    Send a message to the local Ollama AI and get a spoken response.

    Uses the llama3.2:1b model running locally via Ollama.
    Keeps the last 12 messages as conversation memory.
    If Ollama is not installed or not running, gives a friendly error.
    """
    global chat_history

    # Check if the ollama package is available
    if ollama is None:
        speak("The ollama package is not installed. "
              "Please run: pip install ollama")
        return

    # Add the user's message to history
    chat_history.append({"role": "user", "content": user_message})

    # Keep only the last 12 messages to save memory
    if len(chat_history) > 12:
        chat_history = chat_history[-12:]

    # Build the full message list with the system prompt
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_history

    try:
        model_to_use = OLLAMA_MODEL
        try:
            installed_models = [m.model for m in ollama.list().models]
            if not any(model_to_use in m for m in installed_models) and installed_models:
                model_to_use = installed_models[0]
        except Exception:
            pass

        response = ollama.chat(
            model=model_to_use,
            messages=messages,
        )

        # Extract the reply text
        reply = response["message"]["content"].strip()

        # Add the assistant's reply to history
        chat_history.append({"role": "assistant", "content": reply})

        # Speak the reply
        speak(reply)

    except Exception as e:
        error_msg = str(e).lower()

        if "connection" in error_msg or "refused" in error_msg:
            speak("I can't reach the Ollama server. "
                  "Please make sure Ollama is running. "
                  "You can start it by opening the Ollama app or running ollama serve in a terminal.")
        elif "model" in error_msg and "not found" in error_msg:
            speak(f"The model {OLLAMA_MODEL} is not downloaded yet. "
                  f"Please run: ollama pull {OLLAMA_MODEL}")
        else:
            print(f"[AI chat error]: {e}")
            speak("Sorry, something went wrong with the AI. "
                  "Make sure Ollama is running and the model is downloaded.")


def chat_with_ai_multilang(user_message):
    """
    Like chat_with_ai but instructs the AI to reply in the current language.
    Uses a language-aware system prompt so the AI responds in Hindi/Odia/English.
    """
    global chat_history

    if ollama is None:
        speak("The ollama package is not installed. Please run pip install ollama.")
        return

    # Build language-aware system prompt
    if current_language == "hindi":
        lang_instruction = (
            "You are Liku, a friendly voice assistant. "
            "Always reply in simple, spoken Hindi (Devanagari script or Roman transliteration is fine). "
            "Keep replies to one to three short sentences, plain text only, no markdown."
        )
    elif current_language == "odia":
        lang_instruction = (
            "You are Liku, a friendly voice assistant. "
            "Always reply in simple, spoken Odia (Roman transliteration is fine if Odia script is unavailable). "
            "Keep replies to one to three short sentences, plain text only, no markdown."
        )
    else:
        lang_instruction = SYSTEM_PROMPT

    chat_history.append({"role": "user", "content": user_message})
    if len(chat_history) > 12:
        chat_history = chat_history[-12:]

    messages = [{"role": "system", "content": lang_instruction}] + chat_history

    try:
        model_to_use = OLLAMA_MODEL
        try:
            installed_models = [m.model for m in ollama.list().models]
            if not any(model_to_use in m for m in installed_models) and installed_models:
                model_to_use = installed_models[0]
        except Exception:
            pass

        response = ollama.chat(model=model_to_use, messages=messages)
        reply = response["message"]["content"].strip()
        chat_history.append({"role": "assistant", "content": reply})
        speak(reply)

    except Exception as e:
        error_msg = str(e).lower()
        if "connection" in error_msg or "refused" in error_msg:
            speak("I can't reach the Ollama server. Please make sure Ollama is running.")
        elif "model" in error_msg and "not found" in error_msg:
            speak(f"The model {OLLAMA_MODEL} is not downloaded yet. Please run ollama pull {OLLAMA_MODEL}")
        else:
            print(f"[AI chat error]: {e}")
            speak("Sorry, something went wrong with the AI.")


# =============================================================================
# COMMAND ROUTER - The brain that decides what to do
# =============================================================================

def process_command(command):
    """
    Process a voice command in priority order.

    Normalizes speech quirks first ('you tube' -> 'youtube', strips 'please', etc.)
    Then routes in priority order.
    """
    # Normalize speech recognition text
    command = normalize_command(command)

    if not command:
        return True  # Empty command, keep running

    print(f"[Processing]: '{command}'")

    # ----- 1. QUIT -----
    quit_words = ["stop", "exit", "goodbye", "good bye", "bye", "quit",
                  "shut down assistant", "turn off"]
    if command in quit_words:
        speak(phrase("goodbye"))
        return False  # Signal to stop the main loop

    # ----- 2. LANGUAGE SWITCH -----
    new_lang = detect_language_command(command)
    if new_lang is not None:
        global current_language
        current_language = new_lang
        speak(LANG_PHRASES[new_lang]["switched"])
        return True

    # ----- 3. CODE WRITING -----
    if is_code_request(command):
        write_code(command)
        return True

    # ----- 4. YOUTUBE -----
    if handle_youtube(command):
        return True

    # ----- 5. VOLUME & MEDIA -----
    if handle_media(command):
        return True

    # ----- 6. SCREENSHOT -----
    if "screenshot" in command or "screen shot" in command:
        take_screenshot()
        return True

    # ----- 7. LOCK COMPUTER -----
    if "lock" in command and ("computer" in command or "pc" in command
                              or "screen" in command or "system" in command):
        lock_computer()
        return True

    # ----- 8. GOOGLE SEARCH -----
    match = re.match(r"(?:search\s+google\s+for|google\s+search\s+for|"
                     r"search\s+for|google)\s+(.+)", command)
    if match:
        google_search(match.group(1).strip())
        return True

    # ----- 9. DIRECT WEBSITE OR APP NAME (e.g. "youtube", "chrome", "vs code", "notepad") -----
    site = find_website(command)
    if site and command in WEBSITES:
        url, matched_name = site
        speak(f"Opening {matched_name}.")
        open_url(url)
        return True

    app = find_app(command)
    if app and command in APPS:
        cmd, matched_name = app
        open_app(matched_name)
        return True

    # ----- 10. OPEN WEBSITE (WITH 'OPEN', 'GO TO', 'LAUNCH') -----
    open_match = re.match(r"(?:open|go\s+to|visit|turn\s+on|launch|start|run)\s+(?:the\s+)?(.+)", command)
    if open_match:
        target = open_match.group(1).strip()
        website = find_website(target)
        if website:
            url, matched_name = website
            speak(f"Opening {matched_name}.")
            open_url(url)
            return True

    # ----- 11. CLOSE APP -----
    close_match = re.match(r"(?:close|kill|shut\s+down|exit)\s+(.+)", command)
    if close_match:
        close_app(close_match.group(1).strip())
        return True

    # ----- 12. OPEN APP (WITH 'OPEN', 'LAUNCH') -----
    if open_match:
        # We already checked websites above, so this is an app
        open_app(open_match.group(1).strip())
        return True

    # ----- 13. TIME & DATE -----
    if "time" in command and ("what" in command or "current" in command
                              or "tell" in command):
        get_time()
        return True

    if "date" in command and ("what" in command or "today" in command
                              or "tell" in command):
        get_date()
        return True

    # ----- 14. AI CHAT (fallback) — language-aware -----
    # If nothing else matched, send it to the AI (responds in the current language)
    chat_with_ai_multilang(command)
    return True


def clear_audio_queue(audio_q, recog=None):
    """Discard all queued audio packets and reset Kaldi recognizer state."""
    while not audio_q.empty():
        try:
            audio_q.get_nowait()
        except queue.Empty:
            break
    if recog is not None:
        try:
            recog.Reset()
        except Exception:
            pass


# =============================================================================
# MAIN LOOP - Listens to the microphone and processes commands
# =============================================================================

def record_until_silence(samplerate=SAMPLE_RATE, silence_thresh=350,
                         silence_duration=0.8, max_duration=15,
                         listen_timeout=3.5, min_speech_duration=0.2,
                         cancel_queue=None):
    """
    Record audio from the microphone using sounddevice until silence is detected.
    Uses Voice Activity Detection (VAD) with pre-roll buffering so speech
    is captured cleanly without cutting off the beginning of words.
    If cancel_queue has pending items (e.g. text command), recording cancels immediately.

    Args:
        samplerate: Audio sample rate (Hz)
        silence_thresh: RMS amplitude below which audio is considered silence
        silence_duration: Seconds of silence after speech before stopping recording
        max_duration: Maximum total recording duration in seconds
        listen_timeout: Seconds to wait for speech to begin before returning None
        min_speech_duration: Minimum seconds of speech to count as valid input
        cancel_queue: Optional queue; if not empty, recording cancels immediately

    Returns:
        bytes: Raw PCM audio data (16-bit mono), or None if no speech detected
    """
    import numpy as np
    from collections import deque

    pre_buffer = deque(maxlen=4)  # ~250ms of audio before speech starts
    speech_chunks = []
    speech_started = False
    silence_counter = 0
    speech_counter = 0
    chunk_duration = BLOCK_SIZE / samplerate

    def callback(indata, frames, time_info, status):
        nonlocal speech_started, silence_counter, speech_counter
        raw = bytes(indata)
        audio_array = np.frombuffer(raw, dtype=np.int16)
        rms = np.sqrt(np.mean(audio_array.astype(np.float64) ** 2)) if len(audio_array) > 0 else 0

        if not speech_started:
            if rms > silence_thresh:
                speech_started = True
                speech_chunks.extend(list(pre_buffer))
                speech_chunks.append(raw)
                speech_counter = 1
                silence_counter = 0
            else:
                pre_buffer.append(raw)
        else:
            speech_chunks.append(raw)
            if rms < silence_thresh:
                silence_counter += 1
            else:
                silence_counter = 0
                speech_counter += 1

    stream = sd.RawInputStream(
        samplerate=samplerate,
        blocksize=BLOCK_SIZE,
        dtype="int16",
        channels=CHANNELS,
        callback=callback,
    )

    silence_blocks_needed = int(silence_duration / chunk_duration)
    max_blocks = int(max_duration / chunk_duration)
    listen_timeout_blocks = int(listen_timeout / chunk_duration)
    min_speech_blocks = int(min_speech_duration / chunk_duration)

    with stream:
        block_count = 0
        while block_count < max_blocks:
            # If a text command arrived, cancel listening immediately
            if cancel_queue is not None and not cancel_queue.empty():
                return None

            time.sleep(chunk_duration)
            block_count += 1

            # If no speech started within listen_timeout, exit early to cycle
            if not speech_started and block_count >= listen_timeout_blocks:
                break

            # Stop when we have enough silence after speech
            if speech_started and silence_counter >= silence_blocks_needed:
                break

    if not speech_started or speech_counter < min_speech_blocks:
        return None  # No speech detected

    return b"".join(speech_chunks)


def recognize_speech_google(audio_bytes, language="en-IN"):
    """
    Send recorded audio to Google's free Speech Recognition API.

    Args:
        audio_bytes: Raw PCM audio data (16-bit mono, 16kHz)
        language: Language code for recognition (e.g. 'en-IN', 'hi-IN', 'or-IN')

    Returns:
        Recognized text string, or None if recognition failed
    """
    if sr is None:
        return None

    # Create an AudioData object from raw PCM bytes
    audio_data = sr.AudioData(audio_bytes, sample_rate=SAMPLE_RATE, sample_width=2)

    recognizer = sr.Recognizer()
    try:
        text = recognizer.recognize_google(audio_data, language=language)
        return text.strip() if text else None
    except sr.UnknownValueError:
        return None  # Google couldn't understand
    except sr.RequestError as e:
        print(f"[Google Speech error]: {e} — check internet connection")
        return None


def check_file_commands(cmd_queue):
    """
    Check if a 'commands.txt' file exists in the Liku folder.
    If commands are found, enqueues them as text commands and clears the file.
    This allows users or external scripts to feed text commands to Liku.
    """
    cmd_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commands.txt")
    if os.path.exists(cmd_file):
        try:
            with open(cmd_file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            if lines:
                open(cmd_file, "w", encoding="utf-8").close()
                for line in lines:
                    cmd_queue.put(("text", line))
        except Exception:
            pass


def main():
    """
    Main function: sets up speech recognition and listens continuously
    for the wake word "Hey Liku" or direct commands.

    Uses Google's free Speech Recognition (same as Google Search voice input)
    for high accuracy. Falls back to Vosk offline if no internet.
    Microphone input uses sounddevice (no PyAudio needed).
    """
    global is_speaking

    # --- Check required libraries ---
    if pyttsx3 is None:
        print("ERROR: 'pyttsx3' is not installed. Run: pip install pyttsx3")
        sys.exit(1)
    if sd is None:
        print("ERROR: 'sounddevice' is not installed. Run: pip install sounddevice")
        sys.exit(1)

    # =========================================================================
    # SET UP SPEECH RECOGNITION
    # =========================================================================

    use_google = sr is not None
    if use_google:
        print("[OK] Using Google Speech Recognition (free, high accuracy)")
        print("     Supports: English, Hindi, Odia")
    else:
        print("[i] SpeechRecognition not installed. Run: pip install SpeechRecognition")
        print("    Using Vosk offline recognition.")

    # --- Set up Vosk as offline fallback ---
    vosk_recognizer = None
    vosk_model_loaded = False

    if not use_google:
        if Model is None:
            print("ERROR: 'vosk' is not installed. Run: pip install vosk")
            sys.exit(1)

        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")

        if not os.path.exists(model_path):
            print("=" * 60)
            print("ERROR: Vosk model not found!")
            print()
            print("Please download the model:")
            print("  1. Go to: https://alphacephei.com/vosk/models")
            print("  2. Download: vosk-model-small-en-in-0.4")
            print("  3. Extract the ZIP file")
            print("  4. Rename the folder to 'model'")
            print(f"  5. Place it here: {model_path}")
            print("=" * 60)
            sys.exit(1)

        print("Loading Vosk speech model... (this may take a moment)")
        try:
            vosk_model_obj = Model(model_path)
            vosk_recognizer = KaldiRecognizer(vosk_model_obj, SAMPLE_RATE)
            vosk_model_loaded = True
        except Exception as e:
            print(f"ERROR: Could not load Vosk model: {e}")
            sys.exit(1)

        print("Vosk model loaded successfully!")

    # --- Test microphone ---
    print("Testing microphone...")
    try:
        test_stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            dtype="int16",
            channels=CHANNELS,
        )
        test_stream.close()
        print("[OK] Microphone is working!")
    except Exception as e:
        print(f"ERROR: Could not open microphone: {e}")
        print("Make sure a microphone is connected and not in use by another app.")
        sys.exit(1)

    # =========================================================================
    # DUAL INPUT SETUP (Voice + Text)
    # =========================================================================
    command_queue = queue.Queue()
    running = [True]

    # 1. CLI Argument Support: e.g. python liku.py "open notepad and write code..."
    if len(sys.argv) > 1:
        initial_cmd = " ".join(sys.argv[1:]).strip()
        if initial_cmd:
            command_queue.put(("text", initial_cmd))

    # 2. Background Thread for Live Console Text Input:
    # Users can type commands in the terminal at any time and press Enter!
    def text_input_worker():
        while running[0]:
            try:
                line = sys.stdin.readline()
                if not line:
                    time.sleep(0.2)
                    continue
                line = line.strip()
                if line:
                    command_queue.put(("text", line))
            except (EOFError, KeyboardInterrupt):
                break
            except Exception:
                time.sleep(0.5)

    text_thread = threading.Thread(target=text_input_worker, daemon=True)
    text_thread.start()

    def handle_text_command(cmd_text):
        """Execute a text command. Strips wake word if present, otherwise runs directly."""
        print(f"\n[Text Command]: '{cmd_text}'")
        wake_detected, remaining = check_wake_word(cmd_text)
        actual_cmd = remaining if wake_detected and remaining else cmd_text
        return process_command(actual_cmd)

    # =========================================================================
    # BANNER
    # =========================================================================
    print()
    print("=" * 60)
    print("  LIKU ASSISTANT (Voice + Text)")
    if use_google:
        print("  [Voice Mode] Google Speech Recognition enabled (en-IN, hi-IN, or-IN)")
    else:
        print("  [Voice Mode] Vosk offline recognition active.")
    print("  [Text Mode]  Type any command in this window & press Enter!")
    print("  [File Mode]  Or write commands into 'commands.txt'")
    print("  Say 'Hey Liku' or type 'exit' to quit.")
    print("=" * 60)
    print()

    speak(phrase("hello"))

    # =========================================================================
    # GOOGLE SPEECH RECOGNITION LOOP (primary — accurate like Google Search)
    # Uses sounddevice for audio capture + simultaneous text input support
    # =========================================================================
    if use_google:
        while running[0]:
            try:
                # Check for file-based text commands in commands.txt
                check_file_commands(command_queue)

                # Process any pending text commands immediately
                while not command_queue.empty():
                    source, text_cmd = command_queue.get_nowait()
                    if source == "text":
                        running[0] = handle_text_command(text_cmd)
                        if not running[0]:
                            break
                if not running[0]:
                    break

                # Don't listen while Liku is speaking
                if is_speaking:
                    time.sleep(0.1)
                    continue

                # Record audio until silence (cancels immediately if text is typed)
                audio_bytes = record_until_silence(cancel_queue=command_queue)

                # If text command arrived during audio recording, loop back immediately
                if not command_queue.empty():
                    continue

                if audio_bytes is None:
                    continue  # No speech detected, keep listening

                # Recognize with Google (free — no API key needed)
                lang_code = GOOGLE_LANG_CODES.get(current_language, "en-IN")
                text = recognize_speech_google(audio_bytes, language=lang_code)

                if not text:
                    continue

                print(f"[Heard]: '{text}'")

                # Check for wake word
                wake_detected, remaining_command = check_wake_word(text)

                if wake_detected:
                    if remaining_command:
                        running[0] = process_command(remaining_command)
                    else:
                        speak(phrase("yes"))

                        print("[Waiting for command...]")
                        follow_audio = record_until_silence(max_duration=FOLLOW_UP_TIMEOUT, cancel_queue=command_queue)
                        if not command_queue.empty():
                            continue

                        if follow_audio:
                            follow_text = recognize_speech_google(follow_audio, language=lang_code)
                            if follow_text:
                                print(f"[Heard]: '{follow_text}'")
                                running[0] = process_command(follow_text)
                            else:
                                speak(phrase("no_command"))
                        else:
                            speak(phrase("no_command"))

                elif ALLOW_DIRECT_COMMANDS and is_direct_command(text):
                    print(f"[Direct command]: '{text}'")
                    running[0] = process_command(text)

                elif ALLOW_AI_WITHOUT_WAKE_WORD and len(text.split()) >= 2:
                    print(f"[Direct AI Query]: '{text}'")
                    running[0] = process_command(text)

                else:
                    print(f"[Ignored - command must start with 'Hey Liku' or 'Liku']: '{text}'")

            except KeyboardInterrupt:
                print("\nInterrupted by user.")
                speak("Goodbye!")
                running[0] = False
            except Exception as e:
                print(f"[Error in main loop]: {e}")
                continue

    # =========================================================================
    # VOSK OFFLINE FALLBACK LOOP (when Google is unavailable)
    # =========================================================================
    elif vosk_model_loaded:
        audio_queue_vosk = queue.Queue()

        def audio_callback(indata, frames, time_info, status):
            """Called by sounddevice for each audio block."""
            if status:
                print(f"[Audio warning]: {status}")
            if not is_speaking:
                audio_queue_vosk.put(bytes(indata))

        vosk_stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            dtype="int16",
            channels=CHANNELS,
            callback=audio_callback,
        )

        with vosk_stream:
            while running[0]:
                try:
                    # Check for file-based text commands
                    check_file_commands(command_queue)

                    # Process any pending text commands
                    while not command_queue.empty():
                        source, text_cmd = command_queue.get_nowait()
                        if source == "text":
                            running[0] = handle_text_command(text_cmd)
                            if not running[0]:
                                break
                    if not running[0]:
                        break

                    try:
                        data = audio_queue_vosk.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    if vosk_recognizer.AcceptWaveform(data):
                        result = json.loads(vosk_recognizer.Result())
                        text = result.get("text", "").strip()

                        if not text:
                            continue

                        print(f"[Heard]: '{text}'")

                        wake_detected, remaining_command = check_wake_word(text)

                        if wake_detected:
                            if remaining_command:
                                running[0] = process_command(remaining_command)
                                clear_audio_queue(audio_queue_vosk, vosk_recognizer)
                            else:
                                speak(phrase("yes"))
                                clear_audio_queue(audio_queue_vosk, vosk_recognizer)

                                print("[Waiting for command...]")
                                start_time = time.time()
                                got_command = False
                                partial_text = ""

                                while time.time() - start_time < FOLLOW_UP_TIMEOUT:
                                    try:
                                        audio_data = audio_queue_vosk.get(timeout=0.2)
                                    except queue.Empty:
                                        continue

                                    if vosk_recognizer.AcceptWaveform(audio_data):
                                        res = json.loads(vosk_recognizer.Result())
                                        follow_up = res.get("text", "").strip()
                                        if follow_up:
                                            print(f"[Heard]: '{follow_up}'")
                                            running[0] = process_command(follow_up)
                                            got_command = True
                                            break
                                    else:
                                        part = json.loads(vosk_recognizer.PartialResult()).get("partial", "").strip()
                                        if part:
                                            partial_text = part

                                if not got_command:
                                    final_res = json.loads(vosk_recognizer.FinalResult()).get("text", "").strip()
                                    fallback_cmd = final_res or partial_text
                                    if fallback_cmd:
                                        print(f"[Heard (fallback)]: '{fallback_cmd}'")
                                        running[0] = process_command(fallback_cmd)
                                    else:
                                        speak(phrase("no_command"))

                                clear_audio_queue(audio_queue_vosk, vosk_recognizer)

                        elif ALLOW_DIRECT_COMMANDS and is_direct_command(text):
                            print(f"[Direct command]: '{text}'")
                            running[0] = process_command(text)
                            clear_audio_queue(audio_queue_vosk, vosk_recognizer)

                        elif ALLOW_AI_WITHOUT_WAKE_WORD and len(text.split()) >= 2:
                            print(f"[Direct AI Query]: '{text}'")
                            running[0] = process_command(text)
                            clear_audio_queue(audio_queue_vosk, vosk_recognizer)

                        else:
                            print(f"[Ignored - command must start with 'Hey Liku' or 'Liku']: '{text}'")
                            clear_audio_queue(audio_queue_vosk, vosk_recognizer)

                except KeyboardInterrupt:
                    print("\nInterrupted by user.")
                    speak("Goodbye!")
                    running[0] = False
                except Exception as e:
                    print(f"[Error in main loop]: {e}")
                    continue

    print("Liku has stopped. See you next time!")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    main()

