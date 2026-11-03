from __future__ import annotations

import pytest

from domain.card_rules import (
    assemble_characteristics,
    find_card_issues,
    is_fact_supported,
    review_issue,
    short_description_warnings,
)
from domain.entities.card import CardTexts, Characteristic, Commercial, DescriptionFact
from domain.entities.product import Product

# Test cases:
# 1. Чистые тексты: замечаний нет
# 2. Заголовок: 70 символов без замечания, 71 с замечанием, пустой с замечанием
# 3. Описание: 1200 без замечания, 1201 с замечанием, пустое с замечанием
# 4. Короткое описание: не замечание, только warning; 800 символов без warning; пустое без него
# 5. Запросы: мало, много, пустые не считаются, повтор с учётом регистра и вида тире
# 6. Commercial: пустые audience и tasks дают по замечанию
# 7. Числа: запятая равна точке, незначащие нули равны, ½ и ² разбираются как у входа
# 8. Число вне входа в каждом текстовом поле даёт замечание с именем поля
# 9. Числа входа берутся из названия, производителя, описания, имён и значений specs
# 10. Служебные выражения: только в описании, «входной сигнал» не замечание
# 11. Замечание: для модели указание, для контент-менеджера текст без указаний модели
# 12. Цитата ревьюера: найдена с нормализацией во всех полях, ложная и пустая отброшены
# 13. Вид замечания ревьюера определяет текст warning, причина модели в него не идёт
# 14. Факт принят: цитата нормализуется, значение в именительном падеже опирается на цитату
# 15. Факт отброшен: нет цитаты, число не из цитаты, слово не из цитаты, пустое значение
# 16. Короткие слова значения не проверяются, у длинных хватает общего начала
# 17. Сборка: значения specs как во входе и по порядку, затем факты, затем отсутствующие
# 18. Сборка: specs главнее факта, дубли убираются по нормализованному имени
# 19. Сборка: отброшенный факт даёт warning, значения в списке нет
# 20. Сборка: факт с именем из заполненной строки specs не проверяется и не даёт warning
# 21. Сборка: пустые имена пропускаются, дубли внутри specs остаются как во входе
# 22. Цитата ищется с границами: слева и справа не буква, не цифра и не обрывок числа
# 23. «Не» или «без» сразу перед цитатой в описании и нет в значении: факт отброшен
# 24. «Без» внутри цитаты не теряется, как и «не»
# 25. Значение без букв и цифр: факт отброшен
# 26. Сборка: подтверждённый факт встаёт на место пустой строки specs, порядок прежний, второй строки нет
# 27. Сборка: неподтверждённый факт с именем пустой строки specs даёт warning, строка остаётся пустой
# 28. Числа со знаком в текстах: минус вплотную к числу часть числа, слово «минус» то же, плюс равен отсутствию знака
# 29. Число без знака и с минусом это разные числа, вид минуса не важен
# 30. Минус после цифры, буквы, единицы, закрывающего знака, разделителя или с пробелом это не знак
# 31. Числа факта сравниваются со знаком, цитата без минуса из описания не проходит
# 32. Минус после многоточия это знак: тексты и факты с диапазоном из двух отрицательных чисел
# 33. Плюс-минус в любом написании это два числа, x и -x
# 34. Плюс-минус вплотную к числу не теряет ни одного из чисел, лишний знак даёт замечание


PRODUCT = Product(
    name="Манометр DM 02",
    manufacturer="Манотомь",
    specs={"Диапазон": "0–1,6 МПа", "Диаметр корпуса": 100, "Защита": None},
    description="Прибор для жидкостей и газов. Температура: -40…+100 °С.",
)
LONG_TEXT = "а" * 900


def texts_with(**overrides: object) -> CardTexts:
    values: dict[str, object] = {
        "seo_title": "Манометр DM 02",
        "seo_description": LONG_TEXT,
        "search_queries": ("манометр", "манометр купить", "манометр манотомь"),
        "commercial": Commercial(audience="служба КИПиА", tasks="контроль давления"),
    }
    return CardTexts(**{**values, **overrides})


def remarks_for(texts: CardTexts) -> list[str]:
    return [issue.remark for issue in find_card_issues(PRODUCT, texts)]


def fact(value: str, quote: str, name: str = "Среда") -> DescriptionFact:
    return DescriptionFact(name=name, value=value, quote=quote)


