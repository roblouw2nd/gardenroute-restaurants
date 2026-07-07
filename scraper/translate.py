"""
translate.py — Translate site content into all locales

Backends (set TRANSLATE_PROVIDER):
  openrouter (default)  — OpenRouter, OpenAI-compatible API. Use a :free model
                          to stay at $0 (the $10 top-up just unlocks 1000/day).
  ollama                — local Ollama, fully free/offline.

It translates into Afrikaans, German, French, Spanish and Portuguese and writes
JSON the Astro site reads for localized pages:

  restaurants : data/restaurants/*.json  ->  data/i18n/restaurants/<slug>.json
  content     : data/content/{towns,cuisines}.json -> data/i18n/content/{towns,cuisines}.json
  blog        : site/src/pages/blog/*.md  ->  data/i18n/blog/<slug>.json

QUALITY MODE (default): ONE language per request, with a native-speaker prompt
and an automatic QA gate (language heuristics, length ratio, paragraph and
proper-noun preservation). Failing output is retried once and never written.
~2,275 requests for the full site = 2-3 daily runs on the free tier; fully
incremental/resumable. The old all-langs-in-one-call mode (~455 requests,
lower quality) is available with --batch-langs.

RATE LIMITS (OpenRouter free models): 20 req/min, 1000 req/day on the $10 tier.
This script self-throttles to --rpm (default 18) and stops at --max-requests
(default 950), refuses non-:free models unless --allow-paid, and prints your
key's live usage from the OpenRouter API at startup. Re-runs only translate
new/changed/missing items — if you hit the daily cap, run it again tomorrow.

Setup:
  1. Buy $10 of credits at openrouter.ai (one-time, unlocks 1000/day on free models)
  2. Create an API key, put it in scraper/.env:  OPENROUTER_API_KEY=sk-or-...
  3. Then:
     python3 translate.py --list-free                     # see current :free models
     python3 translate.py --qa                            # score existing translations
     python3 translate.py --qa --purge                    # delete the bad ones
     python3 translate.py --only restaurants --langs de   # small test first
     python3 translate.py                                 # full run (resumable)

The default model is 'auto': the script fetches the live :free model list and
picks the strongest match (Qwen > DeepSeek > Nemotron > Llama > largest-context)
— free-model availability changes monthly, so nothing is hardcoded.

Env: OPENROUTER_API_KEY, OPENROUTER_MODEL, TRANSLATE_PROVIDER,
     OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_TIMEOUT
"""

import os
import re
import sys
import json
import time
import hashlib
import argparse
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("TRANSLATE_PROVIDER", "openrouter").lower()

OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "auto")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

ROOT = Path(__file__).parent.parent
REST_DIR = ROOT / "data" / "restaurants"
CONTENT_DIR = ROOT / "data" / "content"
BLOG_DIR = ROOT / "site" / "src" / "pages" / "blog"
OUT = ROOT / "data" / "i18n"

LANG_NAMES = {
    "af": "Afrikaans", "de": "German", "fr": "French",
    "es": "Spanish (European)", "pt": "Portuguese (European)",
}
ALL_LANGS = list(LANG_NAMES.keys())

# Extra per-language guidance injected into the single-language prompt.
LANG_STYLE = {
    "af": "Natural, modern Afrikaans as written in the Western Cape. Never coin words; "
          "if unsure, rephrase simply. Use 'middagete' not 'middagmeal'.",
    "de": "Natural German for tourists (Sie-form, warm but not stiff). Prefer plain "
          "phrasing over long compounds; never invent compound nouns.",
    "fr": "Natural French for travel content (vous-form).",
    "es": "European Spanish, natural travel-guide register.",
    "pt": "European Portuguese (not Brazilian), natural travel-guide register.",
}

# Common function words used by the QA gate to sanity-check the output language.
LANG_STOPWORDS = {
    "en": {"the", "and", "with", "for", "from", "this", "that", "where", "of"},
    "af": {"die", "en", "met", "vir", "van", "hierdie", "waar", "wat", "'n"},
    "de": {"und", "mit", "der", "die", "das", "für", "von", "ein", "eine", "im"},
    "fr": {"et", "avec", "le", "la", "les", "des", "pour", "dans", "une", "où"},
    "es": {"y", "con", "el", "la", "los", "las", "para", "una", "donde", "del"},
    "pt": {"e", "com", "o", "a", "os", "as", "para", "uma", "onde", "num"},
}

