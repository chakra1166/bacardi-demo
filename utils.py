import pandas as pd
import streamlit as st
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from matplotlib.colors import LinearSegmentedColormap
from st_aggrid import (
    AgGrid,
    GridOptionsBuilder,
    GridUpdateMode,
    JsCode,
    ColumnsAutoSizeMode,
)


def read_data(file_name, separator=";"):
    df = pd.read_csv(file_name, sep=separator, encoding="ISO-8859-1")
    grp_cols = [
        "Retailer",
        "Category",
        "Segment",
        "Sub-Segment",
        "Brand",
        "KNAC-14",
        "Description",
        "Day",
        "Month",
        "Year",
    ]
    df = (
        df.groupby(grp_cols)
        .agg(
            Units=("Units", "sum"),
            Volume=("Sales in kg", "sum"),
            Value=("Sales in LC", "sum"),
        )
        .reset_index()
    )
    df["Date"] = df[["Day", "Month", "Year"]].apply(
        lambda row: "-".join(row.values.astype(str)), axis=1
    )
    df["Date"] = pd.to_datetime(df["Date"], format="%d-%m-%Y").dt.normalize()
    df["year"] = df["Date"].dt.year
    df["SKU"] = df["Description"]
    df["Value"] = 0.0012 * df["Value"]
    df["n_weeks"] = df.groupby(["KNAC-14"])["Date"].transform("nunique")
    df = df.loc[df["n_weeks"] >= 114]
    df["pred_flag"] = np.where(df["Date"].dt.year == 2021, 1, 0)
    df = df.drop(["Day", "Month", "Year", "Description", "n_weeks"], axis=1)
    df = df.sort_values(by=["SKU", "Date"])
    df["R2"] = np.random.randint(low=55, high=85, size=df.shape[0])
    df["R2"] = df.groupby(["SKU"])["R2"].transform("mean")
    df["MAPE"] = (100 - df["R2"]) / 2
    df["Unit Price"] = df["Value"] / df["Units"]
    df["Vol Price"] = df["Value"] / df["Volume"]
    return df


tt = read_data("data/weekly_raw_data.csv")
tt.to_csv("data/sales_data.csv", index=False)


@st.cache_data()
def read_app_data():
    df = pd.read_csv("data/sales_data.csv")
    df["Market"] = "USA"
    return df


def build_line_chart(df, x_col="Date", y_col="Units"):
    # color = ["#D01E2F" if x == 0 else "goldenrod" for x in pred_flag]
    x_data = df[x_col]
    y_data = df[y_col]
    fig = go.Figure()
    fig = fig.add_trace(
        go.Scatter(
            x=x_data,
            y=y_data,
            mode="lines",
            line={"color": "#D01E2F", "width": 2, "dash": "dot"},
            name="Historical Sales"
            # line_color=color,
        )
    )

    x_data = df.loc[df["pred_flag"] == 1][x_col]
    y_data = df.loc[df["pred_flag"] == 1][y_col]
    fig = fig.add_trace(
        go.Scatter(
            x=x_data,
            y=y_data,
            mode="lines+markers",
            line={"color": "#27A844", "width": 2},
            name="Predictions"
            # line_color=color,
        )
    )
    fig.update_xaxes(
        showgrid=False, ticklabelmode="period", dtick="M1", tickformat="%m-%d-%Y"
    )
    fig.update_layout(
        legend=dict(yanchor="bottom", xanchor="center", orientation="h", y=-0.5, x=0.5)
    )
    return fig


def format_layout_fig(fig, title="Unit Sales", x_axis_title="Date", prefix=False):
    fig.update_layout(title_text=title)
    fig.update_xaxes(
        title_text=x_axis_title,
        showline=True,
        linewidth=1,
        linecolor="black",
        mirror=True,
    )
    fig.update_yaxes(
        rangemode="tozero", showline=True, linewidth=1, linecolor="black", mirror=True
    )
    fig.update(layout=dict(title=dict(x=0.5)))
    fig.update_layout(
        title_font_family="Rockwell", title_font_color="Black", template="plotly_white"
    )
    fig.update_layout(hovermode="x unified")
    fig.update_layout(
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Rockwell")
    )
    if prefix:
        fig.update_layout(yaxis_tickprefix="$")
    return fig


def gen_sku_metrics(df):
    tt = (
        df.groupby(["SKU", "year"])
        .agg(
            Units=("Units", "sum"),
            Value=("Value", "sum"),
            Rsq=("R2", "mean"),
            MAPE=("MAPE", "mean"),
        )
        .reset_index()
        .sort_values(by=["SKU", "year"])
    )
    tt["unit_growth"] = tt.groupby(["SKU"])["Units"].pct_change()
    tt["value_growth"] = tt.groupby(["SKU"])["Value"].pct_change()
    out_dict = {
        "units_sales": tt.loc[tt["year"] == 2020]["Units"].values[0],
        "value_sales": tt.loc[tt["year"] == 2020]["Value"].values[0],
        "unit_yoy_grth": tt.loc[tt["year"] == 2020]["unit_growth"].values[0],
        "value_yoy_grth": tt.loc[tt["year"] == 2020]["value_growth"].values[0],
        "MAPE": tt["MAPE"].mean(),
        "R2": tt["Rsq"].mean(),
    }
    return out_dict


# @st.cache_data()
def read_scenario_data():
    df = pd.read_excel("data/scenarios.xlsx", sheet_name="Scenarios Summary")
    df["Created Date"] = df["Created Date"].dt.normalize()
    df["prec_profit"] = df["prec_profit"] * 100
    # df = df.style.format({"% Profit": "{:.2%}",}).background_gradient(
    #     subset="% Profit", cmap=temp
    # )
    return df


def gen_aggrid(df):
    gd = GridOptionsBuilder.from_dataframe(df)
    # gd.configure_default_column(hide=True, editable=False)
    gd.configure_column(
        field="Created Date",
        header_name="Created Date",
        hide=False,
        type=["customDateTimeFormat"],
        custom_format_string="MM-dd-yyyy",
    )
    gd.configure_column(
        field="revenue",
        header_name="Revenue ($)",
        hide=False,
        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
        valueFormatter="data.revenue.toLocaleString('en-US');",
    )
    gd.configure_column(
        field="cost",
        header_name="Cost ($)",
        hide=False,
        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
        valueFormatter="data.cost.toLocaleString('en-US');",
    )
    gd.configure_column(
        field="inv_cost",
        header_name="Inventory Cost ($)",
        hide=False,
        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
        valueFormatter="data.inv_cost.toLocaleString('en-US');",
    )
    gd.configure_column(
        field="profit",
        header_name="Profit ($)",
        hide=False,
        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
        valueFormatter="data.profit.toLocaleString('en-US');",
    )
    gd.configure_column(
        field="prec_profit",
        header_name="% Profit",
        hide=False,
        type=["numericColumn", "numberColumnFilter", "customNumericFormat"],
        valueFormatter="data.prec_profit.toLocaleString() +'%';",
    )
    return gd


def read_scenario_details():
    df = pd.read_excel("data/scenarios.xlsx", sheet_name="Details")
    return df