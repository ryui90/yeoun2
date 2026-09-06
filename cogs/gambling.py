import random
import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from config import GAMBLING_MAX_BET, WHEEL_MAX_BET, GAMBLING_POOL_MAX_BET

HAND_EMOJI = {"가위": "✌️", "바위": "✊", "보": "🖐️"}
BEATS = {"가위": "보", "바위": "가위", "보": "바위"}


# ========================= 야바위 =========================

class ShellGameView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int, amount: int):
        super().__init__(timeout=20)
        self.guild_id = guild_id
        self.user_id = user_id
        self.amount = amount
        self.answer = random.randint(1, 3)
        self.message = None

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(content="⏰ 시간이 초과되었습니다.", view=self)
            except Exception:
                pass

    async def pick(self, interaction: discord.Interaction, cup: int):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 본인 게임만 플레이 가능합니다.", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        cups = ["🥤", "🥤", "🥤"]
        cups[self.answer - 1] = "⚽"

        if cup == self.answer:
            reward = self.amount * 2
            await db.add_gacha_points(self.guild_id, self.user_id, reward)
            embed = discord.Embed(
                title="🎯 야바위 성공!",
                description=f"{' '.join(cups)}\n\n+{self.amount:,} 가챠P",
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="💸 야바위 실패!",
                description=f"{' '.join(cups)}\n\n-{self.amount:,} 가챠P",
                color=discord.Color.red(),
            )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="1번 컵")
    async def cup1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.pick(interaction, 1)

    @discord.ui.button(label="2번 컵")
    async def cup2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.pick(interaction, 2)

    @discord.ui.button(label="3번 컵")
    async def cup3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.pick(interaction, 3)


# ========================= 가위바위보 (대인전) =========================

class RPSChooseView(discord.ui.View):
    def __init__(self, guild_id, challenger, opponent, amount):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.challenger = challenger  # discord.Member
        self.opponent = opponent      # discord.Member
        self.amount = amount
        self.choices = {}
        self.message = None

    async def on_timeout(self):
        if self.message and len(self.choices) < 2:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(content="⏰ 시간 초과로 대결이 취소되었습니다.", embed=None, view=self)
            except Exception:
                pass

    async def handle_choice(self, interaction: discord.Interaction, hand: str):
        valid_ids = (self.challenger.id, self.opponent.id)
        if interaction.user.id not in valid_ids:
            await interaction.response.send_message("❌ 이 대결의 참가자가 아닙니다.", ephemeral=True)
            return
        if interaction.user.id in self.choices:
            await interaction.response.send_message("이미 선택하셨습니다. 상대를 기다려주세요.", ephemeral=True)
            return

        self.choices[interaction.user.id] = hand
        await interaction.response.send_message(
            f"{HAND_EMOJI[hand]} **{hand}** 선택 완료! 상대의 선택을 기다리는 중...", ephemeral=True
        )

        if len(self.choices) < 2:
            return

        for item in self.children:
            item.disabled = True

        c_hand = self.choices[self.challenger.id]
        o_hand = self.choices[self.opponent.id]

        if c_hand == o_hand:
            result_text = "🤝 무승부! 포인트 변동 없음"
            color = discord.Color.yellow()
        elif BEATS[c_hand] == o_hand:
            await db.add_gacha_points(self.guild_id, self.challenger.id, self.amount)
            await db.add_gacha_points(self.guild_id, self.opponent.id, -self.amount)
            result_text = f"🏆 {self.challenger.mention} 승리! (+{self.amount:,} / -{self.amount:,} 가챠P)"
            color = discord.Color.green()
        else:
            await db.add_gacha_points(self.guild_id, self.opponent.id, self.amount)
            await db.add_gacha_points(self.guild_id, self.challenger.id, -self.amount)
            result_text = f"🏆 {self.opponent.mention} 승리! (+{self.amount:,} / -{self.amount:,} 가챠P)"
            color = discord.Color.green()

        embed = discord.Embed(
            title="✊✌️🖐️ 가위바위보 결과",
            description=(
                f"{self.challenger.mention}: {HAND_EMOJI[c_hand]} {c_hand}\n"
                f"{self.opponent.mention}: {HAND_EMOJI[o_hand]} {o_hand}\n\n"
                f"{result_text}"
            ),
            color=color,
        )
        try:
            await self.message.edit(content=None, embed=embed, view=self)
        except Exception:
            pass
        self.stop()

    @discord.ui.button(label="가위", emoji="✌️")
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "가위")

    @discord.ui.button(label="바위", emoji="✊")
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "바위")

    @discord.ui.button(label="보", emoji="🖐️")
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "보")


