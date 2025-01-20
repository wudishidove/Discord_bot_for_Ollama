import json
import discord
from discord.ext import commands
import requests

# 載入配置文件
with open("config.json", "r") as config_file:
    config = json.load(config_file)

# Discord Bot Token
DISCORD_TOKEN = config["DISCORD_TOKEN"]
# Ollama API URL
OLLAMA_API_URL = "http://localhost:11434/api/generate"

# 指定上線訊息的頻道 ID
STATUS_CHANNEL_ID = 1330190647096905788  # 替換為你的頻道 ID

# 初始化 Bot
intents = discord.Intents.default()
intents.messages = True  # 啟用訊息事件
intents.message_content = True  # 啟用訊息內容訪問
bot = commands.Bot(command_prefix="++", intents=intents)


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

ALLOWED_CHANNEL_ID = 1330190647096905788  # 替換為你的頻道 ID


def is_in_allowed_channel(ctx):
    return ctx.channel.id == ALLOWED_CHANNEL_ID


@bot.command()
@commands.check(is_in_allowed_channel)
async def help(ctx):
    """顯示可用指令清單"""
    help_message = """
🤖 **可用指令清單**:
1. **++chat <訊息>** - 與 Bot 進行對話。
2. **++setmodel <模型名稱>** - 選擇要使用的模型。
3. **++help** - 顯示此幫助訊息。

📘 **可用模型**:
- 預設模型: gemma2:latest
- 模型名稱	        max_token_limit  擅長項目
- Qwen2.5:7b       4096          編碼理解、數學能力
- gemma2:latest    8192          文本生成、邏輯推理
- mistral:latest   8192          文本生成
- llama3.2:latest  128000        數學問題、對話系統
- phi4:latest      8192          文本生成、對話系統

🎯 **使用方式**:
- 輸入 `++chat 你好` 與 Bot 開始對話。
- 輸入 `++setmodel gemma2:latest` 切換到指定的模型。
- 輸入 `++help` 查看可用指令清單。
"""
    await ctx.send(help_message)

# 儲存當前選擇的模型
current_model = "phi4:latest"  # 預設模型


@bot.command()
@commands.check(is_in_allowed_channel)
async def setmodel(ctx, model_name: str):
    """設定使用的模型"""
    global current_model
    # 可用模型清單
    available_models = ["Qwen2.5:7b", "gemma2:latest",
                        "mistral:latest", "llama3.2:latest", "phi4:latest"]

    if model_name in available_models:
        current_model = model_name
        await ctx.send(f"已將模型切換為 `{model_name}`")
        print(f"模型切換為：{model_name}")
    else:
        await ctx.send(f"無效的模型名稱！可用模型：{', '.join(available_models)}")
        print(f"無效的模型名稱：{model_name}")


@bot.command()
@commands.check(is_in_allowed_channel)
async def chat(ctx, *, user_input: str):
    """收到訊息後先回覆 '已收到'，並以繁體中文回應"""
    try:
        # 初步回應：已收到訊息
        print(f"收到指令：{user_input}")
        thinking_message = await ctx.send(f"已收到：{user_input}，正在使用 `{current_model}` 模型思考...")

        # 後台打印進度
        print("向 Ollama API 發送請求...")

        # 增加繁體中文的上下文指引
        full_prompt = f"如我用繁體中文問問題，也請你用繁體中文回答以下問題 ，並避免使用任何特殊字符：{user_input}"

        # 向 Ollama API 發送請求
        response = requests.post(
            OLLAMA_API_URL,
            json={"model": current_model, "prompt": full_prompt},
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            # 解析逐行返回的結果
            response.encoding = 'utf-8'  # 明確指定回應的編碼格式
            print("正在處理 API 回應...")
            full_response = ""
            for line in response.text.splitlines():
                data = json.loads(line)
                full_response += data.get("response", "")  # 獲取每個片段的內容
                if data.get("done", False):  # 如果完成，退出解析
                    break

            # 刪除初步回應
            await thinking_message.delete()

            # 發送完整回應
            if full_response.strip():
                print(f"完成，模型回應內容：{full_response}")
                # 確保內容的 Unicode 編碼正常
                await ctx.send(full_response.encode('utf-8').decode('utf-8'))
            else:
                print("模型未返回內容")
                await ctx.send("模型未返回內容，請稍後再試。")
        else:
            print(f"Ollama API 返回錯誤，狀態碼：{response.status_code}")
            await thinking_message.delete()
            await ctx.send(f"Ollama API 返回錯誤，狀態碼：{response.status_code}")
    except Exception as e:
        # 發生錯誤時，刪除初步回應
        print(f"處理請求時出現錯誤：{e}")
        await thinking_message.delete()
        await ctx.send(f"出現錯誤：{e}")

bot.run(DISCORD_TOKEN)
