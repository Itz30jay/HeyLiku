"""
test_liku.py - Offline tests for Liku voice assistant.

These tests do NOT use the microphone or Vosk model.
They test the core logic: wake word detection, YouTube parsing,
app matching, direct command detection, and command routing.

Run with: python test_liku.py
"""

import sys
import os

# Add the parent directory so we can import from liku.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the functions we want to test
from liku import (
    check_wake_word,
    extract_youtube_query,
    find_app,
    find_website,
    normalize_command,
    is_direct_command,
)


def test_wake_word_with_command():
    """Test: 'hey liku open vs code' should detect wake word and extract command."""
    detected, command = check_wake_word("hey liku open vs code")
    assert detected is True, f"Wake word not detected! Got: {detected}"
    assert command == "open vs code", f"Wrong command! Got: '{command}'"
    print("PASS: 'hey liku open vs code' -> detected, command='open vs code'")


def test_wake_word_alone():
    """Test: just 'hey liku' should detect wake word with empty command."""
    detected, command = check_wake_word("hey liku")
    assert detected is True, f"Wake word not detected! Got: {detected}"
    assert command == "", f"Expected empty command! Got: '{command}'"
    print("PASS: 'hey liku' -> detected, command=''")


def test_wake_word_standalone_start():
    """Test: 'liku open youtube' should detect wake word and extract command."""
    detected, command = check_wake_word("liku open youtube")
    assert detected is True, f"Wake word not detected! Got: {detected}"
    assert command == "open youtube", f"Wrong command! Got: '{command}'"
    print("PASS: 'liku open youtube' -> detected, command='open youtube'")


def test_wake_word_at_end():
    """Test: 'open youtube liku' should detect wake word at the end."""
    detected, command = check_wake_word("open youtube liku")
    assert detected is True, f"Wake word at end not detected! Got: {detected}"
    assert command == "open youtube", f"Wrong command! Got: '{command}'"
    print("PASS: 'open youtube liku' -> detected, command='open youtube'")


def test_wake_word_greeting_at_end():
    """Test: 'open youtube hey liku' should detect wake word at the end."""
    detected, command = check_wake_word("open youtube hey liku")
    assert detected is True, f"Wake word at end not detected! Got: {detected}"
    assert command == "open youtube", f"Wrong command! Got: '{command}'"
    print("PASS: 'open youtube hey liku' -> detected, command='open youtube'")


def test_wake_word_fuzzy_leeku():
    """Test: 'hey leeku' should be accepted (fuzzy match)."""
    detected, command = check_wake_word("hey leeku")
    assert detected is True, f"Fuzzy match 'leeku' failed! Got: {detected}"
    print("PASS: 'hey leeku' -> detected (fuzzy)")


def test_wake_word_fuzzy_liko():
    """Test: 'hey liko' should be accepted (fuzzy match)."""
    detected, command = check_wake_word("hey liko")
    assert detected is True, f"Fuzzy match 'liko' failed! Got: {detected}"
    print("PASS: 'hey liko' -> detected (fuzzy)")


def test_wake_word_fuzzy_like_you():
    """Test: 'hey like you open chrome' should be accepted (two-word fuzzy match)."""
    detected, command = check_wake_word("hey like you open chrome")
    assert detected is True, f"Fuzzy match 'like you' failed! Got: {detected}"
    assert command == "open chrome", f"Wrong command! Got: '{command}'"
    print("PASS: 'hey like you open chrome' -> detected (fuzzy)")


def test_wake_word_no_match():
    """Test: random text should NOT trigger the wake word."""
    detected, command = check_wake_word("hello world how are you")
    assert detected is False, f"False positive! Got: {detected}"
    print("PASS: 'hello world how are you' -> NOT detected")


def test_is_direct_command():
    """Test: direct action commands without wake word are recognized."""
    direct_phrases = [
        "open youtube",
        "open you tube",
        "turn on youtube",
        "please open youtube",
        "open vs code",
        "play magician video",
        "take a screenshot",
        "what time is it",
        "volume up",
        "close notepad",
        "lock the computer",
    ]
    for phrase in direct_phrases:
        assert is_direct_command(phrase) is True, f"Expected '{phrase}' to be direct command!"
    print("PASS: direct commands detected without wake word")


def test_is_not_direct_command():
    """Test: normal conversation is NOT treated as direct command."""
    non_direct = [
        "hello world",
        "how are you today",
        "tell a joke",
        "what is the meaning of life",
    ]
    for phrase in non_direct:
        assert is_direct_command(phrase) is False, f"Did not expect '{phrase}' to be direct command!"
    print("PASS: conversational phrases are NOT direct commands")


def test_normalize_command():
    """Test: speech recognition normalization."""
    assert normalize_command("you tube") == "youtube"
    assert normalize_command("please open youtube") == "open youtube"
    assert normalize_command("can you open vs code") == "open vs code"
    assert normalize_command("could you please open notepad") == "open notepad"
    print("PASS: normalize_command handles polite prefixes and speech quirks")


def test_youtube_turn_on_and_play():
    """Test: 'turn on youtube and play magician video' extracts the query."""
    query = extract_youtube_query("turn on youtube and play magician video")
    assert query == "magician video", f"Wrong query! Got: '{query}'"
    print("PASS: YouTube query = 'magician video'")


def test_youtube_turn_on_play_no_and():
    """Test: 'turn on youtube play magician video' (without 'and') extracts the query."""
    query = extract_youtube_query("turn on youtube play magician video")
    assert query == "magician video", f"Wrong query! Got: '{query}'"
    print("PASS: YouTube query (no 'and') = 'magician video'")


