"""Copy what the collector stored on the `data` branch into the local data_store.

Run: python -m apollo.data.sync [--root data_store]

Only bars, context, quality and ledger are copied. journal.duckdb and journal_media/
are local-only and never touched. Bar files are merged rather than replaced: Yahoo only
serves a rolling window, so a local bar the branch lacks can't be fetched again.
"""

import argparse
import io
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

import polars as pl

FOLDERS = ("bars", "context", "quality", "ledger")


def sync_data(root: Path, ref: str = "origin/data", repo: Path = Path(".")) -> dict[str, int]:
    done = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", ref], capture_output=True, check=False
    )
    if done.returncode != 0:
        raise ValueError(f"no such ref {ref}")
    counts: dict[str, int] = {}
    with tarfile.open(fileobj=io.BytesIO(done.stdout)) as tar:
        for member in tar.getmembers():
            path = PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts:
                continue
            if path.parts[0] not in FOLDERS:
                continue
            target = root.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            src = tar.extractfile(member)
            if src is None:
                continue
            data = src.read()
            if path.parts[0] == "bars" and target.suffix == ".parquet" and target.exists():
                both = pl.concat([pl.read_parquet(target), pl.read_parquet(io.BytesIO(data))])
                both.unique("ts", keep="last", maintain_order=True).sort("ts").write_parquet(
                    target, compression="zstd"
                )
            else:
                target.write_bytes(data)
            counts[path.parts[0]] = counts.get(path.parts[0], 0) + 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data_store"))
    parser.add_argument("--ref", default="origin/data")
    args = parser.parse_args()
    subprocess.run(["git", "fetch", "origin", "data"], check=True)
    for folder, n in sorted(sync_data(args.root, args.ref).items()):
        print(f"{folder}: {n} files")


if __name__ == "__main__":
    main()
