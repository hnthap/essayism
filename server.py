import base64
import http.server
import math
import os
import re
import shutil
import socketserver
import tempfile
import urllib.parse
import uuid
import zipfile
from datetime import datetime
from typing import Any

# --- Configuration ---
PORT = int(os.environ.get("ESSAY_PORT", "8000"))
ESSAY_DIR = os.environ.get("ESSAY_DIRECTORY", "essays")
ITEMS_PER_PAGE = int(os.environ.get("ESSAY_ITEMS_PER_PAGE", "10"))
MAX_UPLOAD_SIZE = (
    int(os.environ.get("ESSAY_MAX_UPLOAD_SIZE_MIB", "50")) * 1024 * 1024
)  # 50 MB Limit to prevent DoS
CSRF_TOKEN = str(uuid.uuid4())  # Unique token for this server session

# --- Security Credentials (Default: admin / admin) ---
AUTH_USERNAME = os.environ.get("ESSAY_USER", "admin")
AUTH_PASSWORD = os.environ.get("ESSAY_PASS", "admin")

DDC_CLASSES = [
    "000 Computer science, information and general works",
    "100 Philosophy and psychology",
    "200 Religion",
    "300 Social sciences",
    "400 Language",
    "500 Pure science",
    "600 Technology",
    "700 Arts and recreation",
    "800 Literature",
    "900 History and geography",
]

# --- CSS Styling (Dark Mode + Analytics + Edit Form) ---
CSS = """
<style>
    body { 
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
        line-height: 1.6; 
        max-width: 850px; 
        margin: 40px auto; 
        padding: 0 20px; 
        color: #e0e0e0; 
        background-color: #121212; 
    }
    h1 { border-bottom: 2px solid #333; padding-bottom: 10px; color: #fff; margin-top: 0;}
    h2, h3, h4 { color: #ccc; margin-top: 25px; margin-bottom: 10px; }
    h3 { border-bottom: 1px solid #333; padding-bottom: 5px; }
    
    a { color: #66b3ff; text-decoration: none; transition: color 0.2s; }
    a:hover { color: #99ccff; text-decoration: underline; }
    
    /* Layout */
    .header-controls { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 20px; }
    
    /* Site Header (Logo + Title) */
    .site-header { 
        display: flex; 
        align-items: center; 
        border-bottom: 2px solid #333; 
        padding-bottom: 10px; 
        margin-bottom: 20px; /* Replaces the margin usually found on h1 */
    }
    .site-header h1 { 
        border-bottom: none; 
        padding-bottom: 0; 
        margin: 0; 
    }
    .site-logo { 
        width: 50px; 
        height: 50px; 
        border-radius: 50%; 
        margin-right: 15px; 
        object-fit: cover; 
        background-color: #333; /* Placeholder color if image loads slow/fails */
    }

    /* Essay List */
    .essay-list { list-style: none; padding: 0; }
    .essay-item { 
        background: #1e1e1e;
        margin-bottom: 15px; 
        border: 1px solid #333; 
        border-radius: 6px;
        padding: 15px;
        transition: transform 0.2s;
    }
    .essay-item:hover { transform: translateX(5px); border-color: #444; }
    .essay-header { display: flex; justify-content: space-between; align-items: center; }
    .essay-title { font-size: 1.2em; font-weight: bold; }
    
    /* Metadata Badges */
    .badges { display: flex; gap: 10px; font-size: 0.8em; margin-top: 8px; flex-wrap: wrap; }
    .badge { padding: 2px 8px; border-radius: 4px; background: #333; color: #bbb; display: inline-block; }
    .badge-tag { background: #3d3d5c; color: #ccccff; border: 1px solid #4d4d7a; }
    
    /* Score Badge Variants */
    .badge-grade.high { background: #2d4035; color: #8fce00; border: 1px solid #3e5746; }
    .badge-grade.medium { background: #363018; color: #ffcc00; border: 1px solid #4d4422; }
    .badge-grade.low { background: #3d2222; color: #ff6b6b; border: 1px solid #573030; }
    
    .meta { font-size: 0.85em; color: #888; }
    .back-link { display: inline-block; margin-bottom: 20px; font-weight: bold; }
    
    .content-box { margin-bottom: 30px; font-size: 1.05em; }
    .content-box p { margin-bottom: 1em; }
    .content-box blockquote { 
        border-left: 4px solid #555; 
        margin: 1.5em 10px; 
        padding: 0.5em 10px; 
        background: #1a1a1a;
        color: #aaa;
        font-style: italic;
    }
    
    /* Structured Review Boxes */
    .review-section { margin-top: 40px; border-top: 1px solid #333; padding-top: 20px; }
    
    .card { padding: 20px; border-radius: 8px; margin-bottom: 20px; }
    
    .grader-card { 
        background: #15191d; 
        border: 1px solid #2a3b4d; 
        border-left: 4px solid #66b3ff;
    }
    .grader-meta { font-size: 0.9em; color: #66b3ff; font-weight: bold; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px;}
    
    .reflection-card { 
        background: #1d1b15; 
        border: 1px solid #4d4422; 
        border-left: 4px solid #ffcc00;
    }
    .reflection-meta { font-size: 0.9em; color: #ffcc00; font-weight: bold; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px;}

    /* Form Styling */
    .search-bar { display: flex; gap: 10px; margin-bottom: 20px; }
    .search-input { 
        flex-grow: 1; padding: 10px; border-radius: 4px; 
        border: 1px solid #333; background: #1e1e1e; color: #fff; 
    }
    .search-btn, .sort-btn, .btn { 
        padding: 10px 15px; border-radius: 4px; border: none; 
        background: #333; color: #fff; cursor: pointer; font-size: 0.9em;
        text-decoration: none; display: inline-block;
    }
    .search-btn:hover, .sort-btn:hover, .btn:hover { background: #444; }
    .sort-active { background: #66b3ff; color: #000; font-weight: bold; }
    .sort-active:hover { background: #5599dd; }
    
    /* Pagination */
    .pagination { display: flex; justify-content: center; gap: 5px; margin-top: 30px; }
    .page-link { padding: 8px 12px; background: #1e1e1e; color: #fff; text-decoration: none; border-radius: 4px; border: 1px solid #333; }
    .page-link:hover { background: #333; border-color: #444; }
    .page-link.active { background: #66b3ff; color: #000; font-weight: bold; border-color: #66b3ff; }
    .page-link.disabled { opacity: 0.5; pointer-events: none; }

    /* Edit Form Specifics */
    .edit-form { display: flex; flex-direction: column; gap: 15px; }
    .edit-form label { font-weight: bold; color: #ccc; margin-bottom: 5px; display: block;}
    .edit-form input[type="text"], 
    .edit-form input[type="number"], 
    .edit-form input[type="date"],
    .edit-form select {
        width: 100%; padding: 10px; background: #1e1e1e; border: 1px solid #333; color: #fff; border-radius: 4px; box-sizing: border-box;
    }
    .edit-form textarea {
        width: 100%; padding: 10px; background: #1e1e1e; border: 1px solid #333; color: #fff; border-radius: 4px;
        min-height: 300px; font-family: 'Courier New', monospace; line-height: 1.6; box-sizing: border-box; resize: vertical;
    }
    .edit-actions { display: flex; gap: 10px; margin-top: 10px; }
    .btn-primary { background: #0066cc; }
    .btn-primary:hover { background: #0055aa; }
    .btn-danger { background: #802222; }
    .btn-danger:hover { background: #a03333; }
</style>
"""