def test_case_1() -> None:
    # 1. Чистые тексты: замечаний нет
    # Act
    issues = find_card_issues(PRODUCT, texts_with())

    # Assert
    assert issues == ()


@pytest.mark.parametrize(
    ("title", "remarks"),
    [
        ("я" * 70, []),
        ("я" * 71, ["Заголовок 71 символов, нужно до 70. Сократи."]),
        ("   ", ["seo_title пуст. Заполни его."]),
    ],
)
def test_case_2(title, remarks) -> None:
    # 2. Заголовок: 70 символов без замечания, 71 с замечанием, пустой с замечанием
    # Act
    result = remarks_for(texts_with(seo_title=title))

    # Assert
    assert result == remarks


@pytest.mark.parametrize(
    ("description", "remarks"),
    [
        ("я" * 1200, []),
        (
            "я" * 1201,
            [
                "seo_description 1201 символов, нужно до 1200. Сократи без потери значений."
            ],
        ),
        ("", ["seo_description пуст. Напиши текст."]),
    ],
)
def test_case_3(description, remarks) -> None:
    # 3. Описание: 1200 без замечания, 1201 с замечанием, пустое с замечанием
    # Act
    result = remarks_for(texts_with(seo_description=description))

    # Assert
    assert result == remarks


@pytest.mark.parametrize(
    ("description", "warnings"),
    [
        (
            "я" * 799,
            (
                "Описание короче 800 символов (799): данных о приборе мало, "
                "дополните их или допишите текст вручную.",
            ),
        ),
        ("я" * 800, ()),
        ("   ", ()),
    ],
)
def test_case_4(description, warnings) -> None:
    # 4. Короткое описание: не замечание, только warning; 800 символов без warning; пустое без него
    # Act
    result = short_description_warnings(description)

    # Assert
    assert result == warnings
    if len(description) == 799:
        assert remarks_for(texts_with(seo_description=description)) == []


@pytest.mark.parametrize(
    ("queries", "remarks"),
    [
        (("а", "б"), ["Запросов 2, нужно 3-5."]),
        (("а", "б", "в", "г", "д", "е"), ["Запросов 6, нужно 3-5."]),
        (("а", "б", "  "), ["Запросов 2, нужно 3-5."]),
        (
            ("Манометр 0–1", "манометр  0-1", "в"),
            ["Есть одинаковые поисковые запросы, сделай их разными."],
        ),
    ],
)
def test_case_5(queries, remarks) -> None:
    # 5. Запросы: мало, много, пустые не считаются, повтор с учётом регистра и вида тире
    # Arrange
    product = Product(
        name="Манометр 0-1", manufacturer=None, specs={}, description=None
    )
    texts = texts_with(seo_title="Манометр", search_queries=queries)

    # Act
    result = [issue.remark for issue in find_card_issues(product, texts)]

    # Assert
    assert result == remarks


def test_case_6() -> None:
    # 6. Commercial: пустые audience и tasks дают по замечанию
    # Arrange
    texts = texts_with(commercial=Commercial(audience=" ", tasks=""))

    # Act
    result = remarks_for(texts)

    # Assert
    assert result == ["commercial.audience пуст.", "commercial.tasks пуст."]


@pytest.mark.parametrize(
    ("value", "text"),
    [
        ("1,6", "1.6 МПа"),
        ("1.6", "1,6 МПа"),
        ("1,50", "1,5"),
        ("100,0", "100"),
        ("G½″", "G1/2"),
        ("10 м²", "10 м2"),
        ("0,01...100,0 МПа", "0.01 и 100"),
    ],
)
def test_case_7(value, text) -> None:
    # 7. Числа: запятая равна точке, незначащие нули равны, ½ и ² разбираются как у входа
    # Arrange
    product = Product(
        name="Прибор", manufacturer=None, specs={"П": value}, description=None
    )

    # Act
    issues = find_card_issues(product, texts_with(seo_title=text))

    # Assert
    assert issues == ()


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"seo_title": "Манометр 2,5 МПа"}, "seo_title"),
        ({"seo_description": LONG_TEXT + " 2,5"}, "seo_description"),
        (
            {"search_queries": ("манометр 2,5 мпа", "манометр купить", "манотомь")},
            "search_queries",
        ),
        (
            {"commercial": Commercial(audience="2,5", tasks="контроль")},
            "commercial.audience",
        ),
        (
            {"commercial": Commercial(audience="служба", tasks="контроль 2,5")},
            "commercial.tasks",
        ),
    ],
)
def test_case_8(overrides, field) -> None:
    # 8. Число вне входа в каждом текстовом поле даёт замечание с именем поля
    # Act
    result = remarks_for(texts_with(**overrides))

    # Assert
    assert result == [
        f"Число 2,5 в поле {field} не встречается в данных о приборе. Убери его."
    ]


