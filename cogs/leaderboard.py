import discord
from discord import app_commands
from discord.ext import commands

import database as db
from config import COLOR_MAIN

MEDALS = ["🥇", "🥈", "🥉"]


class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="음성순위", description="음성 채팅 누적 시간 순위를 확인합니다")
    async def voice_rank(self, interaction: discord.Interaction):
        await interaction.response.defer()

        tracking_cog = self.bot.get_cog("Tracking")
        totals = await tracking_cog.get_all_voice_totals(interaction.guild.id)
        top = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:10]

        embed = discord.Embed(title="🎤 음성 누적 시간 순위", color=COLOR_MAIN)
        lines = []
        for i, (user_id, total_seconds) in enumerate(top):
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"알 수 없음 ({user_id})"
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            prefix = MEDALS[i] if i < 3 else f"`{i + 1}`"
            lines.append(f"{prefix}  **{name}** — {h}시간 {m}분")

        embed.description = "\n".join(lines) if lines else "아직 기록이 없습니다."
        embed.set_footer(text=f"{interaction.guild.name}")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="채팅순위", description="채팅 누적 횟수 순위를 확인합니다")
    async def chat_rank(self, interaction: discord.Interaction):
        await interaction.response.defer()
        rows = await db.get_top_chat(interaction.guild.id, 10)

        embed = discord.Embed(title="💬 채팅 누적 횟수 순위", color=COLOR_MAIN)
        lines = []
        for i, row in enumerate(rows):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"알 수 없음 ({row['user_id']})"
            prefix = MEDALS[i] if i < 3 else f"`{i + 1}`"
            lines.append(f"{prefix}  **{name}** — {row['message_count']:,}회")

        embed.description = "\n".join(lines) if lines else "아직 기록이 없습니다."
        embed.set_footer(text=f"{interaction.guild.name}")
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
