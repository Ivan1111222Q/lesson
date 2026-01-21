import subprocess
import yaml
import sys
from pathlib import Path
from ruamel.yaml import YAML

def run(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Ошибка: {' '.join(cmd)}\n{result.stderr}")
        sys.exit(1)
    return result.stdout.strip()

def main():
    try:
        print("🚀 ДЕПЛОЙ")
        cfg = yaml.safe_load(open(Path(__file__).parent / "deploy_config.yaml"))
        
        name, tag, registry = cfg["image"], cfg["tag"], cfg["registry"]
        dockerfile = cfg["dockerfile_path"]
        chart = cfg["helm_chart_path"]
        values = cfg["values_file_path"]
        release = cfg.get("helm_release") or name.replace("-service", "")
        namespace = cfg["helm_namespace"]
        git_branch = cfg.get("git_branch", "lesson")
        
        # Автоинкремент версии
        print(f"🔄 Автоинкремент версии {tag}")
        if cfg.get("auto_version"):
            parts = tag.lstrip("v").split(".")
            if all(p.isdigit() for p in parts):
                parts[-1] = str(int(parts[-1]) + 1)
                tag = ".".join(parts)
                cfg["tag"] = tag
                yaml.dump(cfg, open(Path(__file__).parent / "deploy_config.yaml", "w"), default_flow_style=False)
        
        local_img = f"{name}:{tag}"
        remote_img = f"{registry}/{name}:{tag}"
        
        # Сборка и push
        print(f"📦 Сборка {local_img}")
        run(["docker", "build", "--platform", "linux/amd64", "-t", local_img, dockerfile])
        run(["docker", "tag", local_img, remote_img])
        run(["docker", "push", remote_img])
        
        # Обновление values
        print(f"📝 Обновление values {values}")
        if cfg.get("update_values"):
            y = YAML()
            y.preserve_quotes = True
            v = y.load(open(values))
            v.setdefault("image", {})["repository"] = f"{registry}/{name}"
            v["image"]["tag"] = tag
            y.dump(v, open(values, "w"))
        
        # Helm upgrade
        print(f"🚀 Helm upgrade {release}")
        run(["helm", "upgrade", "--install", release, chart, "-f", values, "-n", namespace])
        
        # Git push
        print(f"📝 Git push в ветку {git_branch}")
        repo = Path(__file__).parent
        while repo != repo.parent and not (repo / ".git").exists():
            repo = repo.parent
        if (repo / ".git").exists():
            if subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True).stdout:
                run(["git", "add", "-A"], cwd=repo)
                run(["git", "commit", "-m", f"Deploy {name}:{tag}"], cwd=repo)
            run(["git", "push", "origin", git_branch], cwd=repo)
        print(f"✅ Git push готов в ветку {git_branch}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)        
        
        print(f"✅ Готово: {remote_img}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
