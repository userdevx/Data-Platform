import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from engine.search.search_router import search_web


PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = PROJECT_ROOT / "engine" / "agents"
INPUT_FILE = AGENT_DIR / "agent_input.json"
OUTPUT_FILE = AGENT_DIR / "agent_output.json"
LOG_FILE = AGENT_DIR / "agent.log"
RECORDS_FILE = PROJECT_ROOT / "data" / "records.jsonl"
PAIGE_NAME = "paige"


class DuckDuckGoResultParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_result_link = False
        self.current_href = ""
        self.current_text = []
        self.results = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        class_value = attrs_dict.get("class", "")

        if tag == "a" and "result__a" in class_value:
            self.in_result_link = True
            self.current_href = attrs_dict.get("href", "")
            self.current_text = []

    def handle_data(self, data):
        if self.in_result_link:
            clean = data.strip()
            if clean:
                self.current_text.append(clean)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_result_link:
            title = " ".join(self.current_text).strip()

            if title:
                real_url = clean_duckduckgo_url(self.current_href)
                domain = get_domain(real_url)

                self.results.append(
                    {
                        "title": title,
                        "url": real_url,
                        "domain": domain,
                    }
                )

            self.in_result_link = False
            self.current_href = ""
            self.current_text = []


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def log(message):
    AGENT_DIR.mkdir(parents=True, exist_ok=True)

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(f"{utc_now()} {message}\n")


def read_json(path):
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def append_record(payload):
    RECORDS_FILE.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "source": "paige",
        "category": "internet_data",
        "record_type": "search_result",
        "input": payload.get("input"),
        "action": payload.get("action"),
        "result": payload.get("result"),
        "unit": "text",
        "timestamp": payload.get("timestamp"),
        "agent_name": payload.get("agent_name"),
        "status": payload.get("status"),
    }

    with RECORDS_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")


def clean_duckduckgo_url(raw_url):
    if not raw_url:
        return ""

    decoded_url = raw_url.strip()

    if decoded_url.startswith("//"):
        decoded_url = "https:" + decoded_url

    parsed = urllib.parse.urlparse(decoded_url)
    params = urllib.parse.parse_qs(parsed.query)

    real_url = params.get("uddg", [decoded_url])[0]
    real_url = urllib.parse.unquote(real_url)

    if real_url.startswith("//"):
        real_url = "https:" + real_url

    return real_url


def get_domain(url):
    if not url:
        return "unknown"

    parsed = urllib.parse.urlparse(url)

    if parsed.netloc:
        return parsed.netloc.replace("www.", "")

    return "unknown"


def search_duckduckgo(query, limit=5):
    search_url = "https://duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})

    request = urllib.request.Request(
        search_url,
        headers={
            "User-Agent": "Mozilla/5.0 DataPlatformPaige/1.0",
        },
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        html = response.read().decode("utf-8", errors="replace")

    parser = DuckDuckGoResultParser()
    parser.feed(html)

    return parser.results[:limit]


def fallback_answer(query):
    return (
        f"Paige received your question: {query}\n\n"
        "Live source links were not available from the current search provider. "
        "The system is working, but the provider did not return readable result links.\n\n"
        "Next backend improvement: connect Paige to a more reliable provider or OpenAI web search."
    )


def format_search_result(query, results):
    if not results:
        return fallback_answer(query)

    first_result = results[0]

    if first_result.get("answer_type") == "direct_answer":
        return first_result.get("snippet", "Paige could not generate an answer.")

    lines = [f"Top results for: {query}", ""]

    for index, item in enumerate(results, start=1):
        title = item.get("title", "Untitled result")
        domain = item.get("domain", "unknown")
        url = item.get("url", "")

        lines.append(f"{index}. {title}")
        lines.append(f"   Source: {domain}")

        if url:
            lines.append(f"   URL: {url}")

        lines.append("")

    return "\n".join(lines).strip()


def create_error_output(user_input, action, error_message):
    return {
        "source": "paige",
        "category": "internet_data",
        "record_type": "search_result",
        "input": user_input,
        "action": action,
        "result": f"Paige failed safely: {error_message}",
        "unit": "text",
        "timestamp": utc_now(),
        "agent_name": PAIGE_NAME,
        "status": "error",
    }


def process_task(task):
    user_input = str(task.get("input", "")).strip()

    if not user_input:
        return create_error_output(
            user_input,
            "Validate question",
            "No question was provided.",
        )

    action = f"Search for: {user_input}"

    try:
        results = search_web(user_input, limit=5)
        result_text = format_search_result(user_input, results)

        return {
            "source": "paige",
            "category": "internet_data",
            "record_type": "search_result",
            "input": user_input,
            "action": action,
            "result": result_text,
            "unit": "text",
            "timestamp": utc_now(),
            "agent_name": PAIGE_NAME,
            "status": "complete",
        }

    except Exception as error:
        return create_error_output(user_input, action, str(error))


def mark_task_complete(task):
    task["status"] = "complete"
    task["completed_at"] = utc_now()
    write_json(INPUT_FILE, task)


def main():
    AGENT_DIR.mkdir(parents=True, exist_ok=True)
    log("Paige started.")

    last_processed_input = ""

    while True:
        task = read_json(INPUT_FILE)

        if not task:
            time.sleep(1)
            continue

        task_input = str(task.get("input", "")).strip()
        task_status = task.get("status")

        if task_status == "new" and task_input and task_input != last_processed_input:
            log(f"Processing question: {task_input}")

            output = process_task(task)

            write_json(OUTPUT_FILE, output)
            append_record(output)
            mark_task_complete(task)

            last_processed_input = task_input
            log(f"Answer saved: {task_input}")

        time.sleep(1)


if __name__ == "__main__":
    main()
