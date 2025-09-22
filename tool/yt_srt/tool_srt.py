import os
import torch
from faster_whisper import WhisperModel
import os
import re
import shutil
import subprocess
from pydub import AudioSegment
import math


def clean_download_data_dir(download_dir: str):
    """清理 download_data 目錄中的舊檔案"""
    if os.path.exists(download_dir):
        for file in os.listdir(download_dir):
            file_path = os.path.join(download_dir, file)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"已刪除舊檔案: {file}")
            except Exception as e:
                print(f"刪除檔案 {file} 失敗: {e}")
    else:
        os.makedirs(download_dir, exist_ok=True)
        print(f"已建立目錄: {download_dir}")

def slice_audio_with_overlap(mp3_path: str, download_dir: str) -> list[str]:
    """
    將超過10分鐘的音頻切片，每片11分鐘，片段間重疊2分鐘

    Args:
        mp3_path: 原始MP3檔案路徑
        download_dir: 儲存切片的目錄

    Returns:
        切片檔案路徑列表
    """
    try:
        print(f"\n=== 音頻切片處理 ===")
        audio = AudioSegment.from_mp3(mp3_path)
        duration_ms = len(audio)
        duration_min = duration_ms / 1000 / 60

        print(f"音頻總長度: {duration_min:.2f} 分鐘")

        # 如果小於等於10分鐘，不需要切片
        if duration_min <= 10:
            print("音頻長度 <= 10分鐘，不需要切片")
            return [mp3_path]

        # 計算切片參數
        segment_duration = 11 * 60 * 1000  # 11分鐘（毫秒）
        step_duration = 9 * 60 * 1000      # 步進9分鐘（重疊2分鐘）

        sliced_files = []
        part_index = 0
        start_time = 0

        while start_time < duration_ms:
            # 計算結束時間
            end_time = min(start_time + segment_duration, duration_ms)

            # 提取片段
            segment = audio[start_time:end_time]

            # 儲存片段
            part_filename = f"yt_part_{part_index}.mp3"
            part_path = os.path.join(download_dir, part_filename)
            segment.export(part_path, format="mp3")

            segment_min = (end_time - start_time) / 1000 / 60
            print(f"已生成片段 {part_index}: {start_time/1000/60:.2f}-{end_time/1000/60:.2f}分鐘 (長度: {segment_min:.2f}分鐘)")

            sliced_files.append(part_path)

            # 如果已到達結尾，停止
            if end_time >= duration_ms:
                break

            # 移動到下一個片段（步進9分鐘）
            start_time += step_duration
            part_index += 1

        print(f"總共生成 {len(sliced_files)} 個片段")
        return sliced_files

    except Exception as e:
        print(f"音頻切片失敗: {e}")
        # 如果切片失敗，返回原始檔案
        return [mp3_path]

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
    
    # 使用絕對路徑，不切換目錄
    if not os.path.isabs(output_dir):
        output_dir = os.path.abspath(output_dir)

    os.makedirs(output_dir, exist_ok=True)

    # 優先使用yt_dlp模組
    try:
        import yt_dlp
        return _download_with_module(url, use_cookie, cookie_path, output_dir)
    except ImportError:
        print("未安裝yt_dlp模組，嘗試使用外部yt-dlp...")
        return _download_with_cli(url, use_cookie, cookie_path, output_dir)


