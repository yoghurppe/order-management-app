import streamlit as st
import pandas as pd
import requests

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
mode = st.sidebar.radio("操作を選択", ["📤 CSVアップロード", "📦 発注判定"])

# --- CSVアップロードモード ---
if mode == "📤 CSVアップロード":
    st.header("🧾 商品マスター（products）")
    file1 = st.file_uploader("CSVファイルをアップロード", type="csv", key="upload1")
    if file1:
        df = pd.read_csv(file1)
        for _, row in df.iterrows():
            requests.post(
                f"{SUPABASE_URL}/rest/v1/products",
                headers=HEADERS,
                json=row.to_dict()
            )
        st.success("✅ 商品マスターを Supabase に保存しました")

    st.header("📈 販売実績（sales）")
    file2 = st.file_uploader("CSVファイルをアップロード", type="csv", key="upload2")
    if file2:
        df = pd.read_csv(file2)
        for _, row in df.iterrows():
            requests.post(
                f"{SUPABASE_URL}/rest/v1/sales",
                headers=HEADERS,
                json=row.to_dict()
            )
        st.success("✅ 販売実績を Supabase に保存しました")

# --- 発注判定モード ---
elif mode == "📦 発注判定":
    st.header("📦 発注対象商品リスト")

    @st.cache_data
    def fetch_table(table_name):
        url = f"{SUPABASE_URL}/rest/v1/{table_name}?select=*"
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            return pd.DataFrame(res.json())
        else:
            st.error(f"{table_name} の取得に失敗しました: {res.text}")
            return pd.DataFrame()

    df_products = fetch_table("products")
    df_sales = fetch_table("sales")

    if df_products.empty or df_sales.empty:
        st.warning("商品マスターまたは販売実績が不足しています。アップロードしてください。")
        st.stop()

    df = pd.merge(df_products, df_sales, on="jan", how="inner")

    def calculate_recommended_order(row):
        if row["quantity_sold"] > 0:
            lot = row.get("order_lot", 0)
            if pd.isna(lot) or lot <= 0:
                return 0
            return ((row["quantity_sold"] // lot) + 1) * lot
        return 0

    df["推奨発注数"] = df.apply(calculate_recommended_order, axis=1)
    df["発注必要"] = df["推奨発注数"] > 0

    order_df = df[df["発注必要"] == True][[
        "jan", "maker", "name", "quantity_sold", "order_lot", "推奨発注数"
    ]]

    st.subheader("📝 発注対象リスト")
    st.dataframe(order_df)

    if not order_df.empty:
        csv = order_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 CSVダウンロード",
            data=csv,
            file_name="order_list.csv",
            mime="text/csv"
        )
