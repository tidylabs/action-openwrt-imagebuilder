#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import subprocess
import tarfile

from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import ContentTooShortError
from urllib.request import urlopen

URL_IMAGEBUILDER_SNAPSHOT = "https://downloads.openwrt.org"\
    "/snapshots/targets/{target}/{subtarget}"\
    "/openwrt-imagebuilder-{target}-{subtarget}.Linux-x86_64.tar.xz"
URL_IMAGEBUILDER_RELEASE = "https://downloads.openwrt.org"\
    "/releases/{version}/targets/{target}/{subtarget}"\
    "/openwrt-imagebuilder-{version}-{target}-{subtarget}.Linux-x86_64.tar.xz"

def basename(path, suffix=""):
    name = os.path.basename(path)
    return name[:-len(suffix)] if suffix and name.endswith(suffix) else name

def urldownload(url, path="."):
    filename = Path(path, os.path.basename(url)).resolve()
    os.makedirs(filename.parent, exist_ok=True)

    with urlopen(url) as response:
        size = -1
        if content_length := response.headers.get("Content-Length"):
            size = int(content_length)

        mtime = -1
        if last_modified := response.headers.get("Last-Modified"):
            mtime = parsedate_to_datetime(last_modified).timestamp()

        if filename.exists():
            stat = filename.stat()
            if stat.st_mtime == mtime and stat.st_size == size:
                print(f"Already downloaded: {filename.name}")
                return filename

        print(f"Downloading: {filename.name}")
        with filename.open("wb") as file:
            read = 0
            while block := response.read(1024 * 8):
                read += len(block)
                file.write(block)
            
            if mtime != -1:
                atime = filename.stat().st_atime
                os.utime(filename, times=(atime, mtime))
        
        if size >= 0 and read < size:
            raise ContentTooShortError(
                f"download incomplete: got only {read} out of {size} bytes",
                content=(filename, response.info()),
            )
    
    return filename

if __name__ == "__main__":
    args_parser = argparse.ArgumentParser(add_help=False)
    args_parser.add_argument(
        "--profile",
        help="target profile (e.g. friendlyarm_nanopi-r4s)",
    )
    args_parser.add_argument(
        "--target",
        default="rockchip/armv8",
        help="target device type (e.g. rockchip/armv8)",
    )
    args_parser.add_argument(
        "--version",
        default="SNAPSHOT",
        help="target version (e.g. 22.03.0-rc1)",
    )
    args_parser.add_argument(
        "--packages",
        help="list of packages to include or exclude (e.g. \"luci firewall -firewall4\")",
    )
    args_parser.add_argument(
        "--patches_dir",
        default="./patches",
        help="directory of \".patch\" files to apply to imagebuilder",
    )
    args_parser.add_argument(
        "--files_dir",
        default="./files",
        help="directory of extra files to include in rootfs",
    )
    args_parser.add_argument(
        "--packages_dir",
        default="./packages",
        help="directory of \".ipk\" files to install in image",
    )
    args_parser.add_argument(
        "--bin_dir",
        default=".",
        help="output directory for the images",
    )

    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument(
        "--json_file",
        default="./image.json",
        help="json file with default image arguments"
    )

    parser = argparse.ArgumentParser(
        description="Build an OpenWrt image",
        parents=[ args_parser, config_parser ],
    )

    args, argv = config_parser.parse_known_args()

    json_file = Path(args.json_file).resolve()
    if json_file.exists():
        defaults = json.load(json_file.open())
        parser.set_defaults(**defaults)

    parser.parse_args(argv, args)

    profile = args.profile
    target, subtarget = args.target.split("/", 1)
    version = args.version
    packages = args.packages

    patches_dir = Path(args.patches_dir).resolve()
    files_dir = Path(args.files_dir).resolve()
    packages_dir = Path(args.packages_dir).resolve()
    bin_dir = Path(args.bin_dir).resolve()

    imagebuilder_url = (URL_IMAGEBUILDER_SNAPSHOT if version == "SNAPSHOT"
        else URL_IMAGEBUILDER_RELEASE).format(**locals())
    imagebuilder_tar = urldownload(imagebuilder_url)

    imagebuilder_dir = basename(imagebuilder_url, suffix=".tar.xz")
    if os.path.exists(imagebuilder_dir):
        print(f"Deleting stale directory: {imagebuilder_dir}")
        shutil.rmtree(imagebuilder_dir)

    with tarfile.open(name=imagebuilder_tar) as tar_file:
        print(f"Extracting: {imagebuilder_tar.name}")
        tar_file.extractall()

    os.chdir(imagebuilder_dir)

    for patch_file in patches_dir.glob("*.patch"):
        print(f"Applying patch: {patch_file.name}")
        subprocess.run(["patch", "-p0", "-i", f"{patch_file}"], check=True)

    for package_file in packages_dir.glob("*.ipk"):
        print(f"Copying package: {package_file.name}")
        shutil.copy2(package_file, "./packages")

    imagebuilder_cmd = [ "make", "image" ]
    if profile:
        imagebuilder_cmd += [ f"PROFILE={profile}" ]
    if packages:
        imagebuilder_cmd += [ f"PACKAGES={' '.join(packages)}" ]
    if files_dir.exists():
        imagebuilder_cmd += [ f"FILES={files_dir}" ]
    if bin_dir:
        imagebuilder_cmd += [ f"BIN_DIR={bin_dir}" ]
    subprocess.run(imagebuilder_cmd, check=True)
