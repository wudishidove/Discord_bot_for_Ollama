import json
import discord
from discord.ext import commands
import requests
from langchain.memory import ConversationBufferMemory
import time
import asyncio
import os
import base64
from PIL import Image
from io import BytesIO
import re
# 導入 PDF 轉換函數
from to_html import convert_pdf_to_html
import pymupdf4llm
import pymupdf.pro

# 模型對應的最大 token 限制
MODEL_MAX_TOKENS = {
    "gemma2:latest": 8192,
    "phi4:latest": 8192,
    "Qwen2.5:7b": 4096,
    "mistral:latest": 8192,
    "llama3.2:latest": 131072,
    "llama3.2-vision:latest": 131072,
    "deepseek-r1:1.5b": 131072,
    "deepseek-r1:latest": 131072,
    "deepseek-r1:8b": 131072,
    "deepseek-r1:14b": 131072,
    "gemma3:12b": 131072,
    "gemma3:27b": 131072,
    "gemma3:nsfw2": 131072,
    "deepseek-r1:32b": 131072
}

# 初始化記憶功能（臨時使用，每次對話前都會重新加載頻道特定的記憶）
memory = ConversationBufferMemory(
    memory_key="history",
    return_messages=False,
    max_len=128000)  # 默認為 phi4 的最大 token 限制
# 紀錄下載的檔案內容
file_contents = []
# 載入配置文件
with open("config.json", "r") as config_file:
    config = json.load(config_file)

# Discord Bot Token
DISCORD_TOKEN = config["DISCORD_TOKEN"]
# Ollama API URL
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# 指定上線訊息的頻道 ID
STATUS_CHANNEL_ID = 1073495605286027267  # 替換為你的頻道 ID
ALLOWED_CHANNEL_IDS = config["ALLOWED_CHANNEL_IDS"]

# 初始化 Bot
intents = discord.Intents.default()
intents.messages = True  # 啟用訊息事件
intents.message_content = True  # 啟用訊息內容訪問
bot = commands.Bot(command_prefix="++", intents=intents)

# 儲存當前選擇的模型
current_model = "gemma3:27b"  # 預設模型


def is_in_allowed_channel(ctx):
    return ctx.channel.id in ALLOWED_CHANNEL_IDS


def update_memory_limit():
    """根據當前模型更新記憶最大 token 限制（只更新記憶大小，不影響內容）"""
    global memory
    max_tokens = MODEL_MAX_TOKENS.get(current_model, 8192)  # 默認為 8192
    # 只更新 token 限制，不會清除任何記憶內容
    memory = ConversationBufferMemory(
        memory_key="history",
        return_messages=False,
        max_len=max_tokens)
    print(f"[DEBUG] 記憶最大 token 限制更新為: {max_tokens}")


def save_history_to_file(channel_id):
    """將記憶歷史保存到頻道特定的 JSON 文件中"""
    if not channel_id:
        print("[WARNING] 未提供頻道 ID，無法保存記憶")
        return
        
    context = memory.load_memory_variables({})
    # 確保頻道目錄存在
    os.makedirs(str(channel_id), exist_ok=True)
    history_file_path = os.path.join(str(channel_id), "history.json")
    with open(history_file_path, "w", encoding="utf-8") as history_file:
        json.dump(context, history_file, ensure_ascii=False, indent=4)
    print(f"[DEBUG] 頻道 {channel_id} 的記憶已保存到 {history_file_path}")


def load_history_from_file(channel_id):
    """從頻道特定的 JSON 文件中載入記憶歷史"""
    global memory
    
    # 重置記憶（確保不會混合不同頻道的記憶）
    memory = ConversationBufferMemory(max_token_limit=MODEL_MAX_TOKENS.get(current_model, 8192))
    
    if not channel_id:
        print("[WARNING] 未提供頻道 ID，無法載入記憶")
        return False
        
    # 載入指定頻道的歷史記憶
    history_file_path = os.path.join(str(channel_id), "history.json")
    if os.path.exists(history_file_path):
        try:
            with open(history_file_path, "r", encoding="utf-8") as history_file:
                context = json.load(history_file)
                if "history" in context:
                    # 將歷史加載到記憶中
                    memory.save_context({"input": ""}, {"output": context["history"]})
                    print(f"[DEBUG] 已載入頻道 {channel_id} 的記憶歷史")
                    return True
        except Exception as e:
            print(f"[ERROR] 載入頻道 {channel_id} 的記憶歷史時出錯: {e}")
    else:
        print(f"[DEBUG] 頻道 {channel_id} 沒有歷史記憶文件，使用空記憶")
    
    return False


