import inspect
import json
import re
from bs4 import BeautifulSoup  # 加入此匯入以使用 BeautifulSoup
import time
import requests
import ollama
# 儲存當前選擇的模型
current_model = "mistral-small3.1"  # 預設模型
client = ollama.Client(host="http://localhost:11434")
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
def web_search(query: str) -> str:
    """Search DuckDuckGo and return a list of results (title and URL).

    Args:
        query: The search query to look up on DuckDuckGo.

    Returns:
        A string containing search results with titles and URLs, one per line.
    """
    max_results = 3
    url = f"https://duckduckgo.com/html/?q={requests.utils.requote_uri(query)}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    results = []
    for a in soup.find_all("a", class_="result__url", href=True)[:max_results]:
        title = a.get_text().strip()
        href = a['href']
        results.append(f"{title}: {href}")
    return "\n".join(results) if results else "No results found."
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
                model=current_model,
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
def do_math(a:int, op:str, b:int)->str:
    """
    Do basic math operations.

    Args:
        a: The first number.
        op: The operation to perform (+, -, *, /).
        b: The second number.

    Returns:
        The result of the operation as a string.
    """
    res = "Nan"
    if op == "+":
        res = str(int(a) + int(b))
    elif op == "-":
        res = str(int(a) - int(b))
    elif op == "*":
        res = str(int(a) * int(b))
    elif op == "/":
        if int(b) != 0:
            res = str(int(a) / int(b))
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
if __name__ == "__main__":
    tools = [
    generate_function_description(get_current_weather),
    generate_function_description(get_local_time),
    generate_function_description(google_search),
    generate_function_description(fetch_url_content),
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
                    model=current_model,
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

