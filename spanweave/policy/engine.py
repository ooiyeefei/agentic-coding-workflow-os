from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from spanweave.policy.cost_tracker import CostTracker
from spanweave.policy.defaults import (
    DAILY_COST_CAP_USD,
    RUN_COST_CAP_USD,
)
from spanweave.policy.defaults import (
    is_dry_run as default_is_dry_run,
)
from spanweave.policy.defaults import (
    requires_approval as default_requires_approval,
)

_ZERO_COST = Decimal("0")


def _to_decimal(value: Decimal | float | int | str) -> Decimal:
    if isinstance(value, Decimal):
        result = value
    else:
        try:
            result = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"Invalid cost amount: {value!r}") from exc
    if result < _ZERO_COST:
        raise ValueError("Cost amounts must be non-negative")
    return result


class CostCapExceeded(RuntimeError):
    def __init__(
        self,
        *,
        scope: Literal["run", "day"],
        cap_usd: Decimal,
        current_total_usd: Decimal,
        proposed_cost_usd: Decimal,
        projected_total_usd: Decimal,
    ) -> None:
        self.scope = scope
        self.cap_usd = cap_usd
        self.current_total_usd = current_total_usd
        self.proposed_cost_usd = proposed_cost_usd
        self.projected_total_usd = projected_total_usd
        super().__init__(
            f"{scope} cost cap exceeded: projected ${projected_total_usd:.2f} "
            f"> ${cap_usd:.2f}"
        )


class PolicyEngine:
    def __init__(
        self,
        *,
        cost_tracker: CostTracker | None = None,
        run_cost_cap_usd: Decimal | float | int | str = RUN_COST_CAP_USD,
        daily_cost_cap_usd: Decimal | float | int | str = DAILY_COST_CAP_USD,
    ) -> None:
        self.cost_tracker = cost_tracker or CostTracker()
        self.run_cost_cap_usd = _to_decimal(run_cost_cap_usd)
        self.daily_cost_cap_usd = _to_decimal(daily_cost_cap_usd)

    def requires_approval(self, stage: str, context: Mapping[str, Any] | None = None) -> bool:
        del context
        return default_requires_approval(stage)

    def is_dry_run(self, operation: str) -> bool:
        return default_is_dry_run(operation)

    def check_cost(self, run_id: str, proposed_cost: Decimal | float | int | str) -> bool:
        proposed = _to_decimal(proposed_cost)
        current_run_total = self.cost_tracker.sum_run_cost(run_id)
        projected_run_total = current_run_total + proposed
        if projected_run_total > self.run_cost_cap_usd:
            raise CostCapExceeded(
                scope="run",
                cap_usd=self.run_cost_cap_usd,
                current_total_usd=current_run_total,
                proposed_cost_usd=proposed,
                projected_total_usd=projected_run_total,
            )

        current_day_total = self.cost_tracker.sum_day_cost()
        projected_day_total = current_day_total + proposed
        if projected_day_total > self.daily_cost_cap_usd:
            raise CostCapExceeded(
                scope="day",
                cap_usd=self.daily_cost_cap_usd,
                current_total_usd=current_day_total,
                proposed_cost_usd=proposed,
                projected_total_usd=projected_day_total,
            )

        return True


__all__ = ["CostCapExceeded", "PolicyEngine"]
