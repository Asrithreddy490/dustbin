# app.py
import streamlit as st
import json
import os
from datetime import datetime
import pandas as pd
from tab_generator import TabGenerator, clean_blank_and_convert_to_numeric
from datamap_parser import parse_datamap_to_json
import pyreadstat  # Add this with other imports

# Constants
JSON_FILE = "questions_master.json"
DEFAULT_DATA_FILE = "Final_CE_10042023_V3.csv"
DEFAULT_STUDY_NAME = "DTV-010 Feature Prioritization"
DEFAULT_CLIENT_NAME = "PEERLESS INSIGHTS"

# ----------------------
# Helper functions
# ----------------------
def load_questions():
    """Load questions from local JSON file with error handling."""
    try:
        if os.path.exists(JSON_FILE):
            with open(JSON_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        st.error(f"Error loading questions: {str(e)}")
        return []

def save_questions(questions):
    """Save questions to local JSON file with error handling."""
    try:
        with open(JSON_FILE, "w", encoding='utf-8') as f:
            json.dump(questions, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error saving questions: {str(e)}")
        return False

def validate_display_structure(structure):
    """Validate the display structure format."""
    if not isinstance(structure, list):
        return False
    for item in structure:
        if not (isinstance(item, (list, tuple)) and len(item) >= 3):
            return False
        if item[0] not in ["code", "net"]:
            return False
    return True

# ----------------------
# Initialize session state
# ----------------------
if 'questions' not in st.session_state:
    st.session_state.questions = load_questions()

# ----------------------
# UI Layout
# ----------------------
st.set_page_config(layout="wide", page_title="Survey Table Config Manager")
st.title("📊 Survey Table Config Manager")

# Sidebar - View/Select Questions
st.sidebar.header("🔍 Stored Questions")

if st.session_state.questions:
    question_options = {f"ID {q['id']} - {q['question_text'][:30]}...": q['id'] 
                      for q in st.session_state.questions}
    selected_label = st.sidebar.selectbox(
        "Select Question", 
        list(question_options.keys()),
        key="question_select"
    )
    selected_id = question_options[selected_label]

    col1, col2 = st.sidebar.columns(2)
    if col1.button("✏️ Edit", key="edit_btn"):
        st.session_state.edit_id = selected_id
        st.rerun()
    if col2.button("🗑️ Delete", key="delete_btn"):
        st.session_state.questions = [q for q in st.session_state.questions 
                                    if q['id'] != selected_id]
        if save_questions(st.session_state.questions):
            st.sidebar.success(f"Deleted question ID {selected_id}")
            st.rerun()
else:
    st.sidebar.info("ℹ️ No questions stored yet. Import or add new questions below.")

# Main content tabs
tab1, tab2, tab3 = st.tabs(["📥 Import Questions", "✏️ Add/Edit Questions", "📊 Generate Tables"])

# ----------------------
# Tab 1: Import Questions
# ----------------------
with tab1:
    st.header("Import from Datamap")
    uploaded_file = st.file_uploader(
        "Upload Datamap Excel File", 
        type=["xlsx"],
        help="Upload your survey datamap Excel file to automatically generate question configurations"
    )

    if uploaded_file is not None:
        if st.button("⚡ Generate Questions from Datamap", type="primary"):
            try:
                with st.spinner("🔍 Processing datamap..."):
                    new_questions = parse_datamap_to_json(uploaded_file)
                    
                    # Get next available ID
                    existing_ids = [q['id'] for q in st.session_state.questions] if st.session_state.questions else [0]
                    start_id = max(existing_ids) + 1
                    
                    # Update IDs to avoid conflicts
                    for i, q in enumerate(new_questions):
                        q['id'] = start_id + i
                    
                    st.session_state.questions.extend(new_questions)
                    if save_questions(st.session_state.questions):
                        st.success(f"✅ Added {len(new_questions)} new questions from datamap!")
                        st.rerun()
            except Exception as e:
                st.error(f"❌ Error processing datamap: {str(e)}")
                st.exception(e)

# ----------------------
# Tab 2: Add/Edit Question
# ----------------------
with tab2:
    st.header("Add / Edit Question")
    
    # Initialize form defaults
    form_defaults = {
        "question_var": "",
        "question_text": "",
        "base_text": "Total Respondents",
        "display_structure": [
            ["code", "Male", 1],
            ["code", "Female", 2],
            ["net", "All Genders", [1, 2]]
        ],
        "base_filter": "",
        "question_type": "single",
        "mean_var": "",
        "show_sigma": True
    }

    # Load question for editing if in edit mode
    if "edit_id" in st.session_state:
        q_to_edit = next((q for q in st.session_state.questions 
                         if q['id'] == st.session_state.edit_id), None)
        if q_to_edit:
            form_defaults.update({
                "question_var": ",".join(q_to_edit['question_var']) 
                              if isinstance(q_to_edit['question_var'], list) 
                              else q_to_edit['question_var'],
                "question_text": q_to_edit['question_text'],
                "base_text": q_to_edit['base_text'],
                "display_structure": q_to_edit['display_structure'],
                "base_filter": q_to_edit['base_filter'] or "",
                "question_type": q_to_edit['question_type'],
                "mean_var": q_to_edit['mean_var'] or "",
                "show_sigma": q_to_edit.get("show_sigma", True)
            })
        else:
            st.warning("Question not found for editing.")
            st.session_state.pop("edit_id", None)

    with st.form("question_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            question_var = st.text_input(
                "Question Variable*",
                value=form_defaults["question_var"],
                help="Variable name(s) from dataset. Separate multiple with commas for multi-select questions"
            )
            question_text = st.text_input(
                "Question Text*",
                value=form_defaults["question_text"],
                help="The text that will appear as the question title in tables"
            )
            base_text = st.text_input(
                "Base Text*",
                value=form_defaults["base_text"],
                help="Base description (e.g., 'Total Respondents')"
            )
            question_type = st.selectbox(
                "Question Type*",
                ["single", "multi", "open_numeric"],
                index=["single", "multi", "open_numeric"].index(form_defaults["question_type"]),
                help="Single-select, Multi-select, or Open Numeric question"
            )
            
        with col2:
            display_structure = st.text_area(
                "Display Structure (JSON)*",
                value=json.dumps(form_defaults["display_structure"], indent=2),
                height=200,
                help="""Format: [["type", "label", code(s)]]
Example:
[
  ["code", "Very Good", 1],
  ["code", "Good", 2],
  ["net", "Top 2 Box (NET)", [1, 2]]
]"""
            )
            base_filter = st.text_input(
                "Base Filter",
                value=form_defaults["base_filter"],
                help="Optional filter condition (e.g., 'Q1 == 1')"
            )
            mean_var = st.text_input(
                "Mean Variable",
                value=form_defaults["mean_var"],
                help="Optional variable for calculating means"
            )
            show_sigma = st.checkbox(
                "Show Sigma",
                value=form_defaults["show_sigma"],
                help="Show statistical significance testing"
            )

        submitted = st.form_submit_button("💾 Save Question", type="primary")

        if submitted:
            # Validate required fields
            if not all([question_var, question_text, base_text, display_structure]):
                st.error("Please fill in all required fields (*)")
                st.stop()

            try:
                display_structure_parsed = json.loads(display_structure)
                if not validate_display_structure(display_structure_parsed):
                    st.error("Invalid display structure format")
                    st.stop()
            except json.JSONDecodeError:
                st.error("Display Structure must be valid JSON")
                st.stop()

            # Prepare question data
            question_data = {
                "question_var": [v.strip() for v in question_var.split(",")] 
                              if "," in question_var else question_var,
                "question_text": question_text,
                "base_text": base_text,
                "display_structure": display_structure_parsed,
                "base_filter": base_filter if base_filter else None,
                "question_type": question_type,
                "mean_var": mean_var if mean_var else None,
                "show_sigma": show_sigma
            }

            if "edit_id" in st.session_state:
                # Update existing question
                for q in st.session_state.questions:
                    if q['id'] == st.session_state.edit_id:
                        q.update(question_data)
                        break
                success_msg = f"Question ID {st.session_state.edit_id} updated!"
                st.session_state.pop("edit_id", None)
            else:
                # Add new question
                new_id = max([q['id'] for q in st.session_state.questions], default=0) + 1
                question_data["id"] = new_id
                st.session_state.questions.append(question_data)
                success_msg = f"Question saved with ID {new_id}!"

            if save_questions(st.session_state.questions):
                st.success(success_msg)
                st.rerun()

# ----------------------
# Tab 3: Generate Tables
# ----------------------
with tab3:
    st.header("Generate Output Tables")
    
    with st.expander("⚙️ Configuration", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            data_file = st.text_input(
                "Data File Path*",
                value=DEFAULT_DATA_FILE,
                help="Path to your data file (CSV, Excel, or SPSS)"
            )
        with col2:
            study_name = st.text_input(
                "Study Name*",
                value=DEFAULT_STUDY_NAME
            )
        with col3:
            client_name = st.text_input(
                "Client Name*",
                value=DEFAULT_CLIENT_NAME
            )

    # Banner configuration
    st.subheader("Banner Configuration")
    banner_config = [
        {"id": "A", "label": "Total", "condition": None},
        {"id": "B", "label": "Gen Pop Sample", "condition": "vboost == 1"},
        {"id": "C", "label": "MVPD Users", "condition": "hMVPD == 2"},
        {"id": "D", "label": "vMVPD Users", "condition": "S6r1 == 1 or S6r2 == 1 or S6r3 == 1 or S6r4 == 1 or S6r5 == 1 or S6r6 == 1 or S6r7 == 1 or S6r8 == 1 or S6r9 == 1"},
        {"id": "E", "label": "Male", "condition": "hGender == 1 and vboost == 1"},    
        {"id": "F", "label": "Female", "condition": "hGender == 2 and vboost == 1"},
    ]
    
    if st.button("✨ Generate Tables", type="primary", disabled=not st.session_state.questions):
        if not all([data_file, study_name, client_name]):
            st.error("Please fill in all required configuration fields (*)")
            st.stop()

        if not os.path.exists(data_file):
            st.error(f"Data file not found at: {data_file}")
            st.stop()

        try:
            with st.spinner("⏳ Generating tables..."):
                # Load data
                ext = os.path.splitext(data_file)[1].lower()
                if ext == ".csv":
                    data = pd.read_csv(data_file)
                elif ext == ".xls":
                    try:
                        data = pd.read_excel(data_file, engine='xlrd')
                    except ImportError:
                        st.error("❌ xlrd package required for .xls files")
                        st.info("Please run: pip install xlrd")
                        st.stop()
                elif ext == ".xlsx":
                    try:
                        data = pd.read_excel(data_file, engine='openpyxl')
                    except ImportError:
                        st.error("❌ openpyxl package required for .xlsx files")
                        st.info("Please run: pip install openpyxl")
                        st.stop()
                elif ext == ".sav":
                    try:
                        data, _ = pyreadstat.read_sav(data_file)
                    except Exception as e:
                        st.error(f"❌ Failed to read SPSS file: {str(e)}")
                        st.info("Try exporting your data to CSV/Excel and re-uploading")
                        st.stop()
                else:
                    raise ValueError(f"Unsupported file format: {ext}")

                # Process data
                data = data.set_index(keys=["record","uuid"]).sort_index()
                data = clean_blank_and_convert_to_numeric(data)

                # Get current date
                now = datetime.now()
                month = now.strftime("%B")
                year = now.year

                # Generate tables
                results = []
                for i, question in enumerate(st.session_state.questions, start=1):
                    tg = TabGenerator(
                        client_name=client_name,
                        study_name=study_name,
                        month=month,
                        year=year,
                        first_data=data,
                        question_var=question["question_var"],
                        question_text=question["question_text"],
                        base_text=question["base_text"],
                        display_structure=question["display_structure"],
                        question_type=question["question_type"],
                        table_number=i,
                        mean_var=question["mean_var"],
                        filter_condition=question["base_filter"],
                        show_sigma=question["show_sigma"]
                    )
                    
                    cross_tab_df = tg.generate_crosstab(banner_config, tg.display_structure)
                    
                    # Prepare metadata rows
                    metadata = pd.DataFrame([
                        [""],
                        ["#page"],
                        [client_name],
                        [study_name],
                        [f"{month} {year}"],
                        [f"Table {i}"],
                        [question["question_text"]],
                        [f"Base: {question['base_text']}"]
                    ], columns=["Label"]).reindex(columns=cross_tab_df.columns, fill_value="")
                    
                    # Prepare banner rows
                    banner_labels = [""] + [seg["label"] for seg in banner_config]
                    banner_ids = [""] + [seg["id"] for seg in banner_config]
                    
                    # Combine all components
                    full_table = pd.concat([
                        metadata,
                        pd.DataFrame([[""] * len(cross_tab_df.columns)], columns=cross_tab_df.columns),
                        pd.DataFrame([banner_labels], columns=cross_tab_df.columns),
                        pd.DataFrame([banner_ids], columns=cross_tab_df.columns),
                        cross_tab_df
                    ], ignore_index=True)
                    
                    results.append(full_table)

                # Save output
                today = datetime.today().strftime('%m%d%Y')
                file_name = f"{study_name.replace(' ', '_')}_Output_Tables_{today}.csv"
                
                if results:
                    final_df = pd.concat(results, ignore_index=True)
                    final_df.to_csv(file_name, index=False, header=False)
                    st.success(f"✅ Tables generated successfully! Saved to: {file_name}")
                    
                    # Provide download button
                    with open(file_name, "rb") as f:
                        st.download_button(
                            label="⬇️ Download Tables",
                            data=f,
                            file_name=file_name,
                            mime="text/csv"
                        )
                else:
                    st.warning("No tables were generated")

        except Exception as e:
            st.error(f"❌ Error generating tables: {str(e)}")
            st.exception(e)

# ----------------------
# Current Questions Display
# ----------------------
with st.expander("📋 View Current Questions (JSON)"):
    st.json(st.session_state.questions)