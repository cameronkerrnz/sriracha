import sys
import wx
import os
import threading
from pubsub import pub  # Use pypubsub instead
from collections.abc import MutableSet
from typing import Any, Iterable, Iterator, Optional, Set, List
from mbox_indexer import MBoxIndexer
from whoosh.fields import Schema, TEXT, ID, DATETIME, STORED
from whoosh.analysis import StemmingAnalyzer

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
    def __init__(self, subject: str, sender: str, recipients: list[str], date: str, body: str, tags: Optional[Iterable[str]] = None, marked: bool = False, attachments: Optional[list[Any]] = None, msg_id: Any = None):
        self.subject: str = subject
        self.sender: str = sender
        self.recipients: list[str] = recipients
        self.date: str = date
        self.body: str = body
        self.tags: Set[str] = set(tags) if tags else set()
        self.marked: bool = marked
        self.attachments: list[Any] = attachments or []
        self.msg_id: Any = msg_id
    def add_tag(self, tag: str) -> None:
        self.tags.add(tag)
    def remove_tag(self, tag: str) -> None:
        self.tags.discard(tag)
    def toggle_marked(self) -> None:
        self.marked = not self.marked
    def __repr__(self) -> str:
        return f"<Message subject={self.subject!r} sender={self.sender!r} date={self.date!r} tags={sorted(self.tags)} marked={self.marked}>"

class MessageCollection:
    """
    Container for Message objects, with helper methods for filtering, searching, etc.
    Maintains an ordered set of all tags present in the collection.
    """
    def __init__(self, messages: Optional[Iterable[Message]] = None, tags: Optional[Iterable[str]] = None):
        self.messages: list[Message] = list(messages) if messages else []
        # Aggregate tags from messages if not provided
        if tags is not None:
            self.tags = OrderedSet(tags)
        else:
            tag_set = OrderedSet()
            for msg in self.messages:
                for tag in msg.tags:
                    tag_set.add(tag)
            self.tags = tag_set
    def add(self, message: Message) -> None:
        self.messages.append(message)
        for tag in message.tags:
            self.tags.add(tag)
    def get_marked(self) -> list[Message]:
        return [msg for msg in self.messages if msg.marked]
    def filter_by_tags(self, tags: Iterable[str]) -> 'MessageCollection':
        tag_set = set(tags)
        filtered = [msg for msg in self.messages if msg.tags & tag_set]
        # Only include tags present in filtered messages
        filtered_tags = OrderedSet()
        for msg in filtered:
            for tag in msg.tags:
                filtered_tags.add(tag)
        return MessageCollection(filtered, tags=filtered_tags)
    def __getitem__(self, idx: int) -> Message:
        return self.messages[idx]
    def __len__(self) -> int:
        return len(self.messages)
    def __iter__(self) -> Iterator[Message]:
        return iter(self.messages)
    def __repr__(self) -> str:
        return f"<MessageCollection n={len(self.messages)} messages>"
    def tag_visible_counts(self, enabled_tags: Set[str]) -> dict[str, int]:
        """
        For each tag, return the number of messages with that tag that are currently visible.
        """
        counts = {}
        for message in self.messages:
            message_is_visible = message.tags & enabled_tags
            for tag in message.tags:
                if message_is_visible:
                    if tag not in counts:
                        counts[tag] = 0
                    counts[tag] += 1
        return counts

