import os
import sys
import torch
from faster_whisper import WhisperModel

def process_single_audio(mp3_path: str) -> tuple[bool, str | None]:
    """
    處理單個音頻檔案，生成字幕文字檔

    Args:
        mp3_path: MP3檔案路徑

    Returns:
        tuple[bool, str | None]: (成功與否, 輸出檔案路徑或None)
    """
    # 設置環境變數
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    if not os.path.exists(mp3_path):
        print(f"錯誤: 找不到音頻檔案 {mp3_path}")
        return False, None

    try:
        # 設定輸出檔案路徑
        base_name = os.path.splitext(os.path.basename(mp3_path))[0]
        output_dir = os.path.dirname(mp3_path)
        txt_path = os.path.join(output_dir, f"{base_name}.txt")

        print(f"處理音頻: {mp3_path}")
        print(f"輸出檔案: {txt_path}")

        # 載入 Whisper 模型
        print("\n=== 載入 Whisper 模型 ===")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "float32"

        print(f"使用設備: {device}")
        print("載入 large-v3 模型...")

        model = WhisperModel("large-v3", device=device, compute_type=compute_type)
        print("模型載入完成")

        # 轉錄音頻
        print("\n=== 開始轉錄 ===")
        segments, info = model.transcribe(
            mp3_path,
            beam_size=8,
            language=None,  # 自動偵測語言
            initial_prompt="如果語言是中文，輸出繁體中文"
        )

        # 偵測到的語言
        print(f"偵測到語言: {info.language} (機率: {info.language_probability:.2f})")

        # 收集轉錄結果（normal 模式）
        transcribed_text = []
        segment_count = 0

        for segment in segments:
            text = segment.text.strip()
            if text:
                transcribed_text.append(text)
                segment_count += 1
                # 顯示進度
                if segment_count % 10 == 0:
                    print(f"  已處理 {segment_count} 個段落...")

        print(f"轉錄完成，共 {segment_count} 個段落")

        # 組合結果（使用逗號分隔）
        final_text = '，'.join(transcribed_text)

        # 寫入檔案
        print(f"\n=== 儲存結果 ===")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(final_text)

        file_size = os.path.getsize(txt_path)
        print(f"已儲存到: {txt_path}")
        print(f"檔案大小: {file_size} bytes")
        print(f"內容長度: {len(final_text)} 字元")

        # 顯示預覽
        if len(final_text) > 200:
            print(f"內容預覽: {final_text[:200]}...")
        else:
            print(f"內容: {final_text}")

        return True, txt_path

    except Exception as e:
        print(f"轉錄過程發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False, None

if __name__ == "__main__":
    # 注意：結束時會閃退，請通過subprocess執行
    if len(sys.argv) < 2:
        print("錯誤: 請提供音頻檔案路徑作為參數")
        print("用法: python tool_srt_single.py <mp3_path>")
        sys.exit(1)

    mp3_path = sys.argv[1]

    try:
        print("[DEBUG] 開始處理單個音頻檔案...")
        success, output_file = process_single_audio(mp3_path)
        print(f"[DEBUG] 函數返回: success={success}, output_file={output_file}")

        if success:
            print(f"\n成功！輸出檔案: {output_file}")
            sys.exit(0)
        else:
            print("\n處理失敗！")
            sys.exit(1)

    except Exception as e:
        print(f"程式執行錯誤: {e}")
        sys.exit(1)