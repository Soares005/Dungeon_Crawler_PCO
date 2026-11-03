"""Elemental Chaos - entry point.

Run with:  python main.py
"""
import sys
import traceback


def main():
    try:
        import pygame  # noqa: F401  (checked here to give a friendly message)
    except ImportError:
        print("Pygame is not installed. Install the requirements first:\n"
              "    pip install -r requirements.txt")
        return 1

    from settings import CRASH_LOG
    from game import Game

    try:
        Game().run()
    except Exception:  # last line of defence: never lose the error silently
        details = traceback.format_exc()
        try:
            with open(CRASH_LOG, "w", encoding="utf-8") as file:
                file.write(details)
        except OSError:
            pass
        print(details)
        print(f"Elemental Chaos stopped because of an unexpected error. Details saved to {CRASH_LOG}")
        return 1
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
