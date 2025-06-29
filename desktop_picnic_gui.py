import sys
import wx
import os
import threading
import json
from pubsub import pub  # Use pypubsub instead
from collections.abc import MutableSet
from typing import Any, Iterable, Iterator, Optional, Set, List
from mbox_indexer import MBoxIndexer
from mbox_query import MBoxQuery

class OrderedSet(MutableSet):
    def __init__(self, iterable: Optional[Iterable[Any]] = None):
        self._dict = dict()
        if iterable:
            for value in iterable:
                self._dict[value] = None
    def __contains__(self, value: Any) -> bool:
        return value in self._dict
    def __iter__(self) -> Iterator[Any]:
        return iter(self._dict.keys())
    def __len__(self) -> int:
        return len(self._dict)
    def add(self, value: Any) -> None:
        self._dict[value] = None
    def discard(self, value: Any) -> None:
        self._dict.pop(value, None)
    def __repr__(self) -> str:
        return f"OrderedSet({list(self._dict.keys())})"
    def to_list(self) -> List[Any]:
        return list(self._dict.keys())

class IndexThread(threading.Thread):
    def __init__(self, mbox_path, callback):
        super().__init__()
        self.mbox_path = mbox_path
        self.callback = callback

    def run(self):
        import time
        steps = 10
        delay = 0.03
        for i in range(steps + 1):
            wx.CallAfter(pub.sendMessage, 'update_progress', value=int(i * 100 / steps))
            time.sleep(delay)
        wx.CallAfter(lambda: self.callback(None))

class Message:
    """
    Represents a single email message, including metadata and app-specific fields.
    """
    def __init__(self, subject: str, sender: str, recipients: list[str], date: str, body: str, labels: Optional[Iterable[str]] = None, marked: bool = False, attachments: Optional[list[Any]] = None, msg_id: Any = None):
        self.subject: str = subject
        self.sender: str = sender
        self.recipients: list[str] = recipients
        self.date: str = date
        self.body: str = body
        self.labels: Set[str] = set(labels) if labels else set()
        self.marked: bool = marked
        self.attachments: list[Any] = attachments or []
        self.msg_id: Any = msg_id
    def add_label(self, label: str) -> None:
        self.labels.add(label)
    def remove_label(self, label: str) -> None:
        self.labels.discard(label)
    def toggle_marked(self) -> None:
        self.marked = not self.marked
    def __repr__(self) -> str:
        return f"<Message subject={self.subject!r} sender={self.sender!r} date={self.date!r} labels={sorted(self.labels)} marked={self.marked}>"

class MessageCollection:
    """
    Container for Message objects, with helper methods for filtering, searching, etc.
    Maintains an ordered set of all labels present in the collection.
    """
    def __init__(self, messages: Optional[Iterable[Message]] = None, labels: Optional[Iterable[str]] = None):
        self.messages: list[Message] = list(messages) if messages else []
        # Aggregate labels from messages if not provided
        if labels is not None:
            self.labels = OrderedSet(labels)
        else:
            label_set = OrderedSet()
            for msg in self.messages:
                for label in msg.labels:
                    label_set.add(label)
            self.labels = label_set
    def add(self, message: Message) -> None:
        self.messages.append(message)
        for label in message.labels:
            self.labels.add(label)
    def get_marked(self) -> list[Message]:
        return [msg for msg in self.messages if msg.marked]
    def filter_by_labels(self, labels: Iterable[str]) -> 'MessageCollection':
        label_set = set(labels)
        filtered = [msg for msg in self.messages if msg.labels & label_set]
        filtered_labels = OrderedSet()
        for msg in filtered:
            for label in msg.labels:
                filtered_labels.add(label)
        return MessageCollection(filtered, labels=filtered_labels)
    def __getitem__(self, idx: int) -> Message:
        return self.messages[idx]
    def __len__(self) -> int:
        return len(self.messages)
    def __iter__(self) -> Iterator[Message]:
        return iter(self.messages)
    def __repr__(self) -> str:
        return f"<MessageCollection n={len(self.messages)} messages>"
    def label_visible_counts(self, enabled_labels: Set[str]) -> dict[str, int]:
        counts = {}
        for message in self.messages:
            message_is_visible = message.labels & enabled_labels
            for label in message.labels:
                if message_is_visible:
                    if label not in counts:
                        counts[label] = 0
                    counts[label] += 1
        return counts

