import os
import torch
from faster_whisper import WhisperModel
import os
import re
import shutil
import subprocess


def download_youtube_mp3(url: str, output_dir: str = ".", use_cookie: bool = False, cookie_path: str = "") -> tuple[bool, str | None]:
    """
    下載YouTube視頻為MP3音頻文件
    
    Args:
        url: YouTube視頻網址
        output_dir: 輸出目錄，默認為當前目錄
        use_cookie: 是否使用cookie文件
        cookie_path: cookie文件路徑
        
    Returns:
        tuple[bool, str | None]: (下載成功與否, MP3文件名或None)
    """
    if not url.strip():
        print("錯誤: 請提供有效的YouTube網址")
        return False, None
    
    if use_cookie and not os.path.exists(cookie_path):
        print(f"錯誤: 找不到cookie文件: {cookie_path}")
        return False, None
    
    # 切換到輸出目錄
    original_dir = os.getcwd()
    if output_dir != ".":
        os.makedirs(output_dir, exist_ok=True)
        os.chdir(output_dir)
    
    try:
        # 優先使用yt_dlp模組
        try:
            import yt_dlp
            return _download_with_module(url, use_cookie, cookie_path)
        except ImportError:
            print("未安裝yt_dlp模組，嘗試使用外部yt-dlp...")
            return _download_with_cli(url, use_cookie, cookie_path)
            
    finally:
        # 恢復原始目錄
        os.chdir(original_dir)


def _download_with_module(url: str, use_cookie: bool, cookie_path: str) -> tuple[bool, str | None]:
    """使用yt_dlp模組下載"""
    import yt_dlp
    
    # 檢查下載前的文件列表
    files_before = set(os.listdir('.'))
    print(f"下載前文件數量: {len(files_before)}")
    
    # 檢查ffmpeg
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        print(f"找到 ffmpeg: {ffmpeg_path}")
    else:
        print("警告: 未找到ffmpeg，轉檔可能會失敗。")
    
    ydl_opts = {
        'outtmpl': '%(title)s.%(ext)s',
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '0',
        }],
        'noplaylist': True,
        'verbose': True,  # 啟用詳細輸出
    }
    
    if ffmpeg_path:
        ydl_opts['ffmpeg_location'] = os.path.dirname(ffmpeg_path)
    
    if use_cookie and cookie_path:
        ydl_opts['cookiefile'] = cookie_path
        print(f"使用 cookie 文件: {cookie_path}")
    
    print(f"yt_dlp 配置: {ydl_opts}")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"開始下載: {url}")
            info = ydl.extract_info(url, download=True)
            try:
                print(f"視頻信息: 標題={info.get('title', 'Unknown')}")
            except UnicodeEncodeError:
                print("視頻信息: 標題包含特殊字符，無法顯示")
            
            # 先執行文件清理
            _cleanup_filenames()
            
            # 檢查下載後的文件
            files_after = set(os.listdir('.'))
            new_files = files_after - files_before
            print(f"下載後文件數量變化: {len(files_after) - len(files_before)}")
            
            # 直接驗證 MP3 文件是否存在（這是最可靠的方法）
            mp3_files = [f for f in os.listdir('.') if f.lower().endswith('.mp3')]
            if mp3_files:
                print(f"SUCCESS: 成功生成 MP3 文件: {mp3_files}")
                return True, mp3_files[0]  # 返回第一個 MP3 文件名
            else:
                # 檢查是否有其他音頻格式
                audio_files = [f for f in os.listdir('.') if f.lower().endswith(('.mp3', '.m4a', '.webm', '.ogg'))]
                if audio_files:
                    print(f"找到音頻文件但非 MP3 格式: {audio_files}")
                print("ERROR: 沒有找到 MP3 文件")
                return False, None
                
    except Exception as e:
        print(f"下載失敗: {type(e).__name__}: {e}")
        import traceback
        print(f"詳細錯誤: {traceback.format_exc()}")
        return False, None


def _download_with_cli(url: str, use_cookie: bool, cookie_path: str) -> tuple[bool, str | None]:
    """使用外部yt-dlp命令行工具下載"""
    cli = _find_yt_dlp_cli()
    if not cli:
        print("找不到外部yt-dlp，請安裝yt-dlp或將其加入PATH")
        return False, None
    
    cmd = [
        cli,
        '-f', 'bestaudio/best',
        '--extract-audio',
        '--audio-format', 'mp3',
        '--audio-quality', '0',
        url,
    ]
    
    if use_cookie and cookie_path:
        cmd.insert(-1, '--cookies')
        cmd.insert(-1, cookie_path)
    
    print(f"執行命令: {' '.join(cmd)}")
    
    try:
        proc = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            encoding='utf-8', 
            errors='ignore'
        )
        
        if proc.stdout:
            print(proc.stdout)
        
        if proc.returncode == 0:
            _cleanup_filenames()
            # 檢查 MP3 文件
            mp3_files = [f for f in os.listdir('.') if f.lower().endswith('.mp3')]
            if mp3_files:
                print("下載完成！")
                return True, mp3_files[0]
            else:
                print("下載完成但未找到 MP3 文件")
                return False, None
        else:
            print("下載失敗")
            return False, None
            
    except Exception as e:
        print(f"執行yt-dlp失敗: {e}")
        return False, None


