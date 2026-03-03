import streamlit as st

st.markdown("""
<style>
/* ===== multiselect の選択タグ（黒文字・目に優しい） ===== */

/* タグ本体 */
[data-baseweb="tag"] {
    background-color: #D1D5DB !important;   /* 薄いグレー */
    color: #111827 !important;              /* 黒（少し柔らかめ） */
    border-radius: 6px !important;
    font-weight: 500 !important;
}

/* テキスト部分（念のため明示） */
[data-baseweb="tag"] span {
    color: #111827 !important;
}

/* × ボタン */
[data-baseweb="tag"] svg {
    color: #374151 !important;              /* 濃いグレー */
}

/* hover */
[data-baseweb="tag"]:hover {
    background-color: #9CA3AF !important;   /* 少し濃いグレー */
}
</style>
""", unsafe_allow_html=True)


# ✅ ページ設定を追加
st.set_page_config(
    page_title="【ASEAN】一元管理システム",
    layout="wide",                 # 横幅を最大化
    initial_sidebar_state="expanded"
)

import pandas as pd
import requests
import datetime
import os
import math
import re
import hashlib
import time
from zoneinfo import ZoneInfo
from streamlit_javascript import st_javascript

# ここに parse_items_fixed を追加
def parse_items_fixed(text):
    items = []
    lines = text.strip().splitlines()
    item = {}

    def normalize_number(s):
        table = str.maketrans('０１２３４５６７８９', '0123456789')
        return s.translate(table).strip()

    for line in lines:
        line = line.strip()

        if "品番" in line:
            item = {'品番': line.split("品番")[-1].strip()}

        elif "JAN" in line:
            item['jan'] = line.split("JAN")[-1].strip()

        elif re.search(r'（[\d,]+円 × \d+点）', line):
            m = re.search(r'（([\d,]+)円 × (\d+)点）', line)
            item['単価'] = int(m.group(1).replace(',', ''))
            item['ロット'] = int(m.group(2))

        elif normalize_number(line).isdigit() and '数量' not in item:
            item['数量'] = int(normalize_number(line))

            if all(k in item for k in ['品番', 'jan', '単価', 'ロット', '数量']):
                item['ロット×数量'] = item['ロット'] * item['数量']
                items.append(item)
                item = {}

    df = pd.DataFrame(items)

    if not df.empty:
        df['小計'] = df['単価'] * df['ロット'] * df['数量']
        subtotal = df['小計'].sum()

        df.loc[len(df)] = {
            '品番': '合計',
            'jan': '',
            '単価': '',
            'ロット': '',
            '数量': '',
            'ロット×数量': '',
            '小計': subtotal
        }

    return df
    
# 🟢 ここからアプリの中身（言語選択など）
language = st.sidebar.selectbox("言語 / Language", ["日本語", "中文"], key="language")

