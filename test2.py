
import os
import sys
import yaml
import subprocess
from pathlib import Path

argo_cd = 'argo-cd'

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

        if folder == argo_cd:
            namespace = argo_cd
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
                    print(f"   🔍 Уже установлены: {', '.join(installed_releases)}")
                
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



def check_and_fix_rollouts():
    """Проверить и автоматически исправить проблемные rollouts"""
    
    print("\n🔧 Проверка и восстановление Rollouts...")
    print("=" * 70)
    
    # 1. Получаем список всех rollouts
    cmd_list = "kubectl get rollouts -A --no-headers -o custom-columns=NAME:.metadata.name,NAMESPACE:.metadata.namespace"
    list_result = run_command(cmd_list, check=False)
    
    if list_result.returncode != 0:
        if list_result.returncode == 1:
            print("❌ Команда kubectl не смогла выполниться")
        elif list_result.returncode == 127:
            print("❌ Команда kubectl не найдена. Установите Kubernetes CLI")
        else:
            print(f"❌ Неизвестная ошибка (код: {list_result.returncode})")
            print(f"Детали: {list_result.stderr}")
            return
        
    if not list_result.stdout.strip():
            print("✅ Команда выполнена успешно, но rollouts не найдены в кластере")
            return
    
    # Разбираем список
    rollouts = []
    for line in list_result.stdout.strip().split('\n'):
        if line.strip():
            parts = line.strip().split()
            if len(parts) >= 2:
                rollout_name = parts[0]
                namespace = parts[1]
                rollouts.append((rollout_name, namespace))
    
    print(f"📊 Найдено {len(rollouts)} rollout(s)")
    print("-" * 70)
    
    # Статистика
    healthy_count = 0
    fixed_count = 0
    failed_count = 0
    
    # 2. Проверяем каждый rollout
    for rollout_name, namespace in rollouts:
        print(f"\n📦 Rollout: {rollout_name}")
        print(f"   Namespace: {namespace}")
        
        # Проверяем текущий статус
        status_cmd = f"kubectl get rollout {rollout_name} -n {namespace} -o jsonpath='{{.status.phase}}' 2>/dev/null"
        status_result = run_command(status_cmd, check=False)
        
        if status_result.returncode == 0:
            status = status_result.stdout.strip()
            print(f"   Текущий статус: {status}")
            
            # Проверяем реплики
            replicas_cmd = f"kubectl get rollout {rollout_name} -n {namespace} -o jsonpath='{{.status.readyReplicas}}/{{.status.replicas}}' 2>/dev/null"
            replicas_result = run_command(replicas_cmd, check=False)
            
            if replicas_result.returncode == 0:
                ready, total = replicas_result.stdout.strip().split('/')
                print(f"   Реплики: {ready}/{total}")
                
                # ===== ЛОГИКА ВОССТАНОВЛЕНИЯ =====
                
                # Случай 1: Rollout здоров
                if status == "Healthy" and ready == total:
                    print(f"   ✅ Здоров, ничего не делаю")
                    healthy_count += 1
                
                # Случай 2: Rollout деградировал или не все реплики готовы
                elif status == "Degraded" or ready != total:
                    print(f"   ⚠️  Проблема обнаружена!")
                    
                    try:
                        # 1. Путь к вашему репозиторию (укажите ваш путь)
                        repo_path = os.path.abspath("LESSON4356")
                        import os
                        original_dir = os.getcwd()
                        os.chdir(repo_path)

                        # 2. Делаем отмену последнего коммита (именно он привел к ошибке)
                        revert_cmd = "git revert HEAD --no-edit"
                        revert_res = run_command(revert_cmd, check=False)
                        
                        if revert_res.returncode == 0:
                            # 3. Пушим изменения. Argo CD увидит новый коммит и сам откатит все 5 сервисов
                            push_res = run_command("git push origin argocd", check=False)
                            
                            if push_res.returncode == 0:
                                print(f"   ✅ Git Revert выполнен и отправлен в репозиторий.")
                                print(f"   🚀 Argo CD начал автоматическое восстановление всех сервисов.")
                                fixed_count = len(rollouts) 
                                os.chdir(original_dir)
                                break # Прерываем цикл, так как мы откатили сразу весь стек
                            else:
                                print(f"   ❌ Ошибка git push: {push_res.stderr}")
                        else:
                            print(f"   ❌ Ошибка git revert: {revert_res.stderr}")
                        
                        os.chdir(original_dir)
                    except Exception as e:
                        print(f"   ❌ Ошибка при работе с Git: {e}")
                    
                    failed_count += 1
    
    # 3. Итоговая статистика
    print("\n" + "=" * 70)
    print("📊 ИТОГ ВОССТАНОВЛЕНИЯ ROLLOUTS:")
    print(f"   ✅ Здоровые: {healthy_count}")
    print(f"   🔄 Исправлено: {fixed_count}")
    print(f"   ❌ Не удалось исправить: {failed_count}")
    print(f"   📊 Всего обработано: {len(rollouts)}")
    print("=" * 70)


def main():
    print("\n🔍Установка Helm чартов...")
    helm_command(helm_chart(),service_ls())
    print("\n🔍Установка ArgoCD приложений...")
    argocd_apps(service_ls())
    print("\n🔍Проверка rollouts...")
    check_and_fix_rollouts()
    




if __name__ == "__main__":
    main()