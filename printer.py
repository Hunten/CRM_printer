import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import hashlib
from streamlit_gsheets import GSheetsConnection
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image

st.set_page_config(page_title="Printer Service CRM", page_icon="🖨️", layout="wide")

# Authentication
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
                st.error("❌ Configure passwords in secrets!")
                return False
    return False

def remove_diacritics(text):
    if not isinstance(text, str):
        return text
    m = {'ă':'a','Ă':'A','â':'a','Â':'A','î':'i','Î':'I','ș':'s','Ș':'S','ț':'t','Ț':'T'}
    for d, r in m.items():
        text = text.replace(d, r)
    return text

# Google Sheets Connection
@st.cache_resource
def get_sheets_connection():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        return conn
    except Exception as e:
        st.error(f"Sheets connection failed: {str(e)}")
        return None

# PDF Generation - Initial Receipt
def generate_initial_receipt_pdf(order, company_info, logo_image=None):
    buffer = io.BytesIO()
    width, height = 210*mm, 148.5*mm
    c = canvas.Canvas(buffer, pagesize=(width, height))

    # Logo
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

    # Company info
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(10*mm, height-35*mm, remove_diacritics(company_info.get('company_name','')))
    c.setFont("Helvetica", 8)
    c.drawString(10*mm, height-40*mm, remove_diacritics(company_info.get('company_address','')))

    # Title
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(105*mm, height-55*mm, "BON PREDARE ECHIPAMENT")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor('#0066cc'))
    c.drawCentredString(105*mm, height-62*mm, f"Nr: {order['order_id']}")

    # Order details
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 8)
    y_pos = height-72*mm
    c.drawString(10*mm, y_pos, f"Client: {remove_diacritics(order['client_name'])}")
    y_pos -= 4*mm
    c.drawString(10*mm, y_pos, f"Tel: {order['client_phone']}")
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

# CRM Class
class PrinterServiceCRM:
    def __init__(self, connection):
        self.conn = connection
        self.worksheet = "Orders"  # Sheet name
        self.next_order_id = 1
        self.load_from_sheets()

    def load_from_sheets(self):
        try:
            df = self.conn.read(worksheet=self.worksheet, ttl=0)
            if not df.empty and 'order_id' in df.columns:
                max_id = max([int(oid.split('-')[1]) for oid in df['order_id'].values if 'SRV-' in str(oid)])
                self.next_order_id = max_id + 1
        except:
            # Sheet doesn't exist or is empty
            pass

    def save_to_sheets(self, df):
        try:
            self.conn.update(worksheet=self.worksheet, data=df)
            st.sidebar.success("💾 Saved!")
            return True
        except Exception as e:
            st.sidebar.error(f"Save failed: {str(e)}")
            return False

    def create_service_order(self, client_name, client_phone, client_email, printer_brand, printer_model, printer_serial, issue_description, accessories, notes, date_received, date_pickup):
        order_id = f"SRV-{self.next_order_id:05d}"

        new_order = pd.DataFrame([{
            'order_id': order_id,
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
        }])

        try:
            existing_df = self.conn.read(worksheet=self.worksheet, ttl=0)
        except:
            existing_df = pd.DataFrame()

        if existing_df.empty:
            updated_df = new_order
        else:
            updated_df = pd.concat([existing_df, new_order], ignore_index=True)

        if self.save_to_sheets(updated_df):
            self.next_order_id += 1
            return order_id
        return None

    def get_order(self, order_id):
        try:
            df = self.conn.read(worksheet=self.worksheet, ttl=0)
            if not df.empty:
                order = df[df['order_id'] == order_id]
                if not order.empty:
                    return order.iloc[0].to_dict()
        except:
            pass
        return None

    def update_order(self, order_id, **kwargs):
        try:
            df = self.conn.read(worksheet=self.worksheet, ttl=0)
            if df.empty:
                return False

            idx = df[df['order_id'] == order_id].index
            if len(idx) == 0:
                return False

            for key, value in kwargs.items():
                df.loc[idx, key] = value

            if 'labor_cost' in kwargs or 'parts_cost' in kwargs:
                df.loc[idx, 'total_cost'] = float(df.loc[idx, 'labor_cost'].values[0]) + float(df.loc[idx, 'parts_cost'].values[0])

            return self.save_to_sheets(df)
        except Exception as e:
            st.error(f"Update failed: {str(e)}")
            return False

    def list_orders_df(self):
        try:
            df = self.conn.read(worksheet=self.worksheet, ttl=0)
            return df if not df.empty else pd.DataFrame()
        except:
            return pd.DataFrame()

# Main App
def main():
    if not check_password():
        st.stop()

    st.title("🖨️ Printer Service CRM")

    # Initialize session state
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

    # Sidebar
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

        # Connection status
        conn = get_sheets_connection()
        if conn:
            st.success("✅ Connected to Sheets!")
        else:
            st.error("❌ Not connected")

    # Initialize CRM
    conn = get_sheets_connection()
    if not conn:
        st.error("Cannot connect to Google Sheets!")
        st.stop()

    if 'crm' not in st.session_state:
        st.session_state['crm'] = PrinterServiceCRM(conn)

    crm = st.session_state['crm']

    # Tabs
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
                    if order_id:
                        st.session_state['last_created_order'] = order_id
                        st.success(f"✅ Created: {order_id}")
                else:
                    st.error("❌ Fill required fields")

        if st.session_state['last_created_order']:
            order = crm.get_order(st.session_state['last_created_order'])
            if order:
                pdf = generate_initial_receipt_pdf(order, st.session_state['company_info'], st.session_state.get('logo_image'))
                st.download_button("📄 Download Receipt", pdf, f"Initial_{order['order_id']}.pdf", "application/pdf")

    with tab2:
        st.header("All Orders")
        df = crm.list_orders_df()
        if not df.empty:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total", len(df))
            col2.metric("Received", len(df[df['status']=='Received']))
            col3.metric("Completed", len(df[df['status']=='Completed']))
            st.dataframe(df[['order_id','client_name','printer_brand','status','total_cost']], use_container_width=True)

            # Backup download button
            csv = df.to_csv(index=False)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label="💾 Download Backup (CSV)",
                data=csv,
                file_name=f"crm_backup_{timestamp}.csv",
                mime="text/csv",
                use_container_width=True
            )
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
                    new_status = st.selectbox("Status", ['Received','In Progress','Ready','Completed'], index=['Received','In Progress','Ready','Completed'].index(order['status']))
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
