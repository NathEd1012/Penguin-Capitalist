"""Active trading strategy (penguin) configuration."""
import os
from penguins import (
    Emperor_Penguin,
    Simpler_Penguin,
    Simpler_Penguin2,
    SP500,
    SP500x2,
)

ACTIVE_PENGUINS = [
    Emperor_Penguin,
    Simpler_Penguin,
    Simpler_Penguin2,
    SP500,
    SP500x2,
]

_STRATEGY_GROUPS = {}

_STRATEGY_CLASSES = {
    strategy.__name__: strategy
    for strategy in (
        *ACTIVE_PENGUINS,
    )
}
_STRATEGY_NAMES = {
    name.casefold(): name
    for name in (*_STRATEGY_GROUPS, *_STRATEGY_CLASSES)
}


def _resolve_active_penguins(raw_value):
    if raw_value is None:
        return ACTIVE_PENGUINS

    selected = []
    seen = set()
    tokens = str(raw_value).replace("\n", ",").split(",")

    for token in tokens:
        name = token.strip()
        if not name:
            continue
        if name.startswith("*"):
            name = name[1:]
        name = _STRATEGY_NAMES.get(name.casefold(), name)

        if name in _STRATEGY_GROUPS:
            strategies = _STRATEGY_GROUPS[name]
        elif name in _STRATEGY_CLASSES:
            strategies = [_STRATEGY_CLASSES[name]]
        else:
            raise ValueError(f"Unknown ACTIVE_PENGUINS entry: {name}")

        for strategy in strategies:
            if strategy not in seen:
                selected.append(strategy)
                seen.add(strategy)

    return selected or ACTIVE_PENGUINS


ACTIVE_PENGUINS = _resolve_active_penguins(os.getenv("ACTIVE_PENGUINS"))


__all__ = [
    "ACTIVE_PENGUINS",
]
