from __future__ import annotations

import csv
import re
from html import unescape
from typing import Any

from src.knowledge.chunking.ragflow_like.parsers import general

QUESTION_PREFIX_RE = re.compile(
    r'^(?:\u95ee\u9898|\u7b54\u6848|\u56de\u7b54|user|assistant|Q|A|Question|Answer)\s*[:\uff1a\-]+\s*',
    flags=re.IGNORECASE,
)
LIST_PREFIX_RE = re.compile(r'^(?:(?:[-*+]|\d+[.)])\s+)+')
QUESTION_START_RE = re.compile(
    r'^(?:what|why|how|when|where|which|who|whom|whose|can|could|should|would|will|is|are|was|were|do|does|did|has|have|had|explain|describe|compare|give|list|name)\b',
    flags=re.IGNORECASE,
)
META_TITLE_PATTERNS = (
    'table of contents',
    'hide/show table of contents',
    'back to top',
    'see deep-dive answer',
)
ANSWER_NOISE_PATTERNS = (
    'back to top',
    'hide/show table of contents',
)
ANSWER_WRAPPER_ONLY_RE = re.compile(
    r'^(?:</?(?:details|summary|p|div)\b[^>]*>\s*|<(?:summary|details)\b[^>]*>.*?</(?:summary|details)>\s*)+$',
    flags=re.IGNORECASE,
)
ANSWER_TITLE_RE = re.compile(
    r'^(?:#{1,6}\s*)?(?:\*\*|__)?(?:\u56de\u7b54|\u7b54\u6848|answer)(?:\*\*|__)?\s*[:\uff1a\-]?\s*',
    flags=re.IGNORECASE,
)
HTML_TAG_RE = re.compile(r'<[^>]+>')
MARKDOWN_LINK_RE = re.compile(r'\[([^\]]+)\]\([^\)]+\)')
MARKDOWN_EMPHASIS_RE = re.compile(r'[*_`~]+')
NUMBER_ONLY_RE = re.compile(r'^\d+[.)]?$')
QUESTION_LINE_RE = re.compile(r'^(?:\u95ee\u9898|question|q)\s*[:\uff1a\-]', flags=re.IGNORECASE)
ANSWER_LINE_RE = re.compile(r'^(?:\u56de\u7b54|\u7b54\u6848|answer|a)\s*[:\uff1a\-]', flags=re.IGNORECASE)


def _rm_prefix(text: str) -> str:
    return QUESTION_PREFIX_RE.sub('', (text or '').strip())


def _to_qa_chunk(question: str, answer: str, eng: bool = False) -> str:
    qprefix = 'Question: ' if eng else '\u95ee\u9898\uff1a'
    aprefix = 'Answer: ' if eng else '\u56de\u7b54\uff1a'
    return '\t'.join([qprefix + _rm_prefix(question), aprefix + _rm_prefix(answer)])


def _clean_inline_markdown(text: str) -> str:
    normalized = unescape(text or '').strip()
    normalized = MARKDOWN_LINK_RE.sub(r'\1', normalized)
    normalized = HTML_TAG_RE.sub(' ', normalized)
    normalized = MARKDOWN_EMPHASIS_RE.sub('', normalized)
    normalized = normalized.replace('\\', ' ')
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip(' |:-')


def _normalize_question_title(text: str) -> str:
    normalized = _clean_inline_markdown(text)
    normalized = LIST_PREFIX_RE.sub('', normalized)
    normalized = re.sub(r'^(?:question|q)\s*\d*\s*[:\uff1a.\-)]\s*', '', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'^\d+\s*[.)]\s*', '', normalized)
    return normalized.strip()


def _looks_like_question(text: str) -> bool:
    normalized = _normalize_question_title(text)
    lowered = normalized.lower()

    if not normalized or len(normalized) < 6:
        return False
    if NUMBER_ONLY_RE.fullmatch(normalized):
        return False
    if any(pattern in lowered for pattern in META_TITLE_PATTERNS):
        return False
    if lowered in {'answer', 'question', 'questions', 'no', 'no.', 'faq'}:
        return False
    if normalized.endswith('?') or normalized.endswith('\uff1f'):
        return True
    if QUESTION_START_RE.match(normalized):
        return True
    if any(token in lowered for token in ('output of', 'outcome of', 'difference between')):
        return True
    return False


