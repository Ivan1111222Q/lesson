# Микросервисная архитектура интернет-магазина

Бекенд приложение интернет-магазина, состоящее из 3 микросервисов на Python с использованием FastAPI.

## Архитектура

### 1. Users Service (порт 8003)
- Регистрация и аутентификация пользователей
- Управление профилями
- JWT-подобная токен-аутентификация

### 2. Products Service (порт 8001)
- Управление каталогом товаров
- Отслеживание инвентаря (stock)
- CRUD операции для товаров

### 3. Orders Service (порт 8002)
- Создание заказов
- Управление статусами заказов
- Интеграция с Products Service для проверки наличия товаров

## Запуск

### Используя Docker Compose (рекомендуется)

```bash
# Запуск всех сервисов
docker-compose up --build

# Запуск в фоновом режиме
docker-compose up -d --build

# Остановка
docker-compose down
```

### Локальный запуск

Для каждого сервиса:

```bash
cd <service-name>
pip install -r requirements.txt
python main.py
```

## API Endpoints

### Users Service (http://localhost:8003)

```
POST   /register          - Регистрация нового пользователя
POST   /login            - Вход пользователя
GET    /me               - Получить текущего пользователя (требует токен)
POST   /logout           - Выход (требует токен)
GET    /users/{user_id}  - Получить пользователя по ID
```

### Products Service (http://localhost:8001)

```
POST   /products                    - Создать товар
GET    /products                    - Получить список товаров
GET    /products?category={name}    - Фильтр по категории
GET    /products/{product_id}       - Получить товар по ID
PUT    /products/{product_id}       - Обновить товар
DELETE /products/{product_id}       - Удалить товар
PATCH  /products/{product_id}/stock - Обновить количество на складе
```

### Orders Service (http://localhost:8002)

```
POST   /orders                      - Создать заказ
GET    /orders                      - Получить все заказы
GET    /orders?user_id={id}         - Фильтр по пользователю
GET    /orders/{order_id}           - Получить заказ по ID
PATCH  /orders/{order_id}/status    - Обновить статус заказа
```

## Примеры использования

### 1. Регистрация пользователя

```bash
curl -X POST http://localhost:8003/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123",
    "name": "John Doe"
  }'
```

### 2. Создание товара

```bash
curl -X POST http://localhost:8001/products \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Laptop",
    "description": "High-performance laptop",
    "price": 999.99,
    "stock": 10,
    "category": "electronics"
  }'
```

### 3. Создание заказа

```bash
curl -X POST http://localhost:8002/orders \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "items": [
      {
        "product_id": 1,
        "quantity": 2,
        "price": 999.99
      }
    ]
  }'
```

## Технологии

- FastAPI - современный веб-фреймворк для Python
- Pydantic - валидация данных
- Uvicorn - ASGI сервер
- httpx - асинхронный HTTP клиент
- Docker & Docker Compose - контейнеризация

## Особенности

- RESTful API
- Микросервисная архитектура
- Межсервисная коммуникация (Orders -> Products)
- Базовая аутентификация с токенами
- Управление инвентарем
- Docker-ready

## Примечания

Данная реализация использует in-memory хранилище для демонстрации. В продакшене следует использовать реальные базы данных (PostgreSQL, MongoDB и т.д.).

## Swagger Documentation

После запуска сервисов, документация API доступна по адресам:

- Users: http://localhost:8003/docs
- Products: http://localhost:8001/docs
- Orders: http://localhost:8002/docs
