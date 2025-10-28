# Микросервисная архитектура интернет-магазина

Бекенд приложение интернет-магазина, состоящее из 3 микросервисов на Python с использованием FastAPI.

## Архитектура

Приложение построено на основе микросервисной архитектуры с синхронной HTTP-коммуникацией между сервисами.

### 1. Users Service (порт 8003)
**Отвечает за:**
- Регистрация и аутентификация пользователей
- Управление профилями
- JWT-подобная токен-аутентификация
- Агрегация данных о заказах пользователей
- Статистика активности пользователей

**Зависимости:**
- Orders Service (для получения заказов пользователя)

### 2. Products Service (порт 8001)
**Отвечает за:**
- Управление каталогом товаров
- Отслеживание инвентаря (stock)
- CRUD операции для товаров
- Аналитика популярных товаров
- Мониторинг товаров с низким остатком

**Зависимости:**
- Orders Service (для получения статистики продаж)

### 3. Orders Service (порт 8002)
**Отвечает за:**
- Создание заказов с валидацией
- Управление статусами заказов
- Отмена заказов с возвратом товаров на склад
- Интеграция с Products Service для проверки наличия и обновления остатков
- Интеграция с Users Service для проверки существования пользователя
- Детальная информация о заказах с обогащением данными о товарах
- Статистика выручки и продаж

**Зависимости:**
- Products Service (проверка наличия, обновление stock)
- Users Service (валидация пользователей)

### Межсервисная коммуникация

Все сервисы общаются друг с другом через HTTP REST API:

```
┌─────────────────┐
│  Users Service  │
│    :8003        │
└────────┬────────┘
         │
         │ GET /orders?user_id={id}
         │ GET /orders/{id}
         ▼
┌─────────────────┐      GET /products/{id}      ┌──────────────────┐
│ Orders Service  │◄────────────────────────────►│ Products Service │
│    :8002        │  PATCH /products/{id}/stock  │     :8001        │
└─────────────────┘                               └──────────────────┘
         ▲
         │ GET /orders (for stats)
         │
┌────────┴────────┐
│ Products Service│
│    :8001        │
└─────────────────┘
```

**Особенности реализации:**
- Распределенная трассировка через X-Trace-ID
- Таймауты на межсервисные вызовы (5 секунд)
- Graceful degradation при недоступности сервисов
- Автоматическая метрика latency всех HTTP вызовов
- Retry логика не реализована (добавить в продакшене)

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
POST   /register                - Регистрация нового пользователя
POST   /login                   - Вход пользователя
GET    /me                      - Получить текущего пользователя (требует токен)
POST   /logout                  - Выход (требует токен)
GET    /users/{user_id}         - Получить пользователя по ID
GET    /users/{user_id}/orders  - Получить все заказы пользователя
GET    /users/{user_id}/stats   - Получить статистику заказов пользователя
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
GET    /products/popular            - Получить популярные товары (на основе заказов)
GET    /products/low-stock          - Получить товары с низким остатком
GET    /products/{product_id}/stats - Получить статистику продаж продукта
```

### Orders Service (http://localhost:8002)

```
POST   /orders                      - Создать заказ
GET    /orders                      - Получить все заказы
GET    /orders?user_id={id}         - Фильтр по пользователю
GET    /orders/{order_id}           - Получить заказ по ID
GET    /orders/{order_id}/details   - Получить детальную информацию о заказе с продуктами
PATCH  /orders/{order_id}/status    - Обновить статус заказа
POST   /orders/{order_id}/cancel    - Отменить заказ (возвращает товары на склад)
GET    /orders/stats/revenue        - Получить статистику по выручке
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

### 4. Получение статистики пользователя

```bash
curl http://localhost:8003/users/1/stats
```

Ответ:
```json
{
  "user_id": 1,
  "user_name": "John Doe",
  "user_email": "user@example.com",
  "total_orders": 5,
  "completed_orders": 3,
  "cancelled_orders": 1,
  "total_spent": 4999.95,
  "average_order_value": 999.99,
  "orders_by_status": {
    "delivered": 3,
    "pending": 1,
    "cancelled": 1
  },
  "first_order_date": "2025-10-28T10:00:00",
  "last_order_date": "2025-10-28T15:33:06"
}
```

### 5. Получение популярных товаров

```bash
curl http://localhost:8001/products/popular?limit=5
```

### 6. Получение статистики выручки

```bash
curl http://localhost:8002/orders/stats/revenue
```

