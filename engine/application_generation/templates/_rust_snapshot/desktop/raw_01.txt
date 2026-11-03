#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk


APP_NAME = __APP_NAME__
REQUEST = __REQUEST__


class Application(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title(APP_NAME)
        self.geometry("760x480")
        self.minsize(560, 360)

        container = ttk.Frame(
            self,
            padding=32,
        )

        container.pack(
            fill="both",
            expand=True,
        )

        title = ttk.Label(
            container,
            text=APP_NAME,
            font=(
                "Sans",
                22,
                "bold",
            ),
        )

        title.pack(
            anchor="w",
        )

        description = ttk.Label(
            container,
            text=REQUEST,
            wraplength=660,
            justify="left",
        )

        description.pack(
            anchor="w",
            pady=(
                14,
                24,
            ),
        )

        self.status = ttk.Label(
            container,
            text="Application ready.",
        )

        self.status.pack(
            anchor="w",
            pady=(
                0,
                16,
            ),
        )

        button = ttk.Button(
            container,
            text="Get started",
            command=self.handle_action,
        )

        button.pack(
            anchor="w",
        )

    def handle_action(self) -> None:
        self.status.configure(
            text="Primary action executed.",
        )


if __name__ == "__main__":
    Application().mainloop()
