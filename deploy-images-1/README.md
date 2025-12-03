# Deploy Script 

Автоматизированный скрипт для деплоя Docker образов в Kubernetes через Helm.

## 🚀 Возможности

Скрипт `deploy.py` позволяет одной командой:

- ✅ **Собирать Docker image** с автоматической проверкой архитектуры
- ✅ **Проверять архитектуру** и пересобирать под `linux/amd64`, если нужно
- ✅ **Пушить в Yandex Container Registry** (и опционально в DockerHub)
- ✅ **Обновлять Helm chart** (`values.yaml`) только для `image.repository` и `image.tag`
- ✅ **Выполнять `helm upgrade --install`** в указанном namespace
- ✅ **Автоматически инкрементировать версию** образа
- ✅ **Валидировать конфигурацию** перед запуском
- ✅ **Проверять зависимости** (Docker, Helm)

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

### Проверка установки

```bash
docker --version
helm version
python3 --version
```

---

## ⚙️ Настройка `deploy_config.yaml`

Создайте файл `deploy_config.yaml` в папке со скриптом:

```yaml
# Имя образа (без registry)
image: frontend-service

# Текущая версия (будет автоматически увеличена, если auto_version: true)
tag: "2.10"

# Yandex Container Registry
registry: cr.yandex/crpiqtsurn6alildl4cb

# DockerHub (опционально, укажите null если не используете)
dockerhub: null
# dockerhub: your-dockerhub-username

# Путь к Dockerfile относительно deploy.py
dockerfile_path: ../

# Путь к основному Helm chart относительно deploy.py
helm_chart_path: ../../Helm/frontend-service

# Имя Helm release для основного чарта
helm_release: frontend-service

# Namespace для деплоя
helm_namespace: lesson4356

# Автоматически увеличивать версию (например, 2.10 → 2.11)
auto_version: true

# Обновлять values.yaml (только image.repository и image.tag) для основного чарта
update_values: true

# === Опционально: настройки rollout-чарта ===

# Путь к rollout Helm chart (например, чарт с Argo Rollouts)
# Если не нужен — можно не указывать
rollout_helm_chart_path: ../../Helm/frontend-service-rollout

# Имя Helm release для rollout-чарта
rollout_helm_release: frontend-service-rollout

# Namespace для rollout-чарта (по умолчанию = helm_namespace)
rollout_helm_namespace: lesson4356

# Обновлять values.yaml у rollout-чарта (по умолчанию = update_values)
rollout_update_values: true

# === Опционально: umbrella-чарт для всех rollout-сервисов ===

# Путь к umbrella-чарту rollout-сервисов
services_umbrella_chart_path: ../../Helm/services-rollout

# Имя Helm release для umbrella-чарта
services_umbrella_release: services-rollout

# Namespace для umbrella-чарта (по умолчанию = helm_namespace)
services_umbrella_namespace: lesson4356
```

### Параметры конфигурации

| Параметр | Обязательный | Описание |
|----------|--------------|----------|
| `image` | ✅ | Имя образа (без registry) |
| `tag` | ✅ | Версия образа (например, "2.10") |
| `registry` | ✅ | Registry для push (например, `cr.yandex/xxx`) |
| `dockerhub` | ❌ | DockerHub username (или `null`) |
| `dockerfile_path` | ✅ | Путь к Dockerfile (относительно скрипта) |
| `helm_chart_path` | ✅ | Путь к основному Helm chart (относительно скрипта) |
| `helm_release` | ✅ | Имя Helm release основного чарта |
| `helm_namespace` | ✅ | Kubernetes namespace |
| `auto_version` | ❌ | Автоинкремент версии (по умолчанию `false`) |
| `update_values` | ❌ | Обновлять values.yaml основного чарта (по умолчанию `false`) |
| `rollout_helm_chart_path` | ❌ | Путь к rollout Helm chart (Argo Rollouts) |
| `rollout_helm_release` | ❌ | Имя Helm release для rollout-чарта |
| `rollout_helm_namespace` | ❌ | Namespace для rollout-чарта (если отличается) |
| `rollout_update_values` | ❌ | Обновлять values.yaml rollout-чарта (по умолчанию = `update_values`) |
| `services_umbrella_chart_path` | ❌ | Путь к umbrella-чарту для всех rollout-сервисов |
| `services_umbrella_release` | ❌ | Имя Helm release для umbrella-чарта |
| `services_umbrella_namespace` | ❌ | Namespace для umbrella-чарта (по умолчанию = `helm_namespace`) |

