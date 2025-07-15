import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="Campaign Dashboard", layout="wide")
st.title("📊 Campaign Metrics Dashboard")

# Step 1: Upload File (CSV or Excel)
uploaded_file = st.file_uploader("📂 Upload your Campaign file (Excel or CSV)", type=["xlsx", "csv"])

if uploaded_file:
    try:
        # Step 2: Read the uploaded file based on extension
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        # Step 3: ADDSPEND Column Check
        if "ADDSPEND" not in df.columns:
            st.warning("📉 'ADDSPEND' column missing — calculating using Revenue / ROI")
            df["ADDSPEND"] = df.apply(
                lambda row: (row["Total Revenue (Rs.)"] / row["ROI"])
                if pd.notnull(row["ROI"]) and row["ROI"] != 0 else 0,
                axis=1
            )

        # Step 4: Group by SKU ID
        agg_df = df.groupby("Sku Id").agg({
            "ADDSPEND": "sum",
            "Views": "sum",
            "Clicks": "sum",
            "Direct Units Sold": "sum",
            "Indirect Units Sold": "sum",
            "Total Revenue (Rs.)": "sum"
        }).reset_index()

        # Step 5: Metric Calculations
        agg_df["Total Units Sold"] = agg_df["Direct Units Sold"] + agg_df["Indirect Units Sold"]
        agg_df["CTR"] = (agg_df["Clicks"] / agg_df["Views"]).replace([float('inf'), -float('inf')], 0) * 100
        agg_df["Conversion Rate per SKU"] = agg_df["Total Units Sold"] / agg_df["Clicks"].replace(0, 1)
        agg_df["Conversion Rate Direct Adjusted"] = agg_df["Direct Units Sold"] / (
            agg_df["Clicks"] - agg_df["Indirect Units Sold"]).replace(0, 1)
        agg_df["Direct Revenue"] = agg_df.apply(
            lambda row: (row["Direct Units Sold"] / row["Total Units Sold"]) * row["Total Revenue (Rs.)"]
            if row["Total Units Sold"] > 0 else 0, axis=1)
        agg_df["ROI_Direct"] = agg_df.apply(
            lambda row: row["Direct Revenue"] / row["ADDSPEND"]
            if row["ADDSPEND"] > 0 else 0, axis=1)

        # Step 6: Sidebar Filters
        st.sidebar.header("🔎 Filter Conditions")
        filter_clicks = st.sidebar.text_input("Clicks (e.g. > 100)")
        filter_ctr = st.sidebar.text_input("CTR (%) (e.g. >= 2.5)")

        # Date Filter (if present)
        if "Date" in df.columns:
            unique_dates = sorted(df["Date"].dropna().astype(str).unique().tolist())
            selected_date = st.sidebar.selectbox("📅 Filter by Date", options=["All"] + unique_dates)
        else:
            selected_date = "All"

        # Sku filter
        sku_list = agg_df["Sku Id"].dropna().unique().tolist()
        selected_skus = st.sidebar.multiselect(
            "🔢 Filter by Sku Id (search + multi-select)",
            options=sorted(sku_list),
        )

        # Apply Filters
        filtered_df = agg_df.copy()

        def apply_condition(df, column, condition):
            match = re.match(r"^\s*(>=|<=|>|<|==|=)\s*(\d+(\.\d+)?)\s*$", condition)
            if match:
                op, val = match.group(1), float(match.group(2))
                return df.query(f"`{column}` {op} {val}")
            else:
                st.warning(f"⚠️ Invalid filter for {column}. Use like '> 100' or '<= 2.5'")
                return df

        if filter_clicks:
            filtered_df = apply_condition(filtered_df, "Clicks", filter_clicks)

        if filter_ctr:
            filtered_df = apply_condition(filtered_df, "CTR", filter_ctr)

        if selected_skus:
            filtered_df = filtered_df[filtered_df["Sku Id"].isin(selected_skus)]

        if selected_date != "All" and "Date" in df.columns:
            sku_with_date = df[df["Date"].astype(str) == selected_date]
            sku_ids = sku_with_date["Sku Id"].unique()
            filtered_df = filtered_df[filtered_df["Sku Id"].isin(sku_ids)]

        # Step 7: KPI Cards
        total_clicks = filtered_df["Clicks"].sum()
        total_views = filtered_df["Views"].sum()
        total_direct = filtered_df["Direct Units Sold"].sum()
        total_indirect = filtered_df["Indirect Units Sold"].sum()

        ctr_overall = (total_clicks / total_views) * 100 if total_views > 0 else 0
        cr_per_sku = ((total_direct + total_indirect) / total_clicks) if total_clicks > 0 else 0
        cr_direct_adj = total_direct / (total_clicks - total_indirect) if (total_clicks - total_indirect) > 0 else 0

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("👁️ Total Views", f"{int(total_views):,}")
        kpi2.metric("🖱️ Total Clicks", f"{int(total_clicks):,}")
        kpi3.metric("🎯 CTR Overall (%)", f"{ctr_overall:.2f}")
        kpi4.metric("📈 Conversion Rate Direct Unit", f"{cr_direct_adj:.2%}")

        # Step 8: Table Output
        selected_columns = [
            "Sku Id", "ADDSPEND", "CTR", "Conversion Rate per SKU",
            "Direct Units Sold", "Views", "Clicks", "Indirect Units Sold",
            "Total Revenue (Rs.)", "Direct Revenue", "ROI_Direct", "Conversion Rate Direct Adjusted"
        ]

        st.subheader("📋 Aggregated Campaign Table")
        st.dataframe(filtered_df[selected_columns], use_container_width=True)

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
