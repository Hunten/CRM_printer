import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import hashlib
import psycopg2
from psycopg2.extras import RealDictCursor
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
# POSTGRESQL DATABASE CONNECTION
# ============================================================================

@st.cache_resource
def get_database_connection():
    """Get PostgreSQL connection from Streamlit secrets"""
    try:
        conn_string = st.secrets["database"]["connection_string"]
        conn = psycopg2.connect(conn_string)
        return conn
    except Exception as e:
        st.error(f"Database connection failed: {str(e)}")
        return None

def test_database_connection():
    """Test if database connection works"""
    try:
        conn = get_database_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            st.sidebar.success("✅ Database connected!")
            return True
        return False
    except Exception as e:
        st.sidebar.error(f"❌ Database error: {str(e)}")
        return False


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
# PDF GENERATION - COMPLETION RECEIPT (3-COLUMN)
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
# CRM CLASS - POSTGRESQL VERSION
# ============================================================================

class PrinterServiceCRM:
    def __init__(self):
        self.conn = get_database_connection()
        self.next_order_id = self._get_next_order_id()

    def _get_next_order_id(self):
        """Get the next order ID from database"""
        try:
            if not self.conn:
                return 1
            with self.conn.cursor() as cur:
                cur.execute("SELECT order_id FROM service_orders ORDER BY order_id DESC LIMIT 1")
                result = cur.fetchone()
                if result:
                    last_id = int(result[0].split('-')[1])
                    return last_id + 1
                return 1
        except:
            return 1

    def create_service_order(self, client_name, client_phone, client_email, printer_brand, printer_model, printer_serial, issue_description, accessories, notes, date_received, date_pickup):
        """Create new service order in database"""
        try:
            if not self.conn:
                st.error("❌ No database connection!")
                return None

            order_id = f"SRV-{self.next_order_id:05d}"

            with self.conn.cursor() as cur:
                sql = """
                INSERT INTO service_orders (
                    order_id, client_name, client_phone, client_email,
                    printer_brand, printer_model, printer_serial,
                    issue_description, accessories, notes,
                    date_received, date_pickup_scheduled, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cur.execute(sql, (
                    order_id, client_name, client_phone, client_email,
                    printer_brand, printer_model, printer_serial,
                    issue_description, accessories, notes,
                    date_received, date_pickup, 'Received'
                ))
                self.conn.commit()

            self.next_order_id += 1
            st.sidebar.success("💾 Saved to database!")
            return order_id
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            st.sidebar.error(f"Save error: {str(e)}")
            return None

    def get_order(self, order_id):
        """Get order by ID from database"""
        try:
            if not self.conn:
                return None
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM service_orders WHERE order_id = %s", (order_id,))
                result = cur.fetchone()
                if result:
                    # Convert date objects to strings
                    order = dict(result)
                    for key in ['date_received', 'date_pickup_scheduled', 'date_completed', 'date_picked_up']:
                        if order.get(key):
                            order[key] = str(order[key])
                        else:
                            order[key] = ''
                    return order
                return None
        except Exception as e:
            st.error(f"Error fetching order: {str(e)}")
            return None

    def update_order(self, order_id, **kwargs):
        """Update order in database"""
        try:
            if not self.conn:
                return False

            # Calculate total cost if labor or parts cost provided
            if 'labor_cost' in kwargs or 'parts_cost' in kwargs:
                order = self.get_order(order_id)
                labor = float(kwargs.get('labor_cost', order.get('labor_cost', 0)))
                parts = float(kwargs.get('parts_cost', order.get('parts_cost', 0)))
                kwargs['total_cost'] = labor + parts

            # Build UPDATE query
            set_clause = ', '.join([f"{key} = %s" for key in kwargs.keys()])
            sql = f"UPDATE service_orders SET {set_clause}, updated_at = NOW() WHERE order_id = %s"
            values = list(kwargs.values()) + [order_id]

            with self.conn.cursor() as cur:
                cur.execute(sql, values)
                self.conn.commit()

            st.sidebar.success("💾 Updated in database!")
            return True
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            st.sidebar.error(f"Update error: {str(e)}")
            return False

    def list_orders_df(self):
        """Get all orders as DataFrame"""
        try:
            if not self.conn:
                return pd.DataFrame()

            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM service_orders ORDER BY date_received DESC")
                results = cur.fetchall()
                if results:
                    df = pd.DataFrame([dict(row) for row in results])
                    # Convert dates to strings
                    for col in ['date_received', 'date_pickup_scheduled', 'date_completed', 'date_picked_up']:
                        if col in df.columns:
                            df[col] = df[col].astype(str)
                    return df
                return pd.DataFrame()
        except Exception as e:
            st.error(f"Error loading orders: {str(e)}")
            return pd.DataFrame()


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    if not check_password():
        st.stop()

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

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        st.success(f"👤 {st.session_state.get('username', 'User')}")
        if st.button("🚪 Logout", key="logout_btn"):
            st.session_state['authenticated'] = False
            st.rerun()
        st.divider()

        # Logo upload
        with st.expander("🖼️ Company Logo", expanded=False):
            uploaded_logo = st.file_uploader("Upload logo (PNG/JPG)", type=['png', 'jpg', 'jpeg'], key="logo_uploader")
            if uploaded_logo:
                st.session_state['logo_image'] = uploaded_logo
                st.success("✅ Logo uploaded!")
                st.image(uploaded_logo, width=150)
            elif st.session_state['logo_image']:
                st.image(st.session_state['logo_image'], width=150)

        # Company details
        with st.expander("🏢 Company Details", expanded=False):
            st.session_state['company_info']['company_name'] = st.text_input("Company Name", value=st.session_state['company_info']['company_name'], key="company_name_input")
            st.session_state['company_info']['company_address'] = st.text_input("Address", value=st.session_state['company_info']['company_address'], key="company_address_input")
            st.session_state['company_info']['cui'] = st.text_input("CUI", value=st.session_state['company_info']['cui'], key="company_cui_input")
            st.session_state['company_info']['reg_com'] = st.text_input("Reg.Com", value=st.session_state['company_info']['reg_com'], key="company_regcom_input")
            st.session_state['company_info']['phone'] = st.text_input("Phone", value=st.session_state['company_info']['phone'], key="company_phone_input")
            st.session_state['company_info']['email'] = st.text_input("Email", value=st.session_state['company_info']['email'], key="company_email_input")

        # Database status
        with st.expander("🗄️ Database", expanded=False):
            test_database_connection()

    # Initialize CRM
    if 'crm' not in st.session_state:
        st.session_state['crm'] = PrinterServiceCRM()

    crm = st.session_state['crm']

    # Tabs
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
                    order_id = crm.create_service_order(client_name, client_phone, client_email, printer_brand, printer_model, printer_serial, issue_description, accessories, notes, date_received, date_pickup)
                    if order_id:
                        st.session_state['last_created_order'] = order_id
                        st.success(f"✅ Order Created: **{order_id}**")
                        st.balloons()
                else:
                    st.error("❌ Please fill in all required fields (*)")

        if st.session_state['last_created_order']:
            order = crm.get_order(st.session_state['last_created_order'])
            if order:
                st.divider()
                st.subheader("📄 Download Receipt")
                logo = st.session_state.get('logo_image', None)
                pdf_buffer = generate_initial_receipt_pdf(order, st.session_state['company_info'], logo)
                st.download_button("📄 Download Initial Receipt", pdf_buffer, f"Initial_{order['order_id']}.pdf", "application/pdf", type="secondary", use_container_width=True, key="dl_new_init")
                if st.button("✅ Done", use_container_width=True, key="done_new_order"):
                    st.session_state['last_created_order'] = None
                    st.rerun()


    with tab2:
        st.header("All Service Orders")
        df = crm.list_orders_df()
        if not df.empty:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📊 Total Orders", len(df))
            col2.metric("📥 Received", len(df[df['status'] == 'Received']))
            col3.metric("✅ Ready", len(df[df['status'] == 'Ready for Pickup']))
            col4.metric("🎉 Completed", len(df[df['status'] == 'Completed']))
            st.dataframe(df[['order_id', 'client_name', 'printer_brand', 'date_received', 'status', 'total_cost']], use_container_width=True)
            st.download_button("📥 Export to CSV", df.to_csv(index=False), f"orders_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", key="dl_csv")
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
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Client:** {order['client_name']}")
                        st.write(f"**Phone:** {order['client_phone']}")
                    with col2:
                        st.write(f"**Printer:** {order['printer_brand']} {order['printer_model']}")
                        st.write(f"**Received:** {order['date_received']}")
                    st.divider()
                    new_status = st.selectbox("Status", ['Received', 'In Progress', 'Ready for Pickup', 'Completed'], index=['Received', 'In Progress', 'Ready for Pickup', 'Completed'].index(order['status']))
                    if new_status == 'Completed':
                        actual_pickup_date = st.date_input("Actual Pickup Date", value=date.today())
                    st.subheader("Repair Details")
                    repair_details = st.text_area("Repairs Performed", value=order.get('repair_details', '') or '', height=100)
                    parts_used = st.text_input("Parts Used", value=order.get('parts_used', '') or '')
                    technician = st.text_input("Technician", value=order.get('technician', '') or '')
                    col1, col2, col3 = st.columns(3)
                    labor_cost = col1.number_input("Labor Cost (RON)", value=float(order.get('labor_cost', 0) or 0), min_value=0.0, step=10.0)
                    parts_cost = col2.number_input("Parts Cost (RON)", value=float(order.get('parts_cost', 0) or 0), min_value=0.0, step=10.0)
                    col3.metric("💰 Total Cost", f"{labor_cost + parts_cost:.2f} RON")
                    if st.button("💾 Update Order", type="primary", key="update_order_btn"):
                        updates = {'status': new_status, 'repair_details': repair_details, 'parts_used': parts_used, 'technician': technician, 'labor_cost': labor_cost, 'parts_cost': parts_cost}
                        if new_status == 'Ready for Pickup' and not order.get('date_completed'):
                            updates['date_completed'] = datetime.now().strftime("%Y-%m-%d")
                        if new_status == 'Completed':
                            updates['date_picked_up'] = actual_pickup_date.strftime("%Y-%m-%d")
                        if crm.update_order(selected_order_id, **updates):
                            st.success("✅ Order updated successfully!")
                            st.rerun()
                    st.divider()
                    st.subheader("📄 Download Receipts")
                    st.info("💡 Both PDFs available for download")
                    logo = st.session_state.get('logo_image', None)
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Initial Receipt**")
                        st.caption("Drop-off receipt for client")
                        pdf_init = generate_initial_receipt_pdf(order, st.session_state['company_info'], logo)
                        st.download_button("📄 Download Initial Receipt", pdf_init, f"Initial_{order['order_id']}.pdf", "application/pdf", use_container_width=True, key=f"dl_upd_init_{order['order_id']}")
                    with col2:
                        st.markdown("**Completion Receipt**")
                        st.caption("Pickup/invoice receipt")
                        if order.get('status') not in ['Ready for Pickup', 'Completed'] or float(order.get('total_cost', 0) or 0) == 0:
                            st.warning("⚠️ Complete repair details and costs first")
                        pdf_comp = generate_completion_receipt_pdf(order, st.session_state['company_info'], logo)
                        st.download_button("📄 Download Completion Receipt", pdf_comp, f"Completion_{order['order_id']}.pdf", "application/pdf", use_container_width=True, key=f"dl_upd_comp_{order['order_id']}")
        else:
            st.info("📝 No orders yet. Create your first order in the 'New Order' tab!")

    with tab4:
        st.header("Reports & Analytics")
        df = crm.list_orders_df()
        if not df.empty:
            col1, col2, col3 = st.columns(3)
            col1.metric("💰 Total Revenue", f"{df['total_cost'].sum():.2f} RON")
            avg_cost = df[df['total_cost'] > 0]['total_cost'].mean() if len(df[df['total_cost'] > 0]) > 0 else 0
            col2.metric("📊 Average Cost", f"{avg_cost:.2f} RON")
            col3.metric("👥 Unique Clients", df['client_name'].nunique())
            st.divider()
            st.subheader("Orders by Status")
            st.bar_chart(df['status'].value_counts())
        else:
            st.info("📝 No data yet. Create orders to see reports!")

if __name__ == "__main__":
    main()
