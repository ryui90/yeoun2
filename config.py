import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DB_PATH = os.getenv("DB_PATH", "bot_data.db")

COLOR_MAIN = 0x71aeff
COLOR_SUB = 0xcf98ff
GRADIENT_START = (113, 174, 255)  # 연초록 RGB
GRADIENT_END = (207, 152, 255)     # 노랑 RGB

# 프로필 카드용 폰트 (한글 지원 폰트 필요 - README 참고)
FONT_BOLD_PATH = "assets/fonts/NotoSansKR-Bold.ttf"
FONT_REGULAR_PATH = "assets/fonts/NotoSansKR-Regular.ttf"

# 포인트 환산: 음성 5분(300초)당 100포인트, 채팅 1회당 1포인트
VOICE_POINT_PER_SECOND = 100 / 300
CHAT_POINT_PER_MESSAGE = 1

# 도박 게임 배팅 상한
GAMBLING_MAX_BET = 1000       # 야바위/홀짝/동전던지기/OX/가위바위보 최대 배팅
WHEEL_MAX_BET = 10000         # 돌림판 최대 배팅
GAMBLING_POOL_MAX_BET = 5000  # 몰아주기 참여 최대 배팅

# 포인트 <-> 가챠포인트 전환 비율
POINT_TO_GACHA_UNIT = 10      # 이 단위(포인트)로만 전환 가능
POINT_TO_GACHA_RATE = 100     # 10 포인트 -> 100 가챠포인트
GACHA_TO_POINT_UNIT = 100     # 이 단위(가챠포인트)로만 전환 가능
GACHA_TO_POINT_RATE = 10      # 100 가챠포인트 -> 10 포인트
