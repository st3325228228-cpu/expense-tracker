# 每月支出追蹤器 PWA（Google Sheets 永久儲存版）

這個版本將原本的本機 `data/*.csv` 儲存改為 **Google Sheets**，適合部署到 Streamlit Community Cloud；PWA 外殼可放在 GitHub Pages。

## 專案結構

```text
monthly_expense_tracker_google_sheets_pwa/
├─ streamlit_app.py
├─ requirements.txt
├─ index.html
├─ manifest.json
├─ sw.js
├─ gen_icons.py
├─ DEPLOY_CHECKLIST.md
├─ .gitignore
├─ .streamlit/
│  ├─ config.toml
│  └─ secrets.toml.example
└─ icons/
   ├─ icon-192.png
   ├─ icon-512.png
   ├─ icon-maskable-192.png
   ├─ icon-maskable-512.png
   ├─ apple-touch-icon.png
   └─ favicon-32.png
```

## 主要變更

- 交易、預算、分類改存 Google Sheets：`transactions`、`budgets`、`categories` 三個工作表。
- 保留 CSV / Excel 匯出與完整 ZIP 備份。
- `index.html` 透過 `?embed=true` 嵌入 Streamlit，符合 Streamlit Community Cloud 的官方嵌入方式。
- 不關閉 CORS / XSRF 防護。
- 真正的 Google Service Account 金鑰只放在 Streamlit Secrets，不放進 GitHub。

## 你只需要改一個 PWA 網址設定

部署好 Streamlit 後，打開 `index.html`：

```js
const DEFAULT_APP_URL = "YOUR_STREAMLIT_URL";
```

改成：

```js
const DEFAULT_APP_URL = "https://你的-app.streamlit.app";
```

PWA 會自動把 iframe 載入網址轉為 `?embed=true`；右上角「另開原站」仍開啟正常 Streamlit 網址。

## Google Sheets Secrets

不要上傳真正的 `.streamlit/secrets.toml`。請參考 `.streamlit/secrets.toml.example`，並在 Streamlit Community Cloud 的 App Secrets 貼上設定。

完整部署流程請看 [`DEPLOY_CHECKLIST.md`](./DEPLOY_CHECKLIST.md)。
