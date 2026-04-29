"""
Recall: Spaced Repetition Flashcards
Run with: streamlit run flashcards_app.py
"""

import streamlit as st
import anthropic
import json
import os
import re
import random
import csv
import io
from datetime import datetime, timedelta
from pathlib import Path

# --- Config ---
DATA_FILE = Path("flashcards_data.json")
MODEL = "claude-sonnet-4-6"

# --- Fonts ---
FONTS = {
    "Serif (Georgia)": {"family": "Georgia, 'Times New Roman', serif", "google": None},
    "Serif (Lora)":    {"family": "'Lora', Georgia, serif", "google": "Lora:ital,wght@0,400;0,500;0,600;1,400"},
    "Serif (Crimson)": {"family": "'Crimson Pro', Georgia, serif", "google": "Crimson+Pro:ital,wght@0,400;0,500;0,600;1,400"},
    "Sans (Inter)":    {"family": "'Inter', system-ui, sans-serif", "google": "Inter:wght@400;500;600;700"},
    "System":          {"family": "system-ui, -apple-system, BlinkMacSystemFont, sans-serif", "google": None},
    "Mono (JetBrains)":{"family": "'JetBrains Mono', monospace", "google": "JetBrains+Mono:wght@400;500;600"},
}

# --- Color Palettes ---
PALETTES = {
    "Twilight":  {"bg": "#0e0d0b", "fg": "#f0ebe0", "muted": "#6b6355", "accent": "#c9a84c",
                  "panel": "#1a1814", "border": "#2a2620",
                  "ans_bg": "#1a1f1a", "ans_border": "#2a3a2a", "ans_fg": "#c8e0c8"},
    "Midnight":  {"bg": "#0a0e1a", "fg": "#e0e6f0", "muted": "#5a6478", "accent": "#7a9eff",
                  "panel": "#141828", "border": "#252a40",
                  "ans_bg": "#141e2a", "ans_border": "#253545", "ans_fg": "#c8d8f0"},
    "Forest":    {"bg": "#0d1410", "fg": "#e0ebe0", "muted": "#5a6855", "accent": "#7ac74f",
                  "panel": "#141d18", "border": "#243024",
                  "ans_bg": "#141f1a", "ans_border": "#2a3a2a", "ans_fg": "#c8e0c8"},
    "Slate":     {"bg": "#1a1d24", "fg": "#dde2eb", "muted": "#7a8290", "accent": "#a0b8d8",
                  "panel": "#252a33", "border": "#363b48",
                  "ans_bg": "#252e30", "ans_border": "#3a4548", "ans_fg": "#c8d8d4"},
    "Parchment": {"bg": "#f4ede0", "fg": "#2a2418", "muted": "#8b7d6b", "accent": "#8b5a2b",
                  "panel": "#fbf6ea", "border": "#d8cfb8",
                  "ans_bg": "#eef4e8", "ans_border": "#c0c8a8", "ans_fg": "#2a3818"},
    "Paper":     {"bg": "#ffffff", "fg": "#1a1a1a", "muted": "#777777", "accent": "#2563eb",
                  "panel": "#f7f7f7", "border": "#d0d0d0",
                  "ans_bg": "#f0f7f0", "ans_border": "#c0d0c0", "ans_fg": "#1a3a1a"},
}

DEFAULT_SETTINGS = {"font": "Serif (Georgia)", "palette": "Twilight", "study_profile": ""}

# Confidence button labels and their SM-2 quality scores
CONFIDENCE_LEVELS = [
    ("No Idea",    0, "I had no idea what this was"),
    ("Unfamiliar", 1, "I knew a bit but not really"),
    ("Familiar",   2, "I knew this with some effort"),
    ("Got It",     3, "I knew this immediately"),
]

REQUEUE_THRESHOLD = 3  # cards between re-inserts from the requeue pool


