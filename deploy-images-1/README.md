# Deploy Script 

Автоматизированный скрипт для деплоя Docker образов в Kubernetes через Helm.

## 🚀 Возможности

Скрипт `deploy.py` позволяет одной командой:

- ✅ **Собирать Docker image** с автоматической проверкой архитектуры
- ✅ **Проверять архитектуру** и пересобирать под `linux/amd64`, если нужно
- ✅ **Пушить в Yandex Container Registry** (и опционально в DockerHub)
- ✅ **Обновлять values файл** в `Helm/values/` только для `image.repository` и `image.tag`
- ✅ **Выполнять `helm upgrade --install`** с универсальным chart `python-service-chart`
- ✅ **Автоматически инкрементировать версию** образа
- ✅ **Валидировать конфигурацию** перед запуском
- ✅ **Проверять зависимости** (Docker, Helm)
- ✅ **Автоматически делать git push** в ветку `lesson` после успешного деплоя

---

## 📋 Требования

### Установка зависимостей Python

```bash
pip3 install ruamel.yaml pyyaml
```

### Системные зависимости

Убедитесь, что установлены:

- **Docker** (версия 20.10+)
- **Helm** (версия 3.0+)
- **Python 3.7+**
- Доступ к **Yandex Container Registry** (или другой registry)
- **Git** (для автоматического push)

### Проверка установки

```bash
docker --version
helm version
python3 --version
git --version
```

---

## ⚙️ Настройка `deploy_config.yaml`

Создайте файл `deploy_config.yaml` в папке со скриптом:

```yaml
# Имя образа (без registry)
image: users-service

# Текущая версия (будет автоматически увеличена, если auto_version: true)
tag: "2.23"

# Yandex Container Registry
registry: cr.yandex/crpiqtsurn6alildl4cb

# DockerHub (опционально, укажите null если не используете)
dockerhub: null
# dockerhub: your-dockerhub-username

# Путь к Dockerfile (абсолютный или относительный)
dockerfile_path: /Users/spirit/Desktop/lesson8/users-service

# Путь к универсальному Helm chart python-service-chart
helm_chart_path: /Users/spirit/Desktop/lesson8/Helm/python-service-chart

# Путь к values файлу для конкретного сервиса
values_file_path: /Users/spirit/Desktop/lesson8/Helm/values/users-service.yaml

# Имя Helm release (опционально, по умолчанию берется из image без суффикса -service)
helm_release: users

# Namespace для деплоя
helm_namespace: lesson4356

# Автоматически увеличивать версию (например, 2.23 → 2.24)
auto_version: true

# Обновлять values файл (только image.repository и image.tag)
update_values: true
```

### Параметры конфигурации

| Параметр | Обязательный | Описание |
|----------|--------------|----------|
| `image` | ✅ | Имя образа (без registry), например `users-service` |
| `tag` | ✅ | Версия образа (например, "2.23") |
| `registry` | ✅ | Registry для push (например, `cr.yandex/xxx`) |
| `dockerhub` | ❌ | DockerHub username (или `null`) |
| `dockerfile_path` | ✅ | Путь к Dockerfile (абсолютный или относительный) |
| `helm_chart_path` | ✅ | Путь к универсальному Helm chart `python-service-chart` |
| `values_file_path` | ✅ | Путь к values файлу в `Helm/values/{service}-service.yaml` |
| `helm_release` | ❌ | Имя Helm release (по умолчанию: `image` без суффикса `-service`) |
| `helm_namespace` | ✅ | Kubernetes namespace |
| `auto_version` | ❌ | Автоинкремент версии (по умолчанию `false`) |
| `update_values` | ❌ | Обновлять values файл (по умолчанию `false`) |

### Примеры конфигурации для разных сервисов

**Для users-service:**
```yaml
image: users-service
dockerfile_path: /Users/spirit/Desktop/lesson8/users-service
values_file_path: /Users/spirit/Desktop/lesson8/Helm/values/users-service.yaml
helm_release: users
```

**Для orders-service:**
```yaml
image: orders-service
dockerfile_path: /Users/spirit/Desktop/lesson8/orders-service
values_file_path: /Users/spirit/Desktop/lesson8/Helm/values/orders-service.yaml
helm_release: orders
```

---

## 🔹 Использование

### Базовое использование

1. Перейдите в папку со скриптом:
   ```bash
   cd deploy-images-1
   ```

2. Убедитесь, что `deploy_config.yaml` настроен правильно

