import streamlit as st
import pandas as pd
import requests
import os
import math
import re

# 言語選択
language = st.sidebar.selectbox("\ud83c\udf10 言語 / Language", ["日本語", "中文"], key="language")

# ユーザー表示用ラベルテキスト
TEXT = {
    "日本語": {
        "title_order_ai": "\ud83d\udce6 発注AI（利用可能在庫で判断）",
        "mode_select": "モードを選んでください",
        "upload_csv": "\ud83d\udcc4 CSVアップロード",
        "order_ai": "\ud83d\udce6 発注AI判定",
        "search_item": "\ud83d\udd0d 商品情報検索",
        "upload_item": "\ud83d\udcc4 商品情報CSVアップロード",
        "price_improve": "\ud83d\udcb0 仕入価格改善リスト",
        "search_keyword": "商品名・商品コードで検索",
        "search_brand": "ブランドで絞り込み",
        "search_type": "取扱区分で絞り込み",
        "product_list": "\ud83d\udccb 商品一覧"
    },
    "中文": {
        "title_order_ai": "\ud83d\udce6 订货AI（根据可用库存）",
        "mode_select": "请选择模式",
        "upload_csv": "\ud83d\udcc4 上传CSV",
        "order_ai": "\ud83d\udce6 订货AI判断",
        "search_item": "\ud83d\udd0d 商品信息查询",
        "upload_item": "\ud83d\udcc4 上传商品信息CSV",
        "price_improve": "\ud83d\udcb0 进货价格优化清单",
        "search_keyword": "按商品名称或编号搜索",
        "search_brand": "按品牌筛选",
        "search_type": "按分类筛选",
        "product_list": "\ud83d\udccb 商品列表"
    }
}

# 列名マッピング
COLUMN_NAMES = {
    "日本語": {
        "商品コード": "商品コード",
        "jan": "JAN",
        "ランク": "ランク",
        "ブランド": "ブランド",
        "商品名": "商品名",
        "取扱区分": "取扱区分",
        "在庫": "在庫",
        "利用可能": "利用可能",
        "発注済": "発注済",
        "仕入価格": "仕入価格",
        "ケース入数": "ケース入数",
        "発注ロット": "発注ロット",
        "重量": "重量(g)"
    },
    "中文": {
        "商品コード": "商品编号",
        "jan": "条码",
        "ランク": "等级",
        "ブランド": "品牌",
        "商品名": "商品名称",
        "取扱区分": "分类",
        "在庫": "库存",
        "利用可能": "可用库存",
        "発注済": "已订购",
        "仕入価格": "进货价",
        "ケース入数": "箱入数",
        "発注ロット": "订购单位",
        "重量": "重量(g)"
    }
}

# タイトル
st.set_page_config(page_title=TEXT[language]["title_order_ai"])
st.title(TEXT[language]["title_order_ai"])

# モード選択
mode = st.sidebar.radio(TEXT[language]["mode_select"], [
    TEXT[language]["upload_csv"],
    TEXT[language]["order_ai"],
    TEXT[language]["search_item"],
    TEXT[language]["upload_item"],
    TEXT[language]["price_improve"]
])


def fetch_table_cached(table_name):
    if table_name not in st.session_state:
        headers = {**HEADERS, "Prefer": "count=exact"}
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
                st.session_state[table_name] = pd.DataFrame()
                return
            data = res.json()
            if not data:
                break
            dfs.append(pd.DataFrame(data))
            offset += limit
        df = pd.concat(dfs, ignore_index=True)
        st.session_state[table_name] = df
    st.write(f"📦 {table_name} 件数: {len(st.session_state[table_name])}")
    return st.session_state[table_name]

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

mode = st.sidebar.radio("モードを選んでください", ["📤 CSVアップロード", "📦 発注AI判定", "🔍 商品情報検索", "📤 商品情報CSVアップロード", "💰 仕入価格改善リスト"])



