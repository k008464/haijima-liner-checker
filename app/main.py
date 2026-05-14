from playwright.sync_api import sync_playwright
from datetime import datetime
import os
from notifier import send_discord

LOGIN_URL = "https://www.smooz.jp/Smooz/login.xhtml?refererView=top"

TARGET_TRAINS = [
    "拝島ライナー２号",
    "拝島ライナー４号"
]

WEEKDAYS = [
    "月", "火", "水",
    "木", "金", "土", "日"
]


def jst_now():
    return datetime.now()


def is_after_stop_time(target_date):
    stop_time = datetime.strptime(
        f"{target_date} 08:00",
        "%Y-%m-%d %H:%M"
    )

    return jst_now() >= stop_time


def format_date_value(target_date):
    return target_date.replace("-", "")


def format_message(
    target_date,
    train_name,
    seats
):
    dt = datetime.strptime(
        target_date,
        "%Y-%m-%d"
    )

    weekday = WEEKDAYS[
        dt.weekday()
    ]

    seat_text = ", ".join(seats)

    return (
        f"{dt.strftime('%Y/%m/%d')}"
        f"_{weekday}曜日 "
        f"{train_name} "
        f"空き座席: {seat_text}"
    )


def login(page):
    page.goto(
        LOGIN_URL,
        wait_until="networkidle"
    )

    page.fill(
        "#loginId",
        os.environ["SMOOZ_ID"]
    )

    page.fill(
        "#password",
        os.environ["SMOOZ_PASSWORD"]
    )

    page.click("#submit")

    page.wait_for_url(
        "**/top.xhtml",
        timeout=30000
    )


def search_train(
    page,
    target_date
):
    page.click("#specifyTime")

    page.select_option(
        "#departureDate",
        format_date_value(
            target_date
        )
    )

    page.select_option(
        "#departureHour",
        "04"
    )

    page.select_option(
        "#departureMinute",
        "00"
    )

    page.click("#selectDeparture")

    page.select_option(
        "#departureStation",
        "1807########"
    )

    page.select_option(
        "#arrivalStation",
        "1402########"
    )

    page.click("#searchTrain")

    page.wait_for_url(
        "**/ticket/seat-select.xhtml",
        timeout=30000
    )

    page.wait_for_load_state(
        "networkidle"
    )


def click_purchase_for_train(
    page,
    train_name
):
    if (
        "２号" in train_name
        or
        "2号" in train_name
    ):

        page.locator(
            '[id="0:buyBtn2"]'
        ).click()

    elif (
        "４号" in train_name
        or
        "4号" in train_name
    ):

        page.locator(
            '[id="2:buyBtn2"]'
        ).click()

    else:
        raise Exception(
            f"未知の列車名: "
            f"{train_name}"
        )

    page.wait_for_timeout(3000)


def choose_seat_map(page):

    print(
        "===== 購入後画面 ====="
    )

    print(
        page.locator("body")
        .inner_text()
    )

    page.wait_for_timeout(3000)

    # 1名選択
    one_person = page.locator(
        'input[value="1"]'
    )

    if one_person.count() > 0:
        one_person.first.check(force=True)

    else:
        raise Exception(
            "1名選択inputが見つからない"
        )

    page.wait_for_timeout(2000)

    # シートマップ選択
    if page.get_by_text(
        "シートマップ",
        exact=False
    ).count() > 0:

        page.get_by_text(
            "シートマップ",
            exact=False
        ).click(force=True)

    else:
        raise Exception(
            "シートマップが見つからない"
        )

    page.wait_for_timeout(5000)

    page.wait_for_load_state(
        "networkidle"
    )

def collect_available_seats(
    page
):
    all_seats = []

    for car_no in range(1, 11):

        car_label = (
            f"{car_no}号車"
        )

        if page.get_by_text(
            car_label,
            exact=False
        ).count() == 0:

            continue

        page.get_by_text(
            car_label,
            exact=False
        ).first.click()

        page.wait_for_timeout(
            1000
        )

        seats = page.locator(
            "td.crossSeat:not(.notsale)"
        )

        count = seats.count()

        for i in range(count):

            seat = seats.nth(i)

            seat_id = (
                seat.get_attribute("id")
            )

            text = (
                seat.inner_text()
                .replace("*", "")
                .strip()
            )

            if (
                not seat_id
                or
                not text
            ):
                continue

            car = int(
                seat_id.split("-")[0]
            )

            all_seats.append(
                f"{car}号車{text}"
            )

    return sorted(
        set(all_seats)
    )


def main():
    target_date = os.environ[
        "TARGET_DATE"
    ]

    if not target_date:
        raise Exception(
            "TARGET_DATE 未設定"
        )

    if is_after_stop_time(
        target_date
    ):

        print(
            "8:00を過ぎたため終了"
        )

        return

    with sync_playwright() as p:

        browser = (
            p.chromium.launch(
                headless=True
            )
        )

        page = browser.new_page(
            locale="ja-JP",
            timezone_id="Asia/Tokyo"
        )

        login(page)

        search_train(
            page,
            target_date
        )

        for train_name in (
            TARGET_TRAINS
        ):

            if page.get_by_text(
                train_name
            ).count() == 0:

                print(
                    f"{train_name}: "
                    f"表示なし"
                )

                continue

            click_purchase_for_train(
                page,
                train_name
            )

            choose_seat_map(page)

            seats = (
                collect_available_seats(
                    page
                )
            )

            if seats:

                message = (
                    format_message(
                        target_date,
                        train_name,
                        seats
                    )
                )

                send_discord(
                    message
                )

                print(message)

            else:

                print(
                    f"{train_name}: "
                    f"座席取得なし"
                )

            page.go_back()

            page.wait_for_load_state(
                "networkidle"
            )

        browser.close()


if __name__ == "__main__":
    main()