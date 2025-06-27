import zipfile
import mailbox
import os
from whoosh.fields import Schema, TEXT, ID, DATETIME
from whoosh.index import create_in
from whoosh.analysis import StemmingAnalyzer
from email.utils import parsedate_to_datetime
import tempfile
from math import ceil
from tqdm import tqdm
import readline
from whoosh.qparser import QueryParser

# Path to the zip archive
ZIP_PATH = "../takeout-downloads/my-gmail/takeout-20250627T054951Z-1-001.zip"

# Whoosh schema for email indexing
schema = Schema(
    subject=TEXT(stored=True, analyzer=StemmingAnalyzer()),
    sender=TEXT(stored=True),
    recipients=TEXT(stored=True),
    date=DATETIME(stored=True),
    body=TEXT(stored=True, analyzer=StemmingAnalyzer()),
    mbox_file=ID(stored=True),
    msg_key=ID(stored=True, unique=True)
)

def extract_and_index(zip_path, schema, index_dir):
    with zipfile.ZipFile(zip_path, 'r') as z:
        mbox_files = [f for f in z.namelist() if f.endswith('.mbox')]
        if not mbox_files:
            print("No .mbox files found in the archive.")
            return
        if not os.path.exists(index_dir):
            os.makedirs(index_dir)
        ix = create_in(index_dir, schema)
        writer = ix.writer()
        for mbox_name in mbox_files:
            print(f"Processing {mbox_name}...")
            z.extract(mbox_name, index_dir)
            mbox_path = os.path.join(index_dir, mbox_name)
            mbox = mailbox.mbox(mbox_path)
            total = len(mbox)
            if total == 0:
                print("  (No messages found)")
                continue
            print(f"  {total} messages to index...")
            for i, (key, msg) in enumerate(tqdm(mbox.iteritems(), total=total, desc=f"Indexing {mbox_name}", unit="msg")):
                subject = msg.get('subject', '')
                sender = msg.get('from', '')
                recipients = msg.get('to', '')
                date = msg.get('date', '')
                try:
                    date_parsed = parsedate_to_datetime(date) if date else None
                except Exception:
                    date_parsed = None
                if msg.is_multipart():
                    body = ''
                    for part in msg.walk():
                        if part.get_content_type() == 'text/plain':
                            try:
                                payload = part.get_payload(decode=True)
                                if isinstance(payload, bytes):
                                    body += payload.decode(part.get_content_charset() or 'utf-8', errors='replace')
                                elif isinstance(payload, str):
                                    body += payload
                            except Exception:
                                continue
                else:
                    try:
                        payload = msg.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            body = payload.decode(msg.get_content_charset() or 'utf-8', errors='replace')
                        elif isinstance(payload, str):
                            body = payload
                        else:
                            body = ''
                    except Exception:
                        body = ''
                writer.add_document(
                    subject=subject,
                    sender=sender,
                    recipients=recipients,
                    date=date_parsed,
                    body=body,
                    mbox_file=mbox_name,
                    msg_key=f"{mbox_name}:{key}"
                )
        writer.commit()
        print(f"Indexing complete. Index is stored in: {index_dir}")

def list_zip_files(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as z:
        print("Files in zip archive:")
        for name in z.namelist():
            print(name)

if __name__ == "__main__":
    INDEX_DIR = os.path.join(os.path.dirname(__file__), "whoosh-index")
    # ldist_zip_files(ZIP_PATH)
    extract_and_index(ZIP_PATH, schema, INDEX_DIR)
