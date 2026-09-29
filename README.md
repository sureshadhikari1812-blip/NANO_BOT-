🤖 NANO_BOT

A Telegram media downloader bot powered by Python and "yt-dlp".

✨ Features

- Telegram bot interface
- Media downloading
- "yt-dlp" support
- Easy Termux setup
- Secure token configuration
- Token stored outside the source code

---

📋 Requirements

You need:

- Android phone
- Termux
- Internet connection
- Git
- Python 3
- A Telegram Bot Token

«Note: The Telegram Bot Token is a secret. Never publish it on GitHub or share it publicly.»

---

📦 Complete Installation Guide

This guide is written for someone who is setting everything up from the beginning.

1. Install Termux

Install Termux on your Android device.

Open Termux after installation.

---

2. Update Termux

Run these commands:

pkg update -y
pkg upgrade -y

Wait until the process finishes.

---

3. Install Git and Python

Run:

pkg install git python -y

Check that they were installed:

git --version
python --version

---

4. Clone NANO_BOT

Run:

git clone https://github.com/sureshadhikari1812-blip/NANO_BOT-.git

Then enter the bot folder:

cd NANO_BOT-

You can check the files with:

ls

You should see files such as:

bot.py
requirements.txt
README.md
.env.example
models

---

5. Install Python Dependencies

Run:

pip install -r requirements.txt

Wait until all required packages are installed.

---

🔐 6. Configure the Telegram Bot Token

The bot needs a Telegram Bot Token to connect to Telegram.

If you already have a bot

Get its token from @BotFather on Telegram.

If you don't have a bot

1. Open Telegram.
2. Search for @BotFather.
3. Start the chat.
4. Use "/newbot".
5. Follow the instructions.
6. BotFather will give you a Bot Token.

Create the ".env" file

Inside the "NANO_BOT-" folder, run:

nano .env

Add:

BOT_TOKEN="YOUR_BOT_TOKEN_HERE"

Replace:

YOUR_BOT_TOKEN_HERE

with your actual Telegram Bot Token.

Example format:

BOT_TOKEN="123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

Do not use the example token above.

Save the file

In nano:

CTRL + X
Y
Enter

---

🔒 IMPORTANT: Keep Your Token Private

Never put your real Bot Token in:

- "README.md"
- "bot.py"
- GitHub
- Screenshots
- Public messages
- Videos/tutorials

Never run:

git add .env

The ".env" file is meant to stay on the machine where the bot is running.

This repository includes ".gitignore" so ".env" is ignored by Git.

---

▶️ 7. Start NANO_BOT

After configuring the token, run:

python bot.py

If everything is configured correctly, you should see something similar to:

🤖 NANO_BOT AI v9 is running...

Now open your bot on Telegram and use it.

---

🛑 8. Stop NANO_BOT

To stop the bot:

CTRL + C

---

🔄 9. Update NANO_BOT

If a new version is released on GitHub, go to the bot folder:

cd NANO_BOT-

Then run:

git pull

After updating, start the bot again:

python bot.py

«Your ".env" file should remain on your device because it is not stored in GitHub.»

---

👥 Using the Same Bot

The Bot Token belongs to the bot owner.

Other people do not need your Bot Token just to use your bot.

They simply open your bot on Telegram and use it.

The bot itself should normally have one active running instance to avoid polling conflicts.

---

🆕 Setting Up NANO_BOT on Another Android Phone

If you are setting up NANO_BOT on another phone:

pkg update -y
pkg upgrade -y
pkg install git python -y
git clone https://github.com/sureshadhikari1812-blip/NANO_BOT-.git
cd NANO_BOT-
pip install -r requirements.txt
nano .env

Then add your Bot Token:

BOT_TOKEN="YOUR_BOT_TOKEN_HERE"

Save it and run:

python bot.py

Do not upload that ".env" file to GitHub.

---

📁 Project Structure

NANO_BOT-/
├── bot.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
└── models/

---

🛠️ Common Problems

InvalidToken

If you see:

telegram.error.InvalidToken

Check your ".env" file:

cat .env

Make sure it contains:

BOT_TOKEN="YOUR_ACTUAL_TOKEN"

Do not leave:

BOT_TOKEN="YOUR_BOT_TOKEN_HERE"

---

GitHub asks for username/password

If the repository is public, cloning should normally not require GitHub authentication.

Make sure you are using the correct repository URL:

git clone https://github.com/sureshadhikari1812-blip/NANO_BOT-.git

---

🔐 Security

Your Bot Token gives control over your Telegram bot.

If you accidentally expose your token:

1. Open @BotFather.
2. Revoke/regenerate the token.
3. Replace the old token in ".env".
4. Never publish the new token.

---

📄 License

For personal and educational use.
