import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import hashlib
import math

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
    page_title="Printer Service CRM",
    page_icon="🖨️",
    layout="wide",
)


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
# PDF GENERATION
# ============================================================================
def generate_initial_receipt_pdf(order, company_info, logo_image=None):
    """PDF bon predare echipament (received order)"""
    buffer = io.BytesIO()
    width, height = 210 * mm, 148.5 * mm
    c = canvas.Canvas(buffer, pagesize=(width, height))

    # Logo
    if logo_image:
        try:
            logo = Image.open(logo_image)
            logo.thumbnail((150, 95), Image.Resampling.LANCZOS)
            logo_buffer = io.BytesIO()
            logo.save(logo_buffer, format="PNG")
            logo_buffer.seek(0)
            c.drawImage(
                ImageReader(logo_buffer),
                10 * mm, height - 30 * mm,
                width=40 * mm, height=25 * mm,
                preserveAspectRatio=True, mask="auto",
            )
        except Exception:
            c.setFillColor(colors.HexColor("#f0f0f0"))
            c.rect(10 * mm, height - 30 * mm, 40 * mm, 25 * mm, fill=1, stroke=1)
    else:
        c.setFillColor(colors.HexColor("#f0f0f0"))
        c.rect(10 * mm, height - 30 * mm, 40 * mm, 25 * mm, fill=1, stroke=1)

    # Company info
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(10 * mm, height - 35 * mm, remove_diacritics(company_info.get("company_name", "")))
    c.setFont("Helvetica", 8)
    y_pos = height - 40 * mm
    c.drawString(10 * mm, y_pos, remove_diacritics(company_info.get("company_address", "")))
    y_pos -= 3.5 * mm
    c.drawString(10 * mm, y_pos, f"CUI: {company_info.get('cui','')} | Reg.Com: {company_info.get('reg_com','')}")
    y_pos -= 3.5 * mm
    c.drawString(10 * mm, y_pos, f"Tel: {company_info.get('phone','')} | {company_info.get('email','')}")

    # Title
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(105 * mm, height - 55 * mm, "BON PREDARE ECHIPAMENT IN SERVICE")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#0066cc"))
    c.drawCentredString(105 * mm, height - 62 * mm, f"Nr. Comanda: {order['order_id']}")
    c.setFillColor(colors.black)

    # Details
    y_pos = height - 72 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10 * mm, y_pos, "DETALII ECHIPAMENT:")
    y_pos -= 5 * mm
    c.setFont("Helvetica", 8)
    c.drawString(10 * mm, y_pos, f"Imprimanta: {remove_diacritics(safe_text(order.get('printer_brand')))} {remove_diacritics(safe_text(order.get('printer_model')))}")
    y_pos -= 4 * mm
    c.drawString(10 * mm, y_pos, f"Serie: {safe_text(order.get('printer_serial','N/A'))}")
    y_pos -= 4 * mm
    c.drawString(10 * mm, y_pos, f"Data predarii: {safe_text(order.get('date_received'))}")

    if order.get("accessories"):
        y_pos -= 4 * mm
        c.drawString(10 * mm, y_pos, f"Accesorii: {remove_diacritics(safe_text(order.get('accessories')))}")

    y_pos -= 6 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10 * mm, y_pos, "PROBLEMA RAPORTATA:")
    y_pos -= 4 * mm
    c.setFont("Helvetica", 8)
    issue_text = remove_diacritics(safe_text(order.get("issue_description")))
    # Simple text wrapping
    words = issue_text.split()
    line = ""
    for word in words:
        test_line = line + word + " "
        if c.stringWidth(test_line, "Helvetica", 8) < 190 * mm:
            line = test_line
        else:
            c.drawString(10 * mm, y_pos, line)
            y_pos -= 4 * mm
            line = word + " "
    if line:
        c.drawString(10 * mm, y_pos, line)

    # Signatures
    y_pos = 25 * mm
    c.rect(10 * mm, y_pos, 85 * mm, 20 * mm)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(12 * mm, y_pos + 17 * mm, "OPERATOR SERVICE")
    c.setFont("Helvetica", 7)
    c.drawString(12 * mm, y_pos + 2 * mm, "Semnatura si stampila")

    c.rect(115 * mm, y_pos, 85 * mm, 20 * mm)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(117 * mm, y_pos + 17 * mm, "CLIENT")
    c.setFont("Helvetica", 7)
    c.drawString(117 * mm, y_pos + 13 * mm, f"Nume: {remove_diacritics(safe_text(order.get('client_name')))}")
    c.drawString(117 * mm, y_pos + 2 * mm, "Semnatura")

    c.setFont("Helvetica", 6)
    c.drawCentredString(105 * mm, 3 * mm, "Acest document constituie dovada predarii echipamentului in service.")

    c.save()
    buffer.seek(0)
    return buffer


