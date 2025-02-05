以下是 **`bot_with_history.py`** 對應的完整 README 文件範例：

---

# Discord Bot with ollama

## 專案簡介
本專案是一個基於 Discord 的聊天機器人，整合了 **Ollama API** 和 **LangChain 記憶功能**，支援多種模型對話並能保存聊天記錄。使用者可以輕鬆地與機器人互動、切換模型以及管理對話歷史。

---

## 功能特色
- **多模型支持**：提供多種模型選擇，包括文本生成和多語言支持模型。
- **對話記憶**：能保存與用戶的聊天記錄，提供連續對話的上下文。
- **歷史裁剪**：自動優化和裁剪長記憶內容，確保高效運行。
- **易於操作**：提供直觀的指令列表，讓使用者快速上手。
- **可擴展性**：支援自定義模型和配置。

---

## 使用方法

### 1. 環境安裝
首先確保您已安裝以下依賴環境：
- Python 3.8 或以上版本
- Discord.py
- LangChain
- Requests

#### 安裝依賴
運行以下指令安裝所需套件：
```bash
pip install discord.py langchain requests
```

---

### 2. 安裝 Ollama
#### Ollama 是本專案的核心，需本地部署以支援對話生成。

1. 到 [Ollama 官網](https://ollama.ai) 下載並安裝 Ollama。
2. 啟動 Ollama 本地服務，默認運行於 `http://localhost:11434`。
3. 下載模型 可用open webui 或 ```ollama pull <模型名稱>```
---

### 3. 配置文件設置
在專案目錄下創建一個名為 `config.json` 的配置文件，並添加以下內容：
```json
{
    "DISCORD_TOKEN": "你的 Discord Bot Token"
}
```

將 `"你的 Discord Bot Token"` 替換為您的 Discord 開發者平台生成的機器人 Token。

---

### 4. 運行 Bot
運行以下命令啟動機器人：
```bash
python bot_with_history.py
```

機器人成功上線後，會在指定的 Discord 頻道中發送提示訊息。

---

## 使用說明

### 可用指令
以下是機器人支持的指令列表：

1. **聊天指令**：
   - `++chat <訊息>`：與機器人進行對話。
   - 例如：`++chat 你好`

2. **模型設置**：
   - `++setmodel <模型名稱>`：切換聊天模型。
   - 可用模型(你已安裝的模型)：`Qwen2.5:7b`，`gemma2:latest`，`mistral:latest`，`llama3.2:latest`，`phi4:latest`。
   - 例如：`++setmodel gemma2:latest`

3. **清除歷史**：
   - `++clean_history`：清除機器人的記憶歷史。

4. **幫助**：
   - `++help`：顯示可用指令和說明。

---

## 注意事項
- 須確保 Ollama 本地服務正在運行，並且可通過 `http://localhost:11434` 訪問。
- 在配置文件中正確填寫 Discord Token 以保證機器人正常運行。
- 頻道 ID 需替換為實際使用的 Discord 頻道 ID。
- 


如果有其他補充或修改需求，請告訴我！

[Switch to English](README.md)



