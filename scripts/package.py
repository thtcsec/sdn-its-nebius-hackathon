import os
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ZIP_NAME = "sdn_its_resilience_ai_submission.zip"
OUTPUT_ZIP_PATH = PROJECT_ROOT / OUTPUT_ZIP_NAME

INCLUDE_PATHS = [
    "data",
    "models",
    "sdn_controller",
    "simulation",
    "docs",
    "tests",
    "scripts",
    "requirements.txt",
    "README.md",
    "IEDE_Autumn_Report_Updated.docx",
    ".gitignore"
]

EXCLUDE_PATTERNS = [
    "__pycache__",
    ".pytest_cache",
    ".venv",
    ".git",
    "*.pyc",
    "*.log",
    "*.zip"
]

def should_exclude(rel_path: str) -> bool:
    for pat in EXCLUDE_PATTERNS:
        if pat.startswith("*") and rel_path.endswith(pat[1:]):
            return True
        if pat in rel_path.split(os.sep):
            return True
    return False

def package_project():
    print("=" * 70)
    print("  SDN-ITS RESILIENCE AI - PROJECT SOURCE CODE PACKAGER")
    print("=" * 70)
    print(f"[*] Packaging project files from: {PROJECT_ROOT}")
    
    with zipfile.ZipFile(OUTPUT_ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
        file_count = 0
        for item in INCLUDE_PATHS:
            item_path = PROJECT_ROOT / item
            if not item_path.exists():
                print(f"[!] Warning: Path {item} does not exist, skipping.")
                continue
                
            if item_path.is_file():
                rel_path = item_path.relative_to(PROJECT_ROOT)
                zipf.write(item_path, rel_path)
                file_count += 1
                print(f" [+] Added file: {rel_path}")
            elif item_path.is_dir():
                for root, dirs, files in os.walk(item_path):
                    # Filter out excluded directories in-place
                    dirs[:] = [d for d in dirs if not should_exclude(d)]
                    for file in files:
                        full_file_path = Path(root) / file
                        rel_path = full_file_path.relative_to(PROJECT_ROOT)
                        if not should_exclude(str(rel_path)):
                            zipf.write(full_file_path, rel_path)
                            file_count += 1
                            print(f" [+] Added: {rel_path}")

    zip_size_mb = os.path.getsize(OUTPUT_ZIP_PATH) / (1024 * 1024)
    print("=" * 70)
    print(f"[+] Package created successfully!")
    print(f"    File: {OUTPUT_ZIP_PATH.name}")
    print(f"    Size: {zip_size_mb:.2f} MB")
    print(f"    Total files archived: {file_count}")
    print("=" * 70)

if __name__ == "__main__":
    package_project()
