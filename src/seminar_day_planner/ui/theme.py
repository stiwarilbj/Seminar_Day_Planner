from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from nicegui import app, ui

THEME_CSS = """
:root {
  --blue-25: #f6faff;
  --blue-50: #f1f7ff;
  --blue-100: #e6f1ff;
  --blue-200: #cddff5;
  --blue-300: #a8c7ec;
  --blue-600: #0864e8;
  --blue-700: #0756c9;
  --navy-950: #0d214f;
  --navy-700: #344c73;
  --muted: #627491;
  --surface: #ffffff;
  --success: #24a66a;
  --success-soft: #e9f8f0;
  --warning: #f59e0b;
  --warning-soft: #fff5e5;
  --danger: #ef4444;
  --danger-soft: #fff0f0;
  --shadow: 0 14px 34px rgba(42, 84, 132, 0.08);
}

* { box-sizing: border-box; }
html, body { background: var(--blue-25); color: var(--navy-950); }
body, .q-field, .q-btn, .q-table, .q-menu {
  font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
body { margin: 0; }
.nicegui-content { padding: 0 !important; gap: 0 !important; max-width: none !important; }
.app-shell { width: 100%; min-height: 100vh; align-items: stretch; background: var(--blue-25); gap: 0; }
.planner-sidebar {
  position: fixed; inset: 0 auto 0 0; width: 232px; min-height: 100vh; padding: 24px 16px 18px;
  background: #f3f9ff;
  border-right: 1px solid var(--blue-200); z-index: 20;
}
.brand-row { gap: 12px; padding: 0 5px 26px; align-items: center; }
.brand-mark { color: var(--blue-600); font-size: 29px; }
.brand-name { font-size: 20px; line-height: 1.05; font-weight: 750; letter-spacing: -0.02em; }
.nav-stack { width: 100%; gap: 8px; }
.nav-item.q-btn {
  width: 100%; justify-content: flex-start; min-height: 46px; padding: 0 13px; border-radius: 8px;
  color: var(--navy-950); font-size: 14px; font-weight: 560; text-transform: none; box-shadow: none;
}
.nav-item .q-btn__content { justify-content: flex-start; gap: 12px; }
.nav-item .q-icon { color: #5d7291; font-size: 22px; }
.nav-item:hover { background: var(--blue-100); }
.nav-item.active { color: #fff; background: var(--blue-600); }
.nav-item.active .q-icon { color: #fff; }
.sidebar-footer { margin-top: auto; width: 100%; padding: 18px 10px 0; border-top: 1px solid var(--blue-200); }
.school-name { font-size: 13px; line-height: 1.35; font-weight: 700; }
.staff-profile { margin-top: 18px; gap: 10px; align-items: center; }
.profile-avatar { background: #d9eafb; color: #365372; }
.profile-name { font-size: 12px; font-weight: 650; }
.profile-role { font-size: 11px; color: var(--muted); }

.planner-main { margin-left: 232px; width: calc(100% - 232px); min-height: 100vh; padding: 26px 28px 38px; gap: 18px; }
.page-header { width: 100%; align-items: flex-start; justify-content: space-between; gap: 24px; }
.page-title { font-size: 29px; line-height: 1.12; font-weight: 780; letter-spacing: -0.035em; margin: 0; }
.page-subtitle { color: var(--navy-700); font-size: 14px; margin-top: 6px; }
.header-actions { gap: 12px; align-items: center; }
.mobile-menu { display: none; }
.primary-btn.q-btn, .secondary-btn.q-btn, .quiet-btn.q-btn {
  min-height: 43px; border-radius: 7px; padding: 0 18px; text-transform: none; font-size: 13px; font-weight: 680;
}
.primary-btn.q-btn { background: var(--blue-600); color: #fff; box-shadow: 0 8px 18px rgba(8, 100, 232, .16); }
.primary-btn.q-btn:hover { background: var(--blue-700); }
.secondary-btn.q-btn { color: var(--navy-950); background: #fff; border: 1px solid #b9cbe1; }
.quiet-btn.q-btn { color: var(--blue-700); background: transparent; padding-inline: 10px; }
.page-content { width: 100%; min-width: 0; gap: 16px; }
.page-content > * { min-width: 0; max-width: 100%; }

.surface { background: var(--surface); border: 1px solid var(--blue-200); border-radius: 12px; box-shadow: var(--shadow); }
.open-surface { min-width: 0; max-width: 100%; background: var(--surface); border: 1px solid var(--blue-200); border-radius: 10px; }
.section-pad { padding: 18px; }
.section-title { font-size: 16px; font-weight: 750; letter-spacing: -0.01em; }
.section-copy { color: var(--muted); font-size: 12px; line-height: 1.45; }
.divider { width: 100%; height: 1px; background: var(--blue-200); }

.metric-strip { width: 100%; min-height: 92px; padding: 16px 20px; gap: 0; align-items: stretch; }
.metric-item { flex: 1 1 0; min-width: 0; padding: 0 24px; justify-content: center; }
.metric-item:first-child { padding-left: 10px; }
.metric-item + .metric-item { border-left: 1px solid var(--blue-200); }
.metric-icon { color: var(--blue-600); font-size: 32px; }
.metric-icon.success { color: var(--success); }
.metric-value { font-size: 14px; font-weight: 760; }
.metric-label { font-size: 11px; color: var(--muted); margin-top: 2px; }
.metric-check { color: var(--success); margin-left: auto; }

.two-column { width: 100%; display: grid !important; grid-template-columns: minmax(0, 1.2fr) minmax(330px, .95fr); gap: 16px; }
.overview-grid { width: 100%; display: grid !important; grid-template-columns: 1.25fr .75fr; gap: 16px; }
.form-grid { width: 100%; display: grid !important; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 18px; }
.student-about-grid { width: 100%; display: grid !important; grid-template-columns: 1.05fr 1.05fr .95fr; gap: 18px; }
.student-layout { width: 100%; display: grid !important; grid-template-columns: minmax(0, 1fr) 310px; gap: 0; }
.import-layout { width: 100%; display: grid !important; grid-template-columns: minmax(0, 1fr) 265px; gap: 16px; }

.field-label { font-size: 12px; color: var(--navy-950); font-weight: 610; margin-bottom: 5px; }
.q-field--outlined .q-field__control { border-radius: 7px; min-height: 42px; background: #fff; }
.q-field--outlined .q-field__control:before { border-color: #b9cbe1; }
.q-field--outlined.q-field--focused .q-field__control:after { border-color: var(--blue-600); border-width: 1.5px; }
.q-field__native, .q-field__input, .q-field__label { color: var(--navy-950); font-size: 13px; }
.q-textarea .q-field__native { line-height: 1.5; }
.q-toggle__label, .q-checkbox__label, .q-radio__label { font-size: 13px; }
.q-btn-toggle { border: 1px solid #b9cbe1; border-radius: 7px; overflow: hidden; box-shadow: none; }
.q-btn-toggle .q-btn { min-height: 40px; color: var(--navy-950); background: #fff; }
.q-btn-toggle .q-btn.bg-primary { color: var(--blue-700) !important; background: var(--blue-50) !important; }

.status-ok { color: var(--success); }
.status-warning { color: var(--warning); }
.status-error { color: var(--danger); }
.soft-success { background: var(--success-soft); }
.soft-warning { background: var(--warning-soft); }
.soft-danger { background: var(--danger-soft); }
.validation-message { color: var(--danger); font-size: 11px; gap: 5px; align-items: center; }
.info-message { color: var(--muted); font-size: 11px; }

.progress-track { display: flex; width: 100%; height: 14px; border-radius: 4px; overflow: hidden; background: var(--blue-100); }
.progress-first { background: #24a66a; }
.progress-second { background: #1478ed; }
.progress-third { background: #ffae2b; }
.progress-lower { background: #ef4e4e; }
.legend-row { gap: 14px; margin-top: 10px; flex-wrap: wrap; }
.legend-item { font-size: 11px; color: var(--navy-700); gap: 5px; align-items: center; }
.legend-dot { width: 9px; height: 9px; border-radius: 2px; }

.data-table { width: 100%; min-width: 0; max-width: 100%; border-radius: 0 0 10px 10px; box-shadow: none; }
.data-table .q-table__middle { width: 100%; max-width: 100%; overflow-x: auto; }
.data-table .q-table__top { min-height: 0; padding: 0; }
.data-table thead tr { background: #f8fbff; }
.data-table th { color: var(--navy-950); font-size: 11px; font-weight: 750; padding: 10px 12px; border-color: var(--blue-200); }
.data-table td { color: var(--navy-950); font-size: 11px; padding: 9px 12px; border-color: #dbe8f5; }
.data-table tbody tr:hover { background: var(--blue-50); }
.table-header { width: 100%; min-height: 50px; padding: 0 18px; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--blue-200); }

.step-row { width: 100%; align-items: center; justify-content: center; gap: 12px; padding: 2px 28px 8px; }
.step { gap: 8px; align-items: center; color: var(--muted); font-size: 13px; }
.step-number { width: 27px; height: 27px; border: 1px solid var(--blue-200); border-radius: 50%; display: flex; align-items: center; justify-content: center; background: #fff; }
.step.active { color: var(--navy-950); font-weight: 700; }
.step.active .step-number { color: #fff; background: var(--blue-600); border-color: var(--blue-600); }
.step-line { height: 1px; flex: 1; max-width: 150px; background: var(--blue-200); }
.source-switcher { width: 100%; gap: 8px; }
.source-button.q-btn { flex: 1; min-height: 43px; color: var(--navy-950); background: #fff; border: 1px solid var(--blue-200); text-transform: none; }
.source-button.selected { color: var(--blue-700); border-color: var(--blue-600); background: var(--blue-25); }
.summary-rail { background: #fff; border: 1px solid var(--blue-200); border-radius: 10px; overflow: hidden; align-self: stretch; }
.summary-block { padding: 18px; gap: 11px; border-bottom: 1px solid var(--blue-200); }
.summary-label { font-size: 13px; font-weight: 750; }
.summary-line { gap: 9px; align-items: center; font-size: 12px; color: var(--navy-700); }

.public-header { width: 100%; height: 62px; padding: 0 22px; background: #fff; border-bottom: 1px solid var(--blue-200); align-items: center; justify-content: space-between; }
.student-page { min-height: calc(100vh - 62px); background: var(--blue-25); padding-left: 4.2%; }
.student-main { padding: 32px 30px 38px 0; gap: 18px; }
.student-info-rail { padding: 35px 26px; border-left: 1px solid var(--blue-200); background: rgba(241, 247, 255, .7); gap: 0; }
.form-accent { border-left: 4px solid var(--blue-600); overflow: hidden; }
.student-section { width: 100%; padding: 17px 22px; gap: 11px; border-bottom: 1px solid var(--blue-200); }
.choice-row { width: 100%; gap: 7px; align-items: center; }
.choice-number { width: 34px; height: 40px; border: 1px solid #b9cbe1; border-radius: 6px; display: flex; justify-content: center; align-items: center; font-weight: 650; }
.choice-select { flex: 1; min-width: 0; }
.move-btn.q-btn { width: 38px; min-width: 38px; height: 38px; color: var(--navy-950); border: 1px solid var(--blue-200); border-radius: 6px; background: #fff; }
.how-step { padding: 24px 0 28px; gap: 14px; border-bottom: 1px solid var(--blue-200); }
.how-number { flex: 0 0 auto; width: 31px; height: 31px; border-radius: 50%; color: #fff; background: var(--blue-600); display: flex; align-items: center; justify-content: center; font-weight: 750; }
.how-title { font-size: 16px; line-height: 1.25; font-weight: 760; }
.how-copy { font-size: 12px; line-height: 1.5; color: var(--navy-700); }

.login-page { min-height: 100vh; width: 100%; background: var(--blue-25); display: flex; align-items: center; justify-content: center; padding: 24px; }
.login-card { width: min(430px, 100%); padding: 30px; gap: 18px; }

@media (max-width: 1040px) {
  .planner-sidebar { width: 205px; }
  .planner-main { margin-left: 205px; width: calc(100% - 205px); padding-inline: 20px; }
  .two-column, .overview-grid { grid-template-columns: 1fr; }
  .student-layout { grid-template-columns: 1fr 270px; }
}
@media (max-width: 820px) {
  .planner-sidebar { display: none; }
  .planner-main { margin-left: 0; width: 100%; padding: 18px 14px 30px; }
  .mobile-menu { display: inline-flex; }
  .page-title { font-size: 24px; }
  .page-header { gap: 12px; }
  .header-actions .secondary-btn { display: none; }
  .metric-strip { overflow-x: auto; }
  .metric-item { min-width: 190px; }
  .form-grid, .student-about-grid, .import-layout, .student-layout { grid-template-columns: 1fr; }
  .student-page { padding-left: 0; }
  .student-main { padding: 24px 14px; }
  .student-info-rail { border-left: 0; border-top: 1px solid var(--blue-200); }
  .step-line { display: none; }
  .step-row { justify-content: flex-start; overflow-x: auto; padding-inline: 0; }
}
@media (max-width: 560px) {
  .public-header { height: 58px; padding-inline: 14px; }
  .brand-name { font-size: 17px; }
  .page-header { flex-direction: column; }
  .header-actions { width: 100%; }
  .header-actions .primary-btn { flex: 1; }
  .student-section { padding: 17px 14px; }
  .choice-row { flex-wrap: wrap; }
  .choice-select { order: 2; flex-basis: calc(100% - 42px); }
  .move-btn { order: 3; }
  .metric-strip { flex-wrap: wrap !important; overflow: visible; padding: 8px; }
  .metric-item { flex: 1 1 calc(50% - 4px); min-width: 145px; padding: 12px 10px; justify-content: flex-start; }
  .metric-item + .metric-item { border-left: 0; }
  .metric-item:nth-child(even) { border-left: 1px solid var(--blue-200); }
  .metric-item:nth-child(n+3) { border-top: 1px solid var(--blue-200); }
}

@media (prefers-reduced-motion: no-preference) {
  .q-btn, .surface, .nav-item { transition: background-color .16s ease, border-color .16s ease, transform .16s ease; }
  .primary-btn:hover { transform: translateY(-1px); }
}
"""


