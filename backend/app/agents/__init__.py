"""Agent orchestration layer.

This is the "genuine agent abstraction" the assignment asks for: a real
module that owns the assistant's persona, builds conversation context
from persisted messages, and delegates actual text generation to a
``ModelProvider`` (``app.services.model_providers``). The API layer
(``app.api.sessions``) never talks to a provider directly.
"""
