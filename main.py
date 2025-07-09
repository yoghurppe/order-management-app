import streamlit as st
import pandas as pd
import requests
import os
import math
import re
import hashlib
import time
from zoneinfo import ZoneInfo
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
        "loading_data": "📊 データを読み込み中...",
        "multi_jan": "複数JAN入力（改行またはカンマ区切り）"
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
        "loading_data": "📊 正在读取数据...",
        "multi_jan": "批量输入条码（换行或逗号分隔）"
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
        "重量": "重量(g)",
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

# 🔐 Supabase接続設定
SUPABASE_URL_PRE = st.secrets["SUPABASE_URL"]
SUPABASE_KEY_PRE = st.secrets["SUPABASE_KEY"]
HEADERS_PRE = {
    "apikey": SUPABASE_KEY_PRE,
    "Authorization": f"Bearer {SUPABASE_KEY_PRE}",
    "Content-Type": "application/json"
}

# 📅 item_master の最新更新日時を JST 表示で取得
def fetch_latest_item_update():
    url = f"{SUPABASE_URL_PRE}/rest/v1/item_master?select=updated_at&order=updated_at.desc&limit=1"
    res = requests.get(url, headers=HEADERS_PRE)
    if res.status_code == 200 and res.json():
        dt = pd.to_datetime(res.json()[0]["updated_at"], errors="coerce", utc=True)
        if pd.notnull(dt):
            dt_jst = dt.tz_convert(ZoneInfo("Asia/Tokyo"))
            return f"（{dt_jst.strftime('%-m.%d update')}）"
    return ""

def fetch_table(table_name):
    headers = {**HEADERS_PRE, "Prefer": "count=exact"}
    dfs = []
    offset = 0
    limit = 1000
    while True:
        url = f"{SUPABASE_URL_PRE}/rest/v1/{table_name}?select=*&offset={offset}&limit={limit}"
        res = requests.get(url, headers=headers)
        if res.status_code == 416 or not res.json():
            break
        if res.status_code not in [200, 206]:
            st.error(f"{table_name} の取得に失敗: {res.status_code} / {res.text}")
            return pd.DataFrame()
        dfs.append(pd.DataFrame(res.json()))
        offset += limit
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

item_master_update_text = fetch_latest_item_update()