---

## 🔹 Использование

### Базовое использование

1. Перейдите в папку со скриптом:
   ```bash
   cd frontend-service/deploy-images
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
9. ✅ **Обновление values.yaml** (если `update_values: true`)
10. ✅ **Helm upgrade** - выполняет `helm upgrade --install`

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

📦 Авто-версия: 2.10 → 2.11

=== СБОРКА ОБРАЗА ===
>>> RUN: docker build -t frontend-service:2.11 ../
✅ Образ собран: frontend-service:2.11

=== ПРОВЕРКА АРХИТЕКТУРЫ ===
Архитектура: arm64
⚠️  Архитектура != amd64 → пересобираем под linux/amd64
>>> RUN: docker build --platform linux/amd64 -t frontend-service:2.11 ../
✅ Образ пересобран под amd64

=== PUSH В YANDEX REGISTRY ===
>>> RUN: docker tag frontend-service:2.11 cr.yandex/crpiqtsurn6alildl4cb/frontend-service:2.11
>>> RUN: docker push cr.yandex/crpiqtsurn6alildl4cb/frontend-service:2.11
✅ Образ запушен: cr.yandex/crpiqtsurn6alildl4cb/frontend-service:2.11

=== ОБНОВЛЕНИЕ values.yaml ===
✅ values.yaml обновлен: repository=cr.yandex/crpiqtsurn6alildl4cb/frontend-service, tag=2.11

=== HELM UPGRADE ===
>>> RUN: helm upgrade --install frontend-service ../../Helm/frontend-service -n lesson4356
✅ Helm upgrade выполнен: frontend-service в namespace lesson4356

==================================================
✅ ДЕПЛОЙ УСПЕШНО ЗАВЕРШЕН
==================================================
📦 Образ: cr.yandex/crpiqtsurn6alildl4cb/frontend-service:2.11
🚀 Release: frontend-service
📁 Namespace: lesson4356
```

---

## ⚠️ Важные замечания

### Структура values.yaml

Скрипт ожидает, что `values.yaml` содержит секцию `image`:

```yaml
image:
  repository: ""
  tag: ""
```

Скрипт **не трогает** остальные поля (replicaCount, resources, service, readinessProbe и др.)

### Пути в конфиге

Все пути в `deploy_config.yaml` должны быть **относительными** к папке, где лежит `deploy.py`.

### Автоинкремент версии

Функция `inc_version()` работает с числовыми версиями:
- ✅ `2.10` → `2.11`
- ✅ `1.0.0` → `1.0.1`
- ✅ `v2.10` → `2.11` (префикс `v` удаляется)

Нечисловые версии (например, `latest`, `dev`) пропускаются без изменений.

### Архитектура образа

Скрипт автоматически проверяет архитектуру образа и пересобирает под `linux/amd64`, если текущая архитектура отличается. Это полезно при сборке на Apple Silicon (M1/M2).

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
❌ Путь к Dockerfile не существует: ../Dockerfile
```
Решение: Проверьте путь `dockerfile_path` в конфиге

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
tag: "2.10"
```

### Отключение обновления values.yaml

Если хотите обновлять values.yaml вручную:

```yaml
update_values: false
```

---

## 📚 Структура проекта

```
frontend-service/
├── deploy-images/
│   ├── deploy.py              # Основной скрипт
│   ├── deploy_config.yaml     # Конфигурация
│   └── README.md              # Документация
├── Dockerfile                 # Dockerfile для сборки
└── ...
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
- [ ] Пути к Dockerfile и Helm chart корректны
- [ ] Есть доступ к Yandex Container Registry
- [ ] `values.yaml` содержит секцию `image`
- [ ] Kubernetes namespace существует