def _guess_delimiter(lines: list[str]) -> str:
    comma = 0
    tab = 0
    for line in lines:
        if len(line.split(',')) == 2:
            comma += 1
        if len(line.split('\t')) == 2:
            tab += 1
    return '\t' if tab >= comma else ','


def _extract_pairs_with_delimiter(lines: list[str], delimiter: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    question = ''
    answer = ''

    for line in lines:
        arr = line.split(delimiter)
        if len(arr) != 2:
            if question:
                answer += '\n' + line
            continue

        if question and answer:
            pairs.append((question, answer))
        question, answer = arr

    if question:
        pairs.append((question, answer))

    return [(q.strip(), a.strip()) for q, a in pairs if q.strip() and a.strip()]


def _extract_pairs_from_csv(lines: list[str], delimiter: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    question = ''
    answer = ''

    reader = csv.reader(lines, delimiter=delimiter)
    for row, raw_line in zip(reader, lines, strict=False):
        if len(row) != 2:
            if question:
                answer += '\n' + raw_line
            continue

        if question and answer:
            pairs.append((question, answer))
        question, answer = row

    if question:
        pairs.append((question, answer))

    return [(q.strip(), a.strip()) for q, a in pairs if q.strip() and a.strip()]


def _parse_markdown_table_row(line: str) -> list[str] | None:
    if '|' not in line:
        return None

    text = line.strip()
    if not text:
        return None

    if text.startswith('|'):
        text = text[1:]
    if text.endswith('|'):
        text = text[:-1]

    cells = [cell.strip() for cell in text.split('|')]
    if not cells:
        return None

    if all(re.fullmatch(r':?-{3,}:?', c.replace(' ', '')) for c in cells if c):
        return None

    return cells


def _table_header_is_qa(cells: list[str]) -> bool:
    if len(cells) < 2:
        return False
    header = [_clean_inline_markdown(cell).lower() for cell in cells[:2]]
    return header[0] in {'question', 'questions', '\u95ee\u9898'} and header[1] in {
        'answer',
        'answers',
        '\u56de\u7b54',
        '\u7b54\u6848',
    }


def _extract_pairs_from_markdown_tables(markdown_content: str, *, strict_header: bool) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    block: list[list[str]] = []

    def flush() -> None:
        nonlocal block
        if len(block) < 2:
            block = []
            return

        rows = block
        start_index = 0
        if strict_header:
            if not _table_header_is_qa(rows[0]):
                block = []
                return
            start_index = 1

        for row in rows[start_index:]:
            if len(row) < 2:
                continue
            question = _normalize_question_title(row[0])
            answer = _clean_answer('\n'.join(row[1:]))
            if question and answer and _looks_like_question(question):
                pairs.append((question, answer))
        block = []

    for line in (markdown_content or '').splitlines():
        cells = _parse_markdown_table_row(line)
        if cells is None:
            flush()
            continue
        block.append(cells)

    flush()
    return pairs


def _parse_heading_candidate(line: str) -> tuple[int, str] | None:
    stripped = line.strip()
    if not stripped:
        return None

    without_list_prefix = LIST_PREFIX_RE.sub('', stripped)
    match = re.match(r'^(#{1,6})\s+(.*)$', without_list_prefix)
    if match:
        level = len(match.group(1))
        title = _normalize_question_title(match.group(2))
        return level, title

    return None


def _clean_answer(answer: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in (answer or '').splitlines():
        stripped = raw_line.strip()
        lowered = stripped.lower()

        if not stripped:
            if cleaned_lines and cleaned_lines[-1] != '':
                cleaned_lines.append('')
            continue
        if ANSWER_WRAPPER_ONLY_RE.fullmatch(stripped):
            continue
        if stripped in {'---', '***', '___', '<details>', '</details>', '<p>', '</p>', '<div>', '</div>'}:
            continue
        if stripped.startswith('<summary') or stripped.startswith('</summary'):
            continue
        if any(pattern in lowered for pattern in ANSWER_NOISE_PATTERNS):
            continue

        normalized_stripped = _clean_inline_markdown(stripped)
        if ANSWER_TITLE_RE.match(stripped) or ANSWER_TITLE_RE.match(normalized_stripped):
            normalized_line = ANSWER_TITLE_RE.sub('', normalized_stripped).strip()
            if normalized_line:
                cleaned_lines.append(normalized_line)
            continue

        cleaned_lines.append(raw_line.rstrip())

    return '\n'.join(cleaned_lines).strip()


def _extract_pairs_from_markdown_sections(markdown_content: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    current_question = ''
    answer_lines: list[str] = []
    code_block = False

    for line in (markdown_content or '').splitlines():
        stripped = line.strip()
        if stripped.startswith('```'):
            code_block = not code_block

        heading = None if code_block else _parse_heading_candidate(line)
        if heading:
            level, title = heading
            if _looks_like_question(title):
                answer = _clean_answer('\n'.join(answer_lines))
                if current_question and answer:
                    pairs.append((current_question, answer))
                current_question = title
                answer_lines = []
                continue

            if current_question and level <= 2:
                answer = _clean_answer('\n'.join(answer_lines))
                if answer:
                    pairs.append((current_question, answer))
                current_question = ''
                answer_lines = []
                continue

        if current_question:
            answer_lines.append(line)

    answer = _clean_answer('\n'.join(answer_lines))
    if current_question and answer:
        pairs.append((current_question, answer))

    return pairs


def _extract_pairs_by_prefix(lines: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    question = ''
    answer_lines: list[str] = []

    for line in lines:
        if QUESTION_LINE_RE.match(line):
            answer = _clean_answer('\n'.join(answer_lines))
            if question and answer:
                pairs.append((question, answer))
            question = _normalize_question_title(QUESTION_LINE_RE.sub('', line).strip())
            answer_lines = []
            continue

        if ANSWER_LINE_RE.match(line):
            answer_lines.append(ANSWER_LINE_RE.sub('', line).strip())
            continue

        if question:
            answer_lines.append(line)

    answer = _clean_answer('\n'.join(answer_lines))
    if question and answer:
        pairs.append((question, answer))

    return [(q.strip(), a.strip()) for q, a in pairs if q.strip() and a.strip()]


def _dedupe_pairs(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    res: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for question, answer in pairs:
        q = _normalize_question_title(question)
        a = _clean_answer(answer)
        if not q or not a or not _looks_like_question(q):
            continue
        key = (q, a)
        if key in seen:
            continue
        seen.add(key)
        res.append((q, a))

    return res


def chunk_markdown(filename: str, markdown_content: str, parser_config: dict[str, Any] | None = None) -> list[str]:
    parser_config = parser_config or {}
    eng = str(parser_config.get('language', 'Chinese')).lower() == 'english'

    suffix = ''
    if filename and '.' in filename:
        suffix = '.' + filename.lower().split('.')[-1]

    lines = [line for line in (markdown_content or '').splitlines() if line.strip()]
    pairs: list[tuple[str, str]] = []

    if suffix in {'.xlsx', '.xls'}:
        pairs.extend(_extract_pairs_from_markdown_tables(markdown_content, strict_header=False))
        if not pairs:
            delimiter = _guess_delimiter(lines)
            pairs.extend(_extract_pairs_with_delimiter(lines, delimiter))
    elif suffix == '.csv':
        pairs.extend(_extract_pairs_from_markdown_tables(markdown_content, strict_header=False))
        delimiter = '\t' if any('\t' in line for line in lines) else ','
        pairs.extend(_extract_pairs_from_csv(lines, delimiter))
    elif suffix in {'.md', '.markdown', '.mdx'}:
        pairs.extend(_extract_pairs_from_markdown_sections(markdown_content))
        pairs.extend(_extract_pairs_by_prefix(lines))
        pairs.extend(_extract_pairs_from_markdown_tables(markdown_content, strict_header=True))
    elif suffix == '.docx':
        pairs.extend(_extract_pairs_from_markdown_sections(markdown_content))
        pairs.extend(_extract_pairs_by_prefix(lines))
        pairs.extend(_extract_pairs_from_markdown_tables(markdown_content, strict_header=True))
    else:
        pairs.extend(_extract_pairs_from_markdown_sections(markdown_content))
        pairs.extend(_extract_pairs_by_prefix(lines))
        if not pairs:
            delimiter = _guess_delimiter(lines)
            pairs.extend(_extract_pairs_with_delimiter(lines, delimiter))

    pairs = _dedupe_pairs(pairs)

    if not pairs:
        return general.chunk_markdown(markdown_content, parser_config)

    return [_to_qa_chunk(q, a, eng=eng) for q, a in pairs]
