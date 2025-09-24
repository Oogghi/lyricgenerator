import urllib.request
import os
import shutil
import zipfile

os.chdir(os.path.dirname(os.path.abspath(__file__)))

GITHUB_VERSION_URL = "https://raw.githubusercontent.com/Oogghi/lyricgenerator/main/version.txt"
GITHUB_ZIP_URL = "https://github.com/Oogghi/lyricgenerator/archive/refs/heads/main.zip"

def get_remote_version():
    try:
        with urllib.request.urlopen(GITHUB_VERSION_URL) as response:
            return response.read().decode().strip()
    except Exception as e:
        print("Erreur lors de la récupération de la version distante:", e)
        return None

def get_local_version():
    try:
        with open("version.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def download_update():
    print("[Updater] Téléchargement de la nouvelle version...")
    urllib.request.urlretrieve(GITHUB_ZIP_URL, "update.zip")
    with zipfile.ZipFile("update.zip", "r") as zip_ref:
        zip_ref.extractall("update_temp")

    extracted_folder = os.path.join("update_temp", os.listdir("update_temp")[0])

    print("[Updater] Suppression des anciens fichiers...")
    for item in os.listdir("."):
        if item not in ["update.py", "start.bat", "update.zip", "update_temp", "__pycache__"]:
            try:
                if os.path.isdir(item):
                    shutil.rmtree(item)
                else:
                    os.remove(item)
            except Exception as e:
                print(f"Erreur suppression {item}: {e}")

    print("[Updater] Copie des nouveaux fichiers...")
    for item in os.listdir(extracted_folder):
        src_path = os.path.join(extracted_folder, item)
        dst_path = os.path.join(".", item)

        if os.path.exists(dst_path) and item != "update.py":
            if os.path.isdir(dst_path):
                shutil.rmtree(dst_path)
            else:
                os.remove(dst_path)

        if item == "update.py":
            print("[Updater] Ignorer update.py pendant la copie.")
            continue

        if os.path.isdir(src_path):
            shutil.copytree(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)

    shutil.rmtree("update_temp")
    os.remove("update.zip")
    print("[Updater] Mise à jour terminée.")

    os.system("python main.py")

if __name__ == "__main__":
    print("[Updater] Vérification de la version...")
    local_version = get_local_version()
    remote_version = get_remote_version()

    if not remote_version:
        print("[Updater] Impossible de vérifier la version. Lancement du jeu.")
        os.system("python main.py")
    elif local_version == remote_version:
        print("[Updater] Version à jour.")
        os.system("python main.py")
    else:
        print(f"[Updater] Nouvelle version détectée ({remote_version}). Mise à jour...")
        download_update()
        os.system("python main.py")