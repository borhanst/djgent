"""Django-backed LangGraph checkpoint saver."""

from __future__ import annotations

import asyncio
import base64
import pickle
from typing import Any, Dict, Iterable, Iterator, Optional


try:  # pragma: no cover - exercised when langgraph is installed.
    from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple
except Exception:  # pragma: no cover - keeps djgent importable in lean envs.
    BaseCheckpointSaver = object  # type: ignore
    CheckpointTuple = None  # type: ignore


def _serialize(value: Any) -> str:
    return base64.b64encode(pickle.dumps(value)).decode("ascii")


def _deserialize(value: str) -> Any:
    return pickle.loads(base64.b64decode(value.encode("ascii")))


def _configurable(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return dict((config or {}).get("configurable") or {})


def _thread_id(config: Dict[str, Any]) -> str:
    value = _configurable(config).get("thread_id")
    if not value:
        raise ValueError("LangGraph checkpoint config requires configurable.thread_id.")
    return str(value)


def _checkpoint_ns(config: Optional[Dict[str, Any]]) -> str:
    return str(_configurable(config).get("checkpoint_ns") or "")


def _checkpoint_id(config: Optional[Dict[str, Any]]) -> str:
    return str(_configurable(config).get("checkpoint_id") or "")


def _make_checkpoint_tuple(
    *,
    config: Dict[str, Any],
    checkpoint: Any,
    metadata: Dict[str, Any],
    parent_config: Optional[Dict[str, Any]],
    pending_writes: list[Any],
) -> Any:
    if CheckpointTuple is None:
        return {
            "config": config,
            "checkpoint": checkpoint,
            "metadata": metadata,
            "parent_config": parent_config,
            "pending_writes": pending_writes,
        }
    try:
        return CheckpointTuple(
            config=config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=pending_writes,
        )
    except TypeError:
        return CheckpointTuple(config, checkpoint, metadata, parent_config, pending_writes)


class DjangoCheckpointSaver(BaseCheckpointSaver):  # type: ignore[misc]
    """Persist LangGraph checkpoints in Djgent's Django database."""

    def get_tuple(self, config: Dict[str, Any]) -> Any:
        from djgent.models import LangGraphCheckpoint, LangGraphCheckpointWrite

        thread_id = _thread_id(config)
        checkpoint_ns = _checkpoint_ns(config)
        checkpoint_id = _checkpoint_id(config)
        queryset = LangGraphCheckpoint.objects.filter(
            thread_id=thread_id,
            checkpoint_ns=checkpoint_ns,
        )
        if checkpoint_id:
            queryset = queryset.filter(checkpoint_id=checkpoint_id)
        row = queryset.order_by("-created_at").first()
        if row is None:
            return None

        read_config = dict(row.config or {})
        configurable = dict(read_config.get("configurable") or {})
        configurable.update(
            {
                "thread_id": row.thread_id,
                "checkpoint_ns": row.checkpoint_ns,
                "checkpoint_id": row.checkpoint_id,
            }
        )
        read_config["configurable"] = configurable

        parent_config = None
        if row.parent_checkpoint_id:
            parent_config = {
                "configurable": {
                    "thread_id": row.thread_id,
                    "checkpoint_ns": row.checkpoint_ns,
                    "checkpoint_id": row.parent_checkpoint_id,
                }
            }

        writes = []
        for item in LangGraphCheckpointWrite.objects.filter(
            thread_id=row.thread_id,
            checkpoint_ns=row.checkpoint_ns,
            checkpoint_id=row.checkpoint_id,
        ).order_by("idx"):
            writes.append((item.task_id, item.channel, _deserialize(item.value)))

        return _make_checkpoint_tuple(
            config=read_config,
            checkpoint=_deserialize(row.checkpoint),
            metadata=row.metadata or {},
            parent_config=parent_config,
            pending_writes=writes,
        )

    def list(
        self,
        config: Optional[Dict[str, Any]],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Iterator[Any]:
        from djgent.models import LangGraphCheckpoint

        queryset = LangGraphCheckpoint.objects.all()
        if config:
            configurable = _configurable(config)
            if configurable.get("thread_id"):
                queryset = queryset.filter(thread_id=str(configurable["thread_id"]))
            queryset = queryset.filter(checkpoint_ns=_checkpoint_ns(config))
        if filter:
            for key, value in filter.items():
                queryset = queryset.filter(**{f"metadata__{key}": value})
        if before and _checkpoint_id(before):
            marker = (
                LangGraphCheckpoint.objects.filter(
                    thread_id=_thread_id(before),
                    checkpoint_ns=_checkpoint_ns(before),
                    checkpoint_id=_checkpoint_id(before),
                )
                .values_list("created_at", flat=True)
                .first()
            )
            if marker is not None:
                queryset = queryset.filter(created_at__lt=marker)

        rows = queryset.order_by("-created_at")
        if limit is not None:
            rows = rows[:limit]
        for row in rows:
            yield self.get_tuple(
                {
                    "configurable": {
                        "thread_id": row.thread_id,
                        "checkpoint_ns": row.checkpoint_ns,
                        "checkpoint_id": row.checkpoint_id,
                    }
                }
            )

    def put(
        self,
        config: Dict[str, Any],
        checkpoint: Any,
        metadata: Dict[str, Any],
        new_versions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from djgent.models import LangGraphCheckpoint

        thread_id = _thread_id(config)
        checkpoint_ns = _checkpoint_ns(config)
        checkpoint_id = str(
            getattr(checkpoint, "id", None)
            or (checkpoint.get("id") if isinstance(checkpoint, dict) else "")
            or _checkpoint_id(config)
        )
        if not checkpoint_id:
            raise ValueError("LangGraph checkpoint payload requires an id.")

        LangGraphCheckpoint.objects.update_or_create(
            thread_id=thread_id,
            checkpoint_ns=checkpoint_ns,
            checkpoint_id=checkpoint_id,
            defaults={
                "parent_checkpoint_id": _checkpoint_id(config),
                "config": config,
                "metadata": metadata or {},
                "checkpoint": _serialize(checkpoint),
            },
        )
        next_config = dict(config or {})
        configurable = dict(next_config.get("configurable") or {})
        configurable.update(
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        )
        next_config["configurable"] = configurable
        return next_config

    def put_writes(
        self,
        config: Dict[str, Any],
        writes: Iterable[Any],
        task_id: str,
        task_path: str = "",
    ) -> None:
        from djgent.models import LangGraphCheckpointWrite

        thread_id = _thread_id(config)
        checkpoint_ns = _checkpoint_ns(config)
        checkpoint_id = _checkpoint_id(config)
        for idx, item in enumerate(writes):
            channel, value = item
            LangGraphCheckpointWrite.objects.update_or_create(
                thread_id=thread_id,
                checkpoint_ns=checkpoint_ns,
                checkpoint_id=checkpoint_id,
                task_id=str(task_id),
                idx=idx,
                defaults={
                    "channel": str(channel),
                    "value": _serialize(value),
                },
            )

    def delete_thread(self, thread_id: str) -> None:
        from djgent.models import LangGraphCheckpoint, LangGraphCheckpointWrite

        LangGraphCheckpoint.objects.filter(thread_id=str(thread_id)).delete()
        LangGraphCheckpointWrite.objects.filter(thread_id=str(thread_id)).delete()

    async def aget_tuple(self, config: Dict[str, Any]) -> Any:
        return await asyncio.to_thread(self.get_tuple, config)

    async def alist(
        self,
        config: Optional[Dict[str, Any]],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> list[Any]:
        return await asyncio.to_thread(
            lambda: list(
                self.list(config, filter=filter, before=before, limit=limit)
            )
        )

    async def aput(
        self,
        config: Dict[str, Any],
        checkpoint: Any,
        metadata: Dict[str, Any],
        new_versions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self.put, config, checkpoint, metadata, new_versions
        )

    async def aput_writes(
        self,
        config: Dict[str, Any],
        writes: Iterable[Any],
        task_id: str,
        task_path: str = "",
    ) -> None:
        await asyncio.to_thread(
            self.put_writes, config, writes, task_id, task_path
        )

    async def adelete_thread(self, thread_id: str) -> None:
        await asyncio.to_thread(self.delete_thread, thread_id)