def trim_memory_with_ollama(channel_id):
    """使用 Ollama 模型裁剪記憶歷史"""
    if not channel_id:
        print("[WARNING] 未提供頻道 ID，無法裁剪記憶")
        return
        
    context = memory.load_memory_variables({})
    history = context.get("history", "")
    estimated_tokens = len(history.split())  # 簡單估算token數
    
    # 如果token數小於最大限制的50%，不需裁減
    if estimated_tokens < MODEL_MAX_TOKENS[current_model] * 0.5:
        print(f"[DEBUG] 當前token數（約{estimated_tokens}）不需裁減")
        return

    # 發送請求到 Ollama 模型
    trim_prompt = """請分析以下對話歷史，並進行重要內容提取：
    1. 保留關鍵的上下文信息
    2. 保持對話的連貫性
    3. 優先保留最近的對話
    4. 刪除重複或不重要的內容
    
    對話歷史：
    {history}
    
    請提供精簡後的重要對話：""".format(history=history)

    response = requests.post(
        OLLAMA_API_URL,
        json={"model": current_model, "prompt": trim_prompt},
        headers={"Content-Type": "application/json"}
    )

    if response.status_code == 200:
        try:
            result = response.json()
            trimmed_history = result.get("response", "")
            print("[DEBUG] 裁剪後的記憶歷史：", trimmed_history)
            print(f"[DEBUG] 裁剪前token數：{estimated_tokens}，裁剪後token數：{len(trimmed_history.split())}")

            # 更新記憶
            memory.save_context({"input": ""}, {"output": trimmed_history})
            save_history_to_file(channel_id)  # 保存裁剪後的記憶
        except json.JSONDecodeError as e:
            print("[ERROR] 無法解析裁剪回應：", e)
    else:
        print("[ERROR] Ollama API 返回錯誤：", response.status_code, response.text)


