from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin


# Manual tuning block:
# Adjust these values here first so the strategy is easy to finetune by hand.
TRAINABLE_PENGUIN3_BB_PERIOD = 20
TRAINABLE_PENGUIN3_BB_STDDEV = 2.0
TRAINABLE_PENGUIN3_MAX_CASH_FRACTION = 0.05
TRAINABLE_PENGUIN3_STOP_LOSS_PCT = 0.04
TRAINABLE_PENGUIN3_TAKE_PROFIT_PCT = 0.08
TRAINABLE_PENGUIN3_COOLDOWN_BARS = 10


@dataclass
class TrainablePenguin3Params:
	bb_period: int = TRAINABLE_PENGUIN3_BB_PERIOD
	bb_stddev: float = TRAINABLE_PENGUIN3_BB_STDDEV
	max_cash_fraction: float = TRAINABLE_PENGUIN3_MAX_CASH_FRACTION
	stop_loss_pct: float = TRAINABLE_PENGUIN3_STOP_LOSS_PCT
	take_profit_pct: float = TRAINABLE_PENGUIN3_TAKE_PROFIT_PCT
	cooldown_bars: int = TRAINABLE_PENGUIN3_COOLDOWN_BARS


class TrainablePenguin3(BasePenguin):
	LOOKBACK_BARS = 120

	def __init__(
		self,
		name: str = "TrainablePenguin3",
		bb_period: int = TRAINABLE_PENGUIN3_BB_PERIOD,
		bb_stddev: float = TRAINABLE_PENGUIN3_BB_STDDEV,
		max_cash_fraction_per_trade: float = TRAINABLE_PENGUIN3_MAX_CASH_FRACTION,
		stop_loss_pct: float = TRAINABLE_PENGUIN3_STOP_LOSS_PCT,
		take_profit_pct: float = TRAINABLE_PENGUIN3_TAKE_PROFIT_PCT,
		cooldown_bars: int = TRAINABLE_PENGUIN3_COOLDOWN_BARS,
	):
		super().__init__(name)
		self.params = TrainablePenguin3Params(
			bb_period=bb_period,
			bb_stddev=bb_stddev,
			max_cash_fraction=max_cash_fraction_per_trade,
			stop_loss_pct=stop_loss_pct,
			take_profit_pct=take_profit_pct,
			cooldown_bars=cooldown_bars,
		)

	def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio: Portfolio) -> tuple[str, int]:
		min_required = max(60, self.params.bb_period) + 2
		if bid <= 0 or ask <= 0 or len(mid_prices) < min_required:
			return "HOLD", 0

		upper_band, middle_band, lower_band = self._bollinger_bands(mid_prices, self.params.bb_period, self.params.bb_stddev)
		trend_score = self._trend_quality(mid_prices)
		cash = self._get_cash(portfolio)
		shares_owned = self._get_position(portfolio, symbol)
		avg_entry = self._get_avg_entry(portfolio, symbol)
		current_price = mid_prices[-1]

		if shares_owned > 0:
			# SELL part
			loss_trigger = avg_entry is not None and current_price <= avg_entry * (1 - self.params.stop_loss_pct)
			profit_reversal_trigger = avg_entry is not None and current_price >= avg_entry * (1 + self.params.take_profit_pct) and current_price >= upper_band and trend_score < 0.3
			overbought_breakdown_trigger = current_price >= upper_band and trend_score < 0.15
			if loss_trigger or profit_reversal_trigger or overbought_breakdown_trigger:
				return "SELL", shares_owned
		else:
			# BUY part
			buy_signal = current_price <= lower_band and trend_score > 0.5
			if buy_signal:
				# AMOUNT part
				strength = min(1.5, max(0.25, trend_score / 0.5))
				max_trade_value = cash * self.params.max_cash_fraction
				qty = math.floor((max_trade_value * strength) / ask)
				if qty > 0:
					return "BUY", qty

		return "HOLD", 0

	def _trend_quality(self, prices: List[float]) -> float:
		sma_10 = sum(prices[-10:]) / 10
		sma_30 = sum(prices[-30:]) / 30
		sma_60 = sum(prices[-60:]) / 60

		score = 0.0
		if sma_10 > sma_30:
			score += 0.35
		if sma_30 > sma_60:
			score += 0.35
		if prices[-1] > sma_30:
			score += 0.20
		if prices[-1] > prices[-5]:
			score += 0.10
		return min(score, 1.0)

	def _bollinger_bands(self, prices: List[float], period: int, num_std: float) -> tuple[float, float, float]:
		recent = prices[-period:]
		middle = sum(recent) / period
		variance = sum((price - middle) ** 2 for price in recent) / period
		std_dev = variance ** 0.5
		upper = middle + num_std * std_dev
		lower = middle - num_std * std_dev
		return upper, middle, lower

	def _get_cash(self, portfolio: Portfolio) -> float:
		return float(portfolio.cash)

	def _get_position(self, portfolio: Portfolio, symbol: str) -> int:
		return int(portfolio.get_position(symbol))

	def _get_avg_entry(self, portfolio: Portfolio, symbol: str) -> float | None:
		return portfolio.cost_basis.get(symbol)


class TrainablePenguin3_Manual(TrainablePenguin3):
	LOOKBACK_BARS = 120

	def __init__(
		self,
		name: str = "TrainablePenguin3_Manual",
		bb_period: int = TRAINABLE_PENGUIN3_BB_PERIOD,
		bb_stddev: float = TRAINABLE_PENGUIN3_BB_STDDEV,
		max_cash_fraction_per_trade: float = TRAINABLE_PENGUIN3_MAX_CASH_FRACTION,
		stop_loss_pct: float = TRAINABLE_PENGUIN3_STOP_LOSS_PCT,
		take_profit_pct: float = TRAINABLE_PENGUIN3_TAKE_PROFIT_PCT,
		cooldown_bars: int = TRAINABLE_PENGUIN3_COOLDOWN_BARS,
	):
		super().__init__(
			name=name,
			bb_period=bb_period,
			bb_stddev=bb_stddev,
			max_cash_fraction_per_trade=max_cash_fraction_per_trade,
			stop_loss_pct=stop_loss_pct,
			take_profit_pct=take_profit_pct,
			cooldown_bars=cooldown_bars,
		)