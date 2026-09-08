import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bot import Bot
from app.schemas.bot import BotCreate, BotUpdate


class BotService:
    @staticmethod
    async def create(
        db: AsyncSession,
        bot_in: BotCreate,
        user_id: uuid.UUID | None = None,
    ) -> Bot:
        """Create a new bot entity."""
        bot = Bot(
            user_id=user_id,
            name=bot_in.name,
            description=bot_in.description,
            system_prompt=bot_in.system_prompt,
            settings=bot_in.settings,
        )
        db.add(bot)
        await db.commit()
        await db.refresh(bot)
        return bot

    @staticmethod
    async def get_by_id(db: AsyncSession, bot_id: uuid.UUID) -> Bot | None:
        """Retrieve a bot by its primary key ID."""
        result = await db.execute(select(Bot).where(Bot.id == bot_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_multi(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        user_id: uuid.UUID | None = None,
    ) -> tuple[list[Bot], int]:
        """List bots with pagination and total count."""
        query = select(Bot)
        count_query = select(func.count(Bot.id))

        if user_id is not None:
            query = query.where(Bot.user_id == user_id)
            count_query = count_query.where(Bot.user_id == user_id)

        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        items_result = await db.execute(
            query.order_by(Bot.created_at.desc()).offset(skip).limit(limit)
        )
        items = list(items_result.scalars().all())

        return items, total

    @staticmethod
    async def update(
        db: AsyncSession,
        bot: Bot,
        bot_in: BotUpdate,
    ) -> Bot:
        """Update an existing bot."""
        update_data = bot_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(bot, field, value)

        await db.commit()
        await db.refresh(bot)
        return bot

    @staticmethod
    async def delete(db: AsyncSession, bot: Bot) -> None:
        """Delete a bot."""
        await db.delete(bot)
        await db.commit()
