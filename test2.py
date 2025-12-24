
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



def helm_chart():
    """Получить папки чартов, исключая chart которые не нужно устанавливать"""
    exclude_folders = ['gitlab']
    
    all_items = os.listdir('./Helm')
    
    # Фильтруем: только папки И не в списке исключений
    filtered_folders = [
        item for item in all_items
        if os.path.isdir(os.path.join('./Helm', item)) 
        and item not in exclude_folders
    ]
    
    return filtered_folders

def helm_command(chart_folders, service_files):
    """Установить Helm charts из папок"""

    for folder in chart_folders:
        print(f"\n📦 Обрабатываю chart: {folder}")

        chart_path = f"./Helm/{folder}"
        chart_yaml = os.path.join(chart_path, 'Chart.yaml')
        
        if not os.path.exists(chart_yaml):
            print(f"   ✅ Chart.yaml не найден в {chart_path}")
            continue  # Пропускаем эту папку

        if folder == 'argo-cd':
            namespace = 'argo-cd'
        else:
            namespace = 'lesson4356'

        if folder == 'python-service-chart':
            chart = 'python-service-chart'
            print(f"   🔄 Устанавливаю {chart} для всех сервисов")
            
            for service_file in service_files:  # "orders-service.yaml", "users-service.yaml", etc.
                service_name = service_file.split(".")[0].split("-")[0]  # "orders-service", "users-service"
                
                # ⚠️ ВАЖНО: Создаем УНИКАЛЬНОЕ имя релиза!
                release_name = f"{service_name}"  # или "python-{service_name}"
                # Для 4 сервисов получим:
                # 1. orders-service
                # 2. users-service  
                # 3. products-service
                # 4. reviews-service
                
                print(f"\n   📁 Сервис: {service_name}")
                print(f"   🚀 Имя релиза: {release_name}")
                
                # Проверяем, установлен ли уже ЭТОТ релиз
                check_cmd = f"helm list -n {namespace} -q"
                check_result = run_command(check_cmd, check=False)
                
                # Получаем список всех установленных релизов
                installed_releases = []
                if check_result.returncode == 0 and check_result.stdout:
                    installed_releases = [r.strip() for r in check_result.stdout.split('\n') if r.strip()]
                
                if release_name in installed_releases:
                    print(f"   ✅ Релиз '{release_name}' уже установлен")
                    continue
                
            
                checp_cmd = f"helm upgrade --install {release_name} ./Helm/{chart} -f ./Helm/values/{service_file} -n lesson4356 --wait"
                check_checp = run_command(checp_cmd, check=False)

                if check_checp.returncode == 0:
                    print(f"   ✅ Релиз {release_name} успешно установлен!")
                else:
                    print(f"   ❌ Ошибка при установке {release_name}:")
            continue            

        # 1. Проверяем, установлен ли уже релиз
        # Используем более надежную проверку через helm list
        check_cmd = f"helm list -n {namespace} -q"
        check_result = run_command(check_cmd, check=False)

        # Проверяем, есть ли релиз в списке установленных
        if check_result.returncode == 0 and folder in check_result.stdout:
            print(f"   ✅ Релиз {folder} уже установлен в кластере")
            continue
        else:
            print(f"   ℹ️  Релиз {folder} не найден, устанавливаю...")

        # 2. Если релиз не найден, устанавливаем его
        cmd = f"helm upgrade --install {folder} ./Helm/{folder} -n {namespace} --wait"
        apply_result = run_command(cmd, check=False)

        # Проверяем результат установки по коду возврата
        if apply_result.returncode == 0:
            print(f"   ✅ Релиз {folder} успешно установлен!")
        else:
            print(f"   ❌ Ошибка при установке {folder}:")
            print(f"   {apply_result.stderr}")
           
     



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
    print("\n🔍Установка Helm чартов...")
    helm_command(helm_chart(),service_ls())
    print("\n🔍Установка ArgoCD приложений...")
    argocd_apps(service_ls())
    





if __name__ == "__main__":
    main()