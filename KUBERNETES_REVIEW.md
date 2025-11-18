# Анализ конфигурации Kubernetes проекта

## ✅ Что сделано правильно

1. **Единый namespace** - все ресурсы используют namespace `lesson4356`
2. **Service объекты** - все deployment имеют соответствующие Service объекты
3. **Liveness probes** - большинство сервисов имеют liveness probes
4. **Resource limits** - все контейнеры имеют requests и limits
5. **PVC для данных** - используются PersistentVolumeClaim для postgres, elasticsearch, grafana, reviews
6. **ConfigMaps и Secrets** - правильное разделение конфигурации и секретов
7. **RBAC для Prometheus** - настроены ClusterRole и ClusterRoleBinding

## ⚠️ Проблемы и рекомендации

### 🔴 Критические проблемы

#### 1. **Readiness probes закомментированы**
**Проблема:** В deployment файлах users, orders, products, reviews сервисов readiness probes закомментированы.

**Почему это важно:** Readiness probes предотвращают отправку трафика на поды, которые еще не готовы обрабатывать запросы. Это особенно важно для сервисов с зависимостями.

**Решение:** Раскомментировать readiness probes во всех сервисах.

**Файлы:**
- `users-service/deployment.yaml` (строки 34-41)
- `orders-service/deployment.yaml` (строки 32-39)
- `products-service/deployment.yaml` (строки 32-39)
- `reviews-service/deployment.yaml` (строки 37-44)

#### 2. **Отсутствует Namespace ресурс**
**Проблема:** Нет явного создания namespace `lesson4356`.

**Решение:** Создать файл `namespace.yaml`:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: lesson4356
```

#### 3. **Отсутствуют health checks для инфраструктурных компонентов**
**Проблема:** Postgres, Elasticsearch, Grafana, Prometheus не имеют liveness/readiness probes.

**Решение:** Добавить probes для всех компонентов.

### 🟡 Важные улучшения

#### 4. **Отсутствует imagePullPolicy**
**Проблема:** Большинство deployment не указывают `imagePullPolicy`. Для локальных образов (products-service:5.0, orders-service:5.0 и т.д.) это может вызвать проблемы.

**Решение:** Добавить `imagePullPolicy: IfNotPresent` или `imagePullPolicy: Never` для локальных образов.

**Пример:**
```yaml
containers:
- name: products-service
  image: products-service:5.0
  imagePullPolicy: IfNotPresent  # или Never для локальных образов
```

#### 5. **Проблемы с nginx proxy_pass в frontend**
**Проблема:** В `frontend-service/configmap.yaml` proxy_pass не заканчиваются на `/`, что может вызвать проблемы с маршрутизацией.

**Текущая конфигурация:**
```nginx
location /api/products/ {
    proxy_pass http://products-service:8001;
}
```

**Рекомендация:** Добавить trailing slash или изменить путь:
```nginx
location /api/products/ {
    proxy_pass http://products-service:8001/;
}
```

Или использовать rewrite:
```nginx
location /api/products/ {
    rewrite ^/api/products/(.*) /$1 break;
    proxy_pass http://products-service:8001;
}
```

#### 6. **Хардкод токена в Kibana**
**Проблема:** В `kibana/deployment.yaml` (строка 24-25) захардкожен ServiceAccount токен.

**Проблемы:**
- Токен может истечь
- Небезопасно хранить токены в deployment файлах
- Токен специфичен для конкретного кластера

**Решение:** Использовать ServiceAccount и автоматическую инжекцию токена через projected volumes или убрать токен, если security отключен.

#### 7. **Fluent Bit использует Docker-specific пути**
**Проблема:** В `fluent/deployment.yaml` используется `/var/lib/docker/containers`, что работает только с Docker runtime.

**Решение:** Для современных кластеров (containerd, cri-o) нужно использовать другие пути или использовать Kubernetes API для получения логов.

**Альтернатива:** Использовать `/var/log/pods` и `/var/log/containers` которые работают с любым CRI.

#### 8. **Отсутствует POSTGRES_USER в reviews-config**
**Проблема:** В `reviews-service/configmap.yaml` есть `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, но нет `POSTGRES_USER`.

**Решение:** Добавить `POSTGRES_USER` в configmap или убедиться, что приложение использует значение из secret.

