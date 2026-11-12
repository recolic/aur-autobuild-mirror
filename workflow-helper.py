# created by GPT-5.6
"""Incremental clean-chroot builds and unsigned pacman repository publication."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
DIST = Path("dist").resolve()
TAG = "archlinux-packages"
PACMAN_CONFIG = "/usr/share/devtools/pacman.conf.d/extra.conf"


def run(*args, cwd=None):
    return subprocess.check_output([str(arg) for arg in args], cwd=cwd, text=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def metadata(directory):
    values = {}
    for line in run("runuser", "-u", "builder", "--", "makepkg", "--printsrcinfo", cwd=directory).splitlines():
        key, separator, value = line.strip().partition(" = ")
        if separator:
            values.setdefault(key, []).append(value)
    return values


def recipe_directories(work):
    directories = {path.name: path for path in sorted((ROOT / "pkgs").iterdir()) if path.is_dir()}
    passthru = ROOT / "pkgs/aur-passthru.txt"
    if not passthru.exists():
        return directories
    names = []
    for number, line in enumerate(passthru.read_text().splitlines(), start=1):
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        if not re.fullmatch(r"[a-z0-9@_+][a-z0-9@._+-]*", name) or name in names:
            raise ValueError(f"{passthru}:{number}: invalid or duplicate AUR package name: {name}")
        names.append(name)
    if not names:
        return directories
    query = urlencode([("arg[]", name) for name in names])
    with urlopen(f"https://aur.archlinux.org/rpc/v5/info?{query}", timeout=30) as response:
        info = json.load(response)
    if info.get("error"):
        raise ValueError(f"AUR lookup failed: {info['error']}")
    found = {package["Name"]: package["PackageBase"] for package in info["results"]}
    if missing := set(names) - found.keys():
        raise ValueError(f"AUR packages not found: {sorted(missing)}")
    upstream = work / "aur"
    upstream.mkdir()
    run("chown", "builder:builder", upstream)
    for base in sorted(set(found.values())):
        if not re.fullmatch(r"[a-z0-9@_+][a-z0-9@._+-]*", base) or base in directories:
            raise ValueError(f"Invalid AUR package base or collision with a local recipe: {base}")
        directory = upstream / base
        run("runuser", "-u", "builder", "--", "git", "clone", "--depth", "1", "--", f"https://aur.archlinux.org/{base}.git", directory)
        directories[base] = directory
    return directories


def release_exists():
    pages = json.loads(run("gh", "api", "--paginate", "--slurp", f"repos/{os.environ['GITHUB_REPOSITORY']}/releases?per_page=100"))
    return any(release["tag_name"] == TAG for page in pages for release in page)


def download(name, directory):
    if Path(name).name != name or name.startswith("-"):
        raise ValueError(f"Invalid release asset name: {name}")
    run("gh", "release", "download", TAG, "--repo", os.environ["GITHUB_REPOSITORY"], "--pattern", name, "--dir", directory)


def verify_assets(manifest):
    for package in manifest["packages"].values():
        for name, checksum in package["files"].items():
            if Path(name).name != name or digest(DIST / name) != checksum:
                raise ValueError(f"Package checksum mismatch: {name}")


def materialize(package):
    for name, checksum in package["files"].items():
        if Path(name).name != name or name.startswith("-"):
            raise ValueError(f"Invalid release asset name: {name}")
        if not (DIST / name).exists():
            download(name, DIST)
        if digest(DIST / name) != checksum:
            raise ValueError(f"Package checksum mismatch: {name}")


def non_aur_packages(previous):
    known = {name: checksum for package in previous["packages"].values() for name, checksum in package["files"].items()}
    selected = subprocess.check_output(["bash", str(ROOT / "pkgs/non-aur-upstreams.sh"), str(DIST)], input="\n".join(known), text=True).splitlines()
    packages = {}
    for name in selected:
        if Path(name).name != name or name.startswith("-") or ".pkg.tar." not in name:
            raise ValueError(f"Invalid upstream package filename: {name}")
        package = "upstream:" + name.rsplit("-", 3)[0]
        if package in packages:
            raise ValueError(f"Duplicate upstream package: {package}")
        if name not in known:
            run("bsdtar", "-xOf", DIST / name, ".PKGINFO")
        packages[package] = {"files": {name: known[name] if name in known else digest(DIST / name)}}
    return packages


def build():
    DIST.mkdir()
    with tempfile.TemporaryDirectory(prefix="archlinux-build-", dir="/var/tmp") as temporary:
        work = Path(temporary)
        work.chmod(0o755)
        previous = {"packages": {}}
        if release_exists():
            download("manifest.json", work)
            previous = json.loads((work / "manifest.json").read_text())
            if previous["schema"] != 1:
                raise ValueError("Unsupported previous build manifest")
        # An empty installed-package database makes resolution independent of the CI container.
        database = work / "database"
        shutil.copytree("/var/lib/pacman/sync", database / "sync")
        directories = recipe_directories(work)
        recipes = {name: metadata(path) for name, path in directories.items()}
        providers = {}
        for name, info in recipes.items():
            for provided in info["pkgname"] + info.get("provides", []) + info.get("provides_x86_64", []):
                provided = re.split(r"[<>=]", provided)[0]
                if provided in providers and providers[provided] != name:
                    raise ValueError(f"Ambiguous local provider: {provided}")
                providers[provided] = name
        pending = set(recipes)
        results = {}
        changed = False
        chroot = work / "chroot"
        builder = [digest(Path(__file__)), digest(ROOT / ".github/workflows/archlinux-pkgs.yml")]
        while pending:
            progress = False
            for name in sorted(pending):
                info = recipes[name]
                dependencies = set()
                for key in ("depends", "makedepends", "checkdepends"):
                    dependencies.update(info.get(key, []) + info.get(f"{key}_x86_64", []))
                local = {providers[re.split(r"[<>=]", dep)[0]] for dep in dependencies if re.split(r"[<>=]", dep)[0] in providers} - {name}
                if not local <= results.keys():
                    continue
                official = sorted(dep for dep in dependencies if re.split(r"[<>=]", dep)[0] not in providers)
                resolved = run("pacman", "--config", PACMAN_CONFIG, "--dbpath", database, "-Sp", "--noconfirm", "--print-format", "%n=%v", "--", "base-devel", "pacman", "git", *official)
                versions = sorted(set(resolved.splitlines()))
                if not versions or any(not re.fullmatch(r"[a-zA-Z0-9@._+-]+=\S+", version) for version in versions):
                    raise ValueError(f"{name}: unexpected pacman dependency resolution output: {resolved}")
                recipe = directories[name]
                inputs = {str(path.relative_to(recipe)): digest(path) for path in sorted(recipe.rglob("*")) if path.is_file() and ".git" not in path.relative_to(recipe).parts}
                key = fingerprint({"recipe": inputs, "dependencies": versions, "local": {dep: results[dep]["fingerprint"] for dep in sorted(local)}, "builder": builder})
                old = previous["packages"].get(name)
                if old and old["fingerprint"] == key and os.environ.get("FORCE") != "true":
                    print(f"{name}: unchanged", flush=True)
                    results[name] = old
                else:
                    changed = True
                    print(f"{name}: rebuilding", flush=True)
                    source = work / "build" / name
                    source.parent.mkdir(exist_ok=True)
                    shutil.copytree(recipe, source, ignore=shutil.ignore_patterns(".git"))
                    revision = old["revision"] + 1 if old else 1
                    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", info["pkgrel"][0]):
                        raise ValueError(f"{name}: CI requires a numeric recipe pkgrel before appending its rebuild revision")
                    release, _, subrelease = info["pkgrel"][0].partition(".")
                    pkgrel = f"{release}.{int(subrelease or '0') + revision}"
                    version = f"{info.get('epoch', ['0'])[0]}:{info['pkgver'][0]}-{pkgrel}"
                    if old and int(run("vercmp", version, old["version"]).strip()) <= 0:
                        raise ValueError(f"{name}: {version} would not upgrade {old['version']}; bump the recipe version")
                    with (source / "PKGBUILD").open("a") as stream:
                        stream.write(f"\npkgrel={pkgrel}\n")
                    run("chown", "-R", "builder:builder", source)
                    if not chroot.exists():
                        chroot.mkdir()
                        subprocess.run(["mkarchroot", "-C", PACMAN_CONFIG, str(chroot / "root"), "base-devel", "pacman", "git"], check=True)
                        with (chroot / "root/etc/makepkg.conf").open("a") as stream:
                            stream.write("\nOPTIONS+=('!debug')\n")
                    # Install transitive local dependencies together, so pacman can resolve their provides.
                    closure = set(local)
                    for dep in local:
                        closure.update(results[dep]["local"])
                    command = ["makechrootpkg", "-c", "-r", chroot, "-U", "builder"]
                    for dep in sorted(closure):
                        materialize(results[dep])
                        for asset in results[dep]["files"]:
                            command.extend(["-I", DIST / asset])
                    command.extend(["--", "--nosign"])
                    subprocess.run([str(arg) for arg in command], cwd=source, check=True)
                    assets = sorted(source.glob("*.pkg.tar.zst"))
                    if not assets:
                        raise ValueError(f"{name}: build produced no .pkg.tar.zst packages")
                    for asset in assets:
                        # Detect mirror skew between planning and building instead of recording incorrect state.
                        buildinfo = subprocess.check_output(["bsdtar", "-xOf", str(asset), ".BUILDINFO"], text=True)
                        installed = {line.removeprefix("installed = ").rsplit("-", 1)[0] for line in buildinfo.splitlines() if line.startswith("installed = ")}
                        expected = {version.replace("=", "-", 1) for version in versions}
                        if not expected <= installed:
                            raise ValueError(f"{name}: build dependencies differ from plan; retry after mirrors synchronize: {expected - installed}")
                        shutil.copy2(asset, DIST / asset.name)
                    results[name] = {"fingerprint": key, "version": version, "revision": revision, "dependencies": versions, "local": sorted(closure), "files": {asset.name: digest(asset) for asset in assets}}
                pending.remove(name)
                progress = True
            if not progress:
                raise ValueError(f"Cyclic local dependencies: {sorted(pending)}")
        upstream = non_aur_packages(previous)
        for name, package in upstream.items():
            if name.removeprefix("upstream:") in providers:
                raise ValueError(f"Upstream package collides with a build recipe: {name}")
            changed |= previous["packages"].get(name) != package
        results.update(upstream)
        changed |= results.keys() != previous["packages"].keys()
        if not results:
            raise ValueError("No package directories found")
        manifest = {"schema": 1, "commit": os.environ["GITHUB_SHA"], "packages": results}
        (DIST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        if changed:
            for package in results.values():
                materialize(package)
            verify_assets(manifest)
            run("repo-add", DIST / "recoarch.db.tar.gz", *sorted(DIST.glob("*.pkg.tar.*")))
            # Release uploads need regular files for pacman's database aliases.
            for alias in ("recoarch.db", "recoarch.files"):
                (DIST / alias).unlink()
                shutil.copyfile(DIST / f"{alias}.tar.gz", DIST / alias)
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as stream:
            stream.write(f"changed={str(changed).lower()}\n")
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write(f"Arch repository: {'updated' if changed else 'unchanged'}; {len(results)} package entries checked.\n")


def publish():
    manifest = json.loads((DIST / "manifest.json").read_text())
    verify_assets(manifest)
    repository = os.environ["GITHUB_REPOSITORY"]
    if not release_exists():
        run("gh", "release", "create", TAG, "--repo", repository, "--target", os.environ["GITHUB_SHA"], "--title", "Arch package repository (automated, unsigned)", "--notes", "Auto-managed rolling archlinux repository.", "--prerelease", "--latest=false")
    else:
        run("gh", "release", "edit", TAG, "--repo", repository, "--prerelease", "--latest=false")
    for paths in (sorted(DIST.glob("*.pkg.tar.*")), sorted(DIST.glob("recoarch.*")), [DIST / "manifest.json"]):
        run("gh", "release", "upload", TAG, *paths, "--repo", repository, "--clobber")
    current = {name for package in manifest["packages"].values() for name in package["files"]}
    release = json.loads(run("gh", "api", f"repos/{repository}/releases/tags/{TAG}"))
    pages = json.loads(run("gh", "api", "--paginate", "--slurp", f"repos/{repository}/releases/{release['id']}/assets?per_page=100"))
    for page in pages:
        for asset in page:
            if ".pkg.tar." in asset["name"] and not asset["name"].endswith(".sig") and asset["name"] not in current:
                run("gh", "api", "--method", "DELETE", f"repos/{repository}/releases/assets/{asset['id']}")


if __name__ == "__main__":
    if sys.argv[1:] == ["build"]:
        build()
    elif sys.argv[1:] == ["publish"]:
        publish()
    else:
        sys.exit("Usage: workflow-helper.py build|publish")
