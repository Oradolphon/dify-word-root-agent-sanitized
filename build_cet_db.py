"""
四六级词汇词源数据库构建脚本
从 Wiktionary API 批量查询词源，存入 SQLite
"""

import sqlite3
import requests
import re
import time
import sys
import os
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 配置
_proxy_url = os.environ.get('WORD_ROOT_PROXY')
PROXIES = {'http': _proxy_url, 'https': _proxy_url} if _proxy_url else None
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('CET_DB_PATH', BASE_DIR / 'cet_etymology.db'))
CET4_PATH = Path(os.environ.get('CET4_PATH', BASE_DIR / 'CET4.txt'))
CET6_PATH = Path(os.environ.get('CET6_PATH', BASE_DIR / 'CET6.txt'))


def extract_words_from_file(filepath):
    """从词汇表文件提取纯单词列表"""
    words = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('大学英语') or line.startswith('共'):
                continue
            
            # 提取单词（第一个空格或方括号前的部分）
            match = re.match(r'^([a-zA-Z\-]+)', line)
            if match:
                word = match.group(1).lower()
                if len(word) > 1:  # 跳过单字母
                    words.append(word)
    
    return list(set(words))  # 去重


def _collect_pron_templates(section):
    """从 English 段抓所有 {{IPA|en|...}} 与 {{en-IPA|...}} 内部串（容忍一层嵌套模板）"""
    pat = r'\{\{((?:IPA\|en)|(?:en-IPA))\|((?:[^{}]|\{\{[^{}]*\}\})*?)\}\}'
    return [(mm.group(1).upper(), mm.group(2)) for mm in re.finditer(pat, section, re.I)]


# en-IPA 裸值白名单：跳过这些噪音参数
_ENIPA_SKIP_KEYS = {'audio','a','b','c','d','e','f','g','h','i','j','k','l','m',
                    'n','o','p','q','r','s','t','u','v','w','x','y','z',
                    'note','ref','qual','qualifier','homophones','bopomofo','hangul',
                    'hebr','arab','cyrl','thai','ja','ko','zh','ru'}


def _is_ipa_bare(tok):
    """判断一个裸串是否像音标：含 IPA 特殊字符、重音符号或至少两个音节点"""
    if not tok or len(tok) < 2:
        return False
    # 含非 ASCII IPA 字符
    if re.search(r'[əɚæʃʒθðŋɲɪʊɜːɑɒɔɛœøɐɶäẽõũĩã]', tok):
        return True
    # 含重音标记 / 长音符号
    if any(c in tok for c in ('ˈ', 'ˌ', 'ː')):
        return True
    # 纯 ASCII 但含多个音节分隔符（如 ˈθɝz.deɪ → 有 .）
    if '.' in tok and len(tok) >= 4:
        return True
    return False


def _parse_transcripts(inner, tpl_type='IPA|EN'):
    """把一个模板内部串拆成 [(transcript, label)]，容忍子模板嵌套与 a= / a2= 标签在前后"""
    inner = re.sub(r'\{\{[^{}]*\}\}', ' ', inner)          # 去掉内层子模板
    tokens = []
    for tok in inner.split('|'):
        tok = tok.strip()
        if tok:
            tokens.append(tok)

    enipal = {'GenAm','GA','US','RP','UK','India','AU','CA','Outlyd','Mid','NH',
              'RF','TN','MAE','UWA','SA-E','Alp','BA','ME','OE','OF','NE','OSL'}
    out = []
    label = ''
    for tok in tokens:
        # a=RP,GA / a2=obsolete 之类标签
        am = re.match(r'^a\d*=(.*)$', tok)
        if am:
            label = am.group(1).strip()
            continue
        # 位置式 dialect 标签（en-IPA: |US|foo|）
        if tok in enipal:
            label = tok
            continue
        # 显式 /.../ 或 [...] 音标（两种模板都认）
        tm = re.match(r'^(\[[^\]]+\]|/[^/]+/)', tok)
        if tm:
            out.append((tm.group(1), label))
            label = ''
            continue
        # en-IPA 专用：接受裸串（需通过白名单 + 音标特征检查）
        if tpl_type == 'EN-IPA':
            # 跳过命名参数 key=value
            if '=' in tok:
                continue
            # 跳过已知噪音键
            low = tok.lower().split('=')[0]
            if low in _ENIPA_SKIP_KEYS:
                continue
            # 检查是否像音标
            if _is_ipa_bare(tok):
                out.append(('/' + tok + '/', label))
                label = ''
    return out


