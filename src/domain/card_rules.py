from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import replace
from decimal import Decimal

from domain.entities.card import (
    AssembledCharacteristics,
    CardIssue,
    CardTexts,
    Characteristic,
    Clarification,
    DescriptionFact,
)
from domain.entities.product import Product

NO_DATA = "данных нет"
NAME_LABEL = "Название"
MANUFACTURER_LABEL = "Производитель"
SPECS_LABEL = "Характеристики"
DESCRIPTION_LABEL = "Описание"

TITLE_MAX = 70
DESCRIPTION_MIN = 800
DESCRIPTION_MAX = 1200
QUERIES_MIN = 3
QUERIES_MAX = 5
SHORT_WORD_MAX = 2
SHORT_HEAD_WORD_MAX = 4
SHORT_HEAD_TAIL_FREE = 1
LONG_HEAD_MIN = 4
LONG_HEAD_TAIL_FREE = 2
NEGATIONS = ("не", "без")

DASHES = str.maketrans(dict.fromkeys("\u2010\u2011\u2012\u2013\u2014\u2015\u2212", "-"))
NUMBER = re.compile(r"(?:(?:(?<![\w.,%°′)\]»\"])|(?<=\.\.))-)?\d+(?:[.,]\d+)?")
PLUS_MINUS = re.compile(
    r"(?:±|\+\s*/?\s*-|(?<![^\W_])плюс[\s/-]*минус)\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
MINUS_WORD = re.compile(r"(?<![^\W_])минус\s+(?=\d)", re.IGNORECASE)
WORD = re.compile(r"[^\W\d_]+")
LETTER_OR_DIGIT = re.compile(r"[^\W_]")
ONLY_PUNCTUATION = re.compile(r"[\s\-_.…?/\\*]*")
NO_VALUE_MARKS = frozenset(
    {"n/a", "n.a", "н/д", "н.д", "нетданных", "данныхнет", "неуказано", "null"}
)
BOUNDED_QUOTE = r"(?<![^\W_])(?<!\d[.,]){quote}(?![^\W_])(?![.,]\d)"
NEGATION_BEFORE_QUOTE = re.compile(r"(?<![^\W_])(не|без) $")
SERVICE_PATTERNS = (
    re.compile(r"json"),
    re.compile(r"входн\w*\s+(?:данн\w*|json)"),
    re.compile(r"черновик\w*"),
    re.compile(r"карточк\w*"),
)

REVIEW_WARNINGS = {
    "unsupported_claim": "Не подтверждено данными о приборе: «{quote}». Проверьте или уберите.",
    "filler": "Лишняя фраза без сведений о приборе: «{quote}». Можно убрать.",
    "language_error": "Ошибка в формулировке: «{quote}». Исправьте.",
}
SHORT_DESCRIPTION_WARNING = (
    "Описание короче {minimum} символов ({length}): данных о приборе мало, "
    "дополните их или допишите текст вручную."
)
FACT_DROPPED_WARNING = (
    "Характеристика «{name}» не добавлена: значение не подтверждено описанием прибора, "
    "проверьте вручную."
)
CLARIFICATION_NUMBER_WARNING = (
    "В уточнении «{field}» число {number} не встречается в данных о приборе: "
    "проверьте его."
)


def is_empty(value: str | int | float | None) -> bool:
    if not isinstance(value, str):
        return value is None
    return (
        ONLY_PUNCTUATION.fullmatch(value.translate(DASHES)) is not None
        or "".join(value.split()).rstrip(".").casefold() in NO_VALUE_MARKS
    )


def find_missing_input(product: Product) -> tuple[str, ...]:
    missing: list[str] = []
    if is_empty(product.name):
        missing.append(NAME_LABEL)
    if is_empty(product.manufacturer):
        missing.append(MANUFACTURER_LABEL)
    if product.specs:
        missing.extend(name for name, value in product.specs.items() if is_empty(value))
    else:
        missing.append(SPECS_LABEL)
    if is_empty(product.description):
        missing.append(DESCRIPTION_LABEL)
    return tuple(missing)


def missing_after_assembly(
    missing: Iterable[str],
    characteristics: Iterable[Characteristic],
) -> tuple[str, ...]:
    rows = tuple(characteristics)
    filled = {_normalize(item.name) for item in rows if item.value != NO_DATA}
    unfilled = {_normalize(item.name) for item in rows if item.value == NO_DATA}
    return tuple(
        label
        for label in missing
        if label != SPECS_LABEL
        and (_normalize(label) in unfilled or _normalize(label) not in filled)
    )


def has_too_little_data(product: Product) -> bool:
    has_specs = any(not is_empty(value) for value in product.specs.values())
    return is_empty(product.name) or (not has_specs and is_empty(product.description))


def find_card_issues(product: Product, texts: CardTexts) -> tuple[CardIssue, ...]:
    return (
        *_title_issues(texts.seo_title),
        *_description_issues(texts.seo_description),
        *_queries_issues(texts.search_queries),
        *_commercial_issues(texts),
        *_number_issues(product, texts),
        *_service_issues(texts.seo_description),
    )


def short_description_warnings(description: str) -> tuple[str, ...]:
    if is_empty(description) or len(description) >= DESCRIPTION_MIN:
        return ()
    return (
        SHORT_DESCRIPTION_WARNING.format(
            minimum=DESCRIPTION_MIN,
            length=len(description),
        ),
    )


def clarification_warnings(
    product: Product,
    clarifications: Iterable[Clarification],
) -> tuple[str, ...]:
    allowed = _input_numbers(product)
    return tuple(
        CLARIFICATION_NUMBER_WARNING.format(
            field=item.field,
            number=number.replace(".", ","),
        )
        for item in clarifications
        for number in sorted(_numbers(f"{item.field}\n{item.reason}") - allowed)
    )


def review_issue(
    texts: CardTexts,
    *,
    kind: str,
    quote: str,
    reason: str,
) -> CardIssue | None:
    if not any(_contains_quote(text, quote) for _, _, text in _text_fields(texts)):
        return None
    return CardIssue(
        remark=f"«{quote}»: {reason}",
        warning=REVIEW_WARNINGS[kind].format(quote=quote),
    )


def is_fact_supported(fact: DescriptionFact, description: str) -> bool:
    value_words = _words(fact.value)
    if is_empty(fact.value) or LETTER_OR_DIGIT.search(fact.value) is None:
        return False
    if not _quote_supported(description, fact.quote, value_words):
        return False
    quote_numbers = _numbers(fact.quote)
    if not _numbers(fact.value) <= quote_numbers <= _numbers(description):
        return False
    quote_words = _words(fact.quote)
    if any(word in quote_words and word not in value_words for word in NEGATIONS):
        return False
    return all(_word_supported(word, quote_words) for word in value_words)


def assemble_characteristics(
    product: Product,
    *,
    facts: Iterable[DescriptionFact],
    missing_names: Iterable[str],
) -> AssembledCharacteristics:
    characteristics = list(_characteristics_from_specs(product.specs))
    seen = {
        _normalize(name) for name, value in product.specs.items() if not is_empty(value)
    }
    empty_rows = {
        _normalize(name): row
        for row, (name, value) in enumerate(product.specs.items())
        if is_empty(value)
    }
    warnings: list[str] = []
    for fact in facts:
        key = _normalize(fact.name)
        if not key or key in seen:
            continue
        if not is_fact_supported(fact, product.description or ""):
            warnings.append(FACT_DROPPED_WARNING.format(name=fact.name))
            continue
        if key in empty_rows:
            row = empty_rows[key]
            characteristics[row] = replace(characteristics[row], value=fact.value)
        else:
            characteristics.append(Characteristic(name=fact.name, value=fact.value))
        seen.add(key)
    seen.update(empty_rows)
    added_missing: list[str] = []
    for name in missing_names:
        key = _normalize(name)
        if not key or key in seen:
            continue
        characteristics.append(Characteristic(name=name, value=NO_DATA))
        added_missing.append(name)
        seen.add(key)
    return AssembledCharacteristics(
        characteristics=tuple(characteristics),
        added_missing=tuple(added_missing),
        warnings=tuple(warnings),
    )


def _characteristics_from_specs(
    specs: Mapping[str, str | int | float | None],
) -> tuple[Characteristic, ...]:
    return tuple(
        Characteristic(
            name=name,
            value=NO_DATA if is_empty(value) else str(value),
        )
        for name, value in specs.items()
    )


def _title_issues(title: str) -> Iterator[CardIssue]:
    if is_empty(title):
        yield CardIssue(
            remark="seo_title пуст. Заполни его.",
            warning="Заголовок пуст: напишите его вручную.",
        )
    elif len(title) > TITLE_MAX:
        yield CardIssue(
            remark=f"Заголовок {len(title)} символов, нужно до {TITLE_MAX}. Сократи.",
            warning=f"Заголовок длиннее {TITLE_MAX} символов ({len(title)}): сократите его перед публикацией.",
        )


def _description_issues(description: str) -> Iterator[CardIssue]:
    if is_empty(description):
        yield CardIssue(
            remark="seo_description пуст. Напиши текст.",
            warning="Описание пусто: напишите его вручную.",
        )
    elif len(description) > DESCRIPTION_MAX:
        yield CardIssue(
            remark=f"seo_description {len(description)} символов, нужно до {DESCRIPTION_MAX}. Сократи без потери значений.",
            warning=f"Описание длиннее {DESCRIPTION_MAX} символов ({len(description)}): сократите его перед публикацией.",
        )


def _queries_issues(queries: tuple[str, ...]) -> Iterator[CardIssue]:
    filled = [_normalize(query) for query in queries if not is_empty(query)]
    if not QUERIES_MIN <= len(filled) <= QUERIES_MAX:
        yield CardIssue(
            remark=f"Запросов {len(filled)}, нужно {QUERIES_MIN}-{QUERIES_MAX}.",
            warning=f"Поисковых запросов {len(filled)}, нужно от {QUERIES_MIN} до {QUERIES_MAX}.",
        )
    if len(set(filled)) != len(filled):
        yield CardIssue(
            remark="Есть одинаковые поисковые запросы, сделай их разными.",
            warning="Есть одинаковые поисковые запросы: оставьте разные.",
        )


def _commercial_issues(texts: CardTexts) -> Iterator[CardIssue]:
    if is_empty(texts.commercial.audience):
        yield CardIssue(
            remark="commercial.audience пуст.",
            warning="Не заполнено, кому подходит прибор.",
        )
    if is_empty(texts.commercial.tasks):
        yield CardIssue(
            remark="commercial.tasks пуст.",
            warning="Не заполнено, какие задачи решает прибор.",
        )


def _number_issues(product: Product, texts: CardTexts) -> Iterator[CardIssue]:
    allowed = _input_numbers(product)
    for field, label, text in _text_fields(texts):
        for number in sorted(_numbers(text) - allowed):
            shown = number.replace(".", ",")
            yield CardIssue(
                remark=f"Число {shown} в поле {field} не встречается в данных о приборе. Убери его.",
                warning=f"Число {shown} в {label} не встречается в данных о приборе: проверьте его.",
            )


def _service_issues(description: str) -> Iterator[CardIssue]:
    lowered = description.lower()
    for pattern in SERVICE_PATTERNS:
        match = pattern.search(lowered)
        if match is not None:
            yield CardIssue(
                remark=f"В seo_description служебное выражение «{match.group()}». Перепиши фразу так, чтобы читатель не видел служебных слов.",
                warning=f"В описании служебное выражение «{match.group()}»: уберите его перед публикацией.",
            )


def _text_fields(texts: CardTexts) -> tuple[tuple[str, str, str], ...]:
    return (
        ("seo_title", "заголовке", texts.seo_title),
        ("seo_description", "описании", texts.seo_description),
        ("search_queries", "поисковых запросах", "\n".join(texts.search_queries)),
        ("commercial.audience", "блоке «Кому подходит»", texts.commercial.audience),
        ("commercial.tasks", "блоке «Какие задачи решает»", texts.commercial.tasks),
    )


def _input_numbers(product: Product) -> set[str]:
    parts = [product.name or "", product.manufacturer or "", product.description or ""]
    for name, value in product.specs.items():
        parts.append(name)
        parts.append("" if value is None else str(value))
    return _numbers("\n".join(parts))


def _numbers(text: str) -> set[str]:
    plain = unicodedata.normalize("NFKC", text).translate(DASHES)
    signed = MINUS_WORD.sub("-", PLUS_MINUS.sub(r" -\1 \1", plain))
    return {
        format(Decimal(token.replace(",", ".")).normalize(), "f")
        for token in NUMBER.findall(signed)
    }


def _words(text: str) -> list[str]:
    return [word.lower() for word in WORD.findall(text)]


def _word_supported(word: str, quote_words: list[str]) -> bool:
    if len(word) <= SHORT_WORD_MAX:
        return word in quote_words
    if len(word) <= SHORT_HEAD_WORD_MAX:
        head = word[: len(word) - SHORT_HEAD_TAIL_FREE]
    else:
        head = word[: max(LONG_HEAD_MIN, len(word) - LONG_HEAD_TAIL_FREE)]
    return any(quote_word.startswith(head) for quote_word in quote_words)


def _quote_supported(description: str, quote: str, value_words: list[str]) -> bool:
    needle = _normalize(quote)
    if not needle:
        return False
    text = _normalize(description)
    pattern = BOUNDED_QUOTE.format(quote=re.escape(needle))
    return any(
        not _negation_lost(text[: match.start()], value_words)
        for match in re.finditer(pattern, text)
    )


def _negation_lost(text_before: str, value_words: list[str]) -> bool:
    negation = NEGATION_BEFORE_QUOTE.search(text_before)
    return negation is not None and negation.group(1) not in value_words


def _contains_quote(text: str, quote: str) -> bool:
    needle = _normalize(quote)
    return bool(needle) and needle in _normalize(text)


def _normalize(text: str) -> str:
    return " ".join(text.translate(DASHES).lower().split())
