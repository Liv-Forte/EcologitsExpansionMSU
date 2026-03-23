import streamlit as st

from ecologits.tracers.utils import llm_impacts

from src.config.constants import PROMPTS
from src.config.content import HOW_TO_TEXT
from src.core.formatting import format_impacts
from src.core.latency_estimator import latency_estimator
from src.repositories.models import load_models
from src.ui.components import display_model_warnings, render_model_selector
from src.ui.impacts import display_equivalent_energy, display_equivalent_ghg, display_impacts


def msu_mode(key_suffix: str = "msu"):
    """Shared calculator UI — pass a unique key_suffix per tab."""

    # Initialize session state
    tally_key = f"tally_{key_suffix}"
    impacts_key = f"impacts_{key_suffix}"
    if tally_key not in st.session_state:
        st.session_state[tally_key] = 0
    if impacts_key not in st.session_state:
        st.session_state[impacts_key] = None

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
        except Exception as e:
            st.error(f"Error: {e}")

    # Button and tally row — rendered after calculation so tally is already updated
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
            st.markdown(
                '<p align="center">Making this request to the LLM is equivalent to the following actions :</p>',
                unsafe_allow_html=True,
            )
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