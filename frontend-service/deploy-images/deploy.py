import subprocess
import json
import yaml
import os


def run(cmd, cwd=None):
    print(f"\n>>> RUN: {' '.join(cmd)} (cwd={cwd})")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError(f"Ошибка: {' '.join(cmd)}")
    return result.stdout.strip()


def inc_version(tag):
    if not tag.replace(".", "").isdigit():
        return tag
    p = tag.split(".")
    p[-1] = str(int(p[-1]) + 1)
    return ".".join(p)


# === 1. Читаем конфиг ===
with open("deploy_config.yaml", "r") as f:
    cfg = yaml.safe_load(f)

name = cfg["image"]
tag = cfg["tag"]
registry = cfg["registry"]
dockerhub = cfg.get("dockerhub")
dockerfile_path = cfg["dockerfile_path"]
helm_chart_path = cfg["helm_chart_path"]
release = cfg["helm_release"]
namespace = cfg["helm_namespace"]
auto_version = cfg.get("auto_version", False)
update_values = cfg.get("update_values", False)

# AUTO VERSION
if auto_version:
    new_tag = inc_version(tag)
    print(f"\nАвто-версия: {tag} → {new_tag}")
    tag = new_tag
    cfg["tag"] = new_tag

    # сохраняем обратно
    with open("deploy_config.yaml", "w") as f:
        yaml.dump(cfg, f)

local_image = f"{name}:{tag}"
yandex_image = f"{registry}/{name}:{tag}"
dockerhub_image = f"{dockerhub}:{tag}" if dockerhub else None

print("\n=== СБОРКА ОБРАЗА ===")
run(["docker", "build", "-t", local_image, dockerfile_path])

print("\n=== ПРОВЕРКА АРХИТЕКТУРЫ ===")
info = run(["docker", "inspect", local_image])
arch = json.loads(info)[0]["Architecture"]

if arch != "amd64":
    print("Архитектура != amd64 → пересобираем")
    run([
        "docker", "build",
        "--platform", "linux/amd64",
        "-t", local_image,
        dockerfile_path
    ])

print("\n=== PUSH В YANDEX ===")
run(["docker", "tag", local_image, yandex_image])
run(["docker", "push", yandex_image])

if dockerhub_image:
    print("\n=== PUSH В DOCKER HUB ===")
    run(["docker", "tag", local_image, dockerhub_image])
    run(["docker", "push", dockerhub_image])

# === ОБНОВЛЕНИЕ values.yaml ===
if update_values:
    print("\n=== ОБНОВЛЯЮ values.yaml ===")
    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.preserve_quotes = True

    values_path = os.path.join(helm_chart_path, "values.yaml")

    with open(values_path, "r") as f:
        values = yaml.load(f)

    # Меняем только repository и tag
    if 'image' not in values or not isinstance(values['image'], dict):
        values['image'] = {}
    values['image']['repository'] = f"{registry}/{name}"
    values['image']['tag'] = str(tag)

    with open(values_path, "w") as f:
        yaml.dump(values, f)

print("\n=== HELM UPGRADE ===")
run([
    "helm", "upgrade",
    release,
    helm_chart_path,
    "-n",
    namespace
])

print("\n========================")
print("  ДЕПЛОЙ ГОТОВ ✔️")
print("========================")
print(f"Образ: {yandex_image}")