def process_user_input(user_input, channel_id):
    """處理用戶輸入，使用 Ollama API 並儲存記憶"""
    try:
        # 先加載頻道特定的記憶
        load_history_from_file(channel_id)
        
        # 檢查並可能裁減記憶
        context = memory.load_memory_variables({})
        current_tokens = len(context.get("history", "").split())  # 簡單估算token數
        
        # 如果超過最大限制的80%，觸發裁減
        if current_tokens > MODEL_MAX_TOKENS[current_model] * 0.8:
            print(f"[DEBUG] 當前token數（約{current_tokens}）超過限制的80%，觸發裁減")
            trim_memory_with_ollama(channel_id)
            # 重新載入裁減後的上下文
            context = memory.load_memory_variables({})

        prompt_with_memory = context.get("history", "") + f"\nUser: {user_input}\nBot:"

        print("[DEBUG] Prompt sent to Ollama API:", prompt_with_memory)
        start_time = time.time()
        full_prompt = f"如我用繁體中文問問題，也請你用繁體中文回答，並不使用任何特殊字符和表情：{prompt_with_memory}"
        prompt_with_memory = full_prompt
        # 發送到 Ollama API
        response = requests.post(
            OLLAMA_API_URL,
            json={"model": current_model, "prompt": prompt_with_memory},
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            try:
                # 計算處理時間
                elapsed_time = time.time() - start_time
                # 檢查是否為逐行 JSON 回應
                if '\n' in response.text:
                    full_response = ""
                    for line in response.text.splitlines():
                        try:
                            data = json.loads(line)
                            full_response += data.get("response", "")
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
                    memory.save_context({"input": user_input}, {
                                        "output": full_response})
                    print("[DEBUG] Full response processed:", full_response)
                    save_history_to_file(channel_id)  # 保存記憶歷史
                    return full_response.strip(), elapsed_time
                else:
                    # 單行 JSON 回應
                    result = response.json()
                    bot_response = result.get("response", "模型未返回內容，請稍後再試。")
                    # 更新記憶
                    memory.save_context({"input": user_input}, {
                                        "output": bot_response})
                    print("[DEBUG] Single-line response:", bot_response)
                    save_history_to_file(channel_id)  # 保存記憶歷史
                    return bot_response, elapsed_time
            except json.JSONDecodeError as e:
                raise Exception(f"JSON 解碼錯誤：{e}")
        else:
            raise Exception(
                f"Ollama API Error: {response.status_code} - {response.text}"
            )
    except Exception as e:
        raise Exception(f"處理請求時發生錯誤：{e}")

def handle_file_upload(filepath):
    """處理文件上傳，並返回文件內容"""
    try:
        ext = os.path.splitext(filepath)[1].lower()
        # 使用絕對路徑來獲取頻道 ID 和文件目錄
        abs_filepath = os.path.abspath(filepath)
        channel_dir = os.path.dirname(abs_filepath) # 獲取頻道目錄的絕對路徑
        channel_id = os.path.basename(channel_dir) # 假設頻道目錄名稱就是頻道 ID
        
        print(f"[DEBUG] 處理文件 (絕對路徑): {abs_filepath}")
        print(f"[DEBUG] 文件類型: {ext}")
        print(f"[DEBUG] 頻道目錄 (絕對路徑): {channel_dir}")
        print(f"[DEBUG] 頻道 ID: {channel_id}")
        
        # 讀取或初始化頻道的文件內容 (使用絕對路徑)
        file_contents_path = os.path.join(channel_dir, 'file_contents.json')
        
        try:
            if os.path.exists(file_contents_path):
                print(f"[DEBUG] 發現現有的 file_contents.json")
                with open(file_contents_path, 'r', encoding='utf-8') as f:
                    channel_file_contents = json.load(f)
            else:
                print(f"[DEBUG] 未找到 file_contents.json，將創建新的")
                channel_file_contents = []
        except Exception as e:
            print(f"[ERROR] 讀取文件內容列表時出錯: {e}")
            channel_file_contents = []
        
        # 處理圖片檔案
        if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp'):
            try:
                img_content = image_to_base64(abs_filepath) # 使用絕對路徑
                if img_content:
                    # 保存 base64 圖片列表到頻道資料夾 (使用絕對路徑)
                    base64_file_path = os.path.join(channel_dir, 'image_base64_list.json')
                    try:
                        # 讀取現有的 base64 列表（如果存在）
                        if os.path.exists(base64_file_path):
                            with open(base64_file_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                existing_data = data.get('images', [])
                                idle_count = data.get('idle_count', 0)
                        else:
                            existing_data = []
                            idle_count = 0
                        
                        # 重置 idle count 因為有新圖片
                        idle_count = 0
                        
                        # 添加新的 base64 圖片
                        image_data = {
                            'filename': os.path.basename(abs_filepath),
                            'base64_content': img_content,
                            'timestamp': time.time()
                        }
                        existing_data.append(image_data)
                        
                        # 保存更新後的列表和 idle count
                        with open(base64_file_path, 'w', encoding='utf-8') as f:
                            json.dump({
                                'images': existing_data,
                                'idle_count': idle_count
                            }, f, ensure_ascii=False, indent=4)
                        
                        print(f"[DEBUG] 已保存 base64 圖片到: {base64_file_path}")
                    except Exception as e:
                        print(f"[ERROR] 保存 base64 圖片列表時出錯: {e}")
                    
                    return True
            except Exception as e:
                print(f"[ERROR] 圖片處理錯誤: {e}")
                return False
        
        # 處理文字檔案
        else:
            file_content = read_file_content(abs_filepath) # 使用絕對路徑
            print(f"[DEBUG] 讀取到的文件內容: {file_content[:200]}...")  # 只打印前200個字符
            
            if file_content != "[Unsupported file type]":
                # 添加新的文件內容
                # 使用絕對路徑記錄檔案名稱
                new_content = f"檔案名稱: {abs_filepath}\n檔案內容: {file_content}"
                channel_file_contents.append(new_content)
                
                # 保存更新後的文件內容列表
                try:
                    with open(file_contents_path, 'w', encoding='utf-8') as f:
                        json.dump(channel_file_contents, f, ensure_ascii=False, indent=4)
                    print(f"[DEBUG] 成功寫入 file_contents.json")
                except Exception as e:
                    print(f"[ERROR] 寫入 file_contents.json 時出錯: {e}")
                    return False
                return True
            else:
                print(f"[WARNING] 不支援的檔案類型: {filepath}")
                return False
                
    except Exception as e:
        print(f"[ERROR] 檔案處理錯誤: {e}")
        return False

def image_idle_check(channel_id):
    """檢查並管理圖片快取
    - 每次被提及時增加閒置計數
    - 當圖片超過最大數量或閒置次數過多時清理
    - 清理時優先清理最舊的圖片
    """
    # 設定最大圖片數量和最大閒置次數
    MAX_IMAGES = 10
    MAX_IDLE_COUNT = 20
    
    try:
        base64_file_path = os.path.join(str(channel_id), 'image_base64_list.json')
        if os.path.exists(base64_file_path):
            with open(base64_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                image_data_list = data.get('images', [])
                idle_count = data.get('idle_count', 0)
            
            # 增加閒置計數
            idle_count += 1
            
            # 檢查閒置次數
            if idle_count > MAX_IDLE_COUNT and image_data_list:
                # 移除最舊的圖片
                image_data_list.pop(0)
                print("[DEBUG] 太久沒用，已移除最舊的圖片")
                print(f"[DEBUG] 當前快取圖片數量: {len(image_data_list)}, 閒置次數: {idle_count}")
            
            # 檢查圖片數量是否超過限制
            while len(image_data_list) > MAX_IMAGES:
                image_data_list.pop(0)  # 移除最舊的圖片
                print("[DEBUG] 圖片數量超過限制，已移除最舊的圖片")
            
            # 保存更新後的列表和 idle count
            with open(base64_file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'images': image_data_list,
                    'idle_count': idle_count
                }, f, ensure_ascii=False, indent=4)
            
    except Exception as e:
        print(f"[ERROR] 圖片快取管理錯誤: {e}")
        # 發生錯誤時重置狀態
        if os.path.exists(base64_file_path):
            with open(base64_file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'images': [],
                    'idle_count': 0
                }, f)


def image_to_base64(image_path):
    """將圖片轉換為 base64 編碼"""
    try:
        with Image.open(image_path) as img:
            buffered = BytesIO()
            # 確定圖片的格式
            image_format = img.format.lower() if img.format else 'png'
            
            # 根據圖片格式選擇保存格式
            save_format = {
                'jpeg': 'JPEG',
                'jpg': 'JPEG',
                'gif': 'GIF',
                'bmp': 'BMP',
                'tiff': 'TIFF',
                'png': 'PNG'
            }.get(image_format, 'PNG')
            
            img.save(buffered, format=save_format)
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"[ERROR] 圖片轉換錯誤 {image_path}: {e}")
        return None
