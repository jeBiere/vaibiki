from pathlib import Path
import shutil
import sys
import hashlib
import yaml


class OverlayManager:
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.assets_dir = Path(__file__).resolve().parent / "assets"
        self.assets_dir.mkdir(exist_ok=True)

    def process(self, overlay_path: str) -> bool:
        source_path = Path(overlay_path)

        if not source_path.is_file():
            print(f"Ошибка: файл '{overlay_path}' не найден.")
            sys.exit(1)

        target_name = self._resolve_filename(source_path)
        self._update_config(target_name)
        return True

    def _resolve_filename(self, source_path: Path) -> str:
        filename = source_path.name
        dest_path = self.assets_dir / filename

        if dest_path.exists() and self._is_same_file(source_path, dest_path):
            return filename

        if dest_path.exists():
            base, ext = dest_path.stem, dest_path.suffix
            counter = 1
            while True:
                new_name = f"{base}_{counter}{ext}"
                new_path = self.assets_dir / new_name
                if not new_path.exists():
                    dest_path = new_path
                    filename = new_name
                    break
                counter += 1

        shutil.copy2(source_path, dest_path)
        return filename

    def _is_same_file(self, file1: Path, file2: Path) -> bool:
        return self._hash(file1) == self._hash(file2)

    def _hash(self, path: Path, chunk_size: int = 8192) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _update_config(self, filename: str):
        with self.config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        config["overlay_image"] = str(Path("assets") / filename).replace("\\", "/")

        with self.config_path.open("w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)

        print(f"✔ Конфигурация обновлена: overlay_image -> {config['overlay_image']}")
