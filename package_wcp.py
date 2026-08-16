#!/usr/bin/env python3
"""
Project Sakura GameDeck Package Builder
Converts raw component directories (Turnip -> .zip, DXVK -> .wcp) into release packages.
"""

import os
import sys
import json
import shutil
import zipfile
import subprocess
import hashlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLKIT_ROOT = SCRIPT_DIR
RELEASES_DIR = os.path.join(TOOLKIT_ROOT, "releases")
SCRATCH_TEMP_DIR = os.path.join(TOOLKIT_ROOT, "build_wcp_temp")

def ensure_dirs():
    os.makedirs(RELEASES_DIR, exist_ok=True)
    if os.path.exists(SCRATCH_TEMP_DIR):
        shutil.rmtree(SCRATCH_TEMP_DIR)
    os.makedirs(SCRATCH_TEMP_DIR, exist_ok=True)

def create_wcp_archive(source_dir, output_wcp_path):
    """Creates a .tar.zst archive with .wcp extension using tar --zstd."""
    print(f" -> Compressing into WCP: {os.path.basename(output_wcp_path)}...")
    if os.path.exists(output_wcp_path):
        os.remove(output_wcp_path)
        
    cmd = ["tar", "--zstd", "-cf", output_wcp_path, "-C", source_dir, "."]
    subprocess.run(cmd, check=True)
    size_mb = os.path.getsize(output_wcp_path) / (1024 * 1024)
    print(f" -> Created {os.path.basename(output_wcp_path)} ({size_mb:.2f} MB)")

def create_zip_archive(source_dir, output_zip_path):
    """Creates a standard .zip archive containing directory contents at zip root."""
    print(f" -> Compressing into ZIP: {os.path.basename(output_zip_path)}...")
    if os.path.exists(output_zip_path):
        os.remove(output_zip_path)

    with zipfile.ZipFile(output_zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, arcname)

    size_mb = os.path.getsize(output_zip_path) / (1024 * 1024)
    print(f" -> Created {os.path.basename(output_zip_path)} ({size_mb:.2f} MB)")

def package_turnip():
    turnip_dir = os.path.join(TOOLKIT_ROOT, "turnip-latest")
    if not os.path.exists(turnip_dir):
        print("[WARN] turnip-latest directory not found, skipping.")
        return

    print("\n[+] Packaging Freedreno Turnip Vulkan Driver (.zip)...")
    output_path = os.path.join(RELEASES_DIR, "turnip-latest.zip")
    create_zip_archive(turnip_dir, output_path)

def package_dxvk():
    dxvk_dir = os.path.join(TOOLKIT_ROOT, "dxvk-sarek-latest")
    if not os.path.exists(dxvk_dir):
        print("[WARN] dxvk-sarek-latest directory not found, skipping.")
        return

    print("\n[+] Packaging DXVK Sarek (.wcp)...")
    output_path = os.path.join(RELEASES_DIR, "dxvk-sarek-latest.wcp")

    # If profile.json already exists in the directory, package directly to preserve exact configuration
    existing_profile = os.path.join(dxvk_dir, "profile.json")
    if os.path.exists(existing_profile):
        create_wcp_archive(dxvk_dir, output_path)
        return

    staging_dir = os.path.join(SCRATCH_TEMP_DIR, "dxvk_staging")
    os.makedirs(staging_dir, exist_ok=True)

    sys32_dir = os.path.join(staging_dir, "system32")
    syswow64_dir = os.path.join(staging_dir, "syswow64")
    os.makedirs(sys32_dir, exist_ok=True)
    os.makedirs(syswow64_dir, exist_ok=True)

    # Copy 64-bit DLLs
    src_x64 = os.path.join(dxvk_dir, "x64")
    if os.path.exists(src_x64):
        for f in os.listdir(src_x64):
            shutil.copy2(os.path.join(src_x64, f), os.path.join(sys32_dir, f))

    # Copy 32-bit DLLs
    src_x32 = os.path.join(dxvk_dir, "x32")
    if os.path.exists(src_x32):
        for f in os.listdir(src_x32):
            shutil.copy2(os.path.join(src_x32, f), os.path.join(syswow64_dir, f))

    # Build standardized profile.json
    profile = {
        "type": "DXVK",
        "versionName": "1.12.0-sarek",
        "versionCode": 1,
        "description": "DXVK Sarek with DirectX 8, 9, 10, 11 and DirectDraw support for Sakura GameDeck",
        "files": []
    }

    # Add system32 files
    for f in sorted(os.listdir(sys32_dir)):
        if f.endswith(".dll"):
            profile["files"].append({
                "source": f"system32/{f}",
                "target": f"${{system32}}/{f}"
            })

    # Add syswow64 files
    for f in sorted(os.listdir(syswow64_dir)):
        if f.endswith(".dll"):
            profile["files"].append({
                "source": f"syswow64/{f}",
                "target": f"${{syswow64}}/{f}"
            })

    profile_path = os.path.join(staging_dir, "profile.json")
    with open(profile_path, "w") as f:
        json.dump(profile, f, indent=2)

    create_wcp_archive(staging_dir, output_path)

def generate_checksums():
    print("\n[+] Updating SHA256SUMS.txt...")
    checksum_file = os.path.join(RELEASES_DIR, "SHA256SUMS.txt")
    lines = []
    
    files = sorted([f for f in os.listdir(RELEASES_DIR) if f.endswith((".wcp", ".zip"))])
    for fname in files:
        fpath = os.path.join(RELEASES_DIR, fname)
        hasher = hashlib.sha256()
        with open(fpath, "rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        lines.append(f"{digest}  {fname}\n")
        print(f"  {digest}  {fname}")

    with open(checksum_file, "w") as f:
        f.writelines(lines)
    print(" -> SHA256SUMS.txt updated successfully.")

def cleanup():
    if os.path.exists(SCRATCH_TEMP_DIR):
        shutil.rmtree(SCRATCH_TEMP_DIR)

def main():
    print("=" * 60)
    print(" Android Gaming Packages - Driver & Translation Packaging Tool")
    print("=" * 60)
    ensure_dirs()
    try:
        package_turnip()
        package_dxvk()
        generate_checksums()
        print("\n[✓] All packages built successfully!")
    finally:
        cleanup()

if __name__ == "__main__":
    main()
