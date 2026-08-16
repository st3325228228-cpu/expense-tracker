from __future__ import annotations

import calendar
import io
import zipfile
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------------------------
# 基本設定
# ---------------------------------------------------------------------------
TRANSACTIONS_CSV = "transactions"  # 相容既有函式命名；實際儲存在 Google Sheets
BUDGETS_CSV = "budgets"
CATEGORIES_CSV = "categories"

TRANSACTION_FIELDS = [
    "id", "date", "transaction_type", "category", "item",
    "amount", "payment_method", "note", "created_at",
]
BUDGET_FIELDS = ["month", "amount"]
CATEGORY_FIELDS = ["type", "category"]

SHEET_SCHEMAS = {
    TRANSACTIONS_CSV: TRANSACTION_FIELDS,
    BUDGETS_CSV: BUDGET_FIELDS,
    CATEGORIES_CSV: CATEGORY_FIELDS,
}

DEFAULT_EXPENSE_CATEGORIES = ["飲食", "交通", "娛樂", "購物", "居家", "醫療", "教育", "其他"]
DEFAULT_INCOME_CATEGORIES = ["薪資", "獎金", "投資", "兼職", "其他"]
PAYMENT_METHODS = ["現金", "信用卡", "電子支付", "轉帳", "其他"]

st.set_page_config(page_title="每月支出追蹤器", page_icon="💰", layout="wide")