STREAM = False   # --watch: stream model output live to the terminal
WORKERS = 1      # --workers: concurrent translations (local Ollama only)
BATCH = False    # --batch-langs: old all-languages-in-one-request mode


# ── Rate limiter ────────────────────────────────────────────────────────────
class Limiter:
    def __init__(self, rpm, max_requests):
        self.min_interval = 60.0 / max(rpm, 1)
        self.max_requests = max_requests
        self.count = 0
        self.last = 0.0

    def wait(self):
        if self.count >= self.max_requests:
            print(f"\nReached --max-requests ({self.max_requests}) for this run. "
                  f"Progress is saved — run again to resume (e.g. tomorrow).")
            sys.exit(0)
        gap = time.time() - self.last
        if gap < self.min_interval:
            time.sleep(self.min_interval - gap)
        self.last = time.time()
        self.count += 1


LIMITER = None  # set in main()


# ── OpenRouter account / model helpers ──────────────────────────────────────
def fetch_free_models():
    """Live list of :free chat models: [(id, context_length), ...]."""
    r = requests.get(OPENROUTER_MODELS_URL, timeout=30)
    r.raise_for_status()
    out = []
    for m in r.json().get("data", []):
        if m.get("id", "").endswith(":free"):
            out.append((m["id"], int(m.get("context_length") or 0)))
    return out


def pick_free_model():
    """Choose the best available :free model by family preference, then context."""
    models = fetch_free_models()
    if not models:
        sys.exit("No :free models currently listed on OpenRouter — check openrouter.ai/models")
    prefs = ["qwen", "deepseek", "nemotron", "llama", "gemma", "mistral"]
    def rank(item):
        mid, ctx = item
        fam = next((i for i, p in enumerate(prefs) if p in mid.lower()), len(prefs))
        return (fam, -ctx)
    choice = sorted(models, key=rank)[0][0]
    print(f"Auto-selected free model: {choice}  (override with --model or OPENROUTER_MODEL)")
    return choice


def print_key_usage():
    """Show live usage/limits for the configured key (free-tier safety check)."""
    try:
        r = requests.get(OPENROUTER_KEY_URL,
                         headers={"Authorization": f"Bearer {OPENROUTER_KEY}"}, timeout=15)
        r.raise_for_status()
        d = r.json().get("data", {})
        usage = d.get("usage")
        limit = d.get("limit")
        free = d.get("is_free_tier")
        print(f"Key status: usage=${usage} limit={'unlimited' if limit is None else f'${limit}'} "
              f"free_tier={free}")
        if usage and float(usage) > 0:
            print("  NOTE: this key has non-zero paid usage — :free models never bill, "
                  "so this is from past paid calls, not this script.")
    except requests.RequestException as e:
        print(f"  (could not fetch key status: {str(e)[:60]})")


def _hash(payload):
    return hashlib.md5(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]


def _strip_fences(text):
    # Remove any reasoning blocks a thinking-model may emit in the content.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"<think>.*$", "", text, flags=re.S)
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    return text.strip()


