import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import hashlib
import gspread
from google.oauth2 import service_account
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image

st.set_page_config(page_title="Printer Service CRM", page_icon="🖨️", layout="wide")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_password():
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    if st.session_state['authenticated']:
        return True
    st.markdown("## 🔒 Login Required")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        if submit:
            try:
                correct_password = st.secrets["passwords"]["admin_password"]
                if username == "admin" and hash_password(password) == hash_password(correct_password):
                    st.session_state['authenticated'] = True
                    st.session_state['username'] = username
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password")
            except KeyError:
                st.error("❌ Password not configured in secrets!")
                return False
    return False

def remove_diacritics(text):
    if not isinstance(text, str):
        return text
    diacritics_map = {'ă':'a','Ă':'A','â':'a','Â':'A','î':'i','Î':'I','ș':'s','Ș':'S','ț':'t','Ț':'T'}
    for d, r in diacritics_map.items():
        text = text.replace(d, r)
    return text

@st.cache_resource
def get_google_sheets_client():
    try:
        credentials = service_account.Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]),
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {str(e)}")
        return None

def test_sheets_connection():
    try:
        client = get_google_sheets_client()
        if client:
            spreadsheet_id = st.secrets["sheets"]["spreadsheet_id"]
            sheet = client.open_by_key(spreadsheet_id)
            st.sidebar.success("✅ Connected to Google Sheets!")
            return True
        return False
    except Exception as e:
        st.sidebar.error(f"❌ Sheets error: {str(e)}")
        return False

