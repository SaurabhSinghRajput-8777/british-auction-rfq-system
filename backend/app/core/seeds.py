from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.models import User, Supplier


def seed_demo_data(db: Session):
    """Populates initial demo Buyers and Carrier Suppliers if not already present."""
    if db.query(User).count() > 0:
        return

    now = datetime.now(timezone.utc)

    # 1. Buyers
    buyer1 = User(
        name="Global Retail Logistics (Alice Buyer)",
        email="alice@globalretail.com",
        role="BUYER",
        created_at=now,
    )
    buyer2 = User(
        name="Nexus Freight Corp (Bob Buyer)",
        email="bob@nexusfreight.com",
        role="BUYER",
        created_at=now,
    )
    db.add_all([buyer1, buyer2])
    db.flush()

    # 2. Suppliers
    s1_user = User(
        name="DHL Express Dispatcher",
        email="bids@dhl.com",
        role="SUPPLIER",
        created_at=now,
    )
    s2_user = User(
        name="FedEx Freight Dispatcher",
        email="quotes@fedex.com",
        role="SUPPLIER",
        created_at=now,
    )
    s3_user = User(
        name="Maersk Ocean Line",
        email="pricing@maersk.com",
        role="SUPPLIER",
        created_at=now,
    )
    s4_user = User(
        name="Kuehne+Nagel Logistics",
        email="tender@kuehne-nagel.com",
        role="SUPPLIER",
        created_at=now,
    )
    db.add_all([s1_user, s2_user, s3_user, s4_user])
    db.flush()

    sup1 = Supplier(user_id=s1_user.id, carrier_name="DHL Global Forwarding", is_active=True, created_at=now)
    sup2 = Supplier(user_id=s2_user.id, carrier_name="FedEx Freight Services", is_active=True, created_at=now)
    sup3 = Supplier(user_id=s3_user.id, carrier_name="Maersk Ocean Cargo", is_active=True, created_at=now)
    sup4 = Supplier(user_id=s4_user.id, carrier_name="Kuehne+Nagel Intermodal", is_active=True, created_at=now)
    db.add_all([sup1, sup2, sup3, sup4])
    db.commit()