def test_youtube_play_on():
    """Test: 'play lofi music on youtube' extracts the query."""
    query = extract_youtube_query("play lofi music on youtube")
    assert query == "lofi music", f"Wrong query! Got: '{query}'"
    print("PASS: YouTube query = 'lofi music'")


def test_youtube_general_play():
    """Test: 'play magician video' without 'on youtube' routes to YouTube."""
    query = extract_youtube_query("play magician video")
    assert query == "magician video", f"Wrong query! Got: '{query}'"
    print("PASS: YouTube general play query = 'magician video'")


def test_youtube_search_for():
    """Test: 'search youtube for cat videos' extracts the query."""
    query = extract_youtube_query("search youtube for cat videos")
    assert query == "cat videos", f"Wrong query! Got: '{query}'"
    print("PASS: YouTube query = 'cat videos'")


def test_youtube_open():
    """Test: 'open youtube' returns empty string (just open the site)."""
    assert extract_youtube_query("open youtube") == ""
    assert extract_youtube_query("open you tube") == ""
    assert extract_youtube_query("turn on youtube") == ""
    assert extract_youtube_query("youtube") == ""
    print("PASS: 'open youtube' variants -> just open site (empty query)")


def test_youtube_not_youtube():
    """Test: non-YouTube commands return None."""
    query = extract_youtube_query("open notepad")
    assert query is None, f"Should be None! Got: '{query}'"
    print("PASS: 'open notepad' -> not a YouTube command")


def test_find_app_vscode():
    """Test: 'vs code' matches the vscode entry."""
    result = find_app("vs code")
    assert result is not None, "vs code not found!"
    command, name = result
    assert command == "code", f"Wrong command! Got: '{command}'"
    print(f"PASS: find_app('vs code') -> command='code', name='{name}'")


def test_find_app_fuzzy():
    """Test: fuzzy matching for slightly misspelled app name."""
    result = find_app("notpad")  # misspelling of "notepad"
    assert result is not None, "Fuzzy match for 'notpad' failed!"
    command, name = result
    assert command == "notepad", f"Wrong command! Got: '{command}'"
    print(f"PASS: find_app('notpad') -> fuzzy matched to '{name}'")


def test_find_app_not_found():
    """Test: unknown app returns None."""
    result = find_app("xyznonexistentapp123")
    assert result is None, f"Should be None! Got: {result}"
    print("PASS: find_app('xyznonexistentapp123') -> None")


def test_find_website_google():
    """Test: 'google' matches the Google website."""
    result = find_website("google")
    assert result is not None, "google website not found!"
    url, name = result
    assert url == "https://www.google.com", f"Wrong URL! Got: '{url}'"
    print(f"PASS: find_website('google') -> url='{url}'")


def test_find_website_not_found():
    """Test: unknown website returns None."""
    result = find_website("xyznonexistentsite123")
    assert result is None, f"Should be None! Got: {result}"
    print("PASS: find_website('xyznonexistentsite123') -> None")


def test_wake_word_hey_like():
    """Test: 'hey like open youtube' and 'hey like open vs code' (speech recognition variations)."""
    detected, cmd = check_wake_word("hey like open youtube")
    assert detected is True, f"Failed detecting 'hey like'! Got: {detected}"
    assert cmd == "open youtube", f"Wrong command! Got: '{cmd}'"

    detected2, cmd2 = check_wake_word("hey like open vs code")
    assert detected2 is True, f"Failed detecting 'hey like'! Got: {detected2}"
    assert cmd2 == "open vs code", f"Wrong command! Got: '{cmd2}'"
    print("PASS: 'hey like open ...' phonetic variants recognized")


def test_direct_commands_extended():
    """Test: direct commands work without any wake word."""
    assert is_direct_command("open vs code") is True
    assert is_direct_command("open youtube") is True
    assert is_direct_command("open chrome") is True
    assert is_direct_command("vs code") is True
    assert is_direct_command("chrome") is True
    assert is_direct_command("notepad") is True
    assert is_direct_command("youtube") is True
    assert is_direct_command("volume up") is True
    assert is_direct_command("screenshot") is True
    print("PASS: extended direct commands recognized without wake word")


# =============================================================================
# RUN ALL TESTS
# =============================================================================

def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_wake_word_with_command,
        test_wake_word_alone,
        test_wake_word_standalone_start,
        test_wake_word_at_end,
        test_wake_word_greeting_at_end,
        test_wake_word_fuzzy_leeku,
        test_wake_word_fuzzy_liko,
        test_wake_word_fuzzy_like_you,
        test_wake_word_hey_like,
        test_wake_word_no_match,
        test_is_direct_command,
        test_direct_commands_extended,
        test_is_not_direct_command,
        test_normalize_command,
        test_youtube_turn_on_and_play,
        test_youtube_turn_on_play_no_and,
        test_youtube_play_on,
        test_youtube_general_play,
        test_youtube_search_for,
        test_youtube_open,
        test_youtube_not_youtube,
        test_find_app_vscode,
        test_find_app_fuzzy,
        test_find_app_not_found,
        test_find_website_google,
        test_find_website_not_found,
    ]

    print("=" * 60)
    print("  LIKU VOICE ASSISTANT - TEST SUITE")
    print("=" * 60)
    print()

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test_fn.__name__} - {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test_fn.__name__} - {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"  Results: {passed} passed, {failed} failed, {len(tests)} total")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    else:
        print("  All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()
