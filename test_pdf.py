from ollama_ocr import OCRProcessor

# Initialize OCR processor
ocr = OCRProcessor(model_name='gemma3:27b')  # You can use any vision model available on Ollama
# you can pass your custom ollama api

# Process an image
result = ocr.process_image(
    image_path="test1.pdf", # path to your pdf files "path/to/your/file.pdf"
    format_type="markdown",  # Options: markdown, text, json, structured, key_value
    custom_prompt="提取所有文本及表格", # Optional custom prompt
    language="chinese" # Specify the language of the text (New! 🆕)
)
print(result)