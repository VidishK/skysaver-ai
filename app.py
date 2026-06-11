"""
SkySaver AI — Streamlit app.

Run with:
    streamlit run app.py

Pages:
  - Auth (Sign in / Sign up tabs)  — real signup/login backed by MongoDB
  - Dashboard                       — itinerary + disruption recovery
  - Trip details                    — view + fully edit every leg
  - Preferences                     — edit traveller preferences
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:  # graceful fallback if package not installed yet
    def st_autorefresh(*args, **kwargs):  # type: ignore[no-redef]
        return None

from airports import LABELS as AIRPORT_LABELS, iata_from_label, label_from_iata
from cascade import _flight_label, calculate_cascade
from chatbot import ask_chatbot
from confirmation_scanner import scan_confirmation
from deep_links import (
    airline_booking_link,
    google_calendar_link,
    google_flights_link,
    hotel_search_link,
    uber_link,
)
from flight_search import search_flights
from ics_export import trip_to_ics
from mongo_helpers import (
    add_leg,
    authenticate_user,
    create_session_token,
    create_user,
    delete_leg,
    delete_session_token,
    get_trip,
    list_users,
    log_disruption,
    lookup_session_token,
    next_leg_id,
    save_trip,
    update_leg,
)
from seed_trip import build_demo_trip


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEMO_TRIP_ID = "trip_001"


def current_trip_id() -> str:
    """Trip id scoped to the logged-in user. Hackathon-scope: one trip per user.

    Anonymous fallback returns the demo id so things still work pre-signup.
    """
    user = st.session_state.get("user", {})
    email = (user.get("email") or "").strip().lower()
    if not email:
        return DEMO_TRIP_ID
    safe = email.replace("@", "_at_").replace(".", "_")
    return f"trip_{safe}"

SEVERITY_COLORS = {
    "ok": "#10B981",        # emerald
    "shifted": "#3B82F6",   # blue
    "tight": "#F59E0B",     # amber
    "broken": "#EF4444",    # red
}
LEG_ICON = {
    "flight": "✈",
    "hotel": "🏨",
    "transport": "🚖",
    "meeting": "📅",
}
STATUS_COLORS = {
    "scheduled":   "#64748B",
    "in_progress": "#3B82F6",
    "completed":   "#10B981",
    "rebooked":    "#10B981",
    "disrupted":   "#F59E0B",
    "cancelled":   "#EF4444",
}

PAGE_DASHBOARD = "Dashboard"
PAGE_TRIP = "Trip details"
PAGE_PLAN = "Plan a trip"
PAGE_PREFS = "Preferences"
PAGE_SETTINGS = "Settings"
PAGES = [PAGE_DASHBOARD, PAGE_TRIP, PAGE_PLAN, PAGE_PREFS, PAGE_SETTINGS]

WINDOWS = {
    "Any time": (0, 24),
    "Early morning (00–06)": (0, 6),
    "Morning (06–12)": (6, 12),
    "Afternoon (12–18)": (12, 18),
    "Evening (18–24)": (18, 24),
}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Global CSS — the modern look
# ---------------------------------------------------------------------------


CUSTOM_CSS = """
<style>
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        letter-spacing: -0.01em;
    }
    .main { background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%); }

    h1 { font-weight: 700 !important; letter-spacing: -0.02em !important; color: #0F172A !important; }
    h2, h3 { font-weight: 600 !important; letter-spacing: -0.015em !important; color: #0F172A !important; }

    .stButton > button, .stDownloadButton > button {
        border-radius: 10px !important; font-weight: 500 !important;
        transition: all 0.15s ease !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05) !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 12px rgba(99, 102, 241, 0.18) !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #4F46E5 0%, #8B5CF6 100%) !important;
        color: #FFFFFF !important; border: none !important;
    }

    .stTextInput input, .stTextArea textarea, .stSelectbox > div,
    .stMultiSelect > div, .stNumberInput input {
        border-radius: 10px !important; border-color: #E2E8F0 !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #4F46E5 !important;
        box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1) !important;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 14px !important; border-color: #E2E8F0 !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
    }

    [data-testid="stSidebar"] {
        background: #F8FAFC !important; border-right: 1px solid #E2E8F0;
    }
    [data-testid="stSidebar"] h2 {
        background: linear-gradient(135deg, #4F46E5, #8B5CF6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    [data-testid="stMetric"] {
        background: #FFFFFF; padding: 14px 18px; border-radius: 12px;
        border: 1px solid #E2E8F0; box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
    }
    [data-testid="stMetricValue"] { font-weight: 700 !important; color: #0F172A !important; }
    [data-testid="stMetricLabel"] { color: #64748B !important; font-size: 0.85rem !important; }

    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent; }

    hr {
        border: none !important;
        border-top: 1px solid #E2E8F0 !important;
        margin: 24px 0 !important;
    }

    /* ---- Top navigation bar ---- */
    .top-nav {
        display: flex; justify-content: space-between; align-items: center;
        padding: 14px 28px;
        background: rgba(15, 23, 42, 0.92);
        backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        margin-bottom: 18px;
    }
    .top-nav .brand {
        font-size: 1.15rem; font-weight: 700;
        background: linear-gradient(135deg, #818CF8 0%, #C084FC 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.01em;
    }
    .top-nav .nav-links { display: flex; gap: 22px; }
    .top-nav .nav-links a {
        color: #CBD5E1; text-decoration: none; font-size: 0.92rem; font-weight: 500;
        transition: color 0.15s ease;
    }
    .top-nav .nav-links a:hover { color: #FFFFFF; }
    .top-nav .nav-cta {
        display: flex; gap: 10px; align-items: center;
    }
    .top-nav .btn-ghost {
        color: #E2E8F0; padding: 8px 16px; border-radius: 8px;
        text-decoration: none; font-size: 0.9rem; font-weight: 500;
        transition: background 0.15s ease;
    }
    .top-nav .btn-ghost:hover { background: rgba(255,255,255,0.06); }
    .top-nav .btn-cta {
        background: linear-gradient(135deg, #6366F1 0%, #A855F7 100%);
        color: #FFFFFF !important; padding: 8px 18px; border-radius: 8px;
        font-size: 0.9rem; font-weight: 600; text-decoration: none;
        box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
        transition: all 0.15s ease;
    }
    .top-nav .btn-cta:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 18px rgba(99, 102, 241, 0.5);
    }

    /* ---- Futuristic Hero ---- */
    @keyframes heroFadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes brandPulse {
        0%, 100% {
            filter: drop-shadow(0 0 24px rgba(139, 92, 246, 0.5))
                    drop-shadow(0 0 48px rgba(236, 72, 153, 0.2));
        }
        50% {
            filter: drop-shadow(0 0 36px rgba(139, 92, 246, 0.85))
                    drop-shadow(0 0 72px rgba(236, 72, 153, 0.35));
        }
    }
    @keyframes gridDrift {
        0% { background-position: 0 0; }
        100% { background-position: 80px 80px; }
    }
    @keyframes orbitGlow {
        0%, 100% { transform: translateX(-50%) scale(1); opacity: 0.55; }
        50% { transform: translateX(-50%) scale(1.08); opacity: 0.75; }
    }
    @keyframes scanLine {
        0% { transform: translateY(-100%); opacity: 0; }
        10% { opacity: 0.4; }
        50% { opacity: 0.6; }
        90% { opacity: 0.4; }
        100% { transform: translateY(700%); opacity: 0; }
    }

    .auth-hero {
        position: relative;
        background: radial-gradient(120% 100% at 50% 0%, #1E1B4B 0%, #0F172A 60%, #020617 100%);
        border-radius: 24px;
        padding: 110px 24px 130px;
        text-align: center;
        overflow: hidden;
        box-shadow: 0 30px 70px -30px rgba(79, 70, 229, 0.55);
    }
    /* Animated grid pattern */
    .auth-hero::before {
        content: "";
        position: absolute; inset: 0;
        background-image:
            linear-gradient(rgba(139, 92, 246, 0.12) 1px, transparent 1px),
            linear-gradient(90deg, rgba(139, 92, 246, 0.12) 1px, transparent 1px);
        background-size: 80px 80px;
        animation: gridDrift 20s linear infinite;
        mask-image: radial-gradient(ellipse at center, black 30%, transparent 75%);
        -webkit-mask-image: radial-gradient(ellipse at center, black 30%, transparent 75%);
        z-index: 0;
    }
    /* Bottom orbit glow */
    .auth-hero::after {
        content: "";
        position: absolute; left: 50%; bottom: -200px;
        width: 800px; height: 800px; transform: translateX(-50%);
        background: radial-gradient(circle,
            rgba(139, 92, 246, 0.35) 0%,
            rgba(236, 72, 153, 0.15) 35%,
            transparent 70%);
        z-index: 0;
        animation: orbitGlow 6s ease-in-out infinite;
    }
    .auth-hero-inner {
        position: relative; z-index: 1;
        animation: heroFadeIn 1s ease-out;
    }
    /* Scan line sweep */
    .scan-line {
        position: absolute; left: 0; right: 0; top: 0; height: 2px;
        background: linear-gradient(90deg,
            transparent 0%,
            rgba(139, 92, 246, 0) 10%,
            rgba(192, 132, 252, 0.7) 50%,
            rgba(139, 92, 246, 0) 90%,
            transparent 100%);
        animation: scanLine 8s linear infinite;
        z-index: 2; pointer-events: none;
    }

    .auth-eyebrow {
        display: inline-block;
        font-size: 0.78rem; font-weight: 600; letter-spacing: 0.22em;
        text-transform: uppercase; color: #C7D2FE;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(199, 210, 254, 0.22);
        padding: 8px 18px; border-radius: 999px;
        margin-bottom: 28px;
        backdrop-filter: blur(8px);
    }
    .brand-mark {
        font-size: 7rem; font-weight: 900;
        line-height: 0.95; letter-spacing: -0.05em;
        margin: 0 0 6px;
        background: linear-gradient(135deg, #FFFFFF 0%, #C7D2FE 35%, #C084FC 70%, #F472B6 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: brandPulse 3.6s ease-in-out infinite;
    }
    .auth-title {
        font-size: 1.8rem; font-weight: 500;
        line-height: 1.2; letter-spacing: -0.02em; color: #CBD5E1;
        margin: 8px 0 24px;
    }
    .auth-title .grad {
        background: linear-gradient(135deg, #818CF8 0%, #C084FC 50%, #F472B6 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
        font-weight: 700;
    }
    .auth-sub {
        font-size: 1.1rem; color: #94A3B8; max-width: 600px;
        margin: 0 auto; line-height: 1.6;
    }
    .auth-hero-cta {
        display: inline-flex; gap: 14px; margin-top: 42px;
        flex-wrap: wrap; justify-content: center;
    }
    .auth-hero-cta a {
        text-decoration: none; padding: 14px 30px;
        border-radius: 999px; font-weight: 600; font-size: 1rem;
        transition: all 0.18s ease;
    }
    .auth-hero-cta .cta-primary {
        background: #FFFFFF; color: #0F172A;
        box-shadow:
            0 4px 18px rgba(255, 255, 255, 0.18),
            0 0 0 1px rgba(255, 255, 255, 0.6) inset;
    }
    .auth-hero-cta .cta-primary:hover {
        transform: translateY(-2px);
        box-shadow:
            0 8px 28px rgba(139, 92, 246, 0.32),
            0 0 0 1px rgba(255, 255, 255, 0.8) inset;
    }
    .auth-hero-cta .cta-secondary {
        background: rgba(255, 255, 255, 0.04); color: #E2E8F0;
        border: 1px solid rgba(255, 255, 255, 0.14);
        backdrop-filter: blur(8px);
    }
    .auth-hero-cta .cta-secondary:hover {
        background: rgba(255, 255, 255, 0.08);
        border-color: rgba(255, 255, 255, 0.24);
    }

    /* ---- Feature cards ---- */
    .feature-grid {
        display: grid; grid-template-columns: repeat(3, 1fr);
        gap: 16px; margin: 32px 0;
    }
    .feature-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 16px;
        padding: 24px;
        transition: all 0.2s ease;
    }
    .feature-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
        border-color: #C7D2FE;
    }
    .feature-icon {
        display: inline-flex; align-items: center; justify-content: center;
        width: 44px; height: 44px;
        background: linear-gradient(135deg, #EEF2FF 0%, #F5F3FF 100%);
        border: 1px solid #E0E7FF;
        border-radius: 12px;
        font-size: 1.4rem;
        margin-bottom: 14px;
    }
    .feature-title {
        font-weight: 700; font-size: 1.05rem; color: #0F172A;
        margin-bottom: 6px;
    }
    .feature-desc {
        color: #64748B; font-size: 0.92rem; line-height: 1.5;
    }

    /* ---- Section heading ---- */
    .section-eyebrow {
        text-align: center;
        font-size: 0.78rem; font-weight: 700; letter-spacing: 0.18em;
        text-transform: uppercase; color: #6366F1;
        margin-top: 50px; margin-bottom: 8px;
    }
    .section-title {
        text-align: center;
        font-size: 2rem; font-weight: 700; color: #0F172A;
        letter-spacing: -0.02em; margin-bottom: 12px;
    }
    .section-sub {
        text-align: center; color: #64748B;
        max-width: 560px; margin: 0 auto 28px; font-size: 1rem;
    }

    /* ---- Quick start (futuristic intake) ---- */
    .quickstart-wrap {
        max-width: 920px; margin: -40px auto 30px;
        position: relative; z-index: 5;
    }
    .quickstart-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(248,250,252,0.96) 100%);
        border: 1px solid rgba(99, 102, 241, 0.18);
        border-radius: 20px;
        padding: 28px 32px;
        box-shadow:
            0 25px 60px -25px rgba(99, 102, 241, 0.45),
            0 0 0 1px rgba(255, 255, 255, 0.06) inset;
        position: relative;
        overflow: hidden;
    }
    .quickstart-card::before {
        content: "";
        position: absolute; top: -2px; left: -2px; right: -2px; bottom: -2px;
        background: linear-gradient(135deg, #6366F1, #A855F7, #EC4899, #6366F1);
        background-size: 400% 400%;
        border-radius: 22px;
        z-index: -1;
        animation: borderShimmer 12s linear infinite;
        opacity: 0.5;
    }
    @keyframes borderShimmer {
        0% { background-position: 0% 50%; }
        100% { background-position: 400% 50%; }
    }
    .quickstart-label {
        display: inline-block;
        font-size: 0.74rem; font-weight: 700; letter-spacing: 0.18em;
        text-transform: uppercase;
        background: linear-gradient(135deg, #6366F1, #A855F7);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 6px;
    }
    .quickstart-title {
        font-size: 1.5rem; font-weight: 700; color: #0F172A;
        letter-spacing: -0.02em; margin-bottom: 4px;
    }
    .quickstart-sub {
        color: #64748B; font-size: 0.95rem; margin-bottom: 20px;
    }
    .quickstart-confirm {
        background: linear-gradient(135deg, #EEF2FF 0%, #F5F3FF 100%);
        border: 1px solid #C7D2FE;
        border-radius: 12px;
        padding: 14px 18px;
        color: #3730A3;
        font-size: 0.92rem;
        margin-top: 16px;
    }

    .auth-card-wrap {
        max-width: 520px; margin: 30px auto 50px;
        position: relative; z-index: 5;
    }
    .auth-card-wrap [data-testid="stVerticalBlockBorderWrapper"] {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        box-shadow: 0 25px 50px -20px rgba(15, 23, 42, 0.18) !important;
        padding: 6px 6px 4px !important;
    }

    /* ---- Payment method cards ---- */
    .pay-grid { display:flex; gap:10px; margin-top:8px; flex-wrap:wrap; }
    .pay-pill {
        flex:1; min-width:140px;
        background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px;
        padding:14px 14px; text-align:center; font-weight:600; color:#0F172A;
        box-shadow:0 1px 3px rgba(15,23,42,0.04);
    }
    .pay-pill .pay-sub {
        display:block; font-weight:500; font-size:0.78rem;
        color:#64748B; margin-top:2px;
    }

    /* ---- Floating chat hint ---- */
    .chat-hint {
        background: linear-gradient(135deg, #EEF2FF 0%, #F5F3FF 100%);
        border: 1px solid #C7D2FE;
        border-radius: 12px;
        padding: 12px 16px;
        color: #3730A3;
        font-size: 0.9rem;
        margin-top: 8px;
    }

    /* ---- Live disruption alert (top of dashboard) ---- */
    @keyframes alertPulse {
        0%, 100% {
            box-shadow:
                0 0 0 0 rgba(239, 68, 68, 0.55),
                0 8px 30px -10px rgba(239, 68, 68, 0.55);
        }
        50% {
            box-shadow:
                0 0 0 14px rgba(239, 68, 68, 0),
                0 12px 40px -10px rgba(239, 68, 68, 0.7);
        }
    }
    @keyframes alertSlideIn {
        from { transform: translateY(-12px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
    }
    @keyframes sirenSpin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    .alert-banner {
        position: relative;
        background: linear-gradient(135deg, #FEE2E2 0%, #FECACA 60%, #FCA5A5 100%);
        border: 1px solid #FCA5A5;
        border-left: 6px solid #DC2626;
        border-radius: 14px;
        padding: 18px 22px;
        margin-bottom: 18px;
        animation: alertSlideIn 0.45s ease-out, alertPulse 2.2s ease-in-out infinite;
    }
    .alert-banner-row {
        display: flex; align-items: center; gap: 16px;
    }
    .alert-icon {
        width: 44px; height: 44px;
        display: inline-flex; align-items: center; justify-content: center;
        background: #DC2626; color: #FFFFFF;
        border-radius: 12px; font-size: 1.6rem;
        animation: sirenSpin 6s linear infinite;
        box-shadow: 0 4px 16px rgba(220, 38, 38, 0.45);
        flex-shrink: 0;
    }
    .alert-text { flex: 1; }
    .alert-title {
        font-size: 1.1rem; font-weight: 700;
        color: #7F1D1D; margin: 0; letter-spacing: -0.01em;
    }
    .alert-body {
        color: #991B1B; font-size: 0.95rem; margin-top: 4px;
    }
    .alert-time {
        font-size: 0.8rem; color: #B91C1C;
        margin-top: 4px; letter-spacing: 0.04em;
    }

    /* ---- Notification dot ---- */
    @keyframes notifPulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(1.18); }
    }
    .notif-bell {
        position: relative;
        display: inline-flex; align-items: center; gap: 8px;
        padding: 8px 14px;
        background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%);
        border: 1px solid #FDE68A;
        border-radius: 999px;
        font-size: 0.88rem; font-weight: 600; color: #92400E;
    }
    .notif-bell .dot {
        width: 8px; height: 8px; border-radius: 50%;
        background: #DC2626;
        animation: notifPulse 1.4s ease-in-out infinite;
    }

    /* ---- Stat card color treatments ---- */
    .stat-card-grad {
        background: linear-gradient(135deg, #EEF2FF 0%, #F5F3FF 100%);
        border: 1px solid #C7D2FE;
    }
    .stat-card-warn {
        background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%);
        border: 1px solid #FCD34D;
    }
    .stat-card-danger {
        background: linear-gradient(135deg, #FEE2E2 0%, #FECACA 100%);
        border: 1px solid #FCA5A5;
    }

    /* ---- Rainbow accent divider ---- */
    .accent-divider {
        height: 4px; border-radius: 999px;
        background: linear-gradient(90deg,
            #6366F1 0%, #8B5CF6 25%, #EC4899 50%, #F59E0B 75%, #10B981 100%);
        background-size: 200% 100%;
        animation: gradientShift 6s linear infinite;
        margin: 20px 0;
    }
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        100% { background-position: 200% 50%; }
    }

    /* ---- Glowing leg card on disrupted status ---- */
    @keyframes dangerGlow {
        0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.2), 0 1px 3px rgba(15,23,42,0.04); }
        50% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0), 0 4px 16px rgba(239, 68, 68, 0.25); }
    }

    /* =====================================================================
       TIER 2 POLISH — top-site-quality interactions
       Inspired by Stripe, Linear, Vercel, Arc Browser, Cursor
       ===================================================================== */

    /* Smooth fluid transitions everywhere */
    * { transition-timing-function: cubic-bezier(0.22, 1, 0.36, 1); }

    /* Buttons: gradient + shimmer on hover (Stripe-style) */
    .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
        position: relative; overflow: hidden;
        background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #EC4899 100%) !important;
        background-size: 200% 200% !important;
        animation: gradientShift 8s ease infinite;
    }
    .stButton > button[kind="primary"]::after,
    .stDownloadButton > button[kind="primary"]::after {
        content: ""; position: absolute; top: 0; left: -100%;
        width: 100%; height: 100%;
        background: linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.3) 50%, transparent 100%);
        transition: left 0.6s ease;
    }
    .stButton > button[kind="primary"]:hover::after,
    .stDownloadButton > button[kind="primary"]:hover::after {
        left: 100%;
    }

    /* All buttons: subtle lift + tinted shadow on hover */
    .stButton > button, .stDownloadButton > button, .stLinkButton > a {
        transition: all 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover {
        transform: translateY(-2px) !important;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow:
            0 10px 30px -8px rgba(99, 102, 241, 0.55),
            0 0 0 1px rgba(255,255,255,0.6) inset !important;
    }

    /* Cards / containers: glass + glow on hover */
    [data-testid="stVerticalBlockBorderWrapper"] {
        transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1) !important;
        background: linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(248,250,252,0.96) 100%) !important;
        backdrop-filter: blur(8px);
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-2px);
        border-color: #C7D2FE !important;
        box-shadow:
            0 12px 30px -10px rgba(99, 102, 241, 0.22),
            0 1px 3px rgba(15, 23, 42, 0.06) !important;
    }

    /* Metric tiles get colour shifts on hover */
    [data-testid="stMetric"] {
        position: relative; overflow: hidden;
        transition: all 0.25s ease !important;
    }
    [data-testid="stMetric"]::before {
        content: ""; position: absolute; top: 0; left: 0;
        width: 100%; height: 3px;
        background: linear-gradient(90deg, #6366F1, #8B5CF6, #EC4899);
        opacity: 0.6;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px -10px rgba(99, 102, 241, 0.35) !important;
        border-color: #C7D2FE !important;
    }

    /* Sidebar nav: active page gets a gradient pill */
    [data-testid="stSidebar"] [role="radiogroup"] label {
        transition: all 0.2s ease;
        border-radius: 10px;
        padding: 8px 12px !important;
        margin-bottom: 2px;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: rgba(99, 102, 241, 0.08);
    }
    [data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"],
    [data-testid="stSidebar"] [role="radiogroup"] input:checked + div {
        background: linear-gradient(135deg, #EEF2FF 0%, #F5F3FF 100%) !important;
        color: #4F46E5 !important;
        font-weight: 600 !important;
    }

    /* Tab pill polish */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: #F1F5F9; padding: 4px; border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        padding: 8px 16px !important;
        transition: all 0.2s ease !important;
        color: #475569 !important;
        font-weight: 500 !important;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: #FFFFFF !important;
        color: #4F46E5 !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
        font-weight: 600 !important;
    }

    /* Section headings with gradient accent */
    h2::before, h3::before {
        content: ""; display: inline-block;
        width: 4px; height: 18px; vertical-align: middle;
        background: linear-gradient(180deg, #6366F1, #8B5CF6, #EC4899);
        border-radius: 999px; margin-right: 10px;
        opacity: 0.8;
    }

    /* Type-coded leg gradients (Linear-style category colours) */
    .leg-flight {
        background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%) !important;
        border-color: #BFDBFE !important;
    }
    .leg-hotel {
        background: linear-gradient(135deg, #FAF5FF 0%, #F3E8FF 100%) !important;
        border-color: #E9D5FF !important;
    }
    .leg-transport {
        background: linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%) !important;
        border-color: #FDE68A !important;
    }
    .leg-meeting {
        background: linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%) !important;
        border-color: #A7F3D0 !important;
    }

    /* Smooth hover for our custom leg cards */
    .leg-card {
        transition: all 0.25s cubic-bezier(0.22, 1, 0.36, 1);
        cursor: default;
    }
    .leg-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 28px -12px rgba(15, 23, 42, 0.12) !important;
    }

    /* Custom scrollbars */
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-track { background: #F8FAFC; }
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, #C7D2FE, #A78BFA);
        border-radius: 999px;
        border: 2px solid #F8FAFC;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(180deg, #818CF8, #8B5CF6);
    }

    /* Toasts and success messages: punchier */
    [data-baseweb="notification"] {
        border-radius: 12px !important;
        backdrop-filter: blur(10px);
        animation: alertSlideIn 0.4s ease-out;
    }

    /* Dashboard mesh gradient subtle background */
    .dashboard-mesh {
        position: fixed; inset: 0;
        background:
            radial-gradient(circle at 20% 30%, rgba(99, 102, 241, 0.05) 0%, transparent 40%),
            radial-gradient(circle at 80% 20%, rgba(236, 72, 153, 0.04) 0%, transparent 40%),
            radial-gradient(circle at 50% 80%, rgba(139, 92, 246, 0.05) 0%, transparent 40%);
        pointer-events: none; z-index: 0;
    }

    /* Live status pulse */
    @keyframes livePing {
        0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6); }
        100% { box-shadow: 0 0 0 14px rgba(16, 185, 129, 0); }
    }
    .live-ping {
        width: 8px; height: 8px; border-radius: 50%;
        background: #16A34A; position: relative;
    }
    .live-ping::after {
        content: ""; position: absolute; inset: 0;
        border-radius: 50%; background: #16A34A;
        animation: livePing 1.6s ease-out infinite;
    }

    /* Big number callout style */
    .big-num {
        font-size: 2.4rem; font-weight: 800;
        background: linear-gradient(135deg, #4F46E5, #8B5CF6, #EC4899);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
        line-height: 1; letter-spacing: -0.03em;
    }
</style>
"""


# ---------------------------------------------------------------------------
# Helpers — time + formatting
# ---------------------------------------------------------------------------


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _fmt(iso: str) -> str:
    return _parse(iso).strftime("%a %d %b %H:%M UTC")


def _badge(text: str, color: str) -> str:
    return (
        f"<span style='background:{color};color:#fff;padding:3px 12px;"
        f"border-radius:999px;font-size:0.72rem;font-weight:600;"
        f"letter-spacing:0.03em;text-transform:uppercase;'>{text}</span>"
    )


def _parse_serpapi_time(value: str, fallback_date: str) -> datetime:
    if not value:
        return datetime.fromisoformat(fallback_date + "T09:00:00+00:00")
    value = value.strip()
    try:
        if " " in value and "-" in value:
            return datetime.fromisoformat(value.replace(" ", "T") + "+00:00")
        hh, mm = value.split(":", 1)
        base = datetime.fromisoformat(fallback_date + "T00:00:00+00:00")
        return base.replace(hour=int(hh), minute=int(mm[:2]))
    except (ValueError, IndexError):
        return datetime.fromisoformat(fallback_date + "T09:00:00+00:00")


def _augment_with_iso(opt: dict, date: str) -> dict:
    dep_dt = _parse_serpapi_time(opt.get("departure_time", ""), date)
    arr_dt = _parse_serpapi_time(opt.get("arrival_time", ""), date)
    if arr_dt <= dep_dt:
        arr_dt += timedelta(days=1)
    return {
        **opt,
        "origin": opt.get("origin") or "DXB",
        "destination": opt.get("destination") or "SIN",
        "departure_at_iso": _to_iso(dep_dt),
        "arrival_at_iso": _to_iso(arr_dt),
    }


def _score(opt: dict, prefs: dict) -> float:
    s = 0.0
    if prefs.get("prefers_direct") and opt.get("stops", 0) == 0:
        s += 30
    airline_code = (opt.get("airline_code") or "").upper()
    for i, code in enumerate(prefs.get("preferred_airlines", [])):
        if code.upper() == airline_code:
            s += 20 - i * 5
            break
    price = opt.get("price_usd") or 9999
    weight = {"low": 0.005, "medium": 0.02, "high": 0.05}[prefs.get("budget_sensitivity", "medium")]
    s -= price * weight
    s -= (opt.get("duration_minutes") or 0) / 60
    return s


def _departure_hour(opt: dict) -> int:
    dep = opt.get("departure_time", "")
    if not dep:
        return 12
    try:
        if " " in dep:
            return int(dep.split(" ", 1)[1].split(":")[0])
        return int(dep.split(":")[0])
    except (ValueError, IndexError):
        return 12


# ---------------------------------------------------------------------------
# Auth pages
# ---------------------------------------------------------------------------


def render_auth() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # ---- Top nav bar ----
    st.markdown(
        """
        <div class="top-nav">
            <div class="brand">✈ SkySaver AI</div>
            <div class="nav-links">
                <a href="#features">Features</a>
                <a href="#how-it-works">How it works</a>
            </div>
            <div class="nav-cta">
                <a class="btn-ghost" href="#signin">Log in</a>
                <a class="btn-cta" href="#signup">Sign up</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Futuristic hero with big SkySaver AI brand mark ----
    st.markdown(
        """
        <div class="auth-hero">
            <div class="scan-line"></div>
            <div class="auth-hero-inner">
                <div class="auth-eyebrow">✦ Travel that handles itself</div>
                <h1 class="brand-mark">SkySaver AI</h1>
                <p class="auth-title">Meet your <span class="grad">travel guardian</span>.</p>
                <p class="auth-sub">
                    Watches your trip 24/7. When something breaks — a cancelled flight, a missed
                    connection, a tight meeting — it finds the best alternative and books it with your tap.
                </p>
                <div class="auth-hero-cta">
                    <a class="cta-primary" href="#signup">Get started — free</a>
                    <a class="cta-secondary" href="#how-it-works">See how it works</a>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Features as bullet points ----
    st.markdown(
        """
        <div id="features"></div>
        <div class="section-eyebrow">What you get</div>
        <h2 class="section-title">Features</h2>
        <div style="max-width:760px;margin:0 auto 40px;">
          <ul style="list-style:none;padding:0;margin:0;font-size:1rem;color:#0F172A;">
            <li style="display:flex;gap:14px;padding:14px 0;border-bottom:1px solid #E2E8F0;">
              <span style="font-size:1.4rem;line-height:1;">🛡</span>
              <span><b>24/7 monitoring</b> — every flight, hotel, transfer and meeting watched in real time.</span>
            </li>
            <li style="display:flex;gap:14px;padding:14px 0;border-bottom:1px solid #E2E8F0;">
              <span style="font-size:1.4rem;line-height:1;">🧠</span>
              <span><b>Cascade-aware planning</b> — every recovery option shows the ripple effect across your full trip before you commit.</span>
            </li>
            <li style="display:flex;gap:14px;padding:14px 0;border-bottom:1px solid #E2E8F0;">
              <span style="font-size:1.4rem;line-height:1;">⚡</span>
              <span><b>One-tap recovery</b> — pick an option, SkySaver updates every downstream booking and hands you off to pay.</span>
            </li>
            <li style="display:flex;gap:14px;padding:14px 0;border-bottom:1px solid #E2E8F0;">
              <span style="font-size:1.4rem;line-height:1;">🏨</span>
              <span><b>Hotels, AirBnB, and stays</b> — choose where you stay around your budget, with ratings, amenities, and loyalty programs in mind.</span>
            </li>
            <li style="display:flex;gap:14px;padding:14px 0;border-bottom:1px solid #E2E8F0;">
              <span style="font-size:1.4rem;line-height:1;">🚖</span>
              <span><b>Ground transport, your way</b> — Uber, Lyft, public transit, rental car — preferences saved per trip.</span>
            </li>
            <li style="display:flex;gap:14px;padding:14px 0;border-bottom:1px solid #E2E8F0;">
              <span style="font-size:1.4rem;line-height:1;">🗺</span>
              <span><b>Curated attractions</b> — if you're traveling for leisure, get suggestions for what to see at your destination.</span>
            </li>
            <li style="display:flex;gap:14px;padding:14px 0;">
              <span style="font-size:1.4rem;line-height:1;">💬</span>
              <span><b>Built-in chat assistant</b> — ask SkySaver anything about your trip and it'll take you to the right page in one click.</span>
            </li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- How it works — centered ----
    st.markdown(
        """
        <div id="how-it-works"></div>
        <div style="text-align:center;max-width:760px;margin:60px auto 30px;">
            <div style="font-size:0.78rem;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#6366F1;margin-bottom:8px;">
                How it works
            </div>
            <h2 style="font-size:2.4rem;font-weight:700;color:#0F172A;letter-spacing:-0.02em;margin:0 0 16px;">
                Plan once. Travel without thinking.
            </h2>
            <p style="color:#64748B;font-size:1.05rem;line-height:1.6;margin:0;">
                Tell SkySaver about your trip — where you're going, how long, who's with you,
                where you'd like to stay. Then sit back. When something happens, you'll get
                options that already account for everything else on your plate.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- Auth card ----
    st.markdown('<div id="signin"></div><div id="signup"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="text-align:center;margin-top:30px;">'
        '<div style="font-size:0.78rem;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#6366F1;margin-bottom:8px;">Get started</div>'
        '<h2 style="font-size:2rem;font-weight:700;color:#0F172A;letter-spacing:-0.02em;margin:0 0 8px;">Create your account</h2>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="auth-card-wrap">', unsafe_allow_html=True)
    with st.container(border=True):
        # Log in first — that's the most common return path for existing users.
        tab_login, tab_signup = st.tabs(["Log in", "Sign up"])
        with tab_login:
            _render_login_form()
        with tab_signup:
            _render_signup_form()
    st.markdown('</div>', unsafe_allow_html=True)


def _render_login_form() -> None:
    with st.form("login_form", clear_on_submit=False):
        st.markdown("##### Welcome back")
        email = st.text_input("Email", placeholder="you@example.com", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)
        if submitted:
            if not email or not password:
                st.error("Email and password are required.")
                return
            user = authenticate_user(email, password)
            if user is None:
                st.error("Invalid email or password. If you're new, use the Sign up tab.")
                return
            st.session_state["user"] = user
            st.session_state["authenticated"] = True
            # Issue a persistent session token and stamp it onto the URL.
            token = create_session_token(user["email"])
            st.session_state["session_token"] = token
            st.query_params["session"] = token
            # If they had an existing trip, go to Dashboard; otherwise nudge to Plan a Trip.
            trip = get_trip(current_trip_id())
            st.session_state["page"] = PAGE_DASHBOARD if trip else PAGE_PLAN
            st.rerun()


def _render_signup_form() -> None:
    with st.form("signup_form", clear_on_submit=False):
        st.markdown("##### Create your account")
        st.caption("Already have one? Use the **Log in** tab above.")
        name = st.text_input("Full name", placeholder="Vidish K", key="signup_name")
        email = st.text_input("Email", placeholder="you@example.com", key="signup_email")
        password = st.text_input("Password (8+ characters)", type="password", key="signup_password")
        confirm = st.text_input("Confirm password", type="password", key="signup_confirm")
        submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
        if submitted:
            if not all([name.strip(), email.strip(), password, confirm]):
                st.error("All fields are required.")
                return
            if not EMAIL_RE.match(email.strip()):
                st.error("Please enter a valid email address.")
                return
            if len(password) < 8:
                st.error("Password must be at least 8 characters.")
                return
            if password != confirm:
                st.error("Passwords don't match.")
                return
            user = create_user(name, email, password)
            if user is None:
                st.error("An account with that email already exists. Try signing in instead.")
                return
            st.session_state["user"] = user
            st.session_state["authenticated"] = True
            # Issue a persistent session token and stamp it onto the URL.
            token = create_session_token(user["email"])
            st.session_state["session_token"] = token
            st.query_params["session"] = token
            # New users always go straight to Plan a Trip — they need a trip first.
            st.session_state["page"] = PAGE_PLAN
            st.success("Account created. Let's plan your first trip.")
            st.rerun()


# ---------------------------------------------------------------------------
# Shared rendering
# ---------------------------------------------------------------------------


def render_leg_card(leg: dict, *, compact: bool = False, show_actions: bool = True) -> None:
    icon = LEG_ICON.get(leg["type"], "•")
    status = leg.get("status", "scheduled")
    status_color = STATUS_COLORS.get(status, "#64748B")

    action_label: str | None = None
    action_link: str | None = None

    if leg["type"] == "flight":
        label = _flight_label(leg)
        title = f"{icon}  {label} — {leg['origin']} → {leg['destination']}"
        sub = f"{_fmt(leg['start_at'])}  →  {_fmt(leg['end_at'])}"
        meta = f"${leg.get('price_usd', '?')} · Terminal {leg.get('departure_terminal','?')}"
        action_label = "Manage flight ↗"
        action_link = airline_booking_link(leg.get("airline"), leg.get("origin", ""), leg.get("destination", ""))
    elif leg["type"] == "hotel":
        title = f"{icon}  {leg['name']} — {leg['city']}"
        sub = f"Check-in {_fmt(leg['start_at'])} → Check-out {_fmt(leg['end_at'])}"
        meta = f"${leg.get('total_usd','?')} total"
        action_label = "View on Booking.com ↗"
        action_link = hotel_search_link(leg.get("name", ""), leg.get("city", ""))
    elif leg["type"] == "transport":
        title = f"{icon}  {leg['mode'].title()} — {leg['from']} → {leg['to']}"
        sub = f"{_fmt(leg['start_at'])}  →  {_fmt(leg['end_at'])}"
        meta = f"~${leg.get('estimated_cost_usd','?')}"
        action_label = "Order Uber ↗"
        action_link = uber_link(leg.get("from"), leg.get("to"))
    elif leg["type"] == "meeting":
        title = f"{icon}  {leg['title']}"
        sub = f"{_fmt(leg['start_at'])}  →  {_fmt(leg['end_at'])}"
        meta = f"{leg.get('location','')} · importance: {leg.get('importance','medium')}"
    else:
        title, sub, meta = "Unknown leg", "", ""

    padding = "12px 16px" if compact else "16px 20px"
    type_class = f"leg-{leg['type']}" if leg.get("type") in {"flight", "hotel", "transport", "meeting"} else ""
    st.markdown(
        f"""
        <div class="leg-card {type_class}" style="border:1px solid #E2E8F0;border-left:4px solid {status_color};
                    padding:{padding};margin-bottom:8px;border-radius:10px 10px 0 0;
                    box-shadow:0 1px 3px rgba(15,23,42,0.04);
                    border-bottom:none;">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:14px;">
                <div style="font-weight:600;font-size:1.02rem;color:#0F172A;">{title}</div>
                <div>{_badge(status, status_color)}</div>
            </div>
            <div style="color:#334155;margin-top:6px;font-size:0.9rem;">{sub}</div>
            <div style="color:#64748B;margin-top:2px;font-size:0.82rem;">{meta}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if show_actions and action_label and action_link:
        st.markdown(
            f"""<div style="border:1px solid #E2E8F0;border-top:none;border-radius:0 0 10px 10px;
                        background:#F8FAFC;padding:8px 14px;margin-top:-1px;margin-bottom:12px;">
                <a href="{action_link}" target="_blank" rel="noopener"
                   style="font-size:0.85rem;font-weight:600;color:#4F46E5;text-decoration:none;">
                   {action_label}</a>
            </div>""",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="margin-bottom:12px;border-bottom:1px solid #E2E8F0;border-radius:0 0 10px 10px;"></div>',
            unsafe_allow_html=True,
        )


def render_cascade_table(report) -> None:
    rows_html = []
    for imp in report.impacts:
        color = SEVERITY_COLORS.get(imp.severity, "#64748B")
        rows_html.append(
            f"""<tr style='border-top:1px solid #F1F5F9;'>
                <td style="padding:8px 12px;">{_badge(imp.severity, color)}</td>
                <td style="padding:8px 12px;font-weight:600;color:#0F172A;">{imp.leg_type.title()}</td>
                <td style="padding:8px 12px;color:#475569;font-size:0.9rem;">{imp.summary}</td>
            </tr>"""
        )

    overall_color = SEVERITY_COLORS.get(report.overall_severity, "#64748B")
    arrival_label = (
        f"{report.arrival_delta_minutes:+d} min"
        if report.arrival_delta_minutes
        else "no change"
    )

    table_html = f"""
    <div style="border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;margin-top:8px;
                box-shadow:0 1px 3px rgba(15,23,42,0.04);">
        <div style="background:#F8FAFC;padding:10px 14px;font-weight:600;font-size:0.92rem;
                    display:flex;justify-content:space-between;align-items:center;
                    border-bottom:1px solid #E2E8F0;color:#0F172A;">
            <span>Cascade impact</span>
            <span style="font-size:0.82rem;color:#64748B;font-weight:500;">
                arrival: {arrival_label} &nbsp;·&nbsp; {_badge(report.overall_severity, overall_color)}
            </span>
        </div>
        <table style="width:100%;border-collapse:collapse;background:#FFFFFF;">{''.join(rows_html)}</table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Disruption recovery — filterable, expandable
# ---------------------------------------------------------------------------


def render_recovery_panel(trip: dict) -> None:
    disrupted = [l for l in trip["legs"] if l.get("status") in {"cancelled", "disrupted"}]
    if not disrupted:
        return

    affected = disrupted[0]
    st.markdown("---")
    st.markdown("## 🚨 Disruption detected")
    st.error(
        f"**{_flight_label(affected)}** — {affected['origin']} → {affected['destination']} "
        f"on {_fmt(affected['start_at'])} is **{affected['status']}**."
    )

    with st.spinner(f"Searching Google Flights for {affected['origin']} → {affected['destination']}..."):
        date = affected["start_at"][:10]
        options = search_flights(affected["origin"], affected["destination"], date)

    st.caption(
        f"Flight options sourced live from **Google Flights** (via SerpAPI) — "
        f"{len(options)} total result(s) for {affected['origin']} → {affected['destination']} on {date}."
    )

    if not options:
        st.warning("No alternatives returned by the search engine. Try a different date or check API quota.")
        return

    available_airlines = sorted({o.get("airline") for o in options if o.get("airline")})

    with st.container(border=True):
        st.markdown("##### Tell SkySaver what you want")
        f1, f2, f3, f4 = st.columns([2, 2, 1.4, 1])
        with f1:
            window_label = st.selectbox(
                "Preferred departure window",
                options=list(WINDOWS.keys()),
                index=0,
                key="filter_window",
            )
        with f2:
            max_price = st.slider(
                "Max price (USD)",
                min_value=200,
                max_value=3000,
                value=1500,
                step=50,
                key="filter_max_price",
            )
        with f3:
            sort_by = st.selectbox(
                "Sort by",
                options=[
                    "Best for you",
                    "Cheapest first",
                    "Fastest first",
                    "Earliest departure",
                    "Latest departure",
                    "Fewest stops",
                ],
                index=0,
                key="filter_sort_by",
            )
        with f4:
            num_results = st.selectbox(
                "Show",
                options=[3, 5, 10, 15, 20, 30, 50],
                index=2,
                key="filter_num_results",
            )

        f5, f6, f7 = st.columns([2, 1, 1])
        with f5:
            selected_airlines = st.multiselect(
                "Airlines (leave all selected to see everything)",
                options=available_airlines,
                default=available_airlines,
                key="filter_airlines",
            )
        with f6:
            st.markdown("&nbsp;", unsafe_allow_html=True)
            direct_only = st.checkbox(
                "Direct only",
                value=False,
                key="filter_direct_only",
            )
        with f7:
            st.markdown("&nbsp;", unsafe_allow_html=True)
            compact_view = st.checkbox(
                "Compact view",
                value=False,
                key="filter_compact_view",
                help="Use compact cards so you can scan more options at once.",
            )

    window_start, window_end = WINDOWS[window_label]

    def passes_filter(opt: dict) -> bool:
        if direct_only and opt.get("stops", 0) > 0:
            return False
        price = opt.get("price_usd") or 0
        if price > max_price:
            return False
        hr = _departure_hour(opt)
        if not (window_start <= hr < window_end):
            return False
        if selected_airlines and opt.get("airline") not in selected_airlines:
            return False
        return True

    filtered = [o for o in options if passes_filter(o)]
    if not filtered:
        st.warning(
            f"No options match your filters. {len(options)} total flights are available — "
            f"try widening the window, raising the max price, picking more airlines, or unchecking 'direct only'."
        )
        return

    prefs = trip.get("preferences", {})

    def _sort_key(opt: dict):
        if sort_by == "Cheapest first":
            return (opt.get("price_usd") or 99999,)
        if sort_by == "Fastest first":
            return (opt.get("duration_minutes") or 99999,)
        if sort_by == "Earliest departure":
            return (_departure_hour(opt),)
        if sort_by == "Latest departure":
            return (-_departure_hour(opt),)
        if sort_by == "Fewest stops":
            return (opt.get("stops") or 0, opt.get("duration_minutes") or 99999)
        # "Best for you" — higher score = better; negate so default ascending sort works
        return (-_score(opt, prefs),)

    ranked = sorted(filtered, key=_sort_key)[:num_results]
    enriched = [_augment_with_iso(opt, date) for opt in ranked]
    reports = [calculate_cascade(trip, affected["leg_id"], opt) for opt in enriched]

    st.markdown(
        f"### {len(enriched)} option{'s' if len(enriched) != 1 else ''} · sorted by **{sort_by}**"
    )
    st.caption(
        f"{len(filtered)} of {len(options)} flights matched your filters. "
        f"Showing {len(enriched)} · adjust 'Show' or 'Sort by' above to see more."
    )

    for i, (opt, report) in enumerate(zip(enriched, reports), start=1):
        render_option_card(i, opt, report, affected["leg_id"], compact=compact_view)


def render_option_card(i: int, opt: dict, report, affected_leg_id: str, compact: bool = False) -> None:
    stops_label = "Direct" if opt.get("stops", 0) == 0 else f"{opt['stops']} stop"
    duration = opt.get("duration_minutes") or 0
    duration_label = f"{duration // 60}h{duration % 60:02d}m"
    price = opt.get("price_usd", "?")
    airline = opt.get("airline") or "Unknown airline"
    overall = report.overall_severity
    overall_color = SEVERITY_COLORS.get(overall, "#64748B")

    risk_text = {
        "ok": "Low risk · fits cleanly",
        "shifted": "Shifts your hotel/transport",
        "tight": "Tight buffer · watch the clock",
        "broken": "Will break a meeting or connection",
    }.get(overall, overall.title())

    if compact:
        # Compact: one-liner card for quickly scanning lots of options.
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 1.4, 1.4])
            with c1:
                st.markdown(
                    f"<div style='font-weight:700;color:#0F172A;'>#{i}  {airline}</div>"
                    f"<div style='color:#64748B;font-size:0.82rem;'>{stops_label} · {duration_label}</div>",
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    f"<div style='color:#475569;font-size:0.88rem;'>"
                    f"{opt.get('departure_time','?')} → {opt.get('arrival_time','?')}</div>"
                    f"<div style='margin-top:4px;'>{_badge(risk_text, overall_color)}</div>",
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    f"<div style='text-align:right;font-size:1.4rem;font-weight:700;color:#4F46E5;'>${price}</div>",
                    unsafe_allow_html=True,
                )
            with c4:
                if st.button("Book", key=f"book_{i}_{affected_leg_id}", type="primary", use_container_width=True):
                    st.session_state["pending_booking"] = {
                        "trip_id": current_trip_id(),
                        "affected_leg_id": affected_leg_id,
                        "option": opt,
                        "report_dict": report.to_dict(),
                    }
                    st.session_state["confirm_open"] = True
            with st.expander("Cascade impact"):
                render_cascade_table(report)
        return

    # Standard: full card
    with st.container(border=True):
        head_l, head_r = st.columns([3, 1])
        with head_l:
            st.markdown(
                f"<div style='color:#94A3B8;font-size:0.82rem;font-weight:500;"
                f"letter-spacing:0.05em;text-transform:uppercase;margin-bottom:4px;'>"
                f"Option {i}</div>"
                f"<div style='font-size:1.4rem;font-weight:700;color:#0F172A;'>{airline}</div>"
                f"<div style='color:#475569;margin-top:6px;'>"
                f"{opt.get('departure_time','?')} → {opt.get('arrival_time','?')} "
                f"&nbsp;·&nbsp; {duration_label} &nbsp;·&nbsp; {stops_label}</div>",
                unsafe_allow_html=True,
            )
        with head_r:
            st.markdown(
                f"<div style='text-align:right;font-size:2rem;font-weight:700;"
                f"color:#0F172A;line-height:1;'>${price}</div>"
                f"<div style='text-align:right;margin-top:8px;'>"
                f"{_badge(risk_text, overall_color)}</div>",
                unsafe_allow_html=True,
            )

        with st.expander("See cascade impact across your trip"):
            render_cascade_table(report)

        if st.button("Book this option", key=f"book_{i}_{affected_leg_id}", type="primary", use_container_width=True):
            st.session_state["pending_booking"] = {
                "trip_id": current_trip_id(),
                "affected_leg_id": affected_leg_id,
                "option": opt,
                "report_dict": report.to_dict(),
            }
            st.session_state["confirm_open"] = True


def render_confirmation_dialog() -> None:
    """Two-step booking handoff.

    SkySaver can't actually take your payment — no airline OAuth integration
    exists for indie developers. So the honest flow is:

      Step 1 — go to the airline's site (or Google Flights) and pay there.
      Step 2 — come back, paste your confirmation reference, and SkySaver
               records the booking and applies the cascade changes to your
               trip.

    Step 2 only enables after Step 1 has been triggered, so the user knows
    the order and won't confirm before they've actually paid.
    """
    if not st.session_state.get("confirm_open"):
        return

    pending = st.session_state.get("pending_booking")
    if not pending:
        return

    opt = pending["option"]

    # ---- Auto-scroll anchor ----
    # When the dialog appears, this anchor + JS jumps the viewport to it so
    # the user doesn't have to scroll manually after clicking "Book this option".
    st.markdown(
        """
        <div id="booking_dialog"></div>
        <script>
          (function() {
            // Wait for Streamlit to finish rendering, then scroll.
            setTimeout(function() {
              const target = window.parent.document.getElementById('booking_dialog');
              if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 100);
          })();
        </script>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("### ✋ Two steps to finalize this booking")
    st.info(
        f"**{opt.get('airline','?')} {opt.get('flight_number','?')}** for "
        f"**${opt.get('price_usd','?')}**. SkySaver can't process the payment itself "
        f"(no airline OAuth for indie devs), so we hand you off to the airline, "
        f"then capture the confirmation when you come back."
    )

    # ---- Derive route + date for deep linking ----
    airline_code = opt.get("airline_code") or (opt.get("airline", "") or "")[:2].upper()
    airline_name = opt.get("airline") or ""
    origin = opt.get("origin", "")
    destination = opt.get("destination", "")
    # Pull the date from departure_at_iso (set by _augment_with_iso), else the option's raw text
    dep_iso = opt.get("departure_at_iso") or ""
    departure_date = dep_iso[:10] if dep_iso else (opt.get("departure_time", "")[:10] if opt.get("departure_time") else "")

    # ---- Step 1: pay on the airline site OR Google Flights ----
    st.markdown("##### Step 1 · Pay")
    st.caption(
        "Pick where you want to complete payment. The airline button below "
        "pre-fills your route and date when supported."
    )
    s1c1, s1c2 = st.columns(2)
    with s1c1:
        airline_link = airline_booking_link(
            airline_code,
            fallback_origin=origin,
            fallback_dest=destination,
            airline_name=airline_name,
            departure_date=departure_date,
        )
        airline_label = airline_name or airline_code or "the airline"
        st.link_button(
            f"✈ Open {airline_label} ↗",
            airline_link,
            use_container_width=True,
            type="primary",
            help=f"Opens {airline_label} pre-filled with {origin} → {destination} on {departure_date} when supported.",
        )
    with s1c2:
        gf_link = google_flights_link(origin, destination, departure_date)
        st.link_button(
            f"🔎 Compare on Google Flights ↗",
            gf_link,
            use_container_width=True,
            help=f"Compare prices for {origin} → {destination} on {departure_date}.",
        )

    st.markdown(
        "<div style='color:#64748B;font-size:0.82rem;margin-top:6px;'>"
        "Opens in a new tab. Complete payment there. Your booking confirmation "
        "code (PNR or reference) will arrive by email — keep it handy."
        "</div>",
        unsafe_allow_html=True,
    )

    if st.button("✅ I've paid — show me Step 2", key="paid_button", use_container_width=False):
        st.session_state["paid_externally"] = True

    if not st.session_state.get("paid_externally"):
        return

    # ---- Step 2: enter confirmation, SkySaver records it ----
    st.markdown("---")
    st.markdown("##### Step 2 · Confirm your booking in SkySaver")

    # ---- 2a. Upload + Gemini Vision scan (the fast path) ----
    st.markdown("**Fast path — upload your confirmation, SkySaver reads it.**")
    st.caption(
        "Drop the airline's email PDF, a screenshot, or a photo of your ticket. "
        "Gemini will read it and pre-fill the fields below."
    )
    uploaded = st.file_uploader(
        "Upload confirmation (PDF, PNG, or JPG)",
        type=["pdf", "png", "jpg", "jpeg", "webp"],
        key="confirm_upload",
        label_visibility="collapsed",
    )

    if uploaded is not None and st.session_state.get("scanned_filename") != uploaded.name:
        with st.spinner("📄 SkySaver is reading your confirmation…"):
            extracted = scan_confirmation(uploaded.getvalue(), uploaded.name)
        st.session_state["scanned_filename"] = uploaded.name
        if extracted.get("error"):
            st.error(extracted["error"])
        else:
            st.session_state["scanned_confirmation"] = extracted
            ref = extracted.get("confirmation_reference") or "(none)"
            airline = extracted.get("airline_name") or extracted.get("airline_code") or "?"
            flightno = extracted.get("flight_number") or "?"
            st.success(
                f"Scanned **{uploaded.name}** — extracted ref **{ref}** for "
                f"**{airline} {flightno}**. Confirm the details below and save."
            )

    scanned = st.session_state.get("scanned_confirmation", {}) or {}

    # ---- 2b. Final form (manual or pre-filled) ----
    st.markdown("---")
    st.caption(
        "Or type it in manually. SkySaver writes the new flight to MongoDB and "
        "shifts hotel, transport, and meetings to match."
    )
    with st.form("confirm_booking_form"):
        confirmation = st.text_input(
            "Booking confirmation code (PNR / reference)",
            value=scanned.get("confirmation_reference") or "",
            placeholder="e.g. EK-Z7P2KL",
        )
        method_options = ["Credit / debit card", "PayPal", "Apple Pay", "Google Pay", "Other"]
        scanned_method = (scanned.get("paid_with") or "").lower()
        method_default = 0
        for i, m in enumerate(method_options):
            if scanned_method and scanned_method[:3] in m.lower():
                method_default = i
                break
        method = st.selectbox("Paid with", method_options, index=method_default)

        # Show what was extracted so the user can sanity check.
        if scanned:
            with st.expander("Show extracted details", expanded=False):
                st.json({k: v for k, v in scanned.items() if v is not None})

        c1, c2, _ = st.columns([1, 1, 4])
        with c1:
            confirmed = st.form_submit_button("Save booking", type="primary", use_container_width=True)
        with c2:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

    def _clear_booking_state() -> None:
        st.session_state["confirm_open"] = False
        st.session_state["pending_booking"] = None
        st.session_state["paid_externally"] = False
        st.session_state["scanned_confirmation"] = {}
        st.session_state["scanned_filename"] = None

    if cancelled:
        _clear_booking_state()
        st.rerun()
    if confirmed:
        if not confirmation.strip():
            st.error("Please paste the confirmation code so SkySaver can track this flight.")
            return
        pending["confirmation_reference"] = confirmation.strip()
        pending["paid_with"] = method
        apply_booking(pending)
        _clear_booking_state()
        st.session_state["last_booking_method"] = method
        st.success(
            f"Booked {opt.get('airline','?')} {opt.get('flight_number','?')} (ref {confirmation.strip()}). "
            f"Itinerary updated. SkySaver is now tracking the new flight."
        )
        st.rerun()


def apply_booking(pending: dict) -> None:
    trip_id = pending["trip_id"]
    leg_id = pending["affected_leg_id"]
    opt = pending["option"]
    report_dict = pending["report_dict"]
    confirmation_ref = pending.get("confirmation_reference") or "DEMO-BOOKED"
    paid_with = pending.get("paid_with") or "external"

    update_leg(
        trip_id,
        leg_id,
        {
            "airline": opt.get("airline_code") or (opt.get("airline", "") or "")[:2].upper(),
            "flight_number": opt.get("flight_number", "TBD"),
            "origin": opt["origin"],
            "destination": opt["destination"],
            "start_at": opt["departure_at_iso"],
            "end_at": opt["arrival_at_iso"],
            "price_usd": opt.get("price_usd"),
            "status": "rebooked",
            "booking_reference": confirmation_ref,
            "booking_method": paid_with,
        },
    )
    for imp in report_dict["impacts"]:
        if not imp.get("proposed_changes"):
            continue
        change_dict = {c["field"]: c["to"] for c in imp["proposed_changes"]}
        update_leg(trip_id, imp["leg_id"], change_dict)

    log_disruption(
        trip_id,
        {
            "disruption_id": f"rec_{leg_id}",
            "affected_leg_id": leg_id,
            "disruption_type": "recovered",
            "details": f"Rebooked to {opt.get('airline','?')} {opt.get('flight_number','?')} (ref {confirmation_ref}).",
            "chosen_alternative": report_dict["replacement_summary"],
            "booking_method": paid_with,
            "new_booking_reference": confirmation_ref,
            "cascade_changes": [
                c for imp in report_dict["impacts"] for c in imp.get("proposed_changes", [])
            ],
        },
    )


# ---------------------------------------------------------------------------
# Page: Dashboard
# ---------------------------------------------------------------------------


def _unseen_disruptions(trip: dict | None) -> list[dict]:
    """Disruptions the user hasn't dismissed yet.

    A disruption is 'unseen' if its disruption_id isn't in session_state's
    seen set and its type is something the user should react to.
    """
    if not trip:
        return []
    seen: set[str] = st.session_state.setdefault("seen_disruptions", set())
    out = []
    for d in trip.get("disruption_history", []):
        if d.get("disruption_type") not in {"cancelled", "delayed", "gate_change"}:
            continue
        if d.get("disruption_id") in seen:
            continue
        out.append(d)
    return out


def render_alert_banner(trip: dict | None) -> None:
    """Animated, attention-grabbing alert at the top of the dashboard."""
    unseen = _unseen_disruptions(trip)
    if not unseen:
        return

    # Show the most recent unseen disruption prominently.
    latest = unseen[-1]
    details = latest.get("details", "A tracked flight has changed status.")
    detected_at = latest.get("detected_at", "")
    dtype = latest.get("disruption_type", "alert").upper()

    st.markdown(
        f"""
        <div class="alert-banner">
          <div class="alert-banner-row">
            <div class="alert-icon">🚨</div>
            <div class="alert-text">
              <div class="alert-title">{dtype} · Flight needs your attention</div>
              <div class="alert-body">{details}</div>
              <div class="alert-time">Detected {detected_at}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, _ = st.columns([2, 1, 4])
    with c1:
        if st.button("See recovery options ↓", type="primary", key="goto_recovery", use_container_width=True):
            # Streamlit can't smooth-scroll natively, but the recovery panel
            # is already below — the button just gives the user a clear next step.
            st.toast("Scroll down to view alternatives.", icon="🚨")
    with c2:
        if st.button("Dismiss", key="dismiss_alert", use_container_width=True):
            seen: set[str] = st.session_state.setdefault("seen_disruptions", set())
            for d in unseen:
                seen.add(d.get("disruption_id", ""))
            st.rerun()

    # Show count of older unseen alerts if any
    if len(unseen) > 1:
        st.caption(f"{len(unseen) - 1} other recent alert(s). View all in disruption history.")


def page_dashboard(trip: dict | None) -> None:
    user_name = st.session_state.get("user", {}).get("name", "Traveller")

    # 🔁 Auto-refresh every 10 seconds so disruptions appear without the user
    # clicking anything. Each refresh re-reads MongoDB and re-evaluates flight
    # status — what would be a continuous background poller in production.
    st_autorefresh(interval=10 * 1000, key="dashboard_autorefresh")

    # Hero
    tracked_flights = []
    if trip:
        tracked_flights = [
            l for l in trip.get("legs", [])
            if l.get("type") == "flight" and l.get("status") in {"scheduled", "rebooked", "in_progress"}
        ]
    live_count = len(tracked_flights)
    now_label = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    st.markdown(
        f"""
        <div class="dashboard-mesh"></div>
        <div style='padding:8px 0 12px;position:relative;z-index:1;'>
            <div style='display:flex;align-items:center;gap:16px;flex-wrap:wrap;'>
                <h1 style='margin:0;font-size:2.2rem;letter-spacing:-0.025em;'>Welcome back, {user_name}.</h1>
                <div style='display:inline-flex;align-items:center;gap:10px;
                            background:linear-gradient(135deg,#DCFCE7 0%,#BBF7D0 100%);
                            border:1px solid #86EFAC;color:#14532D;
                            padding:8px 16px;border-radius:999px;
                            font-size:0.82rem;font-weight:700;letter-spacing:0.04em;
                            box-shadow:0 4px 12px -4px rgba(22, 163, 74, 0.35);'>
                    <span class="live-ping"></span>
                    LIVE · watching {live_count} flight{'s' if live_count != 1 else ''}
                </div>
                <div style='font-size:0.8rem;color:#64748B;'>Last check: {now_label}</div>
            </div>
            <p style='color:#475569;margin:8px 0 0;font-size:1rem;line-height:1.5;'>
                Your itinerary, monitored in real time. SkySaver re-checks every 10 seconds
                and surfaces disruptions the moment they happen.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 🚨 Live disruption alert (slides in, pulses red)
    render_alert_banner(trip)

    if trip is None:
        # ---- Empty state ----
        st.markdown(
            """
            <div style="background:linear-gradient(180deg,#FFFFFF 0%,#F8FAFC 100%);
                        border:1px dashed #C7D2FE;border-radius:18px;
                        padding:48px 32px;text-align:center;margin-top:24px;">
                <div style="font-size:3rem;line-height:1;margin-bottom:14px;">🗺️</div>
                <div style="font-size:1.4rem;font-weight:700;color:#0F172A;
                            letter-spacing:-0.02em;margin-bottom:8px;">
                    No trip yet
                </div>
                <p style="color:#64748B;max-width:520px;margin:0 auto 24px;font-size:0.98rem;">
                    Plan your first trip and SkySaver will watch it 24/7. Or load the
                    demo data to see how the cascade recovery flow works.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2, _ = st.columns([1, 1, 2])
        with c1:
            if st.button("✈ Plan a trip", type="primary", use_container_width=True):
                st.session_state["page"] = PAGE_PLAN
                st.rerun()
        with c2:
            if st.button("🧪 Load demo data", use_container_width=True):
                new_trip = build_demo_trip(days_out=7)
                new_trip["_id"] = current_trip_id()
                user = st.session_state.get("user", {})
                if user.get("email"):
                    new_trip["user_id"] = user["email"]
                save_trip(new_trip)
                st.rerun()
        return

    # Top metrics — coloured stat cards
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    c1.markdown(
        f"<div class='stat-card-grad' style='padding:14px 18px;border-radius:12px;'>"
        f"<div style='color:#4F46E5;font-size:0.75rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;'>Current trip</div>"
        f"<div style='font-size:1.3rem;font-weight:700;color:#0F172A;margin-top:4px;'>{trip['title']}</div>"
        f"<div style='color:#6366F1;font-size:0.8rem;margin-top:4px;'>Trip <code>{trip['_id']}</code></div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    c2.metric("Legs", len(trip["legs"]))
    flights = [l for l in trip["legs"] if l["type"] == "flight"]
    c3.metric("Flights", len(flights))
    disruption_count = len(trip.get("disruption_history", []))
    if disruption_count:
        c4.markdown(
            f"<div class='stat-card-danger' style='padding:14px 18px;border-radius:12px;'>"
            f"<div style='color:#991B1B;font-size:0.75rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;'>Disruptions</div>"
            f"<div style='font-size:1.8rem;font-weight:700;color:#7F1D1D;margin-top:4px;line-height:1;'>{disruption_count}</div>"
            f"<div style='color:#B91C1C;font-size:0.75rem;margin-top:6px;'>Tracked recoveries</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        c4.markdown(
            f"<div class='stat-card-grad' style='padding:14px 18px;border-radius:12px;'>"
            f"<div style='color:#4F46E5;font-size:0.75rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;'>All clear</div>"
            f"<div style='font-size:1.4rem;font-weight:700;color:#0F172A;margin-top:4px;'>0</div>"
            f"<div style='color:#6366F1;font-size:0.75rem;margin-top:6px;'>No disruptions yet</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Rainbow accent under metrics
    st.markdown('<div class="accent-divider"></div>', unsafe_allow_html=True)

    # Calendar export button
    cal1, cal2 = st.columns([1, 5])
    with cal1:
        ics_bytes = trip_to_ics(trip).encode("utf-8")
        st.download_button(
            label="📅  Add to calendar",
            data=ics_bytes,
            file_name=f"skysaver_{trip['_id']}.ics",
            mime="text/calendar",
            use_container_width=True,
            help="Downloads an .ics file you can import into Google Calendar, Apple Calendar, or Outlook.",
        )

    st.markdown("")  # spacer

    # Two columns: itinerary on the left, chat assistant on the right.
    left, right = st.columns([1.6, 1])
    with left:
        st.markdown("### Itinerary")
        for leg in trip["legs"]:
            render_leg_card(leg)

        # Compact preferences summary + edit shortcut, tucked under the itinerary.
        prefs = trip.get("preferences", {})
        with st.expander("⚙ Preferences quick view"):
            rows = [
                ("Direct flights", "Yes" if prefs.get("prefers_direct") else "No"),
                ("Airlines", ", ".join(prefs.get("preferred_airlines", [])) or "—"),
                ("Budget", prefs.get("budget_sensitivity", "medium").title()),
                ("Max layover", f"{prefs.get('max_layover_hours','?')} hours"),
                ("Arrival window", prefs.get("preferred_arrival_window", "any").title()),
            ]
            for label, value in rows:
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;"
                    f"padding:6px 0;border-bottom:1px solid #F1F5F9;font-size:0.88rem;'>"
                    f"<span style='color:#64748B;'>{label}</span>"
                    f"<span style='font-weight:600;text-align:right;color:#0F172A;'>{value}</span></div>",
                    unsafe_allow_html=True,
                )
            if st.button("Edit preferences →", use_container_width=True, key="dash_edit_prefs"):
                st.session_state["page"] = PAGE_PREFS
                st.rerun()

        if trip.get("disruption_history"):
            with st.expander("🕒 Recent activity"):
                for event in trip["disruption_history"][-5:]:
                    kind = event.get("disruption_type", "?")
                    details = event.get("details", "")
                    st.caption(f"**{kind.title()}** — {details}")

    with right:
        render_chat_panel(trip, compact=True)

    render_recovery_panel(trip)
    render_confirmation_dialog()


# ---------------------------------------------------------------------------
# Chat assistant
# ---------------------------------------------------------------------------


def render_chat_panel(trip: dict | None, *, compact: bool = False) -> None:
    """Chat assistant panel.

    When `compact=True`, render a side-rail version sized to fit the dashboard's
    right column (sticky header, scrollable history, chat input pinned).
    """
    if compact:
        st.markdown(
            """
            <div style="background:linear-gradient(135deg,#4F46E5 0%,#8B5CF6 50%,#EC4899 100%);
                        border-radius:14px 14px 0 0;padding:14px 18px;color:#FFFFFF;
                        box-shadow:0 4px 14px -6px rgba(99,102,241,0.45);">
              <div style="font-weight:700;font-size:1.05rem;display:flex;align-items:center;gap:8px;">
                💬 Ask SkySaver
              </div>
              <div style="font-size:0.8rem;opacity:0.9;margin-top:2px;">
                Powered by Gemini · reads trip via MongoDB MCP
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown("## 💬 Ask SkySaver")
        st.markdown(
            '<div class="chat-hint">'
            'I can answer questions about your trip and take you to payment, '
            'booking, or check-in pages. Try: <em>"Take me to book my Uber to '
            'Marina Bay Sands"</em> or <em>"When does my Singapore meeting start?"</em>'
            '</div>',
            unsafe_allow_html=True,
        )

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    # Chat history is wrapped in a styled, scrollable container in compact mode.
    if compact:
        history_open = (
            '<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-top:none;'
            'padding:10px 14px;max-height:520px;overflow-y:auto;'
            'border-radius:0 0 14px 14px;box-shadow:0 1px 3px rgba(15,23,42,0.04);">'
        )
        st.markdown(history_open, unsafe_allow_html=True)

    # Empty state hint
    if compact and not st.session_state["chat_messages"]:
        st.markdown(
            "<div style='padding:10px 4px;color:#64748B;font-size:0.88rem;line-height:1.5;'>"
            "<b>Try asking:</b><br>"
            "• <em>When does my Singapore meeting start?</em><br>"
            "• <em>Take me to book an Uber to my hotel.</em><br>"
            "• <em>What's the buffer if my flight delays 2h?</em>"
            "</div>",
            unsafe_allow_html=True,
        )

    # Replay history
    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if compact:
        st.markdown("</div>", unsafe_allow_html=True)

    if prompt := st.chat_input("Ask SkySaver anything about your trip…"):
        # Append user message
        st.session_state["chat_messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Call Gemini
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                try:
                    response = ask_chatbot(
                        prompt,
                        st.session_state["chat_messages"][:-1],
                        trip,
                    )
                except Exception as exc:  # noqa: BLE001
                    response = (
                        f"I hit an error reaching the model: `{exc}`. "
                        f"Check that your Google Cloud project and ADC are still active."
                    )
                st.markdown(response)
        st.session_state["chat_messages"].append({"role": "assistant", "content": response})


# ---------------------------------------------------------------------------
# Page: Trip details (view + edit individual legs — all fields)
# ---------------------------------------------------------------------------


def _render_finalize_flight_panel(trip: dict, leg: dict) -> None:
    """Inline flight finder for an unbooked leg.

    Workflow:
      1. SkySaver searches live Google Flights options for this leg's route/date,
         pre-filtered by the user's preferences.
      2. We show 5 ranked options inline so the user can scan tradeoffs.
      3. Two buttons per option:
            - "Search this on Google Flights ↗"  → opens Google Flights with the
              exact route + date pre-filled, so the user can complete the booking.
            - "I'll book this one"  → writes the selected option to the leg in
              MongoDB. After the user books on Google Flights and gets a real
              flight number + confirmation, the existing "I booked externally"
              form below stores the final details so SkySaver can track it.
    """
    with st.expander("🔍 Find & finalize this flight (live Google Flights options)", expanded=False):
        st.caption(
            "Tell SkySaver to search options for this leg, pick the one you like, then "
            "complete the booking on Google Flights. Come back with the flight number and "
            "SkySaver will track it for disruptions."
        )

        if not (leg.get("origin") and leg.get("destination") and leg.get("start_at")):
            st.warning("This leg is missing an origin, destination, or start date. Fill those in first.")
            return

        date = leg["start_at"][:10]
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("Search flights", key=f"search_{leg['leg_id']}", type="primary"):
                st.session_state[f"finalize_search_{leg['leg_id']}"] = True
        with c2:
            st.caption(f"Will search {leg['origin']} → {leg['destination']} on {date}.")

        # Always show a direct Google Flights link, even before searching, in case
        # SerpAPI is rate-limited.
        gf_link = google_flights_link(leg["origin"], leg["destination"], date)
        st.link_button(
            f"🔎 Open Google Flights for {leg['origin']} → {leg['destination']} on {date}  ↗",
            gf_link,
            use_container_width=True,
        )

        if not st.session_state.get(f"finalize_search_{leg['leg_id']}"):
            return

        with st.spinner("Querying Google Flights…"):
            options = search_flights(leg["origin"], leg["destination"], date)

        if not options:
            st.warning(
                "No options returned by the search engine for this route/date. "
                "Use the Google Flights link above to browse directly."
            )
            return

        prefs = trip.get("preferences", {})
        ranked = sorted(options, key=lambda o: _score(o, prefs), reverse=True)[:5]
        st.caption(f"Top {len(ranked)} of {len(options)} options, ranked by your preferences.")

        for i, opt in enumerate(ranked, 1):
            stops_label = "Direct" if opt.get("stops", 0) == 0 else f"{opt['stops']} stop"
            duration = opt.get("duration_minutes") or 0
            duration_label = f"{duration // 60}h{duration % 60:02d}m"
            price = opt.get("price_usd", "?")
            airline = opt.get("airline") or "Unknown"

            with st.container(border=True):
                head_l, head_r = st.columns([3, 1])
                with head_l:
                    st.markdown(
                        f"**{airline}**  ·  {opt.get('departure_time','?')} → {opt.get('arrival_time','?')}  "
                        f"·  {duration_label}  ·  {stops_label}"
                    )
                with head_r:
                    st.markdown(
                        f"<div style='text-align:right;font-size:1.3rem;font-weight:700;color:#4F46E5;'>${price}</div>",
                        unsafe_allow_html=True,
                    )

                act_l, act_r = st.columns(2)
                with act_l:
                    if st.button("I'll book this one", key=f"apply_{leg['leg_id']}_{i}", use_container_width=True):
                        enriched = _augment_with_iso(opt, date)
                        update_leg(
                            current_trip_id(),
                            leg["leg_id"],
                            {
                                "airline": opt.get("airline_code") or (opt.get("airline", "") or "")[:2].upper(),
                                "flight_number": opt.get("flight_number", "TBD"),
                                "origin": leg["origin"],
                                "destination": leg["destination"],
                                "start_at": enriched["departure_at_iso"],
                                "end_at": enriched["arrival_at_iso"],
                                "price_usd": opt.get("price_usd"),
                                "status": "scheduled",
                                "booking_method": "selected_pending_payment",
                                "notes": (leg.get("notes", "") + " · Selected via SkySaver finder.").strip(" ·"),
                            },
                        )
                        st.success(
                            f"Saved {airline} option to {leg['leg_id']}. Open Google Flights to complete the booking, "
                            f"then add your real flight number + confirmation in the 'I booked externally' form below."
                        )
                        st.rerun()
                with act_r:
                    st.link_button("Open Google Flights ↗", gf_link, use_container_width=True)


def _render_finalize_hotel_panel(leg: dict) -> None:
    """Inline 'find a stay' for an unbooked hotel leg."""
    with st.expander("🔍 Find & finalize this stay (Booking.com / Airbnb / Google)", expanded=False):
        st.caption(
            "Search live options for this stay. Pick one externally, then come back and "
            "add the confirmation code with 'Apply external booking' below."
        )
        city = leg.get("city") or ""
        name = leg.get("name") or ""
        check_in = leg["start_at"][:10] if leg.get("start_at") else ""
        check_out = leg["end_at"][:10] if leg.get("end_at") else ""

        if not city:
            st.warning("Add a city to this hotel leg first so we can search for stays.")
            return

        from urllib.parse import quote_plus
        booking_q = quote_plus(f"{name} {city}".strip())
        airbnb_q = quote_plus(f"{city}")
        google_q = quote_plus(f"hotels in {city}")

        booking_url = (
            f"https://www.booking.com/search.html?ss={booking_q}"
            + (f"&checkin={check_in}" if check_in else "")
            + (f"&checkout={check_out}" if check_out else "")
        )
        airbnb_url = (
            f"https://www.airbnb.com/s/{airbnb_q}/homes"
            + (f"?checkin={check_in}" if check_in else "")
            + (f"&checkout={check_out}" if check_out else "")
        )
        google_hotels_url = f"https://www.google.com/travel/hotels?q={google_q}"

        c1, c2, c3 = st.columns(3)
        with c1:
            st.link_button("🛏 Booking.com ↗", booking_url, use_container_width=True)
        with c2:
            st.link_button("🏠 Airbnb ↗", airbnb_url, use_container_width=True)
        with c3:
            st.link_button("🔎 Google Hotels ↗", google_hotels_url, use_container_width=True)

        st.caption(
            "After booking, use the editor above to set the name, address, confirmation code, "
            "and total — then SkySaver tracks it like any other leg."
        )


def _render_add_leg_form(trip: dict) -> None:
    leg_type = st.selectbox(
        "Leg type",
        options=["flight", "hotel", "transport", "meeting"],
        format_func=lambda x: f"{LEG_ICON.get(x,'•')} {x.title()}",
        key="new_leg_type",
    )

    with st.form(f"add_leg_form_{leg_type}", clear_on_submit=True):
        common_l, common_r = st.columns(2)
        with common_l:
            new_start = st.text_input("Start (ISO 8601 UTC)", placeholder="2026-06-15T10:00:00Z", key=f"new_start_{leg_type}")
        with common_r:
            new_end = st.text_input("End (ISO 8601 UTC)", placeholder="2026-06-15T18:00:00Z", key=f"new_end_{leg_type}")

        type_specific: dict = {"type": leg_type, "status": "scheduled"}

        if leg_type == "flight":
            c1, c2 = st.columns(2)
            with c1:
                type_specific["airline"] = st.text_input("Airline (IATA, e.g. EK, SQ, BA)", placeholder="EK", key="new_airline")
                origin_label = st.selectbox(
                    "Origin airport",
                    options=[""] + AIRPORT_LABELS,
                    key="new_origin_label",
                )
                type_specific["origin"] = iata_from_label(origin_label)
                type_specific["departure_terminal"] = st.text_input("Departure terminal", key="new_dep_term")
                type_specific["price_usd"] = st.number_input("Price (USD)", min_value=0.0, value=0.0, step=10.0, key="new_price")
            with c2:
                type_specific["flight_number"] = st.text_input("Flight number", placeholder="EK8", key="new_flight_no")
                dest_label = st.selectbox(
                    "Destination airport",
                    options=[""] + AIRPORT_LABELS,
                    key="new_dest_label",
                )
                type_specific["destination"] = iata_from_label(dest_label)
                type_specific["arrival_terminal"] = st.text_input("Arrival terminal", key="new_arr_term")
                type_specific["booking_reference"] = st.text_input("Booking ref", key="new_book_ref")
            type_specific["currency"] = "USD"
            type_specific["stops"] = 0
            type_specific["booking_method"] = "mock"
            type_specific["ticket_class"] = "economy"

        elif leg_type == "hotel":
            c1, c2 = st.columns(2)
            with c1:
                type_specific["name"] = st.text_input("Hotel name", key="new_hotel_name")
                type_specific["city"] = st.text_input("City", key="new_hotel_city")
                type_specific["address"] = st.text_area("Address", key="new_hotel_addr")
            with c2:
                type_specific["total_usd"] = st.number_input("Total (USD)", min_value=0.0, value=0.0, step=10.0, key="new_hotel_total")
                type_specific["nightly_rate_usd"] = st.number_input("Nightly rate (USD)", min_value=0.0, value=0.0, step=10.0, key="new_hotel_rate")
                type_specific["confirmation_code"] = st.text_input("Confirmation code", key="new_hotel_conf")

        elif leg_type == "transport":
            c1, c2 = st.columns(2)
            with c1:
                type_specific["mode"] = st.selectbox(
                    "Mode",
                    options=["taxi", "train", "rental_car", "rideshare", "private_transfer"],
                    key="new_transport_mode",
                )
                type_specific["from"] = st.text_input("From", key="new_transport_from")
            with c2:
                type_specific["to"] = st.text_input("To", key="new_transport_to")
                type_specific["estimated_cost_usd"] = st.number_input("Estimated cost (USD)", min_value=0.0, value=0.0, step=5.0, key="new_transport_cost")

        elif leg_type == "meeting":
            c1, c2 = st.columns(2)
            with c1:
                type_specific["title"] = st.text_input("Title", key="new_meeting_title")
                type_specific["location"] = st.text_input("Location", key="new_meeting_loc")
            with c2:
                type_specific["importance"] = st.selectbox("Importance", options=["low", "medium", "high"], key="new_meeting_importance")
                type_specific["buffer_before_minutes"] = st.number_input("Buffer before (minutes)", min_value=0, value=60, step=15, key="new_meeting_buffer")
            attendees_text = st.text_input("Attendees (comma-separated emails)", key="new_meeting_attendees")
            type_specific["attendees"] = [s.strip() for s in attendees_text.split(",") if s.strip()]

        new_notes = st.text_area("Notes (optional)", key=f"new_notes_{leg_type}")
        type_specific["notes"] = new_notes
        type_specific["start_at"] = new_start
        type_specific["end_at"] = new_end

        if st.form_submit_button("Add to trip", type="primary"):
            if not (new_start and new_end):
                st.error("Start and end times are required.")
                return
            type_specific["leg_id"] = next_leg_id(trip)
            add_leg(current_trip_id(), type_specific)
            st.success(f"Added {type_specific['leg_id']} ({leg_type}) to your trip.")
            st.rerun()


def page_trip_details(trip: dict | None) -> None:
    st.markdown("# Trip details")
    st.caption("View, edit, add, or remove any leg. Changes save instantly to MongoDB.")

    if trip is None:
        st.warning("No trip found.")
        return

    # ---- Add a new leg ----
    with st.expander("➕ Add a new leg (flight, hotel, transport, meeting)"):
        _render_add_leg_form(trip)

    st.markdown("### Existing legs")
    leg_options = [
        (l["leg_id"], f"{LEG_ICON.get(l['type'],'•')}  {l['leg_id']}  ({l['type']})")
        for l in trip["legs"]
    ]
    selected = st.selectbox(
        "Pick a leg",
        options=leg_options,
        format_func=lambda x: x[1],
        key="trip_details_selector",
    )
    leg = next(l for l in trip["legs"] if l["leg_id"] == selected[0])

    st.markdown("#### Current")
    render_leg_card(leg, show_actions=False)

    # ---- Delete button ----
    del_c1, del_c2 = st.columns([1, 5])
    with del_c1:
        if st.button("🗑 Delete this leg", key=f"del_{leg['leg_id']}"):
            delete_leg(current_trip_id(), leg["leg_id"])
            st.success(f"Deleted {leg['leg_id']}.")
            st.rerun()

    # ---- Find & finalize (search live options for unbooked legs) ----
    if leg["type"] == "flight" and not leg.get("booking_reference"):
        _render_finalize_flight_panel(trip, leg)
    if leg["type"] == "hotel" and not leg.get("confirmation_code"):
        _render_finalize_hotel_panel(leg)

    # ---- I booked externally (sync back) ----
    if leg["type"] == "flight":
        with st.expander("🔄 I booked this externally (e.g. on Emirates) — sync the change"):
            st.caption(
                "If you went to the airline's site (or anywhere else) and booked a different flight, "
                "tell SkySaver here. The leg will be updated and the cascade re-applied to your trip."
            )
            with st.form(f"sync_form_{leg['leg_id']}"):
                s1, s2 = st.columns(2)
                with s1:
                    sync_airline = st.text_input("New airline (IATA)", value=leg.get("airline", ""))
                    sync_flight_number = st.text_input("New flight number", value=leg.get("flight_number", ""))
                    sync_price = st.number_input("New price (USD)", min_value=0.0, value=float(leg.get("price_usd") or 0), step=10.0)
                with s2:
                    sync_start = st.text_input("New start (ISO 8601 UTC)", value=leg.get("start_at", ""))
                    sync_end = st.text_input("New end (ISO 8601 UTC)", value=leg.get("end_at", ""))
                    sync_ref = st.text_input("Confirmation reference", value=leg.get("booking_reference", "") or "")

                if st.form_submit_button("Apply external booking", type="primary"):
                    update_leg(current_trip_id(), leg["leg_id"], {
                        "airline": sync_airline,
                        "flight_number": sync_flight_number,
                        "price_usd": sync_price,
                        "start_at": sync_start,
                        "end_at": sync_end,
                        "booking_reference": sync_ref,
                        "status": "rebooked",
                        "booking_method": "external",
                    })
                    log_disruption(current_trip_id(), {
                        "disruption_id": f"ext_{leg['leg_id']}",
                        "affected_leg_id": leg["leg_id"],
                        "disruption_type": "external_sync",
                        "details": f"User reported external booking: {sync_airline}{sync_flight_number} (ref {sync_ref}).",
                        "booking_method": "external",
                        "new_booking_reference": sync_ref,
                        "cascade_changes": [],
                    })
                    st.success("Leg updated with external booking. Cascade will re-compute on next disruption check.")
                    st.rerun()

    st.markdown("### Edit")
    with st.form(f"edit_form_{leg['leg_id']}"):
        common_status_options = ["scheduled", "in_progress", "completed", "disrupted", "cancelled", "rebooked"]
        new_status = st.selectbox(
            "Status",
            options=common_status_options,
            index=common_status_options.index(leg.get("status", "scheduled")),
        )
        new_start = st.text_input("Start (ISO 8601 UTC, e.g. 2026-06-06T10:00:00Z)", value=leg.get("start_at", ""))
        new_end = st.text_input("End (ISO 8601 UTC)", value=leg.get("end_at", ""))

        type_specific: dict = {}
        if leg["type"] == "flight":
            c1, c2 = st.columns(2)
            with c1:
                type_specific["airline"] = st.text_input("Airline (IATA code)", value=leg.get("airline", ""))
                type_specific["origin"] = st.text_input("Origin (IATA)", value=leg.get("origin", ""))
                type_specific["departure_terminal"] = st.text_input("Departure terminal", value=str(leg.get("departure_terminal", "")))
                type_specific["price_usd"] = st.number_input("Price (USD)", value=float(leg.get("price_usd") or 0), min_value=0.0, step=10.0)
            with c2:
                type_specific["flight_number"] = st.text_input("Flight number", value=leg.get("flight_number", ""))
                type_specific["destination"] = st.text_input("Destination (IATA)", value=leg.get("destination", ""))
                type_specific["arrival_terminal"] = st.text_input("Arrival terminal", value=str(leg.get("arrival_terminal", "")))
                type_specific["booking_reference"] = st.text_input("Booking ref", value=leg.get("booking_reference", "") or "")
        elif leg["type"] == "hotel":
            c1, c2 = st.columns(2)
            with c1:
                type_specific["name"] = st.text_input("Hotel name", value=leg.get("name", ""))
                type_specific["city"] = st.text_input("City", value=leg.get("city", ""))
                type_specific["address"] = st.text_area("Address", value=leg.get("address", ""))
            with c2:
                type_specific["total_usd"] = st.number_input("Total (USD)", value=float(leg.get("total_usd") or 0), min_value=0.0, step=10.0)
                type_specific["nightly_rate_usd"] = st.number_input("Nightly rate (USD)", value=float(leg.get("nightly_rate_usd") or 0), min_value=0.0, step=10.0)
                type_specific["confirmation_code"] = st.text_input("Confirmation code", value=leg.get("confirmation_code", ""))
        elif leg["type"] == "transport":
            c1, c2 = st.columns(2)
            with c1:
                type_specific["mode"] = st.selectbox(
                    "Mode",
                    options=["taxi", "train", "rental_car", "rideshare", "private_transfer"],
                    index=["taxi", "train", "rental_car", "rideshare", "private_transfer"].index(leg.get("mode", "taxi")),
                )
                type_specific["from"] = st.text_input("From", value=leg.get("from", ""))
            with c2:
                type_specific["to"] = st.text_input("To", value=leg.get("to", ""))
                type_specific["estimated_cost_usd"] = st.number_input("Estimated cost (USD)", value=float(leg.get("estimated_cost_usd") or 0), min_value=0.0, step=5.0)
        elif leg["type"] == "meeting":
            c1, c2 = st.columns(2)
            with c1:
                type_specific["title"] = st.text_input("Title", value=leg.get("title", ""))
                type_specific["location"] = st.text_input("Location", value=leg.get("location", ""))
            with c2:
                type_specific["importance"] = st.selectbox(
                    "Importance",
                    options=["low", "medium", "high"],
                    index=["low", "medium", "high"].index(leg.get("importance", "medium")),
                )
                type_specific["buffer_before_minutes"] = st.number_input(
                    "Buffer before (minutes)",
                    value=int(leg.get("buffer_before_minutes", 60)),
                    min_value=0, step=15,
                )
            attendees_text = st.text_input(
                "Attendees (comma-separated emails)",
                value=", ".join(leg.get("attendees", [])),
            )
            type_specific["attendees"] = [s.strip() for s in attendees_text.split(",") if s.strip()]

        new_notes = st.text_area("Notes", value=leg.get("notes", ""))

        if st.form_submit_button("Save changes", type="primary"):
            payload = {
                "status": new_status,
                "start_at": new_start,
                "end_at": new_end,
                "notes": new_notes,
                **type_specific,
            }
            update_leg(current_trip_id(), leg["leg_id"], payload)
            st.success(f"Updated {leg['leg_id']}.")
            st.rerun()


# ---------------------------------------------------------------------------
# Page: Preferences
# ---------------------------------------------------------------------------


def page_preferences(trip: dict | None) -> None:
    st.markdown("# Preferences")
    st.caption(
        "Tell SkySaver what matters to you — across flights, hotels, and ground transport. "
        "These drive how it ranks alternatives during disruption recovery."
    )

    if trip is None:
        st.warning("No trip found.")
        return

    prefs = trip.get("preferences", {})

    tabs = st.tabs(["✈ Flights", "🏨 Hotels", "🚖 Ground transport"])

    with st.form("prefs_form"):
        # ---- Tab: Flights ----
        with tabs[0]:
            f1, f2 = st.columns(2)
            with f1:
                prefers_direct = st.toggle("Prefer direct flights", value=prefs.get("prefers_direct", True))
                seat_class = st.selectbox(
                    "Seat class",
                    options=["economy", "premium_economy", "business", "first"],
                    index=["economy", "premium_economy", "business", "first"].index(prefs.get("seat_class", "economy")),
                )
                carry_on = st.number_input(
                    "Carry-on bags", min_value=0, max_value=4,
                    value=int(prefs.get("carry_on_bags", 1)),
                )
                checked_bags = st.number_input(
                    "Checked bags", min_value=0, max_value=8,
                    value=int(prefs.get("checked_bags", 1)),
                )
            with f2:
                max_layover_hours = st.slider(
                    "Max layover (hours)", min_value=0, max_value=12,
                    value=int(prefs.get("max_layover_hours", 4)),
                )
                arrival_window = st.selectbox(
                    "Preferred arrival window",
                    options=["any", "morning", "afternoon", "evening"],
                    index=["any", "morning", "afternoon", "evening"].index(prefs.get("preferred_arrival_window", "any")),
                )
                meal_pref = st.selectbox(
                    "Meal preference",
                    options=["any", "vegetarian", "vegan", "halal", "kosher", "gluten_free"],
                    index=["any", "vegetarian", "vegan", "halal", "kosher", "gluten_free"].index(prefs.get("meal_preference", "any")),
                )
                seat_pref = st.selectbox(
                    "Seat preference",
                    options=["any", "window", "aisle", "extra_legroom"],
                    index=["any", "window", "aisle", "extra_legroom"].index(prefs.get("seat_preference", "any")),
                )

            preferred_airlines = st.text_input(
                "Preferred airlines (IATA codes, comma-separated)",
                value=", ".join(prefs.get("preferred_airlines", [])),
            )
            avoid_airlines = st.text_input(
                "Avoid these airlines (IATA codes, comma-separated)",
                value=", ".join(prefs.get("avoid_airlines", [])),
            )
            loyalty_text = st.text_input(
                "Frequent flyer numbers (e.g. SQ=KrisFlyer-123, EK=Skywards-456)",
                value=", ".join(f"{k}={v}" for k, v in prefs.get("loyalty_programs", {}).items()),
            )

        # ---- Tab: Hotels ----
        with tabs[1]:
            h1, h2 = st.columns(2)
            with h1:
                min_stars = st.slider(
                    "Minimum hotel rating (stars)", min_value=1, max_value=5,
                    value=int(prefs.get("hotel_min_stars", 4)),
                )
                room_type = st.selectbox(
                    "Preferred room type",
                    options=["standard", "deluxe", "suite", "executive"],
                    index=["standard", "deluxe", "suite", "executive"].index(prefs.get("hotel_room_type", "standard")),
                )
                breakfast_included = st.toggle("Breakfast included", value=prefs.get("hotel_breakfast", True))
            with h2:
                bed_type = st.selectbox(
                    "Bed type",
                    options=["any", "king", "queen", "twin"],
                    index=["any", "king", "queen", "twin"].index(prefs.get("hotel_bed_type", "any")),
                )
                smoking = st.toggle("Smoking room OK", value=prefs.get("hotel_smoking_ok", False))
                quiet_floor = st.toggle("Prefer quiet floor", value=prefs.get("hotel_quiet_floor", True))

            hotel_chains = st.text_input(
                "Preferred hotel chains (e.g. Marriott, Hilton, Hyatt)",
                value=", ".join(prefs.get("preferred_hotel_chains", [])),
            )
            hotel_loyalty = st.text_input(
                "Hotel loyalty programs (e.g. Marriott=Bonvoy-789)",
                value=", ".join(f"{k}={v}" for k, v in prefs.get("hotel_loyalty", {}).items()),
            )

        # ---- Tab: Ground transport ----
        with tabs[2]:
            g1, g2 = st.columns(2)
            with g1:
                preferred_ride_app = st.selectbox(
                    "Preferred ride-share app",
                    options=["uber", "lyft", "ola", "bolt", "grab", "didi", "none"],
                    index=["uber", "lyft", "ola", "bolt", "grab", "didi", "none"].index(prefs.get("preferred_ride_app", "uber")),
                )
                uber_tier = st.selectbox(
                    "Preferred ride tier",
                    options=["economy", "comfort", "premium", "shared", "xl"],
                    index=["economy", "comfort", "premium", "shared", "xl"].index(prefs.get("preferred_ride_tier", "comfort")),
                )
            with g2:
                accepts_public_transit = st.toggle("Public transit OK", value=prefs.get("accepts_public_transit", True))
                rental_car_ok = st.toggle("Rental car OK", value=prefs.get("rental_car_ok", False))
                max_ride_cost = st.slider(
                    "Max ride cost (USD)", min_value=10, max_value=200,
                    value=int(prefs.get("max_ride_cost_usd", 60)), step=5,
                )

        # Budget sensitivity now lives on Flights tab; notifications + currency
        # were moved to Settings.
        budget_sensitivity = prefs.get("budget_sensitivity", "medium")
        trip_currency = prefs.get("currency", "USD")
        notify_email = prefs.get("notify_email", True)
        notify_sms = prefs.get("notify_sms", False)
        auto_book_low_risk = prefs.get("auto_book_low_risk", False)

        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.form_submit_button("Save all preferences", type="primary"):
            # Parse loyalty strings into dicts
            def _parse_kv(text: str) -> dict:
                out = {}
                for pair in text.split(","):
                    pair = pair.strip()
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        out[k.strip()] = v.strip()
                return out

            new_prefs = {
                **prefs,
                # Flights
                "prefers_direct": prefers_direct,
                "seat_class": seat_class,
                "carry_on_bags": int(carry_on),
                "checked_bags": int(checked_bags),
                "checked_baggage": int(checked_bags) > 0,  # legacy boolean
                "max_layover_hours": max_layover_hours,
                "preferred_arrival_window": arrival_window,
                "meal_preference": meal_pref,
                "seat_preference": seat_pref,
                "preferred_airlines": [s.strip().upper() for s in preferred_airlines.split(",") if s.strip()],
                "avoid_airlines": [s.strip().upper() for s in avoid_airlines.split(",") if s.strip()],
                "loyalty_programs": _parse_kv(loyalty_text),
                # Hotels
                "hotel_min_stars": min_stars,
                "hotel_room_type": room_type,
                "hotel_breakfast": breakfast_included,
                "hotel_bed_type": bed_type,
                "hotel_smoking_ok": smoking,
                "hotel_quiet_floor": quiet_floor,
                "preferred_hotel_chains": [s.strip() for s in hotel_chains.split(",") if s.strip()],
                "hotel_loyalty": _parse_kv(hotel_loyalty),
                # Ground transport
                "preferred_ride_app": preferred_ride_app,
                "preferred_ride_tier": uber_tier,
                "accepts_public_transit": accepts_public_transit,
                "rental_car_ok": rental_car_ok,
                "max_ride_cost_usd": max_ride_cost,
                # General
                "budget_sensitivity": budget_sensitivity,
                "currency": trip_currency,
                "notify_email": notify_email,
                "notify_sms": notify_sms,
                "auto_book_low_risk": auto_book_low_risk,
            }
            trip["preferences"] = new_prefs
            save_trip(trip)
            st.success("All preferences saved.")
            st.rerun()


# ---------------------------------------------------------------------------
# Page: Users (signups overview)
# ---------------------------------------------------------------------------


def page_settings() -> None:
    st.markdown("# Settings")
    st.caption("Your account, your data, and where it lives.")

    user = st.session_state.get("user", {}) or {}

    # ---- Your account ----
    st.markdown("### Your account")
    with st.container(border=True):
        st.markdown(
            f"<div style='display:grid;grid-template-columns:160px 1fr;gap:10px 22px;font-size:0.95rem;'>"
            f"<div style='color:#64748B;'>Name</div><div style='font-weight:600;'>{user.get('name','—')}</div>"
            f"<div style='color:#64748B;'>Email</div><div style='font-weight:600;'>{user.get('email','—')}</div>"
            f"<div style='color:#64748B;'>Account created</div><div>{user.get('created_at','—')}</div>"
            f"<div style='color:#64748B;'>Last sign-in</div><div>{user.get('last_login_at','—')}</div>"
            f"<div style='color:#64748B;'>Sign-ins to date</div><div>{user.get('login_count','—')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ---- Notifications + general (moved here from Preferences) ----
    trip = get_trip(current_trip_id())
    prefs = (trip or {}).get("preferences", {}) if trip else {}
    st.markdown("### Notifications & general")
    with st.form("settings_general_form"):
        c1, c2 = st.columns(2)
        with c1:
            notify_email = st.toggle("Email notifications", value=prefs.get("notify_email", True))
            notify_sms = st.toggle("SMS notifications", value=prefs.get("notify_sms", False))
        with c2:
            currency = st.selectbox(
                "Currency",
                ["USD", "EUR", "GBP", "INR", "SGD", "AED"],
                index=["USD", "EUR", "GBP", "INR", "SGD", "AED"].index(prefs.get("currency", "USD")),
            )
            auto_book_low_risk = st.toggle(
                "Auto-book low-risk recoveries",
                value=prefs.get("auto_book_low_risk", False),
                help="If on, SkySaver books replacement flights without your approval when the cascade is clean.",
            )
        if st.form_submit_button("Save", type="primary"):
            if trip:
                prefs.update({
                    "notify_email": notify_email,
                    "notify_sms": notify_sms,
                    "currency": currency,
                    "auto_book_low_risk": auto_book_low_risk,
                })
                trip["preferences"] = prefs
                save_trip(trip)
                st.success("Saved.")
                st.rerun()
            else:
                st.warning("Create a trip first so these settings have somewhere to live.")

    # ---- Database access ----
    users = list_users()
    total_logins = sum(int(u.get("login_count", 0)) for u in users)

    st.markdown("### Database")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total signups", len(users))
    c2.metric("Total sign-ins", total_logins)
    active_today = sum(1 for u in users if (u.get("last_login_at") or "").startswith(_to_iso(datetime.now(timezone.utc))[:10]))
    c3.metric("Active today", active_today)

    st.markdown(
        "<div style='color:#64748B;font-size:0.92rem;margin-top:6px;'>"
        "Browse in MongoDB Atlas: <code>cloud.mongodb.com</code> → "
        "<b>SkySaverAI</b> cluster → <b>Browse Collections</b> → "
        "<code>skysaver.users</code> and <code>skysaver.trips</code>."
        "</div>",
        unsafe_allow_html=True,
    )

    with st.expander("View all signups (admin)"):
        if not users:
            st.info("No users yet.")
        else:
            rows = []
            for u in users:
                rows.append({
                    "Name": u.get("name", ""),
                    "Email": u.get("email", ""),
                    "Signed up": u.get("created_at", ""),
                    "Last sign-in": u.get("last_login_at", "") or "—",
                    "Sign-ins": u.get("login_count", 0),
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Page: Plan a trip (comprehensive intake form)
# ---------------------------------------------------------------------------


def page_plan_trip() -> None:
    st.markdown("# Plan a new trip")
    st.caption(
        "Tell SkySaver about your trip — destinations, dates, who's coming, what you're carrying, where you're staying — "
        "and it'll seed your itinerary. You can edit any leg afterwards."
    )

    user = st.session_state.get("user", {})

    # Pre-fill from landing-page quick-start (if it was used).
    qs = st.session_state.pop("quickstart_pending", None)
    if qs:
        st.success(
            f"Continuing from your quick start: {qs['from']} → {qs['to']} on {qs['when']} · "
            f"{qs['travelers']} traveler(s)."
        )

    purpose_default_options = ["Business", "Leisure", "Family visit", "Conference", "Honeymoon", "Other"]
    purpose_index = purpose_default_options.index(qs["purpose"]) if (qs and qs.get("purpose") in purpose_default_options) else 0

    with st.form("plan_trip_form", clear_on_submit=False):
        st.markdown("### Basics")
        b1, b2 = st.columns([2, 1])
        with b1:
            default_title = f"{qs['from']} → {qs['to']} trip" if qs else ""
            title = st.text_input("Trip title", value=default_title, placeholder="Singapore Q3 Review Trip")
            purpose = st.selectbox("Trip purpose", purpose_default_options, index=purpose_index)
        with b2:
            currency = st.selectbox("Currency", ["USD", "EUR", "GBP", "INR", "SGD", "AED"], index=0)
            budget_total = st.number_input("Total budget (approximate)", min_value=0, value=2500, step=100)

        st.markdown("### Where")
        w1, w2, w3 = st.columns([2, 3, 1])
        with w1:
            # Pre-fill from quickstart if it looks like an IATA we know
            qs_from_label = label_from_iata(qs.get("from", "")) if qs else None
            origin_label = st.selectbox(
                "Home / origin airport",
                options=[""] + AIRPORT_LABELS,
                index=(AIRPORT_LABELS.index(qs_from_label) + 1) if qs_from_label in AIRPORT_LABELS else 0,
                help="Start typing a city or airport name — autocomplete will find the right IATA code.",
            )
        with w2:
            # Multi-select destinations
            qs_to_default: list[str] = []
            if qs:
                t = label_from_iata(qs.get("to", ""))
                if t:
                    qs_to_default = [t]
            destination_labels = st.multiselect(
                "Destinations (pick one or more)",
                options=AIRPORT_LABELS,
                default=qs_to_default,
                help="Type a city to filter the list. Add multiple destinations for a multi-leg trip.",
            )
        with w3:
            return_to_origin = st.toggle("Return to origin?", value=True)

        # Translate the rich labels back into raw IATA codes
        origin = iata_from_label(origin_label)
        destinations_iata = [iata_from_label(d) for d in destination_labels]
        destinations = ", ".join(destinations_iata)

        st.markdown("### When")
        d1, d2 = st.columns(2)
        with d1:
            depart_date = st.date_input("Departure date")
            depart_time = st.time_input("Departure time (UTC)")
        with d2:
            return_date = st.date_input("Return date")
            return_time = st.time_input("Return time (UTC)")

        st.markdown("### Who's coming")
        p1, p2, p3 = st.columns(3)
        with p1:
            adults = st.number_input("Adults", min_value=1, max_value=10, value=1)
        with p2:
            children = st.number_input("Children", min_value=0, max_value=10, value=0)
        with p3:
            infants = st.number_input("Infants", min_value=0, max_value=4, value=0)

        st.markdown("### What you're carrying")
        l1, l2, l3 = st.columns(3)
        with l1:
            carry_on = st.number_input("Carry-on bags (total)", min_value=0, max_value=20, value=int(adults))
        with l2:
            checked = st.number_input("Checked bags (total)", min_value=0, max_value=20, value=int(adults))
        with l3:
            special_items = st.text_input("Special items (golf clubs, instruments, pets...)", placeholder="")

        st.markdown("### Flight preferences for this trip")
        f1, f2 = st.columns(2)
        with f1:
            seat_class = st.selectbox("Cabin", ["economy", "premium_economy", "business", "first"])
            prefers_direct = st.toggle("Prefer direct flights", value=True)
        with f2:
            preferred_airlines = st.text_input("Preferred airlines (IATA)", placeholder="SQ, EK")
            avoid_airlines = st.text_input("Avoid airlines", placeholder="")

        st.markdown("### Stay")
        h1, h2, h3 = st.columns(3)
        with h1:
            stay_type = st.selectbox(
                "Stay type",
                ["Hotel", "AirBnB / vacation rental", "Hostel", "Staying with family/friends", "Don't need a stay"],
            )
            need_hotel = stay_type != "Don't need a stay"
            hotel_min_stars = st.slider("Minimum stars (hotels)", 1, 5, 4)
        with h2:
            preferred_hotel = st.text_input("Specific stay (optional)", placeholder="Marina Bay Sands or 1BR near Bayfront")
            preferred_hotel_city = st.text_input("Stay city", placeholder="Singapore")
        with h3:
            nightly_budget = st.number_input("Max nightly rate", min_value=0, value=400, step=25)
            breakfast = st.toggle("Breakfast included (hotels)", value=True)

        st.markdown("### Ground transport at destination")
        g1, g2, g3 = st.columns(3)
        with g1:
            need_transport = st.toggle("I'll need ground transport", value=True)
            transport_mode = st.selectbox(
                "Primary mode",
                ["Ride-share (Uber/Lyft/Ola/etc.)", "Rental car", "Public transit", "Mix of the above", "I'll figure it out"],
            )
        with g2:
            preferred_ride_app = st.selectbox("Preferred ride app", ["uber", "lyft", "ola", "bolt", "grab", "didi", "none"])
            ride_tier = st.selectbox("Ride tier", ["economy", "comfort", "premium", "shared", "xl"])
        with g3:
            airport_pickup = st.text_input("Airport pickup destination", placeholder="Hotel address or area")
            max_ride_cost = st.number_input("Max ride cost (one-way)", min_value=0, value=60, step=5)

        # ---- Attractions (leisure trips) ----
        purpose_is_leisure = purpose.lower() in {"leisure", "family visit", "honeymoon"}
        if purpose_is_leisure:
            st.markdown("### Attractions")
            a1, a2 = st.columns([1, 2])
            with a1:
                want_attractions = st.toggle("Suggest things to see/do", value=True)
            with a2:
                activity_interests = st.multiselect(
                    "What are you into?",
                    ["Museums", "Food", "Nightlife", "Nature/parks", "Beaches", "Hiking", "Shopping", "History", "Music/concerts", "Sports", "Family-friendly"],
                    default=["Food", "Museums"],
                )
        else:
            want_attractions = False
            activity_interests = []

        st.markdown("### Meetings (one per line: `YYYY-MM-DD HH:MM | Title | Location`)")
        meetings_text = st.text_area(
            "Meetings",
            placeholder="2026-06-09 10:00 | Q3 review with Acme | Acme Singapore HQ\n2026-06-10 14:00 | Customer dinner | Marina Bay",
            height=100,
        )

        st.markdown("### Anything else")
        notes = st.text_area("Notes for SkySaver", placeholder="e.g. flexible on dates ±2 days, prefer morning arrivals…")

        submitted = st.form_submit_button("Create trip", type="primary")
        if submitted:
            if not all([title.strip(), origin.strip(), destinations.strip()]):
                st.error("Title, origin, and destinations are required.")
                return
            depart_dt = datetime.combine(depart_date, depart_time, tzinfo=timezone.utc)
            return_dt = datetime.combine(return_date, return_time, tzinfo=timezone.utc)
            duration_days = max(1, (return_dt - depart_dt).days)
            new_trip = _build_trip_from_intake(
                title=title,
                origin=origin,
                destinations=[d.strip().upper() for d in destinations.split(",") if d.strip()],
                depart_dt=depart_dt,
                return_dt=return_dt,
                duration_days=duration_days,
                return_to_origin=return_to_origin,
                adults=int(adults),
                children=int(children),
                infants=int(infants),
                carry_on=int(carry_on),
                checked=int(checked),
                special_items=special_items,
                seat_class=seat_class,
                prefers_direct=prefers_direct,
                preferred_airlines=[s.strip().upper() for s in preferred_airlines.split(",") if s.strip()],
                avoid_airlines=[s.strip().upper() for s in avoid_airlines.split(",") if s.strip()],
                stay_type=stay_type,
                need_hotel=need_hotel,
                hotel_min_stars=int(hotel_min_stars),
                preferred_hotel=preferred_hotel,
                preferred_hotel_city=preferred_hotel_city,
                nightly_budget=int(nightly_budget),
                breakfast=breakfast,
                need_transport=need_transport,
                transport_mode=transport_mode,
                preferred_ride_app=preferred_ride_app,
                ride_tier=ride_tier,
                airport_pickup=airport_pickup,
                max_ride_cost=int(max_ride_cost),
                want_attractions=want_attractions,
                activity_interests=activity_interests,
                meetings_text=meetings_text,
                notes=notes,
                purpose=purpose,
                currency=currency,
                budget_total=int(budget_total),
                user_id=user.get("email", "user_demo"),
            )
            save_trip(new_trip)
            st.success(f"Trip `{new_trip['_id']}` created with {len(new_trip['legs'])} legs.")
            st.session_state["page"] = PAGE_DASHBOARD
            st.rerun()


def _build_trip_from_intake(**k) -> dict:
    """Turn the intake form values into a full trip document."""
    legs: list[dict] = []
    leg_n = 1

    def _next_id() -> str:
        nonlocal leg_n
        lid = f"leg_{leg_n:03d}"
        leg_n += 1
        return lid

    # Outbound flights — one leg per destination hop
    current_origin = k["origin"].upper()
    cumulative = k["depart_dt"]
    for dest in k["destinations"]:
        legs.append({
            "leg_id": _next_id(),
            "type": "flight",
            "status": "scheduled",
            "start_at": _to_iso(cumulative),
            "end_at": _to_iso(cumulative + timedelta(hours=7)),
            "airline": (k["preferred_airlines"][0] if k["preferred_airlines"] else "TBD"),
            "flight_number": "TBD",
            "origin": current_origin,
            "destination": dest,
            "stops": 0,
            "duration_minutes": 420,
            "price_usd": 0,
            "currency": k["currency"],
            "booking_reference": None,
            "booking_method": "pending",
            "ticket_class": k["seat_class"],
            "notes": "Auto-generated from intake. Edit in Trip details.",
        })
        current_origin = dest
        cumulative = cumulative + timedelta(hours=10)

    # Stay at the final destination (hotel, airbnb, hostel, with friends, or skipped)
    if k["need_hotel"]:
        stay_type = k.get("stay_type", "Hotel")
        legs.append({
            "leg_id": _next_id(),
            "type": "hotel",
            "status": "scheduled",
            "start_at": _to_iso(cumulative),
            "end_at": _to_iso(k["return_dt"] - timedelta(hours=4)),
            "name": k["preferred_hotel"] or f"TBD {stay_type.split()[0].lower()}",
            "stay_type": stay_type,
            "city": k["preferred_hotel_city"] or (k["destinations"][-1] if k["destinations"] else ""),
            "address": "",
            "confirmation_code": "",
            "nightly_rate_usd": k["nightly_budget"],
            "total_usd": k["nightly_budget"] * max(1, (k["return_dt"] - cumulative).days),
            "notes": f"Stay type: {stay_type}. Breakfast: {'included' if k['breakfast'] else 'not included'}.",
        })

    # Ground transport from airport to hotel
    if k["need_transport"]:
        mode_label = (k.get("transport_mode") or "Ride-share").lower()
        mode = "rideshare"
        if "rental" in mode_label:
            mode = "rental_car"
        elif "public" in mode_label:
            mode = "train"
        legs.append({
            "leg_id": _next_id(),
            "type": "transport",
            "status": "scheduled",
            "start_at": _to_iso(cumulative + timedelta(minutes=20)),
            "end_at": _to_iso(cumulative + timedelta(minutes=70)),
            "mode": mode,
            "from": f"{k['destinations'][-1] if k['destinations'] else 'Airport'} terminal",
            "to": k["airport_pickup"] or k["preferred_hotel"] or "Hotel",
            "estimated_cost_usd": k.get("max_ride_cost", 35),
            "notes": f"Mode: {k.get('transport_mode','?')}. App: {k['preferred_ride_app']}, tier: {k['ride_tier']}.",
        })

    # Meetings
    for line in (k["meetings_text"] or "").splitlines():
        if not line.strip() or "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            continue
        when_str = parts[0]
        meeting_title = parts[1] if len(parts) > 1 else "Meeting"
        meeting_loc = parts[2] if len(parts) > 2 else ""
        try:
            when_dt = datetime.fromisoformat(when_str.replace(" ", "T")).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        legs.append({
            "leg_id": _next_id(),
            "type": "meeting",
            "status": "scheduled",
            "start_at": _to_iso(when_dt),
            "end_at": _to_iso(when_dt + timedelta(hours=1)),
            "title": meeting_title,
            "location": meeting_loc,
            "attendees": [],
            "importance": "medium",
            "buffer_before_minutes": 60,
            "notes": "",
        })

    # Return flight
    if k["return_to_origin"] and k["destinations"]:
        legs.append({
            "leg_id": _next_id(),
            "type": "flight",
            "status": "scheduled",
            "start_at": _to_iso(k["return_dt"]),
            "end_at": _to_iso(k["return_dt"] + timedelta(hours=8)),
            "airline": (k["preferred_airlines"][0] if k["preferred_airlines"] else "TBD"),
            "flight_number": "TBD",
            "origin": k["destinations"][-1],
            "destination": k["origin"].upper(),
            "stops": 0,
            "duration_minutes": 480,
            "price_usd": 0,
            "currency": k["currency"],
            "booking_reference": None,
            "booking_method": "pending",
            "ticket_class": k["seat_class"],
            "notes": "Auto-generated. Edit in Trip details.",
        })

    # Optional: a single "Explore the city" placeholder meeting for leisure trips,
    # so the dashboard surfaces "things to see" once we wire attractions data.
    if k.get("want_attractions"):
        legs.append({
            "leg_id": _next_id(),
            "type": "meeting",
            "status": "scheduled",
            "start_at": _to_iso(cumulative + timedelta(hours=24)),
            "end_at": _to_iso(cumulative + timedelta(hours=28)),
            "title": f"Explore {k['destinations'][-1] if k['destinations'] else 'the city'}",
            "location": k["preferred_hotel_city"] or (k['destinations'][-1] if k['destinations'] else ""),
            "attendees": [],
            "importance": "low",
            "buffer_before_minutes": 30,
            "notes": f"Interests: {', '.join(k.get('activity_interests', []))}. SkySaver will suggest attractions matching these.",
        })

    # Trip ID — per-user.
    trip_id = current_trip_id()
    return {
        "_id": trip_id,
        "user_id": k["user_id"],
        "title": k["title"],
        "status": "active",
        "purpose": k["purpose"],
        "duration_days": k.get("duration_days", 1),
        "travelers": {
            "adults": k["adults"],
            "children": k["children"],
            "infants": k["infants"],
        },
        "luggage": {
            "carry_on": k["carry_on"],
            "checked": k["checked"],
            "special_items": k["special_items"],
        },
        "budget_total_usd": k["budget_total"],
        "preferences": {
            "prefers_direct": k["prefers_direct"],
            "seat_class": k["seat_class"],
            "carry_on_bags": k["carry_on"],
            "checked_bags": k["checked"],
            "checked_baggage": k["checked"] > 0,
            "max_layover_hours": 4,
            "preferred_arrival_window": "any",
            "preferred_airlines": k["preferred_airlines"],
            "avoid_airlines": k["avoid_airlines"],
            "stay_type": k.get("stay_type", "Hotel"),
            "hotel_min_stars": k["hotel_min_stars"],
            "hotel_breakfast": k["breakfast"],
            "transport_mode": k.get("transport_mode", ""),
            "preferred_ride_app": k["preferred_ride_app"],
            "preferred_ride_tier": k["ride_tier"],
            "max_ride_cost_usd": k.get("max_ride_cost", 60),
            "want_attractions": k.get("want_attractions", False),
            "activity_interests": k.get("activity_interests", []),
            "budget_sensitivity": "medium",
            "currency": k["currency"],
        },
        "legs": legs,
        "disruption_history": [],
        "intake_notes": k["notes"],
    }


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_sidebar(trip: dict | None) -> None:
    user = st.session_state.get("user", {})
    with st.sidebar:
        st.markdown("## SkySaver AI")
        st.caption("Autonomous travel recovery agent")

        if user:
            st.markdown(
                f"<div style='padding:12px 14px;background:#FFFFFF;border:1px solid #E2E8F0;"
                f"border-radius:10px;margin-top:8px;'>"
                f"<div style='font-weight:600;color:#0F172A;'>{user.get('name','?')}</div>"
                f"<div style='color:#64748B;font-size:0.85rem;margin-top:2px;'>{user.get('email','?')}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            if st.button("Log out", use_container_width=True):
                # Revoke the persistent token so the URL link no longer works.
                token = st.session_state.get("session_token") or st.query_params.get("session")
                if token:
                    delete_session_token(token)
                try:
                    del st.query_params["session"]
                except KeyError:
                    pass
                st.session_state["authenticated"] = False
                st.session_state["user"] = None
                st.session_state["session_token"] = None
                st.rerun()

        # 🔔 Notification bell — pulses red dot when there are unseen disruptions
        unseen = _unseen_disruptions(trip)
        if unseen:
            st.markdown(
                f"<div class='notif-bell' style='margin-top:10px;'>"
                f"<span class='dot'></span> 🔔 {len(unseen)} new alert(s)"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown("---")
        page = st.radio(
            "Navigate",
            PAGES,
            index=PAGES.index(st.session_state.get("page", PAGE_DASHBOARD)),
            label_visibility="collapsed",
        )
        st.session_state["page"] = page

        st.markdown("---")

        # 🔍 Live tracking — the user shouldn't need to do anything for normal use.
        st.markdown("### Live tracking")
        st.caption(
            "Dashboard auto-refreshes every 10 seconds. When any tracked flight's "
            "status flips to cancelled or disrupted in MongoDB, SkySaver detects it "
            "and fires an alert on the next refresh — no clicking required."
        )

        with st.expander("🧪 Demo simulator (for recording the demo only)"):
            st.caption(
                "In production a flight-status API like FlightAware or Cirium would "
                "feed the cancellation. For the hackathon video, use the trigger below "
                "and watch the dashboard auto-detect it within 10 seconds."
            )
            if st.button("🧪 Load demo data into my trip", use_container_width=True):
                new_trip = build_demo_trip(days_out=7)
                new_trip["_id"] = current_trip_id()
                user = st.session_state.get("user", {})
                if user.get("email"):
                    new_trip["user_id"] = user["email"]
                save_trip(new_trip)
                st.success("Demo data loaded.")
                st.rerun()

            if trip:
                flight_legs = [l for l in trip["legs"] if l["type"] == "flight" and l["status"] == "scheduled"]
                if flight_legs:
                    target = st.selectbox(
                        "Simulate cancellation on:",
                        options=[(l["leg_id"], _flight_label(l) + " " + l["origin"] + "→" + l["destination"]) for l in flight_legs],
                        format_func=lambda x: x[1],
                        key="cancel_target",
                    )
                    if st.button("⚠ Simulate airline cancellation", use_container_width=True):
                        update_leg(current_trip_id(), target[0], {"status": "cancelled"})
                        leg = next(l for l in trip["legs"] if l["leg_id"] == target[0])
                        ts = int(datetime.now(timezone.utc).timestamp())
                        log_disruption(
                            current_trip_id(),
                            {
                                "disruption_id": f"dis_{target[0]}_{ts}",
                                "affected_leg_id": target[0],
                                "disruption_type": "cancelled",
                                "details": f"{_flight_label(leg)} cancelled by airline.",
                            },
                        )
                        st.warning(
                            f"Simulated cancellation of {_flight_label(leg)}. "
                            f"Open the Dashboard — the alert will pulse in within 10s."
                        )
                        st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _restore_session_from_url() -> None:
    """If the URL contains a valid session token, hydrate session_state from it.

    The token is stored as ?session=... in the URL, set by the login form on a
    successful sign-in. This means a browser reload, server restart, or new tab
    opened from the existing URL all keep the user logged in for ~30 days.
    """
    if st.session_state.get("authenticated"):
        return
    token = st.query_params.get("session")
    if not token:
        return
    user = lookup_session_token(token)
    if user is None:
        # Stale or invalid token — wipe it.
        try:
            del st.query_params["session"]
        except KeyError:
            pass
        return
    st.session_state["user"] = user
    st.session_state["authenticated"] = True
    st.session_state["session_token"] = token


def main() -> None:
    st.set_page_config(
        page_title="SkySaver AI",
        page_icon="✈",
        layout="wide",
    )
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("page", PAGE_DASHBOARD)

    # 🔑 Auto-login if the URL has a valid session token
    _restore_session_from_url()

    if not st.session_state["authenticated"]:
        render_auth()
        return

    trip = get_trip(current_trip_id())
    render_sidebar(trip)

    page = st.session_state.get("page", PAGE_DASHBOARD)
    if page == PAGE_DASHBOARD:
        page_dashboard(trip)
    elif page == PAGE_TRIP:
        page_trip_details(trip)
    elif page == PAGE_PLAN:
        page_plan_trip()
    elif page == PAGE_PREFS:
        page_preferences(trip)
    elif page == PAGE_SETTINGS:
        page_settings()


if __name__ == "__main__":
    main()