def test_case_9() -> None:
    # 9. Числа входа берутся из названия, производителя, описания, имён и значений specs
    # Arrange
    product = Product(
        name="Прибор 11",
        manufacturer="Завод 22",
        specs={"Параметр 33": "44 МПа", "Вес": 55, "Пусто": None},
        description="Описание 66.",
    )
    texts = texts_with(seo_title="11 22 33 44 55 66")

    # Act
    issues = find_card_issues(product, texts)

    # Assert
    assert issues == ()


@pytest.mark.parametrize(
    ("description", "found"),
    [
        (LONG_TEXT + " Черновик", "черновик"),
        (LONG_TEXT + " Карточка товара", "карточка"),
        (LONG_TEXT + " формат JSON", "json"),
        (LONG_TEXT + " по входным данным", "входным данным"),
        (LONG_TEXT + " входной json", "входной json"),
    ],
)
def test_case_10(description, found) -> None:
    # 10. Служебные выражения: только в описании, «входной сигнал» не замечание
    # Act
    result = remarks_for(texts_with(seo_description=description))

    # Assert
    assert len(result) >= 1
    assert f"В seo_description служебное выражение «{found}»." in result[-1]
    assert remarks_for(texts_with(seo_description=LONG_TEXT + " Входной сигнал")) == []
    assert remarks_for(texts_with(seo_title="Черновик")) == []


def test_case_11() -> None:
    # 11. Замечание: для модели указание, для контент-менеджера текст без указаний модели
    # Arrange
    texts = texts_with(
        seo_title="я" * 71,
        seo_description=LONG_TEXT + " черновик 2,5",
        search_queries=("а", "а", "б"),
        commercial=Commercial(audience="", tasks=""),
    )

    # Act
    issues = find_card_issues(PRODUCT, texts)

    # Assert
    assert [issue.warning for issue in issues] == [
        "Заголовок длиннее 70 символов (71): сократите его перед публикацией.",
        "Есть одинаковые поисковые запросы: оставьте разные.",
        "Не заполнено, кому подходит прибор.",
        "Не заполнено, какие задачи решает прибор.",
        "Число 2,5 в описании не встречается в данных о приборе: проверьте его.",
        "В описании служебное выражение «черновик»: уберите его перед публикацией.",
    ]
    for issue in issues:
        assert "seo_" not in issue.warning
        assert "commercial." not in issue.warning
        assert "search_queries" not in issue.warning


@pytest.mark.parametrize(
    ("quote", "found"),
    [
        ("Манометр  DM-02", True),
        ("СЛУЖБА кипиа", True),
        ("манометр купить", True),
        ("контроль давления", True),
        ("влагозащищённый", False),
        ("", False),
        ("   ", False),
    ],
)
def test_case_12(quote, found) -> None:
    # 12. Цитата ревьюера: найдена с нормализацией во всех полях, ложная и пустая отброшены
    # Arrange
    texts = texts_with(seo_title="Манометр DM–02")

    # Act
    issue = review_issue(texts, kind="filler", quote=quote, reason="причина")

    # Assert
    assert (issue is not None) is found


@pytest.mark.parametrize(
    ("kind", "warning"),
    [
        (
            "unsupported_claim",
            "Не подтверждено данными о приборе: «контроль давления». Проверьте или уберите.",
        ),
        (
            "filler",
            "Лишняя фраза без сведений о приборе: «контроль давления». Можно убрать.",
        ),
    ],
)
def test_case_13(kind, warning) -> None:
    # 13. Вид замечания ревьюера определяет текст warning, причина модели в него не идёт
    # Act
    issue = review_issue(
        texts_with(),
        kind=kind,
        quote="контроль давления",
        reason="убери фразу из <device>",
    )

    # Assert
    assert issue.warning == warning
    assert issue.remark == "«контроль давления»: убери фразу из <device>"


