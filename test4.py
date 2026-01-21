
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
                        repo_path = "./lesson4356" 
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
    check_and_fix_rollouts()





if __name__ == "__main__":
    main()