"""三种感知模式的最小分发；研究后端故障不得静默回退到占位输出。"""
from .placeholder import placeholder_infer
from .unavailable import unavailable_infer


def disabled_infer(bundle, **geometry):
    return unavailable_infer(bundle, "perception_disabled", **geometry)


def research_infer(bundle, preflight=None, **geometry):
    """研究后端尚未接入时保持 fail-closed。"""
    if preflight is not None and not preflight["ready"]:
        reason = "research_preflight_blocked:" + ",".join(preflight["blockers"])
    else:
        reason = "research_backend_not_implemented"
    return unavailable_infer(bundle, reason, source_type="model", **geometry)
