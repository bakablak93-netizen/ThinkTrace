# ThinkTrace AI

Прототип для IT FEST 2026 (направление «Minds and Machines in Rethinking Learning»).

Студент решает линейное уравнение **по шагам**. Система проверяет каждый шаг, определяет
тип ошибки и ведёт наводящими вопросами, **не выдавая решение**. После решения даёт
похожую задачу без подсказок (задача переноса), чтобы проверить понимание.

**Принцип:** математику и диагностику делает код (SymPy). LLM только формулирует текст
(подсказка по готовому ID ошибки, разбор неизвестной ошибки, текст отчёта). У каждой
LLM-функции есть шаблонный fallback, поэтому демо работает без интернета.

## Структура

```
backend/
  requirements.txt
  pytest.ini
  thinktrace/
    parser.py       строка -> sympy.Eq
    verifier.py     equivalent(prev, new), is_solved(eq)
    bugs/catalog.py каталог типовых ошибок
    diagnose.py     поиск ошибки по каталогу
    hints.py        Hint Ladder (уровни 1-4) + guard от выдачи ответа
    problems.py     генераторы задач и задач переноса
    events.py       журнал событий (Thinking Trace)
    report.py       отчёт и Индекс самостоятельности
    llm.py          LLMClient: реальный провайдер / TemplateClient
    i18n.py         тексты ru/kk/en
    db.py           SQLite (stdlib sqlite3)
    api.py          FastAPI
  tests/
frontend/           React + Vite + TypeScript
  src/i18n/         ru.ts, kk.ts, en.ts
eval/               (этап 3) steps.csv + скрипт точности диагностики
```

## Запуск

Backend (Python 3.11+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn thinktrace.api:create_app --factory --reload --port 8000
```

Тесты:

```bash
cd backend && pytest -q
```

Frontend (Node 18+):

```bash
cd frontend
npm install
npm run dev
```

Откройте http://localhost:5173. Запросы на `/api` проксируются на `localhost:8000`.

## Конфигурация

Скопируйте `.env.example` в `.env`. Если `LLM_API_KEY` пуст, используются шаблоны
(TemplateClient). `.env` в git не коммитится.

## Данные и этика

- Хранится только анонимный ник, без ФИО и почты.
- Есть полное удаление данных пользователя.
- Диагноз вероятностный. В интерфейсе это помечено, а кнопка «Не согласен с оценкой» сохраняет событие.
- По одной ошибке система не делает выводов о способностях человека.
