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
        tuple[bool, str | None]: (執行成功與否, download_data目錄路徑或None)
    """
    try:
        # 取得絕對路徑 - 嘗試多種方式確保找到正確目錄
        if os.path.exists(r"D:\OneDrive\code\mygithub\Discord_bot_for_Ollama"):
            # 優先使用硬編碼路徑（最可靠）
            current_dir = r"D:\OneDrive\code\mygithub\Discord_bot_for_Ollama"
        else:
            # 否則使用當前工作目錄
            current_dir = os.getcwd()
            # 確保得到 Discord_bot_for_Ollama 目錄
            if "Discord_bot_for_Ollama" not in current_dir:
                # 嘗試從文件路徑推斷
                if '__file__' in globals():
                    file_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    if "Discord_bot_for_Ollama" in file_dir:
                        current_dir = file_dir

        tool_dir = os.path.abspath(os.path.join(current_dir, "tool", "yt_srt"))
        tool_script = os.path.join(tool_dir, "tool_srt.py")

        # 確認腳本存在
        if not os.path.exists(tool_script):
            print(f"錯誤: 找不到 tool_srt.py 於 {tool_script}")
            return False, f"error:can't find tool_srt.py in {tool_script}"

        # 使用 subprocess 執行 tool_srt.py
        # print(f"準備在隔離環境中執行 tool_srt.py...")
        # print(f"處理網址: {url}")
        # print(f"工作目錄: {tool_dir}")
        # print("-" * 50)

        # 設定 download_data 目錄路徑
        download_data_dir = os.path.join(tool_dir, "download_data")

        # 檢查 download_data 目錄是否已有檔案
        if os.path.exists(download_data_dir):
            txt_files = [f for f in os.listdir(download_data_dir) if f.endswith('.txt')]
            if txt_files:
                print(f"發現已存在的字幕檔案: {txt_files}")
                print(f"返回現有的 download_data 目錄")
                return True, download_data_dir

        # 設定 UTF-8 環境變數
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONLEGACYWINDOWSSTDIO'] = '0'

        # 在 tool/yt_srt 目錄下執行
        result = subprocess.run(
            [sys.executable, "tool_srt.py", url],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            check=False,  # 不要在非零退出碼時拋出異常
            cwd=tool_dir,  # 設置工作目錄
            env=env  # 添加環境變數
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

        print(f"等待字幕檔案生成...")
        print(f"檢查目錄: {download_data_dir}")

        # 確保目錄存在
        os.makedirs(download_data_dir, exist_ok=True)

        while total_waited < max_wait_time:
            # 檢查 download_data 目錄中的 txt 檔案
            if os.path.exists(download_data_dir):
                txt_files = [f for f in os.listdir(download_data_dir) if f.endswith('.txt')]

                if txt_files:
                    # 檢查所有 txt 檔案是否非空
                    all_valid = True
                    total_size = 0

                    for txt_file in txt_files:
                        txt_path = os.path.join(download_data_dir, txt_file)
                        if os.path.exists(txt_path):
                            file_size = os.path.getsize(txt_path)
                            total_size += file_size
                            if file_size == 0:
                                all_valid = False
                                print(f"檔案 {txt_file} 為空，繼續等待...")

                    if all_valid and total_size > 0:
                        print(f"[OK] 成功找到 {len(txt_files)} 個字幕檔案")
                        for txt_file in sorted(txt_files):
                            txt_path = os.path.join(download_data_dir, txt_file)
                            file_size = os.path.getsize(txt_path)
                            print(f"     - {txt_file}: {file_size} bytes")
                        print(f"     總大小: {total_size} bytes，等待時間: {total_waited} 秒")
                        return True, download_data_dir

            time.sleep(wait_interval)
            total_waited += wait_interval

            # 每10秒顯示進度並列出目錄內容
            if total_waited % 10 == 0:
                print(f"已等待 {total_waited}/{max_wait_time} 秒...")

                # 檢查 download_data 目錄內容
                if os.path.exists(download_data_dir):
                    files = os.listdir(download_data_dir)
                    if files:
                        print(f"  download_data 目錄內容:")
                        for f in sorted(files):
                            if f.endswith(('.txt', '.mp3')):
                                fpath = os.path.join(download_data_dir, f)
                                fsize = os.path.getsize(fpath) if os.path.exists(fpath) else 0
                                print(f"    - {f} ({fsize} bytes)")

        # 超時
        print(f"警告: 等待 {max_wait_time} 秒後仍未找到字幕檔案")

        # 檢查是否有 MP3 檔案（可能下載成功但轉錄失敗）
        if os.path.exists(download_data_dir):
            mp3_files = [f for f in os.listdir(download_data_dir) if f.endswith('.mp3')]
            if mp3_files:
                total_mp3_size = sum(os.path.getsize(os.path.join(download_data_dir, f)) for f in mp3_files)
                print(f"發現 {len(mp3_files)} 個 MP3 檔案 (總大小: {total_mp3_size} bytes)，可能轉錄過程失敗")

        return False, None

    except Exception as e:
        print(f"執行 subprocess 時發生錯誤: {e}")
        # 即使有錯誤，也檢查 download_data 目錄
        download_data_dir = "D:/OneDrive/code/mygithub/Discord_bot_for_Ollama/tool/yt_srt/download_data"
        if os.path.exists(download_data_dir):
            txt_files = [f for f in os.listdir(download_data_dir) if f.endswith('.txt')]
            if txt_files:
                total_size = sum(os.path.getsize(os.path.join(download_data_dir, f)) for f in txt_files)
                if total_size > 0:
                    print(f"雖然有錯誤，但找到 {len(txt_files)} 個字幕檔案 (總大小: {total_size} bytes)")
                    return True, download_data_dir
        return False, "exception error"
    


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
    success, output_dir = run_srt_tool_isolated(youtube_url)

    print("-" * 50)
    if success and output_dir:
        print(f"主程式：字幕生成成功完成")
        print(f"輸出目錄: {output_dir}")

        # 顯示所有生成的字幕檔案
        try:
            if os.path.exists(output_dir):
                txt_files = sorted([f for f in os.listdir(output_dir) if f.endswith('.txt')])

                if txt_files:
                    print(f"\n找到 {len(txt_files)} 個字幕檔案:")

                    total_content_length = 0
                    for txt_file in txt_files:
                        txt_path = os.path.join(output_dir, txt_file)
                        with open(txt_path, "r", encoding="utf-8") as f:
                            content = f.read()
                            content_length = len(content)
                            total_content_length += content_length
                            print(f"  - {txt_file}: {content_length} 字元")

                            # 顯示每個檔案的前200字元作為預覽
                            if content_length > 200:
                                print(f"    預覽: {content[:200]}...")
                            else:
                                print(f"    內容: {content}")

                    print(f"\n總字元數: {total_content_length}")
                else:
                    print(f"警告：在 {output_dir} 中未找到字幕檔案")
            else:
                print(f"警告：輸出目錄 {output_dir} 不存在")
        except Exception as e:
            print(f"讀取檔案時發生錯誤: {e}")
    else:
        print("字幕生成發生問題，但主程式仍在運行")

        # 檢查 download_data 目錄中的 MP3 檔案
        download_dir = "./download_data"
        if os.path.exists(download_dir):
            mp3_files = [f for f in os.listdir(download_dir) if f.endswith('.mp3')]
            if mp3_files:
                print(f"提示: 在 {download_dir} 中找到 {len(mp3_files)} 個 MP3 檔案，但轉錄可能失敗")

    print("\n主程式正常結束")


if __name__ == "__main__":
    main()