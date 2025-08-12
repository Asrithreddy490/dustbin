
import pandas as pd
import numpy as np
from datetime import datetime
#import copy
import json
import os

#first_data = pd.read_csv("Final_CE_10042023_V3.csv").set_index(keys=["record","uuid"]).sort_index()
#first_data.head()

def clean_blank_and_convert_to_numeric(first_data):
    exclude_cols = ['date','markers','record','uuid']
    cols_to_convert = first_data.columns.difference(exclude_cols)
    first_data[cols_to_convert] = first_data[cols_to_convert].replace({' ':np.nan,'':np.nan})
    first_data[cols_to_convert] = first_data[cols_to_convert].apply(pd.to_numeric,errors='coerce')
    return first_data



class TabGenerator:
    def __init__(self, first_data, question_var, question_text, base_text, display_structure,
                 table_number, study_name, client_name, month, year, question_type, mean_var,
                 filter_condition=None, show_sigma=True):
        self.df = first_data.copy()
        self.question_var = question_var
        self.question_text = question_text
        self.base_text = base_text
        self.display_structure = display_structure
        self.codes_dict = {payload: label for row_type, label, payload in (display_structure or [])
                           if row_type == "code"}
        self.multi_vars = [payload for row_type, label, payload in (display_structure or [])
                           if row_type == "code" and isinstance(payload, str)]
        self.table_number = table_number
        self.study_name = study_name
        self.client_name = client_name
        self.month = month
        self.year = year
        self.question_type = question_type
        self.mean = mean_var
        self.filter_condition = filter_condition
        self.show_sigma = show_sigma

    def _get_multi_columns(self):
        if self.multi_vars:
            return self.multi_vars
        return [k for k in self.codes_dict.keys() if isinstance(k, str)]
    
    def open_numeric_table(self):
        df_filtered = self.apply_filter(self.df,self.filter_condition)
        numeric_data = pd.to_numeric(df_filtered[self.question_var], errors='coerce')
        dist_counts = numeric_data.value_counts().sort_index()
        total_valid = dist_counts.sum()
        valid_percent = ((dist_counts / total_valid) * 100).round(2)
        dist_df = pd.DataFrame({'Count': dist_counts, 'Percent': valid_percent}).reset_index()
        dist_df.rename(columns={'index': 'Value'}, inplace=True)
        return dist_df
        

    def calculate_sigma_and_no_answer(self, df_filtered, base_n, total_count, question_type):
        result = {}
        if base_n == 0:
            no_answer_count = 0
        elif question_type == "single":
            no_answer_count = max(0, base_n - int(total_count))
        elif question_type == "multi":
            multi_cols = self._get_multi_columns()
            if not multi_cols:
                answered_mask = df_filtered.notna().any(axis=1)
            else:
                answered_mask = (df_filtered[multi_cols] == 1).any(axis=1)
            no_answer_count = int(base_n - int(answered_mask.sum()))
        else:
            no_answer_count = 0

        no_answer_percent = (no_answer_count / base_n) * 100 if base_n > 0 else 0
        if no_answer_count > 0:
            result["No Answer"] = [no_answer_count, f"{no_answer_percent:.2f}%"]

        sigma_count = total_count + no_answer_count
        sigma_percent = (sigma_count / base_n) * 100 if base_n > 0 else 0
        result["Sigma"] = [sigma_count, f"{sigma_percent:.2f}%"]
        return result
    
    def calculate_stats(self, df_filtered):
        result = {}
        if self.mean and self.mean in df_filtered.columns:
            mean = df_filtered[self.mean].mean()
            std_val = df_filtered[self.mean].std()
            sem_val = df_filtered[self.mean].sem()
            median_val = df_filtered[self.mean].median()
            result["Mean"] = [f"{mean:.2f}", ""]
            result["Std.err"] = [f"{std_val:.2f}", ""]
            result["Std.dev"] = [f"{sem_val:.2f}", ""]
            result["Median"] = [f"{median_val:.2f}", ""]
        return result

    def generate_crosstab(self, banner_segments, display_structure=None):
        if display_structure is None:
            display_structure = self.display_structure

        banner_data = {}
        base_ns = {}
        labels = [label for _, label, _ in display_structure]
        used_labels = set(labels)

        for banner in banner_segments:
            condition = banner.get("condition")
            banner_id = banner["id"]

            if self.filter_condition:
                df_base_filter = self.df.query(self.filter_condition)
            else:
                df_base_filter = self.df

            if condition:
                df_filtered = df_base_filter.query(condition)
            else:
                df_filtered = df_base_filter

            base_n = len(df_filtered)
            base_ns[banner_id] = base_n
            banner_data[banner_id] = {}
            total_count = 0

            for row_type, label_text, payload in display_structure:
                if self.question_type == "single":
                    if row_type == "code":
                        code = payload
                        count = int((df_filtered[self.question_var] == code).sum())
                        pct = (count / base_n * 100) if base_n > 0 else 0
                        banner_data[banner_id][label_text] = [count, f"{pct:.2f}%"]
                        total_count += count
                    elif row_type == "net" and isinstance(payload, list):
                        count = int(df_filtered[self.question_var].isin(payload).sum())
                        pct = (count / base_n * 100) if base_n > 0 else 0
                        banner_data[banner_id][label_text] = [count, f"{pct:.2f}%"]
                        used_labels.add(label_text)

                elif self.question_type == "multi":
                    if row_type == "code":
                        col = (payload)
                        count = int((df_filtered[col] == 1).sum()) if col in df_filtered.columns else 0
                        pct = (count / base_n * 100) if base_n > 0 else 0
                        banner_data[banner_id][label_text] = [count, f"{pct:.2f}%"]
                        total_count += count
                    elif row_type == "net" and isinstance(payload, list):
                        present = [(c) for c in payload if (c) in df_filtered.columns]
                        count = int(df_filtered[present].sum().sum()) if present else 0
                        pct = (count / base_n * 100) if base_n > 0 else 0
                        banner_data[banner_id][label_text] = [count, f"{pct:.2f}%"]
                        used_labels.add(label_text)
                elif self.question_type == "numeric":
                    dist_df = self.open_numeric_table(df_filtered)
                    for _, row in dist_df.iterrows():
                        label = row["index"]
                        count = row["Count"]
                        pct = row["Percent"]
                        banner_data[banner_id][label] = [count, f"{pct:.2f}%"]
                        used_labels.add(label)
                        total_count = dist_df
                    
                


            if self.show_sigma:
                sigma_data = self.calculate_sigma_and_no_answer(df_filtered, base_n, total_count, self.question_type)
                for lbl, vals in sigma_data.items():
                    banner_data[banner_id][lbl] = vals
                    used_labels.add(lbl)
            stats_data = self.calculate_stats(df_filtered)
            for lbl, vals in stats_data.items():
                banner_data[banner_id][lbl] = vals
                used_labels.add(lbl)

        final_labels = [label for _, label, _ in display_structure]
        if self.show_sigma and "No Answer" in used_labels:
            final_labels.append("No Answer")
        if self.show_sigma and "Sigma" in used_labels:
            final_labels.append("Sigma")
        for stat in ["Mean", "Std.err", "Std.dev", "Median"]:
            if stat in used_labels:
                final_labels.append(stat)

        header = ["Label"] + [f"{seg['id']} ({seg['label']})" for seg in banner_segments]
        output = [["Base"] + [base_ns[seg["id"]] for seg in banner_segments]]

        for label in final_labels:
            count_row = [label]
            percent_row = [""]
            has_percent = False
            for seg in banner_segments:
                values = banner_data[seg["id"]].get(label, [0, ""])
                count_row.append(values[0])
                percent_row.append(values[1])
                if values[1]:
                    has_percent = True
            output.append(count_row)
            if has_percent:
                output.append(percent_row)

        return pd.DataFrame(output, columns=header)

    def generate(self):
        if self.filter_condition:
            df_filtered = self.df.query(self.filter_condition)
        else:
            df_filtered = self.df

        base_n = len(df_filtered)
        total_count = 0
        results = {}

        for row_type, label_text, payload in self.display_structure:
            if self.question_type == "single":
                if row_type == "code":
                    count = int((df_filtered[self.question_var] == payload).sum())
                    pct = (count / base_n * 100) if base_n > 0 else 0
                    results[label_text] = [count, f"{pct:.2f}%"]
                    total_count += count
                elif row_type == "net" and isinstance(payload, list):
                    count = int(df_filtered[self.question_var].isin(payload).sum())
                    pct = (count / base_n * 100) if base_n > 0 else 0
                    results[label_text] = [count, f"{pct:.2f}%"]

            elif self.question_type == "multi":
                if row_type == "code":
                    col = (payload)
                    count = ((df_filtered[col] == 1).sum()) if col in df_filtered.columns else 0
                    pct = (count / base_n * 100) if base_n > 0 else 0
                    results[label_text] = [count, f"{pct:.2f}%"]
                    total_count += count
                elif row_type == "net" and isinstance(payload, list):
                    present_cols = [(c) for c in payload if (c) in df_filtered.columns]
                    count = int(df_filtered[present_cols].sum().sum()) if present_cols else 0
                    pct = (count / base_n * 100) if base_n > 0 else 0
                    results[label_text] = [count, f"{pct:.2f}%"]
            elif self.question_type == "numeric":
                    dist_df = self.open_numeric_table(df_filtered)
                    for _, row in dist_df.iterrows():
                        label = row["index"]
                        count = row["Count"]
                        pct = row["Percent"]
                        results[label] = [count, f"{pct:.2f}%"]
                        total_count = dist_df['Count'].sum()

            

        if self.show_sigma:
            sigma_data = self.calculate_sigma_and_no_answer(df_filtered, base_n, total_count, self.question_type)
            for lbl, vals in sigma_data.items():
                results[lbl] = vals

        results.update(self.calculate_stats(df_filtered))

        output = [["Base", base_n]]
        for label, vals in results.items():
            output.append([label, vals[0]])
            if vals[1]:
                output.append(["", vals[1]])

        return pd.DataFrame(output, columns=["Label", self.base_text])