def _download_with_module(url: str, use_cookie: bool, cookie_path: str, output_dir: str) -> tuple[bool, str | None]:
    """使用yt_dlp模組下載"""
    import yt_dlp
    
    # 檢查下載前的文件列表（在輸出目錄）
    files_before = set(os.listdir(output_dir))
    print(f"下載前文件數量 (在 {output_dir}): {len(files_before)}")
    
    # 檢查ffmpeg
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        print(f"找到 ffmpeg: {ffmpeg_path}")
    else:
        print("警告: 未找到ffmpeg，轉檔可能會失敗。")
    
    # 確保使用 download_data 目錄
    download_dir = os.path.join(output_dir, "download_data")
    os.makedirs(download_dir, exist_ok=True)

    ydl_opts = {
        'outtmpl': os.path.join(download_dir, 'yt.%(ext)s'),
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
            
            # 檢查下載後的文件（在輸出目錄）
            files_after = set(os.listdir(output_dir))
            new_files = files_after - files_before
            print(f"下載後文件數量變化: {len(files_after) - len(files_before)}")

            # 直接驗證 MP3 文件是否存在（這是最可靠的方法）
            mp3_path = os.path.join(download_dir, "yt.mp3")
            if os.path.exists(mp3_path):
                print(f"SUCCESS: 成功生成 MP3 文件: {mp3_path}")
                return True, mp3_path  # 返回完整路徑
            else:
                # 檢查是否有其他音頻格式
                audio_files = [f for f in os.listdir(download_dir) if f.lower().endswith(('.mp3', '.m4a', '.webm', '.ogg'))]
                if audio_files:
                    print(f"找到音頻文件但非 MP3 格式: {audio_files}")
                print(f"ERROR: 沒有找到 MP3 文件於: {mp3_path}")
                return False, None
                
    except Exception as e:
        print(f"下載失敗: {type(e).__name__}: {e}")
        import traceback
        print(f"詳細錯誤: {traceback.format_exc()}")
        return False, None


def _download_with_cli(url: str, use_cookie: bool, cookie_path: str, output_dir: str) -> tuple[bool, str | None]:
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
        '-o', os.path.join(output_dir, 'download_data', 'yt.%(ext)s'),  # 指定輸出路徑
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
            # 檢查 MP3 文件
            mp3_path = os.path.join(output_dir, "download_data", "yt.mp3")
            if os.path.exists(mp3_path):
                print(f"下載完成！{mp3_path}")
                return True, mp3_path
            else:
                print(f"下載完成但未找到 MP3 文件於: {mp3_path}")
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
        # 設定目錄路徑
        output_dir = os.path.abspath(".")
        download_dir = os.path.join(output_dir, "download_data")

        # 清理舊檔案
        print("\n=== 清理舊檔案 ===")
        clean_download_data_dir(download_dir)

        # 步驟 1: 下載 MP3
        print("\n=== 步驟 1: 下載 MP3 ===")
        success, mp3_path = download_youtube_mp3(url, output_dir=output_dir)

        if not success or not mp3_path:
            print("MP3 下載失敗")
            return False, None

        print(f"MP3 下載成功: {mp3_path}")

        # 步驟 1.5: 音頻切片（如果需要）
        print("\n=== 步驟 1.5: 檢查是否需要切片 ===")
        mp3_files = slice_audio_with_overlap(mp3_path, download_dir)
        print(f"要處理的音頻檔案: {len(mp3_files)} 個")
        
        # 步驟 2: 載入 Whisper 模型
        print("\n=== 步驟 2: 載入 Whisper 模型 ===")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "float32"
        
        print(f"使用設備: {device}")
        print("載入 large-v3 模型...")
        
        model = WhisperModel("large-v3", device=device, compute_type=compute_type)
        print("模型載入完成")
        
        # 步驟 3: 轉錄所有音頻檔案
        print("\n=== 步驟 3: 轉錄音頻 ===")

        # 處理語言參數
        transcribe_language = None if language == "auto" else language

        output_files = []

        # 處理每個音頻檔案
        for idx, mp3_file in enumerate(mp3_files):
            print(f"\n--- 處理檔案 {idx+1}/{len(mp3_files)}: {os.path.basename(mp3_file)} ---")

            print(f"開始轉錄: {mp3_file}")
            segments, info = model.transcribe(
                mp3_file,
                beam_size=8,
                language=transcribe_language,
                initial_prompt="如果語言是中文，輸出繁體中文"
            )

            print(f"轉錄完成，音頻長度: {round(info.duration, 2)} 秒")

            # 處理轉錄結果
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

            # 儲存結果
            # 根據音頻檔案名生成輸出檔案名
            base_name = os.path.basename(mp3_file).replace('.mp3', '.txt')
            output_file = os.path.join(download_dir, base_name)

            print(f"儲存至: {output_file}")

            with open(output_file, "w", encoding="utf-8") as file:
                file.write(transcription)
                file.flush()
                os.fsync(file.fileno())

            # 確認檔案已成功寫入
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                print(f"[OK] 結果已儲存 (大小: {file_size} bytes)")
                output_files.append(output_file)
            else:
                print(f"[ERROR] 檔案 {output_file} 未能成功建立")

        print(f"\n=== 處理完成 ===")
        print(f"總共生成 {len(output_files)} 個字幕檔案")

        if output_files:
            # 返回成功狀態和 download_data 目錄路徑
            return True, download_dir
        else:
            return False, None

    except Exception as e:
        print(f"\n處理過程中發生錯誤: {str(e)}")
        import traceback
        print(f"錯誤詳情:\n{traceback.format_exc().encode('utf-8', 'ignore').decode('utf-8')}")
        return False, None



if __name__ == "__main__":
    # 結束會閃退，請通過subprocess執行
    import sys

    if len(sys.argv) < 2:
        print("錯誤: 請提供 YouTube 網址作為參數")
        print("用法: python tool_srt.py <youtube_url>")
        sys.exit(1)

    test_url = sys.argv[1]

    try:
        print("[DEBUG] 開始呼叫 yt_srt_generation_wrapper...")
        success, output_file = yt_srt_generation(test_url)
        print(f"[DEBUG] 函數返回: success={success}, output_file={output_file}")

        if success:
            print(f"\n成功！輸出檔案: {output_file}")
            sys.exit(0)
        else:
            print("\n處理失敗！")
            sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 主程式捕獲異常: {str(e)}")
        import traceback
        print(f"錯誤詳情:\n{traceback.format_exc().encode('utf-8', 'ignore').decode('utf-8')}")
        sys.exit(2)