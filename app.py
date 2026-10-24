"""LimpIA: a Flask web application that predicts urban waste accumulation risk."""

from flask import Flask, render_template

import content

app = Flask(__name__)


@app.context_processor
def inject_app_name():
    return {"app_name": content.APP_NAME}


@app.route("/")
def home():
    return render_template(
        "home.html",
        title=content.PROJECT_TITLE,
        problem=content.PROBLEM_STATEMENT,
        question=content.RESEARCH_QUESTION,
        objective=content.GENERAL_OBJECTIVE,
    )


if __name__ == "__main__":
    app.run(debug=True)
