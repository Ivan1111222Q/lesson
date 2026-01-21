import subprocess
import json
import yaml
import os
import sys
from pathlib import Path
from ruamel.yaml import YAML


def run(cmd, cwd=None, check=True):
    """Выполняет команду с улучшенной обработкой ошибок"""
    print(f"\n>>> RUN: {' '.join(cmd)}")
    if cwd:
        print(f"    (cwd={cwd})")
    
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    
    if result.returncode != 0 and check:
        print(f"❌ ОШИБКА при выполнении команды:")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        raise RuntimeError(f"Команда завершилась с кодом {result.returncode}: {' '.join(cmd)}")
    
    return result.stdout.strip()


def check_dependencies():
    """Проверяет наличие необходимых инструментов"""
    tools = ['docker', 'helm']
    for tool in tools:
        try:
            run([tool, '--version'], check=False)
        except FileNotFoundError:
            raise RuntimeError(f"❌ {tool} не найден. Установите {tool} и попробуйте снова.")


def validate_config(cfg):
    """Валидирует конфигурацию"""
    # Базовые обязательные поля
    required = ['image', 'tag', 'registry', 'dockerfile_path', 'helm_namespace', 
                'helm_chart_path', 'values_file_path']
    
    missing = [key for key in required if key not in cfg or cfg.get(key) in (None, "")]
    if missing:
        raise ValueError(f"❌ Отсутствуют обязательные поля в конфиге: {', '.join(missing)}")
    
    # Проверка путей
    dockerfile_dir = Path(cfg['dockerfile_path'])
    if not dockerfile_dir.exists():
        raise ValueError(f"❌ Путь к Dockerfile не существует: {dockerfile_dir}")
    
    helm_chart = Path(cfg['helm_chart_path'])
    if not helm_chart.exists():
        raise ValueError(f"❌ Путь к Helm chart не существует: {helm_chart}")
    
    values_file = Path(cfg['values_file_path'])
    if not values_file.exists():
        raise ValueError(f"❌ Файл values не найден: {values_file}")


def inc_version(tag):
    """Улучшенная функция инкремента версии"""
    # Убираем префикс 'v' если есть
    tag = tag.lstrip('v')
    
    # Проверяем формат версии (например, 2.10, 2.10.0)
    parts = tag.split(".")
    
    if not all(p.isdigit() for p in parts):
        print(f"⚠️  Версия '{tag}' не в числовом формате, пропускаем автоинкремент")
        return tag
    
    # Инкрементируем последнюю часть
    parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def get_image_architecture(image):
    """Получает архитектуру образа"""
    try:
        arch = run(["docker", "inspect", "--format", "{{.Architecture}}", image])
        return arch.strip()
    except RuntimeError:
        # Fallback на JSON парсинг
        info = run(["docker", "inspect", image])
        data = json.loads(info)
        return data[0]["Architecture"]


