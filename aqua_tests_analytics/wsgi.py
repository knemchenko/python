from app import create_app

app = create_app()

if __name__ == "__main__":
    # This is for development only, Gunicorn runs `app` directly
    app.run()