NAV_ITEMS = (
    ("Overview", "home", "/staff/overview", "overview"),
    ("Data imports", "cloud_upload", "/staff/imports", "imports"),
    ("Seminars", "menu_book", "/staff/seminars", "seminars"),
    ("Schedule builder", "calendar_month", "/staff/builder", "builder"),
    ("Results", "bar_chart", "/staff/results", "results"),
)


def apply_theme(page_title: str = "Seminar Day Planner") -> None:
    ui.page_title(page_title)
    ui.add_head_html(f"<style>{THEME_CSS}</style>")
    ui.colors(primary="#0864e8", secondary="#344c73", positive="#24a66a", negative="#ef4444")


def brand(compact: bool = False) -> None:
    with ui.row().classes("brand-row" if not compact else "brand-row !p-0"):
        ui.icon("menu", size="29px").classes("brand-mark")
        ui.label("Seminar Day\nPlanner" if not compact else "Seminar Day Planner").classes(
            "brand-name whitespace-pre-line"
        )


def _mobile_navigation() -> None:
    with ui.button(icon="menu").props(
        "flat round aria-label='Open navigation'"
    ).classes("mobile-menu quiet-btn"):
        with ui.menu().props("anchor='bottom left' self='top left'"):
            for label, _icon, route, _key in NAV_ITEMS:
                ui.menu_item(label, on_click=lambda route=route: ui.navigate.to(route))


