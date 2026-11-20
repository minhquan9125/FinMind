"""Compatibility registry for b1_answering layout."""""
import sys
from .core import policy
from .evidence import citations, prompt
from .providers import gemini
from .application import service, dialogue

_ALIASES = {
    "policy": policy,
    "citations": citations,
    "prompt": prompt,
    "gemini": gemini,
    "service": service,
    "dialogue": dialogue,
}
for _name, _mod in _ALIASES.items():
    sys.modules[f"{__name__}.{_name}"] = _mod
    globals()[_name] = _mod
