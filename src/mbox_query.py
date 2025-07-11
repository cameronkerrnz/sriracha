# Sriracha - Makes Takeout Better
# Copyright (C) 2025 Cameron Kerr
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import os
from typing import List, Optional, Dict, Any
from whoosh.index import open_dir
from whoosh.qparser import MultifieldParser, OrGroup
from whoosh.query import Query
from whoosh.searching import Results
from email.message import EmailMessage

class MBoxQuery:
    """
    Provides a query/search interface for indexed MBOX files using Whoosh.
    """
    def __init__(self, index_dir: str):
        if not os.path.exists(index_dir):
            raise FileNotFoundError(f"Index directory not found: {index_dir}")
        self.ix = open_dir(index_dir)
        self.default_fields = ["subject", "body", "sender", "recipients"]

    def search(self, query_str: str, limit: int = 50, fields: Optional[List[str]] = None, filters: Optional[Dict[str, Any]] = None) -> Results:
        """
        Search the index for the given query string.
        :param query_str: The search query string.
        :param limit: Maximum number of results to return.
        :param fields: List of fields to search (defaults to subject, body, sender, recipients).
        :param filters: Optional dictionary of field:value pairs to filter results.
        :return: Whoosh Results object.
        """
        with self.ix.searcher() as searcher:
            parser = MultifieldParser(fields or self.default_fields, schema=self.ix.schema, group=OrGroup)
            query: Query = parser.parse(query_str)
            # Apply filters if provided
            if filters:
                from whoosh.query import And, Term
                filter_query = And([Term(field, str(value)) for field, value in filters.items()])
                query = query & filter_query
            results = searcher.search(query, limit=limit)
            # Return a list of dicts for each hit
            return [dict(hit) for hit in results]

    def get_labels(self) -> List[str]:
        """
        Return a list of all unique labels (from aggregate_labels.json if present).
        """
        agg_path = os.path.join(self.ix.storage.folder, 'aggregate_labels.json')
        if os.path.exists(agg_path):
            import json
            with open(agg_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return sorted(data.keys(), key=lambda s: s.lower())
        return []

    def highlights(self, message_id: Optional[str] = None, docnum: Optional[int] = None, query_str: Optional[str] = None, field: str = "body", top: int = 10) -> Optional[List[str]]:
        """
        Return highlighted fragments for a message given its message_id or docnum and a query string.
        :param message_id: The Message-ID of the message (preferred if available).
        :param docnum: The Whoosh docnum (if known).
        :param query_str: The search query string to highlight terms for.
        :param field: The field to highlight (default: body).
        :param top: The number of top fragments to return.
        :return: List of highlighted fragments, or None if not found or no highlights.
        """
        from whoosh.highlight import UppercaseFormatter
        if not query_str:
            return None
        with self.ix.searcher() as searcher:
            parser = MultifieldParser(self.default_fields, schema=self.ix.schema, group=OrGroup)
            query = parser.parse(query_str)
            if message_id is not None:
                results = searcher.search(query, limit=None)
                results.formatter = UppercaseFormatter()
                for hit in results:
                    if hit.get("message_id") == message_id:
                        fragments = hit.highlights(field, top=top, text=hit.get(field, None))
                        if fragments:
                            return [fragments]
                        else:
                            return None
                return None
            elif docnum is not None:
                doc = searcher.stored_fields(docnum)
                results = searcher.search(query, limit=None)
                for hit in results:
                    if hit.docnum == docnum:
                        fragments = hit.highlights(field, top=top, text=hit.get(field, None))
                        if fragments:
                            return [fragments]
                        else:
                            return None
                return None
            else:
                return None

    def extract_message_by_extents(self, mbox_path: str, extents: tuple) -> 'EmailMessage':
        """
        Given a path to an mbox file and a (start, stop) tuple, seek to the start,
        read the correct number of bytes, and return the message as an EmailMessage.
        The extents should include the 'From ' line and the full message.
        """
        from email.parser import BytesParser
        from email.policy import default
        start, stop = extents
        with open(mbox_path, 'rb') as f:
            f.seek(start)
            raw_bytes = f.read(stop - start)
        # Parse as a full RFC822 message (including 'From ' line)
        # Remove the 'From ' line if present, as email.parser expects headers to start immediately
        if raw_bytes.startswith(b'From '):
            first_nl = raw_bytes.find(b'\n')
            if first_nl != -1:
                raw_bytes = raw_bytes[first_nl+1:]
        msg = BytesParser(policy=default).parsebytes(raw_bytes)
        return msg

if __name__ == "__main__":

    from whoosh.highlight import Formatter, get_text

    class BeforeAfterFormatter(Formatter):
        def __init__(self, before, after, between="..."):
            """
            :param between: the text to add between fragments.
            """
            self.before = before
            self.after = after
            self.between = between

        def format_token(self, text, token, replace=False):
            ttxt = get_text(text, token, replace)
            return f"{self.before}{ttxt}{self.after}"

    coloriser = BeforeAfterFormatter('\033[31m', '\033[0m')

    import sys
    index_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    query_engine = MBoxQuery(index_dir)
    print(f"Loaded index from: {index_dir}")
    print("Welcome to Sriracha!")
    print("Commands:")
    print("  :labels   - List all unique labels")
    print("  :help     - Show this help message")
    print("  :quit     - Exit the REPL")
    print("Type a search query to search the index.")
    output_mode = "plain"
    while True:
        try:
            line = input("query> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if not line:
            continue
        if line.lower() in (":quit", ":exit", "quit", "exit"):
            break
        if line.startswith(":help"):
            print("Commands:")
            print("  :labels   - List all unique labels")
            print("  :help     - Show this help message")
            print("  :quit     - Exit the REPL")
            print("Type a search query to search the index.")
            continue
        if line.startswith(":out"):
            print("The :out command is no longer supported. Output is always human-friendly with highlights.")
            continue
        if line.startswith(":labels"):
            labels = query_engine.get_labels()
            print(f"Labels ({len(labels)}):")
            for label in labels:
                print(f"  {label}")
            continue
        # Use the Whoosh searcher directly for highlights
        with query_engine.ix.searcher() as searcher:
            parser = MultifieldParser(query_engine.default_fields, schema=query_engine.ix.schema, group=OrGroup)
            query = parser.parse(line)
            results = searcher.search(query, limit=10)
            results.formatter = coloriser
            print(f"Found {len(results)} result(s):")
            for i, hit in enumerate(results, 1):
                subj = hit.get("subject", "")
                sender = hit.get("sender", "")
                date = hit.get("date", "")
                recipients = hit.get("recipients", "")
                message_id = hit.get("message_id", "")
                labels = hit.get("labels", "").split(",") if hit.get("labels") else []
                print(f"[{i}] {date} | {subj[:60]}")
                print(f"    From: {sender}")
                print(f"    To: {recipients}")
                print(f"    Message-ID: {message_id}")
                print(f"    Labels: {', '.join(labels)}")
                print(f"    Subject: {subj}")
                print(f"    {hit.highlights('body', top=2)}\n")
                print("" + "-" * 80)
