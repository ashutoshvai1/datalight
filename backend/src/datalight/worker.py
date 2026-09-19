import logging
import signal
import threading
from pathlib import Path

from . import service
from .config import Settings
from .db import connect
from .ingestion import SourceError

log = logging.getLogger("datalight.worker")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings()
    _, factory = connect(settings.database_url)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        try:
            service.bootstrap(factory, settings)
            break
        except SourceError as exc:
            log.warning("%s", exc)
            Path("/tmp/datalight-worker-heartbeat").touch()
            stop.wait(5)
        except Exception as exc:
            log.warning("Startup is waiting for storage (%s).", type(exc).__name__)
            stop.wait(5)

    def loop(kind):
        while not stop.is_set():
            try:
                claimed = service.claim(factory, kind)
                if not claimed:
                    stop.wait(0.2 if kind == "replay" else 1)
                    continue
                job_id, token = claimed
                try:
                    action = service.replay if kind == "replay" else service.interpret
                    action(factory, settings, job_id, token)
                except SourceError as exc:
                    service.fail_job(factory, job_id, token, str(exc))
                except Exception as exc:
                    # Do not log raw rows, credentials, SQL parameter payloads, or request bodies.
                    log.error("Job %s failed (%s).", job_id, type(exc).__name__)
                    service.fail_job(
                        factory,
                        job_id,
                        token,
                        f"Processing failed ({type(exc).__name__}). Start a new analysis after resolving the error.",
                    )
            except Exception as exc:
                log.warning(
                    "Worker storage unavailable (%s); leases allow recovery.", type(exc).__name__
                )
                stop.wait(2)

    threads = [
        threading.Thread(target=loop, args=(kind,), name=kind, daemon=True)
        for kind in ("replay", "interpretation", "finding_interpretation")
    ]
    for thread in threads:
        thread.start()
    while not stop.wait(1):
        if not all(t.is_alive() for t in threads):
            raise RuntimeError("A worker loop stopped unexpectedly.")
        Path("/tmp/datalight-worker-heartbeat").touch()
    for thread in threads:
        thread.join(timeout=settings.llm_timeout + 5)


if __name__ == "__main__":
    main()