Ответ:
```json
{
  "total_orders": 10,
  "completed_orders": 7,
  "cancelled_orders": 2,
  "total_revenue": 12475.50,
  "average_order_value": 1247.55,
  "orders_by_status": {
    "pending": 1,
    "processing": 0,
    "shipped": 2,
    "delivered": 7,
    "cancelled": 2
  },
  "revenue_by_status": {
    "delivered": 10000.00,
    "shipped": 2475.50
  }
}
```

### 7. Отмена заказа

```bash
curl -X POST http://localhost:8002/orders/1/cancel
```

Товары автоматически вернутся на склад.

## Технологии

- **FastAPI** - современный веб-фреймворк для Python
- **Pydantic** - валидация данных
- **Uvicorn** - ASGI сервер
- **httpx** - асинхронный HTTP клиент для межсервисной коммуникации
- **Docker & Docker Compose** - контейнеризация
- **Prometheus** - мониторинг и сбор метрик
- **python-dotenv** - управление переменными окружения

## Особенности

- ✅ RESTful API
- ✅ Микросервисная архитектура
- ✅ Межсервисная коммуникация (Orders ↔ Products ↔ Users)
- ✅ Базовая аутентификация с токенами
- ✅ Управление инвентарем с автоматическим обновлением остатков
- ✅ Структурированное JSON логирование
- ✅ Распределенная трассировка запросов (X-Trace-ID)
- ✅ Prometheus метрики для мониторинга
- ✅ Конфигурация через переменные окружения
- ✅ Docker-ready

## Логирование и мониторинг

### Структурированное логирование

Все сервисы используют структурированное JSON-логирование с поддержкой трассировки:

- **Формат**: JSON с полями timestamp, level, message, service, trace_id
- **Уровни**: INFO, WARNING, ERROR
- **Трассировка**: X-Trace-ID автоматически передается между сервисами
- **Конфигурация**: через переменные окружения LOG_LEVEL и LOG_FORMAT

Пример лога:
```json
{
  "timestamp": "2025-10-28T15:33:06.715980",
  "level": "INFO",
  "message": "Order created successfully",
  "service": "orders-service",
  "trace_id": "abc123def456",
  "order_id": 1,
  "user_id": 1,
  "total": 2475.0
}
```

### Prometheus метрики

Каждый сервис экспортирует метрики на `/metrics` endpoint:

**Products Service (http://localhost:8001/metrics):**
- `products_created_total` - количество созданных товаров (по категориям)
- `products_deleted_total` - количество удаленных товаров
- `products_stock_total` - общее количество товаров на складе
- `product_price_distribution` - распределение цен по категориям
- `stock_updates_total` - количество обновлений остатков
- `http_client_request_duration_seconds` - latency межсервисных вызовов

**Orders Service (http://localhost:8002/metrics):**
- `orders_created_total` - количество созданных заказов (по статусам)
- `orders_cancelled_total` - количество отмененных заказов
- `order_items_total` - общее количество проданных товаров
- `order_value_distribution` - распределение стоимости заказов
- `revenue_total` - общая выручка
- `order_status_changes_total` - изменения статусов заказов
- `http_client_request_duration_seconds` - latency межсервисных вызовов

**Users Service (http://localhost:8003/metrics):**
- `users_registered_total` - количество зарегистрированных пользователей
- `user_logins_total` - попытки входа (успешные/неудачные)
- `user_logouts_total` - количество выходов
- `active_users_total` - текущее количество активных пользователей
- `http_client_request_duration_seconds` - latency межсервисных вызовов

Также доступны автоматические HTTP метрики от prometheus-fastapi-instrumentator:
- Latency запросов
- Количество запросов по эндпоинтам
- HTTP коды ответов

## Конфигурация

Каждый сервис настраивается через переменные окружения. Создайте `.env` файл на основе `.env.example`:

**Products Service:**
```env
ORDERS_SERVICE_URL=http://orders-service:8002
PORT=8001
LOG_LEVEL=INFO
LOG_FORMAT=json
METRICS_ENABLED=true
```

**Orders Service:**
```env
PRODUCTS_SERVICE_URL=http://products-service:8001
USERS_SERVICE_URL=http://users-service:8003
PORT=8002
LOG_LEVEL=INFO
LOG_FORMAT=json
METRICS_ENABLED=true
```

**Users Service:**
```env
ORDERS_SERVICE_URL=http://orders-service:8002
PORT=8003
LOG_LEVEL=INFO
LOG_FORMAT=json
METRICS_ENABLED=true
```

## Примечания

Данная реализация использует in-memory хранилище для демонстрации. В продакшене следует использовать реальные базы данных (PostgreSQL, MongoDB и т.д.).

## Swagger Documentation

После запуска сервисов, документация API доступна по адресам:

- Users: http://localhost:8003/docs
- Products: http://localhost:8001/docs
- Orders: http://localhost:8002/docs
