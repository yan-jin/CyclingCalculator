import math
import pandas as pd
import plotly.graph_objects as go
from dash import Dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import plotly.express as px


class ScrapeParameters:
    rp_wr = 0
    rp_wb = 0
    rp_a = 0
    rp_cd = 0
    rp_dtl = 0

    ep_crr = 0
    ep_rho = 0
    ep_headwind = 0
    ep_g = 0

    def __init__(self,
                 rider_weight,
                 bike_weight,
                 frontal_area,
                 drag_coefficient,
                 hill_grade,
                 headwind,
                 air_density,
                 drivetrain_loss=2,
                 rolling_resistance_coefficient=0.005
                 ):
        self.rp_wb = bike_weight
        self.rp_wr = rider_weight
        self.rp_a = frontal_area
        self.rp_cd = drag_coefficient
        self.rp_dtl = drivetrain_loss
        self.ep_g = hill_grade
        self.ep_crr = rolling_resistance_coefficient
        self.ep_rho = air_density
        self.ep_headwind = headwind


def calculate_forces(velocity, params):
    f_gravity = 9.8067 * \
                (params.rp_wr + params.rp_wb) * \
                math.sin(math.atan(params.ep_g / 100.0))

    f_rolling = 9.8067 * \
                (params.rp_wr + params.rp_wb) * \
                math.cos(math.atan(params.ep_g / 100.0)) * \
                params.ep_crr

    if velocity < 0:
        f_rolling *= -1.0

    f_drag = 0.5 * \
             params.rp_a * \
             params.rp_cd * \
             params.ep_rho * \
             ((velocity + params.ep_headwind) * 1000.0 / 3600.0) * \
             ((velocity + params.ep_headwind) * 1000.0 / 3600.0)

    if velocity + params.ep_headwind < 0:
        f_drag *= -1.0

    return {'f_gravity': f_gravity,
            'f_rolling': f_rolling,
            'f_drag': f_drag}


def calculate_power(velocity, params):
    # calculate the forces on the rider.
    forces = calculate_forces(velocity, params)
    total_force = forces['f_gravity'] + forces['f_rolling'] + forces['f_drag']

    # calculate necessary wheelpower.
    wheel_power = total_force * (velocity * 1000.0 / 3600.0)

    # calculate necessary legpower. Note: if wheelpower is negative,
    # i.e., braking is needed instead of pedaling, then there is
    # no drivetrain loss.
    drive_train_frac = 1.0
    if wheel_power > 0.0:
        drive_train_frac = drive_train_frac - (params.rp_dtl / 100.0)

    leg_power = wheel_power / drive_train_frac

    if leg_power > 0.0:
        leg_power = leg_power
        wheel_power = wheel_power
        drive_train_loss = leg_power - wheel_power
        braking_power = 0.0
    else:
        leg_power = 0.0
        wheel_power = 0.0
        drive_train_loss = 0.0
        braking_power = leg_power * -1.0

    return {'leg_power': leg_power,
            'wheel_power': wheel_power,
            'drive_train_loss': drive_train_loss,
            'braking_power': braking_power}


def calculate_velocity(power, params):
    # How close to get before finishing.
    epsilon = 0.000001

    # Set some reasonable upper / lower starting points.
    lower_vel = -1000.0
    upper_vel = 1000.0
    mid_vel = 0.0
    mid_pow_dict = calculate_power(mid_vel, params)

    # Iterate until completion.
    it_count = 0
    while True:
        mid_pow = pow_dict_to_leg_power(mid_pow_dict)
        if abs(mid_pow - power) < epsilon:
            break

        if mid_pow > power:
            upper_vel = mid_vel
        else:
            lower_vel = mid_vel

        mid_vel = (upper_vel + lower_vel) / 2.0
        mid_pow_dict = calculate_power(mid_vel, params)
        it_count += 1
        if it_count > 100:
            break

    return mid_vel


# Returns the legpower (negative for brakepower) from the powerdict.
def pow_dict_to_leg_power(pow_dict):
    mid_pow = 0.0
    if pow_dict['braking_power'] > 0.0:
        mid_pow = pow_dict['braking_power'] * -1.0
    else:
        mid_pow = pow_dict['leg_power']
    return mid_pow


app = Dash(__name__)

