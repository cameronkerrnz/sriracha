import os
import threading
from typing import Callable, List, Optional, Any, Dict
import mailbox
from whoosh.fields import Schema
from whoosh.index import create_in, open_dir
from whoosh.analysis import StemmingAnalyzer
from email.message import Message as EmailMessage
from email.utils import parsedate_to_datetime
import logging

class MBoxIndexer(threading.Thread):
    """
    Indexes one or more MBOX files in a background thread, reporting progress and allowing per-message hooks.
    """
    def __init__(
        self,
        mbox_files: List[str],
        index_dir: str,
        schema: Schema,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        message_callback: Optional[Callable[[str, int, EmailMessage], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        super().__init__()
        self.mbox_files = mbox_files
        self.index_dir = index_dir
        self.schema = schema
        self.progress_callback = progress_callback
        self.message_callback = message_callback
        self.status_callback = status_callback
        self.extra = extra or {}
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        logger = logging.getLogger(__name__)
        # Remove any existing index directory and its contents
        if os.path.exists(self.index_dir):
            import shutil
            shutil.rmtree(self.index_dir)
        if not os.path.exists(self.index_dir):
            os.makedirs(self.index_dir)
        try:
            ix = create_in(self.index_dir, self.schema)
        except Exception:
            ix = open_dir(self.index_dir)
        # Performance: set StemmingAnalyzer cachesize to -1 (unbounded)
        for fieldname, field in self.schema.items():
            if hasattr(field, 'format') and hasattr(field.format, 'analyzer') and field.format.analyzer:
                analyzer = field.format.analyzer
                analyzer.cachesize = -1
                if hasattr(analyzer, 'clear'):
                    analyzer.clear()
        # Use batch writer settings for speed
        writer = ix.writer(limitmb=256, procs=4, multisegment=True)
        for mbox_path in self.mbox_files:
            if not os.path.exists(mbox_path):
                continue
            if self.status_callback:
                self.status_callback(f"Opening MBOX and building Table of Contents: {mbox_path}")
            logger.info(f"Opening MBOX {mbox_path!r}")
            # TODO: Make a custom MBox class that doesn't use a TOC
            mbox = mailbox.mbox(mbox_path)
            if self.status_callback:
                self.status_callback(f"Indexing messages in: {mbox_path}")
            mbox_file_size = os.path.getsize(mbox_path)
            processed = 0
            for i, (key, msg) in enumerate(mbox.iteritems()):
                if self._stop_event.is_set():
                    writer.commit()
                    return
                if self.message_callback:
                    self.message_callback(mbox_path, i, msg)
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
                mbox_message_extents = mbox._lookup(key)
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
                processed += 1
                # Progress: use file offset if available
                if mbox_message_extents and isinstance(mbox_message_extents, tuple):
                    file_offset = mbox_message_extents[0]
                    percent = min(100, int(100 * file_offset / mbox_file_size)) if mbox_file_size else 0
                else:
                    percent = 0
                if self.progress_callback:
                    self.progress_callback(mbox_path, percent, processed)
            if self.status_callback:
                self.status_callback(f"Finalising indexing: {mbox_path}")
        writer.commit()
        # Ensure processed is always defined
        if self.progress_callback:
            self.progress_callback('done', 100, locals().get('processed', 0))
        if self.status_callback:
            self.status_callback("All MBOX files indexed.")

if __name__ == "__main__":
    import sys
    import time
    import logging
    from whoosh.fields import Schema, TEXT, ID, DATETIME, STORED
    from whoosh.analysis import StemmingAnalyzer
    from collections import Counter

    # Configure logging for the CLI
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Define a schema similar to the experiment
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

    if len(sys.argv) < 3:
        print("Usage: python mbox_indexer.py <index_dir> <mbox1> [<mbox2> ...]")
        sys.exit(1)
    index_dir = sys.argv[1]
    mbox_files = sys.argv[2:]

    label_set = set()
    label_counter = Counter()

    def progress_callback(mbox_path: str, percent: int, processed: int):
        if mbox_path == 'done':
            print(f"\nIndexing complete. {processed} messages indexed.")
        else:
            print(f"\rIndexing {os.path.basename(mbox_path)}: {percent}% ({processed} messages)", end="", flush=True)

    def message_callback(mbox_path: str, idx: int, msg: EmailMessage):
        import re
        label_headers = msg.get_all('X-Gmail-Labels', [])
        for header in label_headers:
            for label in header.split(','):
                # Collapse all whitespace (including line breaks) to a single space
                label = re.sub(r'\s+', ' ', label).strip()
                if label:
                    label_set.add(label)
                    label_counter[label] += 1

    def status_callback(msg: str):
        print(f"[STATUS] {msg}")

    print(f"Indexing {len(mbox_files)} MBOX file(s) into {index_dir} ...")
    indexer = MBoxIndexer(
        mbox_files=mbox_files,
        index_dir=index_dir,
        schema=schema,
        progress_callback=progress_callback,
        message_callback=message_callback,
        status_callback=status_callback
    )
    indexer.start()
    while indexer.is_alive():
        time.sleep(0.1)
    print("\n\nUnique X-Gmail-Labels found:")
    for label, count in label_counter.most_common():
        print(f"  {label}: {count} messages")
