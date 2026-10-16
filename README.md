<div align="center">
  <img src="https://github.com/hikariatama/assets/raw/master/1326-command-window-line-flat.webp" height="80">
  <h1>Heroku Userbot</h1>
  <p>Advanced Telegram userbot with enhanced security and modern features</p>
  
  <p>
    <a href="https://www.codacy.com/gh/Heroku-userbot/Heroku/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=Heroku-userbot/Heroku&amp;utm_campaign=Badge_Grade">
      <img src="https://app.codacy.com/project/badge/Grade/97e3ea868f9344a5aa6e4d874f83db14" alt="Codacy Grade">
    </a>
    <a href="#">
      <img src="https://img.shields.io/github/languages/code-size/Heroku-userbot/Heroku" alt="Code Size">
    </a>
    <a href="#">
      <img src="https://img.shields.io/github/issues-raw/Heroku-userbot/Heroku" alt="Open Issues">
    </a>
    <a href="#">
      <img src="https://img.shields.io/github/license/Heroku-userbot/Heroku" alt="License">
    </a>
    <a href="#">
      <img src="https://img.shields.io/github/commit-activity/m/Heroku-userbot/Heroku" alt="Commit Activity">
    </a>
    <br>
    <a href="#">
      <img src="https://img.shields.io/github/forks/Heroku-userbot/Heroku?style=flat" alt="Forks">
    </a>
    <a href="#">
      <img src="https://img.shields.io/github/stars/Heroku-userbot/Heroku" alt="Stars">
    </a>
    <a href="https://github.com/psf/black">
      <img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code Style: Black">
    </a>
    <br>
    <a href="https://github.com/Heroku-userbot/Heroku/blob/master/README.md">
      <img src="https://img.shields.io/badge/lang-en-red.svg" alt="En">
    </a>
    <a href="https://github.com/Heroku-userbot/Heroku/blob/master/README_RU.md">
      <img src="https://img.shields.io/badge/lang-ru-green.svg" alt="Ru">
    </a>
  </p>
  
</div>

### Manual Installation (VPS/VDS Server)

---

## ⚠️ Security Notice

> **Important Security Advisory**  
> While Heroku implements extended security measures, installing modules from untrusted developers may still cause damage to your server/account.
> 
> **Recommendations:**
> - ✅ Download modules exclusively from official repositories or trusted developers
> - ❌ Do NOT install modules if unsure about their safety
> - ⚠️ Exercise caution with unknown commands (`.terminal`, `.eval`, `.ecpp`, etc.)

---

## 🚀 Installation

### Alternative: universal installer (Linux, WSL, UserLAnd)
Installation with a single command, the step-by-step instructions below remain the main one.
It installs the requirements, creates a virtual environment (`.venv`) and starts Heroku. Run the same command again to start the installed Heroku.

```bash
curl -fsSL https://raw.githubusercontent.com/Heroku-userbot/Heroku/master/install.sh | bash
```

> - Root users: add `-s -- --root` (`... | bash -s -- --root`)
> - `HEROKU_FORCE_INSTALL=1` forces a reinstall

### VPS/VDS
> **Note for VPS/VDS Users:**  
> Add `--root` for root users (to avoid entering force_insecure)
<details> <summary><b>Ubuntu / Debian</b></summary>

  ```bash
  sudo apt update && sudo apt install git python3 -y && \
  git clone https://github.com/Heroku-userbot/Heroku && \
  cd Heroku && \
  python3 -m venv .venv && \
  source .venv/bin/activate && \
  pip install -r requirements.txt && \
  python3 -m heroku
  ```
</details>

<details>
<summary><b>Fedora</b></summary>
  
  ```bash
  sudo dnf update -y && sudo dnf install git python3 -y && \
  git clone https://github.com/Heroku-userbot/Heroku && \
  cd Heroku && \
  python3 -m venv .venv && \
  source .venv/bin/activate && \
  python3 -m pip install -r requirements.txt && \
  python3 -m heroku
  ```
</details>

<details>
<summary><b>Arch Linux</b></summary>
  
```bash
sudo pacman -Syu --noconfirm && sudo pacman -S git python --noconfirm --needed && \
git clone https://github.com/Heroku-userbot/Heroku && \
cd Heroku && \
python3 -m venv .venv && \
source .venv/bin/activate && \
python3 -m pip install -r requirements.txt && \
python3 -m heroku
```
</details>



