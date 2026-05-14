from playwright.sync_api import sync_playwright
from datetime import datetime
import os
import re
from notifier import send_discord

LOGIN_URL = "https://www.smooz.jp/Smooz/login.xhtml?refererView=top"

TARGET_TRAINS = ["拝島ライナー２号", "拝島ライナー４号"]
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]


def jst_now():
    return datetime.now()


def is_after_stop_time(target_date):
    stop_time = datetime.strptime(f"{target_date} 08:00", "%Y-%m-%d %H:%M")
    return jst_now() >= stop_time


def format_date_value(target_date):
    return target_date.replace("-", "")


def normalize_train_name(name):
    return name.replace("2", "２").replace("4", "４")


def format_message(target_date, train_name, seats):
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    weekday = WEEKDAYS[dt.weekday()]
    seat_text = ", ".join(seats)

    return f"{dt.strftime('%Y/%m/%d')}_{weekday}曜日 {train_name} 空き座席: {seat_text}"


def login(page):
    page.goto(LOGIN_URL, wait_until="networkidle")

    page.fill("#loginId", os.environ["SMOOZ_ID"])
    page.fill("#password", os.environ["SMOOZ_PASSWORD"])
    page.click("#submit")

    page.wait_for_url("**/top.xhtml", timeout=30000)


def search_train(page, target_date):
    page.click("#specifyTime")

    page.select_option("#departureDate", format_date_value(target_date))
    page.select_option("#departureHour", "04")
    page.select_option("#departureMinute", "00")

    page.click("#selectDeparture")

    page.select_option("#departureStation", "1807########")
    page.select_option("#arrivalStation", "1402########")

    page.click("#searchTrain")

    page.wait_for_url("**/ticket/seat-select.xhtml", timeout=30000)
    page.wait_for_load_state("networkidle")


def train_has_available(page, train_name):
    train_area = page.locator("body").filter(has_text=train_name)
    return page.get_by_text(train_name).count() > 0 and page.get_by_text("空席あり").count() > 0


def click_purchase_for_train(page, train_name):
    # 対象列車名を含む行の近くにある「購入」を押す
    xpath = (
        f"//*[contains(normalize-space(), '{train_name}')]"
        f"/ancestor::*[self::tr or self::div][1]"
        f"//following::*[@value='購入' or normalize-space()='購入'][1]"
    )

    page.locator(f"xpath={xpath}").click()
    page.wait_for_load_state("networkidle")


def choose_seat_map(page):
    # 大人1名
    page.get_by_text("1名", exact=True).first.click()

    # シートマップから選択
    page.get_by_text("シートマップ", exact=False).click()

    page.wait_for_load_state("networkidle")


def collect_available_seats(page):
    all_seats = []

    # 1〜10号車を順番に見る
    for car_no in range(1, 11):
        car_label = f"{car_no}号車"

        if page.get_by_text(car_label, exact=False).count() == 0:
            continue

        page.get_by_text(car_label, exact=False).first.click()
        page.wait_for_timeout(800)

        seats = page.locator("td.crossSeat:not(.notsale)")
        count = seats.count()

        for i in range(count):
            seat = seats.nth(i)
            seat_id = seat.get_attribute("id")
            text = seat.inner_text().replace("*", "").strip()

            if not seat_id or not text:
                continue

            # 例: 08-07D → 8号車7D
            car = int(seat_id.split("-")[0])
            all_seats.append(f"{car}号車{text}")

    return sorted(set(all_seats))


def main():
    target_date = os.environ["TARGET_DATE"]

    if is_after_stop_time(target_date):
        print("8:00を過ぎたため終了")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="ja-JP", timezone_id="Asia/Tokyo")

        login(page)
        search_train(page, target_date)

        for train_name in TARGET_TRAINS:
            if page.get_by_text(train_name).count() == 0:
                print(f"{train_name}: 表示なし")
                continue

            if page.get_by_text("空席あり").count() == 0:
                print(f"{train_name}: 空席なし")
                continue

            click_purchase_for_train(page, train_name)
            choose_seat_map(page)

            seats = collect_available_seats(page)

            if seats:
                message = format_message(target_date, train_name, seats)
                send_discord(message)
                print(message)
            else:
                print(f"{train_name}: 座席番号取得なし")

            page.go_back()
            page.wait_for_load_state("networkidle")

        browser.close()


if __name__ == "__main__":
    main()