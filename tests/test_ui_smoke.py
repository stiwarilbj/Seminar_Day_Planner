from __future__ import annotations


def test_ui_modules_import() -> None:
    from seminar_day_planner.ui import app, theme
    from seminar_day_planner.ui.pages import (
        builder,
        imports,
        login,
        overview,
        results,
        seminars,
        submit,
    )

    assert app.ApplicationContext
    assert theme.THEME_CSS
    assert all((builder, imports, login, overview, results, seminars, submit))

