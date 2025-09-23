import subprocess
import sys
import os
import time

def process_single_segment(mp3_path: str, segment_index: int) -> tuple[bool, str | None]:
    """
    使用 subprocess 隔離執行單個音頻段的 SRT 生成

    Args:
        mp3_path: 單個MP3檔案路徑
        segment_index: 段落索引

    Returns:
        tuple[bool, str | None]: (執行成功與否, 字幕檔案路徑或None)
    """
    try:
        # 取得當前目錄
        current_dir = os.path.dirname(os.path.abspath(__file__))
        tool_script = os.path.join(current_dir, "tool_srt_single.py")

        # 確認腳本存在
        if not os.path.exists(tool_script):
            print(f"錯誤: 找不到 tool_srt_single.py 於 {tool_script}")
            return False, None

        print(f"準備處理音頻段 {segment_index}: {os.path.basename(mp3_path)}")
        print(f"工作目錄: {current_dir}")

        # 設定輸出檔案路徑
        base_name = os.path.splitext(os.path.basename(mp3_path))[0]
        txt_path = os.path.join(current_dir, "download_data", f"{base_name}.txt")

        # 設定 UTF-8 環境變數
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONLEGACYWINDOWSSTDIO'] = '0'

        # 執行 subprocess
        print(f"執行 Whisper 轉錄...")
        result = subprocess.run(
            [sys.executable, tool_script, mp3_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            check=False,
            cwd=current_dir,
            env=env,
            timeout=300  # 5分鐘超時
        )

        # 顯示輸出（用於除錯）
        if result.stdout:
            print("Subprocess 輸出:")
            print(result.stdout)
        if result.stderr:
            print("Subprocess 錯誤:")
            print(result.stderr)

        # 等待檔案生成（最多等待 30 秒）
        max_wait_time = 30
        wait_interval = 1
        total_waited = 0

        print(f"等待字幕檔案生成: {txt_path}")

        while total_waited < max_wait_time:
            if os.path.exists(txt_path):
                file_size = os.path.getsize(txt_path)
                if file_size > 0:
                    print(f"[OK] 成功找到字幕檔案: {txt_path} ({file_size} bytes)")
                    return True, txt_path

            time.sleep(wait_interval)
            total_waited += wait_interval

            if total_waited % 5 == 0:
                print(f"已等待 {total_waited}/{max_wait_time} 秒...")

        # 超時
        print(f"警告: 等待 {max_wait_time} 秒後仍未找到字幕檔案")
        return False, None

    except subprocess.TimeoutExpired:
        print(f"錯誤: 處理音頻段 {segment_index} 超時（超過5分鐘）")
        return False, None
    except Exception as e:
        print(f"執行 subprocess 時發生錯誤: {e}")
        return False, None

def main():
    """測試用主函數"""
    if len(sys.argv) > 1:
        mp3_path = sys.argv[1]
        segment_index = int(sys.argv[2]) if len(sys.argv) > 2 else 0

        print(f"處理音頻檔案: {mp3_path}")
        print(f"段落索引: {segment_index}")
        print("=" * 50)

        success, txt_path = process_single_segment(mp3_path, segment_index)

        if success and txt_path:
            print(f"\n成功生成字幕: {txt_path}")

            # 顯示字幕內容預覽
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(f"字幕內容長度: {len(content)} 字元")
                    if len(content) > 200:
                        print(f"內容預覽: {content[:200]}...")
                    else:
                        print(f"內容: {content}")
            except Exception as e:
                print(f"讀取字幕檔案時發生錯誤: {e}")
        else:
            print("\n字幕生成失敗")
    else:
        print("請提供 MP3 檔案路徑作為參數")
        print("用法: python process_single_segment.py <mp3_path> [segment_index]")

if __name__ == "__main__":
    main()