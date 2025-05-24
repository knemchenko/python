from app import create_app, db
# from app.models import User, Post # Import your models here

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db} # Add your models to the shell context

if __name__ == '__main__':
    app.run(debug=app.config.get('FLASK_DEBUG', True))
