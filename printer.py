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
                    st.error("❌ Invalid credentials")
            except:
                st.error("❌ Configure secrets!")
                return False
    return False

def remove_diacritics(text):
    if not isinstance(text, str):
        return text
    m = {'ă':'a','Ă':'A','â':'a','Â':'A','î':'i','Î':'I','ș':'s','Ș':'S','ț':'t','Ț':'T'}
    for d, r in m.items():
        text = text.replace(d, r)
    return text

class GoogleDriveStorage:
    def __init__(self, credentials_dict):
        try:
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            self.service = build('drive', 'v3', credentials=credentials)
            self.folder_id = None
        except Exception as e:
            st.error(f"Drive init failed: {str(e)}")
            self.service = None

    def find_or_create_folder(self, folder_name="PrinterServiceCRM"):
        if not self.service:
            return None
        try:
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id, name)",
                spaces='drive'
            ).execute()
            folders = results.get('files', [])
            if folders:
                self.folder_id = folders[0]['id']
                st.sidebar.success("✅ Connected to Drive!")
                return self.folder_id
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            self.folder_id = folder.get('id')
            st.sidebar.success("✅ Created Drive folder!")
            return self.folder_id
        except Exception as e:
            st.sidebar.error(f"Folder error: {str(e)}")
            return None

    def save_dataframe(self, df, filename="crm_database.csv"):
        if not self.service:
            return False
        if not self.folder_id:
            self.find_or_create_folder()
            if not self.folder_id:
                return False
        try:
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)

            query = f"name='{filename}' and '{self.folder_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id)",
                spaces='drive'
            ).execute()
            files = results.get('files', [])

            media = MediaIoBaseUpload(
                io.BytesIO(csv_buffer.getvalue().encode()),
                mimetype='text/csv'
            )

            if files:
                file_id = files[0]['id']
                self.service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
            else:
                file_metadata = {
                    'name': filename,
                    'parents': [self.folder_id]
                }
                self.service.files().create(
                    body=file_metadata,
                    media_body=media
                ).execute()
            st.sidebar.success("💾 Saved to Drive!")
            return True
        except Exception as e:
            st.sidebar.error(f"Save error: {str(e)}")
            return False

    def load_dataframe(self, filename="crm_database.csv"):
        if not self.service or not self.folder_id:
            return pd.DataFrame()
        try:
            query = f"name='{filename}' and '{self.folder_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id)",
                spaces='drive'
            ).execute()
            files = results.get('files', [])
            if not files:
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
            return df
        except:
            return pd.DataFrame()

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
    c.setFont("Helvetica-Bold", 11)
    c.drawString(10*mm, height-35*mm, remove_diacritics(company_info.get('company_name','')))
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(105*mm, height-55*mm, "BON PREDARE ECHIPAMENT")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor('#0066cc'))
    c.drawCentredString(105*mm, height-62*mm, f"Nr: {order['order_id']}")
    c.setFillColor(colors.black)
    y_pos = height-72*mm
    c.setFont("Helvetica", 8)
    c.drawString(10*mm, y_pos, f"Client: {remove_diacritics(order['client_name'])}")
    y_pos -= 4*mm
    c.drawString(10*mm, y_pos, f"Imprimanta: {remove_diacritics(order['printer_brand'])} {remove_diacritics(order['printer_model'])}")
    y_pos -= 4*mm
    c.drawString(10*mm, y_pos, f"Data: {order['date_received']}")
    c.save()
    buffer.seek(0)
    return buffer

def generate_completion_receipt_pdf(order, company_info, logo_image=None):
    buffer = io.BytesIO()
    width, height = 210*mm, 148.5*mm
    c = canvas.Canvas(buffer, pagesize=(width, height))
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(105*mm, height-30*mm, "BON FINALIZARE")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor('#00aa00'))
    c.drawCentredString(105*mm, height-38*mm, f"Nr: {order['order_id']}")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 8)
    c.drawString(10*mm, height-50*mm, f"Total: {order.get('total_cost',0)} RON")
    c.save()
    buffer.seek(0)
    return buffer

class PrinterServiceCRM:
    def __init__(self, drive_storage=None):
        self.drive_storage = drive_storage
        self.service_orders = []
        self.next_order_id = 1
        self.load_from_storage()

    def load_from_storage(self):
        if self.drive_storage is None:
            return
        if not hasattr(self.drive_storage, 'folder_id'):
            return
        if not self.drive_storage.folder_id:
            return
        try:
            df = self.drive_storage.load_dataframe()
            if not df.empty:
                self.service_orders = df.to_dict('records')
                if self.service_orders:
                    max_id = max([int(o['order_id'].split('-')[1]) for o in self.service_orders])
                    self.next_order_id = max_id + 1
        except:
            pass

    def save_to_storage(self):
        if self.drive_storage and self.service_orders:
            df = pd.DataFrame(self.service_orders)
            return self.drive_storage.save_dataframe(df)
        return False

    def create_service_order(self, client_name, client_phone, client_email, printer_brand, printer_model, printer_serial, issue_description, accessories, notes, date_received, date_pickup):
        order = {
            'order_id': f"SRV-{self.next_order_id:05d}",
            'client_name': client_name,
            'client_phone': client_phone,
            'client_email': client_email,
            'printer_brand': printer_brand,
            'printer_model': printer_model,
            'printer_serial': printer_serial,
            'issue_description': issue_description,
            'accessories': accessories,
            'notes': notes,
            'date_received': date_received.strftime("%Y-%m-%d") if date_received else "",
            'date_pickup_scheduled': date_pickup.strftime("%Y-%m-%d") if date_pickup else "",
            'date_completed': '',
            'date_picked_up': '',
            'status': 'Received',
            'technician': '',
            'repair_details': '',
            'parts_used': '',
            'labor_cost': 0.0,
            'parts_cost': 0.0,
            'total_cost': 0.0
        }
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
                order['total_cost'] = float(order.get('labor_cost', 0)) + float(order.get('parts_cost', 0))
            self.save_to_storage()
            return True
        return False

    def list_orders_df(self):
        if self.service_orders:
            return pd.DataFrame(self.service_orders)
        return pd.DataFrame()