def generate_initial_receipt_pdf(order, company_info, logo_image=None):
    buffer = io.BytesIO()
    width, height = 210*mm, 148.5*mm
    c = canvas.Canvas(buffer, pagesize=(width, height))
    if logo_image:
        try:
            logo = Image.open(logo_image)
            logo.thumbnail((150,95), Image.Resampling.LANCZOS)
            logo_buffer = io.BytesIO()
            logo.save(logo_buffer, format='PNG')
            logo_buffer.seek(0)
            c.drawImage(ImageReader(logo_buffer), 10*mm, height-30*mm, width=40*mm, height=25*mm, preserveAspectRatio=True, mask='auto')
        except:
            c.setFillColor(colors.HexColor('#f0f0f0'))
            c.rect(10*mm, height-30*mm, 40*mm, 25*mm, fill=1, stroke=1)
            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(15*mm, height-20*mm, "[LOGO]")
    else:
        c.setFillColor(colors.HexColor('#f0f0f0'))
        c.rect(10*mm, height-30*mm, 40*mm, 25*mm, fill=1, stroke=1)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(15*mm, height-20*mm, "[LOGO]")
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(10*mm, height-35*mm, remove_diacritics(company_info.get('company_name','')))
    c.setFont("Helvetica", 8)
    y_pos = height-40*mm
    c.drawString(10*mm, y_pos, remove_diacritics(company_info.get('company_address','')))
    y_pos -= 3.5*mm
    c.drawString(10*mm, y_pos, f"CUI: {company_info.get('cui','')} | Reg.Com: {company_info.get('reg_com','')}")
    y_pos -= 3.5*mm
    c.drawString(10*mm, y_pos, f"Tel: {company_info.get('phone','')} | {company_info.get('email','')}")
    c.setFont("Helvetica-Bold", 9)
    c.drawString(120*mm, height-15*mm, "CLIENT")
    c.setFont("Helvetica", 8)
    y_pos = height-20*mm
    c.drawString(120*mm, y_pos, f"Nume: {remove_diacritics(order['client_name'])}")
    y_pos -= 3.5*mm
    c.drawString(120*mm, y_pos, f"Tel: {order['client_phone']}")
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(105*mm, height-55*mm, "BON PREDARE ECHIPAMENT IN SERVICE")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor('#0066cc'))
    c.drawCentredString(105*mm, height-62*mm, f"Nr. Comanda: {order['order_id']}")
    c.setFillColor(colors.black)
    y_pos = height-72*mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10*mm, y_pos, "DETALII ECHIPAMENT:")
    y_pos -= 5*mm
    c.setFont("Helvetica", 8)
    c.drawString(10*mm, y_pos, f"Imprimanta: {remove_diacritics(order['printer_brand'])} {remove_diacritics(order['printer_model'])}")
    y_pos -= 4*mm
    c.drawString(10*mm, y_pos, f"Serie: {order.get('printer_serial','N/A')}")
    y_pos -= 4*mm
    c.drawString(10*mm, y_pos, f"Data predarii: {order['date_received']}")
    if order.get('accessories'):
        y_pos -= 4*mm
        c.drawString(10*mm, y_pos, f"Accesorii: {remove_diacritics(order['accessories'])}")
    y_pos -= 6*mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10*mm, y_pos, "PROBLEMA RAPORTATA:")
    y_pos -= 4*mm
    c.setFont("Helvetica", 8)
    issue_text = remove_diacritics(order['issue_description'])
    text_object = c.beginText(10*mm, y_pos)
    text_object.setFont("Helvetica", 8)
    words = issue_text.split()
    line = ""
    for word in words:
        test_line = line + word + " "
        if c.stringWidth(test_line, "Helvetica", 8) < 190*mm:
            line = test_line
        else:
            text_object.textLine(line)
            line = word + " "
    text_object.textLine(line)
    c.drawText(text_object)
    y_pos = 25*mm
    c.rect(10*mm, y_pos, 85*mm, 20*mm)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(12*mm, y_pos+17*mm, "OPERATOR SERVICE")
    c.setFont("Helvetica", 7)
    c.drawString(12*mm, y_pos+2*mm, "Semnatura si Stampila")
    c.rect(115*mm, y_pos, 85*mm, 20*mm)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(117*mm, y_pos+17*mm, "CLIENT")
    c.setFont("Helvetica", 7)
    c.drawString(117*mm, y_pos+13*mm, f"Nume: {remove_diacritics(order['client_name'])}")
    c.drawString(117*mm, y_pos+2*mm, "Semnatura")
    c.setFont("Helvetica", 6)
    c.drawCentredString(105*mm, 3*mm, "Acest document constituie dovada predarii echipamentului in service.")
    c.setDash(3, 3)
    c.line(5*mm, 1*mm, 205*mm, 1*mm)
    c.save()
    buffer.seek(0)
    return buffer

def generate_completion_receipt_pdf(order, company_info, logo_image=None):
    buffer = io.BytesIO()
    width, height = 210*mm, 148.5*mm
    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(105*mm, height-30*mm, "BON FINALIZARE REPARATIE")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor('#00aa00'))
    c.drawCentredString(105*mm, height-38*mm, f"Nr. Comanda: {order['order_id']}")
    c.setFillColor(colors.black)
    c.save()
    buffer.seek(0)
    return buffer

