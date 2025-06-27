# Desktop Picnic

This is a desktop application which will allow a user to index and quickly
search the content in an email MBOX archive from Google Mail, as downloaded
using Google Takeout.

This can be useful for record-keeping compliance without needing to import
another user's MBOX data into an existing email application such as
Thunderbird, Mac Mail etc.

## Architecture

The MBOX data will be stored, and will remain, on a remote file system, accessible via SMB or similar. This is how access to the data will be controlled.

MBOX data must be considered read-only at all times, to maintain data in an evidentiary standard.

The index data will be stored alongside the MBOX data. For performance and functionality reasons, the index data will be copied locally temporarily, either into memory or temporary file.

    Note that into memory would be preferable, to prevent index data accidentally being synced up the cloud, as typically happens with data on a users Desktop.

The application should be able to be easily copied from the server and then run by the user. The application should appear as a single executable to the user. Different executables may be provided for Windows, macOS and Linux.

The application is a GUI desktop application using the QT framework, and the bulk of the application is written in Python. Content indexing will use the Whoosh.

## Important UI Functions

- Open an MBOX archive (MBOX & its index)
- Open an MBOX archive (MBOX which doesn't have an index yet) -- initiates index
- Search the archive according to common email search needs
- Mark/unmark messages according based on search results
- Mark/unmark messages manually
- Highlight matches in a message
- Highlight attachments containing matches
- Export marked messages in their source verbatim form
- Open attachments upon user request
- Apply or clear tags according to the user's needs (these tags go into the index)
- Toggle message list visibility to only show only certain tags.


## Milestones

### Milestone 1

- read email messages from a decompressed mbox file (Google Takeout for Gmail)
- populate a Whoosh index with a suitable email-related schema from each email message
- get the MBOX message for a result found in the search
- no UI at this stage

### Milestone 2

- initial UI
- prove that this can be done as a 'single-executable' deployment

### Milestone 3

- flesh out UI functions
- attachments out of scope for this milestone

### Milestone 4

- improve Whoosh schema and index common attachment metadata and content

### Milestone 5

- UI support for mail attachments