def main():
    if not check_password():
        st.stop()

    st.title("🖨️ Printer Service CRM")

    if 'company_info' not in st.session_state:
        st.session_state['company_info'] = {
            'company_name': 'Print Service Pro SRL',
            'company_address': 'Str. Industriei Nr. 45',
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

        with st.expander("🖼️ Logo"):
            uploaded_logo = st.file_uploader("Upload", type=['png','jpg','jpeg'])
            if uploaded_logo:
                st.session_state['logo_image'] = uploaded_logo
                st.image(uploaded_logo, width=150)

        with st.expander("🏢 Company"):
            st.session_state['company_info']['company_name'] = st.text_input("Name", value=st.session_state['company_info']['company_name'])

        with st.expander("☁️ Google Drive"):
            is_connected = ('drive_storage' in st.session_state and st.session_state.get('drive_storage') and hasattr(st.session_state['drive_storage'], 'folder_id') and st.session_state['drive_storage'].folder_id)
            if is_connected:
                st.success("✅ Connected!")
            else:
                st.warning("⚠️ Not connected")
                if st.button("🔄 Connect"):
                    try:
                        credentials = dict(st.secrets["gcp_service_account"])
                        drive = GoogleDriveStorage(credentials)
                        folder_id = drive.find_or_create_folder()
                        if folder_id:
                            st.session_state['drive_storage'] = drive
                            st.session_state['crm'] = PrinterServiceCRM(drive)
                            st.success("✅ Connected!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

    if 'crm' not in st.session_state:
        try:
            credentials = dict(st.secrets["gcp_service_account"])
            drive = GoogleDriveStorage(credentials)
            drive.find_or_create_folder()
            st.session_state['drive_storage'] = drive
        except:
            st.session_state['drive_storage'] = None
        st.session_state['crm'] = PrinterServiceCRM(st.session_state.get('drive_storage'))

    crm = st.session_state['crm']

    tab1, tab2, tab3, tab4 = st.tabs(["📥 New", "📋 All", "✏️ Update", "📊 Reports"])

    with tab1:
        st.header("Create Order")
        with st.form("new_order", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                client_name = st.text_input("Client *")
                client_phone = st.text_input("Phone *")
                client_email = st.text_input("Email")
            with col2:
                printer_brand = st.text_input("Brand *")
                printer_model = st.text_input("Model *")
                printer_serial = st.text_input("Serial")
            date_received = st.date_input("Date", value=date.today())
            date_pickup = st.date_input("Pickup", value=None)
            issue_description = st.text_area("Issue *")
            accessories = st.text_input("Accessories")
            notes = st.text_area("Notes")
            submit = st.form_submit_button("Create")
            if submit:
                if client_name and client_phone and printer_brand and printer_model and issue_description:
                    order_id = crm.create_service_order(client_name, client_phone, client_email, printer_brand, printer_model, printer_serial, issue_description, accessories, notes, date_received, date_pickup)
                    st.session_state['last_created_order'] = order_id
                    st.success(f"✅ Created: {order_id}")
                else:
                    st.error("❌ Fill required fields")

        if st.session_state['last_created_order']:
            order = crm.get_order(st.session_state['last_created_order'])
            if order:
                pdf = generate_initial_receipt_pdf(order, st.session_state['company_info'], st.session_state.get('logo_image'))
                st.download_button("📄 Download", pdf, f"Initial_{order['order_id']}.pdf", "application/pdf")

    with tab2:
        st.header("All Orders")
        df = crm.list_orders_df()
        if not df.empty:
            st.metric("Total", len(df))
            st.dataframe(df[['order_id','client_name','printer_brand','status','total_cost']], use_container_width=True)
        else:
            st.info("No orders")

    with tab3:
        st.header("Update Order")
        df = crm.list_orders_df()
        if not df.empty:
            order_id = st.selectbox("Select", df['order_id'].tolist())
            if order_id:
                order = crm.get_order(order_id)
                if order:
                    st.write(f"**{order['client_name']}**")
                    new_status = st.selectbox("Status", ['Received','In Progress','Ready','Completed'])
                    repair = st.text_area("Repairs", value=order.get('repair_details',''))
                    parts = st.text_input("Parts", value=order.get('parts_used',''))
                    labor = st.number_input("Labor", value=float(order.get('labor_cost',0)))
                    parts_cost = st.number_input("Parts Cost", value=float(order.get('parts_cost',0)))
                    if st.button("Update"):
                        updates = {'status':new_status, 'repair_details':repair, 'parts_used':parts, 'labor_cost':labor, 'parts_cost':parts_cost}
                        if crm.update_order(order_id, **updates):
                            st.success("Updated!")
                            st.rerun()

    with tab4:
        st.header("Reports")
        df = crm.list_orders_df()
        if not df.empty:
            st.metric("Revenue", f"{df['total_cost'].sum():.2f} RON")
        else:
            st.info("No data")

if __name__ == "__main__":
    main()