if mode == "📤 CSVアップロード":
    st.header("📤 CSVアップロード")

    def preprocess_csv(df, table):
        df.columns = df.columns.str.strip()

        if table == "sales":
            df.rename(columns={
                "アイテム": "jan",
                "取扱区分": "handling_type",
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
                        df[col] = df[col].round().astype(int)
            df["jan"] = df["jan"].apply(normalize_jan)

        return df

    def batch_upload_csv_to_supabase(file_path, table):
        try:
            df = pd.read_csv(file_path)
            df = preprocess_csv(df, table)

            url = f"{SUPABASE_URL}/rest/v1/{table}?id=gt.0"
            requests.delete(url, headers=HEADERS)

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
        with st.spinner("📤 sales.csv アップロード中..."):
            temp_path = "/tmp/sales.csv"
            with open(temp_path, "wb") as f:
                f.write(sales_file.read())
            batch_upload_csv_to_supabase(temp_path, "sales")

    purchase_file = st.file_uploader("📦 purchase_data.csv アップロード", type="csv")
    if purchase_file:
        with st.spinner("📤 purchase_data.csv アップロード中..."):
            temp_path = "/tmp/purchase_data.csv"
            with open(temp_path, "wb") as f:
                f.write(purchase_file.read())
            batch_upload_csv_to_supabase(temp_path, "purchase_data")

if mode == "📦 発注AI判定":
    with st.spinner("📦 データを読み込み中..."):
        st.header("📦 発注AI（利用可能在庫ベース）")

        df_sales = fetch_table_cached("sales")
        df_purchase = fetch_table_cached("purchase_data")

    if df_sales.empty or df_purchase.empty:
        st.warning("販売実績または仕入データが不足しています。")
        st.stop()

    

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

    with st.spinner("🤖 発注AIを計算中..."):
        results = []
        for _, row in df_sales.iterrows():
            jan = row["jan"]
            sold = row["quantity_sold"]
            stock = row.get("stock_available", 0)
            ordered = row.get("stock_ordered", 0)
            options = df_purchase[df_purchase["jan"] == jan].copy()
            if options.empty:
                continue

            if stock >= sold:
                need_qty = 0
            else:
                need_qty = sold - stock + math.ceil(sold * 0.5) - ordered
                need_qty = max(need_qty, 0)

            if need_qty <= 0:
                continue

            options = options[options["order_lot"] > 0]
            options["diff"] = (options["order_lot"] - need_qty).abs()

            smaller_lots = options[options["order_lot"] <= need_qty]

            if not smaller_lots.empty:
                best_option = smaller_lots.loc[smaller_lots["diff"].idxmin()]
            else:
                near_lots = options[(options["order_lot"] > need_qty) & (options["order_lot"] <= need_qty * 1.5) & (options["order_lot"] != 1)]
                if not near_lots.empty:
                    best_option = near_lots.loc[near_lots["diff"].idxmin()]
                else:
                    one_lot = options[options["order_lot"] == 1]
                    if not one_lot.empty:
                        best_option = one_lot.iloc[0]
                    else:
                        best_option = options.sort_values("order_lot").iloc[0]  # 最小ロットを選ぶ

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

        st.markdown("---")
        st.subheader("📦 仕入先別ダウンロード")
        for supplier, group in result_df.groupby("仕入先"):
            supplier_csv = group.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label=f"📥 {supplier} 用 発注CSVダウンロード",
                data=supplier_csv,
                file_name=f"orders_{supplier}.csv",
                mime="text/csv"
            )
    else:
        st.info("現在、発注が必要な商品はありません。")

# 商品情報検索
if mode == "🔍 商品情報検索":
    st.header("🔍 商品情報DB検索")

    @st.cache_resource
    def fetch_item_master():
        url = f"{SUPABASE_URL}/rest/v1/item_master?select=*"
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            return pd.DataFrame(res.json())
        st.error("item_master の取得に失敗しました")
        return pd.DataFrame()

    if "df_master" not in st.session_state:
        st.session_state.df_master = fetch_item_master()

    df_master = st.session_state.df_master

    if df_master.empty:
        st.warning("商品情報データベースにデータが存在しません。")
        st.stop()

    df_master["jan"] = df_master["jan"].astype(str)
    df_master["商品コード"] = df_master["商品コード"].astype(str)
    df_master["商品名"] = df_master["商品名"].astype(str)

    st.subheader("🔎 検索条件")

    keyword = st.text_input("商品名・商品コードで検索", "")
    brand_filter = st.selectbox("ブランドで絞り込み", ["すべて"] + sorted(df_master["ブランド"].dropna().unique()))
    type_filter = st.selectbox("取扱区分で絞り込み", ["すべて"] + sorted(df_master["取扱区分"].dropna().unique()))

    df_view = df_master.copy()

    if keyword:
        df_view = df_view[
            df_view["商品名"].str.contains(keyword, case=False, na=False) |
            df_view["商品コード"].str.contains(keyword, case=False, na=False)
        ]
    if brand_filter != "すべて":
        df_view = df_view[df_view["ブランド"] == brand_filter]
    if type_filter != "すべて":
        df_view = df_view[df_view["取扱区分"] == type_filter]

    view_cols = [
        "商品コード", "jan", "ランク", "ブランド", "商品名", "取扱区分",
        "在庫", "利用可能", "発注済", "仕入価格", "ケース入数", "発注ロット", "重量"
    ]
    rename_map = {
        "商品コード": "商品コード/商品编号",
        "jan": "JAN",
        "ランク": "ランク/等级",  # ←★追加
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
    available_cols = [col for col in view_cols if col in df_view.columns]

    st.subheader("📋 商品一覧")
    display_df = df_view[available_cols].sort_values(by="商品コード")
    display_df = display_df.rename(columns=rename_map)
    st.dataframe(display_df)

    csv = display_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 CSVダウンロード", data=csv, file_name="item_master_filtered.csv", mime="text/csv")



# 商品情報CSVアップロード
if mode == "📤 商品情報CSVアップロード":
    st.header("📤 商品情報CSVアップロード")

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
            "商品ランク": "ランク"  # ←★追加
        }, inplace=True)
        # 不要な列を削除
        df.drop(columns=["内部ID"], inplace=True, errors="ignore")

        for col in ["ケース入数", "発注ロット", "在庫", "利用可能", "発注済"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).round().astype(int)
    
        df["jan"] = df["jan"].apply(normalize_jan)
        return df

    item_file = st.file_uploader("🧾 item_master.csv アップロード", type="csv")
    if item_file:
        temp_path = "/tmp/item_master.csv"
        with open(temp_path, "wb") as f:
            f.write(item_file.read())

        try:
            df = pd.read_csv(temp_path)
            df = preprocess_item_master(df)
        
            # Supabaseテーブル初期化（既存削除）
            requests.delete(f"{SUPABASE_URL}/rest/v1/item_master?id=gt.0", headers=HEADERS)
        
            # 商品コードをキーに重複排除
            df = df.drop_duplicates(subset=["商品コード"], keep="last")
        
            # 🔽 ID付与
            if "id" not in df.columns:
                df.insert(0, "id", range(1, len(df) + 1))
        
            # NaN・inf を JSON互換な None に変換
            df = df.replace({pd.NA: None, pd.NaT: None, float('nan'): None, float('inf'): None, -float('inf'): None})
            df = df.where(pd.notnull(df), None)
        
            # バッチPOST
            batch_size = 500
            for i in range(0, len(df), batch_size):
                batch = df.iloc[i:i+batch_size].to_dict(orient="records")
                res = requests.post(
                    f"{SUPABASE_URL}/rest/v1/item_master",
                    headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
                    json=batch
                )
                if res.status_code not in [200, 201]:
                    st.error(f"❌ バッチPOST失敗: {res.status_code} {res.text}")
                    break
            else:
                st.success(f"✅ item_master に {len(df)} 件アップロード完了")
        except Exception as e:
            st.error(f"❌ item_master のアップロード中にエラー: {e}")

