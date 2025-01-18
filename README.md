# README

## English
### Project Overview
This is a Discord Bot chatbot project that interacts with various models via the Ollama API. You can dynamically switch models based on your needs and chat with the bot in a designated channel.

### Features
- **Model Interaction:** Communicate with models via the Ollama API.
- **Model Switching:** Dynamically select models. You need to install the models yourself using the following command:
  ```bash
  ollama pull [Model Name in Ollama library]
  ```
- **Channel Restriction:** Commands are limited to specific channels to prevent misuse.
- **Simple Commands:** Includes `++chat`, `++setmodel`, and `++help`.

### How to Use
1. Ensure that Ollama is installed and running:
   - Visit [Ollama Official Site](https://ollama.ai) for download and installation instructions.
   - Make sure `ollama serve` is successfully running.
2. Clone the project locally:
   ```bash
   git clone <GitHub Repository URL>
   ```
3. Create a `config.json` file in the project directory and add your Discord Token:
   ```json
   {
       "DISCORD_TOKEN": "Your Discord Bot Token"
   }
   ```
4. **Set up the Discord Bot:**
   - Log in to the [Discord Developer Portal](https://discord.com/developers/applications).
   - Click "New Application" to create a new application.
   - Go to the **Bot** tab and click "Add Bot" to create a bot.
   - Copy the Token and paste it into your `config.json`.
   - Under **OAuth2** > **URL Generator**, select "bot" and the required permissions, then generate an invite link to add the bot to your server.

5. Start the bot:
   ```bash
   python bot.py
   ```
6. **Enable Privileged Gateway Intents:**
   - Go back to the [Discord Developer Portal](https://discord.com/developers/applications).
   - Select your application and navigate to the **Bot** settings page.
   - Enable the **Message Content Intent** option.

### Available Commands
- `++chat <message>`: Chat with the bot.
- `++setmodel <model_name>`: Switch the current model.
- `++help`: View a list of commands and their descriptions.

### Notes
- **Ollama Model Management:** Ensure that you have correctly downloaded and installed the required models.
- **Discord Permissions:** Verify that the bot has sufficient permissions in the server to read and send messages.

### Contact
For any issues, pm .

[切換到英文](README_zh.md)