st.markdown("""
<style>
div[data-testid="stMetric"] {
    background: #ffffff10;
    border: 1px solid #ffffff20;
    border-radius: 12px;
    padding: 14px 16px;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Google Sheets 基礎讀寫
# ---------------------------------------------------------------------------
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@st.cache_resource
def get_spreadsheet():
    """以 Streamlit Secrets 中的 Service Account 連線到指定 Google Sheet。"""
    try:
        service_account_info = dict(st.secrets["gcp_service_account"])
        spreadsheet_id = str(st.secrets["google_sheets"]["spreadsheet_id"]).strip()
    except Exception as exc:
        st.error(
            "尚未設定 Google Sheets 憑證。請在 Streamlit Community Cloud 的 Secrets "
            "加入 [gcp_service_account] 與 [google_sheets] 設定。"
        )
        st.code(
            '[google_sheets]\nspreadsheet_id = "你的 Google Sheet ID"\n\n'
            '[gcp_service_account]\ntype = "service_account"\n...'
        )
        st.stop()
        raise RuntimeError("Missing Streamlit secrets") from exc

    if not spreadsheet_id:
        st.error("google_sheets.spreadsheet_id 不可空白。")
        st.stop()

    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=GOOGLE_SCOPES,
    )
    client = gspread.authorize(credentials)
    try:
        return client.open_by_key(spreadsheet_id)
    except Exception as exc:
        st.error(
            "無法開啟 Google Sheet。請確認 Spreadsheet ID 正確，且已把試算表分享給 Service Account 的 client_email（編輯者）。"
        )
        st.exception(exc)
        st.stop()
        raise


@st.cache_resource
def get_worksheet(sheet_name: str, fieldnames: list[str]):
    book = get_spreadsheet()
    try:
        ws = book.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(
            title=sheet_name,
            rows=1000,
            cols=max(10, len(fieldnames)),
        )

    values = ws.get_all_values()
    if not values:
        ws.update(range_name="A1", values=[fieldnames])
    else:
        header = values[0][:len(fieldnames)]
        if header != fieldnames:
            raise RuntimeError(
                f"工作表 {sheet_name!r} 欄位不符。期待 {fieldnames}，目前為 {header}。"
            )
    return ws


def read_csv(sheet_name: str) -> list[dict]:
    """保留既有函式名稱，實際從 Google Sheets 讀取。"""
    fieldnames = SHEET_SCHEMAS[sheet_name]
    ws = get_worksheet(sheet_name, fieldnames)
    values = ws.get_all_values()
    if len(values) <= 1:
        return []

    rows: list[dict] = []
    for values_row in values[1:]:
        padded = values_row + [""] * (len(fieldnames) - len(values_row))
        if not any(str(v).strip() for v in padded[:len(fieldnames)]):
            continue
        rows.append(dict(zip(fieldnames, padded[:len(fieldnames)])))
    return rows


def write_csv(sheet_name: str, fieldnames: list[str], rows: list[dict]) -> None:
    """保留既有函式名稱，實際整批寫回 Google Sheets。"""
    ws = get_worksheet(sheet_name, fieldnames)
    matrix = [fieldnames]
    matrix.extend([[row.get(k, "") for k in fieldnames] for row in rows])
    ws.clear()
    ws.update(range_name="A1", values=matrix, value_input_option="USER_ENTERED")


def ensure_csv_files() -> None:
    """初始化三個工作表；名稱保留以減少既有程式改動。"""
    get_worksheet(TRANSACTIONS_CSV, TRANSACTION_FIELDS)
    get_worksheet(BUDGETS_CSV, BUDGET_FIELDS)
    category_ws = get_worksheet(CATEGORIES_CSV, CATEGORY_FIELDS)
    category_rows = read_csv(CATEGORIES_CSV)
    if not category_rows:
        seed = (
            [{"type": "支出", "category": c} for c in DEFAULT_EXPENSE_CATEGORIES]
            + [{"type": "收入", "category": c} for c in DEFAULT_INCOME_CATEGORIES]
        )
        write_csv(CATEGORIES_CSV, CATEGORY_FIELDS, seed)


def shift_month(month_str: str, delta: int) -> str:
    year, month = map(int, month_str.split("-"))
    total = year * 12 + (month - 1) + delta
    new_year, new_month = divmod(total, 12)
    return f"{new_year:04d}-{new_month + 1:02d}"


# ---------------------------------------------------------------------------
# 交易資料
# ---------------------------------------------------------------------------
def load_transactions_df() -> pd.DataFrame:
    rows = read_csv(TRANSACTIONS_CSV)
    if not rows:
        return pd.DataFrame(columns=TRANSACTION_FIELDS)
    df = pd.DataFrame(rows)
    df["id"] = df["id"].apply(lambda x: int(as_float(x, 0)))
    df["amount"] = df["amount"].apply(as_float)
    return df


def get_transactions(month: str) -> pd.DataFrame:
    df = load_transactions_df()
    if df.empty:
        return df
    filtered = df[df["date"].str[:7] == month].copy()
    return filtered.sort_values(by=["date", "id"], ascending=[False, False])


def create_transaction(payload: dict) -> int:
    rows = read_csv(TRANSACTIONS_CSV)
    next_id = max((int(as_float(r.get("id"), 0)) for r in rows), default=0) + 1
    rows.append({
        "id": next_id,
        "date": payload["date"],
        "transaction_type": payload["transaction_type"],
        "category": payload["category"],
        "item": payload["item"],
        "amount": payload["amount"],
        "payment_method": payload.get("payment_method", ""),
        "note": payload.get("note", ""),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    write_csv(TRANSACTIONS_CSV, TRANSACTION_FIELDS, rows)
    return next_id


def sync_month_transactions(month: str, edited_df: pd.DataFrame) -> tuple[bool, str]:
    """把 data_editor 編輯後的整月資料寫回 Google Sheets（其他月份維持不動）。"""
    all_rows = read_csv(TRANSACTIONS_CSV)
    other_rows = [r for r in all_rows if r.get("date", "")[:7] != month]
    existing_by_id = {int(as_float(r.get("id"), 0)): r for r in all_rows}
    next_id = max((int(as_float(r.get("id"), 0)) for r in all_rows), default=0) + 1

    new_month_rows = []
    for _, r in edited_df.iterrows():
        t_date = r.get("date")
        t_type = str(r.get("transaction_type") or "").strip()
        category = str(r.get("category") or "").strip()
        item = str(r.get("item") or "").strip()
        amount = as_float(r.get("amount"), -1)
        payment_method = str(r.get("payment_method") or "").strip()
        note = str(r.get("note") or "").strip()

        if t_date is None or pd.isna(t_date):
            continue  # 空白列略過
        date_str = t_date.strftime("%Y-%m-%d") if hasattr(t_date, "strftime") else str(t_date)

        if t_type not in {"收入", "支出"}:
            return False, f"第 {date_str} 筆交易類型必須為「收入」或「支出」"
        if not category:
            return False, f"第 {date_str} 筆分類不可空白"
        if not item:
            return False, f"第 {date_str} 筆項目不可空白"
        if amount <= 0:
            return False, f"第 {date_str} 筆金額必須大於 0"

        raw_id = r.get("id")
        rid = int(as_float(raw_id, 0))
        if rid <= 0 or rid not in existing_by_id:
            rid = next_id
            next_id += 1
            created_at = datetime.now().isoformat(timespec="seconds")
        else:
            created_at = existing_by_id[rid].get("created_at", datetime.now().isoformat(timespec="seconds"))

        new_month_rows.append({
            "id": rid, "date": date_str, "transaction_type": t_type,
            "category": category, "item": item, "amount": amount,
            "payment_method": payment_method, "note": note, "created_at": created_at,
        })

    write_csv(TRANSACTIONS_CSV, TRANSACTION_FIELDS, other_rows + new_month_rows)
    return True, "已儲存變更"


def import_transactions(df: pd.DataFrame) -> tuple[int, list[str]]:
    required = {"date", "transaction_type", "category", "item", "amount"}
    missing = required - set(df.columns)
    if missing:
        return 0, [f"缺少欄位：{', '.join(missing)}"]

    success, errors = 0, []
    for idx, row in df.iterrows():
        try:
            date_str = str(row["date"]).strip()
            datetime.strptime(date_str, "%Y-%m-%d")
            t_type = str(row["transaction_type"]).strip()
            if t_type not in {"收入", "支出"}:
                raise ValueError("類型須為收入或支出")
            amount = as_float(row["amount"], -1)
            if amount <= 0:
                raise ValueError("金額須大於 0")
            create_transaction({
                "date": date_str, "transaction_type": t_type,
                "category": str(row["category"]).strip(),
                "item": str(row["item"]).strip(), "amount": amount,
                "payment_method": str(row.get("payment_method", "")).strip(),
                "note": str(row.get("note", "")).strip(),
            })
            success += 1
        except Exception as exc:
            errors.append(f"第 {idx + 2} 列：{exc}")
    return success, errors


# ---------------------------------------------------------------------------
# 預算 & 分類
# ---------------------------------------------------------------------------
def get_budget(month: str) -> float:
    for row in read_csv(BUDGETS_CSV):
        if row.get("month") == month:
            return as_float(row.get("amount"))
    return 0.0


def save_budget(month: str, amount: float) -> None:
    rows = read_csv(BUDGETS_CSV)
    found = False
    for row in rows:
        if row.get("month") == month:
            row["amount"] = amount
            found = True
            break
    if not found:
        rows.append({"month": month, "amount": amount})
    rows.sort(key=lambda r: r.get("month", ""))
    write_csv(BUDGETS_CSV, BUDGET_FIELDS, rows)


def get_categories(t_type: str) -> list[str]:
    rows = read_csv(CATEGORIES_CSV)
    names = sorted({r["category"] for r in rows if r.get("type") == t_type and r.get("category")})
    return names or (DEFAULT_EXPENSE_CATEGORIES if t_type == "支出" else DEFAULT_INCOME_CATEGORIES)


def add_category(t_type: str, name: str) -> bool:
    name = name.strip()
    if not name:
        return False
    rows = read_csv(CATEGORIES_CSV)
    if any(r.get("type") == t_type and r.get("category") == name for r in rows):
        return False
    rows.append({"type": t_type, "category": name})
    write_csv(CATEGORIES_CSV, CATEGORY_FIELDS, rows)
    return True


def remove_category(t_type: str, name: str) -> None:
    rows = read_csv(CATEGORIES_CSV)
    rows = [r for r in rows if not (r.get("type") == t_type and r.get("category") == name)]
    write_csv(CATEGORIES_CSV, CATEGORY_FIELDS, rows)


ensure_csv_files()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
if "selected_month" not in st.session_state:
    st.session_state.selected_month = date.today().strftime("%Y-%m")

st.sidebar.title("💰 每月支出追蹤器")
st.sidebar.markdown("---")

nav_prev, nav_label, nav_next = st.sidebar.columns([1, 2, 1])
if nav_prev.button("◀", use_container_width=True):
    st.session_state.selected_month = shift_month(st.session_state.selected_month, -1)
nav_label.markdown(
    f"<h4 style='text-align:center;margin-top:6px;'>{st.session_state.selected_month}</h4>",
    unsafe_allow_html=True,
)
if nav_next.button("▶", use_container_width=True):
    st.session_state.selected_month = shift_month(st.session_state.selected_month, 1)

selected_month = st.session_state.selected_month

st.sidebar.markdown("---")
st.sidebar.subheader("📌 月度預算")
current_budget = get_budget(selected_month)
new_budget = st.sidebar.number_input(
    "設定本月預算", min_value=0.0, value=float(current_budget), step=100.0, format="%.2f"
)
if st.sidebar.button("💾 儲存預算", use_container_width=True):
    save_budget(selected_month, new_budget)
    st.sidebar.success("預算已儲存！")
    st.rerun()

st.sidebar.markdown("---")
with st.sidebar.expander("🏷️ 分類管理"):
    manage_type = st.radio("類型", ["支出", "收入"], horizontal=True, key="manage_cat_type")
    existing_cats = get_categories(manage_type)
    st.caption("目前分類：" + "、".join(existing_cats))

    new_cat = st.text_input("新增分類名稱", key="new_cat_input")
    if st.button("➕ 新增分類", use_container_width=True):
        if add_category(manage_type, new_cat):
            st.success(f"已新增分類「{new_cat}」")
            st.rerun()
        else:
            st.warning("分類重複或名稱空白")

    del_cat = st.selectbox("刪除分類", [""] + existing_cats, key="del_cat_select")
    if st.button("🗑️ 刪除選定分類", use_container_width=True, disabled=not del_cat):
        remove_category(manage_type, del_cat)
        st.success(f"已刪除分類「{del_cat}」")
        st.rerun()

st.sidebar.markdown("---")
with st.sidebar.expander("📥 匯入資料"):
    uploaded = st.file_uploader("上傳 CSV（需含 date, transaction_type, category, item, amount）", type=["csv"])
    if uploaded is not None and st.button("開始匯入", use_container_width=True):
        try:
            import_df = pd.read_csv(uploaded, dtype=str)
            ok, errs = import_transactions(import_df)
            st.success(f"成功匯入 {ok} 筆")
            if errs:
                st.error("部分失敗：\n" + "\n".join(errs[:10]))
            st.rerun()
        except Exception as exc:
            st.error(f"讀取失敗：{exc}")

with st.sidebar.expander("📤 匯出 / 備份"):
    export_df = get_transactions(selected_month)
    if not export_df.empty:
        csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("下載本月 CSV", data=csv_bytes,
                            file_name=f"transactions_{selected_month}.csv",
                            mime="text/csv", use_container_width=True)

        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            export_df.to_excel(writer, sheet_name="交易明細", index=False)
        st.download_button("下載本月 Excel", data=excel_buffer.getvalue(),
                            file_name=f"transactions_{selected_month}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True)
    else:
        st.caption("本月尚無交易資料")

    if st.button("💾 產生完整資料備份 (ZIP)", use_container_width=True):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for sheet_name, fields in SHEET_SCHEMAS.items():
                rows = read_csv(sheet_name)
                backup_df = pd.DataFrame(rows, columns=fields)
                zf.writestr(
                    f"{sheet_name}.csv",
                    backup_df.to_csv(index=False).encode("utf-8-sig"),
                )
        st.download_button("下載備份 ZIP", data=zip_buffer.getvalue(),
                            file_name=f"backup_{datetime.now():%Y%m%d_%H%M%S}.zip",
                            mime="application/zip", use_container_width=True)

# ---------------------------------------------------------------------------
# 主畫面資料準備
# ---------------------------------------------------------------------------
month_df = get_transactions(selected_month)
prev_month = shift_month(selected_month, -1)
prev_df = get_transactions(prev_month)


def sum_by_type(df: pd.DataFrame, t: str) -> float:
    return df.loc[df["transaction_type"] == t, "amount"].sum() if not df.empty else 0.0


income = sum_by_type(month_df, "收入")
expense = sum_by_type(month_df, "支出")
balance = income - expense
prev_income = sum_by_type(prev_df, "收入")
prev_expense = sum_by_type(prev_df, "支出")
prev_balance = prev_income - prev_expense

budget = get_budget(selected_month)
remaining_budget = budget - expense
budget_usage = (expense / budget * 100) if budget > 0 else 0

st.title(f"📊 {selected_month} 支出總覽")

tab_overview, tab_manage, tab_charts, tab_trend = st.tabs(
    ["📈 總覽", "📋 交易資料", "🥧 圖表分析", "📅 歷史趨勢"]
)

# ---- Tab 1：總覽 ----
with tab_overview:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💵 總收入", f"${income:,.0f}", delta=f"{income - prev_income:,.0f}")
    col2.metric("💸 總支出", f"${expense:,.0f}", delta=f"{expense - prev_expense:,.0f}", delta_color="inverse")
    col3.metric("📈 結餘", f"${balance:,.0f}", delta=f"{balance - prev_balance:,.0f}")
    col4.metric("🎯 預算剩餘", f"${remaining_budget:,.0f}")

    if budget > 0:
        st.markdown("#### 預算使用進度")
        st.progress(min(budget_usage / 100, 1.0))

        # 預算節奏預測：跟「理論上該花多少」比較
        year, mon = map(int, selected_month.split("-"))
        days_in_month = calendar.monthrange(year, mon)[1]
        today = date.today()
        month_start = date(year, mon, 1)
        month_end = date(year, mon, days_in_month)
        if today < month_start:
            days_elapsed = 0
        elif today > month_end:
            days_elapsed = days_in_month
        else:
            days_elapsed = today.day
        expected_ratio = days_elapsed / days_in_month
        expected_spend = budget * expected_ratio

        pace_col1, pace_col2 = st.columns(2)
        pace_col1.metric("理論應花費（依天數比例）", f"${expected_spend:,.0f}")
        pace_col2.metric("實際已花費", f"${expense:,.0f}", delta=f"{expense - expected_spend:,.0f}", delta_color="inverse")

        if budget_usage >= 100:
            st.error(f"⚠️ 已超支！目前使用 {budget_usage:.1f}% 的預算")
        elif expense > expected_spend * 1.15:
            st.warning("⚠️ 花錢速度超前進度，照這個節奏可能會超支")
        elif budget_usage >= 80:
            st.warning(f"⚠️ 預算即將用完，已使用 {budget_usage:.1f}%")
        else:
            st.info(f"目前已使用 {budget_usage:.1f}% 的預算，節奏正常")
    else:
        st.caption("尚未設定本月預算，請於左側側邊欄設定。")

    st.markdown("---")
    top_col, recent_col = st.columns(2)

    with top_col:
        st.markdown("#### 🏆 本月消費排行榜 Top 5")
        expense_only = month_df[month_df["transaction_type"] == "支出"]
        if expense_only.empty:
            st.caption("本月尚無支出資料")
        else:
            top5 = (
                expense_only.groupby("item")["amount"].sum()
                .sort_values(ascending=False).head(5).reset_index()
            )
            top5.columns = ["項目", "金額"]
            st.dataframe(top5.style.format({"金額": "${:,.0f}"}), use_container_width=True, hide_index=True)

    with recent_col:
        st.markdown("#### 🕒 最近 5 筆交易")
        if month_df.empty:
            st.caption("本月尚無交易紀錄")
        else:
            preview = month_df.head(5)[["date", "transaction_type", "category", "item", "amount"]]
            preview.columns = ["日期", "類型", "分類", "項目", "金額"]
            st.dataframe(preview.style.format({"金額": "${:,.0f}"}), use_container_width=True, hide_index=True)

# ---- Tab 2：交易資料（新增 / 篩選 / 行內編輯）----
with tab_manage:
    st.subheader("➕ 快速新增")
    with st.form("add_transaction_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            t_date = st.date_input("日期", value=date.today())
            t_type = st.selectbox("交易類型", ["支出", "收入"])
        with c2:
            categories = get_categories(t_type)
            t_category = st.selectbox("分類", categories)
            t_payment = st.selectbox("付款方式", PAYMENT_METHODS)
        with c3:
            t_item = st.text_input("項目名稱")
            t_amount = st.number_input("金額", min_value=0.0, step=10.0, format="%.2f")

        t_note = st.text_area("備註", height=68)
        submitted = st.form_submit_button("✅ 新增交易", use_container_width=True)

        if submitted:
            errors = []
            if not t_item.strip():
                errors.append("項目名稱不可空白")
            if t_amount <= 0:
                errors.append("金額必須大於 0")
            if errors:
                for e in errors:
                    st.error(e)
            else:
                create_transaction({
                    "date": t_date.strftime("%Y-%m-%d"), "transaction_type": t_type,
                    "category": t_category, "item": t_item.strip(), "amount": t_amount,
                    "payment_method": t_payment, "note": t_note.strip(),
                })
                st.success("交易新增成功！")
                st.rerun()

    st.markdown("---")
    st.subheader("🔍 篩選查詢")
    f1, f2, f3, f4 = st.columns(4)
    filter_type = f1.selectbox("類型", ["全部", "收入", "支出"])
    all_cats = sorted(set(month_df["category"]).union() if not month_df.empty else [])
    filter_cat = f2.selectbox("分類", ["全部"] + all_cats)
    filter_pay = f3.selectbox("付款方式", ["全部"] + PAYMENT_METHODS)
    keyword = f4.text_input("關鍵字（項目/備註）")

    view_df = month_df.copy()
    if filter_type != "全部" and not view_df.empty:
        view_df = view_df[view_df["transaction_type"] == filter_type]
    if filter_cat != "全部" and not view_df.empty:
        view_df = view_df[view_df["category"] == filter_cat]
    if filter_pay != "全部" and not view_df.empty:
        view_df = view_df[view_df["payment_method"] == filter_pay]
    if keyword and not view_df.empty:
        mask = view_df["item"].str.contains(keyword, case=False, na=False) | \
               view_df["note"].str.contains(keyword, case=False, na=False)
        view_df = view_df[mask]

    if view_df.empty:
        st.info("查無符合條件的交易。")
    else:
        show_cols = view_df[["date", "transaction_type", "category", "item", "amount", "payment_method", "note"]]
        show_cols.columns = ["日期", "類型", "分類", "項目", "金額", "付款方式", "備註"]
        st.dataframe(show_cols.style.format({"金額": "${:,.0f}"}), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📝 批次編輯（可直接改格子、加列、刪列）")
    st.caption("編輯完成後記得按下方「儲存變更」，變更才會寫回 Google Sheets。")

    editor_source = month_df.copy()
    if editor_source.empty:
        editor_source = pd.DataFrame(columns=TRANSACTION_FIELDS)
    else:
        editor_source["date"] = pd.to_datetime(editor_source["date"]).dt.date

    edited = st.data_editor(
        editor_source[["id", "date", "transaction_type", "category", "item", "amount", "payment_method", "note"]],
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "date": st.column_config.DateColumn("日期", format="YYYY-MM-DD"),
            "transaction_type": st.column_config.SelectboxColumn("類型", options=["收入", "支出"]),
            "category": st.column_config.TextColumn("分類"),
            "item": st.column_config.TextColumn("項目"),
            "amount": st.column_config.NumberColumn("金額", min_value=0.0, format="%.2f"),
            "payment_method": st.column_config.TextColumn("付款方式"),
            "note": st.column_config.TextColumn("備註"),
        },
        key="transaction_editor",
    )

    if st.button("💾 儲存變更", type="primary", use_container_width=True):
        ok, msg = sync_month_transactions(selected_month, edited)
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

# ---- Tab 3：圖表分析 ----
with tab_charts:
    expense_df = month_df[month_df["transaction_type"] == "支出"] if not month_df.empty else pd.DataFrame()

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.markdown("##### 分類佔比（支出）")
        if not expense_df.empty:
            category_summary = expense_df.groupby("category")["amount"].sum().reset_index()
            category_summary.columns = ["分類", "金額"]
            fig_pie = px.pie(category_summary, names="分類", values="金額", hole=0.4)
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.caption("本月尚無支出資料")

    with chart_col2:
        st.markdown("##### 每日支出趨勢")
        if not expense_df.empty:
            daily_summary = expense_df.groupby("date")["amount"].sum().reset_index()
            daily_summary.columns = ["日期", "金額"]
            daily_summary = daily_summary.sort_values("日期")
            fig_line = px.line(daily_summary, x="日期", y="金額", markers=True)
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.caption("本月尚無支出資料")

    st.markdown("##### 🏆 消費項目排行（前 10）")
    if not expense_df.empty:
        top10 = expense_df.groupby("item")["amount"].sum().sort_values(ascending=False).head(10).reset_index()
        top10.columns = ["項目", "金額"]
        fig_bar_items = px.bar(top10, x="金額", y="項目", orientation="h")
        fig_bar_items.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig_bar_items, use_container_width=True)
    else:
        st.caption("本月尚無支出資料")

# ---- Tab 4：歷史趨勢（近 6 個月）----
with tab_trend:
    st.markdown("##### 近 6 個月收支比較")
    history_months = [shift_month(selected_month, -i) for i in range(5, -1, -1)]
    history_rows = []
    category_history_rows = []

    for m in history_months:
        m_df = get_transactions(m)
        m_income = sum_by_type(m_df, "收入")
        m_expense = sum_by_type(m_df, "支出")
        history_rows.append({"月份": m, "收入": m_income, "支出": m_expense})

        if not m_df.empty:
            m_expense_only = m_df[m_df["transaction_type"] == "支出"]
            if not m_expense_only.empty:
                cat_sum = m_expense_only.groupby("category")["amount"].sum()
                for cat, amt in cat_sum.items():
                    category_history_rows.append({"月份": m, "分類": cat, "金額": amt})

    history_df = pd.DataFrame(history_rows)
    melted = history_df.melt(id_vars="月份", value_vars=["收入", "支出"], var_name="類型", value_name="金額")
    fig_bar = px.bar(
        melted, x="月份", y="金額", color="類型", barmode="group",
        color_discrete_map={"收入": "#2ecc71", "支出": "#e74c3c"},
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    st.dataframe(
        history_df.style.format({"收入": "${:,.0f}", "支出": "${:,.0f}"}),
        use_container_width=True, hide_index=True,
    )

    st.markdown("---")
    st.markdown("##### 🌐 分類支出趨勢（近 6 個月）")
    if category_history_rows:
        cat_history_df = pd.DataFrame(category_history_rows)
        fig_area = px.area(
            cat_history_df, x="月份", y="金額", color="分類",
            groupnorm=None,
        )
        st.plotly_chart(fig_area, use_container_width=True)
    else:
        st.caption("近 6 個月尚無支出資料可供分析")

