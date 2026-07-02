from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.database.base import get_db
from app.models.auth import User
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/knowledge-base", tags=["Knowledge Base"])


@router.post("/upload")
async def upload_document(
    file: UploadFile,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.ai.knowledge_base.processor import KnowledgeBaseProcessor
    processor = KnowledgeBaseProcessor(session)
    doc = await processor.process_upload(file, uploaded_by=current_user.id)
    return {"id": str(doc.id), "title": doc.title, "status": doc.status}


@router.post("/url")
async def add_url(
    url: str,
    title: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    from app.ai.knowledge_base.processor import KnowledgeBaseProcessor
    processor = KnowledgeBaseProcessor(session)
    doc = await processor.process_url(url, title=title, uploaded_by=current_user.id)
    return {"id": str(doc.id), "title": doc.title, "status": doc.status}


@router.post("/search")
async def search_knowledge_base(
    query: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 5,
) -> dict:
    from app.ai.knowledge_base.retriever import KnowledgeBaseRetriever
    retriever = KnowledgeBaseRetriever(session)
    results = await retriever.search(query, limit=limit)
    return {"results": results}
