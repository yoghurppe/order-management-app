import streamlit as st
import pandas as pd
import requests
import os
import math
import re

def normalize_jan(x):
    try:
        if re.fullmatch(r"\d+(\.0+)?", str(x)):
            return str(int(float(x)))
        else:
            return str(x).strip()
    except:
        return ""
      
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

st.set_page_config(page_title="発注AI（納品タイミング + 利用可能在庫）", layout="wide")
st.title("📦 発注AI（利用可能在庫で判断）")

mode = st.sidebar.radio("モードを選んでください", ["📤 CSVアップロード", "📦 発注AI判定", "🔍 商品情報検索", "📤 商品情報CSVアップロード"])




if mode == "📤 CSVアップロード":
    st.header("📤 CSVアップロード")

    def preprocess_csv(df, table):
        if table == "sales":
            df.rename(columns={
                "アイテム": "jan",
                "販売数量": "quantity_sold",
                "現在の手持数量": "stock_total",
                "現在の利用可能数量": "stock_available",
                "現在の注文済数量": "stock_ordered"
            }, inplace=True)
            for col in ["quantity_sold", "stock_total", "stock_available", "stock_ordered"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
            df["jan"] = df["jan"].apply(normalize_jan)

        if table == "purchase_data":
            for col in ["order_lot", "price"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(",", "")
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                    if col == "order_lot":
                        df[col] = df[col].round().astype(int)  # ← ロット1を除外しないように修正
            df["jan"] = df["jan"].apply(normalize_jan)


        return df

    def batch_upload_csv_to_supabase(file_path, table):
        try:
            df = pd.read_csv(file_path)
            df = preprocess_csv(df, table)

            url = f"{SUPABASE_URL}/rest/v1/{table}?id=gt.0"
            requests.delete(url, headers=HEADERS)  # 初期化

            if table == "purchase_data":
                df = df.drop_duplicates(subset=["jan", "supplier", "order_lot"], keep="last")
            else:
                df = df.drop_duplicates(subset=["jan"], keep="last")

            batch_size = 500
            for i in range(0, len(df), batch_size):
                batch = df.iloc[i:i+batch_size].where(pd.notnull(df.iloc[i:i+batch_size]), None).to_dict(orient="records")
                res = requests.post(
                    f"{SUPABASE_URL}/rest/v1/{table}",
                    headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
                    json=batch
                )
                if res.status_code not in [200, 201]:
                    st.error(f"❌ バッチPOST失敗: {res.status_code} {res.text}")
                    return
            st.success(f"✅ {table} に {len(df)} 件アップロード完了")
        except Exception as e:
            st.error(f"❌ {table} のアップロード中にエラー: {e}")

    sales_file = st.file_uploader("🧾 sales.csv アップロード", type="csv")
    if sales_file:
        temp_path = "/tmp/sales.csv"
        with open(temp_path, "wb") as f:
            f.write(sales_file.read())
        batch_upload_csv_to_supabase(temp_path, "sales")

    purchase_file = st.file_uploader("📦 purchase_data.csv アップロード", type="csv")
    if purchase_file:
        temp_path = "/tmp/purchase_data.csv"
        with open(temp_path, "wb") as f:
            f.write(purchase_file.read())
        batch_upload_csv_to_supabase(temp_path, "purchase_data")

if mode == "📦 発注AI判定":
    st.header("📦 発注AI（利用可能在庫ベース）")

    @st.cache_data(ttl=1)
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

        df = pd.concat(dfs, ignore_index=True)
        st.write(f"📦 {table_name} 件数: {len(df)}")
        return df

    df_sales = fetch_table("sales")
    df_purchase = fetch_table("purchase_data")

    if df_sales.empty or df_purchase.empty:
        st.warning("販売実績または仕入データが不足しています。")
        st.stop()

    df_sales["jan"] = df_sales["jan"].apply(normalize_jan)
    df_purchase["jan"] = df_purchase["jan"].apply(normalize_jan)

    df_sales["quantity_sold"] = pd.to_numeric(df_sales["quantity_sold"], errors="coerce").fillna(0).astype(int)
    df_sales["stock_available"] = pd.to_numeric(df_sales["stock_available"], errors="coerce").fillna(0).astype(int)
    df_sales["stock_ordered"] = pd.to_numeric(df_sales["stock_ordered"], errors="coerce").fillna(0).astype(int)
    df_purchase["order_lot"] = pd.to_numeric(df_purchase["order_lot"], errors="coerce").fillna(0).astype(int)
    df_purchase["price"] = pd.to_numeric(df_purchase["price"], errors="coerce").fillna(0)

    MAX_MONTHS_OF_STOCK = 3
    results = []

    for _, row in df_sales.iterrows():
        jan = row["jan"]
        sold = row["quantity_sold"]
        stock = row.get("stock_available", 0)
        ordered = row.get("stock_ordered", 0)

        options = df_purchase[df_purchase["jan"] == jan].copy()
        if options.empty:
            continue

        options["price"] = pd.to_numeric(options["price"], errors="coerce")

        if stock >= sold:
            need_qty = 0
        else:
            need_qty = sold - stock
            need_qty += math.ceil(sold * 0.5)
            need_qty -= ordered  # 発注済み分を差し引く
            need_qty = max(need_qty, 0)

        if need_qty <= 0:
            continue

        options = options[options["order_lot"] > 0]
        options["diff"] = (options["order_lot"] - need_qty).abs()

        smaller_lots = options[options["order_lot"] <= need_qty]

        if not smaller_lots.empty:
            best_option = smaller_lots.loc[smaller_lots["diff"].idxmin()]
        else:
            near_lots = options[(options["order_lot"] > need_qty) & (options["order_lot"] <= need_qty * 1.2) & (options["order_lot"] != 1)]
            if not near_lots.empty:
                best_option = near_lots.loc[near_lots["diff"].idxmin()]
            else:
                one_lot = options[options["order_lot"] == 1]
                if one_lot.empty:
                    continue
                best_option = one_lot.iloc[0]

        sets = math.ceil(need_qty / best_option["order_lot"])
        qty = sets * best_option["order_lot"]
        total_cost = qty * best_option["price"]

        best_plan = {
            "jan": jan,
            "販売実績": sold,
            "在庫": stock,
            "発注済": ordered,
            "理論必要数": need_qty,
            "発注数": qty,
            "ロット": best_option["order_lot"],
            "数量": round(qty / best_option["order_lot"], 2),
            "単価": best_option["price"],
            "総額": total_cost,
            "仕入先": best_option.get("supplier", "不明")
        }
        results.append(best_plan)

    if results:
        result_df = pd.DataFrame(results)
        column_order = ["jan", "販売実績", "在庫", "発注済", "理論必要数", "発注数", "ロット", "数量", "単価", "総額", "仕入先"]
        result_df = result_df[[col for col in column_order if col in result_df.columns]]
        st.success(f"✅ 発注対象: {len(result_df)} 件")
        st.dataframe(result_df)
        csv = result_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 発注CSVダウンロード", data=csv, file_name="orders_available_based.csv", mime="text/csv")
    else:
        st.info("現在、発注が必要な商品はありません。")

# --- 商品情報DB検索機能 ---
if mode == "🔍 商品情報検索":
    st.header("🔍 商品情報DB検索")

    @st.cache_data(ttl=60)
    def fetch_item_master():
        url = f"{SUPABASE_URL}/rest/v1/item_master?select=*"
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            return pd.DataFrame(res.json())
        st.error("item_master の取得に失敗しました")
        return pd.DataFrame()

    df_master = fetch_item_master()
    if df_master.empty:
        st.warning("商品情報データベースにデータが存在しません。")
        st.stop()

    df_master["jan"] = df_master["jan"].astype(str)

    st.subheader("🔎 検索条件")

    keyword = st.text_input("商品名で検索", "")
    brand_filter = st.selectbox("ブランドで絞り込み", ["すべて"] + sorted(df_master["ブランド"].dropna().unique()))
    status_filter = st.selectbox("状態で絞り込み", ["すべて"] + sorted(df_master["状態"].dropna().unique()))
    buyer_filter = st.selectbox("担当者で絞り込み", ["すべて"] + sorted(df_master["担当者"].dropna().unique()))
    order_flag = st.checkbox("発注済以外のみ表示")

    df_view = df_master.copy()

    if keyword:
        df_view = df_view[df_view["商品名"].astype(str).str.contains(keyword, case=False, na=False)]
    if brand_filter != "すべて":
        df_view = df_view[df_view["ブランド"] == brand_filter]
    if status_filter != "すべて":
        df_view = df_view[df_view["状態"] == status_filter]
    if buyer_filter != "すべて":
        df_view = df_view[df_view["担当者"] == buyer_filter]
    if order_flag and "発注済" in df_view.columns:
        df_view = df_view[df_view["発注済"] != 1]

    view_cols = ["jan", "担当者", "状態", "ブランド", "商品名", "仕入価格", "ケース入数", "重量", "発注済"]
    available_cols = [col for col in view_cols if col in df_view.columns]

    st.subheader("📋 商品一覧")
    st.dataframe(df_view[available_cols].sort_values(by="jan"))

    csv = df_view[available_cols].to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 CSVダウンロード", data=csv, file_name="item_master_filtered.csv", mime="text/csv")