if mode == "💰 仕入価格改善リスト":
    with st.spinner("📊 データを読み込み中..."):
        df_sales = fetch_table_cached("sales")
        df_purchase = fetch_table_cached("purchase_data")
        df_item = fetch_table_cached("item_master")
        df_sales["jan"] = df_sales["jan"].apply(normalize_jan)
        df_purchase["jan"] = df_purchase["jan"].apply(normalize_jan)
        df_item["jan"] = df_item["jan"].apply(normalize_jan)
        df_purchase["price"] = pd.to_numeric(df_purchase["price"], errors="coerce").fillna(0)

    # 発注AIから現在の仕入価格を再現
    current_prices = {}
    for _, row in df_sales.iterrows():
        jan = row["jan"]
        sold = row["quantity_sold"]
        stock = row.get("stock_available", 0)
        ordered = row.get("stock_ordered", 0)
        options = df_purchase[df_purchase["jan"] == jan].copy()
        if options.empty:
            continue

        if stock >= sold:
            need_qty = 0
        else:
            need_qty = sold - stock + math.ceil(sold * 0.5) - ordered
            need_qty = max(need_qty, 0)

        if need_qty <= 0:
            continue

        options = options[options["order_lot"] > 0]
        options["diff"] = (options["order_lot"] - need_qty).abs()

        smaller_lots = options[options["order_lot"] <= need_qty]

        if not smaller_lots.empty:
            best_option = smaller_lots.loc[smaller_lots["diff"].idxmin()]
        else:
            near_lots = options[(options["order_lot"] > need_qty) & (options["order_lot"] <= need_qty * 1.5) & (options["order_lot"] != 1)]
            if not near_lots.empty:
                best_option = near_lots.loc[near_lots["diff"].idxmin()]
            else:
                one_lot = options[options["order_lot"] == 1]
                if not one_lot.empty:
                    best_option = one_lot.iloc[0]
                else:
                    best_option = options.sort_values("order_lot").iloc[0]

        current_prices[jan] = best_option["price"]

    # 最安値取得
    min_prices = df_purchase.groupby("jan")["price"].min().to_dict()

    rows = []
    for jan, current_price in current_prices.items():
        if jan in min_prices and min_prices[jan] < current_price:
            item = df_item[df_item["jan"] == jan].head(1)
            if not item.empty:
                row = {
                    "商品コード": item.iloc[0].get("item_code", ""),
                    "JAN": jan,
                    "ブランド": item.iloc[0].get("brand", ""),
                    "現在の仕入価格": current_price,
                    "最安値の仕入価格": min_prices[jan],
                    "差分": round(min_prices[jan] - current_price, 2)
                }
                rows.append(row)

    if rows:
        df_result = pd.DataFrame(rows)
        st.success(f"✅ 改善対象商品数: {len(df_result)} 件")
        st.dataframe(df_result)
        csv = df_result.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 改善リストCSVダウンロード", data=csv, file_name="price_improvement_list.csv", mime="text/csv")
    else:
        st.info("改善の余地がある商品は見つかりませんでした。")
