#python -m streamlit run app.py run this in terminal to run the app ("http://localhost:8501") 

import streamlit as st
import json
import os
from datetime import datetime
import pandas as pd
from tab_generator import TabGenerator, clean_blank_and_convert_to_numeric
from datamap_parser import parse_datamap_to_json

JSON_FILE = "questions_master.json"

# ----------------------
# Helper functions
# ----------------------
def load_questions():
    """Load questions from local JSON file."""
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r") as f:
            return json.load(f)
    return []

def save_questions(questions):
    """Save questions to local JSON file."""
    with open(JSON_FILE, "w") as f:
        json.dump(questions, f, indent=4)

# ----------------------
# Load existing data
# ----------------------
questions = load_questions()

st.title("Survey Table Config Manager")
# Add new section for datamap import
st.header("Import from Datamap")
uploaded_file = st.file_uploader("Upload Datamap Excel File", type=["xlsx"])

if uploaded_file is not None:
    if st.button("Generate Questions from Datamap"):
        try:
            with st.spinner("Processing datamap..."):
                new_questions = parse_datamap_to_json(uploaded_file)
                
                # Get next available ID
                existing_ids = [q['id'] for q in questions] if questions else [0]
                start_id = max(existing_ids) + 1
                
                # Update IDs to avoid conflicts
                for i, q in enumerate(new_questions):
                    q['id'] = start_id + i
                
                questions.extend(new_questions)
                save_questions(questions)
                
            st.success(f"Added {len(new_questions)} new questions from datamap!")
            st.rerun()
        except Exception as e:
            st.error(f"Error processing datamap: {str(e)}")
st.header("Configuration Section")
data_file = st.text_input("Data File Path", value="Final_CE_10042023_V3.csv")
study_name = st.text_input("Study Name", value="DTV-010 Feature Prioritization")
client_name = st.text_input("Client Name", value="PEERLESS INSIGHTS")

# ----------------------
# Sidebar - View / Select Questions
# ----------------------
st.sidebar.header("Stored Questions")

if questions:
    question_options = {f"ID {q['id']} - {q['question_text']}": q['id'] for q in questions}
    selected_label = st.sidebar.selectbox("Select Question", list(question_options.keys()))
    selected_id = question_options[selected_label]

    col1, col2 = st.sidebar.columns(2)
    if col1.button("Edit"):
        st.session_state.edit_id = selected_id
    if col2.button("Delete"):
        questions = [q for q in questions if q['id'] != selected_id]
        save_questions(questions)
        st.sidebar.success(f"Deleted question ID {selected_id}")
        st.rerun()
else:
    st.sidebar.write("No questions stored yet.")

# ----------------------
# Add/Edit Question Form
# ----------------------
st.header("Add / Edit Question")

if "edit_id" in st.session_state:
    # Load question for editing
    q_to_edit = next((q for q in questions if q['id'] == st.session_state.edit_id), None)
    if q_to_edit:
        question_var_default = ",".join(q_to_edit['question_var']) if isinstance(q_to_edit['question_var'], list) else q_to_edit['question_var']
        question_text_default = q_to_edit['question_text']
        base_text_default = q_to_edit['base_text']
        display_structure_default = json.dumps(q_to_edit['display_structure'], indent=4)
        base_filter_default = q_to_edit['base_filter'] if q_to_edit['base_filter'] else ""
        question_type_default = q_to_edit['question_type']
        mean_var_default = q_to_edit['mean_var'] if q_to_edit['mean_var'] else ""
        show_sigma_default = q_to_edit.get("show_sigma", True)
    else:
        st.session_state.pop("edit_id", None)
        st.warning("Question not found for editing.")
        st.stop()
else:
    # Defaults for new entry
    question_var_default = ""
    question_text_default = ""
    base_text_default = "Total Respondents"
    display_structure_default = json.dumps([
        ["code", "Male", 1],
        ["code", "Female", 2],
        ["net", "All Genders", [1, 2]]
    ], indent=4)
    base_filter_default = ""
    question_type_default = "single"
    mean_var_default = ""
    show_sigma_default = True

