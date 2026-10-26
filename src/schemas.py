"""Provider-independent events for the Step 2 text-only prototype."""

from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Provider = Literal["openai", "anthropic"]


class ChunkTelemetry(BaseModel):
    """Local counts are estimates. Throughput = output tokens / elapsed time."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    local_prompt_tokens: int | None = Field(default=None, ge=0)
    usage_source: Literal["unavailable", "local_estimate", "provider_partial", "provider"]
    is_estimate: bool
    elapsed_seconds: float = Field(ge=0, allow_inf_nan=False)
    ttft_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    tokens_per_second: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    total_cost_usd: Decimal | None = Field(default=None, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    cache_write_input_tokens: int = Field(default=0, ge=0)
    stop_reason: str | None = None


class StreamChunk(BaseModel):
    """A text fragment can contain zero, one, or many tokens."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    delta_text: str = ""
    provider: Provider
    model: str
    is_final: bool = False
    telemetry: ChunkTelemetry | None = None
