import streamlit as st
import pandas as pd
import requests
import os

# Supabase設定
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

st.set_page_config(page_title="発注管理システム", layout="wide")
st.title("📦 発注管理システム（統合版）")

# --- モード選択 ---
mode = st.sidebar.radio("モードを選んでください", ["📤 CSVアップロード", "📦 発注AI判定"])

# --- バッチアップロード関数 ---
def batch_upload_csv_to_supabase(file_path, table):
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
            requests.delete(f"{SUPABASE_URL}/rest/v1/{table}?id=gt.0", headers=HEADERS)

        if table == "purchase_data":
            for col in ["order_lot", "price"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(",", "")
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                    if col == "order_lot":
                        df[col] = df[col].round().astype(int)
            df["jan"] = pd.to_numeric(df["jan"], errors="coerce").fillna(0).astype("int64").astype(str).str.strip()
            requests.delete(f"{SUPABASE_URL}/rest/v1/{table}?id=gt.0", headers=HEADERS)

        df = df.drop_duplicates(subset=["jan", "supplier"] if "supplier" in df.columns else "jan", keep="last")

        batch_size = 500
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size].where(pd.notnull(df.iloc[i:i+batch_size]), None).to_dict(orient="records")
            res = requests.post(
                f"{SUPABASE_URL}/rest/v1/{table}",
                headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
                json=batch
            )
            if res.status_code not in [200, 201]:
                st.error(f"❌ バッチPOST失敗: {res.status_code} {res.text}")
                return
        st.success(f"✅ {table} に {len(df)} 件アップロード完了")
    except Exception as e:
        st.error(f"❌ {table} のアップロード中にエラー: {e}")

# --- CSVアップロード画面 ---
if mode == "📤 CSVアップロード":
    st.header("📤 CSVアップロード")

    sales_file = st.file_uploader("🧾 sales.csv アップロード", type="csv")
    if sales_file:
        temp_path = "/tmp/sales.csv"
        with open(temp_path, "wb") as f:
            f.write(sales_file.read())
        batch_upload_csv_to_supabase(temp_path, "sales")

    purchase_file = st.file_uploader("📦 purchase_data.csv アップロード", type="csv")
    if purchase_file:
        temp_path = "/tmp/purchase_data.csv"
        with open(temp_path, "wb") as f:
            f.write(purchase_file.read())
        batch_upload_csv_to_supabase(temp_path, "purchase_data")

# --- 発注判定画面 ---
if mode == "📦 発注AI判定":
    st.header("📦 発注対象商品AI判定")

    @st.cache_data
    def fetch_table(table_name):
        res = requests.get(f"{SUPABASE_URL}/rest/v1/{table_name}?select=*", headers=HEADERS)
        if res.status_code == 200:
            return pd.DataFrame(res.json())
        st.error(f"{table_name} の取得に失敗: {res.text}")
        return pd.DataFrame()

    df_sales = fetch_table("sales")
    df_purchase = fetch_table("purchase_data")
    
    if df_sales.empty or df_purchase.empty:
        st.warning("販売実績または仕入データが不足しています。")
        st.stop()


    df_sales["jan"] = df_sales["jan"].astype(str).str.strip()
    df_purchase["jan"] = df_purchase["jan"].astype(str).str.strip()

    df_sales["quantity_sold"] = pd.to_numeric(df_sales["quantity_sold"], errors="coerce").fillna(0).astype(int)
    df_sales["stock_total"] = pd.to_numeric(df_sales["stock_total"], errors="coerce").fillna(0).astype(int)
    df_purchase["order_lot"] = pd.to_numeric(df_purchase["order_lot"], errors="coerce").fillna(0).astype(int)
    df_purchase["price"] = pd.to_numeric(df_purchase["price"], errors="coerce").fillna(0)

    results = []
    for _, row in df_sales.iterrows():
        jan = row["jan"]
        sold = row["quantity_sold"]
        stock = row["stock_total"]
        need_qty = max(sold - stock, 0)

        st.write(f"🔍 JAN: {jan}, 販売数={sold}, 在庫={stock}, 必要数={need_qty}")
        if need_qty <= 0:
            continue

        options = df_purchase[df_purchase["jan"] == jan]
        if options.empty:
            st.warning(f"⚠️ 仕入候補が見つかりません (JAN: {jan})")
            continue

        best_plan = None
        for _, opt in options.iterrows():
            lot = opt["order_lot"]
            price = opt["price"]
            supplier = opt.get("supplier", "不明")
            if pd.isna(lot) or pd.isna(price) or lot <= 0:
                continue
            sets = -(-need_qty // lot)
            total = sets * lot * price
            if best_plan is None or total < best_plan["合計"]:
                best_plan = {
                    "jan": jan,
                    "販売数": sold,
                    "在庫": stock,
                    "必要数": need_qty,
                    "ロット": lot,
                    "単価": price,
                    "セット数": sets,
                    "合計": total,
                    "仕入先": supplier
                }

        if best_plan:
            results.append(best_plan)

    if results:
        result_df = pd.DataFrame(results)
        st.success(f"✅ 発注対象: {len(result_df)} 件")
        st.dataframe(result_df)
        csv = result_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 発注CSVダウンロード", data=csv, file_name="orders.csv", mime="text/csv")
    else:
        st.info("現在、発注が必要な商品はありません。")
