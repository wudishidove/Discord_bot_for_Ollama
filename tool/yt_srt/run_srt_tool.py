import subprocess
import sys
import os
import time

def run_srt_tool_isolated(url):
    """
    使用 subprocess 隔離執行 tool_srt.py，避免閃退影響主程式

    Args:
        url: YouTube 影片網址

    Returns:
        tuple[bool, str | None]: (執行成功與否, 輸出檔案路徑或None)
    """
    try:
        # 取得當前工作目錄
        current_dir = os.getcwd()
        tool_dir = os.path.join(current_dir, "tool", "yt_srt")
        tool_script = os.path.join(tool_dir, "tool_srt.py")

        # 確認腳本存在
        if not os.path.exists(tool_script):
            print(f"錯誤: 找不到 tool_srt.py 於 {tool_script}")
            return False, None

        # 使用 subprocess 執行 tool_srt.py
        print(f"準備在隔離環境中執行 tool_srt.py...")
        print(f"處理網址: {url}")
        print("-" * 50)

        # 預期的輸出檔案路徑
        expected_output = os.path.join(tool_dir, "yt.txt")

        # 如果已存在舊檔案，先刪除
        if os.path.exists(expected_output):
            try:
                os.remove(expected_output)
                print(f"已刪除舊的 yt.txt 檔案")
            except Exception as e:
                print(f"警告: 無法刪除舊檔案: {e}")

        # 在 tool/yt_srt 目錄下執行
        result = subprocess.run(
            [sys.executable, "tool_srt.py", url],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            check=False,  # 不要在非零退出碼時拋出異常
            cwd=tool_dir  # 設置工作目錄
        )

        # 顯示 subprocess 的輸出（用於除錯）
        if result.stdout:
            print("Subprocess 輸出:")
            print(result.stdout)
        if result.stderr:
            print("Subprocess 錯誤:")
            print(result.stderr)

        # 等待檔案生成（最多等待 300 秒）
        max_wait_time = 300  # 5分鐘
        wait_interval = 2    # 每2秒檢查一次
        total_waited = 0

        print(f"等待 yt.txt 檔案生成...")
        while total_waited < max_wait_time:
            if os.path.exists(expected_output):
                # 檢查檔案大小，確保不是空檔案
                file_size = os.path.getsize(expected_output)
                if file_size > 0:
                    print(f"✓ 成功生成 yt.txt (大小: {file_size} bytes)，等待時間: {total_waited} 秒")
                    return True, expected_output
                else:
                    print(f"檔案存在但為空，繼續等待...")

            time.sleep(wait_interval)
            total_waited += wait_interval

            # 每10秒顯示進度
            if total_waited % 10 == 0:
                print(f"已等待 {total_waited}/{max_wait_time} 秒...")

        # 超時
        print(f"警告: 等待 {max_wait_time} 秒後仍未找到 yt.txt")

        # 檢查是否有 MP3 檔案（可能下載成功但轉錄失敗）
        mp3_file = os.path.join(tool_dir, "yt.mp3")
        if os.path.exists(mp3_file):
            print(f"發現 MP3 檔案 ({os.path.getsize(mp3_file)} bytes)，可能轉錄過程失敗")

        return False, None

    except Exception as e:
        print(f"執行 subprocess 時發生錯誤: {e}")
        return False, None
    


def main():
    """主函數，處理用戶輸入並執行工具"""
    print("YouTube 影片字幕生成工具")
    print("=" * 50)

    # 獲取 YouTube 網址
    if len(sys.argv) > 1:
        # 如果有命令行參數，使用第一個參數作為網址
        youtube_url = sys.argv[1]
        print(f"使用命令行參數網址: {youtube_url}")
    else:
        # 否則詢問用戶輸入
        youtube_url = input("請輸入 YouTube 網址: ").strip()

    if not youtube_url:
        print("錯誤: 未提供 YouTube 網址")
        return

    # 執行工具
    success, output_file = run_srt_tool_isolated(youtube_url)

    print("-" * 50)
    if success:
        print(f"主程式：字幕生成成功完成")
        print(f"輸出檔案: {output_file}")

        # 嘗試顯示部分內容
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                content = f.read()
                print(f"\n檔案內容長度: {len(content)} 字元")

                # 顯示前500個字符作為預覽
                if len(content) > 500:
                    print(f"內容預覽 (前 500 字元):")
                    print(content[:500])
                    print("...")
                else:
                    print("完整內容:")
                    print(content)
        except FileNotFoundError:
            print(f"警告：找不到輸出檔案 {output_file}")
        except Exception as e:
            print(f"讀取檔案時發生錯誤: {e}")
    else:
        print("字幕生成發生問題，但主程式仍在運行")

        # 檢查是否有 MP3 檔案
        if os.path.exists("yt.mp3"):
            print("提示: MP3 檔案已下載成功，但轉錄可能失敗")

    print("\n主程式正常結束")


if __name__ == "__main__":
    main()