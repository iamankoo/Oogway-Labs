"""Model provider abstraction.

``ModelProvider`` is the single interface the agent layer depends on.
``OllamaProvider`` and ``AnthropicProvider`` are the two implementations;
``factory.get_model_provider`` picks between them based on
``Settings.llm_provider``. Nothing above this package's boundary
branches on which provider is active - the agent layer, the API layer,
and the frontend all interact with "the configured provider," never
with Ollama or Anthropic specifics directly.
"""
