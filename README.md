# Task Tracker


## Структура проекта

```
task_tracker/
├── main.py
├── .env
├── requirements.txt
├── init.sql
├── app/
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── services/
│   │   └── auth.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── projects.py
│   │   ├── tasks.py
│   │   ├── attachments.py
│   │   └── analytics.py
│   └── static/
│       ├── css/main.css
│       ├── js/api.js
│       ├── js/auth.js
│       └── uploads/
└── templates/
    ├── base.html
    ├── auth/
    │   ├── login.html
    │   └── register.html
    ├── projects/
    │   ├── list.html
    │   └── board.html
    └── analytics/
        └── report.html
```

## Установка и запуск

### 1. Клонировать репозиторий

```bash
git clone https://github.com/Pahaluyk/Course_work_kanban.git
cd Course_work_kanban
```

### 2. Создать базу данных

Если не знаете пароль от пользователя postgres — сбросьте его:

```bash
psql -U postgres
\password postgres
# ввести новый пароль: 12345
\q
```

Затем создайте базу и таблицы:

```bash
psql -U postgres -c "CREATE DATABASE task_tracker;"
psql -U postgres -d task_tracker -f init.sql
```

После этого укажите тот же пароль в файле `.env`:

```
DATABASE_URL=postgresql+asyncpg://postgres:12345@localhost:5432/task_tracker
```

### 3. Создать виртуальное окружение и установить зависимости

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 4. Запустить сервер

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Приложение доступно по адресу http://localhost:8000