class MainFrame(wx.Frame):
    def __init__(self, parent, title: str, mbox_path: Optional[str] = None):
        super().__init__(parent, title=title, size=wx.Size(900, 700))
        self.mbox_path: Optional[str] = mbox_path
        self.index_exists: bool = False
        self.messages: MessageCollection = MessageCollection()
        self.enabled_tags: Set[str] = set()
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

        # Remove the info_label entirely
        # hbox_file = wx.BoxSizer(wx.HORIZONTAL)
        # self.info_label = wx.StaticText(panel, label="")
        # hbox_file.Add(self.info_label, flag=wx.ALL|wx.ALIGN_CENTER_VERTICAL, border=5)
        # vbox.Add(hbox_file, flag=wx.EXPAND)

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

        hbox_main = wx.BoxSizer(wx.HORIZONTAL)
        self.results_list = wx.ListBox(panel)
        self.results_list.Bind(wx.EVT_LISTBOX, self.on_select_message)
        self.results_list.Disable()
        hbox_main.Add(self.results_list, proportion=1, flag=wx.EXPAND|wx.ALL, border=5)

        right_panel = wx.BoxSizer(wx.VERTICAL)
        self.message_view = wx.TextCtrl(panel, style=wx.TE_MULTILINE|wx.TE_READONLY)
        right_panel.Add(self.message_view, proportion=1, flag=wx.EXPAND|wx.ALL, border=5)
        hbox_actions = wx.BoxSizer(wx.HORIZONTAL)
        self.mark_btn = wx.Button(panel, label="Mark/Unmark")
        self.mark_btn.Bind(wx.EVT_BUTTON, self.on_mark)
        self.mark_btn.Disable()
        hbox_actions.Add(self.mark_btn, flag=wx.ALL, border=5)
        self.export_btn = wx.Button(panel, label="Export Marked")
        self.export_btn.Bind(wx.EVT_BUTTON, self.on_export)
        self.export_btn.Disable()
        hbox_actions.Add(self.export_btn, flag=wx.ALL, border=5)
        self.tag_btn = wx.Button(panel, label="Apply/Clear Tag")
        self.tag_btn.Bind(wx.EVT_BUTTON, self.on_tag)
        self.tag_btn.Disable()
        hbox_actions.Add(self.tag_btn, flag=wx.ALL, border=5)
        right_panel.Add(hbox_actions, flag=wx.ALIGN_LEFT)
        hbox_main.Add(right_panel, proportion=2, flag=wx.EXPAND)
        vbox.Add(hbox_main, proportion=1, flag=wx.EXPAND)

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
        if not force_rebuild and os.path.exists(index_dir):
            self.set_status(f"Index already exists for {os.path.basename(path)}. Ready.")
            self.progress.Hide()
            self.index_exists = True
            self.search_box.Enable()
            self.results_list.Enable()
            self.export_btn.Enable()
            self.enabled_tags = set()
            self.update_tag_badges()
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
        self.indexer = MBoxIndexer(
            mbox_files=mbox_files,
            index_dir=index_dir,
            schema=schema,
            progress_callback=progress_callback,
            message_callback=message_callback,
            status_callback=status_callback
        )
        def on_index_complete():
            self.index_exists = True
            self.search_box.Enable()
            self.results_list.Enable()
            self.export_btn.Enable()
            self.enabled_tags = set()
            self.update_tag_badges()
            if self.mbox_path:
                self.set_status(f"Indexed: {os.path.basename(self.mbox_path)}")
                self.SetTitle(f"Desktop Picnic — {os.path.basename(self.mbox_path)}")
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
            tags = set(random.sample(tag_list, num_tags))
            msg = Message(subject, sender, recipients, date, body, tags=tags, marked=False, msg_id=i+1)
            self.messages.add(msg)
        self.enabled_tags = set(self.messages.tags)
        self.update_tag_badges()
        if self.mbox_path:
            self.set_status(f"Indexed: {os.path.basename(self.mbox_path)}")
            self.SetTitle(f"Desktop Picnic — {os.path.basename(self.mbox_path)}")
        self.show_message_list()

    def show_message_list(self, filter_tags=None):
        # Show messages filtered by tags if provided, else all
        if filter_tags is None:
            filter_tags = self.enabled_tags
        filtered = self.messages if not filter_tags else self.messages.filter_by_tags(filter_tags)
        display = [f"{'* ' if msg.marked else ''}{msg.subject} [{', '.join(sorted(msg.tags))}]" for msg in filtered]
        self.results_list.Set(display)
        self.set_status(f"Filtering by tags: {', '.join(sorted(filter_tags))}")

    def filter_results_by_tags(self):
        self.show_message_list()

    def on_select_message(self, event):
        idx = self.results_list.GetSelection()
        if idx != wx.NOT_FOUND:
            filter_tags = self.enabled_tags
            filtered = self.messages if not filter_tags else self.messages.filter_by_tags(filter_tags)
            msg = filtered[idx]
            self.show_message_content(msg)
            self.mark_btn.Enable()
            self.tag_btn.Enable()
        else:
            self.message_view.SetValue("")
            self.mark_btn.Disable()
            self.tag_btn.Disable()

    def show_message_content(self, msg):
        content = f"Subject: {msg.subject}\nFrom: {msg.sender}\nTo: {', '.join(msg.recipients)}\nDate: {msg.date}\nTags: {', '.join(sorted(msg.tags))}\n\n{msg.body}"
        self.message_view.SetValue(content)

    def on_mark(self, event):
        idx = self.results_list.GetSelection()
        if idx != wx.NOT_FOUND:
            filter_tags = self.enabled_tags
            filtered = self.messages if not filter_tags else self.messages.filter_by_tags(filter_tags)
            msg = filtered[idx]
            msg.toggle_marked()
            self.show_message_list()
            self.results_list.SetSelection(idx)

    def on_export(self, event):
        wx.MessageBox("Exporting marked messages (not implemented)", "Export", wx.OK | wx.ICON_INFORMATION)

    def on_tag(self, event):
        idx = self.results_list.GetSelection()
        if idx != wx.NOT_FOUND:
            filter_tags = self.enabled_tags
            filtered = self.messages if not filter_tags else self.messages.filter_by_tags(filter_tags)
            msg = filtered[idx]
            # For demo: toggle the first enabled tag
            if self.enabled_tags:
                tag = next(iter(self.enabled_tags))
                if tag in msg.tags:
                    msg.remove_tag(tag)
                else:
                    msg.add_tag(tag)
                self.show_message_list()
                self.results_list.SetSelection(idx)
                self.show_message_content(msg)
            self.update_tag_badges()

    def update_tag_badges(self) -> None:
        for child in self.tag_panel.GetChildren():
            child.Destroy()
        self.tag_sizer.Clear()
        tag_counts = self.messages.tag_visible_counts(self.enabled_tags)
        for idx, tag in enumerate(self.messages.tags):
            label = f"{tag} ({tag_counts.get(tag, 0)})"
            btn = wx.ToggleButton(self.tag_panel, label=label, size=wx.Size(80, 24))
            btn.SetValue(tag in self.enabled_tags)
            btn.Bind(wx.EVT_TOGGLEBUTTON, lambda evt, t=tag: self.on_toggle_tag(evt, t))
            btn.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            btn.SetMinSize(wx.Size(60, 24))
            btn.SetMaxSize(wx.Size(120, 24))
            btn.SetToolTip(f"Filter by tag: {tag}")
            self.tag_sizer.Add(btn, flag=wx.RIGHT|wx.BOTTOM, border=4)
        self.tag_panel.Layout()
        self.tag_panel.Fit()
        self.tag_panel.Refresh()
        self.tag_panel.GetParent().Layout()
        self.filter_results_by_tags()

    def on_toggle_tag(self, event, tag):
        if not hasattr(self, 'enabled_tags'):
            self.enabled_tags = set(self.messages.tags)
        if event.GetEventObject().GetValue():
            self.enabled_tags.add(tag)
        else:
            self.enabled_tags.discard(tag)
        self.filter_results_by_tags()
        self.update_tag_badges()

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
        query = self.search_box.GetValue().lower()
        filtered = MessageCollection([msg for msg in self.messages if query in msg.subject.lower() or query in msg.body.lower()])
        display = [f"{'* ' if msg.marked else ''}{msg.subject} [{', '.join(sorted(msg.tags))}]" for msg in filtered]
        self.results_list.Set(display)
        self.set_status(f"Search results for: {query}")

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
