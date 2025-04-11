import streamlit as st
import pandas as pd
from supabase import create_client, Client

# Supabase接続情報
SUPABASE_URL = "https://hyndhledwvknysnzrfta.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="発注管理：CSVアップロード", layout="wide")
st.title("📤 Supabase 連携：CSVアップロード")

# 商品マスターアップロード
st.header("🧾 商品マスター（products）")
file1 = st.file_uploader("CSVファイルをアップロード", type="csv", key="upload1")
if file1:
    df = pd.read_csv(file1)
    try:
        data = df.to_dict(orient="records")
        supabase.table("products").insert(data).execute()
        st.success("✅ 商品マスターを Supabase に保存しました")
    except Exception as e:
        st.error(f"❌ エラー発生: {e}")

# 販売実績アップロード
st.header("📈 販売実績（sales）")
file2 = st.file_uploader("CSVファイルをアップロード", type="csv", key="upload2")
if file2:
    df = pd.read_csv(file2)
    try:
        data = df.to_dict(orient="records")
        supabase.table("sales").insert(data).execute()
        st.success("✅ 販売実績を Supabase に保存しました")
    except Exception as e:
        st.error(f"❌ エラー発生: {e}")
