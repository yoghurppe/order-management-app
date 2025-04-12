
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
st.title("📦 発注管理システム（デバッグ版）")

@st.cache_data
def fetch_table(table_name):
    res = requests.get(f"{SUPABASE_URL}/rest/v1/{table_name}?select=*", headers=HEADERS)
    if res.status_code == 200:
        return pd.DataFrame(res.json())
    st.error(f"{table_name} の取得に失敗: {res.text}")
    return pd.DataFrame()

# データ取得
df_sales = fetch_table("sales")
df_purchase = fetch_table("purchase_data")

# デバッグ出力
st.subheader("✅ デバッグ: データベース取得結果")
st.write(f"✅ df_sales 件数: {len(df_sales)}")
st.write(f"✅ df_purchase 件数: {len(df_purchase)}")
st.write("✅ df_sales.columns:", df_sales.columns.tolist())
st.write("✅ df_purchase.columns:", df_purchase.columns.tolist())
if not df_sales.empty:
    st.write("✅ df_sales サンプル:", df_sales.head())
if not df_purchase.empty:
    st.write("✅ df_purchase サンプル:", df_purchase.head())

# 判定条件
if df_sales.empty or df_purchase.empty:
    st.warning("販売実績または仕入データが不足しています。")
    st.stop()

# 判定処理（簡略版）
st.success("📦 判定処理を実行可能です！（テーブルにデータがあります）")