def estimate_reading_time(text: str):
    """Calculates word count and estimated reading time (minutes)."""
    word_count = len(text.split())
    minutes = math.ceil(word_count / 200)  # Avg reading speed 200 wpm
    return word_count, minutes


def render_markdown(text: str):
    """Lightweight Markdown parser (Bold, Italic, Headers, Quotes, Paragraphs)."""
    if not text:
        return ""

    # 1. Escape HTML (Basic security)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    lines = text.split("\n")
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Headers
        if stripped.startswith("### "):
            new_lines.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith("## "):
            new_lines.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("# "):
            new_lines.append(f"<h1>{stripped[2:]}</h1>")
        # Blockquotes
        elif stripped.startswith("> "):
            new_lines.append(f"<blockquote>{stripped[2:]}</blockquote>")
        else:
            # Inline formatting (Bold & Italic)
            # Bold **text**
            line = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", line)
            # Italic *text*
            line = re.sub(r"\*(.*?)\*", r"<em>\1</em>", line)
            new_lines.append(line)

    # Rejoin to handle paragraph splitting (Double newline = new paragraph)
    # We join everything back, then split by double newlines to find paragraphs
    # Note: Headers/Quotes already have tags, so we need to be careful not to wrap them in <p> if not needed.
    # For a lightweight parser, we'll keep it simple: Double \n is a separator.

    processed_body = "\n".join(new_lines)
    blocks = processed_body.split("\n\n")

    final_html_blocks: list[str] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # If the block is already an HTML tag (header/quote), don't wrap in <p>
        if block.startswith("<h") or block.startswith("<blockquote"):
            final_html_blocks.append(block)
        else:
            # Convert single newlines within a paragraph to <br> for line breaks
            content = block.replace("\n", "<br>")
            final_html_blocks.append(f"<p>{content}</p>")

    return "\n".join(final_html_blocks)


