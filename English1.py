from flask import Flask, request, jsonify
import os
import re
import json
import sqlite3
import requests
import cloudscraper
import html as html_lib
from bs4 import BeautifulSoup
from pathlib import Path

app = Flask(__name__)

DATA_DIR = os.environ.get('WORD_ROOT_DATA_DIR', str(Path(__file__).with_name('data')))
os.makedirs(DATA_DIR, exist_ok=True)

ETYMOLOGY_CACHE_DIR = os.path.join(DATA_DIR, "etymology_cache")
os.makedirs(ETYMOLOGY_CACHE_DIR, exist_ok=True)


def safe_root(root):
    return re.sub(r'[^a-zA-Z\-]', '', root)


_scraper = None


def _get_scraper():
    global _scraper
    if _scraper is None:
        _scraper = cloudscraper.create_scraper()
    return _scraper


_proxy_url = os.environ.get('WORD_ROOT_PROXY')
PROXIES = {'http': _proxy_url, 'https': _proxy_url} if _proxy_url else None

CET_DB_PATH = os.environ.get('CET_DB_PATH', str(Path(__file__).with_name('cet_etymology.db')))
app.config['CET_DB_PATH'] = CET_DB_PATH
from word_learning import learning
app.register_blueprint(learning)


@app.get('/openapi.json')
def openapi_schema():
    with open(os.path.join(os.path.dirname(__file__), 'word_root_api.json'), encoding='utf-8') as schema_file:
        return jsonify(json.load(schema_file))


class LookupUnavailable(Exception):
    """An upstream request failed; absence of a word has not been established."""


def meaningful_etymology(text):
    if not isinstance(text, str) or not text.strip():
        return False
    return "internet's go-to source" not in text.lower() and 'quick and reliable accounts of the origin' not in text.lower()


def query_cet_db(word):
    """从本地 CET 词源数据库查询，返回 dict 或 None"""
    if not os.path.exists(CET_DB_PATH):
        return None
    conn = sqlite3.connect(CET_DB_PATH)
    c = conn.cursor()
    c.execute('SELECT level, etymology_clean, pie_root, ipa FROM cet_words WHERE word = ?', (word.lower(),))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "word": word,
        "level": row[0],
        "etymology": row[1],
        "pie_root": row[2],
        "ipa": row[3],
        "source": "cet_db"
    }


def search_cet_db(prefix, limit=20):
    """前缀模糊搜索 CET 数据库"""
    if not os.path.exists(CET_DB_PATH):
        return []
    conn = sqlite3.connect(CET_DB_PATH)
    c = conn.cursor()
    c.execute('SELECT word, level, pie_root FROM cet_words WHERE word LIKE ? ORDER BY word LIMIT ?',
              (prefix.lower() + '%', limit))
    rows = c.fetchall()
    conn.close()
    return [{"word": r[0], "level": r[1], "pie_root": r[2]} for r in rows]


def fetch_from_etymonline(word):
    """从 Etymonline 抓取词源（备选，经常超时或被 Cloudflare 拦截）"""
    url = f"https://www.etymonline.com/word/{word}"
    scraper = _get_scraper()

    for attempt in range(2):
        try:
            resp = scraper.get(url, timeout=10, proxies=PROXIES)
            if resp.status_code == 404:
                return None
            if resp.status_code != 200:
                continue

            page = resp.text
            if "Just a moment" in page:
                import time
                time.sleep(2)
                continue

            soup = BeautifulSoup(page, "html.parser")

            prose = soup.find("section", class_=re.compile(r"prose-lg"))
            if prose:
                paragraphs = prose.find_all("p")
                texts = []
                for p in paragraphs:
                    t = p.get_text(separator=" ", strip=True)
                    t = re.sub(r'\s+', ' ', t)
                    if t and "Want to remove ads" not in t:
                        texts.append(t)
                if texts:
                    return " ".join(texts)[:2000]

            meta = soup.find("meta", attrs={"name": "description"})
            if meta and meta.get("content"):
                content = html_lib.unescape(meta["content"])
                if len(content) > 30 and meaningful_etymology(content):
                    return content

            return None
        except Exception:
            continue

    raise LookupUnavailable('etymonline_unavailable')


