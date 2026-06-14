# Secure Notes

Projekt wykonany w ramach przedmiotu **Programowanie Usług Sieciowych (PUS)**.

## Autorzy

* Antoni Michalczak
* Szymon Niedzielski

---

# Opis projektu

Secure Notes to aplikacja klient-serwer umożliwiająca bezpieczne przechowywanie prywatnych notatek użytkownika.

Komunikacja odbywa się za pomocą autorskiego protokołu **Secure Notes Protocol (SNP)** zaprojektowanego w ramach Etapu 1 projektu.

System umożliwia:

* rejestrację użytkownika,
* logowanie,
* dodawanie notatek,
* wyświetlanie notatek,
* usuwanie notatek,
* bezpieczną komunikację przez TLS.

---

# Technologie

* Python 3
* TCP Socket
* TLS / SSL
* SQLite
* JSON
* Git
* WSL Ubuntu

---

# Struktura projektu

```text
secure-notes/
├── client/
│   └── client.py
├── server/
│   ├── server.py
│   ├── database.py
│   └── protocol.py
├── certs/
├── docs/
├── tests/
├── README.md
├── requirements.txt
└── .gitignore
```

---

# Wymagania

* Python 3.10+
* OpenSSL
* SQLite3

Instalacja:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv openssl sqlite3
```

---

# Generowanie certyfikatu TLS

W katalogu projektu:

```bash
openssl req -x509 -newkey rsa:2048 \
-keyout certs/server.key \
-out certs/server.crt \
-days 365 \
-nodes
```

Przykładowe dane:

```text
Country Name: PL
State: Malopolskie
City: Krakow
Organization: SecureNotes
Common Name: localhost
```

Powstaną pliki:

```text
certs/server.key
certs/server.crt
```

---

# Inicjalizacja bazy danych

Usunięcie starej bazy (opcjonalnie):

```bash
rm secure_notes.db
```

Utworzenie nowej bazy:

```bash
python3 server/database.py
```

Domyślny użytkownik:

```text
login: test
hasło: test123
```

---

# Uruchomienie serwera

W pierwszym terminalu:

```bash
python3 server/server.py
```

Oczekiwany komunikat:

```text
[INFO] Secure Notes Server running on 127.0.0.1:8443
```

---

# Uruchomienie klienta

W drugim terminalu:

```bash
python3 client/client.py
```

---

# Funkcjonalności

## Rejestracja

Tworzenie nowego konta użytkownika.

## Logowanie

Autoryzacja użytkownika na podstawie loginu i hasła.

## Dodawanie notatek

Tworzenie nowej notatki przypisanej do użytkownika.

## Wyświetlanie notatek

Pobieranie listy własnych notatek.

## Usuwanie notatek

Usuwanie wybranej notatki.

---

# Bezpieczeństwo

Projekt wykorzystuje:

* TLS do szyfrowania komunikacji,
* haszowanie haseł (SHA-256),
* tokeny sesyjne,
* walidację komunikatów JSON,
* autoryzację dostępu do notatek.

---

# Przykładowe scenariusze testowe

## Poprawne logowanie

```text
Login: test
Password: test123
```

Oczekiwany wynik:

```text
Authentication successful
```

## Błędne logowanie

```text
Login: test
Password: zle_haslo
```

Oczekiwany wynik:

```text
ERROR 102 Authentication failed
```

## Dodanie notatki

```text
Title: Zakupy
Content: Mleko, chleb
```

Oczekiwany wynik:

```text
Note added
```

## Usunięcie nieistniejącej notatki

Oczekiwany wynik:

```text
ERROR 107 Note not found
```

---

# Protokół SNP

Obsługiwane komunikaty:

```text
HELLO
HELLO_ACK

REGISTER
REGISTER_ACK

AUTH
AUTH_ACK

ADD_NOTE
LIST_NOTES
DELETE_NOTE

SUCCESS
ERROR

BYE
BYE_ACK
```

---

# Status projektu

Wersja MVP ukończona.

Zaimplementowano:

* komunikację klient-serwer,
* TLS,
* bazę SQLite,
* logowanie,
* rejestrację,
* zarządzanie notatkami,
* obsługę błędów,
* autorski protokół SNP.
