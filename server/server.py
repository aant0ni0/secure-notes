import socket
import ssl
import secrets
import sys
import os
import signal
import threading

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from protocol import (
    create_message,
    create_error,
    encode_message,
    decode_message,
    validate_message
)

from database import (
    init_db,
    create_default_user,
    create_user,
    verify_user,
    add_note,
    list_notes,
    delete_note,
    create_session,
    get_username_by_token
)


HOST = "127.0.0.1"
PORT = 8443

CERT_FILE = "certs/server.crt"
KEY_FILE = "certs/server.key"


def send_response(conn, message):
    conn.sendall(encode_message(message))


def get_username_from_token(token):
    if not token:
        return None
    return get_username_by_token(token)


def handle_hello(conn):
    send_response(conn, create_message(
        "HELLO_ACK",
        {"server": "Secure Notes Server", "version": "1.0"}
    ))


def handle_register(conn, payload):
    username = payload.get("username")
    password = payload.get("password")

    if not username or not password:
        send_response(conn, create_error(100, "Username and password are required"))
        return

    if create_user(username, password):
        send_response(conn, create_message("REGISTER_ACK", {"message": "User created"}))
    else:
        send_response(conn, create_error(100, "Username already exists"))


def handle_auth(conn, payload):
    username = payload.get("username")
    password = payload.get("password")

    if not username or not password:
        send_response(conn, create_error(100, "Username and password are required"))
        return

    if verify_user(username, password):
        token = secrets.token_hex(32)

        create_session(username, token)

        send_response(conn, create_message(
            "AUTH_ACK",
            {
                "message": "Authentication successful",
                "session_token": token
            }
        ))
    else:
        send_response(conn, create_error(102, "Authentication failed"))


def handle_add_note(conn, message):
    token = message.get("session_token")
    username = get_username_from_token(token)

    if not username:
        send_response(conn, create_error(103, "Authorization failed"))
        return

    payload = message["payload"]
    title = payload.get("title")
    content = payload.get("content")

    if not title or not content:
        send_response(conn, create_error(100, "Title and content are required"))
        return

    if len(title) > 100 or len(content) > 2000:
        send_response(conn, create_error(100, "Note is too long"))
        return

    note_id = add_note(username, title, content)

    send_response(conn, create_message(
        "SUCCESS",
        {
            "message": "Note added",
            "note_id": note_id
        }
    ))


def handle_list_notes(conn, message):
    token = message.get("session_token")
    username = get_username_from_token(token)

    if not username:
        send_response(conn, create_error(103, "Authorization failed"))
        return

    notes = list_notes(username)

    send_response(conn, create_message(
        "SUCCESS",
        {
            "notes": notes
        }
    ))


def handle_delete_note(conn, message):
    token = message.get("session_token")
    username = get_username_from_token(token)

    if not username:
        send_response(conn, create_error(103, "Authorization failed"))
        return

    note_id = message["payload"].get("note_id")

    if not note_id:
        send_response(conn, create_error(100, "note_id is required"))
        return

    try:
        note_id = int(note_id)
    except ValueError:
        send_response(conn, create_error(100, "note_id must be integer"))
        return

    if delete_note(username, note_id):
        send_response(conn, create_message("SUCCESS", {"message": "Note deleted"}))
    else:
        send_response(conn, create_error(107, "Note not found"))


def handle_client(conn, addr):
    print(f"[INFO] Connected: {addr}")

    try:
        with conn:
            buffer = b""

            while True:
                data = conn.recv(4096)

                if not data:
                    print(f"[INFO] Disconnected: {addr}")
                    break

                buffer += data

                while b"\n" in buffer:
                    raw_message, buffer = buffer.split(b"\n", 1)

                    try:
                        message = decode_message(raw_message)
                        validate_message(message)

                        message_type = message["type"]

                        print(f"[RECV] {message_type} from {addr}")

                        if message_type == "HELLO":
                            handle_hello(conn)

                        elif message_type == "REGISTER":
                            handle_register(conn, message["payload"])

                        elif message_type == "AUTH":
                            handle_auth(conn, message["payload"])

                        elif message_type == "ADD_NOTE":
                            handle_add_note(conn, message)

                        elif message_type == "LIST_NOTES":
                            handle_list_notes(conn, message)

                        elif message_type == "DELETE_NOTE":
                            handle_delete_note(conn, message)

                        elif message_type == "BYE":
                            send_response(conn, create_message("BYE_ACK", {"message": "Goodbye"}))
                            return

                        else:
                            send_response(conn, create_error(101, "Unknown message type"))

                    except ValueError as e:
                        send_response(conn, create_error(100, str(e)))

    except Exception as e:
        print(f"[ERROR] Client error {addr}: {e}")


def start_server():
    init_db()
    create_default_user()

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server_socket.bind((HOST, PORT))
    server_socket.listen(5)

    print(f"[INFO] Secure Notes Server running on {HOST}:{PORT}")

    def shutdown_handler(signum, frame):
        print(f"\n[INFO] Otrzymano sygnał systemowy ({signum}). Rozpoczynam Graceful Shutdown...")
        server_socket.close()
        print("[INFO] Gniazdo główne zamknięte. Proces serwera zakończony bezpiecznie.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        while True:

            client_socket, addr = server_socket.accept()
            tls_conn = context.wrap_socket(client_socket, server_side=True)

            client_thread = threading.Thread(target=handle_client, args=(tls_conn, addr))
            client_thread.start()

    except OSError as e:
        pass
    except Exception as e:
        print(f"[KRYTYCZNY BŁĄD SERWERA] Niespodziewany wyjątek w pętli głównej: {e}")
    finally:
        server_socket.close()


if __name__ == "__main__":
    start_server()