def fetch_from_wiktionary(word):
    """从 Wiktionary 获取词源（走代理）"""
    url = "https://en.wiktionary.org/w/api.php"
    params = {
        "action": "parse",
        "page": word,
        "prop": "wikitext",
        "format": "json"
    }
    headers = {"User-Agent": "DifyWordRootBot/1.0"}
    try:
        resp = requests.get(url, params=params, headers=headers,
                            timeout=15, proxies=PROXIES)
        resp.raise_for_status()
        data = resp.json()
        if 'error' in data:
            if data['error'].get('code') == 'missingtitle':
                return None
            raise LookupUnavailable('wiktionary_api_error')
        wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
        if not wikitext:
            return None
        # Only parse modern English; another language may appear earlier on the page.
        english = re.search(r'^==English==\s*\n(.*?)(?=^==[^=\n]+==\s*$|\Z)', wikitext, re.M | re.S)
        if not english:
            return None
        wikitext = english.group(1)
        marker = "===Etymology"
        idx = wikitext.find(marker)
        if idx == -1:
            marker = "==Etymology"
            idx = wikitext.find(marker)
        if idx == -1:
            return None

        next_heading = re.search(r'^={2,}[^=\n].*?={2,}\s*$', wikitext[idx + len(marker):], re.M)
        end_idx = idx + len(marker) + next_heading.start() if next_heading else len(wikitext)

        section = wikitext[idx + len(marker):end_idx].strip()
        section = re.sub(r'^=+\s*', '', section)
        section = re.sub(r'\[\[([^\]|]*\|)?([^\]]*)\]\]', r'\2', section)
        section = re.sub(r"'''?", '', section)
        section = re.sub(r'\n{3,}', '\n\n', section).strip()

        return section[:2000] if section else None
    except (requests.RequestException, ValueError) as exc:
        raise LookupUnavailable('wiktionary_unavailable') from exc


@app.route('/add_word', methods=['POST'])
def add_word():
    data = request.json
    word = data.get('word', '').strip().lower()
    root = safe_root(data.get('root', '').strip().lower())
    meaning = data.get('meaning', '').strip()
    example = data.get('example', '').strip()

    if not word or not root or not meaning:
        return jsonify({"error": "缺少参数：word、root、meaning 都是必填"}), 400

    if len(word) > 50 or len(root) > 30 or len(meaning) > 500 or len(example) > 2000:
        return jsonify({"error": "参数长度超限"}), 400

    txt_file = os.path.join(DATA_DIR, f"{root}_family.txt")
    existing_words = set()
    if os.path.exists(txt_file):
        with open(txt_file, 'r', encoding='utf-8') as f:
            existing_words = {line.strip().lower() for line in f if line.strip()}

    if word in existing_words:
        return jsonify({"status": "duplicate", "message": f"{word} 已在 {root} 家族中"})

    with open(txt_file, 'a', encoding='utf-8') as f:
        f.write(word + '\n')

    md_file = os.path.join(DATA_DIR, f"{root}_notes.md")
    if not os.path.exists(md_file):
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(f"# {root} 词根家族\n\n")
            f.write("| 单词 | 核心意象 | 例句 |\n")
            f.write("|------|----------|----------|\n")

    meaning_safe = meaning.replace("|", r"\|")
    example_safe = example.replace("|", r"\|")
    with open(md_file, 'a', encoding='utf-8') as f:
        f.write(f"| {word} | {meaning_safe} | {example_safe} |\n")

    return jsonify({
        "status": "ok",
        "word": word,
        "root": root,
        "message": f"已添加 {word} 到 {root} 家族"
    })


