from fastapi import APIRouter

from server.routers.auth_router import auth
from server.routers.chat_router import chat
from server.routers.dashboard_router import dashboard
from server.routers.department_router import department
from server.routers.knowledge_router import knowledge
from server.routers.evaluation_router import evaluation
from server.routers.mcp_router import mcp
from server.routers.mindmap_router import mindmap
from server.routers.skill_router import skills
from server.routers.system_router import system
from server.routers.task_router import tasks
from server.routers.tool_router import tools

router = APIRouter()

router.include_router(system)
router.include_router(auth)
router.include_router(chat)
router.include_router(dashboard)
router.include_router(department)
router.include_router(knowledge)
router.include_router(evaluation)
router.include_router(mindmap)
router.include_router(tasks)
router.include_router(mcp)
router.include_router(skills)
router.include_router(tools)
