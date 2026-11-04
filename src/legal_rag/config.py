"""配置读取。所有路径都相对仓库根目录，脚本从任意 cwd 启动都能工作。"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS = REPO_ROOT / "config" / "settings.yaml"
DEFAULT_CATALOG = REPO_ROOT / "config" / "corpus_catalog.yaml"


def ensure_utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def load_yaml(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} 不是合法的 YAML 映射")
    return data


def load_settings(path: Path | None = None) -> dict[str, Any]:
    """加载配置；LEGAL_RAG_SETTINGS 可指定其他配置文件。"""
    chosen = path or os.environ.get("LEGAL_RAG_SETTINGS") or DEFAULT_SETTINGS
    chosen = Path(chosen)
    if not chosen.is_absolute():
        chosen = REPO_ROOT / chosen
    cfg = load_yaml(chosen)
    cfg["_settings_file"] = str(chosen)
    # 把 paths 下的相对路径解析成绝对路径，避免依赖 cwd
    for key, value in list(cfg.get("paths", {}).items()):
        p = Path(value)
        cfg["paths"][key] = str(p if p.is_absolute() else REPO_ROOT / p)
    return cfg


def load_catalog(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or DEFAULT_CATALOG)


def data_path(cfg: dict[str, Any], key: str) -> Path:
    return Path(cfg["paths"][key])


def ensure_dir(path: Path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def env_password() -> str | None:
    return os.environ.get("NEO4J_PASSWORD")


def resolve_embedding_model(cfg: dict[str, Any], override: str | None = None) -> str:
    """优先级：命令行 > 环境变量 > settings；本地路径存在时转绝对路径。"""
    name = override or os.environ.get("LEGAL_RAG_EMBEDDING_MODEL") or cfg["embedding"]["model"]
    path = Path(name)
    if path.exists():
        return str(path.resolve())
    return name


def resolve_chroma_dir(cfg: dict[str, Any]) -> Path:
    """返回 Chroma 实际落盘目录。

    Chroma 的 Rust HNSW 写入器在非 ASCII 路径下无法落盘大规模索引
    （实测 4104 条只写出 sqlite，无 data_level0.bin）。此处在路径含中文时
    自动回退到 LOCALAPPDATA 下的 ASCII 目录，并在 manifest 中记录实际路径。
    """
    raw = os.environ.get("LEGAL_RAG_CHROMA_DIR") or cfg["paths"]["chroma_dir"]
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if all(ord(ch) < 128 for ch in str(path.resolve())):
        return path
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".cache") / "legal_rag" / "chroma"
    digest = hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()[:10]
    fallback = base / digest
    print(
        f"[提示] 仓库路径含非 ASCII 字符，Chroma 索引改存至：{fallback}"
        "（可用 LEGAL_RAG_CHROMA_DIR 覆盖）",
        file=sys.stderr,
    )
    return fallback
