import inspect
import logging
import json
import re
from bs4 import BeautifulSoup  # 加入此匯入以使用 BeautifulSoup
import time
import requests
import ollama
import subprocess
import os
import global_var as GV
# 儲存當前選擇的模型

client = ollama.Client(host="http://localhost:11434")
def get_base_dir():
    """獲取 Discord_bot_for_Ollama 基礎目錄"""
    # 嘗試從 __file__ 獲取
    if '__file__' in globals():
        base = os.path.dirname(os.path.abspath(__file__))
        if "Discord_bot_for_Ollama" in base:
            return base

    # 否則使用當前工作目錄
    cwd = os.getcwd()
    if "Discord_bot_for_Ollama" in cwd:
        return cwd

    # 最後嘗試硬編碼路徑
    fallback = r"D:\OneDrive\code\mygithub\Discord_bot_for_Ollama"
    if os.path.exists(fallback):
        return fallback

    return cwd
def generate_function_description(func):
    func_name = func.__name__
    docstring = func.__doc__

    # Get function signature
    sig = inspect.signature(func)
    params = sig.parameters

    # Create the properties for parameters
    properties = {}
    required = []

    # Process the docstring to extract argument descriptions
    arg_descriptions = {}
    if docstring:
        # remove leading/trailing whitespace or leading empty lines and split into lines
        docstring = re.sub(r'^\s*|\s*$', '', docstring, flags=re.MULTILINE)
        lines = docstring.split('\n')
        current_arg = None
        for line in lines:
            line = line.strip()
            if line:
                if ':' in line:
                    # strip leading/trailing whitespace and split into two parts
                    line = re.sub(r'^\s*|\s*$', '', line)
                    parts = line.split(':', 1)
                    if parts[0] in params:
                        current_arg = parts[0]
                        arg_descriptions[current_arg] = parts[1].strip()
                elif current_arg:
                    arg_descriptions[current_arg] += ' ' + line.strip()

    for param_name, param in params.items():
        param_type = 'string'  # Default type; adjust as needed based on annotations
        if param.annotation != inspect.Parameter.empty:
            param_type = param.annotation.__name__.lower()

        param_description = arg_descriptions.get(param_name, f'The name of the {param_name}')

        properties[param_name] = {
            'type': param_type,
            'description': param_description,
        }
        if param.default == inspect.Parameter.empty:
            required.append(param_name)

    # Create the JSON object
    function_description = {
        'type': 'function',
        'function': {
            'name': func_name,
            'description': docstring.split('\n')[0] if docstring else f'Function {func_name}',
            'parameters': {
                'type': 'object',
                'properties': properties,
                'required': required,
            },
        },
    }

    return function_description


def use_tools(tools_calls, tool_functions):
    tools_responses = []
    for tool_call in tools_calls:
        # Parse tool name and arguments
        tool_name = tool_call['function']['name']
        arguments = tool_call['function']['arguments']

        # Dynamically call the function
        if tool_name in tool_functions:
            result = tool_functions[tool_name](**arguments)
            tools_responses.append(str(result))
        else:
            raise KeyError(f"Function {tool_name} not found in the provided tool functions.")
    return "\n".join(tools_responses)
def get_current_date(date_format="%Y-%m-%d") -> str:
    """Get the current date.

    Args:
        date_format: The format to return the date in. Default is %Y-%m-%d.
    
    Returns:
        A string with the current date in the requested format.
    """
    current_date = time.strftime(date_format)
    return f"{current_date}"

def get_local_time() -> str:
    """
    Get the current local date and time.

    Returns:
        A string with the current date and time in YYYY-MM-DD HH:MM:SS format.
    """
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"{current_time}"

def get_current_weather(city:str) -> str:
    """Get the current weather for a city.

    Args:
        city: The city to get the weather for.

    Returns:
        A string with the current temperature in Celsius for the city.
    """
    base_url = f"https://wttr.in/{city}?format=j1"
    response = requests.get(base_url)
    data = response.json()
    return f"The current temperature in {city} is: {data['current_condition'][0]['temp_C']}°C"

######
# def web_search(query: str) -> str:
#     """Search DuckDuckGo and return a list of results (title and URL).

#     Args:
#         query: The search query to look up on DuckDuckGo.

