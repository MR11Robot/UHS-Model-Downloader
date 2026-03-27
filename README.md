# UHS Model Downloader

Automatic player model downloader for the **UHS (Ultimate Hardcore Survival)** Sven Co-op server.

Watches your Sven Co-op console log and automatically downloads and installs any missing player models from GameBanana — no manual work needed.

---

## Requirements

- Python 3.14+
- [UnRAR](https://www.rarlab.com/download.htm) installed on your system (required for `.rar` extraction)
- Sven Co-op installed via Steam

---

## Installation

```bash
git clone https://github.com/MR11Robot/UHS-Model-Downloader
```

---

## Setup

### 1. Create a virtual environment & activate
```bash
cd UHS-Model-Downloader
python -m venv .venv
.\.venv\Scripts\activate
```

### 2. Install dependencies
```bash
pip install poetry
poetry install
```

### 3. Enable Console Logging in Sven Co-op

The tool works by reading Sven Co-op's console log file, so you need to enable it first.

1. Launch Sven Co-op
2. Open the in-game console (default: `~`)
3. Type the following command and hit Enter:

```
condebug
```

You should see this confirmation message:

```
Console debugging enabled: console-*.log
```

The log files are saved in your Sven Co-op folder, e.g.:
```
C:\Program Files (x86)\Steam\steamapps\common\Sven Co-op\
```

---

### 4. Configure `config.json`

Create a `config.json` file in the project directory:

```json
{
    "unrar_tool": "C:\\Program Files\\WinRAR\\UnRAR.exe",
    "search_dirs": [
        "C:\\Steam\\steamapps\\common\\Sven Co-op\\svencoop\\models\\player",
        "C:\\Steam\\steamapps\\common\\Sven Co-op\\svencoop_addon\\models\\player",
        "C:\\Steam\\steamapps\\common\\Sven Co-op\\svencoop_downloads\\models\\player"
    ],
    "install_dir": "C:\\Steam\\steamapps\\common\\Sven Co-op\\svencoop_addon\\models\\player",
    "temp_dir": "temp",
    "log_dir": "C:\\Steam\\steamapps\\common\\Sven Co-op",
    "scan_timeout": 3
}
```

| Key | Description |
|---|---|
| `unrar_tool` | Full path to `UnRAR.exe` |
| `search_dirs` | Directories to check for already-installed models (checked before downloading) |
| `install_dir` | Where new models will be installed |
| `temp_dir` | Temporary folder used during download and extraction |
| `log_dir` | Directory containing the `console-*.log` files |
| `scan_timeout` | Seconds to wait after the last detected model before starting downloads |

---

## Usage

```bash
python main.py
```

The tool will start watching the latest log file. Once you join the UHS server and players start loading, it will collect all missing models and download them automatically.

---

## How It Works

1. Watches the latest `console-*.log` file in `log_dir`
2. Detects lines matching `[AF2P] Player ... model is ...`
3. Collects models until no new ones appear for `scan_timeout` seconds
4. Looks up each model's MD5 hash from the [pmodels](https://github.com/wootguy/pmodels) database
5. Falls back to [wootdata](https://github.com/wootguy) if the model isn't in the main database
6. Downloads the model from GameBanana, extracts it, and copies it to the install directory
7. Records everything in a local `models.db` SQLite database to avoid re-downloading

---

## Database

The tool creates a local `models.db` file with two tables:

- **`requested_models`** — every model that was looked up, with its status: `installed`, `not_found`, `no_source`, `trashed`, `extract_error`, or `no_mdl`
- **`installed_folders`** — every model folder that was successfully installed

---

## Author

**MR11Robot** — taha.youssef.fares@gmail.com