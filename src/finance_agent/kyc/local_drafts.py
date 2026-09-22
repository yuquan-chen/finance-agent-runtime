from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

OCR_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
OCR_DOCUMENT_EXTENSIONS = OCR_IMAGE_EXTENSIONS | {".pdf"}
MAX_OCR_PDF_PAGES = 5


class KycDraftError(ValueError):
    """Expected validation or local OCR error for a KYC draft operation."""


class KycLocalDraftStore:
    """Persist KYC files outside session JSON while keeping them session-scoped."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_component(value: str, label: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
            raise KycDraftError(f"无效的{label}")
        return value

    def _directory(self, session_id: str, skill_key: str) -> Path:
        session = self._safe_component(session_id, "会话标识")
        skill = self._safe_component(skill_key, "Skill 标识")
        directory = self.root / session / skill
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @staticmethod
    def _accepted_extensions(accept: str) -> set[str]:
        return {
            item.strip().casefold()
            for item in accept.split(",")
            if item.strip().startswith(".")
        }

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def save_upload(
        self,
        *,
        session_id: str,
        skill_key: str,
        upload_id: str,
        filename: str,
        content_type: str,
        content: bytes,
        accept: str,
        max_size_mb: float | None,
    ) -> dict[str, Any]:
        self._safe_component(upload_id, "材料标识")
        original_name = Path(filename).name.strip()
        suffix = Path(original_name).suffix.casefold()
        allowed_extensions = self._accepted_extensions(accept)
        if not original_name or suffix not in allowed_extensions:
            allowed = ", ".join(sorted(allowed_extensions))
            raise KycDraftError(f"文件类型不支持，仅允许：{allowed}")
        if max_size_mb and len(content) > int(max_size_mb * 1024 * 1024):
            raise KycDraftError(f"文件不能超过 {max_size_mb} MB")
        if not content:
            raise KycDraftError("不能上传空文件")

        document_id = uuid.uuid4().hex
        stored_name = f"{document_id}{suffix}"
        path = self._directory(session_id, skill_key) / stored_name
        path.write_bytes(content)
        return {
            "document_id": document_id,
            "upload_id": upload_id,
            "name": original_name,
            "size": len(content),
            "type": content_type or "application/octet-stream",
            "uploaded_at": self._timestamp(),
            "ocr_status": "pending" if suffix in OCR_DOCUMENT_EXTENSIONS else "not_available",
            "ocr_message": "等待 OCR" if suffix in OCR_DOCUMENT_EXTENSIONS else "当前本地 OCR 支持 JPG、PNG、WEBP 和 PDF 文件",
            "stored_name": stored_name,
        }

    def save_inbox_upload(
        self,
        *,
        session_id: str,
        filename: str,
        content_type: str,
        content: bytes,
        max_size_mb: float | None,
    ) -> dict[str, Any]:
        """Save a chat attachment before its KYC material type is confirmed."""
        return self.save_upload(
            session_id=session_id,
            skill_key="chat_inbox",
            upload_id=f"attachment_{uuid.uuid4().hex}",
            filename=filename,
            content_type=content_type,
            content=content,
            accept=".jpg,.jpeg,.png,.webp,.pdf",
            max_size_mb=max_size_mb,
        )

    def run_ocr(self, *, session_id: str, skill_key: str, record: dict[str, Any]) -> dict[str, Any]:
        stored_name = str(record.get("stored_name") or "")
        if not re.fullmatch(r"[A-Fa-f0-9]{32}\.[a-z0-9]+", stored_name):
            raise KycDraftError("材料记录无效")
        path = self._directory(session_id, skill_key) / stored_name
        if not path.is_file():
            raise KycDraftError("未找到已上传的材料")
        if path.suffix.casefold() not in OCR_DOCUMENT_EXTENSIONS:
            return {
                **record,
                "ocr_status": "not_available",
                "ocr_message": "当前本地 OCR 支持 JPG、PNG、WEBP 和 PDF 文件；文件已保留在草稿中。",
            }
        if shutil.which("tesseract") is None:
            raise KycDraftError("本机未安装 tesseract，无法执行 OCR")
        with tempfile.TemporaryDirectory(prefix="finance-agent-ocr-") as temp_dir:
            pages = self._ocr_pages(path, Path(temp_dir))
            text = self._recognize_pages(pages)
        return {
            **record,
            "ocr_status": "completed",
            "ocr_message": "OCR 已完成，请人工核对后再填写字段。",
            "ocr_text": text,
            "ocr_completed_at": self._timestamp(),
        }

    def stored_upload_path(
        self,
        *,
        session_id: str,
        skill_key: str,
        record: dict[str, Any],
    ) -> Path:
        """Resolve a previously stored upload after validating its record."""
        stored_name = str(record.get("stored_name") or "")
        if not re.fullmatch(r"[A-Fa-f0-9]{32}\.[a-z0-9]+", stored_name):
            raise KycDraftError("材料记录无效")
        path = self._directory(session_id, skill_key) / stored_name
        if not path.is_file():
            raise KycDraftError("未找到已上传的材料")
        return path

    def promote_upload(
        self,
        *,
        session_id: str,
        source_skill_key: str,
        target_skill_key: str,
        target_upload_id: str,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        """Copy a confirmed inbox file into its KYC material slot."""
        self._safe_component(target_upload_id, "材料标识")
        stored_name = str(record.get("stored_name") or "")
        if not re.fullmatch(r"[A-Fa-f0-9]{32}\.[a-z0-9]+", stored_name):
            raise KycDraftError("材料记录无效")
        source = self._directory(session_id, source_skill_key) / stored_name
        if not source.is_file():
            raise KycDraftError("未找到待确认的材料")
        target_dir = self._directory(session_id, target_skill_key)
        target = target_dir / stored_name
        shutil.copyfile(source, target)
        return {**record, "upload_id": target_upload_id, "stored_name": stored_name}

    @staticmethod
    def _ocr_pages(path: Path, temp_dir: Path) -> list[Path]:
        if path.suffix.casefold() in OCR_IMAGE_EXTENSIONS:
            return [path]
        if shutil.which("pdftoppm") is None:
            raise KycDraftError("本机未安装 Poppler，无法识别 PDF；请安装 pdftoppm")
        prefix = temp_dir / "page"
        try:
            completed = subprocess.run(
                [
                    "pdftoppm",
                    "-png",
                    "-r",
                    "200",
                    "-f",
                    "1",
                    "-l",
                    str(MAX_OCR_PDF_PAGES),
                    str(path),
                    str(prefix),
                ],
                capture_output=True,
                check=False,
                timeout=30,
            )
        except subprocess.TimeoutExpired as error:
            raise KycDraftError("PDF 转换超时，请使用更小的文件") from error
        pages = sorted(temp_dir.glob("page-*.png"))
        if completed.returncode or not pages:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise KycDraftError(f"PDF 转换失败：{detail or '未生成可识别页面'}")
        return pages

    @staticmethod
    def _recognize_pages(pages: list[Path]) -> str:
        results: list[str] = []
        for index, page in enumerate(pages, start=1):
            try:
                completed = subprocess.run(
                    ["tesseract", str(page), "stdout", "-l", "eng+chi_sim"],
                    capture_output=True,
                    check=False,
                    timeout=30,
                )
            except subprocess.TimeoutExpired as error:
                raise KycDraftError("OCR 超时，请使用更小或更清晰的图片") from error
            page_text = completed.stdout.decode("utf-8", errors="replace").strip()
            if completed.returncode and not page_text:
                detail = completed.stderr.decode("utf-8", errors="replace").strip()
                raise KycDraftError(f"OCR 失败：{detail or 'tesseract 未返回文本'}")
            if page_text:
                results.append(page_text if len(pages) == 1 else f"[第 {index} 页]\n{page_text}")
        return "\n\n".join(results)

    def export_draft(self, *, session_id: str, skill_key: str, state: dict[str, Any]) -> Path:
        directory = self._directory(session_id, skill_key) / "exports"
        directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = directory / f"{skill_key}-draft-{timestamp}.json"
        payload = {
            "format": "finance-agent-local-kyc-draft/v1",
            "exported_at": self._timestamp(),
            "session_id": session_id,
            "skill_key": skill_key,
            "state": state,
            "boundary": "本地草稿，不代表审批结果，也未提交至 DogPay。",
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def delete_session(self, session_id: str) -> int:
        directory = self.root / self._safe_component(session_id, "会话标识")
        if not directory.exists():
            return 0
        count = sum(1 for path in directory.rglob("*") if path.is_file())
        shutil.rmtree(directory)
        return count
