import json
import discord
from discord.ext import commands
import requests
from langchain.memory import ConversationBufferMemory
import time
import asyncio
import os
import base64
# from PIL import Image
from io import BytesIO
import re
import glob
import ollama
# 導入 PDF 轉換函數
from ollama_tool import *
import global_var as GV
import pymupdf4llm
import pymupdf.pro
pymupdf.pro.unlock()

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
    "deepseek-r1:32b": 131072,
    "qwq": 131072,
    "mistral-small3.2:24b": 131072,
    "gpt-oss:latest": 131072
}
# calling tools
tools = [
    generate_function_description(get_local_time),
    generate_function_description(google_search),
    # generate_function_description(advanced_web_search),
    generate_function_description(fetch_url_content),
    generate_function_description(do_math),
    generate_function_description(get_youtube_srt),
]
# Ollama client
client = ollama.Client(host="http://localhost:11434")

def ensure_model_available(model_name: str) -> str:
    """確保模型可用；若不存在則嘗試拉取，不行則回退到 gpt-oss:latest。

    回傳實際可用的模型名稱。
    """
    try:
        # 先檢查當前已安裝模型
        installed = []
        try:
            listed = client.list()
            if isinstance(listed, dict) and 'models' in listed:
                installed = [m.get('name') for m in listed.get('models', []) if isinstance(m, dict)]
        except Exception:
            installed = []

        if model_name not in installed:
            try:
                client.pull(model=model_name, stream=False)
            except Exception:
                pass

        # 再次確認
        try:
            listed = client.list()
            if isinstance(listed, dict) and 'models' in listed:
                installed = [m.get('name') for m in listed.get('models', []) if isinstance(m, dict)]
        except Exception:
            installed = []

        if model_name in installed:
            return model_name

        # 回退到預設可用模型
        fallback_model = "gpt-oss:latest"
        if fallback_model not in installed:
            try:
                client.pull(model=fallback_model, stream=False)
            except Exception:
                pass
        return fallback_model
    except Exception:
        # 發生非預期錯誤時，最後仍回退
        return "gpt-oss:latest"

def get_channel_dir(channel_id):
    """獲取頻道專用的儲存目錄路徑"""
    return os.path.join("save_history", str(channel_id))

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



def is_in_allowed_channel(ctx):
    return ctx.channel.id in ALLOWED_CHANNEL_IDS


def update_memory_limit():
    """根據當前模型更新記憶最大 token 限制（只更新記憶大小，不影響內容）"""
    global memory
    max_tokens = MODEL_MAX_TOKENS.get(GV.current_model, 8192)  # 默認為 8192
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
    channel_dir = get_channel_dir(channel_id)
    os.makedirs(channel_dir, exist_ok=True)
    history_file_path = os.path.join(channel_dir, "history.json")
    with open(history_file_path, "w", encoding="utf-8") as history_file:
        json.dump(context, history_file, ensure_ascii=False, indent=4)
    print(f"[DEBUG] 頻道 {channel_id} 的記憶已保存到 {history_file_path}")