def _find_yt_dlp_cli() -> str | None:
    """尋找yt-dlp命令行工具"""
    for name in ("yt-dlp", "yt-dlp.exe", "yt_dlp", "yt_dlp.exe"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _cleanup_filenames() -> None:
    """清理檔名中的方括號內容"""
    patterns = (".mp4", ".mkv", ".webm", ".m4a", ".mp3")
    for name in os.listdir('.'):
        lower = name.lower()
        if any(lower.endswith(ext) for ext in patterns):
            new_name = _remove_square_brackets(name)
            if new_name != name:
                try:
                    os.rename(name, new_name)
                    print(f"重新命名: {name} -> {new_name}")
                except Exception:
                    pass


def _remove_square_brackets(filename: str) -> str:
    """移除檔名中的方括號內容"""
    base, ext = os.path.splitext(filename)
    new_base = re.sub(r"\s*\[[^\]]+\]\s*", " ", base)
    new_base = re.sub(r"\s+", " ", new_base).strip()
    return f"{new_base}{ext}"




def yt_srt_generation(url: str) -> tuple[bool, str | None]:
    """
    自動下載 YouTube MP3 並生成對應的 SRT 或文字檔
    
    Args:
        url: YouTube 網址
        
    Returns:
        tuple[bool, str | None]: (成功與否, 輸出檔案名或None)
    """
    language= "auto"
    mode = "normal"
    # 設置環境變數
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    
    # 參數驗證
    if not url.strip():
        print("錯誤: 請提供有效的 YouTube 網址")
        return False, None
    
    if mode not in ["normal", "timeline", "subtitle"]:
        print(f"錯誤: 不支援的輸出模式 '{mode}'，支援的模式: normal, timeline, subtitle")
        return False, None
    
    print(f"開始處理 YouTube 影片: {url}")
    print(f"語言設定: {language}")
    print(f"輸出模式: {mode}")
    
    try:
        # 步驟 1: 下載 MP3
        print("\n=== 步驟 1: 下載 MP3 ===")
        success, mp3_filename = download_youtube_mp3(url, output_dir=".")
        
        if not success or not mp3_filename:
            print("MP3 下載失敗")
            return False, None
            
        print(f"MP3 下載成功: {mp3_filename}")
        
        # 步驟 2: 載入 Whisper 模型
        print("\n=== 步驟 2: 載入 Whisper 模型 ===")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "float32"
        
        print(f"使用設備: {device}")
        print("載入 large-v3 模型...")
        
        model = WhisperModel("large-v3", device=device, compute_type=compute_type)
        print("模型載入完成")
        
        # 步驟 3: 轉錄音頻
        print("\n=== 步驟 3: 轉錄音頻 ===")
        
        # 處理語言參數
        transcribe_language = None if language == "auto" else language
        
        print("開始轉錄...")
        segments, info = model.transcribe(
            mp3_filename,
            beam_size=8,
            language=transcribe_language,
            initial_prompt="如果語言是中文，輸出繁體中文"  # 空白提示詞
        )
        
        print(f"轉錄完成，音頻總長度: {round(info.duration, 2)} 秒")
        
        # 步驟 4: 處理轉錄結果
        print("\n=== 步驟 4: 處理轉錄結果 ===")
        transcription = ""
        segment_count = 0
        
        for i, segment in enumerate(segments, 1):
            segment_count += 1
            
            if mode == "normal":
                transcription += segment.text + "，"
            elif mode == "timeline":
                transcription += "[%.2fs -> %.2fs] %s\n" % (segment.start, segment.end, segment.text)
            elif mode == "subtitle":
                # SRT 格式處理
                start_hours, start_remainder = divmod(segment.start, 3600)
                start_minutes, start_seconds = divmod(start_remainder, 60)
                end_hours, end_remainder = divmod(segment.end, 3600)
                end_minutes, end_seconds = divmod(end_remainder, 60)
                start_time = f"{int(start_hours):02d}:{int(start_minutes):02d}:{start_seconds:06.3f}".replace('.', ',')
                end_time = f"{int(end_hours):02d}:{int(end_minutes):02d}:{end_seconds:06.3f}".replace('.', ',')
                transcription += f"{i}\n{start_time} --> {end_time}\n{segment.text}\n\n"
        
        print(f"處理了 {segment_count} 個音頻片段")
        
        # 步驟 5: 儲存結果
        print("\n=== 步驟 5: 儲存結果 ===")
        file_name = os.path.splitext(mp3_filename)[0]
        
        if mode == "subtitle":
            output_file = f"{file_name}.srt"
        else:
            output_file = f"{file_name}.txt"
        
        with open(output_file, "w", encoding="utf-8") as file:
            file.write(transcription)
        
        print(f"結果已儲存至: {output_file}")
        
        # 步驟 6: 清理資源
        print("\n=== 步驟 6: 清理資源 ===")
        del model
        if device == "cuda":
            torch.cuda.empty_cache()
            print("已釋放 GPU 記憶體")
        
        print("\n=== 處理完成 ===")
        return True, output_file
        
    except Exception as e:
        print(f"\n處理過程中發生錯誤: {str(e)}")
        return False, None


if __name__ == "__main__":
    # 測試用法
    test_url = input("請輸入 YouTube 網址: ").strip()
    if test_url:
        
        success, output_file = yt_srt_generation(test_url)
        
        if success:
            print(f"\n成功！輸出檔案: {output_file}")
        else:
            print("\n處理失敗！")