## Ollama Discord 機器人專案說明（program.md）

本文件整理此專案的目錄結構、主要模組與資料流、指令與執行方式，以及安裝與設定注意事項，方便快速上手與維護。

### 專案目的
- 利用本機 `Ollama` 模型（含多模型切換、圖片理解、工具使用）在 Discord 上提供聊天助理。
- 支援頻道級對話記憶、PDF/文字檔案讀取、圖片快取管理、串流回覆與外部檢索工具（Google/DuckDuckGo/抓取網頁內容/數學運算）。

## 目錄結構

```
Discord_bot_for_Ollama/
  ├─ <channel_id>/                  # 以頻道 ID 命名的對話與快取資料夾（動態生成）
  │   ├─ history.json               # 該頻道的對話記憶
  │   ├─ idle_count.json            # 圖片閒置計數器
  │   ├─ pdf_images/                # 從 PDF 萃取出的圖片（自動清理舊檔）
  │   └─ ...（上傳的檔案與暫存資料）
  │
  ├─ bot_with_history.py            # Discord Bot 主程式（對話、記憶、串流、檔案處理）
  ├─ bot.py                         # 可能的早期/精簡版本（如無使用可忽略）
  ├─ ollama_tool.py                 # 工具函式（Google/DDG 搜尋、抓網頁、數學、時間/天氣等）
  ├─ global_var.py                  # 共用變數（例如 current_model）
  ├─ to_html.py                     # PDF 轉 HTML（目前主流程改用 PyMuPDF4LLM）
  ├─ pdf2htmlEX/                    # 第三方 PDF→HTML 工具（目前非主流程）
  ├─ outputs/                       # 測試輸出資料夾
  ├─ test_*.py / test.* / README.*  # 測試與說明
  ├─ discord_ollama.bat             # Windows 啟動批次檔（可用於啟動 bot）
  └─ program.md                     # 本文件
```

## 主要模組與職責

### `bot_with_history.py`
- **Discord Bot 與對話核心**：
  - 指令：`++chat`、`++setmodel`、`++help`、`++clean_history`
  - 事件：`on_ready`（啟動），`on_message`（處理提及與附件）
- **模型與記憶**：
  - `current_model`：預設 `gpt-oss:latest`（可用 `++setmodel` 切換）
  - `MODEL_MAX_TOKENS`：不同模型 token 上限（影響記憶大小）
  - `ConversationBufferMemory`：頻道級記憶，存於 `<channel_id>/history.json`
  - 超過閾值時以 Ollama 呼叫 `trim_memory_with_ollama()` 摘要裁剪記憶
- **訊息組裝與串流**：
  - `handle_promt_history()`：把歷史記憶轉換為 chat messages，含 `system` 指示（繁中、遇數學先用工具、搜尋附來源、避免特殊字元）
  - `stream_response()`：串流回覆；符合關鍵字時自動進入「工具模式」，否則一般對話模式
- **檔案與圖片處理**：
  - `handle_file_upload()`：
    - 圖片：只重置 `<channel_id>/idle_count.json` 的閒置計數
    - 文字/PDF：以 `pymupdf4llm` 萃取 Markdown 與圖片（存至 `<channel_id>/pdf_images`），文字摘要寫入 `<channel_id>/file_contents.json`
  - `image_idle_check()`：控制圖片快取數量與閒置次數（預設最多 10 張、閒置 10 次即淘汰最舊）
  - 回覆完成後的清理：刪除 `file_contents.json`、清理 `.txt/.pdf` 原檔，移除超過時效的 PDF 圖片並清空空資料夾

### `ollama_tool.py`
- **工具宣告與綁定**：`generate_function_description()` 產生給 LLM 的工具描述格式
- **內建工具**：
  - `google_search(query)`：Google CSE（需 `config.json` 的 `GOOGLE_API_KEY` 與 `GOOGLE_CX`）
  - `web_search(query)`：DuckDuckGo 簡易搜尋
  - `fetch_url_content(url, user_input)`：抓取網頁、清理 HTML，並以當前模型摘要與關鍵字對齊
  - `do_math(a, op, b)`：基本數學運算
  - `get_local_time()`／`get_current_weather(city)`：時間與天氣示例
- **與主程式整合**：
  - `bot_with_history.py` 內將上述工具包裝進 `tools` 清單，必要時由模型自行呼叫；工具結果以 `role: tool` 回饋至對話

## 資料流與執行流程（高層次）
1. 使用者在允許的頻道傳訊息（或提及 Bot）／上傳檔案。
2. `on_message`：
   - 建立 `<channel_id>` 目錄並保存上傳檔案。
   - 非圖片檔：以 `pymupdf4llm` 抽取文字與圖片，文字摘要暫存於 `file_contents.json`。
   - 提及 Bot 時整合同頻道的 `file_contents.json` 內容與使用者訊息，並呼叫 `stream_response()`。
