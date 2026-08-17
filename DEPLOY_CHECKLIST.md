# 每月支出追蹤器：免費部署 Checklist

> 目標：Streamlit Community Cloud + Google Sheets + GitHub Pages PWA。

## A. 本機檔案確認

- [ ] 專案根目錄有 `streamlit_app.py`。
- [ ] 專案根目錄有 `requirements.txt`。
- [ ] PWA 檔案有 `index.html`、`manifest.json`、`sw.js`。
- [ ] `.streamlit/config.toml` 已存在。
- [ ] `.streamlit/secrets.toml` **沒有** commit 到 GitHub。
- [ ] 執行 `python gen_icons.py` 後，`icons/` 有 6 個圖示。

## B. 建立 Google Sheet

- [ ] 在 Google Sheets 建立一份空白試算表，例如「每月支出追蹤器資料庫」。
- [ ] 從網址複製 Spreadsheet ID：`https://docs.google.com/spreadsheets/d/<這一段就是ID>/edit`。
- [ ] 不用手動建立工作表；App 第一次啟動會建立 `transactions`、`budgets`、`categories`。

## C. 建立 Google Cloud Service Account

- [ ] 進入 Google Cloud Console，建立或選擇一個 Project。
- [ ] 啟用 **Google Sheets API**。
- [ ] 建立 Service Account。
- [ ] 為 Service Account 建立 JSON key，下載 JSON。
- [ ] 找到 JSON 內的 `client_email`。
- [ ] 回到 Google Sheet →「共用」→ 把 `client_email` 加入，權限設為 **編輯者**。
- [ ] 不要把下載的 JSON key 上傳到 GitHub。

## D. 設定 Streamlit Secrets

- [ ] 依 `.streamlit/secrets.toml.example` 建立 Secrets 內容。
- [ ] `[google_sheets] spreadsheet_id` 填入 Spreadsheet ID。
- [ ] `[gcp_service_account]` 各欄位填入 Service Account JSON 對應值。
- [ ] `private_key` 保留 BEGIN/END PRIVATE KEY 與換行。

## E. 上傳 GitHub

- [ ] 建立 GitHub repository，例如 `expense-tracker`。
- [ ] 上傳整個專案，但不要上傳真正的 `secrets.toml` / Service Account JSON。
- [ ] 確認 GitHub 頁面看不到任何 private key。

## F. 部署 Streamlit Community Cloud

- [ ] 登入 Streamlit Community Cloud。
- [ ] 建立 App，選 GitHub repo、branch `main`、main file `streamlit_app.py`。
- [ ] 在 App settings / Secrets 貼上 D 區準備的 Secrets。
- [ ] Deploy。
- [ ] 開啟 Streamlit 網址，確認沒有 Google Sheets 憑證錯誤。
- [ ] 新增一筆交易。
- [ ] 重新整理 App，確認交易仍存在。
- [ ] 回 Google Sheet，確認 `transactions` 出現資料。
- [ ] 設定預算，確認 `budgets` 出現資料。
- [ ] 新增分類，確認 `categories` 出現資料。

## G. 填入 PWA 預設 Streamlit URL

- [ ] 複製實際 Streamlit URL，例如 `https://xxx.streamlit.app`。
- [ ] 打開 `index.html`。
- [ ] 找到 `const DEFAULT_APP_URL = "YOUR_STREAMLIT_URL";`。
- [ ] 換成實際 Streamlit URL。
- [ ] 不需要手動加 `?embed=true`，PWA 程式會自動加入。

## H. 部署 GitHub Pages

- [ ] GitHub repo → Settings → Pages。
- [ ] Source 選 `Deploy from a branch`。
- [ ] Branch 選 `main`，Folder 選 `/ (root)`。
- [ ] Save。
- [ ] 開啟 `https://<帳號>.github.io/<repo>/`。
- [ ] 確認 Streamlit App 能在 PWA iframe 中載入。
- [ ] 點「另開原站」，確認正常開啟 Streamlit。

## I. PWA 安裝測試

- [ ] Chrome / Edge 桌機開啟 GitHub Pages 網址。
- [ ] 確認出現「安裝 App」或瀏覽器安裝圖示。
- [ ] 安裝後確認以 standalone 視窗開啟。
- [ ] Android Chrome 開啟同一網址。
- [ ] 加到主畫面 / 安裝 App。
- [ ] 關閉網路後重新開啟：PWA 外殼應可顯示；Streamlit 本體仍需要網路。

## J. 備份與安全測試


- [ ] 產生「完整資料備份 ZIP」，確認包含 `transactions.csv`、`budgets.csv`、`categories.csv`。
- [ ] GitHub 全 repo 搜尋 `BEGIN PRIVATE KEY`，結果必須為 0（範例檔除外只含佔位文字）。
- [ ] 若 Service Account key 曾誤上傳 GitHub，立即在 Google Cloud 刪除該 key 並重新建立。

## 完成判定

- [ ] GitHub Pages 可安裝成 PWA。
- [ ] iframe 可正常載入 Streamlit。
- [ ] 新增/修改/刪除交易後資料仍永久保留在 Google Sheets。
- [ ] 預算與分類也永久保留。
- [ ] 匯出/備份功能正常。