# タイトル表示
st.title(TEXT[language]["title_order_ai"])

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
    "monthly_sales": {
        "日本語": "販売実績（直近1ヶ月）",
        "中文": "销售业绩（最近一个月）"
    },
    "order_ai": {
        "日本語": "発注AI判定",
        "中文": "订货AI判断"
    },
    "rank_a_check": {
        "日本語": "🅰️ Aランク商品確認",
        "中文": "🅰️ A等级商品检查"
    },
    "purchase_history": {
        "日本語": "📜 発注履歴",
        "中文": "📜 订货记录"
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

    # 🔵 モード切替
    ai_mode = st.radio("発注AIモードを選択", ["通常モード", "JDモード"], index=0)

    # ✅ 計算開始ボタン
    if st.button("🤖 計算を開始する"):
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

        def normalize_jan(x):
            try:
                return str(x).strip()
            except:
                return ""

        with st.spinner("📦 データを読み込み中..."):
            df_sales = fetch_table("sales")
            df_purchase = fetch_table("purchase_data")
            df_master = fetch_table("item_master")
            if ai_mode == "JDモード":
                df_warehouse = fetch_table("warehouse_stock")

        if df_sales.empty or df_purchase.empty or df_master.empty:
            st.warning("必要なデータが不足しています。")
            st.stop()
        if ai_mode == "JDモード" and df_warehouse.empty:
            st.warning("JDモード用の warehouse_stock データが不足しています。")
            st.stop()

        df_sales["jan"] = df_sales["jan"].apply(normalize_jan)
        df_purchase["jan"] = df_purchase["jan"].apply(normalize_jan)
        df_master["jan"] = df_master["jan"].apply(normalize_jan)
        if ai_mode == "JDモード":
            df_warehouse["product_code"] = df_warehouse["product_code"].apply(normalize_jan)
            df_warehouse["stock_available"] = pd.to_numeric(df_warehouse["stock_available"], errors="coerce").fillna(0).astype(int)

        df_sales["quantity_sold"] = pd.to_numeric(df_sales["quantity_sold"], errors="coerce").fillna(0).astype(int)
        df_sales["stock_available"] = pd.to_numeric(df_sales["stock_available"], errors="coerce").fillna(0).astype(int)
        df_sales["stock_ordered"] = pd.to_numeric(df_sales["stock_ordered"], errors="coerce").fillna(0).astype(int)
        df_purchase["order_lot"] = pd.to_numeric(df_purchase["order_lot"], errors="coerce").fillna(0).astype(int)
        df_purchase["price"] = pd.to_numeric(df_purchase["price"], errors="coerce").fillna(0)

        rank_multiplier = {
            "Aランク": 1.5,
            "Bランク": 1.2,
            "Cランク": 1.0,
            "TEST": 1.5
        }

        with st.spinner("🤖 発注AIが計算をしています..."):
            from datetime import date, timedelta
            import math

            df_history = fetch_table("purchase_history")
            df_history["order_date"] = pd.to_datetime(df_history["order_date"], errors="coerce").dt.date
            today = date.today()
            yesterday = today - timedelta(days=1)
            recent_jans = df_history[df_history["order_date"].isin([today, yesterday])]["jan"].dropna().astype(str).apply(normalize_jan).unique().tolist()

            results = []
            for _, row in df_sales.iterrows():
                jan = row["jan"]
                sold = row["quantity_sold"]

                # 🔄 在庫引用元切替
                if ai_mode == "JDモード":
                    stock_row = df_warehouse[df_warehouse["product_code"] == jan]
                    stock = stock_row["stock_available"].values[0] if not stock_row.empty else 0
                else:
                    stock = row.get("stock_available", 0)

                ordered = row.get("stock_ordered", 0)

                rank_row = df_master[df_master["jan"] == jan]
                rank = rank_row["ランク"].values[0] if not rank_row.empty and "ランク" in rank_row else ""
                multiplier = rank_multiplier.get(rank, 1.0)

                need_qty_raw = math.ceil(sold * multiplier) - stock - ordered

                if stock <= 1 and sold >= 1 and need_qty_raw <= 0:
                    need_qty = 1
                else:
                    need_qty = max(need_qty_raw, 0)

                if jan in recent_jans:
                    continue

                if rank in ["Aランク", "Bランク"]:
                    reorder_point = max(math.floor(sold * 0.9), 1)
                else:
                    reorder_point = max(math.floor(sold * 0.7), 1)
                
                current_total = stock + ordered
                if current_total > reorder_point:
                    continue

                if need_qty <= 0:
                    continue

                options = df_purchase[df_purchase["jan"] == jan].copy()
                if options.empty:
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

                sets = math.ceil(need_qty / best_option["order_lot"])
                qty = sets * best_option["order_lot"]
                total_cost = qty * best_option["price"]

                results.append({
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
                    "仕入先": best_option.get("supplier", "不明"),
                    "ランク": rank
                })

            if results:
                result_df = pd.DataFrame(results)

                df_master["商品コード"] = df_master["商品コード"].astype(str).str.strip()
                result_df["jan"] = result_df["jan"].astype(str).str.strip()

                df_temp = df_master[["商品コード", "商品名", "取扱区分"]].copy()
                df_temp.rename(columns={"商品コード": "jan"}, inplace=True)

                result_df = pd.merge(result_df, df_temp, on="jan", how="left")

                if "商品名" in result_df.columns:
                    result_df = result_df[result_df["商品名"].notna()]
                if "取扱区分" in result_df.columns:
                    result_df = result_df[result_df["取扱区分"] != "取扱中止"]
                else:
                    st.warning("⚠️『取扱区分』列が存在しません。")

                column_order = ["jan", "商品名", "ランク", "販売実績", "在庫", "発注済", "理論必要数", "発注数", "ロット", "数量", "単価", "総額", "仕入先"]
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

    # ✅ バッチ取得（既存）
    def fetch_item_master():
        headers = {**HEADERS, "Prefer": "count=exact"}
        dfs = []
        offset, limit = 0, 1000
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

    df_master["jan"]       = df_master["jan"].astype(str)
    df_master["商品コード"] = df_master["商品コード"].astype(str)
    df_master["商品名"]     = df_master["商品名"].astype(str)

    # ---------- 🔍 検索 UI ----------
    col1, col2 = st.columns(2)

    with col1:
        keyword_name = st.text_input(TEXT[language]["search_keyword"], "")
        keyword_code = st.text_input(TEXT[language]["search_code"], "")

    with col2:
        jan_filter_multi = st.text_area(
            TEXT[language]["multi_jan"],                # ←動的ラベル
            placeholder="例:\n4901234567890\n4987654321098",
            height=120,
        )

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

    # ---------- 🧹 フィルタリング ----------
    import re

    # ① 複数 JAN リストを整形
    jan_list = [j.strip() for j in re.split(r"[,\n\r]+", jan_filter_multi) if j.strip()]

    df_view = df_master.copy()

    # 複数 JAN が最優先
    if jan_list:
        df_view = df_view[df_view["jan"].isin(jan_list)]

    # 単一キーワード（商品コード／JAN 部分一致）
    elif keyword_code:
        df_view = df_view[
            df_view["商品コード"].str.contains(keyword_code, case=False, na=False) |
            df_view["jan"].str.contains(keyword_code, case=False, na=False)
        ]

    # 商品名キーワード
    if keyword_name:
        df_view = df_view[
            df_view["商品名"].str.contains(keyword_name, case=False, na=False)
        ]

    # メーカー
    if maker_filter != TEXT[language]["all"]:
        df_view = df_view[df_view["メーカー名"] == maker_filter]

    # ランク
    if rank_filter != TEXT[language]["all"]:
        df_view = df_view[df_view["ランク"] == rank_filter]

    # 取扱区分
    if type_filter != TEXT[language]["all"]:
        df_view = df_view[df_view["取扱区分"] == type_filter]

    # ---------- 📋 一覧表示 ----------
    view_cols = [
        "商品コード", "jan", "ランク", "メーカー名", "商品名", "取扱区分",
        "在庫", "利用可能", "発注済", "仕入価格", "ケース入数", "発注ロット", "重量"
    ]
    available_cols = [c for c in view_cols if c in df_view.columns]

    display_df = (
        df_view[available_cols]
        .sort_values(by="商品コード")
        .rename(columns=COLUMN_NAMES[language])
    )

    #️⃣ 追加: 件数カウント
    row_count = len(display_df)

    #️⃣ 追加: ヘッダー行を左右 2 カラムで表示
    h_left, h_right = st.columns([1, 0.15])        # 右側を少し細く
    h_left.subheader(TEXT[language]["product_list"])
    # HTMLで右寄せ & 同行内表示
    h_right.markdown(
        f"<h4 style='text-align:right; margin-top: 0.6em;'>{row_count:,}件</h4>",
        unsafe_allow_html=True
    )

    # ✏️ 変更: ↓ 旧 subheader 行は不要なのでコメントアウト or 削除
    # st.subheader(TEXT[language]["product_list"])

    st.dataframe(display_df, use_container_width=True)

    csv = display_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 CSVダウンロード",
        data=csv,
        file_name="item_master_filtered.csv",
        mime="text/csv",
    )



