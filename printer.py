import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import hashlib
import math  # dacă nu e deja importat sus

from streamlit_gsheets import GSheetsConnection

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from PIL import Image


# -------------------------------------------------------------------
# APP CONFIG
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Printer Service CRM",
    page_icon="🖨️",
    layout="wide",
)


# -------------------------------------------------------------------
# AUTH
# -------------------------------------------------------------------
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
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            try:
                correct_password = st.secrets["passwords"]["admin_password"]
            except KeyError:
                st.error("❌ Password not configured in secrets!")
                st.info(
                    "Add 'passwords.admin_password' in Streamlit Cloud Settings → Secrets"
                )
                return False

            if username == "admin" and hash_password(password) == hash_password(
                correct_password
            ):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid username or password")

    return False


# -------------------------------------------------------------------
# UTILS
# -------------------------------------------------------------------
def remove_diacritics(text):
    if not isinstance(text, str):
        return text
    diacritics_map = {
        "ă": "a",
        "Ă": "A",
        "â": "a",
        "Â": "A",
        "î": "i",
        "Î": "I",
        "ș": "s",
        "Ș": "S",
        "ț": "t",
        "Ț": "T",
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

# -------------------------------------------------------------------
# GOOGLE SHEETS CONNECTION (st.connection)
# -------------------------------------------------------------------
@st.cache_resource
def get_sheets_connection():
    """
    Native Streamlit connection to Google Sheets using streamlit-gsheets.

    Requires in secrets:

    [connections.gsheets]
    spreadsheet = "https://docs.google.com/spreadsheets/d/ID/edit"
    type = "service_account"
    project_id = "..."
    private_key_id = "..."
    private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
    client_email = "service-account@project.iam.gserviceaccount.com"
    client_id = "..."
    auth_uri = "https://accounts.google.com/o/oauth2/auth"
    token_uri = "https://oauth2.googleapis.com/token"
    auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
    client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
    """
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        return conn
    except Exception as e:
        st.error(f"Google Sheets connection failed: {e}")
        return None


# -------------------------------------------------------------------
# PDF GENERATION
# -------------------------------------------------------------------
def generate_initial_receipt_pdf(order, company_info, logo_image=None):
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
                10 * mm,
                height - 30 * mm,
                width=40 * mm,
                height=25 * mm,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            c.setFillColor(colors.HexColor("#f0f0f0"))
            c.rect(10 * mm, height - 30 * mm, 40 * mm, 25 * mm, fill=1, stroke=1)
            c.setFillColor(colors.black)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(15 * mm, height - 20 * mm, "[LOGO]")
    else:
        c.setFillColor(colors.HexColor("#f0f0f0"))
        c.rect(10 * mm, height - 30 * mm, 40 * mm, 25 * mm, fill=1, stroke=1)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(15 * mm, height - 20 * mm, "[LOGO]")

    # Company info
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(
        10 * mm,
        height - 35 * mm,
        remove_diacritics(company_info.get("company_name", "")),
    )
    c.setFont("Helvetica", 8)
    y_pos = height - 40 * mm
    c.drawString(
        10 * mm, y_pos, remove_diacritics(company_info.get("company_address", ""))
    )
    y_pos -= 3.5 * mm
    c.drawString(
        10 * mm,
        y_pos,
        f"CUI: {company_info.get('cui','')} | Reg.Com: {company_info.get('reg_com','')}",
    )
    y_pos -= 3.5 * mm
    c.drawString(
        10 * mm,
        y_pos,
        f"Tel: {company_info.get('phone','')} | {company_info.get('email','')}",
    )

    # Title
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(105 * mm, height - 55 * mm, "BON PREDARE ECHIPAMENT IN SERVICE")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#0066cc"))
    c.drawCentredString(
        105 * mm, height - 62 * mm, f"Nr. Comandă: {order['order_id']}"
    )
    c.setFillColor(colors.black)

    # Details
    y_pos = height - 72 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10 * mm, y_pos, "DETALII ECHIPAMENT:")
    y_pos -= 5 * mm
    c.setFont("Helvetica", 8)
    c.drawString(
        10 * mm,
        y_pos,
        f"Imprimantă: {remove_diacritics(order['printer_brand'])} {remove_diacritics(order['printer_model'])}",
    )
    y_pos -= 4 * mm
    c.drawString(10 * mm, y_pos, f"Serie: {order.get('printer_serial','N/A')}")
    y_pos -= 4 * mm
    c.drawString(10 * mm, y_pos, f"Data predării: {order['date_received']}")

    if order.get("accessories"):
        y_pos -= 4 * mm
        c.drawString(
            10 * mm,
            y_pos,
            f"Accesorii: {remove_diacritics(order['accessories'])}",
        )

    y_pos -= 6 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(10 * mm, y_pos, "PROBLEMĂ RAPORTATĂ:")
    y_pos -= 4 * mm
    c.setFont("Helvetica", 8)
    issue_text = remove_diacritics(order["issue_description"])
    text_object = c.beginText(10 * mm, y_pos)
    text_object.setFont("Helvetica", 8)
    words = issue_text.split()
    line = ""
    for word in words:
        test_line = line + word + " "
        if c.stringWidth(test_line, "Helvetica", 8) < 190 * mm:
            line = test_line
        else:
            text_object.textLine(line)
            line = word + " "
    text_object.textLine(line)
    c.drawText(text_object)

    # Signatures
    y_pos = 25 * mm
    c.rect(10 * mm, y_pos, 85 * mm, 20 * mm)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(12 * mm, y_pos + 17 * mm, "OPERATOR SERVICE")
    c.setFont("Helvetica", 7)
    c.drawString(12 * mm, y_pos + 2 * mm, "Semnătură și ștampilă")

    c.rect(115 * mm, y_pos, 85 * mm, 20 * mm)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(117 * mm, y_pos + 17 * mm, "CLIENT")
    c.setFont("Helvetica", 7)
    c.drawString(
        117 * mm,
        y_pos + 13 * mm,
        f"Nume: {remove_diacritics(order['client_name'])}",
    )
    c.drawString(117 * mm, y_pos + 2 * mm, "Semnătură")

    c.setFont("Helvetica", 6)
    c.drawCentredString(
        105 * mm,
        3 * mm,
        "Acest document constituie dovada predării echipamentului în service.",
    )
    c.setDash(3, 3)
    c.line(5 * mm, 1 * mm, 205 * mm, 1 * mm)

    c.save()
    buffer.seek(0)
    return buffer