def get_theme_css(font_name, palette_name):
    f = FONTS.get(font_name, FONTS["Serif (Georgia)"])
    p = PALETTES.get(palette_name, PALETTES["Twilight"])
    google = (f"@import url('https://fonts.googleapis.com/css2?family={f['google']}&display=swap');"
              if f["google"] else "")
    return f"""
<style>
{google}

/* Page and top bar */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
[data-testid="stToolbar"], header, .stApp > header {{
    background-color: {p['bg']} !important;
}}
[data-testid="stDecoration"] {{ display: none !important; }}
.main .block-container {{ padding-top: 2rem; max-width: 720px; }}

/* Sidebar */
[data-testid="stSidebar"], [data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {{
    background-color: {p['bg']} !important;
}}

/* Text */
body, .stApp, .stMarkdown,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] strong,
[data-testid="stMarkdownContainer"] em,
[data-testid="stWidgetLabel"] p,
[data-testid="stText"],
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
.stAlert p {{
    color: {p['fg']} !important;
    font-family: {f['family']};
}}
label, [data-testid="stWidgetLabel"] {{
    color: {p['fg']} !important;
    font-family: {f['family']};
}}
h1, h2, h3, h4, h5, h6 {{
    color: {p['fg']} !important;
    font-family: {f['family']};
}}
[data-testid="stCaptionContainer"] p, small {{
    color: {p['muted']} !important;
}}

/* Inputs */
.stTextInput input, .stTextArea textarea,
[data-testid="stNumberInput"] input {{
    background-color: {p['panel']} !important;
    color: {p['fg']} !important;
    border-color: {p['border']} !important;
    font-family: {f['family']};
}}

/* Selectbox: targeted, no wildcard to avoid arrow bug */
[data-testid="stSelectbox"] [data-baseweb="select"] > div:first-child {{
    background-color: {p['panel']} !important;
    border-color: {p['border']} !important;
}}
[data-baseweb="select"] [data-baseweb="value"] span,
[data-baseweb="select"] [data-baseweb="value"] {{
    color: {p['fg']} !important;
}}
[data-baseweb="popover"] [data-baseweb="menu"],
[data-baseweb="menu"] {{
    background-color: {p['panel']} !important;
}}
[data-baseweb="menu"] [role="option"],
[data-baseweb="popover"] li {{
    color: {p['fg']} !important;
    background-color: {p['panel']} !important;
}}

/* Radio buttons */
[data-testid="stRadio"] label,
[data-testid="stRadio"] p {{
    color: {p['fg']} !important;
}}

/* File uploader */
[data-testid="stFileUploaderDropzone"] {{
    background-color: {p['panel']} !important;
    border-color: {p['border']} !important;
}}
[data-testid="stFileUploaderDropzone"] p,
[data-testid="stFileUploaderDropzone"] span,
[data-testid="stFileUploader"] span {{
    color: {p['fg']} !important;
}}

/* Buttons */
.stButton > button {{
    border-radius: 4px;
    font-weight: 500;
    letter-spacing: 0.03em;
    font-family: {f['family']};
}}

/* Metrics */
[data-testid="stMetricValue"] {{ color: {p['accent']} !important; }}
[data-testid="stMetricLabel"] p {{ color: {p['muted']} !important; }}

/* Bordered containers */
[data-testid="stVerticalBlockBorderWrapper"] > div {{
    background-color: {p['panel']} !important;
    border-color: {p['border']} !important;
}}

/* Tabs */
[data-testid="stTabs"] [role="tab"] {{ color: {p['fg']} !important; }}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{ color: {p['accent']} !important; }}

/* Expanders */
[data-testid="stExpander"] {{
    background-color: {p['panel']} !important;
    border-color: {p['border']} !important;
}}
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary {{
    color: {p['fg']} !important;
}}

/* Flashcard panels */
.question-card {{
    background: {p['panel']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 40px 32px;
    margin: 16px 0;
    text-align: center;
    font-size: 1.3rem;
    font-family: {f['family']};
    color: {p['fg']} !important;
    line-height: 1.6;
}}
.answer-card {{
    background: {p['ans_bg']};
    border: 1px solid {p['ans_border']};
    border-radius: 8px;
    padding: 32px;
    margin: 8px 0;
    text-align: center;
    font-size: 1.15rem;
    font-family: {f['family']};
    color: {p['ans_fg']} !important;
    line-height: 1.6;
}}
.card-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    color: {p['muted']} !important;
    text-transform: uppercase;
    text-align: center;
    margin-bottom: 4px;
}}
.requeue-badge {{
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 0.1em;
    color: {p['accent']} !important;
    text-transform: uppercase;
    text-align: center;
    margin-bottom: 4px;
    opacity: 0.8;
}}

/* Confidence button tints — use sibling-marker pattern for reliability.
   We emit a hidden marker <span> right before each rating button; the
   following Streamlit button container is then styled via the sibling
   combinator. This is robust to Streamlit DOM changes. */
.recall-btn-marker {{ display: none; }}
.recall-btn-no-idea + div .stButton > button,
.recall-btn-no-idea + .stButton > button,
.recall-btn-no-idea ~ div [data-testid="stButton"] > button {{
    background-color: rgba(220, 70, 70, 0.18) !important;
    border: 1px solid rgba(220, 70, 70, 0.5) !important;
    color: {p['fg']} !important;
}}
.recall-btn-no-idea + div .stButton > button:hover,
.recall-btn-no-idea + .stButton > button:hover {{
    background-color: rgba(220, 70, 70, 0.28) !important;
    border-color: rgba(220, 70, 70, 0.7) !important;
}}
.recall-btn-got-it + div .stButton > button,
.recall-btn-got-it + .stButton > button,
.recall-btn-got-it ~ div [data-testid="stButton"] > button {{
    background-color: rgba(70, 130, 220, 0.18) !important;
    border: 1px solid rgba(70, 130, 220, 0.5) !important;
    color: {p['fg']} !important;
}}
.recall-btn-got-it + div .stButton > button:hover,
.recall-btn-got-it + .stButton > button:hover {{
    background-color: rgba(70, 130, 220, 0.28) !important;
    border-color: rgba(70, 130, 220, 0.7) !important;
}}

/* Multi-segment progress bar */
.recall-progress-wrap {{
    width: 100%;
    margin: 8px 0 4px 0;
}}
.recall-progress-bar {{
    display: flex;
    width: 100%;
    height: 8px;
    background: {p['panel']};
    border: 1px solid {p['border']};
    border-radius: 4px;
    overflow: hidden;
}}
.recall-progress-bar > span {{
    display: block;
    height: 100%;
    transition: width 0.3s ease;
}}
.recall-progress-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    color: {p['muted']} !important;
    margin-top: 6px;
    text-transform: uppercase;
}}
</style>
"""


