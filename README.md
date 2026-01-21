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

### 4. Reviews Service (порт 8004)
**Отвечает за:**
- Создание отзывов с рейтингами (1-5 звезд)
- Загрузка и хранение фотографий к отзывам (до 5 фото)
- Верификация покупок через Orders Service
- Статистика рейтингов товаров
- Фильтрация отзывов по товарам/пользователям
- Пагинация и сортировка отзывов

**Зависимости:**
- Users Service (валидация пользователей)
- Products Service (валидация товаров)
- Orders Service (верификация покупок)

**Особенности:**
- Хранение фотографий внутри контейнера с Docker volume
- Поддержка multipart/form-data для загрузки файлов
- Валидация изображений (формат, размер)
- Автоматический расчет средних рейтингов

### Межсервисная коммуникация

Все сервисы общаются друг с другом через HTTP REST API:

```
┌─────────────────┐                              ┌──────────────────┐
│  Users Service  │                              │ Reviews Service  │
│    :8003        │◄──────────────────────────────│     :8004        │
└────────┬────────┘  GET /users/{id}            └────────┬─────────┘
         │                                                │
         │ GET /orders?user_id={id}                      │ GET /orders/{id}
         │ GET /orders/{id}                              │ Verify purchase
         ▼                                               ▼
┌─────────────────┐      GET /products/{id}      ┌──────────────────┐
│ Orders Service  │◄────────────────────────────►│ Products Service │
│    :8002        │  PATCH /products/{id}/stock  │     :8001        │◄───┐
└─────────────────┘                               └──────────────────┘    │
         ▲                                                ▲                │
         │ GET /orders (for stats)                       │                │
         │                                               │ GET /products/{id}
┌────────┴────────┐                              ┌───────┴────────┐       │
│ Products Service│                              │ Reviews Service│───────┘
│    :8001        │                              │     :8004      │
└─────────────────┘                              └────────────────┘
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

## API Endpoints - Полная документация

### Users Service (http://localhost:8003)

#### `GET /`
**Описание:** Проверка работоспособности сервиса

**Ответ:**
```json
{
  "service": "users-service",
  "status": "running"
}
```

---

#### `POST /register`
**Описание:** Регистрация нового пользователя

**Тело запроса:**
```json
{
  "email": "user@example.com",
  "password": "password123",
  "name": "John Doe"
}
```

**Ответ (200):**
```json
{
  "token": "secure-token-string",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

**Ошибки:**
- `400` - Email уже зарегистрирован

---

#### `POST /login`
**Описание:** Вход пользователя в систему

**Тело запроса:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Ответ (200):**
```json
{
  "token": "secure-token-string",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe"
  }
}
```

**Ошибки:**
- `401` - Неверный email или пароль

---

#### `GET /me`
**Описание:** Получить информацию о текущем пользователе

**Заголовки:**
```
Authorization: Bearer {token}
```

**Ответ (200):**
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "John Doe"
}
```

**Ошибки:**
- `401` - Неверный или отсутствующий токен

---

#### `POST /logout`
**Описание:** Выход из системы (удаление токена)

**Заголовки:**
```
Authorization: Bearer {token}
```

**Ответ (200):**
```json
{
  "message": "Logged out successfully"
}
```

---

#### `GET /users/{user_id}`
**Описание:** Получить информацию о пользователе по ID

**Параметры пути:**
- `user_id` (integer) - ID пользователя

**Ответ (200):**
```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "John Doe"
}
```

**Ошибки:**
- `404` - Пользователь не найден

---

#### `GET /users/{user_id}/orders`
**Описание:** Получить все заказы пользователя

**Параметры пути:**
- `user_id` (integer) - ID пользователя

**Ответ (200):**
```json
{
  "user_id": 1,
  "user_name": "John Doe",
  "user_email": "user@example.com",
  "orders_count": 3,
  "orders": [
    {
      "id": 1,
      "user_id": 1,
      "items": [...],
      "status": "delivered",
      "total": 2475.0,
      "created_at": "2025-10-28T15:33:06.715980"
    }
  ]
}
```

**Ошибки:**
- `404` - Пользователь не найден
- `503` - Orders Service недоступен

---

#### `GET /users/{user_id}/stats`
**Описание:** Получить статистику заказов пользователя

**Параметры пути:**
- `user_id` (integer) - ID пользователя

**Ответ (200):**
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

**Ошибки:**
- `404` - Пользователь не найден
- `503` - Orders Service недоступен

---

#### `GET /metrics`
**Описание:** Prometheus метрики сервиса

**Ответ (200):** Текстовый формат Prometheus

---

#### `GET /health`
**Описание:** Базовая проверка здоровья сервиса

**Ответ (200):**
```json
{
  "status": "healthy",
  "service": "users-service"
}
```

---

#### `GET /live`
**Описание:** Liveness probe для Kubernetes - проверяет что приложение живо

**Ответ (200):**
```json
{
  "status": "alive",
  "service": "users-service",
  "timestamp": "2025-10-28T15:33:06.715980"
}
```

---

#### `GET /ready`
**Описание:** Readiness probe для Kubernetes - проверяет готовность сервиса принимать запросы

**Проверяет зависимости:**
- Orders Service

**Ответ (200) - все зависимости доступны:**
```json
{
  "status": "ready",
  "service": "users-service",
  "timestamp": "2025-10-28T15:33:06.715980",
  "dependencies": {
    "orders-service": {
      "status": "healthy",
      "response_time_ms": 45.23
    }
  }
}
```

**Ответ (503) - есть недоступные зависимости:**
```json
{
  "status": "not_ready",
  "service": "users-service",
  "timestamp": "2025-10-28T15:33:06.715980",
  "dependencies": {
    "orders-service": {
      "status": "unhealthy",
      "error": "Connection refused",
      "response_time_ms": 2000.15
    }
  }
}
```

---

### Products Service (http://localhost:8001)

#### `GET /`
**Описание:** Проверка работоспособности сервиса

**Ответ:**
```json
{
  "service": "products-service",
  "status": "running"
}
```

---

#### `POST /products`
**Описание:** Создать новый товар

**Тело запроса:**
```json
{
  "name": "Laptop",
  "description": "High-performance laptop",
  "price": 1200.0,
  "stock": 10,
  "category": "electronics"
}
```

**Ответ (200):**
```json
{
  "id": 1,
  "name": "Laptop",
  "description": "High-performance laptop",
  "price": 1200.0,
  "stock": 10,
  "category": "electronics"
}
```

---

#### `GET /products`
**Описание:** Получить список всех товаров

**Query параметры (опционально):**
- `category` (string) - Фильтр по категории

**Примеры:**
- `GET /products` - все товары
- `GET /products?category=electronics` - только электроника

**Ответ (200):**
```json
[
  {
    "id": 1,
    "name": "Laptop",
    "description": "High-performance laptop",
    "price": 1200.0,
    "stock": 10,
    "category": "electronics"
  },
  {
    "id": 2,
    "name": "Mouse",
    "description": "Wireless mouse",
    "price": 25.0,
    "stock": 50,
    "category": "electronics"
  }
]
```

---

#### `GET /products/{product_id}`
**Описание:** Получить товар по ID

**Параметры пути:**
- `product_id` (integer) - ID товара

**Ответ (200):**
```json
{
  "id": 1,
  "name": "Laptop",
  "description": "High-performance laptop",
  "price": 1200.0,
  "stock": 10,
  "category": "electronics"
}
```

**Ошибки:**
- `404` - Товар не найден

---

#### `PUT /products/{product_id}`
**Описание:** Обновить информацию о товаре

**Параметры пути:**
- `product_id` (integer) - ID товара

**Тело запроса:**
```json
{
  "name": "Gaming Laptop",
  "description": "Updated description",
  "price": 1500.0,
  "stock": 15,
  "category": "electronics"
}
```

**Ответ (200):**
```json
{
  "id": 1,
  "name": "Gaming Laptop",
  "description": "Updated description",
  "price": 1500.0,
  "stock": 15,
  "category": "electronics"
}
```

**Ошибки:**
- `404` - Товар не найден

---

#### `DELETE /products/{product_id}`
**Описание:** Удалить товар

**Параметры пути:**
- `product_id` (integer) - ID товара

**Ответ (200):**
```json
{
  "message": "Product deleted successfully"
}
```

**Ошибки:**
- `404` - Товар не найден

---

#### `PATCH /products/{product_id}/stock`
**Описание:** Обновить количество товара на складе

**Параметры пути:**
- `product_id` (integer) - ID товара

**Query параметры:**
- `quantity` (integer) - Изменение количества (может быть отрицательным)

**Примеры:**
- `PATCH /products/1/stock?quantity=10` - добавить 10 единиц
- `PATCH /products/1/stock?quantity=-5` - убавить 5 единиц

**Ответ (200):**
```json
{
  "id": 1,
  "name": "Laptop",
  "stock": 15,
  "message": "Stock updated successfully"
}
```

**Ошибки:**
- `404` - Товар не найден
- `400` - Недостаточно товара на складе (при отрицательном quantity)

---

#### `GET /products/popular`
**Описание:** Получить популярные товары на основе количества заказов

**Query параметры (опционально):**
- `limit` (integer, default=10) - Максимальное количество товаров

**Пример:**
- `GET /products/popular?limit=5`

**Ответ (200):**
```json
[
  {
    "product_id": 1,
    "product_name": "Laptop",
    "product_category": "electronics",
    "product_price": 1200.0,
    "current_stock": 8,
    "times_ordered": 15,
    "total_quantity_sold": 45,
    "total_revenue": 54000.0
  },
  {
    "product_id": 2,
    "product_name": "Mouse",
    "product_category": "electronics",
    "product_price": 25.0,
    "current_stock": 35,
    "times_ordered": 12,
    "total_quantity_sold": 48,
    "total_revenue": 1200.0
  }
]
```

**Ошибки:**
- `503` - Orders Service недоступен

---

#### `GET /products/low-stock`
**Описание:** Получить товары с низким остатком

**Query параметры (опционально):**
- `threshold` (integer, default=10) - Порог низкого остатка

**Пример:**
- `GET /products/low-stock?threshold=5`

**Ответ (200):**
```json
[
  {
    "id": 5,
    "name": "Keyboard",
    "category": "electronics",
    "stock": 3,
    "price": 50.0,
    "warning": "Low stock alert"
  },
  {
    "id": 8,
    "name": "Headphones",
    "category": "electronics",
    "stock": 5,
    "price": 75.0,
    "warning": "Low stock alert"
  }
]
```

---

#### `GET /products/{product_id}/stats`
**Описание:** Получить статистику продаж конкретного товара

**Параметры пути:**
- `product_id` (integer) - ID товара

**Ответ (200):**
```json
{
  "product_id": 1,
  "product_name": "Laptop",
  "product_category": "electronics",
  "current_price": 1200.0,
  "current_stock": 8,
  "times_ordered": 15,
  "total_quantity_sold": 45,
  "total_revenue": 54000.0,
  "average_order_quantity": 3.0,
  "first_order_date": "2025-10-20T10:00:00",
  "last_order_date": "2025-10-28T15:33:06"
}
```

**Ошибки:**
- `404` - Товар не найден
- `503` - Orders Service недоступен

---

#### `GET /metrics`
**Описание:** Prometheus метрики сервиса

**Ответ (200):** Текстовый формат Prometheus

---

#### `GET /health`
**Описание:** Базовая проверка здоровья сервиса

**Ответ (200):**
```json
{
  "status": "healthy",
  "service": "products-service"
}
```

---

#### `GET /live`
**Описание:** Liveness probe для Kubernetes - проверяет что приложение живо

**Ответ (200):**
```json
{
  "status": "alive",
  "service": "products-service",
  "timestamp": "2025-10-28T15:33:06.715980"
}
```

---

#### `GET /ready`
**Описание:** Readiness probe для Kubernetes - проверяет готовность сервиса принимать запросы

**Проверяет зависимости:**
- Orders Service

**Ответ (200) - все зависимости доступны:**
```json
{
  "status": "ready",
  "service": "products-service",
  "timestamp": "2025-10-28T15:33:06.715980",
  "dependencies": {
    "orders-service": {
      "status": "healthy",
      "response_time_ms": 38.12
    }
  }
}
```

**Ответ (503) - есть недоступные зависимости:**
```json
{
  "status": "not_ready",
  "service": "products-service",
  "timestamp": "2025-10-28T15:33:06.715980",
  "dependencies": {
    "orders-service": {
      "status": "unhealthy",
      "error": "Connection timeout",
      "response_time_ms": 2001.45
    }
  }
}
```

---

### Orders Service (http://localhost:8002)

#### `GET /`
**Описание:** Проверка работоспособности сервиса

**Ответ:**
```json
{
  "service": "orders-service",
  "status": "running"
}
```

---

#### `POST /orders`
**Описание:** Создать новый заказ

**Тело запроса:**
```json
{
  "user_id": 1,
  "items": [
    {
      "product_id": 1,
      "quantity": 2,
      "price": 1200.0
    },
    {
      "product_id": 2,
      "quantity": 3,
      "price": 25.0
    }
  ],
  "status": "pending"
}
```

**Процесс создания заказа:**
1. Проверяется существование пользователя (вызов Users Service)
2. Для каждого товара проверяется наличие и достаточность stock (вызов Products Service)
3. Автоматически обновляется stock товаров (вычитается количество)
4. Создается заказ с расчетом общей суммы

**Ответ (200):**
```json
{
  "id": 1,
  "user_id": 1,
  "items": [
    {
      "product_id": 1,
      "quantity": 2,
      "price": 1200.0
    },
    {
      "product_id": 2,
      "quantity": 3,
      "price": 25.0
    }
  ],
  "status": "pending",
  "total": 2475.0,
  "created_at": "2025-10-28T15:33:06.715980"
}
```

**Ошибки:**
- `404` - Пользователь или товар не найден
- `400` - Недостаточно товара на складе
- `503` - Users Service или Products Service недоступен

---

#### `GET /orders`
**Описание:** Получить список всех заказов

**Query параметры (опционально):**
- `user_id` (integer) - Фильтр по пользователю

**Примеры:**
- `GET /orders` - все заказы
- `GET /orders?user_id=1` - заказы пользователя с ID 1

**Ответ (200):**
```json
[
  {
    "id": 1,
    "user_id": 1,
    "items": [...],
    "status": "delivered",
    "total": 2475.0,
    "created_at": "2025-10-28T15:33:06.715980"
  },
  {
    "id": 2,
    "user_id": 2,
    "items": [...],
    "status": "pending",
    "total": 1500.0,
    "created_at": "2025-10-28T16:00:00"
  }
]
```

---

#### `GET /orders/{order_id}`
**Описание:** Получить информацию о заказе по ID

**Параметры пути:**
- `order_id` (integer) - ID заказа

**Ответ (200):**
```json
{
  "id": 1,
  "user_id": 1,
  "items": [
    {
      "product_id": 1,
      "quantity": 2,
      "price": 1200.0
    }
  ],
  "status": "delivered",
  "total": 2400.0,
  "created_at": "2025-10-28T15:33:06.715980"
}
```

**Ошибки:**
- `404` - Заказ не найден

---

#### `GET /orders/{order_id}/details`
**Описание:** Получить детальную информацию о заказе с обогащенными данными о товарах

**Параметры пути:**
- `order_id` (integer) - ID заказа

**Ответ (200):**
```json
{
  "id": 1,
  "user_id": 1,
  "items": [
    {
      "product_id": 1,
      "product_name": "Laptop",
      "product_description": "High-performance laptop",
      "product_category": "electronics",
      "current_price": 1200.0,
      "ordered_price": 1200.0,
      "quantity": 2,
      "subtotal": 2400.0
    },
    {
      "product_id": 2,
      "product_name": "Mouse",
      "product_description": "Wireless mouse",
      "product_category": "electronics",
      "current_price": 25.0,
      "ordered_price": 25.0,
      "quantity": 3,
      "subtotal": 75.0
    }
  ],
  "status": "delivered",
  "total": 2475.0,
  "created_at": "2025-10-28T15:33:06.715980"
}
```

**Примечание:** Если товар был удален из каталога, будет показано "Product not found"

**Ошибки:**
- `404` - Заказ не найден

---

#### `PATCH /orders/{order_id}/status`
**Описание:** Обновить статус заказа

**Параметры пути:**
- `order_id` (integer) - ID заказа

**Query параметры:**
- `status` (string) - Новый статус (pending, processing, shipped, delivered, cancelled)

**Пример:**
- `PATCH /orders/1/status?status=shipped`

**Ответ (200):**
```json
{
  "id": 1,
  "status": "shipped"
}
```

**Ошибки:**
- `404` - Заказ не найден
- `400` - Недопустимый статус

---

#### `POST /orders/{order_id}/cancel`
**Описание:** Отменить заказ и вернуть товары на склад

**Параметры пути:**
- `order_id` (integer) - ID заказа

**Процесс отмены:**
1. Проверяется статус заказа (можно отменить только pending или processing)
2. Для каждого товара возвращается количество на склад (вызов Products Service)
3. Статус заказа меняется на "cancelled"
4. Уменьшается метрика выручки

**Ответ (200):**
```json
{
  "id": 1,
  "status": "cancelled",
  "message": "Order cancelled successfully. Stock returned to inventory.",
  "returned_items": 2
}
```

**Ошибки:**
- `404` - Заказ не найден
- `400` - Заказ нельзя отменить (статус shipped/delivered)
- `503` - Products Service недоступен

---

#### `GET /orders/stats/revenue`
**Описание:** Получить статистику по выручке и заказам

**Ответ (200):**
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

**Примечание:** Отмененные заказы не учитываются в выручке

---

#### `GET /metrics`
**Описание:** Prometheus метрики сервиса

**Ответ (200):** Текстовый формат Prometheus

---

#### `GET /health`
**Описание:** Базовая проверка здоровья сервиса

**Ответ (200):**
```json
{
  "status": "healthy",
  "service": "orders-service"
}
```

---

#### `GET /live`
**Описание:** Liveness probe для Kubernetes - проверяет что приложение живо

**Ответ (200):**
```json
{
  "status": "alive",
  "service": "orders-service",
  "timestamp": "2025-10-28T15:33:06.715980"
}
```

---

#### `GET /ready`
**Описание:** Readiness probe для Kubernetes - проверяет готовность сервиса принимать запросы

**Проверяет зависимости:**
- Products Service
- Users Service

**Ответ (200) - все зависимости доступны:**
```json
{
  "status": "ready",
  "service": "orders-service",
  "timestamp": "2025-10-28T15:33:06.715980",
  "dependencies": {
    "products-service": {
      "status": "healthy",
      "response_time_ms": 32.54
    },
    "users-service": {
      "status": "healthy",
      "response_time_ms": 41.28
    }
  }
}
```

**Ответ (503) - есть недоступные зависимости:**
```json
{
  "status": "not_ready",
  "service": "orders-service",
  "timestamp": "2025-10-28T15:33:06.715980",
  "dependencies": {
    "products-service": {
      "status": "healthy",
      "response_time_ms": 35.12
    },
    "users-service": {
      "status": "unhealthy",
      "error": "Service unavailable",
      "response_time_ms": 2000.87
    }
  }
}
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