def parse_metadata(comments_text: str):
    """Parses the section after '----' for structured fields."""
    meta: dict[str, Any] = {
        "grade": None,
        "grader": "Unknown",
        "grader_note": "",
        "reflection": "",
        "tag": None,
        "raw_comments": comments_text,
    }

    if not comments_text:
        return meta

    # 1. Extract Grade (Regex)
    grade_match = re.search(r"Grade:\s*([\d\.]+)/10", comments_text, re.IGNORECASE)
    if grade_match:
        try:
            meta["grade"] = float(grade_match.group(1))
        except ValueError:
            pass

    # 2. Extract Tag (Regex)
    tag_match = re.search(r"Class:\s*(.+)", comments_text, re.IGNORECASE)
    if tag_match:
        meta["tag"] = tag_match.group(1).strip()

    # 3. Extract Grader Name
    grader_match = re.search(r"Grader:\s*(.+)", comments_text, re.IGNORECASE)
    if grader_match:
        meta["grader"] = grader_match.group(1).strip()

    # 4. Extract Blocks (Grader's Note & Self-Reflection)
    # We scan line by line to handle multi-line content
    lines = comments_text.split("\n")
    current_section: str | None = None
    buffer = []

    def save_buffer(section_name: str | None):
        if section_name and buffer:
            meta[section_name] = "\n".join(buffer).strip()

    for line in lines:
        clean_line = line.strip()

        if clean_line.startswith("Grader's Note:"):
            save_buffer(current_section)
            current_section = "grader_note"
            buffer = [clean_line.replace("Grader's Note:", "").strip()]
        elif clean_line.startswith("Self-Reflection:"):
            save_buffer(current_section)
            current_section = "reflection"
            buffer = [clean_line.replace("Self-Reflection:", "").strip()]
        elif (
            clean_line.startswith("Grade:")
            or clean_line.startswith("Grader:")
            or clean_line.startswith("Class:")
        ):
            # These keys reset the block reading if we were in one
            save_buffer(current_section)
            current_section = None
            buffer = []
        else:
            if current_section:
                buffer.append(line)  # Keep indentation if any

    save_buffer(current_section)

    # Render markdown for the notes
    if meta["grader_note"]:
        meta["grader_note_html"] = render_markdown(meta["grader_note"])
    if meta["reflection"]:
        meta["reflection_html"] = render_markdown(meta["reflection"])

    return meta


def load_essays():
    """Scans the essay folder and returns a list of dictionaries."""
    data: list[dict[str, Any]] = []

    if not os.path.exists(ESSAY_DIR):
        os.makedirs(ESSAY_DIR)
        return data

    for filename in os.listdir(ESSAY_DIR):
        if filename.endswith(".txt"):
            filepath = os.path.join(ESSAY_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f.readlines()]

                if len(lines) >= 3:
                    title = lines[0]
                    # Date is expected to be the last line
                    date_str = lines[-1]

                    full_text = "\n".join(lines[1:-1])  # Exclude Title and Date line

                    if "----" in full_text:
                        parts = full_text.split("----")
                        content_body = parts[0].strip()
                        # Join back any remaining parts in case user used ---- multiple times
                        comments_block = "----".join(parts[1:]).strip()
                    else:
                        content_body = full_text.strip()
                        comments_block = ""

                    word_count, read_time = estimate_reading_time(content_body)

                    # Parse Metadata
                    meta = parse_metadata(comments_block)

                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    except ValueError:
                        date_obj = datetime.min

                    entry = {
                        "filename": filename,
                        "title": title,
                        "content_raw": content_body,
                        "comments_raw": comments_block,
                        "date_str": date_str,
                        "date_obj": date_obj,
                        "word_count": word_count,
                        "read_time": read_time,
                    }
                    entry.update(meta)  # Merge parsed metadata (grade, tag, etc)
                    data.append(entry)
            except Exception as e:
                print(f"Error reading {filename}: {e}")

    # Default sort by date descending
    data.sort(key=lambda x: x["date_obj"], reverse=True)
    return data