def generate_completion_receipt_pdf(order, company_info, logo_image=None):
    """PDF bon finalizare (completion receipt)"""
    buffer = io.BytesIO()
    width, height = 210 * mm, 148.5 * mm
    c = canvas.Canvas(buffer, pagesize=(width, height))

    # Logo
    if logo_image:
        try:
            logo = Image.open(logo_image)
            logo.thumbnail((150, 95), Image.Resampling.LANCZOS)
            logo_buffer = io.BytesIO()
            logo.save(logo_buffer, format="PNG")
            logo_buffer.seek(0)
            c.drawImage(
                ImageReader(logo_buffer),
                10 * mm, height - 30 * mm,
                width=40 * mm, height=25 * mm,
                preserveAspectRatio=True, mask="auto",
            )
        except Exception:
            pass

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.HexColor("#00aa00"))
    c.drawCentredString(105 * mm, height - 40 * mm, "BON FINALIZARE REPARATIE")
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(105 * mm, height - 48 * mm, f"Nr. Comanda: {order['order_id']}")
    
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    y_pos = height - 60 * mm
    c.drawString(10 * mm, y_pos, f"Client: {safe_text(order.get('client_name'))}")
    y_pos -= 5 * mm
    c.drawString(10 * mm, y_pos, f"Telefon: {safe_text(order.get('client_phone'))}")
    y_pos -= 5 * mm
    c.drawString(10 * mm, y_pos, f"Echipament: {safe_text(order.get('printer_brand'))} {safe_text(order.get('printer_model'))}")
    
    y_pos -= 8 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10 * mm, y_pos, "REPARATII EFECTUATE:")
    y_pos -= 5 * mm
    c.setFont("Helvetica", 8)
    repair_text = remove_diacritics(safe_text(order.get('repair_details', 'N/A')))
    words = repair_text.split()
    line = ""
    for word in words:
        test_line = line + word + " "
        if c.stringWidth(test_line, "Helvetica", 8) < 190 * mm:
            line = test_line
        else:
            c.drawString(10 * mm, y_pos, line)
            y_pos -= 4 * mm
            line = word + " "
    if line:
        c.drawString(10 * mm, y_pos, line)
    
    y_pos -= 6 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10 * mm, y_pos, "PIESE UTILIZATE:")
    y_pos -= 5 * mm
    c.setFont("Helvetica", 8)
    c.drawString(10 * mm, y_pos, safe_text(order.get('parts_used', 'N/A')))
    
    y_pos -= 8 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(10 * mm, y_pos, f"Manopera: {safe_float(order.get('labor_cost')):.2f} RON")
    y_pos -= 6 * mm
    c.drawString(10 * mm, y_pos, f"Piese: {safe_float(order.get('parts_cost')):.2f} RON")
    y_pos -= 8 * mm
    c.setFillColor(colors.HexColor("#00aa00"))
    c.setFont("Helvetica-Bold", 14)
    total = safe_float(order.get('total_cost'))
    c.drawString(10 * mm, y_pos, f"TOTAL: {total:.2f} RON")

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

    # Load company info from Secrets (NOT from session state default)
    if "company_info" not in st.session_state:
        try:
            # Citim din secrets
            st.session_state["company_info"] = dict(st.secrets.get("company_info", {}))
        except Exception:
            # Fallback doar dacă secrets nu sunt setate
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

    tab1, tab2, tab3, tab4 = st.tabs(["📥 New Order", "📋 All Orders", "✏️ Update Order", "📊 Reports"])

    # ========================================================================
    # TAB 1: NEW ORDER
    # ========================================================================
    with tab1:
        st.header("Create New Service Order")
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
                        st.success(f"✅ Order Created: **{order_id}**")
                        st.balloons()
                else:
                    st.error("❌ Please fill in all required fields (*)")

        if st.session_state["last_created_order"]:
            # Re-read to get the order we just created
            df_fresh = crm.list_orders_df()
            order_row = df_fresh[df_fresh["order_id"] == st.session_state["last_created_order"]]
            if not order_row.empty:
                order = order_row.iloc[0].to_dict()
                st.divider()
                st.subheader("📄 Download Receipt")
                logo = st.session_state.get("logo_image", None)
                pdf_buffer = generate_initial_receipt_pdf(order, st.session_state["company_info"], logo)
                st.download_button(
                    "📄 Download Initial Receipt",
                    pdf_buffer,
                    f"Initial_{order['order_id']}.pdf",
                    "application/pdf",
                    type="secondary",
                    use_container_width=True,
                    key="dl_new_init",
                )
                if st.button("✅ Done", use_container_width=True, key="done_new_order"):
                    st.session_state["last_created_order"] = None
                    st.rerun()

    # ========================================================================
    # TAB 2: ALL ORDERS
    # ========================================================================
    with tab2:
        st.header("All Service Orders")
        df = df_all_orders
        if not df.empty:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📊 Total Orders", len(df))
            col2.metric("📥 Received", len(df[df["status"] == "Received"]))
            col3.metric("✅ Ready", len(df[df["status"] == "Ready for Pickup"]))
            col4.metric("🎉 Completed", len(df[df["status"] == "Completed"]))

            st.dataframe(
                df[["order_id", "client_name", "printer_brand", "date_received", "status", "total_cost"]],
                use_container_width=True,
            )

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
    # TAB 3: UPDATE ORDER
    # ========================================================================
    with tab3:
        st.header("Update Service Order")
        df = df_all_orders

        if not df.empty:
            # Selectează dintr-o listă
            available_orders = df["order_id"].tolist()
            selected_order_id = st.selectbox(
                "Select Order",
                available_orders,
                key="update_order_select",
                label_visibility="collapsed",  # Ascunde label-ul
            )


            if selected_order_id:
                order_row = df[df["order_id"] == selected_order_id]
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


                    # Status
                    status_options = ["Received", "In Progress", "Ready for Pickup", "Completed"]
                    current_status = safe_text(order.get("status")) or "Received"
                    if current_status not in status_options:
                        current_status = "Received"
                    status_index = status_options.index(current_status)

                    new_status = st.selectbox(
                        "Status",
                        status_options,
                        index=status_index,
                        key="update_status",
                    )

                    if new_status == "Completed":
                        actual_pickup_date = st.date_input(
                            "Actual Pickup Date",
                            value=date.today(),
                            key="update_pickup_date",
                        )
                    else:
                        actual_pickup_date = None

                    # Editable fields with old values
                    st.subheader("Repair details (editable)")

                    repair_details = st.text_area(
                        "Repairs performed",
                        value=safe_text(order.get("repair_details")),
                        height=100,
                        key="update_repair_details",
                    )

                    parts_used = st.text_input(
                        "Parts used",
                        value=safe_text(order.get("parts_used")),
                        key="update_parts_used",
                    )

                    technician = st.text_input(
                        "Technician",
                        value=safe_text(order.get("technician")),
                        key="update_technician",
                    )

                    # Costs
                    colc1, colc2, colc3 = st.columns(3)
                    labor_cost = colc1.number_input(
                        "Labor cost (RON)",
                        value=safe_float(order.get("labor_cost")),
                        min_value=0.0,
                        step=10.0,
                        key="update_labor_cost",
                    )
                    parts_cost = colc2.number_input(
                        "Parts cost (RON)",
                        value=safe_float(order.get("parts_cost")),
                        min_value=0.0,
                        step=10.0,
                        key="update_parts_cost",
                    )
                    colc3.metric("💰 Total", f"{labor_cost + parts_cost:.2f} RON")

                    # Update button
                    if st.button("💾 Update Order", type="primary", key="update_order_btn"):
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
    # TAB 4: REPORTS
    # ========================================================================
    with tab4:
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
