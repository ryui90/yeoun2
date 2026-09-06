import os
import aiosqlite
from config import DB_PATH, VOICE_POINT_PER_SECOND


async def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                voice_seconds INTEGER NOT NULL DEFAULT 0,
                message_count INTEGER NOT NULL DEFAULT 0,
                points INTEGER NOT NULL DEFAULT 0,
                gacha_points INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        # 기존 DB(가챠포인트 컬럼 없던 버전)를 위한 마이그레이션
        try:
            await conn.execute("ALTER TABLE users ADD COLUMN gacha_points INTEGER NOT NULL DEFAULT 0")
            await conn.commit()
        except Exception:
            pass
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS shop_roles (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                price INTEGER NOT NULL,
                category TEXT NOT NULL DEFAULT '기타',
                PRIMARY KEY (guild_id, role_id)
            )
        """)
        # 기존 DB(카테고리 컬럼 없던 버전)를 위한 마이그레이션
        try:
            await conn.execute("ALTER TABLE shop_roles ADD COLUMN category TEXT NOT NULL DEFAULT '기타'")
            await conn.commit()
        except Exception:
            pass
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reaction_roles (
                message_id INTEGER NOT NULL,
                emoji TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                PRIMARY KEY (message_id, emoji)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER PRIMARY KEY,
                unverified_role INTEGER,
                newface_role INTEGER,
                base_role INTEGER,
                male_role INTEGER,
                female_role INTEGER,
                teen_role INTEGER,
                twenties_role INTEGER,
                thirties_role INTEGER,
                fourties_role INTEGER,
                log_channel INTEGER
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rank_tiers (
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                required_points INTEGER NOT NULL,
                role_id INTEGER,
                PRIMARY KEY (guild_id, name)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS voice_category_rates (
                guild_id INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                points_per_5min INTEGER NOT NULL,
                PRIMARY KEY (guild_id, category_id)
            )
        """)
        await conn.commit()


async def _ensure_user(conn, guild_id, user_id):
    await conn.execute(
        "INSERT OR IGNORE INTO users (guild_id, user_id) VALUES (?, ?)",
        (guild_id, user_id)
    )


