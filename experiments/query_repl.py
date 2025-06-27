import os
import readline
from whoosh.qparser import QueryParser
from whoosh.index import open_dir

HISTFILE = os.path.join(os.path.dirname(__file__), "query.history")
try:
    readline.read_history_file(HISTFILE)
except FileNotFoundError:
    pass

def run_repl(ix):
    help_text = '''\nWhoosh Email Index REPL Help
Type your search query, or 'exit' to quit. You can search on:
  body:<text>         - search in message body (default if no field specified)
  subject:<text>      - search in subject
  sender:<email>      - search by sender (from)
  recipients:<email>  - search by recipient (to/cc/bcc)
  date:YYYY-MM-DD     - search by date (e.g., date:2024-06-27)

Sample queries:
  hello world
  subject:invoice
  sender:alice@example.com
  recipients:bob@example.com
  date:2024-06-27
  subject:report body:urgent
Type 'help' to see this message again.
'''
    print("\nWhoosh Email Index REPL. Type your search query, or 'exit' to quit.")
    print(help_text)
    qp = QueryParser("body", schema=ix.schema)
    with ix.searcher() as searcher:
        while True:
            try:
                query_str = input("search> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting REPL.")
                break
            if query_str.lower() in ("exit", "quit", ":q"):
                print("Exiting REPL.")
                break
            if query_str.lower() == "help":
                print(help_text)
                continue
            if not query_str:
                continue
            try:
                q = qp.parse(query_str)
            except Exception as e:
                print(f"Query error: {e}")
                continue
            results = searcher.search(q, limit=None)
            if not results:
                print("No results found.")
                continue
            page_size = 10
            total = len(results)
            page = 0
            while True:
                start = page * page_size
                end = min(start + page_size, total)
                for i, hit in enumerate(results[start:end], start=start+1):
                    print(f"[{i}/{total}] {hit['date']} | {hit['subject'][:60]}")
                    print(f"    From: {hit['sender']} | To: {hit['recipients']}")
                    print(f"    Key: {hit['msg_key']}")
                    print(f"    {hit.highlights('body', top=2)}\n")
                if end >= total:
                    break
                inp = input(f"-- More ({end}/{total}) -- Press Enter for next page, 'q' to quit: ")
                if inp.strip().lower() == 'q':
                    break
                page += 1
    try:
        readline.write_history_file(HISTFILE)
    except Exception:
        pass

def main():
    index_dir = os.path.join(os.path.dirname(__file__), "whoosh-index")
    if not os.path.exists(index_dir):
        print(f"Index directory not found: {index_dir}\nRun the indexing script first.")
        return
    ix = open_dir(index_dir)
    run_repl(ix)

if __name__ == "__main__":
    main()
