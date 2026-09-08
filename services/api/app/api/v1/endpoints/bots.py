import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.bot import BotCreate, BotListResponse, BotResponse, BotUpdate
from app.services.bot_service import BotService

router = APIRouter(prefix="/bots", tags=["bots"])


@router.post(
    "",
    response_model=BotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new bot",
    description="Create a new chatbot agent with initial persona and settings.",
)
async def create_bot(
    bot_in: BotCreate,
    db: AsyncSession = Depends(get_db),
) -> BotResponse:
    bot = await BotService.create(db=db, bot_in=bot_in)
    return BotResponse.model_validate(bot)


@router.get(
    "",
    response_model=BotListResponse,
    summary="List bots",
    description="Retrieve a paginated list of created bots.",
)
async def list_bots(
    skip: int = Query(default=0, ge=0, description="Pagination offset"),
    limit: int = Query(default=20, ge=1, le=100, description="Pagination page size"),
    db: AsyncSession = Depends(get_db),
) -> BotListResponse:
    items, total = await BotService.get_multi(db=db, skip=skip, limit=limit)
    return BotListResponse(
        items=[BotResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{bot_id}",
    response_model=BotResponse,
    summary="Get bot by ID",
    description="Retrieve full details and current status for a specific bot.",
)
async def get_bot(
    bot_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BotResponse:
    bot = await BotService.get_by_id(db=db, bot_id=bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with ID {bot_id} not found",
        )
    return BotResponse.model_validate(bot)


@router.patch(
    "/{bot_id}",
    response_model=BotResponse,
    summary="Update bot",
    description="Partially update a bot's configuration, prompt, status, or settings.",
)
async def update_bot(
    bot_id: uuid.UUID,
    bot_in: BotUpdate,
    db: AsyncSession = Depends(get_db),
) -> BotResponse:
    bot = await BotService.get_by_id(db=db, bot_id=bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with ID {bot_id} not found",
        )
    updated_bot = await BotService.update(db=db, bot=bot, bot_in=bot_in)
    return BotResponse.model_validate(updated_bot)


@router.delete(
    "/{bot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete bot",
    description="Permanently remove a bot.",
)
async def delete_bot(
    bot_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    bot = await BotService.get_by_id(db=db, bot_id=bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with ID {bot_id} not found",
        )
    await BotService.delete(db=db, bot=bot)
