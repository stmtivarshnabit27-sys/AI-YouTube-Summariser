import os
import re
from io import BytesIO
from datetime import datetime, timezone

import requests
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth as admin_auth
from dotenv import load_dotenv
from google import genai
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.units import inch
from xml.sax.saxutils import escape
from youtube_transcript_api import YouTubeTranscriptApi


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

load_dotenv()

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
FIREBASE_AUTH_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:"
)
FIRESTORE_COLLECTION = "summaries"

st.set_page_config(
    page_title="AI YouTube Video Summariser",
    page_icon="🎬",
    layout="centered",
)


# --------------------------------------------------
# MODERN FRONTEND STYLING
# --------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');

    :root {
        --ink: #172033;
        --muted: #64748b;
        --violet: #7557ff;
        --pink: #ff5ea8;
        --cyan: #38d9d6;
        --glass: rgba(255, 255, 255, 0.78);
    }

    .stApp {
        background:
            radial-gradient(ellipse at 8% 5%, rgba(117,87,255,.17), transparent 34%),
            radial-gradient(ellipse at 92% 14%, rgba(255,94,168,.14), transparent 32%),
            radial-gradient(ellipse at 70% 95%, rgba(56,217,214,.13), transparent 35%),
            linear-gradient(135deg, #f8f9ff 0%, #f7f5ff 48%, #f2fbff 100%);
        color: var(--ink);
        font-family: 'DM Sans', sans-serif;
    }

    [data-testid="stHeader"] {
        background: rgba(255,255,255,.45);
        backdrop-filter: blur(14px);
    }

    .block-container {
        max-width: 1080px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    h1, h2, h3 {
        font-family: 'Space Grotesk', sans-serif !important;
        color: #1d2440;
        letter-spacing: -0.035em;
    }

    h1 {
        font-size: clamp(2.2rem, 5vw, 3.7rem) !important;
        line-height: 1.05 !important;
        font-weight: 700 !important;
    }

    [data-testid="stCaptionContainer"] p,
    .stMarkdown p {
        color: #526078;
    }

    [data-testid="stForm"],
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stExpander"] {
        border: 1px solid rgba(125, 139, 180, .20) !important;
        border-radius: 22px !important;
        background: var(--glass);
        box-shadow: 0 14px 42px rgba(42, 48, 94, .06);
        backdrop-filter: blur(14px);
    }

    [data-testid="stForm"] {
        padding: 1.25rem 1.35rem;
    }

    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea {
        border: 1px solid #e0e5f2 !important;
        border-radius: 13px !important;
        background: rgba(255,255,255,.92) !important;
        color: #1d2440 !important;
        transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease;
    }

    [data-testid="stTextInput"] input:focus,
    [data-testid="stTextArea"] textarea:focus {
        border-color: #8a73ff !important;
        box-shadow: 0 0 0 4px rgba(117,87,255,.13) !important;
    }

    [data-testid="stBaseButton-primary"],
    [data-testid="stFormSubmitButton"] button {
        border: 0 !important;
        border-radius: 14px !important;
        background: linear-gradient(100deg, #7557ff, #a05bff 52%, #ff5ea8) !important;
        color: white !important;
        font-weight: 700 !important;
        box-shadow: 0 9px 22px rgba(117,87,255,.22);
        transition: transform .18s ease, box-shadow .18s ease, filter .18s ease;
    }

    [data-testid="stBaseButton-primary"]:hover,
    [data-testid="stFormSubmitButton"] button:hover {
        transform: translateY(-2px);
        box-shadow: 0 13px 28px rgba(117,87,255,.30);
        filter: saturate(1.12);
    }

    [data-testid="stBaseButton-secondary"],
    [data-testid="stDownloadButton"] button {
        border-radius: 13px !important;
        border: 1px solid #dcdff4 !important;
        background: rgba(255,255,255,.88) !important;
        color: #4b3bb4 !important;
        font-weight: 700 !important;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(245,243,255,.97), rgba(239,249,255,.97));
        border-right: 1px solid rgba(125,139,180,.16);
    }

    [data-testid="stAlert"] {
        border-radius: 14px;
    }

    [data-testid="stProgressBar"] > div > div > div > div {
        background: linear-gradient(90deg, #7557ff, #ff5ea8, #38d9d6);
    }

    .hero-panel {
        position: relative;
        overflow: hidden;
        padding: 2.1rem 2rem;
        margin: .4rem 0 1.5rem 0;
        border-radius: 28px;
        color: white;
        background: linear-gradient(115deg, #29245d 0%, #5943c7 48%, #b54c9c 100%);
        box-shadow: 0 20px 50px rgba(74, 55, 164, .22);
    }

    .hero-panel:before {
        content: "";
        position: absolute;
        width: 250px;
        height: 250px;
        right: -45px;
        top: -105px;
        border-radius: 50%;
        background: rgba(255,255,255,.13);
        animation: floatGlow 7s ease-in-out infinite;
    }

    .hero-panel:after {
        content: "";
        position: absolute;
        width: 160px;
        height: 160px;
        right: 125px;
        bottom: -110px;
        border-radius: 50%;
        background: rgba(56,217,214,.22);
        animation: floatGlow 9s ease-in-out infinite reverse;
    }

    .hero-kicker {
        position: relative;
        z-index: 1;
        display: inline-block;
        padding: .35rem .75rem;
        margin-bottom: .8rem;
        border: 1px solid rgba(255,255,255,.28);
        border-radius: 999px;
        background: rgba(255,255,255,.12);
        color: #fff;
        font-size: .78rem;
        font-weight: 700;
        letter-spacing: .08em;
        text-transform: uppercase;
    }

    .hero-title {
        position: relative;
        z-index: 1;
        margin: 0 0 .65rem 0;
        color: #fff !important;
        font-family: 'Space Grotesk', sans-serif;
        font-size: clamp(2rem, 4.5vw, 3.2rem);
        line-height: 1.06;
        font-weight: 700;
        letter-spacing: -.045em;
    }

    .hero-copy {
        position: relative;
        z-index: 1;
        max-width: 650px;
        margin: 0;
        color: rgba(255,255,255,.86) !important;
        font-size: 1.02rem;
        line-height: 1.7;
    }

    .feature-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
        margin: 0 0 1.5rem 0;
    }

    .feature-card {
        padding: 1rem 1.05rem;
        border: 1px solid rgba(125,139,180,.20);
        border-radius: 18px;
        background: rgba(255,255,255,.72);
        box-shadow: 0 8px 26px rgba(42,48,94,.04);
        transition: transform .2s ease, box-shadow .2s ease;
    }

    .feature-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 15px 30px rgba(42,48,94,.09);
    }

    .feature-icon {
        font-size: 1.45rem;
        margin-bottom: .45rem;
    }

    .feature-title {
        color: #24264a;
        font-weight: 800;
        margin-bottom: .2rem;
    }

    .feature-copy {
        color: #68738b;
        font-size: .86rem;
        line-height: 1.45;
    }

    .section-chip {
        display: inline-block;
        padding: .35rem .7rem;
        margin-bottom: .5rem;
        border-radius: 999px;
        background: #ece8ff;
        color: #5a43c6;
        font-size: .78rem;
        font-weight: 800;
        letter-spacing: .04em;
    }

    @keyframes floatGlow {
        0%, 100% { transform: translateY(0) scale(1); }
        50% { transform: translateY(14px) scale(1.06); }
    }

    @media (max-width: 700px) {
        .block-container { padding: 1rem 1rem 2rem 1rem; }
        .hero-panel { padding: 1.5rem 1.25rem; border-radius: 22px; }
        .feature-grid { grid-template-columns: 1fr; }
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { animation: none !important; transition: none !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# FIREBASE INITIALIZATION
# --------------------------------------------------

def initialize_firestore():
    """Initialize Firebase Admin SDK and return Firestore client."""
    service_path = os.getenv(
        "FIREBASE_SERVICE_ACCOUNT_PATH",
        "firebase-service-account.json",
    ).strip()

    if not os.path.isabs(service_path):
        service_path = os.path.join(os.path.dirname(__file__), service_path)

    if not os.path.isfile(service_path):
        raise FileNotFoundError(
            "Firebase service-account JSON was not found. Check "
            "FIREBASE_SERVICE_ACCOUNT_PATH in your .env file."
        )

    if not firebase_admin._apps:
        credential = credentials.Certificate(service_path)
        firebase_admin.initialize_app(credential)

    return firestore.client()


@st.cache_resource(show_spinner=False)
def get_firestore():
    return initialize_firestore()


def firebase_auth(action, email, password, api_key):
    """Create an account or sign in using Firebase Authentication REST API."""
    if not api_key:
        raise ValueError(
            "FIREBASE_WEB_API_KEY is missing from your .env file."
        )

    endpoint_action = "signUp" if action == "signup" else "signInWithPassword"
    url = f"{FIREBASE_AUTH_URL}{endpoint_action}?key={api_key}"

    response = requests.post(
        url,
        json={
            "email": email.strip(),
            "password": password,
            "returnSecureToken": True,
        },
        timeout=20,
    )

    try:
        data = response.json()
    except ValueError:
        data = {}

    if response.status_code != 200:
        error_code = data.get("error", {}).get("message", "AUTHENTICATION_FAILED")
        friendly_messages = {
            "EMAIL_EXISTS": "This email already has an account. Please sign in.",
            "OPERATION_NOT_ALLOWED": "Email/Password sign-in is not enabled in Firebase Authentication.",
            "WEAK_PASSWORD : Password should be at least 6 characters":
                "Choose a password with at least 6 characters.",
            "INVALID_EMAIL": "Enter a valid email address.",
            "EMAIL_NOT_FOUND": "No account was found for this email. Please sign up.",
            "INVALID_PASSWORD": "Incorrect email or password.",
            "INVALID_LOGIN_CREDENTIALS": "Incorrect email or password.",
            "USER_DISABLED": "This account has been disabled.",
            "TOO_MANY_ATTEMPTS_TRY_LATER":
                "Too many attempts. Please wait and try again later.",
            "API_KEY_INVALID": "The Firebase Web API key is invalid. Check .env.",
        }
        message = friendly_messages.get(error_code, error_code.replace("_", " ").title())
        raise ValueError(message)

    return {
        "uid": data["localId"],
        "email": data.get("email", email.strip()),
        "id_token": data["idToken"],
    }


def verify_firebase_token(id_token):
    """Verify Firebase ID token with a small clock-skew allowance."""
    decoded = admin_auth.verify_id_token(
        id_token,
        clock_skew_seconds=10
    )
    return decoded["uid"]


def save_summary(db, uid, record):
    """Save one summary under the authenticated user's own document path."""
    doc_ref = (
        db.collection("users")
        .document(uid)
        .collection(FIRESTORE_COLLECTION)
        .document()
    )
    doc_ref.set(record)
    return doc_ref.id


def get_user_summaries(db, uid, limit=20):
    """Fetch only summaries belonging to the signed-in user's UID."""
    docs = (
        db.collection("users")
        .document(uid)
        .collection(FIRESTORE_COLLECTION)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


# --------------------------------------------------
# YOUTUBE HELPERS
# --------------------------------------------------

def get_video_id(url):
    """Extract a YouTube video ID from common YouTube URL formats."""
    url = url.strip()
    patterns = [
        r"(?:youtube\.com/watch\?.*?v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})",
        r"(?:youtube\.com/live/)([A-Za-z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url

    raise ValueError("Invalid YouTube URL. Please paste a valid YouTube video link.")


def fetch_transcript(video_id):
    """Fetch the most appropriate accessible caption track."""
    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)
    available = list(transcript_list)

    if not available:
        raise ValueError("No accessible captions were found for this video.")

    selected = None
    for transcript in available:
        if transcript.language_code == "en" and not transcript.is_generated:
            selected = transcript
            break

    if selected is None:
        for transcript in available:
            if transcript.language_code == "en":
                selected = transcript
                break

    if selected is None:
        for transcript in available:
            if not transcript.is_generated:
                selected = transcript
                break

    if selected is None:
        selected = available[0]

    fetched = selected.fetch()
    transcript_text = " ".join(
        snippet.text for snippet in fetched
    ).strip()

    if not transcript_text:
        raise ValueError("The caption track was empty.")

    return transcript_text, selected.language, selected.language_code


def split_text(text, max_chars=12000):
    """Split long transcripts into smaller sections."""
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0

    for word in words:
        word_length = len(word) + 1
        if current_chunk and current_length + word_length > max_chars:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_length = 0
        current_chunk.append(word)
        current_length += word_length

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


# --------------------------------------------------
# GEMINI SUMMARY
# --------------------------------------------------

def generate_summary(transcript, api_key, source_language, output_language):
    """Summarise a transcript with Gemini."""
    client = genai.Client(api_key=api_key)
    chunks = split_text(transcript)

    if not chunks:
        raise ValueError("The video transcript contains no text to summarise.")

    if output_language == "Same as video":
        language_instruction = (
            f"Write the summary in {source_language}, "
            "the language of the selected video captions."
        )
    else:
        language_instruction = f"Write the entire summary in {output_language}."

    partial_summaries = []
    progress = st.progress(0)
    status = st.empty()

    for index, chunk in enumerate(chunks):
        status.write(
            f"Summarising transcript part {index + 1} of {len(chunks)}..."
        )
        prompt = f"""
You are an expert YouTube video summariser.
Summarise the following transcript section.
{language_instruction}

Requirements:
- Use clear headings and bullet points.
- Include important ideas, facts, examples and explanations.
- Keep technical terms and names accurate.
- Remove repeated ideas.
- Do not add facts that are not present in the transcript.
- Make the summary easy to understand.

Transcript section {index + 1} of {len(chunks)}:
{chunk}
"""
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        if not response.text:
            raise ValueError(
                f"Gemini returned an empty response for part {index + 1}."
            )
        partial_summaries.append(response.text.strip())
        progress.progress((index + 1) / len(chunks))

    status.write("Preparing the final summary...")

    if len(partial_summaries) == 1:
        final_summary = partial_summaries[0]
    else:
        combined_notes = "\n\n".join(partial_summaries)
        final_prompt = f"""
Combine these notes into one complete, well-organised YouTube video summary.
{language_instruction}
Use suitable sections such as Overview, Main Points, Important Examples,
Key Takeaways, and Conclusion. Avoid repetition, preserve important details,
and do not invent facts.

Notes:
{combined_notes}
"""
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=final_prompt,
        )
        if not response.text:
            raise ValueError("Gemini returned an empty final summary.")
        final_summary = response.text.strip()

    progress.progress(1.0)
    status.success("Summary generated successfully!")
    return final_summary


# --------------------------------------------------
# PDF CREATION
# --------------------------------------------------

def create_pdf(summary, video_url, source_language, output_language):
    """Create a downloadable PDF summary."""
    pdf_buffer = BytesIO()
    document = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title="AI YouTube Video Summary",
        author="AI YouTube Video Summariser",
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    heading_style = styles["Heading2"]
    body_style = styles["BodyText"]
    body_style.leading = 15
    body_style.spaceAfter = 8

    story = [
        Paragraph("AI YouTube Video Summary", title_style),
        Spacer(1, 12),
        Paragraph("Video URL", heading_style),
        Paragraph(
            f'<link href="{escape(video_url)}">{escape(video_url)}</link>',
            body_style,
        ),
        Paragraph("Caption Language", heading_style),
        Paragraph(escape(source_language), body_style),
        Paragraph("Summary Language", heading_style),
        Paragraph(escape(output_language), body_style),
        Spacer(1, 12),
        Paragraph("Summary", heading_style),
        Spacer(1, 6),
    ]

    for line in summary.splitlines():
        line = line.strip()
        if not line:
            story.append(Spacer(1, 5))
            continue

        safe_line = escape(line)
        if line.startswith("# "):
            story.append(Paragraph(escape(line[2:]), heading_style))
        elif line.startswith("## "):
            story.append(Paragraph(escape(line[3:]), heading_style))
        elif line.startswith(("- ", "* ", "• ")):
            story.append(Paragraph(f"&bull; {escape(line[2:].strip())}", body_style))
        else:
            story.append(Paragraph(safe_line, body_style))

    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(
            A4[0] - 0.65 * inch,
            0.35 * inch,
            f"Page {doc.page}",
        )
        canvas.restoreState()

    document.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "user" not in st.session_state:
    st.session_state.user = None
if "summary_result" not in st.session_state:
    st.session_state.summary_result = None
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "Sign in"


# --------------------------------------------------
# AUTHENTICATION SCREEN
# --------------------------------------------------

st.markdown(
    """
    <section class="hero-panel">
        <div class="hero-kicker">✦ AI-powered learning companion</div>
        <div class="hero-title">Turn long videos into<br>clear ideas.</div>
        <p class="hero-copy">
            Summarise YouTube videos in seconds, choose your preferred language,
            and keep your key takeaways together in one beautiful workspace.
        </p>
    </section>
    <div class="feature-grid">
        <div class="feature-card">
            <div class="feature-icon">⚡</div>
            <div class="feature-title">Quick summaries</div>
            <div class="feature-copy">Understand the important points without watching every minute.</div>
        </div>
        <div class="feature-card">
            <div class="feature-icon">🌏</div>
            <div class="feature-title">Your language</div>
            <div class="feature-copy">Create summaries in English, Tamil, Hindi and more.</div>
        </div>
        <div class="feature-card">
            <div class="feature-icon">📚</div>
            <div class="feature-title">Saved history</div>
            <div class="feature-copy">Keep summaries linked to your own Firebase account.</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("Sign in to create summaries and save them to your personal history.")

if not st.session_state.user:
    st.subheader("Welcome")
    st.session_state.auth_mode = st.radio(
        "Choose an option",
        ["Sign in", "Sign up"],
        horizontal=True,
        index=0 if st.session_state.auth_mode == "Sign in" else 1,
    )

    with st.form("auth_form", clear_on_submit=False):
        email = st.text_input("Email address", placeholder="you@example.com")
        password = st.text_input(
            "Password",
            type="password",
            help="Use at least 6 characters for a new account.",
        )
        confirm_password = ""
        if st.session_state.auth_mode == "Sign up":
            confirm_password = st.text_input("Confirm password", type="password")

        submitted = st.form_submit_button(
            "Create account" if st.session_state.auth_mode == "Sign up" else "Sign in",
            use_container_width=True,
            type="primary",
        )

    if submitted:
        if not email.strip() or not password:
            st.error("Enter your email address and password.")
        elif st.session_state.auth_mode == "Sign up" and len(password) < 6:
            st.error("Your password must contain at least 6 characters.")
        elif (
            st.session_state.auth_mode == "Sign up"
            and password != confirm_password
        ):
            st.error("The passwords do not match.")
        else:
            try:
                firebase_api_key = os.getenv("FIREBASE_WEB_API_KEY", "").strip()
                action = "signup" if st.session_state.auth_mode == "Sign up" else "signin"
                with st.spinner("Connecting to Firebase Authentication..."):
                    user = firebase_auth(action, email, password, firebase_api_key)

                # Initialize the Admin SDK before verifying the signed-in user's token.
                get_firestore()
                # Verify the token server-side before trusting the UID for database access.
                verified_uid = admin_auth.verify_id_token(user["id_token"])["uid"]
                if verified_uid != user["uid"]:
                    raise ValueError("Firebase returned an unexpected user identity.")

                st.session_state.user = {
                    "uid": verified_uid,
                    "email": user["email"],
                    "id_token": user["id_token"],
                }
                st.session_state.summary_result = None
                st.success("Account ready! You are signed in.")
                st.rerun()
            except Exception as error:
                st.error("Authentication failed.")
                st.caption(str(error))

    st.info(
        "Email/Password sign-in must be enabled in Firebase Authentication. "
        "Use a test account you control."
    )
    st.stop()


# --------------------------------------------------
# SIGNED-IN APP
# --------------------------------------------------

user = st.session_state.user
with st.sidebar:
    st.success(f"Signed in as {user['email']}")
    if st.button("Sign out", use_container_width=True):
        st.session_state.user = None
        st.session_state.summary_result = None
        st.rerun()

    st.divider()
    st.subheader("Saved summaries")
    if st.button("Refresh history", use_container_width=True):
        st.session_state.pop("saved_history", None)

    try:
        db = get_firestore()
        # Re-verify token for the current session before accessing user data.
        verified_uid = admin_auth.verify_id_token(user["id_token"])["uid"]
        if verified_uid != user["uid"]:
            st.session_state.user = None
            st.error("Your session could not be verified. Please sign in again.")
            st.stop()

        history = get_user_summaries(db, verified_uid)
        if history:
            for item in history:
                title = item.get("video_title") or item.get("video_url") or "YouTube summary"
                created = item.get("created_at", "")
                label = f"{title[:35]}{'…' if len(title) > 35 else ''}"
                with st.expander(label):
                    st.caption(str(created))
                    st.markdown(item.get("summary", ""))
                    st.link_button("Open video", item.get("video_url", "https://www.youtube.com"))
        else:
            st.caption("No saved summaries yet.")
    except Exception as error:
        st.warning("Firestore history is unavailable. Check the service-account file and Firebase project.")
        st.caption(f"Error type: {type(error).__name__}")

st.write(
    "Paste a YouTube video link to generate an AI-powered summary "
    "and download it as a PDF. Summaries are saved to your account."
)
st.info(
    "The video must have captions accessible through YouTube Transcript API. "
    "Some videos do not provide accessible captions."
)

output_language = st.selectbox(
    "Choose summary language",
    [
        "Same as video", "English", "Tamil", "Hindi", "Telugu", "Malayalam",
        "Kannada", "Bengali", "Marathi", "Spanish", "French", "German",
        "Japanese", "Chinese", "Arabic",
    ],
)

video_url = st.text_input(
    "YouTube video URL",
    placeholder="https://www.youtube.com/watch?v=...",
)

generate_button = st.button(
    "✨ Generate Summary",
    type="primary",
    use_container_width=True,
)

if generate_button:
    st.session_state.summary_result = None
    if not video_url.strip():
        st.error("Please enter a YouTube video URL.")
    else:
        gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not gemini_api_key:
            st.error("GEMINI_API_KEY is missing from your .env file.")
        else:
            try:
                with st.spinner("Checking the video and fetching captions..."):
                    video_id = get_video_id(video_url)
                    transcript, source_language, source_language_code = fetch_transcript(video_id)

                st.success(
                    f"Captions found. Caption language: {source_language} "
                    f"({source_language_code})."
                )
                summary = generate_summary(
                    transcript=transcript,
                    api_key=gemini_api_key,
                    source_language=source_language,
                    output_language=output_language,
                )

                record = {
                    "video_url": video_url.strip(),
                    "video_id": video_id,
                    "video_title": f"YouTube video {video_id}",
                    "source_language": source_language,
                    "source_language_code": source_language_code,
                    "output_language": output_language,
                    "summary": summary,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }

                try:
                    db = get_firestore()
                    verified_uid = admin_auth.verify_id_token(
                        st.session_state.user["id_token"]
                    )["uid"]
                    if verified_uid != st.session_state.user["uid"]:
                        raise ValueError("Session identity verification failed.")
                    record["user_email"] = st.session_state.user["email"]
                    save_summary(db, verified_uid, record)
                    st.success("Summary saved to your Firebase account.")
                    st.session_state.pop("saved_history", None)
                except Exception as save_error:
                    st.error("The summary was generated, but it could not be saved to Firestore.")
                    st.caption(f"Error type: {type(save_error).__name__}: {save_error}")

                st.session_state.summary_result = {
                    "summary": summary,
                    "video_url": video_url.strip(),
                    "source_language": source_language,
                    "output_language": output_language,
                }

            except Exception as error:
                st.error("Sorry, the summary could not be generated.")
                st.caption(f"Error type: {type(error).__name__}")
                st.write(str(error))
                error_text = str(error).upper()
                if "TRANSCRIPTSDISABLED" in error_text or "NOTRANSCRIPTFOUND" in error_text:
                    st.info("Try a video with accessible captions.")
                elif "API_KEY_INVALID" in error_text or "INVALID API KEY" in error_text:
                    st.warning("Check the Gemini API key in .env. Do not share it publicly.")
                elif "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
                    st.warning("The Gemini API may have reached a usage limit.")

result = st.session_state.summary_result
if result:
    st.divider()
    st.subheader("📝 Video Summary")
    st.caption(
        f"Caption language: {result['source_language']} | "
        f"Summary language: {result['output_language']}"
    )
    st.markdown(result["summary"])

    try:
        pdf_bytes = create_pdf(
            summary=result["summary"],
            video_url=result["video_url"],
            source_language=result["source_language"],
            output_language=result["output_language"],
        )
        st.download_button(
            label="📄 Download Summary as PDF",
            data=pdf_bytes,
            file_name="youtube_video_summary.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except Exception as error:
        st.warning("The summary was created, but the PDF could not be generated.")
        st.caption(f"Error type: {type(error).__name__}")

st.divider()
st.caption("Built with Streamlit, YouTube Transcript API, Gemini AI and Firebase.")
