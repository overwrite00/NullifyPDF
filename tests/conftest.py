"""Pytest configuration shared by the test suite."""

import pathlib
import sys


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
root_str = str(PROJECT_ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)


def pytest_sessionfinish(session, exitstatus):
    """Destroy Qt objects while QApplication is still alive.

    Dialogs and windows left in reference cycles would otherwise be collected
    at interpreter shutdown, after the application object, which crashes the
    process on some platforms even though every test passed.
    """
    try:
        import gc

        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.closeAllWindows()
            app.processEvents()
        gc.collect()
        if app is not None:
            app.processEvents()
    except Exception:
        pass
