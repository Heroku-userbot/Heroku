<div align="center">
  <img src="https://github.com/hikariatama/assets/raw/master/1326-command-window-line-flat.webp" height="80">
  <h1>Heroku Userbot</h1>
  <p>Продвинутый юзербот для Telegram с повышенной безопасностью и современными функциями</p>

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
  </p>
</div>

---

## ⚠️ Уведомление о безопасности

> Важное предупреждение о безопасности  
> Хотя Heroku реализует расширенные меры безопасности, установка модулей от ненадежных разработчиков все еще может нанести вред вашему серверу/аккаунту.
> 
> Рекомендации:
> - ✅ Загружайте модули исключительно из официальных репозиториев или от доверенных разработчиков
> - ❌ НЕ устанавливайте модули, если не уверены в их безопасности
> - ⚠️ Будьте осторожны с неизвестными командами (.terminal, .eval, .ecpp и т.д.)

---
## 🚀 Установка

### Альтернатива: универсальный установщик (Linux, WSL, UserLAnd)
Способ установки одной командой, основной остаётся пошаговая инструкция ниже.
Он ставит зависимости, создаёт виртуальное окружение (`.venv`) и запускает Heroku. Та же команда при повторном запуске просто запустит уже установленный Heroku.

```bash
curl -fsSL https://raw.githubusercontent.com/Heroku-userbot/Heroku/master/install.sh | bash
```

> - Для root-пользователей добавьте `-s -- --root` (`... | bash -s -- --root`)
> - `HEROKU_FORCE_INSTALL=1` принудительно запускает переустановку

### VPS/VDS
> **Примечание для пользователей VPS/VDS:**  
> Добавьте `--root` для пользователей root (чтобы избежать ввода force_insecure)

<details>
  <summary><b>Ubuntu / Debian</b></summary>

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



### Другие
<details>
  <summary><b>WSL(Windows)</b></summary>

  > **⚠️ ВНИМАНИЕ: Может быть нестабильно!**

1. **Скачайте WSL.** Для этого откройте PowerShell с правами администратора и введите в консоль
```powershell
wsl --install -d Ubuntu-22.04
```

> *⚠️Для установки требуется Windows 10 сборки 2004 или Windows 11 любой версии и ПК с поддержкой виртуализации.*
> *Для установки на более ранние ОС, пожалуйста, обратитесь к этой [странице](https://learn.microsoft.com/ru-ru/windows/wsl/install-manual).*

2. **Перезагрузите ПК и запустите программу Ubuntu 22.04.x**
3. **Введите эту команду (ПКМ):**
```bash
curl -Ss https://bootstrap.pypa.io/get-pip.py | python3
```
> *⚠️ Если появятся желтые предупреждения, введите export PATH="/home/username/.local/bin:$PATH", заменив /home/username/.local/bin путем, указанным в сообщении*

4. **Введите эту команду (ПКМ):**
```bash
clear && git clone https://github.com/Heroku-userbot/Heroku && cd Heroku && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python3 -m heroku
```
> **🔗Как получить API_ID и API_HASH?:** [Видео](https://youtu.be/DcqDA249Lhg?t=24)
  
</details>

<details>
  <summary><b>Phone(Userland)</b></summary>
  
 1. <b>Установите UserLAnd по</b> <a href="https://play.google.com/store/apps/details?id=tech.ula">ссылке</a>
2. <b>Откройте его, выберите Ubuntu —> Minimal —> Terminal</b>
3. <b>Дождитесь установки дистрибутива, можете заварить чай</b>
4. <b>После успешной установки перед вами откроется терминал, введите туда:</b>
```bash
sudo apt update ; sudo apt upgrade -y ; sudo apt install -y python3 python3-venv git ; git clone https://github.com/Heroku-userbot/Heroku ; cd Heroku ; python3 -m venv venv ; source venv/bin/activate ; python3 -m heroku
```
5. <b>В конце установки появится ссылка, перейдите по ней и введите данные своей учетной записи для входа.</b>
> Вуаля! Вы установили Heroku на UserLAnd.
</details>

### Официальные хосты
<details>
<summary><b>🌘 HikkaHost</b></summary>
  
 1. Перейдите в [@hikkahost_bot](https://.me/hikkahost_bot)
2. Нажмите "Установить"
3. Выберите "🪐 Heroku"
И продолжайте установку.

> **После этого вы получите ссылку, откройте ее и войдите в свою учетную запись.**

</details>



## Дополнительные функции

<details>
  <summary><b>🔒 Автоматическое резервное копирование базы данных</b></summary>
  <img src="https://user-images.githubusercontent.com/36935426/202905566-964d2904-f3ce-4a14-8f05-0e7840e1b306.png" width="400">
</details>

<details>
  <summary><b>👋 Приветственные экраны установки</b></summary>
  <img src="https://user-images.githubusercontent.com/36935426/202905720-6319993b-697c-4b09-a194-209c110c79fd.png" width="300">
  <img src="https://user-images.githubusercontent.com/36935426/202905746-2a511129-0208-4581-bb27-7539bd7b53c9.png" width="300">
</details>

---

## ✨ Ключевые особенности и улучшения

| Особенность | Описание |
|-------------|------------|
| 🆕 Последний слой Telegram | Поддержка форумов и новейших функций Telegram |
| 🔒 Повышенная безопасность | Нативное кэширование сущностей и целевые правила безопасности |
| 🎨 Улучшения UI/UX | Современный интерфейс и пользовательский опыт |
| 📦 Основные модули | Улучшенный и новый основной функционал |
| ⏱️ Быстрое исправление ошибок | Более быстрое решение, чем у FTG/GeekTG |
| 🔄 Обратная совместимость | Работает с модулями FTG, GeekTG и Hikka |
| ▶️ Инлайн-элементы | Поддержка форм, галерей и списков |

---

## 📋 Требования

- Python 3.10+
- Учетные данные API из [Telegram Apps](https://my.telegram.org/apps)

---

## 📚 Документация

| Тип | Ссылка |
|------|-------|
| Документация для пользователей | [heroku-ub.xyz](https://heroku-ub.xyz/) |
| Документация для разработчиков | [dev.heroku-ub.xyz](https://dev.heroku-ub.xyz/) |

---

## 💬 Поддержка

[![Поддержка Telegram](https://img.shields.io/badge/Telegram-Support_Group-2594cb?logo=telegram)](https://t.me/heroku_talks)

---

## ⚠️ Отказ от ответственности за использование

> Этот проект предоставляется «как есть». Разработчик НЕ несет ответственности за:
> - Блокировки или ограничения аккаунта
> - Удаления сообщений Telegram
> - Проблемы безопасности, вызванные мошенническими модулями
> - Утечки сессий, вызванные вредоносными модулями
>
> Рекомендации по безопасности:
> - Включите .api_fw_protection
> - Избегайте одновременной установки множества модулей
> - Ознакомьтесь с [telegram TOS](https://core.telegram.org/api/terms)

---

## 🙏 Благодарности

- [Hikari](https://gitlab.com/hikariatama) за Hikka (основа проекта)
- [Lonami](https://t.me/lonami) за Telethon (основа Heroku-TL)
