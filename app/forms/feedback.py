from flask_wtf import FlaskForm
from wtforms import HiddenField, RadioField, TextAreaField
from wtforms.fields.choices import SelectChoice
from wtforms.validators import DataRequired, InputRequired, Length

KIND_CHOICES = [
    SelectChoice("incident", "Incident"),
    SelectChoice("bug", "Bug"),
    SelectChoice("suggestion", "Suggestion"),
]


class FeedbackForm(FlaskForm):
    kind = RadioField("What is it about?", choices=KIND_CHOICES, validators=[InputRequired("Choose a kind.")])
    message = TextAreaField("Message", filters=[lambda value: value.strip() if value else value], validators=[
        DataRequired("Write what happened or what you suggest."),
        Length(max=2000, message="Keep the message under 2,000 characters."),
    ])
    page = HiddenField()
