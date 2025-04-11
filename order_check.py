import streamlit as st
import pandas as pd
import requests

# Supabase設定（secrets.tomlから取得）
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

st.set_page_config(page_title="発注判定画面", layout="wide")
st.title("📦 発注対象商品リスト")

# データ取得
@st.cache_data
def fetch_table(table_name):
    url = f"{SUPABASE_URL}/rest/v1/{table_name}?select=*"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        return pd.DataFrame(res.json())
    else:
        st.error(f"{table_name} の取得に失敗しました: {res.text}")
        return pd.DataFrame()

# 商品マスターと販売実績を取得
df_products = fetch_table("products")
df_sales = fetch_table("sales")

if df_products.empty or df_sales.empty:
    st.warning("商品マスターまたは販売実績が不足しています。アップロードしてください。")
    st.stop()

# JANコードで結合
df = pd.merge(df_products, df_sales, on="jan", how="inner")

# 発注判定ロジック
def calculate_recommended_order(row):
    if row["quantity_sold"] > 0:
        lot = row.get("order_lot", 0)
        if pd.isna(lot) or lot <= 0:
            return 0
        return ((row["quantity_sold"] // lot) + 1) * lot
    return 0

df["推奨発注数"] = df.apply(calculate_recommended_order, axis=1)
df["発注必要"] = df["推奨発注数"] > 0

# 発注対象商品のみ表示
order_df = df[df["発注必要"] == True][[
    "jan", "maker", "name", "quantity_sold", "order_lot", "推奨発注数"
]]

st.subheader("📝 発注対象リスト")
st.dataframe(order_df)

# CSVダウンロードボタン
if not order_df.empty:
    csv = order_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 CSVダウンロード",
        data=csv,
        file_name="order_list.csv",
        mime="text/csv"
    )