### 8. Создание отзыва с фотографиями

```bash
curl -X POST http://localhost:8004/reviews \
  -F "user_id=1" \
  -F "product_id=1" \
  -F "order_id=1" \
  -F "rating=5" \
  -F "text=Отличный товар! Рекомендую!" \
  -F "photos=@photo1.jpg" \
  -F "photos=@photo2.jpg"
```

Ответ:
```json
{
  "id": 1,
  "user_id": 1,
  "product_id": 1,
  "order_id": 1,
  "rating": 5,
  "text": "Отличный товар! Рекомендую!",
  "photos": [
    "uuid-1.jpg",
    "uuid-2.jpg"
  ],
  "is_verified_purchase": true,
  "created_at": "2025-10-28T19:00:00"
}
```

### 9. Получение рейтинга товара

```bash
curl http://localhost:8004/products/1/rating
```

Ответ:
```json
{
  "product_id": 1,
  "average_rating": 4.5,
  "total_reviews": 10,
  "rating_distribution": {
    "5": 6,
    "4": 2,
    "3": 1,
    "2": 1,
    "1": 0
  },
  "verified_purchases": 8,
  "reviews_with_photos": 5
}
```

### 10. Получение фотографии из отзыва

```bash
curl http://localhost:8004/reviews/1/photos/uuid-1.jpg --output photo.jpg
```