@app.route('/batch_add', methods=['POST'])
def batch_add():
    data = request.json
    words = data.get('words', [])

    if not isinstance(words, list) or len(words) == 0:
        return jsonify({"error": "参数 words 必须是非空数组"}), 400

    if len(words) > 100:
        return jsonify({"error": "单次最多 100 个"}), 400

    results = []
    for item in words:
        word = item.get('word', '').strip().lower()
        root = safe_root(item.get('root', '').strip().lower())
        meaning = item.get('meaning', '').strip()
        example = item.get('example', '').strip()

        if not word or not root or not meaning:
            results.append({"word": word, "status": "error", "message": "缺少必填字段"})
            continue

        if len(word) > 50 or len(root) > 30 or len(meaning) > 500 or len(example) > 2000:
            results.append({"word": word, "status": "error", "message": "长度超限"})
            continue

        txt_file = os.path.join(DATA_DIR, f"{root}_family.txt")
        existing_words = set()
        if os.path.exists(txt_file):
            with open(txt_file, 'r', encoding='utf-8') as f:
                existing_words = {line.strip().lower() for line in f if line.strip()}

        if word in existing_words:
            results.append({"word": word, "root": root, "status": "duplicate"})
            continue

        with open(txt_file, 'a', encoding='utf-8') as f:
            f.write(word + '\n')

        md_file = os.path.join(DATA_DIR, f"{root}_notes.md")
        if not os.path.exists(md_file):
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(f"# {root} 词根家族\n\n")
                f.write("| 单词 | 核心意象 | 例句 |\n")
                f.write("|------|----------|----------|\n")

        meaning_safe = meaning.replace("|", r"\|")
        example_safe = example.replace("|", r"\|")
        with open(md_file, 'a', encoding='utf-8') as f:
            f.write(f"| {word} | {meaning_safe} | {example_safe} |\n")

        results.append({"word": word, "root": root, "status": "ok"})

    added = sum(1 for r in results if r["status"] == "ok")
    dupes = sum(1 for r in results if r["status"] == "duplicate")
    errors = sum(1 for r in results if r["status"] == "error")
    return jsonify({
        "status": "ok",
        "summary": {"added": added, "duplicate": dupes, "error": errors},
        "details": results
    })


@app.route('/delete_word', methods=['POST'])
def delete_word():
    data = request.json
    word = data.get('word', '').strip().lower()
    root = safe_root(data.get('root', '').strip().lower())

    if not word or not root:
        return jsonify({"error": "缺少参数：word 和 root 都是必填"}), 400

    txt_file = os.path.join(DATA_DIR, f"{root}_family.txt")
    if not os.path.exists(txt_file):
        return jsonify({"error": f"{root} 家族不存在"}), 404

    with open(txt_file, 'r', encoding='utf-8') as f:
        lines = [line for line in f if line.strip()]

    found = any(line.strip().lower() == word for line in lines)
    if not found:
        return jsonify({"status": "not_found", "message": f"{word} 不在 {root} 家族中"})

    new_lines = [line for line in lines if line.strip().lower() != word]
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    md_file = os.path.join(DATA_DIR, f"{root}_notes.md")
    if os.path.exists(md_file):
        with open(md_file, 'r', encoding='utf-8') as f:
            md_lines = f.readlines()
        md_lines = [ml for ml in md_lines if not ml.startswith(f"| {word} |")]
        with open(md_file, 'w', encoding='utf-8') as f:
            f.writelines(md_lines)

    return jsonify({"status": "ok", "message": f"已从 {root} 家族删除 {word}"})


@app.route('/list_roots', methods=['GET'])
def list_roots():
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('_family.txt')]
    roots = [f.replace('_family.txt', '') for f in files]
    return jsonify({"roots": roots})


@app.route('/read_family/<root>', methods=['GET'])
def read_family(root):
    root = safe_root(root)
    txt_file = os.path.join(DATA_DIR, f"{root}_family.txt")
    if not os.path.exists(txt_file):
        return jsonify({"error": f"{root} 家族不存在"}), 404
    with open(txt_file, 'r', encoding='utf-8') as f:
        words = [line.strip() for line in f if line.strip()]
    return jsonify({"root": root, "count": len(words), "words": words})


