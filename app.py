import os
from datetime import date, datetime

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import case

load_dotenv()

app = Flask(__name__)
database_url = os.environ.get("DATABASE_URL")
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    db_path = "/tmp/todo.db" if os.environ.get("VERCEL") else "todo.db"
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

PRIORITIES = ["high", "medium", "low"]
PRIORITY_LABELS = {"high": "높음", "medium": "보통", "low": "낮음"}


class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    memo = db.Column(db.Text)
    priority = db.Column(db.String(10), nullable=False, default="medium")
    due_date = db.Column(db.Date)
    done = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    subtasks = db.relationship(
        "Subtask", backref="todo", cascade="all, delete-orphan", order_by="Subtask.id"
    )


class Subtask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    todo_id = db.Column(db.Integer, db.ForeignKey("todo.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False)


with app.app_context():
    db.create_all()


def parse_due_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@app.route("/")
def index():
    priority_order = case(
        {p: i for i, p in enumerate(PRIORITIES)}, value=Todo.priority, else_=len(PRIORITIES)
    )
    todos = (
        Todo.query.order_by(
            Todo.done, Todo.due_date.is_(None), Todo.due_date, priority_order, Todo.created_at.desc()
        ).all()
    )
    return render_template(
        "index.html", todos=todos, priorities=PRIORITIES, priority_labels=PRIORITY_LABELS, today=date.today()
    )


@app.route("/add", methods=["POST"])
def add():
    title = request.form.get("title", "").strip()
    if title:
        priority = request.form.get("priority", "medium")
        if priority not in PRIORITIES:
            priority = "medium"
        todo = Todo(
            title=title,
            memo=request.form.get("memo", "").strip() or None,
            priority=priority,
            due_date=parse_due_date(request.form.get("due_date")),
        )
        db.session.add(todo)
        db.session.commit()
    return redirect(url_for("index"))


@app.route("/toggle/<int:todo_id>", methods=["POST"])
def toggle(todo_id):
    todo = db.get_or_404(Todo, todo_id)
    todo.done = not todo.done
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/delete/<int:todo_id>", methods=["POST"])
def delete(todo_id):
    todo = db.get_or_404(Todo, todo_id)
    db.session.delete(todo)
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/todo/<int:todo_id>/subtask/add", methods=["POST"])
def add_subtask(todo_id):
    db.get_or_404(Todo, todo_id)
    title = request.form.get("title", "").strip()
    if title:
        db.session.add(Subtask(todo_id=todo_id, title=title))
        db.session.commit()
    return redirect(url_for("index"))


@app.route("/subtask/<int:subtask_id>/toggle", methods=["POST"])
def toggle_subtask(subtask_id):
    subtask = db.get_or_404(Subtask, subtask_id)
    subtask.done = not subtask.done
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/subtask/<int:subtask_id>/delete", methods=["POST"])
def delete_subtask(subtask_id):
    subtask = db.get_or_404(Subtask, subtask_id)
    db.session.delete(subtask)
    db.session.commit()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
