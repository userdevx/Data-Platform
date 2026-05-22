import time

from run_ingestion import main as run_once
from engine.logger import log_error, log_info
from engine.recovery import run_recovery_check


INTERVAL_SECONDS = 10


def main():
    recovery_report = run_recovery_check()
    log_info("live_ingestion_recovery", str(recovery_report))

    log_info(
        "live_ingestion_start",
        f"Live ingestion started interval_seconds={INTERVAL_SECONDS}"
    )

    while True:
        try:
            run_once()
            log_info("live_ingestion_cycle", "Ingestion cycle completed")

        except KeyboardInterrupt:
            log_info("live_ingestion_stop", "Live ingestion stopped by user")
            print("Live ingestion stopped")
            break

        except Exception as error:
            log_error("live_ingestion_error", str(error))
            print({"error": str(error)})

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
