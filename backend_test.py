#!/usr/bin/env python3
"""
Backend API Testing Suite for Invoice Management System
Tests all critical backend functionality including CRUD operations, PDF generation, and analytics.
"""

import requests
import json
import uuid
from datetime import datetime, date, timedelta
import base64
import os

# Configuration
BASE_URL = "https://8b5d5864-2114-4009-bb61-0b5d03704856.preview.emergentagent.com/api"
TIMEOUT = 30

class InvoiceBackendTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.test_customer_id = None
        self.test_invoice_id = None
        self.test_results = {}
        
    def log_test(self, test_name, success, message="", data=None):
        """Log test results"""
        self.test_results[test_name] = {
            "success": success,
            "message": message,
            "data": data
        }
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        
    def make_request(self, method, endpoint, data=None, files=None):
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        try:
            if method.upper() == "GET":
                response = self.session.get(url, timeout=TIMEOUT)
            elif method.upper() == "POST":
                if files:
                    response = self.session.post(url, data=data, files=files, timeout=TIMEOUT)
                else:
                    response = self.session.post(url, json=data, timeout=TIMEOUT)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, timeout=TIMEOUT)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, timeout=TIMEOUT)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            return response
        except requests.exceptions.RequestException as e:
            print(f"Request failed for {method} {url}: {str(e)}")
            return None
    
    def test_health_check(self):
        """Test health check endpoint"""
        print("\n=== Testing Health Check ===")
        response = self.make_request("GET", "/health")
        
        if response and response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                self.log_test("Health Check", True, "API is healthy and responding")
                return True
            else:
                self.log_test("Health Check", False, f"Unexpected response: {data}")
        else:
            status_code = response.status_code if response else "No response"
            self.log_test("Health Check", False, f"Health check failed with status: {status_code}")
        return False
    
    def test_company_settings(self):
        """Test company settings API"""
        print("\n=== Testing Company Settings API ===")
        
        # Test GET company settings (should return defaults if none exist)
        response = self.make_request("GET", "/company-settings")
        if not response or response.status_code != 200:
            self.log_test("Company Settings GET", False, f"Failed to get settings: {response.status_code if response else 'No response'}")
            return False
        
        settings_data = response.json()
        self.log_test("Company Settings GET", True, "Successfully retrieved company settings")
        
        # Test POST company settings
        test_settings = {
            "company_name": "Acme Corporation",
            "address": "123 Business St",
            "city": "New York",
            "state": "NY",
            "zip_code": "10001",
            "country": "USA",
            "phone": "+1-555-0123",
            "email": "info@acme.com",
            "website": "https://acme.com",
            "tax_number": "TAX123456",
            "default_tax_rate": 8.5,
            "default_payment_terms": "Net 30",
            "currency": "USD"
        }
        
        response = self.make_request("POST", "/company-settings", test_settings)
        if response and response.status_code == 200:
            self.log_test("Company Settings POST", True, "Successfully updated company settings")
            return True
        else:
            status_code = response.status_code if response else "No response"
            self.log_test("Company Settings POST", False, f"Failed to update settings: {status_code}")
            return False
    
    def test_customer_management(self):
        """Test customer CRUD operations"""
        print("\n=== Testing Customer Management API ===")
        
        # Test POST - Create customer
        test_customer = {
            "name": "John Smith",
            "email": "john.smith@example.com",
            "phone": "+1-555-0199",
            "company": "Smith Industries",
            "address": "456 Customer Ave",
            "city": "Los Angeles",
            "state": "CA",
            "zip_code": "90210",
            "country": "USA",
            "tax_number": "CUST789"
        }
        
        response = self.make_request("POST", "/customers", test_customer)
        if not response or response.status_code != 200:
            self.log_test("Customer CREATE", False, f"Failed to create customer: {response.status_code if response else 'No response'}")
            return False
        
        create_result = response.json()
        self.test_customer_id = create_result.get("customer_id")
        self.log_test("Customer CREATE", True, f"Successfully created customer with ID: {self.test_customer_id}")
        
        # Test GET all customers
        response = self.make_request("GET", "/customers")
        if not response or response.status_code != 200:
            self.log_test("Customer GET ALL", False, f"Failed to get customers: {response.status_code if response else 'No response'}")
            return False
        
        customers = response.json()
        if isinstance(customers, list) and len(customers) > 0:
            self.log_test("Customer GET ALL", True, f"Successfully retrieved {len(customers)} customers")
        else:
            self.log_test("Customer GET ALL", False, "No customers returned or invalid format")
            return False
        
        # Test GET specific customer
        if self.test_customer_id:
            response = self.make_request("GET", f"/customers/{self.test_customer_id}")
            if response and response.status_code == 200:
                customer_data = response.json()
                if customer_data.get("name") == test_customer["name"]:
                    self.log_test("Customer GET BY ID", True, "Successfully retrieved customer by ID")
                else:
                    self.log_test("Customer GET BY ID", False, "Customer data mismatch")
                    return False
            else:
                status_code = response.status_code if response else "No response"
                self.log_test("Customer GET BY ID", False, f"Failed to get customer by ID: {status_code}")
                return False
        
        # Test PUT - Update customer
        if self.test_customer_id:
            updated_customer = test_customer.copy()
            updated_customer["name"] = "John Smith Updated"
            updated_customer["customer_id"] = self.test_customer_id
            
            response = self.make_request("PUT", f"/customers/{self.test_customer_id}", updated_customer)
            if response and response.status_code == 200:
                self.log_test("Customer UPDATE", True, "Successfully updated customer")
            else:
                status_code = response.status_code if response else "No response"
                self.log_test("Customer UPDATE", False, f"Failed to update customer: {status_code}")
                return False
        
        return True
    
    def test_invoice_management(self):
        """Test invoice CRUD operations with line items and calculations"""
        print("\n=== Testing Invoice Management API ===")
        
        if not self.test_customer_id:
            self.log_test("Invoice Management", False, "No test customer available for invoice testing")
            return False
        
        # Test POST - Create invoice with line items
        test_invoice = {
            "invoice_number": f"INV-TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "customer_id": self.test_customer_id,
            "issue_date": date.today().isoformat(),
            "due_date": (date.today() + timedelta(days=30)).isoformat(),
            "status": "draft",
            "line_items": [
                {
                    "description": "Web Development Services",
                    "quantity": 40.0,
                    "unit_price": 75.0,
                    "tax_rate": 8.5
                },
                {
                    "description": "Domain Registration",
                    "quantity": 1.0,
                    "unit_price": 15.0,
                    "tax_rate": 0.0
                }
            ],
            "notes": "Thank you for your business!",
            "terms": "Payment due within 30 days"
        }
        
        response = self.make_request("POST", "/invoices", test_invoice)
        if not response or response.status_code != 200:
            self.log_test("Invoice CREATE", False, f"Failed to create invoice: {response.status_code if response else 'No response'}")
            return False
        
        create_result = response.json()
        self.test_invoice_id = create_result.get("invoice_id")
        self.log_test("Invoice CREATE", True, f"Successfully created invoice with ID: {self.test_invoice_id}")
        
        # Test GET specific invoice to verify calculations
        if self.test_invoice_id:
            response = self.make_request("GET", f"/invoices/{self.test_invoice_id}")
            if response and response.status_code == 200:
                invoice_data = response.json()
                
                # Verify calculations
                expected_subtotal = (40.0 * 75.0) + (1.0 * 15.0)  # 3015.0
                expected_tax = (40.0 * 75.0) * 0.085  # 255.0
                expected_total = expected_subtotal + expected_tax  # 3270.0
                
                actual_subtotal = invoice_data.get("subtotal", 0)
                actual_tax = invoice_data.get("tax_amount", 0)
                actual_total = invoice_data.get("total_amount", 0)
                
                if (abs(actual_subtotal - expected_subtotal) < 0.01 and 
                    abs(actual_tax - expected_tax) < 0.01 and 
                    abs(actual_total - expected_total) < 0.01):
                    self.log_test("Invoice Calculations", True, f"Calculations correct: Subtotal={actual_subtotal}, Tax={actual_tax}, Total={actual_total}")
                else:
                    self.log_test("Invoice Calculations", False, f"Calculation mismatch: Expected Total={expected_total}, Got={actual_total}")
                    return False
                
                self.log_test("Invoice GET BY ID", True, "Successfully retrieved invoice with customer data")
            else:
                status_code = response.status_code if response else "No response"
                self.log_test("Invoice GET BY ID", False, f"Failed to get invoice by ID: {status_code}")
                return False
        
        # Test GET all invoices
        response = self.make_request("GET", "/invoices")
        if response and response.status_code == 200:
            invoices = response.json()
            if isinstance(invoices, list):
                self.log_test("Invoice GET ALL", True, f"Successfully retrieved {len(invoices)} invoices")
            else:
                self.log_test("Invoice GET ALL", False, "Invalid invoice list format")
                return False
        else:
            status_code = response.status_code if response else "No response"
            self.log_test("Invoice GET ALL", False, f"Failed to get invoices: {status_code}")
            return False
        
        # Test PUT - Update invoice status
        if self.test_invoice_id:
            status_update = {"status": "sent"}
            response = self.make_request("PUT", f"/invoices/{self.test_invoice_id}/status", status_update)
            if response and response.status_code == 200:
                self.log_test("Invoice Status UPDATE", True, "Successfully updated invoice status")
            else:
                status_code = response.status_code if response else "No response"
                self.log_test("Invoice Status UPDATE", False, f"Failed to update invoice status: {status_code}")
                return False
        
        return True
    
    def test_pdf_generation(self):
        """Test PDF generation system - most complex feature"""
        print("\n=== Testing PDF Generation System ===")
        
        if not self.test_invoice_id:
            self.log_test("PDF Generation", False, "No test invoice available for PDF generation")
            return False
        
        response = self.make_request("GET", f"/invoices/{self.test_invoice_id}/pdf")
        
        if not response:
            self.log_test("PDF Generation", False, "No response from PDF endpoint")
            return False
        
        if response.status_code == 200:
            # Check if response is actually a PDF
            content_type = response.headers.get('content-type', '')
            content_disposition = response.headers.get('content-disposition', '')
            
            if 'application/pdf' in content_type:
                # Check if we got actual PDF content
                pdf_content = response.content
                if pdf_content and len(pdf_content) > 1000:  # PDF should be substantial
                    # Check PDF magic bytes
                    if pdf_content.startswith(b'%PDF'):
                        self.log_test("PDF Generation", True, f"Successfully generated PDF ({len(pdf_content)} bytes)")
                        
                        # Save PDF for manual verification if needed
                        try:
                            with open('/app/test_invoice.pdf', 'wb') as f:
                                f.write(pdf_content)
                            print("PDF saved as /app/test_invoice.pdf for verification")
                        except Exception as e:
                            print(f"Could not save PDF file: {e}")
                        
                        return True
                    else:
                        self.log_test("PDF Generation", False, "Response is not a valid PDF (missing PDF header)")
                else:
                    self.log_test("PDF Generation", False, f"PDF content too small ({len(pdf_content) if pdf_content else 0} bytes)")
            else:
                self.log_test("PDF Generation", False, f"Wrong content type: {content_type}")
        else:
            self.log_test("PDF Generation", False, f"PDF generation failed with status: {response.status_code}")
            if response.content:
                try:
                    error_data = response.json()
                    print(f"Error details: {error_data}")
                except:
                    print(f"Error response: {response.text}")
        
        return False
    
    def test_payment_tracking(self):
        """Test payment recording and invoice status updates"""
        print("\n=== Testing Payment Tracking API ===")
        
        if not self.test_invoice_id:
            self.log_test("Payment Tracking", False, "No test invoice available for payment testing")
            return False
        
        # Test POST - Record payment
        test_payment = {
            "invoice_id": self.test_invoice_id,
            "amount": 1500.0,  # Partial payment
            "payment_date": date.today().isoformat(),
            "payment_method": "Credit Card",
            "reference_number": "CC123456789",
            "notes": "Partial payment received"
        }
        
        response = self.make_request("POST", "/payments", test_payment)
        if not response or response.status_code != 200:
            self.log_test("Payment CREATE", False, f"Failed to record payment: {response.status_code if response else 'No response'}")
            return False
        
        payment_result = response.json()
        payment_id = payment_result.get("payment_id")
        self.log_test("Payment CREATE", True, f"Successfully recorded payment with ID: {payment_id}")
        
        # Test GET payments for invoice
        response = self.make_request("GET", f"/payments/invoice/{self.test_invoice_id}")
        if response and response.status_code == 200:
            payments = response.json()
            if isinstance(payments, list) and len(payments) > 0:
                self.log_test("Payment GET BY INVOICE", True, f"Successfully retrieved {len(payments)} payments for invoice")
            else:
                self.log_test("Payment GET BY INVOICE", False, "No payments found for invoice")
                return False
        else:
            status_code = response.status_code if response else "No response"
            self.log_test("Payment GET BY INVOICE", False, f"Failed to get payments: {status_code}")
            return False
        
        # Verify invoice payment status was updated
        response = self.make_request("GET", f"/invoices/{self.test_invoice_id}")
        if response and response.status_code == 200:
            invoice_data = response.json()
            amount_paid = invoice_data.get("amount_paid", 0)
            payment_status = invoice_data.get("payment_status", "")
            
            if amount_paid == 1500.0 and payment_status == "partial":
                self.log_test("Payment Status Update", True, f"Invoice payment status correctly updated: {payment_status}, Amount paid: {amount_paid}")
            else:
                self.log_test("Payment Status Update", False, f"Payment status not updated correctly: {payment_status}, Amount: {amount_paid}")
                return False
        else:
            self.log_test("Payment Status Update", False, "Could not verify invoice payment status update")
            return False
        
        return True
    
    def test_dashboard_analytics(self):
        """Test dashboard statistics and calculations"""
        print("\n=== Testing Dashboard Analytics API ===")
        
        # Test GET dashboard stats
        response = self.make_request("GET", "/dashboard/stats")
        if not response or response.status_code != 200:
            self.log_test("Dashboard Stats", False, f"Failed to get dashboard stats: {response.status_code if response else 'No response'}")
            return False
        
        stats = response.json()
        required_fields = [
            "total_customers", "total_invoices", "total_revenue", 
            "pending_amount", "overdue_amount", "paid_amount",
            "draft_count", "sent_count", "paid_count", "overdue_count"
        ]
        
        missing_fields = [field for field in required_fields if field not in stats]
        if missing_fields:
            self.log_test("Dashboard Stats", False, f"Missing required fields: {missing_fields}")
            return False
        
        # Verify data types and reasonable values
        numeric_fields = required_fields
        for field in numeric_fields:
            value = stats.get(field)
            if not isinstance(value, (int, float)) or value < 0:
                self.log_test("Dashboard Stats", False, f"Invalid value for {field}: {value}")
                return False
        
        self.log_test("Dashboard Stats", True, f"Dashboard stats valid: {stats['total_customers']} customers, {stats['total_invoices']} invoices, ${stats['total_revenue']:.2f} revenue")
        
        # Test GET recent invoices
        response = self.make_request("GET", "/dashboard/recent-invoices")
        if response and response.status_code == 200:
            recent_invoices = response.json()
            if isinstance(recent_invoices, list):
                self.log_test("Recent Invoices", True, f"Successfully retrieved {len(recent_invoices)} recent invoices")
            else:
                self.log_test("Recent Invoices", False, "Invalid recent invoices format")
                return False
        else:
            status_code = response.status_code if response else "No response"
            self.log_test("Recent Invoices", False, f"Failed to get recent invoices: {status_code}")
            return False
        
        return True
    
    def test_search_functionality(self):
        """Test search and filtering functionality"""
        print("\n=== Testing Search and Filtering API ===")
        
        # Test customer search
        response = self.make_request("GET", "/search/customers?q=John")
        if not response or response.status_code != 200:
            self.log_test("Customer Search", False, f"Failed to search customers: {response.status_code if response else 'No response'}")
            return False
        
        customer_results = response.json()
        if isinstance(customer_results, list):
            self.log_test("Customer Search", True, f"Customer search returned {len(customer_results)} results")
        else:
            self.log_test("Customer Search", False, "Invalid customer search results format")
            return False
        
        # Test invoice search
        response = self.make_request("GET", "/search/invoices?q=INV")
        if response and response.status_code == 200:
            invoice_results = response.json()
            if isinstance(invoice_results, list):
                self.log_test("Invoice Search", True, f"Invoice search returned {len(invoice_results)} results")
            else:
                self.log_test("Invoice Search", False, "Invalid invoice search results format")
                return False
        else:
            status_code = response.status_code if response else "No response"
            self.log_test("Invoice Search", False, f"Failed to search invoices: {status_code}")
            return False
        
        # Test empty search queries
        response = self.make_request("GET", "/search/customers?q=")
        if response and response.status_code == 200:
            empty_results = response.json()
            if isinstance(empty_results, list) and len(empty_results) == 0:
                self.log_test("Empty Search Query", True, "Empty search query handled correctly")
            else:
                self.log_test("Empty Search Query", False, "Empty search query not handled correctly")
                return False
        else:
            self.log_test("Empty Search Query", False, "Empty search query failed")
            return False
        
        return True
    
    def cleanup_test_data(self):
        """Clean up test data"""
        print("\n=== Cleaning Up Test Data ===")
        
        # Delete test invoice
        if self.test_invoice_id:
            response = self.make_request("DELETE", f"/invoices/{self.test_invoice_id}")
            if response and response.status_code == 200:
                print(f"✅ Deleted test invoice: {self.test_invoice_id}")
            else:
                print(f"⚠️ Could not delete test invoice: {self.test_invoice_id}")
        
        # Delete test customer
        if self.test_customer_id:
            response = self.make_request("DELETE", f"/customers/{self.test_customer_id}")
            if response and response.status_code == 200:
                print(f"✅ Deleted test customer: {self.test_customer_id}")
            else:
                print(f"⚠️ Could not delete test customer: {self.test_customer_id}")
    
    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Invoice Management Backend API Tests")
        print(f"Testing against: {self.base_url}")
        print("=" * 60)
        
        test_methods = [
            ("Health Check", self.test_health_check),
            ("Company Settings API", self.test_company_settings),
            ("Customer Management API", self.test_customer_management),
            ("Invoice Management API", self.test_invoice_management),
            ("PDF Generation System", self.test_pdf_generation),
            ("Payment Tracking API", self.test_payment_tracking),
            ("Dashboard Analytics API", self.test_dashboard_analytics),
            ("Search and Filtering API", self.test_search_functionality),
        ]
        
        passed_tests = 0
        total_tests = len(test_methods)
        
        for test_name, test_method in test_methods:
            try:
                if test_method():
                    passed_tests += 1
            except Exception as e:
                self.log_test(test_name, False, f"Test failed with exception: {str(e)}")
                print(f"❌ {test_name} failed with exception: {str(e)}")
        
        # Cleanup
        self.cleanup_test_data()
        
        # Summary
        print("\n" + "=" * 60)
        print("🏁 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED!")
        else:
            print("⚠️ Some tests failed. Check the details above.")
        
        return passed_tests, total_tests, self.test_results

if __name__ == "__main__":
    tester = InvoiceBackendTester()
    passed, total, results = tester.run_all_tests()