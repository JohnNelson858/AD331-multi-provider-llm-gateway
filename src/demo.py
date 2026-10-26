"""Optional live terminal demo. Requires local API credentials and incurs cost.

Run from the repository root: uv run python -m src.demo --help
No provider requests occur for --help or when importing this module.
"""

import argparse
import asyncio
from contextlib import aclosing
from dotenv import load_dotenv
from .gateway import GatewayProviderError, UnifiedLLMGateway
from .pricing import MODEL_PRICING


async def run(prompt: str, model: str, temperature: float, max_tokens: int) -> None:
    load_dotenv(override=False)
    async with UnifiedLLMGateway() as gateway:
        async with aclosing(gateway.stream(prompt, model, temperature, max_tokens=max_tokens)) as events:
            async for event in events:
                if event.delta_text:
                    print(event.delta_text, end="", flush=True)
                if event.is_final:
                    print("\n\nFinal provider telemetry:")
                    print(event.telemetry.model_dump_json(indent=2))
                    print(f"Display cost: ${event.telemetry.total_cost_usd:.6f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Live text-only gateway demo (paid API usage).")
    parser.add_argument("--model", choices=list(MODEL_PRICING), required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=128)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.prompt, args.model, args.temperature, args.max_tokens))
    except GatewayProviderError as exc:
        parser.exit(1, f"Gateway error: {exc}\n")
    except KeyboardInterrupt:
        parser.exit(130, "\nCancelled.\n")


if __name__ == "__main__":
    main()