def read_pdf_content(filepath):
    # 讓 to_markdown() 回傳每一頁的結構化資料，並提取圖片
    chunks = pymupdf4llm.to_markdown(
        doc= filepath,
        write_images=True,
        image_format='jpg',
        image_path="images",
        page_chunks=True
    )

    # 取得所有頁面中圖片的檔案名稱
    pdf_text=''
    image_filenames = []
    for page in chunks:
        pdf_text += f'page {page["metadata"]["page"]}:\n'
        pdf_text += f'{page["text"]}'
    # 利用正則表達式抓取所有符合 Markdown 圖片語法的部分
    image_filenames = re.findall(r'!\[\]\((images/[^)]+\.jpg)\)', pdf_text)

    return pdf_text, image_filenames

def read_file_content(filepath):
    """讀取文件內容"""
    ext = os.path.splitext(filepath)[1].lower()
    
    try:
        if ext == '.txt':
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                return content if content.strip() else "[Empty file]"
        elif ext == '.pdf':
            # 確保 PDF 文件路徑是絕對路徑
            pdf_filepath = os.path.abspath(filepath)
            
            # PDF to markdown基礎轉換
            # md_text = pymupdf4llm.to_markdown(pdf_filepath)
            md_text, image_filenames = read_pdf_content(pdf_filepath)
            return md_text if md_text.strip() else "[Empty file]"

            # # 獲取 PDF 文件所在的頻道目錄
            # channel_dir = os.path.dirname(pdf_filepath)
            
            # # 設定輸出的 HTML 文件的絕對路徑
            # html_filename = os.path.splitext(os.path.basename(pdf_filepath))[0] + '.html'
            # html_filepath = os.path.abspath(os.path.join(channel_dir, html_filename))
            
            # print("debug, pdf_filepath:", pdf_filepath)
            # print("debug, html_filepath:", html_filepath)
            
            # # 轉換 PDF 到 HTML
            # if convert_pdf_to_html(pdf_filepath, html_filepath):
            #     # 如果轉換成功,讀取 HTML 內容
            #     try:
            #         with open(html_filepath, 'r', encoding='utf-8') as f:
            #             content = f.read()
            #         # 刪除生成的 HTML 文件
            #         # try:
            #         #     os.remove(html_filepath)
            #         # except:
            #         #     pass
            #         return content
            #     except Exception as e:
            #         return f"[Error reading converted HTML file: {str(e)}]"
            # else:
            #     return "[PDF conversion failed]"
        else:
            return "[Unsupported file type]"
    except UnicodeDecodeError:
        return "[File encoding error]"
    except Exception as e:
        print(f"[ERROR] 檔案讀取錯誤 {filepath}: {e}")
        return f"[Error reading file: {str(e)}]"

