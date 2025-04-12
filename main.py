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
        file_products = st.file_uploader("📦 products.csv をアップロード", type="csv")
        if file_products:
            with open("temp_products.csv", "wb") as f:
                f.write(file_products.getbuffer())
            batch_upload_csv_to_supabase("temp_products.csv", "products")

    with upload_col2:
        file_sales = st.file_uploader("📈 sales.csv をアップロード", type="csv")
        if file_sales:
            with open("temp_sales.csv", "wb") as f:
                f.write(file_sales.getbuffer())
            batch_upload_csv_to_supabase("temp_sales.csv", "sales")

# --- バッチアップロード関数 ---
def batch_upload_csv_to_supabase(file_path, table):
    if not os.path.exists(file_path):
        st.warning(f"❌ ファイルが見つかりません: {file_path}")
        return
    try:
        df = pd.read_csv(file_path)

        # sales テーブル用に列名を変換
        if table == "sales":
            rename_cols = {
                "アイテム": "jan",
                "販売数量": "quantity_sold",
                "現在の手持数量": "stock_total",
                "現在の利用可能数量": "stock_available"
            }
            df.rename(columns=rename_cols, inplace=True)

        # ロット階層データを処理（lot1, price1, lot2, price2...）から lot_levels を作成
        if table == "products":
            lot_cols = [col for col in df.columns if col.startswith("lot") and not col.endswith("price")]
            for _, row in df.iterrows():
                levels = []
                for i in range(1, 6):  # 最大5段階まで対応
                    lot_col = f"lot{i}"
                    price_col = f"price{i}"
                    if lot_col in df.columns and price_col in df.columns:
                        lot = row.get(lot_col)
                        price = row.get(price_col)
                        if pd.notna(lot) and pd.notna(price):
                            levels.append({"lot": int(lot), "price": float(price)})
                row["lot_levels"] = json.dumps(levels, ensure_ascii=False)
            df = df.drop(columns=[col for col in df.columns if col.startswith("lot") or col.startswith("price")], errors="ignore")

        df["jan"] = df["jan"].astype(str).str.strip()
        df = df.drop_duplicates(subset="jan", keep="last")
        for _, row in df.iterrows():
            requests.post(
                f"{SUPABASE_URL}/rest/v1/{table}?on_conflict=jan",
                headers=HEADERS,
                json=row.where(pd.notnull(row), None).to_dict()
            )
        st.success(f"✅ {table} テーブルに {len(df)} 件をバッチアップロードしました")
    except Exception as e:
        st.error(f"❌ {table} のアップロード中にエラー: {e}")

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
