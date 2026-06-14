import json
import time
import uuid

MAX_MESSAGE_SIZE = 8192


def create_message(message_type, payload=None, session_token=None):
    """
    Tworzy standardową wiadomość protokołu SNP.
    """
    return {
        "type": message_type,
        "msg_id": str(uuid.uuid4()),
        "timestamp": int(time.time()),
        "session_token": session_token,
        "payload": payload or {}
    }


def create_error(code, message):
    """
    Tworzy wiadomość błędu.
    """
    return create_message(
        "ERROR",
        {
            "code": code,
            "message": message
        }
    )


def encode_message(message):
    """
    Zamienia słownik Python na JSON bytes.
    Dodajemy znak nowej linii jako separator wiadomości.
    """
    data = json.dumps(message).encode("utf-8") + b"\n"

    if len(data) > MAX_MESSAGE_SIZE:
        raise ValueError("Message too large")

    return data


def decode_message(raw_data):
    """
    Zamienia odebrane bytes na słownik Python.
    """
    if len(raw_data) > MAX_MESSAGE_SIZE:
        raise ValueError("Message too large")

    try:
        return json.loads(raw_data.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format")


def validate_message(message):
    """
    Sprawdza, czy wiadomość ma wymagane pola.
    """
    required_fields = ["type", "msg_id", "timestamp", "payload"]

    if not isinstance(message, dict):
        raise ValueError("Message must be JSON object")

    for field in required_fields:
        if field not in message:
            raise ValueError(f"Missing required field: {field}")

    if not isinstance(message["type"], str):
        raise ValueError("Field 'type' must be string")

    if not isinstance(message["msg_id"], str):
        raise ValueError("Field 'msg_id' must be string")

    if not isinstance(message["timestamp"], int):
        raise ValueError("Field 'timestamp' must be integer")

    if not isinstance(message["payload"], dict):
        raise ValueError("Field 'payload' must be object")

    return True