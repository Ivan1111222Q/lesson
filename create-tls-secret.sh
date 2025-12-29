#!/bin/bash
NAMESPACE="lesson4356"
SECRET_NAME="kube-prometheus-stack-admission"

# Генерируем сертификат
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes \
  -subj "/CN=kube-prometheus-stack.$NAMESPACE.svc"

# Создаём Kubernetes secret
kubectl create secret tls $SECRET_NAME \
  --namespace $NAMESPACE \
  --cert=cert.pem \
  --key=key.pem

# Уберите временные файлы
rm -f key.pem cert.pem

echo "✅ Secret $SECRET_NAME создан в namespace $NAMESPACE"
