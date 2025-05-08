import streamlit as st
import pandas as pd
import requests
import os
import math
import re
import hashlib
import time
from streamlit_javascript import st_javascript

# ページ設定
st.set_page_config(page_title="管理補助システム", layout="wide")

# 🔑 パスワード（MD5ハッシュ化済）: 例「admin123」
PASSWORD_HASH = "0f754d47528b6393d510866d26f508de"  # MD5("smikie0826")

# 🧠 セッション状態
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# 🍪 クッキー確認
cookie = st_javascript("document.cookie")

# ✅ 認証済み or クッキー有効ならスルー
if st.session_state.authenticated or ("auth_token=valid" in str(cookie)):
    st.session_state.authenticated = True

    # 🔒 ログアウト機能（クッキー削除 + リロード）
    if st.sidebar.button("🔒 ログアウト"):
        st.session_state.authenticated = False
        st_javascript("document.cookie = 'auth_token=; Max-Age=0'; location.reload();")

else:
    st.title("🔐 認証が必要です")

    # ✅ エンターキー対応フォーム
    with st.form("login_form"):
        password = st.text_input("パスワードを入力", type="password")
        submitted = st.form_submit_button("ログイン")

    if submitted:
        hashed = hashlib.md5(password.encode()).hexdigest()
        if hashed == PASSWORD_HASH:
            st.session_state.authenticated = True
            st_javascript("document.cookie = 'auth_token=valid; Max-Age=86400'")
            st.success("✅ 認証成功、リロードします")
            time.sleep(1)
            st.experimental_rerun()
        else:
            st.error("❌ パスワードが違います")

    st.stop()
    
# 🟢 ここからアプリの中身（言語選択など）
language = st.sidebar.selectbox("言語 / Language", ["日本語", "中文"], key="language")

# ユーザー表示用ラベルテキスト
TEXT = {
    "日本語": {
        "title_order_ai": "管理補助システム",
        "mode_select": "モードを選んでください",
        "upload_csv": "CSVアップロード",
        "order_ai": "発注AI判定",
        "search_item": "商品情報検索",
        "upload_item": "商品情報CSVアップロード",
        "price_improve": "仕入価格改善リスト",
        "search_keyword": "商品名・商品コードで検索",
        "search_brand": "メーカー名で絞り込み",
        "search_type": "取扱区分で絞り込み",
        "product_list": "商品一覧",
        "search_keyword": "商品名・商品コードで検索",
        "search_brand": "メーカー名で絞り込み",
        "search_type": "取扱区分で絞り込み",
        "search_rank": "ランクで絞り込み",
        "search_code": "商品コード / JAN",
        "all": "すべて",
        "loading_data": "📊 データを読み込み中..."
    },
    "中文": {
        "title_order_ai": "管理支持系统",
        "mode_select": "请选择模式",
        "upload_csv": "上传CSV",
        "order_ai": "订货AI判断",
        "search_item": "商品信息查询",
        "upload_item": "上传商品信息CSV",
        "price_improve": "进货价格优化清单",
        "search_keyword": "按商品名称或编号搜索",
        "search_brand": "按品牌筛选",
        "search_type": "按分类筛选",
        "product_list": "商品列表",
        "search_keyword": "按商品名称或编号搜索",
        "search_brand": "按制造商筛选",
        "search_type": "按分类筛选",
        "search_rank": "按等级筛选",
        "search_code": "商品编号 / 条码",
        "all": "全部",
        "loading_data": "📊 正在读取数据..."
    }
}

