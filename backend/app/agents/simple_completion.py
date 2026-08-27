"""A single, tool-free model turn - the shared primitive behind content generation (Phase 5).

``GrowthAssistantAgent`` (Phase 3/4) owns the conversational chat turn,
with its own history-seeding and grounding logic. Ship 30 essay and
artifact generation (``app.services.artifact_generation``) are a
different shape of request - one prompt in, one document out, no prior
turns to seed - so this is a small, separate helper built the same way
(a real ``pi_agent.agent.Agent`` with zero tools, one iteration) rather
than overloading ``GrowthAssistantAgent`` with a second calling
convention. Both still go through the same required agent framework and
the same provider abstraction.
"""

from __future__ import annotations

import asyncio
import tempfile

from pi_agent.agent import Agent as PiAgent
from pi_agent.config import AgentConfig
from pi_agent.llm import LLMProvider
from pi_agent.sandbox import Sandbox
from pi_agent.tools.registry import ToolRegistry

from app.agents.errors import EmptyResponseError, ModelTimeoutError
from app.agents.growth_assistant import _map_provider_exception


async def run_single_turn(
    provider: LLMProvider, *, system_prompt: str, user_prompt: str, timeout_seconds: float, max_iterations: int = 1
) -> str:
    """Run one tool-free turn through the required agent framework; return the text."""
    agent = PiAgent(
        provider=provider,
        registry=ToolRegistry([]),
        sandbox=Sandbox(tempfile.gettempdir()),
        config=AgentConfig(
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            auto_approve=True,
            stream=False,
            reflect=False,
            max_retries=3,
        ),
    )
    try:
        content = await asyncio.wait_for(asyncio.to_thread(agent.run, user_prompt), timeout=timeout_seconds)
    except asyncio.TimeoutError as exc:
        raise ModelTimeoutError() from exc
    except Exception as exc:  # noqa: BLE001 - normalized immediately below
        raise _map_provider_exception(exc) from exc

    if not content or not content.strip():
        raise EmptyResponseError()
    return content
