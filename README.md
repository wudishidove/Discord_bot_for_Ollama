以下是 **`bot_with_history.py`** 的英文版 README 文件範例：

---

# Discord Bot with Ollama

## Project Overview
This project is a Discord bot integrated with **Ollama API** and **LangChain memory features**. It supports multiple conversation models, saves chat history, and provides a seamless conversational experience. Users can interact with the bot, switch models, and manage conversation history effortlessly.

---

## Features
- **Multi-Model Support**: Choose from various models for text generation and multilingual support.
- **Conversation Memory**: Retains chat context for continuous conversations.
- **History Trimming**: Automatically optimizes and trims lengthy memory for efficient performance.
- **User-Friendly Commands**: Intuitive commands for easy operation.
- **Extensibility**: Customizable for additional models and configurations.

---

## Usage

### 1. Environment Setup
Ensure you have the following prerequisites installed:
- Python 3.8 or later
- Discord.py
- LangChain
- Requests

#### Install Dependencies
Run the following command to install the required packages:
```bash
pip install discord.py langchain requests
```

---

### 2. Install Ollama
#### Ollama is the core service powering this bot and must be installed locally.

1. Download and install Ollama from the [official website](https://ollama.ai).
2. Start the Ollama local server, which runs by default at `http://localhost:11434`.

---

### 3. Configure the Bot
Create a `config.json` file in the project directory with the following content:
```json
{
    "DISCORD_TOKEN": "your_discord_bot_token"
}
```

Replace `"your_discord_bot_token"` with the token generated in your Discord Developer Portal.

---

### 4. Run the Bot
Start the bot with the following command:
```bash
python bot_with_history.py
```

Once the bot is successfully online, it will send a ready message to the designated Discord channel.

---

## Commands

### Available Commands
Here are the bot’s available commands:

1. **Chat Commands**:
   - `++chat <message>`: Chat with the bot.
   - Example: `++chat Hello`

2. **Model Selection**:
   - `++setmodel <model_name>`: Switch between available conversation models.
   - Supported models: `Qwen2.5:7b`, `gemma2:latest`, `mistral:latest`, `llama3.2:latest`, `phi4:latest`.
   - Example: `++setmodel gemma2:latest`

3. **Clear History**:
   - `++clean_history`: Clears the bot’s memory history.

4. **Help**:
   - `++help`: Displays the list of available commands and instructions.

---

## Notes
- Ensure that the Ollama local server is running and accessible at `http://localhost:11434`.
- Verify that the Discord token is correctly configured in the `config.json` file.
- Replace the channel ID in the code with the actual Discord channel ID you intend to use.

Let me know if there’s anything else you’d like to adjust or add!

[切換到中文](README_zh.md)