class EssayHandler(http.server.SimpleHTTPRequestHandler):
    def check_auth(self):
        """Validates the HTTP Basic Authentication header."""
        auth_header = self.headers.get("Authorization")
        if not auth_header:
            return False

        try:
            # Header is typically "Basic <base64_string>"
            auth_type, encoded = auth_header.split(" ", 1)
            if auth_type.lower() != "basic":
                return False

            # Decode the base64 string
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, password = decoded.split(":", 1)

            # Verify credentials
            return username == AUTH_USERNAME and password == AUTH_PASSWORD
        except Exception:
            return False

    def do_auth_request(self):
        """Sends the 401 response to trigger the browser login popup."""
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="EssayServer"')
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"401 Unauthorized: Access Denied")

    def do_POST(self):
        """Handle saving essay updates with structured metadata."""

        # 1. Authentication Check
        if not self.check_auth():
            self.do_auth_request()
            return

        # 2. Security: Check Content-Length to prevent DoS (Memory Exhaustion)
        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            content_length = 0

        if content_length > MAX_UPLOAD_SIZE:
            self.send_error(
                413, f"Payload Too Large. Limit is {MAX_UPLOAD_SIZE / (1024 * 1024)}MB."
            )
            return

        parsed_path = urllib.parse.urlparse(self.path)

        # --- Route: Upload Zip Restore ---
        if parsed_path.path == "/upload_zip":
            # CSRF Check for AJAX Upload
            if self.headers.get("X-CSRF-Token") != CSRF_TOKEN:
                self.send_error(403, "CSRF Check Failed: Token missing or invalid")
                return

            # Use temp file to avoid RAM spike from large uploads
            tmp_upload_path = None
            try:
                # Stream to disk using a temp file
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    tmp_upload_path = tmp_file.name
                    bytes_remaining = content_length
                    chunk_size = 64 * 1024  # 64KB chunks

                    while bytes_remaining > 0:
                        chunk = self.rfile.read(min(chunk_size, bytes_remaining))
                        if not chunk:
                            break
                        tmp_file.write(chunk)
                        bytes_remaining -= len(chunk)

                # Check magic number
                with open(tmp_upload_path, "rb") as f:
                    if f.read(2) != b"PK":
                        self.send_error(400, "Not a valid zip file")
                        return

                if not zipfile.is_zipfile(tmp_upload_path):
                    self.send_error(400, "Not a valid zip file")
                    return

                # Create essay dir if missing
                if not os.path.exists(ESSAY_DIR):
                    os.makedirs(ESSAY_DIR)

                count_added = 0
                count_renamed = 0

                # Process the zip file from disk
                with zipfile.ZipFile(tmp_upload_path, "r") as zip_ref:
                    for member in zip_ref.namelist():
                        # Basic security: skip directories and files with traversal
                        if member.endswith("/") or ".." in member:
                            continue

                        # Only accept .txt
                        if not member.lower().endswith(".txt"):
                            continue

                        # Use basename to flatten structure and prevent traversal
                        filename = os.path.basename(member)
                        if not filename:
                            continue

                        target_path = os.path.join(ESSAY_DIR, filename)

                        # GRACEFUL CONFLICT HANDLING
                        if os.path.exists(target_path):
                            existing_content = open(target_path, "rb").read()
                            new_content = zip_ref.read(member)

                            if existing_content != new_content:
                                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                                name, ext = os.path.splitext(filename)
                                new_filename = f"{name}_conflict_{timestamp}{ext}"
                                target_path = os.path.join(ESSAY_DIR, new_filename)
                                count_renamed += 1
                            else:
                                continue

                        with open(target_path, "wb") as f:
                            f.write(zip_ref.read(member))
                        count_added += 1

                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(
                    f"Restore complete. Added: {count_added}, Renamed (Conflicts): {count_renamed}".encode(
                        "utf-8"
                    )
                )

            except Exception as e:
                print(f"Zip Upload Error: {e}")
                self.send_error(500, f"Error processing zip: {str(e)}")
            finally:
                # Cleanup temp file
                if tmp_upload_path and os.path.exists(tmp_upload_path):
                    try:
                        os.remove(tmp_upload_path)
                    except Exception:
                        pass
            return

        # --- Route: Save/Delete Essay (Standard POST) ---
        try:
            post_data = self.rfile.read(content_length).decode("utf-8")
            params = urllib.parse.parse_qs(post_data)

            # CSRF Check for Form Submissions
            submitted_token = params.get("csrf_token", [""])[0]
            if submitted_token != CSRF_TOKEN:
                self.send_error(403, "CSRF Check Failed: Token missing or invalid")
                return

            # --- Handle Delete ---
            if params.get("action", [""])[0] == "delete":
                filename = params.get("filename", [""])[0]

                # SECURITY FIX: Prevent Path Traversal
                # We strictly extract the basename, ignoring any path components provided
                filename = os.path.basename(filename)

                if filename:
                    filepath = os.path.join(ESSAY_DIR, filename)
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except OSError as e:
                            self.send_error(500, f"Error deleting file: {e}")
                            return
                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()
                return

            # Extract Core fields
            filename = params.get("filename", [""])[0]
            title = params.get("title", [""])[0]
            content = params.get("content", [""])[0]
            date_str = params.get("date", [""])[0]

            # Extract Metadata Fields
            meta_grade = params.get("meta_grade", [""])[0]
            meta_tag = params.get("meta_tag", [""])[0]
            meta_grader = params.get("meta_grader", [""])[0]
            meta_note = params.get("meta_note", [""])[0]
            meta_reflection = params.get("meta_reflection", [""])[0]

            if not title:
                self.send_error(400, "Missing title")
                return

            # SECURITY FIX: Prevent Path Traversal
            # We strictly extract the basename, ignoring any path components provided
            if filename:
                # Editing existing file
                filename = os.path.basename(filename)
            else:
                # Creating new file (Automatic Filename)
                filename = f"{uuid.uuid4()}.txt"

            if not filename.endswith(".txt"):
                filename += ".txt"

            # Normalize line endings for main content
            content = content.replace("\r\n", "\n")
            meta_note = meta_note.replace("\r\n", "\n")
            meta_reflection = meta_reflection.replace("\r\n", "\n")

            # Reconstruct the Metadata Block
            comments_parts: list[str] = []
            if meta_grade:
                comments_parts.append(f"Grade: {meta_grade}/10")
            if meta_tag:
                comments_parts.append(f"Class: {meta_tag}")
            if meta_grader:
                comments_parts.append(f"Grader: {meta_grader}")

            if meta_note:
                comments_parts.append(f"Grader's Note:\n{meta_note}")

            if meta_reflection:
                comments_parts.append(f"Self-Reflection:\n{meta_reflection}")

            new_comments_block = "\n\n".join(comments_parts)

            # Reconstruct file content matching the format
            file_content = (
                f"{title}\n\n{content}\n\n----\n\n{new_comments_block}\n\n{date_str}"
            )

            filepath = os.path.join(ESSAY_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(file_content)

            self.send_response(303)
            self.send_header("Location", f"/?file={filename}")
            self.end_headers()

        except Exception as e:
            print(f"POST Error: {e}")
            self.send_error(500, f"Error saving file: {str(e)}")

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)

        # --- Route: Logout ---
        if parsed_path.path == "/logout":
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="EssayServer"')
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<!DOCTYPE html><html><body style='font-family: sans-serif; background: #121212; color: #e0e0e0; padding: 40px;'><h1>Logged out</h1><p>You have been logged out. <a href='/' style='color: #66b3ff;'>Log in again</a></p></body></html>"
            )
            return

        # 1. Authentication Check
        if not self.check_auth():
            self.do_auth_request()
            return

        # --- Route: Download Backup Zip ---
        if parsed_path.path == "/download_zip":
            # Use temp file to avoid RAM spike from backup generation
            tmp_zip_path = None
            try:
                # Create zip in temp file on disk
                with tempfile.NamedTemporaryFile(
                    suffix=".zip", delete=False
                ) as tmp_file:
                    tmp_zip_path = tmp_file.name
                    with zipfile.ZipFile(
                        tmp_file, "w", zipfile.ZIP_DEFLATED
                    ) as zip_file:
                        if os.path.exists(ESSAY_DIR):
                            for root, _, files in os.walk(ESSAY_DIR):
                                for file in files:
                                    if file.endswith(".txt"):
                                        file_path = os.path.join(root, file)
                                        zip_file.write(
                                            file_path, os.path.basename(file_path)
                                        )

                # Stream it out
                with open(tmp_zip_path, "rb") as f:
                    fs = os.fstat(f.fileno())
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    self.send_header(
                        "Content-Disposition",
                        f'attachment; filename="essays-{timestamp}.zip"',
                    )
                    self.send_header("Content-Length", str(fs.st_size))
                    self.end_headers()
                    shutil.copyfileobj(f, self.wfile)

            except Exception as e:
                print(f"Backup Error: {e}")
                self.send_error(500, f"Error creating backup: {str(e)}")
            finally:
                if tmp_zip_path and os.path.exists(tmp_zip_path):
                    try:
                        os.remove(tmp_zip_path)
                    except Exception:
                        pass
            return

        # --- Route: Index / List / Search ---
        if parsed_path.path == "/":
            query_params = urllib.parse.parse_qs(parsed_path.query)
            essays = load_essays()
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            # 1. Create View
            if "action" in query_params and query_params["action"][0] == "create":
                # Generate options for dropdown
                ddc_options = ""
                for c in DDC_CLASSES:
                    ddc_options += f'<option value="{c}">{c}</option>'

                html = f"""
                <!DOCTYPE html>
                <html>
                <head><title>New Essay</title>{CSS}</head>
                <body>
                    <h1>New Essay</h1>
                    <form method="POST" action="/" class="edit-form">
                        <input type="hidden" name="csrf_token" value="{CSRF_TOKEN}">
                        <div>
                            <label>Title</label>
                            <input type="text" name="title" placeholder="Essay Title" required>
                        </div>
                        <div>
                            <label>Content (Markdown supported)</label>
                            <textarea name="content" placeholder="Write your essay here..."></textarea>
                        </div>
                        
                        <div style="background: #1a1a1a; padding: 15px; border-radius: 6px; border: 1px solid #333;">
                            <h3 style="margin-top:0; color:#66b3ff; border-bottom: none;">Metadata & Review</h3>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                                <div>
                                    <label style="font-size:0.85em; color:#888;">Grade (x/10)</label>
                                    <input type="number" step="0.1" name="meta_grade" placeholder="8.5">
                                </div>
                                <div>
                                    <label style="font-size:0.85em; color:#888;">Class (DDC)</label>
                                    <select name="meta_tag">
                                        <option value="" disabled selected>Select a class...</option>
                                        {ddc_options}
                                    </select>
                                </div>
                                <div>
                                    <label style="font-size:0.85em; color:#888;">Grader Name</label>
                                    <input type="text" name="meta_grader" placeholder="Claude 3.5">
                                </div>
                            </div>
                            
                            <div style="margin-bottom: 15px;">
                                <label style="font-size:0.85em; color:#888;">Grader's Note</label>
                                <textarea name="meta_note" style="min-height: 100px; font-family: inherit; font-size: 0.9em;" placeholder="Critique summary..."></textarea>
                            </div>
                            
                            <div>
                                <label style="font-size:0.85em; color:#888;">Self-Reflection</label>
                                <textarea name="meta_reflection" style="min-height: 100px; font-family: inherit; font-size: 0.9em;" placeholder="My thoughts..."></textarea>
                            </div>
                        </div>

                        <div>
                            <label>Date</label>
                            <input type="date" name="date" value="{datetime.now().strftime("%Y-%m-%d")}" required>
                        </div>
                        <div class="edit-actions">
                            <button type="submit" class="btn btn-primary">Save Essay</button>
                            <a href="/" class="btn">Cancel</a>
                        </div>
                    </form>
                </body>
                </html>
                """
                self.wfile.write(html.encode("utf-8"))
                return

            # 2. Edit View
            if (
                "action" in query_params
                and query_params["action"][0] == "edit"
                and "file" in query_params
            ):
                filename = query_params["file"][0]
                # Find essay
                row = next((e for e in essays if e["filename"] == filename), None)

                if row:
                    # Helper for safe value extraction
                    grade_val = row["grade"] if row["grade"] is not None else ""
                    tag_val = row["tag"] if row["tag"] else ""
                    grader_val = (
                        row["grader"]
                        if row["grader"] and row["grader"] != "Unknown"
                        else ""
                    )

                    # Generate options for dropdown with selection logic
                    ddc_options = ""
                    for c in DDC_CLASSES:
                        sel = "selected" if tag_val == c else ""
                        ddc_options += f'<option value="{c}" {sel}>{c}</option>'

                    html = f"""
                    <html>
                    <head><title>Edit: {row["title"]}</title>{CSS}</head>
                    <body>
                        <h1>Edit Essay</h1>
                        <form method="POST" action="/" class="edit-form">
                            <input type="hidden" name="csrf_token" value="{CSRF_TOKEN}">
                            <input type="hidden" name="filename" value="{row["filename"]}">
                            <div>
                                <label>Title</label>
                                <input type="text" name="title" value="{row["title"]}" required>
                            </div>
                            <div>
                                <label>Content (Markdown supported)</label>
                                <textarea name="content">{row["content_raw"]}</textarea>
                            </div>
                            
                            <div style="background: #1a1a1a; padding: 15px; border-radius: 6px; border: 1px solid #333;">
                                <h3 style="margin-top:0; color:#66b3ff; border-bottom: none;">Metadata & Review</h3>
                                
                                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 15px;">
                                    <div>
                                        <label style="font-size:0.85em; color:#888;">Grade (x/10)</label>
                                        <input type="number" step="0.1" name="meta_grade" value="{grade_val}">
                                    </div>
                                    <div>
                                        <label style="font-size:0.85em; color:#888;">Class (DDC)</label>
                                        <select name="meta_tag">
                                            <option value="" disabled {"selected" if not tag_val else ""}>Select a class...</option>
                                            {ddc_options}
                                        </select>
                                    </div>
                                    <div>
                                        <label style="font-size:0.85em; color:#888;">Grader Name</label>
                                        <input type="text" name="meta_grader" value="{grader_val}">
                                    </div>
                                </div>
                                
                                <div style="margin-bottom: 15px;">
                                    <label style="font-size:0.85em; color:#888;">Grader's Note</label>
                                    <textarea name="meta_note" style="min-height: 100px; font-family: inherit; font-size: 0.9em;">{row["grader_note"]}</textarea>
                                </div>
                                
                                <div>
                                    <label style="font-size:0.85em; color:#888;">Self-Reflection</label>
                                    <textarea name="meta_reflection" style="min-height: 100px; font-family: inherit; font-size: 0.9em;">{row["reflection"]}</textarea>
                                </div>
                            </div>

                            <div>
                                <label>Date</label>
                                <input type="date" name="date" value="{row["date_str"]}" required>
                            </div>
                            <div class="edit-actions">
                                <button type="submit" class="btn btn-primary">Save Changes</button>
                                <a href="/?file={row["filename"]}" class="btn">Cancel</a>
                                <button type="button" class="btn btn-danger" style="margin-left:auto;" onclick="if(confirm('Are you sure you want to delete this essay?')) document.getElementById('delete-form').submit();">Delete</button>
                            </div>
                        </form>
                        <form id="delete-form" method="POST" action="/">
                            <input type="hidden" name="csrf_token" value="{CSRF_TOKEN}">
                            <input type="hidden" name="action" value="delete">
                            <input type="hidden" name="filename" value="{row["filename"]}">
                        </form>
                    </body>
                    </html>
                    """
                    self.wfile.write(html.encode("utf-8"))
                else:
                    self.wfile.write(b"Essay not found.")
                return

            # 3. View Single Essay
            if "file" in query_params:
                filename = query_params["file"][0]
                # Find essay
                row = next((e for e in essays if e["filename"] == filename), None)

                if row:
                    # Render Markdown Content
                    formatted_content = render_markdown(row["content_raw"])

                    # Grade Badge
                    grade_display = ""
                    if row["grade"] is not None:
                        val = row["grade"]
                        if val >= 9:
                            grade_class = "high"
                        elif val >= 7:
                            grade_class = "medium"
                        else:
                            grade_class = "low"
                        grade_display = f'<span class="badge badge-grade {grade_class}">Grade: {val}/10</span>'

                    # Tag Badge
                    tag_display = ""
                    if row["tag"]:
                        tag_display = (
                            f'<span class="badge badge-tag">{row["tag"]}</span>'
                        )

                    # Build Review Section
                    review_html = ""
                    has_review = row.get("grader_note") or row.get("reflection")

                    if has_review:
                        review_html += '<div class="review-section">'

                        # Grader Card
                        if row.get("grader_note"):
                            note_html = row.get("grader_note_html", row["grader_note"])
                            grader_name = row.get("grader", "Unknown Grader")
                            review_html += f"""
                            <div class="card grader-card">
                                <div class="grader-meta">CRITIQUE BY {grader_name}</div>
                                <div class="content-box" style="margin-bottom:0; font-size:0.95em;">{note_html}</div>
                            </div>
                            """

                        # Reflection Card
                        if row.get("reflection"):
                            ref_html = row.get("reflection_html", row["reflection"])
                            review_html += f"""
                            <div class="card reflection-card">
                                <div class="reflection-meta">AUTHOR'S REFLECTION</div>
                                <div class="content-box" style="margin-bottom:0; font-size:0.95em;">{ref_html}</div>
                            </div>
                            """
                        review_html += "</div>"

                    # If no structured data but raw comments exist, fallback
                    elif row["comments_raw"]:
                        review_html = f'<div class="card grader-card"><pre>{row["comments_raw"]}</pre></div>'

                    html = f"""
                    <html>
                    <head><title>{row["title"]}</title>{CSS}</head>
                    <body>
                        <div class="header-controls">
                            <div><a href="/" class="back-link">&larr; Back to Index</a></div>
                            <div><a href="/?action=edit&file={row["filename"]}" class="btn">Edit</a></div>
                        </div>
                        
                        <h1>{row["title"]}</h1>
                        <div class="badges">
                            {tag_display}
                            <span class="badge">{row["word_count"]} words</span>
                            <span class="badge">{row["read_time"]} min read</span>
                            <span class="badge">{row["date_str"]}</span>
                            {grade_display}
                        </div>
                        <hr style="border-color: #333; margin: 20px 0;">
                        
                        <div class="content-box">
                            {formatted_content}
                        </div>
                        
                        {review_html}
                    </body>
                    </html>
                    """
                    self.wfile.write(html.encode("utf-8"))
                else:
                    self.wfile.write(b"Essay not found.")
                return

            # 4. Index List Logic
            search_query = query_params.get("q", [""])[0]
            filter_class = query_params.get("class", [""])[0]

            if search_query and essays:
                try:
                    pattern = re.compile(search_query, re.IGNORECASE)
                    essays = [
                        e
                        for e in essays
                        if pattern.search(e["title"])
                        or pattern.search(e["content_raw"])
                        or pattern.search(e["comments_raw"])
                    ]
                except re.error:
                    essays = []

            if filter_class and essays:
                essays = [e for e in essays if e.get("tag") == filter_class]

            sort_mode = query_params.get("sort", ["date"])[0]
            if essays:
                if sort_mode == "grade":
                    # Handle None in grade for sorting
                    essays.sort(
                        key=lambda x: (x["grade"] is not None, x["grade"]), reverse=True
                    )
                else:
                    essays.sort(key=lambda x: x["date_obj"], reverse=True)

            # Pagination Logic
            page_param = query_params.get("page", ["1"])[0]
            try:
                current_page = int(page_param)
            except ValueError:
                current_page = 1

            total_count = len(essays)
            total_pages = math.ceil(total_count / ITEMS_PER_PAGE)
            if total_pages == 0:
                total_pages = 1

            if current_page > total_pages:
                current_page = total_pages
            if current_page < 1:
                current_page = 1

            start_idx = (current_page - 1) * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE

            page_essays = essays[start_idx:end_idx]

            list_items = ""
            if page_essays:
                for row in page_essays:
                    link = f"/?file={row['filename']}"

                    # Grade Badge
                    grade_html = ""
                    if row["grade"] is not None:
                        val = row["grade"]
                        if val >= 9:
                            g_class = "high"
                        elif val >= 7:
                            g_class = "medium"
                        else:
                            g_class = "low"
                        grade_html = (
                            f'<span class="badge badge-grade {g_class}">{val}</span>'
                        )

                    # Tag Badge
                    tag_html = ""
                    if row["tag"]:
                        tag_html = f'<span class="badge badge-tag" style="font-size:0.8em; margin-right:5px;">{row["tag"]}</span>'

                    list_items += f"""
                    <li class="essay-item">
                        <div class="essay-header">
                            <a href="{link}" class="essay-title">{row["title"]}</a>
                            {grade_html}
                        </div>
                        <div class="badges">
                            {tag_html}
                            <span class="badge">{row["date_str"]}</span>
                            <span class="badge">{row["read_time"]} min read</span>
                        </div>
                    </li>
                    """
            else:
                list_items = "<p style='color:#888'>No essays found.</p>"

            def sort_cls(name: str):
                return "sort-btn sort-active" if sort_mode == name else "sort-btn"

            # Filter options for index dropdown
            filter_options = '<option value="">All Classes</option>'
            for c in DDC_CLASSES:
                sel = "selected" if filter_class == c else ""
                filter_options += f'<option value="{c}" {sel}>{c}</option>'

            # Construct params for links to preserve filter/search state
            q_param = f"&q={urllib.parse.quote(search_query)}" if search_query else ""
            c_param = (
                f"&class={urllib.parse.quote(filter_class)}" if filter_class else ""
            )
            base_params = q_param + c_param

            # Pagination Controls HTML
            pagination_html = ""
            if total_pages > 1:
                pagination_html = '<div class="pagination">'

                # Helper to make link
                def make_page_link(
                        p: int,
                        text: str,
                        active: bool = False,
                        disabled: bool = False
                ):
                    if disabled:
                        return f'<span class="page-link disabled">{text}</span>'
                    cls = "page-link active" if active else "page-link"
                    url = f"/?page={p}&sort={sort_mode}{base_params}"
                    return f'<a href="{url}" class="{cls}">{text}</a>'

                # Prev
                pagination_html += make_page_link(
                    current_page - 1,
                    "&larr;",
                    disabled=(current_page == 1)
                )

                # Simple sliding window or just all if pages are few
                start_p = max(1, current_page - 2)
                end_p = min(total_pages, current_page + 2)

                # Always show first page
                if start_p > 1:
                    pagination_html += make_page_link(1, "1")
                    if start_p > 2:
                        pagination_html += '<span class="page-link disabled">...</span>'

                for p in range(start_p, end_p + 1):
                    pagination_html += make_page_link(
                        p, str(p), active=(p == current_page)
                    )

                # Always show last page
                if end_p < total_pages:
                    if end_p < total_pages - 1:
                        pagination_html += '<span class="page-link disabled">...</span>'
                    pagination_html += make_page_link(total_pages, str(total_pages))

                # Next
                pagination_html += make_page_link(
                    current_page + 1, "&rarr;", disabled=(current_page == total_pages)
                )

                pagination_html += "</div>"

            # Meta Text
            start_display = start_idx + 1 if total_count > 0 else 0
            end_display = min(end_idx, total_count)
            meta_text = f"Showing {start_display}-{end_display} of {total_count} {'essay' if total_count == 1 else 'essays'}"

            html = f"""
            <html>
            <head>
                <title>Essayism</title>
                <meta name="csrf-token" content="{CSRF_TOKEN}">
                {CSS}
            </head>
            <body>
                <div class="site-header">
                    <img src="/logo.png" class="site-logo" alt="Logo" onerror="this.style.display='none'">
                    <h1>Essayism</h1>
                    <a href="/logout" class="btn" style="margin-left: auto; background-color: #333; border: 1px solid #444; text-decoration: none;">Logout</a>
                </div>
                
                <form action="/" method="get" class="search-bar">
                    <input type="text" name="q" value="{search_query}" placeholder="Search..." class="search-input">
                    <select name="class" class="search-input" style="flex-grow: 0; width: auto; min-width: 150px;">
                        {filter_options}
                    </select>
                    {f'<input type="hidden" name="sort" value="{sort_mode}">' if sort_mode else ""}
                    <button type="submit" class="search-btn">Search</button>
                </form>

                <div class="header-controls">
                    <span class="meta">{meta_text}</span>
                    <div style="display:flex; gap:5px; align-items:center;">
                        <input type="file" id="restoreInput" style="display: none;" accept=".zip" onchange="uploadBackup(this)">
                        <a href="/?action=create" class="btn btn-primary" style="margin-right:5px;text-decoration:none;">New Essay</a>
                        <a href="/download_zip" class="btn" style="margin-right:5px;text-decoration:none;">Backup</a>
                        <a href="#" class="btn" style="margin-right:15px;text-decoration:none;" onclick="document.getElementById('restoreInput').click()">Restore</a>
                        
                        <a href="/?sort=date{base_params}" class="{sort_cls("date")}" style="text-decoration:none;">Newest</a>
                        <a href="/?sort=grade{base_params}" class="{sort_cls("grade")}" style="text-decoration:none;">Highest Grade</a>
                    </div>
                </div>

                <ul class="essay-list">
                    {list_items}
                </ul>
                
                {pagination_html}
                
                <script>
                async function uploadBackup(input) {{
                    if (input.files.length === 0) return;
                    const file = input.files[0];
                    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
                    
                    if (!confirm("This will upload '" + file.name + "' and repopulate the essays folder. Existing files with conflict will be renamed. Continue?")) {{
                        input.value = '';
                        return;
                    }}

                    try {{
                        const response = await fetch('/upload_zip', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/zip',
                                'X-Filename': file.name,
                                'X-CSRF-Token': csrfToken
                            }},
                            body: file
                        }});
                        
                        if (response.ok) {{
                            const text = await response.text();
                            alert(text);
                            window.location.reload();
                        }} else {{
                            alert('Error uploading file.');
                        }}
                    }} catch (e) {{
                        alert('Upload failed: ' + e);
                    }}
                }}
                </script>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            # Handle static files or other paths via default handler
            super().do_GET()


if __name__ == "__main__":
    if not os.path.exists(ESSAY_DIR):
        os.makedirs(ESSAY_DIR)

    with socketserver.TCPServer(("", PORT), EssayHandler) as httpd:
        print(f"Serving at http://localhost:{PORT}")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