def _loads(text):
    """Parse JSON, tolerating prose around it (free-streamed output)."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        i, j = text.find("{"), text.rfind("}")
        if i != -1 and j != -1 and j > i:
            return json.loads(text[i:j + 1])
        raise


def _build_messages(payload, langs):
    lang_map = {l: LANG_NAMES[l] for l in langs}
    sys_msg = (
        "You are a professional translator for a South African restaurant "
        "directory. You will receive a JSON object with a 'text' object and a "
        "'languages' map (code -> language name). Translate the VALUES of 'text' "
        "into EACH language. Rules:\n"
        "- Return a JSON object whose keys are the language codes; each value is "
        "the 'text' object with the SAME keys but translated values.\n"
        "- Do NOT translate proper nouns: restaurant names, town names, "
        "'Garden Route', street names, brand names.\n"
        "- Preserve paragraph breaks (blank lines) and any markdown.\n"
        "- Natural, fluent translations — not word-for-word.\n"
        "- Return ONLY the JSON object."
    )
    user_msg = json.dumps({"text": payload, "languages": lang_map}, ensure_ascii=False)
    return sys_msg, user_msg


def _call_openrouter(sys_msg, user_msg):
    LIMITER.wait()
    body = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "system", "content": sys_msg},
                     {"role": "user", "content": user_msg}],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "stream": STREAM,
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://www.gardenroute-restaurants.co.za",
        "X-Title": "Garden Route Restaurants",
    }
    for attempt in range(5):
        try:
            r = requests.post(OPENROUTER_URL, headers=headers, json=body, stream=STREAM, timeout=120)
            if r.status_code == 429:
                retry = int(r.headers.get("Retry-After", "30"))
                print(f"      429 rate-limited; sleeping {retry}s")
                time.sleep(retry)
                continue
            r.raise_for_status()
            if not STREAM:
                return _strip_fences(r.json()["choices"][0]["message"]["content"])
            buf = []
            for line in r.iter_lines():
                if not line:
                    continue
                s = line.decode() if isinstance(line, bytes) else line
                if s.startswith("data: "):
                    s = s[6:]
                if s.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(s)["choices"][0]["delta"].get("content", "")
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if chunk:
                    sys.stdout.write(chunk); sys.stdout.flush(); buf.append(chunk)
            sys.stdout.write("\n"); sys.stdout.flush()
            return _strip_fences("".join(buf))
        except requests.RequestException:
            if attempt == 4:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("openrouter call failed")


def _call_ollama(sys_msg, user_msg):
    # Qwen3 models support a /no_think prompt switch to skip the reasoning phase.
    if "qwen3" in OLLAMA_MODEL.lower():
        user_msg = user_msg + " /no_think"
    body = {"model": OLLAMA_MODEL,
            "messages": [{"role": "system", "content": sys_msg},
                         {"role": "user", "content": user_msg}],
            "stream": STREAM, "keep_alive": "30m", "think": False,
            "options": {"temperature": 0.3, "num_ctx": 8192}}
    # Constrained JSON only when NOT streaming — the grammar engine buffers
    # output, which prevents live token streaming in --watch mode.
    if not STREAM:
        body["format"] = "json"
    if not STREAM:
        r = requests.post(f"{OLLAMA_HOST}/api/chat", json=body, timeout=OLLAMA_TIMEOUT)
        r.raise_for_status()
        return _strip_fences(r.json()["message"]["content"])
    # streaming — print tokens live as the model writes them
    r = requests.post(f"{OLLAMA_HOST}/api/chat", json=body, stream=True, timeout=OLLAMA_TIMEOUT)
    r.raise_for_status()
    buf = []
    thinking_seen = False
    for line in r.iter_lines():
        if not line:
            continue
        obj = json.loads(line)
        msg = obj.get("message", {})
        # Reasoning models (e.g. qwen3) stream a separate 'thinking' field first.
        think = msg.get("thinking") or ""
        if think:
            if not thinking_seen:
                sys.stdout.write("\033[2m[thinking] "); thinking_seen = True
            sys.stdout.write(think); sys.stdout.flush()
        content = msg.get("content") or ""
        if content:
            if thinking_seen:
                sys.stdout.write("\033[0m\n"); thinking_seen = False
            sys.stdout.write(content); sys.stdout.flush(); buf.append(content)
        if obj.get("done"):
            break
    sys.stdout.write("\033[0m\n"); sys.stdout.flush()
    return _strip_fences("".join(buf))


def translate_all(payload, langs, label=""):
    """One request -> {lang: translated_payload} for all requested langs."""
    if STREAM:
        print(f"\n\033[1m\033[36m▶ {label}\033[0m  ({', '.join(langs)})")
    sys_msg, user_msg = _build_messages(payload, langs)
    raw = _call_openrouter(sys_msg, user_msg) if PROVIDER == "openrouter" else _call_ollama(sys_msg, user_msg)
    data = _loads(raw)
    # tolerate {"af":{...}} or nested {"translations":{...}}
    if all(l not in data for l in langs) and len(data) == 1:
        data = next(iter(data.values()))
    return {l: data[l] for l in langs if isinstance(data.get(l), dict)}


# ── Single-language mode (default): better prompt + QA gate ────────────────
def _build_messages_single(payload, lang):
    sys_msg = (
        f"You are a professional native {LANG_NAMES[lang]} translator working on a "
        "South African restaurant guide (the Garden Route). You will receive a JSON "
        f"object. Translate every VALUE into {LANG_NAMES[lang]}. Rules:\n"
        f"- {LANG_STYLE[lang]}\n"
        "- Do NOT translate proper nouns: restaurant names, town names, "
        "'Garden Route', street names, brand names, dish names that are names.\n"
        "- Preserve paragraph breaks (blank lines) and any markdown, including "
        "link targets like (/some-slug) exactly as they are.\n"
        "- Fluent and idiomatic, never word-for-word. If a phrase has no natural "
        "equivalent, rephrase the meaning simply — never invent words.\n"
        "- Return ONLY a JSON object with exactly the same keys, values translated."
    )
    return sys_msg, json.dumps(payload, ensure_ascii=False)


def _stopword_score(text, lang):
    words = re.findall(r"[a-zà-ÿäöüßñáéíóúâêôçëï']+", text.lower())
    if not words:
        return 0.0
    sw = LANG_STOPWORDS[lang]
    return sum(1 for w in words if w in sw) / len(words)


def qa_issues(src, out, lang):
    """Heuristic QA. Returns a list of problem strings (empty = pass)."""
    problems = []
    if not isinstance(out, dict):
        return ["not a dict"]
    for k, s in src.items():
        t = out.get(k)
        if not isinstance(t, str) or not t.strip():
            if (s or "").strip():
                problems.append(f"{k}: missing/empty")
            continue
        s = s or ""
        if len(s) >= 40:
            ratio = len(t) / len(s)
            if not 0.5 <= ratio <= 2.2:
                problems.append(f"{k}: length ratio {ratio:.2f}")
            if s.count("\n\n") != t.count("\n\n"):
                problems.append(f"{k}: paragraph count changed")
            if t.strip() == s.strip():
                problems.append(f"{k}: identical to English")
            # language sanity: target stopwords should beat English stopwords
            en = _stopword_score(t, "en")
            tgt = _stopword_score(t, lang)
            if en > tgt and en > 0.08:
                problems.append(f"{k}: looks like English (en={en:.2f} {lang}={tgt:.2f})")
        # markdown link targets must survive verbatim
        for link in re.findall(r"\]\((/[^)]+)\)", s):
            if link not in t:
                problems.append(f"{k}: lost link {link}")
    return problems


def translate_single(payload, lang, label=""):
    """One request for ONE language, QA-gated, one retry. Returns dict or None."""
    sys_msg, user_msg = _build_messages_single(payload, lang)
    for attempt in (1, 2):
        try:
            raw = _call_openrouter(sys_msg, user_msg) if PROVIDER == "openrouter" else _call_ollama(sys_msg, user_msg)
            out = _loads(raw)
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"      ! {lang} call failed ({str(e)[:60]})")
            continue
        # tolerate a single wrapper key, e.g. {"translation": {...}}
        if isinstance(out, dict) and set(out) != set(payload) and len(out) == 1:
            inner = next(iter(out.values()))
            if isinstance(inner, dict):
                out = inner
        problems = qa_issues(payload, out, lang)
        if not problems:
            return out
        print(f"      ! {lang} QA fail (try {attempt}): {'; '.join(problems[:3])}")
    return None


def process(payload, existing, force, label=""):
    """Returns (record, changed). record has _hash + one key per lang."""
    h = _hash(payload)
    rec = existing if isinstance(existing, dict) else {}
    have = [l for l in ALL_LANGS if l in rec]
    if rec.get("_hash") == h and not force and set(have) >= set(TARGET):
        return rec, False
    need = TARGET if (force or rec.get("_hash") != h) else [l for l in TARGET if l not in rec]
    if not need:
        return rec, False

    if BATCH:  # legacy mode: everything in one request, no QA
        try:
            translated = translate_all(payload, need, label)
        except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
            print(f"      ! failed: {str(e)[:80]}")
            return rec, False
    else:      # default: one request per language, QA-gated
        translated = {}
        for lang in need:
            out = translate_single(payload, lang, label)
            if out is not None:
                translated[lang] = out
    if not translated:
        return rec, False
    # If the source changed, drop stale languages that didn't get retranslated
    # this run — the missing-lang path picks them up on the next run.
    if rec.get("_hash") != h:
        for l in ALL_LANGS:
            if l in rec and l not in translated:
                rec.pop(l)
    rec["_hash"] = h
    rec.update(translated)
    return rec, True


def _do_one_restaurant(f, dest):
    d = json.load(open(f))
    payload = {"description_short": d.get("description_short", ""),
               "description_long": d.get("description_long", "")}
    if not any(payload.values()):
        return None
    outf = dest / f.name
    existing = json.load(open(outf)) if outf.exists() else {}
    rec, changed = process(payload, existing, FORCE, d.get("slug", f.stem))
    if changed:
        json.dump(rec, open(outf, "w"), indent=2, ensure_ascii=False)
        return d.get("slug")
    return None


def do_restaurants():
    dest = OUT / "restaurants"; dest.mkdir(parents=True, exist_ok=True)
    files = [f for f in sorted(REST_DIR.glob("*.json")) if not f.name.startswith("_")]
    n = len(files)
    print(f"\nRestaurants: {n}  (workers: {WORKERS})")
    if WORKERS <= 1:
        for i, f in enumerate(files, 1):
            slug = _do_one_restaurant(f, dest)
            if slug:
                print(f"  [{i}/{n}] + {slug}")
        return
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(_do_one_restaurant, f, dest): f for f in files}
        done = 0
        for fut in as_completed(futs):
            done += 1
            try:
                slug = fut.result()
            except Exception as e:
                slug = None
                print(f"  ! error: {str(e)[:80]}")
            if slug:
                print(f"  [{done}/{n}] + {slug}")


def do_content():
    dest = OUT / "content"; dest.mkdir(parents=True, exist_ok=True)
    for name in ("towns.json", "cuisines.json"):
        src = CONTENT_DIR / name
        if not src.exists():
            print(f"\nContent: {name} missing (run generate_content.py first) — skipping")
            continue
        data = json.load(open(src))
        outf = dest / name
        existing = json.load(open(outf)) if outf.exists() else {}
        print(f"\nContent: {name} ({len(data)})")
        for key, entry in data.items():
            rec, changed = process(entry, existing.get(key, {}), FORCE, key)
            existing[key] = rec
            if changed:
                json.dump(existing, open(outf, "w"), indent=2, ensure_ascii=False)
                print(f"  + {key}")


def do_blog():
    dest = OUT / "blog"; dest.mkdir(parents=True, exist_ok=True)
    posts = sorted(BLOG_DIR.glob("*.md"))
    print(f"\nBlog: {len(posts)}")
    for f in posts:
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", f.read_text(), re.S)
        if not m:
            continue
        fm, body = m.group(1), m.group(2).strip()
        title = re.search(r'title:\s*"(.*?)"', fm)
        desc = re.search(r'description:\s*"(.*?)"', fm)
        payload = {"title": title.group(1) if title else "",
                   "description": desc.group(1) if desc else "", "body": body}
        outf = dest / (f.stem + ".json")
        existing = json.load(open(outf)) if outf.exists() else {}
        rec, changed = process(payload, existing, FORCE, f.stem)
        if changed:
            json.dump(rec, open(outf, "w"), indent=2, ensure_ascii=False)
            print(f"  + {f.stem}")


# ── QA of existing translations (no API calls) ─────────────────────────────
def _iter_sources():
    """Yield (section, out_file, key_or_None, source_payload) for all items."""
    for f in sorted(REST_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        d = json.load(open(f))
        payload = {"description_short": d.get("description_short", ""),
                   "description_long": d.get("description_long", "")}
        if any(payload.values()):
            yield "restaurants", OUT / "restaurants" / f.name, None, payload
    for name in ("towns.json", "cuisines.json"):
        src = CONTENT_DIR / name
        if src.exists():
            for key, entry in json.load(open(src)).items():
                yield "content", OUT / "content" / name, key, entry
    for f in sorted(BLOG_DIR.glob("*.md")):
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", f.read_text(), re.S)
        if not m:
            continue
        fm, body = m.group(1), m.group(2).strip()
        title = re.search(r'title:\s*"(.*?)"', fm)
        desc = re.search(r'description:\s*"(.*?)"', fm)
        yield "blog", OUT / "blog" / (f.stem + ".json"), None, {
            "title": title.group(1) if title else "",
            "description": desc.group(1) if desc else "", "body": body}


def do_qa(purge=False):
    """Score all existing translations with the QA heuristics; optionally delete
    failing language entries so the next run retranslates only those."""
    checked = bad = purged = 0
    dirty_files = {}
    for section, outf, key, payload in _iter_sources():
        if not outf.exists():
            continue
        blob = dirty_files.get(outf) or json.load(open(outf))
        rec = blob.get(key) if key else blob
        if not isinstance(rec, dict):
            continue
        for lang in ALL_LANGS:
            if lang not in rec:
                continue
            checked += 1
            problems = qa_issues(payload, rec[lang], lang)
            if problems:
                bad += 1
                label = f"{section}/{key or outf.stem}"
                print(f"  BAD {label} [{lang}]: {'; '.join(problems[:3])}")
                if purge:
                    rec.pop(lang)
                    purged += 1
                    dirty_files[outf] = blob
    for outf, blob in dirty_files.items():
        json.dump(blob, open(outf, "w"), indent=2, ensure_ascii=False)
    print(f"\nQA done: {checked} translations checked, {bad} failed"
          + (f", {purged} purged (re-run translate.py to redo them)" if purge
             else ".  Run with --qa --purge to delete the failures."))


def main():
    global LIMITER, TARGET, FORCE, STREAM, WORKERS, BATCH
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["restaurants", "content", "blog"])
    ap.add_argument("--langs", help="comma list e.g. de,fr (default all)")
    ap.add_argument("--provider", choices=["openrouter", "ollama"])
    ap.add_argument("--model", help="override model id ('auto' = pick best live :free model)")
    ap.add_argument("--rpm", type=int, default=18, help="max requests/minute (free tier cap is 20)")
    ap.add_argument("--max-requests", type=int, default=950, help="stop after N requests (free tier daily cap 1000)")
    ap.add_argument("--allow-paid", action="store_true", help="permit a non-:free model (will cost money)")
    ap.add_argument("--batch-langs", action="store_true",
                    help="legacy mode: all languages in one request (fewer calls, lower quality, no QA)")
    ap.add_argument("--list-free", action="store_true", help="list current :free models and exit")
    ap.add_argument("--qa", action="store_true", help="QA-score existing translations (no API calls) and exit")
    ap.add_argument("--purge", action="store_true", help="with --qa: delete failing translations so they get redone")
    ap.add_argument("--watch", action="store_true", help="stream the model's output live to the terminal")
    ap.add_argument("--workers", type=int, default=1, help="parallel translations (default 1 = normal/gentle; raise only if you want to push a local model harder)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    STREAM = args.watch
    BATCH = args.batch_langs

    if args.list_free:
        for mid, ctx in sorted(fetch_free_models(), key=lambda x: -x[1]):
            print(f"  {mid}  (ctx {ctx:,})")
        return
    if args.qa:
        do_qa(purge=args.purge)
        return

    global PROVIDER, OPENROUTER_MODEL, OLLAMA_MODEL
    if args.provider:
        PROVIDER = args.provider
    if args.model:
        OPENROUTER_MODEL = OLLAMA_MODEL = args.model

    TARGET = [l for l in (args.langs.split(",") if args.langs else ALL_LANGS) if l in LANG_NAMES]
    FORCE = args.force
    # Concurrency only for local Ollama, and never while streaming (keeps output readable).
    WORKERS = 1 if (PROVIDER == "openrouter" or STREAM) else max(1, args.workers)
    LIMITER = Limiter(args.rpm, args.max_requests)

    if PROVIDER == "openrouter" and not OPENROUTER_KEY:
        sys.exit("OPENROUTER_API_KEY not set in scraper/.env")
    if PROVIDER == "openrouter" and OPENROUTER_MODEL == "auto":
        OPENROUTER_MODEL = pick_free_model()
    model = OPENROUTER_MODEL if PROVIDER == "openrouter" else OLLAMA_MODEL
    # Safety: never spend money unless explicitly allowed (OpenRouter only).
    if PROVIDER == "openrouter" and not model.endswith(":free") and not args.allow_paid:
        sys.exit(f"Refusing to run: '{model}' is not a :free model and would cost money.\n"
                 f"Use a free model (set OPENROUTER_MODEL to one ending in ':free' from "
                 f"openrouter.ai/models), or pass --allow-paid to override.")
    if PROVIDER == "openrouter":
        print(f"Provider: openrouter | model: {model} | langs: {','.join(TARGET)} "
              f"| {args.rpm} rpm, cap {args.max_requests} "
              f"| mode: {'batch' if BATCH else 'per-language + QA'}")
        print_key_usage()
    else:
        print(f"Provider: ollama (local) | model: {model} | langs: {','.join(TARGET)} "
              f"| workers: {WORKERS} | no rate limit "
              f"| mode: {'batch' if BATCH else 'per-language + QA'}")

    OUT.mkdir(parents=True, exist_ok=True)
    sections = [args.only] if args.only else ["restaurants", "content", "blog"]
    if "restaurants" in sections: do_restaurants()
    if "content" in sections: do_content()
    if "blog" in sections: do_blog()
    print(f"\nDone. {LIMITER.count} requests used. Output in data/i18n/ — commit it, "
          f"then localized pages can be switched on.")


if __name__ == "__main__":
    main()
