import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import hashlib
import math
import base64
from streamlit_gsheets import GSheetsConnection

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image


# ============================================================================
# APP CONFIG
# ============================================================================
st.set_page_config(
    page_title="PRINTHEAD Complete Solutions CRM",
    page_icon="🖨️",
    layout="wide",
)
# Load logo from repository
if "logo_image" not in st.session_state:
    try:
        logo_path = Path("assets/logo.png")
        if logo_path.exists():
            with open(logo_path, "rb") as f:
                logo_bytes = f.read()
            st.session_state["logo_image"] = io.BytesIO(logo_bytes)
        else:
            st.session_state["logo_image"] = None
    except Exception as e:
        st.warning(f"Logo not found: {e}")
        st.session_state["logo_image"] = None

# Initialize active tab in session state
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = 0

# Initialize selected order for tab2
if "selected_order_for_update" not in st.session_state:
    st.session_state["selected_order_for_update"] = None

# Track previous order to detect changes
if "previous_selected_order" not in st.session_state:
    st.session_state["previous_selected_order"] = None

# ============================================================================
# AUTHENTICATION
# ============================================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def check_password() -> bool:
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return True

    st.markdown("## 🔒 Login Required")
    st.markdown("Please enter your credentials to access the CRM system.")

    with st.form("login_form"):
        username = st.text_input("Username", value="admin")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            try:
                correct_password = st.secrets["passwords"]["admin_password"]
            except KeyError:
                st.error("❌ Password not configured in secrets!")
                st.info("Add 'passwords.admin_password' in Streamlit Cloud Settings → Secrets")
                return False

            if username == "admin" and hash_password(password) == hash_password(correct_password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid username or password")

    return False


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def remove_diacritics(text):
    if not isinstance(text, str):
        return text
    diacritics_map = {
        "ă": "a", "Ă": "A", "â": "a", "Â": "A",
        "î": "i", "Î": "I", "ș": "s", "Ș": "S",
        "ț": "t", "Ț": "T",
    }
    for d, r in diacritics_map.items():
        text = text.replace(d, r)
    return text


def safe_text(value: object) -> str:
    """Transformă None / NaN în string gol, altfel în string normal."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def safe_float(value: object, default: float = 0.0) -> float:
    """Transformă None / NaN / string gol în 0 (sau default)."""
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        if isinstance(value, str) and value.strip() == "":
            return default
        return float(value)
    except Exception:
        return default

# ============================================================================
# GOOGLE SHEETS CONNECTION
# ============================================================================
@st.cache_resource
def get_sheets_connection():
    """Native Streamlit connection to Google Sheets using streamlit-gsheets."""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        return conn
    except Exception as e:
        st.error(f"Google Sheets connection failed: {e}")
        return None

# ============================================================================
# PDF GENERATION - INITIAL RECEIPT (BON PREDARE)
# ============================================================================

def generate_initial_receipt_pdf(order, company_info, logo_image=None):
    buffer = io.BytesIO()
    width, height = 210*mm, 148.5*mm
    c = canvas.Canvas(buffer, pagesize=(width, height))
    
    header_y_start = height-10*mm
    x_business = 10*mm
    y_pos = header_y_start
    
    # Company info - left side
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
    c.drawString(x_business, y_pos, f"Email: {company_info.get('email','')}")
    
    # Logo - middle
    logo_x = 85*mm
    logo_y = header_y_start-20*mm
    logo_width = 40*mm
    logo_height = 25*mm
    # Logo cu calitate maximă
    if logo_buffer:
        try:
            logo_buffer.seek(0)
            img = Image.open(logo_buffer)
            
            # Calculează dimensiuni pentru PDF
            target_width_mm = 40
            aspect_ratio = img.height / img.width
            target_height_mm = target_width_mm * aspect_ratio
            
            if target_height_mm > 25:
                target_height_mm = 25
                target_width_mm = target_height_mm / aspect_ratio
            
            logo_buffer.seek(0)
            c.drawImage(
                ImageReader(logo_buffer), 
                10*mm, 
                height-30*mm, 
                width=target_width_mm*mm, 
                height=target_height_mm*mm, 
                preserveAspectRatio=True, 
                mask='auto'
            )
        except Exception as e:
            # Fallback placeholder
            c.setFillColor(colors.HexColor('#f0f0f0'))
            c.rect(10*mm, height-30*mm, 40*mm, 25*mm, fill=1, stroke=1)
            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(10*mm+20*mm, height-17.5*mm, "[LOGO]")
    else:
        c.setFillColor(colors.HexColor('#f0f0f0'))
        c.rect(10*mm, height-30*mm, 40*mm, 25*mm, fill=1, stroke=1)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(10*mm+20*mm, height-17.5*mm, "[LOGO]")
    
    # Client info - right side
    c.setFillColor(colors.black)
    x_client = 155*mm
    y_pos = header_y_start
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x_client, y_pos, "CLIENT")
    y_pos -= 3.5*mm
    c.setFont("Helvetica", 7)
    c.drawString(x_client, y_pos, f"Nume: {remove_diacritics(safe_text(order.get('client_name','')))}")
    y_pos -= 3*mm
    c.drawString(x_client, y_pos, f"Tel: {safe_text(order.get('client_phone',''))}")
    
    # Title
    title_y = height-38*mm
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(105*mm, title_y, "DOVADA PREDARE ECHIPAMENT IN SERVICE")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor('#E5283A'))
    c.drawCentredString(105*mm, title_y-6*mm, f"Nr. Comanda: {safe_text(order.get('order_id',''))}")
    c.setFillColor(colors.black)
  
    # Equipment details
    y_pos = height-50*mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10*mm, y_pos, "DETALII ECHIPAMENT:")
    y_pos -= 5*mm
    c.setFont("Helvetica", 8)
    
    printer_info = f"{remove_diacritics(safe_text(order.get('printer_brand','')))} {remove_diacritics(safe_text(order.get('printer_model','')))}"
    c.drawString(10*mm, y_pos, f"Imprimanta: {printer_info}")
    y_pos -= 4*mm
    
    serial = safe_text(order.get('printer_serial','N/A'))
    c.drawString(10*mm, y_pos, f"Serie: {serial}")
    y_pos -= 4*mm
    
    c.drawString(10*mm, y_pos, f"Data predarii: {safe_text(order.get('date_received',''))}")
    y_pos -= 4*mm
    
    accessories = safe_text(order.get('accessories',''))
    if accessories and accessories.strip():
        c.drawString(10*mm, y_pos, f"Accesorii: {remove_diacritics(accessories)}")
        y_pos -= 4*mm
    
    # Issue description
    y_pos -= 2*mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10*mm, y_pos, "PROBLEMA RAPORTATA:")
    y_pos -= 4*mm
    c.setFont("Helvetica", 8)
    
    issue_text = remove_diacritics(safe_text(order.get('issue_description','')))
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
    if line:
        text_object.textLine(line)
    c.drawText(text_object)

    # Signature boxes
    sig_y = 22*mm
    sig_height = 18*mm
    
    c.rect(10*mm, sig_y, 85*mm, sig_height)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(12*mm, sig_y+sig_height-3*mm, "OPERATOR SERVICE")
    c.setFont("Helvetica", 7)
    c.drawString(12*mm, sig_y+2*mm, "Semnatura")
    
    c.rect(115*mm, sig_y, 85*mm, sig_height)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(117*mm, sig_y+sig_height-3*mm, "CLIENT")
    c.setFont("Helvetica", 7)
    c.drawString(117*mm, sig_y+sig_height-7*mm, "Am luat la cunostinta")
    c.drawString(117*mm, sig_y+2*mm, "Semnatura")

    #more info
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(105*mm, 18*mm, "Avand in vedere ca dispozitivele din prezenta fisa nu au putut fi testate in momentul preluarii lor, acestea sunt considerate ca fiind nefunctionale.")
    c.setFont("Helvetica", 7)
    c.drawCentredString(105*mm, 15*mm, "Aveti obligatia ca, la finalizarea reparatiei echipamentului aflat in service, sa va prezentati in termen de 30 de zile de la data anuntarii de catre")
    c.setFont("Helvetica", 7)
    c.drawCentredString(105*mm, 12*mm, "reprezentantul SC PRINTHEAD COMPLETE SOLUTIONS SRL pentru a ridica echipamentul.In cazul neridicarii echipamentului")
    c.setFont("Helvetica", 7)
    c.drawCentredString(105*mm, 9*mm, "in intervalul specificat mai sus, ne rezervam dreptul de valorificare a acestuia")
    
    # Footer
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
    
    # Company info - left side
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
    c.drawString(x_business, y_pos, f"Email: {company_info.get('email','')}")
    
    # Logo - middle
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
    
    # Client info - right side
    c.setFillColor(colors.black)
    x_client = 155*mm
    y_pos = header_y_start
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x_client, y_pos, "CLIENT")
    y_pos -= 3.5*mm
    c.setFont("Helvetica", 7)
    c.drawString(x_client, y_pos, f"Nume: {remove_diacritics(safe_text(order.get('client_name','')))}")
    y_pos -= 3*mm
    c.drawString(x_client, y_pos, f"Tel: {safe_text(order.get('client_phone',''))}")
    
    # Title
    title_y = height-38*mm
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(105*mm, title_y, "DOVADA RIDICARE ECHIPAMENT DIN SERVICE")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor('#00aa00'))
    c.drawCentredString(105*mm, title_y-6*mm, f"Nr. Comanda: {safe_text(order.get('order_id',''))}")
    c.setFillColor(colors.black)
    
    # Three columns section
    y_start = height-50*mm
    col_width = 63*mm
    
    # LEFT COLUMN - Equipment details
    x_left = 10*mm
    y_pos = y_start
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x_left, y_pos, "DETALII ECHIPAMENT:")
    y_pos -= 3.5*mm
    c.setFont("Helvetica", 8)
    
    printer_info = f"{remove_diacritics(safe_text(order.get('printer_brand','')))} {remove_diacritics(safe_text(order.get('printer_model','')))}"
    if len(printer_info) > 25:
        printer_info = printer_info[:25] + "..."
    c.drawString(x_left, y_pos, f"Printer: {printer_info}")
    y_pos -= 2.5*mm
    
    serial = safe_text(order.get('printer_serial','N/A'))
    if len(serial) > 20:
        serial = serial[:20] + "..."
    c.drawString(x_left, y_pos, f"Serie: {serial}")
    y_pos -= 2.5*mm
    
    c.drawString(x_left, y_pos, f"Predare: {safe_text(order.get('date_received',''))}")
    if order.get('date_completed'):
        y_pos -= 2.5*mm
        c.drawString(x_left, y_pos, f"Finalizare: {safe_text(order.get('date_picked_up',''))}")
    
    # MIDDLE COLUMN - Repairs
    x_middle = 73*mm
    y_pos = y_start
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x_middle, y_pos, "REPARATII EFECTUATE:")
    y_pos -= 3.5*mm
    c.setFont("Helvetica", 8)
    
    repair_text = remove_diacritics(safe_text(order.get('repair_details','N/A')))
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
    
    # RIGHT COLUMN - Parts used
    x_right = 136*mm
    y_pos = y_start
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x_right, y_pos, "PIESE UTILIZATE:")
    y_pos -= 3.5*mm
    c.setFont("Helvetica", 8)
    
    parts_text = remove_diacritics(safe_text(order.get('parts_used','N/A')))
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
    
    # Costs table
    y_cost = height-78*mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10*mm, y_cost, "COSTURI:")
    y_cost -= 4*mm
    
    table_x = 10*mm
    table_width = 70*mm
    row_height = 5*mm
    
    # Table border
    c.rect(table_x, y_cost-(4*row_height), table_width, 4*row_height)
    
    # Header row
    c.setFillColor(colors.HexColor('#e0e0e0'))
    c.rect(table_x, y_cost-row_height, table_width, row_height, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(table_x+2*mm, y_cost-row_height+1.5*mm, "Descriere")
    c.drawString(table_x+table_width-22*mm, y_cost-row_height+1.5*mm, "Suma (RON)")
    c.line(table_x, y_cost-row_height, table_x+table_width, y_cost-row_height)
    
    y_cost -= row_height
    
    # Labor row
    c.setFont("Helvetica", 8)
    c.drawString(table_x+2*mm, y_cost-row_height+1.5*mm, "Manopera")
    labor = safe_float(order.get('labor_cost',0))
    c.drawString(table_x+table_width-22*mm, y_cost-row_height+1.5*mm, f"{labor:.2f}")
    c.line(table_x, y_cost-row_height, table_x+table_width, y_cost-row_height)
    y_cost -= row_height
    
    # Parts row
    c.drawString(table_x+2*mm, y_cost-row_height+1.5*mm, "Piese")
    parts = safe_float(order.get('parts_cost',0))
    c.drawString(table_x+table_width-22*mm, y_cost-row_height+1.5*mm, f"{parts:.2f}")
    c.line(table_x, y_cost-row_height, table_x+table_width, y_cost-row_height)
    y_cost -= row_height
    
    # Total row
    c.setFillColor(colors.HexColor('#f0f0f0'))
    c.rect(table_x, y_cost-row_height, table_width, row_height, fill=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(table_x+2*mm, y_cost-row_height+1.5*mm, "TOTAL")
    total = safe_float(order.get('total_cost', labor+parts))
    c.drawString(table_x+table_width-22*mm, y_cost-row_height+1.5*mm, f"{total:.2f}")
    
    # Signature boxes
    sig_y = 22*mm
    sig_height = 18*mm
    
    c.rect(10*mm, sig_y, 85*mm, sig_height)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(12*mm, sig_y+sig_height-3*mm, "OPERATOR SERVICE")
    c.setFont("Helvetica", 7)
    c.drawString(12*mm, sig_y+2*mm, "Semnatura")
    
    c.rect(115*mm, sig_y, 85*mm, sig_height)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(117*mm, sig_y+sig_height-3*mm, "CLIENT")
    c.setFont("Helvetica", 7)
    c.drawString(117*mm, sig_y+sig_height-7*mm, "Am luat la cunostinta")
    c.drawString(117*mm, sig_y+2*mm, "Semnatura")
    
    # Footer
    c.setFont("Helvetica", 6)
    c.drawCentredString(105*mm, 3*mm, "Acest document constituie dovada ridicarii echipamentului din service.")
    c.setDash(3, 3)
    c.line(5*mm, 1*mm, 205*mm, 1*mm)
    
    c.save()
    buffer.seek(0)
    return buffer

# ============================================================================
# CRM CLASS - GOOGLE SHEETS BACKEND
# ============================================================================
class PrinterServiceCRM:
    def __init__(self, conn: GSheetsConnection):
        self.conn = conn
        self.worksheet = "Orders"
        self.next_order_id = 1
        self._init_sheet()

    def _init_sheet(self):
        """Ensure headers exist and compute next_order_id."""
        df = self._read_df(raw=True, ttl=0)
        if df is None or df.empty:
            columns = [
                "order_id", "client_name", "client_phone", "client_email",
                "printer_brand", "printer_model", "printer_serial",
                "issue_description", "accessories", "notes",
                "date_received", "date_pickup_scheduled", "date_completed", "date_picked_up",
                "status", "technician", "repair_details", "parts_used",
                "labor_cost", "parts_cost", "total_cost",
            ]
            df = pd.DataFrame(columns=columns)
            self._write_df(df, allow_empty=False)
            self.next_order_id = 1
        else:
            if "order_id" in df.columns and not df["order_id"].isna().all():
                try:
                    max_id = max(
                        int(str(oid).split("-")[1])
                        for oid in df["order_id"]
                        if str(oid).startswith("SRV-")
                    )
                    self.next_order_id = max_id + 1
                except Exception:
                    self.next_order_id = 1
            else:
                self.next_order_id = 1

    def _read_df(self, raw: bool = False, ttl: int = 60) -> pd.DataFrame | None:
        """Read sheet with caching (ttl in seconds)."""
        try:
            df = self.conn.read(worksheet=self.worksheet, ttl=ttl)
            if df is None:
                return None
            if raw:
                return df
            if df.empty:
                return pd.DataFrame()
            for col in ["labor_cost", "parts_cost", "total_cost"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            return df
        except Exception as e:
            st.sidebar.error(f"❌ Error reading from Google Sheets: {e}")
            return None if raw else pd.DataFrame()

    def _write_df(self, df: pd.DataFrame, allow_empty: bool = False) -> bool:
        """Write entire DataFrame to Sheets. Prevents accidental data loss."""
        try:
            if df is None:
                st.sidebar.error("❌ Tried to write None DataFrame to Sheets.")
                return False
            if df.empty and not allow_empty:
                st.sidebar.error("⚠️ Refusing to write empty DataFrame to prevent data loss.")
                return False
            self.conn.update(worksheet=self.worksheet, data=df)
            st.sidebar.success("💾 Saved to Google Sheets!")
            return True
        except Exception as e:
            st.sidebar.error(f"❌ Error saving to Google Sheets: {e}")
            return False

    def create_service_order(
        self, client_name, client_phone, client_email, printer_brand, printer_model,
        printer_serial, issue_description, accessories, notes, date_received, date_pickup
    ):
        order_id = f"SRV-{self.next_order_id:05d}"
        new_order = pd.DataFrame([{
            "order_id": order_id,
            "client_name": client_name,
            "client_phone": client_phone,
            "client_email": client_email,
            "printer_brand": printer_brand,
            "printer_model": printer_model,
            "printer_serial": printer_serial,
            "issue_description": issue_description,
            "accessories": accessories,
            "notes": notes,
            "date_received": date_received.strftime("%Y-%m-%d") if date_received else datetime.now().strftime("%Y-%m-%d"),
            "date_pickup_scheduled": date_pickup.strftime("%Y-%m-%d") if date_pickup else "",
            "date_completed": "",
            "date_picked_up": "",
            "status": "Received",
            "technician": "",
            "repair_details": "",
            "parts_used": "",
            "labor_cost": 0.0,
            "parts_cost": 0.0,
            "total_cost": 0.0,
        }])

        df = self._read_df(raw=True, ttl=0)
        if df is None or df.empty:
            updated_df = new_order
        else:
            updated_df = pd.concat([df, new_order], ignore_index=True)

        if self._write_df(updated_df):
            self.next_order_id += 1
            return order_id
        return None

    def list_orders_df(self) -> pd.DataFrame:
        df = self._read_df(raw=False, ttl=60)
        return df if df is not None else pd.DataFrame()

    def update_order(self, order_id: str, **kwargs) -> bool:
        """Update ONLY the matching row, write back entire DataFrame."""
        df = self._read_df(raw=True, ttl=0)
        if df is None or df.empty or "order_id" not in df.columns:
            st.sidebar.error("❌ Cannot update: no data found in Google Sheets.")
            return False

        mask = df["order_id"] == order_id
        if not mask.any():
            st.sidebar.error(f"❌ Order {order_id} not found in sheet.")
            return False

        for key, value in kwargs.items():
            if key in df.columns:
                df.loc[mask, key] = value

        if "labor_cost" in df.columns and "parts_cost" in df.columns:
            labor = pd.to_numeric(df.loc[mask, "labor_cost"], errors="coerce").fillna(0)
            parts = pd.to_numeric(df.loc[mask, "parts_cost"], errors="coerce").fillna(0)
            df.loc[mask, "total_cost"] = labor + parts

        return self._write_df(df)


# ============================================================================
# MAIN APP
# ============================================================================
def main():
    if not check_password():
        st.stop()

    st.title("🖨️ Printer Service CRM")
    st.markdown("### Professional Printer Service Management System")

    # Load company info from Secrets
    if "company_info" not in st.session_state:
        try:
            st.session_state["company_info"] = dict(st.secrets.get("company_info", {}))
        except Exception:
            st.session_state["company_info"] = {
                "company_name": "Company Name",
                "company_address": "Address",
                "cui": "CUI",
                "reg_com": "Reg.Com",
                "phone": "Phone",
                "email": "Email",
            }
    
    if "last_created_order" not in st.session_state:
        st.session_state["last_created_order"] = None
    if "logo_image" not in st.session_state:
        st.session_state["logo_image"] = None
    if "pdf_downloaded" not in st.session_state:
        st.session_state["pdf_downloaded"] = False

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        st.success(f"👤 {st.session_state.get('username', 'User')}")

        if st.button("🚪 Logout", key="logout_btn"):
            st.session_state["authenticated"] = False
            st.rerun()

        st.divider()

        with st.expander("🖼️ Company Logo", expanded=False):
            uploaded_logo = st.file_uploader(
                "Upload logo (PNG/JPG)", type=["png", "jpg", "jpeg"], key="logo_uploader"
            )
            if uploaded_logo:
                st.session_state["logo_image"] = uploaded_logo
                st.success("✅ Logo uploaded!")
                st.image(uploaded_logo, width=150)
            elif st.session_state["logo_image"]:
                st.image(st.session_state["logo_image"], width=150)

        with st.expander("🏢 Company Details", expanded=False):
            ci = st.session_state["company_info"]
            ci["company_name"] = st.text_input("Company Name", value=ci["company_name"], key="company_name_input")
            ci["company_address"] = st.text_input("Address", value=ci["company_address"], key="company_address_input")
            ci["cui"] = st.text_input("CUI", value=ci["cui"], key="company_cui_input")
            ci["reg_com"] = st.text_input("Reg.Com", value=ci["reg_com"], key="company_regcom_input")
            ci["phone"] = st.text_input("Phone", value=ci["phone"], key="company_phone_input")
            ci["email"] = st.text_input("Email", value=ci["email"], key="company_email_input")

        conn = get_sheets_connection()
        with st.expander("📊 Google Sheets", expanded=False):
            if conn:
                st.success("✅ Connected to Google Sheets!")
            else:
                st.error("❌ Not connected to Google Sheets")

    conn = get_sheets_connection()
    if not conn:
        st.error("Cannot connect to Google Sheets. Check secrets configuration.")
        st.stop()

    if "crm" not in st.session_state:
        st.session_state["crm"] = PrinterServiceCRM(conn)

    crm = st.session_state["crm"]

    # Read all orders ONCE per run to minimize API calls
    df_all_orders = crm.list_orders_df()

    # Create tab navigation with buttons
    tab_titles = ["📥 New Order", "📋 All Orders", "✏️ Update Order", "📊 Reports"]
    
    cols = st.columns(4)
    for idx, (col, title) in enumerate(zip(cols, tab_titles)):
        with col:
            if st.button(title, key=f"tab_btn_{idx}", use_container_width=True, 
                        type="primary" if st.session_state["active_tab"] == idx else "secondary"):
                st.session_state["active_tab"] = idx
                st.rerun()

    st.divider()

    active_tab = st.session_state["active_tab"]

    # ========================================================================
    # TAB 0: NEW ORDER
    # ========================================================================
    if active_tab == 0:
        st.header("Create New Service Order")
        
        # Show form only if no order was just created
        if not st.session_state["last_created_order"] or st.session_state["pdf_downloaded"]:
            with st.form(key="new_order_form", clear_on_submit=True):
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
                            client_name, client_phone, client_email, printer_brand, printer_model,
                            printer_serial, issue_description, accessories, notes, date_received, date_pickup
                        )
                        if order_id:
                            st.session_state["last_created_order"] = order_id
                            st.session_state["pdf_downloaded"] = False
                            st.success(f"✅ Order Created: **{order_id}**")
                            st.balloons()
                            st.rerun()
                    else:
                        st.error("❌ Please fill in all required fields (*)")

        # Show download section after order creation
        if st.session_state["last_created_order"] and not st.session_state["pdf_downloaded"]:
            df_fresh = crm.list_orders_df()
            order_row = df_fresh[df_fresh["order_id"] == st.session_state["last_created_order"]]
            if not order_row.empty:
                order = order_row.iloc[0].to_dict()
                st.divider()
                st.success(f"✅ Order Created: **{order['order_id']}**")
                st.subheader("📄 Download Receipt")
                logo = st.session_state.get("logo_image", None)
                pdf_buffer = generate_initial_receipt_pdf(order, st.session_state["company_info"], logo)
                
                if st.download_button(
                    "📄 Download Initial Receipt",
                    pdf_buffer,
                    f"Initial_{order['order_id']}.pdf",
                    "application/pdf",
                    type="primary",
                    use_container_width=True,
                    key="dl_new_init",
                ):
                    st.session_state["last_created_order"] = None
                    st.session_state["pdf_downloaded"] = True
                    st.rerun()

    # ========================================================================
    # TAB 1: ALL ORDERS
    # ========================================================================
    elif active_tab == 1:
        st.header("All Service Orders")
        df = df_all_orders
        if not df.empty:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📊 Total Orders", len(df))
            col2.metric("📥 Received", len(df[df["status"] == "Received"]))
            col3.metric("✅ Ready", len(df[df["status"] == "Ready for Pickup"]))
            col4.metric("🎉 Completed", len(df[df["status"] == "Completed"]))

            st.markdown("**Click on a row to edit that order:**")
            
            event = st.dataframe(
                df[["order_id", "client_name", "printer_brand","printer_serial", "date_received", "status", "total_cost"]],
                use_container_width=True,
                selection_mode="single-row",
                on_select="rerun",
                key="orders_table"
            )
            
            if event and "selection" in event and event["selection"]["rows"]:
                selected_idx = event["selection"]["rows"][0]
                selected_order_id = df.iloc[selected_idx]["order_id"]
                
                st.session_state["selected_order_for_update"] = selected_order_id
                st.session_state["previous_selected_order"] = None  # Reset to force reload
                st.session_state["active_tab"] = 2
                st.rerun()

            csv = df.to_csv(index=False)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                "📥 Export to CSV",
                csv,
                f"orders_{ts}.csv",
                "text/csv",
                key="dl_csv",
                use_container_width=True,
            )
        else:
            st.info("📝 No orders yet. Create your first order in the 'New Order' tab!")

    # ========================================================================
    # TAB 2: UPDATE ORDER
    # ========================================================================
    elif active_tab == 2:
        st.header("Update Service Order")
        
        df = df_all_orders

        if not df.empty:
            available_orders = df["order_id"].tolist()
            
            default_idx = 0
            if st.session_state["selected_order_for_update"] in available_orders:
                default_idx = available_orders.index(st.session_state["selected_order_for_update"])
            
            def on_order_select():
                st.session_state["active_tab"] = 2
            
            selected_order_id = st.selectbox(
                "Select Order",
                available_orders,
                index=default_idx,
                key="update_order_select",
                label_visibility="collapsed",
                on_change=on_order_select
            )

            # DETECT ORDER CHANGE AND FORCE RERUN
            if st.session_state["previous_selected_order"] != selected_order_id:
                st.session_state["previous_selected_order"] = selected_order_id
                st.rerun()

            if selected_order_id:
                # Fetch FRESH data from spreadsheet with NO caching
                df_fresh = crm._read_df(raw=True, ttl=0)
                order_row = df_fresh[df_fresh["order_id"] == selected_order_id]
                
                if order_row.empty:
                    st.error("❌ Order not found in current data. Try refreshing the page.")
                else:
                    order = order_row.iloc[0].to_dict()

                    # Display basic info
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Client:** {safe_text(order.get('client_name'))}")
                        st.write(f"**Phone:** {safe_text(order.get('client_phone'))}")
                        st.write(f"**Printer Name:** {safe_text(order.get('printer_brand'))}")
                        st.write(f"**Printer Model:** {safe_text(order.get('printer_model'))}")
                        st.write(f"**Printer Serial:** {safe_text(order.get('printer_serial'))}")
                    with col2:
                        st.write(f"**Received:** {safe_text(order.get('date_received'))}")
                        st.write(f"**Issue reported:** {safe_text(order.get('issue_description'))}")
                        st.write(f"**Accessories:** {safe_text(order.get('accessories'))}")
                        st.write(f"**Internal notes:** {safe_text(order.get('notes'))}")

                    st.divider()

                    # Status with unique key per order
                    status_options = ["Received", "In Progress", "Ready for Pickup", "Completed"]
                    current_status = safe_text(order.get("status")) or "Received"
                    if current_status not in status_options:
                        current_status = "Received"
                    status_index = status_options.index(current_status)

                    new_status = st.selectbox(
                        "Status",
                        status_options,
                        index=status_index,
                        key=f"update_status_{selected_order_id}",
                    )

                    if new_status == "Completed":
                        actual_pickup_date = st.date_input(
                            "Actual Pickup Date",
                            value=date.today(),
                            key=f"update_pickup_date_{selected_order_id}",
                        )
                    else:
                        actual_pickup_date = None

                    # Editable fields with UNIQUE KEYS per order
                    st.subheader("Repair details")

                    repair_details = st.text_area(
                        "Repairs performed",
                        value=safe_text(order.get("repair_details")),
                        height=100,
                        key=f"update_repair_details_{selected_order_id}",
                        help="This field is loaded from the spreadsheet. You can edit or add to existing text."
                    )

                    parts_used = st.text_input(
                        "Parts used",
                        value=safe_text(order.get("parts_used")),
                        key=f"update_parts_used_{selected_order_id}",
                        help="This field is loaded from the spreadsheet. You can edit or add to existing text."
                    )

                    technician = st.text_input(
                        "Technician",
                        value=safe_text(order.get("technician")),
                        key=f"update_technician_{selected_order_id}",
                        help="This field is loaded from the spreadsheet."
                    )

                    # Costs with UNIQUE KEYS
                    colc1, colc2, colc3 = st.columns(3)
                    labor_cost = colc1.number_input(
                        "Labor cost (RON)",
                        value=safe_float(order.get("labor_cost")),
                        min_value=0.0,
                        step=10.0,
                        key=f"update_labor_cost_{selected_order_id}",
                        help="Loaded from spreadsheet"
                    )
                    parts_cost = colc2.number_input(
                        "Parts cost (RON)",
                        value=safe_float(order.get("parts_cost")),
                        min_value=0.0,
                        step=10.0,
                        key=f"update_parts_cost_{selected_order_id}",
                        help="Loaded from spreadsheet"
                    )
                    colc3.metric("💰 Total", f"{labor_cost + parts_cost:.2f} RON")

                    # Update button
                    if st.button("💾 Update Order", type="primary", key=f"update_order_btn_{selected_order_id}"):
                        updates = {
                            "status": new_status,
                            "repair_details": repair_details,
                            "parts_used": parts_used,
                            "technician": technician,
                            "labor_cost": labor_cost,
                            "parts_cost": parts_cost,
                        }

                        if new_status == "Ready for Pickup" and not order.get("date_completed"):
                            updates["date_completed"] = datetime.now().strftime("%Y-%m-%d")
                        if new_status == "Completed":
                            updates["date_picked_up"] = (
                                actual_pickup_date.strftime("%Y-%m-%d")
                                if actual_pickup_date
                                else datetime.now().strftime("%Y-%m-%d")
                            )

                        if crm.update_order(selected_order_id, **updates):
                            st.success("✅ Order updated successfully!")
                            st.session_state["active_tab"] = 2
                            st.rerun()

                    # PDF downloads
                    st.divider()
                    st.subheader("📄 Download Receipts")
                    logo = st.session_state.get("logo_image", None)
                    colp1, colp2 = st.columns(2)
                    with colp1:
                        st.markdown("**Initial Receipt (Received)**")
                        pdf_init = generate_initial_receipt_pdf(order, st.session_state["company_info"], logo)
                        st.download_button(
                            "📄 Download Initial Receipt",
                            pdf_init,
                            f"Initial_{order['order_id']}.pdf",
                            "application/pdf",
                            use_container_width=True,
                            key=f"dl_upd_init_{order['order_id']}",
                        )
                    with colp2:
                        st.markdown("**Completion Receipt (Ready/Completed)**")
                        pdf_comp = generate_completion_receipt_pdf(order, st.session_state["company_info"], logo)
                        st.download_button(
                            "📄 Download Completion Receipt",
                            pdf_comp,
                            f"Completion_{order['order_id']}.pdf",
                            "application/pdf",
                            use_container_width=True,
                            key=f"dl_upd_comp_{order['order_id']}",
                        )
        else:
            st.info("📝 No orders yet. Create your first order in the 'New Order' tab!")

    # ========================================================================
    # TAB 3: REPORTS
    # ========================================================================
    elif active_tab == 3:
        st.header("Reports & Analytics")
        df = df_all_orders
        if not df.empty:
            col1, col2, col3 = st.columns(3)
            col1.metric("💰 Total Revenue", f"{df['total_cost'].sum():.2f} RON")
            avg_cost = df[df["total_cost"] > 0]["total_cost"].mean() if len(df[df["total_cost"] > 0]) > 0 else 0
            col2.metric("📊 Average Cost", f"{avg_cost:.2f} RON")
            col3.metric("👥 Unique Clients", df["client_name"].nunique())

            st.divider()
            st.subheader("Orders by Status")
            st.bar_chart(df["status"].value_counts())
        else:
            st.info("📝 No data yet. Create orders to see reports!")


if __name__ == "__main__":
    main()