async def get_user(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        await _ensure_user(conn, guild_id, user_id)
        await conn.commit()
        cursor = await conn.execute(
            "SELECT * FROM users WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        )
        row = await cursor.fetchone()
        return dict(row)


async def add_voice_time(guild_id, user_id, seconds, rate_per_5min=None):
    """rate_per_5min이 주어지면 그 요율(5분당 포인트)을 사용하고, 없으면 기본 요율을 사용"""
    if seconds <= 0:
        return
    if rate_per_5min is not None:
        point_delta = int(seconds * (rate_per_5min / 300))
    else:
        point_delta = int(seconds * VOICE_POINT_PER_SECOND)
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_user(conn, guild_id, user_id)
        await conn.execute(
            "UPDATE users SET voice_seconds = voice_seconds + ?, points = points + ? "
            "WHERE guild_id=? AND user_id=?",
            (seconds, point_delta, guild_id, user_id)
        )
        await conn.commit()


async def add_message(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_user(conn, guild_id, user_id)
        await conn.execute(
            "UPDATE users SET message_count = message_count + 1, points = points + 1 "
            "WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        )
        await conn.commit()


async def add_points(guild_id, user_id, delta):
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_user(conn, guild_id, user_id)
        await conn.commit()
        cursor = await conn.execute(
            "SELECT points FROM users WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        )
        row = await cursor.fetchone()
        current = row[0] if row else 0
        new_value = max(0, current + delta)
        await conn.execute(
            "UPDATE users SET points=? WHERE guild_id=? AND user_id=?",
            (new_value, guild_id, user_id)
        )
        await conn.commit()


async def add_gacha_points(guild_id, user_id, delta):
    """가챠(도박) 전용 포인트 증감. 0 밑으로는 내려가지 않음"""
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_user(conn, guild_id, user_id)
        await conn.commit()
        cursor = await conn.execute(
            "SELECT gacha_points FROM users WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        )
        row = await cursor.fetchone()
        current = row[0] if row else 0
        new_value = max(0, current + delta)
        await conn.execute(
            "UPDATE users SET gacha_points=? WHERE guild_id=? AND user_id=?",
            (new_value, guild_id, user_id)
        )
        await conn.commit()
        return new_value


async def get_all_users(guild_id):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM users WHERE guild_id=?", (guild_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_voice_rank(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_user(conn, guild_id, user_id)
        await conn.commit()
        cursor = await conn.execute(
            "SELECT user_id FROM users WHERE guild_id=? ORDER BY voice_seconds DESC",
            (guild_id,)
        )
        rows = await cursor.fetchall()
        ids = [r[0] for r in rows]
        rank = ids.index(user_id) + 1 if user_id in ids else len(ids) + 1
        return rank, len(ids)


async def get_chat_rank(guild_id, user_id):
    async with aiosqlite.connect(DB_PATH) as conn:
        await _ensure_user(conn, guild_id, user_id)
        await conn.commit()
        cursor = await conn.execute(
            "SELECT user_id FROM users WHERE guild_id=? ORDER BY message_count DESC",
            (guild_id,)
        )
        rows = await cursor.fetchall()
        ids = [r[0] for r in rows]
        rank = ids.index(user_id) + 1 if user_id in ids else len(ids) + 1
        return rank, len(ids)


async def get_top_voice(guild_id, limit=10):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM users WHERE guild_id=? ORDER BY voice_seconds DESC LIMIT ?",
            (guild_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_top_chat(guild_id, limit=10):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM users WHERE guild_id=? ORDER BY message_count DESC LIMIT ?",
            (guild_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def upsert_shop_role(guild_id, role_id, price, category="기타"):
    category = category.strip() if category and category.strip() else "기타"
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO shop_roles (guild_id, role_id, price, category) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(guild_id, role_id) DO UPDATE SET price=excluded.price, category=excluded.category",
            (guild_id, role_id, price, category)
        )
        await conn.commit()


async def get_shop_roles(guild_id):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM shop_roles WHERE guild_id=?", (guild_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_shop_categories(guild_id):
    """(카테고리명, 개수) 목록을 카테고리명 순으로 반환"""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT category, COUNT(*) FROM shop_roles WHERE guild_id=? GROUP BY category ORDER BY category",
            (guild_id,)
        )
        rows = await cursor.fetchall()
        return [(r[0], r[1]) for r in rows]


async def get_shop_roles_by_category(guild_id, category):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM shop_roles WHERE guild_id=? AND category=? ORDER BY price",
            (guild_id, category)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def delete_all_shop_roles(guild_id):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM shop_roles WHERE guild_id=?", (guild_id,))
        await conn.commit()


async def get_shop_price(guild_id, role_id):
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT price FROM shop_roles WHERE guild_id=? AND role_id=?",
            (guild_id, role_id)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def add_reaction_role(message_id, emoji, role_id, guild_id):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO reaction_roles (message_id, emoji, role_id, guild_id) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(message_id, emoji) DO UPDATE SET role_id=excluded.role_id",
            (message_id, emoji, role_id, guild_id)
        )
        await conn.commit()


async def get_reaction_role(message_id, emoji):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM reaction_roles WHERE message_id=? AND emoji=?",
            (message_id, emoji)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_guild_config(guild_id):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM guild_config WHERE guild_id=?", (guild_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def upsert_guild_config(guild_id, **kwargs):
    current = await get_guild_config(guild_id) or {}
    fields = [
        "unverified_role", "newface_role", "base_role", "male_role", "female_role",
        "teen_role", "twenties_role", "thirties_role", "fourties_role", "log_channel"
    ]
    merged = {}
    for f in fields:
        new_val = kwargs.get(f)
        merged[f] = new_val if new_val is not None else current.get(f)

    async with aiosqlite.connect(DB_PATH) as conn:
        columns = ", ".join(fields)
        placeholders = ", ".join(["?"] * len(fields))
        updates = ", ".join([f"{f}=excluded.{f}" for f in fields])
        await conn.execute(
            f"""INSERT INTO guild_config (guild_id, {columns})
                VALUES (?, {placeholders})
                ON CONFLICT(guild_id) DO UPDATE SET {updates}""",
            [guild_id] + [merged[f] for f in fields]
        )
        await conn.commit()


async def get_top_points(guild_id, limit=10):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM users WHERE guild_id=? ORDER BY points DESC LIMIT ?",
            (guild_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ---------- 랭크 단계 ----------

async def upsert_rank_tier(guild_id, name, required_points, role_id=None):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO rank_tiers (guild_id, name, required_points, role_id) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(guild_id, name) DO UPDATE SET "
            "required_points=excluded.required_points, role_id=excluded.role_id",
            (guild_id, name, required_points, role_id)
        )
        await conn.commit()


async def delete_rank_tier(guild_id, name):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "DELETE FROM rank_tiers WHERE guild_id=? AND name=?", (guild_id, name)
        )
        await conn.commit()


async def get_rank_tiers(guild_id):
    """필요 포인트가 낮은 순으로 정렬된 랭크 목록"""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM rank_tiers WHERE guild_id=? ORDER BY required_points ASC",
            (guild_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ---------- 음성 카테고리별 포인트 요율 ----------

async def upsert_voice_category_rate(guild_id, category_id, points_per_5min):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO voice_category_rates (guild_id, category_id, points_per_5min) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, category_id) DO UPDATE SET points_per_5min=excluded.points_per_5min",
            (guild_id, category_id, points_per_5min)
        )
        await conn.commit()


async def delete_voice_category_rate(guild_id, category_id):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "DELETE FROM voice_category_rates WHERE guild_id=? AND category_id=?",
            (guild_id, category_id)
        )
        await conn.commit()


async def get_voice_category_rate(guild_id, category_id):
    if category_id is None:
        return None
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "SELECT points_per_5min FROM voice_category_rates WHERE guild_id=? AND category_id=?",
            (guild_id, category_id)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_all_voice_category_rates(guild_id):
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM voice_category_rates WHERE guild_id=?", (guild_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
