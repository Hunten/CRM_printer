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


# -------------------------------------------------------------------
# APP CONFIG
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Printer Service CRM",
    page_icon="🖨️",
    layout="wide"
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

    st.markdown("## 🔒 Autentificare necesară")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Parolă", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            try:
                correct_password = st.secrets["passwords"]["admin_password"]
            except KeyError:
                st.error("❌ Nu ai setat `passwords.admin_password` în Secrets.")
                return False

            if username == "admin" and hash_password(password) == hash_password(
                correct_password
            ):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.success("✅ Login reușit!")
                st.rerun()
            else:
                st.error("❌ Username sau parolă greșite.")
    return False


# -------------------------------------------------------------------
# UTILS
# -------------------------------------------------------------------
def remove_diacritics(text):
    if not isinstance(text, str):
        return text
    mapping = {
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
    for d, r in mapping.items():
        text = text.replace(d, r)
    return text


# -------------------------------------------------------------------
# GOOGLE SHEETS CONNECTION (st.connection)
# -------------------------------------------------------------------
@st.cache_resource
def get_sheets_connection():
    """
    Conexiune nativă Streamlit către Google Sheets.

    Necesită în `secrets.toml`:

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
        st.error(f"Eroare conexiune Google Sheets: {e}")
        return None


# -------------------------------------------------------------------
# PDF GENERATION
# -------------------------------------------------------------------
def generate_initial_receipt_pdf(order, company_info, logo_image=None):
    buffer = io.BytesIO()
    width, height = 210 * mm, 148.5 * mm
    c = canvas.Canvas(buffer, pagesize=(width, height))

    # LOGO
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

    # COMPANY INFO
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

    # TITLU
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(105 * mm, height - 55 * mm, "BON PREDARE ECHIPAMENT")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#0066cc"))
    c.drawCentredString(
        105 * mm, height - 62 * mm, f"Nr. Comandă: {order['order_id']}"
    )
    c.setFillColor(colors.black)

    # DETALII
    y_pos = height - 72 * mm
    c.setFont("Helvetica", 8)
    c.drawString(10 * mm, y_pos, f"Client: {remove_diacritics(order['client_name'])}")
    y_pos -= 4 * mm
    c.drawString(10 * mm, y_pos, f"Telefon: {order['client_phone']}")
    y_pos -= 4 * mm
    c.drawString(
        10 * mm,
        y_pos,
        f"Imprimantă: {remove_diacritics(order['printer_brand'])} {remove_diacritics(order['printer_model'])}",
    )
    y_pos -= 4 * mm
    c.drawString(10 * mm, y_pos, f"Data predării: {order['date_received']}")

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
        f"Total: {float(order.get('total_cost', 0)):.2f} RON",
    )

    c.save()
    buffer.seek(0)
    return buffer


# -------------------------------------------------------------------
# CRM CLASS (GOOGLE SHEETS)
# -------------------------------------------------------------------
class PrinterServiceCRM:
    def __init__(self, conn: GSheetsConnection):
        self.conn = conn
        self.worksheet = "Orders"
        self.next_order_id = 1
        self._init_sheet()

    def _init_sheet(self):
        """Asigură existența headerelor și calculează next_order_id."""
        try:
            df = self.conn.read(worksheet=self.worksheet, ttl=0)
        except Exception:
            df = pd.DataFrame()

        if df.empty:
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
            self.conn.update(worksheet=self.worksheet, data=df)
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

    def _read_df(self) -> pd.DataFrame:
        try:
            df = self.conn.read(worksheet=self.worksheet, ttl=0)
            return df if not df.empty else pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def _write_df(self, df: pd.DataFrame) -> bool:
        try:
            self.conn.update(worksheet=self.worksheet, data=df)
            return True
        except Exception as e:
            st.sidebar.error(f"Eroare salvare în Sheets: {e}")
            return False

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

        new_row = {
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
            else "",
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

        df = self._read_df()
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        if self._write_df(df):
            self.next_order_id += 1
            return order_id
        return None

    def list_orders_df(self) -> pd.DataFrame:
        df = self._read_df()
        # conversie numerică
        for col in ["labor_cost", "parts_cost", "total_cost"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        return df

    def get_order(self, order_id: str):
        df = self._read_df()
        if df.empty:
            return None
        row = df[df["order_id"] == order_id]
        if row.empty:
            return None
        rec = row.iloc[0].to_dict()
        return rec

    def update_order(self, order_id: str, **kwargs) -> bool:
        df = self._read_df()
        if df.empty:
            return False
        mask = df["order_id"] == order_id
        if not mask.any():
            return False

        for key, val in kwargs.items():
            if key in df.columns:
                df.loc[mask, key] = val

        # recalcul total
        if "labor_cost" in df.columns and "parts_cost" in df.columns:
            df.loc[mask, "total_cost"] = (
                pd.to_numeric(df.loc[mask, "labor_cost"], errors="coerce").fillna(0)
                + pd.to_numeric(df.loc[mask, "parts_cost"], errors="coerce").fillna(0)
            )

        return self._write_df(df)


# -------------------------------------------------------------------
# MAIN APP
# -------------------------------------------------------------------
def main():
    if not check_password():
        st.stop()

    st.title("🖨️ Printer Service CRM")

    # SESSION STATE DEFAULTS
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

    # SIDEBAR
    with st.sidebar:
        st.header("⚙️ Setări")
        st.success(f"👤 {st.session_state.get('username', 'User')}")
        if st.button("🚪 Logout"):
            st.session_state["authenticated"] = False
            st.rerun()
        st.divider()

        with st.expander("🖼️ Logo", expanded=False):
            logo_file = st.file_uploader(
                "Încarcă logo", type=["png", "jpg", "jpeg"], key="logo_uploader"
            )
            if logo_file:
                st.session_state["logo_image"] = logo_file
                st.image(logo_file, width=150)

        with st.expander("🏢 Date firmă", expanded=False):
            ci = st.session_state["company_info"]
            ci["company_name"] = st.text_input(
                "Denumire firmă", value=ci["company_name"]
            )
            ci["company_address"] = st.text_input(
                "Adresă", value=ci["company_address"]
            )
            ci["cui"] = st.text_input("CUI", value=ci["cui"])
            ci["reg_com"] = st.text_input("Reg. Com.", value=ci["reg_com"])
            ci["phone"] = st.text_input("Telefon", value=ci["phone"])
            ci["email"] = st.text_input("Email", value=ci["email"])

        # connection status
        conn = get_sheets_connection()
        if conn:
            st.success("✅ Connected to Google Sheets")
        else:
            st.error("❌ Nu mă pot conecta la Google Sheets")

    conn = get_sheets_connection()
    if not conn:
        st.error("Fără conexiune la Google Sheets, app-ul nu poate funcționa.")
        st.stop()

    if "crm" not in st.session_state:
        st.session_state["crm"] = PrinterServiceCRM(conn)

    crm = st.session_state["crm"]

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📥 Comandă nouă", "📋 Toate comenzi", "✏️ Update comandă", "📊 Rapoarte"]
    )

    # TAB 1 - NEW ORDER
    with tab1:
        st.header("Creează comandă nouă")

        with st.form("new_order_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                client_name = st.text_input("Nume client *")
                client_phone = st.text_input("Telefon *")
                client_email = st.text_input("Email")
            with col2:
                printer_brand = st.text_input("Brand imprimantă *")
                printer_model = st.text_input("Model *")
                printer_serial = st.text_input("Serie")

            col3, col4 = st.columns(2)
            with col3:
                date_received = st.date_input("Data primirii *", value=date.today())
            with col4:
                date_pickup = st.date_input(
                    "Data estimată ridicare (opțional)", value=None
                )

            issue_description = st.text_area("Descriere problemă *")
            accessories = st.text_input("Accesorii (cablu, toner, etc.)")
            notes = st.text_area("Note interne")

            submit = st.form_submit_button("✅ Creează comandă")

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
                        st.success(f"Comanda {order_id} a fost creată.")
                        st.balloons()
                else:
                    st.error("Te rog completează toate câmpurile marcate cu *.")

        if st.session_state["last_created_order"]:
            order = crm.get_order(st.session_state["last_created_order"])
            if order:
                st.subheader("📄 Bon predare")
                pdf_buf = generate_initial_receipt_pdf(
                    order,
                    st.session_state["company_info"],
                    st.session_state["logo_image"],
                )
                st.download_button(
                    "📄 Descarcă bon predare",
                    data=pdf_buf,
                    file_name=f"bon_predare_{order['order_id']}.pdf",
                    mime="application/pdf",
                )

    # TAB 2 - ALL ORDERS
    with tab2:
        st.header("Toate comenzile")
        df = crm.list_orders_df()
        if not df.empty:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total comenzi", len(df))
            col2.metric("În lucru / primite", len(df[df["status"] != "Completed"]))
            col3.metric("Finalizate", len(df[df["status"] == "Completed"]))

            st.dataframe(
                df[
                    [
                        "order_id",
                        "client_name",
                        "printer_brand",
                        "printer_model",
                        "status",
                        "total_cost",
                    ]
                ],
                use_container_width=True,
            )

            # backup download
            csv_data = df.to_csv(index=False)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                "💾 Descarcă backup (CSV)",
                data=csv_data,
                file_name=f"crm_backup_{ts}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.info("Nu există comenzi încă.")

    # TAB 3 - UPDATE ORDER
    with tab3:
        st.header("Update comandă")
        df = crm.list_orders_df()
        if not df.empty:
            order_id = st.selectbox("Alege comandă", df["order_id"].tolist())
            if order_id:
                order = crm.get_order(order_id)
                if order:
                    st.subheader(f"Comanda {order_id}")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"Client: **{order['client_name']}**")
                        st.write(
                            f"Imprimantă: {order['printer_brand']} {order['printer_model']}"
                        )
                    with col2:
                        st.write(f"Stare actuală: {order['status']}")
                        st.write(f"Primire: {order['date_received']}")

                    new_status = st.selectbox(
                        "Status",
                        ["Received", "In Progress", "Ready for Pickup", "Completed"],
                        index=[
                            "Received",
                            "In Progress",
                            "Ready for Pickup",
                            "Completed",
                        ].index(order["status"]
                                if order["status"] in
                                ["Received", "In Progress", "Ready for Pickup", "Completed"]
                                else "Received"),
                    )
                    technician = st.text_input(
                        "Tehnician", value=order.get("technician", "")
                    )
                    repair_details = st.text_area(
                        "Detalii reparație",
                        value=order.get("repair_details", ""),
                        height=80,
                    )
                    parts_used = st.text_input(
                        "Piese folosite", value=order.get("parts_used", "")
                    )

                    colc1, colc2, colc3 = st.columns(3)
                    with colc1:
                        labor_cost = st.number_input(
                            "Manoperă (RON)",
                            value=float(order.get("labor_cost", 0) or 0),
                            min_value=0.0,
                            step=10.0,
                        )
                    with colc2:
                        parts_cost = st.number_input(
                            "Cost piese (RON)",
                            value=float(order.get("parts_cost", 0) or 0),
                            min_value=0.0,
                            step=10.0,
                        )
                    with colc3:
                        total_preview = labor_cost + parts_cost
                        st.metric("Total", f"{total_preview:.2f} RON")

                    if st.button("💾 Salvează modificările"):
                        updates = {
                            "status": new_status,
                            "technician": technician,
                            "repair_details": repair_details,
                            "parts_used": parts_used,
                            "labor_cost": labor_cost,
                            "parts_cost": parts_cost,
                        }
                        if new_status == "Ready for Pickup" and not order.get(
                            "date_completed"
                        ):
                            updates["date_completed"] = datetime.now().strftime(
                                "%Y-%m-%d"
                            )
                        if new_status == "Completed" and not order.get(
                            "date_picked_up"
                        ):
                            updates["date_picked_up"] = datetime.now().strftime(
                                "%Y-%m-%d"
                            )

                        if crm.update_order(order_id, **updates):
                            st.success("Comanda a fost actualizată.")
                            st.rerun()

                    st.subheader("📄 PDF-uri")
                    colp1, colp2 = st.columns(2)
                    with colp1:
                        init_pdf = generate_initial_receipt_pdf(
                            order,
                            st.session_state["company_info"],
                            st.session_state["logo_image"],
                        )
                        st.download_button(
                            "📄 Bon predare",
                            data=init_pdf,
                            file_name=f"bon_predare_{order_id}.pdf",
                            mime="application/pdf",
                        )
                    with colp2:
                        compl_pdf = generate_completion_receipt_pdf(
                            order,
                            st.session_state["company_info"],
                            st.session_state["logo_image"],
                        )
                        st.download_button(
                            "📄 Bon finalizare",
                            data=compl_pdf,
                            file_name=f"bon_final_{order_id}.pdf",
                            mime="application/pdf",
                        )
        else:
            st.info("Nu există comenzi pentru update.")

    # TAB 4 - REPORTS
    with tab4:
        st.header("Rapoarte")
        df = crm.list_orders_df()
        if not df.empty:
            total_rev = df["total_cost"].sum()
            col1, col2, col3 = st.columns(3)
            col1.metric("Total venit", f"{total_rev:.2f} RON")
            col2.metric(
                "Comenzi finalizate", len(df[df["status"] == "Completed"])
            )
            col3.metric("Clienți unici", df["client_name"].nunique())
        else:
            st.info("Nu există date pentru rapoarte.")


if __name__ == "__main__":
    main()
