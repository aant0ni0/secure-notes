import socket
import ssl
import sys
import os
import time
import threading

sys.path.append(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "server")
    )
)

from protocol import create_message, encode_message, decode_message


HOST = "127.0.0.1"
PORT = 8443


def receive_message(conn):
    data = b""
    try:
        while not data.endswith(b"\n"):
            chunk = conn.recv(4096)

            if not chunk:
                raise ConnectionError("Serwer zamknął połączenie.")

            data += chunk

        return decode_message(data.strip())
    except (ssl.SSLError, ConnectionError, OSError) as e:
        raise ConnectionError(f"Utracono połączenie podczas odbierania danych: {e}")


def send_message(conn, message):
    try:
        conn.sendall(encode_message(message))
        return receive_message(conn)
    except (ssl.SSLError, ConnectionError, OSError) as e:
        raise ConnectionError(f"Utracono potok wysyłania: {e}")


def print_response(response):
    if not response:
        print("Brak odpowiedzi serwera.")
        return

    msg_type = response.get("type")
    payload = response.get("payload", {})

    if msg_type == "ERROR":
        print(f"BŁĄD {payload.get('code')}: {payload.get('message')}")
    else:
        print("ODPOWIEDŹ:", response)


def main():
    session_token = None

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    while True:
        try:
            with socket.create_connection((HOST, PORT)) as sock:
                with context.wrap_socket(sock, server_hostname="localhost") as conn:
                    print("\n[INFO] Connected to Secure Notes Server")

                    def heartbeat_task(connection):
                        while True:
                            time.sleep(45)
                            try:
                                ping_msg = create_message("PING")
                                connection.sendall(encode_message(ping_msg))
                            except Exception:
                                break

                    heartbeat_thread = threading.Thread(target=heartbeat_task, args=(conn,), daemon=True)
                    heartbeat_thread.start()

                    response = send_message(conn, create_message("HELLO", {"client_version": "1.0"}))
                    print_response(response)

                    # --- WEWNĘTRZNA PĘTLA LOGIKI (MENU) ---
                    while True:
                        print("\n=== SECURE NOTES ===")
                        print("1. Register")
                        print("2. Login")
                        print("3. Add note")
                        print("4. List notes")
                        print("5. Delete note")
                        print("6. Exit")

                        choice = input("Choose option: ")

                        # POPRAWA: Wszystkie poniższe warunki muszą być przesunięte w prawo,
                        # aby znajdowały się wewnątrz pętli while.
                        if choice == "1":
                            username = input("Username: ")
                            password = input("Password: ")

                            response = send_message(conn, create_message(
                                "REGISTER",
                                {
                                    "username": username,
                                    "password": password
                                }
                            ))
                            print_response(response)

                        elif choice == "2":
                            username = input("Username: ")
                            password = input("Password: ")

                            response = send_message(conn, create_message(
                                "AUTH",
                                {
                                    "username": username,
                                    "password": password
                                }
                            ))

                            if response and response.get("type") == "AUTH_ACK":
                                session_token = response["payload"]["session_token"]
                                print("Zalogowano poprawnie.")
                            else:
                                print_response(response)

                        elif choice == "3":
                            if not session_token:
                                print("Najpierw się zaloguj.")
                                continue

                            title = input("Title: ")
                            content = input("Content: ")

                            response = send_message(conn, create_message(
                                "ADD_NOTE",
                                {
                                    "title": title,
                                    "content": content
                                },
                                session_token=session_token
                            ))
                            print_response(response)

                        elif choice == "4":
                            if not session_token:
                                print("Najpierw się zaloguj.")
                                continue

                            response = send_message(conn, create_message(
                                "LIST_NOTES",
                                {},
                                session_token=session_token
                            ))

                            if response and response.get("type") == "SUCCESS":
                                notes = response["payload"].get("notes", [])

                                if not notes:
                                    print("Brak notatek.")
                                else:
                                    print("\nTwoje notatki:")
                                    for note in notes:
                                        print(f"\nID: {note['id']}")
                                        print(f"Tytuł: {note['title']}")
                                        print(f"Treść: {note['content']}")
                                        print(f"Data: {note['created_at']}")
                            else:
                                print_response(response)

                        elif choice == "5":
                            if not session_token:
                                print("Najpierw się zaloguj.")
                                continue

                            note_id = input("Note ID to delete: ")

                            response = send_message(conn, create_message(
                                "DELETE_NOTE",
                                {
                                    "note_id": note_id
                                },
                                session_token=session_token
                            ))
                            print_response(response)

                        elif choice == "6":
                            response = send_message(conn, create_message(
                                "BYE",
                                session_token=session_token
                            ))
                            print_response(response)
                            print("Koniec.")
                            return

                        else:
                            print("Nieznana opcja.")

        except (ConnectionError, ConnectionRefusedError) as e:
            print(f"\n[BŁĄD SIECI] {e}")
            print("[INFO] Próba ponownego połączenia za 5 sekund...")
            time.sleep(5)

        except KeyboardInterrupt:
            print("\n[INFO] Przerwano działanie programu przez użytkownika.")
            break

if __name__ == "__main__":
    main()