# ユーザー表示用ラベルテキスト
TEXT = {
    "日本語": {
        "title_order_ai": "【ASEAN】一元管理システム",
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
        "search_name": "商品名検索",
        "search_brand": "メーカー名で絞り込み",
        "search_type": "取扱区分で絞り込み",
        "search_rank": "ランクで絞り込み",
        "search_code": "商品コード / JAN検索",
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
        "search_name": "按商品名称搜索",
        "search_brand": "按制造商筛选",
        "search_type": "按分类筛选",
        "search_rank": "按等级筛选",
        "search_code": "按商品编号 / 条码搜索",
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
        "実績原価": "実績原価",
        "最安原価": "最安原価"
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
        "重量": "重量(g)",
        "実績原価": "实际成本",
        "最安原価": "最低成本"
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

def apply_common_search_ui(df, language: str):
    """
    商品情報検索 / 販売実績（直近1ヶ月）で共通で使う検索UI＋フィルタ。
    df を絞り込んだ結果を返す。
    """

    # ---------- 🔍 検索UI ----------
    col1, col2 = st.columns(2)

    with col1:
        keyword_code = st.text_input(
            TEXT[language]["search_code"],
            "",
            placeholder="例: 4515061012818"
        )
    with col2:
        keyword_name = st.text_input(
            TEXT[language]["search_name"],
            "",
            placeholder="例: パーフェクトジェル"
        )

    jan_filter_multi = st.text_area(
        TEXT[language]["multi_jan"],
        placeholder="例:\n4901234567890\n4987654321098",
        height=120,
    )

    maker_filter = st.selectbox(
        TEXT[language]["search_brand"],
        [TEXT[language]["all"]] +
        sorted(df.get("メーカー名", pd.Series(dtype=str)).dropna().unique().tolist())
    )
    # ランク候補（空は除外）
    rank_options = (
        df.get("ランク", pd.Series(dtype=str))
          .astype(str).str.strip()
          .replace(["", "nan", "None", "NULL"], pd.NA)
          .dropna()
          .unique()
          .tolist()
    )
    rank_options = sorted(rank_options)
    
    # 複数選択（デフォルトは全選択＝絞り込み無しと同じ）
    rank_filter = st.multiselect(
        TEXT[language]["search_rank"],
        options=rank_options,
        default=rank_options
    )
    type_filter = st.selectbox(
        TEXT[language]["search_type"],
        [TEXT[language]["all"]] +
        sorted(df.get("取扱区分", pd.Series(dtype=str)).dropna().unique().tolist())
    )

    # ---------- 絞り込み ----------
    jan_list = [j.strip() for j in re.split(r"[,\n\r]+", jan_filter_multi) if j.strip()]
    df_view = df.copy()

    # 優先度: 複数JAN > コード/JAN欄 > 商品名欄
    if jan_list:
        if "jan" in df_view.columns:
            df_view = df_view[df_view["jan"].isin(jan_list)]
    elif keyword_code:
        if "商品コード" in df_view.columns and "jan" in df_view.columns:
            df_view = df_view[
                df_view["商品コード"].str.contains(keyword_code, case=False, na=False) |
                df_view["jan"].str.contains(keyword_code, case=False, na=False)
            ]
        elif "jan" in df_view.columns:
            df_view = df_view[df_view["jan"].str.contains(keyword_code, case=False, na=False)]

    if keyword_name and "商品名" in df_view.columns:
        df_view = df_view[df_view["商品名"].str.contains(keyword_name, case=False, na=False)]

    if maker_filter != TEXT[language]["all"] and "メーカー名" in df_view.columns:
        df_view = df_view[df_view["メーカー名"] == maker_filter]

    if "ランク" in df_view.columns and rank_filter:
        # デフォルトが全選択なので、全選択のままなら実質変化なし
        df_view = df_view[df_view["ランク"].isin(rank_filter)]

    if type_filter != TEXT[language]["all"] and "取扱区分" in df_view.columns:
        df_view = df_view[df_view["取扱区分"] == type_filter]

    return df_view


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
    "store_profit": {
        "日本語": "🏪 店舗別 粗利一覧",
        "中文": "🏪 各店铺 毛利一览"
    },
    "daily_sales": {
        "日本語": "📆 店舗別 前日売上",
        "中文": "📆 各店铺 昨日销售"
    },
    "search_item": {
        "日本語": f"🔍 商品情報検索<br>{item_master_update_text}",
        "中文": f"🔍 商品信息查询<br>{item_master_update_text}"
    },
    "monthly_sales": {
        "日本語": "販売実績（直近1ヶ月）",
        "中文": "销售业绩（最近一个月）"
    },
    "expiry_manage": {
        "日本語": "🧊 賞味期限管理",
        "中文": "🧊 保质期管理"
    },
    "order_ai": {
        "日本語": "発注AI判定",
        "中文": "订货AI判断"
    },
    "rank_check": {
        "日本語": "ランク別発注確認",
        "中文": "按等级确认订单"
    },
    "purchase_history": {
        "日本語": "📜 発注履歴",
        "中文": "📜 订货记录"
    },
    "order": {
        "日本語": "📦 発注書作成",
        "中文": "📦 订单书生成模式"
    },
    "csv_upload": {
        "日本語": "CSVアップロード",
        "中文": "上传CSV"
    },
    # "price_improve": {
    #     "日本語": "仕入価格改善リスト",
    #     "中文": "进货价格优化清单"
    # },
    # "difficult_items": {
    #     "日本語": "入荷困難商品",
    #     "中文": "进货困难商品"
    # },
}


# 単一選択モードの初期化
if "mode" not in st.session_state:
    st.session_state["mode"] = "home"  # デフォルトはトップ

# 多言語ラベル取得
def local_label(mode_key: str) -> str:
    d = MODE_KEYS.get(mode_key, {})
    return d.get(language) or d.get("日本語") or mode_key

# 表示グループ定義（順番＝表示順）
GROUPS = [
    ("トップページ",      ["home"]),
    ("【売上データ】",    ["store_profit", "daily_sales"]),
    ("【商品情報】",      ["search_item", "monthly_sales"]),
    ("【賞味期限】", ["expiry_manage"]),
    ("【発注】",          ["order_ai", "rank_check", "purchase_history", "order"]),
    ("【アップロード】",  ["csv_upload"]),
]

# === ここから置き換え ===
from urllib.parse import urlencode

with st.sidebar:
    st.markdown(f"### {TEXT[language]['mode_select']}")

    # スタイル
    st.markdown("""
    <style>
      .nav-group { margin: .5rem 0 .25rem; font-weight: 700; }
      a.nav-btn {
        display: block;
        width: 100%;
        text-align: left;
        padding: .45rem .6rem;
        border: 1px solid rgba(49,51,63,.2);
        border-radius: .55rem;
        margin: .18rem 0;
        background: white;
        text-decoration: none;
        color: inherit;
        transition: all 0.1s ease;
      }
      a.nav-btn:hover { background: rgba(49,51,63,.06); }
      a.nav-btn.active {
        background: rgba(14,165,233,.12);
        border-color: rgba(14,165,233,.45);
        font-weight: 600;
      }
    </style>
    """, unsafe_allow_html=True)

    # グループごとに <a href="?mode=..."> を生成（右クリックで新規タブOK）
    for group_title, keys in GROUPS:
        st.markdown(f"<div class='nav-group'>{group_title}</div>", unsafe_allow_html=True)
        for k in keys:
            label = local_label(k)  # ラベルに <br> を含んでもOK
            active_class = "active" if st.session_state["mode"] == k else ""

            # 既存のクエリを維持しつつ mode だけ上書き
            params = dict(st.query_params)
            params["mode"] = k
            href = "?" + urlencode(params, doseq=True)

            st.markdown(
                f"<a class='nav-btn {active_class}' href='{href}' target='_self'>{label}</a>",
                unsafe_allow_html=True
            )
            
# URL → 状態 反映（新API）
mode_param = st.query_params.get("mode")
if mode_param in MODE_KEYS:
    st.session_state["mode"] = mode_param

# 現在モード
mode = st.session_state["mode"]

# 状態 → URL 同期（直打ちや初期表示時の補完）
if st.query_params.get("mode") != mode:
    st.query_params["mode"] = mode
# === ここまで置き換え ===

# ランク設定
RANK_LABELS = ("Aランク", "Bランク", "Cランク")

def normalize_rank_base(rank) -> str:
    """
    rank: 例 "Aランク", "Aランク★", "Bランク★", "TEST", None
    return: "A" / "B" / "C" / ""（それ以外）
    """
    if rank is None:
        return ""
    s = str(rank).strip()
    if s.startswith("Aランク"):
        return "A"
    if s.startswith("Bランク"):
        return "B"
    if s.startswith("Cランク"):
        return "C"
    return ""

def add_base_rank_column(df: pd.DataFrame, col="rank") -> pd.DataFrame:
    """
    df[col] から base_rank を作って返す（コピーして返す）
    """
    if df is None or df.empty or col not in df.columns:
        return df
    out = df.copy()
    # 正規表現で "A/B/Cランク" の A/B/C だけ抜く（★付きもOK）
    out["base_rank"] = (
        out[col]
        .astype(str)
        .str.strip()
        .str.extract(r"^(A|B|C)ランク", expand=False)
        .fillna("")
    )
    return out



# 各モードの処理分岐
if mode == "home":
    st.subheader("🏠 " + TEXT[language]["title_order_ai"])

    if language == "日本語":
        st.markdown("""
        #### ご利用ありがとうございます。
        左のメニューから操作を選んでください。
        """)
    else:
        st.markdown("""
        #### 感谢您的使用。
        请从左侧菜单中选择操作模式。
        """)

elif mode == "order_ai":
    st.subheader("📦 発注AIモード")

    ai_mode = "JDモード"
    st.caption("✅ 発注AIは JD在庫ベースで計算します")


    if st.button("🤖 計算を開始する"):
        SUPABASE_URL = st.secrets["SUPABASE_URL"]
        SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
        HEADERS = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }

        import math
        from datetime import date, timedelta

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
            df_warehouse = fetch_table("warehouse_stock")  # JD固定なので常に取得


        if df_sales.empty or df_purchase.empty or df_master.empty:
            st.warning("必要なデータが不足しています。")
            st.stop()
        if ai_mode == "JDモード" and df_warehouse.empty:
            st.warning("JDモード用の warehouse_stock データが不足しています。")
            st.stop()

        # 正規化・型揃え
        df_sales["jan"] = df_sales["jan"].apply(normalize_jan)
        df_purchase["jan"] = df_purchase["jan"].apply(normalize_jan)
        df_master["jan"] = df_master["jan"].apply(normalize_jan)
        df_sales["quantity_sold"] = pd.to_numeric(df_sales["quantity_sold"], errors="coerce").fillna(0).astype(int)
        df_sales["stock_available"] = pd.to_numeric(df_sales["stock_available"], errors="coerce").fillna(0).astype(int)

        if ai_mode == "JDモード":
            df_warehouse["product_code"] = df_warehouse["product_code"].apply(normalize_jan)
            df_warehouse["stock_available"] = pd.to_numeric(df_warehouse["stock_available"], errors="coerce").fillna(0).astype(int)

        # 発注履歴（上海除外/直近判定に使用）
        df_history = fetch_table("purchase_history")
        if df_history.empty:
            df_history = pd.DataFrame(columns=["jan", "quantity", "memo", "order_date"])
        df_history["quantity"] = pd.to_numeric(df_history["quantity"], errors="coerce").fillna(0).astype(int)
        df_history["memo"] = df_history["memo"].astype(str).fillna("")
        df_history["jan"] = df_history["jan"].apply(normalize_jan)

        # 「上海」分を item_master 発注済から控除
        df_shanghai = df_history[df_history["memo"].str.contains("上海", na=False)]
        df_shanghai_grouped = df_shanghai.groupby("jan")["quantity"].sum().reset_index(name="shanghai_quantity")
        if "発注済" not in df_master.columns:
            df_master["発注済"] = 0
        df_master = df_master.merge(df_shanghai_grouped, on="jan", how="left")
        df_master["shanghai_quantity"] = df_master["shanghai_quantity"].fillna(0).astype(int)
        df_master["発注済_修正後"] = (pd.to_numeric(df_master["発注済"], errors="coerce").fillna(0) - df_master["shanghai_quantity"]).clip(lower=0)

        # sales に反映
        df_sales.drop(columns=["発注済"], errors="ignore", inplace=True)
        df_sales = df_sales.merge(df_master[["jan", "発注済_修正後"]], on="jan", how="left")
        df_sales["発注済"] = df_sales["発注済_修正後"].fillna(0).astype(int)

        # purchase_data 型揃え
        df_purchase["order_lot"] = pd.to_numeric(df_purchase["order_lot"], errors="coerce").fillna(0).astype(int)
        df_purchase["price"] = pd.to_numeric(df_purchase["price"], errors="coerce")

        # ランク倍率（C/TESTで使用。A/Bは新仕様により未使用）
        rank_multiplier = {
            "Aランク": 1.0,  # 未使用
            "Bランク": 1.2,  # 未使用（発注数は1.7S、発注点1.2Sに変更）
            "Cランク": 1.0,
            "TEST": 1.5,
            "NEW": 1.5
        }

        with st.spinner("🤖 発注AIが計算をしています..."):
            # 直近（本日/昨日）発注の除外
            df_history_recent = df_history.copy()
            df_history_recent["order_date"] = pd.to_datetime(df_history_recent["order_date"], errors="coerce").dt.date
            today = date.today()
            yesterday = today - timedelta(days=1)
            recent_jans = df_history_recent[df_history_recent["order_date"].isin([today, yesterday])]["jan"].dropna().astype(str).apply(normalize_jan).unique().tolist()

            results = []

            for _, row in df_sales.iterrows():
                jan = row["jan"]
                sold = row["quantity_sold"]
                ordered = row["発注済"]

                # 在庫取得
                if ai_mode == "JDモード":
                    stock_row = df_warehouse[df_warehouse["product_code"] == jan]
                    stock = stock_row["stock_available"].values[0] if not stock_row.empty else 0
                else:
                    stock = row.get("stock_available", 0)

                # ランク取得
                rank_row = df_master[df_master["jan"] == jan]
                if not rank_row.empty and ("ランク" in df_master.columns):
                    rank = str(rank_row.iloc[0]["ランク"]) if pd.notna(rank_row.iloc[0]["ランク"]) else ""
                else:
                    rank = ""

                # ★対応：基底ランク（A/B/C or ""）
                base_rank = normalize_rank_base(rank)

                # 直近発注スキップ
                if jan in recent_jans:
                    continue

                current_total = stock + ordered

                # ===== 発注点判定 =====
                if base_rank in ["A", "B"]:
                    # 新仕様：在庫+発注済 が ceil(実績×1.2) を「下回ったら」発注
                    reorder_point = max(math.ceil(sold * 1.2), 1)
                    if current_total >= reorder_point:
                        continue  # 下回っていない（=発注しない）
                else:
                    # 既存仕様（C/TEST）
                    if rank == "Cランク":
                        reorder_point = max(math.floor(sold * 0.7), 1)
                    else:  # TEST or その他
                        reorder_point = max(math.floor(sold * 0.7), 1)
                    if current_total > reorder_point:
                        continue

                # ===== 発注数の基準 =====
                if base_rank in ["A", "B"]:
                    # 新仕様：発注数 = ceil(実績×1.7)
                    base_needed = max(math.ceil(sold * 1.7), 0)
                    # 「最低1個」特例は A/B でも有効にしておく（在庫ほぼゼロで実績ありの安全策）
                    if stock <= 1 and sold >= 1 and base_needed <= 0:
                        base_needed = 1
                else:
                    # C/TEST：不足分 = ceil(実績×倍率) - 在庫 - 発注済
                    m = rank_multiplier.get(rank, 1.0)
                    need_raw = math.ceil(sold * m) - stock - ordered
                    base_needed = 1 if (stock <= 1 and sold >= 1 and need_raw <= 0) else max(need_raw, 0)
                    if base_needed <= 0:
                        continue  # 不足なし

                # ここで base_needed > 0 なら発注必要

                # 仕入候補抽出
                options_all = df_purchase[df_purchase["jan"] == jan].copy()
                valid_options = pd.DataFrame()
                if not options_all.empty:
                    options_all["order_lot"] = pd.to_numeric(options_all["order_lot"], errors="coerce").fillna(0).astype(int)
                    options_all["price"] = pd.to_numeric(options_all["price"], errors="coerce")
                    options_lotpos = options_all[options_all["order_lot"] > 0].copy()
                    valid_options = options_lotpos[options_lotpos["price"].notna() & (options_lotpos["price"] > 0)].copy()

                # 価格が無い/ロット無効 → 空欄で出力
                if valid_options.empty:
                    results.append({
                        "jan": jan,
                        "販売実績": sold,
                        "在庫": stock,
                        "発注済": ordered,
                        "理論必要数": base_needed,
                        "発注数": "",     # 空欄
                        "ロット": "",     # 空欄
                        "数量": "",       # 空欄
                        "単価": "",       # 空欄
                        "総額": "",       # 空欄
                        "仕入先": "",     # 空欄
                        "ランク": rank
                    })
                    continue

                # 価格あり：ロット最適化
                options = valid_options.copy()

                # A/B は base_needed=ceil(1.7S) をロットで切り上げ
                # C/TEST は「不足分」= base_needed をロットで切り上げ
                need_for_lot = base_needed

                if base_rank in ["A", "B"]:
                    bigger_lots = options[options["order_lot"] >= need_for_lot]
                    if not bigger_lots.empty:
                        best_option = bigger_lots.sort_values("order_lot").iloc[0]
                    else:
                        best_option = options.sort_values("order_lot", ascending=False).iloc[0]
                else:
                    # 従来ロジック
                    options["diff"] = (options["order_lot"] - need_for_lot).abs()
                    smaller_lots = options[options["order_lot"] <= need_for_lot]
                    if not smaller_lots.empty:
                        best_option = smaller_lots.loc[smaller_lots["diff"].idxmin()]
                    else:
                        near_lots = options[(options["order_lot"] > need_for_lot) & (options["order_lot"] <= need_for_lot * 1.5) & (options["order_lot"] != 1)]
                        if not near_lots.empty:
                            best_option = near_lots.loc[near_lots["diff"].idxmin()]
                        else:
                            one_lot = options[options["order_lot"] == 1]
                            if not one_lot.empty:
                                best_option = one_lot.iloc[0]
                            else:
                                best_option = options.sort_values("order_lot").iloc[0]


                lot = int(best_option["order_lot"])
                sets = math.ceil(need_for_lot / lot)
                qty = sets * lot
                total_cost = qty * float(best_option["price"])
                
                results.append({
                    "jan": jan,
                    "販売実績": sold,
                    "在庫": stock,
                    "発注済": ordered,
                    "理論必要数": base_needed,
                    "発注数": int(qty),                   # ← 整数
                    "ロット": lot,                        # ← 整数
                    "数量": int(sets),                    # ← 整数
                    "単価": int(best_option["price"]),    # ← 整数
                    "総額": int(total_cost),              # ← 整数
                    "仕入先": best_option.get("supplier", "不明"),
                    "ランク": rank
                })

            # === 出力整形 ===
            if results:
                result_df = pd.DataFrame(results)

                # 商品名・取扱区分を結合
                if "商品コード" in df_master.columns:
                    df_master["商品コード"] = df_master["商品コード"].astype(str).str.strip()
                    result_df["jan"] = result_df["jan"].astype(str).str.strip()
                    df_temp = df_master[["商品コード", "商品名", "取扱区分"]].copy()
                    df_temp.rename(columns={"商品コード": "jan"}, inplace=True)
                    result_df = pd.merge(result_df, df_temp, on="jan", how="left")

                # 弁天在庫（表示のみ）
                df_benten = fetch_table("benten_stock")
                if not df_benten.empty:
                    df_benten["jan"] = df_benten["jan"].astype(str).str.strip()
                    df_benten = df_benten[["jan", "stock"]].rename(columns={"stock": "弁天在庫"})
                    result_df = pd.merge(result_df, df_benten, on="jan", how="left")
                    result_df["弁天在庫"] = result_df["弁天在庫"].fillna(0).astype(int)

                # 列名統一
                result_df.rename(columns={"在庫": "JD在庫"}, inplace=True)

                # 表示フィルタ
                if "商品名" in result_df.columns:
                    result_df = result_df[result_df["商品名"].notna()]
                if "取扱区分" in result_df.columns:
                    result_df = result_df[result_df["取扱区分"] != "取扱中止"]
                else:
                    st.warning("⚠️『取扱区分』列が存在しません。")

                # 表示順
                column_order = ["jan", "商品名", "ランク", "販売実績", "JD在庫", "弁天在庫", "発注済",
                                "理論必要数", "発注数", "ロット", "数量", "単価", "総額", "仕入先"]
                result_df = result_df[[c for c in column_order if c in result_df.columns]]

                st.success(f"✅ 発注対象: {len(result_df)} 件")
                st.dataframe(result_df, use_container_width=True)

                # 一括CSV
                csv = result_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button("📥 発注CSVダウンロード", data=csv, file_name="orders_available_based.csv", mime="text/csv")

                # 仕入先別CSV（仕入先が空白の行は除外）
                st.markdown("---")
                st.subheader("📦 仕入先別ダウンロード")
                if "仕入先" in result_df.columns:
                    for supplier, group in result_df[result_df["仕入先"].notna() & (result_df["仕入先"] != "")].groupby("仕入先"):
                        supplier_csv = group.to_csv(index=False).encode("utf-8-sig")
                        st.download_button(
                            label=f"📥 {supplier} 用 発注CSVダウンロード",
                            data=supplier_csv,
                            file_name=f"orders_{supplier}.csv",
                            mime="text/csv"
                        )
                else:
                    st.info("仕入先列がありません。")
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

    # ---------- データ取得 ----------
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

    def fetch_warehouse_stock():
        headers = {**HEADERS, "Prefer": "count=exact"}
        dfs = []
        offset, limit = 0, 1000
        while True:
            url = f"{SUPABASE_URL}/rest/v1/warehouse_stock?select=*&offset={offset}&limit={limit}"
            res = requests.get(url, headers=headers)
            if res.status_code == 416 or not res.json():
                break
            if res.status_code not in [200, 206]:
                st.error(f"warehouse_stock の取得に失敗: {res.status_code} / {res.text}")
                return pd.DataFrame()
            dfs.append(pd.DataFrame(res.json()))
            offset += limit
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    df_master = fetch_item_master()
    df_warehouse = fetch_warehouse_stock()

    if df_master.empty:
        st.warning("商品情報データベースにデータが存在しません。")
        st.stop()

    # 型整形
    df_master["jan"] = df_master["jan"].astype(str)
    if "商品コード" in df_master.columns:
        df_master["商品コード"] = df_master["商品コード"].astype(str)
    if "商品名" in df_master.columns:
        df_master["商品名"] = df_master["商品名"].astype(str)

    if not df_warehouse.empty:
        df_warehouse["product_code"] = df_warehouse["product_code"].astype(str)
        df_warehouse["stock_available"] = pd.to_numeric(df_warehouse["stock_available"], errors="coerce").fillna(0).astype(int)
        df_warehouse["stock_total"] = df_warehouse["stock_available"]

        # JD在庫（warehouse_stock）を結合
        df_master = df_master.merge(
            df_warehouse[["product_code", "stock_total", "stock_available"]],
            left_on="jan", right_on="product_code",
            how="left"
        )
        df_master["在庫"] = df_master["stock_total"].fillna(0).astype(int)
        df_master["利用可能"] = df_master["stock_available"].fillna(0).astype(int)
    else:
        df_master["在庫"] = 0
        df_master["利用可能"] = 0

    # 価格列（存在しなければ0で埋める）
    df_master["実績原価"] = pd.to_numeric(df_master.get("average_cost", 0), errors="coerce").fillna(0).astype(int)
    df_master["最安原価"] = pd.to_numeric(df_master.get("purchase_cost", 0), errors="coerce").fillna(0).astype(int)

    # ---------- 検索UI ＋ 絞り込み（共通関数） ----------
    df_view = apply_common_search_ui(df_master, language)

    # ---------- 表示 ----------
    view_cols = [
        "商品コード", "jan", "ランク", "メーカー名", "商品名", "取扱区分",
        "在庫", "発注済", "実績原価", "最安原価", "ケース入数", "発注ロット", "重量"
    ]
    available_cols = [c for c in view_cols if c in df_view.columns]

    display_df = (
        df_view[available_cols]
        .sort_values(by=[c for c in ["商品コード", "jan"] if c in available_cols])
    )

    row_count = len(display_df)
    h_left, h_right = st.columns([1, 0.15])
    h_left.subheader("商品一覧")
    h_right.markdown(
        f"<h4 style='text-align:right; margin-top: 0.6em;'>{row_count:,}件</h4>",
        unsafe_allow_html=True
    )

    st.dataframe(display_df, use_container_width=True)

    # ---------- CSV DL ----------
    csv = display_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📅 CSVダウンロード",
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
                "表示名": "商品名",
                "メーカー名": "メーカー名",
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

    # ✅ これもモード内に入れる！
    warehouse_file = st.file_uploader("🏢 倉庫在庫.xlsx アップロード", type=["xlsx"])
    if warehouse_file:
        def preprocess_warehouse_stock(file):
            df = pd.read_excel(file, sheet_name="倉庫在庫")
            df_upload = df.iloc[:, [9, 13, 22]].copy()  # J, N, W
            df_upload.columns = ["product_code", "stock_available", "jan"]
            df_upload["product_code"] = df_upload["product_code"].astype(str).str.strip()
            df_upload["jan"] = df_upload["jan"].astype(str).str.strip()
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
            df_warehouse = preprocess_warehouse_stock(warehouse_file)
            upload_warehouse_stock(df_warehouse)

    benten_file = st.file_uploader("🏭 BENTEN倉庫在庫（CSV）アップロード", type=["csv"])
    if benten_file:
        def preprocess_benten_stock(file):
            df = pd.read_csv(file)
            df.columns = df.columns.str.replace("　", "").str.replace("\ufeff", "").str.strip()

            upc_col = None
            stock_col = None
            for col in df.columns:
                if "UPC" in col:
                    upc_col = col
                if "利用可能" in col:
                    stock_col = col

            if not upc_col or not stock_col:
                raise ValueError(f"❌ 'UPCコード' または '利用可能' 列が見つかりません！列名: {df.columns.tolist()}")

            df = df[[upc_col, stock_col]].copy()
            df.rename(columns={upc_col: "jan", stock_col: "stock"}, inplace=True)
            df["jan"] = df["jan"].astype(str).str.strip()
            df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0).round().astype(int)
            df["updated_at"] = pd.Timestamp.now().isoformat()
            return df

        def upload_benten_stock(df):
            try:
                requests.delete(f"{SUPABASE_URL}/rest/v1/benten_stock?jan=neq.null", headers=HEADERS)
                df = df.drop_duplicates(subset=["jan"], keep="last")
                df = df.replace({pd.NA: None, pd.NaT: None, float("nan"): None}).where(pd.notnull(df), None)

                for i in range(0, len(df), 500):
                    batch = df.iloc[i:i+500].to_dict(orient="records")
                    res = requests.post(
                        f"{SUPABASE_URL}/rest/v1/benten_stock",
                        headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
                        json=batch
                    )
                    if res.status_code not in [200, 201]:
                        st.error(f"❌ benten_stock バッチPOST失敗: {res.status_code} {res.text}")
                        return

                st.success(f"✅ benten_stock に {len(df)} 件アップロード完了")

            except Exception as e:
                st.error(f"❌ benten_stock アップロード中にエラー: {e}")

        with st.spinner("📤 BENTEN倉庫CSV を処理中..."):
            df_benten = preprocess_benten_stock(benten_file)
            upload_benten_stock(df_benten)



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

    # ---------- 🔍 検索UI ＋ 絞り込み（商品情報検索と共通） ----------
    df_view = apply_common_search_ui(df_joined, language)

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