def main():
    first_data = pd.read_csv("Final_CE_10042023_V3.csv").set_index(keys=["record","uuid"]).sort_index()
    first_data = clean_blank_and_convert_to_numeric(first_data)
    file_path = "questions_master.json"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            tabs_config = json.load(f)
    else:
        print(f"File '{file_path}' does not exist. Proceeding with an empty configuration.")
        tabs_config = []

#with open("questions_master.json", "r") as f:
    #tabs_config = json.load(f)


    for table in tabs_config:
        for item in table["display_structure"]:
            if len(item) >= 3 and isinstance(item[2], dict):
                # Convert dict keys to int if numeric
                if table.get("question_type") == "single":
                    item[2] = {
                        int(k) if isinstance(k, str) and k.isdigit() else k: v
                        for k, v in item[2].items()
                    }
                
    study_name = "DTV-010 Feature Prioritization"
    client_name = "PEERLESS INSIGHTS"
    now = datetime.now()
    month =  now.strftime("%B")
    year = now.year

    banner_segments = [
        {"id": "A", "label": "Total", "condition": None},
        {"id": "B", "label": "Gen Pop Sample", "condition": "vboost == 1"},
        {"id": "C", "label": "MVPD Users", "condition": "hMVPD == 2"},
        {"id": "D", "label": "vMVPD Users", "condition": "S6r1 == 1 or S6r2 == 1 or S6r3 == 1 or S6r4 == 1 or S6r5 == 1 or S6r6 == 1 or S6r7 == 1 or S6r8 == 1 or S6r9 == 1"},
        {"id": "E", "label": "Male", "condition": "hGender == 1 and vboost == 1"},    
        {"id": "F", "label": "Female", "condition": "hGender == 2 and vboost == 1"}    
    ]
    results = []

    for i, table in enumerate(tabs_config, start=1):
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

    if results:
        today = datetime.today().strftime('%m%d%Y')
        file_name = f"DTV-010_Output_Python_Tab_{today}.csv"
        final_df = pd.concat(results, ignore_index=True)
        final_df.to_csv(file_name, index=False, header=False)
        final_df.to_csv("tabs_output.csv", index=False, header=False)
        print(f"Output saved to {file_name}")
    else:
        print("As of now, there is no output to save. Please add tabs to the config file.")