elif mode == "purchase_history":
    st.subheader("📜 発注履歴")

    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    # ---------- 🔍 検索フォーム ----------
    col1, col2 = st.columns(2)

    with col1:
        # 従来の単一キーワード（部分一致）
        jan_filter_single = st.text_input("🔍 JANで検索（部分一致）", "")
        order_id_filter   = st.text_input("🔍 Order IDで検索（部分一致）", "")

    with col2:
        jan_filter_multi = st.text_area(
            TEXT[language]["multi_jan"],                # ←動的ラベル
            placeholder="例:\n4901234567890\n4987654321098",
            height=120,
        )

    @st.cache_data(ttl=60)
    def fetch_purchase_history():
        url = f"{SUPABASE_URL}/rest/v1/purchase_history?select=*"
        res = requests.get(url, headers=HEADERS)
        if res.status_code == 200:
            return pd.DataFrame(res.json())
        st.error("❌ 発注履歴データの取得に失敗しました")
        return pd.DataFrame()

    df = fetch_purchase_history()

    if df.empty:
        st.info("発注履歴データが存在しません。")
        st.stop()

    # ------------- 🧹 フィルタリング -------------
    import re

    df["jan"]        = df["jan"].astype(str)
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce").dt.date

    # ① 複数 JAN リストを整形
    jan_list = [j.strip() for j in re.split(r"[,\n\r]+", jan_filter_multi) if j.strip()]

    if jan_list:  # 最優先
        df = df[df["jan"].isin(jan_list)]
    elif jan_filter_single:
        df = df[df["jan"].str.contains(jan_filter_single, na=False)]

    if order_id_filter:
        df = df[df["order_id"].astype(str).str.contains(order_id_filter, na=False)]

    # ------------- 📋 表示 -------------
    df_show = df[["jan", "quantity", "order_date", "order_id"]].sort_values("jan")

    st.success(f"✅ 発注履歴 件数: {len(df_show)} 件")
    st.dataframe(df_show, use_container_width=True)




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