#     Returns:
#         A string containing search results with titles and URLs, one per line.
#     """
#     max_results = 3
#     url = f"https://duckduckgo.com/html/?q={requests.utils.requote_uri(query)}"
#     headers = {"User-Agent": "Mozilla/5.0"}
#     res = requests.get(url, headers=headers)
#     soup = BeautifulSoup(res.text, 'html.parser')
#     results = []
#     for a in soup.find_all("a", class_="result__url", href=True)[:max_results]:
#         title = a.get_text().strip()
#         href = a['href']
#         results.append(f"{title}: {href}")
#     return "\n".join(results) if results else "No results found."
def fetch_url_content(url: str, user_input: str) -> str:
    """
    Fetch a web page and return its text content.
    
    Args:
        url: The URL of the web page to fetch.
        user_input: 依照使用者輸入，從搜尋網站提取重要的內容
    
    Returns:
        A string containing the web page's text content. 
    
    Note:
        This function uses a custom User-Agent header and a timeout of 10 seconds.
        Any exceptions during the request are caught and reported in the returned string.
    """
    try:
        # Send an HTTP GET request to fetch the web page
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        res.encoding = res.apparent_encoding  # 自動檢測編碼
        
        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 移除不必要的元素
        for tag in soup(['script', 'style', 'meta', 'link', 'header', 'footer', 'nav']):
            tag.decompose()
            
        # 提取主要文本內容
        text = soup.get_text(separator="\n").strip()
        
        # 清理文本
        text = re.sub(r'\n+', '\n', text)  # 移除多餘的換行
        text = re.sub(r'\s+', ' ', text)   # 移除多餘的空格
        
        # 如果有用戶輸入，使用LLM生成相關摘要
        if user_input:
            # 準備消息
            url_promt = [
                {"role": "system", "content": f"""請根據關鍵詞「{user_input}」從以下網頁內容中提取相關資訊並生成摘要。
                要求：
                1. 摘要限制在1000字以內
                2. 在不超過長度限制的前提下，保留與關鍵詞最相關的內容
                3. 如果找不到相關內容，請正常提取網頁摘要即可。
                """},
                {"role": "user", "content": f"網頁內容:\n{text[:20000]}"}  # 限制輸入長度
            ]
            print(f"[debug] url promt: {url_promt}")
            # 調用LLM生成摘要
            
            response = client.chat(
                model=GV.current_model,
                messages=url_promt
            )
            print(f"\n========\n[debug] response: {response['message']}")
            # 獲取摘要
            if response and 'message' in response and 'content' in response['message']:
                return f"來源: {url}\n\n" + response['message']['content']
            
        # 如果沒有用戶輸入或LLM處理失敗，返回原始文本的前1000個字符
        return f"來源: {url}\n\n" + text[:2000] + "..."
        
    except Exception as e:
        return f"無法獲取或處理網頁內容 {url}: {str(e)}"
#######
def do_math(a:float, op:str, b:float)->str:
    """
    Do basic math operations.
    EX: a=2,op="^",b=4,return "16"

    Args:
        a: The first number.
        op: The operation to perform (+, -, *, /,^).
        b: The second number.

    Returns:
        The result of the operation as a string.
    """
    res = "Nan"
    if op == "+":
        res = str(a + b)
    elif op == "-":
        res = str(a - b)
    elif op == "*":
        res = str(a*b)
    elif op == "/":
        if int(b) != 0:
            res = str(a/b)
    elif op == "^":
        res = str(a ** b)
    return res

def google_search(query: str) -> str:
    """Search Google and return a list of results (title and URL).

    Args:
        query: The search query to look up on Google.

    Returns:
        A string containing search results with titles and URLs, one per line.
    """
    try:
        # 從 config.json 讀取 API 金鑰和搜尋引擎 ID
        with open("config.json", "r", encoding="utf-8") as config_file:
            config = json.load(config_file)
            api_key = config.get("GOOGLE_API_KEY")
            cx = config.get("GOOGLE_CX")
            
        if not api_key or not cx:
            return "Google API key or CX not found in config.json. Please configure them properly."
        
        # 設置最多回傳 10 個結果
        max_results = 10
        url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cx}&q={requests.utils.requote_uri(query)}&num={max_results}"
        
        # 發送 API 請求
        res = requests.get(url)
        data = res.json()
        results = []
        
        # 處理搜尋結果
        if 'items' in data:
            for item in data['items'][:max_results]:
                title = item.get('title', 'No title')
                href = item.get('link', 'No URL')
                results.append(f"{title},{href}\n")
                # results.append(f"{title},{href},content:{{{fetch_url_content(href, query)}}}\n")
        # 回傳結果，若無結果則回傳 "No results found."
        return "\n".join(results) if results else "No results found."
    except FileNotFoundError:
        return "Config file not found. Please create config.json with GOOGLE_API_KEY and GOOGLE_CX."
    except json.JSONDecodeError:
        return "Invalid config.json format. Please check the file format."
    except Exception as e:
        return f"Error occurred while searching: {str(e)}"

