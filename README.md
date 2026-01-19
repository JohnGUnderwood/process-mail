# Process Mail

A Python utility for processing and converting mailbox (mbox) files into structured JSONL format.

## Description

This tool reads mbox files from a specified directory, extracts email metadata and content, and exports them as JSONL (JSON Lines) files. Each email is assigned a deterministic UUID based on its key fields (subject, sender, recipient, and date).

## Features

- Processes multiple mbox files in batch
- Handles email encoding and decoding automatically
- Extracts email metadata (subject, from, to, date)
- Extracts email body content (plain text)
- Generates deterministic UUIDs (v5) for each email
- Exports emails in JSONL format for easy data processing
- Batches output into files of 1000 emails each
- Automatically deletes processed mbox files

## Requirements

- Python 3.x
- Standard library modules (no external dependencies required)

## Usage

1. Place your mbox files in the configured directory (default: `C:/Users/john/mbox/`)
2. Run the script:
   ```bash
   python import_mailbox.py
   ```
3. Processed emails will be saved to `processed_mail/<mbox_name>/` directory

## Output Format

Each email is exported as a JSON object with the following structure:

```json
{
  "uuid": "unique-identifier",
  "uuid_version": 5,
  "uuid_input": "subject|from|to|date",
  "subject": "Email subject",
  "from": "sender@example.com",
  "to": "recipient@example.com",
  "date": "Date header",
  "body": "Email body content"
}
```

## Configuration

Update the `mbox_dir` variable in the script to specify your mbox directory:

```python
mbox_dir = 'C:/Users/john/mbox/'
```

You can also adjust the `batch_size` variable to control how many emails are written per output file (default: 1000).

## Output Structure

```
processed_mail/
├── mailbox1/
│   ├── mailbox1_0.jsonl
│   ├── mailbox1_1.jsonl
│   └── ...
└── mailbox2/
    ├── mailbox2_0.jsonl
    └── ...
```

## Notes

- The script automatically creates the `processed_mail` directory if it doesn't exist
- Original mbox files are **deleted** after successful processing
- Email bodies are extracted from `text/plain` MIME parts only
- Character encoding errors are handled gracefully with replacement characters

## License

MIT
