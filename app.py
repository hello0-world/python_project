
import calendar
import os

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DATABASE_URL = (
    f"postgresql://{os.getenv('DB_USERNAME')}:"
    f"{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:"
    f"{os.getenv('DB_PORT')}/"
    f"{os.getenv('DB_NAME')}"
)

st.set_page_config(page_title="Chinook Revenue Dashboard", layout="wide")


@st.cache_resource
def get_engine():
    """Create (and cache) the SQLAlchemy engine used for all queries."""
    return create_engine(DATABASE_URL)


@st.cache_data
def load_data():
    engine = get_engine()

    query = """
        SELECT
            i.invoice_id AS invoice_id,
            i.customer_id AS customer_id,
            i.invoice_date AS invoice_date,
            i.billing_country AS billing_country,
            ar.name AS artist_name,
            COALESCE(g.name, 'Unknown') AS genre_name,
            (il.unit_price * il.quantity) AS line_total
        FROM invoice i
        JOIN invoice_line il ON i.invoice_id = il.invoice_id
        JOIN track t ON il.track_id = t.track_id
        JOIN album al ON t.album_id = al.album_id
        JOIN artist ar ON al.artist_id = ar.artist_id
        LEFT JOIN genre g ON t.genre_id = g.genre_id
    """
    df = pd.read_sql_query(query, engine)
    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    return df


st.title("🎵 Chinook Revenue Dashboard")

try:
    data = load_data()
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not connect to the database: {exc}")
    st.stop()

st.sidebar.header("Filters")

country_options = ["All Countries"] + sorted(data["billing_country"].dropna().unique().tolist())
selected_country = st.sidebar.selectbox("Country", country_options)

min_date = data["invoice_date"].min().date()
max_date = data["invoice_date"].max().date()
date_range = st.sidebar.slider(
    "Date Range",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
)

month_names = list(calendar.month_name)[1:]  # Jan..Dec
selected_months = st.sidebar.multiselect(
    "Month",
    options=month_names,
    default=[],
    help="Leave empty to include all months.",
)
selected_month_numbers = [month_names.index(m) + 1 for m in selected_months]

genre_options = sorted(data["genre_name"].dropna().unique().tolist())
selected_genres = st.sidebar.multiselect(
    "Genre",
    options=genre_options,
    default=[],
    help="Leave empty to include all genres.",
)

st.sidebar.divider()
if st.sidebar.button("Reset Filters"):
    st.rerun()

filtered = data.copy()

if selected_country != "All Countries":
    filtered = filtered[filtered["billing_country"] == selected_country]

start_date, end_date = date_range
filtered = filtered[
    (filtered["invoice_date"].dt.date >= start_date)
    & (filtered["invoice_date"].dt.date <= end_date)
]

if selected_month_numbers:
    filtered = filtered[filtered["invoice_date"].dt.month.isin(selected_month_numbers)]

if selected_genres:
    filtered = filtered[filtered["genre_name"].isin(selected_genres)]

if filtered.empty:
    st.warning("No data matches the selected filters. Try widening your selection.")
    st.stop()

total_revenue = filtered["line_total"].sum()
total_invoices = filtered["invoice_id"].nunique()
total_customers = filtered["customer_id"].nunique()

col1, col2, col3 = st.columns(3)
col1.metric("Total Revenue", f"${total_revenue:,.2f}")
col2.metric("Total Invoices", f"{total_invoices:,}")
col3.metric("Total Customers", f"{total_customers:,}")

st.divider()

st.subheader("Top 10 Artists by Revenue")

artist_revenue = (
    filtered.groupby("artist_name")["line_total"]
    .sum()
    .reset_index()
    .rename(columns={"line_total": "revenue"})
    .sort_values("revenue", ascending=False)
    .head(10)
)

if not artist_revenue.empty:
    g_artist = sns.catplot(
        data=artist_revenue,
        y="artist_name",
        x="revenue",
        kind="bar",
        hue="artist_name",
        order=artist_revenue["artist_name"],
        legend=False,
        palette="viridis",
        height=5,
        aspect=1.9,
    )
    ax_artist = g_artist.ax
    for container in ax_artist.containers:
        ax_artist.bar_label(container, fmt="$%.0f", padding=3)
    ax_artist.set_xlabel("Revenue ($)")
    ax_artist.set_ylabel("Artist")
    ax_artist.set_title("Top 10 Artists by Revenue")
    plt.tight_layout()
    st.pyplot(g_artist.fig)
    plt.close(g_artist.fig)
else:
    st.info("No data available for the selected filters.")

st.divider()

st.subheader("Monthly Revenue Trend")

filtered["month"] = filtered["invoice_date"].dt.strftime("%Y-%m")
monthly_revenue = (
    filtered.groupby("month")["line_total"]
    .sum()
    .reset_index()
    .rename(columns={"line_total": "revenue"})
    .sort_values("month")
)

if not monthly_revenue.empty:
    g_month = sns.relplot(
        data=monthly_revenue,
        x="month",
        y="revenue",
        kind="line",
        marker="o",
        height=5,
        aspect=2.4,
    )
    ax_month = g_month.ax
    ax_month.set_xlabel("Month")
    ax_month.set_ylabel("Revenue ($)")
    ax_month.set_title("Monthly Revenue Trend")
    plt.setp(ax_month.get_xticklabels(), rotation=90)
    plt.tight_layout()
    st.pyplot(g_month.fig)
    plt.close(g_month.fig)
else:
    st.info("No data available for the selected filters.")

st.divider()

st.subheader("Revenue by Country")

country_revenue = (
    filtered.groupby("billing_country")["line_total"]
    .sum()
    .reset_index()
    .rename(columns={"line_total": "revenue"})
    .sort_values("revenue", ascending=False)
)

if not country_revenue.empty:
    g_country = sns.catplot(
        data=country_revenue,
        y="billing_country",
        x="revenue",
        kind="bar",
        hue="billing_country",
        order=country_revenue["billing_country"],
        legend=False,
        palette="mako",
        height=8,
        aspect=1.2,
    )
    ax_country = g_country.ax
    for container in ax_country.containers:
        ax_country.bar_label(container, fmt="$%.0f", padding=3)
    ax_country.set_xlabel("Revenue ($)")
    ax_country.set_ylabel("Country")
    ax_country.set_title("Revenue by Country")
    plt.tight_layout()
    st.pyplot(g_country.fig)
    plt.close(g_country.fig)
else:
    st.info("No data available for the selected filters.")

st.divider()

st.subheader("Raw Invoice Data")

invoice_summary = (
    filtered.groupby(["invoice_id", "customer_id", "invoice_date", "billing_country"])["line_total"]
    .sum()
    .reset_index()
    .rename(columns={"line_total": "total"})
    .sort_values("invoice_date")
)
st.dataframe(invoice_summary, use_container_width=True)