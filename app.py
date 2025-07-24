from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from decimal import Decimal
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELS ---
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

class Warehouse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.Text)

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    contact_email = db.Column(db.String(255))

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    type = db.Column(db.String(20), default='single')
    low_stock_threshold = db.Column(db.Integer, default=10)

class ProductSupplier(db.Model):
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), primary_key=True)

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    __table_args__ = (db.UniqueConstraint('product_id', 'warehouse_id', name='uq_product_warehouse'), )

class InventoryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'), nullable=False)
    change = db.Column(db.Integer)
    reason = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SalesOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SalesOrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

with app.app_context():
    db.create_all()

# --- ROUTES ---

# TEMP: Initialize demo company and warehouse (for easy testing)
@app.route('/init-demo', methods=['POST'])
def init_demo():
    if not Company.query.first():
        company = Company(name="Demo Co")
        db.session.add(company)
        db.session.commit()
    else:
        company = Company.query.first()
    if not Warehouse.query.filter_by(company_id=company.id).first():
        warehouse = Warehouse(company_id=company.id, name="Main Warehouse", address="123 Demo St")
        db.session.add(warehouse)
        db.session.commit()
    else:
        warehouse = Warehouse.query.filter_by(company_id=company.id).first()
    return jsonify({"company_id": company.id, "warehouse_id": warehouse.id})

@app.route('/api/products', methods=['POST'])
def create_product():
    data = request.get_json() or {}
    required = ['name', 'sku', 'price', 'warehouse_id', 'initial_quantity']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'error': f'Missing fields: {missing}'}), 400
    try:
        price = Decimal(str(data['price']))
        initial_qty = int(data['initial_quantity'])
        if initial_qty < 0:
            return jsonify({'error': 'Initial quantity cannot be negative'}), 400
        if Product.query.filter_by(sku=data['sku']).first():
            return jsonify({'error': 'SKU already exists'}), 409
        warehouse = Warehouse.query.get(data['warehouse_id'])
        if not warehouse:
            return jsonify({'error': 'Warehouse not found'}), 404
        product = Product(
            name=data['name'],
            sku=data['sku'],
            price=price
        )
        db.session.add(product)
        db.session.flush()
        inventory = Inventory(
            product_id=product.id,
            warehouse_id=data['warehouse_id'],
            quantity=initial_qty
        )
        db.session.add(inventory)
        db.session.commit()
        return jsonify({"message": "Product created", "product_id": product.id}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Database error'}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/api/companies/<int:company_id>/alerts/low-stock', methods=['GET'])
def low_stock_alerts(company_id):
    recent_days = 30
    now = datetime.utcnow()
    start_date = now - timedelta(days=recent_days)
    alerts = []
    total_alerts = 0
    warehouses = Warehouse.query.filter_by(company_id=company_id).all()
    for wh in warehouses:
        inventories = Inventory.query.filter_by(warehouse_id=wh.id).all()
        for inv in inventories:
            product = Product.query.get(inv.product_id)
            threshold = product.low_stock_threshold or 10
            sales = (
                db.session.query(func.sum(SalesOrderItem.quantity))
                .join(SalesOrder, SalesOrderItem.sales_order_id == SalesOrder.id)
                .filter(SalesOrderItem.product_id == product.id)
                .filter(SalesOrder.company_id == company_id)
                .filter(SalesOrder.created_at >= start_date)
                .scalar()
            ) or 0
            if sales == 0 or inv.quantity >= threshold:
                continue
            sales_rate = sales / recent_days if sales else 0
            days_until_stockout = int(inv.quantity / sales_rate) if sales_rate else None
            supplier = (Supplier.query
                .join(ProductSupplier, ProductSupplier.supplier_id == Supplier.id)
                .filter(ProductSupplier.product_id == product.id)
                .first()
            )
            supplier_info = {
                'id': supplier.id,
                'name': supplier.name,
                'contact_email': supplier.contact_email
            } if supplier else None
            alerts.append({
                'product_id': product.id,
                'product_name': product.name,
                'sku': product.sku,
                'warehouse_id': wh.id,
                'warehouse_name': wh.name,
                'current_stock': inv.quantity,
                'threshold': threshold,
                'days_until_stockout': days_until_stockout,
                'supplier': supplier_info
            })
            total_alerts += 1
    return jsonify({"alerts": alerts, "total_alerts": total_alerts})

if __name__ == '__main__':
    app.run(debug=True)
