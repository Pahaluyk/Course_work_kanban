# Task Tracker

## Установка и запуск

### 1. Клонировать репозиторий

```bash
git clone https://github.com/Pahaluyk/Course_work_kanban.git
cd Course_work_kanban
```

### 2. Создать базу данных

```bash
psql -U postgres -c "CREATE DATABASE task_tracker;"
psql -U postgres -d task_tracker -f init.sql
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
