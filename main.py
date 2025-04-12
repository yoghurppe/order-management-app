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
                "現在の利用可能数量": "stock_available",
                "現在の注文済数量": "stock_ordered"
            }
            df.rename(columns=rename_cols, inplace=True)

            for col in ["quantity_sold", "stock_total", "stock_available", "stock_ordered"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).round().astype(int)

            df["jan"] = df["jan"].astype(str).str.strip()

        if table == "purchase_data":
            for col in ["order_lot", "price"]:
                if col in df.columns:
                    df[col] = (df[col].astype(str).str.replace(",", "")
                                    .pipe(pd.to_numeric, errors="coerce")
                                    .fillna(0))
                    if col == "order_lot":
                        df[col] = df[col].round().astype(int)

            # JANコードを整数→文字列に整形（4903301339670.0 → "4903301339670"）
            if "jan" in df.columns:
                df["jan"] = pd.to_numeric(df["jan"], errors="coerce").fillna(0).astype("int64").astype(str).str.strip()

        df = df.drop_duplicates(subset=["jan", "supplier"] if "supplier" in df.columns else "jan", keep="last")

        st.info(f"🔄 {table} に {len(df)} 件をアップロード中...")
        progress = st.progress(0)
        batch_size = 500
        total = len(df)

        for i in range(0, total, batch_size):
            batch = df.iloc[i:i+batch_size].where(pd.notnull(df.iloc[i:i+batch_size]), None).to_dict(orient="records")
            res = requests.post(
                f"{SUPABASE_URL}/rest/v1/{table}",
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
mode = st.sidebar.radio("操作を選択", ["📦 発注＆アップロード", "📚 商品情報DB検索", "📝 発注判定"])

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

# --- 発注判定画面 ---
if mode == "📝 発注判定":
    st.subheader("📝 発注対象商品の自動判定")

    sales_df = fetch_table("sales")
    purchase_df = fetch_table("purchase_data")

    if sales_df.empty or purchase_df.empty:
        st.warning("販売実績または仕入データが不足しています。先にアップロードしてください。")
        st.stop()

    sales_df["jan"] = sales_df["jan"].astype(str).str.strip()
    purchase_df["jan"] = purchase_df["jan"].astype(str).str.strip()

    results = []
    for _, row in sales_df.iterrows():
        jan = row["jan"]
        sold = row.get("quantity_sold", 0)
        stock = row.get("stock_total", 0)
        need_qty = max(sold - stock, 0)
        if need_qty > 0:
            best_plan, reason = suggest_optimal_order(jan, need_qty, purchase_df)
            if best_plan:
                results.append({
                    "jan": jan,
                    "販売数": sold,
                    "在庫": stock,
                    "発注数": need_qty,
                    "ロット": best_plan["lot"],
                    "単価": best_plan["price"],
                    "合計金額": best_plan["total"],
                    "仕入先": best_plan["supplier"],
                    "コメント": reason
                })

    if results:
        df_order = pd.DataFrame(results)
        st.dataframe(df_order)

        csv = df_order.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 発注CSVダウンロード",
            data=csv,
            file_name="recommended_orders.csv",
            mime="text/csv"
        )
    else:
        st.info("現在、発注が必要な商品はありません。")
