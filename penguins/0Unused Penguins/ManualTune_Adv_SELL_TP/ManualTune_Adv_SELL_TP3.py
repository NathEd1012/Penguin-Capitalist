from dataclasses import dataclass
import math
from typing import List

from backtest.portfolio import Portfolio
from penguins.base_penguin import BasePenguin
from indicators.market_context import relative_strength, relative_volume


# Manual tuning block:
# Adjust these values here first so the strategy is easy to finetune by hand.
BB_PERIOD = 36
BB_STDDEV = 1.9121
ADX_PERIOD = 18
ADX_THRESHOLD = 20.6581
MAX_CASH_FRACTION = 0.1406
STOP_LOSS_PCT = 0.0732
TAKE_PROFIT_PCT = 0.143
COOLDOWN_BARS = 2
RELATIVE_STRENGTH_PERIOD = 17
RELATIVE_STRENGTH_THRESHOLD = 0.0683
RVOL_PERIOD = 22
RVOL_THRESHOLD = 1.0719


@dataclass
class ManualTuneAdvSELL_TP3Params:
	bb_period: int = BB_PERIOD
	bb_stddev: float = BB_STDDEV
	adx_period: int = ADX_PERIOD
	adx_threshold: float = ADX_THRESHOLD
	max_cash_fraction: float = MAX_CASH_FRACTION
	stop_loss_pct: float = STOP_LOSS_PCT
	take_profit_pct: float = TAKE_PROFIT_PCT
	cooldown_bars: int = COOLDOWN_BARS
	relative_strength_period: int = RELATIVE_STRENGTH_PERIOD
	relative_strength_threshold: float = RELATIVE_STRENGTH_THRESHOLD
	rvol_period: int = RVOL_PERIOD
	rvol_threshold: float = RVOL_THRESHOLD


class ManualTuneAdvSELL_TP3(BasePenguin):
	LOOKBACK_BARS = 120
	TRAINABLE = True

	def __init__(
		self,
		name: str = "TrainablePenguin3",
		bb_period: int = BB_PERIOD,
		bb_stddev: float = BB_STDDEV,
		adx_period: int = ADX_PERIOD,
		adx_threshold: float = ADX_THRESHOLD,
		max_cash_fraction: float = MAX_CASH_FRACTION,
		stop_loss_pct: float = STOP_LOSS_PCT,
		take_profit_pct: float = TAKE_PROFIT_PCT,
		cooldown_bars: int = COOLDOWN_BARS,
		relative_strength_period: int = RELATIVE_STRENGTH_PERIOD,
		relative_strength_threshold: float = RELATIVE_STRENGTH_THRESHOLD,
		rvol_period: int = RVOL_PERIOD,
		rvol_threshold: float = RVOL_THRESHOLD,
	):
		super().__init__(name)
		self.params = Adv_SELL_TP3Params(
			bb_period=bb_period,
			bb_stddev=bb_stddev,
			adx_period=adx_period,
			adx_threshold=adx_threshold,
			max_cash_fraction=max_cash_fraction,
			stop_loss_pct=stop_loss_pct,
			take_profit_pct=take_profit_pct,
			cooldown_bars=cooldown_bars,
			relative_strength_period=relative_strength_period,
			relative_strength_threshold=relative_strength_threshold,
			rvol_period=rvol_period,
			rvol_threshold=rvol_threshold,
		)

	def decide(self, symbol: str, mid_prices: List[float], bid: float, ask: float, portfolio: Portfolio, spy_prices: List[float] | None = None, volumes: List[float] | None = None) -> tuple[str, int]:
		min_required = max(60, self.params.bb_period, self.params.adx_period, self.params.relative_strength_period, self.params.rvol_period) + 2
		if bid <= 0 or ask <= 0 or len(mid_prices) < min_required:
			return "HOLD", 0

		upper_band, middle_band, lower_band = self._bollinger_bands(mid_prices, self.params.bb_period, self.params.bb_stddev)
		adx_value = self._adx_proxy(mid_prices, self.params.adx_period)
		adx_previous = self._adx_proxy(mid_prices[:-1], self.params.adx_period)
		adx_slope = adx_value - adx_previous
		trend_score = self._trend_quality(mid_prices)
		relative_strength_value = relative_strength(mid_prices, spy_prices, self.params.relative_strength_period)
		rvol = relative_volume(volumes, self.params.rvol_period)
		cash = self._get_cash(portfolio)
		shares_owned = self._get_position(portfolio, symbol)
		avg_entry = self._get_avg_entry(portfolio, symbol)
		current_price = mid_prices[-1]

		if shares_owned > 0:
			# SELL part
			loss_trigger = avg_entry is not None and current_price <= avg_entry * (1 - self.params.stop_loss_pct)
			upper_band_take_profit = current_price >= upper_band and avg_entry is not None and current_price >= avg_entry * (1 + self.params.take_profit_pct)
			adx_trend_reversal = adx_slope < 0 and adx_value < self.params.adx_threshold
			is_profitable = avg_entry is not None and current_price > avg_entry
			relative_strength_exit_trigger = is_profitable and relative_strength_value < self.params.relative_strength_threshold
			rvol_exit_trigger = is_profitable and rvol > self.params.rvol_threshold
			if loss_trigger or (upper_band_take_profit and adx_trend_reversal) or (
				upper_band_take_profit and adx_value < self.params.adx_threshold * 0.85
			) or relative_strength_exit_trigger or rvol_exit_trigger:
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

	def _adx_proxy(self, prices: List[float], period: int) -> float:
		if len(prices) < period + 1:
			return 0.0

		directional_up = 0.0
		directional_down = 0.0
		true_range = 0.0

		start = len(prices) - period
		for index in range(start, len(prices)):
			change = prices[index] - prices[index - 1]
			true_range += abs(change)
			if change > 0:
				directional_up += change
			elif change < 0:
				directional_down -= change

		if true_range <= 0:
			return 0.0

		directional_strength = abs(directional_up - directional_down) / true_range
		return 100.0 * directional_strength

	def _get_cash(self, portfolio: Portfolio) -> float:
		return float(portfolio.cash)

	def _get_position(self, portfolio: Portfolio, symbol: str) -> int:
		return int(portfolio.get_position(symbol))

	def _get_avg_entry(self, portfolio: Portfolio, symbol: str) -> float | None:
		return portfolio.cost_basis.get(symbol)


class ManualTuneAdvSELL_TP3_Manual(ManualTuneAdvSELL_TP3):
	LOOKBACK_BARS = 120
	TRAINABLE = False

	def __init__(
		self,
		name: str = "TrainablePenguin3_Manual",
		bb_period: int = BB_PERIOD,
		bb_stddev: float = BB_STDDEV,
		adx_period: int = ADX_PERIOD,
		adx_threshold: float = ADX_THRESHOLD,
		max_cash_fraction: float = MAX_CASH_FRACTION,
		stop_loss_pct: float = STOP_LOSS_PCT,
		take_profit_pct: float = TAKE_PROFIT_PCT,
		cooldown_bars: int = COOLDOWN_BARS,
	):
		super().__init__(
			name=name,
			bb_period=bb_period,
			bb_stddev=bb_stddev,
			adx_period=adx_period,
			adx_threshold=adx_threshold,
			max_cash_fraction=max_cash_fraction,
			stop_loss_pct=stop_loss_pct,
			take_profit_pct=take_profit_pct,
			cooldown_bars=cooldown_bars,
		)