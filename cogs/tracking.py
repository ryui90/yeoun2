import time
import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils.image_card import create_stat_card


class Tracking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # (guild_id, user_id) -> {"start": time.time(), "channel_id": int}
        self.voice_sessions = {}

    @commands.Cog.listener()
    async def on_ready(self):
        # 봇 재시작 시 이미 음성채널에 있는 유저들의 세션을 새로 시작
        self.voice_sessions.clear()
        for guild in self.bot.guilds:
            afk_id = guild.afk_channel.id if guild.afk_channel else None
            for vc in guild.voice_channels:
                if vc.id == afk_id:
                    continue
                for member in vc.members:
                    if member.bot:
                        continue
                    self.voice_sessions[(guild.id, member.id)] = {
                        "start": time.time(), "channel_id": vc.id
                    }

    async def _rate_for_channel(self, guild_id, channel: discord.VoiceChannel):
        """채널이 속한 카테고리에 설정된 5분당 포인트 요율. 없으면 None(기본 요율 사용)"""
        if channel is None or channel.category_id is None:
            return None
        return await db.get_voice_category_rate(guild_id, channel.category_id)

    async def _flush_session(self, guild, user_id, channel: discord.VoiceChannel, key):
        session = self.voice_sessions.pop(key, None)
        if session is None:
            return
        elapsed = max(int(time.time() - session["start"]), 0)
        if elapsed <= 0:
            return
        rate = await self._rate_for_channel(guild.id, channel)
        await db.add_voice_time(guild.id, user_id, elapsed, rate_per_5min=rate)

        ranks_cog = self.bot.get_cog("Ranks")
        if ranks_cog:
            member = guild.get_member(user_id)
            if member:
                await ranks_cog.sync_role(guild, member)

    async def get_all_voice_totals(self, guild_id):
        """DB에 저장된 음성 시간 + 현재 접속 중인 세션의 실시간 시간을 합쳐서 반환"""
        rows = await db.get_all_users(guild_id)
        now = time.time()
        totals = {}
        for row in rows:
            total = row["voice_seconds"]
            key = (guild_id, row["user_id"])
            if key in self.voice_sessions:
                total += int(now - self.voice_sessions[key]["start"])
            totals[row["user_id"]] = total
        return totals

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild = member.guild
        afk_id = guild.afk_channel.id if guild.afk_channel else None
        key = (guild.id, member.id)

        before_valid = before.channel is not None and before.channel.id != afk_id
        after_valid = after.channel is not None and after.channel.id != afk_id

        if not before_valid and after_valid:
            self.voice_sessions[key] = {"start": time.time(), "channel_id": after.channel.id}
        elif before_valid and not after_valid:
            await self._flush_session(guild, member.id, before.channel, key)
        elif before_valid and after_valid and before.channel.id != after.channel.id:
            # 다른 채널로 이동: 이전 채널 기준 요율로 정산 후 새 세션 시작
            await self._flush_session(guild, member.id, before.channel, key)
            self.voice_sessions[key] = {"start": time.time(), "channel_id": after.channel.id}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None:
            return
        await db.add_message(message.guild.id, message.author.id)

        ranks_cog = self.bot.get_cog("Ranks")
        if ranks_cog:
            await ranks_cog.sync_role(message.guild, message.author)

    @app_commands.command(name="음성", description="음성 채팅 누적 시간을 확인합니다")
    @app_commands.describe(유저="확인할 유저 (비워두면 본인)")
    async def voice_stat(self, interaction: discord.Interaction, 유저: discord.Member = None):
        await interaction.response.defer()
        member = 유저 or interaction.user

        await db.get_user(interaction.guild.id, member.id)  # 유저 레코드 보장
        totals = await self.get_all_voice_totals(interaction.guild.id)
        total_seconds = totals.get(member.id, 0)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        sorted_ids = sorted(totals.keys(), key=lambda uid: totals[uid], reverse=True)
        rank = sorted_ids.index(member.id) + 1 if member.id in sorted_ids else len(sorted_ids) + 1
        total = len(sorted_ids)

        file = await create_stat_card(
            member, "음성 누적 시간",
            f"{hours}시간 {minutes}분",
            f"서버 음성 순위 {rank}위 / {total}명 중"
        )
        await interaction.followup.send(file=file)

    @app_commands.command(name="채팅", description="채팅 누적 횟수를 확인합니다")
    @app_commands.describe(유저="확인할 유저 (비워두면 본인)")
    async def chat_stat(self, interaction: discord.Interaction, 유저: discord.Member = None):
        await interaction.response.defer()
        member = 유저 or interaction.user

        row = await db.get_user(interaction.guild.id, member.id)
        rank, total = await db.get_chat_rank(interaction.guild.id, member.id)
        file = await create_stat_card(
            member, "채팅 누적 횟수",
            f"{row['message_count']:,}회",
            f"서버 채팅 순위 {rank}위 / {total}명 중"
        )
        await interaction.followup.send(file=file)


async def setup(bot):
    await bot.add_cog(Tracking(bot))
