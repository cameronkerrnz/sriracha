import sys
import wx
import os
import threading
from pubsub import pub  # Use pypubsub instead

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

class MainFrame(wx.Frame):
    def __init__(self, parent, title, mbox_path=None):
        super().__init__(parent, title=title, size=wx.Size(900, 700))
        self.mbox_path = mbox_path
        self.index_exists = False
        self.marked_messages = set()
        self.tags = set()
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
        quit_item = file_menu.Append(wx.ID_EXIT, "&Quit\tCtrl+Q", "Quit Desktop Picnic")
        menubar.Append(file_menu, "&File")
        # Help menu
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, "&About\tF1", "About Desktop Picnic")
        menubar.Append(help_menu, "&Help")
        self.SetMenuBar(menubar)
        self.Bind(wx.EVT_MENU, self.on_open_menu, open_item)
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

    def open_mbox_path(self, path):
        self.mbox_path = path
        self.set_status(f"Indexing {os.path.basename(path)}...")
        self.SetTitle(f"Desktop Picnic — {os.path.basename(path)}")
        self.progress.SetValue(0)
        self.progress.Show()
        self.index_exists = False
        self.disable_all()
        thread = IndexThread(self.mbox_path, self.on_index_complete)
        thread.start()

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

    def update_tag_badges(self, tags=None, selected=None):
        # tags: all available tags, selected: set of enabled tags
        if tags is None:
            tags = sorted(self.tags)
        if selected is None:
            # Default: all tags enabled
            selected = set(tags)
        self.enabled_tags = set(selected)
        # Remove old badges
        for child in self.tag_panel.GetChildren():
            child.Destroy()
        self.tag_sizer.Clear()
        for idx, tag in enumerate(tags):
            btn = wx.ToggleButton(self.tag_panel, label=tag, size=wx.Size(80, 24))
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
        # Also relayout the parent sizer to ensure the rest of the window resizes
        self.tag_panel.GetParent().Layout()
        self.filter_results_by_tags()

    def on_toggle_tag(self, event, tag):
        if not hasattr(self, 'enabled_tags'):
            self.enabled_tags = set(self.tags)
        if event.GetEventObject().GetValue():
            self.enabled_tags.add(tag)
        else:
            self.enabled_tags.discard(tag)
        self.filter_results_by_tags()

    def filter_results_by_tags(self):
        # Show messages that have ANY of the enabled tags
        if not hasattr(self, 'enabled_tags') or not self.enabled_tags:
            self.results_list.Set([])
            self.set_status("No tags enabled. No messages to display.")
            return
        filtered = []
        for msg, tags in self.message_tags.items():
            if tags & self.enabled_tags:
                tag_str = ', '.join(sorted(tags))
                filtered.append(f"{msg} [{tag_str}]")
        self.results_list.Set(filtered)
        self.set_status(f"Filtering by tags: {', '.join(sorted(self.enabled_tags))}")

    def on_index_complete(self, _=None):
        import random
        self.index_exists = True
        self.search_box.Enable()
        self.results_list.Enable()
        self.export_btn.Enable()
        # Expanded tag vocabulary (20 tags)
        self.tags = {
            "work", "personal", "legal", "family", "project", "urgent", "archive", "finance", "travel", "friends",
            "school", "medical", "shopping", "events", "photos", "inbox", "sent", "drafts", "spam", "misc"
        }
        # Assign a few random tags to each message for testing
        self.message_tags = {}
        tag_list = list(self.tags)
        for i in range(20):
            msg = f"Message {i+1}"
            num_tags = random.randint(1, 3)
            msg_tags = set(random.sample(tag_list, num_tags))
            self.message_tags[msg] = msg_tags
        self.update_tag_badges(tags=self.tags)  # Defaults to all enabled
        if self.mbox_path:
            self.set_status(f"Indexed: {os.path.basename(self.mbox_path)}")
            self.SetTitle(f"Desktop Picnic — {os.path.basename(self.mbox_path)}")
        # Assign 3-7 random tags to each message for testing
        self.message_tags = {}
        tag_list = list(self.tags)
        messages = []
        for i in range(20):
            msg = f"Message {i+1}"
            num_tags = random.randint(3, 7)
            msg_tags = set(random.sample(tag_list, num_tags))
            self.message_tags[msg] = msg_tags
            tag_str = ', '.join(sorted(msg_tags))
            messages.append(f"{msg} [{tag_str}]")
        self.results_list.Set(messages)

    def on_search(self, event):
        query = self.search_box.GetValue().lower()
        self.results_list.Set([f"Message {i+1}" for i in range(20) if query in f"message {i+1}"])

    def on_select_message(self, event):
        idx = self.results_list.GetSelection()
        if idx != wx.NOT_FOUND:
            self.message_view.SetValue(f"Full content of {self.results_list.GetString(idx)}\n\n[Highlight matches here]")
            self.mark_btn.Enable()
            self.tag_btn.Enable()
        else:
            self.message_view.SetValue("")
            self.mark_btn.Disable()
            self.tag_btn.Disable()

    def on_mark(self, event):
        idx = self.results_list.GetSelection()
        if idx != wx.NOT_FOUND:
            msg = self.results_list.GetString(idx)
            if msg in self.marked_messages:
                self.marked_messages.remove(msg)
                self.results_list.SetString(idx, msg)
            else:
                self.marked_messages.add(msg)
                self.results_list.SetString(idx, f"* {msg}")

    def on_export(self, event):
        wx.MessageBox("Exporting marked messages (not implemented)", "Export", wx.OK | wx.ICON_INFORMATION)

    def on_tag(self, event):
        wx.MessageBox("Apply/Clear tag (not implemented)", "Tag", wx.OK | wx.ICON_INFORMATION)

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
