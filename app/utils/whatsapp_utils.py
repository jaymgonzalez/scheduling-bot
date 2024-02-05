import logging
from flask import current_app, jsonify
import json
import requests
import shelve
import re

from app.services.openai_service import get_calendar_text


def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )


def get_initial_template(recipient, name):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "template",
            "template": {
                "name": "welcome_message_scheduling",
                "language": {
                    "code": "en",
                },
                "components": [
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "text",
                                "text": name,
                            },
                        ],
                    },
                ],
            },
        }
    )


def store_routines(wa_id, routines):
    with shelve.open("routines_db", writeback=True) as routines_shelf:
        routines_shelf[wa_id] = routines


def get_daily_schedule(recipient):
    get_calendar = requests.get(
        "https://n8n.magnetaigency.com/webhook/get_calendar_data"
    )

    print(get_calendar.json())

    return get_calendar.json()

    # get_text_message_input(recipient, get_calendar.json())


def check_if_routine_exists(wa_id):
    with shelve.open("routines_db") as routines_shelf:
        return routines_shelf.get(wa_id, None)


def check_add_routine_format(s):
    pattern = r"add routine [a-zA-Z0-9]+ : [a-zA-Z0-9]+ : [a-zA-Z0-9]+"
    return bool(re.search(pattern, s))


def buttonReply_Message(number, options, body, footer, header, sedd, messageId):
    buttons = []
    for i, option in enumerate(options):
        buttons.append(
            {
                "type": "reply",
                "reply": {"id": sedd + "_btn_" + str(i + 1), "title": option},
            }
        )

    data = json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "header": {"type": "text", "text": header},
                "body": {"text": body},
                "footer": {"text": footer},
                "action": {"buttons": buttons},
            },
        }
    )
    return data


def replyReaction_Message(number, messageId, emoji):
    data = json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": number,
            "type": "reaction",
            "reaction": {"message_id": messageId, "emoji": emoji},
        }
    )
    return data


def listReply_Message(number, options, body, footer, sedd, messageId):
    rows = []
    for i, option in enumerate(options):
        rows.append(
            {"id": sedd + "_row_" + str(i + 1), "title": option, "description": ""}
        )

    data = json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": number,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body},
                "footer": {"text": footer},
                "action": {
                    "button": "Ver Opciones",
                    "sections": [{"title": "Secciones", "rows": rows}],
                },
            },
        }
    )
    return data


def generate_response(response, wa_id, name):
    if response.lower() == "hello":
        # return get_initial_template(wa_id, name)
        body = "Happy to help you today 😊 \n\nPlease click in the buttons below to select your action. \n\n*⚡ Schedule Your Day* ➡️ To generate a new schedule for today \n\n*📅 Update Routines* ➡️ To update the routines you provided in the past"
        footer = "AI Scheduler"
        options = ["⚡ Schedule Your Day", "📅 Update Routines"]
        header = f"Welcome to AI Scheduler {name}"

        return buttonReply_Message(wa_id, options, body, footer, header, "seed", "1")

    if response.lower() == "⚡ schedule your day":
        routines = check_if_routine_exists(wa_id)
        if routines is None:
            body = "Tenemos varias áreas de consulta para elegir. ¿Cuál de estos servicios te gustaría explorar?"
            footer = "Equipo Bigdateros"
            header = f"{name}"
            options = [
                "Analítica Avanzada",
                "Migración Cloud",
                "Inteligencia de Negocio",
            ]

            listReplyData = listReply_Message(wa_id, options, body, footer, "sed2", "1")

            return listReplyData
        else:  # Routines exist

            schedule = get_daily_schedule(wa_id)

            formated_schedule = get_calendar_text(schedule)

            body = f"This is your calendar for today \n\n```{formated_schedule}``` \n\n And here are your routines: \n\n```{check_if_routine_exists(wa_id)}```"
            footer = "AI Scheduler"
            options = ["⚡ Schedule Your Day", "📅 Update Routines"]
            header = f"{name}"

            return buttonReply_Message(
                wa_id, options, body, footer, header, "seed", "2"
            )
        # body = "test"
        # footer = "AI Scheduler"
        # options = ["Add To Google Calendar", "📅 agendar cita"]
        # header = f"{name}"

        # return buttonReply_Message(wa_id, options, body, footer, header, "seed", "1")

        # print(schedule)
        # print(get_text_message_input(wa_id, schedule))
        # return schedule
    if response.lower() == "check routines":
        return get_text_message_input(
            wa_id,
            f"These are your routines: \n{routines} \n to update a routine, type 'update routine'",
        )
    if response.lower() == "add routine":
        return get_text_message_input(
            wa_id,
            "Please enter the routine you would like to add in the format: \nDesired Time: Activity : Duration\n\nExample: 6:00 AM: Breakfast : 1 hour",
        )

    else:
        return get_text_message_input(
            wa_id,
            "Here is the list of all commands to use in this bot:\n1. Create daily schedule\n2. Check routines\n3. Add routine\n4. Update routine\n Use any of these commands to interact with the bot.",
        )

    # Return text in uppercase
    return response.upper()


def send_message(data):
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Bearer {current_app.config['ACCESS_TOKEN']}",
    }

    url = f"https://graph.facebook.com/{current_app.config['VERSION']}/{current_app.config['PHONE_NUMBER_ID']}/messages"

    try:
        response = requests.post(
            url, data=data, headers=headers, timeout=10
        )  # 10 seconds timeout as an example
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.Timeout:
        logging.error("Timeout occurred while sending message")
        return jsonify({"status": "error", "message": "Request timed out"}), 408
    except (
        requests.RequestException
    ) as e:  # This will catch any general request exception
        logging.error(f"Request failed due to: {e}")
        return jsonify({"status": "error", "message": "Failed to send message"}), 500
    else:
        # Process the response as normal
        log_http_response(response)
        return response


def process_text_for_whatsapp(text):
    # Remove brackets
    pattern = r"\【.*?\】"
    # Substitute the pattern with an empty string
    text = re.sub(pattern, "", text).strip()

    # Pattern to find double asterisks including the word(s) in between
    pattern = r"\*\*(.*?)\*\*"

    # Replacement pattern with single asterisks
    replacement = r"*\1*"

    # Substitute occurrences of the pattern with the replacement
    whatsapp_style_text = re.sub(pattern, replacement, text)

    return whatsapp_style_text


def get_whatsapp_message(message):
    if "type" not in message:
        text = "mensaje not recognized"
        return text

    type_message = message["type"]
    if type_message == "text":
        text = message["text"]["body"]
    elif type_message == "button":
        text = message["button"]["text"]
    elif (
        type_message == "interactive" and message["interactive"]["type"] == "list_reply"
    ):
        text = message["interactive"]["list_reply"]["title"]
    elif (
        type_message == "interactive"
        and message["interactive"]["type"] == "button_reply"
    ):
        text = message["interactive"]["button_reply"]["title"]
    else:
        text = "message not processed"

    return text


def process_whatsapp_message(body):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]

    # print(wa_id, name)

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    print(f"message = {message}")

    message_body = get_whatsapp_message(message)

    # TODO: implement custom function here
    response = generate_response(message_body, wa_id, name)

    # OpenAI Integration
    # response = generate_response(message_body, wa_id, name)
    # response = process_text_for_whatsapp(response)

    # Send the parsed response
    # data = get_text_message_input(current_app.config["RECIPIENT_WAID"], response)
    # send_message(data)

    send_message(response)


def is_valid_whatsapp_message(body):
    """
    Check if the incoming webhook event has a valid WhatsApp message structure.
    """
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )
