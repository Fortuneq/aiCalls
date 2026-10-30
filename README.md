# aiCalls — automated sales-call analysis

A Python port of an n8n workflow that analyses sales calls end to end:

1. watches a Google Drive folder for new audio recordings
2. downloads and transcribes them with OpenAI Whisper
3. labels the speakers (salesperson / client)
4. runs an AI review of the call: sales-process stages and a quality checklist
5. writes the results to Google Sheets

The original n8n workflow export is included as JSON, along with HTML exports of the sheet templates (analysis columns and the checklist).

## Setup

```bash
pip install -r requirements.txt
```

1. Create a Google Cloud project, enable the Drive and Sheets APIs, create a service account and download its JSON key.
2. Share the Drive folder and the target spreadsheet with the service account.
3. Run the script once to generate `config.json`, then fill it in:

```bash
python call_automation.py
```

```json
{
  "openai_api_key": "<your OpenAI key>",
  "google_credentials_path": "<path to service-account.json>",
  "google_drive_folder_id": "<Drive folder id>",
  "spreadsheet_id": "<Google Sheet id>",
  "analysis_sheet_name": "Call analysis",
  "checklist_sheet_name": "Checklist",
  "manager_names": ["Alice"],
  "company_name": "Acme"
}
```

## Stack

Python, OpenAI API (Whisper + GPT), Google Drive API, Google Sheets (gspread).

A more complete version of this idea, with a database and a web dashboard, lives in [voiceAI](https://github.com/Fortuneq/voiceAI).