class MainFrame(wx.Frame):
    def __init__(self, parent, title: str, mbox_path: Optional[str] = None):
        super().__init__(parent, title=title, size=wx.Size(1200, 700))
        self.mbox_path: Optional[str] = mbox_path
        self.index_exists: bool = False
        self.messages: MessageCollection = MessageCollection()
        self.enabled_labels: Set[str] = set()
        self.aggregate_label_counts: dict[str, int] = {}
        self.query_engine: Optional[MBoxQuery] = None
        self.init_ui()
        pub.subscribe(self.update_progress, 'update_progress')
        self.Bind(wx.EVT_CLOSE, self.on_close)
        if self.mbox_path:
            wx.CallAfter(self.open_mbox_path, self.mbox_path)

    def init_ui(self):
        menubar = wx.MenuBar()
        # File menu
        file_menu = wx.Menu()
        open_item = file_menu.Append(wx.ID_OPEN, "&Open...\tCtrl+O", "Open MBOX file")
        rebuild_index_id = wx.NewIdRef()
        rebuild_item = file_menu.Append(rebuild_index_id, "Rebuild &Index", "Rebuild the index for the current MBOX file")
        quit_item = file_menu.Append(wx.ID_EXIT, "&Quit\tCtrl+Q", "Quit Desktop Picnic")
        menubar.Append(file_menu, "&File")
        # Help menu
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, "&About\tF1", "About Desktop Picnic")
        menubar.Append(help_menu, "&Help")
        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, self.on_open_menu, open_item)
        self.Bind(wx.EVT_MENU, self.on_rebuild_index_menu, rebuild_item)
        self.Bind(wx.EVT_MENU, self.on_quit_menu, quit_item)
        self.Bind(wx.EVT_MENU, self.on_about_menu, about_item)

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        hbox_search = wx.BoxSizer(wx.HORIZONTAL)
        self.search_box = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_box.SetHint("Search emails...")
        self.search_box.Bind(wx.EVT_TEXT_ENTER, self.on_search)
        self.search_box.Disable()
        hbox_search.Add(self.search_box, proportion=1, flag=wx.EXPAND|wx.ALL, border=5)
        vbox.Add(hbox_search, flag=wx.EXPAND)

        # Tag toggle badges row (under search box)
        self.tag_panel = wx.Panel(panel)
        self.tag_sizer = wx.WrapSizer(wx.HORIZONTAL)
        self.tag_panel.SetSizer(self.tag_sizer)
        # Use proportion=0 so tag_panel resizes and pushes down the rest of the layout
        vbox.Add(self.tag_panel, proportion=0, flag=wx.ALL|wx.EXPAND, border=5)

        # Main horizontal splitter: message list (left) and message view/actions (right)
        self.splitter = wx.SplitterWindow(panel, style=wx.SP_LIVE_UPDATE)
        self.splitter.SetMinimumPaneSize(100)

        # Left: results list
        left_panel = wx.Panel(self.splitter)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        self.results_list = wx.ListBox(left_panel)
        self.results_list.Bind(wx.EVT_LISTBOX, self.on_select_message)
        self.results_list.Disable()
        left_sizer.Add(self.results_list, proportion=1, flag=wx.EXPAND|wx.ALL, border=5)
        left_panel.SetSizer(left_sizer)

        # Right: message view and actions
        right_panel = wx.Panel(self.splitter)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        self.message_view = wx.TextCtrl(right_panel, style=wx.TE_MULTILINE|wx.TE_READONLY)
        right_sizer.Add(self.message_view, proportion=1, flag=wx.EXPAND|wx.ALL, border=5)
        hbox_actions = wx.BoxSizer(wx.HORIZONTAL)
        self.mark_btn = wx.Button(right_panel, label="Mark/Unmark")
        self.mark_btn.Bind(wx.EVT_BUTTON, self.on_mark)
        self.mark_btn.Disable()
        hbox_actions.Add(self.mark_btn, flag=wx.ALL, border=5)
        self.export_btn = wx.Button(right_panel, label="Export Marked")
        self.export_btn.Bind(wx.EVT_BUTTON, self.on_export)
        self.export_btn.Disable()
        hbox_actions.Add(self.export_btn, flag=wx.ALL, border=5)
        self.tag_btn = wx.Button(right_panel, label="Apply/Clear Tag")
        self.tag_btn.Bind(wx.EVT_BUTTON, self.on_tag)
        self.tag_btn.Disable()
        hbox_actions.Add(self.tag_btn, flag=wx.ALL, border=5)
        right_sizer.Add(hbox_actions, flag=wx.ALIGN_LEFT)
        right_panel.SetSizer(right_sizer)

        # Add panels to splitter
        self.splitter.SplitVertically(left_panel, right_panel, sashPosition=int(self.GetSize().GetWidth() * 0.33))

        vbox.Add(self.splitter, proportion=1, flag=wx.EXPAND)

        # Status bar at the bottom
        status_hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.status_msg = wx.StaticText(panel, label="Ready.")
        status_hbox.Add(self.status_msg, proportion=1, flag=wx.ALIGN_LEFT|wx.ALL|wx.EXPAND, border=5)
        self.progress = wx.Gauge(panel, range=100, size=wx.Size(200, 16))
        # self.progress.Hide()
        status_hbox.Add(self.progress, flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL, border=5)
        vbox.Add(status_hbox, flag=wx.EXPAND|wx.BOTTOM, border=2)

        panel.SetSizer(vbox)

    def set_status(self, msg):
        self.status_msg.SetLabel(msg)

    def open_mbox_path(self, path, force_rebuild: bool = False):
        self.mbox_path = path
        self.SetTitle(f"Desktop Picnic — {os.path.basename(path)}")
        mbox_dir = os.path.dirname(path)
        mbox_base = os.path.splitext(os.path.basename(path))[0]
        index_dir = os.path.join(mbox_dir, mbox_base + ".whoosh-index")
        # Load aggregate label counts if present
        agg_path = os.path.join(index_dir, 'aggregate_labels.json')
        if os.path.exists(agg_path):
            try:
                with open(agg_path, 'r', encoding='utf-8') as f:
                    self.aggregate_label_counts = json.load(f)
            except Exception:
                self.aggregate_label_counts = {}
        else:
            self.aggregate_label_counts = {}
        if not force_rebuild and os.path.exists(index_dir):
            self.set_status(f"Index already exists for {os.path.basename(path)}. Ready.")
            self.progress.Hide()
            self.index_exists = True
            self.search_box.Enable()
            self.search_box.SetFocus()  # Ensure search box is focused
            self.results_list.Enable()
            self.export_btn.Enable()
            self.enabled_labels = set(self.aggregate_label_counts.keys())
            self.label_filter_states = {l: 'off' for l in self.aggregate_label_counts.keys()}
            self.update_label_badges()
            self.query_engine = MBoxQuery(index_dir)
            return
        self.set_status(f"Indexing {os.path.basename(path)}...")
        self.progress.SetValue(0)
        self.progress.Show()
        self.index_exists = False
        self.disable_all()
        mbox_files = [path]
        def status_callback(msg: str):
            import re
            def shorten_path(text):
                return re.sub(r'([/\\][^/\\]+)+', lambda m: os.path.basename(m.group(0)), text)
            short_msg = shorten_path(msg)
            wx.CallAfter(self.set_status, short_msg)
            if "indexed" in short_msg.lower() or "all mbox files indexed" in short_msg.lower() or "completed indexing" in short_msg.lower():
                wx.CallAfter(self.progress.Hide)
        def progress_callback(mbox_path: str, percent: int, processed: int):
            wx.CallAfter(self.progress.SetValue, percent)
            if percent >= 100:
                wx.CallAfter(self.progress.Hide)
        def message_callback(mbox_path: str, idx: int, msg):
            pass
        self.indexer = MBoxIndexer(
            mbox_files=mbox_files,
            index_dir=index_dir,
            progress_callback=progress_callback,
            message_callback=message_callback,
            status_callback=status_callback
        )
        def on_index_complete():
            self.index_exists = True
            self.search_box.Enable()
            self.search_box.SetFocus()  # Ensure search box is focused
            self.results_list.Enable()
            self.export_btn.Enable()
            self.label_filter_states = {l: 'off' for l in self.aggregate_label_counts.keys()}
            self.update_label_badges()
            if self.mbox_path:
                self.set_status(f"Indexed: {os.path.basename(self.mbox_path)}")
                self.SetTitle(f"Desktop Picnic — {os.path.basename(self.mbox_path)}")
            if os.path.exists(index_dir):
                self.query_engine = MBoxQuery(index_dir)
            self.progress.Hide()
        def wait_for_indexer():
            if self.indexer.is_alive():
                wx.CallLater(100, wait_for_indexer)
            else:
                wx.CallAfter(on_index_complete)
        self.indexer.start()
        wait_for_indexer()

    def open_mbox(self, event):
        with wx.FileDialog(self, "Select MBOX File", wildcard="MBOX files (*.mbox)|*.mbox|All files (*.*)|*.*", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                self.set_status("No MBOX file selected.")
                return
            path = fileDialog.GetPath()
            self.open_mbox_path(path)

    def update_progress(self, value):
        self.progress.SetValue(value)
        if value == 100:
            self.progress.Hide()
            self.set_status("Indexing complete.")
        else:
            self.set_status(f"Indexing... {value}%")

    def on_index_complete(self, _=None):
        import random
        self.index_exists = True
        self.search_box.Enable()
        self.search_box.SetFocus()  # Ensure search box is focused
        self.results_list.Enable()
        self.export_btn.Enable()
        tag_list = [
            "work", "personal", "family", "finance", "travel", "urgent", "spam"
        ]
        self.messages = MessageCollection()
        for i in range(20):
            subject = f"Message {i+1} Subject"
            sender = f"sender{i+1}@example.com"
            recipients = [f"recipient{i+1}@example.com"]
            date = f"2025-06-{i%30+1:02d}"
            body = f"This is the body of message {i+1}."
            num_tags = random.randint(1, 3)
            labels = set(random.sample(tag_list, num_tags))
            msg = Message(subject, sender, recipients, date, body, labels=labels, marked=False, msg_id=i+1)
            self.messages.add(msg)
        self.enabled_labels = set(self.messages.labels)
        self.label_filter_states = {l: 'off' for l in self.aggregate_label_counts.keys()}
        self.update_label_badges()
        if self.mbox_path:
            self.set_status(f"Indexed: {os.path.basename(self.mbox_path)}")
            self.SetTitle(f"Desktop Picnic — {os.path.basename(self.mbox_path)}")
        self.show_message_list()

    def show_message_list(self, filter_labels=None):
        # Show messages filtered by tags if provided, else all
        if filter_labels is None:
            filter_labels = self.enabled_labels
        filtered = self.messages if not filter_labels else self.messages.filter_by_labels(filter_labels)
        display = [f"{'* ' if msg.marked else ''}{msg.subject} [{', '.join(sorted(msg.labels))}]" for msg in filtered]
        self.results_list.Set(display)
        self.set_status(f"Filtering by labels: {', '.join(sorted(filter_labels))}")

    def filter_results_by_labels(self):
        # Tri-state filtering: include, exclude, off
        include_labels = {l for l, s in self.label_filter_states.items() if s == 'include'}
        exclude_labels = {l for l, s in self.label_filter_states.items() if s == 'exclude'}
        # If all are off, no filtering
        if not include_labels and not exclude_labels:
            filtered = self._search_results if hasattr(self, '_search_results') and self._search_results else self.messages
        else:
            # Filter search results or in-memory messages
            base = self._search_results if hasattr(self, '_search_results') and self._search_results else self.messages
            filtered = []
            for hit in base:
                # hit can be dict (search) or Message (in-memory)
                if isinstance(hit, dict):
                    labels = hit.get('labels', '')
                    labels_set = set(l.strip() for l in labels.split(',') if l.strip())
                else:
                    labels_set = set(getattr(hit, 'labels', []))
                if include_labels and not (include_labels <= labels_set):
                    continue
                if exclude_labels and (exclude_labels & labels_set):
                    continue
                filtered.append(hit)
        display = [f"{'* ' if (r.get('marked', False) if isinstance(r, dict) else r.marked) else ''}{r.get('subject', '') if isinstance(r, dict) else r.subject} [{r.get('sender', '') if isinstance(r, dict) else r.sender}]" for r in filtered]
        self.results_list.Set(display)
        self._filtered_results = filtered
        if include_labels or exclude_labels:
            self.set_status(f"Label filter: +{', '.join(sorted(include_labels))} -{', '.join(sorted(exclude_labels))} ({len(filtered)} shown)")
        else:
            self.set_status(f"No label filter ({len(filtered)} shown)")

    def on_select_message(self, event):
        idx = self.results_list.GetSelection()
        if idx != wx.NOT_FOUND:
            # Use filtered search results if present
            if hasattr(self, '_filtered_results') and self._filtered_results and idx < len(self._filtered_results):
                hit = self._filtered_results[idx]
                if isinstance(hit, dict):
                    labels = hit.get('labels', '')
                    labels_list = labels.split(',') if labels else []
                    # Display headers in typical order: From, To, Cc, Bcc, Date, Subject, Labels
                    content = (
                        f"From: {hit.get('sender', '')}\n"
                        f"To: {hit.get('recipients', '')}\n"
                        f"Date: {hit.get('date', '')}\n"
                        f"Subject: {hit.get('subject', '')}\n"
                        f"Labels: {', '.join(labels_list)}\n\n"
                        f"{hit.get('body', '')}"
                    )
                    self.message_view.SetValue(content)
                    self.mark_btn.Disable()
                    self.tag_btn.Disable()
                    return
            # Fallback to regular message display if no search results
            filter_labels = self.enabled_labels
            filtered = self.messages if not filter_labels else self.messages.filter_by_labels(filter_labels)
            msg = filtered[idx]
            self.show_message_content(msg)
            self.mark_btn.Enable()
            self.tag_btn.Enable()
        else:
            self.message_view.SetValue("")
            self.mark_btn.Disable()
            self.tag_btn.Disable()

    def show_message_content(self, msg):
        content = (
            f"From: {msg.sender}\n"
            f"To: {', '.join(msg.recipients)}\n"
            f"Date: {msg.date}\n"
            f"Subject: {msg.subject}\n"
            f"Tags: {', '.join(sorted(msg.labels))}\n\n"
            f"{msg.body}"
        )
        self.message_view.SetValue(content)

    def on_mark(self, event):
        idx = self.results_list.GetSelection()
        if idx != wx.NOT_FOUND:
            filter_labels = self.enabled_labels
            filtered = self.messages if not filter_labels else self.messages.filter_by_labels(filter_labels)
            msg = filtered[idx]
            msg.toggle_marked()
            self.show_message_list()
            self.results_list.SetSelection(idx)

    def on_export(self, event):
        wx.MessageBox("Exporting marked messages (not implemented)", "Export", wx.OK | wx.ICON_INFORMATION)

    def on_tag(self, event):
        idx = self.results_list.GetSelection()
        if idx != wx.NOT_FOUND:
            filter_labels = self.enabled_labels
            filtered = self.messages if not filter_labels else self.messages.filter_by_labels(filter_labels)
            msg = filtered[idx]
            if self.enabled_labels:
                label = next(iter(self.enabled_labels))
                if label in msg.labels:
                    msg.remove_label(label)
                else:
                    msg.add_label(label)
                self.show_message_list()
                self.results_list.SetSelection(idx)
                self.show_message_content(msg)
            self.update_label_badges()

    def update_label_badges(self) -> None:
        for child in self.tag_panel.GetChildren():
            child.Destroy()
        self.tag_sizer.Clear()
        label_counts = self.aggregate_label_counts
        for idx, label in enumerate(sorted(label_counts.keys(), key=lambda s: s.lower())):
            count = label_counts.get(label, 0)
            # Remove 'Category ' prefix from button label, but keep in tooltip
            display_label = label
            tooltip_label = label
            if label.lower().startswith('category '):
                display_label = label[9:].lstrip()
            # Tri-state: off, include, exclude
            state = self.label_filter_states.get(label, 'off')
            if state == 'include':
                badge_label = f"{display_label} ({count}) +"
            elif state == 'exclude':
                badge_label = f"{display_label} ({count}) -"
            else:
                badge_label = f"{display_label} ({count})"
            btn = wx.ToggleButton(self.tag_panel, label=badge_label)
            btn.SetValue(state != 'off')
            btn.Bind(wx.EVT_TOGGLEBUTTON, lambda evt, l=label: self.on_cycle_label_state(evt, l))
            btn.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            btn.SetToolTip(f"Filter by label: {tooltip_label}\nClick to cycle: off → include (+) → exclude (-) → off")
            self.tag_sizer.Add(btn, flag=wx.RIGHT|wx.BOTTOM, border=4)
        self.tag_panel.Layout()
        self.tag_panel.Fit()
        self.tag_panel.Refresh()
        self.tag_panel.GetParent().Layout()
        self.filter_results_by_labels()

    def on_cycle_label_state(self, event, label):
        # Cycle: off → include → exclude → off
        state = self.label_filter_states.get(label, 'off')
        if state == 'off':
            self.label_filter_states[label] = 'include'
        elif state == 'include':
            self.label_filter_states[label] = 'exclude'
        else:
            self.label_filter_states[label] = 'off'
        self.update_label_badges()

    def disable_all(self):
        self.search_box.Disable()
        self.results_list.Disable()
        self.export_btn.Disable()
        self.mark_btn.Disable()
        self.tag_btn.Disable()
        self.message_view.SetValue("")

    def on_close(self, event):
        self.Destroy()
        wx.GetApp().ExitMainLoop()

    def on_open_menu(self, event):
        self.open_mbox(event)

    def on_quit_menu(self, event):
        self.Close()

    def on_about_menu(self, event):
        wx.MessageBox("Desktop Picnic\nA desktop MBOX search tool\n\u00A9 2025", "About Desktop Picnic", wx.OK | wx.ICON_INFORMATION)

    def on_search(self, event):
        query = self.search_box.GetValue().strip()
        if not query or not self.query_engine:
            self.set_status("No query or index loaded.")
            return
        # Use MBoxQuery to get results
        try:
            results = self.query_engine.search(query, limit=100)
        except Exception as e:
            self.set_status(f"Query error: {e}")
            return
        # Store results for selection, as list of dicts
        self._search_results = results
        self._filtered_results = results  # Initially, all results are shown
        self.filter_results_by_labels()

    def on_rebuild_index_menu(self, event):
        if self.mbox_path:
            self.open_mbox_path(self.mbox_path, force_rebuild=True)
        else:
            wx.MessageBox("No MBOX file is currently open.", "Rebuild Index", wx.OK | wx.ICON_INFORMATION)

class DesktopPicnicApp(wx.App):
    def OnInit(self):
        mbox_path = None
        if len(sys.argv) > 1:
            mbox_path = sys.argv[1]
        self.frame = MainFrame(None, "Desktop Picnic", mbox_path=mbox_path)
        self.frame.Show()
        return True

def main():
    app = DesktopPicnicApp(False)
    app.MainLoop()

if __name__ == "__main__":
    main()