elif mode == "rank_check":
    st.subheader("📌 ランク商品確認モード")

    # =========================
    # データ取得
    # =========================
    df_item = fetch_table("item_master")
    df_sales = fetch_table("sales")
    df_stock = fetch_table("warehouse_stock")
    df_benten = fetch_table("benten_stock")
    df_history = fetch_table("purchase_history")
    
    # =========================
    # 必須/任意 テーブル判定
    # =========================
    required = {
        "item_master": df_item,
        "sales": df_sales,
        "warehouse_stock": df_stock,
    }
    
    optional = {
        "benten_stock": df_benten,
        "purchase_history": df_history,
    }
    
    # 必須が空なら止める
    empty_required = [name for name, df in required.items() if df is None or df.empty]
    if empty_required:
        st.warning(f"必要なテーブルが空です（必須）: {', '.join(empty_required)}")
        st.stop()
    
    # 任意が空なら 0行DFを用意して続行
    if df_benten is None or df_benten.empty:
        # jan / stock だけあれば後続の merge が成立する
        df_benten = pd.DataFrame(columns=["jan", "stock"])
    
    if df_history is None or df_history.empty:
        # jan / quantity / memo があれば後続処理が成立する
        df_history = pd.DataFrame(columns=["jan", "quantity", "memo"])

    # =========================
    # データ整形（item_master）
    # =========================
    df_item["jan"] = df_item["jan"].astype(str).str.strip()
    df_item.loc[df_item["jan"].isin(["", "nan", "None", "NULL"]), "jan"] = None
    df_item["ランク"] = df_item["ランク"].astype(str).str.strip()
    df_item["商品名"] = df_item["商品名"].astype(str)
    df_item["メーカー名"] = df_item["メーカー名"].astype(str)

    # =========================
    # 発注済（上海除外）
    # =========================
    df_history["quantity"] = pd.to_numeric(df_history["quantity"], errors="coerce").fillna(0).astype(int)
    df_history["memo"] = df_history["memo"].astype(str).fillna("")
    df_history["jan"] = df_history["jan"].astype(str).str.strip()

    df_shanghai = df_history[df_history["memo"].str.contains("上海", na=False)]
    df_shanghai_grouped = (
        df_shanghai.groupby("jan")["quantity"]
        .sum()
        .reset_index(name="shanghai_quantity")
    )

    df_item["発注済"] = pd.to_numeric(df_item["発注済"], errors="coerce").fillna(0).astype(int)
    df_item = df_item.merge(df_shanghai_grouped, on="jan", how="left")
    df_item["shanghai_quantity"] = df_item["shanghai_quantity"].fillna(0).astype(int)
    df_item["発注済"] = (df_item["発注済"] - df_item["shanghai_quantity"]).clip(lower=0)

    # =========================
    # 対象商品（JANありは必須。ランクは全部OK：TEST含む）
    # =========================
    df_ab = df_item[df_item["jan"].notnull()].copy()

    df_ab["JAN"] = df_ab["jan"].astype(str).str.strip()
    df_ab = df_ab.drop_duplicates(subset=["JAN"])

    # =========================
    # フィルターUI（ランク候補を自動生成）
    # =========================
    col1, col2 = st.columns(2)

    with col1:
        name_filter = st.text_input("🔍 商品名で絞り込み（部分一致）")

    with col2:
        maker_list = sorted(df_ab["メーカー名"].dropna().unique().tolist())
        selected_maker = st.selectbox(
            "🏭 メーカー名で絞り込み",
            ["すべて"] + maker_list
        )

    # ランク候補（自動生成：空やnanは除外）
    rank_options = (
        df_ab["ランク"].astype(str).str.strip()
        .replace(["", "nan", "None", "NULL"], pd.NA)
        .dropna()
        .unique()
        .tolist()
    )
    rank_options = sorted(rank_options)

    if rank_options:
        selected_ranks = st.multiselect(
            "📌 表示するランク（自動）",
            rank_options,
            default=rank_options
        )
    else:
        st.warning("⚠️ ランクが登録されていないため、ランクフィルタを表示できません。")
        selected_ranks = []


    # =========================
    # sales → JAN（実績30日）
    # =========================
    df_sales["JAN"] = df_sales["jan"].astype(str).str.strip()

    df_sales_30 = (
        df_sales.groupby("JAN", as_index=False)["quantity_sold"]
        .sum()
        .rename(columns={"quantity_sold": "実績（30日）"})
    )

    # =========================
    # 在庫
    # =========================
    df_stock["JAN"] = df_stock["jan"].astype(str).str.strip()
    df_stock = df_stock.rename(columns={"stock_available": "JD在庫"})

    df_benten["JAN"] = df_benten["jan"].astype(str).str.strip()
    df_benten = df_benten.rename(columns={"stock": "弁天在庫"})

    # =========================
    # 発注済
    # =========================
    df_item_sub = df_item[["jan", "発注済"]].copy()
    df_item_sub["JAN"] = df_item_sub["jan"].astype(str).str.strip()
    df_item_sub = df_item_sub[["JAN", "発注済"]]

    # =========================
    # マージ
    # =========================
    base_cols = [
        "JAN",
        "商品名",
        "メーカー名",
        "ランク",
        "ケース入数",
        "発注ロット"
    ]

    if "purchase_cost" in df_ab.columns:
        base_cols.append("purchase_cost")

    df_merged = (
        df_ab[base_cols]
        .rename(columns={"purchase_cost": "最安原価"})
        .merge(df_sales_30, on="JAN", how="left")
        .merge(df_item_sub, on="JAN", how="left")
        .merge(df_stock[["JAN", "JD在庫"]], on="JAN", how="left")
        .merge(df_benten[["JAN", "弁天在庫"]], on="JAN", how="left")
    )

    # =========================
    # 欠損補完
    # =========================
    df_merged["実績（30日）"] = df_merged["実績（30日）"].fillna(0)
    df_merged["発注済"] = df_merged["発注済"].fillna(0).astype(int)
    df_merged["JD在庫"] = df_merged["JD在庫"].fillna(0)
    df_merged["弁天在庫"] = df_merged["弁天在庫"].fillna(0)
    df_merged["最安原価"] = pd.to_numeric(df_merged.get("最安原価"), errors="coerce")

    # =========================
    # 発注アラート
    # =========================
    df_merged["発注アラート1.0"] = df_merged["実績（30日）"] > (
        df_merged["JD在庫"] + df_merged["弁天在庫"] + df_merged["発注済"]
    )

    df_merged["発注アラート1.2"] = (df_merged["実績（30日）"] * 1.2) > (
        df_merged["JD在庫"] + df_merged["弁天在庫"] + df_merged["発注済"]
    )

    # =========================
    # 条件フィルター
    # =========================
    check_1_0 = st.checkbox("✅ 発注アラート1.0のみ表示", value=False)
    check_1_2 = st.checkbox("✅ 発注アラート1.2のみ表示", value=False)

    df_result = df_merged[df_merged["ランク"].isin(selected_ranks)].copy()

    if name_filter:
        df_result = df_result[df_result["商品名"].str.contains(name_filter, case=False, na=False)]

    if selected_maker != "すべて":
        df_result = df_result[df_result["メーカー名"] == selected_maker]

    if check_1_0:
        df_result = df_result[df_result["発注アラート1.0"]]

    if check_1_2:
        df_result = df_result[df_result["発注アラート1.2"]]

    # =========================
    # 出力
    # =========================
    st.dataframe(df_result[[
        "JAN",
        "商品名",
        "メーカー名",
        "ランク",
        "ケース入数",
        "発注ロット",
        "実績（30日）",
        "JD在庫",
        "弁天在庫",
        "発注済",
        "最安原価",
        "発注アラート1.0",
        "発注アラート1.2"
    ]])




