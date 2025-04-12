import streamlit as st
import pandas as pd
import requests
import os
import json

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

# --- バッチアップロード関数（最適化） ---
def batch_upload_csv_to_supabase(file_path, table):
    if not os.path.exists(file_path):
        st.warning(f"❌ ファイルが見つかりません: {file_path}")
        return
    try:
        df = pd.read_csv(file_path)

        if table == "sales":
            rename_cols = {
                "アイテム": "jan",
                "販売数量": "quantity_sold",
                "現在の手持数量": "stock_total",
                "現在の利用可能数量": "stock_available"
            }
            df.rename(columns=rename_cols, inplace=True)

        df["jan"] = df["jan"].astype(str).str.strip()
        df = df.drop_duplicates(subset="jan", keep="last")

        st.info(f"🔄 {table} に {len(df)} 件をアップロード中...")
        progress = st.progress(0)
        batch_size = 500
        total = len(df)

        for i in range(0, total, batch_size):
            batch = df.iloc[i:i+batch_size].where(pd.notnull(df.iloc[i:i+batch_size]), None).to_dict(orient="records")
            res = requests.post(
                f"{SUPABASE_URL}/rest/v1/{table}?on_conflict=jan",
                headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
                json=batch
            )
            if res.status_code not in [200, 201]:
                st.error(f"❌ バッチPOST失敗 ({i} 件目〜): {res.status_code} {res.text}")
                return
            progress.progress(min((i + batch_size) / total, 1.0))

        st.success(f"✅ {table} テーブルに {total} 件をアップロードしました")
    except Exception as e:
        st.error(f"❌ {table} のアップロード中にエラー: {e}")

# --- モード切り替え ---
mode = st.sidebar.radio("操作を選択", ["📦 発注＆アップロード", "📚 商品情報DB検索"])

@st.cache_data
def fetch_table(table_name):
    url = f"{SUPABASE_URL}/rest/v1/{table_name}?select=*"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        return pd.DataFrame(res.json())
    else:
        st.error(f"{table_name} の取得に失敗しました: {res.text}")
        return pd.DataFrame()

# --- CSVアップロード画面 ---
if mode == "📦 発注＆アップロード":
    st.subheader("📤 CSVアップロード")
    upload_col1, upload_col2 = st.columns(2)

    with upload_col1:
        file_sales = st.file_uploader("📈 sales.csv をアップロード", type="csv")
        if file_sales:
            with open("temp_sales.csv", "wb") as f:
                f.write(file_sales.getbuffer())
            batch_upload_csv_to_supabase("temp_sales.csv", "sales")

    with upload_col2:
        file_purchase = st.file_uploader("🛒 purchase_data.csv をアップロード", type="csv")
        if file_purchase:
            with open("temp_purchase.csv", "wb") as f:
                f.write(file_purchase.getbuffer())
            batch_upload_csv_to_supabase("temp_purchase.csv", "purchase_data")

# --- 最適な発注パターンと理由をAI的に提示する関数 ---
def suggest_optimal_order(jan, need_qty, purchase_df):
    purchase_df = purchase_df[purchase_df["jan"] == jan].copy()
    if purchase_df.empty:
        return None, "仕入候補が存在しません"

    best_plan = None
    reason = ""
    for _, row in purchase_df.iterrows():
        lot = row["order_lot"]
        price = row["price"]
        supplier = row["supplier"]
        if lot <= 0:
            continue
        units = -(-need_qty // lot)  # ceiling division
        total_price = units * lot * price
        if (best_plan is None) or (total_price < best_plan["total"]):
            best_plan = {
                "supplier": supplier,
                "lot": lot,
                "price": price,
                "units": units,
                "total": total_price
            }
            reason = f"発注数 {need_qty} に対して、{supplier} のロット {lot} で {units} セット注文 → 合計 {total_price:.0f}円 が最安です"
    return best_plan, reason
