import os
import shutil

# === CONFIG ===
# Change this to the folder you want to organize
source_folder = r"C:\Users\brubakt\Downloads"

# === STEP 1: Make sure the folder exists ===
if not os.path.exists(source_folder):
    print(f"Folder '{source_folder}' not found!")
    exit()

# === STEP 2: Define your file type categories ===
file_types = {
    "Images": [".jpg", ".jpeg", ".png", ".gif"],
    "Documents": [".pdf", ".docx", ".txt", ".pptx"],
    "Spreadsheets": [".xls", ".xlsx", ".csv"],
    "Archives": [".zip", ".rar"],
    "Scripts": [".py", ".sh", ".bat"]
}

# === STEP 3: Loop through files in the folder ===
for filename in os.listdir(source_folder):
    file_path = os.path.join(source_folder, filename)
    
    # Skip folders
    if os.path.isdir(file_path):
        continue

    # Extract the file extension
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    # === STEP 4: Match file type ===
    moved = False
    for folder_name, extensions in file_types.items():
        if ext in extensions:
            dest_folder = os.path.join(source_folder, folder_name)
            os.makedirs(dest_folder, exist_ok=True)  # create folder if not there
            shutil.move(file_path, os.path.join(dest_folder, filename))
            print(f"Moved {filename} → {folder_name}/")
            moved = True
            break

    # === STEP 5: Handle unknown file types ===
    if not moved:
        other_folder = os.path.join(source_folder, "Other")
        os.makedirs(other_folder, exist_ok=True)
        shutil.move(file_path, os.path.join(other_folder, filename))
        print(f"Moved {filename} → Other/")

print("✅ Done organizing files!")