elif mode == "difficult_items":
    st.subheader("🚫 入荷困難商品モード")

    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    df = fetch_table("difficult_items")
    if not df.empty:
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        df["updated_at"] = pd.to_datetime(df["updated_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        df["選択"] = False

        cols = ["選択", "item_key", "reason", "note", "created_at", "updated_at", "id"]
        df = df[cols]

        st.write("### 📋 現在の入荷困難リスト")

        edited_df = st.data_editor(
            df,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "選択": st.column_config.CheckboxColumn("選択")
            },
            disabled=[
                "item_key", "reason", "note", "created_at", "updated_at"
            ]
        )

        selected_df = edited_df[edited_df["選択"]]
        selected_ids = selected_df["id"].tolist()

        # ✅ ボタン無効化管理
        delete_btn_disabled = False

        if st.button("✅ 選択した行を削除"):
            if selected_ids:
                for _id in selected_ids:
                    record = df[df["id"] == _id].copy().to_dict(orient="records")[0]
                    record.pop("選択", None)
                    record.pop("created_at", None)
                    record.pop("updated_at", None)
                    record["item_id"] = record["id"]
                    record.pop("id")
                    record["action"] = "delete"
                    record["action_at"] = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).isoformat()
        
                    res1 = requests.post(
                        f"{SUPABASE_URL}/rest/v1/difficult_items_history",
                        headers={**HEADERS, "Prefer": "return=representation"},
                        json=record
                    )
        
                    res2 = requests.delete(
                        f"{SUPABASE_URL}/rest/v1/difficult_items?id=eq.{_id}",
                        headers=HEADERS
                    )
        
                st.success("✅ 削除完了！")
                st.rerun()
            else:
                st.warning("⚠️ 行が選択されていません")

    with st.form("add_difficult_item"):
        item_key = st.text_input("ブランド / 商品名 / JAN など")
        reason = st.text_input("入荷困難理由")
        note = st.text_area("備考")

        submitted = st.form_submit_button("登録する")
        if submitted:
            payload = {
                "item_key": item_key,
                "reason": reason,
                "note": note
            }

            res = requests.post(
                f"{SUPABASE_URL}/rest/v1/difficult_items",
                headers={**HEADERS, "Prefer": "return=representation"},
                json=payload
            )
            st.write("登録POST:", res.status_code, res.text)

            if res.status_code in [200, 201]:
                record = res.json()[0]
                record["item_id"] = record["id"]
                record.pop("id")
                record.pop("created_at", None)  # ← 忘れず追加！
                record.pop("updated_at", None)  # ← 忘れず追加！
                record["action"] = "insert"
                record["action_at"] = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).isoformat()

                res2 = requests.post(
                    f"{SUPABASE_URL}/rest/v1/difficult_items_history",
                    headers={**HEADERS, "Prefer": "return=representation"},
                    json=record
                )

                st.success("✅ 登録しました！")
                st.rerun()
            else:
                st.error(f"登録失敗: {res.text}")

    df_history = fetch_table("difficult_items_history")
    
    if not df_history.empty:
        one_week_ago = datetime.datetime.now(ZoneInfo("Asia/Tokyo")) - datetime.timedelta(days=7)
        df_history["action_at"] = pd.to_datetime(df_history["action_at"], utc=True)
        df_history = df_history[df_history["action_at"] >= one_week_ago]
    
        # 🔥 JSTに変換
        df_history["action_at"] = df_history["action_at"].dt.tz_convert("Asia/Tokyo")
        df_history["action_at"] = df_history["action_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
    
        st.write("📜 **履歴（直近7日分）**")
        st.dataframe(df_history, use_container_width=True)
    else:
        st.write("📜 **履歴はまだありません**")


# parse_items_fixed は今のまま利用OK

elif mode == "order":
    import numpy as np
    from datetime import datetime, date

    st.subheader("📦 発注書作成モード")

    option = st.radio("入力方法を選択してください", ["テキスト貼り付け", "CSVアップロード"])
    df_order = None

    # ---------- テンプレート配布（CSVのみ） ----------
    def provide_template():
        template = pd.DataFrame({
            "jan": [],
            "数量": [],
            "単価": []
        })
        csv_temp = template.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            "📝 入力用CSVテンプレートをダウンロード",
            data=csv_temp,
            mime="text/csv",
            file_name="order_template.csv",
            help="必須列: jan, 数量, 単価（ロット×数量でも可）"
        )

    provide_template()

    # ---------- 入力 ----------
    if option == "テキスト貼り付け":
        input_text = st.text_area("注文テキストを貼り付け", height=300)
        if st.button("テキストを変換"):
            if not input_text.strip():
                st.warning("⚠ テキストを入力してください")
            else:
                df_order = parse_items_fixed(input_text)
                if df_order is not None and not df_order.empty and "品番" in df_order.columns:
                    df_order = df_order[df_order["品番"] != "合計"]
                else:
                    st.warning("⚠ 商品データを正しく取得できませんでした")

    elif option == "CSVアップロード":
        uploaded_file = st.file_uploader("注文CSVをアップロード", type=["csv", "xlsx"])
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith(".xlsx"):
                    df_order = pd.read_excel(uploaded_file)
                else:
                    df_order = pd.read_csv(uploaded_file, encoding="utf-8-sig")
            except UnicodeDecodeError:
                df_order = pd.read_csv(uploaded_file, encoding="shift_jis")

            df_order.columns = df_order.columns.str.strip().str.lower()

            rename_map = {
                "janコード": "jan", "ＪＡＮ": "jan", "jan": "jan", "JAN": "jan",
                "数量": "数量", "数": "数量", "qty": "数量",
                "ロット×数量": "ロット×数量",
                "単価": "単価", "価格": "単価", "price": "単価"
            }
            df_order.rename(columns={k.lower(): v for k, v in rename_map.items() if k.lower() in df_order.columns}, inplace=True)

            if "jan" not in df_order.columns:
                st.error("❌ CSV/エクセルに 'jan' 列がありません")
                df_order = None

    # ---------- 発注情報 ----------
    suppliers = [
        "0020 エンパイヤ自動車株式会社（KONNGU’S）", "0025 株式会社オンダ","0029 K・BLUE株式会社",
        "0072 新富士バーナー株式会社", "0073 株式会社　エィチ・ケイ", "0077 大分共和株式会社",
        "0085 中央物産株式会社", "0106 西川株式会社", "0197 大木化粧品株式会社", "0201 現金仕入れ",
        "0202 トラスコ中山株式会社", "0256 株式会社 グランジェ", "0258 株式会社 ファイン",
        "0263 株式会社メディファイン", "0285 有限会社オーザイ首藤", "0343 株式会社森フォレスト",
        "0376 菅野株式会社", "0402 ハリマ共和物産株式会社", "0411 株式会社ラクーンコマース（スーパーデリバリー）",
        "0435 株式会社 流久商事", "0444 ハナモンワークス 合同会社", "0445 富森商事 株式会社",
        "0457 カネイシ株式会社", "0468 王子国際貿易株式会社", "0469 株式会社 新日配薬品",
        "0474 株式会社　五洲", "0475 株式会社シゲマツ", "0476 カード仕入れ",
        "0479 スケーター株式会社", "0482 風雲商事株式会社", "0484 ZSA商事株式会社",
        "0486 Maple International株式会社", "0490 NEW WIND株式会社", "0491 アプライド株式会社",
        "0504 京浜商事株式会社", "0510 株式会社タジマヤ", "C000510 太田物産 株式会社",
    ]
    employees = ["079 隋艶偉", "005 川崎里子", "037 米澤和敏", "043 徐越"]
    departments = ["輸出事業 : 輸出（ASEAN）", "輸出事業 : 輸出（中国）", "輸出事業"]
    locations = ["JD-物流-千葉", "弁天倉庫"]

    col1, col2, col3 = st.columns(3)
    with col1:
        external_id = datetime.now().strftime("%Y%m%d%H%M%S")
        st.text_input("外部ID", value=external_id, disabled=True)
        supplier = st.selectbox("仕入先", suppliers)
    with col2:
        order_date = st.date_input("日付", value=date.today())
        employee = st.selectbox("従業員", employees)
    with col3:
        department = st.selectbox("部門", departments)
        location = st.selectbox("場所", locations)

    memo = st.text_input("メモ", "")

    # ---------- 発注書生成 ----------
    if df_order is not None and not df_order.empty:
        df_item = fetch_table("item_master")
        df_item.columns = df_item.columns.str.strip().str.lower()

        # JAN整形（先頭00000を削除）
        df_order["jan"] = df_order["jan"].astype(str).str.strip().str.replace(r"^0{5,}", "", regex=True)
        df_item["jan"] = df_item["jan"].astype(str).str.strip().str.replace(r"^0{5,}", "", regex=True)

        # 税率判定関数
        def get_tax_rate(schedule):
            if not schedule or pd.isna(schedule): return 0.0
            if "10" in schedule: return 0.10
            if "8" in schedule: return 0.08
            return 0.0

        df_item["tax_rate"] = df_item.get("納税スケジュール", "").apply(get_tax_rate)

        df = df_order.merge(df_item, on="jan", how="left")

        # 欠損JANの表示
        missing = df[df["商品名"].isna()]
        if not missing.empty:
            st.warning(f"⚠ {len(missing)} 件のJANが item_master に見つかりません")
            st.dataframe(missing[["jan"]])

        # 数値変換
        qty_col = "ロット×数量" if "ロット×数量" in df.columns else "数量"
        df["数量"] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0).astype(int)
        df["単価"] = pd.to_numeric(df["単価"], errors="coerce").fillna(0).astype(int)

        # 金額・税額・総額
        df["金額"] = df["単価"] * df["数量"]
        df["税額"] = np.floor(df["金額"] * df["tax_rate"]).fillna(0).astype(int)
        df["総額"] = df["金額"] + df["税額"]

        order_date_str = order_date.strftime("%Y/%m/%d")

        df_out = pd.DataFrame({
            "外部ID": external_id,
            "仕入先": supplier,
            "日付": order_date_str,
            "従業員": employee,
            "部門": department,
            "メモ": memo,
            "場所": location,
            "アイテム": df.get("商品コード", "").astype(str) + " " + df.get("商品名", ""),
            "数量": df["数量"],
            "単価/率": df["単価"],
            "金額": df["金額"],
            "税額": df["税額"],
            "総額": df["総額"]
        })

        st.subheader("📑 発注書プレビュー")
        st.dataframe(df_out)

        csv_out = df_out.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 発注書CSVをダウンロード",
            data=csv_out,
            file_name=f"発注書_{external_id}.csv",
            mime="text/csv"
        )
        
