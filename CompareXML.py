import streamlit as st
import xml.etree.ElementTree as ET
import csv
import io
from datetime import datetime

# === 📘 Constraint type dictionary ===
CONSTRAINT_TYPES = {
    '0': 'As Soon As Possible',
    '1': 'As Late As Possible',
    '2': 'Must Start On',
    '3': 'Must Finish On',
    '4': 'Start No Earlier Than',
    '5': 'Start No Later Than',
    '6': 'Finish No Earlier Than',
    '7': 'Finish No Later Than'
}

# === 🔍 Parse tasks from a file ===
def parse_tasks(uploaded_file):
    tree = ET.parse(uploaded_file)
    root = tree.getroot()
    ns = {'ns': root.tag.split('}')[0].strip('{')}

    tasks = {}
    task_elements = root.find('ns:Tasks', ns)
    for task in task_elements.findall('ns:Task', ns):
        # Only include non-summary tasks
        is_summary = task.findtext('ns:Summary', default='1', namespaces=ns)
        if is_summary != '0':
            continue

        uid = task.findtext('ns:UID', default='', namespaces=ns)
        name = task.findtext('ns:Name', default='', namespaces=ns)
        constraint = task.findtext('ns:ConstraintType', default='', namespaces=ns)
        duration = task.findtext('ns:Duration', default='', namespaces=ns)

        predecessors = [
            pred.findtext('ns:PredecessorUID', default='', namespaces=ns)
            for pred in task.findall('ns:PredecessorLink', ns)
        ]

        tasks[uid] = {
            'TaskName': name,
            'ConstraintType': CONSTRAINT_TYPES.get(constraint, f"Unknown ({constraint})"),
            'Duration': duration,
            'Predecessors': sorted(p for p in predecessors if p),
            'Successors': []
        }

    # Fill successors
    for uid, task in tasks.items():
        for pred_uid in task['Predecessors']:
            if pred_uid in tasks:
                tasks[pred_uid]['Successors'].append(uid)

    for task in tasks.values():
        task['Successors'].sort()

    return tasks

# === 🧪 Compare two task dictionaries ===
def compare_tasks(tasks1, tasks2, file1_label, file2_label):
    all_uids = sorted(set(tasks1.keys()).union(set(tasks2.keys())))
    output = io.StringIO()
    writer = csv.writer(output)

    report_lines = []
    writer.writerow(['=== Missing Tasks ==='])
    writer.writerow(['Task UID', 'Results'])
    for uid in all_uids:
        task1 = tasks1.get(uid)
        task2 = tasks2.get(uid)
        if not task1:
            name = task2['TaskName']
            msg = f'Task UID {uid} ("{name}") is missing in {file1_label}'
            report_lines.append(f"\n❌ {msg}")
            writer.writerow([uid, msg])
        elif not task2:
            name = task1['TaskName']
            msg = f'Task UID {uid} ("{name}") is missing in {file2_label}'
            report_lines.append(f"\n❌ {msg}")
            writer.writerow([uid, msg])

    writer.writerow([])
    writer.writerow([])
    writer.writerow(['=== Task Differences ==='])
    writer.writerow(['Task UID', 'Task Name', 'Field', f'Value in {file1_label}', f'Value in {file2_label}'])

    for uid in all_uids:
        task1 = tasks1.get(uid)
        task2 = tasks2.get(uid)
        if not task1 or not task2:
            continue

        diffs = []
        if task1['TaskName'] != task2['TaskName']:
            diffs.append(('TaskName', task1['TaskName'], task2['TaskName']))
        if task1['ConstraintType'] != task2['ConstraintType']:
            diffs.append(('ConstraintType', task1['ConstraintType'], task2['ConstraintType']))
        if task1['Duration'] != task2['Duration']:
            diffs.append(('Duration', task1['Duration'], task2['Duration']))
        if task1['Predecessors'] != task2['Predecessors']:
            diffs.append(('Predecessors', task1['Predecessors'], task2['Predecessors']))
        if task1['Successors'] != task2['Successors']:
            diffs.append(('Successors', task1['Successors'], task2['Successors']))

        if diffs:
            task_name = task1['TaskName'] or task2['TaskName'] or '(No Name)'
            report_lines.append(f"\n🔍 Differences in Task UID {uid}, Task Name \"{task_name}\":")
            for label, val1, val2 in diffs:
                report_lines.append(f"❗ {label}:\n   {file1_label}: {val1}\n   {file2_label}: {val2}")
                writer.writerow([uid, task_name, label, val1, val2])

    csv_bytes = output.getvalue().encode('utf-8')
    return "\n".join(report_lines), csv_bytes

# === 🚀 Streamlit App ===
st.title("📊 MS Project XML Task Comparator")
st.markdown("Upload two Microsoft Project XML files and compare task-level differences.")

file1 = st.file_uploader("Upload File 1", type=["xml"])
file2 = st.file_uploader("Upload File 2", type=["xml"])

if file1 and file2:
    if st.button("Run Comparison"):
        with st.spinner("Parsing and comparing tasks..."):
            tasks1 = parse_tasks(file1)
            tasks2 = parse_tasks(file2)
            report_text, csv_data = compare_tasks(tasks1, tasks2, file1.name, file2.name)

        st.success("Comparison complete!")
        st.subheader("🧾 Report")
        st.code(report_text, language='text')

        st.download_button(
            label="⬇️ Download CSV Report",
            data=csv_data,
            file_name=f"comparison_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime='text/csv'
        )
