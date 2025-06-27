import mailbox
import os
from whoosh.fields import Schema, TEXT, ID, DATETIME, STORED
from whoosh.index import create_in
from whoosh.analysis import StemmingAnalyzer
from email.utils import parsedate_to_datetime
from tqdm import tqdm

# Whoosh schema for email indexing
schema = Schema(
    subject=TEXT(stored=True, analyzer=StemmingAnalyzer()),
    sender=TEXT(stored=True),
    recipients=TEXT(stored=True),
    date=DATETIME(stored=True),
    body=TEXT(stored=True, analyzer=StemmingAnalyzer()),
    mbox_file=ID(stored=True),
    msg_key=ID(stored=True, unique=True),
    mbox_message_extents=STORED()
)

def extract_and_index(mbox_path, schema, index_dir):
    if not os.path.exists(mbox_path):
        print(f"MBOX file not found: {mbox_path}")
        return
    if not os.path.exists(index_dir):
        os.makedirs(index_dir)
    ix = create_in(index_dir, schema)
    writer = ix.writer()
    mbox = mailbox.mbox(mbox_path)
    total = len(mbox)
    if total == 0:
        print("  (No messages found)")
        return
    print(f"  {total} messages to index...")
    for i, (key, msg) in enumerate(tqdm(mbox.iteritems(), total=total, desc=f"Indexing {os.path.basename(mbox_path)}", unit="msg")):
        mbox_message_extents = mbox._lookup(key) # Calculate offset to start of message
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
            mbox_file=os.path.basename(mbox_path),
            msg_key=f"{os.path.basename(mbox_path)}:{key}",
            mbox_message_extents=mbox_message_extents
        )
    writer.commit()
    print(f"Indexing complete. Index is stored in: {index_dir}")

if __name__ == "__main__":
    INDEX_DIR = os.path.join(os.path.dirname(__file__), "whoosh-index")
    # Update this path to your decompressed MBOX file
    MBOX_PATH = os.path.join(os.path.dirname(__file__), "../takeout-downloads/my-gmail/unzipped/All mail Including Spam and Trash.mbox")
    extract_and_index(MBOX_PATH, schema, INDEX_DIR)
