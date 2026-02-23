"""Archive management utilities."""

import os
import shutil
from datetime import datetime


def save_run_results_to_archive(run_start_time):
    """Save completed run to both run_old/YYMMDD/HHMM/ and keep in run_current/."""
    run_current_dir = "run_current"
    run_old_dir = "run_old"
    
    # Check if run_current has any files
    if not os.path.exists(run_current_dir):
        return
    
    files_in_current = os.listdir(run_current_dir)
    # Filter out __pycache__ and only check for actual output files
    output_files = [f for f in files_in_current if not f.startswith('.')]
    
    if not output_files:
        return
    
    # Create run_old directory if it doesn't exist
    os.makedirs(run_old_dir, exist_ok=True)
    
    # Create timestamped subdirectory in run_old using run start time
    # Round time down to nearest 10-minute interval
    date_part = run_start_time.strftime("%y%m%d")
    rounded_minute = (run_start_time.minute // 10) * 10
    time_part = f"{run_start_time.hour:02d}{rounded_minute:02d}"
    
    # Create date folder if needed
    date_folder = os.path.join(run_old_dir, date_part)
    os.makedirs(date_folder, exist_ok=True)
    
    # Create run folder with time (format: run_old/YYMMDD/HHMM/)
    run_folder = os.path.join(date_folder, time_part)
    
    # If folder already exists (same 10-minute window), add a counter
    counter = 1
    original_run_folder = run_folder
    while os.path.exists(run_folder):
        run_folder = f"{original_run_folder}_{counter}"
        counter += 1
    
    os.makedirs(run_folder, exist_ok=True)
    
    # Copy all files from run_current to the timestamped folder in run_old
    print(f"\n💾 Saving run results...")
    for file in output_files:
        src = os.path.join(run_current_dir, file)
        dst = os.path.join(run_folder, file)
        try:
            if os.path.isdir(src):
                # For directories, copy contents
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                # For files, copy
                shutil.copy2(src, dst)
            print(f"  📦 Saved: {file} → {run_folder}")
        except Exception as e:
            print(f"  ⚠️ Failed to save {file}: {e}")
    
    print(f"✅ Run saved to: {run_folder}")
