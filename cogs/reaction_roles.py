import discord
from discord import app_commands
from discord.ext import commands

import database as db
from config import COLOR_MAIN


def parse_color(color_str):
    if not color_str:
        return COLOR_MAIN
    try:
        return int(color_str.replace("#", ""), 16)
    except ValueError:
        return COLOR_MAIN


class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="메세지", description="지정한 채널에 임베드 메세지를 보냅니다")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(
        채널="메세지를 보낼 채널", 제목="임베드 제목", 내용="임베드 내용",
        색상="16진수 색상 코드 (예: #B6E68A), 생략 가능"
    )
    async def send_message(self, interaction: discord.Interaction, 채널: discord.TextChannel,
                            제목: str, 내용: str, 색상: str = None):
        embed = discord.Embed(title=제목, description=내용, color=parse_color(색상))
        msg = await 채널.send(embed=embed)
        await interaction.response.send_message(
            f"✅ 메세지를 보냈습니다. (메세지 ID: `{msg.id}`)", ephemeral=True
        )

    @app_commands.command(name="역할추가", description="메세지에 반응 역할을 연결합니다")
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.describe(
        메세지id="반응을 추가할 메세지 ID", 채널="메세지가 있는 채널",
        이모지="반응으로 사용할 이모지", 역할="반응 시 지급할 역할"
    )
    async def add_reaction_role(self, interaction: discord.Interaction, 메세지id: str,
                                 채널: discord.TextChannel, 이모지: str, 역할: discord.Role):
        try:
            message = await 채널.fetch_message(int(메세지id))
        except (discord.NotFound, ValueError):
            await interaction.response.send_message(
                "메세지를 찾을 수 없습니다. 메세지 ID와 채널을 확인해주세요.", ephemeral=True
            )
            return

        try:
            await message.add_reaction(이모지)
        except discord.HTTPException:
            await interaction.response.send_message("이모지를 반응으로 추가할 수 없습니다.", ephemeral=True)
            return

        await db.add_reaction_role(message.id, 이모지, 역할.id, interaction.guild.id)
        await interaction.response.send_message(
            f"✅ {이모지} 반응에 {역할.mention} 역할을 연결했습니다.", ephemeral=True
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.member is None or payload.member.bot:
            return
        mapping = await db.get_reaction_role(payload.message_id, str(payload.emoji))
        if not mapping:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        role = guild.get_role(mapping["role_id"])
        if role:
            try:
                await payload.member.add_roles(role, reason="반응 역할 지급")
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        mapping = await db.get_reaction_role(payload.message_id, str(payload.emoji))
        if not mapping:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        member = guild.get_member(payload.user_id)
        if member is None or member.bot:
            return
        role = guild.get_role(mapping["role_id"])
        if role:
            try:
                await member.remove_roles(role, reason="반응 역할 해제")
            except discord.Forbidden:
                pass


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
