# Copyright ©️ 2024 John M Reynolds

from typing import Any, Callable, Iterable, List, Optional, Tuple

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.events import (
    Enter,
    Event,
    Key,
    Leave,
    Mount,
    MouseDown,
    MouseMove,
    MouseUp,
)
from textual.geometry import Offset, Region
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Footer, Label, Static


class MenuHeader(Widget):
    pass


class MenuItemMarker(Label):

    DEFAULT_CSS = """
    MenuItemMarker {
        dock: right;
    }
    """

    def on_enter(self, event: Enter) -> None:
        event.bubble = True


class MenuName(Static):
    DEFAULT_CSS = """
    MenuName {
        padding-right: 2;
    }

    MenuName:hover {
        background: $primary-background;
    }
    """

    # Enter event is a bit of a mess in Textual
    def on_enter(self, event: Enter) -> None:
        event.bubble = True


class MenuItem(Static):

    DEFAULT_CSS = """
    MenuItem {
        align: left top;
        margin-left: 1;
        margin-right: 0;
        width: 1fr;
        height: auto;
    }

    MenuItem.keyfocus {
        background: $accent;
    }

    """

    can_focus = True

    menu_action = ""
    callback: Optional[Callable[[str, str], None]] = None
    mode: str = None

    def __init__(
        self,
        name: str = "",
        menu_action: str = "",
        callback: Optional[Callable[[str, str], None]] = None,
        **kwargs
    ):
        super().__init__(name=name, **kwargs)
        if callback:
            self.mode = "callback"
        elif menu_action.startswith("menu"):
            self.mode = "menu"
        else:
            self.mode = "action"
        self.callback = callback
        self.menu_action = menu_action

    def compose(self):
        yield MenuItemMarker(">" if self.mode == "menu" else " ")
        yield MenuName(self.name)

    async def trigger(self, key: bool = False) -> None:
        menu_screen: MenuScreen = self.app.get_screen("menu")

        if self.mode == "menu":
            menu_screen.open_sub_menu(self, self.menu_action[5:], key=key)
        elif self.mode == "callback":
            menu_screen.close()
            self.callback(self.name, self.menu_action)
        else:
            menu_screen.close()
            await self.run_action(self.menu_action)

    async def on_focus(self, event: Event) -> None:
        menu_screen: MenuScreen = self.app.get_screen("menu")
        if menu_screen.mode != "key":
            self.app.set_focus(None)
        else:
            self.add_class("keyfocus")

    async def on_blur(self, event: Event) -> None:
        self.remove_class("keyfocus")

    async def on_click(self, event: Event) -> None:
        event.stop()
        await self.trigger()

    async def on_mouse_up(self, event: MouseUp) -> None:
        menu_screen: MenuScreen = self.app.get_screen("menu")
        if menu_screen.mode == "drag":
            if self.mode == "menu":
                menu_screen.close()
            else:
                await self.trigger()
        event.stop()

    async def on_enter(self, event: Enter) -> None:
        menu_screen: MenuScreen = self.app.get_screen("menu")
        if menu_screen.mode == "drag" and self.mode == "menu":
            menu_screen.open_sub_menu(self, self.menu_action[5:])


def get_child_index(parent: Widget, child: Widget) -> int:
    for index, node in enumerate(parent.children):
        if node == child:
            return index
    return -1


class Menu(Vertical):

    DEFAULT_CSS = """
    Menu {
        align: left top;
        margin: 0;
        height: auto;
        width: auto;
        max-width: 32;
        max-height: 90%;
        dock: left;
        border: round $accent;
    }

    """

    async def on_key(self, event: Key) -> None:
        current_item = self.app.focused
        if event.key in ("space", "enter", "right"):
            await self.app.focused.trigger(key=True)
            event.stop()
        elif event.key in ("shift+tab", "up"):
            index = get_child_index(self, current_item)
            for i in range(index - 1, -1, -1):
                child = self.children[i]
                if not child.disabled:
                    self.app.set_focus(child)
                    break
            event.stop()
        elif event.key in ("tab", "down"):
            index = get_child_index(self, self.app.focused)
            for i in range(index + 1, len(self.children)):
                child = self.children[i]
                if not child.disabled:
                    self.app.set_focus(child)
                    break
            event.stop()
        elif event.key in ("left"):
            menu_screen: MenuScreen = self.app.get_screen("menu")
            menu_screen.pop_menu(key=True)


