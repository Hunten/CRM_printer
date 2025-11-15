import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import hashlib
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image

st.set_page_config(page_title="Printer Service CRM", page_icon="🖨️", layout="wide")

# ============================================================================
# AUTHENTICATION
# ============================================================================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_password():
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    if st.session_state['authenticated']:
        return True
    st.markdown("## 🔒 Login Required")
    st.markdown("Please enter your credentials to access the CRM system.")
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
                st.info("Add 'passwords.admin_password' in Streamlit Cloud Settings → Secrets")
                return False
    return False

# ============================================================================
# UTILITIES
# ============================================================================

def remove_diacritics(text):
    if not isinstance(text, str):
        return text
    diacritics_map = {'ă':'a','Ă':'A','â':'a','Â':'A','î':'i','Î':'I','ș':'s','Ș':'S','ț':'t','Ț':'T'}
    for d, r in diacritics_map.items():
        text = text.replace(d, r)
    return text

# ============================================================================
# GOOGLE DRIVE - FIXED FOR STORAGE QUOTA
# ============================================================================

class GoogleDriveStorage:
    def __init__(self, credentials_dict):
        try:
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict, scopes=['https://www.googleapis.com/auth/drive.file'])
            self.service = build('drive', 'v3', credentials=credentials)
            self.folder_id = None
        except Exception as e:
            st.error(f"Failed to initialize Google Drive: {str(e)}")
            self.service = None

    def find_or_create_folder(self, folder_name="PrinterServiceCRM"):
        if not self.service:
            return None
        try:
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(q=query, fields="files(id, name)", spaces='drive').execute()
            folders = results.get('files', [])
            if folders:
                self.folder_id = folders[0]['id']
                st.sidebar.success(f"📁 Connected to Drive!")
                return self.folder_id
            st.sidebar.error(f"❌ Folder '{folder_name}' not found!")
            st.sidebar.info("Create folder 'PrinterServiceCRM' in your Drive and share it with service account")
            return None
        except Exception as e:
            st.sidebar.error(f"Folder error: {str(e)}")
            return None

    def save_dataframe(self, df, filename="crm_database.csv"):
        if not self.service:
            return False
        # CRITICAL FIX: Ensure folder_id exists before saving
        if not self.folder_id:
            st.sidebar.warning("Finding folder...")
            self.find_or_create_folder()
            if not self.folder_id:
                st.sidebar.error("❌ Cannot save - folder not accessible!")
                return False
        try:
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            query = f"name='{filename}' and '{self.folder_id}' in parents and trashed=false"
            results = self.service.files().list(q=query, fields="files(id)", spaces='drive').execute()
            files = results.get('files', [])
            media = MediaIoBaseUpload(io.BytesIO(csv_buffer.getvalue().encode()), mimetype='text/csv')
            if files:
                self.service.files().update(fileId=files[0]['id'], media_body=media).execute()
                st.sidebar.success("💾 Saved!")
            else:
                file_metadata = {'name': filename, 'parents': [self.folder_id]}
                self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                st.sidebar.success("💾 Created!")
            return True
        except Exception as e:
            st.sidebar.error(f"Save error: {str(e)}")
            return False

    def load_dataframe(self, filename="crm_database.csv"):
        if not self.service or not self.folder_id:
            return pd.DataFrame()
        try:
            query = f"name='{filename}' and '{self.folder_id}' in parents and trashed=false"
            results = self.service.files().list(q=query, fields="files(id)", spaces='drive').execute()
            files = results.get('files', [])
            if not files:
                st.sidebar.info("📄 No database. Starting fresh.")
                return pd.DataFrame()
            file_id = files[0]['id']
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)
            df = pd.read_csv(fh)
            st.sidebar.success(f"📄 Loaded {len(df)} orders!")
            return df
        except Exception as e:
            st.sidebar.error(f"Load error: {str(e)}")
            return pd.DataFrame()

# ============================================================================
# PDF GENERATION - INITIAL RECEIPT
# ============================================================================

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


