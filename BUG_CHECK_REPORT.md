# streamlit_app.py / PWA 檢查報告

## 原始檔案檢查

- 原始 `streamlit_app.py` 共 630 行，並沒有真的截斷在 `days_in_month`。
- 已以 `python -m py_compile` 檢查原始檔，Python 語法可通過。
- 原始 `days_in_month = calendar.monthrange(year, mon)[1]` 語法正確。

## 已修正：未來月份的預算節奏

原版只判斷「是不是本月」：

```python
days_elapsed = today.day if (today.year, today.month) == (year, mon) else days_in_month
```

因此選擇未來月份時，也會被當成「整月已過完」。新版改為：

- 未來月份：`days_elapsed = 0`
- 本月：`days_elapsed = today.day`
- 過去月份：`days_elapsed = days_in_month`

## 已改：CSV 儲存 -> Google Sheets

原版資料寫在：

- `data/transactions.csv`
- `data/budgets.csv`
- `data/categories.csv`

新版改成同名 Google Sheets worksheets：

- `transactions`
- `budgets`
- `categories`

保留既有新增、批次編輯、預算、分類、CSV / Excel 匯出與 ZIP 完整備份功能。

## 已改：PWA iframe

新版 `index.html`：

- 增加單一 `DEFAULT_APP_URL` 設定點。
- iframe 載入時自動加 `?embed=true`。
- 「另開原站」仍使用原始 Streamlit URL。
- 不為 iframe 關閉 CORS / XSRF 防護。

## 驗證

- 修改後 `streamlit_app.py` 已通過 Python 語法編譯。
- `manifest.json` 已通過 JSON parser。
- `index.html` 的 JavaScript 已用 Node `--check` 通過語法檢查。
- 6 個 PWA icons 已重新產生。
- 列印版部署 Checklist PDF 已實際渲染成 4 頁 PNG 檢查，未發現文字裁切、重疊或破圖。

## 尚需你提供

目前沒有這個 App 的實際 `https://xxx.streamlit.app` URL，因此 `index.html` 保留：

```javascript
const DEFAULT_APP_URL = "YOUR_STREAMLIT_URL";
```

取得 Streamlit URL 後只要替換這一行。
