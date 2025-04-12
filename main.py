
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

st.set_page_config(page_title="📊 毎日販売データアップロード + 発注判定", layout="wide")
st.title("📊 販売データ (sales_daily) - 30日分のみ保持")

mode = st.sidebar.radio("モードを選んでください", ["📤 販売データアップロード", "📦 発注AI判定（30日集計）"])

def delete_old_sales():
    cutoff = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    res = requests.delete(f"{SUPABASE_URL}/rest/v1/sales_daily?date=lt.{cutoff}", headers=HEADERS)
    st.write(f"🧹 30日より前のsales_dailyデータ削除: {res.status_code}")

def batch_upload_daily_sales(file_path):
    try:
        df = pd.read_csv(file_path)

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

        # アップロード前に古いデータ削除
        delete_old_sales()

        df = df.drop_duplicates(subset=["jan", "date"], keep="last")

        batch_size = 500
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size].where(pd.notnull(df.iloc[i:i+batch_size]), None).to_dict(orient="records")
            res = requests.post(
                f"{SUPABASE_URL}/rest/v1/sales_daily",
                headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
                json=batch
            )
            if res.status_code not in [200, 201]:
                st.error(f"❌ アップロード失敗: {res.status_code} {res.text}")
                return
        st.success(f"✅ {len(df)} 件 sales_daily にアップロード完了")
    except Exception as e:
        st.error(f"❌ アップロードエラー: {e}")

if mode == "📤 販売データアップロード":
    st.subheader("📤 毎日の販売CSVをアップロード（sales_daily）")
    uploaded = st.file_uploader("sales_daily.csv アップロード", type="csv")
    if uploaded:
        tmp_path = "/tmp/sales_daily.csv"
        with open(tmp_path, "wb") as f:
            f.write(uploaded.read())
        batch_upload_daily_sales(tmp_path)

if mode == "📦 発注AI判定（30日集計）":
    st.header("📦 発注AI（30日間の合計から判定）")

    @st.cache_data(ttl=1)
    def fetch_table(name):
        url = f"{SUPABASE_URL}/rest/v1/{name}?select=*"
        res = requests.get(url, headers=HEADERS)
        return pd.DataFrame(res.json()) if res.status_code == 200 else pd.DataFrame()

    df_sales = fetch_table("sales_daily")
    df_purchase = fetch_table("purchase_data")

    if df_sales.empty or df_purchase.empty:
        st.warning("販売 or 仕入データが不足しています。")
        st.stop()

    df_sales["jan"] = df_sales["jan"].astype(str).str.strip()
    df_purchase["jan"] = df_purchase["jan"].astype(str).str.strip()

    agg_sales = df_sales.groupby("jan").agg({
        "quantity_sold": "sum",
        "stock_available": "last"
    }).reset_index()

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

        st.write(f"JAN: {jan}")
        st.write(f"  30日販売数: {sold}, 利用可能在庫: {stock}")
        st.write(f"  納品時在庫予測: {available_at_arrival}, 必要発注数: {need_qty}")

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
