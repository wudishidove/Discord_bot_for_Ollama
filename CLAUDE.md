# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Starting the Bot
```bash
python bot_with_history.py
```

### Installing Dependencies

**Core Dependencies**
```bash
pip install discord.py langchain requests pymupdf4llm ollama
```

**YouTube Subtitle Tool Dependencies**
```bash
pip install faster-whisper torch yt-dlp
```

**System Requirements**
- FFmpeg: Required for audio conversion (must be in PATH or install via `pip install ffmpeg-python`)
- CUDA (optional): For GPU acceleration of Whisper transcription
- Disk space: ~6GB for Whisper large-v3 model download

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
- Built-in tools: Google search, web scraping, math calculations, time/date, YouTube subtitle extraction
- Dynamic function description generation using introspection

### YouTube Subtitle Tool System

**Architecture Overview**
The YouTube subtitle extraction tool provides automated transcription of YouTube videos using a two-layer architecture for crash protection and reliability. The system now supports automatic audio slicing for long videos with overlapping segments to ensure complete transcription.

**Components**

1. **Subprocess Wrapper (`tool/yt_srt/run_srt_tool.py`)**
   - Isolates the main transcription process using subprocess to prevent crashes from affecting the bot
   - Manages file paths with absolute path resolution for Windows compatibility
   - Monitors all output files in `download_data/` directory with 300-second timeout protection
   - Returns `(success: bool, download_data_dir: str | None)` tuple
   - Automatically checks for existing txt files in download_data to avoid redundant processing

2. **Core Processor (`tool/yt_srt/tool_srt.py`)**
   - **Directory Management**: Cleans and manages `download_data/` directory for all files
   - **Video Download**: Uses yt-dlp (module or CLI fallback) to download YouTube audio as MP3
   - **Audio Slicing** (NEW):
     - Automatically slices audio files > 10 minutes using pydub
     - Creates 11-minute segments with 2-minute overlaps (0-11, 9-21, 19-31...)
     - Ensures complete coverage without missing content
   - **Transcription**: Leverages OpenAI Whisper large-v3 model via faster_whisper
     - Processes each audio segment separately
     - Generates individual `.txt` files for each part
   - **Language Support**: Auto-detection or manual specification
   - **Output Formats**:
     - `normal`: Plain text with comma separation
     - `timeline`: Text with timestamps `[start -> end] text`
     - `subtitle`: Standard SRT format with numbered entries
   - **GPU Acceleration**: Automatic CUDA detection for faster processing

**Integration with Bot**
- Function: `get_youtube_srt(url: str, user_input: str = "") -> str` in `ollama_tool.py`
- Automatically triggered by keywords in user messages
- Reads all `.txt` files from `download_data/` directory
- Combines multiple transcription parts for summarization
- Cleans up all files after processing
- Returns summarized content or error messages

**File Management**
```
tool/yt_srt/
├── run_srt_tool.py         # Subprocess wrapper for crash isolation
├── tool_srt.py             # Core transcription logic with slicing
└── download_data/          # All downloaded and generated files
    ├── yt.mp3              # Full original audio
    ├── yt.txt              # Transcription (for videos ≤ 10 min)
    ├── yt_part_0.mp3       # First segment (0-11 min)
    ├── yt_part_0.txt       # First segment transcription
    ├── yt_part_1.mp3       # Second segment (9-21 min)
    ├── yt_part_1.txt       # Second segment transcription
    └── ...                 # Additional segments as needed
```

**Audio Slicing Details**
- **Threshold**: Videos > 10 minutes are automatically sliced
- **Segment Length**: 11 minutes (10 min content + 1 min overlap on each side)
- **Overlap**: 2 minutes between segments to ensure no content is lost
- **Pattern**: 0-11 min, 9-21 min, 19-31 min, etc.
- **File Naming**: `yt_part_0.mp3`, `yt_part_1.mp3`, etc.

**Processing Flow**
1. User provides YouTube URL
2. `run_srt_tool_isolated()` spawns subprocess with `tool_srt.py`
3. Cleans `download_data/` directory of old files
4. Downloads MP3 using yt-dlp with ffmpeg conversion to `download_data/yt.mp3`
5. **Audio Slicing** (if > 10 minutes):
   - Detects audio duration using pydub
   - Slices into 11-minute overlapping segments
   - Saves as `yt_part_0.mp3`, `yt_part_1.mp3`, etc.
6. Loads Whisper large-v3 model (CUDA/CPU auto-detection)
7. Transcribes each audio file separately with beam search (beam_size=8)
8. Saves individual transcriptions:
   - Single file: `yt.txt` (for videos ≤ 10 min)
   - Multiple files: `yt_part_0.txt`, `yt_part_1.txt`, etc. (for longer videos)
9. Parent process monitors and returns download_data directory path
10. `get_youtube_srt()` reads all txt files, combines them, and sends to Ollama for summarization

**Discord Message Handling for Batch Processing**
When processing YouTube videos with multiple segments:

1. **Message Flow**:
   - Each segment gets its own Discord message to prevent overwriting
   - Progress updates are handled through message editing
   - Final summaries are sent as new messages

2. **Segment Processing Display**:
   - `📝 【段落 X/Y】正在生成字幕...` - New segment starts, creates new Discord message
   - `🤖 【段落 X/Y】正在生成摘要...` - Updates the same segment's message
   - `✅ 【段落 X/Y】摘要內容` - Final summary, edits the segment's message
   - `🎯 【總體摘要】` - Overall summary, sent as new message

3. **Implementation Details** (`bot_with_history.py`):
   - Uses `segment_messages = {}` dictionary to track segment number to Discord message mapping
   - When `📝` is detected, creates new message for that segment
   - Subsequent `🤖` and `✅` updates edit the corresponding segment's message
   - Prevents previous segments from being overwritten by new ones
   - Each segment maintains its complete summary in chat history

**Error Handling**
- Subprocess crash isolation prevents bot termination
- 5-minute timeout for long videos
- Fallback from yt-dlp module to CLI tool
- Cookie support for age-restricted videos
- File existence validation at each step

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