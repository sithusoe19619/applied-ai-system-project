from html import escape

import streamlit as st


THEME_CSS = """
<style>
:root {
    --paw-ink: #1f2933;
    --paw-muted: #5c6b75;
    --paw-line: rgba(31, 41, 51, 0.10);
    --paw-panel: rgba(255, 251, 246, 0.92);
    --paw-panel-strong: rgba(255, 255, 255, 0.96);
    --paw-accent: #1f6f63;
    --paw-accent-dark: #154f48;
    --paw-warm: #d47f4e;
    --paw-warm-dark: #b55f31;
    --paw-soft: #f6ebdf;
    --paw-shadow: 0 22px 55px rgba(31, 41, 51, 0.08);
}

.stApp {
    color: var(--paw-ink);
    background:
        radial-gradient(circle at top right, rgba(212, 127, 78, 0.16), transparent 28%),
        radial-gradient(circle at top left, rgba(31, 111, 99, 0.10), transparent 24%),
        linear-gradient(180deg, #fbf6ef 0%, #f1f5ef 100%);
}

[data-testid="stAppViewContainer"] {
    background: transparent;
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stToolbar"] {
    right: 1rem;
}

.block-container {
    max-width: 980px;
    padding-top: 1.25rem;
    padding-bottom: 2.8rem;
}

h1, h2, h3 {
    color: var(--paw-ink);
    letter-spacing: -0.02em;
}

h1 {
    font-size: 2.45rem;
    line-height: 1.02;
    margin-bottom: 0.35rem;
}

h2 {
    font-size: 1.55rem;
    margin-top: 0.2rem;
}

h3 {
    font-size: 1.15rem;
}

p, li, label {
    color: var(--paw-ink);
}

.paw-hero {
    padding: 0.1rem 0 0.2rem 0;
}

.paw-eyebrow {
    margin: 0 0 0.55rem 0;
    font-size: 0.78rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--paw-accent);
}

.paw-subtitle {
    margin: 0;
    max-width: 48rem;
    font-size: 1.02rem;
    line-height: 1.65;
    color: var(--paw-muted);
}

.paw-card-heading {
    margin-bottom: 0.95rem;
}

.paw-card-heading h3 {
    margin: 0;
    font-size: 1.32rem;
    line-height: 1.2;
    font-weight: 800;
    letter-spacing: -0.025em;
    color: var(--paw-accent-dark);
}

.paw-card-copy {
    margin: 0.28rem 0 0 0;
    color: var(--paw-muted);
    font-size: 0.93rem;
    line-height: 1.5;
}

.paw-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    margin: 0.85rem 0 0.2rem 0;
}

.paw-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.38rem 0.78rem;
    border-radius: 999px;
    border: 1px solid rgba(31, 41, 51, 0.10);
    background: rgba(255, 255, 255, 0.82);
    color: var(--paw-ink);
    font-size: 0.84rem;
    font-weight: 600;
}

.paw-note {
    padding: 0.78rem 0.95rem;
    border-radius: 18px;
    border: 1px solid rgba(31, 111, 99, 0.12);
    background: rgba(31, 111, 99, 0.08);
    color: var(--paw-ink);
    font-size: 0.93rem;
    line-height: 1.55;
}

.paw-note strong {
    color: var(--paw-accent-dark);
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 24px;
    border: 1px solid var(--paw-line);
    background: var(--paw-panel);
    box-shadow: 0 14px 36px rgba(31, 41, 51, 0.06);
}

div[data-testid="stVerticalBlockBorderWrapper"] > div {
    background: transparent;
}

div.stButton > button {
    border-radius: 999px;
    min-height: 2.95rem;
    padding: 0.7rem 1.05rem;
    font-weight: 700;
    font-size: 0.94rem;
    letter-spacing: -0.01em;
    transition: transform 0.14s ease, box-shadow 0.14s ease, border-color 0.14s ease;
}

div.stButton > button:hover,
div[data-testid="stPageLink"] a:hover {
    transform: translateY(-1px);
}

div.stButton > button[kind="primary"] {
    color: #ffffff !important;
    background: linear-gradient(135deg, #155b52 0%, #0f3f39 100%);
    border: none;
    box-shadow: 0 14px 32px rgba(21, 79, 72, 0.25);
}

div.stButton > button[kind="primary"] * {
    color: #ffffff !important;
    fill: #ffffff !important;
}

div.stButton > button[kind="secondary"] {
    color: var(--paw-ink);
    background: rgba(255, 255, 255, 0.88);
    border: 1px solid rgba(31, 41, 51, 0.12);
}

div[data-testid="stPageLink"] a {
    display: inline-flex;
    width: 100%;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    min-height: 2.95rem;
    padding: 0.7rem 1.05rem;
    border-radius: 999px;
    border: none;
    background: linear-gradient(135deg, var(--paw-warm) 0%, var(--paw-warm-dark) 100%);
    color: #fff7f1;
    font-weight: 700;
    font-size: 0.92rem;
    line-height: 1;
    text-align: center;
    white-space: nowrap;
    text-decoration: none;
    box-shadow: 0 14px 32px rgba(181, 95, 49, 0.24);
}

div[data-testid="stPageLink"] a * {
    color: #fff7f1 !important;
    fill: #fff7f1 !important;
    white-space: nowrap !important;
    min-width: 0;
}

div[data-testid="stVerticalBlock"]:has(.paw-results-plan-stack) {
    gap: 1rem;
}

div[data-testid="stVerticalBlock"]:has(.paw-results-plan-stack) > div.element-container:has(.paw-results-plan-stack) {
    display: none;
}

.paw-plan-summary {
    margin: 0 0 1rem 0;
    font-size: 1rem;
    line-height: 1.6;
    color: var(--paw-muted);
}

.paw-profile-summary {
    margin: 0.2rem 0 1rem 0;
    color: var(--paw-muted);
    font-size: 0.95rem;
    line-height: 1.6;
}

.paw-profile-section-title {
    margin: 0;
    color: var(--paw-accent-dark);
    font-size: 1.16rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    line-height: 1.25;
}

.paw-priority-groups {
    display: grid;
    gap: 0.75rem;
    margin-top: 0.75rem;
}

.paw-priority-group {
    padding: 0.85rem 0.95rem;
    border-radius: 16px;
    border: 1px solid rgba(31, 41, 51, 0.08);
    background: rgba(255, 255, 255, 0.7);
}

.paw-priority-group-title {
    margin: 0;
    color: var(--paw-accent-dark);
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}

.paw-priority-group-list {
    margin: 0.55rem 0 0 0;
    padding-left: 1.15rem;
}

.paw-priority-group-list li + li {
    margin-top: 0.45rem;
}

.paw-priority-group-list li {
    color: var(--paw-ink);
    font-size: 0.94rem;
    line-height: 1.6;
}

.paw-task-card {
    padding: 1rem 1.05rem;
    border-radius: 20px;
    border: 1px solid rgba(31, 41, 51, 0.08);
    background: rgba(255, 255, 255, 0.78);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.82);
}

.paw-task-card + .paw-task-card {
    margin-top: 0.8rem;
}

.paw-task-card-header {
    display: flex;
    align-items: flex-start;
    gap: 0.9rem;
}

.paw-time-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 4.25rem;
    padding: 0.42rem 0.75rem;
    border-radius: 999px;
    background: rgba(21, 79, 72, 0.10);
    color: var(--paw-accent-dark);
    font-size: 0.84rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    white-space: nowrap;
}

.paw-task-card-copy {
    flex: 1;
    min-width: 0;
}

.paw-task-card-copy h4 {
    margin: 0;
    color: var(--paw-ink);
    font-size: 1.06rem;
    line-height: 1.35;
}

.paw-task-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-top: 0.55rem;
}

.paw-task-chip {
    display: inline-flex;
    align-items: center;
    padding: 0.26rem 0.68rem;
    border-radius: 999px;
    background: rgba(246, 235, 223, 0.88);
    border: 1px solid rgba(212, 127, 78, 0.16);
    color: var(--paw-ink);
    font-size: 0.8rem;
    font-weight: 600;
}

.paw-task-support {
    margin: 0.8rem 0 0 0;
    color: var(--paw-muted);
    font-size: 0.93rem;
    line-height: 1.6;
}

.paw-task-list {
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
}

.paw-task-list-item {
    padding: 0.95rem 1rem;
    border-radius: 18px;
    border: 1px solid rgba(31, 41, 51, 0.08);
    background: rgba(255, 255, 255, 0.76);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.paw-task-list-header {
    display: flex;
    align-items: flex-start;
    gap: 0.8rem;
}

.paw-task-list-copy {
    flex: 1;
    min-width: 0;
}

.paw-secondary-time-pill {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 3.65rem;
    padding: 0.34rem 0.64rem;
    border-radius: 999px;
    background: rgba(21, 79, 72, 0.08);
    color: var(--paw-accent-dark);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    white-space: nowrap;
}

.paw-task-list-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: 0.45rem;
}

.paw-task-list-title,
.paw-task-list-note,
.paw-section-empty {
    margin: 0;
}

.paw-task-list-title {
    color: var(--paw-ink);
    font-size: 0.98rem;
    font-weight: 700;
    line-height: 1.4;
}

.paw-task-chip-secondary {
    background: rgba(255, 255, 255, 0.88);
    border-color: rgba(31, 41, 51, 0.10);
    font-size: 0.78rem;
}

.paw-task-list-note {
    margin-top: 0.6rem;
    color: var(--paw-ink);
    font-size: 0.9rem;
    line-height: 1.55;
}

.paw-section-empty {
    color: var(--paw-muted);
    font-size: 0.95rem;
    line-height: 1.6;
}

div[data-testid="stTextInputRootElement"] input,
div[data-baseweb="base-input"] input,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] textarea,
div[data-baseweb="input"] input {
    background: rgba(255, 255, 255, 0.92);
    border-radius: 16px;
}

div[data-baseweb="textarea"] textarea {
    min-height: 132px;
}

label[data-testid="stWidgetLabel"] p {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--paw-ink);
}

div[data-testid="stCaptionContainer"] p {
    color: var(--paw-muted);
}

div[data-testid="metric-container"] {
    border-radius: 18px;
    border: 1px solid rgba(31, 41, 51, 0.08);
    background: var(--paw-panel-strong);
    padding: 0.9rem 1rem;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

div[data-testid="stMetricLabel"] p {
    font-size: 0.92rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 800;
    color: var(--paw-accent-dark);
}

div[data-testid="stMetricValue"] {
    font-size: 1.55rem;
    color: var(--paw-ink);
}

div[data-testid="stAlert"] {
    border-radius: 18px;
}

div[data-testid="stExpander"] {
    border-radius: 18px;
    overflow: hidden;
    border: 1px solid rgba(31, 41, 51, 0.10);
    background: rgba(255, 255, 255, 0.76);
}

div[data-testid="stTable"] table {
    border-radius: 16px;
    overflow: hidden;
}

@media (max-width: 900px) {
    .block-container {
        max-width: 100%;
        padding-top: 0.9rem;
        padding-bottom: 2.1rem;
    }

    h1 {
        font-size: 2.05rem;
    }

    .paw-card-heading h3 {
        font-size: 1.2rem;
    }

    .paw-profile-section-title {
        font-size: 1.05rem;
    }

    div[data-testid="stMetricLabel"] p {
        font-size: 0.84rem;
    }

    .paw-task-card-header {
        flex-direction: column;
        gap: 0.7rem;
    }

    .paw-task-list-header {
        flex-direction: column;
        gap: 0.65rem;
    }

    .paw-time-pill {
        min-width: 0;
    }

    .paw-secondary-time-pill {
        min-width: 0;
    }
}
</style>
"""


def apply_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def render_page_intro(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="paw-hero">
            <p class="paw-eyebrow">{escape(eyebrow)}</p>
            <h1>{escape(title)}</h1>
            <p class="paw-subtitle">{escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_card_heading(title: str, body: str = "") -> None:
    body_markup = f'<p class="paw-card-copy">{escape(body)}</p>' if body else ""
    st.markdown(
        f"""
        <div class="paw-card-heading">
            <h3>{escape(title)}</h3>
            {body_markup}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_badges(labels: list[str]) -> None:
    badge_markup = "".join(f'<span class="paw-badge">{escape(label)}</span>' for label in labels if label)
    if not badge_markup:
        return
    st.markdown(f'<div class="paw-badges">{badge_markup}</div>', unsafe_allow_html=True)

def render_results_plan_stack_marker() -> None:
    st.markdown('<div class="paw-results-plan-stack" aria-hidden="true"></div>', unsafe_allow_html=True)


def render_note(text: str, title: str = "") -> None:
    prefix = f"<strong>{escape(title)}</strong> " if title else ""
    st.markdown(f'<div class="paw-note">{prefix}{escape(text)}</div>', unsafe_allow_html=True)
