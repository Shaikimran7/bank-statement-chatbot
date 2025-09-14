import streamlit as st
import pandas as pd
import pdfplumber
import matplotlib.pyplot as plt
from datetime import date
import requests
from io import BytesIO

st.set_page_config(
    page_title="💳 Bank Statement Chatbot",
    page_icon="💳",
    layout="wide"
)

# --- Session State Initialization ---
DEFAULTS = {
    "df": None, "query": "", "start_date": date.today(), "end_date": date.today(),
    "search_term": "", "min_amt": 0.0, "max_amt": 0.0, "amt_col": "Debit", "pdf_url": ""
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- Header ---
st.markdown("<h1 style='text-align:center;'>💳✨ Bank Statement Chatbot ✨💳</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align:center;font-size:18px;'>Upload or link your bank statement PDF and explore your finances with style!</div>", unsafe_allow_html=True)
st.markdown("---")

# --- PDF Handling ---
def get_pdf_from_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return BytesIO(response.content)
    except Exception as e:
        st.error(f"🚨 Could not fetch PDF: {e}")
        return None

def process_pdf_data(file, pwd):
    all_data = []
    try:
        with pdfplumber.open(file, password=pwd if pwd else None) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    df = pd.DataFrame(table[1:], columns=table[0])
                    cols = pd.Series(df.columns)
                    for i in range(len(cols)):
                        if cols.duplicated()[i]:
                            cols[i] = f"{cols[i]}_{i}"
                    df.columns = cols
                    all_data.append(df)
    except pdfplumber.pdf.PDFPasswordError:
        st.error("❌ Incorrect password.")
        return None
    except Exception as e:
        st.error(f"❌ Error during PDF processing: {e}")
        return None
    if not all_data:
        return pd.DataFrame()
    df = pd.concat(all_data, ignore_index=True)
    columns = df.columns
    date_col = next((c for c in columns if "date" in str(c).lower()), None)
    debit_col = next((c for c in columns if "debit" in str(c).lower() or "withdraw" in str(c).lower()), None)
    credit_col = next((c for c in columns if "credit" in str(c).lower() or "deposit" in str(c).lower()), None)
    ref_col = next((c for c in columns if "ref" in str(c).lower() or "particular" in str(c).lower()), None)
    keep_cols = [c for c in [date_col, debit_col, credit_col, ref_col] if c]
    if not keep_cols:
        return pd.DataFrame()
    rename_map = {}
    if date_col: rename_map[date_col] = "Date"
    if debit_col: rename_map[debit_col] = "Debit"
    if credit_col: rename_map[credit_col] = "Credit"
    if ref_col: rename_map[ref_col] = "Reference"
    df = df[keep_cols].rename(columns=rename_map)
    for col in ["Debit", "Credit"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", "").str.strip(), errors="coerce").fillna(0)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return df

# --- Upload/URL Input ---
with st.container():
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        uploaded_file = st.file_uploader("📥 Upload PDF", type=["pdf"])
    with col2:
        pdf_url = st.text_input("🔗 Or paste PDF direct link", value=st.session_state.pdf_url)
        st.session_state.pdf_url = pdf_url
    with col3:
        password = st.text_input("🔒 PDF password", type="password")
    st.markdown("")

pdf_source = uploaded_file if uploaded_file else (get_pdf_from_url(pdf_url) if pdf_url else None)
if pdf_source and st.button("🚀 Process PDF", use_container_width=True):
    with st.spinner("🕐 Processing PDF..."):
        df = process_pdf_data(pdf_source, password)
        if df is not None and not df.empty:
            st.session_state.df = df
            st.success("✅ PDF processed successfully!")
        elif df is not None and df.empty:
            st.warning("⚠️ No relevant data tables found in PDF.")

# --- Utility Functions ---
def get_top_debits(df, n=5):
    if "Debit" in df.columns and "Reference" in df.columns:
        top_debits = df.groupby("Reference")["Debit"].sum().nlargest(n)
        return top_debits[top_debits > 0]
    return pd.Series()

def get_top_credits(df, n=5):
    if "Credit" in df.columns and "Reference" in df.columns:
        top_credits = df.groupby("Reference")["Credit"].sum().nlargest(n)
        return top_credits[top_credits > 0]
    return pd.Series()

def get_day_counts(df):
    if "Date" in df.columns:
        return df.groupby("Date").size()
    return pd.Series()

def filter_by_date(df, start, end):
    if "Date" in df.columns:
        return df[(df["Date"] >= start) & (df["Date"] <= end)]
    return pd.DataFrame()

def get_monthly_summary(df):
    if "Date" in df.columns:
        df = df.copy()
        df["Month"] = df["Date"].dt.to_period("M")
        return df.groupby("Month")[["Debit", "Credit"]].sum()
    return pd.DataFrame()

def get_weekly_summary(df):
    if "Date" in df.columns:
        df = df.copy()
        df["Week"] = df["Date"].dt.to_period("W")
        return df.groupby("Week")[["Debit", "Credit"]].sum()
    return pd.DataFrame()

def search_reference(df, term):
    if "Reference" in df.columns:
        return df[df["Reference"].str.lower().str.contains(term.lower(), na=False)]
    return pd.DataFrame()

def filter_by_amount(df, min_amt=0, max_amt=None, col="Debit"):
    if col in df.columns:
        if max_amt is not None and max_amt > 0:
            return df[(df[col] >= min_amt) & (df[col] <= max_amt)]
        return df[df[col] >= min_amt]
    return pd.DataFrame()

def transaction_count_by_reference(df):
    if "Reference" in df.columns:
        return df["Reference"].value_counts()
    return pd.Series()

def download_csv(df, label="💾 Download CSV"):
    csv = df.to_csv(index=False)
    st.download_button(label, csv, file_name="filtered_transactions.csv", mime="text/csv")

def plot_bar_with_labels(data, title, xlabel, ylabel, color="#0073e6"):
    if data.empty: return
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(data.index.astype(str), data.values, color=color)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.xticks(rotation=45, ha='right')
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:,.2f}', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=10)
    st.pyplot(fig)

# --- Main Interface ---
if st.session_state.df is not None and not st.session_state.df.empty:
    df = st.session_state.df

    with st.sidebar:
        st.header("🔎 Filters & Search")
        date_range = st.date_input("📅 Date Range", [date.today(), date.today()])
        st.session_state.start_date = date_range[0] if date_range else date.today()
        st.session_state.end_date = date_range[1] if len(date_range) > 1 else date.today()
        st.session_state.search_term = st.text_input("🔍 Reference Search", value=st.session_state.search_term)
        st.session_state.min_amt = st.number_input("💸 Min Amount", value=float(st.session_state.min_amt))
        st.session_state.max_amt = st.number_input("💰 Max Amount (0 for no max)", value=float(st.session_state.max_amt))
        st.session_state.amt_col = st.selectbox("🧮 Amount Column", ["Debit", "Credit"], index=0 if st.session_state.amt_col == "Debit" else 1)
        if st.button("🎯 Apply Filters"):
            st.session_state.query = "filter_reference_amount"

    # Quick Analysis
    st.markdown("### ⚡✨ Quick Analysis ✨⚡")
    quick_options = [
        "🔴 Highest Debit", "💰 Highest Credit", "📅 Most Transactions",
        "💸 Total Spent", "💵 Total Deposited", "🗓️ Monthly Summary",
        "🗓️ Weekly Summary", "🔢 Transaction Count by Reference",
        "🔥 Most Frequent Reference", "🏆 Largest Transaction"
    ]
    selected_example = st.radio("Pick one for instant insight", quick_options, horizontal=True)
    if selected_example:
        st.session_state.query = selected_example.split(" ",1)[1].lower().replace(" ", "_")

    # Freeform Query
    st.subheader("💬🤔 Or type your own question")
    user_query = st.text_input("Ask me anything! (e.g. How much did I spend on Starbucks?)", key="user_query")
    if user_query:
        st.session_state.query = user_query.lower()

    # Analysis & Results
    st.markdown("---")
    q = st.session_state.query
    if q:
        if "highest_debit" in q:
            top_debits = get_top_debits(df)
            if not top_debits.empty:
                top_debtor = top_debits.idxmax()
                top_value = top_debits.max()
                st.info(f"🔴 Highest Debit: **{top_debtor}** ({top_value:.2f} 💸)")
                plot_bar_with_labels(top_debits, "Top 5 Debit References 💳", "Reference", "Debit Amount", "#e84c3d")
            else:
                st.warning("No debit data found.")

        elif "highest_credit" in q:
            top_credits = get_top_credits(df)
            if not top_credits.empty:
                top_creditor = top_credits.idxmax()
                top_value = top_credits.max()
                st.info(f"💰 Highest Credit: **{top_creditor}** ({top_value:.2f} 💵)")
                fig, ax = plt.subplots(figsize=(8, 5))
                ax.pie(top_credits.values, labels=top_credits.index, autopct="%1.1f%%", startangle=90)
                ax.set_title("Top 5 Credit References 💰")
                st.pyplot(fig)
            else:
                st.warning("No credit data found.")

        elif "most_transactions" in q:
            day_counts = get_day_counts(df)
            if not day_counts.empty:
                most_day = day_counts.idxmax()
                most_count = day_counts.max()
                st.info(f"📅 Most Transactions: **{most_day.date()}** ({most_count} 📄)")
                plot_bar_with_labels(day_counts, "Transaction Count by Day 📅", "Date", "Transactions", "#2ecc71")
            else:
                st.warning("No date data found.")

        elif "total_spent" in q:
            if "Debit" in df.columns:
                total_spent = df["Debit"].sum()
                st.success(f"💸 Total amount spent: **{total_spent:.2f}**")
            else:
                st.warning("Debit data not available.")

        elif "total_deposited" in q:
            if "Credit" in df.columns:
                total_deposited = df["Credit"].sum()
                st.success(f"💵 Total amount deposited: **{total_deposited:.2f}**")
            else:
                st.warning("Credit data not available.")

        elif "monthly_summary" in q:
            summary = get_monthly_summary(df)
            if not summary.empty:
                st.write("🗓️ Monthly Summary")
                st.dataframe(summary)
                plot_bar_with_labels(summary["Debit"], "Monthly Debits 🔴", "Month", "Debit", "#e84c3d")
                plot_bar_with_labels(summary["Credit"], "Monthly Credits 💰", "Month", "Credit", "#2ecc71")
            else:
                st.warning("No date data available.")

        elif "weekly_summary" in q:
            summary = get_weekly_summary(df)
            if not summary.empty:
                st.write("🗓️ Weekly Summary")
                st.dataframe(summary)
                plot_bar_with_labels(summary["Debit"], "Weekly Debits 🔴", "Week", "Debit", "#e84c3d")
                plot_bar_with_labels(summary["Credit"], "Weekly Credits 💰", "Week", "Credit", "#2ecc71")
            else:
                st.warning("No date data available.")

        elif "count_by_reference" in q:
            counts = transaction_count_by_reference(df)
            if not counts.empty:
                st.write("🔢 Transaction Count by Reference")
                st.dataframe(counts)
                plot_bar_with_labels(counts[:10], "Top 10 References by Transaction Count 🔢", "Reference", "Count", "#0073e6")
            else:
                st.warning("No reference data available.")

        elif "most_frequent_reference" in q:
            counts = transaction_count_by_reference(df)
            if not counts.empty:
                top_ref = counts.idxmax()
                top_count = counts.max()
                st.info(f"🔥 Most Frequent Reference: **{top_ref}** ({top_count} times)")
                plot_bar_with_labels(counts[:10], "Top 10 References 🔥", "Reference", "Count", "#ff9800")
            else:
                st.warning("No reference data available.")

        elif "largest_transaction" in q:
            debit_max = df.get("Debit", pd.Series()).max()
            credit_max = df.get("Credit", pd.Series()).max()
            st.info(f"🏆 Largest Transaction: Debit {debit_max:.2f}, Credit {credit_max:.2f}")

        elif "filter_reference_amount" in q:
            fdf = df
            if st.session_state.search_term:
                fdf = search_reference(fdf, st.session_state.search_term)
            if st.session_state.max_amt > 0:
                fdf = filter_by_amount(fdf, st.session_state.min_amt, st.session_state.max_amt, st.session_state.amt_col)
            else:
                fdf = filter_by_amount(fdf, st.session_state.min_amt, col=st.session_state.amt_col)
            if not fdf.empty:
                st.success(f"🔎 Found {len(fdf)} transactions matching your criteria.")
                st.dataframe(fdf)
                download_csv(fdf)
            else:
                st.info("No matching transactions found.")

        elif "how much" in q or "spent on" in q or "spend on" in q:
            parts = q.split("on")
            if len(parts) > 1:
                search_term = parts[-1].strip()
                filtered_df = search_reference(df, search_term)
                if not filtered_df.empty:
                    total_category_spent = filtered_df.get("Debit", pd.Series()).sum()
                    st.success(f"🛍️ You spent **{total_category_spent:.2f}** on **{search_term}**.")
                    st.dataframe(filtered_df)
                    download_csv(filtered_df)
                else:
                    st.info(f"No transactions found containing '{search_term}'.")
            else:
                st.info("Specify what to search. Example: 'How much did I spend on food?'")

        else:
            st.info("🤖 Sorry, I didn’t understand. Try one of the example buttons or keywords.")
else:
    st.info("📤 Upload a PDF or paste a direct link to get started!")
