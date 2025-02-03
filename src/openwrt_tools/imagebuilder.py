# Copyright (c) 2023-25 Tidy Labs, LLC
"""
Builds an OpenWrt image using the Image Builder.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import tarfile
import zstandard

from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import ContentTooShortError
from urllib.request import urlopen

URL_IMAGEBUILDER_SNAPSHOT = "https://downloads.openwrt.org"\
    "/snapshots/targets/{target}/{subtarget}"\
    "/openwrt-imagebuilder-{target}-{subtarget}.Linux-x86_64.{ext}"
URL_IMAGEBUILDER_RELEASE = "https://downloads.openwrt.org"\
    "/releases/{version}/targets/{target}/{subtarget}"\
    "/openwrt-imagebuilder-{version}-{target}-{subtarget}.Linux-x86_64.{ext}"

def compare_version(ver1, ver2):
    pattern = r"(?P<year>\d\d)\.(?P<month>0[1-9]|1[0-2])\.(?P<release>0|[1-9]\d*)(?:-rc(?P<candidate>[1-9]\d*))?"
    match1 = re.search(pattern, ver1)
    match2 = re.search(pattern, ver2)

    year1 = match1.group('year')
    year2 = match2.group('year')
    if year1 != year2:
        return 1 if year1 > year2 else -1

    month1 = match1.group('month')
    month2 = match2.group('month')
    if month1 != month2:
        return 1 if month1 > month2 else -1

    release1 = match1.group('release')
    release2 = match2.group('release')
    if release1 != release2:
        return 1 if release1 > release2 else -1

    candidate1 = match1.group('candidate')
    candidate2 = match2.group('candidate')
    if candidate1 != candidate2:
        return 1 if candidate1 is None or (candidate2 and candidate1 > candidate2) else -1

    return 0

def join(iterable, delimiter=", "):
    return iterable if isinstance(iterable, str) else delimiter.join(iterable or "")

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

def main() -> int:
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
        help="directory of \".patch\" files to apply to the imagebuilder environment",
    )
    args_parser.add_argument(
        "--files_dir",
        default="./files",
        help="directory of extra files to include in rootfs partition",
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
        default=os.getenv("INPUT_JSON_FILE", "./image.json"),
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

    env_defaults = {}
    for key, value in os.environ.items():
        if key.startswith("INPUT_") and value:
             env_defaults[key[6:].lower()] = value
    parser.set_defaults(**env_defaults)

    parser.parse_args(argv, args)

    profile = args.profile
    target, subtarget = args.target.split("/", 1)
    version = args.version
    packages = join(args.packages, delimiter=" ")

    patches_dir = Path(args.patches_dir).resolve()
    files_dir = Path(args.files_dir).resolve()
    packages_dir = Path(args.packages_dir).resolve()
    bin_dir = Path(args.bin_dir).resolve()

    ext = "tar.zst" if version == "SNAPSHOT" or compare_version("24.10.0-rc1", version) <= 0 else "tar.xz"

    imagebuilder_url = (URL_IMAGEBUILDER_SNAPSHOT if version == "SNAPSHOT"
        else URL_IMAGEBUILDER_RELEASE).format(**locals())
    imagebuilder_tar = urldownload(imagebuilder_url)

    imagebuilder_dir = basename(imagebuilder_url, suffix=f".{ext}")
    if os.path.exists(imagebuilder_dir):
        print(f"Deleting stale directory: {imagebuilder_dir}")
        shutil.rmtree(imagebuilder_dir)

    if ext.endswith("zst"):
        with zstandard.open(imagebuilder_tar, "rb") as zst_file:
            with tarfile.TarFile.taropen(None, "r", zst_file) as tar_file:
                print(f"Extracting: {imagebuilder_tar.name}")
                tar_file.extractall()
    else:
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
        imagebuilder_cmd += [ f"PACKAGES={packages}" ]
    if files_dir.exists():
        imagebuilder_cmd += [ f"FILES={files_dir}" ]
    subprocess.run(imagebuilder_cmd, check=True)

    os.makedirs(bin_dir, exist_ok=True)
    for img_file in Path("bin").glob("**/*.img*"):
        print(f"Copying image: {img_file.name}")
        shutil.copy2(img_file, bin_dir)

    return 0

if __name__ == "__main__":
    sys.exit(main())
