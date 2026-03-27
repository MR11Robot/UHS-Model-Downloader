import re
import time
import glob
import os
import shutil
import zipfile
import rarfile
import sqlite3
import requests
import json

BASE_URL = "https://raw.githubusercontent.com/wootguy/pmodels/master/database/sc"

# ==================== CONFIG ====================

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(config_path):
        print("[ERROR] config.json not found!")
        exit(1)
    with open(config_path, 'r') as f:
        return json.load(f)

config = load_config()

rarfile.UNRAR_TOOL = config["unrar_tool"]
SEARCH_DIRS = config["search_dirs"]
INSTALL_DIR = config["install_dir"]
TEMP_DIR = config["temp_dir"]
LOG_DIR = config["log_dir"]
SCAN_TIMEOUT = config["scan_timeout"]

# ==================== DATABASE ====================

def init_db():
    conn = sqlite3.connect("models.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS requested_models (
            model_name TEXT PRIMARY KEY,
            status TEXT,
            installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS installed_folders (
            folder_name TEXT PRIMARY KEY,
            installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def is_model_requested(model_name):
    conn = sqlite3.connect("models.db")
    c = conn.cursor()
    c.execute("SELECT model_name FROM requested_models WHERE model_name = ?", (model_name,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_model_requested(model_name, status="installed"):
    conn = sqlite3.connect("models.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO requested_models (model_name, status) VALUES (?, ?)", (model_name, status))
    conn.commit()
    conn.close()

def is_folder_installed(folder_name):
    conn = sqlite3.connect("models.db")
    c = conn.cursor()
    c.execute("SELECT folder_name FROM installed_folders WHERE folder_name = ?", (folder_name,))
    result = c.fetchone()
    conn.close()
    return result is not None

def mark_folder_installed(folder_name):
    conn = sqlite3.connect("models.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO installed_folders (folder_name) VALUES (?)", (folder_name,))
    conn.commit()
    conn.close()

# ==================== WOOTDATA ====================

def get_repo_id(model_name):
    hash_val = 0
    for char in model_name:
        hash_val = ((hash_val << 5) - hash_val) + ord(char)
        hash_val = hash_val % 15485863
    return hash_val % 32

def get_md5_from_wootdata(model_name):
    repo_id = get_repo_id(model_name.lower())
    url = f"https://wootdata.github.io/scmodels_data_{repo_id}/models/player/{model_name.lower()}/{model_name.lower()}.json"
    r = requests.get(url)
    if r.status_code == 200:
        return r.json().get("md5")
    return None

# ==================== HELPERS ====================

def folder_exists_on_disk(folder_name):
    for search_dir in SEARCH_DIRS:
        path = os.path.join(search_dir, folder_name)
        if os.path.exists(path):
            return True
    return False

def find_model_folders(extract_path):
    model_folders = []
    for root, dirs, files in os.walk(extract_path):
        if any(f.endswith(".mdl") for f in files):
            model_folders.append(root)
    return model_folders

def extract_file(filepath, extract_to):
    if filepath.endswith(".zip"):
        with zipfile.ZipFile(filepath, 'r') as z:
            z.extractall(extract_to)
    elif filepath.endswith(".rar"):
        with rarfile.RarFile(filepath, 'r') as r:
            r.extractall(extract_to)

# ==================== DOWNLOADER ====================

def download_and_install(model_name, hashes, sources):
    if is_model_requested(model_name):
        print(f"  [SKIP] {model_name} already processed")
        return True

    print(f"  [*] Searching: {model_name}")

    md5 = None
    model_name_lower = model_name.lower()
    for hash_val, models in hashes.items():
        if any(m.lower() == model_name_lower for m in models):
            md5 = hash_val
            break

    if not md5:
        print(f"  [NOT FOUND IN HASHES] trying wootdata...")
        md5 = get_md5_from_wootdata(model_name)
        if not md5:
            print(f"  [NOT FOUND] {model_name}")
            mark_model_requested(model_name, "not_found")
            return False
        print(f"  [FOUND VIA WOOTDATA] md5: {md5}")

    if md5 not in sources:
        print(f"  [NO SOURCE] {model_name}")
        mark_model_requested(model_name, "no_source")
        return False

    for source in sources[md5]:
        if source.startswith("gb:"):
            gb_id = source.split(":")[1]
            api = f"https://api.gamebanana.com/Core/Item/Data?itemtype=Mod&itemid={gb_id}&fields=Files().aFiles()"
            data = requests.get(api).json()

            if not data or not data[0]:
                print(f"  [TRASHED] gb:{gb_id}")
                mark_model_requested(model_name, "trashed")
                return False

            files = data[0]
            first_file = list(files.values())[0]
            url = first_file["_sDownloadUrl"]
            filename = first_file["_sFile"]

            print(f"  [DOWNLOADING] {filename}...")

            os.makedirs(TEMP_DIR, exist_ok=True)
            filepath = os.path.join(TEMP_DIR, filename)

            r = requests.get(url, stream=True)
            total = int(r.headers.get("content-length", 0))
            downloaded = 0

            with open(filepath, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        print(f"\r  Progress: {int(downloaded/total*100)}%", end="")

            print(f"\n  [EXTRACTING]...")
            extract_path = os.path.join(TEMP_DIR, model_name)
            os.makedirs(extract_path, exist_ok=True)

            try:
                extract_file(filepath, extract_path)
            except Exception as e:
                print(f"  [ERROR] Failed to extract: {e}")
                shutil.rmtree(TEMP_DIR)
                mark_model_requested(model_name, "extract_error")
                return False

            model_folders = find_model_folders(extract_path)

            if not model_folders:
                print(f"  [NO MDL FOUND] {model_name}")
                shutil.rmtree(TEMP_DIR)
                mark_model_requested(model_name, "no_mdl")
                return False

            for folder in model_folders:
                folder_name = os.path.basename(folder)

                if is_folder_installed(folder_name) or folder_exists_on_disk(folder_name):
                    print(f"  [SKIP] {folder_name} already exists")
                    mark_folder_installed(folder_name)
                    continue

                dest = os.path.join(INSTALL_DIR, folder_name)
                shutil.copytree(folder, dest)
                mark_folder_installed(folder_name)
                print(f"  [INSTALLED] {folder_name}")

            shutil.rmtree(TEMP_DIR)
            mark_model_requested(model_name, "installed")
            return True

    return False

# ==================== LOG WATCHER ====================

def get_latest_log():
    logs = glob.glob(os.path.join(LOG_DIR, "console-*.log"))
    if not logs:
        return None
    return max(logs, key=os.path.getmtime)

def parse_model(line):
    match = re.search(r'\[AF2P\] Player .+ model is (.+)', line)
    if match:
        return match.group(1).strip()
    return None

def watch_log():
    init_db()

    print("[*] Loading database from GitHub...")
    hashes = requests.get(f"{BASE_URL}/hashes.json").json()
    sources = requests.get(f"{BASE_URL}/sources.json").json()
    print("[*] Database loaded!")
    print("-" * 40)

    models = set()
    scan_count = 0
    last_model_time = None

    log_path = get_latest_log()
    if not log_path:
        print("Log file not found!")
        return

    print(f"Watching: {log_path}")
    print("-" * 40)

    with open(log_path, 'r', errors='ignore') as f:
        f.seek(0, 2)

        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                if models and last_model_time and (time.time() - last_model_time) > SCAN_TIMEOUT:
                    scan_count += 1
                    print(f"\n{'='*40}")
                    print(f"Scan #{scan_count} - {len(models)} models found")
                    print(f"{'='*40}")
                    print("[*] Starting downloads...")
                    print("-" * 40)
                    for model in models:
                        download_and_install(model, hashes, sources)
                    print("\n[ALL DONE]")
                    print("-" * 40)
                    models = set()
                    last_model_time = None
                continue

            model = parse_model(line)
            if model:
                if model not in models:
                    models.add(model)
                    last_model_time = time.time()
                    print(f"  [{len(models)}] {model}")

def main():
    watch_log()

if __name__ == "__main__":
    main()