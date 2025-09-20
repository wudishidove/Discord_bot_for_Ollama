#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
測試 SRT 工具修正
"""

import sys
import os

# 將 tool/yt_srt 加入 Python 路徑
sys.path.insert(0, os.path.join(os.getcwd(), "tool", "yt_srt"))

from tool.yt_srt.run_srt_tool import run_srt_tool_isolated

def test_srt_generation():
    """測試 SRT 生成功能"""
    test_url = "https://www.youtube.com/watch?v=mES8ZefPojA"

    print("=" * 60)
    print("測試 YouTube 字幕生成工具")
    print("=" * 60)
    print(f"測試影片: {test_url}")
    print("-" * 60)

    # 執行字幕生成
    success, output_file = run_srt_tool_isolated(test_url)

    print("-" * 60)
    print("測試結果:")

    if success and output_file:
        print(f"✓ 測試成功！")
        print(f"  輸出檔案: {output_file}")

        # 檢查檔案內容
        if os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            print(f"  檔案大小: {file_size} bytes")

            # 顯示前500個字元作為預覽
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
                preview_length = min(500, len(content))
                print(f"\n內容預覽 (前 {preview_length} 字元):")
                print("-" * 40)
                print(content[:preview_length])
                if len(content) > preview_length:
                    print("...")
                print("-" * 40)

            # 清理測試檔案
            print("\n清理測試檔案...")
            os.remove(output_file)

            # 清理 MP3 檔案
            mp3_file = os.path.join(os.path.dirname(output_file), "yt.mp3")
            if os.path.exists(mp3_file):
                os.remove(mp3_file)
                print("已清理 MP3 檔案")

            print("✓ 測試完成，檔案已清理")
        else:
            print(f"✗ 錯誤: 檔案不存在 {output_file}")
    else:
        print("✗ 測試失敗！字幕生成過程出現問題")

        # 檢查是否有 MP3 檔案
        mp3_file = os.path.join(os.getcwd(), "tool", "yt_srt", "yt.mp3")
        if os.path.exists(mp3_file):
            print(f"  提示: MP3 檔案存在 ({os.path.getsize(mp3_file)} bytes)")
            print("  可能是轉錄過程失敗")
            # 清理 MP3
            os.remove(mp3_file)
            print("  已清理 MP3 檔案")

if __name__ == "__main__":
    test_srt_generation()