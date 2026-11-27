"""Backend message dictionary for ru / kk / en.

ru is the reference language; a missing kk/en key falls back to ru.
kk texts are added in stage 2 and must be reviewed by a native speaker.
"""
from __future__ import annotations

LANGS = ("ru", "kk", "en")

MESSAGES: dict[str, dict[str, str]] = {
    # ---- parse errors ----
    "parse.empty": {"ru": "Введите шаг, например 2x + 6 = 14.", "en": "Enter a step, e.g. 2x + 6 = 14."},
    "parse.too_long": {"ru": "Слишком длинная запись (максимум {max} символов).", "en": "Too long (max {max} characters)."},
    "parse.bad_char": {"ru": "Недопустимый символ «{char}». Можно: цифры, x, + - * / ( ) =.", "en": "Character “{char}” is not allowed. Use digits, x, + - * / ( ) =."},
    "parse.no_equals": {"ru": "В шаге должен быть знак «=».", "en": "A step must contain “=”."},
    "parse.many_equals": {"ru": "Знак «=» должен быть ровно один.", "en": "Use exactly one “=”."},
    "parse.empty_side": {"ru": "Одна из частей уравнения пустая.", "en": "One side of the equation is empty."},
    "parse.unbalanced": {"ru": "Проверьте скобки: не хватает открывающей или закрывающей.", "en": "Check the brackets: one is missing."},
    "parse.incomplete": {"ru": "Запись не закончена: после знака действия ничего нет.", "en": "Incomplete: nothing after an operator."},
    "parse.unexpected": {"ru": "Не удалось разобрать запись рядом с «{char}».", "en": "Could not read the input near “{char}”."},
    "parse.not_linear": {"ru": "Поддерживаются только линейные уравнения (без x·x и деления на x).", "en": "Only linear equations are supported (no x·x, no division by x)."},
    "parse.div_zero": {"ru": "Деление на ноль.", "en": "Division by zero."},
    "parse.bad_number": {"ru": "Некорректное или слишком длинное число.", "en": "Invalid or too long number."},

    # ---- generic hints (used when the bug is unknown or ambiguous) ----
    "hint.general.1": {
        "ru": "Проверь этот шаг ещё раз: какое действие ты выполнил и сделал ли ты его с обеими частями уравнения одинаково?",
        "en": "Check this step again: what did you do, and did you do the same to both sides of the equation?",
    },
    "hint.general.2": {
        "ru": "Ошибка появилась при переходе «{prev}» → «{step}». Предыдущая строка была верной.",
        "en": "The error appeared going from “{prev}” to “{step}”. The previous line was correct.",
    },
    "hint.focus.2": {
        "ru": "Ошибка появилась при переходе «{prev}» → «{step}». {focus_hint}",
        "en": "The error appeared going from “{prev}” to “{step}”. {focus_hint}",
    },
    "hint.general.3": {
        "ru": "Правило: каждое преобразование должно сохранять равенство. Что делаешь с одной частью, делай и с другой; раскрывая скобки, умножай каждое слагаемое; при переносе через «=» меняй знак.",
        "en": "Rule: every step must keep the equality. Do the same to both sides; when expanding, multiply every term; when moving a term across “=”, change its sign.",
    },
    "hint.level4": {
        "ru": "Разберём подробно. {rule} Верный вариант этого действия: «{prev}» → «{correct}». Дальше продолжи сам.",
        "en": "Let's go through it. {rule} The correct version of this step: “{prev}” → “{correct}”. Continue from there yourself.",
    },
    "hint.level4.next": {
        "ru": "Разберём подробно. {rule} Верный следующий шаг: «{prev}» → «{correct}». Дальше продолжи сам.",
        "en": "Let's go through it. {rule} A correct next step: “{prev}” → “{correct}”. Continue from there yourself.",
    },

    # ---- mode "find the error" ----
    "finderr.hint.1": {
        "ru": "Проверь переходы по очереди: на каком шаге обе части перестают быть равны при одном и том же x?",
        "en": "Check the steps one by one: at which step do the two sides stop being equal for the same x?",
    },

    # ---- "what next?" hints (no error yet, the student is stuck) ----
    "stuck.expand.1": {"ru": "Что можно сделать со скобками, чтобы упростить уравнение?", "en": "What could you do with the brackets to simplify the equation?"},
    "stuck.expand.2": {"ru": "Начни с раскрытия скобок.", "en": "Start by expanding the brackets."},
    "stuck.expand.3": {"ru": "Правило: k(a + b) = k·a + k·b — множитель умножается на каждое слагаемое.", "en": "Rule: k(a + b) = k·a + k·b — the factor multiplies every term."},
    "stuck.collect.1": {"ru": "x есть в обеих частях. Как собрать все слагаемые с x в одной части?", "en": "x is on both sides. How can you collect all x-terms on one side?"},
    "stuck.collect.2": {"ru": "Перенеси слагаемые с x в одну часть, а числа — в другую.", "en": "Move the x-terms to one side and the numbers to the other."},
    "stuck.collect.3": {"ru": "Правило: при переносе через «=» знак слагаемого меняется на противоположный.", "en": "Rule: a term moved across “=” changes its sign."},
    "stuck.move.1": {"ru": "Какое число мешает x остаться одному в своей части?", "en": "Which number keeps x from being alone on its side?"},
    "stuck.move.2": {"ru": "Перенеси число из части с x в другую часть.", "en": "Move the number from the x side to the other side."},
    "stuck.move.3": {"ru": "Правило: при переносе через «=» знак слагаемого меняется на противоположный.", "en": "Rule: a term moved across “=” changes its sign."},
    "stuck.divide.1": {"ru": "Перед x стоит число. Каким действием можно получить просто x?", "en": "There is a number in front of x. Which operation leaves just x?"},
    "stuck.divide.2": {"ru": "Раздели обе части уравнения на коэффициент при x.", "en": "Divide both sides by the coefficient of x."},
    "stuck.divide.3": {"ru": "Правило: обе части уравнения делят на одно и то же ненулевое число.", "en": "Rule: divide both sides by the same non-zero number."},
    "stuck.simplify.1": {"ru": "Можно ли упростить числовую часть?", "en": "Can you simplify the numeric part?"},
    "stuck.simplify.2": {"ru": "Вычисли значение числовой части.", "en": "Compute the numeric part."},
    "stuck.simplify.3": {"ru": "Ответ записывают в виде x = число, без невычисленных действий.", "en": "The answer is written as x = number, with nothing left to compute."},

    # ---- report ----
    "report.note": {
        "ru": "Диагноз системы вероятностный: он основан на сравнении шагов с типичными ошибками и может ошибаться. Одна ошибка ничего не говорит о способностях человека.",
        "en": "The system's diagnosis is probabilistic: it compares steps with typical errors and can be wrong. A single error says nothing about a person's abilities.",
    },
    "report.summary": {
        "ru": "Решено задач: {solved} из {total}. Неверных шагов: {errors}. Подсказок: {hints}.",
        "en": "Problems solved: {solved} of {total}. Wrong steps: {errors}. Hints: {hints}.",
    },
    "report.transfer.ok": {"ru": "Задача на перенос решена без ошибок.", "en": "The transfer problem was solved without errors."},
    "report.transfer.errors": {"ru": "В задаче на перенос были неверные шаги: {errors}.", "en": "The transfer problem had wrong steps: {errors}."},
    "report.transfer.repeat": {"ru": "В задаче на перенос снова встретилась ошибка «{name}» — эту тему стоит повторить.", "en": "The error “{name}” appeared again in the transfer problem — worth revisiting."},
    "report.transfer.none": {"ru": "Задача на перенос не решалась.", "en": "The transfer problem was not attempted."},
    "report.transfer.unsolved": {"ru": "Задача на перенос начата, но не решена.", "en": "The transfer problem was started but not solved."},
    "report.unknown_error": {"ru": "Ошибка не из каталога", "en": "Error not in the catalog"},
}


def tr(key: str, lang: str = "ru", **params) -> str:
    entry = MESSAGES.get(key, {})
    text = entry.get(lang) or entry.get("ru") or key
    return text.format(**params) if params else text


def pick(d: dict[str, str], lang: str) -> str:
    """Pick a language from an inline {lang: text} dict (catalog entries), ru fallback."""
    return d.get(lang) or d["ru"]