class RPSJoinView(discord.ui.View):
    def __init__(self, guild_id, challenger: discord.Member, opponent: discord.Member, amount):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.challenger = challenger
        self.opponent = opponent
        self.amount = amount
        self.message = None

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(content="⏰ 참여 시간이 초과되어 대결이 취소되었습니다.", view=self)
            except Exception:
                pass

    @discord.ui.button(label="참여", style=discord.ButtonStyle.success, emoji="✋")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("❌ 이 대결의 상대만 참여할 수 있습니다.", ephemeral=True)
            return

        challenger_row = await db.get_user(self.guild_id, self.challenger.id)
        opponent_row = await db.get_user(self.guild_id, self.opponent.id)
        if challenger_row["gacha_points"] < self.amount or opponent_row["gacha_points"] < self.amount:
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(
                content="❌ 둘 중 한 명의 가챠포인트가 부족해 대결이 취소되었습니다.", view=self
            )
            self.stop()
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content=f"✅ {self.opponent.mention} 님이 참여했습니다! 아래에서 각자 손을 선택하세요.", view=self
        )

        choose_view = RPSChooseView(self.guild_id, self.challenger, self.opponent, self.amount)
        embed = discord.Embed(
            title="✊✌️🖐️ 손을 선택하세요!",
            description=f"{self.challenger.mention} vs {self.opponent.mention}\n배팅: **{self.amount:,}가챠P**\n"
                        f"(선택 결과는 본인에게만 보이며, 둘 다 선택하면 결과가 공개됩니다)",
            color=discord.Color.blurple(),
        )
        msg = await interaction.followup.send(embed=embed, view=choose_view)
        choose_view.message = msg
        self.stop()