#### 9. **Несоответствие в users-config**
**Проблема:** В `users-service/configmap.yaml` есть `REVIEWS_SERVICE_URL`, но в README не упоминается, что users-service использует reviews-service.

**Решение:** Либо убрать эту переменную, либо добавить функциональность в users-service.

### 🟢 Рекомендации для улучшения

#### 10. **Отсутствуют security contexts**
**Рекомендация:** Добавить security contexts для ограничения прав контейнеров:
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  allowPrivilegeEscalation: false
  capabilities:
    drop:
    - ALL
```

#### 11. **Отсутствуют pod disruption budgets**
**Рекомендация:** Для production добавить PodDisruptionBudget для критичных сервисов.

#### 12. **Нет NetworkPolicies**
**Рекомендация:** Добавить NetworkPolicies для ограничения сетевого трафика между сервисами.

#### 13. **Отсутствуют resource quotas**
**Рекомендация:** Добавить ResourceQuota и LimitRange для namespace.

#### 14. **Grafana пароли в plain text**
**Проблема:** В `grafana/deployment.yaml` пароли указаны в plain text в env переменных.

**Решение:** Использовать Secret для паролей.

#### 15. **Отсутствуют startup probes**
**Рекомендация:** Для сервисов с долгим стартом (postgres, elasticsearch) добавить startup probes.

#### 16. **Нет health checks для Prometheus**
**Проблема:** Prometheus deployment не имеет liveness/readiness probes.

**Решение:** Добавить:
```yaml
livenessProbe:
  httpGet:
    path: /-/healthy
    port: 9090
readinessProbe:
  httpGet:
    path: /-/ready
    port: 9090
```

#### 17. **Elasticsearch без health checks**
**Проблема:** Elasticsearch не имеет probes.

**Решение:** Добавить:
```yaml
livenessProbe:
  httpGet:
    path: /_cluster/health
    port: 9200
readinessProbe:
  httpGet:
    path: /_cluster/health
    port: 9200
```

#### 18. **Postgres без health checks**
**Проблема:** Postgres не имеет probes.

**Решение:** Добавить:
```yaml
livenessProbe:
  exec:
    command:
    - /bin/sh
    - -c
    - pg_isready -U user -d reviews
readinessProbe:
  exec:
    command:
    - /bin/sh
    - -c
    - pg_isready -U user -d reviews
```

#### 19. **Grafana без health checks**
**Проблема:** Grafana не имеет probes.

**Решение:** Добавить:
```yaml
livenessProbe:
  httpGet:
    path: /api/health
    port: 3000
readinessProbe:
  httpGet:
    path: /api/health
    port: 3000
```

#### 20. **Отсутствует init container для postgres**
**Рекомендация:** Если нужна инициализация БД, добавить init container.

## 📋 Чек-лист для исправления

- [ ] Создать namespace.yaml
- [ ] Раскомментировать readiness probes во всех сервисах
- [ ] Добавить imagePullPolicy для всех образов
- [ ] Добавить liveness/readiness probes для postgres
- [ ] Добавить liveness/readiness probes для elasticsearch
- [ ] Добавить liveness/readiness probes для grafana
- [ ] Добавить liveness/readiness probes для prometheus
- [ ] Исправить proxy_pass в nginx config
- [ ] Убрать хардкод токена из Kibana или использовать ServiceAccount
- [ ] Исправить пути в Fluent Bit для поддержки containerd
- [ ] Добавить POSTGRES_USER в reviews-config или проверить использование secret
- [ ] Убрать REVIEWS_SERVICE_URL из users-config или добавить функциональность
- [ ] Переместить пароли Grafana в Secret
- [ ] Добавить security contexts
- [ ] Добавить startup probes для долго стартующих сервисов

## 🎯 Приоритеты исправления

### Высокий приоритет (критично для работы):
1. Раскомментировать readiness probes
2. Создать namespace.yaml
3. Добавить health checks для postgres (критично для reviews-service)

### Средний приоритет (важно для стабильности):
4. Добавить imagePullPolicy
5. Добавить health checks для инфраструктурных компонентов
6. Исправить nginx proxy_pass
7. Исправить Fluent Bit пути

### Низкий приоритет (улучшения):
8. Security contexts
9. NetworkPolicies
10. Resource quotas
11. PodDisruptionBudgets