def generate_completion_receipt_pdf(order, company_info, logo_image=None):
    buffer = io.BytesIO()
    width, height = 210 * mm, 148.5 * mm
    c = canvas.Canvas(buffer, pagesize=(width, height))

    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(105 * mm, height - 30 * mm, "BON FINALIZARE REPARAȚIE")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#00aa00"))
    c.drawCentredString(
        105 * mm, height - 38 * mm, f"Nr. Comandă: {order['order_id']}"
    )
    c.setFillColor(colors.black)

    c.setFont("Helvetica", 8)
    c.drawString(
        10 * mm,
        height - 50 * mm,
        f"Total: {float(order.get('total_cost',0)):.2f} RON",
    )

    c.save()
    buffer.seek(0)
    return buffer


# -------------------------------------------------------------------
# CRM CLASS - GOOGLE SHEETS (SAFE VERSION)
# -------------------------------------------------------------------
class PrinterServiceCRM:
    def __init__(self, conn: GSheetsConnection):
        self.conn = conn
        self.worksheet = "Orders"
        self.next_order_id = 1
        self._init_sheet()

    # ---------- internal helpers ----------

    def _init_sheet(self):
        """Ensure headers exist and compute next_order_id."""
        df = self._read_df(raw=True)
        if df is None or df.empty:
            # create empty schema
            columns = [
                "order_id",
                "client_name",
                "client_phone",
                "client_email",
                "printer_brand",
                "printer_model",
                "printer_serial",
                "issue_description",
                "accessories",
                "notes",
                "date_received",
                "date_pickup_scheduled",
                "date_completed",
                "date_picked_up",
                "status",
                "technician",
                "repair_details",
                "parts_used",
                "labor_cost",
                "parts_cost",
                "total_cost",
            ]
            df = pd.DataFrame(columns=columns)
            # scriem schema o singură dată, nu se pierde nimic
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

    def _read_df(self, raw: bool = False) -> pd.DataFrame | None:
        """
        Citește foaia din Google Sheets folosind caching-ul intern al
        st-gsheets-connection (ttl=60 sec), ca să nu mai lovești cota de 60
        request-uri/minut.
        """
        try:
            # IMPORTANT: folosim ttl=60, NU 0
            df = self.conn.read(worksheet=self.worksheet, ttl=60)

            if df is None:
                return None
            if raw:
                return df
            if df.empty:
                return pd.DataFrame()

            # conversie numerică
            for col in ["labor_cost", "parts_cost", "total_cost"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            return df

        except Exception as e:
            st.sidebar.error(f"❌ Error reading from Google Sheets: {e}")
            return None if raw else pd.DataFrame()


    def _write_df(self, df: pd.DataFrame, allow_empty: bool = False) -> bool:
        """
        Scrie ÎNTREGUL DataFrame în Sheets.
        Dacă df este gol și allow_empty=False, refuză scrierea ca să nu șteargă toate datele.
        """
        try:
            if df is None:
                st.sidebar.error("❌ Tried to write None DataFrame to Sheets.")
                return False

            if df.empty and not allow_empty:
                st.sidebar.error(
                    "⚠️ Refuz să scriu un DataFrame gol în Google Sheets ca să nu pierzi toate comenzile."
                )
                return False

            self.conn.update(worksheet=self.worksheet, data=df)
            st.sidebar.success("💾 Saved to Google Sheets!")
            return True
        except Exception as e:
            st.sidebar.error(f"❌ Error saving to Google Sheets: {e}")
            return False

    # ---------- CRUD ----------

    def create_service_order(
        self,
        client_name,
        client_phone,
        client_email,
        printer_brand,
        printer_model,
        printer_serial,
        issue_description,
        accessories,
        notes,
        date_received,
        date_pickup,
    ):
        order_id = f"SRV-{self.next_order_id:05d}"

        new_order = pd.DataFrame(
            [
                {
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
                    "date_received": date_received.strftime("%Y-%m-%d")
                    if date_received
                    else datetime.now().strftime("%Y-%m-%d"),
                    "date_pickup_scheduled": date_pickup.strftime("%Y-%m-%d")
                    if date_pickup
                    else "",
                    "date_completed": "",
                    "date_picked_up": "",
                    "status": "Received",
                    "technician": "",
                    "repair_details": "",
                    "parts_used": "",
                    "labor_cost": 0.0,
                    "parts_cost": 0.0,
                    "total_cost": 0.0,
                }
            ]
        )

        df = self._read_df(raw=True)
        if df is None or df.empty:
            updated_df = new_order
        else:
            # avem deja date → le păstrăm și adăugăm doar rândul nou
            updated_df = pd.concat([df, new_order], ignore_index=True)

        if self._write_df(updated_df):
            self.next_order_id += 1
            return order_id
        return None

    def list_orders_df(self) -> pd.DataFrame:
        df = self._read_df()
        return df if df is not None else pd.DataFrame()

    def get_order(self, order_id: str):
        df = self._read_df()
        if df is None or df.empty or "order_id" not in df.columns:
            return None
        row = df[df["order_id"] == order_id]
        if row.empty:
            return None
        return row.iloc[0].to_dict()

    def update_order(self, order_id: str, **kwargs) -> bool:
        """
        Citește foaia completă, modifică DOAR rândul cu order_id, apoi rescrie tot df-ul.
        NU permite scrierea unui df gol, deci nu poate șterge toată baza de date.
        """
        df = self._read_df(raw=True)
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

        # recalcul total
        if "labor_cost" in df.columns and "parts_cost" in df.columns:
            labor = pd.to_numeric(df.loc[mask, "labor_cost"], errors="coerce").fillna(0)
            parts = pd.to_numeric(df.loc[mask, "parts_cost"], errors="coerce").fillna(0)
            df.loc[mask, "total_cost"] = labor + parts

        return self._write_df(df)



# -------------------------------------------------------------------
# MAIN APP
# -------------------------------------------------------------------
def main():
    if not check_password():
        st.stop()

    st.title("🖨️ Printer Service CRM")
    st.markdown("### Professional Printer Service Management System")

    # Session defaults
    if "company_info" not in st.session_state:
        st.session_state["company_info"] = {
            "company_name": "Print Service Pro SRL",
            "company_address": "Str. Industriei Nr. 45, Cluj-Napoca",
            "cui": "RO98765432",
            "reg_com": "J12/5678/2024",
            "phone": "+40 364 123 456",
            "email": "service@printservicepro.ro",
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

        # Logo
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

        # Company details
        with st.expander("🏢 Company Details", expanded=False):
            ci = st.session_state["company_info"]
            ci["company_name"] = st.text_input(
                "Company Name", value=ci["company_name"], key="company_name_input"
            )
            ci["company_address"] = st.text_input(
                "Address", value=ci["company_address"], key="company_address_input"
            )
            ci["cui"] = st.text_input("CUI", value=ci["cui"], key="company_cui_input")
            ci["reg_com"] = st.text_input(
                "Reg.Com", value=ci["reg_com"], key="company_regcom_input"
            )
            ci["phone"] = st.text_input(
                "Phone", value=ci["phone"], key="company_phone_input"
            )
            ci["email"] = st.text_input(
                "Email", value=ci["email"], key="company_email_input"
            )

        # Sheets status
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

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📥 New Order", "📋 All Orders", "✏️ Update Order", "📊 Reports"]
    )

    # TAB 1: NEW ORDER
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
                date_pickup = st.date_input(
                    "Scheduled Pickup (optional)", value=None
                )

            issue_description = st.text_area("Issue Description *", height=100)
            accessories = st.text_input("Accessories (cables, cartridges, etc.)")
            notes = st.text_area("Additional Notes", height=60)

            submit = st.form_submit_button(
                "🎫 Create Order", type="primary", use_container_width=True
            )

            if submit:
                if (
                    client_name
                    and client_phone
                    and printer_brand
                    and printer_model
                    and issue_description
                ):
                    order_id = crm.create_service_order(
                        client_name,
                        client_phone,
                        client_email,
                        printer_brand,
                        printer_model,
                        printer_serial,
                        issue_description,
                        accessories,
                        notes,
                        date_received,
                        date_pickup,
                    )
                    if order_id:
                        st.session_state["last_created_order"] = order_id
                        st.success(f"✅ Order Created: **{order_id}**")
                        st.balloons()
                        crm = st.session_state["crm"]
                        # Citește o singură dată toate comenzile
                        df_all = crm.list_orders_df()

                else:
                    st.error("❌ Please fill in all required fields (*)")

        if st.session_state["last_created_order"]:
            order = crm.get_order(st.session_state["last_created_order"])
            if order:
                st.divider()
                st.subheader("📄 Download Receipt")
                logo = st.session_state.get("logo_image", None)
                pdf_buffer = generate_initial_receipt_pdf(
                    order, st.session_state["company_info"], logo
                )
                st.download_button(
                    "📄 Download Initial Receipt",
                    pdf_buffer,
                    f"Initial_{order['order_id']}.pdf",
                    "application/pdf",
                    type="secondary",
                    use_container_width=True,
                    key="dl_new_init",
                )

                if st.button(
                    "✅ Done", use_container_width=True, key="done_new_order"
                ):
                    st.session_state["last_created_order"] = None
                    st.rerun()

    # TAB 2: ALL ORDERS
    with tab2:
        st.header("All Service Orders")
        df = crm.list_orders_df()
        if not df.empty:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📊 Total Orders", len(df))
            col2.metric("📥 Received", len(df[df["status"] == "Received"]))
            col3.metric(
                "✅ Ready", len(df[df["status"] == "Ready for Pickup"])
            )
            col4.metric("🎉 Completed", len(df[df["status"] == "Completed"]))

            st.dataframe(
                df[
                    [
                        "order_id",
                        "client_name",
                        "printer_brand",
                        "date_received",
                        "status",
                        "total_cost",
                    ]
                ],
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
            st.info(
                "📝 No orders yet. Create your first order in the 'New Order' tab!"
            )

    # TAB 3: UPDATE ORDER
with tab3:
    st.header("Update Service Order")
    df = crm.list_orders_df()
    if not df.empty:
        # selectăm comanda, dar FĂRĂ să forțăm index care poate da eroare
        selected_order_id = st.selectbox(
            "Select Order to Update",
            df["order_id"].tolist(),
            key="update_order_select",
        )

        if selected_order_id:
            order = crm.get_order(selected_order_id)
            if order:
                # --------- info de sus ----------
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Client:** {safe_text(order.get('client_name'))}")
                    st.write(f"**Phone:** {safe_text(order.get('client_phone'))}")
                with col2:
                    st.write(
                        f"**Printer:** {safe_text(order.get('printer_brand'))} {safe_text(order.get('printer_model'))}"
                    )
                    st.write(f"**Received:** {safe_text(order.get('date_received'))}")

                st.divider()

                # --------- status & dates ----------
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

                # --------- text fields (fără 'nan') ----------
                st.subheader("Repair Details")
                repair_details = st.text_area(
                    "Repairs Performed",
                    value=safe_text(order.get("repair_details")),
                    height=100,
                    key="update_repair_details",
                )
                parts_used = st.text_input(
                    "Parts Used",
                    value=safe_text(order.get("parts_used")),
                    key="update_parts_used",
                )
                technician = st.text_input(
                    "Technician",
                    value=safe_text(order.get("technician")),
                    key="update_technician",
                )

                # --------- costs ----------
                colc1, colc2, colc3 = st.columns(3)
                labor_cost = colc1.number_input(
                    "Labor Cost (RON)",
                    value=safe_float(order.get("labor_cost")),
                    min_value=0.0,
                    step=10.0,
                    key="update_labor_cost",
                )
                parts_cost = colc2.number_input(
                    "Parts Cost (RON)",
                    value=safe_float(order.get("parts_cost")),
                    min_value=0.0,
                    step=10.0,
                    key="update_parts_cost",
                )
                colc3.metric("💰 Total Cost", f"{labor_cost + parts_cost:.2f} RON")

                # --------- buton update ----------
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

                        # curățăm câmpurile text după update
                        st.session_state["update_repair_details"] = ""
                        st.session_state["update_parts_used"] = ""
                        st.session_state["update_technician"] = ""

                        # opțional, poți reselecta nimic
                        # st.session_state["update_order_select"] = ""

                        st.rerun()

                # --------- PDF-uri ----------
                st.divider()
                st.subheader("📄 Download Receipts")
                logo = st.session_state.get("logo_image", None)
                colp1, colp2 = st.columns(2)
                with colp1:
                    st.markdown("**Initial Receipt**")
                    pdf_init = generate_initial_receipt_pdf(
                        order, st.session_state["company_info"], logo
                    )
                    st.download_button(
                        "📄 Download Initial Receipt",
                        pdf_init,
                        f"Initial_{order['order_id']}.pdf",
                        "application/pdf",
                        use_container_width=True,
                        key=f"dl_upd_init_{order['order_id']}",
                    )
                with colp2:
                    st.markdown("**Completion Receipt**")
                    pdf_comp = generate_completion_receipt_pdf(
                        order, st.session_state["company_info"], logo
                    )
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


    # TAB 4: REPORTS
    with tab4:
        st.header("Reports & Analytics")
        df = crm.list_orders_df()
        if not df.empty:
            col1, col2, col3 = st.columns(3)
            col1.metric("💰 Total Revenue", f"{df['total_cost'].sum():.2f} RON")
            avg_cost = (
                df[df["total_cost"] > 0]["total_cost"].mean()
                if len(df[df["total_cost"] > 0]) > 0
                else 0
            )
            col2.metric("📊 Average Cost", f"{avg_cost:.2f} RON")
            col3.metric("👥 Unique Clients", df["client_name"].nunique())

            st.divider()
            st.subheader("Orders by Status")
            st.bar_chart(df["status"].value_counts())
        else:
            st.info("📝 No data yet. Create orders to see reports!")


if __name__ == "__main__":
    main()