# 列名マッピング
COLUMN_NAMES = {
    "日本語": {
        "商品コード": "商品コード",
        "jan": "JAN",
        "ランク": "ランク",
        "メーカー名": "メーカー名",
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
        "メーカー名": "制造商名称",
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

# 🔐 item_master 最新更新日を取得（sidebar表示用）
SUPABASE_URL_PRE = st.secrets["SUPABASE_URL"]
SUPABASE_KEY_PRE = st.secrets["SUPABASE_KEY"]
HEADERS_PRE = {
    "apikey": SUPABASE_KEY_PRE,
    "Authorization": f"Bearer {SUPABASE_KEY_PRE}",
    "Content-Type": "application/json"
}

def fetch_latest_item_update():
    url = f"{SUPABASE_URL_PRE}/rest/v1/item_master?select=updated_at&order=updated_at.desc&limit=1"
    res = requests.get(url, headers=HEADERS_PRE)
    if res.status_code == 200 and res.json():
        dt = pd.to_datetime(res.json()[0]["updated_at"], errors="coerce")
        if pd.notnull(dt):
            return f"（{dt.strftime('%-m.%d update')}）"
    return ""

item_master_update_text = fetch_latest_item_update()

# タイトル表示
st.title(TEXT[language]["title_order_ai"])

# モード選択（言語に依存しない内部キーで管理）
MODE_KEYS = {
    "home": {
        "日本語": "🏠 トップページ",
        "中文": "🏠 主页"
    },
    "search_item": {
        "日本語": f"🔍 商品情報検索{item_master_update_text}",
        "中文": f"🔍 商品信息查询{item_master_update_text}"
    },
    "price_improve": {
        "日本語": "仕入価格改善リスト",
        "中文": "进货价格优化清单"
    },
    "order_ai": {
        "日本語": "発注AI判定",
        "中文": "订货AI判断"
    },
    "csv_upload": {
        "日本語": "CSVアップロード",
        "中文": "上传CSV"
    },
}

mode_labels = [v[language] for v in MODE_KEYS.values()]
mode_selection = st.sidebar.radio(TEXT[language]["mode_select"], mode_labels, index=0)
mode = next(key for key, labels in MODE_KEYS.items() if labels[language] == mode_selection)


# 各モードの処理分岐
if mode == "home":
    st.subheader("🏠 " + TEXT[language]["title_order_ai"])

    if language == "日本語":
        st.markdown("""
        #### ご利用ありがとうございます。
        左のメニューから操作を選んでください。
        - 📦 発注AI
        - 📤 CSVアップロード
        - 🔍 商品情報検索
        - 💰 仕入価格改善リスト
        """)
    else:
        st.markdown("""
        #### 感谢您的使用。
        请从左侧菜单中选择操作模式。
        - 📦 订货AI
        - 📤 上传CSV
        - 🔍 商品信息查询
        - 💰 进货价格优化清单
        """)

elif mode == "order_ai":
    st.subheader("📦 発注AIモード")

    # ──────────────────────────────
    # 🎛 接続情報
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    # ──────────────────────────────
    # 📥 テーブル全件取得ユーティリティ
    def fetch_table(table_name):
        headers = {**HEADERS, "Prefer": "count=exact"}
        dfs, offset, limit = [], 0, 1000
        while True:
            url = f"{SUPABASE_URL}/rest/v1/{table_name}?select=*&offset={offset}&limit={limit}"
            res = requests.get(url, headers=headers)
            if res.status_code == 416 or not res.json():
                break
            if res.status_code not in [200, 206]:
                st.error(f"{table_name} の取得に失敗: {res.status_code} / {res.text}")
                return pd.DataFrame()
            dfs.append(pd.DataFrame(res.json()))
            offset += limit
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    # ──────────────────────────────
    # 🔧 JAN 正規化
    def normalize_jan(x):
        try:
            if re.fullmatch(r"\d+(\.0+)?", str(x)):
                return str(int(float(x)))
            return str(x).strip()
        except Exception:
            return ""

    # ──────────────────────────────
    # 📤 データ読み込み
    with st.spinner("📦 データを読み込み中..."):
        df_sales    = fetch_table("sales")
        df_purchase = fetch_table("purchase_data")
        df_master   = fetch_table("item_master")

    if df_sales.empty or df_purchase.empty or df_master.empty:
        st.warning("必要なデータが不足しています。")
        st.stop()

    # 正規化
    for df in (df_sales, df_purchase, df_master):
        df["jan"] = df["jan"].apply(normalize_jan)

    # 型変換
    df_sales["quantity_sold"]  = pd.to_numeric(df_sales["quantity_sold"],  errors="coerce").fillna(0).astype(int)
    df_sales["stock_available"] = pd.to_numeric(df_sales["stock_available"], errors="coerce").fillna(0).astype(int)
    df_sales["stock_ordered"]  = pd.to_numeric(df_sales["stock_ordered"],   errors="coerce").fillna(0).astype(int)
    df_purchase["order_lot"]   = pd.to_numeric(df_purchase["order_lot"],    errors="coerce").fillna(0).astype(int)
    df_purchase["price"]       = pd.to_numeric(df_purchase["price"],        errors="coerce").fillna(0)

    # ──────────────────────────────
    # 🏷️ ランク列を sales に付与
    df_sales = pd.merge(
        df_sales,
        df_master[["jan", "ランク"]],
        on="jan",
        how="left"
    )

    # ランク → 倍率
    RANK_FACTOR = {
        "Aランク": 1.5,
        "Bランク": 1.2,
        "Cランク": 1.0,
        "TEST":   1.5
    }

    # ──────────────────────────────
    # 🤖 発注AIメインループ
    with st.spinner("🤖 発注AIが計算をしています..."):
        results = []
        for _, row in df_sales.iterrows():
            jan     = row["jan"]
            sold    = row["quantity_sold"]
            stock   = row["stock_available"]
            ordered = row["stock_ordered"]

            # ランク取得＆正規化
            raw_rank = str(row.get("ランク", "")).strip()
            if raw_rank and raw_rank[-2:] != "ランク" and raw_rank.upper() in ["A", "B", "C"]:
                raw_rank = f"{raw_rank.upper()}ランク"
            factor = RANK_FACTOR.get(raw_rank, 1.0)

            # 1 か月分 × 倍率
            raw_need = sold - stock - ordered
            need_qty = max(math.ceil(raw_need * factor), 0)
            if need_qty == 0:
                continue

            options = df_purchase[df_purchase["jan"] == jan].copy()
            options = options[options["order_lot"] > 0]
            if options.empty:
                continue

            # ─ ロット選択ロジック（従来どおり） ─
            options["diff"] = (options["order_lot"] - need_qty).abs()
            smaller = options[options["order_lot"] <= need_qty]
            if not smaller.empty:
                best = smaller.loc[smaller["diff"].idxmin()]
            else:
                near = options[(options["order_lot"] > need_qty) &
                               (options["order_lot"] <= need_qty * 1.5) &
                               (options["order_lot"] != 1)]
                if not near.empty:
                    best = near.loc[near["diff"].idxmin()]
                else:
                    one  = options[options["order_lot"] == 1]
                    best = one.iloc[0] if not one.empty else options.sort_values("order_lot").iloc[0]

            sets       = math.ceil(need_qty / best["order_lot"])
            qty        = sets * best["order_lot"]
            total_cost = qty * best["price"]

            results.append({
                "jan": jan,
                "ランク": raw_rank,
                "販売実績": sold,
                "在庫": stock,
                "発注済": ordered,
                "理論必要数": need_qty,
                "発注数": qty,
                "ロット": best["order_lot"],
                "数量": round(qty / best["order_lot"], 2),
                "単価": best["price"],
                "総額": total_cost,
                "仕入先": best.get("supplier", "不明")
            })

    # ──────────────────────────────
    # 📊 結果出力
    if results:
        result_df = pd.DataFrame(results)

        # 商品名・取扱区分を付与
        result_df = pd.merge(
            result_df,
            df_master[["jan", "商品名", "取扱区分", "ランク"]],
            on="jan",
            how="left"
        )

        # フィルタ
        result_df = result_df[result_df["商品名"].notna()]
        result_df = result_df[result_df["取扱区分"] != "取扱中止"]

        # 列順
        column_order = [
            "jan", "商品名", "ランク",
            "販売実績", "在庫", "発注済",
            "理論必要数", "発注数", "ロット", "数量",
            "単価", "総額", "仕入先"
        ]
        result_df = result_df[[col for col in column_order if col in result_df.columns]]

        # 画面表示
        st.success(f"✅ 発注対象: {len(result_df)} 件")
        st.dataframe(result_df)

        # 全体 CSV
        csv = result_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 発注CSVダウンロード", data=csv,
                           file_name="orders_available_based.csv", mime="text/csv")

        # 仕入先別 CSV
        st.markdown("---")
        st.subheader("📦 仕入先別ダウンロード")
        for supplier, group in result_df.groupby("仕入先"):
            sup_csv = group.to_csv(index=False).encode("utf-8-sig")
            st.download_button(label=f"📥 {supplier} 用 発注CSVダウンロード",
                               data=sup_csv,
                               file_name=f"orders_{supplier}.csv",
                               mime="text/csv")
    else:
        st.info("現在、発注が必要な商品はありません。")



# 🔍 商品情報検索モード -----------------------------
elif mode == "search_item":
    st.subheader("🔍 商品情報検索モード")

    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    # ✅ ここを fetch_table と同じバッチ版に変更
    def fetch_item_master():
        headers = {**HEADERS, "Prefer": "count=exact"}
        dfs = []
        offset, limit = 0, 1000  # Supabase 既定と合わせる
        while True:
            url = f"{SUPABASE_URL}/rest/v1/item_master?select=*&offset={offset}&limit={limit}"
            res = requests.get(url, headers=headers)
            if res.status_code == 416 or not res.json():
                break
            if res.status_code not in [200, 206]:
                st.error(f"item_master の取得に失敗: {res.status_code} / {res.text}")
                return pd.DataFrame()
            dfs.append(pd.DataFrame(res.json()))
            offset += limit
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    df_master = fetch_item_master()

    if df_master.empty:
        st.warning("商品情報データベースにデータが存在しません。")
        st.stop()

    df_master["jan"] = df_master["jan"].astype(str)
    df_master["商品コード"] = df_master["商品コード"].astype(str)
    df_master["商品名"] = df_master["商品名"].astype(str)

    # --- 検索 UI -------------------------------------------------
    st.subheader(TEXT[language]["search_keyword"])
    keyword_name = st.text_input(TEXT[language]["search_keyword"], "")
    keyword_code = st.text_input(TEXT[language]["search_code"], "")
    
    maker_filter = st.selectbox(
        TEXT[language]["search_brand"],
        [TEXT[language]["all"]] + sorted(df_master["メーカー名"].dropna().unique())
    )
    
    rank_filter = st.selectbox(
        TEXT[language]["search_rank"],
        [TEXT[language]["all"]] + sorted(df_master["ランク"].dropna().unique())
    )
    
    type_filter = st.selectbox(
        TEXT[language]["search_type"],
        [TEXT[language]["all"]] + sorted(df_master["取扱区分"].dropna().unique())
    )
    
    # --- フィルタリング ------------------------------------------
    df_view = df_master.copy()
    
    # 商品名キーワード
    if keyword_name:
        df_view = df_view[
            df_view["商品名"].str.contains(keyword_name, case=False, na=False)
        ]
    
    # 商品コード / JAN キーワード
    if keyword_code:
        df_view = df_view[
            df_view["商品コード"].str.contains(keyword_code, case=False, na=False) |
            df_view["jan"].str.contains(keyword_code, case=False, na=False)
        ]
    
    # メーカー名
    if maker_filter != TEXT[language]["all"]:
        df_view = df_view[df_view["メーカー名"] == maker_filter]
    
    # ランク
    if rank_filter != TEXT[language]["all"]:
        df_view = df_view[df_view["ランク"] == rank_filter]
    
    # 取扱区分
    if type_filter != TEXT[language]["all"]:
        df_view = df_view[df_view["取扱区分"] == type_filter]
    
    # --- 一覧表示 -------------------------------------------------
    view_cols = [
        "商品コード", "jan", "ランク", "メーカー名", "商品名", "取扱区分",
        "在庫", "利用可能", "発注済", "仕入価格", "ケース入数", "発注ロット", "重量"
    ]
    available_cols = [col for col in view_cols if col in df_view.columns]

    display_df = df_view[available_cols].sort_values(by="商品コード")
    display_df = display_df.rename(columns=COLUMN_NAMES[language])

    st.subheader(TEXT[language]["product_list"])
    st.dataframe(display_df)

    csv = display_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 CSVダウンロード", data=csv, file_name="item_master_filtered.csv", mime="text/csv")

elif mode == "price_improve":
    st.subheader("💰 " + TEXT[language]["price_improve"])

    # 認証用ヘッダー定義
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    def fetch_table(table_name):
        headers = {**HEADERS, "Prefer": "count=exact"}
        dfs = []
        offset = 0
        limit = 1000
        while True:
            url = f"{SUPABASE_URL}/rest/v1/{table_name}?select=*&offset={offset}&limit={limit}"
            res = requests.get(url, headers=headers)
            if res.status_code == 416 or not res.json():
                break
            if res.status_code not in [200, 206]:
                st.error(f"{table_name} の取得に失敗: {res.status_code} / {res.text}")
                return pd.DataFrame()
            dfs.append(pd.DataFrame(res.json()))
            offset += limit
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    with st.spinner("📊 データを読み込み中..."):
        df_sales = fetch_table("sales")
        df_purchase = fetch_table("purchase_data")
        df_item = fetch_table("item_master")

    def normalize_jan(x):
        try:
            if re.fullmatch(r"\d+(\.0+)?", str(x)):
                return str(int(float(x)))
            else:
                return str(x).strip()
        except:
            return ""

    # 整形
    df_sales["jan"] = df_sales["jan"].apply(normalize_jan)
    df_purchase["jan"] = df_purchase["jan"].apply(normalize_jan)
    df_item["jan"] = df_item["jan"].apply(normalize_jan)
    df_purchase["price"] = pd.to_numeric(df_purchase["price"], errors="coerce").fillna(0)

    # 現在価格判定
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
                    "メーカー名": item.iloc[0].get("brand", ""),
                    "現在の仕入価格": current_price,
                    "最安値の仕入価格": min_prices[jan],
                    "差分": round(min_prices[jan] - current_price, 2)
                }
                rows.append(row)

    if rows:
        df_result = pd.DataFrame(rows)

        # ✅ 多言語カラム名に変換
        column_translation = {
            "日本語": {
                "商品コード": "商品コード",
                "JAN": "JAN",
                "メーカー名": "メーカー名",
                "現在の仕入価格": "現在の仕入価格",
                "最安値の仕入価格": "最安値の仕入価格",
                "差分": "差分"
            },
            "中文": {
                "商品コード": "商品编号",
                "JAN": "条码",
                "メーカー名": "制造商名称",
                "現在の仕入価格": "当前进货价",
                "最安値の仕入価格": "最低进货价",
                "差分": "差额"
            }
        }

        df_result = df_result.rename(columns=column_translation[language])

        st.success(f"✅ 改善対象商品数: {len(df_result)} 件")
        st.dataframe(df_result)

        csv = df_result.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 改善リストCSVダウンロード",
            data=csv,
            file_name="price_improvement_list.csv",
            mime="text/csv",
            key="price_improve_download"  # 🔑 複数呼び出し防止
        )
    else:
        st.info("改善の余地がある商品は見つかりませんでした。")


