import pytest
import sys
import os
import json
import ssl
from unittest.mock import MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "client")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from client import receive_message, send_message, print_response
from protocol import create_message


# ==========================================
# I. TESTY FORMATOWANIA ODPOWIEDZI (UI)
# ==========================================

def test_print_response_error(capsys):
    """Weryfikuje poprawne formatowanie komunikatu o błędzie."""
    mock_response = {
        "type": "ERROR",
        "payload": {
            "code": 102,
            "message": "Authentication failed"
        }
    }

    print_response(mock_response)
    captured = capsys.readouterr()
    assert "BŁĄD 102: Authentication failed" in captured.out


def test_print_response_success(capsys):
    """Weryfikuje poprawne formatowanie standardowej odpowiedzi."""
    mock_response = {
        "type": "SUCCESS",
        "payload": {
            "message": "Note added"
        }
    }

    print_response(mock_response)
    captured = capsys.readouterr()
    assert "ODPOWIEDŹ:" in captured.out
    assert "Note added" in captured.out


def test_print_response_empty(capsys):
    """Weryfikuje zachowanie funkcji w przypadku braku odpowiedzi (None)."""
    print_response(None)
    captured = capsys.readouterr()
    assert "Brak odpowiedzi serwera." in captured.out


# ==========================================
# II. TESTY LOGIKI SIECIOWEJ (I/O)
# ==========================================

def test_receive_message_chunks():
    """
    Weryfikuje, czy funkcja poprawnie skleja pofragmentowane dane
    odczytywane z gniazda aż do napotkania znaku nowej linii.
    """
    mock_conn = MagicMock()
    mock_conn.recv.side_effect = [
        b'{"type": "HELLO_ACK", ',
        b'"payload": {"ver": ',
        b'"1.0"}}\n'
    ]

    response = receive_message(mock_conn)

    assert response["type"] == "HELLO_ACK"
    assert response["payload"]["ver"] == "1.0"
    assert mock_conn.recv.call_count == 3


def test_receive_message_connection_closed():
    """
    Weryfikuje zachowanie, gdy gniazdo zostanie zamknięte (EOF).
    Wymaga zgłoszenia wyjątku ConnectionError dla mechanizmu Auto-Reconnect.
    """
    mock_conn = MagicMock()
    mock_conn.recv.return_value = b""  # Pusty bajt oznacza zamknięcie strumienia (FIN)

    with pytest.raises(ConnectionError, match="Serwer zamknął połączenie"):
        receive_message(mock_conn)


def test_receive_message_network_error():
    """
    Weryfikuje, czy fizyczne błędy sieci i warstwy SSL są poprawnie
    przechwytywane i re-emitowane jako zunifikowany ConnectionError.
    """
    mock_conn = MagicMock()
    # Symulacja błędu z warstwy transportowej/szyfrowania
    mock_conn.recv.side_effect = ssl.SSLError("Błąd certyfikatu lub SSL EOF")

    with pytest.raises(ConnectionError, match="Utracono połączenie podczas odbierania danych"):
        receive_message(mock_conn)


def test_send_message():
    """
    Weryfikuje proces serializacji wiadomości i wysyłania jej przez gniazdo.
    """
    mock_conn = MagicMock()
    mock_conn.recv.return_value = b'{"type": "SUCCESS", "payload": {}}\n'

    test_msg = create_message("HELLO", {"client_version": "1.0"})
    response = send_message(mock_conn, test_msg)

    # Sprawdzamy, czy mock_conn.sendall zostało wywołane dokładnie raz z poprawną ramką
    expected_bytes = json.dumps(test_msg).encode("utf-8") + b"\n"
    mock_conn.sendall.assert_called_once_with(expected_bytes)
    assert response["type"] == "SUCCESS"


def test_send_message_network_error():
    """
    Weryfikuje propagację błędu w przypadku zerwania potoku wysyłania
    (np. próba zapisu do gniazda z nałożoną flagą RST).
    """
    mock_conn = MagicMock()
    # Symulacja błędu gniazda podczas próby wysyłania (np. BrokenPipeError)
    mock_conn.sendall.side_effect = OSError("Broken pipe")

    test_msg = create_message("PING")

    with pytest.raises(ConnectionError, match="Utracono potok wysyłania"):
        send_message(mock_conn, test_msg)