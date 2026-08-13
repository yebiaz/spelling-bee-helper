"""Spelling Bee Helper - standalone app.

Run it with:   streamlit run app.py

This replaces the ipywidgets GUI. All of the actual logic still lives in the
other files, which are the notebook code ported over almost line for line.
"""

import math

import streamlit as st

from dictionary import loadDictionary
from difficulty import trainDifficulty
from game import GameSaving
from hintgrid import OCR_AVAILABLE, applyGrid, checkParse, inferCenter, parseHintGrid
from trie import buildTrie, levelByDifficulty, pangramsLeft

st.set_page_config(page_title="Spelling Bee Helper", page_icon="⬡", layout="wide")

# ----------------------------------------------------------------------
# Look and feel
# ----------------------------------------------------------------------

PAPER = "#E4DFCB"
PANEL = "#EFEBDC"
INK = "#211F18"
INK_SOFT = "#5A5443"
HONEY = "#DFA22B"
MOSS = "#4C6B45"
OCHRE = "#C68A1E"
CLAY = "#9E3D28"
BUTTON_TEXT = "#B4AE9F"  # grey on the black button, so it stays readable
BUTTON_HOVER = "#C9C3B2"
TRACK = "#57534A"  # dark grey progress track

DIFF_COLOR = {0: MOSS, 1: OCHRE, 2: CLAY}
DIFF_NAME = {0: "common", 1: "middling", 2: "obscure"}

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,600&family=Work+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    .stApp {{ background: {PAPER}; color: {INK}; }}
    html, body, [class*="st-"], .stMarkdown, p, span, div, label {{
        font-family: 'Work Sans', system-ui, sans-serif;
    }}

    /* Streamlit draws the expander arrow and the upload icon as ligatures in
       Material Symbols. The rule above was overriding that font, so the
       ligature name ("arrow_down", "upload") printed as literal text on top of
       the label. Hand those elements their font back. */
    span[data-testid="stIconMaterial"], [data-testid="stExpanderToggleIcon"],
    .material-symbols-rounded, .material-icons, [class*="material-symbols"] {{
        font-family: 'Material Symbols Rounded', 'Material Icons' !important;
    }}

    /* nothing in this app should ever be white on cream */
    .stApp, .stMarkdown, [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label,
    .stRadio label, .stCheckbox label, .stSelectbox label, .stTextInput label,
    .stFileUploader label, [data-testid="stExpander"] summary, [data-testid="stExpander"] p {{
        color: {INK} !important;
    }}

    /* Streamlit styles its own paragraphs with [data-testid="stMarkdownContainer"] p,
       which outranks a bare .hive-title class - that is why the title kept coming out
       at body size no matter what number went in here. Match that specificity and
       mark it important so the size actually lands. */
    .hive-title, .stMarkdown .hive-title,
    [data-testid="stMarkdownContainer"] .hive-title {{
        font-family: 'Fraunces', Georgia, serif !important;
        font-weight: 600 !important;
        font-size: clamp(3.4rem, 8vw, 7rem) !important;
        line-height: 0.95 !important;
        letter-spacing: -0.035em !important;
        color: {INK} !important;
        margin: 0 0 0.4rem 0 !important;
    }}
    .rule {{ border-bottom: 1px solid {INK}; opacity: 0.25; margin: 1.1rem 0 1.4rem 0; }}

    .panel-label {{
        font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem;
        letter-spacing: 0.16em; text-transform: uppercase;
        color: {INK_SOFT}; margin-bottom: 0.55rem;
    }}

    .rank {{ font-family: 'Fraunces', serif; font-size: 2.1rem; font-weight: 600; color: {INK}; }}
    .score {{ font-family: 'IBM Plex Mono', monospace; color: {INK_SOFT}; font-size: 0.85rem; }}
    .score b {{ color: {INK}; }}

    .blanks {{
        font-family: 'IBM Plex Mono', monospace; font-size: 1.05rem;
        letter-spacing: 0.06em; color: {INK}; padding-top: 0.45rem;
    }}
    .hintmsg {{
        font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem;
        color: {INK_SOFT}; padding-top: 0.55rem;
    }}
    .verdict {{ font-family: 'Fraunces', serif; font-size: 1.15rem; }}
    .found-word {{
        font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem;
        display: inline-block; padding: 2px 8px; margin: 0 4px 5px 0;
        border: 1px solid rgba(33,31,24,0.28); color: {INK};
    }}
    .pangram {{ background: {HONEY}; border-color: {HONEY}; }}

    .legend {{
        font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;
        color: {INK}; margin: 0.5rem 0 0.2rem 0;
    }}
    .swatch {{
        display: inline-block; width: 11px; height: 11px; margin-right: 5px;
        border: 1px solid rgba(33,31,24,0.35); vertical-align: -1px;
    }}

    /* buttons: black box, grey label; invert on hover so both states read */
    .stButton > button, .stFormSubmitButton > button, [data-testid="stBaseButton-secondary"] {{
        font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;
        border-radius: 0; border: 1px solid {INK};
        background: {INK} !important; color: {BUTTON_TEXT} !important;
    }}
    .stButton > button:hover, .stFormSubmitButton > button:hover {{
        background: {BUTTON_HOVER} !important; color: {INK} !important; border-color: {INK};
    }}
    .stButton > button p, .stFormSubmitButton > button p {{ color: inherit !important; }}

    /* the currently chosen bucket style, in the same honey as the centre cell */
    .st-key-style_two_active button, .st-key-style_len_active button,
    .st-key-bucket_active button {{
        background: {HONEY} !important; color: {INK} !important; border-color: {INK};
    }}
    .st-key-style_two_active button:hover, .st-key-style_len_active button:hover,
    .st-key-bucket_active button:hover {{
        background: {HONEY} !important; color: {INK} !important;
    }}

    /* progress: dark grey track, honey fill */
    [data-testid="stProgress"] div[role="progressbar"] > div,
    .stProgress > div > div > div {{
        background-color: {TRACK} !important; border-radius: 0 !important;
    }}
    [data-testid="stProgress"] div[role="progressbar"] > div > div,
    .stProgress > div > div > div > div {{
        background-color: {HONEY} !important; background-image: none !important;
        border-radius: 0 !important;
    }}

    /* the ? button in the header */
    .st-key-help_btn button, [data-testid="stPopover"] button {{
        font-family: 'Fraunces', serif !important; font-size: 1.1rem !important;
        background: {INK} !important; color: {BUTTON_TEXT} !important;
        border: 1px solid {INK} !important; border-radius: 0;
    }}
    [data-testid="stPopover"] button:hover {{
        background: {HONEY} !important; color: {INK} !important;
    }}

    /* The popover surface follows the browser/Streamlit theme, so pinning the text
       to ink made it black-on-black in dark mode. Pin both sides instead: dark
       panel, honey text. */
    [data-testid="stPopoverBody"], div[data-baseweb="popover"] [data-testid="stPopoverBody"] {{
        background: {INK} !important; border: 1px solid {HONEY} !important;
    }}
    [data-testid="stPopoverBody"] p, [data-testid="stPopoverBody"] div,
    [data-testid="stPopoverBody"] span, [data-testid="stPopoverBody"] b,
    [data-testid="stPopoverBody"] h4, .helpnote, .helpnote * {{
        color: {HONEY} !important;
    }}
    .helpnote {{ font-family: 'Work Sans', sans-serif; font-size: 0.92rem; line-height: 1.5; }}
    .helpnote h4 {{
        font-family: 'Fraunces', serif !important; font-size: 1.15rem;
        margin: 0.9rem 0 0.35rem 0;
    }}
    .helpnote h4:first-child {{ margin-top: 0.1rem; }}
    .dead-word {{
        font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem;
        display: inline-block; padding: 2px 8px; margin: 0 4px 5px 0;
        border: 1px dashed rgba(33,31,24,0.4); color: {INK_SOFT};
        text-decoration: line-through;
    }}

    [data-testid="stSidebar"] {{ background: {PANEL}; }}
    [data-testid="stExpander"] {{ border: 1px solid rgba(33,31,24,0.25); border-radius: 0; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def hiveSVG(letters, center):
    """The seven-cell hive. Centre cell in honey, the rest in wax."""
    R = 44
    d = math.sqrt(3) * R + 7
    outer = sorted(l for l in letters if l != center)
    cx, cy = 125, 138
    spots = [(cx, cy, center, True)]
    for i, letter in enumerate(outer):
        angle = math.radians(30 + 60 * i)
        spots.append((cx + d * math.cos(angle), cy + d * math.sin(angle), letter, False))

    cells = []
    for x, y, letter, isCenter in spots:
        pts = " ".join(
            f"{x + R * math.cos(math.radians(60 * k)):.1f},{y + R * math.sin(math.radians(60 * k)):.1f}"
            for k in range(6)
        )
        fill = HONEY if isCenter else "#F2EEE0"
        cells.append(
            f'<polygon points="{pts}" fill="{fill}" stroke="{INK}" stroke-width="1.5" />'
            f'<text x="{x:.1f}" y="{y + 11:.1f}" text-anchor="middle" '
            f'font-family="Fraunces, Georgia, serif" font-size="31" font-weight="600" '
            f'fill="{INK}">{letter.upper()}</text>'
        )
    return f'<svg viewBox="0 0 250 275" width="100%" style="max-width:280px">{"".join(cells)}</svg>'


# ----------------------------------------------------------------------
# Heavy setup - cached so it happens once, not on every click
# ----------------------------------------------------------------------


@st.cache_resource(show_spinner="Loading the dictionary...")
def getDictionary():
    return loadDictionary()


@st.cache_resource(show_spinner="Building the trie...")
def getTrie(_words, wordCount):
    return buildTrie(_words)


@st.cache_resource(show_spinner="Training the difficulty model...")
def getDifficulty(_words, wordCount):
    return trainDifficulty(_words)


myDict, myPangrams = getDictionary()
wholeTrie = getTrie(myDict, len(myDict))
difficulty, metrics = getDifficulty(myDict, len(myDict))


# ----------------------------------------------------------------------
# State
# ----------------------------------------------------------------------


def startGame(solutions, letters, center):
    """Build a game, minus anything already blacklisted this session.

    Once you have confirmed NYT does not count a word, it should not come back
    the next time those letters turn up, so the blacklist outlives the puzzle.
    """
    game = GameSaving(solutions, letters, center, difficulty)
    for word in st.session_state.get("blacklist", []):
        game.solutions.discard(word)
        game.notCounted.add(word)
    return game


def resetRound():
    st.session_state.verdict = ""
    st.session_state.lastFound = ""
    st.session_state.hints = {}
    st.session_state.bucket = None
    st.session_state.nyt = None
    st.session_state.gridReport = None


def newRandomGame(level="medium"):
    letters, center, solutions = levelByDifficulty(
        wholeTrie, myPangrams, difficulty.familiarity, level
    )
    st.session_state.game = startGame(solutions, letters, center)
    resetRound()


def newNYTGame(rawLetters, rawCenter):
    letters = set(rawLetters.strip().lower())
    center = rawCenter.strip().lower()
    if len(letters) != 7 or len(center) != 1 or center not in letters:
        return "Enter exactly 7 different letters, and a centre letter that is one of them."
    solutions = wholeTrie.search(letters, center)
    if not solutions:
        return "No words in the dictionary use those letters."
    st.session_state.game = startGame(solutions, letters, center)
    resetRound()
    return None


if "game" not in st.session_state:
    newRandomGame()
st.session_state.setdefault("bucketStyle", "two")
st.session_state.setdefault("blacklist", [])
st.session_state.setdefault("showRandom", False)

game = st.session_state.game


def maskedWord(word, mode, prefixLen):
    """What the player is allowed to see of a word in this bucket.

    NYT's two-letter list tells you the first two letters and nothing else -
    crucially not the length - so in that mode the tail is a single ellipsis
    rather than a row of blanks you could count. The letter-and-length grid
    does tell you the length, so that mode shows real blanks.

    Length also becomes fair game once a hint has actually revealed a position
    beyond the prefix, or scrambled the whole word.
    """
    tracker = game.alreadyHints.get(word, {})
    shown = set(tracker.get("shown", []))
    scrambled = tracker.get("scrambled", False)

    revealed = set(range(prefixLen)) | shown
    lengthKnown = mode == "len" or scrambled or any(p >= prefixLen for p in shown)

    if not lengthKnown:
        head = " ".join(word[i].upper() for i in range(prefixLen))
        return f"{head} \u00b7\u00b7\u00b7"

    return " ".join(word[i].upper() if i in revealed else "_" for i in range(len(word)))


def readableGaps(gaps):
    """Turn the leftover quota into lines a person can actually read.

    applyGrid has already paired the two tallies where it could, so most gaps
    arrive as a prefix and a length together. Render those as the blanks they
    describe: AN _ _ _ _ says more than "1 more starting AN".
    """
    lines = []
    for gap in gaps:
        prefix = gap["prefix"].upper()
        length = gap["length"]
        count = gap["count"]
        many = "" if count == 1 else f"{count} words: "

        if length:
            blanks = " ".join(list(prefix) + ["_"] * (length - len(prefix)))
            lines.append(f"{many}{blanks}  ({length} letters)")
        else:
            lines.append(f"{many}{' '.join(list(prefix))} \u00b7\u00b7\u00b7  (length unknown)")
    return lines


# ----------------------------------------------------------------------
# Sidebar - puzzle setup
# ----------------------------------------------------------------------

with st.sidebar:
    st.markdown('<div class="panel-label">Puzzle</div>', unsafe_allow_html=True)

    if st.button("Random puzzle", use_container_width=True):
        st.session_state.showRandom = not st.session_state.showRandom
        st.rerun()

    if st.session_state.showRandom:
        st.markdown('<div class="score">How hard should it be?</div>', unsafe_allow_html=True)
        for label, key in [("Easy", "easy"), ("Medium", "medium"), ("Hard", "hard")]:
            if st.button(label, key=f"level_{key}", use_container_width=True):
                newRandomGame(key)
                st.session_state.showRandom = False
                st.rerun()

    with st.expander("Load NYT puzzle"):
        nytLetters = st.text_input("Seven letters", key="nyt_letters", placeholder="albumen")
        nytCenter = st.text_input("Centre letter", key="nyt_center", placeholder="a", max_chars=1)
        if st.button("Load", key="load_nyt", use_container_width=True):
            problem = newNYTGame(nytLetters, nytCenter)
            if problem:
                st.error(problem)
            else:
                st.rerun()


# ----------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------

titleCol, helpCol = st.columns([9, 1])
with titleCol:
    st.markdown(
        '<div class="hive-title" style="font-size:clamp(3.4rem,8vw,7rem);'
        "line-height:0.95;font-family:'Fraunces',Georgia,serif;font-weight:600;"
        'letter-spacing:-0.035em">Spelling Bee Helper</div>',
        unsafe_allow_html=True,
    )
with helpCol:
    with st.popover("?", use_container_width=True):
        st.markdown(
            """
            <div class="helpnote">
            <h4>What this is</h4>
            A companion for the New York Times Spelling Bee, for people who play it
            religiously. NYT gives you seven letters, a centre letter that every answer must
            use, and a grid of hints that tells you how many answers start with each letter
            pair and each length.

            <h4>What we do that the NYT puzzle doesn't</h4>
            <b>Keeps track for you.</b> Every answer still out there, sorted into the same
            buckets NYT uses, with the words you have found ticked off. No more scribbling on
            a napkin.
            <br><br>
            <b>Tells you if a word is worth chasing.</b> That last stubborn answer: is it a
            word you actually know, or is it LLANO? A logistic-regression model rates every
            remaining answer common, middling or obscure from its frequency, length, letter
            pattern and whether it is a regular form of a word you already know.
            <br><br>
            <b>Hints sized to the word.</b> Common words get a single letter with no position.
            Middling ones get a letter and where it goes. Obscure ones get the whole thing
            scrambled, because a letter would not have helped.
            <br><br>
            <b>Reconciles with NYT's answer list.</b> NYT does not use one fixed dictionary,
            so our solver finds words they do not count and misses a few they do. Upload a
            screenshot of their hint page and it works out which of our candidates they meant,
            and tells you what shape the answers we are missing are.

            <h4>Getting started</h4>
            Pick a random puzzle from the sidebar to practice, or enter today's NYT letters.
            Type guesses in the box under the hive. Open a bucket on the right to see what is
            left and ask for a hint.
            </div>
            """,
            unsafe_allow_html=True,
        )

# The title is large enough that its descenders reach the next row, and removing the
# PROGRESS label pulled both columns up into it. Hold the gap open explicitly.
st.markdown('<div style="height:2.1rem"></div>', unsafe_allow_html=True)

left, right = st.columns([1, 1.35], gap="large")

# ----------------------------------------------------------------------
# Left: progress, the hive, guessing
# ----------------------------------------------------------------------

with left:
    st.markdown(f'<div class="rank">{game.ranking()}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="score">{game.totalScore()} / {game.maxPossScore()} points &nbsp;·&nbsp; '
        f'{len(game.wordsFound)} of {len(game.solutions)} words</div>',
        unsafe_allow_html=True,
    )
    st.progress(min(game.percent() / 100, 1.0))

    st.markdown(hiveSVG(game.letters, game.center), unsafe_allow_html=True)

    with st.form("guess_form", clear_on_submit=True):
        guess = st.text_input("Your word", placeholder="type a word", label_visibility="collapsed")
        submitted = st.form_submit_button("Submit", use_container_width=True)
    if submitted and guess:
        st.session_state.verdict = game.userGuess(guess)
        st.session_state.lastFound = guess.strip().lower()

    if st.session_state.verdict:
        good = st.session_state.verdict == "Congrats, found!"
        color = MOSS if good else CLAY
        message = st.session_state.verdict
        if good and st.session_state.lastFound:
            message = f"Congrats, found &mdash; {st.session_state.lastFound.upper()}"
        st.markdown(f'<div class="verdict" style="color:{color}">{message}</div>', unsafe_allow_html=True)

    if game.rareLeft():
        st.warning("Only rare words left.")

    remainingPangrams = pangramsLeft(game.wordsLeft())
    if remainingPangrams:
        st.markdown(
            f'<div class="score">{len(remainingPangrams)} pangram(s) still out there.</div>',
            unsafe_allow_html=True,
        )

    if game.wordsFound:
        st.markdown('<div class="panel-label" style="margin-top:1rem">Found</div>', unsafe_allow_html=True)
        chips = "".join(
            f'<span class="found-word{" pangram" if len(set(w)) == 7 else ""}">{w}</span>'
            for w in sorted(game.wordsFound)
        )
        st.markdown(chips, unsafe_allow_html=True)

        st.markdown(
            '<div class="score" style="margin-top:0.6rem">Typed one in and NYT would not take '
            "it? Mark it below and the best set-aside word from the same bucket takes its "
            "place.</div>",
            unsafe_allow_html=True,
        )
        cols = st.columns(3)
        for i, word in enumerate(sorted(game.wordsFound)):
            if cols[i % 3].button(f"✕ {word}", key=f"reject_{word}", use_container_width=True):
                swap = game.rejectWord(word)
                if word not in st.session_state.blacklist:
                    st.session_state.blacklist.append(word)
                st.session_state.hints.pop(word, None)
                st.session_state.verdict = swap["msg"]
                st.session_state.lastFound = ""
                st.rerun()

    if st.session_state.blacklist:
        st.markdown(
            '<div class="panel-label" style="margin-top:1.1rem">Not counted</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            "".join(f'<span class="dead-word">{w}</span>' for w in st.session_state.blacklist),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="score">These stay out of every puzzle for the rest of the session, so '
            "you will not chase them twice.</div>",
            unsafe_allow_html=True,
        )
        if st.button("Clear this list", key="clear_blacklist"):
            st.session_state.blacklist = []
            st.rerun()


# ----------------------------------------------------------------------
# Right: hint roadmap + NYT reconciliation
# ----------------------------------------------------------------------

with right:
    st.markdown('<div class="panel-label">Hint roadmap</div>', unsafe_allow_html=True)

    prefixLenCounts, twoLetterCounts = game.roadmap()

    if not game.wordsLeft():
        st.markdown('<div class="score">Every word found. Queen Bee.</div>', unsafe_allow_html=True)
    else:
        styleCols = st.columns(2)
        twoKey = "style_two_active" if st.session_state.bucketStyle == "two" else "style_two"
        lenKey = "style_len_active" if st.session_state.bucketStyle == "len" else "style_len"
        if styleCols[0].button("Two-letter prefix", key=twoKey, use_container_width=True):
            st.session_state.bucketStyle = "two"
            st.session_state.bucket = None
            st.rerun()
        if styleCols[1].button("First letter + length", key=lenKey, use_container_width=True):
            st.session_state.bucketStyle = "len"
            st.session_state.bucket = None
            st.rerun()

        if st.session_state.bucketStyle == "two":
            items = [(f"{p.upper()} · {c}", ("two", p)) for p, c in sorted(twoLetterCounts.items())]
        else:
            items = [
                (f"{l.upper()}{n} · {c}", ("len", l, n)) for (l, n), c in sorted(prefixLenCounts.items())
            ]

        cols = st.columns(5)
        for i, (label, key) in enumerate(items):
            active = st.session_state.bucket == key
            buttonKey = "bucket_active" if active else f"bucket_{label}"
            if cols[i % 5].button(label, key=buttonKey, use_container_width=True):
                st.session_state.bucket = key
                st.rerun()

        st.markdown('<div class="rule"></div>', unsafe_allow_html=True)

        hintType = st.selectbox(
            "Hint strength",
            ["autoDiff", "randLetter", "letterAndPos", "scrambled"],
            format_func=lambda h: {
                "autoDiff": "Auto (model picks by difficulty)",
                "randLetter": "Small - a letter, no position",
                "letterAndPos": "Medium - a letter and its position",
                "scrambled": "Big - the whole word, scrambled",
            }[h],
        )

        st.markdown(
            f'<div class="legend">'
            f'<span class="swatch" style="background:{MOSS}"></span>common'
            f'&nbsp;&nbsp;<span class="swatch" style="background:{OCHRE}"></span>middling'
            f'&nbsp;&nbsp;<span class="swatch" style="background:{CLAY}"></span>obscure'
            f"</div>",
            unsafe_allow_html=True,
        )

        bucket = st.session_state.bucket
        if bucket is None:
            st.markdown(
                '<div class="score">Pick a bucket above to see its words.</div>',
                unsafe_allow_html=True,
            )
        else:
            if bucket[0] == "two":
                prefix = bucket[1]
                words = sorted(w for w in game.wordsLeft() if w.startswith(prefix))
            else:
                _, letter, length = bucket
                prefix = letter
                words = sorted(w for w in game.wordsLeft() if w.startswith(letter) and len(w) == length)

            if not words:
                st.markdown('<div class="score">Nothing left in that bucket.</div>', unsafe_allow_html=True)

            for word in words:
                diff = game.difficulty.predictDifficulty(word)

                c1, c2, c3 = st.columns([2.4, 1.1, 3])
                c1.markdown(
                    f'<div class="blanks"><span style="color:{DIFF_COLOR[diff]}">●</span> '
                    f"{maskedWord(word, bucket[0], len(prefix))}</div>",
                    unsafe_allow_html=True,
                )
                if c2.button("Hint", key=f"hint_{word}", use_container_width=True):
                    # the prefix is already on screen, so don't spend a hint on it
                    game.applyPrefixReveal(word, prefix)
                    st.session_state.hints[word] = game.whichHint(word, hintType)
                    st.rerun()
                c3.markdown(
                    f'<div class="hintmsg">{st.session_state.hints.get(word, DIFF_NAME[diff])}</div>',
                    unsafe_allow_html=True,
                )

    # ------------------------------------------------------------------
    # NYT reconciliation
    # ------------------------------------------------------------------

    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">Compare against NYT hint grid</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="score">NYT does not use one fixed dictionary, so their counts and ours '
        "can disagree. Upload a screenshot of their hint page and this reconciles the two "
        "in one pass, or check a single bucket by hand below.</div>",
        unsafe_allow_html=True,
    )

    # ---------------- screenshot upload ----------------

    if not OCR_AVAILABLE:
        st.info(
            "Screenshot reading needs Tesseract. Install it with `brew install tesseract` "
            "(macOS) or `sudo apt install tesseract-ocr` (Linux), then "
            "`pip install pytesseract pillow`. The manual form below works without it."
        )
    else:
        shot = st.file_uploader(
            "Hint page screenshot", type=["png", "jpg", "jpeg"], label_visibility="collapsed"
        )
        if shot is not None and st.button("Read this screenshot", use_container_width=True):
            try:
                parsed = parseHintGrid(shot)
            except Exception as err:
                parsed = None
                st.error(f"Could not read that image: {err}")

            if parsed:
                if len(parsed["letters"]) != 7:
                    st.error(
                        f"Read {len(parsed['letters'])} letters "
                        f"({''.join(sorted(parsed['letters'])).upper()}), expected 7. "
                        "Try a tighter crop or a larger screenshot."
                    )
                elif not parsed["twoLetters"]:
                    st.error("Found no two-letter list in that image.")
                else:
                    st.session_state.parsed = parsed
                    st.session_state.centerRanking = inferCenter(
                        wholeTrie, parsed["letters"], parsed["twoLetters"]
                    )
                    st.rerun()

    parsed = st.session_state.get("parsed")
    if parsed:
        letterText = " ".join(sorted(parsed["letters"])).upper()
        st.markdown(
            f'<div class="score">Read <b>{letterText}</b> &middot; '
            f'{parsed["words"]} words &middot; {parsed["points"]} points &middot; '
            f'{parsed["pangrams"]} pangram(s) &middot; '
            f'{len(parsed["twoLetters"])} two-letter buckets &middot; '
            f'{len(parsed["gridCounts"])} grid cells</div>',
            unsafe_allow_html=True,
        )

        for warning in checkParse(parsed):
            st.warning(warning)

        ranking = st.session_state.get("centerRanking", [])
        if ranking:
            best, bestScore, bestCount = ranking[0]
            runnerUp = ranking[1][1] if len(ranking) > 1 else 0
            scores = {c: s for c, s, _ in ranking}
            st.markdown(
                '<div class="score">The bold centre letter cannot be read by OCR, so it is '
                "inferred: each candidate is solved with the trie and scored against NYT's "
                "two-letter counts.</div>",
                unsafe_allow_html=True,
            )
            centerPick = st.radio(
                "Centre letter",
                [c for c, _, _ in ranking],
                index=0,
                horizontal=True,
                format_func=lambda c: f"{c.upper()} ({scores[c]:.2f})",
                key="center_pick",
            )
            confident = bestScore - runnerUp > 0.1
            st.markdown(
                f'<div class="score" style="color:{MOSS if confident else OCHRE}">'
                f"Best match {best.upper()} at {bestScore:.2f}, next best {runnerUp:.2f}."
                f'{"" if confident else " Close call - check the bold letter yourself."}</div>',
                unsafe_allow_html=True,
            )

            useGrid = st.checkbox(
                "Also use the letter-by-length grid, not just the two-letter list",
                value=True,
                help="Both tallies are held open at once, so a common word the length grid "
                "rules out will not be kept.",
            )

            if st.button("Load this puzzle and reconcile", use_container_width=True):
                solutions = wholeTrie.search(parsed["letters"], centerPick)
                st.session_state.game = startGame(solutions, parsed["letters"], centerPick)
                resetRound()
                st.session_state.gridReport = applyGrid(
                    st.session_state.game,
                    parsed["twoLetters"],
                    parsed["gridCounts"] if useGrid else None,
                )
                st.session_state.gridReport["before"] = len(solutions)
                st.rerun()

    report = st.session_state.get("gridReport")
    if report:
        st.markdown(
            f'<div class="verdict" style="color:{MOSS}">'
            f'Trimmed {report["before"]} candidates down to {len(report["kept"])}, '
            f'against NYT\'s {report["target"]}.</div>',
            unsafe_allow_html=True,
        )
        if report["gaps"]:
            bullets = "".join(f"<li>{line}</li>" for line in readableGaps(report["gaps"]))
            st.markdown(
                '<div class="score" style="margin-top:0.5rem">Answers NYT counted that we do '
                f'not have:<ul style="margin:0.35rem 0 0 1.1rem">{bullets}</ul></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="score">Every bucket filled exactly.</div>', unsafe_allow_html=True
            )
        st.markdown(
            f'<div class="score" style="margin-top:0.5rem">{len(game.filteredOut)} words set '
            "aside as less likely. If one of yours turns out not to count, mark it under "
            "<b>Found</b> and the best set-aside word from that bucket takes its place.</div>",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">Or check one bucket by hand</div>', unsafe_allow_html=True)

    n1, n2, n3, n4 = st.columns([1.2, 1, 1, 1.1])
    nytPrefix = n1.text_input("Prefix", key="cmp_prefix", placeholder="al")
    nytLength = n2.number_input("Length", min_value=0, max_value=15, step=1, key="cmp_len")
    nytCount = n3.number_input("NYT count", min_value=0, max_value=50, step=1, key="cmp_count")
    n4.markdown('<div style="height:1.85rem"></div>', unsafe_allow_html=True)
    if n4.button("Check", use_container_width=True):
        p = nytPrefix.strip().lower()
        if len(p) == 1:
            st.session_state.nyt = game.getPrefixLen(p, int(nytLength), int(nytCount))
        elif len(p) == 2:
            st.session_state.nyt = game.twoLetsGiven(p, int(nytCount))
        else:
            st.session_state.nyt = {
                "status": "error",
                "msg": "Prefix must be 1 or 2 letters.",
                "kept": [],
                "forLater": [],
            }
        st.rerun()

    result = st.session_state.get("nyt")
    if result:
        tone = {"equal": MOSS, "extra": OCHRE, "missing": CLAY, "error": CLAY}[result["status"]]
        st.markdown(f'<div class="verdict" style="color:{tone}">{result["msg"]}</div>', unsafe_allow_html=True)
        if result["kept"]:
            st.markdown(
                '<div class="score">Keeping: ' + ", ".join(result["kept"]) + "</div>",
                unsafe_allow_html=True,
            )
        if result["forLater"]:
            st.markdown(
                '<div class="score">Set aside: ' + ", ".join(result["forLater"]) + "</div>",
                unsafe_allow_html=True,
            )
