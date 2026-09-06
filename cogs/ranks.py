import discord
from discord import app_commands
from discord.ext import commands

import database as db
from config import COLOR_MAIN

MEDALS = ["🥇", "🥈", "🥉"]


class Ranks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_tier_for_points(self, guild_id, points):
        """포인트에 해당하는 현재 랭크와 전체 랭크 목록(오름차순)을 반환"""
        tiers = await db.get_rank_tiers(guild_id)
        current = None
        for tier in tiers:
            if points >= tier["required_points"]:
                current = tier
            else:
                break
        return current, tiers

    async def sync_role(self, guild: discord.Guild, member: discord.Member, points: int = None):
        """포인트에 맞는 랭크 역할을 자동으로 지급/회수 (역할이 설정된 랭크에 한함)"""
        if member.bot:
            return
        if points is None:
            row = await db.get_user(guild.id, member.id)
            points = row["points"]

        current_tier, tiers = await self.get_tier_for_points(guild.id, points)
        tier_role_ids = {t["role_id"] for t in tiers if t["role_id"]}
        if not tier_role_ids:
            return

        target_role_id = current_tier["role_id"] if current_tier else None

        to_remove = [r for r in member.roles if r.id in tier_role_ids and r.id != target_role_id]
        to_add = []
        if target_role_id:
            role = guild.get_role(target_role_id)
            if role and role not in member.roles:
                to_add.append(role)

        if not to_remove and not to_add:
            return

        try:
            if to_remove:
                await member.remove_roles(*to_remove, reason="랭크 갱신")
            if to_add:
                await member.add_roles(*to_add, reason="랭크 갱신")
        except discord.Forbidden:
            pass

    @app_commands.command(name="랭크설정", description="[관리자] 포인트 랭크 단계를 등록/수정합니다")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        이름="랭크 이름 (예: 랭크1)",
        필요포인트="이 랭크가 되는 데 필요한 최소 포인트",
        역할="도달 시 자동으로 지급할 역할 (생략 가능, 표시만 하려면 비워두세요)",
    )
    async def set_rank(self, interaction: discord.Interaction, 이름: str, 필요포인트: int,
                        역할: discord.Role = None):
        if 필요포인트 < 0:
            await interaction.response.send_message("0 이상의 값을 입력해주세요.", ephemeral=True)
            return
        await db.upsert_rank_tier(interaction.guild.id, 이름, 필요포인트, 역할.id if 역할 else None)
        msg = f"✅ **{이름}** 랭크가 {필요포인트:,}P 이상일 때 부여되도록 등록되었습니다."
        if 역할:
            msg += f" (자동 지급 역할: {역할.mention})"
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="랭크제거", description="[관리자] 등록된 랭크 단계를 삭제합니다")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(이름="삭제할 랭크 이름")
    async def remove_rank(self, interaction: discord.Interaction, 이름: str):
        await db.delete_rank_tier(interaction.guild.id, 이름)
        await interaction.response.send_message(f"✅ **{이름}** 랭크를 삭제했습니다.", ephemeral=True)

    @app_commands.command(name="랭크목록", description="등록된 랭크 단계와 필요 포인트를 모두 확인합니다")
    async def list_ranks(self, interaction: discord.Interaction):
        tiers = await db.get_rank_tiers(interaction.guild.id)
        if not tiers:
            await interaction.response.send_message("등록된 랭크가 없습니다.", ephemeral=True)
            return
        lines = []
        for t in tiers:
            role_text = f" (도달 시 역할 지급: <@&{t['role_id']}>)" if t["role_id"] else ""
            lines.append(f"• **{t['name']}** — 포인트 {t['required_points']:,} 이상{role_text}")
        embed = discord.Embed(
            title="🏆 랭크 단계 안내",
            description=(
                "랭크는 `/포인트`로 확인하는 **포인트**(음성/채팅 활동 및 관리자 지급으로 쌓이는 그 포인트)"
                " 누적량으로 자동 결정됩니다. 도박에서 쓰는 가챠포인트는 랭크와 무관합니다.\n\n"
                + "\n".join(lines)
            ),
            color=COLOR_MAIN,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="랭크", description="누적 포인트에 따른 현재 랭크를 확인합니다")
    @app_commands.describe(유저="확인할 유저 (비워두면 본인)")
    async def rank(self, interaction: discord.Interaction, 유저: discord.Member = None):
        await interaction.response.defer()
        member = 유저 or interaction.user
        row = await db.get_user(interaction.guild.id, member.id)
        points = row["points"]

        current_tier, tiers = await self.get_tier_for_points(interaction.guild.id, points)
        await self.sync_role(interaction.guild, member, points)

        embed = discord.Embed(title="🏆 랭크 정보", color=COLOR_MAIN)
        embed.set_thumbnail(url=member.display_avatar.url)
        tier_name = current_tier["name"] if current_tier else "랭크 없음"
        embed.add_field(name="유저", value=member.mention, inline=True)
        embed.add_field(name="현재 랭크", value=tier_name, inline=True)
        embed.add_field(name="포인트", value=f"{points:,}P", inline=True)

        next_tier = None
        for tier in tiers:
            if tier["required_points"] > points:
                next_tier = tier
                break
        if next_tier:
            remain = next_tier["required_points"] - points
            embed.add_field(
                name="다음 랭크까지", value=f"**{next_tier['name']}** 까지 {remain:,}P 남음", inline=False
            )
        elif tiers:
            embed.add_field(name="다음 랭크까지", value="최고 랭크입니다 🎉", inline=False)
        else:
            embed.add_field(name="안내", value="아직 서버에 등록된 랭크 단계가 없습니다.", inline=False)

        embed.set_footer(text="랭크는 '포인트'(음성/채팅 등으로 쌓이는 것) 기준입니다 · /랭크목록으로 전체 단계 확인")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="랭크순위", description="포인트 및 랭크 순위를 확인합니다")
    async def rank_leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        rows = await db.get_top_points(interaction.guild.id, 10)
        tiers = await db.get_rank_tiers(interaction.guild.id)

        def tier_name_for(points):
            current = None
            for t in tiers:
                if points >= t["required_points"]:
                    current = t
                else:
                    break
            return current["name"] if current else "-"

        embed = discord.Embed(title="🏆 랭크 순위", color=COLOR_MAIN)
        lines = []
        for i, row in enumerate(rows):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"알 수 없음 ({row['user_id']})"
            prefix = MEDALS[i] if i < 3 else f"`{i + 1}`"
            lines.append(f"{prefix}  **{name}** — {tier_name_for(row['points'])} ({row['points']:,}P)")

        embed.description = "\n".join(lines) if lines else "아직 기록이 없습니다."
        embed.set_footer(text=f"{interaction.guild.name}")
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Ranks(bot))
