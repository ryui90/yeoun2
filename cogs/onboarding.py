from datetime import date

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from config import COLOR_MAIN


class Onboarding(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- !안내 ----------
    @commands.command(name="안내")
    @commands.has_permissions(manage_roles=True)
    async def guide(self, ctx: commands.Context, member: discord.Member, gender: str, birth_year: int, *, route: str):
        if gender not in ("남자", "여자"):
            await ctx.send("성별은 `남자` 또는 `여자`로 입력해주세요.\n예) `!안내 @유저 여자 2001 오픈채팅`")
            return

        cfg = await db.get_guild_config(ctx.guild.id)
        if not cfg or not any(cfg.values()):
            await ctx.send("먼저 `/온보딩설정` 명령어로 역할과 로그 채널을 설정해주세요.")
            return

        age = date.today().year - birth_year
        if age < 20:
            age_role_id, age_label = cfg["teen_role"], "10대"
        elif age < 30:
            age_role_id, age_label = cfg["twenties_role"], "20대"
        elif age < 40:
            age_role_id, age_label = cfg["thirties_role"], "30대"
        else:
            age_role_id, age_label = cfg["fourties_role"], "40대 이상"

        gender_role_id = cfg["male_role"] if gender == "남자" else cfg["female_role"]

        to_add = []
        for rid in (cfg["newface_role"], cfg["base_role"], gender_role_id, age_role_id):
            if rid:
                role = ctx.guild.get_role(rid)
                if role:
                    to_add.append(role)

        to_remove = []
        if cfg["unverified_role"]:
            role = ctx.guild.get_role(cfg["unverified_role"])
            if role:
                to_remove.append(role)

        try:
            if to_add:
                await member.add_roles(*to_add, reason="서버 안내 완료")
            if to_remove:
                await member.remove_roles(*to_remove, reason="서버 안내 완료")
        except discord.Forbidden:
            await ctx.send("역할을 변경할 권한이 없습니다. 봇 역할이 대상 역할들보다 위에 있는지 확인해주세요.")
            return

        embed = discord.Embed(title="✅ 새로운 멤버 안내 완료", color=COLOR_MAIN, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="유저", value=member.mention, inline=True)
        embed.add_field(name="성별", value=gender, inline=True)
        embed.add_field(name="연령대", value=age_label, inline=True)
        embed.add_field(name="경로", value=route, inline=False)
        embed.set_footer(text=f"처리자: {ctx.author.display_name}")

        if cfg["log_channel"]:
            log_channel = ctx.guild.get_channel(cfg["log_channel"])
            if log_channel:
                await log_channel.send(embed=embed)

        await ctx.message.add_reaction("✅")

    @guide.error
    async def guide_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("이 명령어는 역할 관리 권한이 있어야 사용할 수 있습니다.")
        elif isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
            await ctx.send("사용법: `!안내 @유저 남자/여자 출생년도(4자리) 경로`\n예) `!안내 @유저 여자 2001 오픈채팅`")
        else:
            raise error

    # ---------- !이름 ----------
    NICK_PREFIX = "『 신입 』"  # 닉네임 앞에 붙는 고정 문구. 바꾸고 싶으면 이 글자만 수정하세요.

    @commands.command(name="이름", aliases=["이름변경"])
    @commands.has_permissions(manage_nicknames=True)
    async def rename(self, ctx: commands.Context, member: discord.Member, *, new_name: str):
        final_nick = f"{self.NICK_PREFIX}{new_name}"
        if len(final_nick) > 32:  # 디스코드 닉네임 최대 길이
            await ctx.send("닉네임이 너무 깁니다. 32자를 넘을 수 없습니다.")
            return
        try:
            await member.edit(nick=final_nick, reason=f"{ctx.author}에 의한 닉네임 변경")
        except discord.Forbidden:
            await ctx.send("닉네임을 변경할 권한이 없습니다. 봇 역할이 대상보다 위에 있는지 확인해주세요.")
            return
        await ctx.message.add_reaction("✅")

    @rename.error
    async def rename_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("이 명령어는 닉네임 관리 권한이 있어야 사용할 수 있습니다.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("사용법: `!이름 @유저 이름`")
        else:
            raise error

    # ---------- /온보딩설정 ----------
    @app_commands.command(name="온보딩설정", description="!안내 명령어에서 사용할 역할/채널을 설정합니다")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        미인증역할="안내 시 제거할 역할",
        뉴페이스역할="안내 시 지급할 역할",
        기본역할="안내 시 지급할 기본 역할",
        남자역할="성별 - 남자 역할",
        여자역할="성별 - 여자 역할",
        십대역할="10대 역할",
        이십대역할="20대 역할",
        삼십대역할="30대 역할",
        사십대이상역할="40대 이상 역할",
        안내로그채널="안내 기록이 남을 채널",
    )
    async def setup_onboarding(
        self,
        interaction: discord.Interaction,
        미인증역할: discord.Role = None,
        뉴페이스역할: discord.Role = None,
        기본역할: discord.Role = None,
        남자역할: discord.Role = None,
        여자역할: discord.Role = None,
        십대역할: discord.Role = None,
        이십대역할: discord.Role = None,
        삼십대역할: discord.Role = None,
        사십대이상역할: discord.Role = None,
        안내로그채널: discord.TextChannel = None,
    ):
        await db.upsert_guild_config(
            interaction.guild.id,
            unverified_role=미인증역할.id if 미인증역할 else None,
            newface_role=뉴페이스역할.id if 뉴페이스역할 else None,
            base_role=기본역할.id if 기본역할 else None,
            male_role=남자역할.id if 남자역할 else None,
            female_role=여자역할.id if 여자역할 else None,
            teen_role=십대역할.id if 십대역할 else None,
            twenties_role=이십대역할.id if 이십대역할 else None,
            thirties_role=삼십대역할.id if 삼십대역할 else None,
            fourties_role=사십대이상역할.id if 사십대이상역할 else None,
            log_channel=안내로그채널.id if 안내로그채널 else None,
        )
        await interaction.response.send_message(
            "✅ 설정이 저장되었습니다. (입력하지 않은 항목은 기존 값이 유지됩니다)", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Onboarding(bot))
