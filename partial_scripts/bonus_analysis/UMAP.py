"""Embed saved training parameter configurations in 2D, colored by performance."""
import argparse
import csv
import json
import os
from importlib import metadata
from pathlib import Path

os.environ.setdefault("NUMBA_NUM_THREADS", "1")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import StrMethodFormatter
import numpy as np

try:
    from .common import load_json, output_path, resolve_run_dir
except ImportError:
    from common import load_json, output_path, resolve_run_dir


MINIMUM_BUY_TRADES = 20

COLOR_FIELDS = {
    "objective": ("objective_value", "Training objective ($; higher is better)"),
    "relative-profit": ("relative_profit_amount", "Benchmark-relative training profit ($)"),
    "profit": ("profit_amount", "Absolute training profit ($)"),
}


def prepare_trials(history, minimum_buys):
    minimum_buys = max(MINIMUM_BUY_TRADES, minimum_buys)
    selected = sorted(
        (trial for trial in history if trial.get("status") == "completed"
         and trial.get("params") and int(trial.get("buy_trades", 0)) >= minimum_buys),
        key=lambda trial: int(trial["trial"]),
    )
    if not selected:
        return selected, np.empty((0, 0)), {"parameters": [], "varying_parameters": [], "bounds": {}}
    parameters = sorted(selected[0]["params"])
    for trial in selected:
        if set(trial["params"]) != set(parameters):
            raise ValueError(f"Trial {trial['trial']} has a different parameter schema; cannot compare these configurations.")
    values = np.asarray([[float(trial["params"][name]) for name in parameters] for trial in selected], dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Parameter vectors contain non-finite values.")
    low, high = values.min(axis=0), values.max(axis=0)
    varying = high > low
    normalized = (values[:, varying] - low[varying]) / (high[varying] - low[varying])
    details = {
        "parameters": parameters,
        "varying_parameters": [name for name, keep in zip(parameters, varying) if keep],
        "bounds": {name: [float(a), float(b)] for name, a, b in zip(parameters, low, high)},
    }
    return selected, normalized, details


def embed_parameters(values, neighbors=15, min_dist=0.1, seed=42):
    if len(values) < 3 or values.shape[1] == 0 or len(np.unique(values, axis=0)) < 3:
        return None, None
    try:
        from umap import UMAP
    except ImportError as error:
        raise RuntimeError("UMAP is unavailable. Run run_bonus_analysis.sh to set up its separate analysis environment.") from error
    neighbors = min(neighbors, len(values) - 1)
    reducer = UMAP(n_components=2, n_neighbors=neighbors, min_dist=min_dist,
                   metric="euclidean", random_state=seed, n_jobs=1,
                   init="spectral" if len(values) > 3 else "random")
    embedding = reducer.fit_transform(values)
    if not np.isfinite(embedding).all():
        raise ValueError("UMAP produced non-finite coordinates.")
    return embedding, neighbors


def plot_strategy(name, trials, embedding, details, color_by, run_name, minimum_buys):
    figure, axis = plt.subplots(figsize=(11.7, 8.3))
    figure.suptitle(f"{name} — UMAP of training configurations", fontsize=16, fontweight="bold", y=0.97)
    figure.text(0.5, 0.925,
                f"{run_name}\n{len(trials)} trials · {len(details['varying_parameters'])} varying parameters · minimum buys: {minimum_buys}",
                ha="center", va="top", fontsize=9)
    if embedding is None:
        axis.text(0.5, 0.5, "At least three distinct eligible configurations\nwith varying parameters are needed for UMAP.",
                  ha="center", va="center", transform=axis.transAxes)
        axis.set_axis_off()
    else:
        field, label = COLOR_FIELDS[color_by]
        colors = np.asarray([float(trial[field]) for trial in trials])
        if not np.isfinite(colors).all():
            raise ValueError(f"{name}: non-finite performance values in {field}.")
        order = np.argsort(colors, kind="stable")
        scatter = axis.scatter(embedding[order, 0], embedding[order, 1], c=colors[order],
                               cmap="viridis", vmin=-20000, vmax=10000, s=28, alpha=0.85, linewidths=0, rasterized=True)
        bar = figure.colorbar(scatter, ax=axis, pad=0.025)
        bar.set_label(label)
        bar.ax.yaxis.set_major_formatter(StrMethodFormatter("${x:,.0f}"))
        best = max(range(len(trials)), key=lambda i: float(trials[i]["objective_value"]))
        axis.scatter(*embedding[best], marker="*", s=260, color="#ed6138", edgecolors="black", linewidths=0.8,
                     zorder=4, label=f"Best objective: trial {int(trials[best]['trial'])}")
        axis.legend(loc="best", fontsize=9)
        axis.set_xlabel("UMAP 1")
        axis.set_ylabel("UMAP 2")
        axis.grid(alpha=0.15)
        axis.spines[["top", "right"]].set_visible(False)
    figure.text(0.5, 0.035,
                "Embedding uses observed-range-normalized parameters only; performance is used only for colour.\n"
                "Each strategy is embedded separately. Colours are sampled training outcomes from different stock/time subsets.",
                ha="center", fontsize=8, color="#555555")
    figure.subplots_adjust(top=0.84, bottom=0.13, left=0.09, right=0.94)
    return figure


def generate(run_dir, destination=None, *, neighbors=15, min_dist=0.1, seed=42,
             color_by="objective"):
    if neighbors < 2 or not 0 <= min_dist <= 1 or not 0 <= seed < 2**32:
        raise ValueError("Use neighbors >= 2, 0 <= min-dist <= 1, and a seed between 0 and 2**32-1.")
    run_dir = resolve_run_dir(run_dir)
    source = run_dir / "artifacts" / "json" / "trainable_penguin_parameter_log.json"
    saved = load_json(source)
    histories = {}
    for trial in saved.get("trial_history", []):
        if trial.get("status") == "completed":
            histories.setdefault(trial["strategy"], []).append(trial)
    if not histories:
        raise ValueError(f"No completed training trials found in {source}")
    minimum_buys = max(MINIMUM_BUY_TRADES, int(saved.get("minimum_buy_trades", MINIMUM_BUY_TRADES)))
    destination = output_path(run_dir, destination, "umap_pareto.pdf")
    details_by_strategy = {}
    coordinates = []
    with PdfPages(destination, metadata={"Title": "UMAP of training parameter configurations"}) as pdf:
        for name, history in sorted(histories.items()):
            trials, values, details = prepare_trials(history, minimum_buys)
            print(f"Embedding {name}: {len(trials)}/{len(history)} trials, {values.shape[1]} varying parameters", flush=True)
            embedding, used_neighbors = embed_parameters(values, neighbors, min_dist, seed)
            details.update({"completed_trials": len(history), "plotted_trials": len(trials),
                            "n_neighbors": used_neighbors, "embedded": embedding is not None})
            details_by_strategy[name] = details
            figure = plot_strategy(name, trials, embedding, details, color_by, run_dir.name, minimum_buys)
            pdf.savefig(figure)
            plt.close(figure)
            best_trial = max(trials, key=lambda t: float(t["objective_value"]))["trial"] if trials else None
            for index, trial in enumerate(trials):
                coordinates.append({
                    "strategy": name, "trial": trial["trial"],
                    "umap_1": float(embedding[index, 0]) if embedding is not None else "",
                    "umap_2": float(embedding[index, 1]) if embedding is not None else "",
                    "objective_value": trial["objective_value"],
                    "relative_profit_amount": trial.get("relative_profit_amount", ""),
                    "profit_amount": trial.get("profit_amount", ""),
                    "buy_trades": trial.get("buy_trades", 0), "best_objective": trial["trial"] == best_trial,
                })
    csv_path = destination.with_suffix(".csv")
    fields = ["strategy", "trial", "umap_1", "umap_2", "objective_value", "relative_profit_amount", "profit_amount", "buy_trades", "best_objective"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(coordinates)
    settings = {
        "source": str(source), "umap_version": metadata.version("umap-learn"),
        "seed": seed, "n_neighbors": neighbors, "min_dist": min_dist, "metric": "euclidean",
        "color_by": color_by, "minimum_buys": minimum_buys,
        "scaling": "min-max of observed eligible parameter values; constant parameters removed",
        "performance_used_as_embedding_feature": False, "strategies": details_by_strategy,
    }
    destination.with_suffix(".json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {destination} ({len(histories)} strategy pages)")
    print(f"Saved {csv_path} and {destination.with_suffix('.json')}")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="Run directory or path below run_log.")
    parser.add_argument("--output", type=Path, help="Output PDF; default: artifacts/umap_pareto.pdf")
    parser.add_argument("--neighbors", type=int, default=15)
    parser.add_argument("--min-dist", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42, help="UMAP layout seed; does not change any experiment seed.")
    parser.add_argument("--color-by", choices=COLOR_FIELDS, default="objective")
    args = parser.parse_args()
    generate(args.run_dir, args.output, neighbors=args.neighbors, min_dist=args.min_dist,
             seed=args.seed, color_by=args.color_by)


if __name__ == "__main__":
    main()