class MenuScreen(ModalScreen[str]):

    DEFAULT_CSS = """
    MenuScreen {
        align: left top;
    }

    """

    AUTO_FOCUS = ""

    BINDINGS = [("escape", "screen.close", "Close menu")]

    menu_stack: List[Tuple[Menu, Optional[MenuItem]]] = []
    mode = "drag"

    def compose(self) -> Iterable[Widget]:
        yield Footer()

    def on_click(self) -> None:
        self.close()

    async def on_mouse_up(self, event: MouseUp) -> None:
        if event.screen_y == 0:
            self.mode = "click"
        elif self.mode == "drag":
            self.close()

    async def on_mouse_move(self, event: MouseMove) -> None:
        if not event.button:
            self.mode = "click"

    def action_close(self):
        self.close()

    def close(self) -> None:
        self.dismiss(False)
        focused = self.app.focused
        if type(focused) == MenuHeader:
            self.app.set_focus(focused.parent.parent.previous_focus)

    def hide(self, menu: Widget):
        menu.offset = (-1000, 0)

    def hide_all(self) -> None:
        for child in self.children:
            self.hide(child)

    def adjust_menu_region(self, region: Region) -> Region:
        return region.translate_inside(
            Region(0, 0, self.app.size.width, self.app.size.height - 1)
        )

    def focus_menu(self, menu: Widget, key: bool):
        try:
            if key:
                for child in menu.children:
                    if not child.disabled:
                        self.app.set_focus(child)
                        break
            else:
                self.app.set_focus(None)
        except:
            pass

    async def context_menu(self, menu_id: Menu, offset: Offset, key: bool = False):
        self.hide_all()
        await self.app.push_screen(self)
        self.menu_stack = []
        try:
            menu = self.app.screen.query_one("#" + menu_id)
        except:
            self.app.pop_screen()
            return
        region = self.adjust_menu_region(
            Region(
                offset.x,
                offset.y,
                menu.virtual_region_with_margin.width,
                menu.virtual_region_with_margin.height,
            )
        )
        menu.styles.offset = (region.x, region.y)
        self.menu_stack.append((menu, None))
        if key:
            self.focus_menu(menu, key)

    async def open_menu(self, menu_header: MenuHeader, key: bool = False):
        self.mode = "key" if key else "drag"
        self.hide_all()
        await self.app.push_screen(self)
        self.menu_stack = []
        offset = menu_header.virtual_region.offset
        menu_id = menu_header.menu_id
        try:
            menu = self.app.screen.query_one("#" + menu_id)
        except:
            self.app.pop_screen()
            return
        region = self.adjust_menu_region(
            Region(
                offset[0],
                offset[1] + 1,
                menu.virtual_region_with_margin.width,
                menu.virtual_region_with_margin.height,
            )
        )
        menu.styles.offset = (region.x, region.y)
        self.menu_stack.append((menu, None))
        self.focus_menu(menu, key)

    def open_sub_menu(self, menu_item: MenuItem, menu_id: str, key: bool = False):
        menu = menu_item.parent
        while menu != self.menu_stack[-1][0]:
            old_menu = self.menu_stack.pop()
            self.hide(old_menu[0])
        virtual_region_with_margin = menu_item.virtual_region
        container_viewport = menu_item.container_viewport
        try:
            menu = self.app.screen.query_one("#" + menu_id)
        except:
            return
        region = self.adjust_menu_region(
            Region(
                container_viewport.x + container_viewport.width - 1,
                container_viewport.y + virtual_region_with_margin.y,
                menu.virtual_region_with_margin.width,
                menu.virtual_region_with_margin.height,
            )
        )
        menu.styles.offset = (region.x, region.y)
        menu.parent.move_child(menu, after=self.menu_stack[-1][0])
        menu.styles.display = "none"
        menu.styles.display = "block"
        self.menu_stack.append((menu, menu_item))
        self.focus_menu(menu, key)

    def pop_menu(self, key=False):
        if len(self.menu_stack) == 1:
            self.close()
            return
        old_menu = self.menu_stack.pop()
        self.hide(old_menu[0])
        if key:
            if old_menu[1] in self.menu_stack[-1][0].children:
                self.app.set_focus(old_menu[1])
            else:
                self.focus_menu(self.menu_stack[-1][0], key)


class MenuHeader(Widget):

    DEFAULT_CSS = """
    MenuHeader {
        padding: 0 1;
        content-align: left middle;
        width: auto;
        max-width: 15;
    }

    MenuHeader:hover {
        background: $primary-background;
    }

    MenuHeader:focus {
        background: $accent;
    }

    """

    name = reactive("")
    menu_id = reactive("")

    can_focus = False

    def __init__(self, menu_id="", name=""):
        super().__init__()
        self.name = name
        self.menu_id = menu_id

    def render(self):
        return self.name

    async def on_mouse_down(self, event: MouseDown) -> None:
        await self.app.get_screen("menu").open_menu(self)

    async def on_key(self, event: Key) -> None:
        if event.key in ("space", "enter", "down"):
            await self.app.get_screen("menu").open_menu(self, key=True)
            self.can_focus = False
            event.stop()
        elif event.key == ("escape"):
            self.can_focus = False
            self.app.set_focus(self.parent.parent.previous_focus)

    async def on_mouse_release(self, event: Event):
        event.stop()
        self.app.set_focus(None)

    async def on_event(self, event: Event) -> None:
        return await super().on_event(event)


class MenuBar(Widget):
    DEFAULT_CSS = """
    MenuBar {
        dock: top;
        width: 100%;
        background: $background-lighten-2;
        height: 1;
    }
    """

    container = None
    previous_focus: Optional[Widget] = None

    def __init__(
        self,
        *children: Widget,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False
    ) -> None:
        self.container = Horizontal()
        super().__init__(
            self.container, name=name, id=id, classes=classes, disabled=disabled
        )
        for child in children:
            self.container.mount(child)

    def activate(self):
        if self.container.children:
            self.previous_focus = self.app.focused
            child = self.container.children[0]
            child.can_focus = True
            child.focus()

    async def on_key(self, event: Key) -> None:
        current = self.app.focused
        index = get_child_index(self.container, current)
        if event.key in ("tab", "right"):
            for i in range(index + 1, len(self.container.children)):
                child = self.container.children[i]
                child.can_focus = True
                child.focus()
                current.can_focus = False
                break
            event.stop()
        elif event.key in ("shift+tab", "left"):
            for i in range(index - 1, -1, -1):
                child = self.container.children[i]
                child.can_focus = True
                child.focus()
                current.can_focus = False
                break
            event.stop()
