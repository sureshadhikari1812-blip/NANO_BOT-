# 🤖 NANO_BOT

A Telegram media downloader bot powered by Python and `yt-dlp`.

## ✨ Features

- Telegram bot interface
- Media downloading
- `yt-dlp` support
- Termux support
- Secure token configuration

## 📋 Requirements

- Android
- Termux
- Internet connection
- Python 3
- Git
- FFmpeg
- Telegram Bot Token

# 📦 Complete Installation

## 1. Update Termux

```bash
pkg update -y
pkg upgrade -y
```

## 2. Install Required Packages

```bash
pkg install git python ffmpeg tmux wget -y
```

## 3. Clone NANO_BOT

```bash
git clone https://github.com/sureshadhikari1812-blip/NANO_BOT-.git
cd NANO_BOT-
```

## 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

## 5. Configure Telegram Bot Token

Create the `.env` file:

```bash
nano .env
```

Add:

```env
BOT_TOKEN="YOUR_BOT_TOKEN_HERE"
```

Replace `YOUR_BOT_TOKEN_HERE` with your actual BotFather token.

Save:

```text
CTRL + X
Y
Enter
```

⚠️ Never upload `.env` to GitHub.

## 6. Start NANO_BOT

```bash
python bot.py
```

If successful:

```text
🤖 NANO_BOT AI v9 is running...
```

## 7. Keep Termux Awake

```bash
termux-wake-lock
```

For a tmux session:

```bash
tmux new -s nano
cd ~/NANO_BOT-
python bot.py
```

Detach:

```text
CTRL + B
D
```

Reconnect:

```bash
tmux attach -t nano
```

## 8. Stop NANO_BOT

If the bot is running directly:

```text
CTRL + C
```

If using tmux, attach first:

```bash
tmux attach -t nano
```

Then:

```text
CTRL + C
```

## 9. Update NANO_BOT

```bash
cd ~/NANO_BOT-
git pull
```

Then:

```bash
python bot.py
```

## 🔐 Security

Never put your real Bot Token in:

- `README.md`
- `bot.py`
- GitHub
- screenshots
- public messages

Keep the real token only inside your private `.env` file.

If your token is exposed, revoke it through `@BotFather` and generate a new one.

## 📁 Project Structure

```text
NANO_BOT-/
├── bot.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
└── models/
```
