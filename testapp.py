# Copyright ©️ 2024 John M Reynolds

import os

from textual.app import App
from textual.containers import (
    Grid,
    Vertical,
    VerticalScroll,
)
from textual.geometry import Offset
from textual.screen import Screen
from textual.widgets import Button, Footer, Label, Log, Static

from zandev_textual_widgets import (
    Dialog,
    FileSelector,
    FileSelectorMode,
    Menu,
    MenuBar,
    MenuHeader,
    MenuItem,
    MenuScreen,
)

quit_dialog = Dialog(
    id="quit_dialog",
    label="Quit application?",
    buttons=[("Quit", "quit", "error"), ("Cancel", "cancel", "primary")],
)

about_dialog = Dialog(
    id="about_dialog",
    label="A simple test application",
    buttons=[("Close", "close", "primary")],
)

overwrite_dialog = Dialog(
    id="overwrite_dialog",
    label="",
    buttons=[("Save", "save", "success"), ("Cancel", "cancel", "error")],
)


class Main(Screen):
    CSS_PATH = "app.tcss"
    BINDINGS = [
        ("q", "quit", "quit"),
        ("m", "menu", "menu"),
        ("f", "file", "file"),
        ("d", "dir", "dir"),
        ("s", "save", "save"),
    ]

    DEFAULT_CSS = """
    Label {
        border: round red;
    }

    Grid {
        width: auto;
        grid-size: 2 2;
        grid-columns: auto;
        grid-rows: auto;
        border: round green;
    }

    Vertical {
        border: round blue;
    }
    """

    AUTO_FOCUS = ""

    menu_bar: MenuBar = None
    log_widget: Log = None

    def action_quit(self) -> None:
        def check_quit(selected: str) -> None:
            if selected == "quit":
                self.app.exit()

        self.app.push_screen(quit_dialog, check_quit)

    def action_toggle_dark(self) -> None:
        self.app.dark = not self.app.dark

    def action_test_screen(self):
        self.app.push_screen("test")

    def action_menu(self):
        self.menu_bar.activate()

    async def action_save(self):
        def save_result(filename):

            def save_success(value):
                if value == "save":
                    self.log_widget.write_line(f"Saved {filename}")

            overwrite_dialog.label = f"Save file {filename}?"
            self.app.push_screen(overwrite_dialog, callback=save_success)

        self.app.push_screen(
            FileSelector(
                directory=os.getcwd(), mode=FileSelectorMode.NEW, ok_text="Save"
            ),
            callback=save_result,
        )

    async def action_file(self):
        def file_result(value):
            self.log_widget.write_line(f"Open file {value}")

        self.app.push_screen(FileSelector(directory=os.getcwd()), callback=file_result)

    async def action_dir(self):
        def file_result(value):
            self.log_widget.write_line(f"Select directory {value}")

        self.app.push_screen(
            FileSelector(directory=os.getcwd(), mode=FileSelectorMode.DIRECTORY),
            callback=file_result,
        )

    async def on_mount(self):
        self.menu_bar = MenuBar(
            MenuHeader(name="TestApp", menu_id="app_menu"),
            MenuHeader(name="File", menu_id="file_menu"),
            MenuHeader(name="Actions", menu_id="action_menu"),
        )

        self.mount(self.menu_bar)
        self.mount(Footer())

        self.t1 = Label("A simple test application for zandev_textual_widgets")
        self.t2 = Label("https://github.com/ZandevOxford/zandev_textual_widgets")
        await self.mount(Grid(Vertical(self.t1, self.t2)))
        self.t1.parent.move_child(self.t1, after=self.t2)

        menu_screen = self.app.get_screen("menu")

        button = Button("A Button for testing context menus")
        button.can_focus == True
        self.mount(button)

        self.log_widget = Log()
        self.mount(self.log_widget)

    async def on_button_pressed(self, event):
        await self.app.get_screen("menu").context_menu(
            "test_menu",
            Offset(
                event.control.region.x + event.control.region.width,
                event.control.region.y,
            ),
        )

    async def on_click(self, event):
        self.log_widget.write_line(
            f"{event.ctrl}, {event.meta}, {event.shift}, {event.control}, {event.button}"
        )
        if event.button == 3 or (event.button == 1 and event.meta):
            await self.app.get_screen("menu").context_menu(
                "test_menu", Offset(event.screen_x, event.screen_y)
            )

    async def on_key(self, event):
        self.log_widget.write_line(f"{event.key}")
        if event.key == "ctrl+a":
            widget = self.app.focused
            if widget:
                await self.app.get_screen("menu").context_menu(
                    "test_menu", Offset(widget.region.x, widget.region.y), key=True
                )

    def action_about(self):
        self.app.push_screen(about_dialog)


