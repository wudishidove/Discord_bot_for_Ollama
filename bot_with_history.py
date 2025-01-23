import json
import discord
from discord.ext import commands
import requests
from langchain.memory import ConversationBufferMemory
import time

# 模型對應的最大 token 限制
MODEL_MAX_TOKENS = {
    "gemma2:latest": 8192,
    "phi4:latest": 8192,
    "Qwen2.5:7b": 4096,
    "mistral:latest": 8192,
    "llama3.2:latest": 128000,
    "llama3.2-vision:latest": 128000,
    "deepseek-r1:1.5b": 128000,
    "deepseek-r1:latest": 128000,
    "deepseek-r1:8b": 128000,
    "deepseek-r1:14b": 128000
}

# 初始化記憶功能
memory = ConversationBufferMemory(
    max_token_limit=8192)  # 默認為 phi4 的最大 token 限制

# 載入配置文件
with open("config.json", "r") as config_file:
    config = json.load(config_file)

# Discord Bot Token
DISCORD_TOKEN = config["DISCORD_TOKEN"]
# Ollama API URL
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# 指定上線訊息的頻道 ID
STATUS_CHANNEL_ID = 1330190647096905788  # 替換為你的頻道 ID
ALLOWED_CHANNEL_ID = 1330190647096905788
# 初始化 Bot
intents = discord.Intents.default()
intents.messages = True  # 啟用訊息事件
intents.message_content = True  # 啟用訊息內容訪問
bot = commands.Bot(command_prefix="++", intents=intents)

# 儲存當前選擇的模型
current_model = "phi4:latest"  # 預設模型


def is_in_allowed_channel(ctx):
    return ctx.channel.id == ALLOWED_CHANNEL_ID


def update_memory_limit():
    """根據當前模型更新記憶最大 token 限制"""
    global memory
    max_tokens = MODEL_MAX_TOKENS.get(current_model, 8192)  # 默認為 8192
    memory = ConversationBufferMemory(max_token_limit=max_tokens)
    print(f"[DEBUG] 記憶最大 token 限制更新為: {max_tokens}")


def save_history_to_file():
    """將記憶歷史保存到 JSON 文件中"""
    context = memory.load_memory_variables({})
    with open("history.json", "w", encoding="utf-8") as history_file:
        json.dump(context, history_file, ensure_ascii=False, indent=4)
    print("[DEBUG] 記憶已保存到 history.json")


def trim_memory_with_ollama():
    """使用 Ollama 模型裁剪記憶歷史"""
    context = memory.load_memory_variables({})
    history = context.get("history", "")

    # 如果記憶太短，無需裁剪
    if len(history.split("\n")) < 20:
        print("[DEBUG] 記憶內容不足以裁剪，跳過")
        return

    # 發送請求到 Ollama 模型
    trim_prompt = f"以下是目前的對話歷史，請選擇對話中最重要的部分並保留：\n{history}\n重要對話："
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

            # 更新記憶
            memory.save_context({"input": ""}, {"output": trimmed_history})
            save_history_to_file()  # 保存裁剪後的記憶
        except json.JSONDecodeError as e:
            print("[ERROR] 無法解析裁剪回應：", e)
    else:
        print("[ERROR] Ollama API 返回錯誤：", response.status_code, response.text)


def process_user_input(user_input):
    """處理用戶輸入，使用 Ollama API 並儲存記憶"""
    try:
        # 確保記憶功能包含上下文
        context = memory.load_memory_variables({})
        prompt_with_memory = context.get(
            "history", "") + f"\nUser: {user_input}\nBot:"

        print("[DEBUG] Prompt sent to Ollama API:", prompt_with_memory)
        start_time = time.time()
        full_prompt = f"如我用繁體中文問問題，也請你用繁體中文回答以下問題並把字數控制在30字以內，並不使用任何特殊字符和表情：{prompt_with_memory}"
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
                    save_history_to_file()  # 保存記憶歷史
                    return full_response.strip(), elapsed_time
                else:
                    # 單行 JSON 回應
                    result = response.json()
                    bot_response = result.get("response", "模型未返回內容，請稍後再試。")
                    # 更新記憶
                    memory.save_context({"input": user_input}, {
                                        "output": bot_response})
                    print("[DEBUG] Single-line response:", bot_response)
                    save_history_to_file()  # 保存記憶歷史
                    return bot_response, elapsed_time
            except json.JSONDecodeError as e:
                raise Exception(f"JSON 解碼錯誤：{e}")
        else:
            raise Exception(
                f"Ollama API Error: {response.status_code} - {response.text}"
            )
    except Exception as e:
        raise Exception(f"處理請求時發生錯誤：{e}")


@bot.event
async def on_ready():
    """當 Bot 上線時觸發"""
    print("Bot 已成功啟動！")
    print(f"已登入 Discord 帳戶：{bot.user}")

    # 發送上線通知到指定頻道
    try:
        status_channel = bot.get_channel(STATUS_CHANNEL_ID)
        if status_channel:
            await status_channel.send("🤖 Bot 已上線，準備接收指令！")
        else:
            print(f"無法找到頻道 ID：{STATUS_CHANNEL_ID}")
    except Exception as e:
        print(f"發送上線通知時出現錯誤：{e}")

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
4. **++clean_history** - 清除記憶歷史。

📘 **可用模型**:
- 預設模型: gemma2:latest
- Qwen2.5:7b      擅長編碼和數學能力
- gemma2:latest   擅長文本生成、對話系統
- mistral:latest  一般用途
- phi4:latest     擅長文本生成、對話系統
- llama3.2:latest 擅長多語言支持、對話系統
- llama3.2-vision:latest  圖像識別、視覺推理
- deepseek-r1:1.5b 快速回答 會輸出推理(思考)過程
- deepseek-r1:latest 7B中等複雜度 會輸出推理(思考)過程
- deepseek-r1:8b  數學程式領域出色 會輸出推理(思考)過程
- deepseek-r1:14b 高等複雜度 會輸出推理(思考)過程
🎯 **使用方式**:
- 輸入 `++chat 你好` 與 Bot 開始對話。
- 輸入 `++setmodel gemma2:latest` 切換到指定的模型。
- 輸入 `++help` 查看可用指令清單。
- 輸入 `++clean_history` 清除記憶歷史。
"""
    await ctx.send(help_message)


@commands.check(is_in_allowed_channel)
@bot.command(name="chat")
async def chat(ctx, *, user_input: str):
    """處理聊天指令"""
    try:
        print(f"收到指令：{user_input}")
        thinking_message = await ctx.send(f"已收到：{user_input}，正在思考...")

        # 生成 Ollama 回應
        response, _ = process_user_input(user_input)
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
    available_models = ["Qwen2.5:7b", "gemma2:latest",
                        "mistral:latest", "llama3.2:latest", "phi4:latest", "llama3.2-vision:latest", "deepseek-r1:latest", "deepseek-r1:1.5b", "deepseek-r1:14b", "deepseek-r1:8b"]
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
    """清除記憶歷史"""
    global memory
    memory = ConversationBufferMemory(
        max_token_limit=MODEL_MAX_TOKENS.get(current_model, 8192))
    print("[DEBUG] 記憶歷史已清除")
    await ctx.send("記憶歷史已成功清除！")

bot.run(DISCORD_TOKEN)
