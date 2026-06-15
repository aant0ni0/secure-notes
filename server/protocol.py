import json
import time
import uuid

MAX_MESSAGE_SIZE = 8192


def create_message(message_type, payload=None, session_token=None):
    """Tworzy standardową wiadomość protokołu SNP."""
    return {
        "type": message_type,
        "msg_id": str(uuid.uuid4()),
        "timestamp": int(time.time()),
        "session_token": session_token,
        "payload": payload or {}
    }


def create_error(code, message):
    """Tworzy wiadomość błędu protokołu SNP."""
    return create_message(
        "ERROR",
        {
            "code": code,
            "message": message
        }
    )


def encode_message(message):
    """Serializuje wiadomość do JSON i dodaje znak nowej linii jako separator."""
    data = json.dumps(message).encode("utf-8") + b"\n"

    if len(data) > MAX_MESSAGE_SIZE:
        raise ValueError("Wiadomość jest zbyt duża")

    return data


def decode_message(raw_data):
    """Deserializuje odebrane bajty do słownika Python."""
    if len(raw_data) > MAX_MESSAGE_SIZE:
        raise ValueError("Wiadomość jest zbyt duża")

    try:
        return json.loads(raw_data.decode("utf-8"))
    except json.JSONDecodeError:
        raise ValueError("Nieprawidłowy format JSON")


def validate_message(message):
    """Sprawdza czy wiadomość zawiera wszystkie wymagane pola protokołu SNP."""
    required_fields = ["type", "msg_id", "timestamp", "payload"]

    if not isinstance(message, dict):
        raise ValueError("Wiadomość musi być obiektem JSON")

    for field in required_fields:
        if field not in message:
            raise ValueError(f"Brakujące pole: {field}")

    if not isinstance(message["type"], str):
        raise ValueError("Pole 'type' musi być ciągiem znaków")

    if not isinstance(message["msg_id"], str):
        raise ValueError("Pole 'msg_id' musi być ciągiem znaków")

    if not isinstance(message["timestamp"], int):
        raise ValueError("Pole 'timestamp' musi być liczbą całkowitą")

    if not isinstance(message["payload"], dict):
        raise ValueError("Pole 'payload' musi być obiektem")

    return True
