# Heart Animation Telegram Web App

This project displays a heart animation as a Telegram Web App.

## Setup and Run

1.  **Create and activate a virtual environment:**
    ```bash
    # Create venv
    python -m venv venv

    # Activate on Windows (PowerShell)
    .\venv\Scripts\Activate.ps1

    # Activate on macOS/Linux
    source venv/bin/activate
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure the bot:**
    - Open `bot.py`.
    - Replace `"YOUR_BOT_TOKEN"` with your actual bot token from BotFather.
    - Replace `"YOUR_WEB_APP_URL"` with the URL where your `index.html` is hosted.

4.  **Run the bot:**
    ```bash
    python bot.py
    ```