# ============================================================================
# PDF GENERATION - COMPLETION RECEIPT (3-COLUMN LAYOUT)
# ============================================================================

def generate_completion_receipt_pdf(order, company_info, logo_image=None):
    buffer = io.BytesIO()
    width, height = 210*mm, 148.5*mm
    c = canvas.Canvas(buffer, pagesize=(width, height))
    header_y_start = height-10*mm
    x_business = 10*mm
    y_pos = header_y_start
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x_business, y_pos, remove_diacritics(company_info.get('company_name','')))
    y_pos -= 3.5*mm
    c.setFont("Helvetica", 7)
    c.drawString(x_business, y_pos, remove_diacritics(company_info.get('company_address','')))
    y_pos -= 3*mm
    c.drawString(x_business, y_pos, f"CUI: {company_info.get('cui','')}")
    y_pos -= 3*mm
    c.drawString(x_business, y_pos, f"Reg.Com: {company_info.get('reg_com','')}")
    y_pos -= 3*mm
    c.drawString(x_business, y_pos, f"Tel: {company_info.get('phone','')}")
    y_pos -= 3*mm
    c.drawString(x_business, y_pos, company_info.get('email',''))
    logo_x = 85*mm
    logo_y = header_y_start-20*mm
    logo_width = 40*mm
    logo_height = 25*mm
    if logo_image:
        try:
            logo = Image.open(logo_image)
            logo.thumbnail((150,95), Image.Resampling.LANCZOS)
            logo_buffer = io.BytesIO()
            logo.save(logo_buffer, format='PNG')
            logo_buffer.seek(0)
            c.drawImage(ImageReader(logo_buffer), logo_x, logo_y, width=logo_width, height=logo_height, preserveAspectRatio=True, mask='auto')
        except:
            c.setFillColor(colors.HexColor('#f0f0f0'))
            c.rect(logo_x, logo_y, logo_width, logo_height, fill=1, stroke=1)
            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(logo_x+(logo_width/2), logo_y+(logo_height/2), "[LOGO]")
    else:
        c.setFillColor(colors.HexColor('#f0f0f0'))
        c.rect(logo_x, logo_y, logo_width, logo_height, fill=1, stroke=1)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(logo_x+(logo_width/2), logo_y+(logo_height/2), "[LOGO]")
    c.setFillColor(colors.black)
    x_client = 155*mm
    y_pos = header_y_start
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x_client, y_pos, "CLIENT")
    y_pos -= 3.5*mm
    c.setFont("Helvetica", 7)
    c.drawString(x_client, y_pos, f"Nume:")
    y_pos -= 3*mm
    client_name = remove_diacritics(order['client_name'])
    if len(client_name) > 20:
        c.drawString(x_client, y_pos, client_name[:20])
        y_pos -= 3*mm
        c.drawString(x_client, y_pos, client_name[20:40])
    else:
        c.drawString(x_client, y_pos, client_name)
    y_pos -= 3*mm
    c.drawString(x_client, y_pos, f"Tel:")
    y_pos -= 3*mm
    c.drawString(x_client, y_pos, order['client_phone'])
    title_y = height-38*mm
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(105*mm, title_y, "BON FINALIZARE REPARATIE")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor('#00aa00'))
    c.drawCentredString(105*mm, title_y-6*mm, f"Nr. Comanda: {order['order_id']}")
    c.setFillColor(colors.black)
    y_start = height-50*mm
    col_width = 63*mm
    x_left = 10*mm
    y_pos = y_start
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x_left, y_pos, "DETALII ECHIPAMENT:")
    y_pos -= 3.5*mm
    c.setFont("Helvetica", 7)
    printer_info = f"{remove_diacritics(order['printer_brand'])} {remove_diacritics(order['printer_model'])}"
    if len(printer_info) > 25:
        printer_info = printer_info[:25] + "..."
    c.drawString(x_left, y_pos, printer_info)
    y_pos -= 2.5*mm
    serial = order.get('printer_serial','N/A')
    if len(serial) > 20:
        serial = serial[:20] + "..."
    c.drawString(x_left, y_pos, f"Serie: {serial}")
    y_pos -= 2.5*mm
    c.drawString(x_left, y_pos, f"Predare: {order['date_received']}")
    if order.get('date_completed'):
        y_pos -= 2.5*mm
        c.drawString(x_left, y_pos, f"Finalizare: {order['date_completed']}")
    x_middle = 73*mm
    y_pos = y_start
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x_middle, y_pos, "REPARATII EFECTUATE:")
    y_pos -= 3.5*mm
    c.setFont("Helvetica", 7)
    repair_text = remove_diacritics(order.get('repair_details','N/A'))
    words = repair_text.split()
    line = ""
    line_count = 0
    max_lines = 5
    for word in words:
        test_line = line + word + " "
        if c.stringWidth(test_line, "Helvetica", 7) < (col_width-2*mm):
            line = test_line
        else:
            if line_count < max_lines:
                c.drawString(x_middle, y_pos, line.strip())
                y_pos -= 2.5*mm
                line_count += 1
                line = word + " "
            else:
                break
    if line and line_count < max_lines:
        c.drawString(x_middle, y_pos, line.strip())
    x_right = 136*mm
    y_pos = y_start
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x_right, y_pos, "PIESE UTILIZATE:")
    y_pos -= 3.5*mm
    c.setFont("Helvetica", 7)
    parts_text = remove_diacritics(order.get('parts_used','N/A'))
    words = parts_text.split()
    line = ""
    line_count = 0
    for word in words:
        test_line = line + word + " "
        if c.stringWidth(test_line, "Helvetica", 7) < (col_width-2*mm):
            line = test_line
        else:
            if line_count < max_lines:
                c.drawString(x_right, y_pos, line.strip())
                y_pos -= 2.5*mm
                line_count += 1
                line = word + " "
            else:
                break
    if line and line_count < max_lines:
        c.drawString(x_right, y_pos, line.strip())
    y_cost = height-78*mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10*mm, y_cost, "COSTURI:")
    y_cost -= 4*mm
    table_x = 10*mm
    table_width = 70*mm
    row_height = 5*mm
    c.rect(table_x, y_cost-(4*row_height), table_width, 4*row_height)
    c.setFillColor(colors.HexColor('#e0e0e0'))
    c.rect(table_x, y_cost-row_height, table_width, row_height, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(table_x+2*mm, y_cost-row_height+1.5*mm, "Descriere")
    c.drawString(table_x+table_width-22*mm, y_cost-row_height+1.5*mm, "Suma (RON)")
    c.line(table_x, y_cost-row_height, table_x+table_width, y_cost-row_height)
    y_cost -= row_height
    c.setFont("Helvetica", 8)
    c.drawString(table_x+2*mm, y_cost-row_height+1.5*mm, "Manopera (Labor)")
    labor = float(order.get('labor_cost',0))
    c.drawString(table_x+table_width-22*mm, y_cost-row_height+1.5*mm, f"{labor:.2f}")
    c.line(table_x, y_cost-row_height, table_x+table_width, y_cost-row_height)
    y_cost -= row_height
    c.drawString(table_x+2*mm, y_cost-row_height+1.5*mm, "Piese (Parts)")
    parts = float(order.get('parts_cost',0))
    c.drawString(table_x+table_width-22*mm, y_cost-row_height+1.5*mm, f"{parts:.2f}")
    c.line(table_x, y_cost-row_height, table_x+table_width, y_cost-row_height)
    y_cost -= row_height
    c.setFillColor(colors.HexColor('#f0f0f0'))
    c.rect(table_x, y_cost-row_height, table_width, row_height, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(table_x+2*mm, y_cost-row_height+1.5*mm, "TOTAL")
    total = float(order.get('total_cost', labor+parts))
    c.drawString(table_x+table_width-22*mm, y_cost-row_height+1.5*mm, f"{total:.2f}")
    sig_y = 22*mm
    sig_height = 18*mm
    c.rect(10*mm, sig_y, 85*mm, sig_height)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(12*mm, sig_y+sig_height-3*mm, "OPERATOR SERVICE")
    c.setFont("Helvetica", 7)
    c.drawString(12*mm, sig_y+2*mm, "Semnatura si Stampila")
    c.rect(115*mm, sig_y, 85*mm, sig_height)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(117*mm, sig_y+sig_height-3*mm, "CLIENT")
    c.setFont("Helvetica", 7)
    c.drawString(117*mm, sig_y+sig_height-7*mm, f"Nume: {remove_diacritics(order['client_name'])}")
    c.drawString(117*mm, sig_y+2*mm, "Semnatura")
    c.setFont("Helvetica", 6)
    c.drawCentredString(105*mm, 3*mm, "Acest document constituie factura si dovada finalizarii reparatiei.")
    c.setDash(3, 3)
    c.line(5*mm, 1*mm, 205*mm, 1*mm)
    c.save()
    buffer.seek(0)
    return buffer

# ============================================================================
# CRM CLASS
# ============================================================================

class PrinterServiceCRM:
    def __init__(self, drive_storage=None):
        self.drive_storage = drive_storage
        self.service_orders = []
        self.next_order_id = 1
        self.load_from_storage()

    def load_from_storage(self):
        if self.drive_storage:
            df = self.drive_storage.load_dataframe()
            if not df.empty:
                self.service_orders = df.to_dict('records')
                if self.service_orders:
                    max_id = max([int(o['order_id'].split('-')[1]) for o in self.service_orders])
                    self.next_order_id = max_id + 1

    def save_to_storage(self):
        if self.drive_storage and self.service_orders:
            df = pd.DataFrame(self.service_orders)
            return self.drive_storage.save_dataframe(df)
        return False

    def create_service_order(self, client_name, client_phone, client_email, printer_brand, printer_model, printer_serial, issue_description, accessories, notes, date_received, date_pickup):
        order = {'order_id':f"SRV-{self.next_order_id:05d}",'client_name':client_name,'client_phone':client_phone,'client_email':client_email,'printer_brand':printer_brand,'printer_model':printer_model,'printer_serial':printer_serial,'issue_description':issue_description,'accessories':accessories,'notes':notes,'date_received':date_received.strftime("%Y-%m-%d") if date_received else datetime.now().strftime("%Y-%m-%d"),'date_pickup_scheduled':date_pickup.strftime("%Y-%m-%d") if date_pickup else '','date_completed':'','date_picked_up':'','status':'Received','technician':'','repair_details':'','parts_used':'','labor_cost':0.0,'parts_cost':0.0,'total_cost':0.0}
        self.service_orders.append(order)
        self.next_order_id += 1
        self.save_to_storage()
        return order['order_id']

    def get_order(self, order_id):
        for order in self.service_orders:
            if order['order_id'] == order_id:
                return order
        return None

    def update_order(self, order_id, **kwargs):
        order = self.get_order(order_id)
        if order:
            order.update(kwargs)
            if 'labor_cost' in kwargs or 'parts_cost' in kwargs:
                order['total_cost'] = float(order.get('labor_cost',0)) + float(order.get('parts_cost',0))
            self.save_to_storage()
            return True
        return False

    def list_orders_df(self):
        if self.service_orders:
            return pd.DataFrame(self.service_orders)
        return pd.DataFrame()


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    # MUST check password FIRST
    if not check_password():
        st.stop()

    # Title
    st.title("🖨️ Printer Service CRM")
    st.markdown("### Professional Printer Service Management System")

    # Initialize session state
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

    # ========== SIDEBAR ==========
    with st.sidebar:
        st.header("⚙️ Configuration")
        st.success(f"👤 {st.session_state.get('username', 'User')}")

        if st.button("🚪 Logout", key="logout_btn"):
            st.session_state['authenticated'] = False
            st.rerun()

        st.divider()

        # Logo Upload
        with st.expander("🖼️ Company Logo", expanded=False):
            uploaded_logo = st.file_uploader("Upload logo (PNG/JPG)", type=['png', 'jpg', 'jpeg'], key="logo_uploader")
            if uploaded_logo:
                st.session_state['logo_image'] = uploaded_logo
                st.success("✅ Logo uploaded!")
                st.image(uploaded_logo, width=150)
            elif st.session_state['logo_image']:
                st.image(st.session_state['logo_image'], width=150)

        # Company Details
        with st.expander("🏢 Company Details", expanded=False):
            st.session_state['company_info']['company_name'] = st.text_input(
                "Company Name", 
                value=st.session_state['company_info']['company_name'],
                key="company_name_input"
            )
            st.session_state['company_info']['company_address'] = st.text_input(
                "Address", 
                value=st.session_state['company_info']['company_address'],
                key="company_address_input"
            )
            st.session_state['company_info']['cui'] = st.text_input(
                "CUI", 
                value=st.session_state['company_info']['cui'],
                key="company_cui_input"
            )
            st.session_state['company_info']['reg_com'] = st.text_input(
                "Reg.Com", 
                value=st.session_state['company_info']['reg_com'],
                key="company_regcom_input"
            )
            st.session_state['company_info']['phone'] = st.text_input(
                "Phone", 
                value=st.session_state['company_info']['phone'],
                key="company_phone_input"
            )
            st.session_state['company_info']['email'] = st.text_input(
                "Email", 
                value=st.session_state['company_info']['email'],
                key="company_email_input"
            )

        # Google Drive Connection
        with st.expander("☁️ Google Drive", expanded=False):
            # Check if connected
            is_connected = ('drive_storage' in st.session_state and 
                          st.session_state.get('drive_storage') is not None and
                          hasattr(st.session_state['drive_storage'], 'folder_id') and
                          st.session_state['drive_storage'].folder_id is not None)

            if is_connected:
                st.success("✅ Connected to Google Drive!")
                st.info(f"Folder ID: {st.session_state['drive_storage'].folder_id[:20]}...")
            else:
                st.warning("⚠️ Not connected")
                st.info("Click below to connect to Google Drive")

                if st.button("🔄 Connect to Drive", key="connect_drive_btn"):
                    try:
                        credentials = dict(st.secrets["gcp_service_account"])
                        drive = GoogleDriveStorage(credentials)

                        if not drive.service:
                            st.error("❌ Failed to initialize service!")
                            st.stop()

                        folder_id = drive.find_or_create_folder()

                        if not folder_id:
                            st.error("❌ Folder 'PrinterServiceCRM' not found!")
                            st.info("1. Create folder in your Google Drive\n2. Share with service account\n3. Try again")
                            st.stop()

                        # Store in session state
                        st.session_state['drive_storage'] = drive
                        st.session_state['crm'] = PrinterServiceCRM(drive)
                        st.success("✅ Connected successfully!")
                        st.rerun()

                    except KeyError as e:
                        st.error(f"❌ Missing in secrets: {e}")
                        st.info("Add 'gcp_service_account' in Streamlit Cloud Settings → Secrets")
                    except Exception as e:
                        st.error(f"❌ Connection error: {str(e)}")

    # ========== INITIALIZE CRM (PRESERVE EXISTING CONNECTION) ==========
    if 'crm' not in st.session_state:
        # Check if we already have connected drive_storage (from button)
        if 'drive_storage' in st.session_state and st.session_state.get('drive_storage'):
            # Already exists, check if it has folder_id
            if st.session_state['drive_storage'].folder_id:
                # Good! Has folder_id, reuse it
                pass
            else:
                # No folder_id yet, try to find it silently
                try:
                    st.session_state['drive_storage'].find_or_create_folder()
                except:
                    pass  # Silent fail, user can click button
        else:
            # No drive_storage yet, try to create and connect automatically
            try:
                credentials = dict(st.secrets["gcp_service_account"])
                drive = GoogleDriveStorage(credentials)
                drive.find_or_create_folder()  # Try to connect automatically
                st.session_state['drive_storage'] = drive
            except:
                # Auto-connect failed, that's ok - user can click button
                st.session_state['drive_storage'] = None

        # Create CRM with whatever drive_storage we have
        st.session_state['crm'] = PrinterServiceCRM(st.session_state.get('drive_storage', None))

    crm = st.session_state['crm']

    # ========== TABS ==========
    tab1, tab2, tab3, tab4 = st.tabs(["📥 New Order", "📋 All Orders", "✏️ Update Order", "📊 Reports"])

    with tab1:
        st.header("Create New Service Order")
        with st.form(key='new_order_form', clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Client Information")
                client_name = st.text_input("Name *")
                client_phone = st.text_input("Phone *")
                client_email = st.text_input("Email")
            with col2:
                st.subheader("Printer Information")
                printer_brand = st.text_input("Brand *")
                printer_model = st.text_input("Model *")
                printer_serial = st.text_input("Serial Number")

            col3, col4 = st.columns(2)
            with col3:
                date_received = st.date_input("Date Received *", value=date.today())
            with col4:
                date_pickup = st.date_input("Scheduled Pickup (optional)", value=None)

            issue_description = st.text_area("Issue Description *", height=100)
            accessories = st.text_input("Accessories (cables, cartridges, etc.)")
            notes = st.text_area("Additional Notes", height=60)

            submit = st.form_submit_button("🎫 Create Order", type="primary", use_container_width=True)

            if submit:
                if client_name and client_phone and printer_brand and printer_model and issue_description:
                    order_id = crm.create_service_order(
                        client_name, client_phone, client_email,
                        printer_brand, printer_model, printer_serial,
                        issue_description, accessories, notes,
                        date_received, date_pickup
                    )
                    st.session_state['last_created_order'] = order_id
                    st.success(f"✅ Order Created: **{order_id}**")
                    st.balloons()
                else:
                    st.error("❌ Please fill in all required fields (*)")

        # Show PDF download for last created order
        if st.session_state['last_created_order']:
            order = crm.get_order(st.session_state['last_created_order'])
            if order:
                st.divider()
                st.subheader("📄 Download Receipt")
                logo = st.session_state.get('logo_image', None)
                pdf_buffer = generate_initial_receipt_pdf(order, st.session_state['company_info'], logo)
                st.download_button(
                    "📄 Download Initial Receipt",
                    pdf_buffer,
                    f"Initial_{order['order_id']}.pdf",
                    "application/pdf",
                    type="secondary",
                    use_container_width=True,
                    key="dl_new_init"
                )
                if st.button("✅ Done", use_container_width=True, key="done_new_order"):
                    st.session_state['last_created_order'] = None
                    st.rerun()

    with tab2:
        st.header("All Service Orders")
        df = crm.list_orders_df()
        if not df.empty:
            # Metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📊 Total Orders", len(df))
            col2.metric("📥 Received", len(df[df['status'] == 'Received']))
            col3.metric("✅ Ready", len(df[df['status'] == 'Ready for Pickup']))
            col4.metric("🎉 Completed", len(df[df['status'] == 'Completed']))

            # Orders table
            st.dataframe(
                df[['order_id', 'client_name', 'printer_brand', 'date_received', 'status', 'total_cost']],
                use_container_width=True
            )

            # CSV Export
            st.download_button(
                "📥 Export to CSV",
                df.to_csv(index=False),
                f"orders_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv",
                key="dl_csv"
            )
        else:
            st.info("📝 No orders yet. Create your first order in the 'New Order' tab!")

    with tab3:
        st.header("Update Service Order")
        df = crm.list_orders_df()
        if not df.empty:
            selected_order_id = st.selectbox("Select Order to Update", df['order_id'].tolist())

            if selected_order_id:
                order = crm.get_order(selected_order_id)
                if order:
                    # Order info
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Client:** {order['client_name']}")
                        st.write(f"**Phone:** {order['client_phone']}")
                    with col2:
                        st.write(f"**Printer:** {order['printer_brand']} {order['printer_model']}")
                        st.write(f"**Received:** {order['date_received']}")

                    st.divider()

                    # Update form
                    new_status = st.selectbox(
                        "Status",
                        ['Received', 'In Progress', 'Ready for Pickup', 'Completed'],
                        index=['Received', 'In Progress', 'Ready for Pickup', 'Completed'].index(order['status'])
                    )

                    if new_status == 'Completed':
                        actual_pickup_date = st.date_input("Actual Pickup Date", value=date.today())

                    st.subheader("Repair Details")
                    repair_details = st.text_area("Repairs Performed", value=order.get('repair_details', ''), height=100)
                    parts_used = st.text_input("Parts Used", value=order.get('parts_used', ''))
                    technician = st.text_input("Technician", value=order.get('technician', ''))

                    # Costs
                    col1, col2, col3 = st.columns(3)
                    labor_cost = col1.number_input("Labor Cost (RON)", value=float(order.get('labor_cost', 0)), min_value=0.0, step=10.0)
                    parts_cost = col2.number_input("Parts Cost (RON)", value=float(order.get('parts_cost', 0)), min_value=0.0, step=10.0)
                    col3.metric("💰 Total Cost", f"{labor_cost + parts_cost:.2f} RON")

                    # Update button
                    if st.button("💾 Update Order", type="primary", key="update_order_btn"):
                        updates = {
                            'status': new_status,
                            'repair_details': repair_details,
                            'parts_used': parts_used,
                            'technician': technician,
                            'labor_cost': labor_cost,
                            'parts_cost': parts_cost
                        }
                        if new_status == 'Ready for Pickup' and not order.get('date_completed'):
                            updates['date_completed'] = datetime.now().strftime("%Y-%m-%d")
                        if new_status == 'Completed':
                            updates['date_picked_up'] = actual_pickup_date.strftime("%Y-%m-%d")

                        if crm.update_order(selected_order_id, **updates):
                            st.success("✅ Order updated successfully!")
                            st.rerun()

                    st.divider()

                    # PDF Downloads
                    st.subheader("📄 Download Receipts")
                    st.info("💡 Both PDFs available for download")

                    logo = st.session_state.get('logo_image', None)
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**Initial Receipt**")
                        st.caption("Drop-off receipt for client")
                        pdf_init = generate_initial_receipt_pdf(order, st.session_state['company_info'], logo)
                        st.download_button(
                            "📄 Download Initial Receipt",
                            pdf_init,
                            f"Initial_{order['order_id']}.pdf",
                            "application/pdf",
                            use_container_width=True,
                            key=f"dl_upd_init_{order['order_id']}"
                        )

                    with col2:
                        st.markdown("**Completion Receipt**")
                        st.caption("Pickup/invoice receipt")
                        if order.get('status') not in ['Ready for Pickup', 'Completed'] or float(order.get('total_cost', 0)) == 0:
                            st.warning("⚠️ Complete repair details and costs first")
                        pdf_comp = generate_completion_receipt_pdf(order, st.session_state['company_info'], logo)
                        st.download_button(
                            "📄 Download Completion Receipt",
                            pdf_comp,
                            f"Completion_{order['order_id']}.pdf",
                            "application/pdf",
                            use_container_width=True,
                            key=f"dl_upd_comp_{order['order_id']}"
                        )
        else:
            st.info("📝 No orders yet. Create your first order in the 'New Order' tab!")

    with tab4:
        st.header("Reports & Analytics")
        df = crm.list_orders_df()
        if not df.empty:
            # Metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("💰 Total Revenue", f"{df['total_cost'].sum():.2f} RON")
            avg_cost = df[df['total_cost'] > 0]['total_cost'].mean() if len(df[df['total_cost'] > 0]) > 0 else 0
            col2.metric("📊 Average Cost", f"{avg_cost:.2f} RON")
            col3.metric("👥 Unique Clients", df['client_name'].nunique())

            st.divider()

            # Charts
            st.subheader("Orders by Status")
            st.bar_chart(df['status'].value_counts())

        else:
            st.info("📝 No data yet. Create orders to see reports!")

if __name__ == "__main__":
    main()
