import streamlit as st
import pandas as pd
import requests

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

st.title("📤 Supabase API連携：CSVアップロード")

# 商品マスターアップロード
st.header("🧾 商品マスター（products）")
file1 = st.file_uploader("CSVファイルをアップロード", type="csv")
if file1:
    df = pd.read_csv(file1)
    for _, row in df.iterrows():
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/products",
            headers=HEADERS,
            json=row.to_dict()
        )
    st.success("✅ 商品マスターを Supabase に保存しました")

# 販売実績アップロード
st.header("📈 販売実績（sales）")
file2 = st.file_uploader("CSVファイルをアップロード", type="csv", key="upload2")
if file2:
    df = pd.read_csv(file2)
    for _, row in df.iterrows():
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/sales",
            headers=HEADERS,
            json=row.to_dict()
        )
    st.success("✅ 販売実績を Supabase に保存しました")