@contextmanager
def staff_shell(
    active: str,
    title: str,
    subtitle: str,
    header_actions: Callable[[], None] | None = None,
) -> Iterator[None]:
    apply_theme(title)
    ui.query(".nicegui-content").classes("p-0")
    with ui.row().classes("app-shell"):
        with ui.column().classes("planner-sidebar"):
            brand()
            with ui.column().classes("nav-stack"):
                for label, icon, route, key in NAV_ITEMS:
                    classes = "nav-item active" if key == active else "nav-item"
                    ui.button(
                        label,
                        icon=icon,
                        on_click=lambda route=route: ui.navigate.to(route),
                    ).props("flat no-caps").classes(classes)
            with ui.column().classes("sidebar-footer"):
                ui.label("Dover-Sherborn\nHigh School").classes("school-name whitespace-pre-line")
                with ui.row().classes("staff-profile"):
                    ui.avatar("MC", size="38px").classes("profile-avatar")
                    with ui.column().classes("gap-0"):
                        ui.label("Seminar Day team").classes("profile-name")
                        ui.label("Staff workspace").classes("profile-role")
                    ui.button(
                        icon="logout",
                        on_click=lambda: _logout(),
                    ).props("flat round dense aria-label='Sign out'").classes("ml-auto text-slate-500")
        with ui.column().classes("planner-main"):
            with ui.row().classes("page-header"):
                with ui.row().classes("items-start gap-2"):
                    _mobile_navigation()
                    with ui.column().classes("gap-0"):
                        ui.label(title).classes("page-title")
                        ui.label(subtitle).classes("page-subtitle")
                if header_actions:
                    with ui.row().classes("header-actions"):
                        header_actions()
            with ui.column().classes("page-content"):
                yield