app.layout = html.Div([
    html.H1("Race Performance Calculator"),
    html.Div([
        "FTP(w): ",
        dcc.Input(id='ftp', value=300.0, type='number'),
        "Race Distance(km): ",
        dcc.Input(id='race_distance', value=180.0, type='number')
    ]),
    html.Br(),
    html.Div([
        "Rider Weight(kg): ",
        dcc.Input(id='rider_weight', value=75.0, type='number'),
        "Bike Weight(kg): ",
        dcc.Input(id='bike_weight', value=10.0, type='number')
    ]),
    html.Br(),
    html.Div([
        "Frontal Area(m^2): ",
        dcc.Input(id='frontal_area', value=0.5, type='number'),
        "Drag Coefficient: ",
        dcc.Input(id='drag_coefficient', value=0.51, type='number')
    ]),
    html.Br(),
    html.Div([
        "Hill Grade(%): ",
        dcc.Input(id='hill_grade', value=0.0, type='number'),
        "Headwind(m/s): ",
        dcc.Input(id='headwind', value=0.0, type='number')
    ]),
    html.Br(),
    html.Div([
        "Air Density(kg/m^3): ",
        dcc.Input(id='air_density', value=1.22, type='number')
    ]),
    dcc.Graph(id='graph'),
])


@app.callback(
    Output('graph', 'figure'),
    Input('ftp', 'value'),
    Input('race_distance', 'value'),
    Input('rider_weight', 'value'),
    Input('bike_weight', 'value'),
    Input('frontal_area', 'value'),
    Input('drag_coefficient', 'value'),
    Input('hill_grade', 'value'),
    Input('headwind', 'value'),
    Input('air_density', 'value'),
)
def update_graph(ftp, race_distance,
                 rider_weight, bike_weight,
                 frontal_area, drag_coefficient, hill_grade, headwind, air_density):
    params = ScrapeParameters(rider_weight=rider_weight,
                              bike_weight=bike_weight,
                              frontal_area=frontal_area,
                              drag_coefficient=drag_coefficient,
                              hill_grade=hill_grade,
                              headwind=headwind,
                              air_density=air_density)

    powers = []
    speeds = []
    tss = []
    durations = []
    duration_texts = []
    for power in range(math.ceil(0.4 * ftp), math.ceil(1.3 * ftp)):
        speed = calculate_velocity(power, params)
        if_value = power / ftp * 1.0
        duration = race_distance / speed

        powers.append(power)
        speeds.append(speed)
        durations.append(duration)
        duration_texts.append(
            str(math.floor(duration)) + ':' + str(math.floor((duration - math.floor(duration)) * 60)) + ':' + str(
                math.floor((((duration - math.floor(duration)) * 60) - math.floor(
                    (duration - math.floor(duration)) * 60)) * 60)))
        tss.append(if_value ** 2 * duration * 100)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=powers,
        y=speeds,
        name="Speed",
        hovertemplate='%{y:.2f} km/h'
    ))

    fig.add_trace(go.Scatter(
        x=powers,
        y=durations,
        name="Duration",
        yaxis="y2",
        hovertemplate='%{text}',
        text=duration_texts
    ))

    fig.add_trace(go.Scatter(
        x=powers,
        y=tss,
        name="TSS",
        yaxis="y3",
        hovertemplate='%{y:.1f}'
    ))

    fig.add_vrect(x0=math.ceil(ftp * 0.56), x1=math.ceil(ftp * 0.75),
                  annotation_text="Zone 2", annotation_position="top left",
                  fillcolor="blue", opacity=0.25, line_width=0)
    fig.add_vrect(x0=math.ceil(ftp * 0.75), x1=math.ceil(ftp * 0.9),
                  annotation_text="Zone 3", annotation_position="top left",
                  fillcolor="green", opacity=0.25, line_width=0)
    fig.add_vrect(x0=math.ceil(ftp * 0.9), x1=math.ceil(ftp * 1.05),
                  annotation_text="Zone 4", annotation_position="top left",
                  fillcolor="orange", opacity=0.25, line_width=0)
    fig.add_vrect(x0=math.ceil(ftp * 1.05), x1=math.ceil(ftp * 1.2),
                  annotation_text="Zone 5", annotation_position="top left",
                  fillcolor="red", opacity=0.25, line_width=0)

    # Create axis objects
    fig.update_layout(
        showlegend=True,
        hovermode='x unified',
        spikedistance=-1,
        xaxis=dict(
            title="Power(w)",
            showspikes=True,
            spikemode='across',
            spikesnap='cursor',
            showline=True,
            showgrid=True,
        ),
        yaxis=dict(
            title="Speed(km/h)",
            titlefont=dict(
                color="#1f77b4"
            ),
            tickfont=dict(
                color="#1f77b4"
            ),
        ),
        yaxis2=dict(
            title="Duration(h)",
            titlefont=dict(
                color="#ff7f0e"
            ),
            tickfont=dict(
                color="#ff7f0e"
            ),
            anchor="free",
            overlaying="y",
            side="left",
            position=0.1
        ),
        yaxis3=dict(
            title="TSS",
            titlefont=dict(
                color="#d62728"
            ),
            tickfont=dict(
                color="#d62728"
            ),
            anchor="x",
            overlaying="y",
            side="right"
        )
    )

    # Update layout properties
    fig.update_layout(
        title_text="Race Performance Calculator",
        width=1000,
        height=800
    )

    return fig


if __name__ == '__main__':
    app.run_server(debug=True)