elif mode == "store_profit":
    st.subheader("🏪 店舗別粗利一覧")

    # Supabase からデータ取得
    df = fetch_table("store_profit_lines")

    if df is None or df.empty:
        st.warning("store_profit_lines が空か、読み出せていません。")
        st.info("次を確認してください：\n"
                "1) Supabaseにデータがあるか（SQLで SELECT count(*)）\n"
                "2) RLSが有効なら、匿名キー(anon)に対してSELECT許可ポリシーがあるか\n"
                "3) fetch_table が 'store_profit_lines' を正しいプロジェクトに向けているか")
        st.stop()

    # 列の存在チェック
    required_cols = {"report_period","line_type","store","qty","revenue","defined_cost","gross_profit","original_line"}
    missing = required_cols - set(df.columns)
    if missing:
        st.error(f"必要列が足りません: {missing}")
        st.stop()

    # 期間選択
    periods = sorted(df["report_period"].dropna().unique())
    if len(periods) == 0:
        st.warning("report_period が見つかりません。アップロード時の period を確認してください。")
        st.stop()
    sel_period = st.selectbox("対象期間を選択", periods, index=len(periods)-1)

    dfp = df[df["report_period"] == sel_period]

    # 店舗別集計（detailのみ）
    dfd = dfp[dfp["line_type"] == "detail"].copy()
    if dfd.empty:
        st.warning("この期間の明細行（line_type='detail'）がありません。CSVの取り込みを確認してください。")
        st.stop()

    # 数値型に変換（念のため）
    for c in ["qty","revenue","defined_cost","gross_profit"]:
        dfd[c] = pd.to_numeric(dfd[c], errors="coerce").fillna(0).astype(int)

    grouped = (
        dfd.groupby("store", as_index=False)
           .agg(qty=("qty","sum"),
                revenue=("revenue","sum"),
                defined_cost=("defined_cost","sum"),
                gross_profit=("gross_profit","sum"))
    )
    grouped["gross_margin"] = (grouped["gross_profit"] / grouped["revenue"] * 100).fillna(0).round(2)

        # ---- 合計（全店）テーブルを先に表示する ---------------------------------
    # 表示ラベル（日本語/中国語）
    LABELS = {
        "日本語": {
            "store": "店舗",
            "qty": "数量",
            "revenue": "売上",
            "defined_cost": "定義原価",
            "gross_profit": "粗利",
            "gross_margin": "粗利率",
        },
        "中文": {
            "store": "店铺",
            "qty": "数量",
            "revenue": "销售额",
            "defined_cost": "定义成本",
            "gross_profit": "毛利",
            "gross_margin": "毛利率",
        },
    }
    TOTAL_LABELS = {
        "日本語": {
            "title": "🧮 合計（全店）",
            "period": "対象期間",
            "qty": "合計数量",
            "revenue": "売上合計",
            "defined_cost": "定義原価合計",
            "gross_profit": "粗利合計",
            "gross_margin": "粗利率",
            "download": "📥 合計（全店）をCSVダウンロード",
        },
        "中文": {
            "title": "🧮 合计（全店）",
            "period": "期间",
            "qty": "合计数量",
            "revenue": "销售额合计",
            "defined_cost": "定义成本合计",
            "gross_profit": "毛利合计",
            "gross_margin": "毛利率",
            "download": "📥 下载合计（全店）CSV",
        },
    }
    labels = LABELS.get(language, LABELS["日本語"])
    tlabels = TOTAL_LABELS.get(language, TOTAL_LABELS["日本語"])

    # フォーマッタ
    def fmt_int(x):
        try:
            return f"{int(x):,}"
        except:
            return x
    def fmt_money(x):
        try:
            return f"{int(round(float(x))):,}"
        except:
            return x
    def fmt_pct(x):
        try:
            return f"{float(x):.2f}%"
        except:
            return x

    # 合計値
    total_qty     = int(grouped["qty"].sum())
    total_rev     = int(grouped["revenue"].sum())
    total_cost    = int(grouped["defined_cost"].sum())
    total_gp      = int(grouped["gross_profit"].sum())
    total_margin  = round((total_gp / total_rev * 100) if total_rev else 0.0, 2)

    df_total = pd.DataFrame([{
        tlabels["period"]: sel_period,
        tlabels["qty"]: fmt_int(total_qty),
        tlabels["revenue"]: fmt_money(total_rev),
        tlabels["defined_cost"]: fmt_money(total_cost),
        tlabels["gross_profit"]: fmt_money(total_gp),
        tlabels["gross_margin"]: fmt_pct(total_margin),
    }])

    st.markdown(f"### {tlabels['title']}")
    st.dataframe(df_total, use_container_width=True)

    st.download_button(
        tlabels["download"],
        df_total.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"store_profit_total_{sel_period}.csv",
        mime="text/csv",
    )


    # ---- 表示ラベル（日本語/中国語）と言語別フォーマット ----
    LABELS = {
        "日本語": {
            "store": "店舗",
            "qty": "数量",
            "revenue": "売上",
            "defined_cost": "定義原価",
            "gross_profit": "粗利",
            "gross_margin": "粗利率",
        },
        "中文": {
            "store": "店铺",
            "qty": "数量",
            "revenue": "销售额",
            "defined_cost": "定义成本",
            "gross_profit": "毛利",
            "gross_margin": "毛利率",
        },
    }
    labels = LABELS.get(language, LABELS["日本語"])

    # 0除算などのNaN/infは0に
    grouped.replace([float("inf"), float("-inf")], 0, inplace=True)
    grouped.fillna(0, inplace=True)

    # 表示用に列名を翻訳
    display_df = grouped.rename(columns={
        "store": labels["store"],
        "qty": labels["qty"],
        "revenue": labels["revenue"],
        "defined_cost": labels["defined_cost"],
        "gross_profit": labels["gross_profit"],
        "gross_margin": labels["gross_margin"],
    })

    # 数字フォーマット：カンマ区切り / 粗利率は%付き（小数2桁）
    def fmt_int(x): 
        try: return f"{int(x):,}"
        except: return x
    def fmt_money(x):
        try: return f"{int(round(float(x))):,}"
        except: return x
    def fmt_pct(x):
        try: return f"{float(x):.2f}%"
        except: return x

    display_df[labels["qty"]] = display_df[labels["qty"]].map(fmt_int)
    display_df[labels["revenue"]] = display_df[labels["revenue"]].map(fmt_money)
    display_df[labels["defined_cost"]] = display_df[labels["defined_cost"]].map(fmt_money)
    display_df[labels["gross_profit"]] = display_df[labels["gross_profit"]].map(fmt_money)
    display_df[labels["gross_margin"]] = display_df[labels["gross_margin"]].map(fmt_pct)

    st.write("### 店舗別集計")
    # 粗利の大きい順で見やすく
    display_df = display_df.sort_values(by=labels["gross_profit"], ascending=False, key=lambda s: s.str.replace(",", "", regex=False).astype(int))
    st.dataframe(display_df, use_container_width=True)

    # ---- ダウンロード（集計 / 原文）----
    # 集計CSVは見た目の列名で出力（数値は生データのままが良ければ 'grouped' を使ってください）
    grouped_l10n = grouped.rename(columns={
        "store": labels["store"],
        "qty": labels["qty"],
        "revenue": labels["revenue"],
        "defined_cost": labels["defined_cost"],
        "gross_profit": labels["gross_profit"],
        "gross_margin": labels["gross_margin"],
    })
    st.download_button(
        "📥 店舗別集計をCSVダウンロード",
        grouped_l10n.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"store_profit_summary_{sel_period}.csv",
        mime="text/csv",
    )

    csv_original = "\n".join(dfp["original_line"].tolist())
    st.download_button(
        "📥 元CSVをダウンロード（完全復元）",
        csv_original,
        file_name=f"store_profit_original_{sel_period}.csv",
        mime="text/csv",
    )

