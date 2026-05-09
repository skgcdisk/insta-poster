import customtkinter as ctk
from app import App


def main():
    # ダークテーマ・ブルーアクセントカラーで統一
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