# --- SM-2 ---
def sm2(card, quality):
    interval, reps, ef = card["interval"], card["repetitions"], card["ease_factor"]
    if quality == 0:
        reps, interval = 0, 1
    else:
        ef = max(1.3, ef + (0.1 - (3 - quality) * (0.08 + (3 - quality) * 0.02)))
        if reps == 0:   interval = 1
        elif reps == 1: interval = 6
        else:           interval = round(interval * ef)
        if quality == 1: interval = max(1, round(interval * 0.8))
        if quality == 3: interval = round(interval * 1.3)
        reps += 1
    return {"interval": interval, "repetitions": reps, "ease_factor": ef,
            "due_date": (datetime.now() + timedelta(days=interval)).isoformat()}


def is_due(card):
    return datetime.fromisoformat(card["due_date"]) <= datetime.now()


def make_card(front, back, card_id):
    return {"id": card_id, "front": front, "back": back, "interval": 0,
            "repetitions": 0, "ease_factor": 2.5,
            "due_date": datetime.now().isoformat()}


# --- Persistence ---
def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE) as f:
                data = json.load(f)
            if "settings" not in data:
                data["settings"] = DEFAULT_SETTINGS.copy()
            else:
                for k, v in DEFAULT_SETTINGS.items():
                    if k not in data["settings"]:
                        data["settings"][k] = v
            return data
        except Exception:
            pass
    return {"cards": [], "decks": [], "settings": DEFAULT_SETTINGS.copy()}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def delete_deck(deck_id):
    data = st.session_state.data
    deck = next((d for d in data["decks"] if d["id"] == deck_id), None)
    if deck:
        ids = set(deck["cardIds"])
        data["cards"] = [c for c in data["cards"] if c["id"] not in ids]
        data["decks"] = [d for d in data["decks"] if d["id"] != deck_id]
    save_data(data)


def delete_card_from_deck(card_id, deck_id):
    data = st.session_state.data
    data["cards"] = [c for c in data["cards"] if c["id"] != card_id]
    for deck in data["decks"]:
        if deck["id"] == deck_id:
            deck["cardIds"] = [cid for cid in deck["cardIds"] if cid != card_id]
    save_data(data)


