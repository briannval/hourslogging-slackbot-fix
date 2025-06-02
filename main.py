import base64
import json
import os

import gspread
import requests
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Form
from fastapi.responses import JSONResponse
from google.oauth2.service_account import Credentials

load_dotenv()

app = FastAPI()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

MONTH_COLS = {
    "april": (2, 3),
    "may": (4, 5),
    "june": (6, 7),
    "july": (8, 9),
    "august": (10, 11),
    "september": (12, 13),
    "october": (14, 15),
    "november": (16, 17),
    "december": (18, 19),
    "january": (20, 21),
    "february": (22, 23),
    "march": (24, 25),
}


def process_loghours(name, month, description, hours, response_url):
    try:
        creds_b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
        creds_json = base64.b64decode(creds_b64).decode("utf-8")
        creds_info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        gc = gspread.authorize(creds)

        name_lower = name.lower()
        target_end = f"{name} TOTAL HOURS".lower()
        month = month.lower()

        if month not in MONTH_COLS:
            raise ValueError(
                f"Month '{month}' not recognized. Please use a full month name, e.g. May."
            )

        desc_col_idx, hours_col_idx = MONTH_COLS[month]
        SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
        spreadsheet = gc.open_by_key(SHEET_ID)
        updated = False

        for sheet in spreadsheet.worksheets():
            col_a = sheet.col_values(1)
            start = None
            end = None

            for idx, cell in enumerate(col_a, start=1):
                cell_lower = cell.strip().lower()
                if cell_lower == name_lower:
                    start = idx
                elif cell_lower == target_end:
                    end = idx
                if start and end:
                    break

            if not start or not end:
                continue

            role = sheet.cell(start - 1, 1).value

            for row_idx in range(start, end):
                desc_cell = sheet.cell(row_idx, desc_col_idx).value
                hours_cell = sheet.cell(row_idx, hours_col_idx).value
                if (not desc_cell or desc_cell.strip() == "") and (
                    not hours_cell or hours_cell.strip() == ""
                ):
                    sheet.update_cell(row_idx, desc_col_idx, description)
                    sheet.update_cell(row_idx, hours_col_idx, hours)
                    response_text = (
                        f"Logged hours for {name} in department {sheet.title}, "
                        f"month {month.capitalize()}! You're such an amazing {role}! :dog-roll:"
                    )
                    requests.post(
                        response_url,
                        json={"response_type": "in_channel", "text": response_text},
                    )
                    updated = True
                    break

            if updated:
                break

        if not updated:
            requests.post(
                response_url,
                json={
                    "response_type": "ephemeral",
                    "text": (
                        "Your name wasn't found, or there isn't any available empty row found to log your hours. :blob-salute:"
                    ),
                },
            )

    except Exception as e:
        requests.post(
            response_url,
            json={"response_type": "ephemeral", "text": f"Error: {str(e)}"},
        )


@app.post("/loghours")
async def log_hours(
    background_tasks: BackgroundTasks,
    text: str = Form(...),
    response_url: str = Form(...),
):
    parts = [p.strip() for p in text.split(";", 3)]
    if len(parts) != 4:
        return JSONResponse(
            {
                "response_type": "ephemeral",
                "text": (
                    "Whoops, not quite! :blob-salute:\n"
                    "Follow this -> */loghours <name>;<month>;<description>;<hours>*\n"
                    "Here's an example! -> */loghours Brian Adhitya;May;1-Went to GM!;2*"
                ),
            }
        )

    name, month, description, hours = parts
    background_tasks.add_task(
        process_loghours, name, month, description, hours, response_url
    )

    return JSONResponse(
        {
            "response_type": "in_channel",
            "text": "Logging your hours... hang on!!! :dog-roll:",
        }
    )
