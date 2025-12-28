# Essayism

A lightweight, zero-dependency essay management system built with Python. Designed for writing, archiving, and tracking essay performance with structured metadata (grades, critiques, and reflections).

## Features

* **Zero Dependencies:** Runs entirely on the Python Standard Library (no `pip install` needed).
* **Flat-File Storage:** Essays are stored as Markdown `.txt` files for easy portability.
* **Metadata Tracking:** Native support for tracking grades, tags (simple DDC classes), grader critiques, and self-reflections.
* **Full Management:** Search, filter, sort, and paginate your essay collection.
* **Backup & Restore:** Download or upload your entire library as a ZIP file directly from the UI.
* **Secure:** Basic Authentication and CSRF protection included.

## Quick Start

1. **Run the server:**
```bash
python3 server.py
```
2. **Access the dashboard:** Open `http://localhost:8000` in your browser.
3. **Login:**
   * Username: `admin`
   * Password: `admin`

## Configuration

You can configure the server using environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `ESSAY_PORT` | `8000` | Port to run the server on. |
| `ESSAY_DIRECTORY` | `essays` | Folder where text files are stored. |
| `ESSAY_USER` | `admin` | Login username. |
| `ESSAY_PASS` | `admin` | Login password. |

**Example:**

```bash
ESSAY_PORT=9090 ESSAY_USER=writer ESSAY_PASS=123write123 python3 server.py
```

## AI Grading Workflow

This system is designed to work alongside LLMs (like GPT-4 or Claude) for feedback.

1. **Write** your essay in the "New Essay" tab.
2. **Copy** the content of `EVALUATION_PROMPT.md` and your essay into an LLM.
3. **Paste** the AI's critique, grade, and your own reflection into the **Metadata & Review** fields in the editor.
4. **Save** to visualize your progress over time.

## Project Structure

You can put `favicon.ico` (site icon, small resolution like 32x32) and `logo.png` (site logo, slightly larger resolution like 200x200) into the root directory.

```text
├── EVALUATION_PROMPT.md  # Rubric for AI grading
├── essays/               # Storage for essay .txt files
├── server.py             # Single-file application
├── favicon.ico           # Site icon
└── logo.png              # Site logo
```
