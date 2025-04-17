import streamlit as st
import pandas as pd
import requests
import os
import math
import re

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def fetch_table(table_name):
    headers = {
        **HEADERS,
        "Prefer": "count=exact"
    }
    dfs = []
    offset = 0
    limit = 1000

    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table_name}?select=*&offset={offset}&limit={limit}"
        res = requests.get(url, headers=headers)
        if res.status_code == 416:
            break
        if res.status_code not in [200, 206]:
            st.error(f"{table_name} の取得に失敗: {res.status_code} / {res.text}")
            return pd.DataFrame()
        data = res.json()
        if not data:
            break
        dfs.append(pd.DataFrame(data))
        offset += limit

    if dfs:
        return pd.concat(dfs, ignore_index=True)
    return pd.DataFrame()

def normalize_jan(x):
    try:
        if re.fullmatch(r"\d+(\.0+)?", str(x)):
            return str(int(float(x)))
        else:
            return str(x).strip()
    except:
        return ""

# 商品マスタを取得（dfが未定義エラー回避のため）
df = fetch_table("items")

# 表示用の列と表示名マッピング
view_cols = [
    "商品コード", "jan", "ランク", "ブランド", "商品名", "取扱区分",
    "在庫", "利用可能", "発注済", "仕入価格", "ケース入数", "発注ロット", "重量"
]
rename_map = {
    "商品コード": "商品コード/商品编号",
    "jan": "JAN",
    "ランク": "ランク/等级",
    "ブランド": "ブランド/品牌",
    "商品名": "商品名/商品名称",
    "取扱区分": "取扱区分/分类",
    "在庫": "在庫/库存",
    "利用可能": "利用可能/可用库存",
    "発注済": "発注済/已订购",
    "仕入価格": "仕入価格/进货价",
    "ケース入数": "ケース入数/箱入数",
    "発注ロット": "発注ロット/订购单位",
    "重量": "重量/重量(g)"
}
available_cols = [col for col in view_cols if col in df.columns]

# 商品情報CSVアップロード処理
st.header("📤 商品情報CSVアップロード")
uploaded_file = st.file_uploader("商品情報CSVをアップロード", type="csv")

if uploaded_file is not None:
    df_upload = pd.read_csv(uploaded_file)

    def preprocess_item_master(df):
        df.rename(columns={
            "UPCコード": "jan",
            "表示名": "商品名",
            "メーカー名": "ブランド",
            "アイテム定義原価": "仕入価格",
            "カートン入数": "ケース入数",
            "発注ロット": "発注ロット",
            "パッケージ重量(g)": "重量",
            "手持": "在庫",
            "利用可能": "利用可能",
            "注文済": "発注済",
            "名前": "商品コード",
            "商品ランク": "ランク"
        }, inplace=True)
        df["jan"] = df["jan"].apply(normalize_jan)
        return df

    df_upload = preprocess_item_master(df_upload)

    if "jan" in df_upload.columns and "ランク" in df_upload.columns:
        for _, row in df_upload.iterrows():
            payload = {
                "rank": row["ランク"]
            }
            res = requests.patch(
                f"{SUPABASE_URL}/rest/v1/items?jan=eq.{row['jan']}",
                headers={**HEADERS, "Content-Type": "application/json"},
                json=payload
            )
            if res.status_code not in [200, 204]:
                st.error(f"JAN {row['jan']} の更新に失敗しました: {res.status_code} / {res.text}")
        st.success("CSVからのランク更新が完了しました")
    else:
        st.error("CSVに必要な 'jan' または '商品ランク'（→ランク）列が存在しません")
