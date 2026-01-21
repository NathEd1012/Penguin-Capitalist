# data/scoreboard.py
import json
import os
from pathlib import Path

SCOREBOARD_FILE = os.path.join(os.path.dirname(__file__), "scoreboard.json")


def load_scoreboard():
    """Load scoreboard from file or return empty dict."""
    if os.path.exists(SCOREBOARD_FILE):
        try:
            with open(SCOREBOARD_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading scoreboard: {e}")
            return {}
    return {}


def save_scoreboard(scoreboard):
    """Save scoreboard to file."""
    try:
        with open(SCOREBOARD_FILE, "w") as f:
            json.dump(scoreboard, f, indent=2)
    except Exception as e:
        print(f"Error saving scoreboard: {e}")


def register_penguin(scoreboard, penguin_name):
    """Add penguin to scoreboard if not already there."""
    if penguin_name not in scoreboard:
        scoreboard[penguin_name] = {"wins": 0, "runs": 0}
    return scoreboard


def record_win(scoreboard, penguin_name):
    """Record a win for a penguin."""
    scoreboard = register_penguin(scoreboard, penguin_name)
    scoreboard[penguin_name]["wins"] += 1
    return scoreboard


def record_run(scoreboard, penguin_name):
    """Record a run participation for a penguin."""
    scoreboard = register_penguin(scoreboard, penguin_name)
    scoreboard[penguin_name]["runs"] += 1
    return scoreboard


def print_scoreboard(scoreboard):
    """Print formatted scoreboard."""
    if not scoreboard:
        print("Scoreboard is empty")
        return

    print("\n" + "=" * 70)
    print("🏆 PENGUIN SCOREBOARD 🏆".center(70))
    print("=" * 70)

    # Sort by wins, then by name
    sorted_penguins = sorted(scoreboard.items(), key=lambda x: (-x[1]["wins"], x[0]))

    for rank, (name, stats) in enumerate(sorted_penguins, 1):
        wins = stats["wins"]
        runs = stats["runs"]
        win_rate = (wins / runs * 100) if runs > 0 else 0
        print(
            f"{rank}. {name:25} Wins: {wins:3d}  Runs: {runs:3d}  Win Rate: {win_rate:5.1f}%"
        )

    print("=" * 70 + "\n")
