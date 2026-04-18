from typing import Optional, List, Dict
import os
import json
import pandas as pd
try:
    import openai
except Exception:
    openai = None


class DataChatbot:
    def __init__(self, data_paths: List[str], data_def_path: str, cheat_sheet_path: str, model: str = "gpt-4o-mini", openai_api_key: Optional[str] = None, max_preview_rows: int = 5):
        self.data_paths = data_paths
        self.data_def_path = data_def_path
        self.cheat_sheet_path = cheat_sheet_path
        self.model = model
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        self.max_preview_rows = max_preview_rows
        self.dfs: List[pd.DataFrame] = []
        self.data_def: Optional[pd.DataFrame] = None
        self.cheat: str = ""
        self._load_files()

        if self.openai_api_key and openai:
            openai.api_key = self.openai_api_key

    def _read_excel(self, path: str) -> pd.DataFrame:
        return pd.read_excel(path, engine="openpyxl")

    def _load_files(self) -> None:
        for p in self.data_paths:
            self.dfs.append(self._read_excel(p))
        try:
            self.data_def = self._read_excel(self.data_def_path)
        except Exception:
            self.data_def = pd.DataFrame()
        try:
            cheat_df = self._read_excel(self.cheat_sheet_path)
            self.cheat = cheat_df.to_csv(index=False)
        except Exception:
            try:
                with open(self.cheat_sheet_path, "r", encoding="utf-8") as f:
                    self.cheat = f.read()
            except Exception:
                self.cheat = ""

    def _df_preview(self, df: pd.DataFrame) -> str:
        return df.head(self.max_preview_rows).to_csv(index=False)

    def _data_def_text(self) -> str:
        if self.data_def is None or self.data_def.empty:
            return ""
        if set(["column", "description"]).issubset(self.data_def.columns):
            lines = []
            for _, r in self.data_def.iterrows():
                lines.append(f"{r['column']}: {r['description']}")
            return "\n".join(lines)
        return self.data_def.to_csv(index=False)

    def build_context(self, max_chars: int = 15000) -> str:
        parts: List[str] = []
        for i, df in enumerate(self.dfs, start=1):
            parts.append(f"DATA{i} file: {self.data_paths[i-1]}\nshape: {df.shape}\npreview:\n{self._df_preview(df)}")
        parts.append("DATA DEFINITIONS:\n" + self._data_def_text())
        parts.append("CHEAT SHEET:\n" + (self.cheat or ""))
        ctx = "\n\n".join(parts)
        if len(ctx) > max_chars:
            ctx = ctx[:max_chars]
        return ctx

    def generate_messages(self, user_query: str) -> List[Dict[str, str]]:
        system = "You are a helpful data assistant. Use the provided data files, data definitions, and cheat sheet to answer queries precisely and state assumptions when needed."
        context = self.build_context()
        user_content = context + "\n\nUser query:\n" + user_query
        return [{"role": "system", "content": system}, {"role": "user", "content": user_content}]

    def answer_query(self, user_query: str, temperature: float = 0.2) -> str:
        messages = self.generate_messages(user_query)
        if not self.openai_api_key or openai is None:
            return json.dumps({"messages": messages}, indent=2)
        resp = openai.ChatCompletion.create(model=self.model, messages=messages, temperature=temperature)
        return resp["choices"][0]["message"]["content"].strip()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Data-driven chatbot: load two data excels, a data-def excel and a cheat-sheet excel/text and interact with a GPT model.")
    parser.add_argument("--data", nargs=2, required=True, help="Two data excel files")
    parser.add_argument("--data-def", required=True, help="Data definition excel (columns + description) or CSV")
    parser.add_argument("--cheat", required=True, help="Cheat sheet file (excel or text)")
    parser.add_argument("--model", default="gpt-4o-mini", help="Chat model name")
    parser.add_argument("--api-key", default=None, help="OpenAI API key (or set OPENAI_API_KEY env var)")
    args = parser.parse_args()

    bot = DataChatbot(list(args.data), args.data_def, args.cheat, model=args.model, openai_api_key=args.api_key)
    print("Loaded files. Enter free-text queries. Type '/context' to print context, empty line to quit.")
    while True:
        try:
            q = input("Query> ")
        except EOFError:
            break
        if not q or q.strip() == "":
            break
        if q.strip() == "/context":
            print(bot.build_context())
            continue
        out = bot.answer_query(q)
        print("\n--- Response ---\n")
        print(out)
    print("Goodbye")
