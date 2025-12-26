
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
                    
                    # Вариант 1: Попробовать откатить к предыдущей версии
                    print(f"   🔄 Пытаюсь откатить rollout...")
                    rollback_cmd = f"kubectl argo rollouts undo {rollout_name} -n {namespace}"
                    rollback_result = run_command(rollback_cmd, check=False)
                    
                    if rollback_result.returncode == 0:
                        print(f"   ✅ Откат запущен")
                        
                        # Ждем немного и проверяем статус
                        print(f"   ⏳ Жду 30 секунд...")
                        import time
                        time.sleep(30)
                        
                        # Проверяем стал ли rollout здоровым
                        check_after_cmd = f"kubectl get rollout {rollout_name} -n {namespace} -o jsonpath='{{.status.phase}}' 2>/dev/null"
                        check_after = run_command(check_after_cmd, check=False)
                        
                        if check_after.returncode == 0 and check_after.stdout.strip() == "Healthy":
                            print(f"   ✅ Rollout восстановлен после отката")
                            fixed_count += 1
                        else:
                            print(f"   ⚠️  Откат не помог, пробую рестарт...")
                            # Вариант 2: Полный рестарт
                            restart_cmd = f"kubectl rollout restart rollout/{rollout_name} -n {namespace}"
                            restart_result = run_command(restart_cmd, check=False)
                            
                            if restart_result.returncode == 0:
                                print(f"   ✅ Рестарт запущен")
                                time.sleep(30)  # Ждем
                                fixed_count += 1
                            else:
                                print(f"   ❌ Не удалось рестартнуть")
                                failed_count += 1
                    else:
                        print(f"   ❌ Не удалось откатить: {rollback_result.stderr[:200]}")
                        failed_count += 1
                
                # Случай 3: В процессе обновления - просто ждем
                elif status == "Progressing":
                    print(f"   ⏳ В процессе обновления, жду 1 минуту...")
                    import time
                    time.sleep(60)
                    
                    # Проверяем еще раз
                    recheck_cmd = f"kubectl get rollout {rollout_name} -n {namespace} -o jsonpath='{{.status.phase}}' 2>/dev/null"
                    recheck = run_command(recheck_cmd, check=False)
                    
                    if recheck.returncode == 0 and recheck.stdout.strip() == "Healthy":
                        print(f"   ✅ Теперь здоров после ожидания")
                        healthy_count += 1
                    else:
                        print(f"   ⚠️  Все еще не здоров, пытаюсь откатить...")
                        # Пробуем откатить
                        undo_cmd = f"kubectl argo rollouts undo {rollout_name} -n {namespace}"
                        run_command(undo_cmd, check=False)
                        fixed_count += 1
            
            else:
                print(f"   ❌ Не удалось получить информацию о репликах")
                failed_count += 1
        
        else:
            # Rollout не найден или ошибка
            print(f"   ❌ Rollout не найден или ошибка доступа")
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