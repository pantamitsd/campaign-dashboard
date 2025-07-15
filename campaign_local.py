import streamlit as st
import pandas as pd
import re
import plotly.express as px

st.set_page_config(page_title="Campaign Dashboard", layout="wide")
st.title("📊 Campaign Metrics Dashboard")

# Step 1: Upload File
uploaded_file = st.file_uploader("📂 Upload your Campaign file (Excel or CSV)", type=["xlsx", "csv"])

if uploaded_file:
    try:
        # Step 2: Read File
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        # Step 3: ADDSPEND check
        if "ADDSPEND" not in df.columns:
            st.warning("📉 'ADDSPEND' column missing — calculating using Revenue / ROI")
            df["ADDSPEND"] = df.apply(
                lambda row: (row["Total Revenue (Rs.)"] / row["ROI"])
                if pd.notnull(row["ROI"]) and row["ROI"] != 0 else 0,
                axis=1
            )

        # ✅ Step 4: Row-level Direct Revenue Calculation
        df["Total Units Sold"] = df["Direct Units Sold"] + df["Indirect Units Sold"]
        df["Direct Revenue"] = df.apply(
            lambda row: (row["Direct Units Sold"] / row["Total Units Sold"]) * row["Total Revenue (Rs.)"]
            if row["Total Units Sold"] > 0 else 0, axis=1
        )

        # ✅ Step 5: Grouped Aggregation (after row-level direct revenue calc)
        agg_df = df.groupby("Sku Id").agg({
            "ADDSPEND": "sum",
            "Views": "sum",
            "Clicks": "sum",
            "Direct Units Sold": "sum",
            "Indirect Units Sold": "sum",
            "Total Revenue (Rs.)": "sum",
            "Direct Revenue": "sum"
        }).reset_index()

        agg_df["Total Units Sold"] = agg_df["Direct Units Sold"] + agg_df["Indirect Units Sold"]
        agg_df["CTR"] = (agg_df["Clicks"] / agg_df["Views"]).replace([float('inf'), -float('inf')], 0) * 100
        agg_df["Conversion Rate per SKU"] = agg_df["Total Units Sold"] / agg_df["Clicks"].replace(0, 1)
        agg_df["Conversion Rate Direct Adjusted"] = agg_df["Direct Units Sold"] / (
            agg_df["Clicks"] - agg_df["Indirect Units Sold"]).replace(0, 1)
        agg_df["ROI_Direct"] = agg_df.apply(
            lambda row: row["Direct Revenue"] / row["ADDSPEND"] if row["ADDSPEND"] > 0 else 0,
            axis=1
        )

        # Step 6: Sidebar Filters
        st.sidebar.header("🔎 Filter Conditions")
        filter_clicks = st.sidebar.text_input("Clicks (e.g. > 100)")
        filter_ctr = st.sidebar.text_input("CTR (%) (e.g. >= 2.5)")
        filter_cr_direct = st.sidebar.text_input("Conversion Rate Direct Adjusted (%)")
        filter_addspend = st.sidebar.text_input("ADDSPEND (e.g. > 5000)")
        filter_revenue = st.sidebar.text_input("Total Revenue (Rs.) (e.g. >= 10000)")

        if "Date" in df.columns:
            unique_dates = sorted(df["Date"].dropna().astype(str).unique().tolist())
            selected_date = st.sidebar.selectbox("📅 Filter by Date", options=["All"] + unique_dates)
        else:
            selected_date = "All"

        sku_list = agg_df["Sku Id"].dropna().unique().tolist()
        selected_skus = st.sidebar.multiselect("🔢 Filter by Sku Id", options=sorted(sku_list))

        # Step 7: Apply Filters
        filtered_df = agg_df.copy()

        def apply_condition(df, column, condition):
            match = re.match(r"^\s*(>=|<=|>|<|==|=)\s*(\d+(\.\d+)?)\s*$", condition)
            if match:
                op, val = match.group(1), float(match.group(2))
                return df.query(f"`{column}` {op} {val}")
            else:
                st.warning(f"⚠️ Invalid filter for {column}. Use like '> 100'")
                return df

        if filter_clicks:
            filtered_df = apply_condition(filtered_df, "Clicks", filter_clicks)
        if filter_ctr:
            filtered_df = apply_condition(filtered_df, "CTR", filter_ctr)
        if filter_cr_direct:
            filtered_df["Conversion Rate Direct Adjusted"] *= 100
            filtered_df = apply_condition(filtered_df, "Conversion Rate Direct Adjusted", filter_cr_direct)
        if filter_addspend:
            filtered_df = apply_condition(filtered_df, "ADDSPEND", filter_addspend)
        if filter_revenue:
            filtered_df = apply_condition(filtered_df, "Total Revenue (Rs.)", filter_revenue)

        if selected_skus:
            filtered_df = filtered_df[filtered_df["Sku Id"].isin(selected_skus)]
        if selected_date != "All" and "Date" in df.columns:
            sku_with_date = df[df["Date"].astype(str) == selected_date]
            sku_ids = sku_with_date["Sku Id"].unique()
            filtered_df = filtered_df[filtered_df["Sku Id"].isin(sku_ids)]

        # Step 8: KPI Cards
        total_clicks = filtered_df["Clicks"].sum()
        total_views = filtered_df["Views"].sum()
        total_direct = filtered_df["Direct Units Sold"].sum()
        total_indirect = filtered_df["Indirect Units Sold"].sum()

        ctr_overall = (total_clicks / total_views) * 100 if total_views > 0 else 0
        cr_direct_adj = total_direct / (total_clicks - total_indirect) if (total_clicks - total_indirect) > 0 else 0

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("👁️ Total Views", f"{int(total_views):,}")
        kpi2.metric("🖱️ Total Clicks", f"{int(total_clicks):,}")
        kpi3.metric("🎯 CTR Overall (%)", f"{ctr_overall:.2f}")
        kpi4.metric("📈 Conversion Rate Direct Unit", f"{cr_direct_adj:.2%}")

        # Step 9: Format %
        filtered_df["Conversion Rate per SKU"] = (filtered_df["Conversion Rate per SKU"] * 100).round(2)
        filtered_df["Conversion Rate Direct Adjusted"] = (filtered_df["Conversion Rate Direct Adjusted"]).round(2)

        # Step 10: Table
        st.subheader("📋 Aggregated Campaign Table")
        selected_columns = [
            "Sku Id", "ADDSPEND", "CTR", "Conversion Rate per SKU",
            "Direct Units Sold", "Views", "Clicks", "Indirect Units Sold",
            "Total Revenue (Rs.)", "Direct Revenue", "ROI_Direct", "Conversion Rate Direct Adjusted"
        ]
        st.dataframe(filtered_df[selected_columns], use_container_width=True)

        # Step 11: ROI Chart
        st.subheader("📊 Top 10 SKUs by ROI_Direct")
        top_roi_df = filtered_df[filtered_df["Direct Units Sold"] > 0].sort_values(by="ROI_Direct", ascending=False).head(10)

        if not top_roi_df.empty:
            fig = px.bar(
                top_roi_df,
                x="Sku Id",
                y="ROI_Direct",
                color="Sku Id",
                text="ROI_Direct",
                title="Top 10 SKUs by ROI_Direct (Direct Units Sold Only)",
                color_discrete_sequence=px.colors.qualitative.Vivid
            )
            fig.update_traces(texttemplate="ROI: %{text:.2f}", textposition="outside")
            fig.update_layout(yaxis_title="ROI (Direct)", xaxis_title="SKU ID", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for ROI chart.")

        # Step 12: AddSpend vs Direct Revenue
        st.subheader("💸 AddSpend vs Direct Revenue (Top 10 by AddSpend)")
        top_spend_df = filtered_df[filtered_df["Direct Units Sold"] > 0].sort_values(by="ADDSPEND", ascending=False).head(10)

        if not top_spend_df.empty:
            revenue_chart_df = top_spend_df[["Sku Id", "ADDSPEND", "Direct Revenue"]].melt(
                id_vars="Sku Id", var_name="Metric", value_name="Amount"
            )
            fig2 = px.bar(
                revenue_chart_df,
                x="Sku Id",
                y="Amount",
                color="Metric",
                barmode="group",
                title="AddSpend vs Direct Revenue per SKU",
                text_auto=True
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No data available for AddSpend vs Revenue chart.")

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")

