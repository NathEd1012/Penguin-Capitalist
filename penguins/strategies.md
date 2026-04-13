# Penguin Strategies (Compact)

Scope: concrete strategy penguins in the main `penguins/` package (excluding `Unused Penguins/`).

| Penguin | Core Idea |
|---|---|
| `SP500` | Benchmark buy-and-hold: buys SPY once with all cash and then holds. |

| `MomentumPenguin` | Simple ROC momentum: buy when 5-bar ROC > 1%, sell when 5-bar ROC < -1%. |

| `RSIMeanReversionPenguin` | Baseline RSI mean reversion: buy oversold RSI, sell overbought RSI. |

| `RSIMeanReversionPenguinStrict1` | RSI mean reversion variant with longer RSI period (30) and same 30/70 thresholds. |

| `RSIMeanReversionPenguinStrict2` | Faster RSI mean reversion variant with shorter RSI period (10) and 30/70 thresholds. |

| `RSIMeanReversionReducedPenguin` | Adaptive RSI mean reversion: shifts oversold/overbought bands daily to target ~1-10 trades/day. |

| `RSIMeanReversionMomentumPenguin` | RSI mean reversion with regime detection (RISING/FALLING/HOLDING) and state-dependent thresholds. |

| `RSIMeanReversionSelectivePenguin` | Low-frequency quality RSI MR with volatility filter, trend-distance filter, cooldown, and daily trade cap. |

| `SmartRSIConfluencePenguin` | Weighted confluence score (RSI + trend + momentum + volatility) with confidence-based sizing and guarded exits. |

| `CopilotPenguin` | Adaptive hybrid (momentum vs mean-reversion) selected by regime confidence, with mode-aware risk/exit rules. |

| `SMA20Penguin` | Robust SMA crossover: confirmed cross-up entries, trend + distance filters, confirmed cross-down/trailing-stop exits. |

| `SMA20AdvancedPenguin` | SMA20Penguin + strength-based dynamic buy sizing with cash reserve control. |

| `MinMaxSRPenguin` | Rolling support/resistance zone trader: buys near support bounce, sells at resistance/support-break/trailing stop. |

| `SRMultiframePenguin` | Plotting placeholder: records multiframe history snapshots, currently does not open trades. |

| `MultitimeframeReactionSRPenguin` | Reaction-level multi-timeframe S/R strategy with touch/bounce entries, momentum fallback entries, and multi-rule exits. |

## Notes

- `BasePenguin` is abstract infrastructure, not a trading strategy.
- `Unused Penguins/` contains experimental/retired strategies not listed here.
