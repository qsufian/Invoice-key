from fastapi import FastAPI, HTTPException, File, UploadFile, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from pymongo import MongoClient
import os
import uuid
from enum import Enum
import io
import base64
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.graphics.shapes import Drawing, Line
from reportlab.graphics import renderPDF
from reportlab.platypus.flowables import HRFlowable
import json
from decimal import Decimal, ROUND_HALF_UP

# Initialize FastAPI app
app = FastAPI(title="Invoice Management System", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URL)
db = client.invoice_management

# Collections
customers_collection = db.customers
invoices_collection = db.invoices
company_settings_collection = db.company_settings
payments_collection = db.payments

# Enums
class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    FAILED = "failed"

# Models
class Customer(BaseModel):
    customer_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None
    tax_number: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class LineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    tax_rate: Optional[float] = 0.0
    total: Optional[float] = None

class Invoice(BaseModel):
    invoice_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    invoice_number: str
    customer_id: str
    issue_date: date
    due_date: date
    status: InvoiceStatus = InvoiceStatus.DRAFT
    line_items: List[LineItem]
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    notes: Optional[str] = None
    terms: Optional[str] = None
    payment_status: PaymentStatus = PaymentStatus.PENDING
    amount_paid: Optional[float] = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CompanySettings(BaseModel):
    company_name: str
    address: str
    city: str
    state: str
    zip_code: str
    country: str
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    tax_number: Optional[str] = None
    logo: Optional[str] = None  # Base64 encoded logo
    default_tax_rate: Optional[float] = 0.0
    default_payment_terms: Optional[str] = "Net 30"
    currency: Optional[str] = "USD"
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Payment(BaseModel):
    payment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    invoice_id: str
    amount: float
    payment_date: date
    payment_method: str
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class DashboardStats(BaseModel):
    total_customers: int
    total_invoices: int
    total_revenue: float
    pending_amount: float
    overdue_amount: float
    paid_amount: float
    draft_count: int
    sent_count: int
    paid_count: int
    overdue_count: int

# Utility functions
def calculate_line_item_total(item: LineItem) -> float:
    subtotal = item.quantity * item.unit_price
    tax_amount = subtotal * (item.tax_rate / 100) if item.tax_rate else 0
    return round(subtotal + tax_amount, 2)

def calculate_invoice_totals(invoice: Invoice) -> Dict[str, float]:
    subtotal = 0
    tax_amount = 0
    
    for item in invoice.line_items:
        item_subtotal = item.quantity * item.unit_price
        item_tax = item_subtotal * (item.tax_rate / 100) if item.tax_rate else 0
        
        subtotal += item_subtotal
        tax_amount += item_tax
        item.total = round(item_subtotal + item_tax, 2)
    
    total_amount = subtotal + tax_amount
    
    return {
        "subtotal": round(subtotal, 2),
        "tax_amount": round(tax_amount, 2),
        "total_amount": round(total_amount, 2)
    }

def generate_invoice_number() -> str:
    # Generate invoice number based on timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"INV-{timestamp}"