@pytest.mark.parametrize(
    ("value", "quote"),
    [
        ("жидкости и газы", "жидкостей и газов"),
        ("Жидкости И ГАЗЫ", "ЖИДКОСТЕЙ  и газов"),
        ("-40…+100 °С", "-40…+100 °С"),
        ("-40…+100,0 °С", "-40…+100 °С"),
    ],
)
def test_case_14(value, quote) -> None:
    # 14. Факт принят: цитата нормализуется, значение в именительном падеже опирается на цитату
    # Act
    result = is_fact_supported(fact(value, quote), PRODUCT.description)

    # Assert
    assert result is True


@pytest.mark.parametrize(
    ("value", "quote"),
    [
        ("жидкости", "работает до 500 °C"),
        ("жидкости", ""),
        ("100 °С и 200 °С", "-40…+100 °С"),
        ("пары и жидкости", "жидкостей и газов"),
        ("агрессивные газы", "жидкостей и газов"),
        ("", "жидкостей и газов"),
        ("   ", "жидкостей и газов"),
    ],
)
def test_case_15(value, quote) -> None:
    # 15. Факт отброшен: нет цитаты, число не из цитаты, слово не из цитаты, пустое значение
    # Act
    result = is_fact_supported(fact(value, quote), PRODUCT.description)

    # Assert
    assert result is False


@pytest.mark.parametrize(
    ("value", "quote", "supported"),
    [
        ("4 мА", "4 мА", True),
        ("газ", "газов", True),
        ("газы", "газов", True),
        ("газы", "гая", False),
        ("неагрессивные жидкости", "неагрессивных жидкостей", True),
        ("неагрессивные жидкости", "неагрес жидкостей", False),
        (
            "неагрессивные к медным сплавам жидкости и газы",
            "неагрессивных к медным сплавам жидкостей и газов",
            True,
        ),
        ("среды", "среда", True),
        ("4–20 В", "4–20 мА", False),
        ("54 кг", "54 мм", False),
        ("более 0,8 Вт", "не более 0,8 Вт", False),
        ("не более 0,8 Вт", "не более 0,8 Вт", True),
        ("сталь", "стандартный сигнал", False),
    ],
)
def test_case_16(value, quote, supported) -> None:
    # 16. Короткое слово значения есть в цитате целиком, у длинного хватает общего начала, отрицание не теряется
    # Act
    result = is_fact_supported(fact(value, quote), f"Текст: {quote}.")

    # Assert
    assert result is supported


def test_case_17() -> None:
    # 17. Сборка: значения specs как во входе и по порядку, затем факты, затем отсутствующие
    # Act
    result = assemble_characteristics(
        PRODUCT,
        facts=[fact("жидкости и газы", "жидкостей и газов", name="Рабочая среда")],
        missing_names=["Класс точности"],
    )

    # Assert
    assert result.characteristics == (
        Characteristic(name="Диапазон", value="0–1,6 МПа"),
        Characteristic(name="Диаметр корпуса", value="100"),
        Characteristic(name="Защита", value="данных нет"),
        Characteristic(name="Рабочая среда", value="жидкости и газы"),
        Characteristic(name="Класс точности", value="данных нет"),
    )
    assert result.added_missing == ("Класс точности",)
    assert result.warnings == ()


def test_case_18() -> None:
    # 18. Сборка: specs главнее факта, дубли убираются по нормализованному имени
    # Act
    result = assemble_characteristics(
        PRODUCT,
        facts=[
            fact("газы", "газов", name="ДИАПАЗОН"),
            fact("жидкости", "жидкостей", name="Среда"),
            fact("газы", "газов", name="среда"),
        ],
        missing_names=["Среда", "защита", "Класс точности", "класс  точности"],
    )

    # Assert
    assert [item.name for item in result.characteristics] == [
        "Диапазон",
        "Диаметр корпуса",
        "Защита",
        "Среда",
        "Класс точности",
    ]
    assert result.characteristics[0].value == "0–1,6 МПа"
    assert result.characteristics[3].value == "жидкости"
    assert result.added_missing == ("Класс точности",)


def test_case_19() -> None:
    # 19. Сборка: отброшенный факт даёт warning, значения в списке нет
    # Act
    result = assemble_characteristics(
        PRODUCT,
        facts=[
            fact("IP68", "IP68", name="Степень защиты"),
            fact("пары", "жидкостей и газов", name="Рабочая среда"),
        ],
        missing_names=[],
    )

    # Assert
    assert [item.name for item in result.characteristics] == [
        "Диапазон",
        "Диаметр корпуса",
        "Защита",
    ]
    assert result.warnings == (
        "Характеристика «Степень защиты» не добавлена: значение не подтверждено описанием прибора, проверьте вручную.",
        "Характеристика «Рабочая среда» не добавлена: значение не подтверждено описанием прибора, проверьте вручную.",
    )


