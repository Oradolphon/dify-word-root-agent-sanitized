"""Personal vocabulary cards and review scheduling; separate from the CET corpus."""
import json
import random
import re
import sqlite3
import uuid
from contextlib import contextmanager, closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

learning = Blueprint('learning', __name__)
WORD = re.compile(r"[a-z]+(?:[-'][a-z]+)*\Z")
STEPS = (1, 3, 7, 14, 30, 60)


def now():
    return datetime.now(timezone.utc)


def stamp(value):
    return value.isoformat(timespec='seconds')


@contextmanager
def database():
    path = current_app.config.get('LEARNING_DB_PATH', str(Path(__file__).with_name('word_learning.db')))
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS cards (
                word TEXT PRIMARY KEY, content TEXT NOT NULL, level TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                due_at TEXT NOT NULL, stage INTEGER NOT NULL DEFAULT 0,
                reviews INTEGER NOT NULL DEFAULT 0, lapses INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS reviews (
                event_id TEXT PRIMARY KEY, word TEXT NOT NULL, rating TEXT NOT NULL,
                reviewed_at TEXT NOT NULL, result TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS quizzes (
                quiz_id TEXT PRIMARY KEY, word TEXT NOT NULL, question TEXT NOT NULL,
                created_at TEXT NOT NULL, result TEXT
            );
        ''')
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def valid_word(value):
    return isinstance(value, str) and len(value) <= 50 and WORD.fullmatch(value)


def card_dict(row):
    result = json.loads(row['content'])
    result.update({k: row[k] for k in ('level', 'due_at', 'stage', 'reviews', 'lapses')})
    result['status'] = 'learning' if row['stage'] < 4 else 'reviewing'
    return result


def cet_level(word):
    path = current_app.config['CET_DB_PATH']
    with closing(sqlite3.connect(Path(path).as_uri() + '?mode=ro', uri=True)) as conn:
        row = conn.execute('SELECT level FROM cet_words WHERE word=?', (word,)).fetchone()
        return row[0] if row else None


@learning.post('/learning/card')
def save_card():
    data = body()
    word = data.get('word', '')
    if isinstance(word, str):
        word = word.strip().lower()
    if not valid_word(word):
        return jsonify(error='word 必须是有效的英文词典形'), 400
    required = ('definition', 'part_of_speech', 'etymology_summary', 'source_note', 'example', 'example_translation')
    optional = ('memory_hint',)
    for key in required + optional:
        value = data.get(key, '')
        if not isinstance(value, str) or len(value) > 3000 or (key in required and not value.strip()):
            return jsonify(error=f'{key} 必须是非空文本，最多 3000 字符' if key in required else f'{key} 格式错误'), 400
    for key in ('roots', 'collocations'):
        value = data.get(key, [])
        if not isinstance(value, list) or len(value) > 12 or any(not isinstance(x, str) or not x.strip() or len(x) > 300 for x in value):
            return jsonify(error=f'{key} 必须是最多 12 项的非空字符串数组'), 400
    if any(not re.fullmatch('[a-z]{1,30}', root) for root in data.get('roots', [])):
        return jsonify(error='roots 必须用规范小写家族名'), 400
    content = {key: data.get(key, '').strip() for key in required + optional}
    content.update(word=word, roots=data.get('roots', []), collocations=data.get('collocations', []))
    # Corpus labels are supplied by the corpus, never guessed by the model.
    level = cet_level(word)
    timestamp = stamp(now())
    with database() as conn:
        conn.execute('''INSERT INTO cards(word,content,level,created_at,updated_at,due_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(word) DO UPDATE SET
            content=excluded.content, level=excluded.level, updated_at=excluded.updated_at''',
            (word, json.dumps(content, ensure_ascii=False), level, timestamp, timestamp, timestamp))
        row = conn.execute('SELECT * FROM cards WHERE word=?', (word,)).fetchone()
        return jsonify(status='ok', card=card_dict(row))


@learning.get('/learning/card/<word>')
def get_card(word):
    with database() as conn:
        row = conn.execute('SELECT * FROM cards WHERE word=?', (word.lower(),)).fetchone()
        if row is None:
            return jsonify(error='尚未建立学习卡；旧词族笔记仍可通过 readNotes 查看', code='no_learning_card'), 404
        return jsonify(card_dict(row))


def filters():
    level = request.args.get('level', '').upper()
    limit = request.args.get('limit', 5, type=int)
    if level not in ('', 'CET4', 'CET6'):
        return None, None
    return level, min(max(limit, 1), 20)


@learning.get('/learning/review')
def review_queue():
    level, limit = filters()
    if level is None:
        return jsonify(error='level 只能为 CET4 或 CET6'), 400
    with database() as conn:
        timestamp = stamp(now())
        args = [timestamp]
        where = 'due_at <= ?'
        if level:
            where += ' AND level=?'
            args.append(level)
        due = conn.execute(f'SELECT COUNT(*) FROM cards WHERE {where}', args).fetchone()[0]
        rows = conn.execute(f'SELECT * FROM cards WHERE {where} ORDER BY due_at, word LIMIT ?', args + [limit]).fetchall()
        total = conn.execute('SELECT COUNT(*) FROM cards').fetchone()[0]
        return jsonify(total_cards=total, due_count=due, cards=[card_dict(r) for r in rows],
                       time_zone='UTC; 展示时转换为 Asia/Shanghai',
                       note='词族入库不等于掌握；旧笔记不会自动计为学习卡。')


def record(conn, word, rating, event_id):
    previous = conn.execute('SELECT word,rating,result FROM reviews WHERE event_id=?', (event_id,)).fetchone()
    if previous:
        if previous['word'] != word or previous['rating'] != rating:
            return {'error': 'event_id 已用于其他复习结果'}, 409
        return json.loads(previous['result']), 200
    row = conn.execute('SELECT * FROM cards WHERE word=?', (word,)).fetchone()
    if row is None:
        return {'error': '请先建立学习卡', 'code': 'no_learning_card'}, 404
    stage = row['stage']
    if rating == 'again':
        stage, delay = 0, timedelta(minutes=10)
    elif rating == 'hard':
        stage, delay = max(0, stage - 1), timedelta(days=1)
    else:
        delay = timedelta(days=STEPS[min(stage, len(STEPS) - 1)])
        stage = min(stage + 1, len(STEPS))
    reviewed = now()
    due = stamp(reviewed + delay)
    result = dict(status='ok', word=word, rating=rating, due_at=due, stage=stage,
                  reviews=row['reviews'] + 1, lapses=row['lapses'] + int(rating == 'again'))
    conn.execute('UPDATE cards SET stage=?, due_at=?, reviews=reviews+1, lapses=lapses+?, updated_at=? WHERE word=?',
                 (stage, due, int(rating == 'again'), stamp(reviewed), word))
    conn.execute('INSERT INTO reviews VALUES(?,?,?,?,?)',
                 (event_id, word, rating, stamp(reviewed), json.dumps(result)))
    return result, 200


@learning.post('/learning/review')
def submit_review():
    data = body()
    word, rating, event_id = data.get('word'), data.get('rating'), data.get('event_id')
    if not valid_word(word) or rating not in ('again', 'hard', 'good') or not isinstance(event_id, str) or not 1 <= len(event_id) <= 100:
        return jsonify(error='需要 word、rating(again/hard/good)、event_id(每次复习唯一，重试复用)'), 400
    with database() as conn:
        conn.execute('BEGIN IMMEDIATE')
        result, status = record(conn, word, rating, event_id)
        return jsonify(result), status


@learning.get('/learning/study')
def study_words():
    level, limit = filters()
    if level is None:
        return jsonify(error='level 只能为 CET4 或 CET6'), 400
    with database() as conn:
        known = {r[0] for r in conn.execute('SELECT word FROM cards')}
    with closing(sqlite3.connect(Path(current_app.config['CET_DB_PATH']).as_uri() + '?mode=ro', uri=True)) as conn:
        rows = conn.execute('SELECT word,level FROM cet_words WHERE (?="" OR level=?) ORDER BY word', (level, level)).fetchall()
    candidates = [dict(word=w, level=l) for w, l in rows if w not in known]
    return jsonify(words=random.sample(candidates, min(limit, len(candidates))), available=len(candidates),
                   note='仅排除已有学习卡；旧词族中的词可能仍出现。级别来自本地词表，不代表真题频率。')


@learning.get('/quiz')
def quiz():
    level, _ = filters()
    if level is None:
        return jsonify(error='level 只能为 CET4 或 CET6'), 400
    with database() as conn:
        rows = conn.execute('SELECT * FROM cards WHERE (?="" OR level=?) ORDER BY due_at', (level, level)).fetchall()
        # Require a real occurrence of the lemma, so a cloze never becomes an unanswerable sentence.
        for row in rows:
            card = json.loads(row['content'])
            pattern = re.compile(r'(?<![A-Za-z])' + re.escape(row['word']) + r'(?![A-Za-z])', re.I)
            if not pattern.search(card['example']):
                continue
            question = pattern.sub('____', card['example'])
            quiz_id = str(uuid.uuid4())
            conn.execute('INSERT INTO quizzes VALUES(?,?,?,?,NULL)', (quiz_id, row['word'], question, stamp(now())))
            return jsonify(quiz_id=quiz_id, question=question, type='cloze',
                           instruction='用所学词的词典形填空。先让用户作答，再调用 answerQuiz；不要提前展示学习卡或答案。')
    return jsonify(error='没有可出题的学习卡：先学习并保存一张例句含词典形的卡片', code='no_quiz_card'), 404


@learning.post('/quiz/answer')
def answer_quiz():
    data = body()
    quiz_id, answer = data.get('quiz_id'), data.get('answer')
    if not isinstance(quiz_id, str) or not isinstance(answer, str) or not answer.strip() or len(answer) > 100:
        return jsonify(error='需要 quiz_id 和用户原始 answer（最多 100 字符）'), 400
    with database() as conn:
        conn.execute('BEGIN IMMEDIATE')
        quiz_row = conn.execute('SELECT * FROM quizzes WHERE quiz_id=?', (quiz_id,)).fetchone()
        if quiz_row is None:
            return jsonify(error='测验不存在'), 404
        if quiz_row['result']:
            return jsonify(json.loads(quiz_row['result']))
        correct = answer.strip().lower() == quiz_row['word']
        review, _ = record(conn, quiz_row['word'], 'good' if correct else 'again', 'quiz:' + quiz_id)
        card = conn.execute('SELECT * FROM cards WHERE word=?', (quiz_row['word'],)).fetchone()
        result = dict(correct=correct, answer=quiz_row['word'], review=review, card=card_dict(card))
        conn.execute('UPDATE quizzes SET result=? WHERE quiz_id=?', (json.dumps(result, ensure_ascii=False), quiz_id))
        return jsonify(result)
