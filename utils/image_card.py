import io
import discord
from PIL import Image, ImageDraw, ImageFont
from config import FONT_BOLD_PATH, FONT_REGULAR_PATH, GRADIENT_START, GRADIENT_END


def _load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _gradient(size, start, end):
    w, h = size
    base = Image.new("RGB", size, start)
    top = Image.new("RGB", size, end)
    mask = Image.new("L", size)
    mask_data = []
    for y in range(h):
        mask_data.extend([int(255 * (y / h))] * w)
    mask.putdata(mask_data)
    base.paste(top, (0, 0), mask)
    return base


def _rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (size[0] - 1, size[1] - 1)], radius=radius, fill=255)
    return mask


async def create_stat_card(member: discord.Member, label: str, value_text: str, rank_text: str) -> discord.File:
    W, H = 900, 300

    base = _gradient((W, H), GRADIENT_START, GRADIENT_END).convert("RGBA")
    mask = _rounded_mask((W, H), 40)
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    card.paste(base, (0, 0), mask)

    draw = ImageDraw.Draw(card)

    panel_margin = 18
    draw.rounded_rectangle(
        [(panel_margin, panel_margin), (W - panel_margin, H - panel_margin)],
        radius=30, fill=(255, 255, 255, 235)
    )

    # 아바타
    asset = member.display_avatar.replace(size=256)
    avatar_bytes = await asset.read()
    avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((180, 180))
    avatar_mask = Image.new("L", (180, 180), 0)
    ImageDraw.Draw(avatar_mask).ellipse((0, 0, 180, 180), fill=255)

    avatar_pos = (55, 60)
    ring_pos = (avatar_pos[0] - 6, avatar_pos[1] - 6)
    ring = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((0, 0, 192, 192), fill=(255, 217, 61, 255))
    card.paste(ring, ring_pos, ring)
    card.paste(avatar_img, avatar_pos, avatar_mask)

    # 텍스트
    font_name = _load_font(FONT_BOLD_PATH, 42)
    font_label = _load_font(FONT_REGULAR_PATH, 26)
    font_value = _load_font(FONT_BOLD_PATH, 54)
    font_rank = _load_font(FONT_REGULAR_PATH, 22)

    text_x = 270
    draw.text((text_x, 62), member.display_name, font=font_name, fill=(45, 45, 45))
    draw.text((text_x, 122), label, font=font_label, fill=(110, 110, 110))
    draw.text((text_x, 155), value_text, font=font_value, fill=(50, 50, 50))
    draw.text((text_x, 232), rank_text, font=font_rank, fill=(130, 130, 130))

    buf = io.BytesIO()
    card.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename="stat_card.png")