if mode == "csv_upload":
    st.subheader("📄 CSVアップロードモード")

    def normalize_jan(x):
        try:
            return str(x).strip()
        except:
            return ""

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

    def preprocess_csv(df, table):
        df.columns = df.columns.str.replace("　", "").str.replace("\ufeff", "").str.strip()

        if table == "sales":
            st.write("📝 sales 列名:", df.columns.tolist())
            item_col = None
            for col in df.columns:
                if "アイテム" in col:
                    item_col = col
                    break
            if item_col:
                df.rename(columns={item_col: "jan"}, inplace=True)
            else:
                raise ValueError(f"❌ 'アイテム' 列が見つかりません！列名: {df.columns.tolist()}")

            df.rename(columns={
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

        elif table == "purchase_data":
            for col in ["order_lot", "price"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(",", "")
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                    if col == "order_lot":
                        df[col] = df[col].round().astype(int)
            df["jan"] = df["jan"].apply(normalize_jan)

        elif table == "item_master":
            st.write("📝 item_master 列名:", df.columns.tolist())
            upc_col = None
            for col in df.columns:
                if "UPC" in col:
                    upc_col = col
                    break

            if upc_col:
                df.rename(columns={upc_col: "jan"}, inplace=True)
            else:
                raise ValueError(f"❌ 'UPCコード' 列が見つかりません！列名: {df.columns.tolist()}")

            df.rename(columns={
                "表示名": "商品名", "メーカー名": "メーカー名",
                "アイテム定義原価": "仕入価格", "カートン入数": "ケース入数",
                "発注ロット": "発注ロット", "パッケージ重量(g)": "重量",
                "手持": "在庫", "利用可能": "利用可能",
                "注文済": "発注済", "名前": "商品コード",
                "商品ランク": "ランク"
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
                df = pd.read_csv(
                    temp_path,
                    sep=",",
                    engine="python",
                    on_bad_lines="skip",
                    encoding="utf-8-sig"
                )
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

    sales_file = st.file_uploader("📎 sales.csv アップロード", type="csv")
    if sales_file:
        upload_file(sales_file, "sales")

    purchase_file = st.file_uploader("📦 purchase_data.csv アップロード", type="csv")
    if purchase_file:
        upload_file(purchase_file, "purchase_data")

    item_file = st.file_uploader("📋 item_master.csv アップロード", type="csv")
    if item_file:
        upload_file(item_file, "item_master")

    order_file = st.file_uploader("📓 purchase_history.csv アップロード", type="csv")
    if order_file:
        def preprocess_purchase_history(df):
            df = df[~df["jan_or_label"].astype(str).str.contains("合計", na=False)]
            df["jan"] = df["jan_or_label"].where(df["jan_or_label"].astype(str).str.match(r"^\d{13}$"))
            df["jan"] = df["jan"].fillna(method="ffill")
            df = df[df["date"].notna() & df["order_id"].notna()]
            df = df[["jan", "date", "order_id", "quantity"]].copy()
            df["jan"] = df["jan"].apply(normalize_jan)
            df["quantity"] = pd.to_numeric(df["quantity"].astype(str).str.replace(",", ""), errors="coerce").fillna(0).astype(int)
            df.rename(columns={"date": "order_date"}, inplace=True)
            return df

        def upload_purchase_history(df):
            try:
                requests.delete(f"{SUPABASE_URL}/rest/v1/purchase_history?id=gt.0", headers=HEADERS)
                df = df.drop_duplicates(subset=["jan", "order_date", "order_id"], keep="last")
                df = df.replace({pd.NA: None, pd.NaT: None, float("nan"): None}).where(pd.notnull(df), None)
                for i in range(0, len(df), 500):
                    batch = df.iloc[i:i+500].to_dict(orient="records")
                    res = requests.post(
                        f"{SUPABASE_URL}/rest/v1/purchase_history",
                        headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
                        json=batch
                    )
                    if res.status_code not in [200, 201]:
                        st.error(f"❌ purchase_history バッチPOST失敗: {res.status_code} {res.text}")
                        return
                st.success(f"✅ purchase_history に {len(df)} 件アップロード完了")
            except Exception as e:
                st.error(f"❌ purchase_history アップロード中にエラー: {e}")

        with st.spinner("📤 purchase_history.csv を処理中..."):
            try:
                df = pd.read_csv(
                    order_file,
                    skiprows=6,
                    encoding="utf-8-sig",
                    sep=",",
                    engine="python",
                    on_bad_lines="skip"
                )
                df.columns = ["jan_or_label", "date", "order_id", "quantity"]
                df = preprocess_purchase_history(df)
                upload_purchase_history(df)
            except Exception as e:
                st.error(f"❌ 処理エラー: {e}")

    warehouse_file = st.file_uploader("🏢 倉庫在庫.xlsx アップロード", type=["xlsx"])
    if warehouse_file:
        def preprocess_warehouse_stock(file):
            df = pd.read_excel(file, sheet_name="倉庫在庫")
            df_upload = df.iloc[:, [13, 22]].copy()  # N列=14番目, W列=23番目
            df_upload.columns = ["stock_available", "product_code"]
            df_upload["product_code"] = df_upload["product_code"].astype(str).str.strip()
            df_upload["jan"] = df_upload["product_code"]  # ← JAN に product_code をコピー！
            df_upload["stock_available"] = pd.to_numeric(df_upload["stock_available"], errors="coerce").fillna(0).round().astype(int)
            return df_upload

        def upload_warehouse_stock(df):
            try:
                requests.delete(f"{SUPABASE_URL}/rest/v1/warehouse_stock?product_code=neq.null", headers=HEADERS)
                df = df.drop_duplicates(subset=["product_code"], keep="last")
                df = df.replace({pd.NA: None, pd.NaT: None, float("nan"): None}).where(pd.notnull(df), None)
                for i in range(0, len(df), 500):
                    batch = df.iloc[i:i+500].to_dict(orient="records")
                    res = requests.post(
                        f"{SUPABASE_URL}/rest/v1/warehouse_stock",
                        headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
                        json=batch
                    )
                    if res.status_code not in [200, 201]:
                        st.error(f"❌ warehouse_stock バッチPOST失敗: {res.status_code} {res.text}")
                        return
                st.success(f"✅ warehouse_stock に {len(df)} 件アップロード完了")
            except Exception as e:
                st.error(f"❌ warehouse_stock アップロード中にエラー: {e}")

        with st.spinner("📤 倉庫在庫.xlsx を処理中..."):
            try:
                df_warehouse = preprocess_warehouse_stock(warehouse_file)
                upload_warehouse_stock(df_warehouse)
            except Exception as e:
                st.error(f"❌ 処理エラー: {e}")


# 🆕 販売実績（直近1ヶ月）モード -----------------------------
elif mode == "monthly_sales":
    st.subheader("📊 販売実績（直近1ヶ月）")

    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    # ✅ データ取得関数
    def fetch_data(table_name):
        headers = {**HEADERS, "Prefer": "count=exact"}
        dfs = []
        offset, limit = 0, 1000
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

    # データ取得
    df_master = fetch_data("item_master")
    df_sales = fetch_data("sales")
    df_warehouse = fetch_data("warehouse_stock")

    if df_master.empty or df_sales.empty or df_warehouse.empty:
        st.warning("必要なデータが存在しません。")
        st.stop()

    # item_master 整形
    df_master["jan"] = df_master["jan"].astype(str)
    df_master["商品コード"] = df_master["商品コード"].astype(str)
    df_master = df_master.rename(columns={"jan": "JAN"})

    # sales 整形
    df_sales["商品コード"] = df_sales["jan"].astype(str)
    df_sales.rename(columns={"quantity_sold": "販売数"}, inplace=True)

    # warehouse_stock 整形
    df_warehouse["product_code"] = df_warehouse["product_code"].astype(str)
    df_warehouse = df_warehouse.rename(columns={
        "product_code": "商品コード",
        "stock_available": "利用可能在庫"
    })

    # --- マージ ---
    df_joined = pd.merge(df_sales, df_master, on="商品コード", how="left")
    df_joined = pd.merge(df_joined, df_warehouse[["商品コード", "利用可能在庫"]], on="商品コード", how="left")

    # --- JAN ---
    if "JAN" in df_joined.columns:
        df_joined["jan"] = df_joined["JAN"]
    else:
        st.warning("⚠️ item_master 側からJANが取得できませんでした。")

    # --- 数値列 ---
    df_joined["販売数"] = pd.to_numeric(df_joined["販売数"], errors="coerce").fillna(0).astype(int)
    df_joined["発注済"] = pd.to_numeric(df_joined.get("stock_ordered", 0), errors="coerce").fillna(0).astype(int)
    df_joined["利用可能"] = df_joined["利用可能在庫"].fillna(0).astype(int)
    df_joined.drop(columns=["利用可能在庫"], inplace=True)

    # 販売数 > 0 のみ
    df_joined = df_joined[df_joined["販売数"] > 0]

    # ---------- 🔍 検索 UI ----------
    col1, col2 = st.columns(2)

    with col1:
        keyword_name = st.text_input(TEXT[language]["search_keyword"], "")
        keyword_code = st.text_input(TEXT[language]["search_code"], "")

    with col2:
        jan_filter_multi = st.text_area(
            TEXT[language]["multi_jan"],
            placeholder="例:\n4901234567890\n4987654321098",
            height=120,
        )

    maker_filter = st.selectbox(
        TEXT[language]["search_brand"],
        [TEXT[language]["all"]] + sorted(df_joined["メーカー名"].dropna().unique())
    )
    rank_filter = st.selectbox(
        TEXT[language]["search_rank"],
        [TEXT[language]["all"]] + sorted(df_joined["ランク"].dropna().unique())
    )
    type_filter = st.selectbox(
        TEXT[language]["search_type"],
        [TEXT[language]["all"]] + sorted(df_joined["取扱区分"].dropna().unique())
    )

    import re
    jan_list = [j.strip() for j in re.split(r"[,\n\r]+", jan_filter_multi) if j.strip()]

    df_view = df_joined.copy()

    if jan_list:
        df_view = df_view[df_view["jan"].isin(jan_list)]
    elif keyword_code:
        df_view = df_view[
            df_view["商品コード"].str.contains(keyword_code, case=False, na=False) |
            df_view["jan"].str.contains(keyword_code, case=False, na=False)
        ]

    if keyword_name:
        df_view = df_view[df_view["商品名"].str.contains(keyword_name, case=False, na=False)]

    if maker_filter != TEXT[language]["all"]:
        df_view = df_view[df_view["メーカー名"] == maker_filter]

    if rank_filter != TEXT[language]["all"]:
        df_view = df_view[df_view["ランク"] == rank_filter]

    if type_filter != TEXT[language]["all"]:
        df_view = df_view[df_view["取扱区分"] == type_filter]

    # ---------- 📋 表示 ----------
    view_cols = [
        "商品コード", "jan", "ランク", "メーカー名",
        "商品名", "取扱区分", "販売数", "利用可能", "発注済"
    ]
    available_cols = [c for c in view_cols if c in df_view.columns]

    display_df = (
        df_view[available_cols]
        .sort_values(by="商品コード")
        .rename(columns=COLUMN_NAMES[language])
    )

    row_count = len(display_df)
    h_left, h_right = st.columns([1, 0.15])
    h_left.subheader(TEXT[language]["product_list"])
    h_right.markdown(
        f"<h4 style='text-align:right; margin-top: 0.6em;'>{row_count:,}件</h4>",
        unsafe_allow_html=True
    )

    st.dataframe(display_df, use_container_width=True)

    csv = display_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 CSVダウンロード",
        data=csv,
        file_name="monthly_sales_filtered.csv",
        mime="text/csv",
    )


elif mode == "rank_a_check":
    st.subheader("🅰️ Aランク商品確認モード")

    # データ取得
    df_item = fetch_table("item_master")
    df_sales = fetch_table("sales")
    df_stock = fetch_table("warehouse_stock")

    if df_item.empty or df_sales.empty or df_stock.empty:
        st.warning("必要なテーブルが空です")
        st.stop()

    # 1️⃣ Aランクのみ
    df_a = df_item[(df_item["ランク"] == "Aランク") & (df_item["jan"].notnull())].copy()
    df_a["商品コード"] = df_a["jan"].astype(str).str.strip()

    df_sales["商品コード"] = df_sales["jan"].astype(str).str.strip()
    df_stock["商品コード"] = df_stock["product_code"].astype(str).str.strip()
    df_stock = df_stock.rename(columns={"stock_available": "在庫数"})

    # 2️⃣ 実績30日
    df_sales_30 = (
        df_sales.groupby("商品コード", as_index=False)["quantity_sold"]
        .sum()
        .rename(columns={"quantity_sold": "実績（30日）"})
    )

    # 3️⃣ 発注済 → item_master から
    df_item["商品コード"] = df_item["商品コード"].astype(str).str.strip()
    df_item_sub = df_item[["商品コード", "発注済"]].copy()

    # 4️⃣ マージ
    df_merged = (
        df_a
        .merge(df_sales_30, on="商品コード", how="left")
        .merge(df_item_sub, on="商品コード", how="left")
        .merge(df_stock[["商品コード", "在庫数"]], on="商品コード", how="left")
    )

    # --- 🔑 必須列を保証 ---
    if "発注済" not in df_merged.columns:
        df_merged["発注済"] = 0

    if "実績（7日）" not in df_merged.columns:
        df_merged["実績（7日）"] = None

    # 欠損補完
    df_merged["発注済"] = df_merged["発注済"].fillna(0).astype(int)
    df_merged["実績（30日）"] = df_merged["実績（30日）"].fillna(0)
    df_merged["在庫数"] = df_merged["在庫数"].fillna(0)

    # 5️⃣ アラート列
    df_merged["発注アラート1.0"] = df_merged["実績（30日）"] > (df_merged["在庫数"] + df_merged["発注済"])
    df_merged["発注アラート1.2"] = (df_merged["実績（30日）"] * 1.2) > (df_merged["在庫数"] + df_merged["発注済"])

    # --- 万一無い場合の保険 ---
    if "発注アラート1.0" not in df_merged.columns:
        df_merged["発注アラート1.0"] = False

    if "発注アラート1.2" not in df_merged.columns:
        df_merged["発注アラート1.2"] = False

    # 6️⃣ フィルター
    check_1_0 = st.checkbox("✅ 発注アラート1.0のみ表示", value=False)
    check_1_2 = st.checkbox("✅ 発注アラート1.2のみ表示", value=False)

    df_result = df_merged.copy()
    if check_1_0:
        df_result = df_result[df_result["発注アラート1.0"]]
    if check_1_2:
        df_result = df_result[df_result["発注アラート1.2"]]

    # 7️⃣ 出力
    st.dataframe(df_result[[
        "商品コード",
        "商品名",
        "ランク",
        "実績（30日）",
        "実績（7日）",
        "在庫数",
        "発注済",
        "発注アラート1.0",
        "発注アラート1.2"
    ]])