def get_youtube_srt(url: str, user_input: str = "") -> str:
    """
    從 YouTube 影片取得字幕並生成摘要

    Args:
        url: YouTube 影片網址
        user_input: 使用者的關鍵詞，用於提取相關內容

    Returns:
        包含影片字幕摘要的字串
    """

    return f"處理 YouTube 影片時發生錯誤: 取得SRT的實作已變換到process_youtube_srt_streaming"

def if_need_tools(messages: list) -> tuple[bool, str | None]:
    """
    檢查使用者的問題是否需要工具

    Args:
        messages: 包含對話紀錄的列表

    Returns:
        (True, tool_name): 需要調用工具
        (False, None): 不須工具，進入一般對話模式
    """
    try:
        # 提取最近的使用者訊息
        user_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break

        if not user_message:
            return False, None

        # 構建工具描述字串
        tool_descriptions = []
        for tool in tools:
            func_info = tool.get("function", {})
            name = func_info.get("name", "")
            desc = func_info.get("description", "")
            tool_descriptions.append(f"- {name}: {desc}")

        tools_text = "\n".join(tool_descriptions)

        # 準備判斷 prompt
        check_prompt = [
            {"role": "system", "content": f"""你是一個判斷助手。請判斷使用者的問題是否需要使用工具才能回答。

可用的工具：
{tools_text}

判斷規則：
1. 如果問題需要即時資訊（如當前時間、天氣、網路搜尋等），回答需要工具
2. 如果問題包含網址需要獲取內容，回答需要工具
3. 如果問題需要數學計算，回答需要工具
4. 如果是一般對話聊天或常識內容，不需要工具
4-1. 若牽涉到法律、專業知識，則需要工具(google_search)
5. 如果問題包含YouTube連結，回答需要工具（使用get_youtube_srt）

回答格式必須是以下其中一種：
- 如果需要工具：True, tool_name（例如：True, google_search）
- 如果不需要工具：False, None

只回答這個格式，不要有其他內容。"""},
            {"role": "user", "content": f"使用者問題：{user_message}\n\n請判斷是否需要工具？"}
        ]

        # 調用 Ollama 進行判斷
        response = client.chat(
            model=GV.current_model,
            messages=check_prompt,
            stream=False
        )
        print("==="*10)
        print(f"[DEBUG] if_need_tools 輸入: {check_prompt}")
        # 解析回應
        if response and 'message' in response and 'content' in response['message']:
            result = response['message']['content'].strip()
            print(f"[DEBUG] if_need_tools 判斷結果: {result}")
            print("==="*10)
            # 解析結果
            if "True" in result:
                # 提取工具名稱
                parts = result.split(",")
                if len(parts) >= 2:
                    tool_name = parts[1].strip().strip("'\"")
                    # 驗證工具名稱是否有效
                    valid_tools = [t['function']['name'] for t in tools]
                    if tool_name in valid_tools:
                        return True, tool_name
                    else:
                        # 如果工具名稱無效，讓系統自己決定
                        return True, None
                return True, None
            else:
                return False, None

        return False, None

    except Exception as e:
        print(f"[ERROR] if_need_tools 發生錯誤: {str(e)}")
        # 錯誤時回退到關鍵字檢測
        if messages:
            last_msg = messages[-1].get("content", "").lower() if messages[-1].get("role") == "user" else ""
            keywords = ['搜尋', '搜索', '查詢', '天氣', '時間', '計算', '數學', '幾點',
                       '現在', '今天', 'search', 'weather', 'time', 'calculate',
                       'math', 'what time', 'current', 'today', 'https://', 'http://',
                       'youtube.com', 'youtu.be']
            if any(keyword in last_msg for keyword in keywords):
                return True, None
        return False, None

