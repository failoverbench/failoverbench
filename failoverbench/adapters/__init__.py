from .base import Adapter, CallResult
from .direct import DirectAdapter
from .endpoint import EndpointAdapter
from .reference import ReferenceAdapter
from .openai_sdk import OpenAIPythonAdapter
from .litellm_router import LiteLLMRouterAdapter

REGISTRY: dict[str, type[Adapter]] = {
    DirectAdapter.name: DirectAdapter,
    EndpointAdapter.name: EndpointAdapter,
    ReferenceAdapter.name: ReferenceAdapter,
    OpenAIPythonAdapter.name: OpenAIPythonAdapter,
    LiteLLMRouterAdapter.name: LiteLLMRouterAdapter,
}


def make_adapter(name: str, params: dict, wall_base: str) -> Adapter:
    try:
        cls = REGISTRY[name]
    except KeyError:
        raise SystemExit(f"unknown adapter '{name}'; known: {', '.join(sorted(REGISTRY))}")
    return cls(params, wall_base)


__all__ = ["Adapter", "CallResult", "REGISTRY", "make_adapter"]