class Gambling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_races = {}
        self.active_pools = {}

    # ========== 야바위 ==========
    @app_commands.command(name="야바위", description="컵 속 공 찾기 (가챠포인트 사용)")
    @app_commands.describe(배팅="배팅할 가챠포인트")
    async def shell_game(self, interaction: discord.Interaction, 배팅: int):
        if 배팅 <= 0 or 배팅 > GAMBLING_MAX_BET:
            await interaction.response.send_message(f"❌ 1~{GAMBLING_MAX_BET} 사이로 배팅하세요.", ephemeral=True)
            return

        row = await db.get_user(interaction.guild.id, interaction.user.id)
        if row["gacha_points"] < 배팅:
            await interaction.response.send_message("❌ 가챠포인트가 부족합니다.", ephemeral=True)
            return

        await db.add_gacha_points(interaction.guild.id, interaction.user.id, -배팅)

        await interaction.response.send_message("🎲 컵을 섞는 중...")
        msg = await interaction.original_response()

        cups = ["🥤", "🥤", "⚽"]
        for _ in range(10):
            random.shuffle(cups)
            embed = discord.Embed(
                title="🎲 컵 섞는 중...", description=" ".join(cups), color=discord.Color.blurple()
            )
            await msg.edit(content=None, embed=embed)
            await asyncio.sleep(0.5)

        embed = discord.Embed(
            title="🎯 공은 어디에 있을까요?", description="🥤 🥤 🥤", color=discord.Color.gold()
        )
        view = ShellGameView(interaction.guild.id, interaction.user.id, 배팅)
        await msg.edit(embed=embed, view=view)
        view.message = msg

    # ========== 홀짝 ==========
    @app_commands.command(name="홀짝", description="홀짝 게임 - 1/2 확률 (가챠포인트 사용)")
    @app_commands.describe(선택="홀 또는 짝", 배팅="배팅할 가챠포인트")
    @app_commands.choices(선택=[
        app_commands.Choice(name="홀", value="홀"),
        app_commands.Choice(name="짝", value="짝"),
    ])
    async def odd_even(self, interaction: discord.Interaction, 선택: str, 배팅: int):
        if 배팅 <= 0 or 배팅 > GAMBLING_MAX_BET:
            await interaction.response.send_message(f"❌ 1~{GAMBLING_MAX_BET} 사이로 배팅하세요.", ephemeral=True)
            return

        row = await db.get_user(interaction.guild.id, interaction.user.id)
        if row["gacha_points"] < 배팅:
            await interaction.response.send_message("❌ 가챠포인트가 부족합니다.", ephemeral=True)
            return

        number = random.randint(1, 10)
        result = "홀" if number % 2 == 1 else "짝"
        win = 선택 == result

        if win:
            await db.add_gacha_points(interaction.guild.id, interaction.user.id, 배팅)
            embed = discord.Embed(
                title="🎲 홀짝 - 승리!",
                description=f"숫자: **{number}** ({result})\n**+{배팅:,}** 가챠P 획득!",
                color=discord.Color.green(),
            )
        else:
            await db.add_gacha_points(interaction.guild.id, interaction.user.id, -배팅)
            embed = discord.Embed(
                title="🎲 홀짝 - 패배",
                description=f"숫자: **{number}** ({result})\n**-{배팅:,}** 가챠P",
                color=discord.Color.red(),
            )

        await interaction.response.send_message(embed=embed)

    # ========== 동전던지기 (애니메이션) ==========
    @app_commands.command(name="동전던지기", description="동전 던지기 - 1/2 확률 (가챠포인트 사용)")
    @app_commands.describe(선택="앞면 또는 뒷면", 배팅="배팅할 가챠포인트")
    @app_commands.choices(선택=[
        app_commands.Choice(name="앞면", value="앞면"),
        app_commands.Choice(name="뒷면", value="뒷면"),
    ])
    async def coin_flip(self, interaction: discord.Interaction, 선택: str, 배팅: int):
        if 배팅 <= 0 or 배팅 > GAMBLING_MAX_BET:
            await interaction.response.send_message(f"❌ 1~{GAMBLING_MAX_BET} 사이로 배팅하세요.", ephemeral=True)
            return

        row = await db.get_user(interaction.guild.id, interaction.user.id)
        if row["gacha_points"] < 배팅:
            await interaction.response.send_message("❌ 가챠포인트가 부족합니다.", ephemeral=True)
            return

        result = random.choice(["앞면", "뒷면"])

        await interaction.response.send_message(
            embed=discord.Embed(title="🪙 동전을 던지는 중...", description="🪙", color=discord.Color.blurple())
        )
        msg = await interaction.original_response()

        frames = ["🪙", "💿", "🪙", "💿", "🪙", "💿"]
        for i, frame in enumerate(frames):
            await msg.edit(embed=discord.Embed(
                title="🪙 동전을 던지는 중...", description=frame, color=discord.Color.blurple()
            ))
            await asyncio.sleep(0.3 + i * 0.05)

        win = 선택 == result
        emoji = "🪙" if result == "앞면" else "💿"

        if win:
            await db.add_gacha_points(interaction.guild.id, interaction.user.id, 배팅)
            embed = discord.Embed(
                title=f"{emoji} 동전던지기 - 승리!",
                description=f"결과: **{result}**\n**+{배팅:,}** 가챠P 획득!",
                color=discord.Color.green(),
            )
        else:
            await db.add_gacha_points(interaction.guild.id, interaction.user.id, -배팅)
            embed = discord.Embed(
                title=f"{emoji} 동전던지기 - 패배",
                description=f"결과: **{result}**\n**-{배팅:,}** 가챠P",
                color=discord.Color.red(),
            )

        await msg.edit(embed=embed)

    # ========== OX 퀴즈 ==========
    @app_commands.command(name="ox", description="O/X 선택 - 1/2 확률 (가챠포인트 사용)")
    @app_commands.describe(선택="O 또는 X", 배팅="배팅할 가챠포인트")
    @app_commands.choices(선택=[
        app_commands.Choice(name="O", value="O"),
        app_commands.Choice(name="X", value="X"),
    ])
    async def ox_game(self, interaction: discord.Interaction, 선택: str, 배팅: int):
        if 배팅 <= 0 or 배팅 > GAMBLING_MAX_BET:
            await interaction.response.send_message(f"❌ 1~{GAMBLING_MAX_BET} 사이로 배팅하세요.", ephemeral=True)
            return

        row = await db.get_user(interaction.guild.id, interaction.user.id)
        if row["gacha_points"] < 배팅:
            await interaction.response.send_message("❌ 가챠포인트가 부족합니다.", ephemeral=True)
            return

        result = random.choice(["O", "X"])
        win = 선택 == result

        if win:
            await db.add_gacha_points(interaction.guild.id, interaction.user.id, 배팅)
            embed = discord.Embed(
                title="⭕ O/X - 승리!",
                description=f"정답: **{result}**\n**+{배팅:,}** 가챠P 획득!",
                color=discord.Color.green(),
            )
        else:
            await db.add_gacha_points(interaction.guild.id, interaction.user.id, -배팅)
            embed = discord.Embed(
                title="❌ O/X - 패배",
                description=f"정답: **{result}**\n**-{배팅:,}** 가챠P",
                color=discord.Color.red(),
            )

        await interaction.response.send_message(embed=embed)

    # ========== 가위바위보 (대인전) ==========
    @app_commands.command(name="가위바위보", description="다른 유저에게 가위바위보 대결을 신청합니다 (가챠포인트 사용)")
    @app_commands.describe(상대="대결할 상대", 배팅="배팅할 가챠포인트")
    async def rps_challenge(self, interaction: discord.Interaction, 상대: discord.Member, 배팅: int):
        if 상대.bot:
            await interaction.response.send_message("❌ 봇과는 대결할 수 없습니다.", ephemeral=True)
            return
        if 상대.id == interaction.user.id:
            await interaction.response.send_message("❌ 자기 자신과는 대결할 수 없습니다.", ephemeral=True)
            return
        if 배팅 <= 0 or 배팅 > GAMBLING_MAX_BET:
            await interaction.response.send_message(f"❌ 1~{GAMBLING_MAX_BET} 사이로 배팅하세요.", ephemeral=True)
            return

        row = await db.get_user(interaction.guild.id, interaction.user.id)
        if row["gacha_points"] < 배팅:
            await interaction.response.send_message("❌ 가챠포인트가 부족합니다.", ephemeral=True)
            return

        view = RPSJoinView(interaction.guild.id, interaction.user, 상대, 배팅)
        embed = discord.Embed(
            title="✊✌️🖐️ 가위바위보 대결 신청!",
            description=(
                f"{interaction.user.mention} 님이 {상대.mention} 님에게 "
                f"**{배팅:,}가챠P** 대결을 신청했습니다!\n아래 **[참여]** 버튼을 눌러 수락하세요. (60초 이내)"
            ),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    # ========== 돌림판 (애니메이션) ==========
    @app_commands.command(name="돌림판", description=f"돌림판 돌리기 (가챠포인트 사용, 최대 {WHEEL_MAX_BET:,}P)")
    @app_commands.describe(배팅="배팅할 가챠포인트")
    async def spin_wheel(self, interaction: discord.Interaction, 배팅: int):
        if 배팅 <= 0 or 배팅 > WHEEL_MAX_BET:
            await interaction.response.send_message(f"❌ 1~{WHEEL_MAX_BET:,} 사이로 배팅하세요.", ephemeral=True)
            return

        row = await db.get_user(interaction.guild.id, interaction.user.id)
        if row["gacha_points"] < 배팅:
            await interaction.response.send_message("❌ 가챠포인트가 부족합니다.", ephemeral=True)
            return

        # 확률: 꽝 50%, 1배 30%, 2배 10%, 3배 5%, 5배 4.9%, 10배 0.1%
        roll = random.random() * 100
        if roll < 50:
            multiplier, result_text = 0, "꽝"
        elif roll < 80:
            multiplier, result_text = 1, "1배"
        elif roll < 90:
            multiplier, result_text = 2, "2배"
        elif roll < 95:
            multiplier, result_text = 3, "3배"
        elif roll < 99.9:
            multiplier, result_text = 5, "5배"
        else:
            multiplier, result_text = 10, "🌟 10배! 🌟"

        segments = ["꽝", "1배", "2배", "3배", "5배", "10배"]

        await interaction.response.send_message(
            embed=discord.Embed(title="🎡 돌림판을 돌리는 중...", description="샤샤샤샤샤...", color=discord.Color.blurple())
        )
        msg = await interaction.original_response()

        delays = [0.15, 0.15, 0.2, 0.2, 0.25, 0.3, 0.35, 0.45, 0.6, 0.8]
        for i, delay in enumerate(delays):
            preview = random.choice(segments) if i < len(delays) - 1 else result_text.replace("🌟 ", "").replace(" 🌟", "")
            await msg.edit(embed=discord.Embed(
                title="🎡 돌림판을 돌리는 중...", description=f"➡️ **{preview}** ⬅️", color=discord.Color.blurple()
            ))
            await asyncio.sleep(delay)

        await db.add_gacha_points(interaction.guild.id, interaction.user.id, -배팅)
        reward = 배팅 * multiplier
        await db.add_gacha_points(interaction.guild.id, interaction.user.id, reward)

        if multiplier == 0:
            embed = discord.Embed(title="🎡 돌림판 - 꽝!", description=f"**-{배팅:,}** 가챠P", color=discord.Color.red())
        elif multiplier == 1:
            embed = discord.Embed(title="🎡 돌림판 - 1배", description="배팅금 그대로!", color=discord.Color.yellow())
        else:
            change = reward - 배팅
            embed = discord.Embed(
                title=f"🎡 돌림판 - {result_text}",
                description=f"**+{change:,}** 가챠P 획득!",
                color=discord.Color.gold(),
            )

        await msg.edit(embed=embed)

    # ========== 경마 (애니메이션 + 참여자 목록) ==========
    @app_commands.command(name="경마시작", description="경마 게임을 시작합니다 (30초 배팅 시간, 가챠포인트 사용)")
    async def start_race(self, interaction: discord.Interaction):
        if interaction.channel.id in self.active_races:
            await interaction.response.send_message("❌ 이미 진행 중인 경마가 있습니다.", ephemeral=True)
            return

        horse_names = ["1번마", "2번마", "3번마", "4번마", "5번마"]
        race = {"bets": {}, "horse_names": horse_names, "message": None}
        self.active_races[interaction.channel.id] = race

        embed = self._build_race_embed(race)
        await interaction.response.send_message(embed=embed)
        race["message"] = await interaction.original_response()

        asyncio.create_task(self.run_race_after_delay(interaction.channel))

    def _build_race_embed(self, race):
        embed = discord.Embed(
            title="🏁 경마 시작!",
            description="30초 안에 `/경마배팅` 으로 배팅하세요!\n\n"
                        + "\n".join(f"🐎 {name}" for name in race["horse_names"]),
            color=discord.Color.blue(),
        )
        if race["bets"]:
            lines = []
            for user_id, (horse, amount) in race["bets"].items():
                lines.append(f"• <@{user_id}> → {horse}번마 ({amount:,}P)")
            embed.add_field(name=f"현재 참여자 ({len(race['bets'])}명)", value="\n".join(lines), inline=False)
        embed.set_footer(text="30초 후 자동으로 레이스가 시작됩니다")
        return embed

    async def run_race_after_delay(self, channel):
        await asyncio.sleep(30)
        await self.run_race(channel)

    @app_commands.command(name="경마배팅", description="경마에 배팅합니다 (가챠포인트 사용)")
    @app_commands.describe(말번호="1~5번 중 선택", 배팅="배팅할 가챠포인트")
    async def bet_race(self, interaction: discord.Interaction, 말번호: int, 배팅: int):
        if interaction.channel.id not in self.active_races:
            await interaction.response.send_message("❌ 진행 중인 경마가 없습니다.", ephemeral=True)
            return
        if 말번호 < 1 or 말번호 > 5:
            await interaction.response.send_message("❌ 1~5 사이의 번호를 선택하세요.", ephemeral=True)
            return
        if 배팅 <= 0:
            await interaction.response.send_message("❌ 1 이상 배팅하세요.", ephemeral=True)
            return

        row = await db.get_user(interaction.guild.id, interaction.user.id)
        if row["gacha_points"] < 배팅:
            await interaction.response.send_message("❌ 가챠포인트가 부족합니다.", ephemeral=True)
            return

        race = self.active_races[interaction.channel.id]
        if interaction.user.id in race["bets"]:
            old_horse, old_amount = race["bets"][interaction.user.id]
            if old_horse != 말번호:
                await interaction.response.send_message("❌ 이미 다른 말에 배팅했습니다.", ephemeral=True)
                return
            race["bets"][interaction.user.id] = (말번호, old_amount + 배팅)
        else:
            race["bets"][interaction.user.id] = (말번호, 배팅)

        await db.add_gacha_points(interaction.guild.id, interaction.user.id, -배팅)
        await interaction.response.send_message(f"✅ **{말번호}번 말**에 **{배팅:,}** 가챠P 배팅 완료!", ephemeral=True)

        if race["message"]:
            try:
                await race["message"].edit(embed=self._build_race_embed(race))
            except Exception:
                pass

    async def run_race(self, channel):
        if channel.id not in self.active_races:
            return
        race = self.active_races.pop(channel.id)

        if not race["bets"]:
            await channel.send("❌ 아무도 배팅하지 않아 경마가 취소되었습니다.")
            return

        # ---- 레이스 애니메이션 시뮬레이션 ----
        track_length = 24
        positions = {i: 0 for i in range(1, 6)}
        race_msg = await channel.send(embed=discord.Embed(title="🏁 경주 시작!", color=discord.Color.blue()))

        winner = None
        for _ in range(30):
            for h in positions:
                positions[h] += random.randint(1, 3)
            lines = []
            for h in range(1, 6):
                pos = min(positions[h], track_length)
                lines.append(f"{h}번  " + "─" * pos + "🐎" + "─" * (track_length - pos) + "🏁")
            await race_msg.edit(embed=discord.Embed(
                title="🏁 경주 진행 중...", description="```\n" + "\n".join(lines) + "\n```",
                color=discord.Color.blue(),
            ))
            finishers = [h for h, p in positions.items() if p >= track_length]
            if finishers:
                winner = finishers[0]
                break
            await asyncio.sleep(0.5)

        if winner is None:
            winner = max(positions, key=positions.get)

        embed = discord.Embed(title="🏆 경마 결과!", description=f"**{winner}번 말** 우승!", color=discord.Color.gold())

        winners_text, losers_text = "", ""
        for user_id, (horse, amount) in race["bets"].items():
            member = channel.guild.get_member(user_id)
            name = member.display_name if member else f"유저 {user_id}"
            if horse == winner:
                winnings = amount * 3
                await db.add_gacha_points(channel.guild.id, user_id, winnings)
                winners_text += f"🎉 {name}: +{winnings:,} 가챠P\n"
            else:
                losers_text += f"💔 {name}: -{amount:,} 가챠P\n"

        if winners_text:
            embed.add_field(name="승자", value=winners_text, inline=False)
        if losers_text:
            embed.add_field(name="패자", value=losers_text, inline=False)

        await race_msg.edit(embed=embed)

    # ========== 몰아주기 (참여자 목록) ==========
    @app_commands.command(name="몰아주기시작", description=f"몰아주기 게임 시작 (최대 {GAMBLING_POOL_MAX_BET:,}가챠P, 30초 대기)")
    async def start_pool(self, interaction: discord.Interaction):
        if interaction.channel.id in self.active_pools:
            await interaction.response.send_message("❌ 이미 진행 중인 몰아주기가 있습니다.", ephemeral=True)
            return

        pool = {"bets": {}, "message": None}
        self.active_pools[interaction.channel.id] = pool

        embed = self._build_pool_embed(pool)
        await interaction.response.send_message(embed=embed)
        pool["message"] = await interaction.original_response()

        asyncio.create_task(self.run_pool_after_delay(interaction.channel))

    def _build_pool_embed(self, pool):
        embed = discord.Embed(
            title="🎰 몰아주기 시작!",
            description=f"30초 안에 `/몰아주기참여` 로 참여하세요!\n최대 {GAMBLING_POOL_MAX_BET:,}가챠P까지 배팅 가능",
            color=discord.Color.purple(),
        )
        if pool["bets"]:
            lines = [f"• <@{uid}>: {amt:,}P" for uid, amt in pool["bets"].items()]
            total = sum(pool["bets"].values())
            embed.add_field(
                name=f"현재 참여자 ({len(pool['bets'])}명, 누적 {total:,}P)",
                value="\n".join(lines), inline=False
            )
        embed.set_footer(text="30초 후 당첨자 추첨!")
        return embed

    async def run_pool_after_delay(self, channel):
        await asyncio.sleep(30)
        await self.run_pool(channel)

    @app_commands.command(name="몰아주기참여", description=f"몰아주기에 참여합니다 (최대 {GAMBLING_POOL_MAX_BET:,}가챠P)")
    @app_commands.describe(배팅="배팅할 가챠포인트")
    async def join_pool(self, interaction: discord.Interaction, 배팅: int):
        if interaction.channel.id not in self.active_pools:
            await interaction.response.send_message("❌ 진행 중인 몰아주기가 없습니다.", ephemeral=True)
            return
        if 배팅 <= 0 or 배팅 > GAMBLING_POOL_MAX_BET:
            await interaction.response.send_message(f"❌ 1~{GAMBLING_POOL_MAX_BET:,} 사이로 배팅하세요.", ephemeral=True)
            return

        pool = self.active_pools[interaction.channel.id]
        if interaction.user.id in pool["bets"]:
            await interaction.response.send_message("❌ 이미 참여했습니다.", ephemeral=True)
            return

        row = await db.get_user(interaction.guild.id, interaction.user.id)
        if row["gacha_points"] < 배팅:
            await interaction.response.send_message("❌ 가챠포인트가 부족합니다.", ephemeral=True)
            return

        pool["bets"][interaction.user.id] = 배팅
        await db.add_gacha_points(interaction.guild.id, interaction.user.id, -배팅)
        await interaction.response.send_message(f"✅ **{배팅:,}** 가챠P로 참여 완료!", ephemeral=True)

        if pool["message"]:
            try:
                await pool["message"].edit(embed=self._build_pool_embed(pool))
            except Exception:
                pass

    async def run_pool(self, channel):
        if channel.id not in self.active_pools:
            return
        pool = self.active_pools.pop(channel.id)

        if len(pool["bets"]) < 2:
            for user_id, amount in pool["bets"].items():
                await db.add_gacha_points(channel.guild.id, user_id, amount)
            await channel.send("❌ 참가자가 2명 미만이라 취소되었습니다. 가챠포인트가 환불됩니다.")
            return

        total_pot = sum(pool["bets"].values())
        participants = list(pool["bets"].keys())
        winner_id = random.choice(participants)
        winner = channel.guild.get_member(winner_id)
        winner_name = winner.display_name if winner else f"유저 {winner_id}"

        await db.add_gacha_points(channel.guild.id, winner_id, total_pot)

        embed = discord.Embed(
            title="🎊 몰아주기 결과!",
            description=f"**{winner_name}** 님이 **{total_pot:,}** 가챠P 획득!",
            color=discord.Color.gold(),
        )
        participants_text = ""
        for user_id, amount in pool["bets"].items():
            member = channel.guild.get_member(user_id)
            name = member.display_name if member else f"유저 {user_id}"
            marker = "👑" if user_id == winner_id else "💸"
            participants_text += f"{marker} {name}: {amount:,} 가챠P\n"
        embed.add_field(name="참가자", value=participants_text, inline=False)

        await channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Gambling(bot))