@bot.event
async def on_ready():
    """當 Bot 上線時觸發"""
    print("Bot 已成功啟動！")
    print(f"已登入 Discord 帳戶：{bot.user}")

    # 發送上線通知到所有允許的頻道
    for channel_id in ALLOWED_CHANNEL_IDS:
        channel = bot.get_channel(channel_id)
        if channel:
            try:
                await channel.send("🤖 Bot 已上線，準備接收指令！")
            except Exception as e:
                print(f"發送上線通知到頻道 {channel_id} 時出現錯誤：{e}")
        else:
            print(f"無法找到頻道 ID：{channel_id}")

bot.remove_command("help")


@bot.command()
@commands.check(is_in_allowed_channel)
async def help(ctx):
    """顯示可用指令清單"""
    help_message = """
🤖 **可用指令清單**:
1. **++chat <訊息>** - 與 Bot 進行對話。
2. **++setmodel <模型名稱>** - 選擇要使用的模型。
3. **++help** - 顯示此幫助訊息。
4. **++clean_history** - 清除當前頻道的記憶歷史和檔案。

📘 **可用模型**:
- 預設模型: gemma3:27b
- gemma3:12b    快速回答，一般使用，圖片理解勉強
- gemma3:27b    回答速度慢，能力較好，圖片理解強(自帶英文OCR)
- gemma3:nsfw2  NSFW魔改版,有時候會胡言亂語
- deepseek-r1:32b 高等複雜度 會輸出推理(思考)過程
- 
🎯 **使用方式**:
- 輸入 `++chat 你好` 與 Bot 開始對話。
- 輸入 `++setmodel gemma3:27b` 切換到指定的模型。
- 輸入 `++help` 查看可用指令清單。
- 輸入 `++clean_history` 清除當前頻道的記憶歷史和檔案。
"""
    await ctx.send(help_message)


@commands.check(is_in_allowed_channel)
@bot.command(name="chat")
async def chat(ctx, *, user_input: str):
    """處理聊天指令"""
    try:
        print(f"收到指令：{user_input}")
        thinking_message = await ctx.send(f"已收到：{user_input}，正在思考...")

        # 生成 Ollama 回應，傳入頻道 ID
        response, _ = process_user_input(user_input, ctx.channel.id)
        response = response.strip()
        await thinking_message.delete()

        if response and response != "模型未返回內容，請稍後再試。":
            await ctx.send(response)
        else:
            await ctx.send("模型未返回內容或發生錯誤，請稍後再試。")
    except Exception as e:
        print("[ERROR] Exception in chat command:", e)
        await ctx.send(f"出現錯誤：{e}")


@bot.command()
@commands.check(is_in_allowed_channel)
async def setmodel(ctx, model_name: str):
    """設定使用的模型"""
    global current_model
    available_models = ["gemma3:nsfw2", "gemma3:27b","gemma3:12b","deepseek-r1:32b"]
    if model_name in available_models:
        current_model = model_name
        update_memory_limit()  # 更新記憶限制
        print("[DEBUG] Model switched to:", model_name)
        await ctx.send(f"已將模型切換為 `{model_name}`，記憶最大限制更新為 {MODEL_MAX_TOKENS[model_name]} tokens。")
    else:
        print("[ERROR] Invalid model name:", model_name)
        await ctx.send(f"無效的模型名稱！可用模型：{', '.join(available_models)}")


