import frappe
import json
from frappe import _
from frappe.utils import logger

@frappe.whitelist(allow_guest=True)
def test():
    print("OK")


@frappe.whitelist(allow_guest=True)
def sync_master_document():
    try:
        data = frappe.request.get_json()
        doctype = data.get("doctype")
        docname = data.get("name")
        sync_flag = data.get("sync")

        if not doctype or not docname:
            return {"error": "doctype and name are required"}

        if doctype not in ["Customer", "Supplier", "Customer Group", "Item", "Address", "Contact"]:
            return {"error": f"Doctype '{doctype}' is not allowed for sync"}

        if frappe.db.exists(doctype, docname):
            doc = frappe.get_doc(doctype, docname)
            doc.update(data)
            doc.save()
            return {"status": "updated", "doctype": doctype, "name": docname}
        else:
            doc = frappe.new_doc(doctype)
            doc.update(data)
            doc.insert()
            return {"status": "created", "doctype": doctype, "name": doc.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Data Sync Failed")
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def sync_document():
    try:
        data = frappe.request.get_json()
        doctype = data.get("doctype")
        docname = data.get("name")
        fields = data.get("fields", {})
        links = data.get("links", [])

        if not doctype:
            return {"error": "doctype is required"}

        if docname and frappe.db.exists(doctype, docname):
            doc = frappe.get_doc(doctype, docname)
            doc.update(fields)
        else:
            doc = frappe.new_doc(doctype)
            doc.update(fields)

        doc.save()

        for link in links:
            link_doctype = link.get("doctype")
            link_fields = link.get("data", {})
            if not link_doctype:
                continue

            if link_doctype == "Address":
                create_or_update_address(link_fields, doc)
            elif link_doctype == "Contact":
                create_or_update_contact(link_fields, doc)

        return {
            "status": "success",
            "doctype": doctype,
            "name": doc.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Dynamic Sync Failed")
        return {"error": str(e)}


@frappe.whitelist(allow_guest=True)
def sync_sales_invoice():
    try:
        data = frappe.request.get_json()
        doctype = data.get("doctype")
        docname = data.get("name")

        if doctype != "Sales Invoice":
            return {"error": "This endpoint only accepts Sales Invoice"}

        customer_name = data.get("customer")
        if not customer_name:
            return {"error": "Sales Invoice must include customer"}

        customer = frappe.get_doc("Customer", customer_name)

        if not customer.get("custom_sync"):
            return {"skipped": True, "reason": "Customer.custom_sync is not true"}

        if frappe.db.exists("Sales Invoice", {"custom_sync_ref_no": docname}):
            existing_docname = frappe.db.get_value("Sales Invoice", {"custom_sync_ref_no": docname}, "name")
            return {
                "status_code": "2",
                "status": "Already Exists",
                "doctype": "Sales Invoice",
                "name": existing_docname
            }
        else:
            doc = frappe.new_doc("Sales Invoice")
            doc.update(data)
            doc.insert()
            return {
                "status_code": "1",
                "status": "created",
                "doctype": "Sales Invoice",
                "name": doc.name
            }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "sync_sales_invoice failed")
        return {"status_code": "0", "error": str(e)}


@frappe.whitelist(allow_guest=False)
def create_or_update_address_and_contact_api():
    try:
        data = frappe.request.get_json()
        if not data:
            return {"status": "error", "message": "No JSON data received."}

        return create_or_update_address_and_contact(data)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Address/Contact Sync Error")
        return {"status": "error", "message": str(e)}


def create_or_update_address_and_contact(data):
    customer_name = data.get("customer")
    if not customer_name:
        return {"status": "error", "message": "Customer name is required."}

    address_data = data.get("address")
    address_doc = None

    if address_data:
        address_name = address_data.get("name")

        if address_name and frappe.db.exists("Address", address_name):
            address_doc = frappe.get_doc("Address", address_name)
        elif address_data.get("address_title"):
            existing = frappe.get_all("Address", filters={"address_title": address_data.get("address_title")}, fields=["name"])

            for item in existing:
                possible_doc = frappe.get_doc("Address", item.name)
                if any(link.link_doctype == "Customer" and link.link_name == customer_name for link in possible_doc.links):
                    address_doc = possible_doc
                    break

        if not address_doc:
            address_doc = frappe.new_doc("Address")

        address_doc.update(address_data)
        address_doc.set("links", [])
        address_doc.append("links", {
            "link_doctype": "Customer",
            "link_name": customer_name
        })
        address_doc.save(ignore_permissions=True)

    contact_data = data.get("contact")
    contact_doc = None

    if contact_data:
        contact_name = contact_data.get("name")

        if contact_name and frappe.db.exists("Contact", contact_name):
            contact_doc = frappe.get_doc("Contact", contact_name)
        else:
            contact_doc = frappe.new_doc("Contact")

        contact_doc.update(contact_data)
        contact_doc.set("links", [])
        contact_doc.append("links", {
            "link_doctype": "Customer",
            "link_name": customer_name
        })
        contact_doc.save(ignore_permissions=True)

    frappe.db.commit()
    return {"status": "success", "message": "Address and Contact processed"}


@frappe.whitelist(allow_guest=True)
def sync_master_woflag():
    try:
        data = frappe.request.get_json()
        doctype = data.get("doctype")
        docname = data.get("name")
        sync_flag = data.get("sync")

        if not doctype or not docname:
            return {"error": "doctype and name are required"}

        allowed_doctypes = ["Customer", "Supplier", "Customer Group", "Item", "Address", "Contact", "Item Group"]

        if doctype not in allowed_doctypes:
            return {"error": f"Doctype '{doctype}' is not allowed for sync"}

        if doctype not in ["Customer Group", "Item", "Item Group", "Supplier"] and not sync_flag:
            return {"error": "'sync' field is required for this doctype"}

        if frappe.db.exists(doctype, docname):
            doc = frappe.get_doc(doctype, docname)
            doc.update(data)
            doc.save()
            return {"status": "updated", "doctype": doctype, "name": docname}
        else:
            doc = frappe.new_doc(doctype)
            doc.update(data)
            doc.insert()
            return {"status": "created", "doctype": doctype, "name": doc.name}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Data Sync Failed")
        return {"error": str(e)}
