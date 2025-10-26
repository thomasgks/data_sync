import frappe
from frappe import _
from frappe.utils import logger
from frappe.utils.data import get_request_form_dict

@frappe.whitelist(allow_guest=True)
def sync_test():
    return {"status": "success", "message": "Webhook received"}

@frappe.whitelist(allow_guest=True)
def sync_customer():
    try:
        # Parse data from JSON or form-urlencoded
        if frappe.request.content_type == "application/json":
            data = frappe.request.get_json()
        else:
            data = get_request_form_dict()

        # Log incoming data for debugging
        frappe.log_error("Incoming Customer Webhook", str(data))

        customer_name = data.get("customer_name")
        custom_code = data.get("custom_code")

        if not customer_name or not custom_code:
            return {"status": "error", "message": "Missing 'customer_name' or 'custom_code'"}

        existing_customer = frappe.db.exists("Customer", {"custom_code": custom_code})

        if existing_customer:
            # Update existing
            doc = frappe.get_doc("Customer", existing_customer)
            doc.update(data)
            doc.save()
            operation = "updated"
        else:
            # Create new
            doc = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": customer_name,
                "custom_code": custom_code,
                "customer_type": data.get("customer_type", "Individual"),
                "customer_group": data.get("customer_group", "Commercial"),
                "territory": data.get("territory", "All Territories")
            })
            doc.insert()
            operation = "created"

        frappe.db.commit()

        return {
            "status": "success",
            "operation": operation,
            "customer": doc.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Customer Sync Error")
        return {
            "status": "error",
            "message": str(e)
        }