@bot.command()
@commands.check(is_in_allowed_channel)
async def clean_history(ctx):
    """清除頻道的記憶歷史和下載的檔案"""
    global memory
    
    # 清除記憶歷史
    memory = ConversationBufferMemory(
        max_token_limit=MODEL_MAX_TOKENS.get(current_model, 8192))
    print(f"[DEBUG] 頻道 {ctx.channel.id} 的記憶歷史已清除")
    
    # 清除歷史記憶文件
    history_file_path = os.path.join(str(ctx.channel.id), "history.json")
    if os.path.exists(history_file_path):
        try:
            os.unlink(history_file_path)
            print(f"[DEBUG] 已刪除記憶歷史文件: {history_file_path}")
        except Exception as e:
            print(f"[ERROR] 刪除記憶歷史文件時出錯 {history_file_path}: {e}")
    
    # 清除 userFile 目錄中的所有檔案
    try:
        userfile_dir = str(ctx.channel.id)
        if os.path.exists(userfile_dir):
            for filename in os.listdir(userfile_dir):
                file_path = os.path.join(userfile_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        print(f"[DEBUG] 已刪除檔案: {file_path}")
                except Exception as e:
                    print(f"[ERROR] 刪除檔案時出錯 {file_path}: {e}")
            print(f"[DEBUG] 頻道 {ctx.channel.id} 的檔案目錄已清空")
    except Exception as e:
        print(f"[ERROR] 清理頻道 {ctx.channel.id} 的檔案目錄時出錯: {e}")
    
    await ctx.send(f"頻道 {ctx.channel.name} 的記憶歷史和下載的檔案已成功清除！")




async def stream_response(user_input, channel_id):
    """
    使用流式請求從 Ollama API 取得部分回應，並每兩秒 yield 當前累積內容
    """
    # 加載頻道特定的記憶
    load_history_from_file(channel_id)
    
    # 整合上下文記憶
    context = memory.load_memory_variables({})
    current_tokens = len(context.get("history", "").split())  # 簡單估算token數
    
    # 如果超過最大限制的80%，觸發裁減
    if current_tokens > MODEL_MAX_TOKENS[current_model] * 0.8:
        print(f"[DEBUG] 當前token數（約{current_tokens}）超過限制的80%，觸發裁減")
        trim_memory_with_ollama(channel_id)
        # 重新載入裁減後的上下文
        context = memory.load_memory_variables({})

    prompt_with_memory = context.get("history", "") + f"\nUser: {user_input}\nBot:"
    
    
    full_prompt = f"""如我用繁體中文問問題，也請你用繁體中文，且老實回答(不知道就老實說不知道，
    除非我特別請你天馬行空發揮創意)，並不使用任何特殊字符和表情，下面開始是我的問題。{prompt_with_memory}"""
    print("[DEBUG] Prompt sent to Ollama API:", full_prompt)
    # 從 JSON 檔案讀取圖片列表
    base64_images = []
    base64_file_path = os.path.join(str(channel_id), 'image_base64_list.json')
    if os.path.exists(base64_file_path):
        try:
            with open(base64_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                image_data_list = data.get('images', [])
                base64_images = [item['base64_content'] for item in image_data_list]
                print(f"[DEBUG] 已從 {base64_file_path} 讀取 {len(base64_images)} 張圖片")
        except Exception as e:
            print(f"[ERROR] 讀取圖片列表時出錯: {e}")
    
    # 使用 requests 的 stream 模式 (run_in_executor 避免阻塞)
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: requests.post(
            OLLAMA_API_URL,
            json={
                "model": current_model,
                "prompt": full_prompt,
                "images": base64_images,
                "stream": True
            },
            headers={"Content-Type": "application/json"},
        )
    )
    
    buffer = ""
    last_update = time.time()
    
    # 逐行處理流式回應
    for line in response.iter_lines(decode_unicode=True):
        if line:
            try:
                data = json.loads(line)
                new_text = data.get("response", "")
                buffer += new_text
                # 每0.5秒 yield 當前累積結果
                if time.time() - last_update >= 0.5:
                    yield buffer
                    last_update = time.time()
                if data.get("done", False):
                    break
            except json.JSONDecodeError:
                continue
    yield buffer

@bot.event
async def on_message(message):
    # 忽略自己與非允許頻道訊息
    if message.author == bot.user or message.channel.id not in ALLOWED_CHANNEL_IDS:
        return

    # 創建 userFile 目錄（如果不存在）
    os.makedirs(str(message.channel.id), exist_ok=True)
    
    # 處理附加檔案
    if message.attachments:
        # 發送初始處理訊息
        processing_msg = await message.channel.send("📂 正在處理上傳的檔案...")
        
        # 用於記錄處理結果的列表
        processing_results = []
        
        for attachment in message.attachments:
            # 設定儲存路徑
            file_path = os.path.join(str(message.channel.id), attachment.filename)
            # 下載檔案
            await attachment.save(file_path)
            print(f"[DEBUG] 已下載檔案: {file_path}")
            
            # 讀取檔案內容
            try:
                result = handle_file_upload(file_path)
                if result:
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp'):
                        processing_results.append(f"✅ 圖片 `{attachment.filename}` 處理成功")
                    else:
                        processing_results.append(f"✅ 文件 `{attachment.filename}` 處理成功")
                else:
                    processing_results.append(f"❌ 檔案 `{attachment.filename}` 處理失敗")
            except Exception as e:
                print(f"[ERROR] 讀取檔案錯誤: {e}")
                processing_results.append(f"❌ 檔案 `{attachment.filename}` 處理出錯: {str(e)}")

        # 更新處理訊息，顯示所有檔案的處理結果
        result_message = "📋 檔案處理結果：\n" + "\n".join(processing_results)
        await processing_msg.edit(content=result_message)

    # 當訊息提及 Bot 時
    if bot.user.mentioned_in(message):
        image_idle_check(message.channel.id)
        user_input = message.content.replace(bot.user.mention, "").strip()
        
        # 讀取頻道的文件內容
        file_contents_path = os.path.join(str(message.channel.id), 'file_contents.json')
        channel_file_contents = []
        if os.path.exists(file_contents_path):
            try:
                with open(file_contents_path, 'r', encoding='utf-8') as f:
                    channel_file_contents = json.load(f)
            except Exception as e:
                print(f"[ERROR] 讀取文件內容列表時出錯: {e}")
        
        # 如果有檔案，將檔案內容加入到用戶輸入中
        if channel_file_contents:
            file_content_text = "\n\n".join(channel_file_contents)
            user_input = f"{user_input}\n\n用戶上傳的檔案：\n{file_content_text}"
            print(f"[DEBUG] 已讀取檔案內容+使用者問題: {user_input}")
        
        if not user_input and not channel_file_contents:
            return
        
        # 先發送一則初始訊息，並用一個列表保存所有訊息（後續依序更新）
        thinking_messages = []
        first_msg = await message.channel.send("🤖 收到提及，正在思考...")
        thinking_messages.append(first_msg)
        final_response = ""  # 儲存最終完整回應
        try:
            # 非同步迭代器取得逐步更新的回應
            async for partial in stream_response(user_input, message.channel.id):
                final_response = partial  # 更新最新累積回應
                # 將累積的回應切割為多個不超過2000字的段落
                segments = [partial[i:i+2000] for i in range(0, len(partial), 2000)]
                for idx, seg in enumerate(segments):
                    if idx < len(thinking_messages):
                        # 編輯已存在的訊息
                        try:
                            await thinking_messages[idx].edit(content=seg)
                        except Exception as e:
                            print(f"[DEBUG] 編輯訊息失敗: {e}")
                    else:
                        # 發送新訊息
                        new_msg = await message.channel.send(seg)
                        thinking_messages.append(new_msg)
                # 等待0.1秒再處理下一次更新
                await asyncio.sleep(0.1)
            # 回應全部取得完畢後，記錄回應歷史
            memory.save_context({"input": user_input}, {"output": final_response})
            print("[DEBUG] Full response processed:", final_response)
            save_history_to_file(message.channel.id)  # 保存頻道特定的記憶歷史
        except Exception as e:
            # 發生錯誤時更新最後一則訊息
            await thinking_messages[-1].edit(content=f"❗️ 發生錯誤：{e}")

    # 處理其他指令
    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