def extract_ipa_from_wiktionary(wikitext):
    """从 wikitext 的 English 段提取国际音标，返回如 /ˈɛseɪ/ 或 [ˈtaɪərd]，无则 None"""
    m = re.search(r'^==\s*English\s*==\s*$', wikitext, re.M)
    start = m.end() if m else 0
    nxt = re.search(r'^==[^=]', wikitext[start:], re.M)
    section = wikitext[start:start + nxt.start()] if nxt else wikitext[start:]

    matches = []
    for tpl_type, inner in _collect_pron_templates(section):
        matches.extend(_parse_transcripts(inner, tpl_type))
    if not matches:
        return None
    # 优先通用美音，其次英音，否则取页面第一个
    for pref in ('GenAm', 'GA', 'US', 'RP', 'UK'):
        for trans, label in matches:
            if pref in label.replace(' ', '').split(','):
                return trans
    return matches[0][0]


def fetch_etymology_from_wiktionary(word):
    """从 Wiktionary API 获取词源与音标，返回 (etymology_raw, pie_root, ipa)"""
    url = "https://en.wiktionary.org/w/api.php"
    params = {
        "action": "parse",
        "page": word,
        "prop": "wikitext",
        "format": "json"
    }
    headers = {"User-Agent": "CET-Etymology-StudyTool/1.0 (personal vocabulary research)"}
    
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=headers,
                               timeout=15, proxies=PROXIES)
            data = resp.json()
            wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")

            if not wikitext:
                return None, None, None

            ipa = extract_ipa_from_wiktionary(wikitext)

            marker = "===Etymology"
            idx = wikitext.find(marker)
            if idx == -1:
                marker = "==Etymology"
                idx = wikitext.find(marker)

            if idx == -1:
                return None, None, ipa

            end_markers = ["===Pronunciation===", "==Pronunciation==",
                           "===Noun===", "==Noun==", "===Verb===", "==Verb==",
                           "===References===", "==References==="]
            end_idx = len(wikitext)
            for em in end_markers:
                ei = wikitext.find(em, idx + len(marker))
                if ei != -1 and ei < end_idx:
                    end_idx = ei

            etymology_raw = wikitext[idx + len(marker):end_idx].strip()
            etymology_raw = re.sub(r'^=+\s*', '', etymology_raw)
            etymology_raw = re.sub(r'\[\[([^\]|]*\|)?([^\]]*)\]\]', r'\2', etymology_raw)

            pie_match = re.search(r'PIE[^\]]*\*([a-zA-Zʰʷːḱǵ-]+)', etymology_raw)
            pie_root = pie_match.group(1) if pie_match else None

            return etymology_raw, pie_root, ipa

        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            log(f"  Error fetching {word}: {e}")
            return None, None, None


