# DXA Quality Control Assistant

Ассистент контроля качества снимков рентгеновской (DXA) денситометрии.
Автоматически проверяет корректность укладки и разметки исследования и даёт
вердикт `ACCEPTED` / `REJECTED` с пояснением.

## Как это работает

```
  DICOM-файл (.dcm)
       |
       v
  +-- MedGemma 1.5 4B (Ollama, CPU) -+
  |  анализирует изображение и       |  DECISION:
  |  метаданные DICOM                |  ACCEPTED / REJECTED
  +---------------------+------------+
                        v
              Фронтенд (React + Ant Design)
```

Зона распознаётся в порядке уменьшения приоритета:
1. теги DICOM (`BodyPartExamined` / `ViewPosition`);
2. ручной выбор зоны в интерфейсе (переопределяет всё).

## Требования

- Python **3.10+** (проект проверен на 3.14)
- Node.js **18+** и npm
- [Ollama](https://ollama.com) с моделью `medgemma1.5:4b`:
  ```
  ollama pull medgemma1.5:4b
  ```
- Только CPU: MedGemma работает на CPU через Ollama.
- Допустимый вход: одиночный DICOM-файл (пакет `Secondary Capture`,
  до 50 МБ).

## Установка (один раз)

```
cd backend
python -m venv .venv
.venv/Scripts/Activate.ps1 -m pip install -r requirements.txt
```

Фронтенд:
```
cd frontend
npm install
```

## Запуск

Удобный вариант — двойным кликом:

| Файл | Что делает |
|------|------------|
| `scripts\start_all.bat` | запускает бэкенд и фронтенд (два окна) |
| `scripts\start_backend.bat` | только бэкенд (http://127.0.0.1:8000) |
| `scripts\start_frontend.bat` | только фронтенд (http://localhost:5173) |

Либо вручную:

```
cd backend
.venv/Scripts/Activate.ps1 -m uvicorn main:app --host 127.0.0.1 --port 8000
cd ../frontend && npm run dev
```

**Приложение:** http://localhost:5173  (прокси на `/api` -> `127.0.0.1:8000`)

Откройте фронтенд, загрузите DICOM-файл (например из `data\Для теста\`)
и нажмите «Анализировать».

## Статус модели

- MedGemma 1.5 4B работает локально через Ollama на CPU.
- Зона определяется по метаданным DICOM или выбору пользователя.


## Структура проекта

```
backend/                 FastAPI-бэкенд
  main.py                эндпоинты /api/analyze, /
  dcm_processing.py      чтение DICOM, метаданные, превью (base64)
  zones.py               зоны, detect_zone(), сборка промпта для MedGemma
  requirements.txt       Python-зависимости
  .venv/                 виртуальное окружение (создаётся setup.bat)
frontend/                React + Vite + Ant Design v5
data/
  Для теста/             примеры DICOM для проверки
scripts/
  setup.bat, start_all.bat, start_backend.bat, start_frontend.bat
```

## Настройки бэкенда (переменные окружения)

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `OLLAMA_BASE` | `http://127.0.0.1:11434` | адрес Ollama |
| `OLLAMA_MODEL` | `medgemma1.5:4b` | модель Ollama |
| `DXA_ENABLE_AUDIT` | `0` | `1` — писать лог аудита в `backend/logs/audit.jsonl` |

## API

- `GET /` — статус: Ollama (доступность, модель).
- `POST /api/analyze` — multipart-загрузка DICOM + опциональное поле `zone`.
  Ответ: `decision`, `response` (текст MedGemma), `zone`/`zone_label`,
  `metadata`, `preview_base64`, `prompt`.
