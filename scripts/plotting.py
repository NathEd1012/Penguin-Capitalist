"""Plotting and visualization utilities."""

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from config import INITIAL_CAPITAL


def plot_capital_curves(curves, filename):
    """Plot and save capital curves."""
    plt.figure(figsize=(12, 6))
    for name, vals in curves.items():
        plt.plot(range(1, len(vals) + 1), vals, label=name, linewidth=3)

    # Calculate and plot overall average capital
    if curves:
        curve_values = list(curves.values())
        num_penguins = len(curve_values)
        overall_avg = [
            sum(vals[i] for vals in curve_values) / num_penguins
            for i in range(len(curve_values[0]))
        ]
        plt.plot(
            range(1, len(overall_avg) + 1),
            overall_avg,
            marker=None,
            label="Overall Average Capital",
            linewidth=3,
            color="black",
            linestyle="--",
        )

    plt.axhline(
        y=INITIAL_CAPITAL,
        color="gray",
        linestyle="--",
        alpha=0.5,
        label="Initial Capital",
    )
    plt.xlabel("Minute")
    plt.ylabel("Total Capital ($)")
    plt.title(f"Penguin Capital Curves")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=100)
    print(f"📈 Updated capital curves to {filename}")


def create_final_report_pdf(curves, portfolios, filename, latest_prices=None):
    """Create PDF with capital curves and per-symbol trade summary."""
    with PdfPages(filename) as pdf:
        # Page 1: Capital Curves
        fig, ax = plt.subplots(figsize=(12, 8))

        for name, vals in curves.items():
            ax.plot(range(1, len(vals) + 1), vals, label=name, linewidth=2)

        # Calculate and plot overall average capital
        if curves:
            curve_values = list(curves.values())
            num_penguins = len(curve_values)
            overall_avg = [
                sum(vals[i] for vals in curve_values) / num_penguins
                for i in range(len(curve_values[0]))
            ]
            ax.plot(
                range(1, len(overall_avg) + 1),
                overall_avg,
                marker=None,
                label="Overall Average Capital",
                linewidth=2.5,
                color="black",
                linestyle="--",
            )

        ax.axhline(
            y=INITIAL_CAPITAL,
            color="gray",
            linestyle="--",
            alpha=0.5,
            label="Initial Capital",
        )
        ax.set_xlabel("Minute")
        ax.set_ylabel("Total Capital ($)")
        ax.set_title(f"Penguin Capital Curves")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close()

        # Page 2+: Trade Summary Table for each Penguin
        for penguin_name, portfolio in sorted(portfolios.items()):
            fig = plt.figure(figsize=(12, 10))
            ax = fig.add_subplot(111)
            ax.axis("tight")
            ax.axis("off")

            summary = portfolio.get_symbol_summary(latest_prices or {})

            cash = portfolio.cash
            market_value = 0.0
            if latest_prices:
                for symbol, pos in portfolio.positions.items():
                    if symbol in latest_prices:
                        market_value += pos.qty * latest_prices[symbol]
            total_value = cash + market_value

            # Build table data
            table_data = [
                [
                    "Symbol",
                    "Buy Cnt",
                    "Sell Cnt",
                    "Pos Qty",
                    "Market Value",
                    "Total Cost",
                    "Total Revenue",
                    "Total PnL",
                    "PnL %",
                ]
            ]

            total_pnl = 0
            for symbol in sorted(summary.keys()):
                s = summary[symbol]
                pnl = s["total_pnl"]
                pnl_pct = s["pnl_pct"]
                total_pnl += pnl

                table_data.append(
                    [
                        symbol,
                        str(s["buy_count"]),
                        str(s["sell_count"]),
                        str(s["position_qty"]),
                        f"${s['market_value']:,.2f}",
                        f"${s['total_cost']:,.2f}",
                        f"${s['total_revenue']:,.2f}",
                        f"${pnl:,.2f}",
                        f"{pnl_pct:+.2f}%",
                    ]
                )

            # Add total row
            table_data.append(
                [
                    "TOTAL",
                    "",
                    "",
                    "",
                    f"${market_value:,.2f}",
                    "",
                    "",
                    f"${total_pnl:,.2f}",
                    "",
                ]
            )

            table = ax.table(
                cellText=table_data,
                cellLoc="center",
                loc="center",
                colWidths=[0.09, 0.08, 0.08, 0.08, 0.13, 0.13, 0.13, 0.12, 0.09],
            )
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1, 2)

            # Style header row
            for i in range(len(table_data[0])):
                table[(0, i)].set_facecolor("#4472C4")
                table[(0, i)].set_text_props(weight="bold", color="white")

            # Style total row
            for i in range(len(table_data[0])):
                table[(len(table_data) - 1, i)].set_facecolor("#E7E6E6")
                table[(len(table_data) - 1, i)].set_text_props(weight="bold")

            title = f"Trade Summary: {penguin_name}"
            fig.suptitle(title, fontsize=14, weight="bold", y=0.98)

            # Portfolio totals at the top
            summary_text = (
                f"Cash: ${cash:,.2f}    "
                f"Market Value: ${market_value:,.2f}    "
                f"Total Value: ${total_value:,.2f}"
            )
            fig.text(0.5, 0.93, summary_text, ha="center", fontsize=11)

            plt.tight_layout()
            pdf.savefig(fig, bbox_inches="tight")
            plt.close()

    print(f"📄 Final report saved to {filename}")