with st.form("question_form"):
    question_var = st.text_input("Question Variable", value=question_var_default)
    question_text = st.text_input("Question Text", value=question_text_default)
    base_text = st.text_input("Base Text", value=base_text_default)
    display_structure_text = st.text_area(
        "Display Structure (JSON list of [type, label, code(s)])",
        value=display_structure_default,
        height=300,
        help="Example:\n"
             "[\n"
             "  [\"code\", \"Very Good\", 1],\n"
             "  [\"code\", \"Good\", 2],\n"
             "  [\"net\", \"Top 2 Box (NET)\", [1, 2]]\n"
             "]"
    )
    base_filter = st.text_input("Base Filter (optional)", value=base_filter_default)
    question_type = st.selectbox("Question Type", ["single", "multi", "open_numeric"], 
                                 index=["single", "multi", "open_numeric"].index(question_type_default))
    mean_var = st.text_input("Mean Var (optional)", value=mean_var_default)
    show_sigma = st.checkbox("Show Sigma", value=show_sigma_default)

    submitted = st.form_submit_button("Save Question")

    if submitted:
        try:
            display_structure_raw = json.loads(display_structure_text)
            # Ensure tuples
            display_structure = [tuple(item) for item in display_structure_raw]
        except Exception:
            st.error("Display Structure must be valid JSON in the format: [[\"code\", \"Label\", 1], [\"net\", \"Label\", [1,2]]]")
            st.stop()

        if "edit_id" in st.session_state:
            for q in questions:
                if q['id'] == st.session_state.edit_id:
                    q['question_var'] = question_var.split(",") if "," in question_var else question_var
                    q['question_text'] = question_text
                    q['base_text'] = base_text
                    q['display_structure'] = display_structure
                    q['base_filter'] = base_filter if base_filter else None
                    q['question_type'] = question_type
                    q['mean_var'] = mean_var if mean_var else None
                    q['show_sigma'] = show_sigma
                    break
            save_questions(questions)
            st.success(f"Question ID {st.session_state.edit_id} updated!")
            st.session_state.pop("edit_id", None)
        else:
            new_id = max([q['id'] for q in questions], default=0) + 1
            new_question = {
                "id": new_id,
                "question_var": question_var.split(",") if "," in question_var else question_var,
                "question_text": question_text,
                "base_text": base_text,
                "display_structure": display_structure,
                "base_filter": base_filter if base_filter else None,
                "question_type": question_type,
                "mean_var": mean_var if mean_var else None,
                "show_sigma": show_sigma
            }
            questions.append(new_question)
            save_questions(questions)
            st.success(f"Question saved with ID {new_id}!")

# ----------------------
# Generate Tables Section
# ----------------------
st.header("Generate Tables")
 
if st.button("Generate Output Tables"):
    try:
        # Load the data file
        ext = os.path.splitext(data_file)[1].lower()
        
        if ext == ".csv":
            first_data = pd.read_csv(data_file)
        elif ext in [".xls", ".xlsx"]:
            first_data = pd.read_excel(data_file)
        elif ext == ".sav":
            first_data = pd.read_spss(data_file)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
            
        # Process the data
        first_data = first_data.set_index(keys=["record","uuid"]).sort_index()
        #first_data = clean_blank_and_convert_to_numeric(first_data)  # Make sure this function is defined
        
        # Get current date info
        now = datetime.now()
        month = now.strftime("%B")
        year = now.year
        
        # Define banner segments
        banner_segments = [
            {"id": "A", "label": "Total", "condition": None},
            {"id": "B", "label": "Gen Pop Sample", "condition": "vboost == 1"},
            {"id": "C", "label": "MVPD Users", "condition": "hMVPD == 2"},
            {"id": "D", "label": "vMVPD Users", "condition": "S6r1 == 1 or S6r2 == 1 or S6r3 == 1 or S6r4 == 1 or S6r5 == 1 or S6r6 == 1 or S6r7 == 1 or S6r8 == 1 or S6r9 == 1"},
            {"id": "E", "label": "Male", "condition": "hGender == 1 and vboost == 1"},    
            {"id": "F", "label": "Female", "condition": "hGender == 2 and vboost == 1"},
        ]
        
        results = []
        
        for i, table in enumerate(questions, start=1):
            tg = TabGenerator(
                client_name=client_name,
                study_name=study_name,
                month=month,
                year=year,
                first_data=first_data,
                question_var=table["question_var"],
                question_text=table["question_text"],
                base_text=table["base_text"],
                display_structure=table["display_structure"],
                question_type=table["question_type"],
                table_number=i,
                mean_var=table["mean_var"],
                filter_condition=table["base_filter"],
                show_sigma=table["show_sigma"]
            )
            
            cross_tab_df = tg.generate_crosstab(banner_segments, tg.display_structure)
            
            metadata = pd.DataFrame([
                [""],
                ["#page"],
                [client_name],
                [study_name],
                [f"{month} {year}"],
                [f"Table {i}"],
                [table["question_text"]],
                [f"Base: {table['base_text']}"]
            ], columns=["Label"]).reindex(columns=cross_tab_df.columns, fill_value="")
            
            banner_labels_row = [""] + [seg["label"] for seg in banner_segments]
            banner_ids_row = [""] + [seg["id"] for seg in banner_segments]
            
            banner_labels_row.extend([""] * (len(cross_tab_df.columns) - len(banner_labels_row)))
            banner_ids_row.extend([""] * (len(cross_tab_df.columns) - len(banner_ids_row)))
            
            full_table = pd.concat([
                metadata,
                pd.DataFrame([[""] * len(cross_tab_df.columns)], columns=cross_tab_df.columns),
                pd.DataFrame([banner_labels_row], columns=cross_tab_df.columns),
                pd.DataFrame([banner_ids_row], columns=cross_tab_df.columns),
                cross_tab_df
            ], ignore_index=True)
            
            results.append(full_table)
        
        # Save the output
        today = datetime.today().strftime('%m%d%Y')
        file_name = f"DTV-010_Output_Python_Tab_{today}.csv"
        
        if results:
            final_df = pd.concat(results, ignore_index=True)
            final_df.to_csv(file_name, index=False, header=False)
            final_df.to_csv("tabs_output.csv", index=False, header=False)
            st.success(f"Output saved to {file_name}")
        else:
            st.warning("No tables were generated. Please add questions to the config.")
            
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
 
# ----------------------
# Display Current Questions
# ----------------------
st.markdown("### Current Questions in Database")
st.json(questions)
 