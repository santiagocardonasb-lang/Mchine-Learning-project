from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, RadioField, TextAreaField
from wtforms.fields.choices import SelectChoice
from wtforms.validators import InputRequired, Length, NumberRange, Optional
from wtforms.widgets import HiddenInput

WASTE_TYPE_CHOICES = [
    SelectChoice("household", "Household"),
    SelectChoice("construction_debris", "Debris"),
    SelectChoice("bulky", "Bulky"),
    SelectChoice("organic", "Organic"),
    SelectChoice("mixed", "Mixed"),
]
SIZE_CHOICES = [
    SelectChoice("small", "A few bags"),
    SelectChoice("medium", "A pile"),
    SelectChoice("large", "Blocks the way"),
]

PICK_A_POINT = "Pick a point on the map."


class ReportForm(FlaskForm):
    latitude = FloatField(
        widget=HiddenInput(),
        validators=[InputRequired(PICK_A_POINT), NumberRange(-90, 90, PICK_A_POINT)],
    )
    longitude = FloatField(
        widget=HiddenInput(),
        validators=[InputRequired(PICK_A_POINT), NumberRange(-180, 180, PICK_A_POINT)],
    )
    waste_type = RadioField(
        "What kind of waste?", choices=WASTE_TYPE_CHOICES,
        validators=[InputRequired("Choose the kind of waste.")],
    )
    size = RadioField(
        "How big is it?", choices=SIZE_CHOICES, validators=[InputRequired("Choose the size.")]
    )
    has_rodents = BooleanField("Rodents")
    has_insects = BooleanField("Insects")
    has_odor = BooleanField("Strong odor")
    near_water = BooleanField("Near a river or canal")
    description = TextAreaField(
        "Note", validators=[Optional(), Length(max=500, message="Keep the note under 500 characters.")]
    )
