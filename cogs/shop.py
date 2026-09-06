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


async def _try_purchase(interaction: discord.Interaction, role_id: int):
    guild = interaction.guild
    role = guild.get_role(role_id)
    if role is None:
        await interaction.response.send_message("이 역할은 더 이상 존재하지 않습니다.", ephemeral=True)
        return
    if role in interaction.user.roles:
        await interaction.response.send_message("이미 보유하고 있는 역할입니다.", ephemeral=True)
        return

    price = await db.get_shop_price(guild.id, role_id)
    if price is None:
        await interaction.response.send_message("이 역할은 더 이상 상점에서 판매하지 않습니다.", ephemeral=True)
        return

    row = await db.get_user(guild.id, interaction.user.id)
    if row["points"] < price:
        await interaction.response.send_message(
            f"포인트가 부족합니다. (보유: {row['points']:,}P / 필요: {price:,}P)", ephemeral=True
        )
        return

    await db.add_points(guild.id, interaction.user.id, -price)
    try:
        await interaction.user.add_roles(role, reason="포인트 상점 구매")
    except discord.Forbidden:
        await db.add_points(guild.id, interaction.user.id, price)
        await interaction.response.send_message(
            "역할을 지급할 권한이 없어 구매가 취소되었습니다.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"🎉 {role.mention} 역할을 구매했습니다! (-{price:,}P, 남은 포인트: {row['points'] - price:,}P)",
        ephemeral=True,
    )


class ItemSelect(discord.ui.Select):
    def __init__(self, roles_data):
        options = [
            discord.SelectOption(
                label=name[:100],
                description=f"{price:,}P",
                value=str(role_id),
            )
            for role_id, price, name in roles_data[:25]
        ]
        super().__init__(
            placeholder="구매할 역할을 선택하세요",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        await _try_purchase(interaction, role_id)


class ItemSelectView(discord.ui.View):
    def __init__(self, roles_data):
        super().__init__(timeout=120)
        self.add_item(ItemSelect(roles_data))


class CategorySelect(discord.ui.Select):
    def __init__(self, guild_id: int, categories):
        if categories:
            options = [
                discord.SelectOption(
                    label=cat[:100],
                    description=f"{count}개",
                    value=cat[:100],
                )
                for cat, count in categories[:25]
            ]
        else:
            options = [discord.SelectOption(label="등록된 상품 없음", value="__none__")]

        super().__init__(
            placeholder="카테고리를 선택하세요",
            options=options,
            min_values=1,
            max_values=1,
            custom_id=f"shop_category_select:{guild_id}",
        )
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        if category == "__none__":
            await interaction.response.send_message("등록된 상점 역할이 없습니다.", ephemeral=True)
            return

        rows = await db.get_shop_roles_by_category(self.guild_id, category)
        roles_data = []
        for r in rows:
            role = interaction.guild.get_role(r["role_id"])
            if role:
                roles_data.append((r["role_id"], r["price"], role.name))

        if not roles_data:
            await interaction.response.send_message("이 카테고리에는 구매 가능한 역할이 없습니다.", ephemeral=True)
            return

        lines = "\n".join(f"• **{name}** — {price:,}P" for _, price, name in roles_data)
        embed = discord.Embed(
            title=f"🛒 {category}",
            description=f"구매하실 역할을 아래에서 선택해주세요.\n\n{lines}",
            color=COLOR_MAIN,
        )
        embed.set_footer(text="이 메세지는 본인만 볼 수 있어요")
        view = ItemSelectView(roles_data)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class CategoryView(discord.ui.View):
    def __init__(self, guild_id: int, categories):
        super().__init__(timeout=None)
        self.add_item(CategorySelect(guild_id, categories))


class ResetConfirmView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=30)
        self.guild_id = guild_id

    @discord.ui.button(label="초기화", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await db.delete_all_shop_roles(self.guild_id)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content="✅ 상점이 초기화되었습니다. 등록된 모든 상품이 삭제되었습니다.\n"
                    "이미 보내둔 상점 메세지가 있다면 `/상점메세지`로 다시 보내주세요.",
            view=self,
        )
        self.stop()

    @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="취소되었습니다.", view=self)
        self.stop()


class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def register_persistent_views(self):
        """봇 재시작 후에도 기존에 보낸 상점 메세지의 드롭다운이 동작하도록 뷰를 재등록"""
        for guild in self.bot.guilds:
            categories = await db.get_shop_categories(guild.id)
            if categories:
                self.bot.add_view(CategoryView(guild.id, categories))

    @app_commands.command(name="상점역할", description="[관리자] 포인트 상점에 판매할 역할을 등록합니다")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        역할="상점에 등록할 역할",
        포인트="구매에 필요한 포인트",
        카테고리="역할이 속할 카테고리 이름 (생략 시 '기타')",
    )
    async def add_shop_role(self, interaction: discord.Interaction, 역할: discord.Role,
                             포인트: int, 카테고리: str = "기타"):
        if 포인트 <= 0:
            await interaction.response.send_message("1 이상의 값을 입력해주세요.", ephemeral=True)
            return
        await db.upsert_shop_role(interaction.guild.id, 역할.id, 포인트, 카테고리)
        await interaction.response.send_message(
            f"✅ {역할.mention} 역할이 **{카테고리}** 카테고리에 {포인트:,}P로 등록되었습니다.\n"
            f"`/상점메세지`로 상점 메세지를 새로 보내면 카테고리 목록에 반영됩니다.",
            ephemeral=True,
        )

    @app_commands.command(name="상점메세지", description="포인트 상점 임베드 메세지를 보냅니다 (카테고리 선택형)")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        채널="메세지를 보낼 채널", 제목="임베드 제목", 내용="임베드 안내 문구",
        색상="16진수 색상 코드, 생략 가능",
    )
    async def shop_message(self, interaction: discord.Interaction, 채널: discord.TextChannel,
                            제목: str, 내용: str, 색상: str = None):
        categories = await db.get_shop_categories(interaction.guild.id)
        if not categories:
            await interaction.response.send_message(
                "등록된 상점 역할이 없습니다. 먼저 `/상점역할`로 역할을 등록해주세요.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=제목,
            description=내용,
            color=parse_color(색상),
        )

        view = CategoryView(interaction.guild.id, categories)
        self.bot.add_view(view)
        await 채널.send(embed=embed, view=view)
        await interaction.response.send_message("✅ 상점 메세지를 보냈습니다.", ephemeral=True)

    @app_commands.command(name="상점초기화", description="[관리자] 상점에 등록된 모든 역할을 삭제합니다")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reset_shop(self, interaction: discord.Interaction):
        rows = await db.get_shop_roles(interaction.guild.id)
        if not rows:
            await interaction.response.send_message("등록된 상점 역할이 없습니다.", ephemeral=True)
            return
        view = ResetConfirmView(interaction.guild.id)
        await interaction.response.send_message(
            f"⚠️ 등록된 상품 **{len(rows)}개**가 모두 삭제됩니다. 계속할까요?",
            view=view, ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Shop(bot))
