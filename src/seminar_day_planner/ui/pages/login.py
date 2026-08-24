from __future__ import annotations

import secrets

from nicegui import app, ui

from seminar_day_planner.ui.app import ApplicationContext
from seminar_day_planner.ui.theme import apply_theme, brand, labeled_field


def register_login_page(context: ApplicationContext) -> None:
    @ui.page("/staff/login")
    def staff_login() -> None:
        apply_theme("Staff sign in")
        ui.query(".nicegui-content").classes("p-0")
        if app.storage.user.get("authenticated") is True:
            ui.navigate.to("/staff/overview")
            return

        with ui.element("main").classes("login-page"):
            with ui.column().classes("surface login-card"):
                brand(compact=True)
                with ui.column().classes("gap-1"):
                    ui.label("Staff sign in").classes("page-title !text-[26px]")
                    ui.label(
                        "Use the planner password to open imports, scheduling, and results."
                    ).classes("page-subtitle !mt-0")
                with ui.column().classes("w-full gap-1"):
                    labeled_field("Password")
                    password = ui.input(
                        placeholder="Enter staff password",
                        password=True,
                        password_toggle_button=True,
                    ).props("outlined autocomplete='current-password'").classes("w-full")
                    error = ui.label("That password did not match.").classes(
                        "validation-message"
                    )
                    error.set_visibility(False)

                def sign_in() -> None:
                    if secrets.compare_digest(
                        str(password.value or ""), context.settings.staff_password
                    ):
                        app.storage.user["authenticated"] = True
                        ui.navigate.to("/staff/overview")
                    else:
                        error.set_visibility(True)
                        password.run_method("focus")

                password.on("keydown.enter", sign_in)
                ui.button("Sign in", icon="login", on_click=sign_in).props(
                    "no-caps unelevated"
                ).classes("primary-btn w-full")
                ui.link("Back to the student form", "/submit").classes(
                    "text-[12px] text-[#0756c9] self-center"
                )

