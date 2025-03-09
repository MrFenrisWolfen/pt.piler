import imaplib
import os
import email
import uuid
from email.header import decode_header
import re
from datetime import datetime, timedelta
import subprocess
import fcntl
import sys

# Konfiguration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(SCRIPT_DIR, "accounts.txt")
SAVE_DIRECTORY = "/var/tmp/emails"
SAVED_EMAILS_FILE = os.path.join(SCRIPT_DIR, "saved_emails.txt")
DELETE_EMAILS = False  
LOCK_FILE = "/var/scripts/24h_script.lock"

# Lock-Datei öffnen und sperren
try:
    with open(LOCK_FILE, "w") as lockfile:
        try:
            fcntl.lockf(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print("🚀 Skript läuft...")

            def clean_subject(subject, max_length=50):
                if not subject:
                    return "No_Subject"

                decoded_parts = decode_header(subject)
                subject = ""
                
                for part, encoding in decoded_parts:
                    try:
                        if isinstance(part, bytes):
                            encoding = encoding or "utf-8"
                            if encoding.lower() == "unknown-8bit":
                                encoding = "utf-8"
                            subject += part.decode(encoding, errors="ignore")
                        else:
                            subject += part
                    except (LookupError, UnicodeDecodeError):  
                        subject += part.decode("utf-8", errors="ignore")

                subject = re.sub(r"[^a-zA-Z0-9\s\-_()]", "", subject)
                subject = re.sub(r"\s+", " ", subject).strip().replace(" ", "_")
                return subject[:max_length]

            def load_saved_emails():
                if not os.path.exists(SAVED_EMAILS_FILE):
                    return set()
                with open(SAVED_EMAILS_FILE, "r", encoding="utf-8") as f:
                    return set(line.strip() for line in f.readlines())

            def save_email_id(message_id):
                with open(SAVED_EMAILS_FILE, "a", encoding="utf-8") as f:
                    f.write(message_id + "\n")

            def download_emails(imap_server, username, password, folder=None):
                imap = None
                try:
                    print(f"📡 Verbinde mit {username} ({imap_server})...")
                    imap = imaplib.IMAP4_SSL(imap_server)
                    imap.login(username, password)

                    folders = [folder] if folder else [box.split()[-1].strip(b'"').decode() for box in imap.list()[1]]
                    saved_emails = load_saved_emails()
                    date_since = (datetime.utcnow() - timedelta(days=1)).strftime("%d-%b-%Y")

                    for folder in folders:
                        print(f"📂 Prüfe Ordner: {folder}")
                        
                        if imap.select(folder, readonly=True)[0] != "OK":
                            print(f"⚠ Fehler: Konnte Ordner '{folder}' nicht auswählen. Überspringe...")
                            continue

                        typ, data = imap.search(None, f'SINCE {date_since}')
                        if typ != "OK" or not data or not data[0]:
                            print(f"📭 Keine neuen E-Mails in {folder} für {username}.")
                            continue

                        for num in data[0].split():
                            typ, msg_data = imap.fetch(num, '(RFC822)')
                            if not msg_data or not msg_data[0]:
                                print(f"⚠ Fehler beim Abrufen der E-Mail {num.decode()} für {username}.")
                                continue

                            email_message = email.message_from_bytes(msg_data[0][1])
                            message_id = email_message.get("Message-ID", f"<{uuid.uuid4()}@generated.local>").strip()

                            if message_id in saved_emails:
                                print(f"✅ E-Mail mit Message-ID {message_id} wurde bereits gespeichert. Überspringe...")
                                continue

                            subject = clean_subject(email_message["Subject"])
                            unique_id = str(uuid.uuid4())[:8]
                            user_folder = os.path.join(SAVE_DIRECTORY, username, folder.replace("/", "_"))
                            os.makedirs(user_folder, exist_ok=True)

                            email_filename = os.path.join(user_folder, f'Email_{unique_id}_{subject}.eml')
                            with open(email_filename, 'wb') as f:
                                f.write(msg_data[0][1])
                            print(f'✅ E-Mail gespeichert: {email_filename}')

                            save_email_id(message_id)

                            if DELETE_EMAILS:
                                imap.store(num, '+FLAGS', '\\Deleted')
                                imap.expunge()
                                print(f'🗑 E-Mail {num.decode()} gelöscht.')

                except Exception as e:
                    print(f"❌ Fehler bei {username}: {e}")
                finally:
                    if imap:
                        try:
                            imap.logout()
                            print(f"🔌 Verbindung getrennt für {username}.")
                        except:
                            print(f"⚠ Fehler beim Abmelden von {username}.")

            def load_accounts():
                if not os.path.exists(ACCOUNTS_FILE):
                    print(f"❌ Fehler: {ACCOUNTS_FILE} nicht gefunden!")
                    return []
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    return [tuple(line.strip().split(";")) + (None,) if len(line.strip().split(";")) == 3 else tuple(line.strip().split(";")) for line in f]

            if __name__ == "__main__":
                print("🚀 Starte E-Mail-Abruf...")
                accounts = load_accounts()
                if accounts:
                    for imap_server, username, password, folder in accounts:
                        download_emails(imap_server, username, password, folder)
                else:
                    print("❌ Keine gültigen E-Mail-Konten gefunden.")

                print("Starte pilerimport als User 'piler'...")
                subprocess.run("cd /var/tmp && pilerimport -d /var/tmp/emails -r", shell=True, check=True)

                print("✅ Skript beendet.")
        
        except IOError:
            print("🚫 Skript läuft bereits woanders. Beende...")
            sys.exit(1)

except Exception as e:
    print(f"❌ Unerwarteter Fehler: {e}")
    sys.exit(1)