3. Запустите скрипт:
   ```bash
   python3 deploy.py
   ```

### Что делает скрипт

Скрипт выполнит следующие шаги в автоматическом режиме:

1. ✅ **Проверка зависимостей** - проверяет наличие Docker и Helm
2. ✅ **Валидация конфига** - проверяет корректность конфигурации
3. ✅ **Автоинкремент версии** (если `auto_version: true`)
4. ✅ **Сборка Docker image** - `docker build -t {image}:{tag} {dockerfile_path}`
5. ✅ **Проверка архитектуры** - проверяет архитектуру образа
6. ✅ **Пересборка под amd64** (если архитектура != amd64)
7. ✅ **Push в Yandex Registry** - тегирует и пушит образ
8. ✅ **Push в DockerHub** (если указан `dockerhub`)
9. ✅ **Обновление values файла** (если `update_values: true`)
10. ✅ **Helm upgrade** - выполняет `helm upgrade --install` с указанным values файлом
11. ✅ **Git push** - автоматически коммитит изменения и пушит в ветку `lesson`

---

## 📝 Пример работы

### Пример вывода скрипта:

```
==================================================
🚀 НАЧАЛО ДЕПЛОЯ
==================================================

=== ПРОВЕРКА ЗАВИСИМОСТЕЙ ===
✅ Все зависимости установлены

✅ Конфигурация валидна

📦 Авто-версия: 2.23 → 2.24

=== СБОРКА ОБРАЗА ===
>>> RUN: docker build -t users-service:2.24 /Users/spirit/Desktop/lesson8/users-service
✅ Образ собран: users-service:2.24

=== ПРОВЕРКА АРХИТЕКТУРЫ ===
Архитектура: arm64
⚠️  Архитектура != amd64 → пересобираем под linux/amd64
>>> RUN: docker build --platform linux/amd64 -t users-service:2.24 /Users/spirit/Desktop/lesson8/users-service
✅ Образ пересобран под amd64

=== PUSH В YANDEX REGISTRY ===
>>> RUN: docker tag users-service:2.24 cr.yandex/crpiqtsurn6alildl4cb/users-service:2.24
>>> RUN: docker push cr.yandex/crpiqtsurn6alildl4cb/users-service:2.24
✅ Образ запушен: cr.yandex/crpiqtsurn6alildl4cb/users-service:2.24

=== ОБНОВЛЕНИЕ values ФАЙЛА ===
✅ Values файл обновлен: repository=cr.yandex/crpiqtsurn6alildl4cb/users-service, tag=2.24

=== HELM UPGRADE ===
>>> RUN: helm upgrade --install users /Users/spirit/Desktop/lesson8/Helm/python-service-chart -f /Users/spirit/Desktop/lesson8/Helm/values/users-service.yaml -n lesson4356
✅ Helm upgrade выполнен: users в namespace lesson4356

==================================================
✅ ДЕПЛОЙ УСПЕШНО ЗАВЕРШЕН
==================================================
📦 Образ: cr.yandex/crpiqtsurn6alildl4cb/users-service:2.24
🚀 Release: users
📁 Namespace: lesson4356

=== GIT PUSH ===
📝 Обнаружены изменения в репозитории
>>> RUN: git add -A
>>> RUN: git commit -m Deploy users-service:2.24
✅ Изменения закоммичены: Deploy users-service:2.24
>>> RUN: git push origin lesson
✅ Изменения запушены в origin/lesson
```

---

## ⚠️ Важные замечания

### Структура values файла

Скрипт ожидает, что values файл в `Helm/values/{service}-service.yaml` содержит секцию `image`:

```yaml
image:
  repository: ""
  tag: ""
```

Скрипт **не трогает** остальные поля (serviceName, namespace, replicaCount, resources, service, config и др.)

### Структура проекта

Проект использует универсальный Helm chart `python-service-chart`:

```
lesson8/
├── Helm/
│   ├── python-service-chart/      # Универсальный chart для всех сервисов
│   │   ├── Chart.yaml
│   │   ├── values.yaml            # Дефолтные значения
│   │   └── templates/
│   │       ├── rollout.yaml
│   │       ├── service.yaml
│   │       └── configmap.yaml
│   └── values/                    # Values файлы для каждого сервиса
│       ├── users-service.yaml
│       ├── orders-service.yaml
│       ├── products-service.yaml
│       └── reviews-service.yaml
├── users-service/
│   └── Dockerfile
├── orders-service/
│   └── Dockerfile
└── deploy-images-1/
    ├── deploy.py
    ├── deploy_config.yaml
    └── README.md
```