class PrinterServiceCRM:
    def __init__(self):
        self.client = get_google_sheets_client()
        if self.client:
            try:
                spreadsheet_id = st.secrets["sheets"]["spreadsheet_id"]
                self.sheet = self.client.open_by_key(spreadsheet_id).sheet1
                self._ensure_headers()
            except Exception as e:
                st.error(f"Failed to open spreadsheet: {str(e)}")
                self.sheet = None
        else:
            self.sheet = None
        self.next_order_id = self._get_next_order_id()

    def _ensure_headers(self):
        try:
            headers = self.sheet.row_values(1)
            if not headers:
                headers = [
                    'order_id', 'client_name', 'client_phone', 'client_email',
                    'printer_brand', 'printer_model', 'printer_serial',
                    'issue_description', 'accessories', 'notes',
                    'date_received', 'date_pickup_scheduled',
                    'date_completed', 'date_picked_up', 'status',
                    'technician', 'repair_details', 'parts_used',
                    'labor_cost', 'parts_cost', 'total_cost'
                ]
                self.sheet.append_row(headers)
        except:
            pass

    def _get_next_order_id(self):
        try:
            if not self.sheet:
                return 1
            all_values = self.sheet.get_all_values()
            if len(all_values) <= 1:
                return 1
            order_ids = [row[0] for row in all_values[1:] if row and row[0]]
            if not order_ids:
                return 1
            last_id = max([int(oid.split('-')[1]) for oid in order_ids if 'SRV-' in oid])
            return last_id + 1
        except:
            return 1

    def create_service_order(self, client_name, client_phone, client_email, printer_brand, printer_model, printer_serial, issue_description, accessories, notes, date_received, date_pickup):
        try:
            if not self.sheet:
                st.error("❌ No connection!")
                return None
            order_id = f"SRV-{self.next_order_id:05d}"
            row = [
                order_id, client_name, client_phone, client_email,
                printer_brand, printer_model, printer_serial,
                issue_description, accessories, notes,
                date_received.strftime("%Y-%m-%d") if date_received else "",
                date_pickup.strftime("%Y-%m-%d") if date_pickup else "",
                "", "", "Received", "", "", "", "0.00", "0.00", "0.00"
            ]
            self.sheet.append_row(row)
            self.next_order_id += 1
            st.sidebar.success("💾 Saved!")
            return order_id
        except Exception as e:
            st.sidebar.error(f"Error: {str(e)}")
            return None

    def get_order(self, order_id):
        try:
            if not self.sheet:
                return None
            all_values = self.sheet.get_all_values()
            headers = all_values[0]
            for row in all_values[1:]:
                if row[0] == order_id:
                    return dict(zip(headers, row))
            return None
        except:
            return None

    def update_order(self, order_id, **kwargs):
        try:
            if not self.sheet:
                return False
            if 'labor_cost' in kwargs or 'parts_cost' in kwargs:
                order = self.get_order(order_id)
                if order:
                    labor = float(kwargs.get('labor_cost', order.get('labor_cost', 0) or 0))
                    parts = float(kwargs.get('parts_cost', order.get('parts_cost', 0) or 0))
                    kwargs['total_cost'] = f"{labor + parts:.2f}"
            all_values = self.sheet.get_all_values()
            headers = all_values[0]
            for row_idx, row in enumerate(all_values[1:], start=2):
                if row[0] == order_id:
                    for key, value in kwargs.items():
                        if key in headers:
                            col_idx = headers.index(key) + 1
                            self.sheet.update_cell(row_idx, col_idx, str(value))
                    st.sidebar.success("💾 Updated!")
                    return True
            return False
        except:
            return False

    def list_orders_df(self):
        try:
            if not self.sheet:
                return pd.DataFrame()
            all_values = self.sheet.get_all_values()
            if len(all_values) <= 1:
                return pd.DataFrame()
            df = pd.DataFrame(all_values[1:], columns=all_values[0])
            for col in ['labor_cost', 'parts_cost', 'total_cost']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except:
            return pd.DataFrame()

