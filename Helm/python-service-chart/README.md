# Универсальный Helm чарт для Python-сервисов

## Оглавление
1. [Проблема: дублирование кода](#проблема-дублирование-кода)
2. [Решение: универсальный чарт](#решение-универсальный-чарт)
3. [Структура чарта](#структура-чарта)
4. [Ключевая идея](#ключевая-идея)
5. [Как это работает](#как-это-работает)
6. [Пошаговая инструкция](#пошаговая-инструкция)
7. [Команды Helm](#команды-helm)
8. [Задания для практики](#задания-для-практики)

---

## Проблема: дублирование кода

### Было (плохо):
```
Helm/
├── orders-service-rollout/
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── rollout.yaml      # Одинаковый шаблон
│       ├── service.yaml      # Одинаковый шаблон
│       └── configmap.yaml    # Одинаковый шаблон
│
├── users-service-rollout/
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── rollout.yaml      # Копия!
│       ├── service.yaml      # Копия!
│       └── configmap.yaml    # Копия!
│
├── products-service-rollout/
│   └── ... те же файлы ...   # Ещё одна копия!
```

**Проблемы:**
- Шаблоны дублируются 5 раз (по числу сервисов)
- Изменение в одном месте требует правок во всех чартах
- Легко забыть обновить один из чартов
- Нарушение принципа DRY (Don't Repeat Yourself)

---

## Решение: универсальный чарт

### Стало (хорошо):
```
Helm/
├── python-service-chart/       # ОДИН чарт для всех
│   ├── Chart.yaml
│   ├── values.yaml             # Дефолтные значения
│   └── templates/
│       ├── rollout.yaml
│       ├── service.yaml
│       └── configmap.yaml
│
└── values/                     # Только values для каждого сервиса
    ├── orders-service.yaml
    ├── users-service.yaml
    └── products-service.yaml
```

**Преимущества:**
- Шаблоны в одном месте
- Изменил один раз — применилось ко всем сервисам
- Для нового сервиса достаточно создать values-файл
- Следование принципу DRY

---

## Структура чарта

```
python-service-chart/
│
├── Chart.yaml          # Метаданные чарта (имя, версия)
│
├── values.yaml         # Значения по умолчанию
│                       # Переопределяются через -f values/<service>.yaml
│
└── templates/          # Шаблоны Kubernetes манифестов
    │
    ├── rollout.yaml    # Argo Rollout (или Deployment)
    │                   # Определяет контейнер, реплики, стратегию деплоя
    │
    ├── service.yaml    # Kubernetes Service
    │                   # Определяет сетевой доступ к подам
    │
    └── configmap.yaml  # ConfigMap
                        # Хранит переменные окружения
```

### Что делает каждый файл:

| Файл | Назначение |
|------|------------|
| `Chart.yaml` | Имя чарта, версия, описание. Helm использует для идентификации |
| `values.yaml` | Переменные с дефолтными значениями. Можно переопределить при установке |
| `rollout.yaml` | Шаблон для создания Argo Rollout (управляет подами и canary-деплоем) |
| `service.yaml` | Шаблон для Service (балансировка трафика на поды) |
| `configmap.yaml` | Шаблон для ConfigMap (переменные окружения приложения) |

---

## Ключевая идея

### Проблема с `.Chart.Name`

В обычных чартах имя ресурсов берётся из имени чарта:
```yaml
metadata:
  name: {{ .Chart.Name }}-rollout    # Всегда "python-service-chart-rollout"
```

Это работает, когда у каждого сервиса свой чарт. Но в универсальном чарте имя одно для всех!

### Решение: `.Values.serviceName`

Вынести имя сервиса в values:
```yaml
# values/orders-service.yaml
serviceName: orders-service

# values/users-service.yaml
serviceName: users-service
```

И использовать в шаблонах:
```yaml
metadata:
  name: {{ .Values.serviceName }}-rollout    # "orders-service-rollout" или "users-service-rollout"
```

---

## Как это работает

### Шаг 1: Helm читает шаблон
```yaml
# templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Values.serviceName }}-service    # Placeholder
  namespace: {{ .Values.namespace }}
spec:
  ports:
    - port: {{ .Values.service.port }}
```

### Шаг 2: Helm загружает values
```yaml
# values/orders-service.yaml
serviceName: orders-service
namespace: lesson4356
service:
  port: 8002
```

### Шаг 3: Helm подставляет значения
```yaml
# Результат (то, что отправится в Kubernetes)
apiVersion: v1
kind: Service
metadata:
  name: orders-service-service
  namespace: lesson4356
spec:
  ports:
    - port: 8002
```

---

## Пошаговая инструкция

### Как добавить новый сервис (например, reviews-service):

**Шаг 1:** Создай файл `values/reviews-service.yaml`

**Шаг 2:** Скопируй структуру из существующего файла (например, orders-service.yaml)

**Шаг 3:** Измени уникальные значения:
```yaml
serviceName: reviews-service      # Уникальное имя
namespace: lesson4356

image:
  repository: cr.yandex/.../reviews-service   # Свой образ
  tag: "1.0"

service:
  port: 8004                      # Свой порт
  targetPort: 8004
  nodePort: 30004                 # Свой nodePort

config:
  PORT: "8004"                    # Свои переменные окружения
  # ... другие переменные
```

**Шаг 4:** Установи:
```bash
helm install reviews ./python-service-chart -f values/reviews-service.yaml
```

---

## Команды Helm

### Установка сервиса
```bash
# Синтаксис: helm install <release-name> <chart-path> -f <values-file>

helm install orders ./python-service-chart -f values/orders-service.yaml
helm install users ./python-service-chart -f values/users-service.yaml
helm install products ./python-service-chart -f values/products-service.yaml
```

### Обновление сервиса
```bash
# После изменения values или шаблонов
helm upgrade orders ./python-service-chart -f values/orders-service.yaml
```

### Просмотр сгенерированных манифестов (без установки)
```bash
# Полезно для отладки — показывает что именно будет создано
helm template orders ./python-service-chart -f values/orders-service.yaml
```

### Удаление сервиса
```bash
helm uninstall orders
```

### Список установленных релизов
```bash
helm list
```

---

## Задания для практики

### Задание 1: Создать secret.yaml (обязательно)
Создай файл `templates/secret.yaml` по аналогии с configmap.yaml:
- Kind: Secret
- Данные берутся из `.Values.secret`
- Не забудь про base64 кодирование (или используй stringData)

### Задание 2: Добавить probes в rollout.yaml (обязательно)
Раскомментируй и доработай секции livenessProbe и readinessProbe:
- Используй значения из `.Values.livenessProbe` и `.Values.readinessProbe`
- Добавь условие `{{- if .Values.livenessProbe }}`

### Задание 3: Добавить resources (обязательно)
Раскомментируй секцию resources в rollout.yaml:
- requests: сколько ресурсов гарантированно выделяется
- limits: максимум, который под может использовать

### Задание 4: Создать values для оставшихся сервисов
- `values/reviews-service.yaml` (порт 8004, nodePort 30004)
- `values/frontend-service.yaml` (порт 8080, nodePort 30080)

### Задание 5: Протестировать (опционально)
```bash
# Проверить что манифесты генерируются корректно
helm template test ./python-service-chart -f values/orders-service.yaml

# Проверить синтаксис
helm lint ./python-service-chart -f values/orders-service.yaml
```

---

## Полезные ссылки

- [Helm Documentation](https://helm.sh/docs/)
- [Helm Template Functions](https://helm.sh/docs/chart_template_guide/function_list/)
- [Argo Rollouts](https://argo-rollouts.readthedocs.io/)
