from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, WebSocket
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.utils.auth_middleware import get_db, get_required_user
from src.services.voice_interview_service import (
    VoiceSessionStartPayload,
    start_voice_interview_session,
    voice_interview_websocket_endpoint,
)
from src.storage.postgres.models_business import User
from src.services.interview_coding_service import (
    find_coding_session,
    get_problem_package_detail,
    get_coding_session,
    get_submission_result,
    list_imported_problem_packages,
    request_coding_hint,
    run_sample_coding_session,
    start_coding_session,
    submit_coding_session,
    update_coding_draft,
)
from src.services.interview_result_service import (
    finalize_interview_result,
    get_interview_history,
    get_interview_improvement_plan,
    get_interview_result,
)

interview = APIRouter(prefix="/interview", tags=["interview"])


class StartCodingSessionRequest(BaseModel):
    target_position: str | None = None
    excluded_problem_ids: list[str] | None = None
    difficulty_level: str | None = None


class UpdateCodingDraftRequest(BaseModel):
    language: str = Field(default="javascript")
    draft_code: str = Field(default="")


class SubmitCodingSessionRequest(BaseModel):
    language: str = Field(default="javascript")
    code: str = Field(default="")


class CodingHintRequest(BaseModel):
    question: str
    draft_code: str = ""


class FinalizeInterviewResultRequest(BaseModel):
    target_position: str | None = None
    interview_round: str | None = None
    force: bool = False


@interview.post("/voice/session/start")
async def start_voice_session(
    payload: VoiceSessionStartPayload,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return await start_voice_interview_session(payload=payload, current_user=current_user, db=db)


@interview.get("/problemsets")
async def get_problemsets(current_user: User = Depends(get_required_user)):
    _ = current_user
    return list_imported_problem_packages()


@interview.get("/problemset-detail")
async def get_problemset_detail(package_path: str, current_user: User = Depends(get_required_user)):
    _ = current_user
    return get_problem_package_detail(package_path)


@interview.get("/{thread_id}/coding-session")
async def get_thread_coding_session(
    thread_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return {
        "coding_session": await find_coding_session(
            db,
            thread_id=thread_id,
            current_user_id=str(current_user.id),
        )
    }


@interview.post("/{thread_id}/coding-session/start")
async def start_thread_coding_session(
    thread_id: str,
    payload: StartCodingSessionRequest = Body(default_factory=StartCodingSessionRequest),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return {
        "coding_session": await start_coding_session(
            db,
            thread_id=thread_id,
            current_user_id=str(current_user.id),
            target_position=payload.target_position,
            excluded_problem_ids=payload.excluded_problem_ids,
            difficulty_level=payload.difficulty_level,
        )
    }

@interview.post("/{thread_id}/coding-session")
async def start_thread_coding_session_legacy(
    thread_id: str,
    payload: StartCodingSessionRequest = Body(default_factory=StartCodingSessionRequest),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return await start_thread_coding_session(
        thread_id=thread_id,
        payload=payload,
        current_user=current_user,
        db=db,
    )


@interview.put("/{thread_id}/coding-session/draft")
async def update_thread_coding_draft(
    thread_id: str,
    payload: UpdateCodingDraftRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return {
        "coding_session": await update_coding_draft(
            db,
            thread_id=thread_id,
            current_user_id=str(current_user.id),
            language=payload.language,
            draft_code=payload.draft_code,
        )
    }


@interview.post("/{thread_id}/coding-session/run-sample")
async def run_thread_coding_sample(
    thread_id: str,
    payload: SubmitCodingSessionRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return {
        "coding_session": await run_sample_coding_session(
            db,
            thread_id=thread_id,
            current_user_id=str(current_user.id),
            language=payload.language,
            code=payload.code,
        )
    }


@interview.post("/{thread_id}/coding-session/submit")
async def submit_thread_coding_session(
    thread_id: str,
    payload: SubmitCodingSessionRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return {
        "coding_session": await submit_coding_session(
            db,
            thread_id=thread_id,
            current_user_id=str(current_user.id),
            language=payload.language,
            code=payload.code,
        )
    }


@interview.get("/{thread_id}/coding-session/submissions/{submission_id}")
async def get_thread_coding_submission(
    thread_id: str,
    submission_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_submission_result(
        db,
        thread_id=thread_id,
        current_user_id=str(current_user.id),
        submission_id=submission_id,
    )


@interview.post("/{thread_id}/coding-session/hint")
async def request_thread_coding_hint(
    thread_id: str,
    payload: CodingHintRequest,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return await request_coding_hint(
        db,
        thread_id=thread_id,
        current_user_id=str(current_user.id),
        question=payload.question,
        draft_code=payload.draft_code,
    )


@interview.get("/{thread_id}/result")
async def get_thread_interview_result(
    thread_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_interview_result(
        db,
        thread_id=thread_id,
        current_user_id=str(current_user.id),
    )


@interview.get("/{thread_id}/improvement-plan")
async def get_thread_interview_improvement_plan(
    thread_id: str,
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_interview_improvement_plan(
        db,
        thread_id=thread_id,
        current_user_id=str(current_user.id),
    )


@interview.get("/history")
async def get_user_interview_history(
    user_id: int | None = Query(default=None),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_interview_history(
        db,
        current_user=current_user,
        user_id=user_id,
    )


@interview.post("/{thread_id}/result/finalize")
async def finalize_thread_interview_result(
    thread_id: str,
    payload: FinalizeInterviewResultRequest = Body(default_factory=FinalizeInterviewResultRequest),
    current_user: User = Depends(get_required_user),
    db: AsyncSession = Depends(get_db),
):
    return await finalize_interview_result(
        db,
        thread_id=thread_id,
        current_user=current_user,
        target_position=payload.target_position,
        interview_round=payload.interview_round,
        force=payload.force,
    )


@interview.websocket("/voice/ws")
async def voice_interview_ws(
    websocket: WebSocket,
    voice_session_id: str = Query(...),
    token: str = Query(...),
):
    await voice_interview_websocket_endpoint(
        websocket=websocket,
        voice_session_id=voice_session_id,
        token=token,
    )