def main():
    if not check_password():
        st.stop()

    st.title("🖨️ Printer Service CRM")

    if 'company_info' not in st.session_state:
        st.session_state['company_info'] = {
            'company_name': 'Print Service Pro SRL',
            'company_address': 'Str. Industriei Nr. 45, Cluj-Napoca',
            'cui': 'RO98765432',
            'reg_com': 'J12/5678/2024',
            'phone': '+40 364 123 456',
            'email': 'service@printservicepro.ro'
        }
    if 'last_created_order' not in st.session_state:
        st.session_state['last_created_order'] = None
    if 'logo_image' not in st.session_state:
        st.session_state['logo_image'] = None

    with st.sidebar:
        st.header("⚙️ Settings")
        st.success(f"👤 {st.session_state.get('username', 'User')}")
        if st.button("🚪 Logout"):
            st.session_state['authenticated'] = False
            st.rerun()
        st.divider()
        with st.expander("🖼️ Logo", expanded=False):
            uploaded_logo = st.file_uploader("Upload logo", type=['png', 'jpg', 'jpeg'])
            if uploaded_logo:
                st.session_state['logo_image'] = uploaded_logo
                st.image(uploaded_logo, width=150)
        with st.expander("🏢 Company", expanded=False):
            st.session_state['company_info']['company_name'] = st.text_input("Name", value=st.session_state['company_info']['company_name'])
        with st.expander("📊 Google Sheets", expanded=False):
            test_sheets_connection()

    if 'crm' not in st.session_state:
        st.session_state['crm'] = PrinterServiceCRM()

    crm = st.session_state['crm']

    tab1, tab2, tab3, tab4 = st.tabs(["📥 New Order", "📋 All Orders", "✏️ Update", "📊 Reports"])

    with tab1:
        st.header("Create New Order")
        with st.form("new_order_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                client_name = st.text_input("Client Name *")
                client_phone = st.text_input("Phone *")
                client_email = st.text_input("Email")
            with col2:
                printer_brand = st.text_input("Printer Brand *")
                printer_model = st.text_input("Model *")
                printer_serial = st.text_input("Serial")
            date_received = st.date_input("Date Received", value=date.today())
            date_pickup = st.date_input("Scheduled Pickup", value=None)
            issue_description = st.text_area("Issue Description *")
            accessories = st.text_input("Accessories")
            notes = st.text_area("Notes")
            submit = st.form_submit_button("Create Order")
            if submit:
                if client_name and client_phone and printer_brand and printer_model and issue_description:
                    order_id = crm.create_service_order(client_name, client_phone, client_email, printer_brand, printer_model, printer_serial, issue_description, accessories, notes, date_received, date_pickup)
                    if order_id:
                        st.session_state['last_created_order'] = order_id
                        st.success(f"✅ Created: {order_id}")
                else:
                    st.error("❌ Fill required fields!")

        if st.session_state['last_created_order']:
            order = crm.get_order(st.session_state['last_created_order'])
            if order:
                pdf = generate_initial_receipt_pdf(order, st.session_state['company_info'], st.session_state.get('logo_image'))
                st.download_button("📄 Download Receipt", pdf, f"Initial_{order['order_id']}.pdf", "application/pdf")

    with tab2:
        st.header("All Orders")
        df = crm.list_orders_df()
        if not df.empty:
            st.metric("Total Orders", len(df))
            st.dataframe(df[['order_id', 'client_name', 'printer_brand', 'status', 'total_cost']], use_container_width=True)
        else:
            st.info("No orders yet")

    with tab3:
        st.header("Update Order")
        df = crm.list_orders_df()
        if not df.empty:
            order_id = st.selectbox("Select Order", df['order_id'].tolist())
            if order_id:
                order = crm.get_order(order_id)
                if order:
                    st.write(f"**Client:** {order['client_name']}")
                    new_status = st.selectbox("Status", ['Received', 'In Progress', 'Ready for Pickup', 'Completed'])
                    repair_details = st.text_area("Repairs", value=order.get('repair_details',''))
                    parts_used = st.text_input("Parts", value=order.get('parts_used',''))
                    labor_cost = st.number_input("Labor Cost", value=float(order.get('labor_cost',0)))
                    parts_cost = st.number_input("Parts Cost", value=float(order.get('parts_cost',0)))
                    if st.button("Update"):
                        updates = {'status': new_status, 'repair_details': repair_details, 'parts_used': parts_used, 'labor_cost': labor_cost, 'parts_cost': parts_cost}
                        if crm.update_order(order_id, **updates):
                            st.success("Updated!")
                            st.rerun()

    with tab4:
        st.header("Reports")
        df = crm.list_orders_df()
        if not df.empty:
            st.metric("Total Revenue", f"{df['total_cost'].sum():.2f} RON")
        else:
            st.info("No data yet")

if __name__ == "__main__":
    main()
