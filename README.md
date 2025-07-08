# Sriracha - Makes Takeout Better

Sriracha is a fast desktop email viewer for large mbox archives. It will be of particular interest to those who need to quickly discover and report on email from the likes of past employees. It specifically aims to leave data in-place and the MBOX data can remain housed on a Windows fileshare / Samba share.

## Description

- Developed against a Google Takeout MBOX (800MB zipped)
- Operate on a single MBOX at a time
- Content is indexed for *fast* querying (slower on a Windows fileshare)
- Google Mail's labels can be used for filtering in/out
- By default only the matched passages are shown, but can toggle to show full message
- Message display is rudimentary; plain text.
- Individual messages can be exported as `*.eml` files to use as needed.

**INDEX FORMAT WILL CHANGE:** This software is in early stages of development. While the MBOX source files will remain read-only, the index it creates (currently `<name>.whoosh-index` alongside the `<name>.mbox`) will change as new features are added, so don't expect to keep the indexes between versions. 

## Interoperability

### Supported Platforms

Basic principle is to build on the oldest versions of operating systems that can build on GitHub Actions:

- macOS 14+ (on Apple Silicon / ARM64)
- Windows Server 2022 / Windows 10  (x86_64)
- Linux (Ubuntu 22.04 LTS x86_64) or similar age via AppImage

### MBOX Sources

- Google Takeout ("All mail Including Spam and Trash.mbox")

### Using `*.eml` files

If you have an email client like Thunderbird, Outlook, macOS Mail, you can do the following with an exported message:

- Double-click to view
- [macOS] quickview is convenient
- Drag into message-list/folder to import
- Drag onto a compose window to attach

Google Mail / Gmail web application is more limited; but these limitations do not apply if using a more regular email client to access your Google Mail.

- Drag onto a compose window to attach, but cannot view.

## Current development ideas

- HTML view (sanitised; stripped of remote content and javascript):
  - Don't have suitable sandboxing mechanisms
- Better search interface
- Make the message-list look more like an email client
- Data exploration tools (eg. network graphs, conversation lists, timelines)

## Using the Source

Install dependencies in a virtual environment:

```bash
git clone https://github.com/cameronkerrnz/sriracha.git
cd sriracha
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Note** that installing wxPython via pip for Linux will greatly benefit from installing the appropriate binary wheels according to your OS release and the version of GTK. See the build.yml for examples.

See `.github/workflows/build.yml` for build steps for macOS, Windows and Linux.

## License

This project is licensed under the GPLv3 License - see the [LICENSE](LICENSE) file for details and [NOTICES](NOTICES) regarding licences of dependencies.

