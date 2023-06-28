# OpenWrt Image Builder

This action downloads and runs the [OpenWrt Image Builder](https://openwrt.org/docs/guide-user/additional-software/imagebuilder) to build custom images based on official OpenWrt releases (or snapshots).

## Usage

```yaml
- uses: tidylabs/action-openwrt-imagebuilder@main
  with:
    # Target profile (e.g. friendlyarm_nanopi-r4s).
    profile: ""
    # Target device type (e.g. rockchip/armv8).
    target: ""
    # Target version (e.g. 22.03.0-rc1).
    version: ""
    # List of packages to include or exclude (e.g. "luci firewall -firewall4").
    packages: ""
    # Directory of ".patch" files to apply to the imagebuilder environment.
    # Default: "./patches"
    patches_dir: ""
    # Directory of extra files to include in rootfs partition.
    # Default: "./files"
    files_dir: ""
    # Directory of ".ipk" files to install in image.
    # Default: "./packages"
    packages_dir: ""
    # Output directory for the images.
    # Default: "."
    bin_dir: ""
    # JSON file with default image arguments.
    # Default: "./image.json"
    json_file: ""
```
