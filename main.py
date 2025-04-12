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
mode = st.sidebar.radio("操作を選択", ["📦 発注＆アップロード", "📚 商品情報DB検索"])

@st.cache_data
def fetch_table(table_name):
    url = f"{SUPABASE_URL}/rest/v1/{table_name}?select=*"
    res = requests.get(url, headers=HEADERS)
    if res.status_code == 200:
        return pd.DataFrame(res.json())
    else:
        st.error(f"{table_name} の取得に失敗しました: {res.text}")
        return pd.DataFrame()

# --- 発注＆アップロードモード ---
if mode == "📦 発注＆アップロード":
    st.header("📤 CSVアップロード")
    st.subheader("🧾 商品マスター（products）")
    file1 = st.file_uploader("CSVファイルをアップロード", type="csv", key="upload1")
    if file1 is not None:
        try:
            df = pd.read_csv(file1)
            df["jan"] = df["jan"].astype(str).str.strip()
            df = df.drop_duplicates(subset="jan", keep="last")
            for _, row in df.iterrows():
                requests.post(
                    f"{SUPABASE_URL}/rest/v1/products?on_conflict=jan",
                    headers=HEADERS,
                    json=row.where(pd.notnull(row), None).to_dict()
                )
            st.success("✅ 商品マスターを Supabase に保存しました")
        except Exception as e:
            st.error(f"❌ 商品マスターCSVの読み込み中にエラー: {e}")

    st.subheader("📈 販売実績（sales）")
    file2 = st.file_uploader("CSVファイルをアップロード", type="csv", key="upload2")
    if file2 is not None:
        try:
            df = pd.read_csv(file2)
            df["jan"] = df["jan"].astype(str).str.strip()
            df = df.drop_duplicates(subset="jan", keep="last")
            for _, row in df.iterrows():
                requests.post(
                    f"{SUPABASE_URL}/rest/v1/sales?on_conflict=jan",
                    headers=HEADERS,
                    json=row.where(pd.notnull(row), None).to_dict()
                )
            st.success("✅ 販売実績を Supabase に保存しました")
        except Exception as e:
            st.error(f"❌ 販売実績CSVの読み込み中にエラー: {e}")

    st.header("📦 発注判定")
    df_products = fetch_table("products")
    df_sales = fetch_table("sales")

    if df_products.empty or df_sales.empty:
        st.warning("商品マスターまたは販売実績が不足しています。アップロードしてください。")
        st.stop()

    df_products["jan"] = df_products["jan"].astype(str).str.strip()
    df_sales["jan"] = df_sales["jan"].astype(str).str.strip()

    df_products = df_products.drop_duplicates(subset="jan", keep="last")
    df_sales = df_sales.drop_duplicates(subset="jan", keep="last")

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

# --- 商品情報DB検索モード ---
elif mode == "📚 商品情報DB検索":
    st.header("📚 商品情報検索システム")
    file = st.file_uploader("CSVファイルをアップロード", type="csv", key="item_master_upload")

    if file:
        try:
            df_upload = pd.read_csv(file)
            df_upload.columns = df_upload.columns.str.strip().str.lower()
            df_upload["jan"] = df_upload["jan"].astype(str).str.strip()

            if "入数" in df_upload.columns:
                df_upload["入数"] = pd.to_numeric(df_upload["入数"], errors="coerce").fillna(0).round().astype(int)

            df_upload = df_upload.drop_duplicates(subset="jan", keep="last")
            st.write("🧾 アップロード内容プレビュー", df_upload.head())

            for _, row in df_upload.iterrows():
                clean_row = {}
                for k, v in row.items():
                    if pd.isnull(v):
                        clean_row[k] = None
                    elif k == "入数":
                        try:
                            clean_row[k] = int(float(v))
                        except:
                            clean_row[k] = 0
                    else:
                        clean_row[k] = v

                res = requests.post(
                    f"{SUPABASE_URL}/rest/v1/item_master?on_conflict=jan",
                    headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
                    json=clean_row
                )
                st.write(f"📤 POST {clean_row.get('jan')} → {res.status_code}: {res.text}")

            st.success("✅ item_master にアップロード完了")

            view_cols = ["jan", "担当者", "状態", "ブランド", "商品名", "仕入価格", "ケース入数", "重量", "入数", "発注済"]
            available_cols = [col for col in view_cols if col in df_upload.columns]

            st.subheader("📋 アップロード済み商品一覧")
            st.dataframe(df_upload[available_cols].sort_values(by="jan"))

            csv = df_upload[available_cols].to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="📥 CSVダウンロード",
                data=csv,
                file_name="item_master_search.csv",
                mime="text/csv"
            )

        except Exception as e:
            st.error(f"❌ アップロード失敗: {e}")

    df_master = fetch_table("item_master")
    if not df_master.empty:
        st.subheader("📦 item_master一覧（DBから取得）")
        view_cols = ["jan", "担当者", "状態", "ブランド", "商品名", "仕入価格", "ケース入数", "重量", "入数", "発注済"]
        available_cols = [col for col in view_cols if col in df_master.columns]
        st.dataframe(df_master[available_cols].sort_values(by="jan"))