def test_case_20() -> None:
    # 20. Сборка: факт с именем из заполненной строки specs не проверяется и не даёт warning
    # Act
    result = assemble_characteristics(
        PRODUCT,
        facts=[fact("IP68", "IP68", name="Диапазон")],
        missing_names=[],
    )

    # Assert
    assert result.warnings == ()
    assert result.characteristics[0] == Characteristic(
        name="Диапазон", value="0–1,6 МПа"
    )


def test_case_21() -> None:
    # 21. Сборка: пустые имена пропускаются, дубли внутри specs остаются как во входе
    # Arrange
    product = Product(
        name="Прибор",
        manufacturer=None,
        specs={"Вес": "1 кг", "вес": "2 кг"},
        description="жидкостей",
    )

    # Act
    result = assemble_characteristics(
        product,
        facts=[fact("жидкости", "жидкостей", name="  ")],
        missing_names=[" ", ""],
    )

    # Assert
    assert result.characteristics == (
        Characteristic(name="Вес", value="1 кг"),
        Characteristic(name="вес", value="2 кг"),
    )
    assert result.added_missing == ()
    assert result.warnings == ()


@pytest.mark.parametrize(
    ("value", "quote", "description", "supported"),
    [
        ("агрессивные среды", "агрессивных сред", "Для неагрессивных сред", False),
        ("газ", "газ", "Для газов", False),
        ("100", "100", "Всего 2100", False),
        ("10", "10", "Всего 100", False),
        ("6 МПа", "6 МПа", "Предел 1,6 МПа", False),
        ("6 МПа", "6 МПа", "Предел 1.6 МПа", False),
        ("1", "1", "Класс 1,5", False),
        ("1", "1", "Класс 1.5", False),
        ("1,6 МПа", "1,6 МПа", "Предел 1,6 МПа.", True),
        ("1,6 МПа", "1,6  мпа", "Предел\n1,6 МПа, далее", True),
        ("–40…+100 °С", "-40…+100 °С", "Среда: –40…+100 °С", True),
        ("жидкости", "жидкостей", "Для ЖИДКОСТЕЙ.", True),
        (
            "агрессивные среды",
            "агрессивных сред",
            "Для неагрессивных сред, но также для агрессивных сред",
            True,
        ),
    ],
)
def test_case_22(value, quote, description, supported) -> None:
    # 22. Цитата ищется с границами: слева и справа не буква, не цифра и не обрывок числа
    # Act
    result = is_fact_supported(fact(value, quote), description)

    # Assert
    assert result is supported


@pytest.mark.parametrize(
    ("value", "quote", "description", "supported"),
    [
        ("более 0,8 Вт", "более 0,8 Вт", "Потребляет не более 0,8 Вт", False),
        ("более 0,8 Вт", "более 0,8 Вт", "Потребляет НЕ  более 0,8 Вт", False),
        ("демпфер", "демпфера", "Манометр без демпфера", False),
        (
            "без безопасного режима",
            "безопасного режима",
            "Работа без безопасного режима",
            True,
        ),
        ("более 0,8 Вт", "более 0,8 Вт", "Потребляет более 0,8 Вт", True),
        ("давление", "давление", "В кране давление", True),
        ("давление", "давление", "В трубе без давление", False),
        ("более 5 Вт", "более 5 Вт", "Сказано не. Более 5 Вт", True),
        (
            "более 0,8 Вт",
            "более 0,8 Вт",
            "Не более 0,8 Вт в покое, более 0,8 Вт в работе",
            True,
        ),
    ],
)
def test_case_23(value, quote, description, supported) -> None:
    # 23. «Не» или «без» сразу перед цитатой в описании и нет в значении: факт отброшен
    # Act
    result = is_fact_supported(fact(value, quote), description)

    # Assert
    assert result is supported


@pytest.mark.parametrize(
    ("value", "quote", "supported"),
    [
        ("демпфер", "без демпфера", False),
        ("без демпфера", "без демпфера", True),
        ("демпфер", "демпфера", True),
    ],
)
def test_case_24(value, quote, supported) -> None:
    # 24. «Без» внутри цитаты не теряется, как и «не»
    # Act
    result = is_fact_supported(fact(value, quote), f"Манометр: {quote}.")

    # Assert
    assert result is supported


