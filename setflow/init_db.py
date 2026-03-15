from .db import ENGINE, SessionLocal
from .models import Base, Department, Surgery, Item, ProcedureDefault, SetInstance


def ensure_db():
    Base.metadata.drop_all(ENGINE)
    Base.metadata.create_all(ENGINE)

    with SessionLocal() as db:
        # Departments
        gs = Department(name="GS", active=True)
        ns = Department(name="NS", active=True)
        os = Department(name="OS", active=True)
        db.add_all([gs, ns, os])
        db.commit()

        # Surgeries
        surgeries = [
            Surgery(name="Appendectomy", department_id=gs.id, active=True),
            Surgery(name="Cholecystectomy", department_id=gs.id, active=True),
            Surgery(name="THA", department_id=os.id, active=True),
            Surgery(name="TKA", department_id=os.id, active=True),
            Surgery(name="Craniotomy", department_id=ns.id, active=True),
            Surgery(name="CEA", department_id=ns.id, active=True),
        ]
        db.add_all(surgeries)
        db.commit()

        # Items
        items = [
            Item(code="SET001", name="GS Minor Set", kind="set", category="GS", storage="멸균물품실", status="멸균완료/보관", active=True),
            Item(code="SET002", name="Hip Tray", kind="set", category="OS", storage="멸균물품실", status="멸균완료/보관", active=True),
            Item(code="SET003", name="Femur Set", kind="set", category="OS", storage="멸균물품실", status="멸균완료/보관", active=True),
            Item(code="SET004", name="Tibia Set", kind="set", category="OS", storage="멸균물품실", status="멸균완료/보관", active=True),
            Item(code="SET005", name="Brain Set", kind="set", category="NS", storage="멸균물품실", status="멸균완료/보관", active=True),
            Item(code="INS001", name="Kelly", kind="instrument", category="GS", storage="멸균물품실", status="멸균완료/보관", active=True),
            Item(code="INS002", name="Mosquito", kind="instrument", category="GS", storage="멸균물품실", status="멸균완료/보관", active=True),
            Item(code="INS003", name="Babcock", kind="instrument", category="GS", storage="멸균물품실", status="멸균완료/보관", active=True),
            Item(code="INS004", name="Mayo", kind="instrument", category="OS", storage="멸균물품실", status="멸균완료/보관", active=True),
            Item(code="INS005", name="Metzenbaum", kind="instrument", category="OS", storage="멸균물품실", status="멸균완료/보관", active=True),
            Item(code="INS006", name="Kocher", kind="instrument", category="OS", storage="멸균물품실", status="멸균완료/보관", active=True),
            Item(code="INS007", name="Adson", kind="instrument", category="일반", storage="멸균물품실", status="멸균완료/보관", active=True),
            Item(code="INS008", name="Curette", kind="instrument", category="일반", storage="멸균물품실", status="멸균완료/보관", active=True),
        ]
        db.add_all(items)
        db.commit()

        item_by_name = {item.name: item for item in db.query(Item).all()}

        # Set instances
        instances = [
            SetInstance(set_item_id=item_by_name["GS Minor Set"].id, serial_no=1),
            SetInstance(set_item_id=item_by_name["GS Minor Set"].id, serial_no=2, memo="Babcock 없음", is_available=False),
            SetInstance(set_item_id=item_by_name["Hip Tray"].id, serial_no=1),
            SetInstance(set_item_id=item_by_name["Hip Tray"].id, serial_no=2, memo="reamer 수리중", is_available=False),
            SetInstance(set_item_id=item_by_name["Femur Set"].id, serial_no=1),
            SetInstance(set_item_id=item_by_name["Femur Set"].id, serial_no=2, memo="distal reamer 없음", is_available=False),
            SetInstance(set_item_id=item_by_name["Femur Set"].id, serial_no=3),
            SetInstance(set_item_id=item_by_name["Tibia Set"].id, serial_no=1),
            SetInstance(set_item_id=item_by_name["Tibia Set"].id, serial_no=2),
            SetInstance(set_item_id=item_by_name["Brain Set"].id, serial_no=1),
        ]
        db.add_all(instances)
        db.commit()

        # Procedure defaults: store master set names only
        surgery_by_name = {s.name: s for s in db.query(Surgery).all()}
        defaults = [
            ("Appendectomy", "GS Minor Set"), ("Appendectomy", "Kelly"), ("Appendectomy", "Mosquito"), ("Appendectomy", "Babcock"),
            ("Cholecystectomy", "GS Minor Set"), ("Cholecystectomy", "Kelly"), ("Cholecystectomy", "Mosquito"),
            ("THA", "Hip Tray"), ("THA", "Femur Set"), ("THA", "Mayo"), ("THA", "Kocher"),
            ("TKA", "Femur Set"), ("TKA", "Tibia Set"), ("TKA", "Mayo"), ("TKA", "Metzenbaum"),
            ("Craniotomy", "Brain Set"), ("Craniotomy", "Adson"),
            ("CEA", "Brain Set"), ("CEA", "Adson"),
        ]
        for surg_name, item_name in defaults:
            db.add(ProcedureDefault(surgery_id=surgery_by_name[surg_name].id, item_id=item_by_name[item_name].id))
        db.commit()

    print("DB 초기화 + 세트번호 시드 완료")


if __name__ == "__main__":
    ensure_db()
