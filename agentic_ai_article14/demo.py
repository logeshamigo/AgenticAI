from pathlib import Path
from tempfile import TemporaryDirectory

from coordination import Coordinator, Specialist


def main():
    with TemporaryDirectory() as folder:
        root = Path(folder)
        coordinator_db = root / "coordinator.db"
        specialist = Specialist(root / "specialist.db")
        coordinator = Coordinator(coordinator_db)
        key = "q3-review-042:pricing:1"
        coordinator.prepare(key, "Estimate Q3 pricing impact for enterprise renewals", deadline=100)

        try:
            coordinator.dispatch(specialist, key, 80, lose_ack=True)
        except TimeoutError:
            print("Submission outcome unknown to coordinator.")

        coordinator = Coordinator(coordinator_db)
        coordinator.dispatch(specialist, key, 85)
        task_id = coordinator.state(key)["task_id"]
        print(f"Recovered remote task {task_id} after coordinator restart.")

        coordinator.finalize(key)
        specialist.finish(task_id, "Estimated impact: -4% for the modeled renewal cohort.")
        coordinator.request_cancel(specialist, key, 103)
        state = coordinator.state(key)

        print(f"Cancellation requested: {bool(state['cancel_requested'])}")
        print(f"Remote outcome: {state['remote_status']}")
        print(f"Remote finding: {state['remote_finding']}")
        print(f"Finding adopted into report: {state['adopted_finding']}")


if __name__ == "__main__":
    main()