elif mode == "daily_sales":
    st.subheader("📆 店舗別前日売上（最新日）")

    df = fetch_table("store_profit_daily_lines")
    if df is None or df.empty:
        st.warning("store_profit_daily_lines が空か、読み出せていません。")
        st.stop()

    required = {"report_date","line_type","store","item","qty","revenue","defined_cost","gross_profit"}
    missing = required - set(df.columns)
    if missing:
        st.error(f"必要列が足りません: {missing}")
        st.stop()

    df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce").dt.date
    for c in ["qty","revenue","defined_cost","gross_profit"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    # 最新日だけ
    latest_date = df["report_date"].max()
    cur = df[df["report_date"] == latest_date].copy()

    # detailのみ + 「合計/総計/計で始まる疑似明細」や EMPTY を除外
    pat_agg = r"^(合計|総計|計)\b"
    cur_detail = cur[cur["line_type"] == "detail"].copy()
    cur_detail = cur_detail[
        ~cur_detail["item"].astype(str).str.match(pat_agg, na=False) &
        ~cur_detail["item_name"].astype(str).str.fullmatch(r"\s*EMPTY\s*", na=False)
    ]

    # ─ 全店合計：detail のみから算出（重複なし） ─
    tot_qty  = int(cur_detail["qty"].sum())
    tot_rev  = int(cur_detail["revenue"].sum())
    tot_cost = int(cur_detail["defined_cost"].sum())
    tot_gp   = int(cur_detail["gross_profit"].sum())
    tot_mgn  = round((tot_gp / tot_rev * 100) if tot_rev else 0.0, 2)

    def fmt_int(x):   return f"{int(x):,}"
    def fmt_money(x): return f"{int(round(float(x))):,}"
    def fmt_pct(x):   return f"{float(x):.2f}%"

    df_total = pd.DataFrame([{
        "対象日": latest_date,
        "合計数量": fmt_int(tot_qty),
        "売上合計": fmt_money(tot_rev),
        "定義原価合計": fmt_money(tot_cost),
        "粗利合計": fmt_money(tot_gp),
        "粗利率": fmt_pct(tot_mgn),
    }])

    st.markdown("### 🧮 合計（全店）")
    st.dataframe(df_total, use_container_width=True)
    st.download_button(
        "📥 合計（全店）CSVダウンロード",
        df_total.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"daily_sales_total_{latest_date}.csv",
        mime="text/csv",
    )

    # ─ 店舗別：detail のみから集計 ─
    cur_g = (cur_detail.groupby("store", as_index=False)
                .agg(qty=("qty","sum"),
                     revenue=("revenue","sum"),
                     defined_cost=("defined_cost","sum"),
                     gross_profit=("gross_profit","sum")))
    cur_g["gross_margin"] = (
        (cur_g["gross_profit"] / cur_g["revenue"].replace({0: pd.NA}) * 100)
        .astype(float).round(2).fillna(0.0)
    )

    LABELS = {
        "日本語": {"store":"店舗","qty":"数量","revenue":"売上","defined_cost":"定義原価","gross_profit":"粗利","gross_margin":"粗利率"},
        "中文":   {"store":"店铺","qty":"数量","revenue":"销售额","defined_cost":"定义成本","gross_profit":"毛利","gross_margin":"毛利率"},
    }
    labels = LABELS.get(language, LABELS["日本語"])

    disp = cur_g.rename(columns={
        "store": labels["store"],
        "qty": labels["qty"],
        "revenue": labels["revenue"],
        "defined_cost": labels["defined_cost"],
        "gross_profit": labels["gross_profit"],
        "gross_margin": labels["gross_margin"],
    }).copy()

    disp[labels["qty"]]          = disp[labels["qty"]].map(fmt_int)
    disp[labels["revenue"]]      = disp[labels["revenue"]].map(fmt_money)
    disp[labels["defined_cost"]] = disp[labels["defined_cost"]].map(fmt_money)
    disp[labels["gross_profit"]] = disp[labels["gross_profit"]].map(fmt_money)
    disp[labels["gross_margin"]] = disp[labels["gross_margin"]].map(fmt_pct)

    st.write("### 店舗別")
    disp = disp.sort_values(
        by=labels["revenue"],
        ascending=False,
        key=lambda s: s.str.replace(",", "", regex=False).astype(int)
    )
    st.dataframe(disp, use_container_width=True)

    st.download_button(
        "📥 店舗別（数値そのまま）CSVダウンロード",
        cur_g.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"daily_sales_by_store_{latest_date}.csv",
        mime="text/csv",
    )


elif mode == "expiry_manage":
    # =========================
    # 🧊 賞味期限管理モード
    # =========================
    st.subheader("🧊 賞味期限管理" if language == "日本語" else "🧊 保质期管理")

    # --- Supabase（このファイル上部で定義済み：SUPABASE_URL_PRE / HEADERS_PRE を使う） ---
    SUPABASE_URL = SUPABASE_URL_PRE
    HEADERS = HEADERS_PRE

    # ---------- ラベル ----------
    LABEL = {
        "日本語": {
            "sync": "🔄 Larkから同期（手動）",
            "synced": "✅ 同期完了",
            "syncing": "同期中...",
            "err": "⚠️ エラー行",
            "filters": "🔎 フィルタ",
            "status": "状態",
            "days": "残り日数",
            "expiry": "最短賞味期限",
            "download": "📥 CSVダウンロード",
            "limit": "表示件数上限",
            "keyword": "JAN / 商品名 検索",
            "only_with_expiry": "賞味期限ありのみ",
            "only_no_expiry": "未登録のみ",

            # 追加（在庫フィルタ）
            "only_in_stock": "在庫ありのみ（在庫0は非表示）",
            "only_zero_stock": "在庫0のみ",

            # メッセージ類
            "no_data": "item_expiry にデータがありません。先に同期してください。",
            "sync_failed": "❌ 同期失敗",
            "fetch_failed_item_expiry": "item_expiry の取得に失敗",
            "fetch_failed_warehouse": "warehouse_stock の取得に失敗",
            "lark_secret_missing": "❌ Lark の認証情報が st.secrets にありません（LARK_APP_ID / LARK_APP_SECRET）",

            # 状態値（表示・フィルタ・色付けで共通利用）
            "st_expired": "期限切れ",
            "st_within": "60日以内",
            "st_ok": "余裕あり",
            "st_none": "未登録",

            # 列名（df列に入れる文字）
            "col_days": "残り日数",
            "col_status": "状態",
            "sync_note": "※ 同期には約20秒程度かかります。同期完了後、ブラウザを更新（再読み込み）してください。",
        },
        "中文": {
            "sync": "🔄 从Lark同步（手动）",
            "synced": "✅ 同步完成",
            "syncing": "同步中...",
            "err": "⚠️ 错误行",
            "filters": "🔎 筛选",
            "status": "状态",
            "days": "剩余天数",
            "expiry": "最短保质期",
            "download": "📥 下载CSV",
            "limit": "显示条数上限",
            "keyword": "搜索：条码 / 商品名",
            "only_with_expiry": "仅显示已登记",
            "only_no_expiry": "仅显示未登记",
            "sync_note": "※ 同步大约需要20秒左右。同步完成后，请刷新浏览器页面。",

            # 追加（在庫フィルタ）
            "only_in_stock": "仅显示有库存（库存0隐藏）",
            "only_zero_stock": "仅显示库存0",

            # メッセージ類
            "no_data": "item_expiry 没有数据。请先进行同步。",
            "sync_failed": "❌ 同步失败",
            "fetch_failed_item_expiry": "获取 item_expiry 失败",
            "fetch_failed_warehouse": "获取 warehouse_stock 失败",
            "lark_secret_missing": "❌ st.secrets 中缺少Lark认证信息（LARK_APP_ID / LARK_APP_SECRET）",

            # 状態値（中国語）
            "st_expired": "已过期",
            "st_within": "60天以内",
            "st_ok": "充足",
            "st_none": "未登记",

            # 列名（中国語）
            "col_days": "剩余天数",
            "col_status": "状态",
        }
    }[language]

    COL_DAYS = LABEL["col_days"]
    COL_STATUS = LABEL["col_status"]

    # --- Lark Sheets 設定（st.secrets 推奨） ---
    try:
        LARK_APP_ID = st.secrets["LARK_APP_ID"]
        LARK_APP_SECRET = st.secrets["LARK_APP_SECRET"]
        LARK_SPREADSHEET_TOKEN = st.secrets.get("LARK_SPREADSHEET_TOKEN", "O6VQsoFDOhOPV7t3qSslkoSEg3b")
        LARK_SHEET_ID = st.secrets.get("LARK_SHEET_ID", "91fd41")
    except Exception:
        st.error(LABEL["lark_secret_missing"])
        st.stop()

    # =========================
    # Lark API
    # =========================
    def lark_get_tenant_token(app_id: str, app_secret: str) -> str:
        url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal/"
        r = requests.post(url, json={"app_id": app_id, "app_secret": app_secret}, timeout=30)
        r.raise_for_status()
        j = r.json()
        if j.get("code") != 0:
            raise RuntimeError(f"Lark token error: {j}")
        return j["tenant_access_token"]

    def lark_read_sheet_values(
        tenant_token: str,
        spreadsheet_token: str,
        sheet_id: str,
        rng: str = "A1:G5000"
    ):
        url = (
            "https://open.larksuite.com/open-apis/"
            f"sheets/v2/spreadsheets/{spreadsheet_token}/values_batch_get"
        )
        headers = {"Authorization": f"Bearer {tenant_token}"}
        params = {"ranges": f"{sheet_id}!{rng}"}

        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()

        if j.get("code") != 0:
            raise RuntimeError(j)

        return j["data"]["valueRanges"][0]["values"]

    # =========================
    # パース
    # =========================
    def normalize_jan_cell(x) -> str | None:
        if x is None:
            return None
        s = str(x).strip()
        if not s:
            return None
        s = re.sub(r"\D", "", s)
        return s if s else None

    def parse_date_cell(x):
        """
        Lark Sheets の日付は
        - 'YYYY/MM/DD' 等の文字列
        - Excelシリアル値（例: 46326）
        の両方が来る
        """
        if x is None:
            return None

        if isinstance(x, (int, float)):
            base = datetime.date(1899, 12, 30)
            return (base + datetime.timedelta(days=int(x))).isoformat()

        s = str(x).strip()
        if not s:
            return None

        for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d", "%Y%m%d"):
            try:
                return datetime.datetime.strptime(s, fmt).date().isoformat()
            except ValueError:
                pass

        # ここは内部エラーなので翻訳必須ではないが、表示され得るので一応英語混ぜず日本語のまま
        raise ValueError(f"日付として解釈できません: {s}")

    def min_date_iso(*isos):
        ds = [d for d in isos if d]
        return min(ds) if ds else None

    # =========================
    # Supabase upsert（REST）
    # =========================
    def supabase_truncate_item_expiry():
        url = f"{SUPABASE_URL}/rest/v1/rpc/truncate_item_expiry"
        r = requests.post(url, headers=HEADERS, json={}, timeout=60)
        if r.status_code not in [200, 204]:
            raise RuntimeError(f"Supabase truncate failed: {r.status_code} {r.text}")

    def supabase_upsert_item_expiry(rows: list[dict]) -> int:
        if not rows:
            return 0
        url = f"{SUPABASE_URL}/rest/v1/item_expiry"
        headers = {**HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"}
        r = requests.post(url, headers=headers, json=rows, timeout=60)
        if r.status_code not in [200, 201]:
            raise RuntimeError(f"Supabase upsert failed: {r.status_code} {r.text}")
        data = r.json()
        return len(data) if isinstance(data, list) else len(rows)

    def sync_lark_to_supabase() -> dict:
        # ★ 同期時は Supabase 側を全削除してから upsert
        supabase_truncate_item_expiry()

        tenant = lark_get_tenant_token(LARK_APP_ID, LARK_APP_SECRET)
        values = lark_read_sheet_values(
            tenant_token=tenant,
            spreadsheet_token=LARK_SPREADSHEET_TOKEN,
            sheet_id=LARK_SHEET_ID,
            rng="A1:G5000"
        )

        if not values or len(values) < 2:
            return {"upserted": 0, "errors": []}

        upserts = []
        errors = []

        for row_idx, row in enumerate(values[1:], start=2):
            try:
                a = row[0] if len(row) > 0 else None
                b = row[1] if len(row) > 1 else None
                c = row[2] if len(row) > 2 else None
                d = row[3] if len(row) > 3 else None
                e = row[4] if len(row) > 4 else None
                f = row[5] if len(row) > 5 else None
                g = row[6] if len(row) > 6 else None

                jan = normalize_jan_cell(a)
                if not jan:
                    continue

                expiry_1 = parse_date_cell(c)
                expiry_2 = parse_date_cell(d)
                expiry_3 = parse_date_cell(e)
                expiry_4 = parse_date_cell(f)
                expiry_5 = parse_date_cell(g)
                expiry_min = min_date_iso(expiry_1, expiry_2, expiry_3, expiry_4, expiry_5)

                upserts.append({
                    "jan": jan,
                    "name": str(b).strip() if b is not None else None,
                    "expiry_1": expiry_1,
                    "expiry_2": expiry_2,
                    "expiry_3": expiry_3,
                    "expiry_4": expiry_4,
                    "expiry_5": expiry_5,
                    "expiry_min": expiry_min,
                    "updated_at": datetime.datetime.utcnow().isoformat()
                })

            except Exception as ex:
                errors.append({"row": row_idx, "raw": row, "error": str(ex)})

        upserted_total = 0
        for i in range(0, len(upserts), 500):
            upserted_total += supabase_upsert_item_expiry(upserts[i:i+500])

        return {"upserted": upserted_total, "errors": errors}

    # =========================
    # UI: 同期
    # =========================
    st.markdown("### " + LABEL["sync"])
    st.caption(LABEL["sync_note"])
    if st.button(LABEL["sync"], key="expiry_sync_btn"):
        with st.spinner(LABEL["syncing"]):
            try:
                result = sync_lark_to_supabase()
                st.success(f"{LABEL['synced']}: {result['upserted']} 件")
                if result["errors"]:
                    st.warning(f"{LABEL['err']}: {len(result['errors'])} 件")
                    df_err = pd.DataFrame(result["errors"]).copy()
                    if "raw" in df_err.columns:
                        df_err["raw"] = df_err["raw"].apply(
                            lambda x: " | ".join(map(str, x)) if isinstance(x, (list, tuple)) else str(x)
                        )
                    st.dataframe(df_err, use_container_width=True)

            except Exception as e:
                st.error(f"{LABEL['sync_failed']}: {e}")

    st.markdown("---")

    # =========================
    # 一覧取得（Supabase → pandas）
    # =========================
    @st.cache_data(ttl=60)
    def fetch_item_expiry():
        url = f"{SUPABASE_URL}/rest/v1/item_expiry?select=*"
        r = requests.get(url, headers=HEADERS, timeout=60)
        if r.status_code != 200:
            st.error(f"{LABEL['fetch_failed_item_expiry']}: {r.status_code} / {r.text}")
            return pd.DataFrame()
        return pd.DataFrame(r.json())

    def chunk_list(lst, size=500):
        for i in range(0, len(lst), size):
            yield lst[i:i+size]

    @st.cache_data(ttl=60)
    def fetch_warehouse_stock_by_jans(jans: list[str]) -> pd.DataFrame:
        """
        item_expiry側のJAN一覧に対して、warehouse_stockから jan, stock_available を必要分だけ取得
        """
        if not jans:
            return pd.DataFrame(columns=["jan", "stock_available"])

        jans = [str(x).strip() for x in jans if pd.notna(x) and str(x).strip() != ""]
        jans = list(dict.fromkeys(jans))  # 順序保持で重複排除

        all_rows = []

        for chunk in chunk_list(jans, 500):
            joined = ",".join(chunk)
            url = (
                f"{SUPABASE_URL}/rest/v1/warehouse_stock"
                f"?select=jan,stock_available&jan=in.({joined})"
            )
            r = requests.get(url, headers=HEADERS, timeout=60)
            if r.status_code != 200:
                st.error(f"{LABEL['fetch_failed_warehouse']}: {r.status_code} / {r.text}")
                continue

            rows = r.json()
            if rows:
                all_rows.extend(rows)

        df_stock = pd.DataFrame(all_rows)
        if df_stock.empty:
            return pd.DataFrame(columns=["jan", "stock_available"])

        df_stock["jan"] = df_stock["jan"].astype(str).str.strip()
        df_stock["stock_available"] = pd.to_numeric(df_stock["stock_available"], errors="coerce").fillna(0).astype(int)

        # JAN重複があり得るなら安全に集約
        df_stock = df_stock.groupby("jan", as_index=False)["stock_available"].sum()
        return df_stock

    # =========================
    # 取得 → JAN一覧から在庫取得 → merge
    # =========================
    df = fetch_item_expiry()

    if df.empty:
        st.info(LABEL["no_data"])
        st.stop()

    df["jan"] = df["jan"].astype(str).str.strip()
    jans = df["jan"].dropna().astype(str).str.strip().unique().tolist()
    df_stock = fetch_warehouse_stock_by_jans(jans)

    # left join：item_expiry を主にして在庫を付与
    df = df.merge(df_stock, on="jan", how="left")

    # 在庫が無い（未取得/NULL）場合は 0 扱いに
    df["stock_available"] = pd.to_numeric(df.get("stock_available"), errors="coerce").fillna(0).astype(int)

    # =========================
    # 表示用加工
    # =========================
    df["jan"] = df["jan"].astype(str).str.strip()
    df["name"] = df["name"].astype(str).fillna("").str.strip()

    expiry_cols = ["expiry_1", "expiry_2", "expiry_3", "expiry_4", "expiry_5"]
    for c in expiry_cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.date

    if set(expiry_cols).issubset(df.columns):
        df["expiry_min"] = pd.to_datetime(df[expiry_cols].stack(), errors="coerce").groupby(level=0).min().dt.date
    else:
        df["expiry_min"] = None

    # updated_at（表示用に now を入れる）
    df["updated_at"] = datetime.datetime.now(ZoneInfo("Asia/Tokyo")).isoformat()

    # NaT/NaN を None に
    df = df.where(pd.notnull(df), None)

    df["expiry_min_dt"] = pd.to_datetime(df.get("expiry_min"), errors="coerce")
    today = pd.Timestamp.today().normalize()

    # 残り日数（言語別列名）
    df[COL_DAYS] = ((df["expiry_min_dt"] - today).dt.days).astype("Int64")

    def status_label(days):
        if pd.isna(days):
            return LABEL["st_none"]
        if days < 0:
            return LABEL["st_expired"]
        if days <= 60:
            return LABEL["st_within"]
        return LABEL["st_ok"]

    df[COL_STATUS] = df[COL_DAYS].apply(status_label)

    # =========================
    # フィルタ
    # =========================
    st.markdown("### " + LABEL["filters"])
    c1, c2, c3, c4 = st.columns([1.2, 1.0, 1.0, 0.8])

    with c1:
        kw = st.text_input(LABEL["keyword"], value="", key="expiry_kw")

    with c2:
        statuses = [LABEL["st_expired"], LABEL["st_within"], LABEL["st_ok"], LABEL["st_none"]]
        default_status = [LABEL["st_expired"], LABEL["st_within"]]
        sel_status = st.multiselect(LABEL["status"], statuses, default=default_status, key="expiry_status")

    with c3:
        only_with = st.checkbox(LABEL["only_with_expiry"], value=False, key="expiry_only_with")
        only_no = st.checkbox(LABEL["only_no_expiry"], value=False, key="expiry_only_no")
        only_in_stock = st.checkbox(LABEL["only_in_stock"], value=True, key="expiry_only_in_stock")
        only_zero_stock = st.checkbox(LABEL["only_zero_stock"], value=False, key="expiry_only_zero_stock")

    with c4:
        limit = st.number_input(LABEL["limit"], min_value=50, max_value=5000, value=500, step=50, key="expiry_limit")

    df_view = df.copy()

    if kw:
        kw_s = kw.strip()
        cond = df_view["jan"].astype(str).str.contains(kw_s, na=False)
        if "name" in df_view.columns:
            cond = cond | df_view["name"].astype(str).str.contains(kw_s, na=False)
        df_view = df_view[cond]

    if sel_status:
        df_view = df_view[df_view[COL_STATUS].isin(sel_status)]

    if only_with and not only_no:
        df_view = df_view[df_view["expiry_min_dt"].notna()]
    if only_no and not only_with:
        df_view = df_view[df_view["expiry_min_dt"].isna()]

    if only_zero_stock:
        df_view = df_view[df_view["stock_available"] <= 0]

    # 在庫フィルタ（デフォルト：在庫0を非表示）
    if "stock_available" in df_view.columns:
        if st.session_state.get("expiry_only_in_stock", True):
            df_view = df_view[df_view["stock_available"] > 0]

    # =========================
    # 表示
    # =========================
    df_view = df_view.sort_values(by=["expiry_min_dt", "jan"], ascending=[True, True])

    cols = ["jan", "name", "stock_available", "expiry_min", COL_DAYS, COL_STATUS,
            "expiry_1", "expiry_2", "expiry_3", "expiry_4", "expiry_5"]
    cols = [c for c in cols if c in df_view.columns]

    row_count = len(df_view)
    h_left, h_right = st.columns([1, 0.15])
    h_left.subheader(f"{LABEL['expiry']} / {LABEL['days']}")
    h_right.markdown(
        f"<h4 style='text-align:right; margin-top: 0.6em;'>{row_count:,}件</h4>",
        unsafe_allow_html=True
    )

    def highlight_status(row):
        if row[COL_STATUS] == LABEL["st_expired"]:
            return ["background-color: #ffcccc"] * len(row)
        if row[COL_STATUS] == LABEL["st_within"]:
            return ["background-color: #ffe599"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_view.head(int(limit))[cols].style.apply(highlight_status, axis=1),
        use_container_width=True
    )

    # CSV ダウンロード
    csv = df_view[cols].to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        LABEL["download"],
        data=csv,
        file_name="item_expiry_filtered.csv",
        mime="text/csv",
        key="expiry_download"
    )
