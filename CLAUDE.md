# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Starting the Bot
```bash
python bot_with_history.py
```

### Installing Dependencies
```bash
pip install discord.py langchain requests pymupdf4llm ollama
```

## Code Architecture

### Core Components

**Main Bot File (`bot_with_history.py`)**
- Discord bot using discord.py with command prefix `++`
- Integrates with local Ollama API at `http://localhost:11434`
- Per-channel conversation memory using LangChain's ConversationBufferMemory
- File upload support (text files, PDFs, images)
- Streaming response system with tool integration

**Tool System (`ollama_tool.py`)**
- Function calling framework for LLM tools
- Built-in tools: Google search, web scraping, math calculations, time/date
- Dynamic function description generation using introspection

**Global Variables (`global_var.py`)**
- Stores current model selection (default: "gpt-oss:latest")

### Memory Management
- Each Discord channel has isolated conversation history stored in `save_history/{channel_id}/history.json`
- Memory auto-trimming when token limits are reached using Ollama for summarization
- File contents temporarily stored per channel in `save_history/{channel_id}/file_contents.json` and cleaned after responses

### Model Configuration
Models are defined in `MODEL_MAX_TOKENS` dict with their token limits:
- gpt-oss:latest (131072 tokens)
- gemma3 variants (131072 tokens) 
- deepseek-r1 variants (131072 tokens)
- Legacy models with lower limits (4096-8192 tokens)

### File Handling
- All files are stored in `save_history/{channel_id}/` directory
- Supports text files, PDFs (converted to markdown), and images
- Images stored in channel directory with idle cleanup system (max 10 images, max 10 idle counts)
- PDF processing includes image extraction to `save_history/{channel_id}/pdf_images/`
- Text files and PDFs automatically cleaned after bot responses, images retained with cleanup logic

### Configuration
`config.json` contains:
- Discord bot token
- Allowed channel IDs
- Google API credentials for search functionality

## Discord Commands

- `++chat <message>` - Chat with the bot
- `++setmodel <model_name>` - Switch between available models
- `++clean_history` - Clear channel memory and files
- `++help` - Display available commands

## File Storage Structure

All channel data is stored under `save_history/{channel_id}/`:
```
save_history/
├── 1073495605286027267/
│   ├── history.json              # Conversation history  
│   ├── file_contents.json        # Temporary file content cache
│   ├── idle_count.json          # Image cleanup tracking
│   ├── uploaded_image.jpg       # User uploaded images
│   ├── document.pdf             # User uploaded documents
│   └── pdf_images/              # Extracted PDF images
│       └── page_1_image.jpg
└── 1355015638979969097/
    └── (same structure)
```

## Important Notes

- Bot requires Ollama running locally on port 11434
- Bot automatically falls back to gpt-oss:latest if requested model unavailable
- Conversation history is persistent per Discord channel in centralized storage
- Image processing includes automatic cleanup based on idle time and count limits
- Tool usage is automatically triggered by keywords in user messages
- All channel data is organized under `save_history/` directory for easy management