### Пути в конфиге

Пути в `deploy_config.yaml` могут быть:
- **Абсолютными** (рекомендуется): `/Users/spirit/Desktop/lesson8/...`
- **Относительными** к папке, где лежит `deploy.py`

### Автоинкремент версии

Функция `inc_version()` работает с числовыми версиями:
- ✅ `2.23` → `2.24`
- ✅ `1.0.0` → `1.0.1`
- ✅ `v2.10` → `2.11` (префикс `v` удаляется)

Нечисловые версии (например, `latest`, `dev`) пропускаются без изменений.

### Архитектура образа

Скрипт автоматически проверяет архитектуру образа и пересобирает под `linux/amd64`, если текущая архитектура отличается. Это полезно при сборке на Apple Silicon (M1/M2).

### Git push

После успешного деплоя скрипт автоматически:
1. Ищет корень git репозитория (поднимается вверх по дереву до `.git`)
2. Проверяет наличие изменений
3. Если есть изменения - делает `git add -A` и коммит с сообщением `Deploy {image}:{tag}`
4. Выполняет `git push origin lesson`

Если git операция не удалась, деплой считается успешным, но выводится предупреждение.

---

## 🐛 Обработка ошибок

Скрипт включает улучшенную обработку ошибок:

- ✅ Проверка наличия всех зависимостей
- ✅ Валидация конфигурации перед запуском
- ✅ Проверка существования файлов и путей
- ✅ Информативные сообщения об ошибках
- ✅ Корректное завершение при прерывании (Ctrl+C)

### Типичные ошибки

**Ошибка: Docker не найден**
```
❌ docker не найден. Установите docker и попробуйте снова.
```
Решение: Установите Docker

**Ошибка: Путь к Dockerfile не существует**
```
❌ Путь к Dockerfile не существует: /path/to/dockerfile
```
Решение: Проверьте путь `dockerfile_path` в конфиге

**Ошибка: Файл values не найден**
```
❌ Файл values не найден: /path/to/values.yaml
```
Решение: Проверьте путь `values_file_path` в конфиге и убедитесь, что файл существует

**Ошибка: Helm upgrade failed**
```
❌ Команда завершилась с кодом 1: helm upgrade ...
```
Решение: Проверьте права доступа к кластеру и корректность Helm chart

---

## 🔧 Расширенные возможности

### Использование DockerHub

Если хотите пушить в DockerHub, укажите в конфиге:

```yaml
dockerhub: your-dockerhub-username
```

Скрипт автоматически затегирует и запушит образ в DockerHub.

### Отключение автоинкремента версии

Если хотите использовать фиксированную версию:

```yaml
auto_version: false
tag: "2.23"
```

### Отключение обновления values файла

Если хотите обновлять values файл вручную:

```yaml
update_values: false
```

### Отключение git push

Если нужно отключить автоматический git push, просто удалите или закомментируйте соответствующий блок кода в `deploy.py` (строки с `=== GIT PUSH ===`).

---

## 📚 Структура проекта

```
lesson8/
├── Helm/
│   ├── python-service-chart/      # Универсальный chart
│   └── values/                     # Values для каждого сервиса
│       ├── users-service.yaml
│       ├── orders-service.yaml
│       ├── products-service.yaml
│       └── reviews-service.yaml
├── users-service/
│   ├── Dockerfile
│   └── ...
├── orders-service/
│   ├── Dockerfile
│   └── ...
└── deploy-images-1/
    ├── deploy.py                   # Основной скрипт
    ├── deploy_config.yaml          # Конфигурация
    └── README.md                   # Документация
```

---

## 🤝 Вклад

Если нашли баг или хотите улучшить скрипт:

1. Проверьте существующие issues
2. Создайте новый issue с описанием проблемы
3. Или создайте Pull Request с улучшениями

---

## 📄 Лицензия

Этот скрипт является частью проекта и следует его лицензии.

---

## ✅ Чеклист перед деплоем

- [ ] Docker установлен и запущен
- [ ] Helm установлен и настроен доступ к кластеру
- [ ] `deploy_config.yaml` настроен правильно
- [ ] Пути к Dockerfile, chart и values файлу корректны
- [ ] Есть доступ к Yandex Container Registry
- [ ] Values файл в `Helm/values/` содержит секцию `image`
- [ ] Kubernetes namespace существует
- [ ] Git репозиторий настроен и есть доступ к remote `origin`
