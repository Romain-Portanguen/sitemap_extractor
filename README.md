# 🚀 Sitemap Extractor

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) ![Python Version](https://img.shields.io/badge/python-3.8%2B-blue) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) ![Last Commit](https://img.shields.io/github/last-commit/Romain-Portanguen/sitemap_extractor?color=blue&label=last%20commit) ![Open Issues](https://img.shields.io/github/issues/Romain-Portanguen/sitemap_extractor?color=blue&label=issues) ![Open PRs](https://img.shields.io/github/issues-pr/Romain-Portanguen/sitemap_extractor?color=blue&label=PRs)

A robust Python CLI tool to extract URLs from XML sitemaps (including sitemap indexes) — local or remote — and export them in various formats. Handles most anti-bot protections, with an interactive fallback for manual extraction if needed.

---

## ✨ Features

- **Supports:** Local files & remote URLs
- **Handles:** Standard sitemaps & sitemap indexes (recursive)
- **Anti-bot evasion:** Custom headers, user agents, cookies, Playwright fallback
- **Interactive mode:** User-friendly CLI for non-technical users
- **Export formats:** TXT, JSON, CSV, XLSX, YAML
- **Progress & error logs:** Clear and actionable

---

## ⚠️ Limitations

Some websites use advanced fingerprinting or IP whitelisting and will only serve the sitemap to real browsers. In such cases, download the sitemap manually in your browser and use this script in local file mode.

---

## 🛠️ Installation

1. **Clone the repository**
2. **Create a virtual environment** (recommended):

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

---

## 🚦 Usage

### CLI (one-liner)

Extract URLs from a local or remote sitemap and export to a file:

```bash
python sitemap_extractor.py https://www.example.com/sitemap.xml --format json --output urls.json
```

### Interactive mode (recommended for non-technical users)

```bash
python sitemap_extractor.py --interactive
```

You will be guided step-by-step (source, format, output, etc.).

### Supported formats

- `txt` (default)
- `json`
- `csv`
- `xlsx`
- `yaml`

### Options

- `source` (positional): Path to local file or sitemap URL
- `--format` / `-f`: Output format (`txt`, `json`, `csv`, `xlsx`, `yaml`)
- `--output` / `-o`: Output file path (otherwise prints to terminal)
- `--interactive` / `-i`: Launches the interactive CLI

---

## 🧩 Troubleshooting & Tips

- **Anti-bot protection:** The script tries advanced evasion, but some sites block all automation. If so, download the sitemap manually and use the script in local mode.
- **Playwright fallback:** If all else fails, a Chromium window will open. Interact as needed (solve captchas, reload, etc.), then press Enter in the terminal to capture the content.
- **No URLs found:** Check that the sitemap is accessible and valid XML. Try downloading it manually if needed.
- **Public IP log:** The script logs your public IP at startup so you can verify VPN/proxy usage.

---

## 💡 Example commands

Extract and print URLs from a local sitemap:

```bash
python sitemap_extractor.py sitemap.xml
```

Extract from a URL and save as CSV:

```bash
python sitemap_extractor.py https://www.example.com/sitemap.xml --format csv --output urls.csv
```

Interactive extraction:

```bash
python sitemap_extractor.py --interactive
```

---

## 🤝 Contributing

Contributions, bug reports, and suggestions are welcome! Please open an issue or submit a pull request.

---

## 📄 License

MIT License — © 2025 Romain Potanguen
