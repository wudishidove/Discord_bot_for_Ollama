#!/usr/bin/env python3
"""
音頻切分性能測試腳本
比較 Pydub 和 FFmpeg 兩種切分方法的速度
"""

import os
import time
import subprocess
import shutil
from pydub import AudioSegment

def get_audio_duration_ffprobe(file_path):
    """使用 ffprobe 獲取音頻時長（秒）"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            file_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        import json
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        return duration
    except Exception as e:
        print(f"ffprobe 獲取時長失敗: {e}")
        return None

def slice_with_pydub(mp3_path, output_dir):
    """
    使用 Pydub 切分音頻（現有方法）
    """
    print("\n=== 使用 Pydub 切分 ===")
    start_time = time.perf_counter()

    try:
        # 載入音頻
        load_start = time.perf_counter()
        audio = AudioSegment.from_mp3(mp3_path)
        load_time = time.perf_counter() - load_start
        print(f"載入音頻耗時: {load_time:.2f} 秒")

        duration_ms = len(audio)
        duration_min = duration_ms / 1000 / 60
        print(f"音頻總長度: {duration_min:.2f} 分鐘")

        # 切分參數
        segment_duration = 12 * 60 * 1000  # 12分鐘
        step_duration = 10 * 60 * 1000     # 步進10分鐘

        sliced_files = []
        part_index = 0
        start_pos = 0

        slice_start = time.perf_counter()

        while start_pos < duration_ms:
            end_pos = min(start_pos + segment_duration, duration_ms)

            # 提取片段
            segment = audio[start_pos:end_pos]

            # 儲存片段
            output_file = os.path.join(output_dir, f"pydub_part_{part_index}.mp3")
            segment.export(output_file, format="mp3")

            segment_min = (end_pos - start_pos) / 1000 / 60
            print(f"片段 {part_index}: {start_pos/1000/60:.2f}-{end_pos/1000/60:.2f} 分鐘")

            sliced_files.append(output_file)

            if end_pos >= duration_ms:
                break

            start_pos += step_duration
            part_index += 1

        slice_time = time.perf_counter() - slice_start
        total_time = time.perf_counter() - start_time

        print(f"\n切分耗時: {slice_time:.2f} 秒")
        print(f"總耗時: {total_time:.2f} 秒")
        print(f"生成 {len(sliced_files)} 個片段")

        return sliced_files, total_time

    except Exception as e:
        print(f"Pydub 切分失敗: {e}")
        return [], 0

def slice_with_ffmpeg(mp3_path, output_dir):
    """
    使用 FFmpeg 直接切分音頻
    """
    print("\n=== 使用 FFmpeg 切分 ===")
    start_time = time.perf_counter()

    try:
        # 獲取音頻時長
        duration = get_audio_duration_ffprobe(mp3_path)
        if not duration:
            # 備用方法：使用 ffmpeg 獲取時長
            cmd = ['ffmpeg', '-i', mp3_path, '-f', 'null', '-']
            result = subprocess.run(cmd, capture_output=True, text=True, errors='ignore')
            # 從 stderr 解析時長
            import re
            match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})', result.stderr)
            if match:
                hours, minutes, seconds = match.groups()
                duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            else:
                print("無法獲取音頻時長")
                return [], 0

        duration_min = duration / 60
        print(f"音頻總長度: {duration_min:.2f} 分鐘")

        # 切分參數
        segment_duration = 12 * 60  # 12分鐘（秒）
        step_duration = 10 * 60      # 步進10分鐘（秒）

        sliced_files = []
        part_index = 0
        start_pos = 0

        while start_pos < duration:
            # 計算片段長度
            remaining = duration - start_pos
            actual_duration = min(segment_duration, remaining)

            output_file = os.path.join(output_dir, f"ffmpeg_part_{part_index}.mp3")

            # FFmpeg 命令
            cmd = [
                'ffmpeg',
                '-ss', str(start_pos),      # 開始時間
                '-t', str(actual_duration), # 持續時間
                '-i', mp3_path,              # 輸入檔案
                '-acodec', 'copy',           # 複製編碼（最快）
                '-y',                        # 覆蓋輸出檔案
                output_file
            ]

            # 如果 copy 失敗，使用重新編碼
            try:
                subprocess.run(cmd, capture_output=True, check=True)
            except subprocess.CalledProcessError:
                # 重新編碼版本
                cmd = [
                    'ffmpeg',
                    '-ss', str(start_pos),
                    '-t', str(actual_duration),
                    '-i', mp3_path,
                    '-acodec', 'libmp3lame',
                    '-b:a', '192k',
                    '-y',
                    output_file
                ]
                subprocess.run(cmd, capture_output=True, check=True)

            end_pos = min(start_pos + segment_duration, duration)
            print(f"片段 {part_index}: {start_pos/60:.2f}-{end_pos/60:.2f} 分鐘")

            sliced_files.append(output_file)

            if end_pos >= duration:
                break

            start_pos += step_duration
            part_index += 1

        total_time = time.perf_counter() - start_time

        print(f"\n總耗時: {total_time:.2f} 秒")
        print(f"生成 {len(sliced_files)} 個片段")

        return sliced_files, total_time

    except Exception as e:
        print(f"FFmpeg 切分失敗: {e}")
        import traceback
        traceback.print_exc()
        return [], 0

def main():
    """主測試函數"""
    # 設定路徑
    current_dir = os.path.dirname(os.path.abspath(__file__))
    download_dir = os.path.join(current_dir, "download_data")

    # 尋找要測試的 MP3 檔案
    test_file = None

    # 優先使用 yt.mp3
    yt_mp3 = os.path.join(download_dir, "yt.mp3")
    if os.path.exists(yt_mp3):
        test_file = yt_mp3
    else:
        # 尋找任何 MP3 檔案
        for file in os.listdir(download_dir):
            if file.endswith('.mp3'):
                test_file = os.path.join(download_dir, file)
                break

    if not test_file:
        print(f"錯誤：在 {download_dir} 中找不到 MP3 檔案")
        print("請先下載一個 YouTube 影片，或放置一個 MP3 檔案到 download_data 目錄")
        return

    print(f"測試檔案: {test_file}")
    file_size_mb = os.path.getsize(test_file) / (1024 * 1024)
    print(f"檔案大小: {file_size_mb:.2f} MB")

    # 創建輸出目錄
    test_output_dir = os.path.join(download_dir, "test_output")
    os.makedirs(test_output_dir, exist_ok=True)

    # 清理輸出目錄
    for file in os.listdir(test_output_dir):
        os.remove(os.path.join(test_output_dir, file))

    # 測試 Pydub
    # pydub_files, pydub_time = slice_with_pydub(test_file, test_output_dir)
    pydub_files=1
    pydub_time=1
    print("\n" + "="*50)

    # 測試 FFmpeg
    ffmpeg_files, ffmpeg_time = slice_with_ffmpeg(test_file, test_output_dir)

    # 結果比較
    print("\n" + "="*50)
    print("=== 性能比較結果 ===")
    print(f"Pydub 耗時:  {pydub_time:.2f} 秒")
    print(f"FFmpeg 耗時: {ffmpeg_time:.2f} 秒")

    if pydub_time > 0 and ffmpeg_time > 0:
        speedup = pydub_time / ffmpeg_time
        if speedup > 1:
            print(f"\nFFmpeg 比 Pydub 快 {speedup:.1f} 倍")
        else:
            print(f"\nPydub 比 FFmpeg 快 {1/speedup:.1f} 倍")

    # 驗證輸出
    print(f"\nPydub 生成 {len(pydub_files)} 個檔案")
    print(f"FFmpeg 生成 {len(ffmpeg_files)} 個檔案")

    # 顯示檔案大小
    if pydub_files:
        total_size = sum(os.path.getsize(f) for f in pydub_files) / (1024 * 1024)
        print(f"Pydub 輸出總大小: {total_size:.2f} MB")

    if ffmpeg_files:
        total_size = sum(os.path.getsize(f) for f in ffmpeg_files) / (1024 * 1024)
        print(f"FFmpeg 輸出總大小: {total_size:.2f} MB")

if __name__ == "__main__":
    main()