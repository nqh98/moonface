from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields


MOE_VERSION = "moe-v1"


@dataclass(frozen=True)
class MoeConfig:
    tau: float = 0.35
    q_confluence: int = 2
    m_per_weight: int = 50
    shrink_snr: float = 1.0
    l1_frac: float = 0.10
    norm_mode: str = "rank"
    seed: int = 1729
    eps: float = 1e-9


def moe_hash(cfg: MoeConfig) -> str:
    payload = {field.name: getattr(cfg, field.name) for field in fields(cfg)}
    payload["__moe_version__"] = MOE_VERSION
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def identity_hash(cfg: MoeConfig, expert_names: list[str],
                  ortho_constants: dict) -> str:
    payload = {
        "moe_hash": moe_hash(cfg),
        "experts": sorted(expert_names),
        "ortho_constants": {
            key: ortho_constants[key] for key in sorted(ortho_constants)
        },
        "__moe_version__": MOE_VERSION,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
