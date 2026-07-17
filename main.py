import asyncio
from src.game import Game


async def main():
    game = Game(screen_width=800, screen_height=600)
    await game.run()


if __name__ == "__main__":
    asyncio.run(main())