def _logout() -> None:
    app.storage.user.clear()
    ui.navigate.to("/staff/login")


def require_staff() -> bool:
    if app.storage.user.get("authenticated") is True:
        return True
    ui.navigate.to("/staff/login")
    return False


def labeled_field(label: str) -> None:
    ui.label(label).classes("field-label")


def metric_item(icon: str, value: str, label: str, success_icon: bool = False) -> None:
    with ui.row().classes("metric-item items-center gap-3"):
        ui.icon(icon).classes("metric-icon" + (" success" if success_icon else ""))
        with ui.column().classes("gap-0"):
            ui.label(value).classes("metric-value")
            ui.label(label).classes("metric-label")
        ui.icon("check_circle", size="16px").classes("metric-check")


def metric_strip(student_count: int, seminar_count: int, period_count: int = 4) -> None:
    with ui.row().classes("surface metric-strip no-wrap"):
        metric_item("groups", f"{student_count} students", "All preferences imported")
        metric_item("menu_book", f"{seminar_count} seminars", "All capacities set")
        metric_item("schedule", f"{period_count} periods", "Periods configured")
        metric_item("restaurant", "Lunch enabled", "Lunch pattern set", success_icon=True)


def satisfaction_bar(satisfaction: dict[str, int] | None) -> None:
    satisfaction = satisfaction or {}
    total = max(1, int(satisfaction.get("students_total", 0)))
    values = [
        ("first", "1st choice", int(satisfaction.get("first_choice", 0))),
        ("second", "2nd choice", int(satisfaction.get("second_choice", 0))),
        ("third", "3rd choice", int(satisfaction.get("third_choice", 0))),
        (
            "lower",
            "4th+ / unranked",
            int(satisfaction.get("fourth_or_lower", 0)) + int(satisfaction.get("unranked", 0)),
        ),
    ]
    with ui.element("div").classes("progress-track"):
        for key, _label, value in values:
            ui.element("div").classes(f"progress-{key}").style(
                f"width: {100 * value / total:.2f}%"
            )
    with ui.row().classes("legend-row"):
        colors = {"first": "#24a66a", "second": "#1478ed", "third": "#ffae2b", "lower": "#ef4e4e"}
        for key, label, value in values:
            with ui.row().classes("legend-item"):
                ui.element("span").classes("legend-dot").style(f"background:{colors[key]}")
                ui.label(f"{label} {100 * value / total:.0f}% ({value})")