elif mode == "csv_upload":
    st.subheader("📤 CSVアップロードモード")

    # 🔐 パスワード認証（まず入力欄を表示）
    input_password = st.text_input("🔑 パスワードを入力してください", type="password")
    correct_password = st.secrets.get("UPLOAD_PASSWORD", "pass1234")

    if input_password != correct_password:
        st.warning("正しいパスワードを入力してください。")
        st.stop()

    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    def normalize_jan(x):
        try:
            if re.fullmatch(r"\d+(\.0+)?", str(x)):
                return str(int(float(x)))
            else:
                return str(x).strip()
        except:
            return ""

    def preprocess_csv(df, table):
        df.columns = df.columns.str.strip()
        if table == "sales":
            df.rename(columns={
                "アイテム": "jan", "取扱区分": "handling_type", "販売数量": "quantity_sold",
                "現在の手持数量": "stock_total", "現在の利用可能数量": "stock_available", "現在の注文済数量": "stock_ordered"
            }, inplace=True)
            for col in ["quantity_sold", "stock_total", "stock_available", "stock_ordered"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
            df["jan"] = df["jan"].apply(normalize_jan)

        elif table == "purchase_data":
            for col in ["order_lot", "price"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(",", "")
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                    if col == "order_lot":
                        df[col] = df[col].round().astype(int)
            df["jan"] = df["jan"].apply(normalize_jan)

        elif table == "item_master":
            df.rename(columns={
                "UPCコード": "jan", "表示名": "商品名", "メーカー名": "メーカー名",
                "アイテム定義原価": "仕入価格", "カートン入数": "ケース入数",
                "発注ロット": "発注ロット", "パッケージ重量(g)": "重量",
                "手持": "在庫", "利用可能": "利用可能", "注文済": "発注済",
                "名前": "商品コード", "商品ランク": "ランク"
            }, inplace=True)
            df.drop(columns=["内部ID"], inplace=True, errors="ignore")
            df["jan"] = df["jan"].apply(normalize_jan)
            for col in ["ケース入数", "発注ロット", "在庫", "利用可能", "発注済"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).round().astype(int)
        return df

    def upload_file(file, table_name):
        if not file:
            return
        with st.spinner(f"📤 {file.name} アップロード中..."):
            temp_path = f"/tmp/{file.name}"
            with open(temp_path, "wb") as f:
                f.write(file.read())
            try:
                df = pd.read_csv(temp_path)
                df = preprocess_csv(df, table_name)
                requests.delete(f"{SUPABASE_URL}/rest/v1/{table_name}?id=gt.0", headers=HEADERS)
                if table_name == "purchase_data":
                    df = df.drop_duplicates(subset=["jan", "supplier", "order_lot"], keep="last")
                elif table_name == "item_master":
                    df = df.drop_duplicates(subset=["商品コード"], keep="last")
                    if "id" not in df.columns:
                        df.insert(0, "id", range(1, len(df) + 1))
                else:
                    df = df.drop_duplicates(subset=["jan"], keep="last")

                df = df.replace({pd.NA: None, pd.NaT: None, float("nan"): None}).where(pd.notnull(df), None)
                for i in range(0, len(df), 500):
                    batch = df.iloc[i:i+500].to_dict(orient="records")
                    res = requests.post(
                        f"{SUPABASE_URL}/rest/v1/{table_name}",
                        headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
                        json=batch
                    )
                    if res.status_code not in [200, 201]:
                        st.error(f"❌ {table_name} バッチPOST失敗: {res.status_code} {res.text}")
                        return
                st.success(f"✅ {table_name} に {len(df)} 件アップロード完了")
            except Exception as e:
                st.error(f"❌ {table_name} アップロード中にエラー: {e}")

    sales_file = st.file_uploader("🧾 sales.csv アップロード", type="csv")
    if sales_file:
        upload_file(sales_file, "sales")

    purchase_file = st.file_uploader("📦 purchase_data.csv アップロード", type="csv")
    if purchase_file:
        upload_file(purchase_file, "purchase_data")

    item_file = st.file_uploader("📋 item_master.csv アップロード", type="csv")
    if item_file:
        upload_file(item_file, "item_master")


