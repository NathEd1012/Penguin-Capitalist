#!/usr/bin/env python3
import os
import re


def rename_files(directory, old_prefix, new_prefix):
    for filename in os.listdir(directory):
        if filename.startswith(old_prefix):
            new_filename = filename.replace(old_prefix, new_prefix, 1)
            match = re.search(r"(\d{4})(\d{4})_(\d{4,6})", new_filename)
            if match:
                year = match.group(1)[2:]
                md = match.group(2)
                time = match.group(3)
                if len(time) == 6:
                    time = time[:-2]  # remove 00
                new_ts = year + md + "_" + time
                old_ts = match.group(1) + match.group(2) + "_" + match.group(3)
                new_filename = new_filename.replace(old_ts, new_ts)
            old_path = os.path.join(directory, filename)
            new_path = os.path.join(directory, new_filename)
            if old_path != new_path:
                try:
                    os.rename(old_path, new_path)
                    print(f"Renamed {filename} to {new_filename}")
                except Exception as e:
                    print(f"Error renaming {filename}: {e}")


# Use absolute paths
rename_files(
    "/Users/nathanael/Documents/Uni/Masterarbeit/VSCode/Penguin-Capitalist/plots",
    "capital_curves_",
    "capital_",
)
rename_files(
    "/Users/nathanael/Documents/Uni/Masterarbeit/VSCode/Penguin-Capitalist/logs",
    "trades_log_",
    "trades_",
)
rename_files(
    "/Users/nathanael/Documents/Uni/Masterarbeit/VSCode/Penguin-Capitalist/logs",
    "curves_data_",
    "data_",
)
