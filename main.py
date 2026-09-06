import asyncio

import discord
from discord.ext import commands
from discord import app_commands

import database as db
from config import TOKEN

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

INITIAL_COGS = [
    "cogs.tracking",
    "cogs.leaderboard",
    "cogs.onboarding",
    "cogs.reaction_roles",
    "cogs.shop",
    "cogs.points",
    "cogs.ranks",
    "cogs.voice_rates",
    "cogs.gambling",
]


@bot.event
async def on_ready():
    print(f"{bot.user} 로그인 완료 (서버 {len(bot.guilds)}개)")

    shop_cog = bot.get_cog("Shop")
    if shop_cog:
        await shop_cog.register_persistent_views()

    try:
        synced = await bot.tree.sync()
        print(f"슬래시 명령어 {len(synced)}개 동기화 완료")
    except Exception as e:
        print(f"명령어 동기화 실패: {e}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "이 명령어를 사용할 권한이 없습니다."
    else:
        print(f"슬래시 명령어 오류: {error}")
        msg = "명령어 실행 중 오류가 발생했습니다."

    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


async def main():
    await db.init_db()
    async with bot:
        for cog in INITIAL_COGS:
            await bot.load_extension(cog)
        await bot.start(TOKEN)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN 환경변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")
    asyncio.run(main())
