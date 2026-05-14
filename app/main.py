from notifier import send_discord
from datetime import datetime

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]

now = datetime.now()

weekday = WEEKDAYS[now.weekday()]

message = (
    f"{now.strftime('%Y/%m/%d')}_{weekday}曜日 "
    f"拝島ライナー2号 空き座席: 3A, 3B"
)

send_discord(message)