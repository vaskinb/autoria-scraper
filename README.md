# AutoRIA Scraper

Скрапер для збору даних про автомобілі з сайту [AUTO.RIA](https://auto.ria.com/uk/car/used).

## Опис

Скрапер збирає інформацію про вживані автомобілі з сайту AUTO.RIA та робить бекап щодня у вказані години. 
Дані зберігаються в базі даних PostgreSQL.

### Основні можливості:

- Щоденний запуск у вказаний час (за замовчуванням о 12:00 збір, о 23:00 резервна копія)
- Проходження по всіх сторінках результатів пошуку
- Збір детальної інформації з кожної картки автомобіля
- Зберігання даних у PostgreSQL
- Створення резервних копій у форматах JSON та CSV
- Налаштування через змінні середовища (.env)
- Розгортання через Docker Compose

## Структура

```
autoria-scraper/
├── .env                    # Файл з налаштуваннями
├── README.md               # Документація проекту
├── docker-compose.yml      # Конфігурація Docker Compose
├── Dockerfile              # Конфігурація Docker образу
├── requirements.txt        # Залежності Python
├── dumps/                  # Директорія для резервних копій
├── app/
│   ├── __init__.py
│   ├── main.py             # Головний модуль додатку
│   ├── config.py           # Налаштування та конфігурація
│   ├── database.py         # Робота з базою даних
│   ├── models.py           # ORM моделі
│   ├── scheduler.py        # Планувальник завдань
│   └── scraper/
│       ├── __init__.py
│       ├── autoria_scraper.py  # Логіка скрапера
│       └── utils.py            # Утиліти

```

## Модель даних

Дані зберігаються в таблиці `cars` з наступними полями:

| Поле | Тип | Опис |
|------|-----|------|
| id | Integer | Первинний ключ |
| url | String | URL сторінки автомобіля |
| title | String | Назва автомобіля |
| price_usd | Float | Ціна в USD |
| odometer | Integer | Пробіг в км |
| username | String | Ім'я продавця |
| phone_number | String | Номер телефону |
| image_url | String | URL головного зображення |
| images_count | Integer | Кількість зображень |
| car_number | String | Номер автомобіля |
| car_vin | String | VIN-код автомобіля |
| datetime_found | DateTime | Дата і час збору даних |

## Вимоги

- Docker
- Docker Compose

## Встановлення та запуск

###  1: Клонування репозиторію

```bash
git clone https://github.com/vaskinb/autoria-scraper.git
cd autoria-scraper
```

### 2: Налаштування змінних середовища

Редагування файлу .env під свої потреби:


```
# Database Configuration
DB_HOST=db
DB_PORT=5432
DB_USER=autoria
DB_PASSWORD=autopassword
DB_NAME=autoria_db

# Scraper Configuration
START_URL=https://auto.ria.com/uk/car/used
SCRAPER_RUN_TIME=12:00
BACKUP_RUN_TIME=23:00
USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36
REQUEST_TIMEOUT=30
REQUEST_DELAY=2

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT="{time} | {level} | {message}"
LOG_ROTATION="500 MB"
```

### 3: Запуск через Docker Compose

```bash
docker-compose up -d
```

Це запустить два сервіси:
- `app`: Скрапер AUTO.RIA
- `db`: База даних PostgreSQL

### 4: Перевірка роботи сервісів

Перегляд логів:

```bash
docker-compose logs -f app
```

## Використання

### Запуск планових задач

```bash
docker-compose exec app python -m app.main
```

### Ручний запуск скрапера негайно

```bash
docker-compose exec app python -m app.main --run-now
```

### Створення резервної копії


```bash
docker-compose exec app python -m app.main --backup
```

### Зміна часу запуску

Для зміни часу запуску скрапера та бекапу змініть зміннні `SCRAPER_RUN_TIME` та
`BACKUP_RUN_TIME` у файлі `.env` відповідно.

## Розробка

Запуск скраперу без Docker:

1. Створення віртуального середовища:

```bash
python3.11 -m venv venv
source venv/bin/activate
```

2. Встановлення залежностей:

```bash 
pip install -r requirements.txt
```

3. Створення локальної бази даних PostgreSQL (або оновіть налаштування в `.env`).

```
$ sudo -u postgres psql
postgres=# CREATE DATABASE autoria_db;
postgres=# CREATE USER autoria WITH ENCRYPTED PASSWORD 'autopassword';
postgres=# GRANT ALL PRIVILEGES ON DATABASE autoria_db TO autoria;
```

4. Запуск парсера негайно:

```bash
python -m app.main --run-now
```

## Логування

Логи зберігаються в директорії `logs/` та виводяться у консоль.