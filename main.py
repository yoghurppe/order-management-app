
import streamlit as st
import pandas as pd
import requests
import os
import datetime
import math

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

st.set_page_config(page_title="📊 販売+仕入データ管理", layout="wide")
st.title("📊 sales + purchase_data 管理 & 発注判定")

mode = st.sidebar.radio("モードを選んでください", ["📤 CSVアップロード", "📦 発注AI判定（30日集計）"])

def delete_old_sales():
    cutoff = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    res = requests.delete(f"{SUPABASE_URL}/rest/v1/sales?date=lt.{cutoff}", headers=HEADERS)
    st.write(f"🧹 30日より前のsalesデータ削除: {res.status_code}")

def batch_upload(file_path, table):
    try:
        df = pd.read_csv(file_path)

        if table == "sales":
            df.rename(columns={
                "アイテム": "jan",
                "販売数量": "quantity_sold",
                "現在の手持数量": "stock_total",
                "現在の利用可能数量": "stock_available",
                "現在の注文済数量": "stock_ordered"
            }, inplace=True)
            for col in ["quantity_sold", "stock_total", "stock_available", "stock_ordered"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
            df["jan"] = df["jan"].astype(str).str.strip()
            df["date"] = pd.to_datetime("today").normalize()
            df["date"] = df["date"].dt.strftime('%Y-%m-%d')
            delete_old_sales()
            df = df.drop_duplicates(subset=["jan", "date"], keep="last")

        elif table == "purchase_data":
            for col in ["order_lot", "price"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(",", "")
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                    if col == "order_lot":
                        df[col] = df[col].round().astype(int)
            df["jan"] = pd.to_numeric(df["jan"], errors="coerce").fillna(0).astype("int64").astype(str).str.strip()
            df = df.drop_duplicates(subset=["jan", "supplier"], keep="last")

        batch_size = 500
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size].where(pd.notnull(df.iloc[i:i+batch_size]), None).to_dict(orient="records")
            res = requests.post(
                f"{SUPABASE_URL}/rest/v1/{table}",
                headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
                json=batch
            )
            if res.status_code not in [200, 201]:
                st.error(f"❌ {table} アップロード失敗: {res.status_code} {res.text}")
                return
        st.success(f"✅ {table} に {len(df)} 件アップロード完了")
    except Exception as e:
        st.error(f"❌ {table} のアップロード中にエラー: {e}")

if mode == "📤 CSVアップロード":
    st.subheader("📤 販売データ (sales)")
    uploaded_sales = st.file_uploader("sales.csv", type="csv", key="sales")
    if uploaded_sales:
        path = "/tmp/sales.csv"
        with open(path, "wb") as f:
            f.write(uploaded_sales.read())
        batch_upload(path, "sales")

    st.subheader("📤 仕入データ (purchase_data)")
    uploaded_purchase = st.file_uploader("purchase_data.csv", type="csv", key="purchase")
    if uploaded_purchase:
        path = "/tmp/purchase_data.csv"
        with open(path, "wb") as f:
            f.write(uploaded_purchase.read())
        batch_upload(path, "purchase_data")

if mode == "📦 発注AI判定（30日集計）":
    st.header("📦 発注AI（salesテーブルから30日間の集計）")

    @st.cache_data(ttl=1)
    def fetch_table(name):
        url = f"{SUPABASE_URL}/rest/v1/{name}?select=*"
        res = requests.get(url, headers=HEADERS)
        return pd.DataFrame(res.json()) if res.status_code == 200 else pd.DataFrame()

    df_sales = fetch_table("sales")
    df_purchase = fetch_table("purchase_data")

    if df_sales.empty or df_purchase.empty:
        st.warning("販売 or 仕入データが不足しています。")
        st.stop()

    df_sales["jan"] = df_sales["jan"].astype(str).str.strip()
    df_sales["date"] = pd.to_datetime(df_sales["date"])
    df_purchase["jan"] = df_purchase["jan"].astype(str).str.strip()

    cutoff_date = pd.to_datetime("today") - pd.Timedelta(days=30)
    df_sales_30 = df_sales[df_sales["date"] >= cutoff_date]

    agg_sales = df_sales_30.groupby("jan").agg({
        "quantity_sold": "sum",
        "stock_available": "last"
    }).reset_index()

    agg_sales["stock_available"] = pd.to_numeric(agg_sales["stock_available"], errors="coerce").fillna(0)

    df_purchase["order_lot"] = pd.to_numeric(df_purchase["order_lot"], errors="coerce").fillna(0).astype(int)
    df_purchase["price"] = pd.to_numeric(df_purchase["price"], errors="coerce").fillna(0)

    results = []
    for _, row in agg_sales.iterrows():
        jan = row["jan"]
        sold = row["quantity_sold"]
        stock = row["stock_available"]
        expected_half_month_sales = sold * 0.5
        available_at_arrival = max(0, stock - expected_half_month_sales)
        need_qty = max(sold - available_at_arrival, 0)

        if need_qty <= 0:
            continue

        options = df_purchase[df_purchase["jan"] == jan]
        if options.empty:
            continue

        options = options.sort_values(by="price")
        best_plan = None
        for _, opt in options.iterrows():
            lot = opt["order_lot"]
            price = opt["price"]
            supplier = opt.get("supplier", "不明")
            if pd.isna(lot) or pd.isna(price) or lot <= 0:
                continue

            sets = math.ceil(need_qty / lot)
            qty = sets * lot

            if best_plan is None or price < best_plan["単価"]:
                best_plan = {
                    "jan": jan,
                    "販売数": sold,
                    "在庫": stock,
                    "発注数": qty,
                    "単価": price,
                    "仕入先": supplier
                }

        if best_plan:
            results.append(best_plan)

    if results:
        result_df = pd.DataFrame(results)
        st.success(f"✅ 発注対象: {len(result_df)} 件")
        st.dataframe(result_df)
        csv = result_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 発注CSVダウンロード", data=csv, file_name="orders_30days.csv", mime="text/csv")
    else:
        st.info("現在、発注が必要な商品はありません。")
