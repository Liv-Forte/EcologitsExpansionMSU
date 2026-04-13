import streamlit as st

from ecologits.tracers.utils import llm_impacts

from src.config.constants import PROMPTS
from src.config.content import HOW_TO_TEXT
from src.core.formatting import format_impacts
from src.core.latency_estimator import latency_estimator
from src.core.equivalences import format_gwp_eq_airplane_paris_nyc
from src.repositories.models import load_models
from src.ui.components import display_model_warnings, render_model_selector
from src.ui.impacts import display_equivalent_energy, display_equivalent_ghg, display_impacts


def msu_mode(key_suffix: str = "msu"):
    """Shared calculator UI — pass a unique key_suffix per tab."""

    from src.core.units import q

    # Initialize session state
    tally_key = f"tally_{key_suffix}"
    impacts_key = f"impacts_{key_suffix}"
    streaming_total_key = f"streaming_total_{key_suffix}"
    flights_total_key = f"flights_total_{key_suffix}"
    model_counts_key = f"model_counts_{key_suffix}"

    if tally_key not in st.session_state:
        st.session_state[tally_key] = 0
    if impacts_key not in st.session_state:
        st.session_state[impacts_key] = None
    if streaming_total_key not in st.session_state:
        st.session_state[streaming_total_key] = 0.0
    if flights_total_key not in st.session_state:
        st.session_state[flights_total_key] = 0.0
    if model_counts_key not in st.session_state:
        st.session_state[model_counts_key] = {}

    # Reserve placeholders at the very top
    charts_placeholder = st.empty()
    top_placeholder = st.empty()

    with st.container(border=True):
        df = load_models(filter_main=True)

        col1, col2, col3 = st.columns(3)

        provider, model = render_model_selector(df, col1, col2, key_suffix=key_suffix)

        with col3:
            output_tokens = st.selectbox(
                label="Example prompt",
                options=[x[0] for x in PROMPTS],
                index=2,
                key=f"prompt_{key_suffix}",
            )

        provider_raw = df[(df["provider_clean"] == provider) & (df["name_clean"] == model)][
            "provider"
        ].values[0]
        model_raw = df[(df["provider_clean"] == provider) & (df["name_clean"] == model)][
            "name"
        ].values[0]

        display_model_warnings(df, provider, model)

    # Run calculation only on button click
    if st.session_state.get(f"button_{key_suffix}"):
        try:
            output_tokens_count = next(x[1] for x in PROMPTS if x[0] == output_tokens)
            estimated_latency = latency_estimator.estimate(
                provider=provider_raw,
                model_name=model_raw,
                output_tokens=output_tokens_count,
            )
            impacts = llm_impacts(
                provider=provider_raw,
                model_name=model_raw,
                output_token_count=output_tokens_count,
                request_latency=estimated_latency,
            )
            impacts, _, _ = format_impacts(impacts)
            st.session_state[impacts_key] = impacts
            st.session_state[tally_key] += 1

            # Raw streaming: gwp * 15.6 h/kgCO2eq, converted to seconds to match display
            STREAMING_GWP_EQ = q("15.6 h / kgCO2eq")
            streaming_eq = (impacts.gwp * STREAMING_GWP_EQ).to("s")
            st.session_state[streaming_total_key] += streaming_eq.magnitude

            # Flights: use format_gwp_eq_airplane_paris_nyc for correct MSU scaling
            flights_value = format_gwp_eq_airplane_paris_nyc(impacts.gwp)
            st.session_state[flights_total_key] += flights_value.magnitude

            # Increment provider count
            counts = st.session_state[model_counts_key]
            counts[provider] = counts.get(provider, 0) + 1
            st.session_state[model_counts_key] = counts

        except Exception as e:
            st.error(f"Error: {e}")

    # Fill top sentence placeholder
    if st.session_state[impacts_key] is not None:
        top_placeholder.markdown(
            '<p align="center">Making this request to the LLM is equivalent to the following actions :</p>',
            unsafe_allow_html=True,
        )

    # Render charts/metrics into top placeholder
    if st.session_state[tally_key] > 0:
        import plotly.express as px

        with charts_placeholder.container():
            st.markdown('<h1 align="center">How Much Energy Does Generative AI Use? Cumulated Result:</h1>', unsafe_allow_html=True)

            col_s, col_f, col_m = st.columns(3)

            # Metric 1: Streaming time (in minutes)
            with col_s:
                streaming_minutes = st.session_state[streaming_total_key] / 60
                st.markdown(f"""
                    <div style='padding-top: 80px; text-align: center;'>
                        <p style='font-size: 5rem; font-weight: bold; margin: 0;'>⏯️</p>
                        <p style='font-size: 2rem; color: gray; margin-bottom: 4px;'>Total Streaming Time (Min)</p>
                        <p style='font-size: 5rem; font-weight: bold; margin: 0;'>{streaming_minutes:.3f} min</p>
                    </div>
                """, unsafe_allow_html=True)

            # Metric 2: Equivalent flights
            with col_f:
                st.markdown(f"""
                    <div style='padding-top: 80px; text-align: center;'>
                        <p style='font-size: 5rem; font-weight: bold; margin: 0;'>✈️</p>
                        <p style='font-size: 1.5rem; color: gray; margin-bottom: 4px;'>Total Equivalent Flights (Paris ↔ NYC)<br>If Every Student at MSU did this Every Day for a Year</p>
                        <p style='font-size: 5rem; font-weight: bold; margin: 0;'>{st.session_state[flights_total_key]:.3f}</p>
                    </div>
                """, unsafe_allow_html=True)

            # Chart 3: Responses per provider
            model_counts = st.session_state[model_counts_key]
            with col_m:
                fig_models = px.pie(
                    values=list(model_counts.values()),
                    names=list(model_counts.keys()),
                    color_discrete_sequence=["#00BF63", "#0B3B36", "#00A854", "#024D3F",
                                             "#00D66E", "#013328", "#00EB78", "#012B23"],
                )
                fig_models.update_traces(domain=dict(x=[0.1, 0.9], y=[0.1, 0.9]))
                fig_models.update_layout(
                    title=dict(
                        text="Responses by Provider",
                        x=0.5,
                        xanchor="center",
                        font=dict(size=30),
                    ),
                    font=dict(size=30),
                    legend=dict(font=dict(size=30)),
                    margin=dict(t=60, b=10, l=10, r=10),
                )
                st.plotly_chart(fig_models, use_container_width=True)

    # Button and tally row
    col_btn, col_tally = st.columns([1, 3])
    with col_btn:
        st.button("Calculate", key=f"button_{key_suffix}")
    with col_tally:
        st.metric("Total Calculations:", st.session_state[tally_key])

    # Display results from session state
    if st.session_state[impacts_key] is not None:
        impacts = st.session_state[impacts_key]

        with st.container(border=False):
            st.markdown('<h3 align="center">Equivalences</h3>', unsafe_allow_html=True)

            page = st.radio(
                "Equivalent to display",
                ["Energy", "GHG"],
                horizontal=True,
                label_visibility="collapsed",
                key=f"radio_{key_suffix}",
            )

            with st.container(border=True):
                if page == "Energy":
                    display_equivalent_energy(impacts)
                else:
                    display_equivalent_ghg(impacts)

        with st.container(border=True):
            st.markdown(
                '<h3 align="center">Environmental impacts</h3>',
                unsafe_allow_html=True,
            )
            display_impacts(impacts)

    st.expander("How to use this calculator?", expanded=False).markdown(HOW_TO_TEXT)


def calculator_mode():
    tab1, tab2 = st.tabs(["Calculator 1", "Calculator 2"])

    with tab1:
        msu_mode(key_suffix="calc1")

    with tab2:
        msu_mode(key_suffix="calc2")