# --- Study session helpers ---
def start_study(card_pool, do_shuffle, reversed_mode):
    """Initialize all study session state."""
    queue = list(card_pool)
    if do_shuffle:
        random.shuffle(queue)
    st.session_state.study_queue        = queue
    st.session_state.study_idx          = 0
    st.session_state.revealed           = False
    st.session_state.show_front         = not reversed_mode
    st.session_state.study_reversed     = reversed_mode
    st.session_state.requeue_pool       = []   # list of card IDs to repeat
    st.session_state.cards_since_requeue = 0
    st.session_state.view               = "study"
    st.session_state.flipped            = False  # kept for compat
    st.session_state.session_ratings    = {}     # card_id -> latest quality
    # Track distinct cards in this session for progress denominator.
    # Requeued cards don't inflate the total — we track unique IDs only.
    st.session_state.session_card_ids   = {c["id"] for c in queue}


def handle_rating(quality, card):
    """Apply SM-2, update requeue pool, possibly insert a requeue card, advance."""
    # Track this rating for the live progress bar (latest rating wins on requeues)
    st.session_state.session_ratings[card["id"]] = quality

    # Save SM-2 update
    updates = sm2(card, quality)
    for c in st.session_state.data["cards"]:
        if c["id"] == card["id"]:
            c.update(updates)
            break
    save_data(st.session_state.data)

    pool = st.session_state.requeue_pool
    card_id = card["id"]

    # Update requeue pool
    if quality <= 1:
        if card_id not in pool:
            pool.append(card_id)
    else:
        if card_id in pool:
            pool.remove(card_id)

    st.session_state.cards_since_requeue += 1
    idx   = st.session_state.study_idx
    queue = st.session_state.study_queue

    # Maybe insert a requeue card
    if st.session_state.cards_since_requeue >= REQUEUE_THRESHOLD and pool:
        candidates = [cid for cid in pool if cid != card_id]
        if not candidates:
            candidates = list(pool)
        if candidates:
            pick_id = random.choice(candidates)
            pick_card = next((c for c in st.session_state.data["cards"]
                              if c["id"] == pick_id), None)
            if pick_card:
                insert_at = min(idx + 2, len(queue))
                queue.insert(insert_at, pick_card)
                pool.remove(pick_id)
                st.session_state.cards_since_requeue = 0

    # Reset card display state
    st.session_state.revealed   = False
    st.session_state.show_front = not st.session_state.study_reversed

    # Advance
    next_idx = idx + 1
    if next_idx >= len(queue):
        # If pool still has cards, append them all and keep going
        if pool:
            for cid in list(pool):
                c = next((c for c in st.session_state.data["cards"]
                           if c["id"] == cid), None)
                if c:
                    queue.append(c)
            pool.clear()
            st.session_state.study_idx = next_idx
        else:
            st.session_state.view = "done"
    else:
        st.session_state.study_idx = next_idx


# --- CSV parsing ---
def parse_csv(file_bytes):
    text = file_bytes.decode("utf-8-sig", errors="ignore")
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ","
    try:
        has_header = csv.Sniffer().has_header(sample)
    except Exception:
        has_header = False
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delimiter)
            if any(cell.strip() for cell in r)]
    if not rows:
        raise ValueError("CSV is empty")
    if has_header and len(rows) > 1:
        first = [c.strip().lower() for c in rows[0]]
        if any(w in first for w in {"front","back","question","answer","term","definition","q","a"}):
            rows = rows[1:]
    pairs = [(r[0].strip(), r[1].strip()) for r in rows
             if len(r) >= 2 and r[0].strip() and r[1].strip()]
    if not pairs:
        raise ValueError("No valid rows found. Each row needs two non-empty columns.")
    return pairs


# --- Prompt + API ---
def build_prompt(study_profile, custom, card_count):
    parts = [
        "You are generating flashcards for spaced repetition study. Each card must be "
        "self-contained and precise.",
        "QUALITY CRITERIA:\n"
        "- Questions must require actual knowledge to answer.\n"
        "- Prefer mechanisms, comparisons, cause-and-effect over surface recall.\n"
        "- Keep answers under 40 words, precise and self-contained.\n"
        "- Vary types: definitions, mechanisms, examples, fill-in-the-blank, application.\n"
        "- No two cards testing the same fact.",
    ]
    if study_profile and study_profile.strip():
        parts.append(f"USER PROFILE:\n{study_profile.strip()}")
    if custom and custom.strip():
        parts.append(f"INSTRUCTIONS FOR THIS DECK:\n{custom.strip()}")
    parts.append(
        f"Generate as close to {card_count} flashcards as the content supports, "
        f"up to {card_count + 10} if dense enough.\n\n"
        "Return ONLY raw JSON, no markdown fences. Shape:\n"
        '{"deckName":"short title","cards":[{"front":"question","back":"answer"}]}'
    )
    return "\n\n".join(parts)


