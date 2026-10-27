"""쇼핑 리스트 JSON 파일 로드/저장."""

import json
import os
import shutil
import threading
from collections.abc import Callable
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "shopping_list.json"

# Streamlit은 세션(탭)마다 스레드를 쓰므로, 읽기-수정-쓰기가 서로 끼어들지 않게 잠근다.
_lock = threading.RLock()


def load() -> list[dict]:
    """저장된 아이템 목록을 반환한다. 파일이 없거나 손상됐으면 빈 리스트."""
    with _lock:
        try:
            with DATA_FILE.open(encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return []
        except (json.JSONDecodeError, UnicodeDecodeError):
            _backup_corrupt_file()
            return []
        except OSError:
            return []

    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    return [_normalize(item) for item in items if _is_valid(item)]


def save(items: list[dict]) -> None:
    """아이템 목록을 JSON 파일에 저장한다. 임시 파일에 쓴 뒤 교체해서 쓰다 끊겨도 기존 파일이 깨지지 않는다."""
    with _lock:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = DATA_FILE.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump({"items": items}, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, DATA_FILE)


def update(change: Callable[[list[dict]], list[dict]]) -> list[dict]:
    """파일의 최신 목록에 change를 적용해 저장하고 결과를 반환한다.

    세션마다 들고 있는 목록으로 파일을 덮어쓰면 다른 탭/기기의 변경이 사라지므로,
    모든 변경은 이 함수를 거쳐 항상 최신 파일 위에서 이뤄진다.
    """
    with _lock:
        items = change(load())
        save(items)
        return items


def _backup_corrupt_file() -> None:
    """손상된 파일은 다음 저장에 덮어써지기 전에 따로 보관한다 (같은 내용이면 다시 복사하지 않음)."""
    backup = DATA_FILE.with_name(DATA_FILE.stem + ".corrupt.json")
    try:
        if not backup.exists() or backup.read_bytes() != DATA_FILE.read_bytes():
            shutil.copyfile(DATA_FILE, backup)
    except OSError:
        pass


def _is_valid(item) -> bool:
    return (
        isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and isinstance(item.get("name"), str)
        and item["name"].strip() != ""
    )


def _normalize(item: dict) -> dict:
    """누락되거나 형식이 잘못된 필드를 기본값으로 채운다."""
    quantity = item.get("quantity")
    if not isinstance(quantity, int) or isinstance(quantity, bool) or not 1 <= quantity <= 999:
        quantity = 1
    return {
        "id": item["id"],
        "name": item["name"],
        "quantity": quantity,
        "memo": item.get("memo") if isinstance(item.get("memo"), str) else "",
        "checked": item.get("checked") is True,
        "created_at": item.get("created_at") if isinstance(item.get("created_at"), str) else "",
    }
