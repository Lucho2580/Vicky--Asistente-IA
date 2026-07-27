from core.env_config import consume_and_scrub_embedded_ai_api_key
from ui.main_window import MainWindow


def main() -> None:
    consume_and_scrub_embedded_ai_api_key()

    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
