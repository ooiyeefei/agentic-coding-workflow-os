from __future__ import annotations


def rolling_window_average(values: list[int], window: int) -> list[float]:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(values) < window:
        return []

    averages: list[float] = []
    for start in range(0, len(values) - window):
        chunk = values[start : start + window]
        averages.append(sum(chunk) / window)
    return averages