def generate_from_text(api_key, text, profile, custom, card_count):
    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"=== Notes ===\n{text.strip()}\n\n{build_prompt(profile, custom, card_count)}"
    msg = client.messages.create(model=MODEL, max_tokens=max(4000, card_count * 120),
                                 messages=[{"role": "user", "content": prompt}])
    raw = "".join(b.text for b in msg.content if hasattr(b, "text"))
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError(f"No JSON in response: {raw[:200]}")
    parsed = json.loads(match.group(0))
    if "cards" not in parsed:
        raise ValueError("Response missing 'cards' array")
    return parsed


# ============================================================
# Streamlit UI
# ============================================================
st.set_page_config(page_title="Recall", layout="centered", initial_sidebar_state="expanded")

_state_defaults = {
    "data": None, "view": "home",
    "study_queue": [], "study_idx": 0,
    "revealed": False, "show_front": True,
    "study_reversed": False, "flipped": False,
    "requeue_pool": [], "cards_since_requeue": 0,
    "current_deck_id": None, "confirm_delete_deck": None,
    "session_ratings": {},  # card_id -> latest quality (0..3) for this session
}
for k, v in _state_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = load_data() if k == "data" else v

settings = st.session_state.data.get("settings", DEFAULT_SETTINGS)
st.markdown(get_theme_css(settings["font"], settings["palette"]), unsafe_allow_html=True)

data      = st.session_state.data
cards     = data["cards"]
decks     = data["decks"]
due_count = sum(1 for c in cards if is_due(c))

# ---- Sidebar ----
with st.sidebar:
    st.markdown("## Recall")
    st.caption("SPACED REPETITION FLASHCARDS")
    st.markdown("---")
    api_key = st.text_input("Anthropic API Key", type="password",
                            value=os.getenv("ANTHROPIC_API_KEY", ""),
                            help="Get one at console.anthropic.com")
    st.caption("Only needed for paste-notes generation.")
    st.markdown("---")
    c1, c2 = st.columns(2)
    c1.metric("Cards", len(cards))
    c2.metric("Due", due_count)
    st.metric("Decks", len(decks))
    st.markdown("---")

    if st.button("Home", use_container_width=True):
        st.session_state.view = "home"
        st.session_state.current_deck_id = None
        st.rerun()

    with st.expander("Study profile"):
        st.caption("Applied to every paste-notes generation automatically.")
        cur_profile = data["settings"].get("study_profile", "")
        new_profile = st.text_area("Profile", value=cur_profile, height=160,
                                   placeholder="e.g. AP Environmental Science student. "
                                               "Prefer mechanisms over vocab.",
                                   label_visibility="collapsed", key="profile_input")
        if st.button("Save profile", use_container_width=True, key="save_profile"):
            data["settings"]["study_profile"] = new_profile
            save_data(data)
            st.success("Saved")

    with st.expander("Appearance"):
        cur_font = data["settings"].get("font", "Serif (Georgia)")
        cur_pal  = data["settings"].get("palette", "Twilight")
        fk = list(FONTS.keys())
        pk = list(PALETTES.keys())
        nf  = st.selectbox("Font", fk, index=fk.index(cur_font) if cur_font in fk else 0)
        np_ = st.selectbox("Color theme", pk, index=pk.index(cur_pal) if cur_pal in pk else 0)
        if nf != cur_font or np_ != cur_pal:
            data["settings"]["font"] = nf
            data["settings"]["palette"] = np_
            save_data(data)
            st.rerun()

    with st.expander("Danger zone"):
        if st.button("Clear all data", use_container_width=True):
            preserved = data.get("settings", DEFAULT_SETTINGS.copy())
            st.session_state.data = {"cards": [], "decks": [], "settings": preserved}
            save_data(st.session_state.data)
            st.session_state.view = "home"
            st.session_state.current_deck_id = None
            st.rerun()


