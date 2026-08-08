"""Abstract generation interface + deterministic stub (DR-6, IF-2, IF-3).

No generation request shall leave the machine (FR-4.1, CON-1).
"""
from abc import ABC, abstractmethod


class Generator(ABC):
    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        ...


class StubGenerator(Generator):
    """Returns a fixed, schema-valid inoculation post. No weights needed."""

    def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        return (
            '{"title": "Stub warning: unexpected calls claiming to be an authority",'
            ' "technique_layer": "Scammers impersonate an authority figure to create'
            ' fear and pressure you into acting before you can think. This is a stub'
            ' response for testing without model weights.",'
            ' "variant_layer": "This is placeholder variant-specific text generated'
            ' by StubGenerator.",'
            ' "action_steps": ["Hang up.", "Verify independently.", "Never share OTPs."]}'
        )


class LocalGenerator(Generator):
    """Real local instruction-tuned model served via Ollama/llama.cpp, 127.0.0.1 only.

    Not yet implemented — wire up in Phase 5, Step 5.2.
    """

    def __init__(self, model_name: str, base_url: str = "http://127.0.0.1:11434"):
        raise NotImplementedError(
            "LocalGenerator not yet implemented. Use MODEL_MODE=stub for now."
        )

    def generate(self, prompt: str, max_tokens: int = 512, temperature: float = 0.7) -> str:
        raise NotImplementedError
