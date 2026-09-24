class FakeGitHubClient:
    repo = "DCOIR-Collector/dcoir-collector"

    def __init__(self, reviews: list[dict[str, str]] | None = None) -> None:
        self.reviews = reviews or []
        self.files = {
            "tools/review_probe.py": "def run_probe(command):\n    return subprocess.run(command, shell=True)\n",
            "docs/review.md": "# Review\n\nKeep governed review evidence visible.\n",
            "tools/later_probe.py": "import subprocess\n\nsubprocess.run('whoami', shell=True)\n",
            "tools/huge_probe.py": "print('large context line')\n" * 1000,
            "tools/aliased_writer.py": "from pathlib import Path as P\nimport pathlib as pl\nimport os as operating_system\n\ndef write_triage_note(filename, note, output_dir):\n    destination = P(output_dir, filename)\n    pl.Path(destination).write_text(note)\n",
        }

    def request(self, _method: str, path: str):
        if path.startswith("/repos/DCOIR-Collector/dcoir-collector/pulls/287/reviews"):
            params = mod.urllib.parse.parse_qs(mod.urllib.parse.urlparse(path).query)
            page = int(params.get("page", ["1"])[0])
            return self.reviews if page == 1 else []
        if "/contents/" not in path:
            raise AssertionError(f"unexpected GitHub path: {path}")
        encoded_path = path.split("/contents/", 1)[1].split("?", 1)[0]
        file_path = mod.urllib.parse.unquote(encoded_path)
        if file_path == "large/oversized.py":
            return {"type": "file", "encoding": "none", "content": ""}
        content = self.files[file_path].encode("utf-8")
        return {
            "type": "file",
            "encoding": "base64",
            "content": base64.b64encode(content).decode("ascii"),
        }
