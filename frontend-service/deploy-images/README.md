# Deploy Script 

Этот скрипт `deploy.py` позволяет одной командой:

- Собирать Docker image
- Проверять архитектуру и пересобирать под amd64, если нужно
- Пушить в Yandex Container Registry
- Обновлять Helm chart (`values.yaml`) только для `image.repository` и `image.tag`
- Выполнять `helm upgrade` в указанном namespace

---

## Структура проекта


---

## Установка зависимостей

Скрипт использует Python 3 и библиотеку `ruamel.yaml`, `pyyaml`. Установите :

```bash

pip3 install ruamel.yaml

python3 -m pip install pyyaml

Также убедитесь, что установлены:

- Docker
- Helm
- Доступ к Yandex Container Registry

---


>>>>>>>>>>Настройка deploy_config.yaml<<<<<<<<<<<

image: frontend-service 
tag: "2.10"
registry: cr.yandex/crpiqtsurn6alildl4cb
dockerhub: null

# Путь к Dockerfile относительно deploy.py
dockerfile_path: ../ >>> ваш путь к Dockerfile

# Путь к Helm chart относительно deploy.py
helm_chart_path: ../../../Helm/front-service >>> ваш путь к helm_chart

helm_release: frontend-service
helm_namespace: prod >>> меняем namespace на тот который вам нужен

auto_version: true >>> автоматически увеличивает версию образа (например, 2.10 → 2.11)
update_values: true >>> обновляет только image.repository и image.tag в values.yaml, не трогая остальное

---



🔹 ## Использование 

Перейдите в папку со скриптом:

cd frontend-service/deploy-images

- Запустите скрипт:

python3 deploy.py

- Скрипт выполнит следующие шаги:

Сборка Docker image
Проверка архитектуры; если != amd64, пересборка с --platform linux/amd64
Push образа в Yandex Registry
Обновление values.yaml (только image.repository и image.tag)
Выполнение helm upgrade для указанного релиза и namespace

🔹 ## Примечания

Если хотите использовать DockerHub, укажите dockerhub в deploy_config.yaml.
Пути в deploy_config.yaml должны быть относительными к папке, где лежит deploy.py.
values.yaml должен содержать ключ image:
image:
  repository: ""
  tag: ""
Скрипт не трогает остальные поля (replicaCount, resources, service, readinessProbe и др.)

- Пример работы:

Авто-версия: 2.10 → 2.11

=== СБОРКА ОБРАЗА ===
>>> RUN: docker build -t frontend-service:2.11 ../

=== ПРОВЕРКА АРХИТЕКТУРЫ ===
Архитектура != amd64 → пересобираем
>>> RUN: docker build --platform linux/amd64 -t frontend-service:2.11 ../

=== PUSH В YANDEX ===
>>> RUN: docker tag frontend-service:2.11 cr.yandex/crpiqtsurn6alildl4cb/frontend-service:2.11
>>> RUN: docker push cr.yandex/crpiqtsurn6alildl4cb/frontend-service:2.11

=== ОБНОВЛЯЮ values.yaml ===
>>> values.yaml успешно обновлён

=== HELM UPGRADE ===
>>> helm upgrade frontend-service ../../../Helm/front-service -n prod









