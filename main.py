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

            if "jan" in df.columns:
                df["jan"] = pd.to_numeric(df["jan"], errors="coerce").fillna(0).astype("int64").astype(str).str.strip()

            # 🔁 全削除（上書き動作）
            del_res = requests.delete(f"{SUPABASE_URL}/rest/v1/purchase_data", headers=HEADERS)
            if del_res.status_code not in [200, 204]:
                st.error(f"❌ テーブル初期化に失敗: {del_res.status_code} {del_res.text}")
                return

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
