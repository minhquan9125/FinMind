"""Cancel an in-flight chat turn when its HTTP client disconnects."""
import asyncio


async def while_connected(request, operation):
    finished = asyncio.Event()
    async def disconnected():
        while not finished.is_set():
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.1)

    work = asyncio.create_task(operation)
    watcher = asyncio.create_task(disconnected())
    try:
        done, _ = await asyncio.wait((work, watcher), return_when=asyncio.FIRST_COMPLETED)
        if work in done:
            return await work
        # Await cancellation so the session store releases its bounded DB lease.
        raise asyncio.CancelledError()
    finally:
        finished.set()
        for task in (work, watcher):
            if not task.done():
                task.cancel()
        await asyncio.gather(work, watcher, return_exceptions=True)
