import socket
import ssl
import secrets
import sys
import os
import signal
import threading
import logging
import time

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
    get_username_by_token,
    delete_session
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("server.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

HOST = "127.0.0.1"
PORT = 8443

CERT_FILE = "certs/server.crt"
KEY_FILE = "certs/server.key"

# Konfiguracja rate limitingu
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW = 60

failed_attempts = {}
rate_limit_lock = threading.Lock()


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
        send_response(conn, create_error(100, "Wymagana nazwa użytkownika i hasło"))
        return

    if create_user(username, password):
        send_response(conn, create_message("REGISTER_ACK", {"message": "Użytkownik utworzony"}))
    else:
        send_response(conn, create_error(100, "Nazwa użytkownika jest już zajęta"))


def handle_auth(conn, payload, addr):
    username = payload.get("username")
    password = payload.get("password")
    ip_address = addr[0]
    current_time = time.time()

    with rate_limit_lock:
        if ip_address in failed_attempts:
            record = failed_attempts[ip_address]
            time_since_last = current_time - record["last_attempt"]

            if time_since_last < LOCKOUT_WINDOW:
                if record["attempts"] >= MAX_FAILED_ATTEMPTS:
                    logging.warning(f"Przekroczono limit prób logowania dla IP {ip_address}.")
                    send_response(conn, create_error(104, "Zbyt wiele nieudanych prób. Spróbuj ponownie później."))
                    return
            else:
                del failed_attempts[ip_address]

    if not username or not password:
        send_response(conn, create_error(100, "Wymagana nazwa użytkownika i hasło"))
        return

    if verify_user(username, password):
        token = secrets.token_hex(32)
        create_session(username, token)

        logging.info(f"Użytkownik '{username}' zalogował się pomyślnie (IP: {ip_address})")

        with rate_limit_lock:
            if ip_address in failed_attempts:
                del failed_attempts[ip_address]

        send_response(conn, create_message(
            "AUTH_ACK",
            {"message": "Uwierzytelnienie zakończone sukcesem", "session_token": token}
        ))
    else:
        logging.warning(f"Nieudana próba logowania dla użytkownika '{username}' (IP: {ip_address})")

        with rate_limit_lock:
            if ip_address not in failed_attempts:
                failed_attempts[ip_address] = {"attempts": 1, "last_attempt": current_time}
            else:
                failed_attempts[ip_address]["attempts"] += 1
                failed_attempts[ip_address]["last_attempt"] = current_time

        send_response(conn, create_error(102, "Błędna nazwa użytkownika lub hasło"))


def handle_add_note(conn, message):
    token = message.get("session_token")
    username = get_username_from_token(token)

    if not username:
        logging.warning("Nieautoryzowane żądanie ADD_NOTE (brak lub nieprawidłowy token)")
        send_response(conn, create_error(103, "Brak autoryzacji"))
        return

    payload = message["payload"]
    title = payload.get("title")
    content = payload.get("content")

    if not title or not content:
        send_response(conn, create_error(100, "Tytuł i treść są wymagane"))
        return

    if len(title) > 100 or len(content) > 2000:
        send_response(conn, create_error(100, "Notatka jest zbyt długa"))
        return

    note_id = add_note(username, title, content)

    send_response(conn, create_message(
        "SUCCESS",
        {
            "message": "Notatka dodana",
            "note_id": note_id
        }
    ))


def handle_list_notes(conn, message):
    token = message.get("session_token")
    username = get_username_from_token(token)

    if not username:
        logging.warning("Nieautoryzowane żądanie LIST_NOTES (brak lub nieprawidłowy token)")
        send_response(conn, create_error(103, "Brak autoryzacji"))
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
        logging.warning("Nieautoryzowane żądanie DELETE_NOTE (brak lub nieprawidłowy token)")
        send_response(conn, create_error(103, "Brak autoryzacji"))
        return

    note_id = message["payload"].get("note_id")

    if not note_id:
        send_response(conn, create_error(100, "Pole note_id jest wymagane"))
        return

    try:
        note_id = int(note_id)
    except ValueError:
        send_response(conn, create_error(100, "Pole note_id musi być liczbą całkowitą"))
        return

    if delete_note(username, note_id):
        send_response(conn, create_message("SUCCESS", {"message": "Notatka usunięta"}))
    else:
        send_response(conn, create_error(107, "Notatka nie została znaleziona"))


def handle_client(conn, addr):
    logging.info(f"Nowe połączenie: {addr}")

    conn.settimeout(60.0)

    try:
        with conn:
            buffer = b""

            while True:
                data = conn.recv(4096)

                if not data:
                    logging.info(f"Rozłączono: {addr}")
                    break

                buffer += data

                while b"\n" in buffer:
                    raw_message, buffer = buffer.split(b"\n", 1)

                    try:
                        message = decode_message(raw_message)
                        validate_message(message)

                        message_type = message["type"]

                        logging.info(f"Odebrano {message_type} od {addr}")

                        if message_type == "HELLO":
                            handle_hello(conn)

                        elif message_type == "REGISTER":
                            handle_register(conn, message["payload"])

                        elif message_type == "AUTH":
                            handle_auth(conn, message["payload"], addr)

                        elif message_type == "ADD_NOTE":
                            handle_add_note(conn, message)

                        elif message_type == "LIST_NOTES":
                            handle_list_notes(conn, message)

                        elif message_type == "DELETE_NOTE":
                            handle_delete_note(conn, message)

                        elif message_type == "PING":
                            logging.debug(f"Otrzymano sygnał Keep-Alive od {addr}")

                        elif message_type == "BYE":
                            token = message.get("session_token")
                            if token:
                                delete_session(token)
                                logging.info("Usunięto token sesji użytkownika (wylogowanie).")
                            send_response(conn, create_message("BYE_ACK", {"message": "Do widzenia"}))
                            return

                        else:
                            send_response(conn, create_error(101, "Nieznany typ wiadomości"))

                    except ValueError as e:
                        logging.warning(f"Nieprawidłowy format wiadomości od {addr}: {e}")
                        send_response(conn, create_error(100, str(e)))

    except socket.timeout:
        logging.warning(f"Przekroczono limit czasu połączenia dla {addr} (brak aktywności przez 60s).")
    except Exception as e:
        logging.error(f"Błąd klienta {addr}: {e}")


def start_server():
    init_db()
    create_default_user()

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)

    logging.info(f"Serwer Secure Notes uruchomiony na {HOST}:{PORT}")

    def shutdown_handler(signum, frame):
        logging.info(f"Otrzymano sygnał systemowy ({signum}). Rozpoczynam bezpieczne zamknięcie...")
        server_socket.close()
        logging.info("Gniazdo główne zamknięte. Serwer zakończył działanie.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        while True:
            client_socket, addr = server_socket.accept()
            tls_conn = context.wrap_socket(client_socket, server_side=True)

            client_thread = threading.Thread(target=handle_client, args=(tls_conn, addr))
            client_thread.start()

    except OSError:
        pass
    except Exception as e:
        logging.critical(f"Niespodziewany wyjątek w pętli głównej: {e}")
    finally:
        server_socket.close()


if __name__ == "__main__":
    start_server()