@app.route('/find_word/<word>', methods=['GET'])
def find_word(word):
    word = safe_root(word.lower())
    if not word:
        return jsonify({"error": "无效单词"}), 400

    families = []
    for fname in os.listdir(DATA_DIR):
        if not fname.endswith('_family.txt'):
            continue
        root = fname.replace('_family.txt', '')
        fpath = os.path.join(DATA_DIR, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            lines = {line.strip().lower() for line in f if line.strip()}
        if word in lines:
            families.append(root)

    return jsonify({"word": word, "families": families, "count": len(families)})


@app.route('/read_notes/<root>', methods=['GET'])
def read_notes(root):
    root = safe_root(root)
    md_file = os.path.join(DATA_DIR, f"{root}_notes.md")
    if not os.path.exists(md_file):
        return jsonify({"error": f"{root} 笔记不存在"}), 404
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    # Older notes used this heading even for generated examples; do not imply an exam source.
    content = content.replace('| 真题例句 |', '| 例句（出处未核实） |')
    return jsonify({"root": root, "notes": content})


@app.route('/etymology/<word>', methods=['GET'])
def etymology(word):
    word = safe_root(word.lower())
    if not word:
        return jsonify({"error": "无效单词"}), 400

    # 优先本地 CET 数据库
    local = query_cet_db(word)
    if local:
        return jsonify(local)

    cache_file = os.path.join(ETYMOLOGY_CACHE_DIR, f"{word}.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            try:
                cached = json.load(f)
            except ValueError:
                cached = {}
            if isinstance(cached, dict) and meaningful_etymology(cached.get('etymology')):
                return jsonify(cached)

    failures = []
    text = None
    for source, fetch in [('wiktionary', fetch_from_wiktionary), ('etymonline', fetch_from_etymonline)]:
        try:
            text = fetch(word)
            if meaningful_etymology(text):
                break
            text = None
        except LookupUnavailable:
            failures.append(source)

    if not text:
        if failures:
            return jsonify({"error": "在线词源查询暂不可用，不能据此断言词典未收录", "code": "upstream_unavailable", "sources": failures}), 503
        return jsonify({"error": f"当前查询未找到 {word} 的可用词源段落", "code": "not_found"}), 404

    result = {
        "word": word,
        "source": source,
        "etymology": text
    }

    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return jsonify(result)


@app.route('/cet_search/<prefix>', methods=['GET'])
def cet_search(prefix):
    prefix = safe_root(prefix.lower())
    if not prefix:
        return jsonify({"error": "无效前缀"}), 400
    limit = request.args.get('limit', 20, type=int)
    limit = min(max(limit, 1), 100)
    results = search_cet_db(prefix, limit)
    return jsonify({"prefix": prefix, "count": len(results), "words": results})


@app.route('/cet_stats', methods=['GET'])
def cet_stats():
    if not os.path.exists(CET_DB_PATH):
        return jsonify({"error": "CET 数据库不存在"}), 404
    conn = sqlite3.connect(CET_DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM cet_words')
    total = c.fetchone()[0]
    c.execute('SELECT level, COUNT(*) FROM cet_words GROUP BY level')
    by_level = dict(c.fetchall())
    c.execute('SELECT COUNT(DISTINCT pie_root) FROM cet_words WHERE pie_root IS NOT NULL')
    pie_count = c.fetchone()[0]
    c.execute('SELECT pie_root, COUNT(*) as cnt FROM cet_words WHERE pie_root IS NOT NULL GROUP BY pie_root ORDER BY cnt DESC LIMIT 10')
    top_pie = [{"root": r[0], "count": r[1]} for r in c.fetchall()]
    conn.close()
    return jsonify({
        "total": total,
        "by_level": by_level,
        "pie_roots": pie_count,
        "top_pie_roots": top_pie
    })


if __name__ == '__main__':
    app.run(host=os.environ.get('WORD_ROOT_HOST', '127.0.0.1'), port=5000)
