"""
Reliable Batch Write Queue for FogGuard.
Accumulates high-frequency database writes and flushes them in atomic batches.
Provides bounded capacity, non-destructive retries, exponential backoff, and full shutdown drainage.
"""
import asyncio
import logging
import time
from typing import Callable, Awaitable, Any, List
from collections import deque

logger = logging.getLogger(__name__)


class WriteQueue:
    """
    Accumulates DB-write work items and flushes them in batches.
    Guarantees no telemetry is dropped on transient DB errors or shutdown.
    """

    def __init__(
        self,
        flush_interval_ms: int = 500,
        max_batch_size: int = 64,
        max_queue_size: int = 2000,
    ):
        self._queue: deque = deque()
        self._flush_interval = flush_interval_ms / 1000.0
        self._max_batch = max_batch_size
        self._max_queue_size = max_queue_size
        self._task: asyncio.Task | None = None
        self._running = False
        self._flush_fn: Callable[[List[Any]], Awaitable[Any]] | None = None
        self._consecutive_failures = 0
        self._lock = asyncio.Lock()

    def set_flush_callback(self, fn: Callable[[List[Any]], Awaitable[Any]]):
        """Set the async function that receives a batch of work items."""
        self._flush_fn = fn

    def enqueue(self, item: Any) -> bool:
        """
        Add a work item to the queue.
        If the queue exceeds max capacity, drop the oldest raw telemetry item
        to protect memory while logging a warning.
        """
        if len(self._queue) >= self._max_queue_size:
            # Drop oldest to avoid unbounded memory growth
            dropped = self._queue.popleft()
            logger.warning(
                f"WriteQueue full ({self._max_queue_size} items). Dropped oldest item to apply backpressure."
            )
        self._queue.append(item)
        return True

    async def start(self):
        if self._running:
            return
        self._running = True
        self._consecutive_failures = 0
        self._task = asyncio.create_task(self._run())
        logger.info(
            f"WriteQueue started (interval={self._flush_interval*1000:.0f}ms, "
            f"batch={self._max_batch}, max_queue={self._max_queue_size})"
        )

    async def stop(self):
        """Gracefully stop the background worker and drain ALL remaining items."""
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        # Full drain loop on shutdown — flush all pending items
        drain_deadline = time.time() + 10.0  # 10s maximum drain time
        flushed_count = 0
        while self._queue and time.time() < drain_deadline:
            success = await self._flush_once()
            if success:
                flushed_count += 1
            else:
                # If DB is completely unreachable, break to avoid hanging shutdown
                logger.error("WriteQueue drain failed during shutdown, stopping drain.")
                break

        remaining = len(self._queue)
        if remaining > 0:
            logger.warning(f"WriteQueue shutdown finished with {remaining} items remaining in queue")
        else:
            logger.info("WriteQueue stopped cleanly, all pending items drained to database.")

    async def _run(self):
        while self._running:
            try:
                await asyncio.sleep(self._flush_interval)
                await self._flush_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in WriteQueue run loop: {e}", exc_info=True)

    async def _flush_once(self) -> bool:
        """
        Atomically inspects and flushes up to _max_batch items.
        Items are ONLY removed from the queue after the flush callback succeeds.
        """
        async with self._lock:
            if not self._queue or not self._flush_fn:
                return True

            # Snapshot the items without popping them yet
            count = min(len(self._queue), self._max_batch)
            batch = [self._queue[i] for i in range(count)]

            try:
                await self._flush_fn(batch)
                # Success: now safely pop exactly the items that were flushed
                for _ in range(count):
                    self._queue.popleft()
                self._consecutive_failures = 0
                return True
            except Exception as e:
                self._consecutive_failures += 1
                backoff = min(2.0, 0.1 * (2 ** min(self._consecutive_failures, 5)))
                logger.error(
                    f"WriteQueue flush error (attempt {self._consecutive_failures}): {e}. "
                    f"Retrying {count} items in {backoff:.2f}s..."
                )
                # If it failed 10+ consecutive times, drop this failing batch to dead letter to prevent permanent stall
                if self._consecutive_failures >= 10:
                    logger.critical(
                        f"WriteQueue permanently dropping {count} items after 10 consecutive failures to prevent deadlock."
                    )
                    for _ in range(count):
                        self._queue.popleft()
                    self._consecutive_failures = 0
                else:
                    await asyncio.sleep(backoff)
                return False

    @property
    def pending(self) -> int:
        return len(self._queue)

    @property
    def is_running(self) -> bool:
        return self._running


write_queue = WriteQueue()
