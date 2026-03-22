from deepagents.backends import CompositeBackend, StateBackend

from src.agents.common.middlewares.skills_middleware import normalize_selected_skills

from .openviking_backend import OpenVikingReadonlyBackend
from .skills_backend import SelectedSkillsReadonlyBackend


def _get_visible_skills_from_runtime(runtime) -> list[str]:
    context = getattr(runtime, "context", None)
    selected = getattr(context, "skills", None) or []
    return normalize_selected_skills(selected)


def create_agent_composite_backend(runtime, *, agent_id: str) -> CompositeBackend:
    visible_skills = _get_visible_skills_from_runtime(runtime)
    return CompositeBackend(
        default=StateBackend(runtime),
        routes={
            "/skills/": SelectedSkillsReadonlyBackend(selected_slugs=visible_skills),
            "/viking/": OpenVikingReadonlyBackend(runtime, agent_id=agent_id),
        },
    )
