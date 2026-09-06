import discord
from discord import app_commands
from discord.ext import commands

import database as db
from config import (
    COLOR_MAIN, POINT_TO_GACHA_UNIT, POINT_TO_GACHA_RATE,
    GACHA_TO_POINT_UNIT, GACHA_TO_POINT_RATE,
)


class Points(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="포인트", description="누적 포인트를 확인합니다")
    @app_commands.describe(유저="확인할 유저 (비워두면 본인)")
    async def points(self, interaction: discord.Interaction, 유저: discord.Member = None):
        member = 유저 or interaction.user
        row = await db.get_user(interaction.guild.id, member.id)
        embed = discord.Embed(title="💰 포인트 현황", color=COLOR_MAIN)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.description = f"**{member.display_name}**님의 포인트: **{row['points']:,} P**"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="가챠포인트", description="누적 가챠(도박) 포인트를 확인합니다")
    @app_commands.describe(유저="확인할 유저 (비워두면 본인)")
    async def gacha_points(self, interaction: discord.Interaction, 유저: discord.Member = None):
        member = 유저 or interaction.user
        row = await db.get_user(interaction.guild.id, member.id)
        embed = discord.Embed(title="🎰 가챠포인트 현황", color=COLOR_MAIN)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.description = f"**{member.display_name}**님의 가챠포인트: **{row['gacha_points']:,} P**"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="포인트전환",
        description=f"포인트를 가챠포인트로 전환합니다 ({POINT_TO_GACHA_UNIT}P → {POINT_TO_GACHA_RATE}가챠P)",
    )
    @app_commands.describe(포인트=f"전환할 포인트 ({POINT_TO_GACHA_UNIT} 단위)")
    async def point_to_gacha(self, interaction: discord.Interaction, 포인트: int):
        if 포인트 <= 0 or 포인트 % POINT_TO_GACHA_UNIT != 0:
            await interaction.response.send_message(
                f"❌ {POINT_TO_GACHA_UNIT} 단위로 입력해주세요.", ephemeral=True
            )
            return

        row = await db.get_user(interaction.guild.id, interaction.user.id)
        if row["points"] < 포인트:
            await interaction.response.send_message(
                f"❌ 포인트가 부족합니다. (보유: {row['points']:,}P)", ephemeral=True
            )
            return

        gacha_amount = (포인트 // POINT_TO_GACHA_UNIT) * POINT_TO_GACHA_RATE
        await db.add_points(interaction.guild.id, interaction.user.id, -포인트)
        await db.add_gacha_points(interaction.guild.id, interaction.user.id, gacha_amount)

        embed = discord.Embed(
            title="🔄 전환 완료",
            description=f"**{포인트:,}P** → **{gacha_amount:,} 가챠P**",
            color=COLOR_MAIN,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="가챠전환",
        description=f"가챠포인트를 포인트로 전환합니다 ({GACHA_TO_POINT_UNIT}가챠P → {GACHA_TO_POINT_RATE}P)",
    )
    @app_commands.describe(가챠포인트=f"전환할 가챠포인트 ({GACHA_TO_POINT_UNIT} 단위)")
    async def gacha_to_point(self, interaction: discord.Interaction, 가챠포인트: int):
        if 가챠포인트 <= 0 or 가챠포인트 % GACHA_TO_POINT_UNIT != 0:
            await interaction.response.send_message(
                f"❌ {GACHA_TO_POINT_UNIT} 단위로 입력해주세요.", ephemeral=True
            )
            return

        row = await db.get_user(interaction.guild.id, interaction.user.id)
        if row["gacha_points"] < 가챠포인트:
            await interaction.response.send_message(
                f"❌ 가챠포인트가 부족합니다. (보유: {row['gacha_points']:,}가챠P)", ephemeral=True
            )
            return

        point_amount = (가챠포인트 // GACHA_TO_POINT_UNIT) * GACHA_TO_POINT_RATE
        await db.add_gacha_points(interaction.guild.id, interaction.user.id, -가챠포인트)
        await db.add_points(interaction.guild.id, interaction.user.id, point_amount)

        ranks_cog = self.bot.get_cog("Ranks")
        if ranks_cog:
            new_row = await db.get_user(interaction.guild.id, interaction.user.id)
            await ranks_cog.sync_role(interaction.guild, interaction.user, new_row["points"])

        embed = discord.Embed(
            title="🔄 전환 완료",
            description=f"**{가챠포인트:,} 가챠P** → **{point_amount:,}P**",
            color=COLOR_MAIN,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="포인트선물", description="다른 유저에게 포인트를 선물합니다")
    @app_commands.describe(대상="선물할 대상", 포인트="선물할 포인트 수량")
    async def gift_points(self, interaction: discord.Interaction, 대상: discord.Member, 포인트: int):
        if 포인트 <= 0:
            await interaction.response.send_message("❌ 1 이상의 수량을 입력하세요.", ephemeral=True)
            return
        if 대상.id == interaction.user.id:
            await interaction.response.send_message("❌ 자신에게 선물할 수 없습니다.", ephemeral=True)
            return
        if 대상.bot:
            await interaction.response.send_message("❌ 봇에게 선물할 수 없습니다.", ephemeral=True)
            return

        sender_row = await db.get_user(interaction.guild.id, interaction.user.id)
        if sender_row["points"] < 포인트:
            await interaction.response.send_message(
                f"❌ 포인트가 부족합니다. (보유: {sender_row['points']:,}P)", ephemeral=True
            )
            return

        await db.add_points(interaction.guild.id, interaction.user.id, -포인트)
        await db.add_points(interaction.guild.id, 대상.id, 포인트)

        ranks_cog = self.bot.get_cog("Ranks")
        if ranks_cog:
            sender_new = await db.get_user(interaction.guild.id, interaction.user.id)
            receiver_new = await db.get_user(interaction.guild.id, 대상.id)
            await ranks_cog.sync_role(interaction.guild, interaction.user, sender_new["points"])
            await ranks_cog.sync_role(interaction.guild, 대상, receiver_new["points"])

        embed = discord.Embed(
            title="🎁 포인트 선물 완료",
            description=f"{interaction.user.mention} → {대상.mention}\n**{포인트:,}P** 전달됨",
            color=COLOR_MAIN,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="추가", description="[관리자] 유저에게 포인트를 지급합니다")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(유저="포인트를 지급할 유저", 포인트="지급할 포인트")
    async def add_points(self, interaction: discord.Interaction, 유저: discord.Member, 포인트: int):
        if 포인트 <= 0:
            await interaction.response.send_message("1 이상의 값을 입력해주세요.", ephemeral=True)
            return
        await db.add_points(interaction.guild.id, 유저.id, 포인트)
        row = await db.get_user(interaction.guild.id, 유저.id)
        ranks_cog = self.bot.get_cog("Ranks")
        if ranks_cog:
            await ranks_cog.sync_role(interaction.guild, 유저, row["points"])
        await interaction.response.send_message(
            f"✅ {유저.mention}님에게 {포인트:,}P를 지급했습니다. (현재 {row['points']:,}P)", ephemeral=True
        )

    @app_commands.command(name="제거", description="[관리자] 유저의 포인트를 차감합니다")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(유저="포인트를 차감할 유저", 포인트="차감할 포인트")
    async def remove_points(self, interaction: discord.Interaction, 유저: discord.Member, 포인트: int):
        if 포인트 <= 0:
            await interaction.response.send_message("1 이상의 값을 입력해주세요.", ephemeral=True)
            return
        await db.add_points(interaction.guild.id, 유저.id, -포인트)
        row = await db.get_user(interaction.guild.id, 유저.id)
        ranks_cog = self.bot.get_cog("Ranks")
        if ranks_cog:
            await ranks_cog.sync_role(interaction.guild, 유저, row["points"])
        await interaction.response.send_message(
            f"✅ {유저.mention}님의 포인트에서 {포인트:,}P를 차감했습니다. (현재 {row['points']:,}P)", ephemeral=True
        )

    @app_commands.command(name="가챠추가", description="[관리자] 유저에게 가챠포인트를 지급합니다")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(유저="가챠포인트를 지급할 유저", 포인트="지급할 가챠포인트")
    async def add_gacha(self, interaction: discord.Interaction, 유저: discord.Member, 포인트: int):
        if 포인트 <= 0:
            await interaction.response.send_message("1 이상의 값을 입력해주세요.", ephemeral=True)
            return
        new_value = await db.add_gacha_points(interaction.guild.id, 유저.id, 포인트)
        await interaction.response.send_message(
            f"✅ {유저.mention}님에게 가챠포인트 {포인트:,}를 지급했습니다. (현재 {new_value:,}가챠P)", ephemeral=True
        )

    @app_commands.command(name="가챠제거", description="[관리자] 유저의 가챠포인트를 차감합니다")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(유저="가챠포인트를 차감할 유저", 포인트="차감할 가챠포인트")
    async def remove_gacha(self, interaction: discord.Interaction, 유저: discord.Member, 포인트: int):
        if 포인트 <= 0:
            await interaction.response.send_message("1 이상의 값을 입력해주세요.", ephemeral=True)
            return
        new_value = await db.add_gacha_points(interaction.guild.id, 유저.id, -포인트)
        await interaction.response.send_message(
            f"✅ {유저.mention}님의 가챠포인트에서 {포인트:,}를 차감했습니다. (현재 {new_value:,}가챠P)", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Points(bot))
