"""
Liku - A free, offline voice assistant for Windows.

This is the main file. It listens for the wake word "Hey Liku",
then processes your voice command: opening apps, playing YouTube,
controlling volume, chatting with a local AI, and more.

Everything runs locally on your PC. No paid APIs or subscriptions needed.
Only YouTube search uses the internet.

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


# =============================================================================
# CONFIGURATION
# =============================================================================

# Voice settings:
# Choose your favorite realistic neural voice:
#   "en-US-AnaNeural"             <- Sweet, cute youthful girl voice (Default)
#   "en-US-AvaNeural"             <- Cheerful, energetic 23-year-old female voice
#   "en-US-JennyNeural"           <- Friendly, natural young female assistant
#   "en-IN-NeerjaExpressiveNeural" <- Expressive young Indian-English female voice
NEURAL_VOICE = "en-US-AnaNeural"
VOICE_PITCH = "+0Hz"    # e.g. "+5Hz" or "+10Hz" for extra cute pitch
VOICE_SPEED = "+0%"     # Speech rate (e.g. "+0%", "+5%", "-5%")
USE_NEURAL_VOICE = True # Uses high-definition cute voice with automatic offline fallback

# Offline voice settings (pyttsx3 fallback)
OFFLINE_VOICE_RATE = 185
OFFLINE_VOICE_VOLUME = 1.0

# How similar a word must be to count as a match (0.0 to 1.0)
WAKE_WORD_THRESHOLD = 0.65   # For wake word fuzzy matching
APP_MATCH_THRESHOLD = 0.6    # For app name fuzzy matching

# How long to wait for a follow-up command after just saying "Hey Liku"
FOLLOW_UP_TIMEOUT = 8  # seconds

# Ollama model name - defaults to installed model (e.g. phi3:mini or llama3.2:1b)
OLLAMA_MODEL = "phi3:mini"

# Vosk audio settings
SAMPLE_RATE = 16000   # 16 kHz as required by Vosk
CHANNELS = 1          # Mono audio
BLOCK_SIZE = 8000     # Audio block size (0.5 seconds of audio)


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

# System prompt that tells the AI how to behave
SYSTEM_PROMPT = (
    "You are Liku, a friendly voice assistant. "
    "Reply in one to three short sentences, plain text only, no lists or markdown."
)


# =============================================================================
# VOICE OUTPUT - Text to Speech
# =============================================================================

def speak_neural(text):
    """Speak using Edge-TTS high-definition cute neural voice."""
    async def _generate():
        communicate = edge_tts.Communicate(
            text,
            NEURAL_VOICE,
            pitch=VOICE_PITCH,
            rate=VOICE_SPEED,
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
        pygame.mixer.init()

    sound_file = io.BytesIO(audio_data)
    pygame.mixer.music.load(sound_file)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(20)


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
    Uses ultra-realistic cute neural voice (young female early 20s)
    and falls back seamlessly to offline Windows voice if needed.
    """
    global is_speaking

    if not text or not text.strip():
        return

    print(f"[Liku]: {text}")

    try:
        is_speaking = True

        # 1. Try cute neural voice first (Edge-TTS)
        if USE_NEURAL_VOICE and edge_tts is not None and pygame is not None:
            try:
                speak_neural(text)
                return
            except Exception as e:
                # Network unavailable or edge-tts glitch: fall back cleanly
                pass

        # 2. Offline fallback (pyttsx3 with female voice)
        speak_offline(text)

    except Exception as e:
        print(f"[Speech error]: {e}")
    finally:
        is_speaking = False


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
    Check if the text contains the wake word (with fuzzy matching and greetings).
    Supports wake word at the beginning, at the end, or alone.

    Accepts:
      'hey liku', 'hi liku', 'hello liku', 'ok liku', 'liku' (as first/last word),
      and variants like 'leeku', 'liko', 'like you'.
    """
    text = text.lower().strip()
    if not text:
        return (False, "")

    # Normalize speech recognition text first
    text = re.sub(r"\b(you\s+tube|u\s+tube)\b", "youtube", text)
    text = re.sub(r"\b(v\s+s\s+code|visual\s+studio\s+code)\b", "vs code", text)

    words = text.split()
    if not words:
        return (False, "")

    liku_variants = ["liku", "leeku", "liko", "leku", "liqu", "leko", "lyku", "licoo"]
    greetings = ["hey", "hi", "hai", "hello", "ok", "okay", "yo", "ay", "ae"]

    def is_liku(w):
        return any(difflib.SequenceMatcher(None, w, v).ratio() >= WAKE_WORD_THRESHOLD for v in liku_variants)

    def is_greeting(w):
        return any(difflib.SequenceMatcher(None, w, g).ratio() >= 0.65 for g in greetings)

    # Check for two-word "like you" (sounds like "liku")
    for i in range(len(words) - 1):
        if difflib.SequenceMatcher(None, words[i] + " " + words[i + 1], "like you").ratio() >= 0.75:
            if i > 0 and is_greeting(words[i - 1]):
                cmd = " ".join(words[:i - 1] + words[i + 2:]).strip()
                return (True, cmd)
            cmd = " ".join(words[:i] + words[i + 2:]).strip()
            return (True, cmd)

    # Case 1: Greeting + Liku anywhere in text
    for i in range(len(words) - 1):
        if is_greeting(words[i]) and is_liku(words[i + 1]):
            cmd = " ".join(words[:i] + words[i + 2:]).strip()
            return (True, cmd)

    # Case 2: Standalone Liku at the very start (e.g. "liku open youtube")
    if is_liku(words[0]):
        cmd = " ".join(words[1:]).strip()
        return (True, cmd)

    # Case 3: Standalone Liku at the very end (e.g. "open youtube liku")
    if is_liku(words[-1]):
        cmd = " ".join(words[:-1]).strip()
        return (True, cmd)

    # Case 4: Wake word alone
    if len(words) == 1 and is_liku(words[0]):
        return (True, "")

    return (False, "")


def is_direct_command(command):
    """
    Check if a spoken phrase is a clear, actionable command.
    Allows users to say e.g. 'open youtube' or 'volume up' without
    needing to repeat the wake word if they forgot it.
    """
    cmd = command.lower().strip()
    cmd = normalize_command(cmd)

    # 1. YouTube commands
    if extract_youtube_query(cmd) is not None:
        return True

    # 2. Opening apps or websites
    if re.match(r"^(?:open|turn\s+on|launch|start|run|go\s+to|visit)\s+", cmd):
        return True

    # 3. Google search
    if re.match(r"^(?:search\s+google|google\s+search|search\s+for|google)\s+", cmd):
        return True

    # 4. Closing apps
    if re.match(r"^(?:close|kill|shut\s+down)\s+", cmd):
        return True

    # 5. Media & volume
    if any(cmd.startswith(v) for v in ["volume up", "volume down", "mute", "unmute"]):
        return True
    if cmd in ["pause", "resume", "play", "stop", "exit", "quit", "goodbye", "next", "previous"]:
        return True

    # 6. Utilities
    if "screenshot" in cmd or "screen shot" in cmd:
        return True
    if "lock" in cmd and ("computer" in cmd or "pc" in cmd or "screen" in cmd):
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
        speak("Goodbye! Have a great day!")
        return False  # Signal to stop the main loop

    # ----- 2. YOUTUBE -----
    if handle_youtube(command):
        return True

    # ----- 3. VOLUME & MEDIA -----
    if handle_media(command):
        return True

    # ----- 4. SCREENSHOT -----
    if "screenshot" in command or "screen shot" in command:
        take_screenshot()
        return True

    # ----- 5. LOCK COMPUTER -----
    if "lock" in command and ("computer" in command or "pc" in command
                              or "screen" in command or "system" in command):
        lock_computer()
        return True

    # ----- 6. GOOGLE SEARCH -----
    match = re.match(r"(?:search\s+google\s+for|google\s+search\s+for|"
                     r"search\s+for|google)\s+(.+)", command)
    if match:
        google_search(match.group(1).strip())
        return True

    # ----- 7. OPEN WEBSITE -----
    # Check this BEFORE apps so "open google" opens the website
    open_match = re.match(r"(?:open|go\s+to|visit|turn\s+on|launch)\s+(?:the\s+)?(.+)", command)
    if open_match:
        target = open_match.group(1).strip()
        website = find_website(target)
        if website:
            url, matched_name = website
            speak(f"Opening {matched_name}.")
            open_url(url)
            return True

    # ----- 8. CLOSE APP -----
    close_match = re.match(r"close\s+(.+)", command)
    if close_match:
        close_app(close_match.group(1).strip())
        return True

    # ----- 9. OPEN APP -----
    if open_match:
        # We already checked websites above, so this is an app
        open_app(open_match.group(1).strip())
        return True

    # ----- 10. TIME & DATE -----
    if "time" in command and ("what" in command or "current" in command
                              or "tell" in command):
        get_time()
        return True

    if "date" in command and ("what" in command or "today" in command
                              or "tell" in command):
        get_date()
        return True

    # ----- 11. AI CHAT (fallback) -----
    # If nothing else matched, send it to the AI
    chat_with_ai(command)
    return True


# =============================================================================
# MAIN LOOP - Listens to the microphone and processes commands
# =============================================================================

def main():
    """
    Main function: loads the Vosk model, opens the microphone,
    and listens continuously for the wake word "Hey Liku".
    """
    global is_speaking

    # --- Check required libraries ---
    if sd is None:
        print("ERROR: 'sounddevice' is not installed. Run: pip install sounddevice")
        sys.exit(1)
    if Model is None:
        print("ERROR: 'vosk' is not installed. Run: pip install vosk")
        sys.exit(1)
    if pyttsx3 is None:
        print("ERROR: 'pyttsx3' is not installed. Run: pip install pyttsx3")
        sys.exit(1)

    # --- Check for the Vosk model ---
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

    # --- Load the model ---
    print("Loading Vosk speech model... (this may take a moment)")
    try:
        model = Model(model_path)
        recognizer = KaldiRecognizer(model, SAMPLE_RATE)
    except Exception as e:
        print(f"ERROR: Could not load Vosk model: {e}")
        sys.exit(1)

    print("Model loaded successfully!")

    # --- Audio queue for thread-safe communication ---
    audio_queue = queue.Queue()

    def audio_callback(indata, frames, time_info, status):
        """Called by sounddevice for each audio block."""
        if status:
            print(f"[Audio warning]: {status}")
        # Only queue audio if Liku isn't speaking
        if not is_speaking:
            audio_queue.put(bytes(indata))

    # --- Open the microphone ---
    try:
        stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            dtype="int16",
            channels=CHANNELS,
            callback=audio_callback,
        )
    except Exception as e:
        print(f"ERROR: Could not open microphone: {e}")
        print("Make sure a microphone is connected and not in use by another app.")
        sys.exit(1)

    # --- Start listening ---
    print()
    print("=" * 60)
    print("  LIKU VOICE ASSISTANT")
    print("  Say 'Hey Liku' followed by your command!")
    print("  Say 'Hey Liku stop' to quit.")
    print("=" * 60)
    print()

    speak("Hello! I'm Liku, your voice assistant. Say Hey Liku to wake me up!")

    running = True

    with stream:
        while running:
            try:
                # Get audio data from the queue (blocks until available)
                data = audio_queue.get()

                # Feed audio to the recognizer
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "").strip()

                    if not text:
                        continue

                    print(f"[Heard]: '{text}'")

                    # Check for the wake word
                    wake_detected, remaining_command = check_wake_word(text)

                    if wake_detected:
                        if remaining_command:
                            # Command came with the wake word
                            # e.g., "Hey Liku open vs code"
                            running = process_command(remaining_command)
                        else:
                            # Just the wake word - wait for the command
                            speak("Yes?")

                            # Clear the audio queue (discard Liku's own voice)
                            while not audio_queue.empty():
                                try:
                                    audio_queue.get_nowait()
                                except queue.Empty:
                                    break

                            # Reset recognizer state to avoid leftover audio
                            recognizer.Reset()

                            # Wait up to 8 seconds for a follow-up command
                            print("[Waiting for command...]")
                            start_time = time.time()
                            got_command = False
                            partial_text = ""

                            while time.time() - start_time < FOLLOW_UP_TIMEOUT:
                                try:
                                    audio_data = audio_queue.get(timeout=0.2)
                                except queue.Empty:
                                    continue

                                if recognizer.AcceptWaveform(audio_data):
                                    res = json.loads(recognizer.Result())
                                    follow_up = res.get("text", "").strip()

                                    if follow_up:
                                        print(f"[Heard]: '{follow_up}'")
                                        running = process_command(follow_up)
                                        got_command = True
                                        break
                                else:
                                    # Capture partial result in case silence endpoint doesn't trigger
                                    part = json.loads(recognizer.PartialResult()).get("partial", "").strip()
                                    if part:
                                        partial_text = part

                            if not got_command:
                                # Check if speech was captured in FinalResult or partial
                                final_res = json.loads(recognizer.FinalResult()).get("text", "").strip()
                                fallback_cmd = final_res or partial_text
                                if fallback_cmd:
                                    print(f"[Heard (fallback)]: '{fallback_cmd}'")
                                    running = process_command(fallback_cmd)
                                    got_command = True
                                else:
                                    speak("I didn't hear a command. "
                                          "Say Hey Liku again when you're ready.")

                            # Clear queue again after processing
                            while not audio_queue.empty():
                                try:
                                    audio_queue.get_nowait()
                                except queue.Empty:
                                    break
                            recognizer.Reset()

                    elif is_direct_command(text):
                        # Direct command detected without wake word (e.g. "open youtube", "volume up")
                        print(f"[Direct command]: '{text}'")
                        running = process_command(text)

            except KeyboardInterrupt:
                print("\nInterrupted by user.")
                speak("Goodbye!")
                running = False
            except Exception as e:
                print(f"[Error in main loop]: {e}")
                # Don't crash - keep listening
                continue

    print("Liku has stopped. See you next time!")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    main()
