# ReadMe

## 繁體中文
### 專案簡介
這是一個基於 Discord Bot 的聊天機器人專案，支援通過 Ollama API 與多種模型進行互動。您可以根據需求動態切換模型，並在指定頻道與機器人進行對話。

### 功能特色
- **模型互動：** 使用 Ollama API 與模型進行聊天。
- **模型切換：** 支援動態選擇模型，必須自己安裝好模型，可用以下指令下載模型：
  ```bash
  ollama pull [模型在 Ollama library 的名字]
  ```
- **頻道限制：** 僅在指定頻道運行指令，確保訊息不被濫用。
- **指令簡單明瞭：** 包括 `++chat`、`++setmodel` 和 `++help`。

### 使用方法
1. 確保已安裝並啟動 Ollama：
   - [Ollama 官網](https://ollama.ai) 提供了下載和安裝指南。
   - 確保 `ollama serve` 成功啟動。
2. 將專案下載到本地：
   ```bash
   git clone <GitHub Repository URL>
   ```
3. 在專案目錄下創建 `config.json` 並填入 Discord Token：
   ```json
   {
       "DISCORD_TOKEN": "你的 Discord Bot Token"
   }
   ```
4. 啟動機器人：
   ```bash
   python bot.py
   ```

### 可用指令
- `++chat <訊息>`：與機器人進行對話。
- `++setmodel <模型名稱>`：切換當前使用的模型。
- `++help`：查看指令清單與功能說明。

### 聯繫方式
如有任何問題，pm我。

[切換到英文](README.md)