def check_if_tool_is_still_needed(tool_name: str, messages: list) -> bool:
    """
    檢查工具的回傳是否已經滿足使用者的問題

    Args:
        messages: 包含對話紀錄的列表，其中包含工具回傳 {"role": "tool", "content": result}

    Returns:
        True: 仍需要調用更多工具
        False: 工具回應已滿足使用者需求，可以進入一般對話模式
    """
    if tool_name == 'get_youtube_srt':
        return False
    try:
        # 提取最近的使用者問題
        user_question = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_question = msg.get("content", "")
                break

        if not user_question:
            return False  # 沒有找到使用者問題，預設不需要更多工具

        # 提取所有工具回應
        tool_responses = []
        for msg in messages:
            if msg.get("role") == "tool":
                tool_responses.append(msg.get("content", ""))

        if not tool_responses:
            return True  # 沒有工具回應，可能需要工具

        # 組合所有工具回應
        combined_tool_response = "\n\n".join(tool_responses[-3:])  # 只取最近3個工具回應避免太長

        # 準備判斷 prompt（獨立的，不污染原始對話）
        check_prompt = [
            {"role": "system", "content": """你是一個判斷助手。請判斷工具的回傳內容是否已經充分回答了使用者的問題。

            判斷標準：
            1. 如果工具已經提供了使用者所需的主要資訊，回答 "false"（不需要更多工具）
            2. 如果工具回應明顯不足或失敗，需要調用其他工具，回答 "true"（仍需要工具）
            3. 如果工具已成功獲取資料（如影片字幕、網頁內容等），回答 "false"

            只回答一個單詞："true" 或 "false"，不要有其他內容。"""},
            {"role": "user", "content": f"""使用者問題：{user_question}

工具回應內容：
{combined_tool_response[:3000]}

請判斷：工具回應是否已經滿足使用者需求？
如果已滿足，回答 "false"（不需要更多工具）
如果未滿足，回答 "true"（仍需要工具）"""}
        ]

        # 調用 Ollama 進行判斷
        response = client.chat(
            model=GV.current_model,
            messages=check_prompt,
            stream=False
        )

        # 解析回應
        if response and 'message' in response and 'content' in response['message']:
            result = response['message']['content'].strip().lower()
            print(f"[DEBUG] check_if_tool_is_still_needed 判斷結果: {result}")

            # 判斷結果
            if "false" in result:
                return False  # 不需要更多工具
            elif "true" in result:
                return True  # 仍需要工具
            else:
                # 預設：如果有工具回應且不為錯誤，假設已滿足
                return False

        return False  # 預設不需要更多工具

    except Exception as e:
        print(f"[ERROR] check_if_tool_is_still_needed 發生錯誤: {str(e)}")
        return False  # 發生錯誤時，預設不需要更多工具，避免無限循環
def advanced_web_search(query: str) -> str:
    """Execute advanced web search using AI-enhanced multi-step process.
    
    This function uses the ollama-web-search project to perform:
    1. Query optimization using AI
    2. Web search via Google API  
    3. AI-powered result selection
    4. Content extraction via Jina Reader API
    5. Return structured search results
    
    Args:
        query: The search query or question to find information about.
    
    Returns:
        A formatted string containing the search results including title, URL, and extracted content.
    """
    try:
        # Get the current working directory
        current_dir = os.getcwd()
        search_script = os.path.join(current_dir, "tool/ollama-web-search", "main.py")
        
        # Check if the search script exists
        if not os.path.exists(search_script):
            return f"Error: ollama-web-search script not found at {search_script}"
        
        # The JSON file that main.py will generate
        json_file = os.path.join(current_dir, "tool/ollama-web-search", "webpage_content.json")

        try:
            # 在執行搜尋前，先清理舊的 JSON 檔案
            if os.path.exists(json_file):
                try:
                    os.remove(json_file)
                    print(f"[DEBUG] 已刪除舊的 webpage_content.json")
                except Exception as e:
                    print(f"[WARNING] 無法刪除舊檔案: {e}")

            # Execute the web search command using --query parameter
            result = subprocess.run([
                "python", search_script, "--query", query
            ], capture_output=True, text=True, timeout=120, encoding='utf-8', errors='replace')
            
            if result.returncode != 0:
                return f"Error executing web search: {result.stderr}"
            
            # Wait for the JSON file to be created (max 30 seconds, check every second)
            max_wait_time = 30
            wait_interval = 1
            waited_time = 0
            
            print(f"[DEBUG] 等待 webpage_content.json 檔案生成...")
            while waited_time < max_wait_time:
                if os.path.exists(json_file):
                    print(f"[DEBUG] 檔案已生成，等待了 {waited_time} 秒")
                    break
                time.sleep(wait_interval)
                waited_time += wait_interval
                if waited_time % 5 == 0:  # 每5秒顯示一次進度
                    print(f"[DEBUG] 等待中... {waited_time}/{max_wait_time} 秒")
            
            # Check if file was created within timeout
            if not os.path.exists(json_file):
                return f"Error: webpage_content.json 在 {max_wait_time} 秒內未被創建。可能是 main.py 執行失敗或 Jina.ai API 超時。"
            
            # Try to read the JSON file with error handling
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    search_data = json.load(f)
            except json.JSONDecodeError:
                return "Error: webpage_content.json 檔案格式不正確，JSON 解析失敗"
            except Exception as e:
                return f"Error: 讀取 webpage_content.json 時發生錯誤: {str(e)}"
            
            # Get the latest entry (main.py appends new searches to the list)
            if not search_data or not isinstance(search_data, list):
                return "Error: Invalid JSON format in webpage_content.json"
            
            latest_search = search_data[-1]  # Get the most recent search
            
            # Extract information from the JSON structure
            user_question = latest_search.get('user_question', 'N/A')
            search_query = latest_search.get('search_query', 'N/A')
            selected_result = latest_search.get('selected_result', {})
            title = selected_result.get('title', 'N/A')
            url = selected_result.get('url', 'N/A')
            content = latest_search.get('webpage_content', 'No content available')
            
            # Format the results for the Discord bot
            formatted_result = f"""AI 智慧搜尋結果：

原始問題：{user_question}
優化搜尋詞：{search_query}

選中結果：
標題：{title}
網址：{url}

內容摘要：
{content[:2500]}{'...' if len(content) > 2500 else ''}

來源：Ollama Web Search (AI增強搜尋)"""

            return formatted_result
            
        finally:
            # Clean up the JSON file immediately after reading
            if os.path.exists(json_file):
                try:
                    os.remove(json_file)
                    print(f"[DEBUG] 已清理 webpage_content.json")
                except Exception as e:
                    print(f"[WARNING] 清理 webpage_content.json 時發生錯誤: {e}")
        
    except subprocess.TimeoutExpired:
        return "Error: Web search timed out after 120 seconds"
    except Exception as e:
        return f"Error during advanced web search: {str(e)}"
