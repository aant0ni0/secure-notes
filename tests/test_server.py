import socket
import ssl
import json
import pytest
import os
import sys
import uuid

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from protocol import create_message, encode_message, decode_message
from database import init_db, get_connection

HOST = "127.0.0.1"
PORT = 8443


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """
    Fixture uruchamiany raz na całą sesję testową.
    Czyści bazę danych przed uruchomieniem testów, aby zapewnić izolację.
    """
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes")
    cursor.execute("DELETE FROM users")
    conn.commit()
    conn.close()


@pytest.fixture
def client_socket():
    """
    Fixture dostarczający połączone gniazdo TLS dla każdego testu.
    Gniazdo jest zamykane automatycznie po zakończeniu testu.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    with socket.create_connection((HOST, PORT)) as sock:
        with context.wrap_socket(sock, server_hostname="localhost") as conn:
            yield conn


def send_and_receive(conn, message_type, payload=None, session_token=None):
    """Pomocnicza funkcja do wysyłania poprawnych komunikatów SNP."""
    msg = create_message(message_type, payload, session_token)
    conn.sendall(encode_message(msg))

    data = b""
    while not data.endswith(b"\n"):
        chunk = conn.recv(4096)
        if not chunk:
            break
        data += chunk

    return decode_message(data.strip())

def test_tc01_register_success(client_socket):
    response = send_and_receive(
        client_socket,
        "REGISTER",
        {"username": "test_user_1", "password": "secure123"}
    )
    assert response["type"] == "REGISTER_ACK"
    assert "User created" in response["payload"]["message"]


def test_tc02_auth_success(client_socket):
    # Logowanie na konto z poprzedniego testu
    response = send_and_receive(
        client_socket,
        "AUTH",
        {"username": "test_user_1", "password": "secure123"}
    )
    assert response["type"] == "AUTH_ACK"
    assert "session_token" in response["payload"]


def test_tc03_add_note_success(client_socket):
    # Najpierw logowanie, by uzyskać token
    auth_resp = send_and_receive(
        client_socket, "AUTH", {"username": "test_user_1", "password": "secure123"}
    )
    token = auth_resp["payload"]["session_token"]

    # Dodanie notatki
    response = send_and_receive(
        client_socket,
        "ADD_NOTE",
        {"title": "Testowa Notatka", "content": "Ważne dane"},
        session_token=token
    )
    assert response["type"] == "SUCCESS"
    assert "note_id" in response["payload"]


def test_tc04_list_notes_success(client_socket):
    auth_resp = send_and_receive(
        client_socket, "AUTH", {"username": "test_user_1", "password": "secure123"}
    )
    token = auth_resp["payload"]["session_token"]

    response = send_and_receive(client_socket, "LIST_NOTES", session_token=token)
    assert response["type"] == "SUCCESS"
    assert isinstance(response["payload"]["notes"], list)
    assert len(response["payload"]["notes"]) >= 1


def test_tc05_delete_note_success(client_socket):
    auth_resp = send_and_receive(
        client_socket, "AUTH", {"username": "test_user_1", "password": "secure123"}
    )
    token = auth_resp["payload"]["session_token"]

    # Pobieramy ID notatki do usunięcia
    list_resp = send_and_receive(client_socket, "LIST_NOTES", session_token=token)
    note_id = list_resp["payload"]["notes"][0]["id"]

    response = send_and_receive(
        client_socket,
        "DELETE_NOTE",
        {"note_id": note_id},
        session_token=token
    )
    assert response["type"] == "SUCCESS"
    assert "Note deleted" in response["payload"]["message"]


def test_tc06_register_conflict(client_socket):
    # Próba ponownej rejestracji tego samego loginu
    response = send_and_receive(
        client_socket,
        "REGISTER",
        {"username": "test_user_1", "password": "newpassword"}
    )
    assert response["type"] == "ERROR"
    assert response["payload"]["code"] == 100
    assert "Username already exists" in response["payload"]["message"]


def test_tc07_auth_failure(client_socket):
    response = send_and_receive(
        client_socket,
        "AUTH",
        {"username": "test_user_1", "password": "wrong_password"}
    )
    assert response["type"] == "ERROR"
    assert response["payload"]["code"] == 102


def test_tc08_unauthorized_access(client_socket):
    # Próba dodania notatki bez tokena sesji
    response = send_and_receive(
        client_socket,
        "ADD_NOTE",
        {"title": "Nieautoryzowana", "content": "Włamanie"}
    )
    assert response["type"] == "ERROR"
    assert response["payload"]["code"] == 103


def test_tc09_delete_nonexistent_note(client_socket):
    auth_resp = send_and_receive(
        client_socket, "AUTH", {"username": "test_user_1", "password": "secure123"}
    )
    token = auth_resp["payload"]["session_token"]

    response = send_and_receive(
        client_socket,
        "DELETE_NOTE",
        {"note_id": 999999},
        session_token=token
    )
    assert response["type"] == "ERROR"
    assert response["payload"]["code"] == 107


def test_tc10_message_too_large(client_socket):
    # Ręczne stworzenie zbyt dużej ramki omijającej `encode_message`
    huge_payload = "A" * 9000
    msg = create_message("HELLO", {"data": huge_payload})
    raw_data = json.dumps(msg).encode("utf-8") + b"\n"

    client_socket.sendall(raw_data)

    data = b""
    while not data.endswith(b"\n"):
        data += client_socket.recv(4096)

    response = json.loads(data.strip())
    assert response["type"] == "ERROR"
    assert response["payload"]["code"] == 100
    assert "Message too large" in response["payload"]["message"]


def test_tc11_malformed_json(client_socket):
    # Wysłanie uciętego JSONa (brak klamry)
    malformed_data = b'{"type": "HELLO", "msg_id": "123", "timestamp": 1234, "payload": {"a": "b"\n'
    client_socket.sendall(malformed_data)

    data = b""
    while not data.endswith(b"\n"):
        data += client_socket.recv(4096)

    response = json.loads(data.strip())
    assert response["type"] == "ERROR"
    assert response["payload"]["code"] == 100
    assert "Invalid JSON format" in response["payload"]["message"]