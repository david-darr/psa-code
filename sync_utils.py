# sync_utils.py
import datetime
import json
import os

LOG_FILE = "sync_log.txt"


def append_log(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {msg}\n")


def read_log():
    if not os.path.exists(LOG_FILE):
        return "No logs available."
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return f.read()


def write_last_sync_time(meta_file="last_sync.txt"):
    with open(meta_file, "w") as f:
        f.write(datetime.datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"))


def read_last_sync_time(meta_file="last_sync.txt"):
    if not os.path.exists(meta_file):
        return None
    with open(meta_file, "r") as f:
        return f.read().strip()
