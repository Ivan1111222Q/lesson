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
    """Валидирует конфигурацию

    Поддерживаются два варианта:
    - обычный Helm-чарт
    - rollout-чарт
    Можно использовать один из них или оба сразу.
    """

    # Базовые обязательные поля (независимо от типа чарта)
    required = ['image', 'tag', 'registry', 'dockerfile_path', 'helm_namespace']

    missing = [key for key in required if key not in cfg or cfg.get(key) in (None, "")]
    if missing:
        raise ValueError(f"❌ Отсутствуют обязательные поля в конфиге: {', '.join(missing)}")

    # Проверка путей
    dockerfile_dir = Path(cfg['dockerfile_path'])
    if not dockerfile_dir.exists():
        raise ValueError(f"❌ Путь к Dockerfile не существует: {dockerfile_dir}")
    
    # Обычный Helm-чарт (опционально)
    helm_chart_path = cfg.get('helm_chart_path')
    helm_release = cfg.get('helm_release')
    if helm_chart_path or helm_release:
        if not helm_chart_path or not helm_release:
            raise ValueError("❌ Для работы с основным Helm chart необходимо указать оба поля: "
                             "`helm_chart_path` и `helm_release`")

        helm_chart = Path(helm_chart_path)
        if not helm_chart.exists():
            raise ValueError(f"❌ Путь к Helm chart не существует: {helm_chart}")

        values_path = helm_chart / "values.yaml"
        if not values_path.exists():
            raise ValueError(f"❌ Файл values.yaml не найден: {values_path}")

    # Rollout-чарт (опционально)
    rollout_chart_path = cfg.get("rollout_helm_chart_path")
    rollout_release = cfg.get("rollout_helm_release")
    if rollout_chart_path or rollout_release:
        if not rollout_chart_path or not rollout_release:
            raise ValueError("❌ Для работы с rollout-чартом необходимо указать оба поля: "
                             "`rollout_helm_chart_path` и `rollout_helm_release`")

        rollout_chart = Path(rollout_chart_path)
        if not rollout_chart.exists():
            raise ValueError(f"❌ Путь к rollout Helm chart не существует: {rollout_chart}")

        rollout_values_path = rollout_chart / "values.yaml"
        if not rollout_values_path.exists():
            raise ValueError(f"❌ Файл values.yaml не найден у rollout-чарта: {rollout_values_path}")

    # Umbrella-чарт для сервисов (опционально)
    services_umbrella_chart_path = cfg.get("services_umbrella_chart_path")
    services_umbrella_release = cfg.get("services_umbrella_release")
    if services_umbrella_chart_path or services_umbrella_release:
        if not services_umbrella_chart_path or not services_umbrella_release:
            raise ValueError("❌ Для работы с umbrella-чартом необходимо указать оба поля: "
                             "`services_umbrella_chart_path` и `services_umbrella_release`")

        umbrella_chart = Path(services_umbrella_chart_path)
        if not umbrella_chart.exists():
            raise ValueError(f"❌ Путь к umbrella Helm chart не существует: {umbrella_chart}")


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
        helm_chart_path = cfg.get("helm_chart_path")
        release = cfg.get("helm_release")
        namespace = cfg["helm_namespace"]
        auto_version = cfg.get("auto_version", False)
        update_values = cfg.get("update_values", False)

        # Параметры для rollout-чарта (опционально)
        rollout_helm_chart_path = cfg.get("rollout_helm_chart_path")
        rollout_release = cfg.get("rollout_helm_release")
        rollout_namespace = cfg.get("rollout_helm_namespace", namespace)
        rollout_update_values = cfg.get("rollout_update_values", update_values)

        # Параметры для umbrella-чарта сервисов (опционально)
        services_umbrella_chart_path = cfg.get("services_umbrella_chart_path")
        services_umbrella_release = cfg.get("services_umbrella_release")
        services_umbrella_namespace = cfg.get("services_umbrella_namespace", namespace)
        
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
        
        # Обновление values.yaml основного чарта (если он сконфигурирован)
        if update_values and helm_chart_path and release:
            print("\n=== ОБНОВЛЕНИЕ values.yaml ===")
            yaml_ruamel = YAML()
            yaml_ruamel.preserve_quotes = True
            yaml_ruamel.default_flow_style = False
            
            values_path = Path(helm_chart_path) / "values.yaml"
            
            with open(values_path, "r") as f:
                values = yaml_ruamel.load(f)
            
            # Обновляем только repository и tag
            if 'image' not in values or not isinstance(values['image'], dict):
                values['image'] = {}
            
            values['image']['repository'] = f"{registry}/{name}"
            values['image']['tag'] = str(tag)
            
            with open(values_path, "w") as f:
                yaml_ruamel.dump(values, f)
            
            print(f"✅ values.yaml (основной чарт) обновлен: repository={values['image']['repository']}, tag={values['image']['tag']}")

        # Helm upgrade для основного чарта (если он сконфигурирован)
        if helm_chart_path and release:
            print("\n=== HELM UPGRADE (основной чарт) ===")
            run([
                "helm", "upgrade", "--install",
                release,
                helm_chart_path,
                "-n", namespace
            ])
            print(f"✅ Helm upgrade выполнен: {release} в namespace {namespace}")

        # Обновление rollout-чарта (если сконфигурирован)
        if rollout_helm_chart_path and rollout_release:
            # Обновление values.yaml rollout-чарта
            if rollout_update_values:
                print("\n=== ОБНОВЛЕНИЕ values.yaml (rollout-чарт) ===")
                yaml_ruamel = YAML()
                yaml_ruamel.preserve_quotes = True
                yaml_ruamel.default_flow_style = False

                rollout_values_path = Path(rollout_helm_chart_path) / "values.yaml"

                with open(rollout_values_path, "r") as f:
                    rollout_values = yaml_ruamel.load(f)

                if 'image' not in rollout_values or not isinstance(rollout_values['image'], dict):
                    rollout_values['image'] = {}

                rollout_values['image']['repository'] = f"{registry}/{name}"
                rollout_values['image']['tag'] = str(tag)

                with open(rollout_values_path, "w") as f:
                    yaml_ruamel.dump(rollout_values, f)

                print(f"✅ values.yaml (rollout-чарт) обновлен: repository={rollout_values['image']['repository']}, tag={rollout_values['image']['tag']}")

            # Helm upgrade для rollout-чарта (только если НЕТ umbrella-чарта)
            # Если есть umbrella-чарт, все сервисы управляются через него
            if not (services_umbrella_chart_path and services_umbrella_release):
                print("\n=== HELM UPGRADE (rollout-чарт) ===")
                run([
                    "helm", "upgrade", "--install",
                    rollout_release,
                    rollout_helm_chart_path,
                    "-n", rollout_namespace
                ])
                print(f"✅ Helm upgrade выполнен: {rollout_release} в namespace {rollout_namespace}")
            else:
                print("\n⚠️  Пропускаем отдельный helm upgrade для rollout-чарта (используется umbrella-чарт)")

        # Helm upgrade для umbrella-чарта сервисов (если сконфигурирован)
        if services_umbrella_chart_path and services_umbrella_release:
            print("\n=== ПОДГОТОВКА ЗАВИСИМОСТЕЙ ДЛЯ UMBRELLA-ЧАРТА СЕРВИСОВ ===")
            # Пересобираем зависимости, чтобы подтянуть обновленные локальные сабчарты
            run([
                "helm", "dependency", "build",
                services_umbrella_chart_path,
            ])

            print("\n=== HELM UPGRADE (umbrella-чарт сервисов) ===")
            run([
                "helm", "upgrade", "--install",
                services_umbrella_release,
                services_umbrella_chart_path,
                "-n", services_umbrella_namespace
            ])
            print(f"✅ Helm upgrade выполнен: {services_umbrella_release} в namespace {services_umbrella_namespace}")
        
        print("\n" + "=" * 50)
        print("✅ ДЕПЛОЙ УСПЕШНО ЗАВЕРШЕН")
        print("=" * 50)
        print(f"📦 Образ: {yandex_image}")
        print(f"🚀 Release: {release}")
        print(f"📁 Namespace: {namespace}")
        
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