def init_database():
    """初始化 SQLite 数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS cet_words (
        word TEXT PRIMARY KEY,
        level TEXT,
        etymology_raw TEXT,
        etymology_clean TEXT,
        pie_root TEXT,
        ipa TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # 旧库升级：补 ipa 列（已存在则忽略）
    try:
        c.execute('ALTER TABLE cet_words ADD COLUMN ipa TEXT')
    except sqlite3.OperationalError:
        pass

    c.execute('CREATE INDEX IF NOT EXISTS idx_pie ON cet_words(pie_root)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_level ON cet_words(level)')
    
    conn.commit()
    return conn


def word_exists(conn, word):
    """检查单词是否已存在"""
    c = conn.cursor()
    c.execute('SELECT 1 FROM cet_words WHERE word = ?', (word,))
    return c.fetchone() is not None


def save_word(conn, word, level, etymology_raw, pie_root, ipa=None):
    """保存单词到数据库"""
    c = conn.cursor()
    
    etymology_clean = etymology_raw
    etymology_clean = re.sub(r'\[\[([^\]|]*\|)?([^\]]*)\]\]', r'\2', etymology_clean)
    etymology_clean = re.sub(r"'''?", '', etymology_clean)
    etymology_clean = re.sub(r'\s+', ' ', etymology_clean).strip()
    
    c.execute('''INSERT OR REPLACE INTO cet_words 
                 (word, level, etymology_raw, etymology_clean, pie_root, ipa)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (word, level, etymology_raw, etymology_clean, pie_root, ipa))
    conn.commit()


def log(msg):
    """Print and write to log file"""
    print(msg, flush=True)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')


LOG_PATH = Path(os.environ.get('CET_BUILD_LOG_PATH', BASE_DIR / 'cet_build.log'))


def backfill_ipa(limit=None, sleep=0.5):
    """为已入库但缺少 ipa 的词补抓音标（需代理在线）。复用抓取函数，只取 ipa。"""
    LOG_PATH.write_text('', encoding='utf-8')
    log("=" * 60)
    log(f"音标回填开始: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)
    conn = init_database()
    rows = conn.execute(
        "SELECT word FROM cet_words WHERE ipa IS NULL OR ipa='' ORDER BY word"
    ).fetchall()
    words = [r[0] for r in rows]
    if limit:
        words = words[:limit]
    log(f"待补音标: {len(words)} 词")

    got = 0
    miss = 0
    for i, w in enumerate(words, 1):
        _, _, ipa = fetch_etymology_from_wiktionary(w)
        if ipa:
            conn.execute("UPDATE cet_words SET ipa=? WHERE word=?", (ipa, w))
            conn.commit()
            got += 1
            log(f"  [{i}/{len(words)}] {w} -> {ipa}")
        else:
            miss += 1
            log(f"  [{i}/{len(words)}] {w} -> 无IPA")
        time.sleep(sleep)

    log(f"\n完成：补到 {got}，无音标 {miss}")
    conn.close()


def main():
    LOG_PATH.write_text('', encoding='utf-8')
    log("=" * 60)
    log("四六级词汇词源数据库构建工具")
    log(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)
    
    # 提取单词
    log("\n[1/4] 提取单词列表...")
    cet4_words = extract_words_from_file(CET4_PATH)
    cet6_words = extract_words_from_file(CET6_PATH)
    
    cet6_only = [w for w in cet6_words if w not in cet4_words]
    
    log(f"  CET-4: {len(cet4_words)} 词")
    log(f"  CET-6: {len(cet6_words)} 词（其中 {len(cet6_only)} 个是六级独有）")
    
    all_words = []
    for w in cet4_words:
        all_words.append((w, 'CET4'))
    for w in cet6_only:
        all_words.append((w, 'CET6'))
    
    log(f"  总计需要查询: {len(all_words)} 词")
    
    # 初始化数据库
    log("\n[2/4] 初始化数据库...")
    conn = init_database()
    log(f"  数据库: {DB_PATH}")
    
    existing_count = 0
    for word, level in all_words:
        if word_exists(conn, word):
            existing_count += 1
    
    log(f"  已存在: {existing_count} 词")
    log(f"  需要新查询: {len(all_words) - existing_count} 词")
    
    # 批量查询
    log("\n[3/4] 开始查询 Wiktionary...")
    success_count = 0
    fail_count = 0
    skip_count = existing_count
    to_query = len(all_words) - existing_count
    start_time = time.time()
    
    for i, (word, level) in enumerate(all_words, 1):
        if word_exists(conn, word):
            continue
        
        elapsed = time.time() - start_time
        done = success_count + fail_count
        if done > 0:
            avg = elapsed / done
            remaining = int(avg * (to_query - done))
            eta = f"ETA: {remaining//60}分{remaining%60}秒"
        else:
            eta = "ETA: 计算中..."
        
        log(f"  [{i}/{len(all_words)}] {word} ({level}) — 成功:{success_count} 失败:{fail_count} | {eta}")
        
        etymology_raw, pie_root, ipa = fetch_etymology_from_wiktionary(word)
        
        if etymology_raw:
            save_word(conn, word, level, etymology_raw, pie_root, ipa)
            success_count += 1
            log(f"    OK (PIE: {pie_root or '无'} | IPA: {ipa or '无'})")
        else:
            fail_count += 1
            log(f"    未找到词源")
        
        time.sleep(0.5)
    
    # 统计
    log("\n[4/4] 完成！")
    log(f"  成功: {success_count}")
    log(f"  失败: {fail_count}")
    log(f"  跳过: {skip_count}")
    log(f"  总计: {success_count + fail_count + skip_count}")
    log(f"  结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    conn.close()
    log(f"\n数据库已保存到: {DB_PATH}")


if __name__ == '__main__':
    if '--backfill-ipa' in sys.argv:
        lim = None
        if '--limit' in sys.argv:
            try:
                lim = int(sys.argv[sys.argv.index('--limit') + 1])
            except (ValueError, IndexError):
                lim = None
        backfill_ipa(limit=lim)
    else:
        main()
