import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os
import datetime
import pytz

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Trading Comps",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    [data-testid="stSidebar"] {
        background: #f8f7f4;
        border-right: 1px solid #e4e2db;
    }
    [data-testid="stSidebar"] .stRadio label {
        font-size: 12px !important;
        color: #374151 !important;
        padding: 2px 0 !important;
    }
    [data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] p {
        font-size: 12px !important;
    }

    .top-bar {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border-radius: 10px; padding: 18px 28px; margin-bottom: 20px;
        display: flex; align-items: center; justify-content: space-between;
    }
    .top-bar .badge {
        background: rgba(245,158,11,0.22); color: #fbbf24; border-radius: 20px;
        padding: 4px 12px; font-size: 12px; font-weight: 600;
        border: 1px solid rgba(245,158,11,0.38);
    }
    .note-text { font-size: 11px; color: #94a3b8; margin-bottom: 8px; }

    [data-testid="stDataFrame"] {
        border: 1px solid #e4e2db; border-radius: 8px; overflow: hidden;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px; background: #f1efe8; border-radius: 8px; padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 13px; font-weight: 500; border-radius: 6px; padding: 6px 16px;
    }
    .stTabs [aria-selected="true"] {
        background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .footer-note {
        font-size: 11px; color: #94a3b8; text-align: right;
        margin-top: 8px; padding-top: 8px; border-top: 1px solid #e4e2db;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Universe — loaded from CSV ────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
UNIVERSE_CSV = os.path.join(_HERE, "universe.csv")


@st.cache_data(show_spinner=False)
def load_universe():
    return pd.read_csv(UNIVERSE_CSV)


@st.cache_data(show_spinner=False)
def get_ticker_metadata():
    df = load_universe()
    return {
        row["ticker"]: {
            "name":       row["name"],
            "sector":     row["sector"],
            "sub_sector": row["sub_sector"],
            "country":    row["listing_country"],
            "exchange":   row["exchange"],
        }
        for _, row in df.iterrows()
    }


# ── Cache TTL: expire after 6 pm ET each day ──────────────────────────────────
def _seconds_until_next_6pm_et():
    et = pytz.timezone("America/New_York")
    now_et = datetime.datetime.now(et)
    target = now_et.replace(hour=18, minute=0, second=0, microsecond=0)
    if now_et >= target:
        target += datetime.timedelta(days=1)
    return max(int((target - now_et).total_seconds()), 60)


@st.cache_data(ttl=_seconds_until_next_6pm_et(), show_spinner=False)
def fetch_metrics(tickers: tuple) -> dict:
    import yfinance as yf

    results = {}
    for ticker in tickers:
        try:
            info      = yf.Ticker(ticker).info
            price     = info.get("currentPrice") or info.get("regularMarketPrice")
            mc        = info.get("marketCap")
            ev        = info.get("enterpriseValue")
            ebitda    = info.get("ebitda")
            revenue   = info.get("totalRevenue")
            rev_gr    = info.get("revenueGrowth")
            gross_mgn = info.get("grossMargins")
            ebitda_mgn= info.get("ebitdaMargins")
            w52hi     = info.get("fiftyTwoWeekHigh")
            fwd_pe    = info.get("forwardPE")
            trail_pe  = info.get("trailingPE")
            cagr      = info.get("earningsGrowth") or rev_gr
            ntm_ebitda= (revenue * ebitda_mgn) if revenue and ebitda_mgn else None

            ntm_ev_ebitda = (ev / ntm_ebitda) if ev and ntm_ebitda else None
            ltm_ev_ebitda = (ev / ebitda)     if ev and ebitda     else None

            # GA EV/EBITDA = EV/EBITDA multiple / revenue growth rate
            # e.g. 15x EV/EBITDA at 15% growth = 1.0x
            def _ga(multiple, growth):
                if multiple and growth and growth > 0:
                    return multiple / (growth * 100)
                return None

            results[ticker] = {
                "market_cap":       mc,
                "tev":              ev,
                "pct_52w_hi":       (price / w52hi) if price and w52hi and w52hi > 0 else None,
                "ntm_ev_ebitda":    ntm_ev_ebitda,
                "ntm_ga_ev_ebitda": _ga(ntm_ev_ebitda, rev_gr),
                "ltm_ev_ebitda":    ltm_ev_ebitda,
                "ltm_ga_ev_ebitda": _ga(ltm_ev_ebitda, rev_gr),
                "pe_ntm":           fwd_pe,
                "pe_ltm":           trail_pe,
                "ntm_rev_growth":   rev_gr,
                "cagr_3y":          cagr,
                "gross_margin":     gross_mgn,
                "ebitda_margin":    ebitda_mgn,
                "rule_of_40":       ((rev_gr or 0) * 100) + ((ebitda_mgn or 0) * 100),
            }
        except Exception:
            results[ticker] = {
                k: None for k in [
                    "market_cap", "tev", "pct_52w_hi",
                    "ntm_ev_ebitda", "ntm_ga_ev_ebitda",
                    "ltm_ev_ebitda", "ltm_ga_ev_ebitda",
                    "pe_ntm", "pe_ltm",
                    "ntm_rev_growth", "cagr_3y",
                    "gross_margin", "ebitda_margin", "rule_of_40",
                ]
            }
    return results


# ── Column definitions ────────────────────────────────────────────────────────
COLUMN_GROUPS = {
    "Market Data": {
        "cols": ["Mkt Cap ($M)", "TEV ($M)", "% 52W Hi"],
        "bg": "#f1f5f9", "fg": "#334155",
    },
    "NTM Multiples": {
        "cols": ["NTM EV/EBITDA", "NTM P/E"],
        "bg": "#fef3c7", "fg": "#92400e",
    },
    "LTM Multiples": {
        "cols": ["LTM EV/EBITDA", "LTM P/E"],
        "bg": "#e2e8f0", "fg": "#475569",
    },
    "Growth Adjusted": {
        "cols": ["NTM GA EV/EBITDA", "LTM GA EV/EBITDA"],
        "bg": "#fde8d8", "fg": "#9a3412",
    },
    "Growth & Margins": {
        "cols": ["NTM Rev Gr%", "3Y CAGR", "Gross Mgn", "EBITDA Mgn", "Rule of 40"],
        "bg": "#f0fdf4", "fg": "#166534",
    },
}

PCT_COLS   = ["% 52W Hi", "NTM Rev Gr%", "3Y CAGR", "Gross Mgn", "EBITDA Mgn"]
MULTI_COLS = ["NTM EV/EBITDA", "NTM P/E", "LTM EV/EBITDA", "LTM P/E",
              "NTM GA EV/EBITDA", "LTM GA EV/EBITDA"]
CURR_COLS  = ["Mkt Cap ($M)", "TEV ($M)"]

# Fixed widths (px) so columns never shift layout
COL_WIDTHS = {
    "Company":            200,
    "Ticker":              60,
    "Mkt Cap ($M)":        90,
    "TEV ($M)":            90,
    "% 52W Hi":            72,
    "NTM EV/EBITDA":       90,
    "NTM P/E":             72,
    "LTM EV/EBITDA":       90,
    "LTM P/E":             72,
    "NTM GA EV/EBITDA":   110,
    "LTM GA EV/EBITDA":   110,
    "NTM Rev Gr%":         80,
    "3Y CAGR":             72,
    "Gross Mgn":           72,
    "EBITDA Mgn":          80,
    "Rule of 40":          72,
}


# ── Table builder ─────────────────────────────────────────────────────────────
def build_comps_table(metrics, ticker_meta):
    rows = []
    for ticker, m in metrics.items():
        meta = ticker_meta.get(ticker, {})
        mc   = m.get("market_cap")
        tev  = m.get("tev")
        rows.append({
            "Company":           meta.get("name", ticker),
            "Ticker":            ticker,
            "Sub Sector":        meta.get("sub_sector", ""),
            "Mkt Cap ($M)":      mc / 1e6 if mc else None,
            "TEV ($M)":          tev / 1e6 if tev else None,
            "% 52W Hi":          m.get("pct_52w_hi"),
            "NTM EV/EBITDA":     m.get("ntm_ev_ebitda"),
            "NTM P/E":           m.get("pe_ntm"),
            "LTM EV/EBITDA":     m.get("ltm_ev_ebitda"),
            "LTM P/E":           m.get("pe_ltm"),
            "NTM GA EV/EBITDA":  m.get("ntm_ga_ev_ebitda"),
            "LTM GA EV/EBITDA":  m.get("ltm_ga_ev_ebitda"),
            "NTM Rev Gr%":       m.get("ntm_rev_growth"),
            "3Y CAGR":           m.get("cagr_3y"),
            "Gross Mgn":         m.get("gross_margin"),
            "EBITDA Mgn":        m.get("ebitda_margin"),
            "Rule of 40":        m.get("rule_of_40"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("TEV ($M)", ascending=False, na_position="last").reset_index(drop=True)
    return df


def compute_stats(df):
    all_cols = [c for g in COLUMN_GROUPS.values() for c in g["cols"]]
    out = {}
    for col in all_cols:
        if col not in df.columns:
            out[col] = {"mean": None, "median": None}
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        out[col] = {
            "mean":   float(s.mean())   if len(s) else None,
            "median": float(s.median()) if len(s) else None,
        }
    return out


# ── Formatting ────────────────────────────────────────────────────────────────
def _fmt(v, kind):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if kind == "pct":
        return f"{v * 100:.0f}%"
    if kind == "mult":
        return f"{v:.1f}x"
    if kind == "r40":
        return f"{v:.0f}"
    if kind == "curr":
        return f"${v / 1000:.1f}B" if abs(v) >= 1000 else f"${v:.0f}M"
    return str(v)


def apply_formats(df):
    d = df.copy()
    for c in PCT_COLS:
        if c in d.columns:
            d[c] = d[c].apply(lambda v: _fmt(v, "pct"))
    for c in MULTI_COLS:
        if c in d.columns:
            d[c] = d[c].apply(lambda v: _fmt(v, "mult"))
    if "Rule of 40" in d.columns:
        d["Rule of 40"] = d["Rule of 40"].apply(lambda v: _fmt(v, "r40"))
    for c in CURR_COLS:
        if c in d.columns:
            d[c] = d[c].apply(lambda v: _fmt(v, "curr"))
    return d


def build_stats_row(stats, display_cols, label, key):
    row = {"Company": label, "Ticker": ""}
    for col in display_cols:
        v = stats.get(col, {}).get(key)
        if v is None:
            row[col] = ""
        elif col in PCT_COLS:
            row[col] = f"{v * 100:.0f}%"
        elif col in MULTI_COLS:
            row[col] = f"{v:.1f}x"
        elif col == "Rule of 40":
            row[col] = f"{v:.0f}"
        elif col in CURR_COLS:
            row[col] = ""
        else:
            row[col] = f"{v:.1f}"
    return row


# ── Column group header HTML ──────────────────────────────────────────────────
def group_header_html(display_cols):
    fixed = '<th colspan="2" style="background:#f1efe8; border:none; min-width:260px;"></th>'
    groups = ""
    for name, g in COLUMN_GROUPS.items():
        visible = [c for c in g["cols"] if c in display_cols]
        if not visible:
            continue
        w = sum(COL_WIDTHS.get(c, 80) for c in visible)
        groups += (
            '<th colspan="{n}" style="background:{bg}; color:{fg}; font-size:11px;'
            " font-weight:700; text-align:center; padding:5px 8px;"
            " border-left:2px solid #e2e8f0; letter-spacing:0.05em;"
            ' min-width:{w}px;">'
            "{label}</th>"
        ).format(n=len(visible), bg=g["bg"], fg=g["fg"], label=name.upper(), w=w)
    return (
        '<table style="width:100%; border-collapse:collapse; table-layout:fixed;">'
        "<tr>{fixed}{groups}</tr></table>"
    ).format(fixed=fixed, groups=groups)


# ── Charts ────────────────────────────────────────────────────────────────────
def bar_chart(df, col, title, color_scale):
    d = df.copy()
    d[col] = pd.to_numeric(d[col], errors="coerce")
    d = d.dropna(subset=[col]).head(25)
    if d.empty:
        st.info(f"No {col} data available.")
        return
    fig = px.bar(d, x="Ticker", y=col, color=col,
                 color_continuous_scale=color_scale, title=title)
    fig.update_layout(
        plot_bgcolor="white", paper_bgcolor="white", coloraxis_showscale=False,
        xaxis=dict(tickangle=45, gridcolor="#f1f5f9"),
        yaxis=dict(gridcolor="#f1f5f9"),
        margin=dict(l=40, r=20, t=50, b=80), height=360,
        font=dict(family="Inter, sans-serif", size=12),
    )
    fig.update_traces(marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True)


def scatter_chart(df):
    d = df.copy()
    d["NTM Rev Gr%"] = pd.to_numeric(d["NTM Rev Gr%"], errors="coerce")
    d["EBITDA Mgn"]  = pd.to_numeric(d["EBITDA Mgn"],  errors="coerce")
    d = d.dropna(subset=["NTM Rev Gr%", "EBITDA Mgn"])
    if d.empty:
        st.info("Insufficient data for scatter plot.")
        return
    fig = px.scatter(d, x="NTM Rev Gr%", y="EBITDA Mgn", text="Ticker",
                     title="Revenue Growth vs EBITDA Margin",
                     color_discrete_sequence=["#d97706"])
    fig.update_traces(textposition="top center", textfont_size=10,
                      marker=dict(size=8, line=dict(width=1, color="white")))
    fig.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        xaxis=dict(tickformat=".0%", gridcolor="#f1f5f9"),
        yaxis=dict(tickformat=".0%", gridcolor="#f1f5f9"),
        margin=dict(l=40, r=20, t=50, b=40), height=420,
        font=dict(family="Inter, sans-serif", size=12),
    )
    st.plotly_chart(fig, use_container_width=True)


def treemap_chart(df):
    d = df.copy()
    d["Mkt Cap ($M)"] = pd.to_numeric(d["Mkt Cap ($M)"], errors="coerce")
    d = d[d["Mkt Cap ($M)"] > 0].dropna(subset=["Mkt Cap ($M)"])
    if d.empty:
        st.info("No market cap data available.")
        return
    fig = px.treemap(d, path=["Sub Sector", "Ticker"], values="Mkt Cap ($M)",
                     title="Market Cap by Sub Sector", color="Mkt Cap ($M)",
                     color_continuous_scale=["#fef3c7", "#d97706"])
    fig.update_layout(font=dict(family="Inter, sans-serif", size=12),
                      paper_bgcolor="white", height=420,
                      margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)


# ── Load static data ──────────────────────────────────────────────────────────
universe_df = load_universe()
ticker_meta  = get_ticker_metadata()
all_sectors  = sorted(universe_df["sector"].unique().tolist())


# ── Sidebar — clean, no filters, no display controls ─────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='padding:10px 0 6px 0;'>"
        "<div style='font-size:14px;font-weight:600;color:#1e293b;letter-spacing:-0.01em;'>"
        "Trading Comps</div>"
        "<div style='font-size:11px;color:#94a3b8;margin-top:1px;'>"
        "Services Universe · US &amp; UK</div>"
        "</div>"
        "<hr style='border:none;border-top:1px solid #e4e2db;margin:8px 0 12px 0;'>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div style='font-size:10px;font-weight:600;color:#94a3b8;"
        "letter-spacing:0.08em;text-transform:uppercase;margin-bottom:6px;'>"
        "Sector</div>",
        unsafe_allow_html=True,
    )
    selected_sector = st.radio(
        "sector",
        ["All Sectors"] + all_sectors,
        index=0,
        label_visibility="collapsed",
    )

    st.markdown(
        "<hr style='border:none;border-top:1px solid #e4e2db;margin:14px 0;'>",
        unsafe_allow_html=True,
    )

    # Universe summary card
    sdf  = universe_df if selected_sector == "All Sectors" else universe_df[universe_df["sector"] == selected_sector]
    n_us = len(sdf[sdf["listing_country"] == "US"])
    n_uk = len(sdf[sdf["listing_country"] == "UK"])

    et       = pytz.timezone("America/New_York")
    now_et   = datetime.datetime.now(et)
    next_ref = now_et.replace(hour=18, minute=0, second=0, microsecond=0)
    if now_et >= next_ref:
        next_ref += datetime.timedelta(days=1)
    refresh_str = next_ref.strftime("%-I:%M %p ET, %b %-d")

    st.markdown(
        "<div style='background:#f1efe8;border-radius:6px;padding:10px 12px;'>"
        "<div style='font-size:10px;color:#94a3b8;font-weight:600;letter-spacing:0.06em;"
        "text-transform:uppercase;margin-bottom:6px;'>Universe</div>"
        "<div style='display:flex;justify-content:space-between;margin-bottom:3px;'>"
        "<span style='font-size:11px;color:#64748b;'>Companies</span>"
        f"<span style='font-size:11px;font-weight:600;color:#1e293b;'>{len(sdf)}</span></div>"
        "<div style='display:flex;justify-content:space-between;margin-bottom:3px;'>"
        "<span style='font-size:11px;color:#64748b;'>US listed</span>"
        f"<span style='font-size:11px;font-weight:600;color:#d97706;'>{n_us}</span></div>"
        "<div style='display:flex;justify-content:space-between;'>"
        "<span style='font-size:11px;color:#64748b;'>UK listed</span>"
        f"<span style='font-size:11px;font-weight:600;color:#d97706;'>{n_uk}</span></div>"
        "<div style='border-top:1px solid #e4e2db;margin-top:8px;padding-top:6px;"
        "font-size:10px;color:#94a3b8;'>Next refresh: "
        f"{refresh_str}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


# ── Filter universe ───────────────────────────────────────────────────────────
if selected_sector == "All Sectors":
    filtered_df = universe_df.copy()
else:
    filtered_df = universe_df[universe_df["sector"] == selected_sector].copy()

tickers_to_load = tuple(filtered_df["ticker"].tolist())


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    "<div class='top-bar'>"
    "<div>"
    "<div style='font-size:10px;color:#94a3b8;font-weight:500;"
    "letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px;'>"
    "Services Universe · US &amp; UK</div>"
    f"<div style='color:white;font-size:22px;font-weight:700;letter-spacing:-0.02em;'>"
    f"{selected_sector}</div>"
    "<div style='color:#cbd5e1;font-size:12px;margin-top:4px;'>"
    "All financials in millions ($M). Sorted by TEV descending. "
    "Data refreshes daily after 6 pm ET.</div>"
    "</div>"
    f"<span class='badge'>{len(tickers_to_load)} companies</span>"
    "</div>",
    unsafe_allow_html=True,
)

if not tickers_to_load:
    st.warning("No companies found for the selected sector.")
    st.stop()


# ── Fetch ─────────────────────────────────────────────────────────────────────
with st.spinner(f"Loading market data for {len(tickers_to_load)} companies..."):
    metrics = fetch_metrics(tickers_to_load)


# ── Build table ───────────────────────────────────────────────────────────────
raw_df = build_comps_table(metrics, ticker_meta)
stats  = compute_stats(raw_df)

all_val_cols = [c for g in COLUMN_GROUPS.values() for c in g["cols"]]
display_cols = ["Company", "Ticker"] + [c for c in all_val_cols if c in raw_df.columns]
display_df   = raw_df[display_cols].copy()


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_table, tab_charts, tab_universe = st.tabs(
    ["Comps Table", "Charts", "Universe"]
)


# ── Tab 1: Table ──────────────────────────────────────────────────────────────
with tab_table:
    st.markdown(group_header_html(display_cols), unsafe_allow_html=True)

    # Company rows — sorted by TEV descending
    formatted = apply_formats(display_df)

    # Stats rows always appended at the bottom, not sortable
    mean_row   = build_stats_row(stats, display_cols, "— Mean —",   "mean")
    median_row = build_stats_row(stats, display_cols, "— Median —", "median")

    full = pd.concat(
        [formatted, pd.DataFrame([mean_row, median_row])],
        ignore_index=True,
    )
    full = full[display_cols].fillna("")

    last  = len(full) - 1
    penul = len(full) - 2

    def highlight_rows(row):
        if row.name == last:
            return [
                "background-color:#f1efe8; font-style:italic; "
                "color:#374151; border-top:2px solid #e4e2db;"
            ] * len(row)
        if row.name == penul:
            return [
                "background-color:#fffbeb; font-style:italic; "
                "color:#374151; border-top:2px solid #e4e2db;"
            ] * len(row)
        return [""] * len(row)

    # Column width config for st.dataframe
    col_config = {
        col: st.column_config.TextColumn(col, width=COL_WIDTHS.get(col, 80))
        for col in display_cols
    }

    styled = (
        full.style
        .apply(highlight_rows, axis=1)
        .set_properties(**{
            "font-size":    "12px",
            "padding":      "4px 8px",
            "white-space":  "nowrap",
        })
        .set_table_styles([
            {"selector": "thead th", "props": [
                ("font-size", "11px"), ("font-weight", "700"),
                ("text-align", "center"), ("padding", "6px 8px"),
                ("border-bottom", "2px solid #e4e2db"),
                ("background-color", "#f1efe8"),
            ]},
            {"selector": "tbody tr:nth-child(-n+{})".format(len(full) - 2) + ":nth-child(even)",
             "props": [("background-color", "#f8f7f4")]},
            {"selector": "tbody tr:hover",
             "props": [("background-color", "#fef9ee")]},
            {"selector": "tbody td",
             "props": [("text-align", "right"), ("border-bottom", "1px solid #ede9e0")]},
            {"selector": "tbody td:first-child, tbody td:nth-child(2)",
             "props": [("text-align", "left")]},
        ])
        .hide(axis="index")
    )

    st.dataframe(
        styled,
        use_container_width=True,
        height=min(800, 36 * len(full) + 60),
        column_config=col_config,
    )

    st.markdown(
        "<div class='footer-note'>Data from Yahoo Finance. "
        "NTM multiples use forward consensus proxies. "
        "GA EV/EBITDA = EV/EBITDA multiple divided by NTM revenue growth rate.</div>",
        unsafe_allow_html=True,
    )
    st.download_button(
        "Download CSV",
        display_df.to_csv(index=False).encode("utf-8"),
        file_name="trading_comps_{}.csv".format(
            selected_sector.replace(" ", "_").lower()
        ),
        mime="text/csv",
    )


# ── Tab 2: Charts ─────────────────────────────────────────────────────────────
with tab_charts:
    def safe_stat(key, sk, mult=1, sfx="x"):
        try:
            v = stats[key][sk]
            return "n/a" if v is None else f"{v * mult:.1f}{sfx}"
        except Exception:
            return "n/a"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Median NTM EV/EBITDA",    safe_stat("NTM EV/EBITDA",    "median"))
    c2.metric("Median NTM P/E",          safe_stat("NTM P/E",          "median"))
    c3.metric("Median LTM EV/EBITDA",    safe_stat("LTM EV/EBITDA",    "median"))
    c4.metric("Median Rev Growth",       safe_stat("NTM Rev Gr%",      "median", 100, "%"))
    c5.metric("Median EBITDA Margin",    safe_stat("EBITDA Mgn",       "median", 100, "%"))

    st.markdown("<br>", unsafe_allow_html=True)

    chart_df = raw_df.copy()
    chart_df["Sub Sector"] = chart_df["Ticker"].map(
        lambda t: ticker_meta.get(t, {}).get("sub_sector", "")
    )

    col_a, col_b = st.columns(2)
    with col_a:
        bar_chart(chart_df, "NTM EV/EBITDA", "NTM EV/EBITDA",
                  ["#fef3c7", "#d97706"])
    with col_b:
        bar_chart(chart_df, "NTM P/E", "NTM P/E",
                  ["#e2e8f0", "#334155"])

    col_c, col_d = st.columns(2)
    with col_c:
        scatter_chart(chart_df)
    with col_d:
        treemap_chart(chart_df)


# ── Tab 3: Universe ───────────────────────────────────────────────────────────
with tab_universe:
    st.markdown("#### Full Universe")
    st.markdown(
        f"<div class='note-text'>{len(filtered_df)} companies in view "
        f"· {len(universe_df)} total in universe</div>",
        unsafe_allow_html=True,
    )
    st.dataframe(
        filtered_df[["name", "ticker", "sector", "sub_sector", "listing_country", "exchange"]]
        .rename(columns={
            "name": "Company", "ticker": "Ticker", "sector": "Sector",
            "sub_sector": "Sub Sector", "listing_country": "Country",
            "exchange": "Exchange",
        })
        .reset_index(drop=True),
        use_container_width=True,
        height=500,
    )

    st.markdown("#### Sub Sector Breakdown")
    if selected_sector != "All Sectors":
        sc = filtered_df["sub_sector"].value_counts().reset_index()
        sc.columns = ["Sub Sector", "Count"]
        fig = px.bar(
            sc, x="Count", y="Sub Sector", orientation="h",
            color="Count",
            color_continuous_scale=["#fef3c7", "#d97706"],
            title="Companies per Sub Sector — {}".format(selected_sector),
        )
        fig.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            showlegend=False, coloraxis_showscale=False,
            yaxis=dict(categoryorder="total ascending"),
            height=max(300, len(sc) * 28),
            margin=dict(l=10, r=20, t=50, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        sc = filtered_df["sector"].value_counts().reset_index()
        sc.columns = ["Sector", "Count"]
        fig = px.pie(
            sc, values="Count", names="Sector",
            title="Universe by Sector",
            color_discrete_sequence=[
                "#1e293b", "#334155", "#475569", "#64748b", "#94a3b8",
                "#d97706", "#f59e0b", "#fbbf24", "#fcd34d", "#fef3c7",
            ],
        )
        fig.update_layout(
            paper_bgcolor="white", height=420,
            margin=dict(l=10, r=10, t=50, b=10),
            font=dict(family="Inter, sans-serif", size=12),
        )
        st.plotly_chart(fig, use_container_width=True)
