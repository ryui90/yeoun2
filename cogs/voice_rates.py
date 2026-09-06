import discord
from discord import app_commands
from discord.ext import commands

import database as db
from config import COLOR_MAIN, VOICE_POINT_PER_SECOND

DEFAULT_RATE_PER_5MIN = int(VOICE_POINT_PER_SECOND * 300)


class VoiceRates(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="음성포인트설정", description="[관리자] 특정 카테고리의 음성 채널에 다른 포인트 요율을 설정합니다")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        카테고리="포인트 요율을 다르게 적용할 카테고리",
        포인트당5분="이 카테고리 음성채널 5분당 지급할 포인트",
    )
    async def set_voice_rate(self, interaction: discord.Interaction,
                              카테고리: discord.CategoryChannel, 포인트당5분: int):
        if 포인트당5분 < 0:
            await interaction.response.send_message("0 이상의 값을 입력해주세요.", ephemeral=True)
            return
        await db.upsert_voice_category_rate(interaction.guild.id, 카테고리.id, 포인트당5분)
        await interaction.response.send_message(
            f"✅ **{카테고리.name}** 카테고리의 음성채널은 이제 5분당 {포인트당5분:,}P가 지급됩니다.\n"
            f"(이미 접속 중인 유저는 다음에 채널을 이동하거나 나갈 때부터 적용됩니다)",
            ephemeral=True,
        )

    @app_commands.command(name="음성포인트제거", description="[관리자] 카테고리에 설정한 음성 포인트 요율을 삭제(기본값으로 복귀)합니다")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(카테고리="기본 요율로 되돌릴 카테고리")
    async def remove_voice_rate(self, interaction: discord.Interaction, 카테고리: discord.CategoryChannel):
        await db.delete_voice_category_rate(interaction.guild.id, 카테고리.id)
        await interaction.response.send_message(
            f"✅ **{카테고리.name}** 카테고리를 기본 요율(5분당 {DEFAULT_RATE_PER_5MIN}P)로 되돌렸습니다.",
            ephemeral=True,
        )

    @app_commands.command(name="음성포인트목록", description="[관리자] 카테고리별 음성 포인트 요율 설정을 확인합니다")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def list_voice_rates(self, interaction: discord.Interaction):
        rows = await db.get_all_voice_category_rates(interaction.guild.id)
        embed = discord.Embed(title="🎚️ 음성 포인트 요율", color=COLOR_MAIN)
        embed.add_field(name="기본 요율", value=f"5분당 {DEFAULT_RATE_PER_5MIN}P", inline=False)

        if rows:
            lines = []
            for r in rows:
                category = interaction.guild.get_channel(r["category_id"])
                cat_name = category.name if category else f"알 수 없음 ({r['category_id']})"
                lines.append(f"• **{cat_name}** — 5분당 {r['points_per_5min']:,}P")
            embed.add_field(name="개별 설정된 카테고리", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="개별 설정된 카테고리", value="없음", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(VoiceRates(bot))
