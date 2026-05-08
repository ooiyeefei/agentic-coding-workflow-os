from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")


class BudgetExceededError(ValueError):
    def __init__(self, *, required_tokens: int, budget_tokens: int) -> None:
        self.required_tokens = required_tokens
        self.budget_tokens = budget_tokens
        super().__init__(
            f"Packet requires {required_tokens} tokens but budget is {budget_tokens} tokens"
        )


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) * 4 / 3)


def enforce_budget(
    *,
    must_items: Sequence[T],
    should_items: Sequence[T],
    nice_items: Sequence[T],
    budget_tokens: int,
    render: Callable[[Sequence[T]], str],
) -> list[T]:
    if budget_tokens <= 0:
        raise ValueError("budget_tokens must be positive")

    must_only_tokens = estimate_tokens(render(must_items))
    if must_only_tokens > budget_tokens:
        raise BudgetExceededError(
            required_tokens=must_only_tokens,
            budget_tokens=budget_tokens,
        )

    selected_should = list(should_items)
    selected_nice = list(nice_items)

    while True:
        selected_items = [*must_items, *selected_should, *selected_nice]
        total_tokens = estimate_tokens(render(selected_items))
        if total_tokens <= budget_tokens:
            return selected_items

        if selected_nice:
            selected_nice.pop()
            continue

        if selected_should:
            selected_should.pop()
            continue

        raise BudgetExceededError(
            required_tokens=total_tokens,
            budget_tokens=budget_tokens,
        )


__all__ = ["BudgetExceededError", "enforce_budget", "estimate_tokens"]