def main():
    try:
        print("=" * 50)
        print("🚀 НАЧАЛО ДЕПЛОЯ")
        print("=" * 50)
        
        # Проверка зависимостей
        print("\n=== ПРОВЕРКА ЗАВИСИМОСТЕЙ ===")
        check_dependencies()
        print("✅ Все зависимости установлены")
        
        # Чтение конфига
        config_path = Path(__file__).parent / "deploy_config.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"❌ Файл конфигурации не найден: {config_path}")
        
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)
        
        # Валидация
        validate_config(cfg)
        print("✅ Конфигурация валидна")
        
        # Извлечение параметров
        name = cfg["image"]
        tag = cfg["tag"]
        registry = cfg["registry"]
        dockerhub = cfg.get("dockerhub")
        dockerfile_path = cfg["dockerfile_path"]
        helm_chart_path = cfg["helm_chart_path"]
        values_file_path = cfg["values_file_path"]
        release = cfg.get("helm_release") or name.replace("-service", "")  # Если не указан, берем имя без -service
        namespace = cfg["helm_namespace"]
        auto_version = cfg.get("auto_version", False)
        update_values = cfg.get("update_values", False)
        git_branch = cfg.get("git_branch", "lesson")  # Ветка для git push (по умолчанию "lesson")
        
        # Автоинкремент версии
        if auto_version:
            new_tag = inc_version(tag)
            print(f"\n📦 Авто-версия: {tag} → {new_tag}")
            tag = new_tag
            cfg["tag"] = new_tag
            
            # Сохраняем обновленный конфиг
            with open(config_path, "w") as f:
                yaml.dump(cfg, f, default_flow_style=False)
        
        local_image = f"{name}:{tag}"
        yandex_image = f"{registry}/{name}:{tag}"
        dockerhub_image = f"{dockerhub}/{name}:{tag}" if dockerhub else None
        
        # Сборка образа
        print("\n=== СБОРКА ОБРАЗА ===")
        run(["docker", "build", "-t", local_image, dockerfile_path])
        print(f"✅ Образ собран: {local_image}")
        
        # Проверка архитектуры
        print("\n=== ПРОВЕРКА АРХИТЕКТУРЫ ===")
        arch = get_image_architecture(local_image)
        print(f"Архитектура: {arch}")
        
        if arch != "amd64":
            print("⚠️  Архитектура != amd64 → пересобираем под linux/amd64")
            run([
                "docker", "build",
                "--platform", "linux/amd64",
                "-t", local_image,
                dockerfile_path
            ])
            print("✅ Образ пересобран под amd64")
        
        # Push в Yandex Registry
        print("\n=== PUSH В YANDEX REGISTRY ===")
        run(["docker", "tag", local_image, yandex_image])
        run(["docker", "push", yandex_image])
        print(f"✅ Образ запушен: {yandex_image}")
        
        # Push в DockerHub (если указан)
        if dockerhub_image:
            print("\n=== PUSH В DOCKER HUB ===")
            run(["docker", "tag", local_image, dockerhub_image])
            run(["docker", "push", dockerhub_image])
            print(f"✅ Образ запушен: {dockerhub_image}")
        
        # Обновление values файла (если включено)
        if update_values:
            print("\n=== ОБНОВЛЕНИЕ values ФАЙЛА ===")
            yaml_ruamel = YAML()
            yaml_ruamel.preserve_quotes = True
            yaml_ruamel.default_flow_style = False
            
            values_path = Path(values_file_path)
            
            with open(values_path, "r") as f:
                values = yaml_ruamel.load(f)
            
            # Обновляем только repository и tag
            if 'image' not in values or not isinstance(values['image'], dict):
                values['image'] = {}
            
            values['image']['repository'] = f"{registry}/{name}"
            values['image']['tag'] = str(tag)
            
            with open(values_path, "w") as f:
                yaml_ruamel.dump(values, f)
            
            print(f"✅ Values файл обновлен: repository={values['image']['repository']}, tag={values['image']['tag']}")

        # Helm upgrade
        print("\n=== HELM UPGRADE ===")
        run([
            "helm", "upgrade", "--install",
            release,
            helm_chart_path,
            "-f", values_file_path,
            "-n", namespace
        ])
        print(f"✅ Helm upgrade выполнен: {release} в namespace {namespace}")
        
        print("\n" + "=" * 50)
        print("✅ ДЕПЛОЙ УСПЕШНО ЗАВЕРШЕН")
        print("=" * 50)
        print(f"📦 Образ: {yandex_image}")
        print(f"🚀 Release: {release}")
        print(f"📁 Namespace: {namespace}")
        
        # Git push после успешного деплоя
        print("\n=== GIT PUSH ===")
        try:
            # Определяем корень git репозитория
            script_dir = Path(__file__).parent.absolute()
            repo_root = script_dir
            # Ищем .git директорию, поднимаясь вверх по дереву
            while repo_root != repo_root.parent:
                if (repo_root / ".git").exists():
                    break
                repo_root = repo_root.parent
            else:
                print("⚠️  Git репозиторий не найден, пропускаем git push")
                return
            
            # Проверяем, есть ли изменения для коммита
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )
            
            if status_result.stdout.strip():
                print("📝 Обнаружены изменения в репозитории")
                # Добавляем все изменения
                run(["git", "add", "-A"], cwd=repo_root)
                # Коммитим изменения
                commit_message = f"Deploy {name}:{tag}"
                run(["git", "commit", "-m", commit_message], cwd=repo_root)
                print(f"✅ Изменения закоммичены: {commit_message}")
            else:
                print("ℹ️  Нет изменений для коммита")
            
            # Push в указанную ветку
            run(["git", "push", "origin", git_branch], cwd=repo_root)
            print(f"✅ Изменения запушены в origin/{git_branch}")
        except RuntimeError as git_error:
            print(f"⚠️  Ошибка при выполнении git push: {git_error}")
            print("⚠️  Деплой завершен успешно, но git push не выполнен")
        except Exception as git_error:
            print(f"⚠️  Непредвиденная ошибка при git push: {git_error}")
            print("⚠️  Деплой завершен успешно, но git push не выполнен")
        
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        print(f"\n❌ ОШИБКА: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Деплой прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ НЕПРЕДВИДЕННАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

