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

    print("[Updater] Copie/merge des nouveaux fichiers...")
    for root, dirs, files in os.walk(extracted_folder):
        rel_path = os.path.relpath(root, extracted_folder)
        dest_dir = os.path.join(".", rel_path) if rel_path != "." else "."

        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        for file in files:
            if file == "update.py":
                print("[Updater] Ignorer update.py pendant la copie.")
                continue

            src_file = os.path.join(root, file)
            dst_file = os.path.join(dest_dir, file)

            try:
                shutil.copy2(src_file, dst_file)  # écrase seulement le fichier si déjà là
                print(f"[Updater] Copié: {dst_file}")
            except Exception as e:
                print(f"[Updater] Erreur copie {file}: {e}")

    shutil.rmtree("update_temp")
    os.remove("update.zip")
    print("[Updater] Mise à jour terminée.")

def parse_version(v):
    try:
        return tuple(map(int, v.split(".")))
    except Exception:
        return (0,)

if __name__ == "__main__":
    print("[Updater] Vérification de la version...")
    local_version_str = get_local_version()
    remote_version_str = get_remote_version()

    if remote_version_str is None:
        print("[Updater] Impossible de trouver la version.")
        print("[Updater] Installation de la dernière version")
        download_update()
        os.system("python main.py")
    else:
        local_version = parse_version(local_version_str) if local_version_str else None
        remote_version = parse_version(remote_version_str)

        if local_version is None:
            print("[Updater] Pas de version locale, installation...")
            download_update()
            os.system("python main.py")
        elif local_version == remote_version:
            print("[Updater] Tout est PARFAIT ! :D")
            print("[Updater] Lancement de main.py...")
            os.system("python main.py")
        elif local_version > remote_version:
            print(f"[Updater] Tu as la version {local_version_str} alors que la dernière est {remote_version_str}, tu voyages dans le temps??")
            download_update()
            os.system("python main.py")
        elif local_version < remote_version:
            print(f"[Updater] Nouvelle version détectée ({remote_version_str}). Mise à jour...")
            download_update()
            os.system("python main.py")
        else:
            print("[Updater] euh, si tu vois ça c'est que t'as fait n'importe quoi, donc on va te mettre la dernière version stable ;)")  
            download_update()
            os.system("python main.py")