if __name__ == "__main__":
    tools = [
    generate_function_description(get_current_weather),
    generate_function_description(get_local_time),
    generate_function_description(google_search),
    generate_function_description(advanced_web_search),
    generate_function_description(fetch_url_content),
    generate_function_description(get_youtube_srt),
    generate_function_description(do_math),
    ]

    logging.debug("Tools:")
    logging.debug(json.dumps(tools, indent=4))
    functions = [f["function"]["description"] for f in tools]
    print("I am a chatbot able to run some functions.\n", "Functions:\n\t", functions)

    # 初始化消息歷史
    messages = []
    messages.append({"role": "system", "content": """如果使用者用中文問你，請用繁體中文回答。遇到工具使用需求時，請自行將使用者的問題透過工具來得到解答，工具使用沒有次數限制，可自行拆分工具步驟來達到使用者的需求"""})
    # 主循環
    try :
        while True:
            query = input("Enter your query (or 'quit' to exit): ")
            if query == "quit":
                break
            if query.strip() == "":
                continue
            
            # 將使用者查詢添加到消息歷史
            messages.append({"role": "user", "content": query})
            
            # 內部循環處理工具調用
            while True:
                # 調用LLM
                response = client.chat(
                    model=GV.current_model,
                    messages=messages,
                    tools=tools,
                )
                
                # 獲取LLM回應
                message = response.get('message', {})
                tool_calls = message.get('tool_calls')
                
                if tool_calls:
                    # 處理工具調用
                    for tool_call in tool_calls:
                        tool_name = tool_call['function']['name']
                        arguments = tool_call['function']['arguments']
                        logging.info(f"Calling tool: {tool_name} with arguments: {arguments}")
                        
                        # 動態執行工具函數
                        result = globals()[tool_name](**arguments)
                        logging.info(f"Tool result: {result}")
                        
                        # 將工具結果添加到消息歷史
                        messages.append({"role": "tool", "content": result})
                else:
                    # 沒有工具調用，輸出最終回答並結束內部循環
                    content = message.get('content', '')
                    print("Assistant:", content)
                    messages.append({"role": "assistant", "content": content})
                    break
    except Exception as e:
        print("error:",e)

# Initialize tools list at the end of the file after all functions are defined
tools=[
    generate_function_description(get_local_time),
    generate_function_description(google_search),
    # generate_function_description(advanced_web_search),
    generate_function_description(fetch_url_content),
    generate_function_description(do_math),
    generate_function_description(get_youtube_srt),
]
