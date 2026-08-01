#!/usr/bin/env python
"""Download REAL public datasets (Kaggle / Hugging Face) into datasets/raw/."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import _bootstrap  # noqa: F401  — puts src/ on sys.path

from sdn_its.utils.paths import PROJECT_ROOT, ensure_dir

# Real mirrors — not placeholders
DATASETS = {
    "insdn": {
        "title": "InSDN (IEEE Access 2020) — SDN intrusion flows",
        "raw_dir": "datasets/raw/insdn",
        "kaggle": "phamthaibao/insdn-dataset",
        "huggingface": {
            "repo_id": "Sharukesh/INSDN",
            "filename": "Dataset.csv",
        },
        "official": [
            "https://aseados.ucd.ie/datasets/SDN/",
            "https://www.kaggle.com/datasets/phamthaibao/insdn-dataset",
            "https://huggingface.co/datasets/Sharukesh/INSDN",
        ],
    },
    "cicids2017": {
        "title": "CSE-CIC-IDS2017 (ML-ready CSV mirror)",
        "raw_dir": "datasets/raw/cicids2017",
        "kaggle": "chethuhn/network-intrusion-dataset",
        "huggingface": {
            "repo_id": "bvk/CICIDS-2017",
            # Attack-heavy days first (no Kaggle token needed)
            "filenames": ["friday.csv", "tuesday.csv", "wednesday.csv"],
        },
        "official": [
            "https://www.unb.ca/cic/datasets/ids-2017.html",
            "https://www.kaggle.com/datasets/chethuhn/network-intrusion-dataset",
            "https://huggingface.co/datasets/bvk/CICIDS-2017",
        ],
    },
}


def _have_kaggle() -> bool:
    home = Path.home()
    cred = home / ".kaggle" / "kaggle.json"
    win_cred = Path.home() / ".kaggle" / "kaggle.json"
    return cred.exists() or win_cred.exists() or shutil.which("kaggle") is not None


def _download_kaggle(slug: str, dest: Path) -> bool:
    ensure_dir(dest)
    cmd = [sys.executable, "-m", "kaggle", "datasets", "download", "-d", slug, "-p", str(dest), "--unzip"]
    print(f"[*] Kaggle: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        # try CLI binary
        if shutil.which("kaggle"):
            try:
                subprocess.check_call(
                    ["kaggle", "datasets", "download", "-d", slug, "-p", str(dest), "--unzip"]
                )
                return True
            except subprocess.CalledProcessError as e2:
                print(f"[!] Kaggle download failed: {e2}")
                return False
        print(f"[!] Kaggle download failed: {exc}")
        print("    → Create token: https://www.kaggle.com/settings → API → Create New Token")
        print("    → Save as %USERPROFILE%\\.kaggle\\kaggle.json")
        print("    → pip install kaggle")
        return False
    # unzip leftover zips if --unzip missed
    for z in dest.glob("*.zip"):
        print(f"[*] Unzipping {z.name}")
        with zipfile.ZipFile(z, "r") as zf:
            zf.extractall(dest)
    return any(dest.rglob("*.csv"))


def _download_huggingface(repo_id: str, filename: str | None, dest: Path, filenames: list[str] | None = None) -> bool:
    ensure_dir(dest)
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("[*] Installing huggingface_hub...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "huggingface_hub"])
        from huggingface_hub import hf_hub_download

    files = list(filenames or [])
    if filename:
        files = [filename] + [f for f in files if f != filename]
    if not files:
        print("[!] No Hugging Face filenames configured")
        return False

    ok_any = False
    for fn in files:
        print(f"[*] Hugging Face: {repo_id} / {fn}")
        try:
            path = hf_hub_download(
                repo_id=repo_id,
                filename=fn,
                repo_type="dataset",
                local_dir=str(dest),
            )
            print(f"[+] Saved {path}")
            ok_any = True
        except Exception as exc:
            print(f"[!] Hugging Face download failed for {fn}: {exc}")
    return ok_any


def _write_readme(name: str, info: dict, dest: Path):
    urls = "\n".join(f"- {u}" for u in info["official"])
    (dest / "README.md").write_text(
        f"# {info['title']}\n\n## Mirrors\n{urls}\n\n"
        f"## Local path\n`{info['raw_dir']}`\n\n"
        f"## Next\n```bash\npython scripts/prepare_data.py --source "
        f"{'insdn' if name == 'insdn' else 'cic'}\n```\n",
        encoding="utf-8",
    )


def download_one(name: str, prefer: str) -> bool:
    info = DATASETS[name]
    dest = ensure_dir(PROJECT_ROOT / info["raw_dir"])
    _write_readme(name, info, dest)

    ok = False
    order = []
    if prefer == "kaggle":
        order = ["kaggle", "hf"]
    elif prefer == "hf":
        order = ["hf", "kaggle"]
    else:  # auto: HF first when available (no token)
        order = ["hf", "kaggle"] if info.get("huggingface") else ["kaggle"]

    for src in order:
        if ok:
            break
        if src == "hf" and info.get("huggingface"):
            hf = info["huggingface"]
            ok = _download_huggingface(
                hf["repo_id"],
                hf.get("filename"),
                dest,
                filenames=hf.get("filenames"),
            )
        elif src == "kaggle" and info.get("kaggle"):
            if not _have_kaggle():
                print(f"[!] Skip Kaggle ({info['kaggle']}): no ~/.kaggle/kaggle.json")
                continue
            try:
                import kaggle  # noqa: F401
            except ImportError:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "kaggle"])
            ok = _download_kaggle(info["kaggle"], dest)

    csvs = list(dest.rglob("*.csv"))
    print(f"[*] {name}: {len(csvs)} CSV file(s) under {dest.relative_to(PROJECT_ROOT)}")
    for c in csvs[:8]:
        print(f"    - {c.relative_to(PROJECT_ROOT)} ({c.stat().st_size / 1e6:.1f} MB)")
    return ok and len(csvs) > 0


def main():
    parser = argparse.ArgumentParser(
        description="Download REAL InSDN / CIC datasets from Kaggle or Hugging Face"
    )
    parser.add_argument("--name", choices=list(DATASETS) + ["all"], default="insdn")
    parser.add_argument(
        "--prefer",
        choices=["auto", "kaggle", "hf"],
        default="auto",
        help="auto: HF first when available (no token), else Kaggle",
    )
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="Run prepare_data.py after successful download",
    )
    args = parser.parse_args()

    names = list(DATASETS) if args.name == "all" else [args.name]
    results = {}
    for name in names:
        print("=" * 60)
        print(f"  {DATASETS[name]['title']}")
        print("=" * 60)
        results[name] = download_one(name, args.prefer)

    print("=" * 60)
    for name, ok in results.items():
        print(f"[{'OK' if ok else 'FAIL'}] {name}")

    if args.prepare and any(results.values()):
        # Prefer the dataset that was just requested (don't silently fall back to InSDN)
        if args.name != "all" and results.get(args.name):
            src = "insdn" if args.name == "insdn" else "cic"
        else:
            src = "cic" if results.get("cicids2017") else "insdn"
        print(f"[*] Running prepare_data --source {src}")
        subprocess.check_call(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "prepare_data.py"),
                "--source",
                src,
                "--max-rows",
                "80000",
            ]
        )

    if not any(results.values()):
        print("\n[!] Download failed. Options:")
        print("  1) HuggingFace: pip install huggingface_hub && retry --prefer hf")
        print("  2) Kaggle: put kaggle.json in %USERPROFILE%\\.kaggle\\ then:")
        print("       pip install kaggle")
        print("       python scripts/download_dataset.py --name cicids2017 --prefer kaggle")
        sys.exit(1)


if __name__ == "__main__":
    main()
