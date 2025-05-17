import os
import shutil

# Pfade zu deinen Vorlagen
TEMPLATE_DOCKERFILE = "docker/function.Dockerfile"
TEMPLATE_REQUIREMENTS = "docker/requirements.txt"

# Basisordner mit deinen Funktionen
BASE_DIR = "functions/webshop"

def apply_templates_to_function(func_path):
    docker_target = os.path.join(func_path, "Dockerfile")
    requirements_target = os.path.join(func_path, "requirements.txt")

    if not os.path.exists(docker_target):
        shutil.copyfile(TEMPLATE_DOCKERFILE, docker_target)
        print(f"✅ Dockerfile hinzugefügt: {docker_target}")

    if not os.path.exists(requirements_target):
        shutil.copyfile(TEMPLATE_REQUIREMENTS, requirements_target)
        print(f"✅ requirements.txt hinzugefügt: {requirements_target}")

def main():
    for name in os.listdir(BASE_DIR):
        path = os.path.join(BASE_DIR, name)
        if os.path.isdir(path):
            apply_templates_to_function(path)

if __name__ == "__main__":
    main()
