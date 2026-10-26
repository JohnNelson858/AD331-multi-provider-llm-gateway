"""Standard first-party text rates, USD per million tokens, checked 2026-10-25.

https://developers.openai.com/api/docs/models/gpt-4o-mini
https://platform.claude.com/docs/en/about-claude/pricing
Excludes tools, images, regional premiums, and negotiated rates.
"""

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from .schemas import Provider


@dataclass(frozen=True)
class ModelPricing:
    provider: Provider
    input_per_million: Decimal
    output_per_million: Decimal
    cache_read_per_million: Decimal
    cache_write_per_million: Decimal | None = None


MODEL_PRICING = MappingProxyType({
    # Assignment example; marked deprecated in provider documentation.
    # Verify account availability before any live demonstration.
    "gpt-4o-mini": ModelPricing("openai", Decimal("0.15"), Decimal("0.60"), Decimal("0.075")),
    "claude-haiku-4-5-20251001": ModelPricing(
        "anthropic", Decimal("1.00"), Decimal("5.00"), Decimal("0.10"), Decimal("1.25")
    ),
})


def calculate_cost(model: str, input_tokens: int, output_tokens: int, *,
                   cache_read_tokens: int = 0, cache_write_tokens: int = 0) -> Decimal:
    """Total input includes cache tokens; cache writes use the five-minute rate.

    Preserve Decimal precision internally; round only for display.
    This prototype does not explicitly enable caching in provider requests.
    """
    counts = (input_tokens, output_tokens, cache_read_tokens, cache_write_tokens)
    if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in counts):
        raise ValueError("Token counts must be non-negative integers.")
    rates = MODEL_PRICING[model]
    uncached = input_tokens - cache_read_tokens - cache_write_tokens
    if uncached < 0:
        raise ValueError("Cached input exceeds total input tokens.")
    if cache_write_tokens and rates.cache_write_per_million is None:
        raise ValueError("Cache-write pricing is not configured for this model.")
    return (
        Decimal(uncached) * rates.input_per_million
        + Decimal(output_tokens) * rates.output_per_million
        + Decimal(cache_read_tokens) * rates.cache_read_per_million
        + Decimal(cache_write_tokens) * (rates.cache_write_per_million or Decimal(0))
    ) / Decimal(1_000_000)
