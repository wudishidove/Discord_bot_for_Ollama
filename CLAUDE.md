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
The YouTube subtitle extraction tool provides automated transcription of YouTube videos using a streaming architecture with segment-by-segment processing. The system supports automatic audio slicing for long videos with overlapping segments and includes automatic yt-dlp updater for better reliability.

**Components**

1. **Main Entry Point (`bot_with_history.py::process_youtube_srt_streaming`)**
   - Handles the streaming response to Discord with real-time progress updates
   - Manages automatic yt-dlp update and retry logic on download failures
   - Yields progress messages for each processing stage

2. **Download and Slice Module (`tool/yt_srt/download_and_slice.py`)**
   - **Video Download**: Uses yt-dlp CLI (no Python module to avoid caching issues) to download YouTube audio as MP3
   - **Automatic Updater**: `update_yt_dlp()` function executes `python -m pip install -U yt-dlp` when download fails
   - **Audio Slicing** (FFmpeg-based for 50x speed improvement):
     - Automatically slices audio files > 10 minutes using FFmpeg
     - Creates 12-minute segments with 2-minute overlaps (0-12, 10-22, 20-32...)
     - Ensures complete coverage without missing content
   - **Directory Management**: Cleans and manages `download_data/` directory

3. **Segment Processor (`tool/yt_srt/process_single_segment.py`)**
   - Controls individual segment processing via subprocess isolation
   - Spawns `tool_srt_single.py` for GPU-intensive transcription work
   - Returns transcription results or error messages

4. **Single Segment Transcriber (`tool/yt_srt/tool_srt_single.py`)**
   - **Transcription**: Uses OpenAI Whisper large-v3 model via faster_whisper
   - **GPU Acceleration**: Automatic CUDA detection for faster processing
   - **Output Formats**: Plain text output optimized for summarization
   - Processes one audio segment at a time to manage GPU memory

**Integration with Bot**
- Main function: `process_youtube_srt_streaming(url, user_input)` in `bot_with_history.py`
- Automatically triggered by YouTube URL detection in messages
- Streams progress updates to Discord in real-time
- Handles segment-by-segment processing with individual summaries
- Generates overall summary for multi-segment videos

**File Management**
```
tool/yt_srt/
├── download_and_slice.py   # Download, update, and audio slicing
├── process_single_segment.py # Segment processing controller
├── tool_srt_single.py      # Single segment transcription
└── download_data/          # Temporary files (auto-cleaned)
    ├── yt.mp3              # Full original audio
    ├── yt_part_0.mp3       # First segment (0-12 min)
    ├── yt_part_0.txt       # First segment transcription
    ├── yt_part_1.mp3       # Second segment (10-22 min)
    ├── yt_part_1.txt       # Second segment transcription
    └── ...                 # Additional segments as needed
```

**Audio Slicing Details**
- **Threshold**: Videos > 10 minutes are automatically sliced
- **Segment Length**: 12 minutes (10 min content + 2 min overlap)
- **Overlap**: 2 minutes between segments to ensure no content is lost
- **Pattern**: 0-12 min, 10-22 min, 20-32 min, etc.
- **File Naming**: `yt_part_0.mp3`, `yt_part_1.mp3`, etc.

**Processing Flow with Auto-Update**
1. User provides YouTube URL
2. `process_youtube_srt_streaming()` attempts first download
3. If download fails:
   - Yields "⚙️ 下載失敗，更新yt下載器版本中..."
   - Executes `update_yt_dlp()` to update yt-dlp
   - Retries download once more
   - If still fails, returns error and exits
4. Downloads MP3 using yt-dlp CLI to `download_data/yt.mp3`
5. **Audio Slicing** (if > 10 minutes):
   - Uses FFmpeg for fast slicing
   - Creates 12-minute overlapping segments
6. For each segment:
   - Spawns subprocess with `tool_srt_single.py` for transcription
   - Loads Whisper large-v3 model (CUDA/CPU auto-detection)
   - Generates transcription and summary
   - Yields progress to Discord
7. Generates overall summary for multi-segment videos
8. Cleans up all temporary files

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