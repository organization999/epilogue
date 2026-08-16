from __future__ import annotations

from .collections.stack import Stack
from .monitor           import StackMonitor

def main() -> int:
    print("--- Initializing Epilogue Engine ---")

    # 1. Set up our tracked infrastructure
    monitor: StackMonitor[str] = StackMonitor[str]()
    stack: Stack[str] = Stack[str](cap=3)

    # Log initial creation state
    monitor.log("INIT", None, stack.save())

    # 2. Simulate standard runtime behavior
    print("\nExecuting user actions...")

    stack.push("OpenFileWindow")
    monitor.log("PUSH", "OpenFileWindow", stack.save())

    stack.push("RenderTextBuffer")
    monitor.log("PUSH", "RenderTextBuffer", stack.save())

    # 3. Capture a healthy system checkpoint
    print("[Checkpoint Saved] Application state is stable.")
    stable_checkpoint = stack.save()

    # 4. Trigger a processing action followed by an error
    stack.push("LoadHeavyPlugin")
    monitor.log("PUSH", "LoadHeavyPlugin", stack.save())

    print("\nSimulating critical failure...")
    try:
        # This push will breach capacity (3) and throw an exception
        stack.push("RenderOverflowCache")
    except RuntimeError as error:
        print(f"[CRASH DETECTED] Error Message: '{error}'")
        monitor.log("CRASH_BUFFER_FULL", "RenderOverflowCache", stack.save())

        print("\n--- RECOVERY INITIATED ---")
        print("Reverting system state back to the last stable snapshot...")
        stack.restore(stable_checkpoint)
        monitor.log("RESTORE", None, stack.save())

    # 5. Output the history ledger captured by our monitor
    print("\nPrinting Epilogue execution summary ledger:\n")
    print(monitor.dump())

    print(f"\nFinal active stack state: {stack.save().data}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