### Other
<details>
  <summary><b>WSL(Windows)</b></summary>

  > **⚠️ WARNING: Can be unstable!**

  1. **Download WSL.** For this open window PowerShell with admin rights and write in console 
  ```powershell
  wsl --install -d Ubuntu-22.04
  ```
  
  > *⚠️For install beed Windows 10 build 2004 or Windows 11 of any version and PC with virtualization support.*
  > *For installation on earlier OS, please refer to this [page](https://learn.microsoft.com/ru-ru/windows/wsl/install-manual).*
  
  2. **Restart PC and start programm Ubuntu 22.04.x**
  3. **Enter this command(RMB):** 
  ```bash
  curl -Ss https://bootstrap.pypa.io/get-pip.py | python3
  ```
  > *⚠️ If yellow warnings appear, enter export PATH="/home/username/.local/bin:$PATH" replacing /home/username/.local/bin with the path mentioned in the message*
  
  4. **Enter this command(RMB):**
  ```bash
  clear && git clone https://github.com/Heroku-userbot/Heroku && cd Heroku && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python3 -m heroku
  ```
  > **🔗How to get API_ID and API_HASH?:** [Video](https://youtu.be/DcqDA249Lhg?t=24)
  
</details>

<details>
  <summary><b>Phone(Userland)</b></summary>
  
  1. <b>Install UserLAnd from</b> <a href="https://play.google.com/store/apps/details?id=tech.ula">the link</a>
  2. <b>Open it, choose Ubuntu —&gt; Minimal —&gt; Terminal</b>
  3. <b>Wait for the distribution to install, you can pour some tea</b> 
  4. <b>After successful installation, a terminal will open in front of you, write there:</b>
    
  ```bash
  sudo apt update ; sudo apt upgrade -y ; sudo apt install -y python3 python3-venv git ; git clone https://github.com/Heroku-userbot/Heroku ; cd Heroku ; python3 -m venv venv ; source venv/bin/activate ; python3 -m heroku
  ```

5. <b>At the end of the installation, a link will appear, follow it and enter your account details to log in.</b>
> **Voila! You have installed Heroku on UserLAnd.**
</details>

### Official hostings
<details>
<summary><b>🌘 HikkaHost</b></summary>
  
  1. Go to [@hikkahost_bot](https://t.me/hikkahost_bot)
  2. Press "Install"
  3. Choose "🪐 Heroku"
  And continue installation.
  > **After that, you will receive a link, open it and login in your account.**

</details>



## Additional Features

<details>
  <summary><b>🔒 Automatic Database Backuper</b></summary>
  <img src="https://user-images.githubusercontent.com/36935426/202905566-964d2904-f3ce-4a14-8f05-0e7840e1b306.png" width="400">
</details>

<details>
  <summary><b>👋 Welcome Installation Screens</b></summary>
  <img src="https://user-images.githubusercontent.com/36935426/202905720-6319993b-697c-4b09-a194-209c110c79fd.png" width="300">
  <img src="https://user-images.githubusercontent.com/36935426/202905746-2a511129-0208-4581-bb27-7539bd7b53c9.png" width="300">
</details>

---

## ✨ Key Features & Improvements

| Feature | Description |
|---------|-------------|
| 🆕 **Latest Telegram Layer** | Support for forums and newest Telegram features |
| 🔒 **Enhanced Security** | Native entity caching and targeted security rules |
| 🎨 **UI/UX Improvements** | Modern interface and user experience |
| 📦 **Core Modules** | Improved and new core functionality |
| ⏱ **Rapid Bug Fixes** | Faster resolution than FTG/GeekTG |
| 🔄 **Backward Compatibility** | Works with FTG, GeekTG and Hikka modules |
| ▶️ **Inline Elements** | Forms, galleries and lists support |

---

## 📋 Requirements

- **Python 3.10+**
- **API Credentials** from [Telegram Apps](https://my.telegram.org/apps)

---

## 📚 Documentation

| Type | Link |
|------|------|
| **User Documentation** | [heroku-ub.xyz](https://heroku-ub.xyz/) |
| **Developer Docs** | [dev.heroku-ub.xyz](https://dev.heroku-ub.xyz/) |

---

## 💬 Support

[![Telegram Support](https://img.shields.io/badge/Telegram-Support_Group-2594cb?logo=telegram)](https://t.me/heroku_talks)

---

## ⚠️ Usage Disclaimer

> This project is provided as-is. The developer takes **NO responsibility** for:
> - Account bans or restrictions
> - Message deletions by Telegram
> - Security issues from scam modules
> - Session leaks from malicious modules
>
> **Security Recommendations:**
> - Enable `.api_fw_protection`
> - Avoid installing many modules at once
> - Review [Telegram's Terms](https://core.telegram.org/api/terms)

---

## 🙏 Acknowledgements

- [**Hikari**](https://gitlab.com/hikariatama) for Hikka (project foundation)
- [**Lonami**](https://t.me/lonami) for Telethon (Heroku-TL backbone)
