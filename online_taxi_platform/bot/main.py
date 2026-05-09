import asyncio
import logging

from apps.taxi.log import get_logger
from bot.handlers.group import router as group_router
from bot.handlers.private import router as private_router
from bot.loader import bot, dp

logger = get_logger(__name__)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    dp.include_router(group_router)
    dp.include_router(private_router)
    logger.info("bot started")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
