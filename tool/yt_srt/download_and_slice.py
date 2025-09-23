import os
import subprocess
import sys
import shutil
import json
import re

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

def download_youtube_mp3(url: str, output_dir: str = ".") -> tuple[bool, str | None]:
    """
    下載YouTube視頻為MP3音頻文件

    Args:
        url: YouTube視頻網址
        output_dir: 輸出目錄，默認為當前目錄

    Returns:
        tuple[bool, str | None]: (成功與否, MP3文件路徑或None)
    """
    # 創建 download_data 子目錄
    download_dir = os.path.join(output_dir, "download_data")
    os.makedirs(download_dir, exist_ok=True)

    # 嘗試使用 yt-dlp Python 模塊
    try:
        import yt_dlp

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(download_dir, 'yt.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
        }

        print(f"使用 yt-dlp 模塊下載: {url}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        mp3_path = os.path.join(download_dir, "yt.mp3")
        if os.path.exists(mp3_path):
            print(f"下載成功！{mp3_path}")
            return True, mp3_path
        else:
            print(f"下載完成但未找到 MP3 文件於: {mp3_path}")
            return False, None

    except ImportError:
        print("yt-dlp模塊未安裝，嘗試使用外部命令")
    except Exception as e:
        print(f"yt-dlp模塊執行失敗: {e}")
        print("切換到外部命令模式")

    # 如果模塊方式失敗，嘗試使用外部命令
    return _download_with_cli(url, output_dir)

def _download_with_cli(url: str, output_dir: str) -> tuple[bool, str | None]:
    """使用外部yt-dlp命令行工具下載"""
    cli = _find_yt_dlp_cli()
    if not cli:
        print("找不到外部yt-dlp，請安裝yt-dlp或將其加入PATH")
        return False, None

    download_dir = os.path.join(output_dir, "download_data")
    cmd = [
        cli,
        '-f', 'bestaudio/best',
        '--extract-audio',
        '--audio-format', 'mp3',
        '--audio-quality', '0',
        '-o', os.path.join(download_dir, 'yt.%(ext)s'),
        url,
    ]

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
            mp3_path = os.path.join(download_dir, "yt.mp3")
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

def get_audio_duration(mp3_path: str) -> float:
    """
    使用 ffprobe 獲取音頻時長（秒）
    """
    try:
        # 優先使用 ffprobe
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            mp3_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            duration = float(data['format']['duration'])
            return duration
    except:
        pass

    # 備用方法：使用 ffmpeg
    try:
        cmd = ['ffmpeg', '-i', mp3_path, '-f', 'null', '-']
        result = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
        # 從 stderr 解析時長
        match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})', result.stderr)
        if match:
            hours, minutes, seconds = match.groups()
            duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            return duration
    except Exception as e:
        print(f"獲取音頻時長失敗: {e}")

    raise Exception(f"無法獲取音頻時長: {mp3_path}")

def slice_audio_with_overlap(mp3_path: str, download_dir: str) -> list[str]:
    """
    使用 FFmpeg 將超過10分鐘的音頻切片，每片12分鐘，片段間重疊2分鐘
    比 Pydub 快 50+ 倍

    Args:
        mp3_path: 原始MP3檔案路徑
        download_dir: 儲存切片的目錄

    Returns:
        切片檔案路徑列表
    """
    try:
        print(f"\n=== 音頻切片處理 (FFmpeg) ===")

        # 獲取音頻時長
        duration = get_audio_duration(mp3_path)
        duration_min = duration / 60
        print(f"音頻總長度: {duration_min:.2f} 分鐘")

        # 如果小於等於10分鐘，不需要切片
        if duration_min <= 10:
            print("音頻長度 <= 10分鐘，不需要切片")
            return [mp3_path]

        # 切片參數（12分鐘片段，10分鐘步進）
        segment_duration = 12 * 60  # 12分鐘（秒）
        step_duration = 10 * 60      # 步進10分鐘（秒）

        sliced_files = []
        part_index = 0
        start_pos = 0

        while start_pos < duration:
            # 計算片段長度
            remaining = duration - start_pos
            actual_duration = min(segment_duration, remaining)

            # 輸出檔案路徑
            part_filename = f"yt_part_{part_index}.mp3"
            part_path = os.path.join(download_dir, part_filename)

            # FFmpeg 命令
            cmd = [
                'ffmpeg',
                '-ss', str(start_pos),      # 開始時間（秒）
                '-t', str(actual_duration), # 持續時間（秒）
                '-i', mp3_path,              # 輸入檔案
                '-acodec', 'libmp3lame',     # MP3 編碼器
                '-b:a', '192k',              # 位元率
                '-y',                        # 覆蓋輸出檔案
                part_path
            ]

            # 執行切片
            result = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')

            if result.returncode != 0:
                print(f"FFmpeg 切片失敗，片段 {part_index}")
                print(f"錯誤訊息: {result.stderr}")
                raise Exception(f"FFmpeg 切片失敗: {result.stderr}")

            # 顯示進度
            end_pos = start_pos + actual_duration
            print(f"已生成片段 {part_index}: {start_pos/60:.2f}-{end_pos/60:.2f}分鐘 (長度: {actual_duration/60:.2f}分鐘)")

            sliced_files.append(part_path)

            # 如果已到達結尾，停止
            if end_pos >= duration:
                break

            # 移動到下一個片段（步進10分鐘）
            start_pos += step_duration
            part_index += 1

        print(f"總共生成 {len(sliced_files)} 個片段")
        return sliced_files

    except Exception as e:
        print(f"音頻切片失敗: {e}")
        raise  # 直接拋出錯誤，不做退回處理

def download_and_slice_audio(url: str) -> tuple[bool, list[str]]:
    """
    下載YouTube影片並切片成多個音頻段

    Args:
        url: YouTube影片網址

    Returns:
        tuple[bool, list[str]]: (成功與否, MP3檔案路徑列表)
    """
    try:
        # 取得工作目錄
        current_dir = os.path.dirname(os.path.abspath(__file__))
        download_dir = os.path.join(current_dir, "download_data")

        print(f"=== 開始處理 YouTube 影片 ===")
        print(f"網址: {url}")
        print(f"工作目錄: {current_dir}")

        # Step 1: 清理舊檔案
        print("\n=== 清理舊檔案 ===")
        clean_download_data_dir(download_dir)

        # Step 2: 下載MP3
        print("\n=== 下載 MP3 ===")
        success, mp3_path = download_youtube_mp3(url, current_dir)

        if not success or not mp3_path:
            print("MP3 下載失敗")
            return False, []

        print(f"MP3 下載成功: {mp3_path}")

        # Step 3: 音頻切片（如果需要）
        print("\n=== 檢查是否需要切片 ===")
        mp3_files = slice_audio_with_overlap(mp3_path, download_dir)

        print(f"\n=== 處理完成 ===")
        print(f"生成 {len(mp3_files)} 個音頻檔案")
        for i, file in enumerate(mp3_files):
            print(f"  {i+1}. {os.path.basename(file)}")

        return True, mp3_files

    except Exception as e:
        print(f"處理過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False, []

if __name__ == "__main__":
    # 測試用
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        success, mp3_files = download_and_slice_audio(test_url)

        if success:
            print(f"\n成功！生成 {len(mp3_files)} 個音頻檔案:")
            for file in mp3_files:
                print(f"  - {file}")
        else:
            print("\n處理失敗！")
    else:
        print("請提供 YouTube 網址作為參數")