@pytest.mark.parametrize("value", ["—", "-", "…", " – ", "%", "..."])
def test_case_25(value) -> None:
    # 25. Значение без букв и цифр: факт отброшен
    # Act
    result = is_fact_supported(fact(value, "жидкостей"), PRODUCT.description)

    # Assert
    assert result is False


def test_case_26() -> None:
    # 26. Сборка: подтверждённый факт встаёт на место пустой строки specs, порядок прежний, второй строки нет
    # Arrange
    product = Product(
        name="Манометр",
        manufacturer=None,
        specs={"Класс точности": None, "Диаметр": 100, "Защита": "  "},
        description="Класс точности 1,5",
    )

    # Act
    result = assemble_characteristics(
        product,
        facts=[fact("1,5", "Класс точности 1,5", name="класс  ТОЧНОСТИ")],
        missing_names=["Класс точности", "Защита"],
    )

    # Assert
    assert result.characteristics == (
        Characteristic(name="Класс точности", value="1,5"),
        Characteristic(name="Диаметр", value="100"),
        Characteristic(name="Защита", value="данных нет"),
    )
    assert result.added_missing == ()
    assert result.warnings == ()


def test_case_27() -> None:
    # 27. Сборка: неподтверждённый факт с именем пустой строки specs даёт warning, строка остаётся пустой
    # Act
    result = assemble_characteristics(
        PRODUCT,
        facts=[fact("IP68", "IP68", name="Защита")],
        missing_names=[],
    )

    # Assert
    assert result.characteristics[2] == Characteristic(
        name="Защита", value="данных нет"
    )
    assert result.warnings == (
        "Характеристика «Защита» не добавлена: значение не подтверждено описанием прибора, проверьте вручную.",
    )


@pytest.mark.parametrize(
    ("source", "text"),
    [
        ("–40…+100 °С", "-40 и +100 °С"),
        ("–40…+100 °С", "−40 и 100 °С"),
        ("+100 °С", "100 °С"),
        ("(-20 °С)", "от -20 °С"),
        ("−0,5 МПа", "–0.5 МПа"),
        ("–40…+100 °С", "от минус 40 до плюс 100 °С"),
        ("Минус 40 °С", "-40 °С"),
    ],
)
def test_case_28(source, text) -> None:
    # 28. Числа со знаком в текстах: минус вплотную к числу часть числа, слово «минус» то же, плюс равен отсутствию знака
    # Arrange
    product = Product(
        name="Прибор", manufacturer=None, specs={"П": source}, description=None
    )

    # Act
    issues = find_card_issues(product, texts_with(seo_title=text))

    # Assert
    assert issues == ()


@pytest.mark.parametrize("minus", list("-\u2010\u2011\u2012\u2013\u2014\u2015\u2212"))
def test_case_29(minus) -> None:
    # 29. Число без знака и с минусом это разные числа, вид минуса не важен
    # Arrange
    unsigned = Product(
        name="Прибор", manufacturer=None, specs={"П": "20 °С"}, description=None
    )
    signed = Product(
        name="Прибор", manufacturer=None, specs={"П": f"{minus}20 °С"}, description=None
    )

    # Act
    extra_minus = find_card_issues(unsigned, texts_with(seo_title=f"Прибор {minus}20"))
    lost_minus = find_card_issues(signed, texts_with(seo_title="Прибор 20"))
    same = find_card_issues(signed, texts_with(seo_title="Прибор −20"))

    # Assert
    assert [issue.remark for issue in extra_minus] == [
        "Число -20 в поле seo_title не встречается в данных о приборе. Убери его."
    ]
    assert [issue.remark for issue in lost_minus] == [
        "Число 20 в поле seo_title не встречается в данных о приборе. Убери его."
    ]
    assert same == ()