### 11. Фильтрация отзывов по товару

```bash
curl "http://localhost:8004/reviews?product_id=1&sort_by=rating&limit=10"
```

Ответ:
```json
[
  {
    "id": 3,
    "user_id": 2,
    "product_id": 1,
    "order_id": 2,
    "rating": 5,
    "text": "Отличный товар!",
    "photos": ["uuid-3.jpg"],
    "is_verified_purchase": true,
    "created_at": "2025-10-28T20:00:00"
  }
]
```

## Технологии

- **FastAPI** - современный веб-фреймворк для Python
- **Pydantic** - валидация данных
- **Uvicorn** - ASGI сервер
- **httpx** - асинхронный HTTP клиент для межсервисной коммуникации
- **Docker & Docker Compose** - контейнеризация
- **Prometheus** - мониторинг и сбор метрик
- **python-dotenv** - управление переменными окружения
- **Pillow** - обработка и валидация изображений
- **aiofiles** - асинхронная работа с файлами
- **python-multipart** - обработка multipart/form-data загрузок

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

**Reviews Service (http://localhost:8004/metrics):**
- `reviews_created_total` - количество созданных отзывов
- `photos_uploaded_total` - количество загруженных фотографий
- `photos_storage_size_bytes` - размер хранилища фотографий в байтах
- `average_product_rating` - средний рейтинг по товарам
- `verified_purchases_total` - количество верифицированных покупок
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

**Reviews Service:**
```env
USERS_SERVICE_URL=http://users-service:8003
PRODUCTS_SERVICE_URL=http://products-service:8001
ORDERS_SERVICE_URL=http://orders-service:8002
PORT=8004
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
- Reviews: http://localhost:8004/docs
