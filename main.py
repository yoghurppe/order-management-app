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
mode = st.sidebar.radio("操作を選択", ["📤 CSVアップロード", "📦 発注判定", "🔎 商品検索"])

# --- 商品検索モード ---
if mode == "🔎 商品検索":
    st.header("🔎 商品検索・表示システム")

    def fetch_table(table_name):
        url = f"{SUPABASE_URL}/rest/v1/{table_name}?select=*"
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            return pd.DataFrame(res.json())
        else:
            st.error(f"{table_name} の取得に失敗しました: {res.text}")
            return pd.DataFrame()

    df = fetch_table("products")

    if df.empty:
        st.warning("商品マスターにデータが存在しません。")
        st.stop()

    df["jan"] = df["jan"].astype(str).str.strip()
    df = df.drop_duplicates(subset="jan", keep="last")

    # 検索・フィルター UI
    col1, col2, col3 = st.columns(3)
    with col1:
        jan_query = st.text_input("JANで検索")
        status_filter = st.selectbox("状態", options=["すべて"] + sorted(df["状態"].dropna().unique().tolist()))
    with col2:
       担当_filter = st.selectbox("担当者", options=["すべて"] + sorted(df["担当者"].dropna().unique().tolist()))
        brand_filter = st.selectbox("ブランド", options=["すべて"] + sorted(df["ブランド"].dropna().unique().tolist()))
    with col3:
        keyword = st.text_input("商品名で検索（部分一致）")
        発注済_filter = st.checkbox("発注済（0以外）")

    # 条件でフィルター
    if jan_query:
        df = df[df["jan"].str.contains(jan_query)]
    if status_filter != "すべて":
        df = df[df["状態"] == status_filter]
    if 担当_filter != "すべて":
        df = df[df["担当者"] == 担当_filter]
    if brand_filter != "すべて":
        df = df[df["ブランド"] == brand_filter]
    if keyword:
        df = df[df["商品名"].str.contains(keyword, case=False, na=False)]
    if 発注済_filter:
        df = df[df["発注済"] != 0]

    # 表示列選択
    view_cols = ["jan", "担当者", "状態", "ブランド", "商品名", "仕入価格", "ケース入数", "重量", "発注済"]
    st.dataframe(df[view_cols].sort_values(by="jan"))

    # CSVダウンロード
    if not df.empty:
        csv = df[view_cols].to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 CSVダウンロード",
            data=csv,
            file_name="search_results.csv",
            mime="text/csv"
        )
