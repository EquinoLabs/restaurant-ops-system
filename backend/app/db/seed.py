from decimal import Decimal
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.modules.businesses.models import Business
from app.modules.outlets.models import Outlet
from app.modules.menus.models import MenuCategory, MenuItem


def seed_database(db: Session):
    # Create or fetch Business
    business = db.query(Business).filter_by(name="Himachal Hospitality Group").first()
    if not business:
        business = Business(
            name="Himachal Hospitality Group",
            status="active"
        )
        db.add(business)
        db.commit()
        db.refresh(business)

    # 1. Riverside Camp Outlet
    camp_outlet = db.query(Outlet).filter_by(public_slug="riverside-camp").first()
    if not camp_outlet:
        camp_outlet = Outlet(
            business_id=business.id,
            name="Riverside Camp Restaurant",
            public_slug="riverside-camp",
            timezone="Asia/Kolkata",
            currency="INR",
            address="Beas River Bank, Near Kasol, Himachal Pradesh",
            status="active"
        )
        db.add(camp_outlet)
        db.commit()
        db.refresh(camp_outlet)

        # Categories for Camp Outlet
        cat_starters = MenuCategory(
            outlet_id=camp_outlet.id,
            name="Campstarters & Snacks",
            description="Crispy, hot appetizers for cold mountain evenings",
            sort_order=1
        )
        cat_mains = MenuCategory(
            outlet_id=camp_outlet.id,
            name="Himachali Main Course",
            description="Authentic Himachali curries and dal cooked with local herbs",
            sort_order=2
        )
        cat_beverages = MenuCategory(
            outlet_id=camp_outlet.id,
            name="Hot & Cold Beverages",
            description="Freshly brewed mountain teas and refreshing drinks",
            sort_order=3
        )
        db.add_all([cat_starters, cat_mains, cat_beverages])
        db.commit()

        # Items for Camp Outlet
        items = [
            MenuItem(
                outlet_id=camp_outlet.id,
                category_id=cat_starters.id,
                name="Trout Fish Fry",
                description="Fresh river trout marinated in local spices and shallow fried to crispy perfection",
                price=Decimal("450.00"),
                is_available=True,
                sort_order=1
            ),
            MenuItem(
                outlet_id=camp_outlet.id,
                category_id=cat_starters.id,
                name="Vegetable Siddu Bites",
                description="Traditional steamed wheat bread stuffed with spiced poppy seeds and dry fruits",
                price=Decimal("180.00"),
                is_available=True,
                sort_order=2
            ),
            MenuItem(
                outlet_id=camp_outlet.id,
                category_id=cat_mains.id,
                name="Traditional Himachali Dham Thali",
                description="Full thali featuring Madra, Chana Khatta, Kadi, Rice, and Meetha Bhaat",
                price=Decimal("320.00"),
                is_available=True,
                sort_order=1
            ),
            MenuItem(
                outlet_id=camp_outlet.id,
                category_id=cat_mains.id,
                name="Pahadi Mutton Curry",
                description="Slow-cooked goat meat cooked in clay pot with rustic Pahadi spices",
                price=Decimal("520.00"),
                is_available=True,
                sort_order=2
            ),
            MenuItem(
                outlet_id=camp_outlet.id,
                category_id=cat_beverages.id,
                name="Rhododendron (Buransh) Juice",
                description="Fresh organic wild flower nectar juice served chilled",
                price=Decimal("120.00"),
                is_available=True,
                sort_order=1
            ),
            MenuItem(
                outlet_id=camp_outlet.id,
                category_id=cat_beverages.id,
                name="Spiced Himalayan Ginger Honey Tea",
                description="Hot herbal infusion with local ginger, wild honey, and green cardamom",
                price=Decimal("90.00"),
                is_available=True,
                sort_order=2
            ),
        ]
        db.add_all(items)
        db.commit()

    # 2. Traditional Town Restaurant Outlet
    town_outlet = db.query(Outlet).filter_by(public_slug="town-restaurant").first()
    if not town_outlet:
        town_outlet = Outlet(
            business_id=business.id,
            name="Heritage Town Restaurant",
            public_slug="town-restaurant",
            timezone="Asia/Kolkata",
            currency="INR",
            address="Mall Road, Kullu, Himachal Pradesh",
            status="active"
        )
        db.add(town_outlet)
        db.commit()
        db.refresh(town_outlet)

        cat_town_mains = MenuCategory(
            outlet_id=town_outlet.id,
            name="Classic Indian Mains",
            description="Rich, aromatic gravies and freshly baked breads",
            sort_order=1
        )
        db.add(cat_town_mains)
        db.commit()

        db.add(
            MenuItem(
                outlet_id=town_outlet.id,
                category_id=cat_town_mains.id,
                name="Paneer Butter Masala",
                description="Cottage cheese cubes simmered in rich tomato butter gravy",
                price=Decimal("280.00"),
                is_available=True,
                sort_order=1
            )
        )
        db.commit()

    # 3. Seed Demo Staff Users & Memberships
    from app.modules.staff.models import User, OutletMembership
    from app.core.security import hash_password

    admin_user = db.query(User).filter_by(email="admin@himachalhospitality.com").first()
    if not admin_user:
        admin_user = User(
            email="admin@himachalhospitality.com",
            password_hash=hash_password("admin123"),
            display_name="Himachali Admin",
            status="active"
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        # Assign owner access to both outlets
        db.add_all([
            OutletMembership(user_id=admin_user.id, outlet_id=camp_outlet.id, role="owner"),
            OutletMembership(user_id=admin_user.id, outlet_id=town_outlet.id, role="owner"),
        ])
        db.commit()

    manager_user = db.query(User).filter_by(email="manager@riverside.com").first()
    if not manager_user:
        manager_user = User(
            email="manager@riverside.com",
            password_hash=hash_password("manager123"),
            display_name="Riverside Manager",
            status="active"
        )
        db.add(manager_user)
        db.commit()
        db.refresh(manager_user)

        # Assign manager access to Riverside Camp
        db.add(OutletMembership(user_id=manager_user.id, outlet_id=camp_outlet.id, role="manager"))
        db.commit()

    waiter_user = db.query(User).filter_by(email="waiter@riverside.com").first()
    if not waiter_user:
        waiter_user = User(
            email="waiter@riverside.com",
            password_hash=hash_password("waiter123"),
            display_name="Riverside Waiter Staff",
            status="active"
        )
        db.add(waiter_user)
        db.commit()
        db.refresh(waiter_user)

        # Assign waiter access to Riverside Camp
        db.add(OutletMembership(user_id=waiter_user.id, outlet_id=camp_outlet.id, role="waiter"))
        db.commit()

    town_manager = db.query(User).filter_by(email="manager@town.com").first()
    if not town_manager:
        town_manager = User(
            email="manager@town.com",
            password_hash=hash_password("manager123"),
            display_name="Town Restaurant Manager",
            status="active"
        )
        db.add(town_manager)
        db.commit()
        db.refresh(town_manager)

        # Assign manager access to Heritage Town Restaurant
        db.add(OutletMembership(user_id=town_manager.id, outlet_id=town_outlet.id, role="manager"))
        db.commit()

    print("Seed data successfully created!")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()