3. `stream_response`：
   - 載入頻道記憶、必要時進行記憶裁剪。
   - 蒐集 `<channel_id>/` 與 `pdf_images/` 下的圖片路徑加入 messages。
   - 依關鍵字自動啟用工具模式或一般模式，串流回覆至 Discord。
4. 串流結束：保存對話至記憶檔、清理暫存文字與舊圖片。

## Bot 指令
- **`++chat <訊息>`**：一般聊天
- **`++setmodel <模型名稱>`**：切換模型（預設允許：`gemma3:nsfw2`、`gemma3:27b`、`gemma3:12b`、`deepseek-r1:32b`）
- **`++help`**：列出支援指令與模型建議
- **`++clean_history`**：清空當前頻道記憶與檔案（僅檔案層，會保留必要控制檔）

## 安裝與執行

### 系統需求
- Windows 10+（本專案含 `discord_ollama.bat`），亦可於其他作業系統執行
- Python 3.10+（建議建立虛擬環境）
- 已安裝並啟動 `Ollama`（預設位址 `http://localhost:11434`）

### 安裝相依套件（示例）
```bash
pip install discord.py requests langchain ollama pymupdf4llm pymupdf beautifulsoup4
```

> 注意：程式中呼叫了 `pymupdf.pro.unlock()`。若未持有 Pro 授權，此呼叫可能失敗；可視情況停用或註解該行。

### 設定 `config.json`
請在專案根目錄建立 `config.json`（鍵值請依實際需求填寫）：
```json
{
  "DISCORD_TOKEN": "你的 Discord Bot Token",
  "ALLOWED_CHANNEL_IDS": [1073495605286027267],
  "GOOGLE_API_KEY": "你的 Google API Key",
  "GOOGLE_CX": "你的 Custom Search Engine ID"
}
```

### 啟動 Bot
- 方式一（Windows）：雙擊或執行 `discord_ollama.bat`
- 方式二（通用）：
```bash
python bot_with_history.py
```

## 重要檔案說明
- **`bot_with_history.py`**：
  - 記憶：`save_history_to_file()`、`load_history_from_file()`、`trim_memory_with_ollama()`
  - 對話：`process_user_input()`、`stream_response()`、`handle_promt_history()`
  - 檔案：`handle_file_upload()`、`read_pdf_content()`、`read_file_content()`、`image_idle_check()`
  - 指令：`help`、`chat`、`setmodel`、`clean_history`
- **`ollama_tool.py`**：
  - 工具宣告：`generate_function_description()`、`use_tools()`
  - 工具實作：`google_search()`、`web_search()`、`fetch_url_content()`、`do_math()`、`get_local_time()`、`get_current_weather()`
- **`global_var.py`**：共用變數模組（例如 `current_model`）
- **`pdf2htmlEX/`**：第三方 PDF→HTML 工具與資源（目前主流程未使用）
- **`to_html.py` / `test_pdf.py` / `outputs/`**：PDF/HTML 測試或輔助腳本與輸出

## 已知限制與實務建議
- **模型一致性**：`ollama_tool.py` 透過 `from global_var import *` 取得 `current_model`，而 `bot_with_history.py` 內亦定義/切換 `current_model`。若要確保「工具」與「主對話」使用同一模型，建議改為以模組方式引用，例如在兩處都使用 `import global_var as GV` 並以 `GV.current_model` 存取，避免值複製造成不同步。
- **記憶預估**：目前以字數近似 token 數；若對長文本模型精準度要求高，建議改為真實 tokenizer 預估。
- **PDF 萃取**：預設以 `pymupdf4llm.to_markdown(page_chunks=True)` 並輸出圖片至 `<channel_id>/pdf_images`；如需 HTML 工作流可切換/擴充 `to_html.py` 或 `pdf2htmlEX/`。
- **清理策略**：`stream_response` 後會刪除 `.txt/.pdf` 原檔與 `file_contents.json`，圖片依時間與數量清理；若需保留原始上傳，請調整清理條件。

## 常見問題（FAQ）
- 啟動後無法解析 `pymupdf.pro.unlock()`：
  - 未使用 Pro 功能可註解該行；或依授權與套件版本需求正確安裝/啟用。
- 工具搜尋回傳空白：
  - 檢查 `config.json` 的 `GOOGLE_API_KEY`、`GOOGLE_CX` 是否正確；或先使用 `web_search()`（DuckDuckGo）。
- 模型回應與工具模型不一致：
  - 參考「模型一致性」建議，集中於 `global_var` 管理並以模組層級引用。

---
如需擴充：新增工具請在 `ollama_tool.py` 增加對應函式並以 `generate_function_description()` 包裝，並在 `bot_with_history.py` 的 `tools` 清單掛載即可。


