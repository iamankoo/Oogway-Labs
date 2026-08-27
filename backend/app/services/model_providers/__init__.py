"""Model provider selection for the agent layer.

The actual provider implementations (``LLMProvider``, ``OpenAIProvider``,
``AnthropicProvider``) come from ``pi-coding-agent`` - the required agent
framework (see ``docs/architecture.md`` "Agent framework choice"), not
from a hand-rolled class here. ``factory.get_model_provider`` is the only
place that picks between them based on ``Settings.llm_provider``.
"""
