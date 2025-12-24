import os
import sys
import yaml
import subprocess
from pathlib import Path

def run_command(cmd, check=True):
    """Выполнить shell команду"""
    print(f"🚀 Выполняю: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0 and check:
        print(f"❌ Ошибка: {result.stderr}")
        sys.exit(1)
    return result

def check_prerequisites():
    """Проверить наличие необходимых инструментов"""
    
    # Проверка Helm
    result = run_command("helm version --short ", check=False)
    if result.returncode != 0:
        print("❌ Helm не установлен")
        run_command("curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash")
    if result.returncode == 0:
        print(f"Helm установлен {result.stdout}")

           
    
    # Проверка kubectl
    result = run_command("kubectl version --client", check=False)
    if result.returncode != 0:
        print("❌ kubectl не установлен")
    if result.returncode == 0:
        print(f"kubectl установлен {result.stdout}")    
    
    # Проверка подключения к кластеру
    result = run_command("kubectl cluster-info", check=False)
    if result.returncode != 0:
        print("❌ Нет подключения к Kubernetes кластеру")
        print("Настройте kubeconfig или запустите minikube:")
        print("  minikube start")
        sys.exit(1)
    if result.returncode == 0:
        if "minikube" in result.stdout:
            print("✅ Подключение к minikube установлено")
        else:
            print(f"✅ Подключение к Kubernetes кластеру установлено: {result.stdout}")

def helm_namespace():
    """Установка Helm Chart"""
    kube_namespace = run_command("kubectl get namespace lesson4356", check=False)
    if kube_namespace.returncode != 0:
        print("❌ Namespace не найден")
        return
    else:
        print(f"✅ Namespace найден {kube_namespace.stdout}")
        
def helm_prometheus_node_exporter():
    # Загрузка Helm Chart - prometheus_node_exporter
    prometheus_node_exporter = run_command("kubectl get pods -n lesson4356 -o wide", check=False)
    if "node-exporter" in prometheus_node_exporter.stdout.lower():
        print("✅Helm prometheus_node_exporter установлен")

    else:    
        print("ℹ️ Helm Chart не найден, устанавливаю...")

        install_result = run_command("helm upgrade --install prometheus-node-exporter ./Helm/prometheus-node-exporter -n lesson4356 --wait", check=False)
        if install_result.returncode != 0:
            print("❌ Ошибка при установке Helm Chart")
            print(f"❌ Ошибка: {install_result.stderr}")
            sys.exit(1)
        else:
            print("✅ Helm Chart prometheus-node-exporter установлен")

def helm_postgres():
    # Загрузка  Helm Chart - postgres
    postgres = run_command("kubectl get pods -n lesson4356 -o wide", check=False)
    if "postgres" in postgres.stdout.lower():
        print("✅Helm postgres установлен")
    else:
        print("ℹ️ Helm Chart postgres не найден, устанавливаю...")
        install_result = run_command("helm upgrade --install postgres ./Helm/postgres -n lesson4356 --wait", check=False)
        if install_result.returncode != 0:
            print("❌ Ошибка при установке Helm Chart postgres")
            sys.exit(1)
        else:
            print("✅ Helm Chart postgres установлен")


def helm_eck_operator():
    # Загрузка  Helm Chart - eck-operator
    eck_operator = run_command("kubectl get pods -n lesson4356 -o wide", check=False)
    if "elastic-operator" in eck_operator.stdout.lower():
        print("✅Helm eck-operator установлен")
    else:
        print("ℹ️ Helm Chart eck-operator не найден, устанавливаю...")    
        install_result = run_command("helm upgrade --install eck-operator ./Helm/eck-operator -n lesson4356 --wait", check=False)
        if install_result.returncode != 0:
            print("❌ Ошибка при установке Helm Chart")
            sys.exit(1)
        else:
            print("✅ Helm Chart eck-operator установлен")
    

def helm_eck_stack():
    # Загрузка  Helm Chart - eck-stack
    eck_stack = run_command("kubectl get pods -n lesson4356 -o wide", check=False)
    if "eck-stack-eck-kibana" in eck_stack.stdout.lower():
        print("✅Helm eck-stack установлен")
    else:
        print("ℹ️ Helm Chart eck-stack не найден, устанавливаю...")
        install_result = run_command("helm upgrade --install eck-stack ./Helm/eck-stack -n lesson4356 --wait", check=False)
        if install_result.returncode != 0:
            print("❌ Ошибка при установке Helm Chart")
            sys.exit(1)
        else:
            print("✅ Helm Chart eck-stack установлен")

def helm_kube_prometheus_stack():
    # Загрузка  Helm Chart kube_prometheus_stack 
    kube_prometheus_stack = run_command("kubectl get pods -n lesson4356 -o wide", check=False)
    if "kube-prometheus-stack-kube-state-metrics" in kube_prometheus_stack.stdout.lower():
        print("✅Helm kube_prometheus_stack установлен")  
    else:
        print("ℹ️ Helm Chart kube_prometheus_stack не найден, устанавливаю...")
        install_result = run_command("helm upgrade --install kube-prometheus-stack ./Helm/kube-prometheus-stack -n lesson4356 --wait", check=False)
        if install_result.returncode != 0:
            print("❌ Ошибка при установке Helm Chart")
            sys.exit(1)
        else:
            print("✅ Helm Chart kube_prometheus_stack установлен")

def helm_argo_rollouts():
    # Загрузка  Helm Chart - argo_rollouts 
    argo_rollouts = run_command("kubectl get pods -n lesson4356 -o wide", check=False)
    if "argo-rollouts" in argo_rollouts.stdout.lower():
        print("✅Helm argo_rollouts установлен")
    else:
        print("ℹ️ Helm Chart argo_rollouts не найден, устанавливаю...")
        install_result = run_command("helm upgrade --install argo-rollouts ./Helm/argo-rollouts -n lesson4356 --wait", check=False)
        if install_result.returncode != 0:
            print("❌ Ошибка при установке Helm Chart argo_rollouts")
            sys.exit(1)
        else:
            print("✅ Helm Chart argo_rollouts установлен")

def helm_argo_cd():
    # Загрузка  Helm Chart - argo_cd 

    argo_cd = run_command("kubectl get pods -n argo-cd -o wide", check=False)
    if "argo-cd" in argo_cd.stdout.lower():
        print("✅Helm argo_cd установлен")
    else:
        print("ℹ️ Helm Chart argo_cd не найден, устанавливаю...")
        install_result = run_command("helm upgrade --install argo-cd ./Helm/argo-cd -n argo-cd --wait", check=False)
        if install_result.returncode != 0:
            print("❌ Ошибка при установке Helm Chart argo_cd")
            sys.exit(1)
        else:
            print("✅ Helm Chart argo_cd установлен")

def helm_grafana():
    # Загрузка Helm Chart -  grafana
    grafana = run_command("kubectl get pods -n lesson4356 -o wide", check=False)
    if "grafana" in grafana.stdout.lower():
        print("✅Helm grafana установлен")
    else:
        print("ℹ️ Helm Chart grafana не найден, устанавливаю...")
        install_result = run_command("helm upgrade --install grafana ./Helm/grafana -n lesson4356 --wait", check=False)
        if install_result.returncode != 0:
            print("❌ Ошибка при установке Helm Chart grafana")
            sys.exit(1)
        else:
            print("✅ Helm Chart grafana установлен")

def helm_users():
    # Загрузка Helm Chart -  service
    service = run_command("kubectl get pods -n lesson4356 -o wide", check=False)
    if "users" in service.stdout.lower():
        print("✅Helm users-service установлен")
    else:
        print("ℹ️ Helm Chart users не найден, устанавливаю...")
        install_result = run_command("helm upgrade --install users ./Helm/python-service-chart -f ./Helm/values/users-service.yaml -n lesson4356 --wait", check=False)
        if install_result.returncode != 0:
            print("❌ Ошибка при установке Helm Chart users")
            sys.exit(1)
        else:
            print("✅ Helm Chart users установлен")

def helm_reviews():
    # Загрузка Helm Chart -  service
    service = run_command("kubectl get pods -n lesson4356 -o wide", check=False)
    if "reviews" in service.stdout.lower():
        print("✅Helm reviews-service установлен")
    else:
        print("ℹ️ Helm Chart reviews не найден, устанавливаю...")
        install_result = run_command("helm upgrade --install reviews ./Helm/python-service-chart -f ./Helm/values/reviews-service.yaml -n lesson4356 --wait", check=False)

        if install_result.returncode != 0:
            print("❌ Ошибка при установке Helm Chart reviews")
            sys.exit(1)
        else:
            print("✅ Helm Chart reviews установлен")
            
            



def helm_products():
    # Загрузка Helm Chart -  service
    service = run_command("kubectl get pods -n lesson4356 -o wide", check=False)
    if "products" in service.stdout.lower():
        print("✅Helm products-service установлен")
    else:
        print("ℹ️ Helm Chart products не найден, устанавливаю...")
        install_result = run_command("helm upgrade --install products ./Helm/python-service-chart -f ./Helm/values/products-service.yaml -n lesson4356 --wait", check=False)
        if install_result.returncode != 0:
            print("❌ Ошибка при установке Helm Chart products")
            sys.exit(1)
        else:
            print("✅ Helm Chart products установлен")   

def helm_orders():
    # Загрузка Helm Chart -  service
    service = run_command("kubectl get pods -n lesson4356 -o wide", check=False)
    if "orders" in service.stdout.lower():
        print("✅Helm orders-service установлен")
    else:
        print("ℹ️ Helm Chart orders не найден, устанавливаю...")
        install_result = run_command("helm upgrade --install orders ./Helm/python-service-chart -f ./Helm/values/orders-service.yaml -n lesson4356 --wait", check=False)
        if install_result.returncode != 0:
            print("❌ Ошибка при установке Helm Chart orders")
            sys.exit(1)
        else:
            print("✅ Helm Chart orders установлен")
            
def helm_frontend():
    # Загрузка Helm Chart -  service
    service = run_command("kubectl get pods -n lesson4356 -o wide", check=False)
    if "frontend" in service.stdout.lower():
        print("✅Helm frontend-service установлен")
    else:
        print("ℹ️ Helm Chart frontend не найден, устанавливаю...")
        install_result = run_command("helm upgrade --install frontend ./Helm/frontend-service-rollout -n lesson4356 --wait", check=False)
        if install_result.returncode != 0:
            print("❌ Ошибка при установке Helm Chart frontend")
            sys.exit(1)
        else:
            print("✅ Helm Chart frontend установлен")   

def check():
    # Проверка, что все сервисы работают
    service = run_command("kubectl get pods -n lesson4356 -o wide", check=False)
    if "frontend" in service.stdout.lower():
        print("✅Helm frontend-service установлен")
    else:
        print("❌ Helm Chart frontend не найден")

    if "orders" in service.stdout.lower():
        print("✅Helm orders-service установлен")
    else:
        print("❌ Helm Chart orders не найден")

    if "products" in service.stdout.lower():
        print("✅Helm products-service установлен")
    else:
        print("❌ Helm Chart products не найден")
                    
def service_ls():
    """Получить список сервисов из Helm values"""
    ls = os.listdir('./Helm/values')
    return ls

def argocd_apps(servic_ls):
    """Установить существующие ArgoCD приложения из ./argocd-apps"""
    print("\n🔍Установка ArgoCD приложений...")
    
    # Проверяем, существует ли директория argocd-apps
    if not os.path.exists('./argocd-apps'):
        print("❌ Директория ./argocd-apps не найдена")
        return
    
    ls = os.listdir('./argocd-apps')

    for i in ls:  # i - файл приложения из ./argocd-apps
        for j in servic_ls:  # j - файл сервиса из ./Helm/values
            
            # Проверяем совпадение имен
            if j.split(".")[0] + "-application" in i.split(".")[0]:
                app_name = j.split(".")[0] + "-application"
                print(f"\n📦 Найден: {app_name} ({i})")
                
                # 1. Сначала проверяем, установлено ли уже приложение
                check_cmd = f"kubectl get applications {app_name} -n argo-cd"
                check_result = run_command(check_cmd, check=False)
                
                # Если приложение найдено (код возврата 0 = успех)
                if check_result.returncode == 0:
                    print(f"   ✅ Приложение {app_name} уже установлено в кластере")
                    break  # переходим к следующему файлу приложения
                
                # 2. Если не установлено - устанавливаем
                apply_cmd = f"kubectl apply -f ./argocd-apps/{i} -n argo-cd"
                print(f"   🚀 Команда: {apply_cmd}")
                print("   ⏳ Устанавливаю...")
                
                apply_result = run_command(apply_cmd, check=False)
                
                # Проверяем результат установки
                if apply_result.returncode == 0:
                    print(f"   ✅ Приложение {app_name} успешно установлено!")
                else:
                    print(f"   ❌ Ошибка при установке {app_name}:")
                    


def main():
      """Основная функция"""
      print("\n🔍 Проверяю зависимости...")
      check_prerequisites()
      print("\n🔍Проверка namespace lesson4356...")
      helm_namespace()
      print("\n🔍Установка Helm Chart - prometheus_node_exporter...")
      helm_prometheus_node_exporter()
      print("\n🔍Установка Helm Chart - postgres...")
      helm_postgres()
      print("\n🔍Установка Helm Chart - eck-operator...")
      helm_eck_operator()
      print("\n🔍Установка Helm Chart - eck-stack...")
      helm_eck_stack()
      print("\n🔍Установка Helm Chart - grafana...")
      helm_grafana()
      print("\n🔍Установка Helm Chart - kube_prometheus_stack...")
      helm_kube_prometheus_stack()
      print("\n🔍Установка Helm Chart - argo_rollouts...")
      helm_argo_rollouts()
      print("\n🔍Установка Helm Chart - argo_cd...")
      helm_argo_cd()
      print("\n🔍Установка Helm Chart - users...")
      helm_users()
      print("\n🔍Установка Helm Chart - reviews...")
      helm_reviews()
      print("\n🔍Установка Helm Chart - products...")
      helm_products()
      print("\n🔍Установка Helm Chart - orders...")
      helm_orders()
      print("\n🔍Установка Helm Chart - frontend...")
      helm_frontend()
      print("\n🔍Проверка...")
      check()
      print("\n🔍Установка ArgoCD приложений...")
      argocd_apps(service_ls())





if __name__ == "__main__":
    main()