def create_invoice_pdf(invoice_data: dict, customer_data: dict, company_data: dict) -> bytes:
    """Generate PDF invoice"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.HexColor('#2563eb'),
        alignment=TA_CENTER
    )
    
    # Add company info and logo
    company_info = []
    if company_data.get('logo'):
        try:
            logo_data = base64.b64decode(company_data['logo'].split(',')[1])
            logo = Image(io.BytesIO(logo_data), width=100, height=50)
            company_info.append([logo, ''])
        except:
            pass
    
    company_text = f"""
    <b>{company_data.get('company_name', 'Your Company')}</b><br/>
    {company_data.get('address', '')}<br/>
    {company_data.get('city', '')}, {company_data.get('state', '')} {company_data.get('zip_code', '')}<br/>
    {company_data.get('country', '')}<br/>
    Phone: {company_data.get('phone', '')}<br/>
    Email: {company_data.get('email', '')}
    """
    
    company_info.append([Paragraph(company_text, styles['Normal']), ''])
    
    company_table = Table(company_info, colWidths=[3*inch, 3*inch])
    company_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    elements.append(company_table)
    elements.append(Spacer(1, 20))
    
    # Invoice title
    elements.append(Paragraph("INVOICE", title_style))
    elements.append(Spacer(1, 20))
    
    # Invoice and customer info
    invoice_info_data = [
        ['Invoice Number:', invoice_data.get('invoice_number', '')],
        ['Invoice Date:', invoice_data.get('issue_date', '')],
        ['Due Date:', invoice_data.get('due_date', '')],
        ['Status:', invoice_data.get('status', '').upper()],
    ]
    
    customer_info_data = [
        ['Bill To:', ''],
        [customer_data.get('name', ''), ''],
        [customer_data.get('company', ''), ''],
        [customer_data.get('address', ''), ''],
        [f"{customer_data.get('city', '')}, {customer_data.get('state', '')} {customer_data.get('zip_code', '')}", ''],
        [customer_data.get('email', ''), ''],
    ]
    
    # Create two-column layout for invoice and customer info
    info_data = []
    max_rows = max(len(invoice_info_data), len(customer_info_data))
    
    for i in range(max_rows):
        invoice_cell = invoice_info_data[i] if i < len(invoice_info_data) else ['', '']
        customer_cell = customer_info_data[i] if i < len(customer_info_data) else ['', '']
        info_data.append([invoice_cell[0], invoice_cell[1], customer_cell[0], customer_cell[1]])
    
    info_table = Table(info_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 30))
    
    # Line items table
    line_items_data = [['Description', 'Quantity', 'Unit Price', 'Tax Rate', 'Total']]
    
    for item in invoice_data.get('line_items', []):
        line_items_data.append([
            item['description'],
            str(item['quantity']),
            f"${item['unit_price']:.2f}",
            f"{item.get('tax_rate', 0)}%",
            f"${item.get('total', 0):.2f}"
        ])
    
    line_items_table = Table(line_items_data, colWidths=[3*inch, 1*inch, 1*inch, 1*inch, 1*inch])
    line_items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(line_items_table)
    elements.append(Spacer(1, 20))
    
    # Totals
    totals_data = [
        ['Subtotal:', f"${invoice_data.get('subtotal', 0):.2f}"],
        ['Tax Amount:', f"${invoice_data.get('tax_amount', 0):.2f}"],
        ['Total Amount:', f"${invoice_data.get('total_amount', 0):.2f}"],
    ]
    
    totals_table = Table(totals_data, colWidths=[4*inch, 2*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.HexColor('#2563eb')),
        ('LINEBELOW', (0, -1), (-1, -1), 2, colors.HexColor('#2563eb')),
    ]))
    
    elements.append(totals_table)
    elements.append(Spacer(1, 30))
    
    # Notes and terms
    if invoice_data.get('notes'):
        elements.append(Paragraph(f"<b>Notes:</b> {invoice_data['notes']}", styles['Normal']))
        elements.append(Spacer(1, 10))
    
    if invoice_data.get('terms'):
        elements.append(Paragraph(f"<b>Terms:</b> {invoice_data['terms']}", styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# API Routes

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "message": "Invoice Management System is running"}

# Company Settings Routes
@app.get("/api/company-settings")
async def get_company_settings():
    settings = company_settings_collection.find_one()
    if not settings:
        # Return default settings
        return {
            "company_name": "",
            "address": "",
            "city": "",
            "state": "",
            "zip_code": "",
            "country": "",
            "phone": "",
            "email": "",
            "website": "",
            "tax_number": "",
            "logo": "",
            "default_tax_rate": 0.0,
            "default_payment_terms": "Net 30",
            "currency": "USD"
        }
    
    settings.pop('_id', None)
    return settings

@app.post("/api/company-settings")
async def update_company_settings(settings: CompanySettings):
    settings_dict = settings.dict()
    company_settings_collection.replace_one({}, settings_dict, upsert=True)
    return {"message": "Company settings updated successfully"}

# Customer Routes
@app.get("/api/customers")
async def get_customers():
    customers = list(customers_collection.find({}, {"_id": 0}))
    return customers

@app.post("/api/customers")
async def create_customer(customer: Customer):
    customer_dict = customer.dict()
    customers_collection.insert_one(customer_dict)
    return {"message": "Customer created successfully", "customer_id": customer.customer_id}

@app.get("/api/customers/{customer_id}")
async def get_customer(customer_id: str):
    customer = customers_collection.find_one({"customer_id": customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@app.put("/api/customers/{customer_id}")
async def update_customer(customer_id: str, customer: Customer):
    customer.updated_at = datetime.utcnow()
    customer_dict = customer.dict()
    result = customers_collection.update_one(
        {"customer_id": customer_id},
        {"$set": customer_dict}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"message": "Customer updated successfully"}

@app.delete("/api/customers/{customer_id}")
async def delete_customer(customer_id: str):
    result = customers_collection.delete_one({"customer_id": customer_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"message": "Customer deleted successfully"}

# Invoice Routes
@app.get("/api/invoices")
async def get_invoices():
    invoices = list(invoices_collection.find({}, {"_id": 0}))
    
    # Add customer info to each invoice
    for invoice in invoices:
        customer = customers_collection.find_one({"customer_id": invoice["customer_id"]}, {"_id": 0})
        invoice["customer_name"] = customer["name"] if customer else "Unknown Customer"
    
    return invoices

@app.post("/api/invoices")
async def create_invoice(invoice: Invoice):
    # Generate invoice number if not provided
    if not invoice.invoice_number:
        invoice.invoice_number = generate_invoice_number()
    
    # Calculate totals
    totals = calculate_invoice_totals(invoice)
    invoice.subtotal = totals["subtotal"]
    invoice.tax_amount = totals["tax_amount"]
    invoice.total_amount = totals["total_amount"]
    
    invoice_dict = invoice.dict()
    invoices_collection.insert_one(invoice_dict)
    return {"message": "Invoice created successfully", "invoice_id": invoice.invoice_id}

@app.get("/api/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    invoice = invoices_collection.find_one({"invoice_id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Add customer info
    customer = customers_collection.find_one({"customer_id": invoice["customer_id"]}, {"_id": 0})
    invoice["customer"] = customer if customer else None
    
    return invoice

@app.put("/api/invoices/{invoice_id}")
async def update_invoice(invoice_id: str, invoice: Invoice):
    # Calculate totals
    totals = calculate_invoice_totals(invoice)
    invoice.subtotal = totals["subtotal"]
    invoice.tax_amount = totals["tax_amount"]
    invoice.total_amount = totals["total_amount"]
    invoice.updated_at = datetime.utcnow()
    
    invoice_dict = invoice.dict()
    result = invoices_collection.update_one(
        {"invoice_id": invoice_id},
        {"$set": invoice_dict}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"message": "Invoice updated successfully"}

@app.delete("/api/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str):
    result = invoices_collection.delete_one({"invoice_id": invoice_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"message": "Invoice deleted successfully"}

@app.put("/api/invoices/{invoice_id}/status")
async def update_invoice_status(invoice_id: str, status_data: dict):
    result = invoices_collection.update_one(
        {"invoice_id": invoice_id},
        {"$set": {"status": status_data["status"], "updated_at": datetime.utcnow()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"message": "Invoice status updated successfully"}

# PDF Generation Route
@app.get("/api/invoices/{invoice_id}/pdf")
async def generate_invoice_pdf_endpoint(invoice_id: str):
    # Get invoice data
    invoice = invoices_collection.find_one({"invoice_id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Get customer data
    customer = customers_collection.find_one({"customer_id": invoice["customer_id"]}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Get company settings
    company_settings = company_settings_collection.find_one({}, {"_id": 0})
    if not company_settings:
        company_settings = {
            "company_name": "Your Company",
            "address": "",
            "city": "",
            "state": "",
            "zip_code": "",
            "country": "",
            "phone": "",
            "email": "",
        }
    
    # Convert dates to strings for PDF
    invoice["issue_date"] = str(invoice["issue_date"])
    invoice["due_date"] = str(invoice["due_date"])
    
    # Generate PDF
    pdf_bytes = create_invoice_pdf(invoice, customer, company_settings)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=invoice_{invoice['invoice_number']}.pdf"}
    )

# Payment Routes
@app.post("/api/payments")
async def create_payment(payment: Payment):
    payment_dict = payment.dict()
    payments_collection.insert_one(payment_dict)
    
    # Update invoice payment status
    invoice = invoices_collection.find_one({"invoice_id": payment.invoice_id})
    if invoice:
        total_paid = invoice.get("amount_paid", 0) + payment.amount
        payment_status = PaymentStatus.PAID if total_paid >= invoice["total_amount"] else PaymentStatus.PARTIAL
        
        invoices_collection.update_one(
            {"invoice_id": payment.invoice_id},
            {"$set": {"amount_paid": total_paid, "payment_status": payment_status, "updated_at": datetime.utcnow()}}
        )
    
    return {"message": "Payment recorded successfully", "payment_id": payment.payment_id}

@app.get("/api/payments/invoice/{invoice_id}")
async def get_payments_for_invoice(invoice_id: str):
    payments = list(payments_collection.find({"invoice_id": invoice_id}, {"_id": 0}))
    return payments

# Dashboard and Analytics Routes
@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    # Get counts
    total_customers = customers_collection.count_documents({})
    total_invoices = invoices_collection.count_documents({})
    
    # Get invoice status counts
    draft_count = invoices_collection.count_documents({"status": "draft"})
    sent_count = invoices_collection.count_documents({"status": "sent"})
    paid_count = invoices_collection.count_documents({"status": "paid"})
    overdue_count = invoices_collection.count_documents({"status": "overdue"})
    
    # Calculate revenue amounts
    paid_invoices = list(invoices_collection.find({"status": "paid"}, {"total_amount": 1}))
    paid_amount = sum(invoice.get("total_amount", 0) for invoice in paid_invoices)
    
    pending_invoices = list(invoices_collection.find({"status": "sent"}, {"total_amount": 1}))
    pending_amount = sum(invoice.get("total_amount", 0) for invoice in pending_invoices)
    
    overdue_invoices = list(invoices_collection.find({"status": "overdue"}, {"total_amount": 1}))
    overdue_amount = sum(invoice.get("total_amount", 0) for invoice in overdue_invoices)
    
    total_revenue = paid_amount + pending_amount + overdue_amount
    
    return DashboardStats(
        total_customers=total_customers,
        total_invoices=total_invoices,
        total_revenue=total_revenue,
        pending_amount=pending_amount,
        overdue_amount=overdue_amount,
        paid_amount=paid_amount,
        draft_count=draft_count,
        sent_count=sent_count,
        paid_count=paid_count,
        overdue_count=overdue_count
    )

@app.get("/api/dashboard/recent-invoices")
async def get_recent_invoices():
    invoices = list(invoices_collection.find({}, {"_id": 0}).sort("created_at", -1).limit(10))
    
    # Add customer info to each invoice
    for invoice in invoices:
        customer = customers_collection.find_one({"customer_id": invoice["customer_id"]}, {"_id": 0})
        invoice["customer_name"] = customer["name"] if customer else "Unknown Customer"
    
    return invoices

# Search Routes
@app.get("/api/search/customers")
async def search_customers(q: str = ""):
    if not q:
        return []
    
    customers = list(customers_collection.find(
        {"$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
            {"company": {"$regex": q, "$options": "i"}}
        ]},
        {"_id": 0}
    ).limit(10))
    
    return customers

@app.get("/api/search/invoices")
async def search_invoices(q: str = ""):
    if not q:
        return []
    
    invoices = list(invoices_collection.find(
        {"$or": [
            {"invoice_number": {"$regex": q, "$options": "i"}},
            {"notes": {"$regex": q, "$options": "i"}}
        ]},
        {"_id": 0}
    ).limit(10))
    
    # Add customer info to each invoice
    for invoice in invoices:
        customer = customers_collection.find_one({"customer_id": invoice["customer_id"]}, {"_id": 0})
        invoice["customer_name"] = customer["name"] if customer else "Unknown Customer"
    
    return invoices

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)