def load_history_from_file(channel_id):
    """從頻道特定的 JSON 文件中載入記憶歷史"""
    global memory
    
    
    # 重置記憶（確保不會混合不同頻道的記憶）
    memory = ConversationBufferMemory(max_token_limit=MODEL_MAX_TOKENS.get(GV.current_model, 8192))
    
    if not channel_id:
        print("[WARNING] 未提供頻道 ID，無法載入記憶")
        return False
        
    # 載入指定頻道的歷史記憶
    channel_dir = get_channel_dir(channel_id)
    history_file_path = os.path.join(channel_dir, "history.json")
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
    if estimated_tokens < MODEL_MAX_TOKENS.get(GV.current_model, 8192) * 0.5:
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

    usable_model = ensure_model_available(GV.current_model)
    response = requests.post(
        OLLAMA_API_URL,
        json={"model": usable_model, "prompt": trim_prompt},
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
        if current_tokens > MODEL_MAX_TOKENS.get(GV.current_model, 8192) * 0.8:
            print(f"[DEBUG] 當前token數（約{current_tokens}）超過限制的80%，觸發裁減")
            trim_memory_with_ollama(channel_id)
            # 重新載入裁減後的上下文
            context = memory.load_memory_variables({})

        prompt_with_memory = context.get("history", "") + f"\nUser: {user_input}\nBot:"

        print("[DEBUG] Prompt sent to Ollama API:", prompt_with_memory)
        start_time = time.time()
        full_prompt = f"如我用繁體中文問問題，也請你用繁體中文回答，並不使用任何特殊字符和表情：{prompt_with_memory}"
        prompt_with_memory = full_prompt
        prompt_with_memory = handle_promt_history(context)
        prompt_with_memory.append({"role": "user", "content": user_input})
        
        usable_model = ensure_model_available(GV.current_model)
        response = client.chat(
            model=usable_model,
            messages=prompt_with_memory,
            stream=False  # 啟用串流模式
        )
        # 計算處理時間
        elapsed_time = time.time() - start_time
        
        # ollama.Client().chat() 返回的是 ChatResponse 對象
        # 從回應中獲取內容
        if response and 'message' in response and 'content' in response['message']:
            bot_response = response['message']['content']
            # 更新記憶
            memory.save_context({"input": user_input}, {"output": bot_response})
            print("[DEBUG] Response processed:", bot_response)
            save_history_to_file(channel_id)  # 保存記憶歷史
            return bot_response.strip(), elapsed_time
        else:
            raise Exception("模型未返回有效內容，請稍後再試。")
    except Exception as e:
        raise Exception(f"處理請求時發生錯誤：{e}")

def handle_file_upload(filepath):
    """處理文件上傳，並返回文件內容"""
    try:
        ext = os.path.splitext(filepath)[1].lower()
        # 使用絕對路徑來獲取頻道 ID 和文件目錄
        abs_filepath = os.path.abspath(filepath)
        channel_dir_full = os.path.dirname(abs_filepath) # 獲取頻道目錄的絕對路徑
        channel_id = os.path.basename(channel_dir_full) # 假設頻道目錄名稱就是頻道 ID
        
        # 使用新的統一路徑結構
        channel_dir = get_channel_dir(channel_id)
        
        print(f"[DEBUG] 處理文件 (絕對路徑): {abs_filepath}")
        print(f"[DEBUG] 文件類型: {ext}")
        print(f"[DEBUG] 頻道目錄: {channel_dir}")
        print(f"[DEBUG] 頻道 ID: {channel_id}")
        
        # 讀取或初始化頻道的文件內容
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
                # 重置閒置計數
                os.makedirs(channel_dir, exist_ok=True)
                idle_count_path = os.path.join(channel_dir, 'idle_count.json')
                try:
                    with open(idle_count_path, 'w', encoding='utf-8') as f:
                        json.dump({'idle_count': 0}, f, ensure_ascii=False, indent=4)
                    print(f"[DEBUG] 已重置閒置計數")
                except Exception as e:
                    print(f"[ERROR] 重置閒置計數時出錯: {e}")
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
                
                # 確保目錄存在並保存更新後的文件內容列表
                try:
                    os.makedirs(channel_dir, exist_ok=True)
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
    MAX_IDLE_COUNT = 10
    
    try:
        # 讀取或初始化閒置計數
        channel_dir = get_channel_dir(channel_id)
        idle_count_path = os.path.join(channel_dir, 'idle_count.json')
        if os.path.exists(idle_count_path):
            with open(idle_count_path, 'r', encoding='utf-8') as f:
                idle_count = json.load(f).get('idle_count', 0)
        else:
            idle_count = 0
        
        # 增加閒置計數
        idle_count += 1
        
        # 獲取所有圖片檔案
        image_dir = channel_dir
        image_files = []
        for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
            image_files.extend(glob.glob(os.path.join(image_dir, f"*{ext}")))
            image_files.extend(glob.glob(os.path.join(image_dir, f"*{ext.upper()}")))
        
        # 根據修改時間排序圖片（最舊的在前）
        image_files.sort(key=lambda x: os.path.getmtime(x))
        
        # 檢查閒置次數
        if idle_count > MAX_IDLE_COUNT and image_files:
            # 移除最舊的圖片
            try:
                os.remove(image_files[0])
                print(f"[DEBUG] 太久沒用，已移除最舊的圖片: {image_files[0]}")
                image_files.pop(0)  # 從列表中移除
            except Exception as e:
                print(f"[ERROR] 刪除閒置圖片時出錯: {e}")
        
        # 檢查圖片數量是否超過限制
        while len(image_files) > MAX_IMAGES:
            try:
                os.remove(image_files[0])
                print(f"[DEBUG] 圖片數量超過限制，已移除最舊的圖片: {image_files[0]}")
                image_files.pop(0)
            except Exception as e:
                print(f"[ERROR] 刪除超量圖片時出錯: {e}")
                break
        
        # 確保目錄存在
        os.makedirs(channel_dir, exist_ok=True)
        # 保存更新後的閒置計數
        with open(idle_count_path, 'w', encoding='utf-8') as f:
            json.dump({'idle_count': idle_count}, f, ensure_ascii=False, indent=4)
            
    except Exception as e:
        print(f"[ERROR] 圖片快取管理錯誤: {e}")
        # 發生錯誤時重置閒置計數
        if os.path.exists(idle_count_path):
            with open(idle_count_path, 'w', encoding='utf-8') as f:
                json.dump({'idle_count': 0}, f, ensure_ascii=False, indent=4)


# def image_to_base64(image_path):
#     """將圖片轉換為 base64 編碼"""
#     try:
#         with Image.open(image_path) as img:
#             buffered = BytesIO()
#             # 確定圖片的格式
#             image_format = img.format.lower() if img.format else 'png'
            
#             # 根據圖片格式選擇保存格式
#             save_format = {
#                 'jpeg': 'JPEG',
#                 'jpg': 'JPEG',
#                 'gif': 'GIF',
#                 'bmp': 'BMP',
#                 'tiff': 'TIFF',
#                 'png': 'PNG'
#             }.get(image_format, 'PNG')
            
#             img.save(buffered, format=save_format)
#             return base64.b64encode(buffered.getvalue()).decode('utf-8')
#     except Exception as e:
#         print(f"[ERROR] 圖片轉換錯誤 {image_path}: {e}")
#         return None
def read_pdf_content(filepath):
    # 讓 to_markdown() 回傳每一頁的結構化資料，並提取圖片
    channel_dir_full = os.path.dirname(filepath) # 獲取頻道目錄的絕對路徑
    channel_id = os.path.basename(channel_dir_full) # 假設頻道目錄名稱就是頻道 ID
    
    # 使用新的統一路徑結構
    channel_dir = get_channel_dir(channel_id)
    pdf_images_path = os.path.join(channel_dir, "pdf_images")
    
    chunks = pymupdf4llm.to_markdown(
        doc=filepath,
        write_images=True,
        image_format='jpg',
        image_path=pdf_images_path,  # 使用完整路徑
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
       
        elif ext == '.pdf'or ext == '.doc' or ext == '.docx':
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
                pass
                # await channel.send("🤖 Bot 已上線，準備接收指令！")
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
- 預設模型: gpt-oss:latest
- gemma3:12b    快速回答，一般使用，圖片理解勉強
- gemma3:27b    回答速度較慢，能力較好，圖片理解較強
- gemma3:nsfw2  NSFW 魔改版
- deepseek-r1:32b 高等複雜度，會輸出推理(思考)過程
- qwq  更強的推理模型
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
    available_models = ["gpt-oss:latest", "gemma3:nsfw2", "gemma3:27b","gemma3:12b","deepseek-r1:32b"]
    if model_name in available_models:
        GV.current_model = model_name
        update_memory_limit()  # 更新記憶限制
        print("[DEBUG] Model switched to:", model_name)
        await ctx.send(f"已將模型切換為 `{model_name}`，記憶最大限制更新為 {MODEL_MAX_TOKENS.get(model_name, 8192)} tokens。")
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
        max_token_limit=MODEL_MAX_TOKENS.get(GV.current_model, 8192))
    print(f"[DEBUG] 頻道 {ctx.channel.id} 的記憶歷史已清除")
    
    # 使用新的路徑結構
    channel_dir = get_channel_dir(ctx.channel.id)
    
    # 清除歷史記憶文件
    history_file_path = os.path.join(channel_dir, "history.json")
    if os.path.exists(history_file_path):
        try:
            os.unlink(history_file_path)
            print(f"[DEBUG] 已刪除記憶歷史文件: {history_file_path}")
        except Exception as e:
            print(f"[ERROR] 刪除記憶歷史文件時出錯 {history_file_path}: {e}")
    
    # 清除 save_history 目錄中的所有檔案
    try:
        if os.path.exists(channel_dir):
            for filename in os.listdir(channel_dir):
                file_path = os.path.join(channel_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                        print(f"[DEBUG] 已刪除檔案: {file_path}")
                    elif os.path.isdir(file_path):
                        # 刪除子目錄（如 pdf_images）
                        import shutil
                        shutil.rmtree(file_path)
                        print(f"[DEBUG] 已刪除目錄: {file_path}")
                except Exception as e:
                    print(f"[ERROR] 刪除檔案時出錯 {file_path}: {e}")
            print(f"[DEBUG] 頻道 {ctx.channel.id} 的檔案目錄已清空")
    except Exception as e:
        print(f"[ERROR] 清理頻道 {ctx.channel.id} 的檔案目錄時出錯: {e}")
    
    await ctx.send(f"頻道 {ctx.channel.name} 的記憶歷史和下載的檔案已成功清除！")


def handle_promt_history(context):
    """處理歷史對話，轉換為 messages 格式"""
    # 初始化消息歷史
    messages = [
        {"role": "system", "content": """如果使用者用繁體中文問你，也請你用繁體中文回答。
        遇到數學問題時，請先嘗試用tool進行計算。看到youtube影片請用get_youtube_srt進行摘要。
        另外，遇到不會的問題時請使用tool進行google_search並fetch_url進行閱讀，最終回答時須附上參考網站的href。
        請不要使用任何特殊字符和表情。"""},
    ]
    
    # 解析並添加歷史記憶到消息中
    history_content = context.get("history", "")
    if history_content:
        # 分割歷史內容為獨立的對話回合
        # 使用 "Human:" 作為分隔點來分割對話
        conversations = history_content.split("Human: ")
        
        # 跳過第一個空元素（如果存在）
        conversations = [conv for conv in conversations if conv.strip()]
        
        for conv in conversations:
            # 分割用戶輸入和 AI 回應
            parts = conv.split("AI: ", 1)
            if len(parts) == 2:
                user_input, ai_response = parts
                
                # 清理並添加用戶訊息
                user_input = user_input.strip()
                if user_input:
                    messages.append({
                        "role": "user",
                        "content": user_input
                    })
                
                # 清理並添加 AI 回應
                ai_response = ai_response.strip()
                if ai_response:
                    messages.append({
                        "role": "assistant",
                        "content": ai_response
                    })
    
    
    return messages

async def stream_response(user_input, channel_id,thinking_messages):
    """
    使用流式請求從 Ollama API 取得部分回應，並每兩秒 yield 當前累積內容
    """
    # 加載頻道特定的記憶
    load_history_from_file(channel_id)
    
    # 整合上下文記憶
    context = memory.load_memory_variables({})
    current_tokens = len(context.get("history", "").split())  # 簡單估算token數
    
    # 如果超過最大限制的80%，觸發裁減
    if current_tokens > MODEL_MAX_TOKENS.get(GV.current_model, 8192) * 0.8:
        print(f"[DEBUG] 當前token數（約{current_tokens}）超過限制的80%，觸發裁減")
        trim_memory_with_ollama(channel_id)
        # 重新載入裁減後的上下文
        context = memory.load_memory_variables({})

    # 添加歷史記憶到消息中
    messages = handle_promt_history(context)

    # 直接從 save_history 目錄讀取所有圖片檔案
    image_dir = get_channel_dir(channel_id)
    image_set = set()
    for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
        image_files = glob.glob(os.path.join(image_dir, f"*{ext}"))
        image_files.extend(glob.glob(os.path.join(image_dir, f"*{ext.upper()}")))
        # 將反斜線轉換為正斜線
        image_files = [path.replace('\\', '/') for path in image_files]
        image_set.update(image_files)
    image_list = sorted(image_set)
    
    # pdf img
    channel_dir = get_channel_dir(channel_id)
    pdf_image_dir = os.path.join(channel_dir, "pdf_images")
    if os.path.exists(pdf_image_dir):  # 確認 pdf_images 目錄存在
        pdf_image_set = set()
        for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
            pdf_files = glob.glob(os.path.join(pdf_image_dir, f"*{ext}"))
            pdf_files.extend(glob.glob(os.path.join(pdf_image_dir, f"*{ext.upper()}")))
            # 將反斜線轉換為正斜線
            pdf_files = [path.replace('\\', '/') for path in pdf_files]
            pdf_image_set.update(pdf_files)
        image_list.extend(sorted(pdf_image_set))  # 將 PDF 圖片加入主列表
    
    print(f"[DEBUG] 使用 {len(image_list)} 張圖片，包含一般圖片和 PDF 圖片")
    if image_list:
        print(f"[DEBUG] 圖片列表: {image_list}")
    
    # 添加用戶輸入
    messages.append({"role": "user", "content": user_input,"images": image_list})
    
    # 檢查是否需要使用工具（關鍵字檢測）
    need_tools = any(keyword in user_input.lower() for keyword in [
        '搜尋', '搜索', '查詢', '天氣', '時間', '計算', '數學', '幾點', '現在', '今天',
        'search', 'weather', 'time', 'calculate', 'math', 'what time', 'current', 'today','https://','http://'
    ])
    
    try:
        client = ollama.Client(host="http://localhost:11434")
        print("[DEBUG] input messages:", json.dumps(messages, ensure_ascii=False, indent=2))
        
        if need_tools:
            print(f"[DEBUG] 檢測到需要工具的關鍵字，使用工具模式")
            # 直接使用帶工具的流式調用
            while True:
                usable_model = ensure_model_available(GV.current_model)
                stream = client.chat(
                    model=usable_model,
                    messages=messages,
                    tools=tools,
                    stream=True
                )
                
                buffer = ""
                last_update_time = time.time()
                tool_calls = []
                
                for chunk in stream:
                    if 'message' in chunk:
                        if 'content' in chunk['message']:
                            new_text = chunk['message']['content']
                            if new_text:
                                buffer += new_text
                                # 每0.5秒更新一次，確保逐步輸出
                                if time.time() - last_update_time >= 0.5 and buffer:
                                    yield buffer
                                    last_update_time = time.time()
                        
                        # 處理工具調用
                        if 'tool_calls' in chunk['message']:
                            for tool_call in chunk['message']['tool_calls']:
                                if tool_call not in tool_calls:
                                    tool_calls.append(tool_call)
                
                # 確保最後的內容也被傳送出去
                if buffer:
                    yield buffer
                
                # 處理工具調用
                if tool_calls:
                    print(f"[DEBUG] 發現工具調用: {len(tool_calls)} 個")
                    
                    for tool_call in tool_calls:
                        try:
                            tool_name = tool_call['function']['name']
                            arguments_str = tool_call['function']['arguments']
                            
                            try:
                                arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                            except json.JSONDecodeError:
                                print(f"[ERROR] 無法解析工具參數: {arguments_str}")
                                arguments = {}
                            
                            # 顯示工具執行狀態
                            yield buffer + f"\n\n🔧 正在使用工具：{tool_name}"
                            
                            # 執行工具
                            print(f"[DEBUG] 調用工具: {tool_name} 參數: {arguments}")
                            result = globals()[tool_name](**arguments)
                            print(f"[DEBUG] 工具結果: {result[:1000]}...") if isinstance(result, str) and len(result) > 1000 else print(f"[DEBUG] 工具結果: {result}")
                            
                            messages.append({"role": "tool", "content": result})
                            
                            # 顯示工具執行結果
                            tool_result_preview = result[:300] + "..." if len(str(result)) > 300 else str(result)
                            yield buffer + f"\n\n🔧 工具 {tool_name} 執行結果：\n{tool_result_preview}"
                            
                        except Exception as e:
                            error_msg = f"工具 {tool_name} 執行錯誤: {str(e)}"
                            print(f"[ERROR] {error_msg}")
                            yield buffer + f"\n\n❌ {error_msg}"
                            messages.append({"role": "tool", "content": f"Error: {str(e)}"})

                    # 檢查工具回應是否已滿足需求
                    if not check_if_tool_is_still_needed(messages):
                        print(f"[DEBUG] 工具回應已滿足需求，切換到一般對話模式")
                        messages.append({"role": "system", "content": """依照使用者的問題和工具的結果進行完整的回答，不能用...結尾"""})
                        # 使用包含工具結果的 messages 進行最終回應
                        usable_model = ensure_model_available(GV.current_model)
                        stream = client.chat(
                            model=usable_model,
                            messages=messages,
                            stream=True
                        )

                        final_buffer = ""
                        last_update_time = time.time()

                        for chunk in stream:
                            if 'message' in chunk and 'content' in chunk['message']:
                                new_text = chunk['message']['content']
                                if new_text:
                                    final_buffer += new_text
                                    # 每0.5秒更新一次，確保逐步輸出
                                    if time.time() - last_update_time >= 0.5 and final_buffer:
                                        yield final_buffer
                                        last_update_time = time.time()

                        # 確保最後的內容也被傳送出去
                        if final_buffer:
                            yield final_buffer
                        break  # 跳出 while True 循環
                else:
                    # 沒有工具調用，結束循環
                    break
        else:
            print(f"[DEBUG] 使用一般對話模式")
            # 使用簡單的流式輸出
            usable_model = ensure_model_available(GV.current_model)
            stream = client.chat(
                model=usable_model,
                messages=messages,
                stream=True
            )
            
            buffer = ""
            last_update_time = time.time()
            
            for chunk in stream:
                if 'message' in chunk and 'content' in chunk['message']:
                    new_text = chunk['message']['content']
                    if new_text:
                        buffer += new_text
                        # 每0.5秒更新一次，確保逐步輸出
                        if time.time() - last_update_time >= 0.5 and buffer:
                            yield buffer
                            last_update_time = time.time()
            
            # 確保最後的內容也被傳送出去
            if buffer:
                yield buffer

    except Exception as e:
        error_message = f"[ERROR] stream_response 發生錯誤: {str(e)}"
        print(error_message)
        yield f"❌ {error_message}"
        
    # 回答完後的清理工作
    try:
        # 1. 清理文字檔案內容的 JSON
        channel_dir = get_channel_dir(channel_id)
        file_contents_path = os.path.join(channel_dir, 'file_contents.json')
        if os.path.exists(file_contents_path):
            try:
                os.remove(file_contents_path)
                print(f"[DEBUG] 已刪除處理完的文字檔案內容: {file_contents_path}")
            except Exception as e:
                print(f"[ERROR] 刪除文字檔案內容時出錯: {e}")
        
        # 2. 清理原始的文字檔案（保留圖片檔案）
        # channel_dir 已在上面定義
        if os.path.exists(channel_dir):
            for filename in os.listdir(channel_dir):
                file_path = os.path.join(channel_dir, filename)
                # 只刪除文字檔案，保留圖片和 JSON 配置檔案
                if os.path.isfile(file_path) and filename.lower().endswith(('.txt', '.pdf')):
                    try:
                        os.remove(file_path)
                        print(f"[DEBUG] 已刪除處理完的原始文字檔案: {file_path}")
                    except Exception as e:
                        print(f"[ERROR] 刪除原始文字檔案時出錯 {file_path}: {e}")
                        
        # 3. 清理 PDF 圖片（如果存在且超過 30 分鐘）
        pdf_image_dir = os.path.join(channel_dir, "pdf_images")
        if os.path.exists(pdf_image_dir):
            current_time = time.time()
            for filename in os.listdir(pdf_image_dir):
                file_path = os.path.join(pdf_image_dir, filename)
                # 檢查檔案是否超過 30 分鐘
                if os.path.isfile(file_path) and (current_time - os.path.getmtime(file_path)) > 3600:
                    try:
                        os.remove(file_path)
                        print(f"[DEBUG] 已刪除超過 60 分鐘的 PDF 圖片: {file_path}")
                    except Exception as e:
                        print(f"[ERROR] 刪除 PDF 圖片時出錯 {file_path}: {e}")
            
            # 如果 pdf_images 目錄為空，則刪除該目錄
            if not os.listdir(pdf_image_dir):
                try:
                    os.rmdir(pdf_image_dir)
                    print(f"[DEBUG] 已刪除空的 PDF 圖片目錄: {pdf_image_dir}")
                except Exception as e:
                    print(f"[ERROR] 刪除 PDF 圖片目錄時出錯: {e}")
                    
    except Exception as e:
        print(f"[ERROR] 執行清理工作時出錯: {e}")

@bot.event
async def on_message(message):
    # 忽略自己與非允許頻道訊息
    if message.author == bot.user or message.channel.id not in ALLOWED_CHANNEL_IDS:
        return

    # 創建 save_history 目錄（如果不存在）
    channel_dir = get_channel_dir(message.channel.id)
    os.makedirs(channel_dir, exist_ok=True)
    
    # 處理附加檔案
    if message.attachments:
        # 發送初始處理訊息
        processing_msg = await message.channel.send("📂 正在處理上傳的檔案...")
        
        # 用於記錄處理結果的列表
        processing_results = []
        
        for attachment in message.attachments:
            # 設定儲存路徑
            file_path = os.path.join(channel_dir, attachment.filename)
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
        file_contents_path = os.path.join(channel_dir, 'file_contents.json')
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
            async for partial in stream_response(user_input, message.channel.id,thinking_messages):
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
