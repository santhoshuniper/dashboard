# Data Chatbot Prototype

Quick prototype that reads two data Excel files, a data-definition Excel, and a cheat-sheet (Excel or text), then exposes an interactive chatbot CLI that sends queries to a GPT model.

Installation
```
pip install -r requirements.txt
```

Example (run from the `dashboard` folder):
```
python src/data_chatbot.py --data tmp/data1.xlsx tmp/data2.xlsx --data-def tmp/data_def.xlsx --cheat tmp/cheat.xlsx --api-key YOUR_OPENAI_KEY
```

Notes
- If `--api-key` or `OPENAI_API_KEY` is not provided, the script will print the generated chat messages JSON instead of calling the API (useful for offline testing).
- The cheat sheet may be an Excel file or a plain text file. Data-def should ideally contain `column` and `description` columns.
