StockFlow Inventory Management System: Solution Document
Submission Instructions
1. Create a document with your responses to all three parts
2. Include reasoning for each decision you made
3. List assumptions you had to make due to incomplete requirements

Part 1: Code Review & Debugging
Issues Found
No input validation: Original code didn’t verify required fields, negative numbers, or correct data types.

No atomic transactions: Product and Inventory were created separately, risking orphan/incomplete records.

No uniqueness check for SKU: Allowed for duplicate SKUs.

Missing warehouse existence check: Could try to create inventory for non-existent warehouses.

No error handling: Crashes or 500 errors on bad input.

No handling for optional fields or decimal prices.

How I Fixed (and Improved)
Added input validation for all required fields, types, and negative check.

Ensured SKU is unique before create; returns 409 error if not.

Checked that referenced warehouse exists; returns 404 error if not.

Combined product and inventory insert into a single (atomic) transaction using db.session; on error, rolls back.

Returns clear error messages for all invalid data or database fails.

Uses Decimal for price, and integer for quantity, guarding for input types.

Reasoning
Input validation protects against corrupt/bad data.

Atomicity ensures consistency—products never "exist" without inventory.

Explicit errors make the API reliable and friendly for front-end/consumer code.

Database constraints (uniqueness, FKs) enforce business rules at a foundational level.

Part 2: Database Design
My Database Schema
Company: Organization unit (multi-tenancy support)

Warehouse: Belongs to a company; has an address.

Product: Unique SKU, price, optional low-stock threshold; can be single/bundle.

Supplier: For future sourcing (many-to-many with Product).

Inventory: Bridges Product and Warehouse; tracks per-warehouse stock.

InventoryLog: Planned for future audit trail.

SalesOrder & SalesOrderItem: Orders for sales activity, needed for low-stock alerting.

Why These Choices? (Reasoning)
Normalization: So there's no duplication and easy scaling.

Many-to-many (Supplier/Product): Real-world flexibility.

Uniqueness and FKs: Guarantee no orphaned/ambiguous data.

Extensible: Future features like bundles and order history are easy to add.

Part 3: API Implementation (Key Endpoints and Features)
Endpoints Implemented
POST /api/products

Creates a product and its inventory atomically

Validates all fields and returns clear messages if input is invalid or business rules are broken

GET /api/companies/<company_id>/alerts/low-stock

Reports all products per company with inventory below threshold (supports multiple warehouses)

Considers only those with recent sales activity (last 30 days)

POST /init-demo

(For demo/testing) Adds a company & warehouse to make API testable with Postman etc.

Reasoning
Product + inventory must be created together, never orphaned.

Alerts should only trigger for items with customer demand (recent sales).

A demo endpoint means anyone can test the app immediately, no manual data seeding needed.

Assumptions
Company and warehouse creation is handled via /init-demo for demonstration; full admin endpoints not required for prompt.

Low-stock threshold is set per product, not per warehouse.

No authentication/authorization required for this case study.

Bundles, suppliers, and sales order constructs are schema-ready but not required in endpoints.

“Recent sales activity” is defined as “sales in last 30 days”.
