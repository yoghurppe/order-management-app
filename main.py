import streamlit as st
import pandas as pd
import requests
import os
import json
import urllib.parse

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

            # 🔁 全削除（idがある前提で高速削除）
            res_del = requests.delete(f"{SUPABASE_URL}/rest/v1/{table}?id=gt.0", headers=HEADERS)
            st.write(f"🗑 DELETE ALL FROM {table}: {res_del.status_code}")

        if table == "purchase_data":
            for col in ["order_lot", "price"]:
                if col in df.columns:
                    df[col] = (df[col].astype(str).str.replace(",", "")
                                    .pipe(pd.to_numeric, errors="coerce")
                                    .fillna(0))
                    if col == "order_lot":
                        df[col] = df[col].round().astype(int)

            if "jan" in df.columns:
                df["jan"] = pd.to_numeric(df["jan"], errors="coerce").fillna(0).astype("int64").astype(str).str.strip()

            # 🔁 全削除（idがある前提で高速削除）
            res_del = requests.delete(f"{SUPABASE_URL}/rest/v1/{table}?id=gt.0", headers=HEADERS)
            st.write(f"🗑 DELETE ALL FROM {table}: {res_del.status_code}")

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

# --- 発注判定ロジック ---
st.header("🧠 発注対象商品のAI判定")

@st.cache_data
def fetch_table(table_name):
    url = f"{SUPABASE_URL}/rest/v1/{table_name}?select=*"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        return pd.DataFrame(res.json())
    else:
        st.error(f"❌ {table_name} の取得に失敗: {res.text}")
        return pd.DataFrame()

df_sales = fetch_table("sales")
df_purchase = fetch_table("purchase_data")

if df_sales.empty or df_purchase.empty:
    st.info("販売実績または仕入データが不足しています。")
    st.stop()

# 整形
df_sales["jan"] = df_sales["jan"].astype(str).str.strip()
df_purchase["jan"] = df_purchase["jan"].astype(str).str.strip()

results = []

for _, row in df_sales.iterrows():
    jan = row["jan"]
    sold = row.get("quantity_sold", 0)
    stock = row.get("stock_total", 0)
    need_qty = max(sold - stock, 0)
    if need_qty <= 0:
        continue

    # 該当JANの仕入候補を抽出
    purchase_options = df_purchase[df_purchase["jan"] == jan]
    if purchase_options.empty:
        continue

    # AIロジック的な最適選択（最安になる組み合わせを選ぶ）
    best_plan = None
    for _, opt in purchase_options.iterrows():
        lot = opt["order_lot"]
        price = opt["price"]
        supplier = opt["supplier"]
        if lot <= 0:
            continue
        units = -(-need_qty // lot)  # ceiling division
        total_cost = units * lot * price
        if best_plan is None or total_cost < best_plan["total"]:
            best_plan = {
                "jan": jan,
                "販売数": sold,
                "在庫": stock,
                "必要数": need_qty,
                "ロット": lot,
                "単価": price,
                "セット数": units,
                "合計": total_cost,
                "仕入先": supplier
            }

    if best_plan:
        results.append(best_plan)

if results:
    result_df = pd.DataFrame(results)
    st.dataframe(result_df)
    csv = result_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 発注CSVダウンロード", data=csv, file_name="recommended_orders.csv", mime="text/csv")
else:
    st.info("現在、発注が必要な商品はありません。")
