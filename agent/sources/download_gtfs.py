"""Download the operators' GTFS feeds into data/gtfs/<operator>/.

Run from the repository root: python -m agent.sources.download_gtfs
Data: transport.data.gouv.fr, licensed under ODbL (attribution required).
"""

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.request import urlopen

FEEDS = {
    "blablacar": "https://www.data.gouv.fr/api/1/datasets/r/fd54f81f-4389-4e73-be75-491133d011c3",
    "flixbus": "https://www.data.gouv.fr/api/1/datasets/r/30d94e83-48a4-4c44-8a96-c082377f5221",
}
SKIPPED_FILES = {"shapes.txt"}


def extract_feed(archive_path: Path, target: Path) -> list[str]:
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        unsafe = [name for name in names
                  if PurePosixPath(name).name != name or not name.endswith(".txt")]
        if unsafe:
            raise ValueError(f"Refusing to extract unexpected entries: {unsafe}")
        target.mkdir(parents=True, exist_ok=True)
        extracted = sorted(name for name in names if name not in SKIPPED_FILES)
        for name in extracted:
            with archive.open(name) as source, (target / name).open("wb") as destination:
                shutil.copyfileobj(source, destination)
        return extracted


def download(root: Path) -> None:
    for operator, url in FEEDS.items():
        with tempfile.TemporaryDirectory() as workspace:
            archive_path = Path(workspace) / f"{operator}.zip"
            with urlopen(url, timeout=300) as response, archive_path.open("wb") as file:
                shutil.copyfileobj(response, file)
            files = extract_feed(archive_path, root / operator)
        print(f"{operator}: {len(files)} files in {root / operator}")


if __name__ == "__main__":
    download(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/gtfs"))