# ============================================================
# Study View
# ============================================================
if st.session_state.view == "study" and st.session_state.study_queue:
    queue = st.session_state.study_queue
    idx   = st.session_state.study_idx
    card  = queue[idx]

    # Multi-segment progress bar broken down by confidence rating.
    # Total denominator = unique cards in the session (requeues don't inflate).
    total_cards = len(st.session_state.get("session_card_ids", set())) or len(queue)
    ratings = st.session_state.session_ratings  # card_id -> quality (0..3)

    # Count cards at each confidence level
    counts = {0: 0, 1: 0, 2: 0, 3: 0}
    for q in ratings.values():
        if q in counts:
            counts[q] += 1
    rated_total = sum(counts.values())
    unrated = max(0, total_cards - rated_total)

    # Colors per quality level (matches button tints + a graded scale in between)
    seg_colors = {
        0: "rgba(220, 70, 70, 0.85)",    # No Idea — red
        1: "rgba(230, 150, 70, 0.85)",   # Unfamiliar — orange
        2: "rgba(180, 180, 90, 0.85)",   # Familiar — yellow-green
        3: "rgba(70, 130, 220, 0.85)",   # Got It — blue
    }

    # Build segments in order: 0, 1, 2, 3, then unrated remainder (transparent)
    segments_html = ""
    for q in (0, 1, 2, 3):
        pct = (counts[q] / total_cards * 100) if total_cards else 0
        if pct > 0:
            segments_html += f'<span style="width:{pct:.4f}%;background:{seg_colors[q]};"></span>'

    pool_size = len(st.session_state.requeue_pool)
    label = f"Card {idx + 1} of {len(queue)}"
    if pool_size > 0:
        label += f"  ·  {pool_size} to revisit"

    st.markdown(
        f'<div class="recall-progress-wrap">'
        f'<div class="recall-progress-bar">{segments_html}</div>'
        f'<div class="recall-progress-label">{label}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Determine what to show based on show_front + study direction
    reversed_mode = st.session_state.study_reversed
    show_front    = st.session_state.show_front

    if show_front:
        visible_text    = card["front"]
        visible_label   = "Term"
        hidden_text     = card["back"]
        hidden_label    = "Definition"
    else:
        visible_text    = card["back"]
        visible_label   = "Definition"
        hidden_text     = card["front"]
        hidden_label    = "Term"

    # Badge if this is a requeue card (it came back from the pool)
    # We detect this by checking the card's ID is not in the original
    # queue position. Simpler: just show badge if it was requeued
    # (we track by checking if it appeared more than once in queue up to idx)
    ids_so_far = [queue[i]["id"] for i in range(idx)]
    is_requeued = ids_so_far.count(card["id"]) > 0
    if is_requeued:
        st.markdown('<div class="requeue-badge">↩ Revisiting</div>', unsafe_allow_html=True)

    if not st.session_state.revealed:
        # Pre-reveal: show the prompt side only
        st.markdown(f'<div class="card-label">{visible_label}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="question-card">{visible_text}</div>', unsafe_allow_html=True)

        if st.button("Reveal", use_container_width=True, type="primary"):
            st.session_state.revealed   = True
            st.session_state.show_front = not show_front  # flip to other side on reveal
            st.rerun()
    else:
        # Post-reveal: show only the currently-facing side as the answer panel
        cur_show_front = st.session_state.show_front
        if cur_show_front:
            revealed_text  = card["front"]
            revealed_label = "Term"
        else:
            revealed_text  = card["back"]
            revealed_label = "Definition"

        st.markdown(f'<div class="card-label">{revealed_label}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="answer-card">{revealed_text}</div>', unsafe_allow_html=True)

        # Flip toggle button
        flip_col, _ = st.columns([1, 3])
        with flip_col:
            if st.button("↩ Flip card", key="flip_btn", use_container_width=True):
                st.session_state.show_front = not st.session_state.show_front
                st.rerun()

        # Confidence buttons. We emit a hidden marker span before "No Idea"
        # and "Got It" so the CSS sibling selectors can tint just those two.
        st.markdown("**How well did you know this?**")
        cols = st.columns(4)
        marker_classes = {
            0: "recall-btn-no-idea",
            3: "recall-btn-got-it",
        }
        for col, (label, quality, tip) in zip(cols, CONFIDENCE_LEVELS):
            with col:
                if quality in marker_classes:
                    st.markdown(
                        f'<span class="recall-btn-marker {marker_classes[quality]}"></span>',
                        unsafe_allow_html=True,
                    )
                if st.button(label, use_container_width=True, key=f"conf_{quality}",
                             help=tip):
                    handle_rating(quality, card)
                    st.rerun()

    st.markdown("---")
    if st.button("End session", key="end_study"):
        st.session_state.view = "home"
        st.session_state.revealed = False
        st.rerun()


# ============================================================
# Done View
# ============================================================
elif st.session_state.view == "done":
    st.title("Session complete")
    st.caption("All cards reviewed, including any revisits. Come back tomorrow.")
    if st.button("Back to home", type="primary"):
        st.session_state.view = "home"
        st.rerun()


# ============================================================
# Deck View (edit)
# ============================================================
elif st.session_state.view == "deck" and st.session_state.current_deck_id:
    deck_id    = st.session_state.current_deck_id
    deck       = next((d for d in data["decks"] if d["id"] == deck_id), None)

    if deck is None:
        st.warning("Deck not found.")
        if st.button("Back to home"):
            st.session_state.view = "home"
            st.rerun()
    else:
        deck_cards = [c for c in data["cards"] if c["id"] in deck["cardIds"]]
        col_back, col_title = st.columns([1, 5])
        if col_back.button("← Back"):
            st.session_state.view = "home"
            st.session_state.current_deck_id = None
            st.rerun()
        col_title.markdown(f"## {deck['name']}")
        st.caption(f"{len(deck_cards)} cards  ·  created {deck['createdAt'][:10]}")
        st.markdown("---")

        if not deck_cards:
            st.info("This deck has no cards left.")
        else:
            st.caption("Click ✕ on any card to remove it permanently.")
            for card in deck_cards:
                with st.container(border=True):
                    col_text, col_del = st.columns([6, 1])
                    with col_text:
                        st.markdown(f"**{card['front']}**")
                        st.caption(card["back"])
                    with col_del:
                        if st.button("✕", key=f"del_card_{card['id']}", help="Remove this card"):
                            delete_card_from_deck(card["id"], deck_id)
                            st.rerun()


# ============================================================
# Home View
# ============================================================
else:
    st.title("Recall")
    st.caption("Generate cards from notes, or import a CSV directly")

    tab_paste, tab_csv = st.tabs(["Paste Notes (AI)", "Import CSV (free)"])

    with tab_paste:
        st.caption("Paste any notes. Claude will generate flashcards.")
        notes = st.text_area("Notes", height=240,
                             placeholder="Paste any text content here...",
                             label_visibility="collapsed")
        col_n, _ = st.columns([1, 2])
        with col_n:
            card_count = st.number_input("Target cards", min_value=5, max_value=100,
                                         value=25, step=5)
        with st.expander("Custom instructions (optional)"):
            st.caption("One-off context for this generation only.")
            custom = st.text_area("Instructions", height=90,
                                  placeholder="e.g. Focus on chapter 3 only",
                                  label_visibility="collapsed", key="custom_instr")

        if st.button("Generate from Notes", type="primary",
                     use_container_width=True, key="gen_notes"):
            if not api_key:
                st.error("Enter your Anthropic API key in the sidebar")
            elif not notes.strip():
                st.error("Paste some notes first")
            else:
                with st.spinner("Claude is generating flashcards..."):
                    try:
                        profile = data["settings"].get("study_profile", "")
                        parsed  = generate_from_text(api_key, notes, profile,
                                                     custom or "", card_count)
                        deck_id   = str(int(datetime.now().timestamp() * 1000))
                        new_cards = [make_card(c["front"], c["back"], f"{deck_id}_{i}")
                                     for i, c in enumerate(parsed["cards"])]
                        new_deck  = {"id": deck_id,
                                     "name": parsed.get("deckName", "Untitled Deck"),
                                     "cardIds": [c["id"] for c in new_cards],
                                     "createdAt": datetime.now().isoformat()}
                        data["cards"].extend(new_cards)
                        data["decks"].append(new_deck)
                        save_data(data)
                        st.success(f"Created {len(new_cards)} cards in '{new_deck['name']}'")
                        st.rerun()
                    except anthropic.APIStatusError as e:
                        st.error(f"API error ({e.status_code}): {e.message}")
                    except Exception as e:
                        st.error(f"Generation failed: {e}")

    with tab_csv:
        st.caption("Upload a CSV: two columns, front and back. Header auto-detected. Free.")
        deck_name_input = st.text_input("Deck name",
                                        placeholder="e.g. Bio Chapter 5 Vocab",
                                        key="csv_deck_name")
        csv_file = st.file_uploader("Upload CSV", type=["csv"],
                                    accept_multiple_files=False,
                                    label_visibility="collapsed", key="csv_uploader")
        if csv_file:
            try:
                pairs = parse_csv(csv_file.getvalue())
                st.success(f"Parsed {len(pairs)} cards from {csv_file.name}")
                with st.expander(f"Preview (first 5 of {len(pairs)})", expanded=True):
                    for front, back in pairs[:5]:
                        st.markdown(f"**Q:** {front}  \n**A:** {back}")
                        st.markdown("---")
                    if len(pairs) > 5:
                        st.caption(f"... and {len(pairs) - 5} more")
                if st.button("Import these cards", type="primary",
                             use_container_width=True, key="import_csv"):
                    name    = deck_name_input.strip() or csv_file.name.rsplit(".", 1)[0]
                    deck_id = str(int(datetime.now().timestamp() * 1000))
                    new_cards = [make_card(f, b, f"{deck_id}_{i}")
                                 for i, (f, b) in enumerate(pairs)]
                    new_deck  = {"id": deck_id, "name": name,
                                 "cardIds": [c["id"] for c in new_cards],
                                 "createdAt": datetime.now().isoformat()}
                    data["cards"].extend(new_cards)
                    data["decks"].append(new_deck)
                    save_data(data)
                    st.success(f"Imported {len(new_cards)} cards into '{name}'")
                    st.rerun()
            except Exception as e:
                st.error(f"Could not parse CSV: {e}")

    cards     = data["cards"]
    decks     = data["decks"]
    due_count = sum(1 for c in cards if is_due(c))

    if decks:
        st.markdown("---")

        # Study options: direction and shuffle
        st.markdown("**Study options**")
        opt_col1, opt_col2 = st.columns(2)
        with opt_col1:
            direction = st.radio("Direction", ["Term → Definition", "Definition → Term"],
                                 horizontal=True, key="study_direction")
        with opt_col2:
            do_shuffle = st.checkbox("Shuffle cards", value=True, key="study_shuffle")

        reversed_mode = (direction == "Definition → Term")

        if due_count > 0:
            if st.button(f"Study All Due ({due_count} cards)",
                         use_container_width=True, type="primary"):
                due_cards = [c for c in cards if is_due(c)]
                start_study(due_cards, do_shuffle, reversed_mode)
                st.rerun()
        else:
            st.info("No cards due today. Come back tomorrow.")

        st.markdown("### Your Decks")
        for deck in decks:
            deck_cards = [c for c in cards if c["id"] in deck["cardIds"]]
            deck_due   = sum(1 for c in deck_cards if is_due(c))

            with st.container(border=True):
                col_info, col_study, col_edit, col_del = st.columns([4, 1.2, 1.2, 1.2])
                col_info.markdown(f"**{deck['name']}**")
                col_info.caption(
                    f"{len(deck_cards)} cards"
                    + (f"  ·  {deck_due} due" if deck_due > 0 else "  ·  up to date")
                )

                if deck_due > 0:
                    if col_study.button("Study", key=f"s_{deck['id']}",
                                        use_container_width=True):
                        due_cards = [c for c in deck_cards if is_due(c)]
                        start_study(due_cards, do_shuffle, reversed_mode)
                        st.rerun()

                if col_edit.button("Edit", key=f"e_{deck['id']}",
                                   use_container_width=True):
                    st.session_state.current_deck_id = deck["id"]
                    st.session_state.view = "deck"
                    st.rerun()

                if st.session_state.confirm_delete_deck == deck["id"]:
                    if col_del.button("Sure?", key=f"dc_{deck['id']}",
                                      use_container_width=True, type="primary"):
                        delete_deck(deck["id"])
                        st.session_state.confirm_delete_deck = None
                        st.rerun()
                else:
                    if col_del.button("Delete", key=f"d_{deck['id']}",
                                      use_container_width=True):
                        st.session_state.confirm_delete_deck = deck["id"]
                        st.rerun()
    else:
        st.markdown("---")
        st.caption("No decks yet. Generate one above.")
