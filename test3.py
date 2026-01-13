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




def helm_chart():
    """Получить папки чартов, исключая chart которые не нужно устанавливать"""
    exclude_folders = ['gitlab', 'python-service-chart', 'values', 'argo-cd']
    
    all_items = os.listdir('./Helm')
    
    # Фильтруем: только папки И не в списке исключений
    filtered_folders = [
        item for item in all_items
        if os.path.isdir(os.path.join('./Helm', item)) 
        and item not in exclude_folders
    ]
    
    return filtered_folders

def helm_command(chart_folders):
    """Установить Helm charts из папок"""

    for folder in chart_folders:
        print(f"\n📦 Обрабатываю chart: {folder}")


        # 1. Проверяем, установлен ли уже релиз
        # Ищем релиз по имени (предполагаем, что имя релиза = имя папки)
        check_cmd = f"helm list -n lesson4356 --filter '^{folder}$'"
        check_result = run_command(check_cmd, check=False)

        if folder in check_result.stdout:
                print(f"   ✅ Релиз {folder} уже установлен в кластере")
                continue
        else:
                print(f"   ❌ Релиз не найдет {folder}:")

                

        #Если релиз не найден, устанавливаем его
        cmd = f"helm upgrade --install {folder} ./Helm/{folder} -n lesson4356 --wait --atomic"
        print("   ⏳ Устанавливаю...")

        apply_result = run_command(cmd, check=False)

        if folder in apply_result.stdout:
                print(f"   ✅ Релиз {folder} успешно установлен!")
                continue
                
        else:
                print(f"   ❌ Ошибка при установке {folder}:")








        
helm_command(helm_chart())