class TestMenuScreen(MenuScreen):

    async def on_mount(self):
        app_menu = Menu(
            MenuItem(name="About", menu_action="screen.about"),
            MenuItem(name="Quit", menu_action="screen.quit"),
            id="app_menu",
        )
        self.mount(app_menu)
        file_menu = Menu(
            MenuItem(name="Open", menu_action="screen.open"),
            MenuItem(name="Save", menu_action="screen.save"),
            MenuItem(name="Test Screen", menu_action="screen.test_screen"),
            MenuItem(name="Test Menu", menu_action="menu.test_menu"),
            id="file_menu",
        )
        self.mount(file_menu)

        action_menu = Menu(
            MenuItem(name="Toggle Dark Mode", menu_action="screen.toggle_dark"),
            MenuItem(name="Test Menu", menu_action="menu.test_menu"),
            id="action_menu",
        )
        self.mount(action_menu)

        def callback_test(name, action):
            self.app.dark = not self.app.dark

        test_menu = Menu(
            MenuItem(name="Test Menu", menu_action="menu.test_menu_2"),
            MenuItem(
                name="Test Menu with some longer text", menu_action="menu.test_menu_2"
            ),
            MenuItem(name="Test Menu", menu_action="menu.test_menu_2"),
            MenuItem(name="Test Menu", menu_action="menu.test_menu_2"),
            MenuItem(
                name="Dark mode via callback",
                menu_action="action",
                callback=callback_test,
            ),
            MenuItem(name="Missing menu", menu_action="menu.foo"),
            id="test_menu",
        )
        self.mount(test_menu)

        test_menu_2 = Menu(
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Menu", menu_action="menu.test_menu_3"),
            MenuItem(name="Menu", menu_action="menu.test_menu_3"),
            id="test_menu_2",
        )
        self.mount(test_menu_2)

        test_menu_3 = Menu(
            MenuItem(name="Item", disabled=True, menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", disabled=True, menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", menu_action="screen.about"),
            MenuItem(name="Item", disabled=True, menu_action="screen.about"),
            id="test_menu_3",
        )
        self.mount(test_menu_3)


class TestScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Close")]

    DEFAULT_CSS = """
    TestScreen Grid {
        grid-size: 2 2;
        grid-columns: 1fr 1fr;
        grid-rows: 1fr 1fr;
    }

    TestScreen Vertical {
        height: auto;
        border: red round;
        margin: 5;
        background: green;
    }

    TestScreen Label.test {
        background: green;
        border: round red;
        width: 300;
        height: 300;
    }
    
    TestScreen Static.test2 {
        width: 100;
        height: 100;
        background: red;
    }
    """

    def on_click(self, event):
        event

    def compose(self):

        # VerticalScroll(Widget(Label("Test2", classes="test")), classes="test2")
        # VerticalScroll(Label("Test2", classes="test"))
        yield VerticalScroll(Vertical(Static("TEST", classes="test2")))
        yield Footer()


class TestApp(App):

    SCREENS = {
        "main": Main,
        "test": TestScreen,
        "menu": TestMenuScreen,
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_mount(self) -> None:
        self.push_screen("main")


if __name__ == "__main__":
    app = TestApp()
    app.run()
