import json
import gzip
import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import ttk

# -----------------------------
# CONFIG
# -----------------------------
INPUT_FOLDER = r"C:\JsonSize\Input"
OUTPUT_FOLDER = r"C:\JsonSize\Output"
UNCOMPRESS_FOLDER = r"C:\JsonSize\Uncompress"

MAX_THREADS = 4
DROP_KEYS = {"tran_schedule_details"}

# -----------------------------
# Rollup Logic
# -----------------------------
def rollup_hourly_tsd(records):
    if not records:
        return records

    rolled = []
    current = records[0].copy()

    for next_rec in records[1:]:

        same_values = (
            current.get("volume__MWH_") == next_rec.get("volume__MWH_") and
            current.get("rate__MW_") == next_rec.get("rate__MW_") and
            current.get("price") == next_rec.get("price")
        )

        if same_values:
            current["end_date"] = next_rec["end_date"]
            current["volume__MWH_"] += next_rec["volume__MWH_"]
        else:
            rolled.append(current)
            current = next_rec.copy()

    rolled.append(current)
    return rolled


# -----------------------------
# Clean + Drop Logic
# -----------------------------
def clean_json(obj):

    if isinstance(obj, dict):
        new_dict = {}

        for k, v in obj.items():

            if k in DROP_KEYS:
                continue

            if k == "hourly_tsd" and isinstance(v, list):
                v = rollup_hourly_tsd(v)

            new_dict[k] = clean_json(v)

        return new_dict

    elif isinstance(obj, list):
        return [clean_json(i) for i in obj]

    return obj


# -----------------------------
# File Processing
# -----------------------------
def process_file(file_path):

    start_dt = datetime.now()
    start_time = time.time()

    filename = os.path.basename(file_path)
    base_name = filename.replace(".json", "")

    compressed_path = os.path.join(OUTPUT_FOLDER, base_name + "_cleaned.json.gz")
    uncompressed_path = os.path.join(UNCOMPRESS_FOLDER, base_name + "_cleaned.json")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    optimized_data = clean_json(data)

    # Compress
    with gzip.open(compressed_path, "wt", encoding="utf-8") as gz:
        json.dump(optimized_data, gz, separators=(",", ":"))

    # Uncompress
    with gzip.open(compressed_path, "rt", encoding="utf-8") as gz:
        with open(uncompressed_path, "w", encoding="utf-8") as out:
            out.write(gz.read())

    original_size = os.path.getsize(file_path)
    compressed_size = os.path.getsize(compressed_path)

    reduction = (1 - compressed_size / original_size) * 100

    end_dt = datetime.now()
    elapsed = time.time() - start_time

    return (
        filename,
        round(original_size / 1024, 2),
        round(compressed_size / 1024, 2),
        round(reduction, 2),
        start_dt.strftime("%H:%M:%S"),
        end_dt.strftime("%H:%M:%S"),
        round(elapsed, 2),
    )


# -----------------------------
# Run Processing (Multi-threaded)
# -----------------------------
def run_processing():

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(UNCOMPRESS_FOLDER, exist_ok=True)

    files = [
        os.path.join(INPUT_FOLDER, f)
        for f in os.listdir(INPUT_FOLDER)
        if f.endswith(".json")
    ]

    results = []

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(process_file, f) for f in files]

        for future in futures:
            results.append(future.result())

    return results


# -----------------------------
# UI Display (After Processing)
# -----------------------------
def show_dashboard(results):

    root = tk.Tk()
    root.title("JSON Processing Summary")
    root.geometry("1200x450")

    columns = (
        "File",
        "Original KB",
        "Compressed KB",
        "Reduction %",
        "Start Time",
        "End Time",
        "Time (s)",
    )

    tree = ttk.Treeview(root, columns=columns, show="headings")

    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=150)

    for row in results:
        tree.insert("", tk.END, values=row)

    tree.pack(fill=tk.BOTH, expand=True)

    root.mainloop()


# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    results = run_processing()
    show_dashboard(results)