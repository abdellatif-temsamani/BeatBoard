import asyncio
import threading


def run_in_main_thread(func, *args, **kwargs):
    loop = asyncio.get_event_loop()

    # Always create a future so the caller can await
    fut = loop.create_future()

    def call_and_resolve():
        try:
            result = func(*args, **kwargs)
            loop.call_soon_threadsafe(fut.set_result, result)
        except Exception as e:
            loop.call_soon_threadsafe(fut.set_exception, e)

    if threading.current_thread() is threading.main_thread():
        # Already on main thread → call directly but still resolve async
        loop.call_soon(call_and_resolve)
    else:
        # Not main thread → run in a thread that jumps back to main thread
        threading.Thread(target=call_and_resolve).start()

    return fut