@pytest.mark.parametrize(
    ("source", "text"),
    [
        ("4–20 мА", "4 и 20 мА"),
        ("4 – 20 мА", "4 и 20 мА"),
        ("ПД100-1Х1", "ПД 100 1 Х 1"),
        ("DM-02", "DM 02"),
        ("0–1,6 МПа", "0 и 1,6 МПа"),
        ("84,0...106,7 кПа", "84 и 106,7 кПа"),
        ("1,-5", "1 и 5"),
        ("1.-5", "1 и 5"),
        ("30 %–80 %", "30 и 80 %"),
        ("10%-90%", "10 и 90 %"),
        ("G½″-14", "G 1/2 и 14"),
        ("G1′-14", "G 1 и 14"),
        ('G1/2"-14', "G 1/2 и 14"),
        ("(0)-10", "0 и 10"),
        ("[0]-10", "0 и 10"),
        ("-40°-85°", "-40 и 85"),
        ("«DM»-100", "DM 100"),
    ],
)
def test_case_30(source, text) -> None:
    # 30. Минус после цифры, буквы, единицы, закрывающего знака, разделителя или с пробелом это не знак
    # Arrange
    product = Product(
        name="Прибор", manufacturer=None, specs={"П": source}, description=None
    )

    # Act
    issues = find_card_issues(product, texts_with(seo_title=text))

    # Assert
    assert issues == ()


@pytest.mark.parametrize(
    ("value", "quote", "supported"),
    [
        ("40…100 °С", "–40…+100 °С", False),
        ("40…100 °С", "40…+100 °С", False),
        ("−40…100 °С", "–40…+100 °С", True),
        ("-40, +100 °С", "–40…+100 °С", True),
    ],
)
def test_case_31(value, quote, supported) -> None:
    # 31. Числа факта сравниваются со знаком, цитата без минуса из описания не проходит
    # Act
    result = is_fact_supported(fact(value, quote), "Среда: –40…+100 °С.")

    # Assert
    assert result is supported


@pytest.mark.parametrize("source", ["–40…–20 °С", "–40...–20 °С", "–40..–20 °С"])
def test_case_32(source) -> None:
    # 32. Минус после многоточия это знак: тексты и факты с диапазоном из двух отрицательных чисел
    # Arrange
    product = Product(
        name="Прибор", manufacturer=None, specs={"П": source}, description=None
    )
    description = f"Хранение {source}."

    # Act
    right = find_card_issues(product, texts_with(seo_title="От -40 до -20 °С"))
    wrong = find_card_issues(product, texts_with(seo_title="От -40 до 20 °С"))

    # Assert
    assert right == ()
    assert [issue.remark for issue in wrong] == [
        "Число 20 в поле seo_title не встречается в данных о приборе. Убери его."
    ]
    assert is_fact_supported(fact("–20 °С", "–20 °С"), description) is True
    assert is_fact_supported(fact("20 °С", "20 °С"), description) is False


@pytest.mark.parametrize(
    "spelling",
    [
        "±0,5",
        "± 0,5",
        "+/-0,5",
        "+/- 0,5",
        "+/−0,5",
        "+-0,5",
        "+–0,5",
        "плюс-минус 0,5",
        "Плюс-минус 0,5",
        "плюс–минус 0,5",
        "плюс минус 0,5",
        "плюс/минус 0,5",
    ],
)
@pytest.mark.parametrize(
    "text",
    ["±0,5 %", "+/-0,5 %", "плюс-минус 0,5 %", "от –0,5 до +0,5 %", "0,5 %", "-0,5 %"],
)
def test_case_33(spelling, text) -> None:
    # 33. Плюс-минус в любом написании это два числа, x и -x
    # Arrange
    product = Product(
        name="Прибор", manufacturer=None, specs={"П": f"{spelling} %"}, description=None
    )

    # Act
    issues = find_card_issues(product, texts_with(seo_title=text))
    reverse = find_card_issues(
        Product(
            name="Прибор", manufacturer=None, specs={"П": "–0,5…+0,5"}, description=None
        ),
        texts_with(seo_title=f"Прибор {spelling}"),
    )

    # Assert
    assert issues == ()
    assert reverse == ()


def test_case_34() -> None:
    # 34. Плюс-минус вплотную к числу не теряет ни одного из чисел, лишний знак даёт замечание
    # Arrange
    product = Product(
        name="Прибор", manufacturer=None, specs={"П": "10±0,5"}, description=None
    )
    unsigned = Product(
        name="Прибор", manufacturer=None, specs={"П": "0,5 %"}, description=None
    )

    # Act
    issues = find_card_issues(product, texts_with(seo_title="10, -0,5 и 0,5"))
    extra = find_card_issues(unsigned, texts_with(seo_title="±0,5 %"))

    # Assert
    assert issues == ()
    assert [issue.remark for issue in extra] == [
        "Число -0,5 в поле seo_title не встречается в данных о приборе. Убери его."
    ]
