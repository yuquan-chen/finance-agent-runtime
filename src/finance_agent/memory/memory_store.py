"""文件化 Memory 存储。

每条记忆一个 .md 文件，带 frontmatter 元数据。
MEMORY.md 作为索引文件。
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from finance_agent.memory.taxonomy import MemoryType


@dataclass
class MemoryFile:
    """单条记忆文件。"""

    name: str
    description: str
    type: MemoryType
    content: str
    path: Path
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    session_id: str = ""

    def to_frontmatter(self) -> str:
        """生成 frontmatter 格式。"""
        return f"""---
name: {self.name}
description: {self.description}
type: {self.type.value}
created_at: {self.created_at}
updated_at: {self.updated_at}
session_id: {self.session_id}
---

{self.content}"""

    def to_manifest_entry(self) -> str:
        """生成 MEMORY.md 索引条目。"""
        return f"- [{self.name}]({self.path.name}) — {self.description}"

    @classmethod
    def from_file(cls, path: Path) -> MemoryFile | None:
        """从文件加载记忆。"""
        if not path.exists() or not path.suffix == ".md":
            return None

        text = path.read_text(encoding="utf-8")

        # 解析 frontmatter
        frontmatter_match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not frontmatter_match:
            return None

        frontmatter_str = frontmatter_match.group(1)
        content = frontmatter_match.group(2).strip()

        # 解析 frontmatter 字段
        frontmatter = {}
        for line in frontmatter_str.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                frontmatter[key.strip()] = value.strip()

        # 验证必填字段
        name = frontmatter.get("name", path.stem)
        description = frontmatter.get("description", "")
        type_str = frontmatter.get("type", "project")

        try:
            mem_type = MemoryType(type_str)
        except ValueError:
            mem_type = MemoryType.PROJECT

        return cls(
            name=name,
            description=description,
            type=mem_type,
            content=content,
            path=path,
            created_at=frontmatter.get("created_at", ""),
            updated_at=frontmatter.get("updated_at", ""),
            session_id=frontmatter.get("session_id", ""),
        )


class MemoryStore:
    """文件化 Memory 存储。"""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_path / "MEMORY.md"

    def list_memories(self) -> list[MemoryFile]:
        """列出所有记忆文件。"""
        memories = []
        for path in self.base_path.glob("*.md"):
            if path.name == "MEMORY.md":
                continue
            memory = MemoryFile.from_file(path)
            if memory:
                memories.append(memory)
        return memories

    def get_memory(self, name: str) -> MemoryFile | None:
        """获取指定名称的记忆。"""
        path = self.base_path / f"{name}.md"
        return MemoryFile.from_file(path)

    def list_session_memories(self, session_id: str) -> list[MemoryFile]:
        """只返回属于当前会话的记忆；未标记的旧记录不进入新会话。"""
        return [memory for memory in self.list_memories() if memory.session_id == session_id]

    def save_memory(self, memory: MemoryFile) -> MemoryFile:
        """保存记忆到文件。"""
        # 更新时间戳
        memory.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # 写入文件
        file_path = self.base_path / f"{memory.name}.md"
        file_path.write_text(memory.to_frontmatter(), encoding="utf-8")
        memory.path = file_path

        # 更新索引
        self._update_index()

        return memory

    def delete_memory(self, name: str) -> bool:
        """删除指定名称的记忆。"""
        path = self.base_path / f"{name}.md"
        if path.exists():
            path.unlink()
            self._update_index()
            return True
        return False

    def delete_session_memories(self, session_id: str) -> int:
        """永久移除一个会话的文件型记忆，并重建索引。"""
        deleted = 0
        for memory in self.list_session_memories(session_id):
            if memory.path.exists():
                memory.path.unlink()
                deleted += 1
        if deleted:
            self._update_index()
        return deleted

    def _update_index(self) -> None:
        """更新 MEMORY.md 索引文件。"""
        memories = self.list_memories()

        # 按类型分组
        grouped: dict[MemoryType, list[MemoryFile]] = {t: [] for t in MemoryType}
        for memory in memories:
            grouped[memory.type].append(memory)

        # 生成索引内容
        lines = ["# Memory Index\n"]
        for mem_type in MemoryType:
            type_memories = grouped[mem_type]
            if not type_memories:
                continue
            lines.append(f"\n## {mem_type.value}\n")
            for memory in sorted(type_memories, key=lambda m: m.name):
                lines.append(memory.to_manifest_entry())

        self.index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def get_manifest(self, limit: int = 20, session_id: str | None = None) -> str:
        """获取轻量级 manifest（用于 LLM 选择记忆）。"""
        memories = self.list_session_memories(session_id) if session_id is not None else self.list_memories()

        # 按更新时间排序，取最新的
        memories.sort(key=lambda m: m.updated_at, reverse=True)
        memories = memories[:limit]

        lines = ["可用的记忆文件：\n"]
        for memory in memories:
            lines.append(f"- [{memory.type.value}] {memory.name}: {memory.description}")
        return "\n".join(lines)

    def save_query_history(self, user_query: str, result_summary: str, tables: list[str] | None = None, fields: list[str] | None = None, session_id: str = "") -> MemoryFile:
        """保存查询历史到 memory（保存用户意图，不保存 SQL）。"""
        # 生成唯一的名称
        timestamp = int(time.time())
        name = f"query_history_{timestamp}_{uuid.uuid4().hex[:8]}"

        # 构建内容（只保存用户意图和结果，不保存 SQL）
        content = f"""## 用户查询
{user_query}

## 涉及的表
{', '.join(tables) if tables else '未知'}

## 涉及的字段
{', '.join(fields[:10]) if fields else '未知'}

## 结果摘要
{result_summary}
"""

        # 创建 memory 文件
        memory = MemoryFile(
            name=name,
            description=f"查询: {user_query[:50]}",
            type=MemoryType.PROJECT,
            content=content,
            path=self.base_path / f"{name}.md",
            session_id=session_id,
        )

        return self.save_memory(memory)

    def get_recent_queries(self, limit: int = 3, session_id: str | None = None) -> list[dict[str, Any]]:
        """获取最近的查询历史。"""
        memories = self.list_session_memories(session_id) if session_id is not None else self.list_memories()

        # 过滤查询历史
        query_memories = [m for m in memories if m.name.startswith("query_history_")]

        # 按更新时间排序，取最新的
        query_memories.sort(key=lambda m: m.updated_at, reverse=True)
        query_memories = query_memories[:limit]

        # 解析内容
        results = []
        for memory in query_memories:
            # 提取查询、表、字段、结果摘要
            query_match = re.search(r"## 用户查询\n(.*?)\n## 涉及的表", memory.content, re.DOTALL)
            tables_match = re.search(r"## 涉及的表\n(.*?)\n## 涉及的字段", memory.content, re.DOTALL)
            fields_match = re.search(r"## 涉及的字段\n(.*?)\n## 结果摘要", memory.content, re.DOTALL)
            result_match = re.search(r"## 结果摘要\n(.*?)$", memory.content, re.DOTALL)

            results.append({
                "user_query": query_match.group(1).strip() if query_match else "",
                "tables": tables_match.group(1).strip() if tables_match else "",
                "fields": fields_match.group(1).strip() if fields_match else "",
                "result_summary": result_match.group(1).strip() if result_match else "",
            })

        return results
